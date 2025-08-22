#!/usr/bin/env python3

# A python tool, that fills CCDB MCProdInfo by
# harvesting the data from production log files from the GRID.
# This is useful, when the information was not directly filled
# by the MC job itself.

import json
import subprocess
import sys
from collections import defaultdict
from zipfile import ZipFile
import re
import os
import argparse

from mcprodinfo_ccdb_upload import MCProdInfo, publish_MCProdInfo  


def alien_find(path, pattern="*"):
    cmd = ["alien.py", "find", path, pattern]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def alien_cp(alien_path, local_path):
    cmd = ["alien.py", "cp", f"alien://{alien_path}", f"file://{local_path}"]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def parse_workflow_path(path, prod_tag):
    parts = path.strip("/").split("/")
    try:
        idx = parts.index(prod_tag)
    except ValueError:
        return None

    after = parts[idx + 1 :]
    if len(after) < 2:
        return None

    if after[0].isdigit() and len(after[0]) == 1:
        cycle = int(after[0])
        run_number = int(after[1])
        split = after[2]
    else:
        cycle = None
        run_number = int(after[0])
        split = after[1]

    return cycle, run_number, split


def extract_from_zip(local_zip_path):
    """Extract workflow.json and stdout from log_archive.zip."""
    wf_data = None
    env_vars = {}
    try:
        with ZipFile(local_zip_path, "r") as zf:
            # workflow.json
            if "workflow.json" in zf.namelist():
                with zf.open("workflow.json") as wf_file:
                    wf_data = json.load(wf_file)

            # stdout (could be named stdout or stdout.log)
            candidates = [n for n in zf.namelist() if n.startswith("stdout")]
            if candidates:
                with zf.open(candidates[0]) as so:
                    text = so.read().decode(errors="ignore")
                    for key in [
                        "ALIEN_JDL_PACKAGES",
                        "ALIEN_JDL_O2DPG_ASYNC_RECO_TAG",
                        "ALIEN_MASTERJOB",
                    ]:
                        m = re.search(rf"{key}=(.*)", text)
                        if m:
                            env_vars[key] = m.group(1).strip()
    except Exception as e:
        print(f"⚠️ Failed to extract from {local_zip_path}: {e}")
    return wf_data, env_vars


def build_info(prod_tag, run_number, wf_data, env_vars):
    meta=wf_data.get("meta")
    if meta != None:
        int_rate = meta.get("interactionRate")
        col_system = meta.get("col")
        orbits_per_tf = meta.get("orbitsPerTF")
    
    return MCProdInfo(
        LPMProductionTag=prod_tag,
        Col=col_system,
        IntRate=int_rate,
        RunNumber=run_number,
        OrbitsPerTF=orbits_per_tf,        
        McTag=env_vars.get("ALIEN_JDL_PACKAGES"),
        RecoTag=env_vars.get("ALIEN_JDL_O2DPG_ASYNC_RECO_TAG")
    )


def pick_split(prod_tag, run_number, candidates, ascending=True):
    """Pick the first valid split (min if ascending, max if not)."""
    def split_key(entry):
        _, split, _ = entry
        try:
            return int(split)
        except ValueError:
            return float("inf")

    candidates_sorted = sorted(candidates, key=split_key, reverse=not ascending)

    for cycle, split, zip_path in candidates_sorted:
        print (f"Trying to analyse {zip_path}")
        local_zip = f"/tmp/log_archive_{run_number}_{cycle or 0}_{split}.zip"
        try:
            alien_cp(zip_path, local_zip)
        except subprocess.CalledProcessError:
            continue

        wf_data, env_vars = extract_from_zip(local_zip)
        
        try:
            os.remove(local_zip)   # cleanup downloaded file
        except OSError:
            pass
        
        if wf_data:
            info = build_info(prod_tag, run_number, wf_data, env_vars)
            return info, cycle, split, zip_path
        print (f"Failed")
    
    return None, None, None, None


def process_prod_tag(prod_tag, year="2025", ccdb_url=None, username=None):
    base_path = f"/alice/sim/{year}/{prod_tag}"

    # Step 1: find all log_archive.zip files
    print (f"Querying AliEn for all directories with zip files")
    zip_files = alien_find(base_path, "log_archive.zip")

    # exclude some unnecessary paths
    zip_files = [
      zf for zf in zip_files
      if "/AOD/" not in zf and "/QC/" not in zf and "/TimeseriesTPCmerging/" not in zf and "/Stage" not in zf
    ]

    # Step 2: group by run_number
    runs = defaultdict(list)
    for zf in zip_files:
        parsed = parse_workflow_path(zf, prod_tag)
        if parsed is None:
            continue
        cycle, run_number, split = parsed
        runs[run_number].append((cycle, split, zf))

    print(f"Found {len(runs)} run numbers")

    # Step 3: for each run_number, handle smallest and largest valid split
    for run_number, candidates in sorted(runs.items()):
        print (f"Analysing run {run_number}")
        info_min, cycle_min, split_min, _ = pick_split(prod_tag, run_number, candidates, ascending=True)
        info_max, cycle_max, split_max, _ = pick_split(prod_tag, run_number, candidates, ascending=False)

        # some consistency checks
        if info_min and info_max:
            if info_min.Col != info_max.Col:
                print(f"❌ ColSystem mismatch for run {run_number}")
            if info_min.OrbitsPerTF != info_max.OrbitsPerTF:
                print(f"❌ OrbitsPerTF mismatch for run {run_number}")

        publish_MCProdInfo(info_min, username=username, ccdb_url=ccdb_url)
        print (info_min)


def main():
    parser = argparse.ArgumentParser(
      description="Harvest MC production metadata from AlienGRID and publish to CCDB"
    )
    parser.add_argument("--prod_tag", required=True, help="Production tag (e.g. prod2025a)")
    parser.add_argument("--ccdb", required=False, default="https://alice-ccdb.cern.ch", help="CCDB server URL")
    parser.add_argument("--username", required=False, help="GRID username (needs appropriate AliEn token initialized)")
    parser.add_argument("--year", default="2025", help="Production year (default: 2025)")
    args = parser.parse_args()

    process_prod_tag(args.prod_tag, year=args.year, ccdb_url=args.ccdb, username=args.username)

if __name__ == "__main__":
    main()
