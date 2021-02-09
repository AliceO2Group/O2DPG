#!/usr/bin/env python3

# started February 2021, sandro.wenzel@cern.ch

import re
import subprocess
import shlex
import time
import json
import logging
import os
try:
    from graphviz import Digraph
    havegraphviz=True
except ImportError:
    havegraphviz=False


#
# Code section to find all topological orderings
# of a DAG. This is used to know when we can schedule
# things in parallel.
#

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
def findAllTopologicalOrders(graph, path, discovered, N, allpaths):
    if len(allpaths) >= 2000:
        # print ('More than 2000 paths found')
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
def printAllTopologicalOrders(graph):
    # get number of nodes in the graph
    N = len(graph.adjList)
 
    # create an auxiliary space to keep track of whether vertex is discovered
    discovered = [False] * N
 
    # list to store the topological order
    path = []
    allpaths = []
    # find all topological ordering and print them
    findAllTopologicalOrders(graph, path, discovered, N, allpaths)
    return allpaths

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
    
    # find topological orderings of the graph -> not used for moment
    # create a graph from edges
    # graph = Graph(edges, N)
    # allorderings = printAllTopologicalOrders(graph)
    allorderings=[[]]
    # find out "can be followed by" for each node
    # can be followed does not mean that all requirements are met though
    # nextjob={}
    # for plan in allorderings:
    #    previous = -1 # means start
    #    for e in plan:
    #        if nextjob.get(previous)!=None:
    #            nextjob[previous].add(e)
    #        else:
    #            nextjob[previous]=set()
    #            nextjob[previous].add(e)
    #        previous=e
            
    # print(nextjob)
            
    return (allorderings, nextjobtrivial)


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
    print (tasktoid)

    nodes = []
    edges = []
    for t in taskuniverse:
        nodes.append(tasktoid[t[0]['name']])
        for n in t[0]['needs']:
            edges.append((tasktoid[n], tasktoid[t[0]['name']]))
    
    return (edges, nodes)
        

# loads the workflow specification
# returns a tuple of (all_topological_ordering, possible_next_job_dict, nodeset)
def load_workflow(workflowfile):
    fp=open(workflowfile)
    workflowspec=json.load(fp)
    return workflowspec


# builds topological orderings (for each timeframe)    
def build_topological_orderings(workflowspec):
    globaltaskuniverse = [ (l, i) for i, l in enumerate(workflowspec['stages'], 1) ]
    timeframeset = set( l['timeframe'] for l in workflowspec['stages'] )

    # timeframes are independent so we can restrict graph to them
    # (this makes the graph analysis less computational/combinatorial)
    timeframe_task_universe = { tf:[ (l, i) for i, l in enumerate(workflowspec['stages'], 1) if (l['timeframe']==tf or l['timeframe']==-1) ]  for tf in timeframeset if tf!=-1 } 
    edges, nodes = build_graph(globaltaskuniverse, workflowspec)
    tup = analyseGraph(edges, nodes)
    # 
    global_next_tasks = tup[1]

    # weight can be anything ... for the moment we just prefer to stay within a timeframe
    def getweight(tid):
        return globaltaskuniverse[tid][0]['timeframe']
    
    # introduce some initial weight as second component
    for key in global_next_tasks:
        global_next_tasks[key] = [ tid for tid in global_next_tasks[key] ]

    task_weights = [ getweight(tid) for tid in range(len(globaltaskuniverse)) ]
        
    print (global_next_tasks)
    return { 'nexttasks' : global_next_tasks, 'weights' : task_weights }


