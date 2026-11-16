#!/usr/bin/env python3
#
# Plans an MC-DATA embedding production: samples a fraction of a run's data AO2D files,
# reads their BC/collision tables and packs whole DF folders into jobs ("rows").
# Writes embedding_table.json (the job input), empty_dfs.json and plan_summary.txt.
#
# Example:
#   plan_embedding.py --run 544653 --data-path /alice/data/2023/LHC23zzm/544653/apass4 \
#                     --fraction 0.002 --seed 1 --tfs-per-job 2 --out plan_544653

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "utils"))

import embedding_plan_lib as lib


def find_files(data_path):
    """All per-job AO2D files below data_path on AliEn."""
    out = subprocess.run(["alien.py", "find", data_path, "AO2D.root"], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"alien.py find failed: {out.stderr.strip()}")
    return lib.aod_lfns(out.stdout.splitlines())


def main():
    parser = argparse.ArgumentParser(description="Plan an MC-DATA embedding production")
    parser.add_argument("--run", type=int, required=True, help="Run number of the data")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--data-path", help="AliEn directory to search for AO2D.root, e.g. /alice/data/2023/LHC23zzm/544653/apass4")
    src.add_argument("--file-list", help="Text file with one data AO2D LFN per line")
    parser.add_argument("--fraction", type=float, default=1.0, help="Fraction of the files to embed into (default 1)")
    parser.add_argument("--seed", type=int, default=1, help="Seed of the file sampling")
    parser.add_argument("--tfs-per-job", type=int, default=0, help="Timeframes per job; a DF is never split (0: one job per file)")
    parser.add_argument("--out", required=True, help="Output directory")
    args = parser.parse_args()

    if args.data_path:
        candidates = find_files(args.data_path)
    else:
        with open(args.file_list) as f:
            candidates = lib.aod_lfns(f.read().splitlines())
    if not candidates:
        print("No data AO2D files found")
        return 1
    files = lib.sample_files(candidates, args.fraction, args.seed)
    print(f"Sampled {len(files)} of {len(candidates)} data AO2D files")

    import o2dpg_data_embedding_utils as utils  # needs ROOT and a GRID token

    os.makedirs(args.out, exist_ok=True)
    workdir = os.getcwd()
    os.chdir(args.out)  # the utils write their local copy of the BC/collision tables here
    table = {"run": args.run,
             "orbits_per_tf": utils.retrieve_Aggregated_RunInfos(args.run)["OrbitsPerTF"],
             "tfs_per_job": args.tfs_per_job,
             "files": {}}
    empty, ntf, nrows, largest = {}, 0, 0, 0
    for lfn in files:
        dfs = utils.units_from_file(lfn, args.run)
        rows = lib.pack_rows(dfs, args.tfs_per_job)
        table["files"][lfn] = [{"dfs": r} for r in rows]
        empty[lfn] = lib.empty_dfs(dfs)
        ntf += sum(len(t) for t in dfs.values())
        nrows += len(rows)
        largest = max([largest] + [sum(len(t) for t in r.values()) for r in rows])
        print(f"{lfn}: {len(dfs)} DFs, {sum(len(t) for t in dfs.values())} TFs, {len(rows)} jobs")
    os.chdir(workdir)

    with open(os.path.join(args.out, "embedding_table.json"), "w") as f:
        json.dump(table, f, indent=1)
    with open(os.path.join(args.out, "empty_dfs.json"), "w") as f:
        json.dump(empty, f, indent=1)
    summary = (f"run {args.run}, {len(files)} of {len(candidates)} files (fraction {args.fraction}, seed {args.seed})\n"
               f"{ntf} timeframes in {nrows} jobs, at most {largest} TFs per job (budget {args.tfs_per_job})\n"
               f"cycles mode: {lib.num_cycles(table)} masterjobs; rows mode: 1 masterjob with {nrows} subjobs\n")
    with open(os.path.join(args.out, "plan_summary.txt"), "w") as f:
        f.write(summary)
    print(summary, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
