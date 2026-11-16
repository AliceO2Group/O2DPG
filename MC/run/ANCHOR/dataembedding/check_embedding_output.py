#!/usr/bin/env python3
#
# Merges the outputs of an MC-DATA embedding production per parent data file and checks
# that each merged MC AO2D is correctly linked to its parent:
#   - no DF folder appears twice, every planned DF is there and no other one;
#   - every DF has a parentFiles entry pointing to the parent;
#   - per DF, the MC truth collisions sit at the BCs of the data collisions, and as many.
#
# Examples:
#   check_embedding_output.py merge --plan plan_544653 --outputs out_cycle0 out_cycle1 --out merged
#   check_embedding_output.py check --plan plan_544653 --mc merged/0000/AO2D.root --parent alien:///.../AO2D.root

import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "utils"))

import embedding_plan_lib as lib


# ---- pure checks -------------------------------------------------------------------------------

def planned_dfs(table, lfn):
    """DF folders the plan expects in the MC output of one parent (empty DFs have no row)."""
    return sorted((df for row in table["files"][lfn] for df in row["dfs"]), key=lib.df_number)


def coverage(planned, produced):
    """(missing, duplicated, unexpected) DF folder names, comparing the plan with the MC file's folders."""
    counts = collections.Counter(produced)
    missing = sorted((df for df in planned if df not in counts), key=lib.df_number)
    duplicated = sorted((df for df, n in counts.items() if n > 1), key=lib.df_number)
    unexpected = sorted((df for df in counts if df not in set(planned)), key=lib.df_number)
    return missing, duplicated, unexpected


def bc_subset(mc_bcs, data_bcs):
    return set(mc_bcs) <= set(data_bcs)


def count_mismatches(mc_counts, data_counts):
    return [f"{df}: {mc_counts.get(df, 0)} MC collisions for {data_counts[df]} data collisions"
            for df in sorted(data_counts, key=lib.df_number) if mc_counts.get(df, 0) != data_counts[df]]


def mccollision_key(keys):
    """The MC collision table among a DF folder's keys (not O2mccollisionlabel)."""
    for k in keys:
        if re.match(r"^O2mccollision_\d+(;\d+)?$", k):
            return k
    return None


def data_counts(data, planned, excluded):
    """DF -> number of data collisions to compare with, leaving out excluded (DF, TF)."""
    return {df: sum(len(bcs) for tf, bcs in data.get(df, {}).items() if (df, tf) not in excluded) for df in planned}


def excluded_from_status(status_paths):
    """(DF, TF) pairs reported as excluded in the given embedding_status.tsv files."""
    out = set()
    for status in status_paths:
        if os.path.exists(status):
            with open(status) as f:
                for line in f:
                    parts = line.split()
                    if len(parts) == 3 and parts[2] == "excluded":
                        out.add((parts[0], int(parts[1])))
    return out


def excluded_tfs(manifest_paths):
    """(DF, TF) pairs a job reported as excluded, from the embedding_status.tsv beside each manifest."""
    return excluded_from_status([os.path.join(os.path.dirname(p), "embedding_status.tsv") for p in manifest_paths])


def missing_aod_is_error(manifest_path):
    """A job without AO2D.root is fine only when its status file reports all its timeframes excluded."""
    status = os.path.join(os.path.dirname(manifest_path), "embedding_status.tsv")
    if not os.path.exists(status):
        return True
    with open(status) as f:
        states = [line.split()[2] for line in f if len(line.split()) == 3]
    return not states or any(st != "excluded" for st in states)


def fully_excluded_dfs(table, lfn, excluded):
    """Planned DF folders of a parent whose timeframes were all excluded; they have no MC output."""
    out = []
    for row in table["files"][lfn]:
        for df, tfs in row["dfs"].items():
            if tfs and all((df, tf) in excluded for tf in tfs):
                out.append(df)
    return sorted(out, key=lib.df_number)


