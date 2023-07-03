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
# usage: o2dpg_release_validation.py rel-val [-h] -i [INPUT1 ...] -j
#                                            [INPUT2 ...]
#                                            [--use-values-as-thresholds [USE_VALUES_AS_THRESHOLDS ...]]
#                                            [--combine-thresholds {mean,max/min}]
#                                            [--with-test-chi2]
#                                            [--test-chi2-threshold CHI2_THRESHOLD]
#                                            [--test-chi2-threshold-margin CHI2_THRESHOLD_MARGIN]
#                                            [--with-test-bin-cont]
#                                            [--test-bin-cont-threshold BIN_CONT_THRESHOLD]
#                                            [--test-bin-cont-threshold-margin BIN_CONT_THRESHOLD_MARGIN]
#                                            [--with-test-num-entries]
#                                            [--test-num-entries-threshold NUM_ENTRIES_THRESHOLD]
#                                            [--test-num-entries-threshold-margin NUM_ENTRIES_THRESHOLD_MARGIN]
#                                            [--include-dirs [INCLUDE_DIRS ...]]
#                                            [--add] [--output OUTPUT]
#
# optional arguments:
#   -h, --help            show this help message and exit
#   -i [INPUT1 ...], --input1 [INPUT1 ...]
#                         EITHER first set of input files for comparison OR
#                         first input directory from simulation for comparison
#   -j [INPUT2 ...], --input2 [INPUT2 ...]
#                         EITHER second set of input files for comparison OR
#                         second input directory from simulation for comparison
#   --use-values-as-thresholds [USE_VALUES_AS_THRESHOLDS ...]
#                         Use values from another run as thresholds for this one
#   --combine-thresholds {mean,max/min}
#                         Arithmetic mean or maximum/minimum is chosen as threshold
#                         value
#   --with-test-chi2      run chi2 test
#   --test-chi2-threshold CHI2_THRESHOLD
#                         chi2 threshold
#   --test-chi2-threshold-margin CHI2_THRESHOLD_MARGIN
#                         Margin to apply to the chi2 threshold extracted from
#                         file
#   --with-test-bin-cont  run bin_cont test
#   --test-bin-cont-threshold BIN_CONT_THRESHOLD
#                         bin_cont threshold
#   --test-bin-cont-threshold-margin BIN_CONT_THRESHOLD_MARGIN
#                         Margin to apply to the bin_cont threshold extracted
#                         from file
#   --with-test-num-entries
#                         run num_entries test
#   --test-num-entries-threshold NUM_ENTRIES_THRESHOLD
#                         num_entries threshold
#   --test-num-entries-threshold-margin NUM_ENTRIES_THRESHOLD_MARGIN
#                         Margin to apply to the num_entries threshold extracted
#                         from file
#   --include-dirs [INCLUDE_DIRS ...]
#                         only inlcude directories; note that each pattern is
#                         assumed to start in the top-directory (at the moment
#                         no regex or *)
#   --add                 If given and there is already a RelVal in the output
#                         directory, extracted objects will be added to the
#                         existing ones
#   --output OUTPUT, -o OUTPUT
#                         output directory

import sys
import argparse
import re
from os import environ, makedirs, remove
from os.path import join, abspath, exists, isdir, dirname, basename, relpath
from glob import glob
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
from itertools import combinations
from shlex import split
import json
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import seaborn
from shutil import copy

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)

sys.path.append(join(dirname(__file__), '.', 'o2dpg_release_validation_variables'))
import o2dpg_release_validation_variables as variables

sys.path.append(join(dirname(__file__), '.', 'o2dpg_release_validation_utils'))
from o2dpg_release_validation_utils import *

ROOT_MACRO_EXTRACT=join(O2DPG_ROOT, "RelVal", "ExtractAndFlatten.C")
ROOT_MACRO_RELVAL=join(O2DPG_ROOT, "RelVal", "ReleaseValidation.C")

from ROOT import gROOT

gROOT.SetBatch()


