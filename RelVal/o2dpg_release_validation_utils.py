#!/usr/bin/env python3
#
# Definition common functionality

import sys
import argparse
import re
from os.path import join, abspath, exists, isdir, dirname
from glob import glob
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
from itertools import combinations
from shlex import split
import json
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import seaborn

sys.path.append(join(dirname(__file__), '.', 'o2dpg_release_validation_variables'))
import o2dpg_release_validation_variables as variables


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


def load_patterns(include_patterns, exclude_patterns, print_loaded=True):
    """
    Load include patterns to be used for regex comparion
    """
    def load_this_patterns(patterns):
        if not patterns or not patterns[0].startswith("@"):
            return patterns
        with open(include_patterns[0][1:], "r") as f:
            return f.read().splitlines()

    include_patterns = load_this_patterns(include_patterns)
    exclude_patterns = load_this_patterns(exclude_patterns)
    if print_loaded:
        if include_patterns:
            print("Following patterns are included:")
            for ip in include_patterns:
                print(f"  - {ip}")
        if exclude_patterns:
            print("Following patterns are excluded:")
            for ep in exclude_patterns:
                print(f"  - {ep}")
    return include_patterns, exclude_patterns


def check_patterns(name, include_patterns, exclude_patterns):
    """
    check a name against a list of regex
    """
    if not include_patterns and not exclude_patterns:
        return True
    if include_patterns:
        for ip in include_patterns:
            if re.search(ip, name):
                return True
        return False
    if exclude_patterns:
        for ip in exclude_patterns:
            if re.search(ip, name):
                return False
        return True
    return False


def check_flags(tests, flags, flags_summary):
    """
    include histograms based on the flags
    """
    if not flags and not flags_summary:
        return True
    for test in tests:
        if test["test_name"] == variables.REL_VAL_TEST_SUMMARY_NAME:
            if flags_summary:
                for f in flags_summary:
                    if test["result"] == f:
                        return True
        elif flags:
            for f in flags:
                if test["result"] == f:
                    return True
    return False


def plot_pie_charts(summary, out_dir, title, include_patterns=None, exclude_patterns=None):

    print("==> Plot pie charts <==")

    test_n_hist_map = {}

    # need to re-arrange the JSON structure abit for per-test result pie charts
    for histo_name, tests in summary.items():
        # check if histo_name is in include patterns
        if not check_patterns(histo_name, include_patterns, exclude_patterns):
            continue
        # loop over tests done
        for test in tests:
            test_name = test["test_name"]
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
            colors.append(variables.REL_VAL_SEVERITY_COLOR_MAP[flag])

        figure, ax = plt.subplots(figsize=(20, 20))
        ax.pie(n_histos, explode=[0.05 for _ in labels], labels=labels, autopct="%1.1f%%", startangle=90, textprops={"fontsize": 30}, colors=colors)
        ax.axis("equal")
        ax.axis("equal")

        figure.suptitle(f"{title} ({which_test})", fontsize=40)
        save_path = join(out_dir, f"pie_chart_{which_test}.png")
        figure.savefig(save_path)
        plt.close(figure)


def extract_from_summary(summary, fields, include_patterns=None, exclude_patterns=None):
    """
    Extract a fields from summary per test and histogram name
    """
    test_histo_value_map = {}
    # need to re-arrange the JSON structure abit for per-test result pie charts
    for histo_name, tests in summary.items():
        # check if histo_name is in include patterns
        if not check_patterns(histo_name, include_patterns, exclude_patterns):
            continue
        # loop over tests done
        for test in tests:
            test_name = test["test_name"]
            if test_name not in test_histo_value_map:
                test_histo_value_map[test_name] = {field: [] for field in fields}
                test_histo_value_map[test_name]["histograms"] = []
            if not test["comparable"]:
                continue
            test_histo_value_map[test_name]["histograms"].append(histo_name)
            for field in fields:
                test_histo_value_map[test_name][field].append(test[field])
    return test_histo_value_map


def plot_values_thresholds(summary, out_dir, title, include_patterns=None, exclude_patterns=None):
    print("==> Plot values and thresholds <==")
    test_histo_value_map = extract_from_summary(summary, ["value", "threshold"], include_patterns, exclude_patterns)

    for which_test, histos_values_thresolds in test_histo_value_map.items():
        if which_test == variables.REL_VAL_TEST_SUMMARY_NAME:
            continue
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


