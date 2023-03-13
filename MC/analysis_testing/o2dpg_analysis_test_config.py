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


def modify(args):
    """
    modify and create a new config
    """

    analyses = None
    with open (args.config, "r") as f:
        analyses = json.load(f)["analyses"]

    for ana in analyses:
        if args.disable_tasks and ana["name"] in args.disable_tasks:
            ana["enabled"] = False
            continue
        if args.enable_tasks and ana["name"] in args.enable_tasks:
            ana["enabled"] = True

    with open(args.output, "w") as f:
        json.dump({"analyses": analyses}, f, indent=2)

    return 0


def check(args):
    """
    check a few things for a given task

    Prints some info on stdout
    1. --status ==> ENABLED or DISABLED
    2. --applicable-to ==> mc/data
    """

    def print_status(enabled):
         if enabled:
            print("ENABLED")
            return
         print("DISABLED")

    def print_applicable_to(valid_keys):
        for vk in valid_keys:
            print(vk)

    analyses = None
    with open (args.config, "r") as f:
        analyses = json.load(f)["analyses"]

    for ana in analyses:
        if ana["name"] == args.task:
            if args.status:
                print_status(ana["enabled"])
            if args.applicable_to:
                print_applicable_to([k for k, v in ana["config"].items() if v])
            return 0

    # analysis not found
    print(f"WARNING: Analysis {args.task} unknown")
    return 1

def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Modify analysis configuration and write new config')
    sub_parsers = parser.add_subparsers(dest="command")

    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("-c", "--config", help="input configuration to modify", default=join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", "analyses_config.json"))

    # modify config
    modify_parser = sub_parsers.add_parser("modify", parents=[config_parser])
    modify_parser.add_argument("-o", "--output", default="analyses_config.json", help="output name of new configuration")
    modify_parser.add_argument("--enable-tasks", dest="enable_tasks", nargs="*", help="analysis task names to enable (if disabled)")
    modify_parser.add_argument("--disable-tasks", dest="disable_tasks", nargs="*", help="analysis task names to disable (if enabled), takes precedence over --enable-tasks")
    modify_parser.set_defaults(func=modify)

    # check properties of a task
    check_parser = sub_parsers.add_parser("check", parents=[config_parser])
    check_parser.add_argument("-t", "--task", help="analysis task to check", required=True)
    check_parser.add_argument("--status", action="store_true", help="check if task is enabled or disabled")
    check_parser.add_argument("--applicable-to", dest="applicable_to", action="store_true", help="check if valid for MC or data")
    check_parser.set_defaults(func=check)

    # parse and run
    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
