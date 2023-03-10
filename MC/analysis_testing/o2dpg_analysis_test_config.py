#!/usr/bin/env python3

import sys
import argparse
from os import environ
from os.path import join
import json

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)


def run(args):
    """digesting what comes from the command line"""

    analyses = None
    with open (args.config, "r") as f:
        analyses = json.load(f)["analyses"]

    for ana in analyses:
        if args.disable and ana["name"] in args.disable:
            ana["enabled"] = False
            continue
        if args.enable and ana["name"] in args.enable:
            ana["enabled"] = True

    with open(args.output, "w") as f:
        json.dump({"analyses": analyses}, f, indent=2)

    return 0

def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Modify analysis configuration and write new config')
    parser.add_argument("-c", "--config", help="input configuration to modify", default=join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", "analyses_config.json"))
    parser.add_argument("-o", "--output", default="analyses_config.json", help="output name of new configuration")
    parser.add_argument("--enable", nargs="*", help="analysis names to enable (if disabled)")
    parser.add_argument("--disable", nargs="*", help="analysis names to disable (if enabled), takes precedence over --enable")
    parser.set_defaults(func=run)
    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