def plot_summary_grid(summary, flags, include_patterns, exclude_patterns, output_path):

    print("==> Plot summary grid <==")

    colors = [None] * len(variables.REL_VAL_SEVERITY_MAP)
    for name, color in variables.REL_VAL_SEVERITY_COLOR_MAP.items():
        colors[variables.REL_VAL_SEVERITY_MAP[name]] = color
    cmap = LinearSegmentedColormap.from_list("Custom", colors, len(colors))
    collect_for_grid = []
    collect_names = []
    collect_annotations = []

    for name, batch in summary.items():
        if not check_patterns(name, include_patterns, exclude_patterns):
            continue
        include_this = not flags
        collect_flags_per_test = [0] * len(variables.REL_VAL_TEST_NAMES_MAP_SUMMARY)
        collect_annotations_per_test = [""] * len(variables.REL_VAL_TEST_NAMES_MAP_SUMMARY)
        for test in batch:
            test_name = test["test_name"]
            if test_name not in variables.REL_VAL_TEST_NAMES_MAP_SUMMARY:
                continue
            if flags and not include_this:
                for f in flags:
                    if test["result"] == f:
                        include_this = True
                        break

            res = test["result"]
            ind = variables.REL_VAL_TEST_NAMES_MAP_SUMMARY[test_name]
            if ind != len(variables.REL_VAL_TEST_NAMES_MAP):
                value_annotaion = f"{test['value']:.3f}" if test["comparable"] else "---"
                collect_annotations_per_test[ind] = f"{test['threshold']:.3f}; {value_annotaion}"
            collect_flags_per_test[ind] = variables.REL_VAL_SEVERITY_MAP[res]

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
    seaborn.heatmap(collect_for_grid, ax=ax, cmap=cmap, vmin=-0.5, vmax=len(variables.REL_VAL_SEVERITY_MAP) - 0.5, yticklabels=collect_names, xticklabels=variables.REL_VAL_TEST_NAMES_SUMMARY, linewidths=0.5, annot=collect_annotations, fmt="")
    cbar = ax.collections[0].colorbar
    cbar.set_ticks(range(len(variables.REL_VAL_SEVERITY_MAP)))
    cbar.set_ticklabels(variables.REL_VAL_SEVERITIES)
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
                if test_name == variables.REL_VAL_TEST_SUMMARY_NAME:
                    continue
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
                user_thresholds.append(json.load(f).get("objects",{}))

        for histo_name, tests in rel_val_dict.items():
            this_histo_thresholds=[]
            for t in tests:
                these_thresholds={}
                test_name = t["test_name"]
                if test_name == variables.REL_VAL_TEST_SUMMARY_NAME:
                    continue
                these_thresholds["test_name"] = test_name
                threshold_list = []
                for ut in user_thresholds:
                    for ref_test in ut.get(histo_name, []):
                        if ref_test["test_name"] == test_name:
                            threshold_list.append(ref_test["value"])
                if args.combine_thresholds == "mean":
                    tuned_threshold = pow(margins_thresholds[test_name], variables.REL_VAL_TEST_UPPER_LOWER_THRESHOLD[variables.REL_VAL_TEST_NAMES_MAP[test_name]]) * sum(threshold_list) / len(threshold_list)
                else:
                    if REL_VAL_TEST_UPPER_LOWER_THRESHOLD[REL_VAL_TEST_NAMES_MAP[test_name]] == 1:
                        maxmin = max(threshold_list)
                    else:
                        maxmin = min(threshold_list)
                    tuned_threshold = pow(margins_thresholds[test_name], variables.REL_VAL_TEST_UPPER_LOWER_THRESHOLD[variables.REL_VAL_TEST_NAMES_MAP[test_name]]) * maxmin
                if args.combine_tuned_and_fixed_thresholds:
                    if variables.REL_VAL_TEST_UPPER_LOWER_THRESHOLD[variables.REL_VAL_TEST_NAMES_MAP[test_name]] == 1:
                        these_thresholds["value"] = max(tuned_threshold,default_thresholds[test_name])
                    else:
                        these_thresholds["value"] = min(tuned_threshold,default_thresholds[test_name])
                else:
                    these_thresholds["value"] = tuned_threshold
                this_histo_thresholds.append(these_thresholds)
            the_thresholds[histo_name] = this_histo_thresholds

    return the_thresholds


def write_single_summary(comp_objects, meta_info, path):
    with open(path, "w") as f:
        json.dump({"objects": comp_objects, "meta_info": meta_info}, f, indent=2)


def read_single_summary(path):
    with open(path, "r") as f:
        d = json.load(f)
        return d.get("objects", {}), d.get("meta_info", {})


