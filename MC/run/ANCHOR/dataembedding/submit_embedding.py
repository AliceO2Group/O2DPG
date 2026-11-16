#!/usr/bin/env python3
#
# Submits an MC-DATA embedding production planned by plan_embedding.py, via grid_submit.sh.
#
# cycles mode (default): one masterjob per cycle c, split on the collection of the data files
#   that have more than c rows; a subjob runs close to its data file and treats row c of it.
# rows mode: one masterjob with one subjob per row of the table (no data locality).
#
# The anchoring variables (run, pass, production tag, generator options, ...) come from
# --anchor-env, a file of 'export ALIEN_JDL_...=...' lines. Without --submit nothing is sent.
#
# Example:
#   submit_embedding.py --plan plan_544653 --anchor-env anchor_544653.env \
#                       --table-dir /alice/cern.ch/user/s/swenzel/embedding/544653 --jobname emb_544653 \
#                       -- --ttl 36000 --packagespec '"VO_ALICE@O2PDPSuite::<tag>"'

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import embedding_plan_lib as lib

# patterns for files a successful job may lack: JAliEn fails a job whose plain output file is missing
OUTPUTS = ["AO2D*.root@disk=2", "embedding_row.json@disk=2", "embedding_status*.tsv@disk=2",
           "debug_log_archive.tgz@disk=1", "*.log@disk=1"]


def _plain(lfn):
    return lfn[len("alien://"):] if lfn.startswith("alien://") else lfn


def submissions(table, mode):
    """The masterjobs to submit: name, cycle, prodsplit and the collection of data files."""
    if mode == "cycles":
        return [{"name": f"cycle{c}", "cycle": c, "prodsplit": None,
                 "collection": [_plain(lfn) for lfn in lib.files_for_cycle(table, c)]}
                for c in range(lib.num_cycles(table))]
    if mode == "rows":
        return [{"name": "rows", "cycle": None, "prodsplit": len(lib.flat_rows(table)), "collection": None}]
    raise ValueError(f"unknown mode {mode}")


def job_script(sub, anchor_env):
    """The job script of one masterjob: anchoring variables, the row selection, then the embedding."""
    owned = re.search(r"\bALIEN_JDL_MC_DATA_EMBEDDING_(TABLE|CYCLE|ROW|AO2D)\b", anchor_env)
    if owned:
        raise ValueError(f"the anchor environment must not set {owned.group(0)}; the wrapper sets it")
    lines = ["#!/bin/bash",
             "#JDL_OUTPUT=" + ",".join(OUTPUTS),
             "#JDL_ERROROUTPUT=" + ",".join(o for o in OUTPUTS if not o.startswith("AO2D")),
             "",
             anchor_env.rstrip("\n"),
             "export ALIEN_JDL_MC_DATA_EMBEDDING_TABLE=embedding_table.json"]
    if sub["cycle"] is not None:
        lines.append(f"export ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE={sub['cycle']}")
    else:
        lines.append("export ALIEN_JDL_MC_DATA_EMBEDDING_ROW=${ALIEN_JDL_MC_DATA_EMBEDDING_ROW:-${ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID}}")
    lines += ["", "${O2DPG_ROOT}/MC/run/ANCHOR/anchorMC_DataEmbedding.sh", ""]
    return "\n".join(lines)


def grid_submit_args(sub, script, collection_file, table_lfn, jobname, dry, extra):
    args = ["--script", script, "--jobname", f"{jobname}_{sub['name']}", "--inputfile", table_lfn]
    if sub["collection"] is not None:
        args += ["--split-on-collection", collection_file]
    else:
        args += ["--prodsplit", str(sub["prodsplit"])]
    if dry:
        args.append("--dry")
    return args + extra


def main():
    parser = argparse.ArgumentParser(description="Submit a planned MC-DATA embedding production")
    parser.add_argument("--plan", required=True, help="Output directory of plan_embedding.py")
    parser.add_argument("--anchor-env", required=True, help="File with 'export ALIEN_JDL_...' anchoring lines")
    parser.add_argument("--table-dir", required=True, help="AliEn directory to upload embedding_table.json to")
    parser.add_argument("--jobname", required=True, help="Job name prefix")
    parser.add_argument("--mode", choices=["cycles", "rows"], default="cycles")
    parser.add_argument("--submit", action="store_true", help="Really submit (default: grid_submit.sh --dry)")
    parser.add_argument("extra", nargs="*", help="After '--': further grid_submit.sh arguments")
    args = parser.parse_args()

    with open(os.path.join(args.plan, "embedding_table.json")) as f:
        table = json.load(f)
    with open(args.anchor_env) as f:
        anchor_env = f.read()
    table_lfn = args.table_dir.rstrip("/") + "/embedding_table.json"
    grid_submit = os.path.join(HERE, "..", "..", "..", "..", "GRID", "utils", "grid_submit.sh")

    if args.submit:
        subprocess.run(["alien.py", "mkdir", "-p", args.table_dir], check=True)
        subprocess.run(["alien.py", "cp", "-f", "file:" + os.path.join(args.plan, "embedding_table.json"),
                        "alien:" + table_lfn], check=True)
    else:
        print(f"[dry] would upload embedding_table.json to {table_lfn}")

    rc = 0
    for sub in submissions(table, args.mode):
        script = os.path.abspath(os.path.join(args.plan, f"job_{sub['name']}.sh"))
        with open(script, "w") as f:
            f.write(job_script(sub, anchor_env))
        os.chmod(script, 0o755)
        collection_file = None
        if sub["collection"] is not None:
            collection_file = os.path.abspath(os.path.join(args.plan, f"collection_{sub['name']}.txt"))
            with open(collection_file, "w") as f:
                f.write("\n".join(sub["collection"]) + "\n")
        cmd = [grid_submit] + grid_submit_args(sub, script, collection_file, table_lfn, args.jobname,
                                               not args.submit, args.extra)
        print(f"{sub['name']}: {len(sub['collection']) if sub['collection'] else sub['prodsplit']} subjobs")
        print(" ".join(cmd))
        rc |= subprocess.run(cmd, cwd=args.plan).returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())
