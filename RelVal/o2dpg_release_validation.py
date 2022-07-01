#!/usr/bin/env python3
#
# Basically, this script allows a user to compare
# 1. 2 corresponding ROOT files containing either histograms or QC Monitoring objects
# 2. 2 corresponding simulation directories
#
# The RelVal suite is run with
# o2dpg_release_validation.py rel-val -i <file-or-sim-dir1> <file-or-sim-dir2>
#
# If 2 sim directories should be compared, it is possible to specify for which parts the RelVal should be done by adding the flags
# --with-<whic-part>
# (see full help message below to see available options)
#
# usage: o2dpg_release_validation.py rel-val [-h] -i INPUT INPUT -t
#                                            {1,2,3,4,5,6,7}
#                                            [--chi2-value CHI2_VALUE]
#                                            [--rel-mean-diff REL_MEAN_DIFF]
#                                            [--rel-entries-diff REL_ENTRIES_DIFF]
#                                            [--select-critical]
#                                            [--threshold THRESHOLD]
#                                            [--with-hits]
#                                            [--detectors [{ITS,TOF,EMC,TRD,PHS,FT0,HMP,MFT,FDD,FV0,MCH,MID,CPV,ZDC,TPC} [{ITS,TOF,EMC,TRD,PHS,FT0,HMP,MFT,FDD,FV0,MCH,MID,CPV,ZDC,TPC} ...]]]
#                                            [--with-tpctracks] [--with-kine]
#                                            [--with-analysis] [--with-qc]
#                                            [--no-plots] [--output OUTPUT]
# 
# optional arguments:
#   -h, --help            show this help message and exit
#   -i INPUT INPUT, --input INPUT INPUT
#                         2 input files for comparison OR 2 input directories
#                         from simulation for comparison
#   -t {1,2,3,4,5,6,7}, --test {1,2,3,4,5,6,7}
#                         index of test case
#   --chi2-value CHI2_VALUE
#                         Chi2 threshold
#   --rel-mean-diff REL_MEAN_DIFF
#                         Threshold of relative difference in mean
#   --rel-entries-diff REL_ENTRIES_DIFF
#                         Threshold of relative difference in number of entries
#   --select-critical     Select the critical histograms and dump to file
#   --threshold THRESHOLD
#                         threshold for how far file sizes are allowed to
#                         diverge before warning
#   --with-hits           include hit comparison when RelVal when run on
#                         simulation directories
#   --detectors [{ITS,TOF,EMC,TRD,PHS,FT0,HMP,MFT,FDD,FV0,MCH,MID,CPV,ZDC,TPC} [{ITS,TOF,EMC,TRD,PHS,FT0,HMP,MFT,FDD,FV0,MCH,MID,CPV,ZDC,TPC} ...]]
#                         include these detectors for hit RelVal
#   --with-tpctracks      include TPC tracks RelVal when run on simulation
#                         directories
#   --with-kine           include kine RelVal when run on simulation directories
#   --with-analysis       include analysis RelVal when run on simulation
#                         directories
#   --with-qc             include QC RelVal when run on simulation directories
#   --no-plots            disable plotting
#   --output OUTPUT, -o OUTPUT
#                         output directory
import sys
import argparse
from os import environ, makedirs
from os.path import join, abspath, exists, isfile, isdir, dirname, relpath
from glob import glob
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
from itertools import combinations
from shlex import split
import json
import matplotlib.pyplot as plt

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)

ROOT_MACRO=join(O2DPG_ROOT, "RelVal", "ReleaseValidation.C")

from ROOT import TFile, gDirectory, gROOT, TChain

DETECTORS_OF_INTEREST_HITS = ["ITS", "TOF", "EMC", "TRD", "PHS", "FT0", "HMP", "MFT", "FDD", "FV0", "MCH", "MID", "CPV", "ZDC", "TPC"]

REL_VAL_SEVERITY_MAP = {"GOOD": 0, "WARNING": 1, "NONCRIT_NC": 2, "CRIT_NC": 3, "BAD": 4}

