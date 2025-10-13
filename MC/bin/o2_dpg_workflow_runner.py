#!/usr/bin/env python3

# started February 2021, sandro.wenzel@cern.ch

import re
import subprocess
import time
import json
import logging
import os
import signal
import socket
import sys
import traceback
import platform
import tarfile
from copy import deepcopy
try:
    from graphviz import Digraph
    havegraphviz=True
except ImportError:
    havegraphviz=False

formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

sys.setrecursionlimit(100000)

import argparse
import psutil
max_system_mem=psutil.virtual_memory().total

sys.path.append(os.path.join(os.path.dirname(__file__), '.', 'o2dpg_workflow_utils'))
from o2dpg_workflow_utils import read_workflow

# defining command line options
parser = argparse.ArgumentParser(description='Parallel execution of a (O2-DPG) DAG data/job pipeline under resource contraints.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-f','--workflowfile', help='Input workflow file name', required=True)
parser.add_argument('-jmax','--maxjobs', type=int, help='Number of maximal parallel tasks.', default=100)
parser.add_argument('-k','--keep-going', action='store_true', help='Keep executing the pipeline as far possibe (not stopping on first failure)')
parser.add_argument('--dry-run', action='store_true', help='Show what you would do.')
parser.add_argument('--visualize-workflow', action='store_true', help='Saves a graph visualization of workflow.')
parser.add_argument('--target-labels', nargs='+', help='Runs the pipeline by target labels (example "TPC" or "DIGI").\
                    This condition is used as logical AND together with --target-tasks.', default=[])
parser.add_argument('-tt','--target-tasks', nargs='+', help='Runs the pipeline by target tasks (example "tpcdigi"). By default everything in the graph is run. Regular expressions supported.', default=["*"])
parser.add_argument('--produce-script', help='Produces a shell script that runs the workflow in serialized manner and quits.')
parser.add_argument('--rerun-from', help='Reruns the workflow starting from given task (or pattern). All dependent jobs will be rerun.')
parser.add_argument('--list-tasks', help='Simply list all tasks by name and quit.', action='store_true')

# Resources
parser.add_argument('--update-resources', dest="update_resources", help='Read resource estimates from a JSON and apply where possible.')
parser.add_argument("--dynamic-resources", dest="dynamic_resources", action="store_true", help="Update reources estimates of task based on finished related tasks") # derive resources dynamically
parser.add_argument('--optimistic-resources', dest="optimistic_resources", action="store_true", help="Try to run workflow even though resource limits might underestimate resource needs of some tasks")
parser.add_argument("--n-backfill", dest="n_backfill", type=int, default=1)
parser.add_argument('--mem-limit', help='Set memory limit as scheduling constraint (in MB)', default=0.9*max_system_mem/1024./1024, type=float)
parser.add_argument('--cpu-limit', help='Set CPU limit (core count)', default=8, type=float)
parser.add_argument('--cgroup', help='Execute pipeline under a given cgroup (e.g., 8coregrid) emulating resource constraints. This m\
ust exist and the tasks file must be writable to with the current user.')

# run control, webhooks
parser.add_argument('--stdout-on-failure', action='store_true', help='Print log files of failing tasks to stdout,')
parser.add_argument('--webhook', help=argparse.SUPPRESS) # log some infos to this webhook channel
parser.add_argument('--checkpoint-on-failure', help=argparse.SUPPRESS) # debug option making a debug-tarball and sending to specified address
                                                                       # argument is alien-path
parser.add_argument('--retry-on-failure', help=argparse.SUPPRESS, default=0) # number of times a failing task is retried
parser.add_argument('--no-rootinit-speedup', help=argparse.SUPPRESS, action='store_true') # disable init of ROOT environment vars to speedup init/startup

parser.add_argument('--remove-files-early', type=str, default="", help="Delete intermediate files early (using the file graph information in the given file)")


# Logging
parser.add_argument('--action-logfile', help='Logfilename for action logs. If none given, pipeline_action_#PID.log will be used')
parser.add_argument('--metric-logfile', help='Logfilename for metric logs. If none given, pipeline_metric_#PID.log will be used')
parser.add_argument('--production-mode', action='store_true', help='Production mode')
# will trigger special features good for non-interactive/production processing (automatic cleanup of files etc).
args = parser.parse_args()

def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""

    handler = logging.FileHandler(log_file, mode='w')
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger

# first file logger
actionlogger_file = ('pipeline_action_' + str(os.getpid()) + '.log', args.action_logfile)[args.action_logfile!=None]
actionlogger = setup_logger('pipeline_action_logger', actionlogger_file, level=logging.DEBUG)

# second file logger
metriclogger = setup_logger('pipeline_metric_logger', ('pipeline_metric_' + str(os.getpid()) + '.log', args.action_logfile)[args.action_logfile!=None])

# Immediately log imposed memory and CPU limit as well as further useful meta info
_ , meta = read_workflow(args.workflowfile)
meta["cpu_limit"] = args.cpu_limit
meta["mem_limit"] = args.mem_limit
meta["workflow_file"] = os.path.abspath(args.workflowfile)
args.target_tasks = [f.strip('"').strip("'") for f in args.target_tasks] # strip quotes from the shell
meta["target_task"] = args.target_tasks
meta["rerun_from"] = args.rerun_from
meta["target_labels"] = args.target_labels
metriclogger.info(meta)

# for debugging without terminal access
# TODO: integrate into standard logger
def send_webhook(hook, t):
    if hook!=None:
      command="curl -X POST -H 'Content-type: application/json' --data '{\"text\":\" " + str(t) + "\"}' " + str(hook) + " &> /dev/null"
      os.system(command)

# A fallback solution to getting all child procs
# in case psutil has problems (PermissionError).
# It returns the same list as psutil.children(recursive=True).
def getChildProcs(basepid):
  cmd='''
  childprocs() {
  local parent=$1
  if [ ! "$2" ]; then
    child_pid_list=""
  fi
  if [ "$parent" ] ; then
    child_pid_list="$child_pid_list $parent"
    for childpid in $(pgrep -P ${parent}); do
      childprocs $childpid "nottoplevel"
    done;
  fi
  # return via a string list (only if toplevel)
  if [ ! "$2" ]; then
    echo "${child_pid_list}"
  fi
  }
  '''
  cmd = cmd + '\n' + 'childprocs ' + str(basepid)
  output = subprocess.check_output(cmd, shell=True)
  plist = []
  for p in output.strip().split():
     try:
         proc=psutil.Process(int(p))
     except psutil.NoSuchProcess:
         continue

     plist.append(proc)
  return plist

#
# Code section to find all topological orderings
# of a DAG. This is used to know when we can schedule
# things in parallel.
# Taken from https://www.geeksforgeeks.org/all-topological-sorts-of-a-directed-acyclic-graph/

# class to represent a graph object
class Graph:

    # Constructor
    def __init__(self, edges, N):

        # A List of Lists to represent an adjacency list
        self.adjList = [[] for _ in range(N)]

        # stores in-degree of a vertex
        # initialize in-degree of each vertex by 0
        self.indegree = [0] * N

        # add edges to the undirected graph
        for (src, dest) in edges:

            # add an edge from source to destination
            self.adjList[src].append(dest)

            # increment in-degree of destination vertex by 1
            self.indegree[dest] = self.indegree[dest] + 1

# Recursive function to find all topological orderings of a given DAG
def findAllTopologicalOrders(graph, path, discovered, N, allpaths, maxnumber=1):
    if len(allpaths) >= maxnumber:
        return

    # do for every vertex
    for v in range(N):

        # proceed only if in-degree of current node is 0 and
        # current node is not processed yet
        if graph.indegree[v] == 0 and not discovered[v]:

            # for every adjacent vertex u of v, reduce in-degree of u by 1
            for u in graph.adjList[v]:
                graph.indegree[u] = graph.indegree[u] - 1

            # include current node in the path and mark it as discovered
            path.append(v)
            discovered[v] = True

            # recur
            findAllTopologicalOrders(graph, path, discovered, N, allpaths)

            # backtrack: reset in-degree information for the current node
            for u in graph.adjList[v]:
                graph.indegree[u] = graph.indegree[u] + 1

            # backtrack: remove current node from the path and
            # mark it as undiscovered
            path.pop()
            discovered[v] = False

    # record valid ordering
    if len(path) == N:
        allpaths.append(path.copy())


# get all topological orderings of a given DAG as a list
def printAllTopologicalOrders(graph, maxnumber=1):
    # get number of nodes in the graph
    N = len(graph.adjList)

    # create an auxiliary space to keep track of whether vertex is discovered
    discovered = [False] * N

    # list to store the topological order
    path = []
    allpaths = []
    # find all topological ordering and print them
    findAllTopologicalOrders(graph, path, discovered, N, allpaths, maxnumber=maxnumber)
    return allpaths

# <--- end code section for topological sorts

# find all tasks that depend on a given task (id); when a cache
# dict is given we can fill for the whole graph in one pass...
def find_all_dependent_tasks(possiblenexttask, tid, cache=None):
    c=cache.get(tid) if cache else None
    if c!=None:
        return c

    daughterlist=[tid]
    # possibly recurse
    for n in possiblenexttask[tid]:
        c = cache.get(n) if cache else None
        if c == None:
            c = find_all_dependent_tasks(possiblenexttask, n, cache)
        daughterlist = daughterlist + c
        if cache is not None:
            cache[n]=c

    if cache is not None:
        cache[tid]=daughterlist
    return list(set(daughterlist))


