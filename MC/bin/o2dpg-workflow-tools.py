#!/usr/bin/env python3

import sys
from os.path import join, dirname, exists
import argparse

sys.path.append(join(dirname(__file__), '.', 'o2dpg_workflow_utils'))

from o2dpg_workflow_utils import createTask, read_workflow, dump_workflow, check_workflow, update_workflow_resource_requirements, make_workflow_filename

def extend(args):
    """extend a workflow by another one

    The overall configuration from the original workflow
    is kept
    """
    # load workflows
    workflow_orig, meta = read_workflow(args.orig_wf)
    workflow_extend, _ = read_workflow(args.extend_wf)

    # extend
    workflow_orig.extend(workflow_extend)

    # dump in new file
    filename = args.output if args.output else args.orig_wf
    # propagate meta information from original workflow that is extended
    dump_workflow(workflow_orig, filename, meta)


def create(args):
    """create an empty workflow skeleton or add task skeletons to existing workflow
    """
    filename = make_workflow_filename(args.file)
    if not args.add_task and exists(filename):
        print(f"Workflow file {filename} does already exist. Delete it and try again")
        return
    if not args.add_task or not exists(filename):
        # just create an empty workflow
        dump_workflow([], filename)
    if args.add_task:
        # add another task skeleton with name
        workflow, meta = read_workflow(filename)
        for name in args.add_task:
            workflow.append(createTask(name=name))
        dump_workflow(workflow, filename, meta=meta)


def find_task(workflow, task_name):
    for s in workflow:
        if s["name"] == task_name:
            return s
    return None


def modify(args):
    workflow, meta = read_workflow(args.file)
    # try to find the requested task
    task = find_task(workflow, args.task)
    if not task:
        print(f"Task with name {args.task} does not exist")
        exit(1)
    for attr in ("name", "needs", "timeframe", "cwd", "labels", "cmd"):
        if hasattr(args, attr) and getattr(args, attr) is not None:
            task[attr] = getattr(args, attr)
    for attr in ("cpu", "relative_cpu", "mem"):
        if hasattr(args, attr) and getattr(args, attr) is not None:
            task["resources"][attr] = getattr(args, attr)

    dump_workflow(workflow, args.file, meta=meta)


def nworkers(args):
    workflow, meta = read_workflow(args.file)
    update_workflow_resource_requirements(workflow, args.jobs)
    dump_workflow(workflow, args.file, meta=meta)


def inspect(args):
    """Inspecting a workflow

    This is at the moment more show-casing what one could do
    """
    workflow, meta = read_workflow(args.file)
    if args.check:
        check_workflow(workflow)
    if args.task:
        task = find_task(workflow, args.task)
        if not task:
            print(f"Task with name {args.task}")
            exit(1)
        print("Here are the requested task information")
        print(task)
    if meta:
        print("Here are the meta information")
        for key, value in meta.items():
            print(f"{key}: {value}")


def main():

    parser = argparse.ArgumentParser(description='Create an ALICE (Run3) MC simulation workflow')

    sub_parsers = parser.add_subparsers(dest="command")

    create_parser = sub_parsers.add_parser("create", help="manage a workflow")
    create_parser.set_defaults(func=create)
    create_parser.add_argument("file", help="workflow file to be created or modifed")
    create_parser.add_argument("--add-task", dest="add_task", nargs="+", help="add named tasks to workflow file")

    # Append to (sim) workflow
    merge_parser = sub_parsers.add_parser("merge", help="append stages")
    merge_parser.set_defaults(func=extend)
    merge_parser.add_argument("orig_wf", help="original workflow")
    merge_parser.add_argument("extend_wf", help="workflow JSON to be merged to orig")
    merge_parser.add_argument("--output", "-o", help="extended workflow output file name", default="workflow_merged.json")

    nworker_parser = sub_parsers.add_parser("nworkers", help="update number of workers")
    nworker_parser.set_defaults(func=nworkers)
    nworker_parser.add_argument("file", help="the workflow file to be modified")
    nworker_parser.add_argument("jobs", type=int, help="number of workers to recompute relative cpu")

    modify_parser = sub_parsers.add_parser("modify", help="modify a task")
    modify_parser.set_defaults(func=modify)
    modify_parser.add_argument("file", help="the workflow file to be modified")
    modify_parser.add_argument("task", help="name of task to be modified")
    # not allowing for changing the name at the moment as this also goes into the log-file name
    #modify_parser.add_argument("--name", help="new name of this task")
    modify_parser.add_argument("--needs", nargs="+", help="required tasks to be executed before this one")
    modify_parser.add_argument("--timeframe", type=int, help="timeframe")
    modify_parser.add_argument("--cwd", help="current working directory of this task")
    modify_parser.add_argument("--labels", nargs="+", help="attached labels")
    modify_parser.add_argument("--cpu", type=int, help="absolute number of workers to be used for this task")
    modify_parser.add_argument("--relative-cpu", dest="relative_cpu", type=float, help="realtive fraction of maximum number of available workers")
    modify_parser.add_argument("--mem", type=int, help="estimated memory")
    modify_parser.add_argument("--cmd", help="command line to be executed")

    inspect_parser = sub_parsers.add_parser("inspect", help="inspect a workflow")
    inspect_parser.set_defaults(func=inspect)
    inspect_parser.add_argument("file", help="Workflow file to inspect")
    inspect_parser.add_argument("--check", action="store_true", help="Check sanity of workflow")
    inspect_parser.add_argument("--task", help="name of task to be inspected in detail")

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.parse_args(["--help"])
        exit(0)

    args.func(args)


if __name__ == "__main__":
    # provide this also stand-alone if called directly from the interpreter
    main()