REL_VAL_SEVERITY_COLOR_MAP = {"GOOD": "green", "WARNING": "orange", "NONCRIT_NC": "cornflowerblue", "CRIT_NC": "navy", "BAD": "red"}

gROOT.SetBatch()

def is_sim_dir(path):
    """
    Decide whether or not path points to a simulation directory
    """
    if not isdir(path):
        return False
    if not glob(f"{path}/pipeline*"):
        # assume there must be pipeline_{metrics,action} in there
        return False
    return True


def find_mutual_files(dirs, glob_pattern, *, grep=None):
    """
    Find mutual files recursively in list of dirs

    Args:
        dirs: iterable
            directories to take into account
        glob_pattern: str
            pattern used to apply glob to only seach for some files
        grep: iterable
            additional list of patterns to grep for
    Returns:
        list: intersection of found files
    """
    files = []
    for d in dirs:
        glob_path = f"{d}/**/{glob_pattern}"
        files.append(glob(glob_path, recursive=True))

    for f, d in zip(files, dirs):
        f.sort()
        for i, _ in enumerate(f):
            # strip potential leading /
            f[i] = f[i][len(d):].lstrip("/")

    # build the intersection
    if not files:
        return []

    intersection = files[0]
    for f in files[1:]:
        intersection = list(set(intersection) & set(f))

    # apply additional grepping if patterns are given
    if grep:
        intersection_cache = intersection.copy()
        intersection = []
        for g in grep:
            for ic in intersection_cache:
                if g in ic:
                    intersection.append(ic)

    # Sort for convenience
    intersection.sort()

    return intersection


def exceeding_difference_thresh(sizes, threshold=0.1):
    """
    Find indices in sizes where value exceeds threshold
    """
    diff_indices = []
    for i1, i2 in combinations(range(len(sizes)), 2):
        diff = abs(sizes[i1] - sizes[i2])
        if diff / sizes[i2] > threshold or diff / sizes[i2] > threshold:
            diff_indices.append((i1, i2))
    return diff_indices


def file_sizes(dirs, threshold):
    """
    Compare file sizes of mutual files in given dirs
    """
    intersection = find_mutual_files(dirs, "*.root")

    # prepare for convenient printout
    max_col_lengths = [0] * (len(dirs) + 1)
    sizes = [[] for _ in dirs]

    # extract file sizes
    for f in intersection:
        max_col_lengths[0] = max(max_col_lengths[0], len(f))
        for i, d in enumerate(dirs):
            size = Path(join(d, f)).stat().st_size
            max_col_lengths[i + 1] = max(max_col_lengths[i + 1], len(str(size)))
            sizes[i].append(size)

    # prepare dictionary to be dumped and prepare printout
    collect_dict = {"directories": dirs, "files": {}, "threshold": threshold}
    top_row = "| " + " | ".join(dirs) + " |"
    print(f"\n{top_row}\n")
    for i, f in enumerate(intersection):
        compare_sizes = []
        o = f"{f:<{max_col_lengths[0]}}"
        for j, s in enumerate(sizes):
            o += f" | {str(s[i]):<{max_col_lengths[j+1]}}"
            compare_sizes.append(s[i])
        o = f"| {o} |"

        diff_indices =  exceeding_difference_thresh(compare_sizes, threshold)
        if diff_indices:
            o += f"  <==  EXCEEDING threshold of {threshold} at columns {diff_indices} |"
            collect_dict["files"][f] = compare_sizes
        else:
            o += " OK |"
        print(o)
    return collect_dict


def load_root_file(path, option="READ"):
    """
    Convenience wrapper to open a ROOT file
    """
    f = TFile.Open(path, option)
    if not f or f.IsZombie():
        print(f"WARNING: ROOT file {path} might not exist or could not be opened")
        return None
    return f


