#!/usr/bin/env python3

from copy import deepcopy
import json


def relativeCPU(n_rel, n_workers):
    # compute number of CPUs from a given number of workers
    # n_workers and a fraction n_rel
    # catch cases where n_rel > 1 or n_workers * n_rel
    return round(min(n_workers, n_workers * n_rel), 2)

def trimString(cmd):
  # trim unnecessary spaces
  return ' '.join(cmd.split())


def make_workflow_filename(filename):
    if filename.lower().rfind(".json") < 0:
        # append extension if not there
        return filename + ".json"
    return filename

def update_workflow_resource_requirements(workflow, n_workers):
    """Update resource requirements/settings
    """
    for s in workflow:
        if s["resources"]["relative_cpu"]:
            s["resources"]["cpu"] = relativeCPU(s["resources"]["relative_cpu"], n_workers)


def createTask(name='', needs=[], tf=-1, cwd='./', lab=[], cpu=1, relative_cpu=None, mem=500, n_workers=8):
    """create and attach new task

    Args:
        name: str
            task name
        needs: list
            list of task names this tasks depends on
        tf: int
            associated timeframe
        cwd: str
            working directory of this task, will be created automatically
        lab: list
            list of labels to be attached
        cpu: float
            absolute number of CPU this task uses/needs on average
        relative_cpu: float or None
            if given, cpu is recomputed based on the number of available workers
        mem: int
            memory size needed by this task

    Returns:
        dict representing the task
    """
    if relative_cpu is not None:
        # Re-compute, if relative number of CPUs requested
        cpu = relativeCPU(relative_cpu, n_workers)
    return { 'name': name,
             'cmd':'',
             'needs': needs,
             'resources': { 'cpu': cpu, 'relative_cpu': relative_cpu , 'mem': mem },
             'timeframe' : tf,
             'labels' : lab,
             'cwd' : cwd }


def summary_workflow(workflow):
    print("=== WORKFLOW SUMMARY ===\n")
    print(f"-> There are {len(workflow)} tasks")


def dump_workflow(workflow, filename):
    """write this workflow to a file

    Args:
        workflow: list
            stages of this workflow
        filename: str
            name of the output file
    """

    # Sanity checks
    check_workflow(workflow)
    taskwrapper_string = "${O2_ROOT}/share/scripts/jobutils2.sh; taskwrapper"
    # prepare for dumping, deepcopy to detach from this instance
    dump_workflow = deepcopy(workflow)

    for s in dump_workflow:
        if s["cmd"] and taskwrapper_string not in s["cmd"]:
            # insert taskwrapper stuff if not there already, only do it if cmd string is not empty
            s['cmd'] = '. ' + taskwrapper_string + ' ' + s['name']+'.log \'' + s['cmd'] + '\''
        # remove unnecessary whitespaces for better readibility
        s['cmd'] = trimString(s['cmd'])
    # make the final dict to be dumped
    dump_workflow = {"stages": dump_workflow}

    filename = make_workflow_filename(filename)
    
    with open(filename, 'w') as outfile:
        json.dump(dump_workflow, outfile, indent=2)

    print(f"Workflow saved at {filename}")


def read_workflow(filename):
    workflow = None
    filename = make_workflow_filename(filename)
    with open(filename, "r") as wf_file:
        workflow = json.load(wf_file)["stages"]
    return workflow


def check_workflow_dependencies(workflow, collect_warnings, collect_errors):
    """check dependencies among tasks

    Args:
        collect_warnings: list
            collect all warnings that might come up
        collect_errors: list
            collect all errors that might come up
    """
    
    is_sane = True
    needed = []
    names = []

    for s in workflow:
        needed.extend(s["needs"])
        names.append(s["name"])
    
    # remove potential duplicates
    needed = list(set(needed))

    for n in needed:
        if n not in names:
            # For now, only add a warning since tasks might still be added
            collect_warnings.append(f"WARNING: Task {n} is needed but is not in tasks (might be added later)")
            is_sane = False

    return is_sane


def check_workflow_unique_names(workflow, collect_warnings, collect_errors):
    """check for uniqueness of task names

    Args:
        collect_warnings: list
            collect all warnings that might come up
        collect_errors: list
            collect all errors that might come up
    """

    is_sane = True
    dupl = []
    for s in workflow:
        if s["name"] in dupl:
            # That is an error since adding another task for instance would not solve that
            collect_errors.append(f"Task with {s['name']} already defined")
            is_sane = False
            continue
        dupl.append(s["name"])
    return is_sane


def check_workflow(workflow):
    """Conduct sanity checks for this workflow
    """
    
    collect_warnings = []
    collect_errors = []
    is_sane = check_workflow_dependencies(workflow, collect_warnings, collect_errors) and check_workflow_unique_names(workflow, collect_warnings, collect_errors)

    print(f"=== There are {len(collect_warnings)} warnings ===")
    for w in collect_warnings:
        print(w)
    print(f"=== There are {len(collect_errors)} errors ===")
    for e in collect_errors:
        print(e)

    if is_sane:
        print("===> The workflow looks sane")
    else:
        print("===> Please check warnings and errors!")

    return is_sane