def make_single_meta_info(args):
    return {"batch_i": [abspath(path) for path in args.input1], "batch_j": [abspath(path) for path in args.input2]}


def make_single_summary(rel_val_dict, args, output_dir, include_patterns=None, exclude_patterns=None, flags=None, flags_summary=None):
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

    this_summary = {}

    default_thresholds = {t: getattr(args, f"{t}_threshold") for t in variables.REL_VAL_TEST_NAMES}
    margins_thresholds = {t: getattr(args, f"{t}_threshold_margin") for t in variables.REL_VAL_TEST_NAMES}
    test_enabled = {t: getattr(args, f"with_{t}") for t in variables.REL_VAL_TEST_NAMES}
    if not any(test_enabled.values()):
        test_enabled = {t: True for t in test_enabled}

    the_thresholds = calc_thresholds(rel_val_dict, default_thresholds, margins_thresholds, args)
    with open(join(output_dir, "used_thresholds.json"), "w") as f:
            json.dump(the_thresholds, f, indent=2)

    for histo_name, tests in rel_val_dict.items():
        if not check_patterns(histo_name, include_patterns, exclude_patterns):
            continue
        test_summary = {"test_name": variables.REL_VAL_TEST_SUMMARY_NAME,
                        "value": None,
                        "threshold": None,
                        "result": None}
        is_critical_summary = False
        passed_summary = True
        is_comparable_summary = True
        these_tests = []
        for t in tests:
            if t["test_name"] == variables.REL_VAL_TEST_SUMMARY_NAME or not test_enabled[t["test_name"]]:
                continue
            test_name = t["test_name"]
            test_id = variables.REL_VAL_TEST_NAMES_MAP[test_name]
            threshold = the_thresholds[histo_name][variables.REL_VAL_TEST_NAMES_MAP[test_name]]["value"]
            t["threshold"] = threshold

            comparable = t["comparable"]
            passed = True
            is_critical = variables.REL_VAL_TEST_CRITICAL[test_id] or histo_name.find("_ratioFromTEfficiency") != -1
            if comparable:
                passed = t["value"] * variables.REL_VAL_TEST_UPPER_LOWER_THRESHOLD[variables.REL_VAL_TEST_NAMES_MAP[t["test_name"]]] <=  threshold * variables.REL_VAL_TEST_UPPER_LOWER_THRESHOLD[variables.REL_VAL_TEST_NAMES_MAP[t["test_name"]]]

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
        if not check_flags(these_tests, flags, flags_summary):
            continue
        this_summary[histo_name] = these_tests

    return this_summary


def run_macro(cmd, log_file, cwd=None):
    p = Popen(split(cmd), cwd=cwd, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
    log_file = open(log_file, 'a')
    for line in p.stdout:
        log_file.write(line)
    p.wait()
    log_file.close()


def map_histos_to_severity(summary, include_patterns=None, exclude_patterns=None):
    """
    Map the histogram names to their severity of the test
    """
    test_n_hist_map = {s: [] for i, s in enumerate(variables.REL_VAL_SEVERITIES) if variables.REL_VAL_SEVERITIES_USE_SUMMARY[i]}

    # need to re-arrange the JSON structure abit for per-test result pie charts
    for histo_name, tests in summary.items():
        # check if histo_name is in include_patterns
        if not check_patterns(histo_name, include_patterns, exclude_patterns):
            continue
        # loop over tests done
        for test in tests:
            test_name = test["test_name"]
            if test_name != variables.REL_VAL_TEST_SUMMARY_NAME:
                continue
            result = test["result"]
            test_n_hist_map[result].append(histo_name)

    return test_n_hist_map


def print_summary(summary, include_patterns=None, exclude_patterns=None, long=False):
    """
    Check if any 2 histograms have a given severity level after RelVal
    """

    test_n_hist_map = map_histos_to_severity(summary, include_patterns, exclude_patterns)

    n_all = sum(len(v) for v in test_n_hist_map.values())
    print(f"\n#####\nNumber of compared histograms: {n_all}\nBased on critical tests, severities are\n")
    for sev, histos in test_n_hist_map.items():
        print(f"  {sev}: {len(histos)}")
        if long:
            for i, h in enumerate(histos, start=1):
                print(f"    {i}. {h}")
    print("#####\n")


def get_summary_path(path):
    if isdir(path):
        path = join(path, "Summary.json")
    if exists(path):
        return path
    print(f"ERROR: Cannot neither find {path}.")
    return None