# wrapper taking some edges, constructing the graph,
# obtain all topological orderings and some other helper data structures
def analyseGraph(edges, nodes):
    # Number of nodes in the graph
    N = len(nodes)

    # candidate list trivial
    nextjobtrivial = { n:[] for n in nodes }
    # startnodes
    nextjobtrivial[-1] = nodes
    for e in edges:
        nextjobtrivial[e[0]].append(e[1])
        if nextjobtrivial[-1].count(e[1]):
            nextjobtrivial[-1].remove(e[1])

    # find topological orderings of the graph
    # create a graph from edges
    graph = Graph(edges, N)
    orderings = printAllTopologicalOrders(graph)

    return (orderings, nextjobtrivial)


def draw_workflow(workflowspec):
    if not havegraphviz:
        print('graphviz not installed, cannot draw workflow')
        return

    dot = Digraph(comment='MC workflow')
    nametoindex={}
    index=0
    # nodes
    for node in workflowspec['stages']:
        name=node['name']
        nametoindex[name]=index
        dot.node(str(index), name)
        index=index+1

    # edges
    for node in workflowspec['stages']:
        toindex = nametoindex[node['name']]
        for req in node['needs']:
            fromindex = nametoindex[req]
            dot.edge(str(fromindex), str(toindex))

    dot.render('workflow.gv')

# builds the graph given a "taskuniverse" list
# builds accompagnying structures tasktoid and idtotask
def build_graph(taskuniverse, workflowspec):
    tasktoid={ t[0]['name']:i for i, t in enumerate(taskuniverse, 0) }
    # print (tasktoid)

    nodes = []
    edges = []
    for t in taskuniverse:
        nodes.append(tasktoid[t[0]['name']])
        for n in t[0]['needs']:
            edges.append((tasktoid[n], tasktoid[t[0]['name']]))

    return (edges, nodes)


# loads json into dict, e.g. for workflow specification
def load_json(workflowfile):
    fp=open(workflowfile)
    workflowspec=json.load(fp)
    return workflowspec


# filters the original workflowspec according to wanted targets or labels
# returns a new workflowspec and the list of "final" workflowtargets
def filter_workflow(workflowspec, targets=[], targetlabels=[]):
    if len(targets)==0:
       return workflowspec, []
    if len(targetlabels)==0 and len(targets)==1 and targets[0]=="*":
       return workflowspec, []

    transformedworkflowspec = workflowspec

    def task_matches(t):
        for filt in targets:
            if filt=="*":
                return True
            if re.match(filt, t) != None:
                return True
        return False

    def task_matches_labels(t):
        # when no labels are given at all it's ok
        if len(targetlabels)==0:
            return True

        for l in t['labels']:
            if targetlabels.count(l)!=0:
                return True
        return False

    # The following sequence of operations works and is somewhat structured.
    # However, it builds lookups used elsewhere as well, so some CPU might be saved by reusing
    # some structures across functions or by doing less passes on the data.

    # helper lookup
    tasknametoid = { t['name']:i for i, t in enumerate(workflowspec['stages'],0) }

    # check if a task can be run at all
    # or not due to missing requirements
    def canBeDone(t,cache={}):
       ok = True
       c = cache.get(t['name'])
       if c != None:
           return c
       for r in t['needs']:
           taskid = tasknametoid.get(r)
           if taskid != None:
             if not canBeDone(workflowspec['stages'][taskid], cache):
                ok = False
                break
           else:
             ok = False
             break
       cache[t['name']] = ok
       if ok == False:
           print (f"Disabling target {t['name']} due to unsatisfied requirements")
       return ok

    okcache = {}
    # build full target list
    full_target_list = [ t for t in workflowspec['stages'] if task_matches(t['name']) and task_matches_labels(t) and canBeDone(t,okcache) ]
    full_target_name_list = [ t['name'] for t in full_target_list ]

    # build full dependency list for a task t
    def getallrequirements(t):
        _l=[]
        for r in t['needs']:
            fulltask = workflowspec['stages'][tasknametoid[r]]
            _l.append(fulltask)
            _l=_l+getallrequirements(fulltask)
        return _l

    full_requirements_list = [ getallrequirements(t) for t in full_target_list ]

    # make flat and fetch names only
    full_requirements_name_list = list(set([ item['name'] for sublist in full_requirements_list for item in sublist ]))

    # inner "lambda" helper answering if a task "name" is needed by given targets
    def needed_by_targets(name):
        if full_target_name_list.count(name)!=0:
            return True
        if full_requirements_name_list.count(name)!=0:
            return True
        return False

    # we finaly copy everything matching the targets as well
    # as all their requirements
    transformedworkflowspec['stages']=[ l for l in workflowspec['stages'] if needed_by_targets(l['name']) ]
    return transformedworkflowspec, full_target_name_list


# builds topological orderings (for each timeframe)
def build_dag_properties(workflowspec):
    globaltaskuniverse = [ (l, i) for i, l in enumerate(workflowspec['stages'], 1) ]
    timeframeset = set( l['timeframe'] for l in workflowspec['stages'] )

    edges, nodes = build_graph(globaltaskuniverse, workflowspec)
    tup = analyseGraph(edges, nodes.copy())
    #
    global_next_tasks = tup[1]


    dependency_cache = {}
    # weight influences scheduling order can be anything user defined ... for the moment we just prefer to stay within a timeframe
    # then take the number of tasks that depend on a task as further weight
    # TODO: bring in resource estimates from runtime, CPU, MEM
    # TODO: make this a policy of the runner to study different strategies
    def getweight(tid):
        return (globaltaskuniverse[tid][0]['timeframe'], len(find_all_dependent_tasks(global_next_tasks, tid, dependency_cache)))

    task_weights = [ getweight(tid) for tid in range(len(globaltaskuniverse)) ]

    for tid in range(len(globaltaskuniverse)):
        actionlogger.info("Score for " + str(globaltaskuniverse[tid][0]['name']) + " is " + str(task_weights[tid]))

    # print (global_next_tasks)
    return { 'nexttasks' : global_next_tasks, 'weights' : task_weights, 'topological_ordering' : tup[0] }


# update the resource estimates of a workflow based on resources given via JSON
def update_resource_estimates(workflow, resource_json):
    # the resource_dict here is generated by tool o2dpg_sim_metrics.py json-stat
    resource_dict = load_json(resource_json)
    stages = workflow["stages"]

    for task in stages:
        if task["timeframe"] >= 1:
            name = "_".join(task["name"].split("_")[:-1])
        else:
            name = task["name"]

        if name not in resource_dict:
            continue

        new_resources = resource_dict[name]

        # memory
        newmem = new_resources.get("pss", {}).get("max", None)
        if newmem is not None:
            oldmem = task["resources"]["mem"]
            actionlogger.info("Updating mem estimate for " + task["name"] + " from " + str(oldmem) + " to " + str(newmem))
            task["resources"]["mem"] = newmem

        # cpu
        newcpu = new_resources.get("cpu", {}).get("mean", None)
        if newcpu is not None:
            oldcpu = task["resources"]["cpu"]
            rel_cpu = task["resources"]["relative_cpu"]
            # TODO: No longer sure about this since we inject numbers from actually measured workloads
            if rel_cpu is not None:
               # respect the relative CPU settings
               # By default, the CPU value in the workflow is already scaled if relative_cpu is given.
               # The new estimate on the other hand is not yet scaled so it needs to be done here.
               newcpu *= rel_cpu
            actionlogger.info("Updating cpu estimate for " + task["name"] + " from " + str(oldcpu) + " to " + str(newcpu))
            task["resources"]["cpu"] = newcpu

