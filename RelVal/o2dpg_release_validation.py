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
from os import environ, system
from os.path import join

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)

ROOT_MACRO=join(O2DPG_ROOT, "RelVal", "ReleaseValidation.C")

def run(args):
    select_critical = "kTRUE" if args.select_critical else "kFALSE"
    cmd = f"\\(\\\"{args.input_files[0]}\\\",\\\"{args.input_files[1]}\\\",{args.test},{args.chi2_value},{args.rel_bc_diff},{args.rel_entries_diff},{select_critical}\\)"
    cmd = f"root -l -b -q {ROOT_MACRO}{cmd}"
    print(f"Running {cmd}")
    system(cmd)
    return 0

def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Wrapping ReleaseValidation macro')
    parser.add_argument("-f", "--input-files", dest="input_files", nargs=2, help="input files for comparison", required=True)
    parser.add_argument("-t", "--test", type=int, help="index of test case", choices=list(range(1, 8)), required=True)
    parser.add_argument("--chi2-value", dest="chi2_value", type=float, help="Chi2 threshold", default=1.5)
    parser.add_argument("--rel-bc-diff", dest="rel_bc_diff", type=float, help="Threshold of relative difference in normalised bin content", default=0.01)
    parser.add_argument("--rel-entries-diff", dest="rel_entries_diff", type=float, help="Threshold of relative difference in number of entries", default=0.01)
    parser.add_argument("--select-critical", dest="select_critical", action="store_true", help="Select the critical histograms and dump to file")
    parser.set_defaults(func=run)

    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
