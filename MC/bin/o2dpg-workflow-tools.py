#!/usr/bin/env python3

import sys
from os.path import join, dirname
import argparse

sys.path.append(join(dirname(__file__), '.', 'o2dpg_workflow_utils'))

from o2dpg_workflow_utils import createTask, read_workflow, dump_workflow, check_workflow, update_workflow_resource_requirements

def extend(args):
    """extend a workflow by another one

    The overall configuration from the original workflow
    is kept
    """
    # load workflows
    workflow_orig = read_workflow(args.orig_wf)
    workflow_extend = read_workflow(args.extend_wf)

    # extend
    workflow_orig.extend(workflow_extend)

    # dump in new file
    filename = args.output if args.output else args.orig_wf
    dump_workflow(workflow_orig, filename)


def create_modify(args):
    """create an empty workflow skeleton or modify it
    """
    if args.create:
        # empty workflow
        dump_workflow([], args.file)
    if args.add_task:
        # add another task skeleton with name
        workflow = read_workflow(args.file)
        for name in args.add_task:
            workflow.append(createTask(name=name))
        dump_workflow(workflow, args.file)
    if args.jobs:
        workflow = read_workflow(args.file)
        update_workflow_resource_requirements(workflow, args.jobs)
        dump_workflow(workflow, args.file)


def inspect(args):
    """Inspecting a workflow

    This is at the moment more show-casing what one could do
    """
    workflow = read_workflow(args.file)
    if args.check:
        check_workflow(workflow)
    if args.summary:
        summary_workflow(workflow)


def main():

    parser = argparse.ArgumentParser(description='Create an ALICE (Run3) MC simulation workflow')

    sub_parsers = parser.add_subparsers(dest="command")

    # Append to (sim) workflow
    merge_parser = sub_parsers.add_parser("merge", help="append stages")
    merge_parser.set_defaults(func=extend)
    merge_parser.add_argument("orig_wf", help="original workflow")
    merge_parser.add_argument("extend_wf", help="workflow JSON to be merged to orig")
    merge_parser.add_argument("--output", "-o", help="extended workflow output file name", default="workflow_merged.json")

    create_modify_parser = sub_parsers.add_parser("modify", help="manage a workflow")
    create_modify_parser.set_defaults(func=create_modify)
    create_modify_parser.add_argument("file", help="workflow file to be created or modifed")
    create_modify_parser.add_argument("--create", action="store_true", help="name of workflow file to be created")
    create_modify_parser.add_argument("--add-task", dest="add_task", nargs="+", help="add named tasks to workflow file")
    create_modify_parser.add_argument("--jobs", "-j", type=int, help="number of workers in case it should be recomputed")

    inspect_parser = sub_parsers.add_parser("inspect", help="inspect a workflow")
    inspect_parser.set_defaults(func=inspect)
    inspect_parser.add_argument("file", help="Workflow file to inspect")
    inspect_parser.add_argument("--summary", action="store_true", help="print summary of workflow")
    inspect_parser.add_argument("--check", action="store_true", help="Check sanity of workflow") 

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.parse_args(["--help"])
        exit(0)

    args.func(args)


if __name__ == "__main__":
    # provide this also stand-alone if called directly from the interpreter
    main()
