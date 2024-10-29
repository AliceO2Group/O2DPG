#!/usr/bin/env python3

# Simple ROOT files merger

from ROOT import TFile, TFileMerger
import sys
import os
import argparse

output_file = ''
input_files = []
# defining command line options

parser = argparse.ArgumentParser(description='Simple ROOT files merger',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-o','--output', help='Output ROOT filename', required=True)
parser.add_argument('-i','--input', help='Input ROOT files to be merged, separated by a comma', required=True)

args = parser.parse_args()

output_file = args.output
input_files = args.input.split(',')

merger = TFileMerger(False)
merger.OutputFile(output_file)

for input_file in input_files:
    if os.path.exists(input_file):
        merger.AddFile(input_file)
    else:
        print(f"Fatal: {input_file} does not exist.")
        sys.exit(1)

if not merger.Merge():
    print("Error: Merging failed.")
    sys.exit(2)
else:
    print(f"Successfully merged files into {output_file}")

sys.exit(0)