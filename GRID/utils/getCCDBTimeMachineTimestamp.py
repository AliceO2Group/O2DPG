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
import dataclasses
from dataclasses import dataclass, asdict, fields
import json
import os
import requests
import statistics
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

# hack to find the script with helper functions
o2dpg_root = os.environ.get("O2DPG_ROOT")
if o2dpg_root is None:
  raise EnvironmentError("O2DPG_ROOT is not set in the environment.")
mc_prodinfo_path = os.path.abspath(os.path.join(o2dpg_root, "MC", "prodinfo"))
sys.path.append(mc_prodinfo_path)
# FIXME: these should probably be moved to a common script
from mcprodinfo_ccdb_upload import extract_metadata_blocks_from_CCDB

CCDB_HOST = "http://alice-ccdb.cern.ch"


@dataclass(frozen=True)
class CCDBTimeMachineTS:
    """
    struct for CCDB time machine timestamp
    """
    LPMProductionTag: str
    Period: str
    Pass: str
    NotAfter: int


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


def get_ccdb_objects(url, timeout = 15):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except Exception as exc:
        return {"error": str(exc)}

    objects = data.get("objects", [])
    return objects


def get_run_start_tf(run):
    run_info_url = f"{CCDB_HOST}/browse/RCT/Info/RunInformation/{run}"
    objects = get_ccdb_objects(run_info_url)

    return objects[0]["STF"]


def ccdb_cross_check(run, path, not_after, timeout=15):
    """Report which object a correctly time-machine-pinned query at not_after
    would actually resolve to, and flag if CCDB has since been updated for the
    same validity window. Never raises; returns None on any failure."""
    timestamp = get_run_start_tf(run)
    url = f"{CCDB_HOST}/browse/{path}/{timestamp}"
    objects = get_ccdb_objects(url)
    if not objects:
        return {"error": "no CCDB object covers this instant"}

    as_of = [o for o in objects if o.get("Created", 0) <= not_after]
    newest = max(objects, key=lambda o: o.get("Created", 0))
    result = {"timestamp": timestamp, "newest": newest, "as_of": None, "outdated": False}
    if as_of:
        result["as_of"] = max(as_of, key=lambda o: o.get("Created", 0))
        result["outdated"] = newest["Created"] > result["as_of"]["Created"]
    return result


def describe_object(o):
    return (f"Created {human(o['Created'])}, JIRA={o.get('JIRA', '?')}, "
            f"comment=\"{o.get('comment', '')}\"")


def make_cert_paths(cert_dir="/tmp"):
    key_path = os.environ.get("JALIEN_TOKEN_KEY")
    cert_path = os.environ.get("JALIEN_TOKEN_CERT")
    if key_path == None and cert_path == None:
       uid = os.getuid()
       cert_path = os.path.join(cert_dir, f"tokencert_{uid}.pem")
       key_path = os.path.join(cert_dir, f"tokenkey_{uid}.pem")

    return cert_path, key_path


def get_NotAfter(year, period, run, passname, samples=9, ccdb_check_path="TPC/Calib/CorrectionMapV2", ccdb_check=True):
    """
    Estimates the CCDBTimeMachine NotAfter timestamp from the output of the production of a given period/run/pass.
    Cross-checks the estimated NotAfter timestamp vs the creation time of a CCDB object which is currently
    valid for the given run.

    Returns:
        int: CCDBTimeMachineTS NotAfter timestamp
    """
    pass_dir = f"/alice/data/{year}/{period}/{run}/{passname}/"
    print(f"[getCCDBTimeMachineTimestamp] Looking for TF output under {pass_dir}", file=sys.stderr)

    matches = find_tf_output_files(pass_dir, run)
    if not matches:
        sys.exit(f"[getCCDBTimeMachineTimestamp] No o2_ctf_run{int(run):08d}_orbit* output found "
                 f"under {pass_dir}. Check year/period/run/pass, or this run+pass may not use this "
                 f"catalog layout. Refusing to guess a timestamp.")

    sampled = sample_evenly(matches, samples)
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
    print(f"[getCCDBTimeMachineTimestamp] Recommended NotAfter: {not_after} ({human(not_after)})",
          file=sys.stderr)

    if ccdb_check:
        check = ccdb_cross_check(run, ccdb_check_path, not_after)
        if check is None or "error" in check:
            reason = check["error"] if check else "unknown error"
            print(f"[getCCDBTimeMachineTimestamp] CCDB cross-check on {ccdb_check_path}/{check["timestamp"]} skipped: {reason}",
                  file=sys.stderr)
        elif check["as_of"] is None:
            print(f"[getCCDBTimeMachineTimestamp] CCDB cross-check on {ccdb_check_path}/{check["timestamp"]}: no object "
                  f"existed yet at the recommended timestamp (earliest is {describe_object(check['newest'])})",
                  file=sys.stderr)
        else:
            print(f"[getCCDBTimeMachineTimestamp] CCDB cross-check on {ccdb_check_path}/{check["timestamp"]}: as-of object is "
                  f"{describe_object(check['as_of'])}", file=sys.stderr)
            if check["outdated"]:
                print(f"[getCCDBTimeMachineTimestamp]   note: CCDB's current object for this window is newer "
                      f"({describe_object(check['newest'])}) - it postdates this pass's processing and was "
                      f"not what this run actually saw.", file=sys.stderr)

    return not_after


