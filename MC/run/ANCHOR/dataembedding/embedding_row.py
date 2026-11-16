#!/usr/bin/env python3
#
# Finds the row of the MC-DATA embedding work table that this GRID job has to treat.
# Cycles mode: ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE=c and the job's input file (input.list or wn.xml).
# Rows mode:   ALIEN_JDL_MC_DATA_EMBEDDING_ROW=r (1-based, set to #alien_counter# in the JDL).
# Prints "<data LFN> <DF,DF,...>" and writes the expected timeframes and a manifest.

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import embedding_plan_lib as lib


def _with_prefix(lfn):
    return lfn if lfn.startswith("alien://") else "alien://" + lfn


def job_lfn(cwd):
    """The data file AliEn assigned to this job: input.list (txt-list) or wn.xml (xml-single)."""
    path = os.path.join(cwd, "input.list")
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    return _with_prefix(line.strip())
    path = os.path.join(cwd, "wn.xml")
    if os.path.exists(path):
        with open(path) as f:
            m = re.search(r'\blfn="([^"]+)"', f.read())
        if m:
            return _with_prefix(m.group(1))
    return None


def resolve_row(table, env, lfn):
    """Returns (data LFN, {DF: [tf, ...]}) for this job, or raises ValueError."""
    if env.get("ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE", "") != "":
        cycle = int(env["ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE"])
        if lfn is None:
            raise ValueError("cycles mode, but the job has no input file (input.list / wn.xml)")
        rows = table["files"].get(lfn)
        if rows is None:
            raise ValueError(f"input file {lfn} is not in the work table")
        if not 0 <= cycle < len(rows):
            raise ValueError(f"cycle {cycle} out of range: {lfn} has {len(rows)} rows")
        return lfn, rows[cycle]["dfs"]
    if env.get("ALIEN_JDL_MC_DATA_EMBEDDING_ROW", "") != "":
        index = int(env["ALIEN_JDL_MC_DATA_EMBEDDING_ROW"])
        flat = lib.flat_rows(table)
        if not 1 <= index <= len(flat):
            raise ValueError(f"row {index} out of range: the table has {len(flat)} rows")
        lfn, row = flat[index - 1]
        return lfn, row["dfs"]
    raise ValueError("neither ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE nor ALIEN_JDL_MC_DATA_EMBEDDING_ROW is set")


def run_cli(argv, env, cwd):
    parser = argparse.ArgumentParser(description="Find this job's row of the MC-DATA embedding work table")
    parser.add_argument("--table", required=True, help="Work table (embedding_table.json)")
    parser.add_argument("--expect-out", required=True, help="Write the planned DF -> timeframes here")
    parser.add_argument("--manifest", required=True, help="Write the job manifest here")
    args = parser.parse_args(argv)

    with open(os.path.join(cwd, args.table)) as f:
        table = json.load(f)
    lfn, dfs = resolve_row(table, env, job_lfn(cwd))
    with open(os.path.join(cwd, args.expect_out), "w") as f:
        json.dump(dfs, f)
    cycle = env.get("ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE", "")
    row = env.get("ALIEN_JDL_MC_DATA_EMBEDDING_ROW", "")
    with open(os.path.join(cwd, args.manifest), "w") as f:
        json.dump({"run": table["run"], "lfn": lfn,
                   "cycle": int(cycle) if cycle != "" else None,
                   "row": int(row) if row != "" else None,
                   "dfs": dfs}, f, indent=1)
    return f"{lfn} {','.join(sorted(dfs, key=lib.df_number))}"


if __name__ == "__main__":
    try:
        print(run_cli(sys.argv[1:], os.environ, os.getcwd()))
    except (ValueError, OSError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
