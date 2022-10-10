#!/usr/bin/env python3
#
# Basically, this script allows a user to compare
# 1. 2 corresponding ROOT files containing either histograms or QC Monitoring objects
# 2. 2 corresponding simulation directories
#
# The RelVal suite is run with
# o2dpg_release_validation.py rel-val -i <file-or-sim-dir1> -j <file-or-sim-dir2>
#
# If 2 sim directories should be compared, it the files to be compared must be given via a config JSON
# via --dirs-config
# See O2DPG/RelVal/config/rel_val_sim_dirs_default.json for as an example
#
# The full help message would be
#usage: o2dpg_release_validation.py rel-val [-h] -i [INPUT1 ...] -j
#                                           [INPUT2 ...]
#                                           [--chi2-threshold CHI2_THRESHOLD]
#                                           [--rel-mean-diff-threshold REL_MEAN_DIFF_THRESHOLD]
#                                           [--rel-entries-diff-threshold REL_ENTRIES_DIFF_THRESHOLD]
#                                           [--use-values-as-thresholds USE_VALUES_AS_THRESHOLDS]
#                                           [--chi2-threshold-margin CHI2_THRESHOLD_MARGIN]
#                                           [--rel-mean-diff-threshold-margin REL_MEAN_DIFF_THRESHOLD_MARGIN]
#                                           [--rel-entries-diff-threshold-margin REL_ENTRIES_DIFF_THRESHOLD_MARGIN]
#                                           [--with-test-chi2]
#                                           [--with-test-bincont]
#                                           [--with-test-numentries]
#                                           [--dir-config DIR_CONFIG]
#                                           [--dir-config-enable [DIR_CONFIG_ENABLE ...]]
#                                           [--dir-config-disable [DIR_CONFIG_DISABLE ...]]
#                                           [--include-dirs [INCLUDE_DIRS ...]]
#                                           [--add] [--output OUTPUT]
#
#optional arguments:
#  -h, --help            show this help message and exit
#  -i [INPUT1 ...], --input1 [INPUT1 ...]
#                        EITHER first set of input files for comparison OR
#                        first input directory from simulation for comparison
#  -j [INPUT2 ...], --input2 [INPUT2 ...]
#                        EITHER second set of input files for comparison OR
#                        second input directory from simulation for comparison
#  --chi2-threshold CHI2_THRESHOLD
#                        Chi2 threshold
#  --rel-mean-diff-threshold REL_MEAN_DIFF_THRESHOLD
#                        Threshold of relative difference in mean
#  --rel-entries-diff-threshold REL_ENTRIES_DIFF_THRESHOLD
#                        Threshold of relative difference in number of entries
#  --use-values-as-thresholds USE_VALUES_AS_THRESHOLDS
#                        Use values from another run as thresholds for this one
#  --chi2-threshold-margin CHI2_THRESHOLD_MARGIN
#                        Margin to apply to the chi2 threshold extracted from
#                        file
#  --rel-mean-diff-threshold-margin REL_MEAN_DIFF_THRESHOLD_MARGIN
#                        Margin to apply to the rel_mean_diff threshold
#                        extracted from file
#  --rel-entries-diff-threshold-margin REL_ENTRIES_DIFF_THRESHOLD_MARGIN
#                        Margin to apply to the rel_entries_diff threshold
#                        extracted from file
#  --with-test-chi2      run chi2 test
#  --with-test-bincont   run bin-content test
#  --with-test-numentries
#                        run number-of-entries test
#  --dir-config DIR_CONFIG
#                        What to take into account in a given directory
#  --dir-config-enable [DIR_CONFIG_ENABLE ...]
#                        only enable these top keys in your dir-config
#  --dir-config-disable [DIR_CONFIG_DISABLE ...]
#                        disable these top keys in your dir-config (precedence
#                        over dir-config-enable)
#  --include-dirs [INCLUDE_DIRS ...]
#                        only inlcude directories; note that each pattern is
#                        assumed to start in the top-directory (at the moment
#                        no regex or *)
#  --add                 If given and there is already a RelVal in the output
#                        directory, extracted objects will be added to the
#                        existing ones
#  --output OUTPUT, -o OUTPUT
#                        output directory

import sys
import argparse
import re
from os import environ, makedirs, remove
from os.path import join, abspath, exists, isfile, isdir, dirname, relpath
from glob import glob
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
from itertools import combinations
from shlex import split
import json
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import seaborn

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)

