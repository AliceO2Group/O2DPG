#!/usr/bin/env python3

import sys
import argparse
import importlib.util
from os import environ
from os.path import join

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)

spec = importlib.util.spec_from_file_location("o2dpg_release_validation", join(O2DPG_ROOT, "RelVal", 'o2dpg_release_validation.py'))
o2dpg_release_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o2dpg_release_validation)
sys.modules["o2dpg_release_validation"] = o2dpg_release_validation
from o2dpg_release_validation import extract_and_flatten

spec = importlib.util.spec_from_file_location("o2dpg_release_validation_plot", join(O2DPG_ROOT, "RelVal", "utils", 'o2dpg_release_validation_plot.py'))
o2dpg_release_validation_plot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o2dpg_release_validation_plot)
sys.modules["o2dpg_release_validation_plot"] = o2dpg_release_validation_plot
from o2dpg_release_validation_plot import plot_overlays_no_rel_val


def run(args):

    if not args.labels:
        args.labels = [f"label_{i}" for i, _ in enumerate(args.input)]

    if len(args.labels) != len(args.input):
        print("ERROR: Number of input files and labels is different, must be the same")
        return 1

    out_configs = []
    ref_file = None
    for i, (input_file, label) in enumerate(zip(args.inputs, args.labels)):

        _, config = extract_and_flatten(input_file, args.output, label, prefix=i, reference_extracted=ref_file)
        if not config:
            print(f"ERROR: Problem with input file {input_file}, cannot extract")
            return 1

        if not ref_file:
            ref_file = config["path"]

        out_configs.append(config)

    plot_overlays_no_rel_val(out_configs, args.output)

    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", nargs="*", help="list of ROOT files", required=True)
    parser.add_argument("-o", "--output", help="output directory", default="overlayPlots")
    parser.add_argument("-l", "--labels", nargs="*", help="plot labels")
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
