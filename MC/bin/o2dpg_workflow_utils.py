#!/usr/bin/env python3

from os import environ, getcwd
from copy import deepcopy
import json


# List of active detectors
ACTIVE_DETECTORS = ["all"]
INACTIVE_DETECTORS = []

def activate_detector(det):
    try:
        # first of all remove "all" if a specific detector is passed
        ind = ACTIVE_DETECTORS.index("all")
        del ACTIVE_DETECTORS[ind]
    except ValueError:
        pass
    ACTIVE_DETECTORS.append(det)

def deactivate_detector(det):
    INACTIVE_DETECTORS.append(det)

def isActive(det):
    return det not in INACTIVE_DETECTORS and ("all" in ACTIVE_DETECTORS or det in ACTIVE_DETECTORS)

def compute_n_workers(interaction_rate, collision_system, n_workers_user=8, n_workers_min=1, interaction_rate_linear_below=300000):
    """
    Compute number of workers

    n_workers = m * IR + b

    based on
    https://indico.cern.ch/event/1395900/contributions/5868567/attachments/2823967/4932440/20240320_slides_cpu_eff.pdf, slide 3

    Assume n_workers_in=8 to be ideal for pp IR > interaction_rate_linear_below

    Start with 1 worker at IR=0
    Go linearly until interaction_rate_linear_below
    """
    if collision_system == "PbPb" or interaction_rate >= interaction_rate_linear_below:
        return n_workers_user

    n_workers_min = max(1, n_workers_min)
    m = (n_workers_user - n_workers_min) / interaction_rate_linear_below
    # at least 1 worker
    return max(1, round(m * interaction_rate + n_workers_min))

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
    """Creates and new task. A task is a dictionary/class with typically the following attributes

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


def createGlobalInitTask(keys_values=None, set_defaults=True):
    """Returns a special task that is recognized by the executor as
       a task whose environment section is to be globally applied to all tasks of
       a workflow.

    Args:
        keys_values: dict or None
            dictionary of environment variables and values to be globally applied to all tasks
            if sharing keys with defaults, keys_values takes precedence
        set_defaults: bool
            whether or not some default values will be added

    Returns:
        dict: task dictionary
    """

    # dictionary holding global environment to be passed to task
    env_dict = {}

    if set_defaults:
        if environ.get('ALICEO2_CCDB_LOCALCACHE') is None:
            print ("ALICEO2_CCDB_LOCALCACHE not set; setting to default " + getcwd() + '/ccdb')
            env_dict['ALICEO2_CCDB_LOCALCACHE'] = getcwd() + "/ccdb"
        else:
        # fixes the workflow to use and remember externally provided path
            env_dict['ALICEO2_CCDB_LOCALCACHE'] = environ.get('ALICEO2_CCDB_LOCALCACHE')
        env_dict['IGNORE_VALIDITYCHECK_OF_CCDB_LOCALCACHE'] = '${ALICEO2_CCDB_LOCALCACHE:+"ON"}'

    if keys_values:
        # keys_values takes priority in case of same keys
        env_dict |= keys_values

    t = createTask(name = '__global_init_task__')
    t['cmd'] = 'NO-COMMAND'
    t['env'] = env_dict
    return t


def summary_workflow(workflow):
    print("=== WORKFLOW SUMMARY ===\n")
    print(f"-> There are {len(workflow)} tasks")


def dump_workflow(workflow, filename, meta=None):
    """write this workflow to a file

    Args:
        workflow: list
            stages of this workflow
        filename: str
            name of the output file
    """

    # Sanity checks on list of tasks
    check_workflow(workflow)
    taskwrapper_string = "${O2_ROOT}/share/scripts/jobutils2.sh; taskwrapper"
    # prepare for dumping, deepcopy to detach from this instance
    to_dump = deepcopy(workflow)

    for s in to_dump:
        if s["cmd"] and s["name"] != '__global_init_task__' and taskwrapper_string not in s["cmd"]:
            # insert taskwrapper stuff if not there already, only do it if cmd string is not empty
            s['cmd'] = '. ' + taskwrapper_string + ' ' + s['name']+'.log \'' + s['cmd'] + '\''
        # remove unnecessary whitespaces for better readibility
        s['cmd'] = trimString(s['cmd'])
    # make the final dict to be dumped
    to_dump = {"stages": to_dump}
    filename = make_workflow_filename(filename)
    to_dump["meta"] = meta if meta else {}

    with open(filename, 'w') as outfile:
        json.dump(to_dump, outfile, indent=2)

    print(f"Workflow saved at {filename}")


def read_workflow(filename):
    workflow = None
    filename = make_workflow_filename(filename)
    with open(filename, "r") as wf_file:
        loaded = json.load(wf_file)
        workflow =loaded["stages"]
        meta = loaded.get("meta", {})
    return workflow, meta


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

# Adjusts software version for RECO (and beyond) stages
# (if this is wished). Function implements specific wish from operations
# to be able to operate with different sim and reco software versions (due to different speed of development and fixes and patching).
def adjust_RECO_environment(workflowspec, package = ""):
    if len(package) == 0:
       return

    # we try to extract the stage from the path (can be given via '@' separation)
    # example O2sim::daily-xxx@DIGI ---> apply this environment from the DIGI phase
    # example O2sim::daily-xxx@RECO ---> apply this environment from the RECO phase
    # example O2sim::daily-xxx ---> apply this environment from the RECO phase == default case
    from_stage = "RECO"
    if package.count('@') == 1:
        package, from_stage = package.split('@')

    # We essentially need to go through the graph and apply the mapping
    # so take the workflow spec and see if the task itself or any child
    # is labeled RECO ---> typical graph traversal with caching

    # helper structures
    taskuniverse = [ l['name'] for l in workflowspec['stages'] ]
    tasktoid = {}
    for i in range(len(taskuniverse)):
        tasktoid[taskuniverse[i]]=i

    matches_label = {}
    # internal helper for recursive graph traversal
    def matches_or_inherits_label(taskid, label, cache):
        if cache.get(taskid) != None:
           return cache[taskid]
        result = False
        if label in workflowspec['stages'][taskid]['labels']:
           result = True
        else:
           # check mother tasks
           for mothertask in workflowspec['stages'][taskid]['needs']:
               motherid = tasktoid[mothertask]
               if matches_or_inherits_label(motherid, label, cache):
                  result = True
                  break

        cache[taskid] = result
        return result

    # fills the matches_label dictionary
    for taskid in range(len(workflowspec['stages'])):
        if (matches_or_inherits_label(taskid, from_stage, matches_label)):
           # now we do the final adjust (as annotation) in the workflow itself
           if workflowspec['stages'][taskid].get('disable_alternative_reco_software', False) != True:
              if workflowspec['stages'][taskid].get("alternative_alienv_package") == None:
                 workflowspec['stages'][taskid]["alternative_alienv_package"] = package

def merge_dicts(dict1, dict2):
    """
    merges dict2 into dict1 (potentially overwriting values)
    """
    for key, value in dict2.items():
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            # If both are dictionaries, merge them recursively
            merge_dicts(dict1[key], value)
        else:
            # Otherwise, overwrite dict1's value with dict2's value
            dict1[key] = value
