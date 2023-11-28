#!/usr/bin/env python3
#
# Basically, this script allows a user to compare
# 1. 2 corresponding ROOT files containing either histograms or QC Monitoring objects
# 2. 2 corresponding simulation directories
#
# The RelVal suite is for instance run with
# o2dpg_release_validation.py rel-val -i <file-or-sim-dir1> -j <file-or-sim-dir2>
#

import sys
import argparse
import importlib.util
from os import environ, makedirs, remove, rename
from os.path import join, abspath, exists, dirname, basename, isfile
from shutil import copy, rmtree

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)


O2DPG_ROOT = environ.get("O2DPG_ROOT")
spec = importlib.util.spec_from_file_location("o2dpg_release_validation_variables", join(O2DPG_ROOT, "RelVal", 'o2dpg_release_validation_variables.py'))
o2dpg_release_validation_variables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o2dpg_release_validation_variables)
sys.modules["o2dpg_release_validation_variables"] = o2dpg_release_validation_variables
import o2dpg_release_validation_variables as variables

spec = importlib.util.spec_from_file_location("o2dpg_release_validation_utils", join(O2DPG_ROOT, "RelVal", 'o2dpg_release_validation_utils.py'))
o2dpg_release_validation_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o2dpg_release_validation_utils)
sys.modules["o2dpg_release_validation_utils"] = o2dpg_release_validation_utils
from o2dpg_release_validation_utils import *

spec = importlib.util.spec_from_file_location("o2dpg_release_validation_plot", join(O2DPG_ROOT, "RelVal", 'o2dpg_release_validation_plot.py'))
o2dpg_release_validation_plot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o2dpg_release_validation_plot)
sys.modules["o2dpg_release_validation_plot"] = o2dpg_release_validation_plot
from o2dpg_release_validation_plot import plot_pie_charts, plot_summary_grid, plot_compare_summaries


ROOT_MACRO_EXTRACT=join(O2DPG_ROOT, "RelVal", "ExtractAndFlatten.C")
ROOT_MACRO_RELVAL=join(O2DPG_ROOT, "RelVal", "ReleaseValidation.C")
ROOT_MACRO_METRICS=join(O2DPG_ROOT, "RelVal", "ReleaseValidationMetrics.C")

from ROOT import gROOT

gROOT.SetBatch()

def copy_overlays(rel_val, input_dir, output_dir):
    """
    copy overlay plots in this summary from the input directory to the output directory
    """
    input_dir = abspath(input_dir)
    output_dir = abspath(output_dir)

    if not exists(input_dir):
        print(f"ERROR: Input directory {input_dir} does not exist")
        return 1

    inOutSame = input_dir == output_dir

    input_dir_new = input_dir + "_tmp"
    if inOutSame:
        # move input directory
        rename(input_dir, input_dir_new)
        input_dir = input_dir_new

    if not exists(output_dir):
        makedirs(output_dir)

    object_names, _ = rel_val.get_result_per_metric_and_test()
    object_names = list(set(object_names))

    ret = 0
    for object_name in object_names:
        filename=join(input_dir, f"{object_name}.png")
        if exists(filename):
            copy(filename, output_dir)
        else:
            print(f"File {filename} not found.")
            ret = 1

    if inOutSame:
        rmtree(input_dir)

    return ret


def metrics_from_root():
    """
    Simply get all registered metrics that are defined in the ROOT macro
    """
    log_file_name = join("/tmp", "RelValMetrics.log")
    if exists(log_file_name):
        remove(log_file_name)
    cmd = f"root -l -b -q {ROOT_MACRO_METRICS}"
    ret = run_macro(cmd, log_file_name)
    if ret > 0:
        return ret

    with open(log_file_name, "r") as f:
        current_metric = None
        for line in f:
            if current_metric is None and "METRIC" in line:
                current_metric = line.split()[1]
                continue
            if "enabled" in line:
                print(current_metric)
                current_metric = None
    return 0