ROOT_MACRO_EXTRACT=join(O2DPG_ROOT, "RelVal", "ExtractAndFlatten.C")
ROOT_MACRO_RELVAL=join(O2DPG_ROOT, "RelVal", "ReleaseValidation.C")

from ROOT import TFile, gDirectory, gROOT, TChain, TH1D

DETECTORS_OF_INTEREST_HITS = ["ITS", "TOF", "EMC", "TRD", "PHS", "FT0", "HMP", "MFT", "FDD", "FV0", "MCH", "MID", "CPV", "ZDC", "TPC"]

REL_VAL_SEVERITIES = ["GOOD", "WARNING", "NONCRIT_NC", "CRIT_NC", "BAD"]
REL_VAL_SEVERITIES_USE_SUMMARY = [True, False, False, True, True]
REL_VAL_SEVERITY_MAP = {v: i for i, v in enumerate(REL_VAL_SEVERITIES)}
REL_VAL_SEVERITY_COLOR_MAP = {"GOOD": "green", "WARNING": "orange", "NONCRIT_NC": "cornflowerblue", "CRIT_NC": "navy", "BAD": "red"}
REL_VAL_TEST_NAMES = ["test_chi2", "test_bin_cont", "test_num_entries"]
REL_VAL_TEST_NAMES_MAP = {v: i for i, v in enumerate(REL_VAL_TEST_NAMES)}
REL_VAL_TEST_CRITICAL = [True, True, False]
TEST_SUMMARY_NAME = "test_summary"
REL_VAL_TEST_NAMES_SUMMARY = REL_VAL_TEST_NAMES + [TEST_SUMMARY_NAME]
REL_VAL_TEST_NAMES_MAP_SUMMARY = {v: i for i, v in enumerate(REL_VAL_TEST_NAMES_SUMMARY)}

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


def plot_pie_charts(summary, out_dir, title):

    print("==> Plot pie charts <==")

    test_n_hist_map = {}

    # need to re-arrange the JSON structure abit for per-test result pie charts
    for histo_name, tests in summary.items():
        # loop over tests done
        for test in tests:
            test_name = test["test_name"];
            if test_name not in test_n_hist_map:
                test_n_hist_map[test_name] = {}
            result = test["result"]
            if result not in test_n_hist_map[test_name]:
                test_n_hist_map[test_name][result] = 0
            test_n_hist_map[test_name][result] += 1


    for which_test, flags in test_n_hist_map.items():
        labels = []
        colors = []
        n_histos = []
        for flag, count in flags.items():
            labels.append(flag)
            n_histos.append(count)
            colors.append(REL_VAL_SEVERITY_COLOR_MAP[flag])

        figure, ax = plt.subplots(figsize=(20, 20))
        ax.pie(n_histos, explode=[0.05 for _ in labels], labels=labels, autopct="%1.1f%%", startangle=90, textprops={"fontsize": 30}, colors=colors)
        ax.axis("equal")
        ax.axis("equal")

        figure.suptitle(f"{title} ({which_test})", fontsize=40)
        save_path = join(out_dir, f"pie_chart_{which_test}.png")
        figure.savefig(save_path)
        plt.close(figure)


def extract_from_summary(summary, fields):
    """
    Extract a fields from summary per test and histogram name
    """
    test_histo_value_map = {}
    # need to re-arrange the JSON structure abit for per-test result pie charts
    for histo_name, tests in summary.items():
        # loop over tests done
        for test in tests:
            test_name = test["test_name"];
            if test_name not in test_histo_value_map:
                test_histo_value_map[test_name] = {field: [] for field in fields}
                test_histo_value_map[test_name]["histograms"] = []
            if not test["comparable"]:
                continue
            test_histo_value_map[test_name]["histograms"].append(histo_name)
            for field in fields:
                test_histo_value_map[test_name][field].append(test[field])
    return test_histo_value_map


def plot_values_thresholds(summary, out_dir, title):
    print("==> Plot values and thresholds <==")
    test_histo_value_map = extract_from_summary(summary, ["value", "threshold"])

    for which_test, histos_values_thresolds in test_histo_value_map.items():

        figure, ax = plt.subplots(figsize=(20, 20))
        ax.plot(range(len(histos_values_thresolds["histograms"])), histos_values_thresolds["value"], label="values", marker="x")
        ax.plot(range(len(histos_values_thresolds["histograms"])), histos_values_thresolds["threshold"], label="thresholds", marker="o")
        ax.legend(loc="best", fontsize=20)
        ax.set_xticks(range(len(histos_values_thresolds["histograms"])))
        ax.set_xticklabels(histos_values_thresolds["histograms"], rotation=90)
        ax.tick_params("both", labelsize=20)

        figure.suptitle(f"{title} ({which_test})", fontsize=40)
        save_path = join(out_dir, f"test_values_thresholds_{which_test}.png")
        figure.tight_layout()
        figure.savefig(save_path)
        plt.close(figure)


