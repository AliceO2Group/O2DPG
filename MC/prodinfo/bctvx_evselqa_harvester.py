#!/usr/bin/env python3
"""
PyROOT pipeline to:
 - parse file paths like ./LHC25as/cpass0/568664/AnalysisResults.root
 - choose highest-priority pass per run
 - extract histogram event-selection-qa-task/hBcTVX
 - hash histogram to prevent duplicates
 - write upload ROOT file
 - upload using o2-ccdb-upload (or optionally call o2::CcdbApi from C++)


Usage:
  python3 upload_pipeline.py --file-list files.txt
  OR
  python3 upload_pipeline.py ./LHC25as/*/*/*/AnalysisResults.root
"""

import os
import sys
import json
import argparse
import hashlib
import tempfile
import subprocess
from collections import defaultdict

# PyROOT import
import ROOT
from ROOT import o2 # for O2 access

# -------- user config ----------
# priority: earlier in list -> higher priority
PASS_PRIORITY = ["apass6", "apass5", "apass4", "apass3", "apass2", "apass1", "cpass0"]

# path inside AnalysisResults.root to histogram
HIST_PATH = "event-selection-qa-task/hBcTVX"

# Local JSON file storing processed histogram hashes to avoid duplicates
PROCESSED_HASH_DB = "processed_hashes.json"

def getRunInformation(runnumber):
    runInfo = o2.parameters.AggregatedRunInfo.buildAggregatedRunInfo(o2.ccdb.BasicCCDBManager.instance(), runnumber)
    return {"SOR" : runInfo.sor,
            "EOR" : runInfo.eor}
    

def make_ccdb_upload_command(localfile, passname, runnumber, sor, eor, key="ccdb_object"):
  l = [
    "o2-ccdb-upload",
    "--host", "http://ccdb-test.cern.ch:8080",   # <-- adapt to your CCDB server
    "--path", "GLO/CALIB/EVSELQA/HBCTVX",              # will be filled per-run
    "--file", f"{localfile}",                         # will be replaced with filename
    "-k", f"{key}",
    "-m", f"run_number={runnumber};pass={passname}",  # no extra quotes here (only needed on shell)
    "--starttimestamp", f"{sor}",
    "--endtimestamp", f"{eor}",
  ]
  return l # " ".join(l)