# a function to read a software environment determined by alienv into
# a python dictionary
def get_alienv_software_environment(packagestring):
    """
    packagestring is something like O2::v202298081-1,O2Physics::xxx representing packages
    published on CVMFS ... or ... a file containing directly the software environment to apply
    """

    # the trivial cases do nothing
    if packagestring == None or packagestring == "" or packagestring == "None":
        return {}

    def load_env_file(env_file):
        """Transform an environment file generated with 'export > env.txt' into a python dictionary."""
        env_vars = {}
        with open(env_file, "r") as f:
          for line in f:
            line = line.strip()

            # Ignore empty lines or comments
            if not line or line.startswith("#"):
                continue

            # Remove 'declare -x ' if present
            if line.startswith("declare -x "):
                line = line.replace("declare -x ", "", 1)

            # Handle case: "FOO" without "=" (assign empty string)
            if "=" not in line:
                key, value = line.strip(), ""
            else:
                key, value = line.split("=", 1)
                value = value.strip('"')  # Remove surrounding quotes if present

            env_vars[key.strip()] = value
        return env_vars

    # see if this is a file
    if os.path.exists(packagestring) and os.path.isfile(packagestring):
       actionlogger.info("Taking software environment from file " + packagestring)
       return load_env_file(packagestring)

    # alienv printenv packagestring --> dictionary
    # for the moment this works with CVMFS only
    cmd="/cvmfs/alice.cern.ch/bin/alienv printenv " + packagestring
    proc = subprocess.Popen([cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

    envstring, err = proc.communicate()
    # see if the printenv command was successful
    if len(err.decode()) > 0:
       print (err.decode())
       raise Exception

    # the software environment is now in the evnstring
    # split it on semicolon
    envstring=envstring.decode()
    tokens=envstring.split(";")
    # build envmap
    envmap = {}
    for t in tokens:
      # check if assignment
      if t.count("=") > 0:
         assignment = t.rstrip().split("=")
         envmap[assignment[0]] = assignment[1]
      elif t.count("export") > 0:
         # the case when we export or a simple variable
         # need to consider the case when this has not been previously assigned
         variable = t.split()[1]
         if not variable in envmap:
            envmap[variable]=""

    return envmap

#
# functions for execution; encapsulated in a WorkflowExecutor class
#

class Semaphore:
    """
    Object that can be used as semaphore
    """
    def __init__(self):
        self.locked = False
    def lock(self):
        self.locked = True
    def unlock(self):
        self.locked = False


class ResourceBoundaries:
    """
    Container holding global resource properties
    """
    def __init__(self, cpu_limit, mem_limit, dynamic_resources=False, optimistic_resources=False):
        self.cpu_limit = cpu_limit
        self.mem_limit = mem_limit
        self.dynamic_resources = dynamic_resources
        # if this is set, tasks that would normally go beyond the resource limits will tried to be run in any case
        self.optimistic_resources = optimistic_resources


class TaskResources:
    """
    Container holding resources of a single task
    """
    def __init__(self, tid, name, cpu, cpu_relative, mem, resource_boundaries):
        # the task ID belonging to these resources
        self.tid = tid
        self.name = name
        # original CPUs/MEM assigned (persistent)
        self.cpu_assigned_original = cpu
        self.mem_assigned_original = mem
        # relative CPU, to be multiplied with sampled CPU; set by the user, e.g. to allow to backfill tasks
        # only takes effect when sampling resources; persistent
        self.cpu_relative = cpu_relative if cpu_relative else 1
        # CPUs/MEM assigned (transient)
        self.cpu_assigned = cpu
        self.mem_assigned = mem
        # global resource settings
        self.resource_boundaries = resource_boundaries
        # sampled resources of this
        self.cpu_sampled = None
        self.mem_sampled = None
        # Set these after a task has finished to compute new estimates for related tasks
        self.walltime = None
        self.cpu_taken = None
        self.mem_taken = None
        # collected during monitoring
        self.time_collect = []
        self.cpu_collect = []
        self.mem_collect = []
        # linked to other resources of task that are of the same type as this one
        self.related_tasks = None
        # can assign a semaphore
        self.semaphore = None
        # the task's nice value
        self.nice_value = None
        # whether or not the task's resources are currently booked
        self.booked = False

    @property
    def is_done(self):
        return self.time_collect and not self.booked

    def is_within_limits(self):
        """
        Check if assigned resources respect limits
        """
        cpu_within_limits = True
        mem_within_limits = True
        if self.cpu_assigned > self.resource_boundaries.cpu_limit:
            cpu_within_limits = False
            actionlogger.warning("CPU of task %s exceeds limits %d > %d", self.name, self.cpu_assigned, self.resource_boundaries.cpu_limit)
        if self.cpu_assigned > self.resource_boundaries.mem_limit:
            mem_within_limits = False
            actionlogger.warning("MEM of task %s exceeds limits %d > %d", self.name, self.cpu_assigned, self.resource_boundaries.cpu_limit)
        return cpu_within_limits and mem_within_limits

    def limit_resources(self, cpu_limit=None, mem_limit=None):
        """
        Limit resources of this specific task
        """
        if not cpu_limit:
            cpu_limit = self.resource_boundaries.cpu_limit
        if not mem_limit:
            mem_limit = self.resource_boundaries.mem_limit
        self.cpu_assigned = min(self.cpu_assigned, cpu_limit)
        self.mem_assigned = min(self.mem_assigned, mem_limit)

    def add(self, time_passed, cpu, mem):
        """
        Brief interface to add resources that were measured after time_passed
        """
        self.time_collect.append(time_passed)
        self.cpu_collect.append(cpu)
        self.mem_collect.append(mem)

    def sample_resources(self):
        """
        If this task is done, sample CPU and MEM for all related tasks that have not started yet
        """
        if not self.is_done:
            return

        if len(self.time_collect) < 3:
            # Consider at least 3 points to sample from
            self.cpu_sampled = self.cpu_assigned
            self.mem_sampled = self.mem_assigned
            actionlogger.debug("Task %s has not enough points (< 3) to sample resources, setting to previosuly assigned values.", self.name)
        else:
            # take the time deltas and leave out the very first CPU measurent which is not meaningful,
            # at least when it domes from psutil.Proc.cpu_percent(interval=None)
            time_deltas = [self.time_collect[i+1] - self.time_collect[i] for i in range(len(self.time_collect) - 1)]
            cpu = sum([cpu * time_delta for cpu, time_delta in zip(self.cpu_collect[1:], time_deltas) if cpu >= 0])
            self.cpu_sampled = cpu / sum(time_deltas)
            self.mem_sampled = max(self.mem_collect)

        mem_sampled = 0
        cpu_sampled = []
        for res in self.related_tasks:
            if res.is_done:
                mem_sampled = max(mem_sampled, res.mem_sampled)
                cpu_sampled.append(res.cpu_sampled)
        cpu_sampled = sum(cpu_sampled) / len(cpu_sampled)

        # This task ran already with the assigned resources, so let's set it to the limit
        if cpu_sampled > self.resource_boundaries.cpu_limit:
            actionlogger.warning("Sampled CPU (%.2f) exceeds assigned CPU limit (%.2f)", cpu_sampled, self.resource_boundaries.cpu_limit)
        elif cpu_sampled < 0:
            actionlogger.debug("Sampled CPU for %s is %.2f < 0, setting to previously assigned value %.2f", self.name, cpu_sampled, self.cpu_assigned)
            cpu_sampled = self.cpu_assigned

        if mem_sampled > self.resource_boundaries.mem_limit:
            actionlogger.warning("Sampled MEM (%.2f) exceeds assigned MEM limit (%.2f)", mem_sampled, self.resource_boundaries.mem_limit)
        elif mem_sampled <= 0:
            actionlogger.debug("Sampled memory for %s is %.2f <= 0, setting to previously assigned value %.2f", self.name, mem_sampled, self.mem_assigned)
            mem_sampled = self.mem_assigned

        for res in self.related_tasks:
            if res.is_done or res.booked:
                continue
            res.cpu_assigned = cpu_sampled * res.cpu_relative
            res.mem_assigned = mem_sampled
            # This task has been run before, stay optimistic and limit the resources in case the sampled ones exceed limits
            res.limit_resources()


class ResourceManager:
    """
    Central class to manage resources

    - CPU limits
    - MEM limits
    - Semaphores

    Entrypoint to set and to query for resources to be updated.

    Can be asked whether a certain task can be run under current resource usage.
    Book and unbook resources.
    """
    def __init__(self, cpu_limit, mem_limit, procs_parallel_max=100, dynamic_resources=False, optimistic_resources=False):
        """
        Initialise members with defaults
        """
        # hold TaskResources of all tasks
        self.resources = []

        # helper dictionaries holding common objects which will be distributed to single TaskResources objects
        # to avoid further lookup and at the same time to share the same common objects
        self.resources_related_tasks_dict = {}
        self.semaphore_dict = {}

        # one common object that holds global resource settings such as CPU and MEM limits
        self.resource_boundaries = ResourceBoundaries(cpu_limit, mem_limit, dynamic_resources, optimistic_resources)

        # register resources that are booked under default nice value
        self.cpu_booked = 0
        self.mem_booked = 0
        # number of tasks currently booked
        self.n_procs = 0

        # register resources that are booked under high nice value
        self.cpu_booked_backfill = 0
        self.mem_booked_backfill = 0
        # number of tasks currently booked under high nice value
        self.n_procs_backfill = 0

        # the maximum number of tasks that run at the same time
        self.procs_parallel_max = procs_parallel_max

        # get the default nice value of this python script
        self.nice_default = os.nice(0)
        # add 19 to get nice value of low-priority tasks
        self.nice_backfill = self.nice_default + 19

    def add_task_resources(self, name, related_tasks_name, cpu, cpu_relative, mem, semaphore_string=None):
        """
        Construct and Add a new TaskResources object
        """
        resources = TaskResources(len(self.resources), name, cpu, cpu_relative, mem, self.resource_boundaries)
        if not resources.is_within_limits() and not self.resource_boundaries.optimistic_resources:
            # exit if we don't dare to try
            print(f"Resources of task {name} are exceeding the boundaries.\nCPU: {cpu} (estimate) vs. {self.resource_boundaries.cpu_limit} (boundary)\nMEM: {mem} (estimated) vs. {self.resource_boundaries.mem_limit} (boundary).")
            print("Pass --optimistic-resources to the runner to attempt the run anyway.")
            exit(1)
        # if we get here, either all is good or the user decided to be optimistic and we limit the resources, by default to the given CPU and mem limits.
        resources.limit_resources()

        self.resources.append(resources)
        # do the following to have the same Semaphore object for all corresponding TaskResources so that we do not need a lookup
        if semaphore_string:
            if semaphore_string not in self.semaphore_dict:
                self.semaphore_dict[semaphore_string] = Semaphore()
            resources.semaphore = self.semaphore_dict[semaphore_string]

        # do the following to give each TaskResources a list of the related tasks so we do not need an additional lookup
        if related_tasks_name:
            if related_tasks_name not in self.resources_related_tasks_dict:
                # assigned list is [valid top be used, list of CPU, list of MEM, list of walltimes of each related task, list of processes that ran in parallel on average, list of taken CPUs, list of assigned CPUs, list of tasks finished in the meantime]
                self.resources_related_tasks_dict[related_tasks_name] = []
            self.resources_related_tasks_dict[related_tasks_name].append(resources)
            resources.related_tasks = self.resources_related_tasks_dict[related_tasks_name]

    def add_monitored_resources(self, tid, time_delta_since_start, cpu, mem):
        self.resources[tid].add(time_delta_since_start, cpu, mem)

    def book(self, tid, nice_value):
        """
        Book the resources of this task with given nice value

        The final nice value is determined by the final submission and could be different.
        This can happen if the nice value should have been changed while that is not allowed by the system.
        """
        res = self.resources[tid]
        # take the nice value that was previously assigned when resources where checked last time
        previous_nice_value = res.nice_value

        if previous_nice_value is None:
            # this has not been checked ever if it was ok to be submitted
            actionlogger.warning("Task ID %d has never been checked for resources. Treating as backfill", tid)
            nice_value = self.nice_backfill
        elif res.nice_value != nice_value:
            actionlogger.warning("Task ID %d has was last time checked for a different nice value (%d) but is now submitted with (%d).", tid, res.nice_value, nice_value)

        res.nice_value = nice_value
        res.booked = True
        if res.semaphore is not None:
            res.semaphore.lock()
        if nice_value != self.nice_default:
            self.n_procs_backfill += 1
            self.cpu_booked_backfill += res.cpu_assigned
            self.mem_booked_backfill += res.mem_assigned
            return
        self.n_procs += 1
        self.cpu_booked += res.cpu_assigned
        self.mem_booked += res.mem_assigned

    def unbook(self, tid):
        """
        Unbook the reources of this task
        """
        res = self.resources[tid]
        res.booked = False
        if self.resource_boundaries.dynamic_resources:
            res.sample_resources()
        if res.semaphore is not None:
            res.semaphore.unlock()
        if res.nice_value != self.nice_default:
            self.cpu_booked_backfill -= res.cpu_assigned
            self.mem_booked_backfill -= res.mem_assigned
            self.n_procs_backfill -= 1
            if self.n_procs_backfill <= 0:
                self.cpu_booked_backfill = 0
                self.mem_booked_backfill = 0
            return
        self.n_procs -= 1
        self.cpu_booked -= res.cpu_assigned
        self.mem_booked -= res.mem_assigned
        if self.n_procs <= 0:
            self.cpu_booked = 0
            self.mem_booked = 0

    def ok_to_submit(self, tids):
        """
        This generator yields the tid and nice value tuple from the list of task ids that should be checked
        """
        tids_copy = tids.copy()

        def ok_to_submit_default(res):
            """
            Return default nice value if conditions are met, None otherwise
            """
            # analyse CPU
            okcpu = (self.cpu_booked + res.cpu_assigned <= self.resource_boundaries.cpu_limit)
            # analyse MEM
            okmem = (self.mem_booked + res.mem_assigned <= self.resource_boundaries.mem_limit)
            actionlogger.debug ('Condition check --normal-- for  ' + str(res.tid) + ':' + res.name + ' CPU ' + str(okcpu) + ' MEM ' + str(okmem))
            return self.nice_default if (okcpu and okmem) else None

        def ok_to_submit_backfill(res, backfill_cpu_factor=1.5, backfill_mem_factor=1.5):
            """
            Return backfill nice value if conditions are met, None otherwise
            """
            if self.n_procs_backfill >= args.n_backfill:
                return None

            if res.cpu_assigned > 0.9 * self.resource_boundaries.cpu_limit or res.mem_assigned / self.resource_boundaries.cpu_limit >= 1900:
                return None

            # analyse CPU
            okcpu = (self.cpu_booked_backfill + res.cpu_assigned <= self.resource_boundaries.cpu_limit)
            okcpu = okcpu and (self.cpu_booked + self.cpu_booked_backfill + res.cpu_assigned <= backfill_cpu_factor * self.resource_boundaries.cpu_limit)
            # analyse MEM
            okmem = (self.mem_booked + self.mem_booked_backfill + res.mem_assigned <= backfill_mem_factor * self.resource_boundaries.mem_limit)
            actionlogger.debug ('Condition check --backfill-- for  ' + str(res.tid) + ':' + res.name + ' CPU ' + str(okcpu) + ' MEM ' + str(okmem))

            return self.nice_backfill if (okcpu and okmem) else None

        if self.n_procs + self.n_procs_backfill >= self.procs_parallel_max:
            # in this case, nothing can be done
            return

        for ok_to_submit_impl, should_break in ((ok_to_submit_default, True), (ok_to_submit_backfill, False)):
            tid_index = 0
            while tid_index < len(tids_copy):

                tid = tids_copy[tid_index]
                res = self.resources[tid]

                actionlogger.info("Setup resources for task %s, cpu: %f, mem: %f", res.name, res.cpu_assigned, res.mem_assigned)
                tid_index += 1

                if (res.semaphore is not None and res.semaphore.locked) or res.booked:
                    continue

                nice_value = ok_to_submit_impl(res)
                if nice_value is not None:
                    # if we get a non-None nice value, it means that this task is good to go
                    res.nice_value = nice_value
                    # yield the tid and its assigned nice value
                    yield tid, nice_value

                elif should_break:
                    # break here if resources of the next task do not fit
                    break


def filegraph_expand_timeframes(data: dict, timeframes: set, target_namelist) -> dict:
    """
    A utility function for the fileaccess logic. Takes a template and duplicates
    for the multi-timeframe structure.
    """
    tf_entries = [
        entry for entry in data.get("file_report", [])
        if re.match(r"^\./tf\d+/", entry["file"])
    ]

    result = {}
    for i in timeframes:
        if i == -1:
            continue
        # Deepcopy to avoid modifying original
        new_entries = deepcopy(tf_entries)
        for entry in new_entries:
            # Fix filepath
            entry["file"] = re.sub(r"^\./tf\d+/", f"./tf{i}/", entry["file"])
            # Fix written_by and read_by (preserve prefix, change numeric suffix)
            entry["written_by"] = [
                re.sub(r"_\d+$", f"_{i}", w) for w in entry["written_by"]
            ]
            # for now we mark some files as keep if they are written
            # by a target in the runner targetlist. TODO: Add other mechanisms
            # to ask for file keeping (such as via regex or the like)
            for e in entry["written_by"]:
                if e in target_namelist:
                    entry["keep"] = True
            entry["read_by"] = [
                re.sub(r"_\d+$", f"_{i}", r) for r in entry["read_by"]
            ]
        result[f"timeframe-{i}"] = new_entries

    return result



class WorkflowExecutor:
    # Constructor
    def __init__(self, workflowfile, args, jmax=100):
      self.args=args
      self.is_productionmode = args.production_mode == True # os.getenv("ALIEN_PROC_ID") != None
      self.workflowfile = workflowfile
      self.workflowspec = load_json(workflowfile)
      self.globalinit = self.extract_global_environment(self.workflowspec) # initialize global environment settings
      for e in self.globalinit['env']:
        if os.environ.get(e, None) == None:
           value = self.globalinit['env'][e]
           actionlogger.info("Applying global environment from init section " + str(e) + " : " + str(value))
           os.environ[e] = str(value)

      # only keep those tasks that are necessary to be executed based on user's filters
      self.full_target_namelist = []
      self.workflowspec, self.full_target_namelist = filter_workflow(self.workflowspec, args.target_tasks, args.target_labels)

      if not self.workflowspec['stages']:
          if args.target_tasks:
              print ('Apparently some of the chosen target tasks are not in the workflow')
              exit (0)
          print ('Workflow is empty. Nothing to do')
          exit (0)

      # construct the DAG, compute task weights
      workflow = build_dag_properties(self.workflowspec)
      if args.visualize_workflow:
          draw_workflow(self.workflowspec)
      self.possiblenexttask = workflow['nexttasks']
      self.taskweights = workflow['weights']
      self.topological_orderings = workflow['topological_ordering']
      self.taskuniverse = [ l['name'] for l in self.workflowspec['stages'] ]
      # construct task ID <-> task name lookup
      self.idtotask = [ 0 for _ in self.taskuniverse ]
      self.tasktoid = {}
      self.idtotf = [ l['timeframe'] for l in self.workflowspec['stages'] ]
      for i, name in enumerate(self.taskuniverse):
          self.tasktoid[name]=i
          self.idtotask[i]=name

      if args.update_resources:
          update_resource_estimates(self.workflowspec, args.update_resources)

      # construct the object that is in charge of resource management...
      self.resource_manager = ResourceManager(args.cpu_limit, args.mem_limit, args.maxjobs, args.dynamic_resources, args.optimistic_resources)
      for task in self.workflowspec['stages']:
          # ...and add all initial resource estimates
          global_task_name = self.get_global_task_name(task["name"])
          try:
              cpu_relative = float(task["resources"]["relative_cpu"])
          except TypeError:
              cpu_relative = 1
          self.resource_manager.add_task_resources(task["name"], global_task_name, float(task["resources"]["cpu"]), cpu_relative, float(task["resources"]["mem"]), task.get("semaphore"))

      self.procstatus = { tid:'ToDo' for tid in range(len(self.workflowspec['stages'])) }
      self.taskneeds= { t:set(self.getallrequirements(t)) for t in self.taskuniverse }
      self.stoponfailure = not args.keep_going
      print ("Stop on failure ",self.stoponfailure)

      self.scheduling_iteration = 0 # count how often it was tried to schedule new tasks
      self.process_list = []  # list of currently scheduled tasks with normal priority
      self.backfill_process_list = [] # list of curently scheduled tasks with low backfill priority (not sure this is needed)
      self.pid_to_psutilsproc = {}  # cache of putilsproc for resource monitoring
      self.pid_to_files = {} # we can auto-detect what files are produced by which task (at least to some extent)
      self.pid_to_connections = {} # we can auto-detect what connections are opened by which task (at least to some extent)
      signal.signal(signal.SIGINT, self.SIGHandler)
      signal.siginterrupt(signal.SIGINT, False)
      self.internalmonitorcounter = 0 # internal use
      self.internalmonitorid = 0 # internal use
      self.tids_marked_toretry = [] # sometimes we might want to retry a failed task (simply because it was "unlucky") and we put them here
      self.retry_counter = [ 0 for tid in range(len(self.taskuniverse)) ] # we keep track of many times retried already
      self.task_retries = [ self.workflowspec['stages'][tid].get('retry_count',0) for tid in range(len(self.taskuniverse)) ] # the per task specific "retry" number -> needs to be parsed from the JSON

      self.alternative_envs = {} # mapping of taskid to alternative software envs (to be applied on a per-task level)
      # init alternative software environments
      self.init_alternative_software_environments()

      # initialize container to keep track of file-task relationsships
      self.file_removal_candidates = {}
      self.do_early_file_removal = False
      self.timeframeset = set([ task["timeframe"] for task in self.workflowspec['stages'] ])
      if args.remove_files_early != "":
          with open(args.remove_files_early) as f:
            filegraph_data = json.load(f)
            self.do_early_file_removal = True
            self.file_removal_candidates = filegraph_expand_timeframes(filegraph_data, self.timeframeset, self.full_target_namelist)

    def apply_global_env(self, environ_dict):
      for e in self.globalinit['env']:
        if environ_dict.get(e, None) == None:
           value = self.globalinit['env'][e]
           actionlogger.info("Applying global environment from init section " + str(e) + " : " + str(value))
           environ_dict[e] = str(value)

    def perform_early_file_removal(self, taskids):
        """
        This function checks which files can be deleted upon completion of task
        and optionally does so.
        """

        def remove_if_exists(filepath: str) -> None:
          """
          Check if a file exists, and remove it if found.
          """
          if os.path.exists(filepath):
            fsize = os.path.getsize(filepath)
            os.remove(filepath)
            actionlogger.info(f"Removing {filepath} since no longer needed. Freeing {fsize/1024./1024.} MB.")
            return True

          return False

        def remove_for_task_id(taskname, file_dict, timeframe_id, listofalltimeframes):
            marked_for_removal = []

            timeframestoscan = [ timeframe_id ]
            if timeframe_id == -1:
               timeframestoscan = [ i for i in listofalltimeframes if i != -1 ]

            # TODO: Note that this traversal of files is not certainly not optimal
            # We should (and will) keep an mapping of tasks->potential files and just
            # scan these. This is already provided by the FileIOGraph analysis tool.
            for tid in timeframestoscan:
                for i,file_entry in enumerate(file_dict[f"timeframe-{tid}"]):
                    filename = file_entry['file']
                    read_by = file_entry['read_by']
                    written_by = file_entry['written_by']
                    if taskname in read_by:
                        file_entry['read_by'].remove(taskname)
                    if taskname in written_by:
                        file_entry['written_by'].remove(taskname)

                    # TODO: in principle the written_by criterion might not be needed
                    if len(file_entry['read_by']) == 0 and len(file_entry['written_by']) == 0 and file_entry.get('keep', False) == False:
                        # the filename mentioned here is no longer needed and we can remove it
                        # make sure it is there and then delete it
                        if remove_if_exists(filename):
                           # also take out the file entry from the dict altogether
                           marked_for_removal.append(file_entry)

            #for k in marked_for_removal:
            #    file_dict[f"timeframe-{tid}"].remove(k)

        for tid in taskids:
            taskname = self.idtotask[tid]
            timeframe_id = self.idtotf[tid]
            remove_for_task_id(taskname, self.file_removal_candidates, timeframe_id, self.timeframeset)


    def SIGHandler(self, signum, frame):
       """
       basically forcing shut down of all child processes
       """
       actionlogger.info("Signal " + str(signum) + " caught")
       try:
           procs = psutil.Process().children(recursive=True)
       except (psutil.NoSuchProcess):
           pass
       except (psutil.AccessDenied, PermissionError):
           procs = getChildProcs(os.getpid())

       for p in procs:
           actionlogger.info("Terminating " + str(p))
           try:
             p.terminate()
           except (psutil.NoSuchProcess, psutil.AccessDenied):
             pass

       _, alive = psutil.wait_procs(procs, timeout=3)
       for p in alive:
           try:
             actionlogger.info("Killing " + str(p))
             p.kill()
           except (psutil.NoSuchProcess, psutil.AccessDenied):
             pass

       exit (1)

    def extract_global_environment(self, workflowspec):
        """
        Checks if the workflow contains a dedicated init task
        defining a global environment. Extract information and remove from workflowspec.
        """
        init_index = 0 # this has to be the first task in the workflow
        globalenv = {}
        initcmd = None
        if workflowspec['stages'][init_index]['name'] == '__global_init_task__':
          env = workflowspec['stages'][init_index].get('env', None)
          if env != None:
            globalenv = { e : env[e] for e in env }
          cmd = workflowspec['stages'][init_index].get('cmd', None)
          if cmd != 'NO-COMMAND':
            initcmd = cmd

          del workflowspec['stages'][init_index]

        return {"env" : globalenv, "cmd" : initcmd }

    def execute_globalinit_cmd(self, cmd):
        actionlogger.info("Executing global setup cmd " + str(cmd))
        # perform the global init command (think of cleanup/setup things to be done in any case)
        p = subprocess.Popen(['/bin/bash','-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()

        # Check if the command was successful (return code 0)
        if p.returncode == 0:
          actionlogger.info(stdout.decode())
        else:
          # this should be an error
          actionlogger.error("Error executing global init function")
          return False
        return True

    def get_global_task_name(self, name):
        """
        Get the global task name

        Tasks are related if only the suffix _<i> is different
        """
        tokens = name.split("_")
        try:
            int(tokens[-1])
            return "_".join(tokens[:-1])
        except ValueError:
            pass
        return name

    def getallrequirements(self, task_name):
        """
        get all requirement of a task by its name
        """
        l=[]
        for required_task_name in self.workflowspec['stages'][self.tasktoid[task_name]]['needs']:
            l.append(required_task_name)
            l=l+self.getallrequirements(required_task_name)
        return l

    def get_logfile(self, tid):
        """
        O2 taskwrapper logs task stdout and stderr to logfile <task>.log
        Get its exact path based on task ID
        """
        # determines the logfile name for this task
        name = self.workflowspec['stages'][tid]['name']
        workdir = self.workflowspec['stages'][tid]['cwd']
        return os.path.join(workdir, f"{name}.log")

    def get_done_filename(self, tid):
        """
        O2 taskwrapper leaves <task>.log_done after a task has successfully finished
        Get its exact path based on task ID
        """
        return f"{self.get_logfile(tid)}_done"

    def get_resources_filename(self, tid):
        """
        O2 taskwrapper leaves <task>.log_time after a task is done
        Get its exact path based on task ID
        """
        return f"{self.get_logfile(tid)}_time"

    # removes the done flag from tasks that need to be run again
    def remove_done_flag(self, listoftaskids):
       """
       Remove <task>.log_done files to given task IDs
       """
       for tid in listoftaskids:
          done_filename = self.get_done_filename(tid)
          name=self.workflowspec['stages'][tid]['name']
          if args.dry_run:
              print ("Would mark task " + name + " as to be done again")
          else:
              print ("Marking task " + name + " as to be done again")
              if os.path.exists(done_filename) and os.path.isfile(done_filename):
                  os.remove(done_filename)

    # submits a task as subprocess and records Popen instance
    def submit(self, tid, nice):
      """
      Submit a task

      1. if needed, construct working directory if it does not yet exist
      2. update lookup structures flagging the task as being run
      3. set specific environment if requested for task
      4. construct psutil.Process from command line
      4.1 adjust the niceness of that process if requested
      5. return psutil.Process object
      """
      actionlogger.debug("Submitting task " + str(self.idtotask[tid]) + " with nice value " + str(nice))
      c = self.workflowspec['stages'][tid]['cmd']
      workdir = self.workflowspec['stages'][tid]['cwd']
      if workdir:
          if os.path.exists(workdir) and not os.path.isdir(workdir):
                  actionlogger.error('Cannot create working dir ... some other resource exists already')
                  return None

          if not os.path.isdir(workdir):
                  os.makedirs(workdir)

      self.procstatus[tid]='Running'
      if args.dry_run:
          drycommand="echo \' " + str(self.scheduling_iteration) + " : would do " + str(self.workflowspec['stages'][tid]['name']) + "\'"
          return subprocess.Popen(['/bin/bash','-c',drycommand], cwd=workdir)

      taskenv = os.environ.copy()
      # apply specific (non-default) software version, if any
      # (this was setup earlier)
      alternative_env = self.alternative_envs.get(tid, None)
      if alternative_env != None and len(alternative_env) > 0:
          actionlogger.info('Applying alternative software environment to task ' + self.idtotask[tid])
          if alternative_env.get('TERM') != None:
              # the environment is a complete environment
              taskenv = {}
              taskenv = alternative_env
          else:
            for entry in alternative_env:
              # overwrite what is present in default
              taskenv[entry] = alternative_env[entry]

      # add task specific environment
      if self.workflowspec['stages'][tid].get('env')!=None:
          taskenv.update(self.workflowspec['stages'][tid]['env'])

      # add global workflow environment
      self.apply_global_env(taskenv)

      if os.environ.get('PIPELINE_RUNNER_DUMP_TASKENVS') != None:
          envfilename = "taskenv_" + str(tid) + ".log"
          with open(envfilename, "w") as file:
            json.dump(taskenv, file, indent=2)

      p = psutil.Popen(['/bin/bash','-c',c], cwd=workdir, env=taskenv)
      try:
          p.nice(nice)
      except (psutil.NoSuchProcess, psutil.AccessDenied):
          actionlogger.error('Couldn\'t set nice value of ' + str(p.pid) + ' to ' + str(nice))

      return p

    def ok_to_skip(self, tid):
        """
        Decide if task can be skipped based on existence of <task>.log_done
        """
        done_filename = self.get_done_filename(tid)
        if os.path.exists(done_filename) and os.path.isfile(done_filename):
          return True
        return False

    def try_job_from_candidates(self, taskcandidates, finished):
       """
       Try to schedule next tasks

       Args:
         taskcandidates: list
           list of possible tasks that can be submitted
         finished: list
           empty list that will be filled with IDs of tasks that were finished in the meantime
       """
       self.scheduling_iteration = self.scheduling_iteration + 1

       # remove "done / skippable" tasks immediately
       for tid in taskcandidates.copy():  # <--- the copy is important !! otherwise this loop is not doing what you think
          if self.ok_to_skip(tid):
              finished.append(tid)
              taskcandidates.remove(tid)
              actionlogger.info("Skipping task " + str(self.idtotask[tid]))

       # if tasks_skipped:
       #   return # ---> we return early in order to preserve some ordering (the next candidate tried should be daughters of skipped jobs)
       # get task ID and proposed niceness from generator
       for (tid, nice_value) in self.resource_manager.ok_to_submit(taskcandidates):
          actionlogger.debug ("trying to submit " + str(tid) + ':' + str(self.idtotask[tid]))
          if p := self.submit(tid, nice_value):
            # explicitly set the nice value here from the process again because it might happen that submit could not change the niceness
            # so we let the ResourceManager know what the final niceness is
            self.resource_manager.book(tid, p.nice())
            self.process_list.append((tid,p))
            taskcandidates.remove(tid)
            # minimal delay
            time.sleep(0.1)

    def stop_pipeline_and_exit(self, process_list):
        # kill all remaining jobs
        for p in process_list:
           p[1].kill()

        exit(1)


    def monitor(self, process_list):
        """
        Go through all running tasks and get their current resources

        Resources are summed up for tasks and all their children

        Pass CPU, PSS, USS, niceness, current time to metriclogger

        Warn if overall PSS exceeds assigned memory limit
        """
        self.internalmonitorcounter+=1
        if self.internalmonitorcounter % 5 != 0:
            return

        self.internalmonitorid+=1

        globalCPU=0.
        globalPSS=0.
        resources_per_task = {}

        # On a global level, we are interested in total disc space used (not differential in tasks)
        # We can call system "du" as the fastest impl
        def disk_usage_du(path: str) -> int:
          """Use system du to get total size in bytes."""
          out = subprocess.check_output(['du', '-sb', path], text=True)
          return int(out.split()[0])

        disc_usage = -1
        if os.getenv("MONITOR_DISC_USAGE"):
            disc_usage = disk_usage_du(os.getcwd()) / 1024. / 1024 # in MB

        for tid, proc in process_list:

            # proc is Popen object
            pid=proc.pid
            if self.pid_to_files.get(pid)==None:
                self.pid_to_files[pid]=set()
                self.pid_to_connections[pid]=set()
            try:
                psutilProcs = [ proc ]
                # use psutil for CPU measurement
                psutilProcs = psutilProcs + proc.children(recursive=True)
            except (psutil.NoSuchProcess):
                continue

            except (psutil.AccessDenied, PermissionError):
                psutilProcs = psutilProcs + getChildProcs(pid)

            # accumulate total metrics (CPU, memory)
            totalCPU = 0.
            totalPSS = 0.
            totalSWAP = 0.
            totalUSS = 0.
            for p in psutilProcs:
                """
                try:
                    for f in p.open_files():
                        self.pid_to_files[pid].add(str(f.path)+'_'+str(f.mode))
                    for f in p.connections(kind="all"):
                        remote=f.raddr
                        if remote==None:
                            remote='none'
                        self.pid_to_connections[pid].add(str(f.type)+"_"+str(f.laddr)+"_"+str(remote))
                except Exception:
                    pass
                """
                thispss=0
                thisuss=0
                # MEMORY part
                try:
                    fullmem=p.memory_full_info()
                    thispss=getattr(fullmem,'pss',0) #<-- pss not available on MacOS
                    totalPSS=totalPSS + thispss
                    totalSWAP=totalSWAP + fullmem.swap
                    thisuss=fullmem.uss
                    totalUSS=totalUSS + thisuss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                # CPU part
                # fetch existing proc or insert
                cachedproc = self.pid_to_psutilsproc.get(p.pid)
                if cachedproc!=None:
                    try:
                        thiscpu = cachedproc.cpu_percent(interval=None)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        thiscpu = 0.
                    totalCPU = totalCPU + thiscpu
                    # thisresource = {'iter':self.internalmonitorid, 'pid': p.pid, 'cpu':thiscpu, 'uss':thisuss/1024./1024., 'pss':thispss/1024./1024.}
                    # metriclogger.info(thisresource)
                else:
                    self.pid_to_psutilsproc[p.pid] = p
                    try:
                        self.pid_to_psutilsproc[p.pid].cpu_percent()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

            time_delta = int((time.perf_counter() - self.start_time) * 1000)
            totalUSS = totalUSS / 1024 / 1024
            totalPSS = totalPSS / 1024 / 1024
            nice_value = proc.nice()
            resources_per_task[tid]={'iter':self.internalmonitorid,
                                     'name':self.idtotask[tid],
                                     'cpu':totalCPU,
                                     'uss':totalUSS,
                                     'pss':totalPSS,
                                     'nice':nice_value,
                                     'swap':totalSWAP,
                                     'label':self.workflowspec['stages'][tid]['labels'],
                                     'disc': disc_usage}
            self.resource_manager.add_monitored_resources(tid, time_delta, totalCPU / 100, totalPSS)
            if nice_value == self.resource_manager.nice_default:
                globalCPU += totalCPU
                globalPSS += totalPSS

            metriclogger.info(resources_per_task[tid])
            send_webhook(self.args.webhook, resources_per_task)

        if globalPSS > self.resource_manager.resource_boundaries.mem_limit:
            metriclogger.info('*** MEMORY LIMIT PASSED !! ***')
            # --> We could use this for corrective actions such as killing jobs currently back-filling
            # (or better hibernating)

    def waitforany(self, process_list, finished, failingtasks):
       """
       Loop through all submitted tasks and check if they are finished

       1. If process is still running, do nothing
       2. If process is finished, get its return value, update finished and failingtasks lists
       2.1 unbook resources
       2.2 add taken resources and pass the to ResourceManager
       """
       failuredetected = False
       failingpids = []
       if len(process_list)==0:
           return False

       for p in list(process_list):
          pid = p[1].pid
          tid = p[0]  # the task id of this process
          returncode = 0
          if not self.args.dry_run:
              returncode = p[1].poll()
          if returncode!=None:
            actionlogger.info ('Task ' + str(pid) + ' ' + str(tid)+':'+str(self.idtotask[tid]) + ' finished with status ' + str(returncode))
            # account for cleared resources
            self.resource_manager.unbook(tid)
            self.procstatus[tid]='Done'
            finished.append(tid)
            #self.validate_resources_running(tid)
            process_list.remove(p)
            if returncode != 0:
               print (str(self.idtotask[tid]) + ' failed ... checking retry')
               # we inspect if this is something "unlucky" which could be resolved by a simple resubmit
               if self.is_worth_retrying(tid) and ((self.retry_counter[tid] < int(args.retry_on_failure)) or (self.retry_counter[tid] < int(self.task_retries[tid]))):
                 print (str(self.idtotask[tid]) + ' to be retried')
                 actionlogger.info ('Task ' + str(self.idtotask[tid]) + ' failed but marked to be retried ')
                 self.tids_marked_toretry.append(tid)
                 self.retry_counter[tid] += 1

               else:
                 failuredetected = True
                 failingpids.append(pid)
                 failingtasks.append(tid)

       if failuredetected and self.stoponfailure:
          actionlogger.info('Stoping pipeline due to failure in stages with PID ' + str(failingpids))
          # self.analyse_files_and_connections()
          if self.args.stdout_on_failure:
             self.cat_logfiles_tostdout(failingtasks)
          self.send_checkpoint(failingtasks, self.args.checkpoint_on_failure)
          self.stop_pipeline_and_exit(process_list)

       # empty finished means we have to wait more
       return len(finished)==0

    def is_worth_retrying(self, tid):
        # This checks for some signatures in logfiles that indicate that a retry of this task
        # might have a chance.
        # Ideally, this should be made user configurable. Either the user could inject a lambda
        # or a regular expression to use. For now we just put a hard coded list
        logfile = self.get_logfile(tid)

        return True #! --> for now we just retry tasks a few times

        # 1) ZMQ_EVENT + interrupted system calls (DPL bug during shutdown)
        # Not sure if grep is faster than native Python text search ...
        # status = os.system('grep "failed setting ZMQ_EVENTS" ' + logfile + ' &> /dev/null')
        # if os.WEXITSTATUS(status) == 0:
        #   return True

        # return False


    def cat_logfiles_tostdout(self, taskids):
        # In case of errors we can cat the logfiles for this taskname
        # to stdout. Assuming convention that "taskname" translates to "taskname.log" logfile.
        for tid in taskids:
            logfile = self.get_logfile(tid)
            if os.path.exists(logfile):
                print (' ----> START OF LOGFILE ', logfile, ' -----')
                os.system('cat ' + logfile)
                print (' <---- END OF LOGFILE ', logfile, ' -----')

    def send_checkpoint(self, taskids, location):
        # Makes a tarball containing all files in the base dir
        # (timeframe independent) and the dir with corrupted timeframes
        # and copies it to a specific ALIEN location. Not a core function
        # just some tool get hold on error conditions appearing on the GRID.

        def get_tar_command(dir='./', flags='cf', findtype='f', filename='checkpoint.tar'):
            return 'find ' + str(dir) + ' -maxdepth 1 -type ' + str(findtype) + ' -print0 | xargs -0 tar ' + str(flags) + ' ' + str(filename)

        if location != None:
           print ('Making a failure checkpoint')
           # let's determine a filename from ALIEN_PROC_ID - hostname - and PID

           aliprocid=os.environ.get('ALIEN_PROC_ID')
           if aliprocid == None:
              aliprocid = 0

           fn='pipeline_checkpoint_ALIENPROC' + str(aliprocid) + '_PID' + str(os.getpid()) + '_HOST' + socket.gethostname() + '.tar'
           actionlogger.info("Checkpointing to file " + fn)
           tarcommand = get_tar_command(filename=fn)
           actionlogger.info("Taring " + tarcommand)

           # create a README file with instruction on how to use checkpoint
           readmefile=open('README_CHECKPOINT_PID' + str(os.getpid()) + '.txt','w')

           for tid in taskids:
             taskspec = self.workflowspec['stages'][tid]
             name = taskspec['name']
             readmefile.write('Checkpoint created because of failure in task ' + name + '\n')
             readmefile.write('In order to reproduce with this checkpoint, do the following steps:\n')
             readmefile.write('a) setup the appropriate O2sim environment using alienv\n')
             readmefile.write('b) run: $O2DPG_ROOT/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt ' + name + '$ --retry-on-failure 0\n')
           readmefile.close()

           # first of all the base directory
           os.system(tarcommand)

           # then we add stuff for the specific timeframes ids if any
           for tid in taskids:
             taskspec = self.workflowspec['stages'][tid]
             directory = taskspec['cwd']
             if directory != "./":
               tarcommand = get_tar_command(dir=directory, flags='rf', filename=fn)
               actionlogger.info("Tar command is " + tarcommand)
               os.system(tarcommand)
               # same for soft links
               tarcommand = get_tar_command(dir=directory, flags='rf', findtype='l', filename=fn)
               actionlogger.info("Tar command is " + tarcommand)
               os.system(tarcommand)

           # prepend file:/// to denote local file
           fn = "file://" + fn
           actionlogger.info("Local checkpoint file is " + fn)

           # location needs to be an alien path of the form alien:///foo/bar/
           copycommand='alien.py cp ' + fn + ' ' + str(location) + '@disk:1'
           actionlogger.info("Copying to alien " + copycommand)
           os.system(copycommand)

    def init_alternative_software_environments(self):
        """
        Initialises alternative software environments for specific tasks, if there
        is an annotation in the workflow specificiation.
        """

        environment_cache = {}
        # go through all the tasks once and setup environment
        for taskid in range(len(self.workflowspec['stages'])):
          packagestr = self.workflowspec['stages'][taskid].get("alternative_alienv_package")
          if packagestr == None:
             continue

          if environment_cache.get(packagestr) == None:
             environment_cache[packagestr] = get_alienv_software_environment(packagestr)

          self.alternative_envs[taskid] = environment_cache[packagestr]


    def analyse_files_and_connections(self):
        for p,s in self.pid_to_files.items():
            for f in s:
                print("F" + str(f) + " : " + str(p))
        for p,s in self.pid_to_connections.items():
            for c in s:
               print("C" + str(c) + " : " + str(p))
            #print(str(p) + " CONS " + str(c))
        try:
            # check for intersections
            for p1, s1 in self.pid_to_files.items():
                for p2, s2 in self.pid_to_files.items():
                    if p1!=p2:
                        if type(s1) is set and type(s2) is set:
                            if len(s1)>0 and len(s2)>0:
                                try:
                                    inters = s1.intersection(s2)
                                except Exception:
                                    print ('Exception during intersect inner')
                                    pass
                                if (len(inters)>0):
                                    print ('FILE Intersection ' + str(p1) + ' ' + str(p2) + ' ' + str(inters))
          # check for intersections
            for p1, s1 in self.pid_to_connections.items():
                for p2, s2 in self.pid_to_connections.items():
                    if p1!=p2:
                        if type(s1) is set and type(s2) is set:
                            if len(s1)>0 and len(s2)>0:
                                try:
                                    inters = s1.intersection(s2)
                                except Exception:
                                    print ('Exception during intersect inner')
                                    pass
                                if (len(inters)>0):
                                    print ('CON Intersection ' + str(p1) + ' ' + str(p2) + ' ' + str(inters))

            # check for intersections
            #for p1, s1 in slf.pid_to_files.items():
            #    for p2, s2 in self.pid_to_files.items():
            #        if p1!=p2 and len(s1.intersection(s2))!=0:
            #            print ('Intersection found files ' + str(p1) + ' ' + str(p2) + ' ' + s1.intersection(s2))
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            print('Exception during intersect outer')
            pass

    def is_good_candidate(self, candid, finishedtasks):
        if self.procstatus[candid] != 'ToDo':
            return False
        needs = set([self.tasktoid[t] for t in self.taskneeds[self.idtotask[candid]]])
        if set(finishedtasks).intersection(needs) == needs:
            return True
        return False

    def emit_code_for_task(self, tid, lines):
        actionlogger.debug("Submitting task " + str(self.idtotask[tid]))
        taskspec = self.workflowspec['stages'][tid]
        c = taskspec['cmd']
        workdir = taskspec['cwd']
        env = taskspec.get('env')
        # in general:
        # try to make folder
        lines.append('[ ! -d ' + workdir + ' ] && mkdir ' + workdir + '\n')
        # cd folder
        lines.append('cd ' + workdir + '\n')
        # set local environment
        if env!=None:
            for e in env.items():
                lines.append('export ' + e[0] + '=' + str(e[1]) + '\n')
        # do command
        lines.append(c + '\n')
        # unset local environment
        if env!=None:
            for e in env.items():
                lines.append('unset ' + e[0] + '\n')

        # cd back
        lines.append('cd $OLDPWD\n')


    # produce a bash script that runs workflow standalone
    def produce_script(self, filename):
        # pick one of the correct task orderings
        taskorder = self.topological_orderings[0]
        outF = open(filename, "w")

        lines=[]
        # header
        lines.append('#!/usr/bin/env bash\n')
        lines.append('#THIS FILE IS AUTOGENERATED\n')
        lines.append('export JOBUTILS_SKIPDONE=ON\n')

        # we record the global environment setting
        # in particular to capture global workflow initialization
        lines.append('#-- GLOBAL INIT SECTION FROM WORKFLOW --\n')
        for e in self.globalinit['env']:
            lines.append('export ' + str(e) + '=' + str(self.globalinit['env'][e]) + '\n')
        lines.append('#-- TASKS FROM WORKFLOW --\n')
        for tid in taskorder:
            print ('Doing task ' + self.idtotask[tid])
            self.emit_code_for_task(tid, lines)

        outF.writelines(lines)
        outF.close()

    def production_endoftask_hook(self, tid):
        # Executes a hook at end of a successful task, meant to be used in GRID productions.
        # For the moment, archiving away log files, done + time files from jobutils.
        # TODO: In future this may be much more generic tasks such as dynamic cleanup of intermediate
        # files (when they are no longer needed).
        # TODO: Care must be taken with the continue feature as `_done` files are stored elsewhere now
        actionlogger.info("Cleaning up log files for task " + str(tid))
        logf = self.get_logfile(tid)
        donef = self.get_done_filename(tid)
        timef = logf + "_time"

        # add to tar file archive
        tf = tarfile.open(name="pipeline_log_archive.log.tar", mode='a')
        if tf != None:
          tf.add(logf)
          tf.add(donef)
          tf.add(timef)
          tf.close()

          # remove original file
          os.remove(logf)
          os.remove(donef)
          os.remove(timef)

    # print error message when no progress can be made
    def noprogress_errormsg(self):
        # TODO: rather than writing this out here; refer to the documentation discussion this?
        msg = """Scheduler runtime error: The scheduler is not able to make progress although we have a non-zero candidate set.

Explanation: This is typically the case because the **ESTIMATED** resource requirements for some tasks
in the workflow exceed the available number of CPU cores or the memory (as explicitely or implicitely determined from the
--cpu-limit and --mem-limit options). Often, this might be the case on laptops with <=16GB of RAM if one of the tasks
is demanding ~16GB. In this case, one could try to tell the scheduler to use a slightly higher memory limit
with an explicit --mem-limit option (for instance `--mem-limit 20000` to set to 20GB). This might work whenever the
**ACTUAL** resource usage of the tasks is smaller than anticipated (because only small test cases are run).

In addition it might be worthwile running the workflow without this resource aware, dynamic scheduler.
This is possible by converting the json workflow into a linearized shell script and by directly executing the shell script.
Use the `--produce-script myscript.sh` option for this.
"""
        print (msg, file=sys.stderr)

    def execute(self):
        self.start_time = time.perf_counter()
        psutil.cpu_percent(interval=None)
        os.environ['JOBUTILS_SKIPDONE'] = "ON"
        errorencountered = False

        def speedup_ROOT_Init():
               """initialize some env variables that speed up ROOT init
               and prevent ROOT from spawning many short-lived child
               processes"""

               # only do it on Linux
               if platform.system() != 'Linux':
                  return

               if os.environ.get('ROOT_LDSYSPATH')!=None and os.environ.get('ROOT_CPPSYSINCL')!=None:
                  # do nothing if already defined
                  return

               # a) the PATH for system libraries
               # search taken from ROOT TUnixSystem
               cmd='LD_DEBUG=libs LD_PRELOAD=DOESNOTEXIST ls /tmp/DOESNOTEXIST 2>&1 | grep -m 1 "system search path" | sed \'s/.*=//g\' | awk \'//{print $1}\''
               proc = subprocess.Popen([cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
               libpath, err = proc.communicate()
               if not (args.no_rootinit_speedup == True):
                  print ("setting up ROOT system")
                  os.environ['ROOT_LDSYSPATH'] = libpath.decode()
                  os.environ['CLING_LDSYSPATH'] = libpath.decode()

               # b) the PATH for compiler includes needed by Cling
               cmd = "LC_ALL=C c++ -xc++ -E -v /dev/null 2>&1 | sed -n '/^#include/,${/^ \\/.*++/{p}}'"
               proc = subprocess.Popen([cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
               incpath, err = proc.communicate()
               incpaths = [ line.lstrip() for line in incpath.decode().splitlines() ]
               joined = ':'.join(incpaths)
               if not (args.no_rootinit_speedup == True):
                  actionlogger.info("Determined ROOT_CPPSYSINCL=" + joined)
                  os.environ['ROOT_CPPSYSINCL'] = joined
                  os.environ['CLING_CPPSYSINCL'] = joined

        speedup_ROOT_Init()

        # we make our own "tmp" folder
        # where we can put stuff such as tmp socket files etc (for instance DPL FAIR-MQ sockets)
        # (In case of running within docker/singularity, this may not be so important)
        if not os.path.isdir("./.tmp"):
          os.mkdir("./.tmp")
        if os.environ.get('FAIRMQ_IPC_PREFIX')==None:
          socketpath = os.getcwd() + "/.tmp"
          actionlogger.info("Setting FAIRMQ socket path to " + socketpath)
          os.environ['FAIRMQ_IPC_PREFIX'] = socketpath

        # some maintenance / init work
        if args.list_tasks:
          print ('List of tasks in this workflow:')
          for i,t in enumerate(self.workflowspec['stages'],0):
              print (t['name'] + '  (' + str(t['labels']) + ')' + ' ToDo: ' + str(not self.ok_to_skip(i)))
          exit (0)

        if args.produce_script != None:
          self.produce_script(args.produce_script)
          exit (0)

        # execute the user-given global init cmd for this workflow
        globalinitcmd = self.globalinit.get("cmd", None)
        if globalinitcmd != None:
           if not self.execute_globalinit_cmd(globalinitcmd):
              exit (1)

        if args.rerun_from:
          reruntaskfound=False
          for task in self.workflowspec['stages']:
              taskname=task['name']
              if re.match(args.rerun_from, taskname):
                reruntaskfound=True
                taskid=self.tasktoid[taskname]
                self.remove_done_flag(find_all_dependent_tasks(self.possiblenexttask, taskid))
          if not reruntaskfound:
              print('No task matching ' + args.rerun_from + ' found; cowardly refusing to do anything ')
              exit (1)

        # *****************
        # main control loop
        # *****************
        candidates = [ tid for tid in self.possiblenexttask[-1] ]

        self.process_list=[] # list of tuples of nodes ids and Popen subprocess instances

        finishedtasks=[] # global list of finished tasks

        try:

            while True:
                # sort candidate list according to task weights
                candidates = [ (tid, self.taskweights[tid]) for tid in candidates ]
                candidates.sort(key=lambda tup: (tup[1][0],-tup[1][1])) # prefer small and same timeframes first then prefer important tasks within frameframe
                # remove weights
                candidates = [ tid for tid,_ in candidates ]

                finished = [] # --> to account for finished because already done or skipped
                actionlogger.debug('Sorted current candidates: ' + str([(c,self.idtotask[c]) for c in candidates]))
                self.try_job_from_candidates(candidates, finished)
                if len(candidates) > 0 and len(self.process_list) == 0:
                    self.noprogress_errormsg()
                    send_webhook(self.args.webhook,"Unable to make further progress: Quitting")
                    errorencountered = True
                    break

                finished_from_started = [] # to account for finished when actually started
                failing = []
                while self.waitforany(self.process_list, finished_from_started, failing):
                    if not args.dry_run:
                        self.monitor(self.process_list) #  ---> make async to normal operation?
                        time.sleep(1) # <--- make this incremental (small wait at beginning)
                    else:
                        time.sleep(0.001)

                finished = finished + finished_from_started
                actionlogger.debug("finished now :" + str(finished_from_started))
                finishedtasks = finishedtasks + finished

                # perform file cleanup
                if self.do_early_file_removal:
                   self.perform_early_file_removal(finished_from_started)

                if self.is_productionmode:
                   # we can do some generic cleanup of finished tasks in non-interactive/GRID mode
                   # TODO: this can run asynchronously
                   for _t in finished_from_started:
                       self.production_endoftask_hook(_t)

                # if a task was marked "failed" and we come here (because
                # we use --keep-going) ... we need to take out the pid from finished
                if len(failing) > 0:
                    # remove these from those marked finished in order
                    # not to continue with their children
                    errorencountered = True
                    for t in failing:
                        finished = [ x for x in finished if x != t ]
                        finishedtasks = [ x for x in finishedtasks if x != t ]

                # if a task was marked as "retry" we simply put it back into the candidate list
                if len(self.tids_marked_toretry) > 0:
                    # we need to remove these first of all from those marked finished
                    for t in self.tids_marked_toretry:
                        finished = [ x for x in finished if x != t ]
                        finishedtasks = [ x for x in finishedtasks if x != t ]

                    candidates = candidates + self.tids_marked_toretry
                    self.tids_marked_toretry = []


                # new candidates
                for tid in finished:
                    if self.possiblenexttask.get(tid)!=None:
                        potential_candidates=list(self.possiblenexttask[tid])
                        for candid in potential_candidates:
                        # try to see if this is really a candidate:
                            if self.is_good_candidate(candid, finishedtasks) and candidates.count(candid)==0:
                                candidates.append(candid)

                actionlogger.debug("New candidates " + str( candidates))
                send_webhook(self.args.webhook, "New candidates " + str(candidates))

                if len(candidates)==0 and len(self.process_list)==0:
                   break
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            traceback.print_exc()
            print ('Cleaning up ')

            self.SIGHandler(0,0)

        endtime = time.perf_counter()
        statusmsg = "success"
        if errorencountered:
           statusmsg = "with failures"

        print ('\n**** Pipeline done ' + statusmsg + ' (global_runtime : {:.3f}s) *****\n'.format(endtime-self.start_time))
        actionlogger.debug("global_runtime : {:.3f}s".format(endtime-self.start_time))
        return errorencountered


if args.cgroup!=None:
    myPID=os.getpid()
    # cgroups such as /sys/fs/cgroup/cpuset/<cgroup-name>/tasks
    # or              /sys/fs/cgroup/cpu/<cgroup-name>/tasks
    command="echo " + str(myPID) + f" > {args.cgroup}"
    actionlogger.info(f"Try running in cgroup {args.cgroup}")
    waitstatus = os.system(command)
    if code := os.waitstatus_to_exitcode(waitstatus):
        actionlogger.error(f"Could not apply cgroup")
        exit(code)
    actionlogger.info("Running in cgroup")


# This starts the fanotify fileaccess monitoring process
# if asked for
o2dpg_filegraph_exec = os.getenv("O2DPG_PRODUCE_FILEGRAPH") # switches filegraph monitoring on and contains the executable name
if o2dpg_filegraph_exec:
    env = os.environ.copy()
    env["FILEACCESS_MON_ROOTPATH"] = os.getcwd()
    env["MAXMOTHERPID"] = f"{os.getpid()}"

    fileaccess_log_file_name = f"pipeline_fileaccess_{os.getpid()}.log"
    fileaccess_log_file = open(fileaccess_log_file_name, "w")
    fileaccess_monitor_proc = subprocess.Popen(
        [o2dpg_filegraph_exec],
        stdout=fileaccess_log_file,
        stderr=subprocess.STDOUT,
        env=env)
else:
    fileaccess_monitor_proc = None

try:
    # This is core workflow runner invocation
    executor=WorkflowExecutor(args.workflowfile,jmax=int(args.maxjobs),args=args)
    rc = executor.execute()
finally:
    if fileaccess_monitor_proc:
        fileaccess_monitor_proc.terminate()  # sends SIGTERM
        try:
            fileaccess_monitor_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            fileaccess_monitor_proc.kill()   # force kill if not stopping
        # now produce the final filegraph output
        o2dpg_root = os.getenv("O2DPG_ROOT")
        analyse_cmd = [
                sys.executable,  # runs with same Python interpreter
                f"{o2dpg_root}/UTILS/FileIOGraph/analyse_FileIO.py",
                "--actionFile", actionlogger_file,
                "--monitorFile", fileaccess_log_file_name,
                "-o", f"pipeline_fileaccess_report_{os.getpid()}.json",
                "--basedir", os.getcwd() ]
        print (f"Producing FileIOGraph with command {analyse_cmd}")
        subprocess.run(analyse_cmd, check=True)

sys.exit(rc)