def plot_compare_summaries(summaries, fields, out_dir, *, labels=None, include_patterns=None, exclude_patterns=None):
    """
    if labels is given, it needs to have the same length as summaries
    """
    test_histo_value_maps = [extract_from_summary(summary, fields, include_patterns, exclude_patterns) for summary in summaries]

    # need to get intersection of tests
    test_names = list(set().union(*[list(t.keys()) for t in test_histo_value_maps]))

    if not labels:
        labels = [f"summary_{i}" for i, _ in enumerate(summaries)]

    for test_name in test_names:
        if test_name == variables.REL_VAL_TEST_SUMMARY_NAME:
            continue
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
        save_path = join(out_dir, f"values_thresholds_{test_name}.png")
        figure.tight_layout()
        figure.savefig(save_path)
        plt.close(figure)


def extract(input_filenames, target_filename, include_file_directories=None, add_if_exists=False, reference_extracted=None):
    """
    Wrap the extraction of objects to be compared

    Will be extracted (from TH1, QC objects, TTree etc.), converted to TH1 and put into a flat ROOT file structure.

    Args:
        reference_extracted: str
        is used in case of the extraction of TTrees in which case the x-axis binning will be set according to that reference
        to make objects comparable.

        include_file_directories: list or None
        will be passed to the ROOT macro and if not None, only sub-directories matching that will be browsed and extracted
    """
    if not include_file_directories:
        include_file_directories = ""

    if not reference_extracted:
        reference_extracted = ""

    if include_file_directories:
        include_file_directories = ",".join(include_file_directories)
    else:
        include_file_directories = ""

    if exists(target_filename) and not add_if_exists:
        remove(target_filename)

    # The ROOT macro is run inside the cwd and puts basename there
    cwd = dirname(target_filename)
    target_filename = basename(target_filename)
    log_file_name = f"{target_filename}_extract_and_flatten.log"

    print(f"Extraction of files\n{','.join(input_filenames)}")

    for f in input_filenames:
        f = abspath(f)
        cmd = f"\\(\\\"{f}\\\",\\\"{target_filename}\\\",\\\"{reference_extracted}\\\",\\\"{include_file_directories}\\\"\\)"
        cmd = f"root -l -b -q {ROOT_MACRO_EXTRACT}{cmd}"
        run_macro(cmd, log_file_name, cwd)


def rel_val_files(files1, files2, args, output_dir, no_extract=False):
    """
    RelVal for 2 ROOT files, simply a wrapper around ReleaseValidation.C macro

    Args:
        no_extract: bool
        If True, expect files1 and files2 to be of length 1. These are expected to already contain extracted objects.
        Hence, extraction will be skipped and objects from these files will directly be compared.
        Potential previous results will not be overwritten but the new ones will be dumped into a new directory (as usual)
    """

    print("==> Process and compare 2 sets of files <==")

    # prepare the output directory
    if not exists(output_dir):
        makedirs(output_dir)
    log_file_rel_val = join(abspath(output_dir), "rel_val.log")

    # flat ROOT files to extract to and read from during RelVal; make absolute paths so we don't confuse ourselves when running e.g. ROOT macros in different directories
    file_1 = abspath(join(output_dir, "extracted_objects_1.root"))
    file_2 = abspath(join(output_dir, "extracted_objects_2.root"))

    if no_extract:
        # in this case we expect the input files to be what we would otherwise extract firt
        if len(files1) != 1 or len(files2) != 1:
            print(f"ERROR: --no-extract option was passed and expecting list of files to be of length 1 each. However, received lengths of {len(files1)} and {len(files2)}")
            return 1
        file_1 = abspath(files1[0])
        file_2 = abspath(files2[0])
    else:
        # extract all objects and put into flat ROOT file structure
        extract(files1, file_1, args.include_dirs, args.add)
        extract(files2, file_2, args.include_dirs, args.add, reference_extracted=file_1)

    # RelVal on flattened files
    cmd = f"\\(\\\"{file_1}\\\",\\\"{file_2}\\\",{args.test},\\\"{args.labels[0]}\\\",\\\"{args.labels[1]}\\\"\\)"
    cmd = f"root -l -b -q {ROOT_MACRO_RELVAL}{cmd}"
    print("Running RelVal on extracted objects")
    run_macro(cmd, log_file_rel_val, cwd=output_dir)

    # This comes from the ROOT macro
    json_path = join(output_dir, "RelVal.json")

    if not exists(json_path):
        # something went wrong
        print(f"ERROR: Something went wrong, cannot find {json_path} which was supposed to be created by ROOT, log file is")
        with open(log_file_rel_val, "r") as f:
            print(f.read())
        return 1

    # go through all we found
    rel_val_summary = None
    with open(json_path, "r") as f:
        rel_val_summary = json.load(f)
    final_summary = make_single_summary(rel_val_summary, args, output_dir)
    meta_info = make_single_meta_info(args)
    write_single_summary(final_summary, meta_info, join(output_dir, "Summary.json"))
    plot_pie_charts(final_summary, output_dir, "")
    plot_values_thresholds(final_summary, output_dir, "")
    plot_summary_grid(final_summary, None, None, None, join(output_dir, "SummaryTests.png"))
    print_summary(final_summary, long=args.long)

    return 0


