#!/usr/bin/env python3

# A tool to add the key FirstOrbitMC to the MCProdInfo objects of an existing MC production.
# FirstOrbitMC is the first orbit the MC used; analysis (AggregatedRunInfo::adjust_from_MC)
# aligns its timeframes with it.
#
# The value is read per run from the log archives of the run's own GRID jobs, since a production
# may contain runs made with different software. Runs without a reachable log archive can be
# filled, and others cross-checked, by rerunning the anchoring step with the run's software.
#
# 1. scan (needs alien.py and a GRID token): read two log archives per run
#      mcprodinfo_firstorbit.py scan --tag LHC26j17 -o LHC26j17.json
# 2. rerun (needs CVMFS): fill runs without archive and cross-check a sample
#      mcprodinfo_firstorbit.py rerun LHC26j17.json --crosscheck 3
# 3. apply (needs a GRID token with the right role): publish new MCProdInfo objects
#      mcprodinfo_firstorbit.py apply LHC26j17.json --comment "FirstOrbitMC added because of O2-7335" --yes
# The apply step is a dry run unless --yes is given.

import argparse
import collections
import concurrent.futures
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import zipfile
from urllib.parse import parse_qs, quote, urlparse

import requests
import urllib3

from mcprodinfo_ccdb_upload import MCProdInfo, publish_MCProdInfo

MONALISA = "https://alimonitor.cern.ch"


def token_cert():
    key = os.environ.get("JALIEN_TOKEN_KEY")
    cert = os.environ.get("JALIEN_TOKEN_CERT")
    if key is None and cert is None:
        uid = os.getuid()
        cert, key = f"/tmp/tokencert_{uid}.pem", f"/tmp/tokenkey_{uid}.pem"
    return cert, key


def list_mcprodinfo(ccdb_url, username, tag):
    """Newest MCProdInfo metadata per run of a production."""
    url = f"{ccdb_url}/browse/Users/{username[0]}/{username}/MCProdInfo/{tag}"
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=120)
    r.raise_for_status()
    newest = {}
    for o in r.json().get("objects", []):
        run = int(o["RunNumber"])
        if run not in newest or int(o["createTime"]) > int(newest[run]["createTime"]):
            newest[run] = o
    return newest


def newest_mcprodinfo(ccdb_url, username, tag, run):
    """Newest MCProdInfo object of one run, or None."""
    url = f"{ccdb_url}/browse/Users/{username[0]}/{username}/MCProdInfo/{tag}/{run}/{run + 1}"
    r = requests.get(url, headers={"Accept": "application/json"}, cert=token_cert(), verify=False, timeout=120)
    r.raise_for_status()
    objs = r.json().get("objects", [])
    return max(objs, key=lambda o: int(o["createTime"])) if objs else None


def masterjobs(tag):
    """Masterjob ids and output directories of a production, per run (from MonALISA)."""
    cert = token_cert()
    r = requests.get(f"{MONALISA}/MC/prodDetails.jsp?tag={quote(tag)}", cert=cert, verify=False,
                     allow_redirects=False, timeout=120)
    jobtype = parse_qs(urlparse(r.headers.get("Location", "")).query).get("filter_jobtype", [None])[0]
    if not jobtype:
        raise RuntimeError(f"no MonALISA jobtype for production {tag}")
    r = requests.get(f"{MONALISA}/job_events.jsp?timesel=0&owner=aliprod&filter_jobtype={quote(jobtype)}&res_path=json",
                     cert=cert, verify=False, timeout=300)
    jobs = collections.defaultdict(dict)
    for mjid, entry in r.json().items():
        run, outdir = entry.get("run_no"), entry.get("outputdir")
        if str(run).isdigit() and outdir:
            jobs[int(run)][str(mjid)] = outdir.rstrip("/")
    return jobs


def masterjob_package(mjid):
    """Packages of a masterjob, from its JDL."""
    m = re.search(r"Packages\s*=\s*\{([^}]*)\}", alien("ps", "-jdl", mjid).stdout)
    return ",".join(re.findall(r'"([^"]+)"', m.group(1))) if m else None