def extract(input_filenames, target_filename, include_file_directories="", add_if_exists=False, reference_extracted=""):
    """
    Wrap the extraction of objects to be compared

    Will be extracted (from TH1, QC objects, TTree etc.), converted to TH1 and put into a flat ROOT file structure.

    Args:
        target_filename: str
            path to file where extracted objects should be saved
        include_file_directories: iterable or "" (default: "")
            only consider a ROOT sub-directory if it contains any of the strings given in the iterable
        add_if_exists: bool (default: False)
            if target_filename already exists, update instead of recreate
        reference_extracted: str
            is used in case of the extraction of TTrees in which case the x-axis binning will be set
            according to that reference to make objects comparable.
    Returns:
        bool
            True in case of success, False otherwise
    """

    include_file_directories = ",".join(include_file_directories) if include_file_directories else ""

    if exists(target_filename) and not add_if_exists:
        # this file will otherwise be updated if it exists
        remove(target_filename)

    # The ROOT macro is run inside the cwd and puts basename there
    cwd = dirname(target_filename)
    target_filename = basename(target_filename)
    log_file_name = join(cwd, f"{target_filename}_extract_and_flatten.log")

    print("Extraction of files")

    for f in input_filenames:
        f = abspath(f)
        print(f"  {f}")
        cmd = f"\\(\\\"{f}\\\",\\\"{target_filename}\\\",\\\"{reference_extracted}\\\",\\\"{include_file_directories}\\\"\\)"
        cmd = f"root -l -b -q {ROOT_MACRO_EXTRACT}{cmd}"
        ret = run_macro(cmd, log_file_name, cwd)
        if ret != 0:
            print(f"ERROR: Extracting from file {f} failed. Please check logfile {abspath(join(cwd, log_file_name))}")
            return False

    return True