def rel_val(args):
    """
    Entry point for RelVal
    """
    if args.add:
        print(f"NOTE: Extracted objects will be added to existing ones in case there was already a RelVal at {args.output}.\n")
    # construct the bit mask
    args.test = 0
    default_sum = 0
    for i, t in enumerate(variables.REL_VAL_TEST_NAMES):
        bit = 2**i
        args.test += bit * getattr(args, f"with_{t}")
        default_sum += bit
    if not args.test:
        args.test = default_sum
    if not exists(args.output):
        makedirs(args.output)
    rel_val_files(args.input1, args.input2, args, args.output, args.no_extract)
    return 0


def copy_overlays(path, output_dir,summary):
    """
    copy overlay plots in this summary from the input directory to the output directory
    """
    path = join(dirname(path),"overlayPlots")
    output_dir = join(output_dir,"overlayPlots")
    if not exists(output_dir):
        makedirs(output_dir)
    for histoname in summary:
        filename=join(path,histoname+".png")
        if exists(filename):
            copy(filename,output_dir)
        else:
            print(f"File {filename} not found.")
    return 0


def inspect(args):
    """
    Inspect a Summary.json in view of RelVal severity
    """
    path = get_summary_path(args.path)
    if not path:
        return 1

    output_dir = args.output or join(dirname(path), "user_summary")
    if not exists(output_dir):
        makedirs(output_dir)

    include_patterns, exclude_patterns = load_patterns(args.include_patterns, args.exclude_patterns)
    flags = args.flags
    flags_summary = args.flags_summary
    current_summary, meta_info = read_single_summary(path)
    summary = make_single_summary(current_summary, args, output_dir, include_patterns, exclude_patterns, flags, flags_summary)
    write_single_summary(summary, meta_info, join(output_dir, "Summary.json"))
    print_summary(summary, include_patterns, long=args.long)

    if args.plot:
        plot_pie_charts(summary, output_dir, "", include_patterns, exclude_patterns)
        plot_values_thresholds(summary, output_dir, "", include_patterns, exclude_patterns)
        plot_summary_grid(summary, args.flags, include_patterns, exclude_patterns, join(output_dir, "SummaryTests.png"))

    if args.copy_overlays:
        copy_overlays(path, output_dir,summary)

    return 0