def alien(*args, timeout=300):
    return subprocess.run(["alien.py", *args], capture_output=True, text=True, timeout=timeout)


def read_job(jobdir, run):
    """Package, FirstOrbitMC and data first orbit from the output of one job, or None.

    The anchoring log and stdout are read from log_archive.zip, or from the job directory
    when a production stores them there as plain files."""
    stdout, log = "", ""
    with tempfile.TemporaryDirectory() as d:
        local = os.path.join(d, "log_archive.zip")
        if alien("cp", f"alien://{jobdir}/log_archive.zip", f"file://{local}").returncode == 0:
            try:
                z = zipfile.ZipFile(local)
                stdout = z.read("stdout").decode(errors="ignore") if "stdout" in z.namelist() else ""
                ts = [n for n in z.namelist() if n.startswith("timestampsampling")]
                log = z.read(ts[0]).decode(errors="ignore") if ts else ""
            except (zipfile.BadZipFile, KeyError):
                pass
        for name in ("stdout", f"timestampsampling_{run}.log"):
            if (name == "stdout" and stdout) or (name != "stdout" and log):
                continue
            plain = os.path.join(d, name)
            if alien("cp", f"alien://{jobdir}/{name}", f"file://{plain}").returncode == 0:
                text = open(plain, errors="ignore").read()
                if name == "stdout":
                    stdout = text
                else:
                    log = text
    fo = re.search(r"Determined first orbit to be:\s+(\d+)", log)
    os_ = re.search(r"^OS\s+(\d+)", log, re.M)
    pkg = re.search(r"ALIEN_JDL_PACKAGES=(\S+)", stdout)
    if not (fo and os_):
        return None
    return {"lfn": jobdir, "package": pkg.group(1) if pkg else None,
            "FirstOrbitMC": int(fo.group(1)), "FirstOrbitData": int(os_.group(1))}


def scan_run(run, outdirs, nsamples):
    """Reads up to nsamples log archives of a run, spread over its masterjobs."""
    candidates = []
    for outdir in sorted(outdirs):
        splits = sorted(s.strip("/") for s in alien("ls", outdir).stdout.split() if re.fullmatch(r"\d{3}/?", s))
        if splits:
            candidates.append([f"{outdir}/{s}" for s in (splits[:2] + splits[-2:])])
    samples = []
    # round robin over the masterjobs, so that different masterjobs of one run are compared
    for i in range(4):
        for c in candidates:
            if len(samples) >= nsamples:
                break
            if i < len(c):
                s = read_job(c[i], run)
                if s:
                    samples.append(s)
    return samples, bool(candidates)


def scan(args):
    meta = list_mcprodinfo(args.ccdb, args.username, args.tag)
    jobs = masterjobs(args.tag)
    runs = sorted(r for r in meta if not args.runs or r in args.runs)
    rows = {}

    def one(run):
        mjs = jobs.get(run, {})
        packages = {mj: masterjob_package(mj) for mj in mjs}
        return run, mjs, packages, scan_run(run, mjs.values(), args.samples)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for run, mjs, mjpackages, (samples, has_output) in ex.map(one, runs):
            optf = int(meta[run]["OrbitsPerTF"])
            row = {"run": run, "OrbitsPerTF": optf, "masterjobs": mjpackages, "samples": samples, "meta": meta[run]}
            firsts = {(s["FirstOrbitMC"], s["FirstOrbitData"]) for s in samples}
            packages = {p for p in mjpackages.values() if p} | {s["package"] for s in samples if s["package"]}
            if len(packages) == 1:
                row["package"] = next(iter(packages))
            if not mjs:
                row["status"] = "NO_JOBS"
            elif not has_output:
                row["status"] = "NO_OUTPUT"
            elif len(packages) > 1 or len(firsts) > 1:
                row["status"] = "MIXED"
            elif not samples:
                row["status"] = "NO_ARCHIVE"
            else:
                (row["FirstOrbitMC"], row["FirstOrbitData"]), = firsts
                row["shift"] = (row["FirstOrbitMC"] - row["FirstOrbitData"]) % optf
                row["status"] = "OK"
            rows[run] = row
            print(f"{run} OrbitsPerTF={optf} {row['status']} samples={len(samples)} "
                  f"package={row.get('package')} FirstOrbitMC={row.get('FirstOrbitMC')} shift={row.get('shift')}", flush=True)
    with open(args.output, "w") as f:
        json.dump({"tag": args.tag, "username": args.username, "rows": [rows[r] for r in runs]}, f, indent=1)
    status = collections.Counter(r["status"] for r in rows.values())
    print(f"{args.output}: {dict(status)}")
    return 0


