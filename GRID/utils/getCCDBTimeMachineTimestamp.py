#!/usr/bin/env python3

# Estimates a CCDB TimeMachine "not-after" timestamp for a given run + reco pass,
# for use as ALIEN_JDL_CCDB_CONDITION_NOT_AFTER in anchored MC.
#
# Async-reco passes are not themselves pinned to a single CCDB instant: each
# per-timeframe job sees CCDB at its own wall-clock execution time. This tool
# approximates that instant from the AliEn catalog timestamps of the pass's own
# per-timeframe reco output for the given run, since that is the closest thing
# to "when did this run actually get processed under this pass" that is left on
# record. It never guesses when it cannot find that record.
#
# started 25.08.2026; Sandro Wenzel

import argparse
import json
import os
import statistics
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

CCDB_HOST = "http://alice-ccdb.cern.ch"


def alien_json(*args):
    """Run alien.py with -json and return the parsed 'results' list."""
    cmd = ["alien.py", "-json"] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)["results"]
    except (json.JSONDecodeError, KeyError):
        return None


def find_tf_output_files(pass_dir, run):
    """LFNs of root_archive.zip directly inside this run's o2_ctf_run* per-TF
    output directories (excludes same-named files from downstream QC/skim/train
    jobs that live deeper under the same pass directory)."""
    results = alien_json("find", pass_dir, "root_archive.zip")
    if not results:
        return []
    marker = f"/o2_ctf_run{int(run):08d}_orbit"
    return sorted(r["lfn"] for r in results if marker in r["lfn"])


def sample_evenly(items, n):
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def stat_ctime(lfn):
    results = alien_json("stat", lfn)
    if not results:
        return None
    try:
        return int(results[0]["ctime"])
    except (KeyError, ValueError, TypeError):
        return None


def human(ts_ms):
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def ccdb_cross_check(path, not_after, timeout=15):
    """Report which object a correctly time-machine-pinned query at not_after
    would actually resolve to, and flag if CCDB has since been updated for the
    same validity window. Never raises; returns None on any failure."""
    url = f"{CCDB_HOST}/browse/{path}/{not_after}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except Exception as exc:
        return {"error": str(exc)}

    objects = data.get("objects", [])
    if not objects:
        return {"error": "no CCDB object covers this instant"}

    as_of = [o for o in objects if o.get("Created", 0) <= not_after]
    newest = max(objects, key=lambda o: o.get("Created", 0))
    result = {"newest": newest, "as_of": None, "outdated": False}
    if as_of:
        result["as_of"] = max(as_of, key=lambda o: o.get("Created", 0))
        result["outdated"] = newest["Created"] > result["as_of"]["Created"]
    return result


def describe_object(o):
    return (f"Created {human(o['Created'])}, JIRA={o.get('JIRA', '?')}, "
            f"comment=\"{o.get('comment', '')}\"")


def main():
    parser = argparse.ArgumentParser(
        description="Estimate a CCDB TimeMachine not-after timestamp for a run+pass, "
                    "from AliEn catalog timestamps of that pass's own reco output.")
    parser.add_argument("--year", default=os.environ.get("ALIEN_JDL_LPMANCHORYEAR"),
                         help="data-taking year, e.g. 2023 (default: $ALIEN_JDL_LPMANCHORYEAR)")
    parser.add_argument("--period", default=os.environ.get("ALIEN_JDL_LPMANCHORPRODUCTION"),
                         help="period name, e.g. LHC23s (default: $ALIEN_JDL_LPMANCHORPRODUCTION)")
    parser.add_argument("--run", default=os.environ.get("ALIEN_JDL_LPMANCHORRUN"),
                         help="run number (default: $ALIEN_JDL_LPMANCHORRUN)")
    parser.add_argument("--pass", dest="passname", default=os.environ.get("ALIEN_JDL_LPMANCHORPASSNAME"),
                         help="pass name, e.g. apass4 (default: $ALIEN_JDL_LPMANCHORPASSNAME)")
    parser.add_argument("--samples", type=int, default=9,
                         help="number of per-timeframe output files to sample (default: 9)")
    parser.add_argument("--ccdb-check-path", default="TPC/Calib/CorrectionMapV2",
                         help="CCDB path to cross-check the estimate against (default: TPC/Calib/CorrectionMapV2)")
    parser.add_argument("--no-ccdb-check", action="store_true",
                         help="skip the CCDB cross-check")
    args = parser.parse_args()

    missing = [n for n in ("year", "period", "run", "passname") if not getattr(args, n)]
    if missing:
        parser.error("missing required value(s): " + ", ".join(missing))

    pass_dir = f"/alice/data/{args.year}/{args.period}/{args.run}/{args.passname}/"
    print(f"[getCCDBTimeMachineTimestamp] Looking for TF output under {pass_dir}", file=sys.stderr)

    matches = find_tf_output_files(pass_dir, args.run)
    if not matches:
        sys.exit(f"[getCCDBTimeMachineTimestamp] No o2_ctf_run{int(args.run):08d}_orbit* output found "
                  f"under {pass_dir}. Check year/period/run/pass, or this run+pass may not use this "
                  f"catalog layout. Refusing to guess a timestamp.")

    sampled = sample_evenly(matches, args.samples)
    ctimes = []
    for lfn in sampled:
        ctime = stat_ctime(lfn)
        if ctime is not None:
            ctimes.append(ctime)
            print(f"[getCCDBTimeMachineTimestamp]   {human(ctime)}  {lfn}", file=sys.stderr)

    if len(ctimes) < 2:
        sys.exit(f"[getCCDBTimeMachineTimestamp] Only got {len(ctimes)} usable timestamp(s) out of "
                  f"{len(sampled)} sampled files ({len(matches)} found in total); refusing to guess.")

    not_after = int(statistics.median(ctimes))
    spread_h = (max(ctimes) - min(ctimes)) / 3.6e6
    print(f"[getCCDBTimeMachineTimestamp] {len(ctimes)} samples out of {len(matches)} TF outputs found; "
          f"span {human(min(ctimes))} .. {human(max(ctimes))} ({spread_h:.1f} h)", file=sys.stderr)
    print(f"[getCCDBTimeMachineTimestamp] Recommended not-after: {not_after} ({human(not_after)})",
          file=sys.stderr)

    if not args.no_ccdb_check:
        check = ccdb_cross_check(args.ccdb_check_path, not_after)
        if check is None or "error" in check:
            reason = check["error"] if check else "unknown error"
            print(f"[getCCDBTimeMachineTimestamp] CCDB cross-check on {args.ccdb_check_path} skipped: {reason}",
                  file=sys.stderr)
        elif check["as_of"] is None:
            print(f"[getCCDBTimeMachineTimestamp] CCDB cross-check on {args.ccdb_check_path}: no object "
                  f"existed yet at the recommended timestamp (earliest is {describe_object(check['newest'])})",
                  file=sys.stderr)
        else:
            print(f"[getCCDBTimeMachineTimestamp] CCDB cross-check on {args.ccdb_check_path}: as-of object is "
                  f"{describe_object(check['as_of'])}", file=sys.stderr)
            if check["outdated"]:
                print(f"[getCCDBTimeMachineTimestamp]   note: CCDB's current object for this window is newer "
                      f"({describe_object(check['newest'])}) - it postdates this pass's processing and was "
                      f"not what this run actually saw.", file=sys.stderr)

    print(not_after)


if __name__ == "__main__":
    main()