def expected_dfs(table, lfn, excluded):
    """DF folders the MC output of a parent must contain."""
    gone = set(fully_excluded_dfs(table, lfn, excluded))
    return [df for df in planned_dfs(table, lfn) if df not in gone]


def group_by_parent(manifests):
    """
    Parent LFN -> AO2D files of the jobs that embedded into it, ordered by their first DF,
    so that --merge-by-name sees the DF folders in order. manifests: [(manifest path, content)].
    """
    groups = collections.defaultdict(list)
    for path, m in manifests:
        first = min(lib.df_number(df) for df in m["dfs"])
        groups[m["lfn"]].append((first, os.path.abspath(os.path.join(os.path.dirname(path), "AO2D.root"))))
    return {lfn: [aod for _, aod in sorted(items)] for lfn, items in groups.items()}


# ---- ROOT-based readers ------------------------------------------------------------------------

def _open(path):
    """TFile.Open that first connects to AliEn for alien:// paths."""
    import ROOT
    if path.startswith("alien://") and not ROOT.gGrid:
        ROOT.TGrid.Connect("alien://")
    f = ROOT.TFile.Open(path)
    if not f or f.IsZombie():
        raise OSError(f"Failed to open file {path}")
    return f


def mc_df_folders(path):
    """DF folder names in a file, once per key cycle (a duplicated folder shows up twice)."""
    import ROOT
    f = _open(path)
    names = [k.GetName() for k in f.GetListOfKeys() if k.GetName().startswith("DF_")]
    f.Close()
    return names


def parent_files(path):
    import ROOT
    f = _open(path)
    m = f.Get("parentFiles")
    out = {}
    if m:
        it = m.MakeIterator()
        key = it.Next()
        while key:
            out[key.GetName()] = m.GetValue(key).GetName()
            key = it.Next()
    f.Close()
    return out


def mc_truth_bcs(path):
    """DF -> list of globalBCs of the MC truth collisions (read with ROOT: AO2Ds may use zstd)."""
    import ROOT
    f = _open(path)
    out = {}
    for df in sorted({k.GetName() for k in f.GetListOfKeys() if k.GetName().startswith("DF_")}):
        d = f.Get(df)
        keys = [k.GetName() for k in d.GetListOfKeys()]
        mcc = mccollision_key(keys)
        bcs = [k for k in keys if k.startswith("O2bc_")]
        if mcc is None or not bcs:
            out[df] = []
            continue
        index = ROOT.RDataFrame(d.Get(mcc)).AsNumpy(["fIndexBCs"])["fIndexBCs"]
        gbc = ROOT.RDataFrame(d.Get(bcs[0])).AsNumpy(["fGlobalBC"])["fGlobalBC"]
        out[df] = [int(gbc[i]) for i in index]
    f.Close()
    return out


def data_collision_bcs(parent, run):
    """DF -> TF -> globalBCs of the triggered data collisions (the ones the contexts were made from)."""
    import o2dpg_data_embedding_utils as utils
    merged = utils.read_timeframe_structure(parent, run)
    out = {}
    for key, frame in merged.items():
        out[key.split("@")[0]] = {int(tf): [int(c[0]) for c in cols]
                                  for tf, cols in zip(frame["timeframeID"], frame["position_vectors"])}
    return out


def check(mc, parent, table, workdir, excluded=frozenset()):
    """Returns a list of problems (empty: the MC file is correctly linked to its parent)."""
    problems = []
    planned = expected_dfs(table, parent, excluded)
    missing, duplicated, unexpected = coverage(planned, mc_df_folders(mc))
    problems += [f"missing DF {df}" for df in missing]
    problems += [f"duplicated DF {df}" for df in duplicated]
    problems += [f"DF {df} is not in the plan" for df in unexpected]

    links = parent_files(mc)
    for df in planned:
        if links.get(df) is None:
            problems.append(f"{df} has no parentFiles entry")
        elif links[df].replace("alien://", "") != parent.replace("alien://", ""):
            problems.append(f"{df} points to {links[df]}")

    cwd = os.getcwd()
    os.chdir(workdir)  # the data tables are copied locally here
    try:
        data = data_collision_bcs(parent, table["run"])
    finally:
        os.chdir(cwd)
    mc_bcs = mc_truth_bcs(mc)
    for df in planned:
        data_bcs = [bc for bcs in data.get(df, {}).values() for bc in bcs]
        if not bc_subset(mc_bcs.get(df, []), data_bcs):
            problems.append(f"{df}: MC collisions at BCs without a data collision")
    problems += count_mismatches({df: len(mc_bcs.get(df, [])) for df in planned},
                                 data_counts(data, planned, excluded))
    return problems