def rerun_anchoring(package, run, orbits_per_tf, tag, timeout=900):
    """Runs the anchoring step for one run; returns (data first orbit, MC first orbit)."""
    pkg = package.split("::")[-1]
    with tempfile.TemporaryDirectory(prefix=f"anchor_{run}_") as wd:
        inner = (f"python3 $O2DPG_ROOT/MC/bin/o2dpg_sim_workflow_anchored.py --run-number {run} --split-id 1 "
                 f"--prod-split 100 --cycle 0 -tf 1 --orbitsPerTF {orbits_per_tf} -- -gen pythia8 -proc inel "
                 f"-productionTag {tag} -e TGeant4 -j 8 -ns 1")
        cmd = ["/cvmfs/alice.cern.ch/bin/alienv", "setenv", f"O2PDPSuite/{pkg}", "-c", "bash", "-c", inner]
        env = {k: v for k, v in os.environ.items() if not k.startswith("ALIEN_JDL")}
        p = subprocess.run(cmd, cwd=wd, env=env, capture_output=True, text=True, timeout=timeout)
    out = p.stdout + p.stderr
    os_ = re.search(r"^OS\s+(\d+)", out, re.M)
    fo = re.search(r"Determined first orbit to be:\s+(\d+)", out)
    if not (os_ and fo):
        raise RuntimeError(f"run {run}: anchoring output not understood (rc {p.returncode}): {out[-300:]}")
    return int(os_.group(1)), int(fo.group(1))


def rerun(args):
    with open(args.table) as f:
        table = json.load(f)
    rows = table["rows"]
    todo = [r for r in rows if r["status"] == "NO_ARCHIVE"]
    ok = [r for r in rows if r["status"] == "OK" and r.get("package")]
    todo += random.Random(1).sample(ok, min(args.crosscheck, len(ok)))

    def one(row):
        package = args.package or row.get("package")
        if not package:
            return row, None, "no package known"
        try:
            return row, rerun_anchoring(package, row["run"], row["OrbitsPerTF"], table["tag"]), package
        except Exception as e:
            return row, None, str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for row, res, info in ex.map(one, todo):
            if res is None:
                print(f"{row['run']} rerun failed: {info}", flush=True)
                continue
            data_first, mc_first = res
            if row["status"] == "OK":
                agree = (mc_first, data_first) == (row["FirstOrbitMC"], row["FirstOrbitData"])
                row["crosscheck"] = "agree" if agree else f"DIFFER rerun {mc_first}/{data_first}"
                print(f"{row['run']} cross-check {row['crosscheck']}", flush=True)
            else:
                row.update(status="RERUN", package=info, FirstOrbitMC=mc_first, FirstOrbitData=data_first,
                           shift=(mc_first - data_first) % row["OrbitsPerTF"])
                print(f"{row['run']} RERUN package={info} FirstOrbitMC={mc_first} shift={row['shift']}", flush=True)
    with open(args.table, "w") as f:
        json.dump(table, f, indent=1)
    return 0