def compare(args):
    """
    Compare 2 RelVal outputs with one another
    """
    if len(args.input1) > 1 or len(args.input2) > 1:
        print("ERROR: You can only compare exactly one RelVal output to exactly to one other RelVal output at the moment.")
        return 1

    inputs = (args.input1[0], args.input2[0])
    output_dir = args.output

    # load everything
    include_patterns, exclude_patterns = load_patterns(args.include_patterns, args.exclude_patterns)
    inputs = [join(get_summary_path(input_path)) for input_path in inputs]

    if not all(inputs):
        print(f"ERROR: Cannot find {inputs[0]} and {inputs[1]}")
        return 1

    # only read the summaries, without meta info
    summaries = [read_single_summary(input_path)[0] for input_path in inputs]

    if not args.difference and not args.compare_values:
        args.difference, args.compare_values = (True, True)

    # plot comparison of values and thresholds of both RelVals per test
    if args.compare_values:
        if not exists(output_dir):
            makedirs(output_dir)
        plot_compare_summaries(summaries, ["threshold", "value"], output_dir, labels=args.labels, include_patterns=include_patterns, exclude_patterns=exclude_patterns)

    # print the histogram names with different severities per test
    if args.difference:
        s = "\nCOMPARING RELVAL SUMMARY\n"
        summaries = [map_histos_to_severity(summary, include_patterns, exclude_patterns) for summary in summaries]
        print("Histograms with different RelVal results from 2 RelVal runs")
        for severity, use in zip(variables.REL_VAL_SEVERITY_MAP, variables.REL_VAL_SEVERITIES_USE_SUMMARY):
            if not use:
                continue
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
    json_in = join(output_dir, "Summary.json")
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

    summary, _ = read_single_summary(json_in)
    with open(out_file, "w") as f:
        for i, (histo_name, tests) in enumerate(summary.items()):
            if not tests:
                continue
            common_string = f"{row_tags},id={i}"
            if args.web_storage:
                common_string += f",web_storage={join(args.web_storage, tests[0]['rel_path_plot'])}"
            common_string += f",histogram_name={histo_name}"
            for test in tests:
                test_string = common_string + f",test_name={test['test_name']} status={variables.REL_VAL_SEVERITY_MAP[test['result']]}"
                for key in ("value", "threshold"):
                    value = test[key]
                    if value is None:
                        continue
                    test_string += f",{key}={value}"
                f.write(f"{test_string}\n")
    return 0


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


def print_table(args):
    """
    Print the filtered histogram names of a Summary.json as list to screen
    """
    path = get_summary_path(args.path)
    if not path:
        return 1

    include_patterns, exclude_patterns = load_patterns(args.include_patterns, args.exclude_patterns, False)
    summary, _ = read_single_summary(path)
    for histo_name, tests in summary.items():
        if not check_patterns(histo_name, include_patterns, exclude_patterns):
            continue
        if not check_flags(tests, args.flags, args.flags_summary):
            continue
        print(f"{histo_name}")

    return 0


def print_header():
    print(f"\n{'#' * 25}\n#{' ' * 23}#\n# RUN ReleaseValidation #\n#{' ' * 23}#\n{'#' * 25}\n")


