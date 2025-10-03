#!/usr/bin/env python3

# A python tool, that calculates mean O2DPG workflow metrics by
# harvesting from data from pipeline_metric files from the GRID (for a given lpm production tag).

import json
import subprocess
from collections import defaultdict
import re
import os
import argparse
import random
from pathlib import Path
import sys
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

# add the parent directory of the current file to sys.path to find the o2dpg_sim_metric
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from o2dpg_sim_metrics import json_stat_impl

def alien_find(path, pattern="*", logging=False):
    cmd = ["alien.py", "find", path, pattern]
    if logging:
        print (f"Performing {cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def alien_cp(alien_path, local_path, parent=None, fatal=False, logging=False):
    cmd = ["alien.py", "cp"]
    if parent != None:
        cmd = cmd + ["-parent", f"{parent}"]
    cmd = cmd + [f"alien://{alien_path}", f"file://{local_path}"]
    if logging:
       print (f"Performing {cmd}")
    try:
       subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError as e:
       pass

def alien_cp_inputfile(inputfile, logging=False):
    cmd = ["alien.py", "cp", "-input", f"{inputfile}"]
    if logging:
       print (f"Performing {cmd}")
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


def calculate_statistics(selecteddirs, prod_tag, run_number, batchcopy = False):
    """
    downloads the metrics files and calculates aggregates statistics
    """
    targetdir = f"/tmp/o2dpg_metrics_harvester/{prod_tag}/{run_number}"
    if not os.path.exists(targetdir):
        os.makedirs(targetdir)

    start=time.time()    
    # determine target dir based on tag and run_number
    if batchcopy == True:
        # make an inputfile
        inputfile = f"{targetdir}/cp_input.list" 
        with open(inputfile,'w') as f:
             for dir in selecteddirs:
                path = Path(dir)
                # Get the last 1 components --> mimics -parent which does not work with inputlists
                last_N = Path(*path.parts[-1:])
                f.write(f"{dir}/pipeline_metr* file:{targetdir}/{last_N}\n")

        # copy with the input-file
        alien_cp_inputfile(inputfile, logging=True)
        
    else:
        for dir in selecteddirs:
            # avoid copy if we can !
            # we need to keep 2-top level dirs
            alien_cp(f"{dir}/pipeline_metr*", targetdir, parent=1)

    end=time.time()
    print(f"Copy took {end-start:.4f} seconds")

    # construct the list of all inputfiles
    input_files = [str(p) for p in Path(targetdir).rglob('pipeline_metr*')]
    print(input_files)

    # calculate the stats with all the files in targetdir
    outputfilename=f"{targetdir}/merged_metrics.json"
    meta_info = {"prod-tag" : prod_tag, "run-number" : run_number}
    json_stat_impl(input_files, outputfilename, meta_info)

import os
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

def treat_parallel(func, data, use_threads=False, max_workers=None):
    """
    Apply `func` to each element of `data` in parallel.

    Parameters
    ----------
    func : callable
        The function to apply to each element.
    data : iterable
        The data to process.
    use_threads : bool, default=False
        If True, use threads (good for I/O-bound tasks).
        If False, use processes (good for CPU-bound tasks).
    max_workers : int, optional
        Number of workers to use. Defaults to number of CPUs for processes.

    Returns
    -------
    list
        The results in the same order as `data`.
    """
    if max_workers is None:
        max_workers = os.cpu_count() if not use_threads else min(32, os.cpu_count() * 5)

    Executor = ThreadPoolExecutor if use_threads else ProcessPoolExecutor

    # --- Use map to preserve order ---
    with Executor(max_workers=max_workers) as executor:
        results = list(executor.map(func, data))

    return results

def treat_one_run(data_element):
        """
        The final worker function to execute for each run.
        Expects it's input parameters in a list to work well with Thread/ProcessExecutor and treat_parallel above.

        data_element should be a tuple, where
        index 0 --> the run_number
        index 1 --> a list of tuples(cycle, split, directory)
        index 2 --> production tag
        index 3 --> sample_size
        """
        run_number, candidates = data_element[0], data_element[1]
        prod_tag = data_element[2]
        sample_size = data_element[3]
        universe = [ w[2] for w in candidates ]
        selected_dirs = random.sample(universe, min(len(universe), sample_size))
        print (f"For {run_number} selected {selected_dirs}")
        calculate_statistics(selected_dirs, prod_tag, run_number, batchcopy=True)


def process_prod_tag(prod_tag, year="2025", ccdb_url=None, username=None, overwrite=False, samplesize=20):
    base_path = f"/alice/sim/{year}/{prod_tag}"

    pipelinemetric_files = alien_find(base_path, "pipeline_metric*")
    
    # exclude some unnecessary paths
    pipelinemetric_files = [
      zf for zf in pipelinemetric_files
      if "/AOD/" not in zf and "/QC/" not in zf and "/TimeseriesTPCmerging/" not in zf and "/Stage" not in zf    
    ]
    print (f"Found {len(pipelinemetric_files)} pipeline metric files")

    # directories containing workflow.json
    workflow_dirs = {os.path.dirname(wf) for wf in pipelinemetric_files}
    print (f"Found {len(workflow_dirs)} workflow dirs")

    # Step 2: group by run_number
    runs = defaultdict(list)
    for dir in workflow_dirs:
        parsed = parse_workflow_path(dir, prod_tag)
        if parsed is None:
            continue
        cycle, run_number, split = parsed
        runs[run_number].append((cycle, split, dir))
    print(f"Found {len(runs)} run numbers")

    # Step 3: for each run_number, pick samplesize files for the final calculation
    # for run_number, candidates in sorted(runs.items()):
    #     universe = [ w[2] for w in candidates ]
    #     selected_dirs = random.sample(universe, min(len(universe), samplesize))
    #     print (f"For {run_number} selected {selected_dirs}")
        
    #     # calculate merged statistics from the sample
    #     calculate_statistics(selected_dirs, prod_tag, run_number, batchcopy=False)

    data = [ (d[0], d[1], prod_tag, samplesize) for d in sorted(runs.items()) ]
    do_parallel = True
    if do_parallel == True:
       treat_parallel(treat_one_run, data, use_threads=False, max_workers=8)
    else:
       for data_element in data:
           treat_one_run(data_element)

def main():
    parser = argparse.ArgumentParser(
      description="Harvest MC metrics from AlienGRID; aggregate; and publish to CCDB"
    )
    parser.add_argument("--prod_tag", required=True, help="Production tag (e.g. prod2025a)")
    parser.add_argument("--ccdb", required=False, default="https://alice-ccdb.cern.ch", help="CCDB server URL")
    parser.add_argument("--username", required=False, help="GRID username (needs appropriate AliEn token initialized)")
    parser.add_argument("--year", default="2025", help="Production year (default: 2025)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing entries")
    args = parser.parse_args()

    process_prod_tag(args.prod_tag, year=args.year, ccdb_url=args.ccdb, username=args.username, overwrite=args.overwrite)

if __name__ == "__main__":
    main()