def rel_val_root(files1, files2, include_root_dirs, add_to_previous, metrics_enabled, metrics_disabled, label1, label2, output_dir, no_extract=False):
    """
    RelVal for 2 ROOT files, simply a wrapper around ReleaseValidation.C macro

    Args:
        files1: iterable
            first batch of files to compare
        files2: iterable
            second batch of files to compare
        add_to_previous: bool
            whether of not extracted objects should be added to existing file (objects therein, if they exist)
        metrics_enabled: iterable or None
            names of metrics to be enabled
        metrics_disabled: iterable or None
            names of metrics to be disabled
        label1, label2: str
            label the overlay plots
        output_dir: str
            path of output directory; will be created if it doesn't exist
        no_extract: bool
            If True, expect files1 and files2 to be of length 1. These are expected to already contain extracted objects.
            Hence, extraction will be skipped and objects from these files will directly be compared.
            Potential previous results will not be overwritten but the new ones will be dumped into a new directory (as usual)
    Returns:
        str or None
            in case of success, return the path to the JSON with computed metrics
            None otherwise
    """
    def get_files_from_list(list_filename):
        """
        Quick helper

        Extract filenames from what is listed in a given file
        """
        collect_files = []
        with open(list_filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                collect_files.append(line)
        return collect_files

    print("==> Process and compare 2 sets of files <==")

    # flat ROOT files to extract to and read from during RelVal; make absolute paths so we don't confuse ourselves when running e.g. ROOT macros in different directories
    file_1 = abspath(join(output_dir, "extracted_objects_1.root"))
    file_2 = abspath(join(output_dir, "extracted_objects_2.root"))

    if len(files1) == 1 and files1[0][0] == "@":
        files1 = get_files_from_list(files1[0])
        if not files1:
            print(f"ERROR: Apparently {files1[0][1:]} contains no files to be extracted.")
            return None
    if len(files2) == 1 and files2[0][0] == "@":
        files2 = get_files_from_list(files2[0])
        if not files2:
            print(f"ERROR: Apparently {files2[0][1:]} contains no files to be extracted.")
            return None

    # prepare the output directory
    if not exists(output_dir):
        makedirs(output_dir)
    log_file_rel_val = join(abspath(output_dir), "rel_val.log")
    
    if no_extract:
        # in this case we expect the input files to be what we would otherwise extract first
        if len(files1) != 1 or len(files2) != 1:
            print(f"ERROR: --no-extract option was passed and expecting list of files to be of length 1 each. However, received lengths of {len(files1)} and {len(files2)}")
            return 1
        file_1 = abspath(files1[0])
        file_2 = abspath(files2[0])
    elif not extract(files1, file_1, include_root_dirs, add_to_previous) or not extract(files2, file_2, include_root_dirs, add_to_previous, reference_extracted=file_1):
        return None

    # RelVal on flattened files
    metrics_enabled = ";".join(metrics_enabled) if metrics_enabled else ""
    metrics_disabled = ";".join(metrics_disabled) if metrics_disabled else ""

    cmd = f"\\(\\\"{file_1}\\\",\\\"{file_2}\\\",\\\"{metrics_enabled}\\\",\\\"{metrics_disabled}\\\",\\\"{label1}\\\",\\\"{label2}\\\"\\)"
    cmd = f"root -l -b -q {ROOT_MACRO_RELVAL}{cmd}"
    print("Running RelVal on extracted objects")
    ret = run_macro(cmd, log_file_rel_val, cwd=output_dir)

    # This comes from the ROOT macro
    json_path = join(output_dir, "RelVal.json")

    if not exists(json_path) or ret > 0:
        # something went wrong
        print(f"ERROR: Something went wrong during the calculation of metrics, log file at {log_file_rel_val} reads")
        with open(log_file_rel_val, "r") as f:
            print(f.read())
        return None

    return json_path


def load_rel_val(json_path, include_patterns=None, exclude_patterns=None, enable_metrics=None, disable_metrics=None):
    """
    Wrapper to create RelVal and set some properties

    Args:
        json_path: str
            path to JSON file with metrics (and potentially results)
        include_patterns: str or None (default: None)
            regex of patterns to be matched against object names to include only certain objects
        exclude_patterns: str or None (default: None)
            regex of patterns to be matched against object names to exclude certain objects
    Returns
        RelVal
    """
    rel_val = RelVal()
    rel_val.set_object_name_patterns(include_patterns, exclude_patterns)
    rel_val.enable_metrics(enable_metrics)
    rel_val.disable_metrics(disable_metrics)
    rel_val.load((json_path,))
    return rel_val


def initialise_evaluator(rel_val, thresholds, thresholds_default, thresholds_margins, thresholds_combine, regions):
    """
    Wrapper to create an evaluator

    Args:
        rel_val: RelVal
            the RelVal object that should potentially be tested and is used to derive default threshold
        thresholds: iterable or None
            if not None, iterable of string as the paths to RelVal JSONs
        thresholds_defaults: iterable of 2-tuples or None
            assign a default threshold value (tuple[1]) to a metric name (tuple[0])
        threshold_margins: iterable of 2-tuples or None
            add a margin given in percent (tuple[1]) to a threshold value of a metric name (tuple[0])
        thresholds_combine: str
            either "mean" or "extreme", how threshold values extracted from argument thresholds should be combined
        regions: iterable or None
            if not None, iterable of string as the paths to RelVal JSONs
    Returns:
        Evaluator
    """
    evaluator = Evaluator()

    # initialise to run tests on proper mean +- std
    if regions:
        rel_val_regions = get_summaries_or_from_file(regions)
        initialise_regions(evaluator, rel_val_regions)

    # initialise to run tests on thresholds
    thresholds_default = {metric_name: float(value) for metric_name, value in thresholds_default} if thresholds_default else None
    rel_val_thresholds = None
    if thresholds:
        thresholds_margins = {metric_name: float(value) for metric_name, value in thresholds_margins} if thresholds_margins else None
        rel_val_thresholds = get_summaries_or_from_file(thresholds)
    initialise_thresholds(evaluator, rel_val, rel_val_thresholds, thresholds_default, thresholds_margins, thresholds_combine)

    evaluator.initialise()
    return evaluator


def rel_val(args):
    """
    Entry point for ReleaseValidation

    This is reached either from rel-val or inspect sub-commands
    """
    def interpret_results(result, metric):
        """
        Taking in a result and the metric it was derived from, assign an interpretation
        """
        is_critical = args.is_critical is None or metric.name in args.is_critical
        if not metric.comparable and is_critical:
            result.interpretation = variables.REL_VAL_INTERPRETATION_CRIT_NC
            return
        if not metric.comparable:
            result.interpretation = variables.REL_VAL_INTERPRETATION_NONCRIT_NC
            return
        if result.result_flag == Result.FLAG_UNKNOWN:
            result.interpretation = variables.REL_VAL_INTERPRETATION_UNKNOWN
            return
        if result.result_flag == Result.FLAG_PASSED:
            result.interpretation = variables.REL_VAL_INTERPRETATION_GOOD
            return
        if result.result_flag == Result.FLAG_FAILED and is_critical:
            result.interpretation = variables.REL_VAL_INTERPRETATION_BAD
            return
        result.interpretation = variables.REL_VAL_INTERPRETATION_WARNING

    if not exists(args.output):
        makedirs(args.output)

    need_apply = False
    is_inspect = False
    if hasattr(args, "json_path"):
        # this comes from the inspect command
        is_inspect = True
        json_path = get_summary_path(args.json_path)
        annotations = None
        include_patterns, exclude_patterns = (args.include_patterns, args.exclude_patterns)
    else:
        # in this case, new input ROOT files were provided and we need to apply all our tests
        need_apply = True
        include_patterns, exclude_patterns = (None, None)
        if args.add:
            print(f"NOTE: Extracted objects will be added to existing ones in case there was already a RelVal at {args.output}.\n")
        json_path = rel_val_root(args.input1, args.input2, args.include_dirs, args.add, args.enable_metric, args.disable_metric, args.labels[0], args.labels[1], args.output, args.no_extract)
        if json_path is None:
            return 1
        annotations = {"batch_i": [abspath(p) for p in args.input1],
                       "batch_j": [abspath(p) for p in args.input2]}

    rel_val = load_rel_val(json_path, include_patterns, exclude_patterns, args.enable_metric, args.disable_metric)

    if need_apply or args.use_values_as_thresholds or args.default_threshold or args.regions:
        evaluator = initialise_evaluator(rel_val, args.use_values_as_thresholds, args.default_threshold, args.margin_threshold, args.combine_thresholds, args.regions)
        rel_val.apply(evaluator)
        # assign interpretations to the results we got
    rel_val.interpret(interpret_results)

    def filter_on_interpretations(result):
        # only consider those results that match a flag requested by the user
        return not args.interpretations or result.interpretation in args.interpretations

    # filter results, in this case cased on their interpretation; this will add an additional mask whenever applicable so that
    # object_names, metric_names, results
    # returned from RelVal match the condition of the filter function
    rel_val.filter_results(filter_on_interpretations)
    # if this comes from inspecting, there will be the annotations from the rel-val before that ==> re-write it
    rel_val.write(join(args.output, "Summary.json"), annotations=annotations or rel_val.annotations[0])

    if is_inspect:
        copy_overlays(rel_val, join(dirname(json_path), "overlayPlots"), join(args.output, "overlayPlots"))

    if not args.no_plot:
        # plot various different figures for user inspection
        plot_pie_charts(rel_val, variables.REL_VAL_SEVERITIES, variables.REL_VAL_SEVERITY_COLOR_MAP, args.output)
        plot_compare_summaries((rel_val,), args.output)
        plot_summary_grid(rel_val, variables.REL_VAL_SEVERITIES, variables.REL_VAL_SEVERITY_COLOR_MAP, args.output)
    print_summary(rel_val, variables.REL_VAL_SEVERITIES, long=args.print_long)

    return 0


def compare(args):
    """
    Compare 2 RelVal outputs with one another
    """
    if len(args.input1) > 1 or len(args.input2) > 1:
        print("ERROR: You can only compare exactly one RelVal output to exactly to one other RelVal output at the moment.")
        return 1

    output_dir = args.output

    # load
    rel_val1 = load_rel_val(get_summary_path(args.input1[0]), args.include_patterns, args.exclude_patterns, args.enable_metric, args.disable_metric)
    rel_val2 = load_rel_val(get_summary_path(args.input2[0]), args.include_patterns, args.exclude_patterns, args.enable_metric, args.disable_metric)

    # get the test and metric names they have in common
    test_names = np.intersect1d(rel_val1.known_test_names, rel_val2.known_test_names)
    metric_names = np.intersect1d(rel_val1.known_metrics, rel_val2.known_metrics)

    print("METRIC NAME, TEST NAME, INTERPRETATION, #IN COMMON, #ONLY IN FIRST, #ONLY IN SECOND")
    for metric_name in metric_names:
        for test_name in test_names:
            object_names1, results1 = rel_val1.get_result_per_metric_and_test(metric_name, test_name)
            object_names2, results2 = rel_val2.get_result_per_metric_and_test(metric_name, test_name)

            for interpretation in variables.REL_VAL_SEVERITIES:
                if args.interpretations and interpretation not in args.interpretations:
                    continue
                # object names of Results matching an interpretation
                object_names_interpretation1 = object_names1[count_interpretations(results1, interpretation)]
                object_names_interpretation2 = object_names2[count_interpretations(results2, interpretation)]
                # elements in 1 that are not in 2...
                only_in1 = np.setdiff1d(object_names_interpretation1, object_names_interpretation2)
                # ...and the other way round
                only_in2 = np.setdiff1d(object_names_interpretation2, object_names_interpretation1)
                # ...as well as elements they have in common
                in_common = np.intersect1d(object_names_interpretation1, object_names_interpretation2)
                s = f"{metric_name}, {test_name}, {interpretation}, {len(in_common)}, {len(only_in1)}, {len(only_in2)}"
                if args.print_long:
                    in_common = ";".join(in_common) if len(in_common) else "NONE"
                    only_in1 = ";".join(only_in1) if len(only_in1) else "NONE"
                    only_in2 = ";".join(only_in2) if len(only_in2) else "NONE"
                    s += f", {in_common}, {only_in1}, {only_in2}"
                print(s)

    # plot comparison of values and thresholds of both RelVals per test
    if args.plot:
        if not exists(output_dir):
            makedirs(output_dir)
        plot_compare_summaries((rel_val1, rel_val2), output_dir, labels=args.labels)

    return 0


def influx(args):
    """
    Create an influxDB metrics file
    """
    rel_val = load_rel_val(get_summary_path(args.path))

    output_path = args.path if isfile(args.path) else join(args.path, "influxDB.dat")
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

    with open(output_path, "w") as f:
        object_names, metric_names, result_names, results = rel_val.query_results()
        for i, (object_name, metric_name, result_name, result) in enumerate(zip(object_names, metric_names, result_names, results)):
            common_string = f"{row_tags},id={i},histogram_name={object_name},metric_name={metric_name},test_name={result_name} status={variables.REL_VAL_SEVERITY_MAP[result.interpretation]}"
            if result.value is not None:
                common_string += f",value={result.value}"
            if result.mean is not None:
                common_string += f",threshold={result.mean}"
            f.write(f"{common_string}\n")
    return 0


def print_simple(args):
    """
    Simply print line-by-line

    object names (--object-names)

    metric names (--metric-names)

    test names (--test-names)
    """

    if not args.path:
        if not args.metric_names:
            return 0
        return metrics_from_root()

    rel_val = load_rel_val(get_summary_path(args.path), args.include_patterns, args.exclude_patterns, args.enable_metric, args.disable_metric)

    def filter_on_interpretations(result):
        # only consider those results that match a flag requested by the user
        return not args.interpretations or result.interpretation in args.interpretations

    rel_val.filter_results(filter_on_interpretations)
    if args.metric_names:
        for metric_name in rel_val.known_metrics:
            print(metric_name)
    if args.test_names and rel_val.number_of_tests:
        for test_name in rel_val.known_test_names:
            print(test_name)
    if args.object_names:
        if rel_val.number_of_tests:
            # we have tests, so we go for object names with interpretations
            object_names, _ = rel_val.get_result_per_metric_and_test()
        else:
            object_names = rel_val.known_objects
        for object_name in np.unique(object_names):
            print(object_name)
    return 0


def print_header():
    print(f"\n{'#' * 25}\n#{' ' * 23}#\n# RUN ReleaseValidation #\n#{' ' * 23}#\n{'#' * 25}\n")


# we define the parser here

COMMON_FILE_PARSER = argparse.ArgumentParser(add_help=False)
COMMON_FILE_PARSER.add_argument("-i", "--input1", nargs="*", help="EITHER first set of input files for comparison OR first input directory from simulation for comparison", required=True)
COMMON_FILE_PARSER.add_argument("-j", "--input2", nargs="*", help="EITHER second set of input files for comparison OR second input directory from simulation for comparison", required=True)
COMMON_FILE_PARSER.add_argument("--labels", nargs=2, help="labels you want to appear in the plot legends in case of overlay plots from batches -i and -j", default=("batch_i", "batch_j"))
COMMON_FILE_PARSER.add_argument("--no-extract", dest="no_extract", action="store_true", help="no extraction but immediately expect histograms present for comparison")

COMMON_THRESHOLD_PARSER = argparse.ArgumentParser(add_help=False)
COMMON_THRESHOLD_PARSER.add_argument("--regions", help="Use calculated regions to test status")
COMMON_THRESHOLD_PARSER.add_argument("--default-threshold", dest="default_threshold", action="append", nargs=2)
COMMON_THRESHOLD_PARSER.add_argument("--use-values-as-thresholds", nargs="*", dest="use_values_as_thresholds", help="Use values from another run as thresholds for this one")
COMMON_THRESHOLD_PARSER.add_argument("--combine-thresholds", dest="combine_thresholds",  choices=["mean", "extreme"], help="Arithmetic mean or extreme value is chosen as threshold", default="mean")
COMMON_THRESHOLD_PARSER.add_argument("--margin-threshold", dest="margin_threshold", action="append", nargs=2)

COMMON_METRIC_PARSER = argparse.ArgumentParser(add_help=False)
COMMON_METRIC_PARSER.add_argument("--enable-metric", dest="enable_metric", nargs="*")
COMMON_METRIC_PARSER.add_argument("--disable-metric", dest="disable_metric", nargs="*")

COMMON_PATTERN_PARSER = argparse.ArgumentParser(add_help=False)
COMMON_PATTERN_PARSER.add_argument("--include-patterns", dest="include_patterns", nargs="*", help="include objects whose name includes at least one of the given patterns (takes precedence)")
COMMON_PATTERN_PARSER.add_argument("--exclude-patterns", dest="exclude_patterns", nargs="*", help="exclude objects whose name includes at least one of the given patterns")

COMMON_FLAGS_PARSER = argparse.ArgumentParser(add_help=False)
COMMON_FLAGS_PARSER.add_argument("--interpretations", nargs="*", help="extract all objects which have at least one test with this severity flag", choices=list(variables.REL_VAL_SEVERITY_MAP.keys()))
COMMON_FLAGS_PARSER.add_argument("--is-critical", dest="is_critical", nargs="*", help="set names of metrics that are assumed to be critical")

COMMON_VERBOSITY_PARSER = argparse.ArgumentParser(add_help=False)
COMMON_VERBOSITY_PARSER.add_argument("--print-long", dest="print_long", action="store_true", help="enhance verbosity")
COMMON_VERBOSITY_PARSER.add_argument("--no-plot", dest="no_plot", action="store_true", help="suppress plotting")

PARSER = argparse.ArgumentParser(description='Wrapping ReleaseValidation macro')
SUB_PARSERS = PARSER.add_subparsers(dest="command")
REL_VAL_PARSER = SUB_PARSERS.add_parser("rel-val", parents=[COMMON_FILE_PARSER, COMMON_METRIC_PARSER, COMMON_THRESHOLD_PARSER, COMMON_FLAGS_PARSER, COMMON_VERBOSITY_PARSER])
REL_VAL_PARSER.add_argument("--include-dirs", dest="include_dirs", nargs="*", help="only include desired directories inside ROOT file; note that each pattern is assumed to start in the top-directory (at the moment no regex or *)")
REL_VAL_PARSER.add_argument("--add", action="store_true", help="If given and there is already a RelVal in the output directory, extracted objects will be added to the existing ones")
REL_VAL_PARSER.add_argument("--output", "-o", help="output directory", default="rel_val")
REL_VAL_PARSER.set_defaults(func=rel_val)

INSPECT_PARSER = SUB_PARSERS.add_parser("inspect", parents=[COMMON_THRESHOLD_PARSER, COMMON_METRIC_PARSER, COMMON_PATTERN_PARSER, COMMON_FLAGS_PARSER, COMMON_VERBOSITY_PARSER])
INSPECT_PARSER.add_argument("--path", dest="json_path", help="either complete file path to a Summary.json or directory where one of the former is expected to be", required=True)
INSPECT_PARSER.add_argument("--output", "-o", help="output directory", default="rel_val_inspect")
INSPECT_PARSER.set_defaults(func=rel_val)

COMPARE_PARSER = SUB_PARSERS.add_parser("compare", parents=[COMMON_FILE_PARSER, COMMON_PATTERN_PARSER, COMMON_METRIC_PARSER, COMMON_VERBOSITY_PARSER, COMMON_FLAGS_PARSER])
COMPARE_PARSER.add_argument("--output", "-o", help="output directory", default="rel_val_comparison")
COMPARE_PARSER.add_argument("--difference", action="store_true", help="plot histograms with different severity")
COMPARE_PARSER.add_argument("--plot", action="store_true", help="plot value and threshold comparisons of RelVals")
COMPARE_PARSER.set_defaults(func=compare)

INFLUX_PARSER = SUB_PARSERS.add_parser("influx")
INFLUX_PARSER.add_argument("--path", help="directory where ReleaseValidation was run", required=True)
INFLUX_PARSER.add_argument("--tags", nargs="*", help="tags to be added for influx, list of key=value")
INFLUX_PARSER.add_argument("--table-suffix", dest="table_suffix", help="prefix for table name")
INFLUX_PARSER.add_argument("--output", "-o", help="output path; if not given, a file influxDB.dat is places inside the RelVal directory")
INFLUX_PARSER.set_defaults(func=influx)

PRINT_PARSER = SUB_PARSERS.add_parser("print", parents=[COMMON_METRIC_PARSER, COMMON_PATTERN_PARSER, COMMON_FLAGS_PARSER])
PRINT_PARSER.add_argument("--path", help="either complete file path to a Summary.json or directory where one of the former is expected to be")
PRINT_PARSER.add_argument("--metric-names", dest="metric_names", action="store_true")
PRINT_PARSER.add_argument("--test-names", dest="test_names", action="store_true")
PRINT_PARSER.add_argument("--object-names", dest="object_names", action="store_true")
PRINT_PARSER.set_defaults(func=print_simple)

def main():
    """entry point when run directly from command line"""
    args = PARSER.parse_args()
    if args.command != "print":
        print_header()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
