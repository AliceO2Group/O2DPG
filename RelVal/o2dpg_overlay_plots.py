#!/usr/bin/env python3

import sys
import argparse
from os import environ, makedirs, remove
from os.path import join, exists, abspath
from subprocess import Popen, PIPE, STDOUT
from shlex import split

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)

ROOT_MACRO_EXTRACT=join(O2DPG_ROOT, "RelVal", "ExtractAndFlatten.C")
ROOT_MACRO_OVERLAYS=join(O2DPG_ROOT, "RelVal", "PlotOverlays.C")

FLATTENED_FILE_NAME = "newfile"

def run_macro(cmd, log_file, output_dir):
    p = Popen(split(cmd), cwd=output_dir, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
    log_file = open(log_file, 'a')
    for line in p.stdout:
        log_file.write(line)
    p.wait()
    log_file.close()

def call_extract_and_flatten(inputs, output_dir):
    output_dir = abspath(output_dir)
    if not exists(output_dir):
        makedirs(output_dir)
    log_file_extract = join(abspath(output_dir), "extract_and_flatten.log")
    counter = 0
    firstfile = join(output_dir,FLATTENED_FILE_NAME+str(1)+".root")
    for f in inputs:
        counter += 1
        print(f"Extraction of objects from {f}")
        f = abspath(f)
        newfile = join(output_dir,FLATTENED_FILE_NAME+str(counter)+".root")
        if exists(newfile):
            remove(newfile)
        cmd = ""
        if counter==1:
            cmd = f"\\(\\\"{f}\\\",\\\"{newfile}\\\",\\\"\\\",\\\"\\\"\\)"
        else:
            cmd = f"\\(\\\"{f}\\\",\\\"{newfile}\\\",\\\"{firstfile}\\\",\\\"\\\"\\)"
        cmd = f"root -l -b -q {ROOT_MACRO_EXTRACT}{cmd}"
        run_macro(cmd, log_file_extract, output_dir)
    return 0

def call_plot_overlays(nInput, output_dir, labels):
    output_dir = abspath(output_dir)
    cmd = f"\\({{"
    for i in range(nInput):
        f = join(output_dir,FLATTENED_FILE_NAME+str(i+1)+".root")
        cmd = cmd + f"\\\"{f}\\\","
    cmd = cmd[:-1]
    cmd = cmd + f"}},{{"
    for l in labels:
        cmd = cmd + f"\\\"{l}\\\","
    cmd = cmd[:-1]
    cmd = cmd + f"}},\\\"{output_dir}\\\"\\)"
    cmd = f"root -l -b -q {ROOT_MACRO_OVERLAYS}{cmd}"
    log_file_extract = join(output_dir, "plot_overlays.log")
    print("Make the plots")
    run_macro(cmd, log_file_extract, output_dir)
    return 0

def clean_up(nInput, output_dir):
    for i in range(nInput):
        f = join(output_dir,FLATTENED_FILE_NAME+str(i+1)+".root")
        remove(f)
        print(f"Remove {f}")
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", nargs="*", help="list of ROOT files", required=True)
    parser.add_argument("-o", "--output", help="output directory", default="overlayPlots")
    parser.add_argument("-l", "--labels", nargs="*", help="plot labels", default="overlayPlots")
    parser.add_argument("--clean", help="delete newfile.root files after macro has finished", action="store_true")
    args = parser.parse_args()
    call_extract_and_flatten(args.input, args.output)
    call_plot_overlays(len(args.input), args.output, args.labels)
    if args.clean:
        clean_up(len(args.input), args.output)
    return 0

if __name__ == "__main__":
    sys.exit(main())