def make_generic_histograms_from_chain(filenames1, filenames2, output_filepath1, output_filepath2, treename="o2sim"):
    """
    Create all possible histograms of TLeaf from given TChains
    """

    chain1 = TChain(treename)
    for f in filenames1:
        chain1.Add(f)
    chain2 = TChain(treename)
    for f in filenames2:
        chain2.Add(f)

    # focus only on these TLeaf types
    accepted_types = ["UInt_t", "Int_t", "Float_t", "Double_t", "Double32_t"]

    # A bit cumbersome but let's just use some code duplication to the same for 2 chains
    # 1. extract names with accepted types
    branch_names1 = []
    leaf_names1 = []
    leaf_names2 = []
    for b in chain1.GetListOfBranches():
        branch_names1.append(b.GetName())
    for l in chain1.GetListOfLeaves():
        if l.GetTypeName() not in accepted_types:
            continue
        this_name = l.GetName()
        if this_name[-1] == "_" and this_name[:-1] in branch_names1:
            # this is sort of a hack, we cannot draw these top-level branches, but can also not derive that from TLeaf::GetTypeName
            continue
        leaf_names1.append(this_name)
    for l in chain2.GetListOfLeaves():
        if l.GetTypeName() not in accepted_types:
            continue
        this_name = l.GetName()
        if this_name[-1] == "_" and this_name[:-1] in branch_names1:
            # this is sort of a hack, we cannot draw these top-level branches, but can also not derive that from TLeaf::GetTypeName
            continue
        leaf_names2.append(l.GetName())

    # 2. sort then in order to...
    leaf_names1.sort()
    leaf_names2.sort()

    # 3. ...compare whether we have the same leaves
    if leaf_names1 != leaf_names2:
        print("WARNING: Found different branches in input files")
        # 4. if not, warn and shrink to intersection
        leaf_names1 = list(set(leaf_names1) & set(leaf_names2))

    # Reset and use later
    leaf_names2 = []
    histograms = []
    output_file1 = load_root_file(output_filepath1, "RECREATE")
    for b in leaf_names1:
        h_name = b.replace(".", "_")
        chain1.Draw(f"{b}>>{h_name}")
        # if successful, append histogram and necessary info
        leaf_names2.append(b)
        hist = gDirectory.Get(h_name)
        histograms.append(hist)
        output_file1.cd()
        hist.Write()

    # Extract the second bunch of histograms
    output_file2 = load_root_file(output_filepath2, "RECREATE")
    for b, h in zip(leaf_names2, histograms):
        # reset the histogram and re-use to guarantee same binning
        h.Reset("ICEMS")
        # change current directory and set it for this histogram
        output_file2.cd()
        h.SetDirectory(output_file2)
        # append to the existing (empty) histogram
        chain2.Draw(f"{b}>>+{h.GetName()}")
        h.Write()

    output_file1.Close()
    output_file2.Close()


