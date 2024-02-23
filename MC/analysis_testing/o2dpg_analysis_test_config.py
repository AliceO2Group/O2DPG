#!/usr/bin/env python3

import sys
import argparse
from os import environ
from os.path import join, exists
import json

### hello Benedikt!

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

    analyses = None
    with open (args.config, "r") as f:
        analyses = json.load(f)["analyses"]

    for ana in analyses:
        if ana["name"] == args.task:
            if args.status:
                print_status(ana["enabled"])
            if args.applicable_to:
                if ana.get("valid_mc", False):
                    print("mc")
                if ana.get("valid_data", False):
                    print("data")

            return 0

    # analysis not found
    print(f"UNKNOWN")
    return 1


def show_tasks(args):
    """
    Browse through analyses and see what is en-/disabled
    """
    if not args.enabled and not args.disabled:
        args.enabled = True
        args.disabled = True

    analyses = None
    with open (args.config, "r") as f:
        analyses = json.load(f)["analyses"]

    for ana in analyses:
        if (args.enabled and ana["enabled"]) or (args.disabled and not ana["enabled"]):
            print(ana["name"])

    return 0


def validate_output(args):
    analyses = None
    with open (args.config, "r") as f:
        analyses = json.load(f)["analyses"]

    # global return code
    ret = 0
    # whether or not check analyses that are by default disabled
    include_disabled = args.include_disabled

    for ana in analyses:
        analysis_name = ana["name"]

        if args.tasks:
            if analysis_name in args.tasks:
                # tasks were specified explicitly, make sure to take them into account at all costs
                include_disabled = True
            else:
                continue

        if not ana["enabled"] and not include_disabled:
            # continue if disabled and not including those
            continue

        analysis_dir = join(args.directory, analysis_name)

        if not exists(analysis_dir):
            print(f"Expected output directory {analysis_dir} for analysis {analysis_name} does not exist.")
            ret = 1
            continue

        if not ana["expected_output"]:
            # expected to have no output
            continue

        for expected_output in ana["expected_output"]:
            expected_output = join(analysis_dir, expected_output)
            if not exists(expected_output):
                print(f"Expected output {expected_output} for analysis {analysis_name} does not exist.")
                ret = 1

        logfile = join(analysis_dir, f"Analysis_{analysis_name}.log")

        if exists(logfile):
            exit_code = "0"
            with open(logfile, "r") as f:
                for line in f:
                    if "TASK-EXIT-CODE:" in line:
                        exit_code = line.strip().split()[1]
                        if exit_code != "0":
                            print(f"Analysis {analysis_name} had non-zero exit code {exit_code}.")
                            ret = 1
                            break
            if exit_code != "0":
                continue
            logfile_done = join(analysis_dir, f"Analysis_{analysis_name}.log_done")
            if not exists(logfile_done):
                print(f"Apparently, analysis {analysis_name} did not run successfully, {logfile_done} does not exist.")
                ret = 1

    return ret


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

    # Show enabled or disabled tasks
    show_parser = sub_parsers.add_parser("show-tasks", parents=[config_parser])
    show_parser.add_argument("--enabled", action="store_true", help="show enabled tasks")
    show_parser.add_argument("--disabled", action="store_true", help="show disabled tasks")
    show_parser.set_defaults(func=show_tasks)

    # check properties of a task
    check_parser = sub_parsers.add_parser("check", parents=[config_parser])
    check_parser.add_argument("-t", "--task", help="analysis task to check", required=True)
    check_parser.add_argument("--status", action="store_true", help="check if task is enabled or disabled")
    check_parser.add_argument("--applicable-to", dest="applicable_to", action="store_true", help="check if valid for MC or data")
    check_parser.set_defaults(func=check)

    # check properties of a task
    validate_parser = sub_parsers.add_parser("validate-output", parents=[config_parser])
    validate_parser.add_argument("-t", "--tasks", nargs="*", help="analysis tasks to validate; if not specified, all analyses a validated")
    validate_parser.add_argument("-d", "--directory", help="top directory (usually called \"Analysis\") where to find individual analysis directories", required=True)
    validate_parser.add_argument("--include-disabled", action="store_true", help="include tasks that are usually switched of (not needed if task is specified explicitly with --task)")
    validate_parser.set_defaults(func=validate_output)

    # parse and run
    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