def plot_compare_summaries(summaries, fields, out_dir, *, labels=None):
    """
    if labels is given, it needs to have the same length as summaries
    """
    test_histo_value_maps = [extract_from_summary(summary, fields) for summary in summaries]

    # need to get intersection of tests
    test_names = list(set().union(*[list(t.keys()) for t in test_histo_value_maps]))

    if not labels:
        labels = [f"summary_{i}" for i, _ in enumerate(summaries)]

    for test_name in test_names:
        histogram_names_intersection = []
        # First we figure out the intersection of histograms ==> histograms in common
        for test_histo_value_map in test_histo_value_maps:
            if test_name not in test_histo_value_map:
                continue
            this_map = test_histo_value_map[test_name]
            if not histogram_names_intersection:
                histogram_names_intersection = this_map["histograms"]
            histogram_names_intersection =  list(set(histogram_names_intersection) & set(this_map["histograms"]))
        values = {field: [[] for _ in test_histo_value_maps] for field in fields}
        # now fill the correct values of the fields for the histograms in common
        for map_index, test_histo_value_map in enumerate(test_histo_value_maps):
            this_map = test_histo_value_map[test_name]
            for histo_name in histogram_names_intersection:
                i = this_map["histograms"].index(histo_name)
                for f in fields:
                    values[f][map_index].append(this_map[f][i])

        # now plot
        figure, ax = plt.subplots(figsize=(20, 20))
        for field, values_lists in values.items():
            for label, single_values in zip(labels, values_lists):
                ax.plot(range(len(histogram_names_intersection)), single_values, label=f"{label}_{field}")
        ax.legend(loc="best", fontsize=20)
        ax.set_xticks(range(len(histogram_names_intersection)))
        ax.set_xticklabels(histogram_names_intersection, rotation=90)
        ax.tick_params("both", labelsize=20)
        save_path = join(out_dir, f"plot_{test_name}_{'_'.join(labels)}.png")
        figure.tight_layout()
        figure.savefig(save_path)
        plt.close(figure)