# ---- commands ----------------------------------------------------------------------------------

def cmd_merge(args, table):
    manifests = []
    for d in args.outputs:
        for p in sorted(glob.glob(os.path.join(d, "**", "embedding_row.json"), recursive=True)):
            with open(p) as f:
                manifests.append((p, json.load(f)))
    groups = group_by_parent(manifests)
    rc = 0
    for i, parent in enumerate(sorted(groups)):
        outdir = os.path.join(args.out, f"{i:04d}")
        os.makedirs(outdir, exist_ok=True)
        manifests_here = [p for p, m in manifests if m["lfn"] == parent]
        aods = [a for a in groups[parent] if os.path.exists(a)]
        bad = [p for p in manifests_here
               if not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(p)), "AO2D.root")) and missing_aod_is_error(p)]
        if bad:
            print(f"ERROR: {len(bad)} job outputs without AO2D.root for {parent}")
            rc = 1
        if not aods:
            if not bad:
                print(f"{parent}: all timeframes excluded, nothing to merge")
            continue
        with open(os.path.join(outdir, "inputs.txt"), "w") as f:
            f.write("\n".join(aods) + "\n")
        with open(os.path.join(outdir, "parent.txt"), "w") as f:
            f.write(parent + "\n")
        merge = subprocess.run(["o2-aod-merger", "--input", "inputs.txt", "--output", "AO2D.root",
                                "--merge-by-name", "--max-size", "1000000000000"], cwd=outdir)
        if merge.returncode != 0:
            print(f"ERROR: merging for {parent} failed")
            rc = 1
            continue
        excluded = excluded_tfs([p for p, m in manifests if m["lfn"] == parent])
        problems = check(os.path.join(outdir, "AO2D.root"), parent, table, outdir, excluded)
        print(f"{parent} -> {outdir}/AO2D.root: {'OK' if not problems else 'FAILED'}")
        for p in problems:
            print(f"  {p}")
        rc |= 1 if problems else 0
    planned_parents = set(table["files"])
    for lfn in sorted(planned_parents - set(groups)):
        print(f"ERROR: no job output at all for {lfn}")
        rc = 1
    return rc


def main():
    parser = argparse.ArgumentParser(description="Merge and check MC-DATA embedding outputs")
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge", help="Merge job outputs per parent and check each result")
    m.add_argument("--plan", required=True)
    m.add_argument("--outputs", nargs="+", required=True, help="Local directories holding the job outputs")
    m.add_argument("--out", required=True)
    c = sub.add_parser("check", help="Check one MC AO2D against its parent")
    c.add_argument("--plan", required=True)
    c.add_argument("--mc", required=True)
    c.add_argument("--parent", required=True)
    c.add_argument("--status", nargs="*", default=[], help="embedding_status.tsv files of the jobs, for excluded timeframes")
    args = parser.parse_args()

    with open(os.path.join(args.plan, "embedding_table.json")) as f:
        table = json.load(f)
    if args.cmd == "merge":
        return cmd_merge(args, table)
    # the data tables are copied beside a local MC file, or into the current directory for alien://
    workdir = os.getcwd() if args.mc.startswith("alien://") else os.path.dirname(os.path.abspath(args.mc))
    problems = check(args.mc, args.parent, table, workdir, excluded_from_status(args.status))
    for p in problems:
        print(p)
    print("OK" if not problems else "FAILED")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