#
# functions for execution; encapsulated in a WorkflowExecutor class
#
class WorkflowExecutor:
    # Constructor
    def __init__(self, workflowfile, args, jmax=100):
      self.args=args
      self.workflowfile = workflowfile
      self.workflowspec = load_workflow(workflowfile)
      workflow = build_topological_orderings(self.workflowspec)
      if args.visualize_workflow:
          draw_workflow(self.workflowspec)
      self.possiblenexttask = workflow['nexttasks']
      self.taskweights = workflow['weights']
      print (self.possiblenexttask)
      self.taskuniverse = [ l['name'] for l in self.workflowspec['stages'] ]
      self.idtotask = [ 0 for l in self.taskuniverse ]
      self.tasktoid = {}
      for i in range(len(self.taskuniverse)):
          self.tasktoid[self.taskuniverse[i]]=i
          self.idtotask[i]=self.taskuniverse[i] 

      self.maxmemperid = [ self.workflowspec['stages'][tid]['resources']['mem'] for tid in range(len(self.taskuniverse)) ]
      self.curmembooked = 0
      self.memlimit = args.mem_limit # some configurable number
      self.procstatus = { tid:'ToDo' for tid in range(len(self.workflowspec['stages'])) }
      self.taskneeds= { t:set(self.getallrequirements(t)) for t in self.taskuniverse }
      self.stoponfailure = True
      self.max_jobs_parallel = int(jmax)
      self.scheduling_iteration = 0
                         
    def getallrequirements(self, t):
        l=[]
        for r in self.workflowspec['stages'][self.tasktoid[t]]['needs']:
            l.append(r)
            l=l+self.getallrequirements(r)
        return l
      
    # submits a task as subprocess and records Popen instance
    def submit(self, tid):
      logging.debug("Submitting task " + str(self.idtotask[tid]))
      c = self.workflowspec['stages'][tid]['cmd']
      workdir = self.workflowspec['stages'][tid]['cwd']
      if not workdir=='':
          if os.path.exists(workdir) and not os.path.isdir(workdir):
              logging.error('Cannot create working dir ... some other resource exists already')
              return None

          if not os.path.isdir(workdir):
              os.mkdir(workdir)

      self.procstatus[tid]='Running'
      if args.dry_run:
          drycommand="echo \' " + str(self.scheduling_iteration) + " : would do " + str(self.workflowspec['stages'][tid]['name']) + "\'"
          return subprocess.Popen(['/bin/bash','-c',drycommand], cwd=workdir)
                                  
      return subprocess.Popen(['/bin/bash','-c',c], cwd=workdir)

    def ok_to_submit(self, tid):
      if self.curmembooked + self.maxmemperid[tid] < self.memlimit:
        return True
      else:
        return False

    def try_job_from_candidates(self, taskcandidates, process_list):
       self.scheduling_iteration = self.scheduling_iteration + 1
       initialcandidates=taskcandidates.copy()
       for tid in initialcandidates:
          logging.debug ("trying to submit" + str(tid))
          if self.ok_to_submit(tid) and len(process_list) < self.max_jobs_parallel:
            p=self.submit(tid)
            if p!=None:
                self.curmembooked+=self.maxmemperid[tid]
                process_list.append((tid,p))
                taskcandidates.remove(tid)
          else:
             break

    def stop_pipeline_and_exit(self, process_list):
        # kill all remaining jobs
        for p in process_list:
           p[1].kill()

        exit(1)

    def waitforany(self, process_list, finished):
       failuredetected = False
       for p in list(process_list):
          logging.debug ("polling" + str(p))
          returncode = 0
          if not self.args.dry_run:
              returncode = p[1].poll()
          if returncode!=None:
            logging.info ('Task' + str(self.idtotask[p[0]]) + ' finished with status ' + str(returncode))
            # account for cleared resources
            self.curmembooked-=self.maxmemperid[p[0]]
            self.procstatus[p[0]]='Done'
            finished.append(p[0])
            process_list.remove(p)
            if returncode!=0:
               failuredetected = True      
    
       if failuredetected and self.stoponfailure:
          logging.info('Stoping pipeline due to failure in a stage')
          self.stop_pipeline_and_exit(process_list)

       # empty finished means we have to wait more        
       return len(finished)==0

    def is_good_candidate(self, candid, finishedtasks):
        if self.procstatus[candid] != 'ToDo':
            return False
        needs = set([self.tasktoid[t] for t in self.taskneeds[self.idtotask[candid]]])
        if set(finishedtasks).intersection(needs) == needs:
            return True
        return False

    def execute(self):
        # main control loop
        currenttimeframe=1
        candidates = [ tid for tid in self.possiblenexttask[-1] ]

        process_list=[] # list of tuples of nodes ids and Popen subprocess instances
        finishedtasks=[]
        while True:
            # sort candidate list occurding to task weights
            candidates = [ (tid, self.taskweights[tid]) for tid in candidates ]
            candidates.sort(key=lambda tup: tup[1])
            # remove weights
            candidates = [ tid for tid,_ in candidates ]

            logging.debug(candidates)
            self.try_job_from_candidates(candidates, process_list)
        
            finished = []
            while self.waitforany(process_list, finished):
                if not args.dry_run:
                    time.sleep(1)
                else:
                    time.sleep(0.01)
    
            logging.debug("finished " + str( finished))
            finishedtasks=finishedtasks + finished
    
            # someone returned
            # new candidates
            for tid in finished:
                if self.possiblenexttask.get(tid)!=None:
                    potential_candidates=list(self.possiblenexttask[tid])
                    for candid in potential_candidates:
                    # try to see if this is really a candidate:
                        if self.is_good_candidate(candid, finishedtasks) and candidates.count(candid)==0:
                            candidates.append(candid)
    
            logging.debug("New candidates " + str( candidates))
    
            if len(candidates)==0 and len(process_list)==0:
                break

import argparse
try:
    from psutil import virtual_memory
    max_system_mem=virtual_memory().total
except ImportError:
    # let's assume 16GB
    max_system_mem=16*1024*1024*1024

parser = argparse.ArgumentParser(description='Parellel execution of a (O2-DPG) DAG data pipeline under resource contraints.')
parser.add_argument('-f','--workflowfile', help='Input workflow file name', required=True)
parser.add_argument('-jmax','--maxjobs', help='number of maximal parallel tasks', default=100)
parser.add_argument('--dry-run', action='store_true', help='show what you would do')
parser.add_argument('--visualize-workflow', action='store_true', help='saves a graph visualization of workflow')
parser.add_argument('--target-stages', help='Runs the pipeline by target labels (example "TPC" or "digi")')

parser.add_argument('--mem-limit', help='set memory limit as scheduling constraint', default=max_system_mem)
args = parser.parse_args()
print (args)            
print (args.workflowfile)

logging.basicConfig(filename='example.log', filemode='w', level=logging.DEBUG)
executor=WorkflowExecutor(args.workflowfile,jmax=args.maxjobs,args=args)
executor.execute()