def apply(args):
    with open(args.table) as f:
        table = json.load(f)
    tag = table["tag"]
    username = args.username or table["username"]
    for row in table["rows"]:
        if row["status"] not in ("OK", "RERUN") or str(row.get("crosscheck", "agree")) != "agree":
            print(f"SKIP {tag} run {row['run']} status={row['status']} crosscheck={row.get('crosscheck')}")
            continue
        m = row["meta"]
        # the newest object must still be the one scanned; skip runs that already carry the value
        current = newest_mcprodinfo(args.ccdb, username, tag, row["run"])
        if current is not None and current.get("id") != m.get("id"):
            if str(current.get("FirstOrbitMC")) == str(row["FirstOrbitMC"]):
                print(f"DONE {tag} run {row['run']} already has FirstOrbitMC={row['FirstOrbitMC']}")
                continue
            print(f"ERROR: {tag} run {row['run']} has a newer object ({current.get('id')}) than the scanned one "
                  f"({m.get('id')}), with FirstOrbitMC={current.get('FirstOrbitMC')}; scan again")
            return 1
        info = MCProdInfo(LPMProductionTag=tag,
                          Col=m.get("Col"),
                          IntRate=float(m["IntRate"]) if m.get("IntRate") not in (None, "None") else None,
                          RunNumber=row["run"],
                          OrbitsPerTF=row["OrbitsPerTF"],
                          Comment=args.comment,
                          McTag=m.get("McTag") if m.get("McTag") not in (None, "None") else row.get("package"),
                          RecoTag=m.get("RecoTag") if m.get("RecoTag") != "None" else None,
                          FirstOrbitMC=row["FirstOrbitMC"])
        print(f"{'PUBLISH' if args.yes else 'DRY'} {tag} run {row['run']} FirstOrbitMC={row['FirstOrbitMC']} "
              f"shift={row['shift']} McTag={info.McTag} -> {args.ccdb} Users/{username[0]}/{username}")
        if args.yes:
            r = publish_MCProdInfo(info, ccdb_url=args.ccdb, username=username, force_overwrite=True)
            where = r.headers.get("Location") or r.headers.get("Content-Location") if r is not None else None
            with open(args.log, "a") as log:
                log.write(f"{tag} {row['run']} {r.status_code if r is not None else None} {where}\n")
            if r is None or r.status_code not in (200, 201):
                print(f"ERROR: upload of run {row['run']} failed: {r.status_code if r is not None else 'no response'} "
                      f"{(r.text[:300] if r is not None else '')}")
                return 1
    return 0


def main():
    urllib3.disable_warnings()
    parser = argparse.ArgumentParser(description="Add FirstOrbitMC to the MCProdInfo objects of an MC production")
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="read FirstOrbitMC per run from the log archives of its jobs")
    s.add_argument("--tag", required=True, help="LPM production tag")
    s.add_argument("--runs", type=int, nargs="*", help="restrict to these runs")
    s.add_argument("--samples", type=int, default=2, help="log archives to read per run")
    s.add_argument("--ccdb", default="http://alice-ccdb.cern.ch", help="CCDB to read MCProdInfo from")
    s.add_argument("--username", default="aliprod", help="owner of the MCProdInfo objects")
    s.add_argument("-j", "--jobs", type=int, default=8, help="runs processed in parallel")
    s.add_argument("-o", "--output", required=True, help="output table (JSON)")
    r = sub.add_parser("rerun", help="rerun the anchoring for runs without archive and for a cross-check sample")
    r.add_argument("table", help="table written by scan, updated in place")
    r.add_argument("--package", help="override the O2PDPSuite package of each run (default: from its masterjob JDL)")
    r.add_argument("--crosscheck", type=int, default=3, help="number of runs with archive to cross-check")
    r.add_argument("-j", "--jobs", type=int, default=8, help="parallel anchoring reruns")
    a = sub.add_parser("apply", help="publish MCProdInfo objects with FirstOrbitMC from a table")
    a.add_argument("table", help="table written by scan")
    a.add_argument("--comment", required=True, help="Comment stored in the new objects")
    a.add_argument("--ccdb", default="https://alice-ccdb.cern.ch", help="CCDB to publish to")
    a.add_argument("--username", help="owner path to publish under (default: as scanned)")
    a.add_argument("--yes", action="store_true", help="really publish (default: dry run)")
    a.add_argument("--log", default="mcprodinfo_firstorbit_published.log", help="appends tag, run, HTTP status and object location per upload")
    args = parser.parse_args()
    return {"scan": scan, "rerun": rerun, "apply": apply}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