# -------------------------------
def load_processed_db(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    else:
        return {"hashes": []}


def save_processed_db(path, db):
    with open(path, "w") as f:
        json.dump(db, f, indent=2)


def parse_path_meta(filepath):
    """
    Find a pattern */<period>/<pass>/<run>/AnalysisResults.root anywhere in the path.
    Returns {period, pass, run}.

    Example accepted paths:
      ./LHC25as/cpass0/568664/AnalysisResults.root
      /tmp/foo/2023/LHC23zzh/cpass0/544095/AnalysisResults.root
    """
    p = os.path.normpath(filepath)
    parts = p.split(os.sep)

    # Find the index of AnalysisResults.root
    try:
        idx = parts.index("AnalysisResults.root")
    except ValueError:
        # maybe something like analysisresults.root? Lowercase?
        # Try case-insensitive fallback
        idx = None
        for i, comp in enumerate(parts):
            if comp.lower() == "analysisresults.root":
                idx = i
                break
        if idx is None:
            raise ValueError(f"File does not contain AnalysisResults.root: {filepath}")

    # Need at least 3 dirs before it: period, pass, run
    if idx < 3:
        raise ValueError(f"Cannot extract period/pass/run from short path: {filepath}")

    run      = parts[idx-1]
    passname = parts[idx-2]
    period   = parts[idx-3]

    # Optional sanity checks
    if not run.isdigit():
        raise ValueError(f"Run number is not numeric: '{run}' in path {filepath}")

    return {"period": period, "pass": passname, "run": run}


def pass_priority_rank(pass_name):
    try:
        return PASS_PRIORITY.index(pass_name)
    except ValueError:
        # unknown pass name -> low priority (append at end)
        return len(PASS_PRIORITY)


def pick_best_pass_file(files_for_run):
    """
    files_for_run: list of dicts with keys {pass, path, period}
    returns the dict for the chosen file (highest priority)
    """
    # sort by priority (lower index -> higher preference)
    files_sorted = sorted(files_for_run, key=lambda x: pass_priority_rank(x["pass"]))
    return files_sorted[0] if files_sorted else None


def histogram_hash(hist):
    """
    Deterministic hash of a TH1* content:
     - axis nbins, xmin, xmax
     - bin contents + bin errors
    Returns hex sha256 string.
    """
    h = hist
    nbins = h.GetNbinsX()
    xmin = h.GetXaxis().GetXmin()
    xmax = h.GetXaxis().GetXmax()
    # collect values
    m = hashlib.sha256()
    m.update(f"{nbins}|{xmin}|{xmax}|{h.GetName()}|{h.GetTitle()}".encode("utf-8"))
    for b in range(0, nbins + 2):  # include under/overflow
        c = float(h.GetBinContent(b))
        e = float(h.GetBinError(b))
        m.update(f"{b}:{c:.17g}:{e:.17g};".encode("utf-8"))
    return m.hexdigest()


def extract_histogram_from_file(root_path, hist_path):
    """
    Returns a clone of the TH1 found at hist_path or raises on error.
    """
    f = ROOT.TFile.Open(root_path, "READ")
    if not f or f.IsZombie():
        raise IOError(f"Cannot open file {root_path}")
    obj = f.Get(hist_path)
    if not obj:
        f.Close()
        raise KeyError(f"Histogram {hist_path} not found in {root_path}")
    if not isinstance(obj, ROOT.TH1):
        f.Close()
        raise TypeError(f"Object at {hist_path} is not a TH1 (found {type(obj)}) in {root_path}")
    # clone to decouple from file and then close file
    clone = obj.Clone(obj.GetName())
    clone.SetDirectory(0)
    f.Close()
    return clone


def write_upload_root(hist, meta, outpath):
    """
    Writes histogram and metadata (as a TObjString) into a new ROOT file for uploading.
    meta: dict of metadata (period, pass, run, runinfo, hash)
    """
    f = ROOT.TFile(outpath, "RECREATE")
    f.cd()
    # set name to include run for clarity
    hist_copy = hist.Clone(hist.GetName())
    hist_copy.SetDirectory(f)
    hist_copy.Write()
    # write metadata as JSON inside TObjString
    json_meta = json.dumps(meta)
    sobj = ROOT.TObjString(json_meta)
    sobj.Write("metadata")
    f.Close()


def upload_ccdb_via_cli(upload_file, ccdb_path, passname, runnumber, sor, eor):
    """
    Call o2-ccdb-upload CLI with CCDB_UPLOAD_CMD template.
    Adjust template above for your environment if needed.
    """
    cmd = make_ccdb_upload_command(upload_file, passname, runnumber, sor, eor, key="hBcTVX")
    print("Running upload command:", " ".join(cmd))
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        # raise RuntimeError(f"o2-ccdb-upload failed: {res.returncode}\nstdout:{res.stdout}\nstderr:{res.stderr}")
        print (f"o2-ccdb-upload failed: {res.returncode}\nstdout:{res.stdout}\nstderr:{res.stderr}")
        return False
    
    print (f"o2-ccdb-upload succeeded: {res.returncode}\nstdout:{res.stdout}\nstderr:{res.stderr}")
    return True


def main(argv):
    parser = argparse.ArgumentParser(description="Extract histogram from AnalysisResults.root and upload to CCDB")
    parser.add_argument("--file-list", help="Text file with one file path per line (or '-')", default=None)
    parser.add_argument("paths", nargs="*", help="globs or paths to AnalysisResults.root files")
    parser.add_argument("--skip-upload", action="store_true", help="Only create upload ROOT files, do not call o2-ccdb-upload")
    parser.add_argument("--out-dir", default="ccdb_uploads", help="Where to put temporary upload ROOT files")
    parser.add_argument("--processed-db", default=PROCESSED_HASH_DB, help="JSON file to keep processed-hashes")
    parser.add_argument("--ccdb-base-path", default="/calibration/hBcTVX", help="Base path inside CCDB where to upload")
    args = parser.parse_args(argv)

    # collect files
    file_paths = []
    if args.file_list:
        if args.file_list == "-":
            lines = sys.stdin.read().splitlines()
        else:
            with open(args.file_list, "r") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
        file_paths.extend(lines)
    if args.paths:
        # expand globs
        import glob
        for p in args.paths:
            file_paths.extend(sorted(glob.glob(p)))
    if not file_paths:
        print("No files provided. Exiting.")
        return 1

    # build per-run grouping
    runs = defaultdict(list)
    for p in file_paths:
        try:
            meta = parse_path_meta(p)
        except Exception as e:
            print(f"Skipping {p}: cannot parse path: {e}")
            continue
        runs[meta["run"]].append({"path": p, "pass": meta["pass"], "period": meta["period"]})

    # load processed DB
    db = load_processed_db(args.processed_db)
    processed_hashes = set(db.get("hashes", []))

    os.makedirs(args.out_dir, exist_ok=True)

    for run, filelist in runs.items():
        selected = pick_best_pass_file(filelist)
        if not selected:
            print(f"No candidate for run {run}, skipping.")
            continue
        path = selected["path"]
        period = selected["period"]
        pass_name = selected["pass"]
        print(f"Selected for run {run}: {path} (period={period}, pass={pass_name})")

        try:
            hist = extract_histogram_from_file(path, HIST_PATH)
        except Exception as e:
            print(f"Failed to extract histogram from {path}: {e}")
            continue

        # compute hash
        hsh = histogram_hash(hist)
        if hsh in processed_hashes:
            print(f"Histogram hash {hsh} for run {run} already processed -> skipping upload.")
            continue

        # get run information
        runinfo = getRunInformation(int(run))
        
        # prepare metadata
        meta = {
            "period": period,
            "pass": pass_name,
            "run": run,
            "runinfo": runinfo,
            "hist_name": hist.GetName(),
            "hist_title": hist.GetTitle(),
            "hash": hsh
        }

        # write temporary upload file
        out_fname = os.path.join(args.out_dir, f"upload_{period}_{pass_name}_{run}.root")
        write_upload_root(hist, meta, out_fname)
        print(f"Wrote upload file: {out_fname}")

        # perform upload
        if not args.skip_upload:
            # build ccdb path (customize to your conventions)
            ccdb_path = os.path.join(args.ccdb_base_path, period, pass_name, run)
            upload_ccdb_via_cli(out_fname, ccdb_path, pass_name, run, runinfo["SOR"], runinfo["EOR"])
            
        # mark as processed (only after successful upload or skip-upload)
        processed_hashes.add(hsh)
        db["hashes"] = list(processed_hashes)
        save_processed_db(args.processed_db, db)
        print(f"Marked hash {hsh} as processed.")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