def plot_summary_grid(summary, flags, include_patterns, output_path):

    print("==> Plot summary grid <==")

    colors = [None] * len(REL_VAL_SEVERITY_MAP)
    for name, color in REL_VAL_SEVERITY_COLOR_MAP.items():
        colors[REL_VAL_SEVERITY_MAP[name]] = color
    cmap = LinearSegmentedColormap.from_list("Custom", colors, len(colors))
    collect_for_grid = []
    collect_names = []
    collect_annotations = []

    for name, batch in summary.items():
        if include_patterns:
            include_this = False
            for ip in include_patterns:
                if ip in name:
                    include_this = True
                    break
            if not include_this:
                continue
        include_this = not flags
        collect_flags_per_test = [0] * len(REL_VAL_TEST_NAMES_MAP_SUMMARY)
        collect_annotations_per_test = [""] * len(REL_VAL_TEST_NAMES_MAP_SUMMARY)
        for test in batch:
            test_name = test["test_name"]
            if test_name not in REL_VAL_TEST_NAMES_MAP_SUMMARY:
                continue
            if flags and not include_this:
                for f in flags:
                    if test["result"] == f:
                        include_this = True
                        break

            res = test["result"]
            ind = REL_VAL_TEST_NAMES_MAP_SUMMARY[test_name]
            if ind != len(REL_VAL_TEST_NAMES_MAP):
                value_annotaion = f"{test['value']:.2f}" if test["comparable"] else "---"
                collect_annotations_per_test[ind] = f"{test['threshold']:.2f}; {value_annotaion}"
            collect_flags_per_test[ind] = REL_VAL_SEVERITY_MAP[res]

        if not include_this:
            continue
        collect_for_grid.append(collect_flags_per_test)
        collect_names.append(name)
        collect_annotations.append(collect_annotations_per_test)

    if not collect_for_grid:
        print("WARNING: Nothing to plot for summary grid")
        return

    figure, ax = plt.subplots(figsize=(20, 20))
    collect_for_grid = [c for _, c in sorted(zip(collect_names, collect_for_grid))]
    collect_annotations = [c for _, c in sorted(zip(collect_names, collect_annotations))]
    collect_names.sort()
    seaborn.heatmap(collect_for_grid, ax=ax, cmap=cmap, vmin=-0.5, vmax=len(REL_VAL_SEVERITY_MAP) - 0.5, yticklabels=collect_names, xticklabels=REL_VAL_TEST_NAMES_SUMMARY, linewidths=0.5, annot=collect_annotations, fmt="")
    cbar = ax.collections[0].colorbar
    cbar.set_ticks(range(len(REL_VAL_SEVERITY_MAP)))
    cbar.set_ticklabels(REL_VAL_SEVERITIES)
    ax.set_title("Test summary (threshold; value)", fontsize=30)
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def calc_thresholds(rel_val_dict, default_thresholds, margins_thresholds, args):
    """
    calculate thresholds
    """
    the_thresholds={}

    if not args.use_values_as_thresholds:
        for histo_name, tests in rel_val_dict.items():
            this_histo_thresholds=[]
            for t in tests:
                test_name = t["test_name"]
                these_thresholds={}
                these_thresholds["test_name"] = test_name
                these_thresholds["value"] = default_thresholds[test_name]
                this_histo_thresholds.append(these_thresholds)
            the_thresholds[histo_name] = this_histo_thresholds

    else:
        if args.use_values_as_thresholds[0].startswith("@"):
            with open(args.use_values_as_thresholds[0][1:], "r") as f:
                list_of_threshold_files = f.read().splitlines()
        else:
            list_of_threshold_files = args.use_values_as_thresholds

        user_thresholds = []
        for file_name in list_of_threshold_files:
            with open(file_name, "r") as f:
                user_thresholds.append(json.load(f))

        for histo_name, tests in rel_val_dict.items():
            this_histo_thresholds=[]
            for t in tests:
                these_thresholds={}
                test_name = t["test_name"]
                these_thresholds["test_name"] = test_name
                threshold_list = []
                for ut in user_thresholds:
                    for ref_test in ut.get(histo_name, []):
                        if ref_test["test_name"] == test_name:
                            threshold_list.append(ref_test["value"])
                if args.combine_thresholds == "mean":
                    these_thresholds["value"] = margins_thresholds[test_name] * sum(threshold_list) / len(threshold_list)
                else:
                    these_thresholds["value"] = margins_thresholds[test_name] * max(threshold_list)
                this_histo_thresholds.append(these_thresholds)
            the_thresholds[histo_name] = this_histo_thresholds

    return the_thresholds


def make_single_summary(rel_val_dict, args, output_dir):
    """
    Make the usual summary
    """
    def assign_result_flag(is_critical, comparable, passed):
        result = "GOOD"
        if is_critical:
            if not comparable:
                result = "CRIT_NC"
            elif not passed:
                result = "BAD"
        else:
            if not comparable:
                result = "NONCRIT_NC"
            elif not passed:
                result = "WARNING"
        return result

    user_thresholds = {}
    this_summary = {}

    default_thresholds = {"test_chi2": args.chi2_threshold,
                          "test_bin_cont": args.rel_mean_diff_threshold,
                          "test_num_entries": args.rel_entries_diff_threshold}
    margins_thresholds = {"test_chi2": args.chi2_threshold_margin,
                          "test_bin_cont": args.rel_mean_diff_threshold_margin,
                          "test_num_entries": args.rel_entries_diff_threshold_margin}

    the_thresholds = calc_thresholds(rel_val_dict, default_thresholds, margins_thresholds, args)
    with open(join(output_dir, "used_thresholds.json"), "w") as f:
            json.dump(the_thresholds, f, indent=2)

    for histo_name, tests in rel_val_dict.items():
        test_summary = {"test_name": TEST_SUMMARY_NAME,
                        "value": None,
                        "threshold": None,
                        "result": None}
        is_critical_summary = False
        passed_summary = True
        is_comparable_summary = True
        these_tests = []
        for t in tests:
            if t["test_name"] == TEST_SUMMARY_NAME:
                continue
            test_name = t["test_name"]
            test_id = REL_VAL_TEST_NAMES_MAP[test_name]
            threshold = the_thresholds[histo_name][REL_VAL_TEST_NAMES_MAP[test_name]]["value"]
            t["threshold"] = threshold

            comparable = t["comparable"]
            passed = True
            is_critical = REL_VAL_TEST_CRITICAL[test_id] or histo_name.find("_ratioFromTEfficiency") != -1
            if comparable:
                passed = t["value"] <= threshold

            t["result"] = assign_result_flag(is_critical, comparable, passed)

            is_critical_summary = is_critical or is_critical_summary
            is_comparable_summary = comparable and is_comparable_summary
            if is_critical:
                # only mark potentially as failed if we run over a critical test
                passed_summary = passed_summary and passed
            these_tests.append(t)

        test_summary["result"] = assign_result_flag(is_critical_summary, is_comparable_summary, passed_summary)
        test_summary["comparable"] = is_comparable_summary
        these_tests.append(test_summary)
        this_summary[histo_name] = these_tests

    return this_summary


