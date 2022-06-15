#!/usr/bin/env python3
#
# This is a short script to conveniently wrap the ROOT macro used for release validation comparisons
#
# Help message:
# usage: o2dpg_release_validation.py [-h] -f INPUT_FILES INPUT_FILES -t {1,2,3,4,5,6,7} [--chi2-value CHI2_VALUE] [--rel-bc-diff REL_BC_DIFF] [--rel-entries-diff REL_ENTRIES_DIFF] [--select-critical]
# 
# Wrapping ReleaseValidation macro
# 
# optional arguments:
#   -h, --help            show this help message and exit
#   -f INPUT_FILES INPUT_FILES, --input-files INPUT_FILES INPUT_FILES
#                         input files for comparison
#   -t {1,2,3,4,5,6,7}, --test {1,2,3,4,5,6,7}
#                         index of test case
#   --chi2-value CHI2_VALUE
#                         Chi2 threshold
#   --rel-bc-diff REL_BC_DIFF
#                         Threshold of relative difference in normalised bin content
#   --rel-entries-diff REL_ENTRIES_DIFF
#                         Threshold of relative difference in number of entries
#   --select-critical     Select the critical histograms and dump to file

import sys
import argparse
from os import environ, makedirs
from os.path import join, abspath, exists
from subprocess import Popen
from shlex import split
import json

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)

ROOT_MACRO=join(O2DPG_ROOT, "RelVal", "ReleaseValidation.C")

def rel_val(args):
    if not exists(args.output):
        makedirs(args.output)
    select_critical = "kTRUE" if args.select_critical else "kFALSE"
    cmd = f"\\(\\\"{abspath(args.input_files[0])}\\\",\\\"{abspath(args.input_files[1])}\\\",{args.test},{args.chi2_value},{args.rel_mean_diff},{args.rel_entries_diff},{select_critical}\\)"
    cmd = f"root -l -b -q {ROOT_MACRO}{cmd}"
    print(f"Running {cmd}")
    p = Popen(split(cmd), cwd=args.output)
    p.wait()
    return 0

def inspect(args):
    res = None
    with open(args.file, "r") as f:
        # NOTE For now care about the summary. However, we have each test individually, so we could do a more detailed check in the future
        res = json.load(f)["test_summary"]
    for s in args.severity:
        names = res.get(s)
        if not names:
            continue
        print(f"Histograms for severity {s}:")
        for n in names:
            print(f"    {n}")
    return 0

def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Wrapping ReleaseValidation macro')
    sub_parsers = parser.add_subparsers(dest="command")
    
    rel_val_parser = sub_parsers.add_parser("rel-val")
    rel_val_parser.add_argument("-f", "--input-files", dest="input_files", nargs=2, help="input files for comparison", required=True)
    rel_val_parser.add_argument("-t", "--test", type=int, help="index of test case", choices=list(range(1, 8)), required=True)
    rel_val_parser.add_argument("--chi2-value", dest="chi2_value", type=float, help="Chi2 threshold", default=1.5)
    rel_val_parser.add_argument("--rel-mean-diff", dest="rel_mean_diff", type=float, help="Threshold of relative difference in mean", default=1.5)
    rel_val_parser.add_argument("--rel-entries-diff", dest="rel_entries_diff", type=float, help="Threshold of relative difference in number of entries", default=0.01)
    rel_val_parser.add_argument("--select-critical", dest="select_critical", action="store_true", help="Select the critical histograms and dump to file")
    rel_val_parser.add_argument("--output", "-o", help="output directory", default="./")
    rel_val_parser.set_defaults(func=rel_val)
    
    inspect_parser = sub_parsers.add_parser("inspect")
    inspect_parser.add_argument("file", help="pass a JSON produced from ReleaseValidation (rel-val)")
    inspect_parser.add_argument("--severity", nargs="*", default=["BAD", "CRIT_NC"], choices=["GOOD", "WARNING", "BAD", "CRIT_NC", "NONCRIT_NC"], help="Choose severity levels to search for")
    inspect_parser.set_defaults(func=inspect)

    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