def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Wrapping ReleaseValidation macro')

    common_file_parser = argparse.ArgumentParser(add_help=False)
    common_file_parser.add_argument("-i", "--input1", nargs="*", help="EITHER first set of input files for comparison OR first input directory from simulation for comparison", required=True)
    common_file_parser.add_argument("-j", "--input2", nargs="*", help="EITHER second set of input files for comparison OR second input directory from simulation for comparison", required=True)
    common_file_parser.add_argument("--labels", nargs=2, help="labels you want to appear in the plot legends in case of overlay plots from batches -i and -j", default=("batch_i", "batch_j"))
    common_file_parser.add_argument("--no-extract", dest="no_extract", action="store_true", help="no extraction but immediately expect histograms present for comparison")

    common_threshold_parser = argparse.ArgumentParser(add_help=False)
    common_threshold_parser.add_argument("--use-values-as-thresholds", nargs="*", dest="use_values_as_thresholds", help="Use values from another run as thresholds for this one")
    common_threshold_parser.add_argument("--combine-thresholds", dest="combine_thresholds",  choices=["mean", "max/min"], help="Arithmetic mean or maximum/minimum is chosen as threshold value", default="mean")
    common_threshold_parser.add_argument("--combine-tuned-and-fixed-thresholds",dest="combine_tuned_and_fixed_thresholds", action="store_true", help="Combine the result from 'combine-thresholds' with the fixed threshold value using maximum/minimum")
    for test, thresh in zip(variables.REL_VAL_TEST_NAMES, variables.REL_VAL_TEST_DEFAULT_THRESHOLDS):
        test_dashed = test.replace("_", "-")
        common_threshold_parser.add_argument(f"--with-test-{test_dashed}", dest=f"with_{test}", action="store_true", help=f"run {test} test")
        common_threshold_parser.add_argument(f"--test-{test_dashed}-threshold", dest=f"{test}_threshold", type=float, help=f"{test} threshold", default=thresh)
        # The following only take effect for thresholds given via an input file
        common_threshold_parser.add_argument(f"--test-{test_dashed}-threshold-margin", dest=f"{test}_threshold_margin", type=float, help=f"Margin to apply to the {test} threshold extracted from file", default=1.0)

    common_pattern_parser = argparse.ArgumentParser(add_help=False)
    common_pattern_parser.add_argument("--include-patterns", dest="include_patterns", nargs="*", help="include objects whose name includes at least one of the given patterns (takes precedence)")
    common_pattern_parser.add_argument("--exclude-patterns", dest="exclude_patterns", nargs="*", help="exclude objects whose name includes at least one of the given patterns")

    common_flags_parser = argparse.ArgumentParser(add_help=False)
    common_flags_parser.add_argument("--flags", nargs="*", help="extract all objects which have at least one test with this severity flag", choices=list(variables.REL_VAL_SEVERITY_MAP.keys()))
    common_flags_parser.add_argument("--flags-summary", dest="flags_summary", nargs="*", help="extract all objects which have this severity flag as overall test result", choices=list(variables.REL_VAL_SEVERITY_MAP.keys()))

    common_verbosity_parser = argparse.ArgumentParser(add_help=False)
    common_verbosity_parser.add_argument("--long", action="store_true", help="enhance verbosity")

    sub_parsers = parser.add_subparsers(dest="command")
    rel_val_parser = sub_parsers.add_parser("rel-val", parents=[common_file_parser, common_threshold_parser, common_verbosity_parser])
    rel_val_parser.add_argument("--include-dirs", dest="include_dirs", nargs="*", help="only include directories; note that each pattern is assumed to start in the top-directory (at the moment no regex or *)")
    rel_val_parser.add_argument("--add", action="store_true", help="If given and there is already a RelVal in the output directory, extracted objects will be added to the existing ones")
    rel_val_parser.add_argument("--output", "-o", help="output directory", default="rel_val")
    rel_val_parser.set_defaults(func=rel_val)

    inspect_parser = sub_parsers.add_parser("inspect", parents=[common_threshold_parser, common_pattern_parser, common_flags_parser, common_verbosity_parser])
    inspect_parser.add_argument("path", help="either complete file path to a Summary.json or directory where one of the former is expected to be")
    inspect_parser.add_argument("--plot", action="store_true", help="Plot the summary grid")
    inspect_parser.add_argument("--output", "-o", help="output directory, by default points to directory where the Summary.json was found")
    inspect_parser.add_argument("--copy-overlays", dest="copy_overlays", action="store_true", help="Copy overlay plots that meet the filter criteria to output directory")
    inspect_parser.set_defaults(func=inspect)

    compare_parser = sub_parsers.add_parser("compare", parents=[common_file_parser, common_pattern_parser])
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

    print_parser = sub_parsers.add_parser("print", parents=[common_pattern_parser, common_flags_parser])
    print_parser.add_argument("path", help="either complete file path to a Summary.json or directory where one of the former is expected to be")
    print_parser.set_defaults(func=print_table)

    file_size_parser = sub_parsers.add_parser("file-sizes", parents=[common_file_parser])
    file_size_parser.add_argument("--threshold", type=float, default=0.5, help="threshold for how far file sizes are allowed to diverge before warning")
    file_size_parser.add_argument("--output", "-o", help="output directory", default="file_sizes")
    file_size_parser.set_defaults(func=dir_comp)

    args = parser.parse_args()
    if not args.command == "print":
        print_header()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