def rel_val_files(file1, file2, args, output_dir):
    """
    RelVal for 2 ROOT files, simply a wrapper around ReleaseValidation.C macro
    """
    if not exists(output_dir):
        makedirs(output_dir)
    select_critical = "kTRUE" if args.select_critical else "kFALSE"
    no_plots = "kTRUE" if args.no_plots else "kFALSE"
    cmd = f"\\(\\\"{abspath(file1)}\\\",\\\"{abspath(file2)}\\\",{args.test},{args.chi2_value},{args.rel_mean_diff},{args.rel_entries_diff},{select_critical},{no_plots}\\)"
    cmd = f"root -l -b -q {ROOT_MACRO}{cmd}"
    log_file = join(abspath(output_dir), "rel_val.log")
    print(f"==> Running {cmd}\nwith log file at {log_file}")
    p = Popen(split(cmd), cwd=output_dir, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
    log_file = open(log_file, 'w')
    for line in p.stdout:
        log_file.write(line)
        #sys.stdout.write(line)
    p.wait()
    log_file.close()
    return 0


def has_severity(filename, severity=("BAD", "CRIT_NC"), *, summary_only=False):
    """
    Check if any 2 histograms have a given severity level after RelVal
    """
    severity = list(severity)
    counter = {s: 0 for s in severity + ["ALL"]}

    def rel_val_summary(d):
        ret = False
        for s in REL_VAL_SEVERITY_MAP:
            names = d.get(s)
            counter["ALL"] += len(names)
            if not names:
                continue
            if s not in severity:
                continue
            if not summary_only:
                print(f"Histograms for severity {s}:")
                for n in names:
                    print(f"    {n}")
            counter[s] = len(names)
            ret = True
        return ret

    def rel_val_summary_global(d):
        ret = False
        to_print = {s: [] for s in severity}
        counter["ALL"] = len(d)
        for h in d:
            if h["test_summary"] in severity:
                to_print[h["test_summary"]].append(h["name"])
                counter[h["test_summary"]] += 1
                ret = True
        if not summary_only:
            for s, names in to_print.items():
                if not names:
                    continue
                print(f"Histograms for severity {s}:")
                for n in names:
                    print(f"    {n}")
        return ret

    res = None
    with open(filename, "r") as f:
        res = json.load(f)

    # decide whether that is an overall summary or from 2 files only
    ret = rel_val_summary_global(res["histograms"]) if "histograms" in res else rel_val_summary(res["test_summary"])
    if ret:
        print(f"\nNumber of compared histograms: {counter['ALL']} out of which severity is")
        for s in severity:
            print(f"    {s}: {counter[s]}")
        print("as printed above.\n")
    return ret


def rel_val_ttree(dir1, dir2, files, output_dir, args, treename="o2sim", *, combine_patterns=None):
    """
    RelVal for 2 ROOT files containing a TTree to be compared
    """
    # Prepare file paths for TChain
    to_be_chained1 = []
    to_be_chained2 = []
    output_dirs = []

    # possibly combine common files, for instance when they come from different timeframes
    if combine_patterns:
        for cp in combine_patterns:
            chained1 = [join(dir1, hf) for hf in files if cp in hf]
            chained2 = [join(dir2, hf) for hf in files if cp in hf]
            if not chained1 or not chained2:
                continue
            to_be_chained1.append(chained1)
            to_be_chained2.append(chained2)
            output_dirs.append(f"{cp}_dir")
    else:
        to_be_chained1 = []
        to_be_chained2 = []
        for hf in files:
            to_be_chained1.append(join(dir1, hf))
            to_be_chained2.append(join(dir2, hf))
            output_dirs.append(f"{hf}_dir")

    # paths for chains prepared, output directory names specified, do RelVal
    for tbc1, tbc2, od in zip(to_be_chained1, to_be_chained2, output_dirs):
        output_dir_hf = join(output_dir, od)
        if not exists(output_dir_hf):
            makedirs(output_dir_hf)

        make_generic_histograms_from_chain(tbc1, tbc2, join(output_dir_hf, "file1.root"), join(output_dir_hf, "file2.root"), treename)
        # after we created files containing histograms, they can be compared with the standard RelVal
        rel_val_files(abspath(join(output_dir_hf, "file1.root")), abspath(join(output_dir_hf, "file2.root")), args, output_dir_hf)
    return 0


def plot_pie_chart_single(summary, out_dir, title):
    for which_test, flagged_histos in summary.items():
        figure, ax = plt.subplots(figsize=(20, 20))
        labels = []
        n_histos = []
        colors = []
        # loop over tests done
        for flag, histos in flagged_histos.items():
            if not histos:
                continue
            labels.append(flag)
            n_histos.append(len(histos))
            colors.append(REL_VAL_SEVERITY_COLOR_MAP[flag])
        ax.pie(n_histos, explode=[0.05 for _ in labels], labels=labels, autopct="%1.1f%%", startangle=90, textprops={"fontsize": 30}, colors=colors)
        ax.axis("equal")
        ax.axis("equal")

        figure.suptitle(f"{title} ({which_test})", fontsize=40)
        save_path = join(out_dir, f"pie_chart_{which_test}.png")
        figure.savefig(save_path)
        plt.close(figure)


def plot_pie_charts(in_dir):
    """
    Make a summary per histogram (that should be able to be parsed by Grafana eventually)
    """
    print("==> Create pie charts <==")
    file_paths = glob(f"{in_dir}/**/Summary.json", recursive=True)
    summary = []

    for path in file_paths:
        # go through all we found
        current_summary = None
        with open(path, "r") as f:
            current_summary = json.load(f)
        # remove the file name, used as the top key for this collection
        rel_val_path = "/".join(path.split("/")[:-1])
        title = relpath(rel_val_path, in_dir)
        plot_pie_chart_single(current_summary, rel_val_path, title)


def make_summary(in_dir):
    """
    Make a summary per histogram (that should be able to be parsed by Grafana eventually)
    """
    print("==> Make summary <==")
    file_paths = glob(f"{in_dir}/**/Summary.json", recursive=True)
    summary = []

    for path in file_paths:
        # go through all we found
        current_summary = None
        with open(path, "r") as f:
            current_summary = json.load(f)
        # remove the file name, used as the top key for this collection
        rel_val_path = "/".join(path.split("/")[:-1])
        type_specific = relpath(rel_val_path, in_dir)
        rel_path_plot = join(type_specific, "overlayPlots")
        type_global = type_specific.split("/")[0]
        make_summary = {}
        for which_test, flagged_histos in current_summary.items():
            # loop over tests done
            for flag, histos in flagged_histos.items():
                # loop over flags per test
                for h in histos:
                    if h not in make_summary:
                        # re-arrange to have histogram at the sop
                        make_summary[h] = {"name": h, "type_global": type_global, "type_specific": type_specific, "rel_path_plot": join(rel_path_plot, f"{h}.png")}
                    # add outcome of test
                    make_summary[h][which_test] = flag
        # re-arrange to list, now each summary["path"] basically contains "rows" and each batch represents the columns
        summary.extend([batch for batch in make_summary.values()])
    return {"histograms": summary}


def rel_val_histograms(dir1, dir2, files, output_dir, args):
    """
    Simply another wrapper to combine multiple files where we expect them to contain histograms already
    """
    for f in files:
        output_dir_f = join(output_dir, f"{f}_dir")
        if not exists(output_dir_f):
            makedirs(output_dir_f)
        rel_val_files(join(dir1, f), join(dir2, f), args, output_dir_f)


def rel_val_sim_dirs(args):
    """
    Make full RelVal for 2 simulation directories
    """
    dir1 = args.input[0]
    dir2 = args.input[1]
    output_dir = args.output

    look_for = "Summary.json"
    summary_dict = {}

    # file sizes
    file_sizes_to_json = file_sizes([dir1, dir2], 0.5)
    with open(join(output_dir, "file_sizes.json"), "w") as f:
        json.dump(file_sizes_to_json, f, indent=2)

    # enable all if everything is disabled
    if not any((args.with_type_hits, args.with_type_tpctracks, args.with_type_kine, args.with_type_analysis, args.with_type_qc)):
        args.with_type_hits, args.with_type_tpctracks, args.with_type_kine, args.with_type_analysis, args.with_type_qc = (True,) * 5

    # hits
    if args.with_type_hits:
        print("==> Run RelVal for hits <==")
        hit_files = find_mutual_files((dir1, dir2), "*Hits*.root", grep=args.detectors)
        output_dir_hits = join(output_dir, "hits")
        if not exists(output_dir_hits):
            makedirs(output_dir_hits)
        rel_val_ttree(dir1, dir2, hit_files, output_dir_hits, args, combine_patterns=[f"Hits{d}" for d in args.detectors])

    # TPC tracks
    if args.with_type_tpctracks:
        print("==> Run RelVal for TPC tracks <==")
        tpctrack_files = find_mutual_files((dir1, dir2), "tpctracks.root")
        output_dir_tpctracks = join(output_dir, "tpctracks")
        if not exists(output_dir_tpctracks):
            makedirs(output_dir_tpctracks)
        rel_val_ttree(dir1, dir2, tpctrack_files, output_dir_tpctracks, args, "tpcrec", combine_patterns=["tpctracks.root"])

    # TPC tracks
    if args.with_type_kine:
        print("==> Run RelVal for MC kinematics <==")
        kine_files = find_mutual_files((dir1, dir2), "*Kine.root")
        output_dir_kine = join(output_dir, "kine")
        if not exists(output_dir_kine):
            makedirs(output_dir_kine)
        rel_val_ttree(dir1, dir2, kine_files, output_dir_kine, args, combine_patterns=["Kine.root"])

    # Analysis
    if args.with_type_analysis:
        print("==> Run RelVal for analysis <==")
        dir_analysis1 = join(dir1, "Analysis")
        dir_analysis2 = join(dir2, "Analysis")
        analysis_files = find_mutual_files((dir_analysis1, dir_analysis2), "*.root")
        output_dir_analysis = join(output_dir, "analysis")
        if not exists(output_dir_analysis):
            makedirs(output_dir_analysis)
        rel_val_histograms(dir_analysis1, dir_analysis2, analysis_files, output_dir_analysis, args)

    # QC
    if args.with_type_qc:
        print("==> Run RelVal for QC <==")
        dir_qc1 = join(dir1, "QC")
        dir_qc2 = join(dir2, "QC")
        qc_files = find_mutual_files((dir_qc1, dir_qc2), "*.root")
        output_dir_qc = join(output_dir, "qc")
        if not exists(output_dir_qc):
            makedirs(output_dir_qc)
        rel_val_histograms(dir_qc1, dir_qc2, qc_files, output_dir_qc, args)


def rel_val(args):
    """
    Entry point for RelVal
    """
    func = None
    # construct the bit mask
    args.test = 1 * args.with_test_chi2 + 2 * args.with_test_bincont + 4 * args.with_test_numentries
    if not args.test:
        args.test = 7
    if isfile(args.input[0]) and isfile(args.input[1]):
        # simply check if files, assume that they would be ROOT files in that case
        func = rel_val_files
    if is_sim_dir(args.input[0]) and is_sim_dir(args.input[1]):
        func = rel_val_sim_dirs
    if not func:
        print("Please provide either 2 files or 2 simulation directories as input.")
        return 1
    if not exists(args.output):
        makedirs(args.output)
    func(args)
    with open(join(args.output, "SummaryGlobal.json"), "w") as f:
        json.dump(make_summary(args.output), f, indent=2)
    plot_pie_charts(args.output)
    has_severity(join(args.output, "SummaryGlobal.json"), REL_VAL_SEVERITY_MAP.keys(), summary_only=True)


def inspect(args):
    """
    Inspect a Summary.json in view of RelVal severity
    """
    path = args.path

    def get_filepath(d):
        summary_global = join(path, "SummaryGlobal.json")
        if exists(summary_global):
            return summary_global
        summary = join(path, "Summary.json")
        if exists(summary):
            return summary
        print(f"Can neither find {summary_global} nor {summary}. Nothing to work with.")
        return None

    if isdir(path):
        path = get_filepath(path)
        if not path:
            return 1

    return not has_severity(path, args.severity)


def influx(args):
    """
    Create an influxDB metrics file
    """
    output_dir = args.dir
    json_in = join(output_dir, "SummaryGlobal.json")
    if not exists(json_in):
        print(f"Cannot find expected JSON summary {json_in}.")
        return 1
    table_name = "O2DPG_MC_ReleaseValidation"
    if args.table_suffix:
        table_name = f"{table_name}_{args.table_suffix}"
    tags_out = ""
    if args.tags:
        for t in args.tags:
            t_split = t.split("=")
            if len(t_split) != 2 or not t_split[0] or not t_split[1]:
                print(f"ERROR: Invalid format of tags {t} for InfluxDB")
                return 1
            # we take it apart and put it back together again to make sure there are no whitespaces etc
            tags_out += f",{t_split[0].strip()}={t_split[1].strip()}"

    # always the same
    row_tags = table_name + tags_out

    out_file = join(output_dir, "influxDB.dat")

    in_list = None
    with open(json_in, "r") as f:
        in_list = json.load(f)["histograms"]
    with open(out_file, "w") as f:
        for i, h in enumerate(in_list):
            s = f"{row_tags},type_global={h['type_global']},type_specific={h['type_specific']},id={i}"
            if args.web_storage:
                s += f",web_storage={join(args.web_storage, h['rel_path_plot'])}"
            s += f" histogram_name=\"{h['name']}\""
            for k, v in h.items():
                # add all tests - do it dynamically because more might be added in the future
                if "test_" not in k:
                    continue
                s += f",{k}={REL_VAL_SEVERITY_MAP[v]}"
            f.write(f"{s}\n")


def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Wrapping ReleaseValidation macro')

    common_file_parser = argparse.ArgumentParser(add_help=False)
    common_file_parser.add_argument("-i", "--input", nargs=2, help="2 input files for comparison OR 2 input directories from simulation for comparison", required=True)

    sub_parsers = parser.add_subparsers(dest="command")
    rel_val_parser = sub_parsers.add_parser("rel-val", parents=[common_file_parser])
    rel_val_parser.add_argument("--with-test-chi2", dest="with_test_chi2", action="store_true", help="run chi2 test")
    rel_val_parser.add_argument("--with-test-bincont", dest="with_test_bincont", action="store_true", help="run bin-content test")
    rel_val_parser.add_argument("--with-test-numentries", dest="with_test_numentries", action="store_true", help="run number-of-entries test")
    rel_val_parser.add_argument("--chi2-value", dest="chi2_value", type=float, help="Chi2 threshold", default=1.5)
    rel_val_parser.add_argument("--rel-mean-diff", dest="rel_mean_diff", type=float, help="Threshold of relative difference in mean", default=1.5)
    rel_val_parser.add_argument("--rel-entries-diff", dest="rel_entries_diff", type=float, help="Threshold of relative difference in number of entries", default=0.01)
    rel_val_parser.add_argument("--select-critical", dest="select_critical", action="store_true", help="Select the critical histograms and dump to file")
    rel_val_parser.add_argument("--threshold", type=float, default=0.1, help="threshold for how far file sizes are allowed to diverge before warning")
    rel_val_parser.add_argument("--with-type-hits", dest="with_type_hits", action="store_true", help="include hit comparison when RelVal when run on simulation directories")
    rel_val_parser.add_argument("--detectors", nargs="*", help="include these detectors for hit RelVal", default=DETECTORS_OF_INTEREST_HITS, choices=DETECTORS_OF_INTEREST_HITS)
    rel_val_parser.add_argument("--with-type-tpctracks", dest="with_type_tpctracks", action="store_true", help="include TPC tracks RelVal when run on simulation directories")
    rel_val_parser.add_argument("--with-type-kine", dest="with_type_kine", action="store_true", help="include kine RelVal when run on simulation directories")
    rel_val_parser.add_argument("--with-type-analysis", dest="with_type_analysis", action="store_true", help="include analysis RelVal when run on simulation directories")
    rel_val_parser.add_argument("--with-type-qc", dest="with_type_qc", action="store_true", help="include QC RelVal when run on simulation directories")
    rel_val_parser.add_argument("--no-plots", dest="no_plots", action="store_true", help="disable plotting")
    rel_val_parser.add_argument("--output", "-o", help="output directory", default="rel_val")
    rel_val_parser.set_defaults(func=rel_val)

    inspect_parser = sub_parsers.add_parser("inspect")
    inspect_parser.add_argument("path", help="either complete file path to a Summary.json or SummaryGlobal.json or directory where one of the former is expected to be")
    inspect_parser.add_argument("--severity", nargs="*", default=["BAD", "CRIT_NC"], choices=REL_VAL_SEVERITY_MAP.keys(), help="Choose severity levels to search for")
    inspect_parser.set_defaults(func=inspect)

    influx_parser = sub_parsers.add_parser("influx")
    influx_parser.add_argument("--dir", help="directory where ReleaseValidation was run", required=True)
    influx_parser.add_argument("--web-storage", dest="web_storage", help="full base URL where the RelVal results are supposed to be")
    influx_parser.add_argument("--tags", nargs="*", help="tags to be added for influx, list of key=value")
    influx_parser.add_argument("--table-suffix", dest="table_suffix", help="prefix for table name")
    influx_parser.set_defaults(func=influx)

    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