def query_CCDBTimeMachineTS(base_url, user, period, passname):
    """
    Queries CCDBTimeMachineTS from CCDB for a given period and pass.

    Returns:
        obtained NotAfter timestamp (int) or None
    """
    # Construct user ID-specific cert and key paths
    cert_path, key_path = make_cert_paths()

    # Build full URL
    query = f"1/Period={period}/Pass={passname}"
    user_path = 'Users/' + user[0] + '/' + user
    url = f"{base_url}/browse/{user_path}/CCDBTimeMachineTS/{query}"

    print(f"[getCCDBTimeMachineTimestamp] Checking if CCDBTimeMachineTS already exists: {url}")

    response = requests.get(url, cert=(cert_path, key_path), verify=False)
    if response.status_code != 404:
        meta = extract_metadata_blocks_from_CCDB(response.content.decode('utf-8'))
        if (len(meta) > 0):
          def filter_known_fields(cls, data: dict) -> dict:
            valid_keys = {f.name for f in fields(cls)}
            return {k: v for k, v in data.items() if k in valid_keys}

          clean_meta = filter_known_fields(CCDBTimeMachineTS, meta[0])
          print(f"[getCCDBTimeMachineTimestamp] Found object for {clean_meta['Period']}, Pass: {clean_meta['Pass']}, "
                f"NotAfter: {clean_meta['NotAfter']} ({human(clean_meta['NotAfter'])}), uploaded by LPMProductionTag {clean_meta['LPMProductionTag']}")
          return clean_meta['NotAfter']

    return None


def upload_CCDBTimeMachineTS(base_url, user, keys):
    """
    Uploads an empty .dat file as CCDBTimeMachineTS with the corresponding meta data provided by `keys`

    Returns:
        Response object from the POST request
    """
    # Create an empty file
    empty_file = "empty.dat"
    with open(empty_file, "w") as f:
        f.write("0")

    # Construct user ID-specific cert and key paths
    cert_path, key_path = make_cert_paths()

    # Build full URL
    query = "/".join(f"{k}={v}" for k, v in keys.items())
    user_path = 'Users/' + user[0] + '/' + user
    start = 1
    stop = start + 1
    url = f"{base_url}/{user_path}/CCDBTimeMachineTS/{start}/{stop}/{query}"

    print(f"[getCCDBTimeMachineTimestamp] Uploading CCDBTimeMachineTS: {url}")

    # Prepare request
    with open(empty_file, 'rb') as f:
        files = {'blob': f}
        response = requests.post(url, files=files, cert=(cert_path, key_path), verify=False)

    os.remove(empty_file)

    return response


def get_CCDBTimeMachineTS(production_tag, year, period, run, passname,
                          samples=9, ccdb_check_path="TPC/Calib/CorrectionMapV2", ccdb_check=True,
                          ccdb_url="https://alice-ccdb.cern.ch", username="aliprod",
                          force_overwrite=False, publish_to_ccdb=True, skip_ccdb_query=False):
    """
    Makes a query to CCDB for a CCDBTimeMachineTS for given period and pass.
    If an object is found, the NotAfter timestamp is returned.
    If no object is found, the NotAfter timestamp is estimated from the reco output of the given period/run/pass.
    In case an object is found, a new upload can be forced by setting the argument `force_overwrite=True`

    Returns:
        int: Either the queried or the estimated NotAfter timestamp
    """
    if not skip_ccdb_query:
        not_after = query_CCDBTimeMachineTS(ccdb_url, username, period, passname)
    else:
        not_after = None

    if not_after is not None and force_overwrite == True:
        print("[getCCDBTimeMachineTimestamp] Existing object will be overwritten")

    if not_after == None or force_overwrite == True:
        print("[getCCDBTimeMachineTimestamp] Estimating CCDBTimeMachineTS for "
              f"LPMProductionTag: {production_tag}, Period: {period}, Pass: {passname}")
        not_after = get_NotAfter(year, period, run, passname, samples, ccdb_check_path, ccdb_check)
        time_machine_ts = CCDBTimeMachineTS(production_tag, period, passname, not_after)
        if publish_to_ccdb:
            upload_CCDBTimeMachineTS(ccdb_url, username, dataclasses.asdict(time_machine_ts))

    return not_after


def main():
    parser = argparse.ArgumentParser(
        description="Estimate a CCDB TimeMachine not-after timestamp for a run+pass, "
                    "from AliEn catalog timestamps of that pass's own reco output.")
    parser.add_argument("--production-tag", default=os.environ.get("ALIEN_JDL_LPMPRODUCTIONTAG"),
                        help="production tag to mark which production uploads an object (default: $ALIEN_JDL_LPMPRODUCTIONTAG)")
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
                        help="skip the CCDB cross-check after calculating the NotAfter")
    parser.add_argument("--publish-to-ccdb", action="store_true",
                        help="upload the CCDBTimeMachineTS object to the CCDB")
    parser.add_argument("--skip-ccdb-query", action="store_true",
                        help="skip CCDB query for existing objects while publishing")
    parser.add_argument("--force-overwrite", action="store_true",
                        help="overwrite the current CCDBTimeMachineTS object in the CCDB if one exists")
    parser.add_argument("--ccdb-url", default="https://alice-ccdb.cern.ch",
                        help="ccdb host for the upload")
    parser.add_argument("--username", default="aliprod",
                        help="username to be used for the upload to CCDB")
    args = parser.parse_args()

    missing = [n for n in ("year", "period", "run", "passname") if not getattr(args, n)]
    if missing:
        parser.error("missing required value(s): " + ", ".join(missing))

    get_CCDBTimeMachineTS(args.production_tag, args.year, args.period, args.run, args.passname,
                          args.samples, args.ccdb_check_path, not args.no_ccdb_check, args.ccdb_url, args.username,
                          args.force_overwrite, args.publish_to_ccdb, args.skip_ccdb_query)


if __name__ == "__main__":
    main()