def rel_val_files(files1, files2, args, output_dir):
    """
    RelVal for 2 ROOT files, simply a wrapper around ReleaseValidation.C macro
    """
    def run_macro(cmd, log_file):
        p = Popen(split(cmd), cwd=output_dir, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
        log_file = open(log_file, 'a')
        for line in p.stdout:
            log_file.write(line)
        p.wait()
        log_file.close()

    print("==> Process and compare 2 sets of files <==")

    if not exists(output_dir):
        makedirs(output_dir)
    log_file_extract = join(abspath(output_dir), "extract_and_flatten.log")
    log_file_rel_val = join(abspath(output_dir), "rel_val.log")
    if args.include_dirs:
        include_directories = ",".join(args.include_dirs)
    else:
        include_directories = ""

    print(f"Extraction of files\n{','.join(files1)}")
    file_1 = "newfile1.root"
    file_from_here = join(output_dir, file_1)
    if exists(file_from_here) and not args.add:
        remove(file_from_here)
    for f in files1:
        f = abspath(f)
        cmd = f"\\(\\\"{f}\\\",\\\"{file_1}\\\",\\\"\\\",\\\"{include_directories}\\\"\\)"
        cmd = f"root -l -b -q {ROOT_MACRO_EXTRACT}{cmd}"
        run_macro(cmd, log_file_extract)

    print(f"Extraction of files\n{','.join(files2)}")
    file_2 = "newfile2.root"
    file_from_here = join(output_dir, file_2)
    if exists(file_from_here) and not args.add:
        remove(file_from_here)
    for f in files2:
        f = abspath(f)
        cmd = f"\\(\\\"{f}\\\",\\\"{file_2}\\\",\\\"{file_1}\\\",\\\"{include_directories}\\\"\\)"
        cmd = f"root -l -b -q {ROOT_MACRO_EXTRACT}{cmd}"
        run_macro(cmd, log_file_extract)

    cmd = f"\\(\\\"{file_1}\\\",\\\"{file_2}\\\",{args.test}\\)"
    cmd = f"root -l -b -q {ROOT_MACRO_RELVAL}{cmd}"
    print("Running RelVal on extracted objects")
    run_macro(cmd, log_file_rel_val)
    json_path = join(output_dir, "RelVal.json")

    if exists(json_path):
        # go through all we found
        rel_val_summary = None
        with open(json_path, "r") as f:
            rel_val_summary = json.load(f)
        final_summary = make_single_summary(rel_val_summary, args, output_dir)
        with open(join(output_dir, "Summary.json"), "w") as f:
            json.dump(final_summary, f, indent=2)
        plot_pie_charts(final_summary, output_dir, "")
        plot_values_thresholds(final_summary, output_dir, "")
        plot_summary_grid(final_summary, None, None, join(output_dir, "SummaryTests.png"))

    return 0


def rel_val_files_only(args):
    return rel_val_files(args.input1, args.input2, args, args.output)


def map_histos_to_severity(summary, include_patterns=None):
    """
    Map the histogram names to their severity of the test
    """
    test_n_hist_map = {s: [] for i, s in enumerate(REL_VAL_SEVERITIES) if REL_VAL_SEVERITIES_USE_SUMMARY[i]}

    # need to re-arrange the JSON structure abit for per-test result pie charts
    for histo_name, tests in summary.items():
        if include_patterns:
            include_this = False
            for ip in include_patterns:
                if ip in histo_name:
                    include_this = True
                    break
            if not include_this:
                continue

        # loop over tests done
        for test in tests:
            test_name = test["test_name"]
            if test_name != TEST_SUMMARY_NAME:
                continue
            result = test["result"]
            test_n_hist_map[result].append(histo_name)

    return test_n_hist_map


def print_summary(summary, include_patterns=None):
    """
    Check if any 2 histograms have a given severity level after RelVal
    """

    test_n_hist_map = map_histos_to_severity(summary, include_patterns)

    n_all = sum(len(v) for v in test_n_hist_map.values())
    print(f"\n#####\nNumber of compared histograms: {n_all}\nBased on critical tests, severities are\n")
    for sev, histos in test_n_hist_map.items():
        print(f"  {sev}: {len(histos)}")
    print("#####\n")


def make_global_summary(in_dir):
    """
    Make a summary per histogram (that should be able to be parsed by Grafana eventually)
    """
    file_paths = glob(f"{in_dir}/**/Summary.json", recursive=True)
    summary = {}

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
        for histo_name, tests in current_summary.items():
            summary[histo_name] = tests
            # loop over tests done
            for test in tests:
                test["name"] = histo_name
                test["type_global"] = type_global
                test["type_specific"] = type_specific
                test["rel_path_plot"] = join(rel_path_plot, f"{histo_name}.png")
    return summary


def rel_val_sim_dirs(args):
    """
    Make full RelVal for 2 simulation directories
    """
    dir1 = args.input1[0]
    dir2 = args.input2[0]
    output_dir = args.output

    look_for = "Summary.json"
    summary_dict = {}

    config = args.dir_config
    with open(config, "r") as f:
        config = json.load(f)

    run_over_keys = list(config.keys())
    if args.dir_config_enable:
        run_over_keys = [rok for rok in run_over_keys if rok in args.dir_config_enable]
    if args.dir_config_disable:
        run_over_keys = [rok for rok in run_over_keys if rok not in args.dir-dir_config_disable]
    if not run_over_keys:
        print("WARNING: All keys in config disabled, nothing to do")
        return 0

    for rok in run_over_keys:
        current_dir_config = config[rok]
        # now run over name and path (to glob)
        for name, path in current_dir_config.items():
            current_files = find_mutual_files((dir1, dir2), path)
            if not current_files:
                print(f"WARNING: Nothing found for search path {path}, continue")
                continue
            in1 = [join(dir1, cf) for cf in current_files]
            in2 = [join(dir2, cf) for cf in current_files]
            current_output_dir = join(output_dir, rok, name)
            if not exists(current_output_dir):
                makedirs(current_output_dir)
            rel_val_files(in1, in2, args, current_output_dir)
    return 0


def rel_val(args):
    """
    Entry point for RelVal
    """
    if args.add:
        print(f"NOTE: Extracted objects will be added to existing ones in case there was already a RelVal at {args.output}.\n")
    func = None
    # construct the bit mask
    args.test = 1 * args.with_test_chi2 + 2 * args.with_test_bincont + 4 * args.with_test_numentries
    if not args.test:
        args.test = 7
    if not exists(args.output):
        makedirs(args.output)
    if is_sim_dir(args.input1[0]) and is_sim_dir(args.input2[0]):
        if not args.dir_config:
            print("ERROR: RelVal to be run on 2 directories. Please provide a configuration what to validate.")
            return 1
        func = rel_val_sim_dirs
    else:
        func = rel_val_files_only
        for f in args.input1 + args.input2:
            if not isfile(f):
                func = None
                break
        # simply check if files, assume that they would be ROOT files in that case
    if not func:
        print("Please provide either 2 sets of files or 2 simulation directories as input.")
        return 1
    if not exists(args.output):
        makedirs(args.output)
    func(args)
    global_summary = make_global_summary(args.output)
    with open(join(args.output, "SummaryGlobal.json"), "w") as f:
        json.dump(global_summary, f, indent=2)
    print_summary(global_summary)
    return 0


def inspect(args):
    """
    Inspect a Summary.json in view of RelVal severity
    """
    path = args.path

    def get_filepath(d):
        summary_global = join(d, "SummaryGlobal.json")
        if exists(summary_global):
            return summary_global
        summary = join(d, "Summary.json")
        if exists(summary):
            return summary
        print(f"Can neither find {summary_global} nor {summary}. Nothing to work with.")
        return None

    if isdir(path):
        path = get_filepath(path)
        if not path:
            return 1

    output_dir = args.output or join(dirname(path), "user_summary")
    if not exists(output_dir):
        makedirs(output_dir)

    current_summary = None
    with open(path, "r") as f:
        current_summary = json.load(f)
    summary = make_single_summary(current_summary, args, output_dir)
    with open(join(output_dir, "Summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print_summary(summary)

    if args.plot:
        plot_pie_charts(summary, output_dir, "")
        plot_values_thresholds(summary, output_dir, "")
        plot_summary_grid(summary, args.flags, args.include_patterns, join(output_dir, "SummaryTests.png"))

    return 0


def compare(args):
    """
    Compare 2 RelVal outputs with one another
    """
    output_dir = args.output

    if not args.difference and not args.compare_values:
        args.difference, args.compare_values = (True, True)

    # plot comparison of values and thresholds of both RelVals per test
    if args.compare_values:
        summaries_common = find_mutual_files((args.input[0], args.input[1]), "Summary.json")
        for summaries in summaries_common:
            output_dir_this = join(output_dir, f"{summaries.replace('/', '_')}_dir")
            if not exists(output_dir_this):
                makedirs(output_dir_this)
            summaries = [join(input, summaries) for input in args.input]
            for i, _ in enumerate(summaries):
                with open(summaries[i], "r") as f:
                    summaries[i] = json.load(f)
            plot_compare_summaries(summaries, ["threshold", "value"], output_dir_this)

    # print the histogram names with different severities per test
    if args.difference:
        summaries_json = [join(json_input, "SummaryGlobal.json") for json_input in args.input]
        summaries = []
        for i, summary in enumerate(summaries_json):
            if not exists(summary):
                print(f"WARNING: Cannot find expected {summary}.")
                return 1
            with open(summaries_json, "r") as f:
                summaries.append(json.load(f))

        s = "\nCOMPARING RELVAL SUMMARY\n"
        summaries = [map_histos_to_severity(summary) for summary in summaries]
        print("Histograms with different RelVal results from 2 RelVal runs")
        for severity in REL_VAL_SEVERITY_MAP:
            intersection = list(set(summaries[0][severity]) & set(summaries[1][severity]))
            s += f"==> SEVERITY {severity} <=="
            print(f"==> SEVERITY {severity} <==")
            s += "\n"
            for i, summary in enumerate(summaries):
                print(f"FILE {i+1}")
                s += f"FILE {i+1}: "
                counter = 0
                for histo_name in summary[severity]:
                    if histo_name not in intersection:
                        print(f"  {histo_name}")
                        counter += 1
                s += f"{counter}   "
            s += "\n"
        print(s)
    return 0


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

    summary = None
    with open(json_in, "r") as f:
        summary = json.load(f)
    with open(out_file, "w") as f:
        for i, (histo_name, tests) in enumerate(summary.items()):
            if not tests:
                continue
            s = f"{row_tags},type_global={tests[0]['type_global']},type_specific={tests[0]['type_specific']},id={i}"
            if args.web_storage:
                s += f",web_storage={join(args.web_storage, tests[0]['rel_path_plot'])}"
            s += f" histogram_name=\"{histo_name}\""
            for test in tests:
                s += f",{test['test_name']}={REL_VAL_SEVERITY_MAP[test['result']]}"
            f.write(f"{s}\n")

def dir_comp(args):
    """
    Entry point for RelVal
    """
    dir1 = args.input1[0]
    dir2 = args.input2[0]
    if not isdir(dir1) or not isdir(dir2):
        print("ERROR: This comparison requires 2 directories as input")
        return 1
    if not exists(args.output):
        makedirs(args.output)
    # file sizes, this is just done on everything to be found in both directories
    file_sizes_to_json = file_sizes([dir1, dir2], args.threshold)
    with open(join(args.output, "file_sizes.json"), "w") as f:
        json.dump(file_sizes_to_json, f, indent=2)
    return 0


def print_header():
    print("\n#########################\n#                       #\n# RUN ReleaseValidation #\n#                       #\n#########################\n")


def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Wrapping ReleaseValidation macro')

    common_file_parser = argparse.ArgumentParser(add_help=False)
    common_file_parser.add_argument("-i", "--input1", nargs="*", help="EITHER first set of input files for comparison OR first input directory from simulation for comparison", required=True)
    common_file_parser.add_argument("-j", "--input2", nargs="*", help="EITHER second set of input files for comparison OR second input directory from simulation for comparison", required=True)

    common_threshold_parser = argparse.ArgumentParser(add_help=False)
    common_threshold_parser.add_argument("--chi2-threshold", dest="chi2_threshold", type=float, help="Chi2 threshold", default=1.5)
    common_threshold_parser.add_argument("--rel-mean-diff-threshold", dest="rel_mean_diff_threshold", type=float, help="Threshold of relative difference in mean", default=1.5)
    common_threshold_parser.add_argument("--rel-entries-diff-threshold", dest="rel_entries_diff_threshold", type=float, help="Threshold of relative difference in number of entries", default=0.01)
    common_threshold_parser.add_argument("--use-values-as-thresholds", nargs="*", dest="use_values_as_thresholds", help="Use values from other runs as thresholds for this one")
    # The following only take effect for thresholds given via an input file
    common_threshold_parser.add_argument("--combine-thresholds", dest="combine_thresholds",  choices=["mean", "max"], help="Arithmetic mean or maximum is chosen as threshold value", default="mean")
    common_threshold_parser.add_argument("--chi2-threshold-margin", dest="chi2_threshold_margin", type=float, help="Margin to apply to the chi2 threshold extracted from file", default=1.0)
    common_threshold_parser.add_argument("--rel-mean-diff-threshold-margin", dest="rel_mean_diff_threshold_margin", type=float, help="Margin to apply to the rel_mean_diff threshold extracted from file", default=1.0)
    common_threshold_parser.add_argument("--rel-entries-diff-threshold-margin", dest="rel_entries_diff_threshold_margin", type=float, help="Margin to apply to the rel_entries_diff threshold extracted from file", default=1.0)

    sub_parsers = parser.add_subparsers(dest="command")
    rel_val_parser = sub_parsers.add_parser("rel-val", parents=[common_file_parser, common_threshold_parser])
    rel_val_parser.add_argument("--with-test-chi2", dest="with_test_chi2", action="store_true", help="run chi2 test")
    rel_val_parser.add_argument("--with-test-bincont", dest="with_test_bincont", action="store_true", help="run bin-content test")
    rel_val_parser.add_argument("--with-test-numentries", dest="with_test_numentries", action="store_true", help="run number-of-entries test")
    rel_val_parser.add_argument("--dir-config", dest="dir_config", help="What to take into account in a given directory")
    rel_val_parser.add_argument("--dir-config-enable", dest="dir_config_enable", nargs="*", help="only enable these top keys in your dir-config")
    rel_val_parser.add_argument("--dir-config-disable", dest="dir_config_disable", nargs="*", help="disable these top keys in your dir-config (precedence over dir-config-enable)")
    rel_val_parser.add_argument("--include-dirs", dest="include_dirs", nargs="*", help="only inlcude directories; note that each pattern is assumed to start in the top-directory (at the moment no regex or *)")
    rel_val_parser.add_argument("--add", action="store_true", help="If given and there is already a RelVal in the output directory, extracted objects will be added to the existing ones")
    rel_val_parser.add_argument("--output", "-o", help="output directory", default="rel_val")
    rel_val_parser.set_defaults(func=rel_val)

    inspect_parser = sub_parsers.add_parser("inspect", parents=[common_threshold_parser])
    inspect_parser.add_argument("path", help="either complete file path to a Summary.json or SummaryGlobal.json or directory where one of the former is expected to be")
    inspect_parser.add_argument("--plot", action="store_true", help="Plot the summary grid")
    inspect_parser.add_argument("--print", action="store_true", help="Print the summary on the screen")
    inspect_parser.add_argument("--flags", nargs="*", help="extract all objects which have at least one test with this severity flag", choices=list(REL_VAL_SEVERITY_MAP.keys()))
    inspect_parser.add_argument("--include-patterns", dest="include_patterns", nargs="*", help="include objects whose name includes at least one of the given patterns (at the moment no regex or *)")
    inspect_parser.add_argument("--output", "-o", help="output directory, by default points to directory where the Summary.json was found")
    inspect_parser.set_defaults(func=inspect)

    compare_parser = sub_parsers.add_parser("compare", parents=[common_file_parser])
    compare_parser.add_argument("--output", "-o", help="output directory", default="rel_val_comparison")
    compare_parser.add_argument("--difference", action="store_true", help="plot histograms with different severity")
    compare_parser.add_argument("--compare-values", action="store_true", help="plot value and threshold comparisons of RelVals")
    compare_parser.set_defaults(func=compare)

    influx_parser = sub_parsers.add_parser("influx")
    influx_parser.add_argument("--dir", help="directory where ReleaseValidation was run", required=True)
    influx_parser.add_argument("--web-storage", dest="web_storage", help="full base URL where the RelVal results are supposed to be")
    influx_parser.add_argument("--tags", nargs="*", help="tags to be added for influx, list of key=value")
    influx_parser.add_argument("--table-suffix", dest="table_suffix", help="prefix for table name")
    influx_parser.set_defaults(func=influx)

    file_size_parser = sub_parsers.add_parser("file-sizes", parents=[common_file_parser])
    file_size_parser.add_argument("--threshold", type=float, default=0.5, help="threshold for how far file sizes are allowed to diverge before warning")
    file_size_parser.add_argument("--output", "-o", help="output directory", default="file_sizes")
    file_size_parser.set_defaults(func=dir_comp)

    args = parser.parse_args()
    print_header()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
