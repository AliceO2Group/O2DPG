#!/usr/bin/env python3

# started February 2021, sandro.wenzel@cern.ch

import re
import subprocess
import shlex
import time
import json
import logging
import os
import signal
import sys
try:
    from graphviz import Digraph
    havegraphviz=True
except ImportError:
    havegraphviz=False


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

# find all tasks that depend on a given task (id)
def find_all_dependent_tasks(possiblenexttask, tid):
    daughterlist=[tid]
    # possibly recurse
    for n in possiblenexttask[tid]:
        daughterlist = daughterlist + find_all_dependent_tasks(n)

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
        

# loads the workflow specification
def load_workflow(workflowfile):
    fp=open(workflowfile)
    workflowspec=json.load(fp)
    return workflowspec


# filters the original workflowspec according to wanted targets or labels
# returns a new workflowspec
def filter_workflow(workflowspec, targets=[], targetlabels=[]):
    if len(targets)==0:
       return workflowspec
    if len(targetlabels)==0 and len(targets)==1 and targets[0]=="*":
       return workflowspec

    transformedworkflowspec = workflowspec

    def task_matches(t):
        for filt in targets:
            if filt=="*":
                return True
            if re.match(filt, t)!=None:
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

    # build full target list
    full_target_list = [ t for t in workflowspec['stages'] if task_matches(t['name']) and task_matches_labels(t) ]
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
    return transformedworkflowspec


# builds topological orderings (for each timeframe)    
def build_dag_properties(workflowspec):
    globaltaskuniverse = [ (l, i) for i, l in enumerate(workflowspec['stages'], 1) ]
    timeframeset = set( l['timeframe'] for l in workflowspec['stages'] )

    edges, nodes = build_graph(globaltaskuniverse, workflowspec)
    tup = analyseGraph(edges, nodes)
    # 
    global_next_tasks = tup[1]

    # weight influences scheduling order can be anything user defined ... for the moment we just prefer to stay within a timeframe
    def getweight(tid):
        return globaltaskuniverse[tid][0]['timeframe']
    
    # introduce some initial weight as second component
    for key in global_next_tasks:
        global_next_tasks[key] = [ tid for tid in global_next_tasks[key] ]

    task_weights = [ getweight(tid) for tid in range(len(globaltaskuniverse)) ]
        
    # print (global_next_tasks)
    return { 'nexttasks' : global_next_tasks, 'weights' : task_weights, 'topological_ordering' : tup[0] }


#
# functions for execution; encapsulated in a WorkflowExecutor class
#
class WorkflowExecutor:
    # Constructor
    def __init__(self, workflowfile, args, jmax=100):
      self.args=args
      self.workflowfile = workflowfile
      self.workflowspec = load_workflow(workflowfile)
      self.workflowspec = filter_workflow(self.workflowspec, args.target_tasks, args.target_labels)

      if len(self.workflowspec['stages']) == 0:
          print ('Workflow is empty. Nothing to do')
          exit (0)
      
      workflow = build_dag_properties(self.workflowspec)
      if args.visualize_workflow:
          draw_workflow(self.workflowspec)
      self.possiblenexttask = workflow['nexttasks']
      self.taskweights = workflow['weights']
      self.topological_orderings = workflow['topological_ordering']
      self.taskuniverse = [ l['name'] for l in self.workflowspec['stages'] ]
      self.idtotask = [ 0 for l in self.taskuniverse ]
      self.tasktoid = {}
      for i in range(len(self.taskuniverse)):
          self.tasktoid[self.taskuniverse[i]]=i
          self.idtotask[i]=self.taskuniverse[i]

      self.maxmemperid = [ self.workflowspec['stages'][tid]['resources']['mem'] for tid in range(len(self.taskuniverse)) ]
      self.cpuperid = [ self.workflowspec['stages'][tid]['resources']['cpu'] for tid in range(len(self.taskuniverse)) ]
      self.curmembooked = 0
      self.curcpubooked = 0
      self.memlimit = float(args.mem_limit) # some configurable number
      self.cpulimit = float(args.cpu_limit)
      self.procstatus = { tid:'ToDo' for tid in range(len(self.workflowspec['stages'])) }
      self.taskneeds= { t:set(self.getallrequirements(t)) for t in self.taskuniverse }
      self.stoponfailure = True
      self.max_jobs_parallel = int(jmax)
      self.scheduling_iteration = 0
      self.process_list = []  # list of currently scheduled tasks with normal priority
      self.backfill_process_list = [] # list of curently scheduled tasks with low backfill priority (not sure this is needed)
      self.pid_to_psutilsproc = {}  # cache of putilsproc for resource monitoring
      self.pid_to_files = {} # we can auto-detect what files are produced by which task (at least to some extent)
      self.pid_to_connections = {} # we can auto-detect what connections are opened by which task (at least to some extent)
      signal.signal(signal.SIGINT, self.SIGHandler)
      signal.siginterrupt(signal.SIGINT, False)
      self.nicevalues = [ 0 for tid in range(len(self.taskuniverse)) ]

    def SIGHandler(self, signum, frame):
       # basically forcing shut down of all child processes
       logging.info("Signal " + str(signum) + " caught")
       procs = psutil.Process().children(recursive=True)
       for p in procs:
           logging.info("Terminating " + str(p))
           try:
               p.terminate()
           except psutil.NoSuchProcess:
               pass
       gone, alive = psutil.wait_procs(procs, timeout=3)
       for p in alive:
           logging.info("Killing " + str(p))
           try:
               p.kill()
           except psutil.NoSuchProcess:
               pass
       exit (1)

    def getallrequirements(self, t):
        l=[]
        for r in self.workflowspec['stages'][self.tasktoid[t]]['needs']:
            l.append(r)
            l=l+self.getallrequirements(r)
        return l

    def get_done_filename(self, tid):
        name = self.workflowspec['stages'][tid]['name']
        workdir = self.workflowspec['stages'][tid]['cwd']
        # name and workdir define the "done" file as used by taskwrapper
        # this assumes that taskwrapper is used to actually check if something is to be rerun
        done_filename = workdir + '/' + name + '.log_done'
        return done_filename

    # removes the done flag from tasks that need to be run again
    def remove_done_flag(self, listoftaskids):
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
    def submit(self, tid, nice=0):
      logging.debug("Submitting task " + str(self.idtotask[tid]) + " with nice value " + str(nice))
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

      taskenv = os.environ.copy()
      # add task specific environment
      if self.workflowspec['stages'][tid].get('env')!=None:
          taskenv.update(self.workflowspec['stages'][tid]['env'])

      p = psutil.Popen(['/bin/bash','-c',c], cwd=workdir, env=taskenv)
      p.nice(nice)
      return p

    def ok_to_submit(self, tid, softcpufactor=1, softmemfactor=1):
      # analyse CPU
      okcpu = (self.curcpubooked + float(self.cpuperid[tid]) <= softcpufactor*self.cpulimit)
      # analyse MEM
      okmem = (self.curmembooked + float(self.maxmemperid[tid]) <= softmemfactor*self.memlimit)
      logging.debug ('Condition check for  ' + str(tid) + ':' + str(self.idtotask[tid]) + ' CPU ' + str(okcpu) + ' MEM ' + str(okmem))
      return (okcpu and okmem)

    def ok_to_skip(self, tid):
        done_filename = self.get_done_filename(tid)
        if os.path.exists(done_filename) and os.path.isfile(done_filename):
            return True
        return False

    def try_job_from_candidates(self, taskcandidates, process_list, finished):
       self.scheduling_iteration = self.scheduling_iteration + 1

       # the ordinary process list part
       initialcandidates=taskcandidates.copy()
       for tid in initialcandidates:
          logging.debug ("trying to submit " + str(tid) + ':' + str(self.idtotask[tid]))
          # check early if we could skip
          # better to do it here (instead of relying on taskwrapper)
          if self.ok_to_skip(tid):
              finished.append(tid)
              taskcandidates.remove(tid)
              continue

          elif self.ok_to_submit(tid) and (len(self.process_list) + len(self.backfill_process_list) < self.max_jobs_parallel):
            p=self.submit(tid)
            if p!=None:
                self.curmembooked+=float(self.maxmemperid[tid])
                self.curcpubooked+=float(self.cpuperid[tid])
                self.process_list.append((tid,p))
                taskcandidates.remove(tid)
                # minimal delay
                time.sleep(0.1)
          else:
             break #---> we break at first failure assuming some priority (other jobs may come in via backfill)

       # the backfill part for remaining candidates
       initialcandidates=taskcandidates.copy()
       for tid in initialcandidates:
          logging.debug ("trying to backfill submit" + str(tid) + ':' + str(self.idtotask[tid]))

          if self.ok_to_submit(tid, softcpufactor=1.5) and (len(self.process_list) + len(self.backfill_process_list)) < self.max_jobs_parallel:
            p=self.submit(tid, 19)
            if p!=None:
                self.curmembooked+=float(self.maxmemperid[tid])
                self.curcpubooked+=float(self.cpuperid[tid])
                self.process_list.append((tid,p))
                taskcandidates.remove(tid) #-> not sure about this one
                # minimal delay
                time.sleep(0.1)
          else:
             continue

    def stop_pipeline_and_exit(self, process_list):
        # kill all remaining jobs
        for p in process_list:
           p[1].kill()

        exit(1)


    def monitor(self, process_list):
        globalCPU=0.
        globalPSS=0.
        resources_per_task = {}
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
            except psutil.NoSuchProcess:
                continue

            # accumulate total metrics (CPU, memory)
            totalCPU = 0.
            totalPSS = 0.
            totalSWAP = 0.
            totalUSS = 0.
            for p in psutilProcs:
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

                # MEMORY part
                try:
                    fullmem=p.memory_full_info()
                    totalPSS=totalPSS + fullmem.pss
                    totalSWAP=totalPSS + fullmem.swap
                    totalUSS=totalUSS + fullmem.uss
                except psutil.NoSuchProcess:
                    pass

                # CPU part
                # fetch existing proc or insert
                cachedproc = self.pid_to_psutilsproc.get(p.pid)
                if cachedproc!=None:
                    try:
                        thiscpu = cachedproc.cpu_percent(interval=None)
                    except psutil.NoSuchProcess:
                        thiscpu = 0.
                    totalCPU = totalCPU + thiscpu
                else:
                    self.pid_to_psutilsproc[p.pid] = p
                    try:
                        self.pid_to_psutilsproc[p.pid].cpu_percent()
                    except psutil.NoSuchProcess:
                        pass

            resources_per_task[tid]={'name':self.idtotask[tid], 'cpu':totalCPU, 'uss':totalUSS/1024./1024., 'pss':totalPSS/1024./1024, 'nice':proc.nice(), 'swap':totalSWAP}
            # print (resources_per_task[tid])
            globalCPU=globalCPU + totalCPU
            globalPSS=globalPSS + totalPSS

        # print ("globalCPU " + str(globalCPU) + ' in ' + str(len(process_list)) + ' tasks ' + str(self.curmembooked) + ',' + str(self.curcpubooked))
        globalPSS = globalPSS/1024./1024.
        # print ("globalPSS " + str(globalPSS))
        if globalPSS > self.memlimit:
            print('*** MEMORY LIMIT PASSED !! ***')
            # --> We could use this for corrective actions such as killing jobs currently back-filling

    def waitforany(self, process_list, finished):
       failuredetected = False
       if len(process_list)==0:
           return False

       for p in list(process_list):
          returncode = 0
          if not self.args.dry_run:
              returncode = p[1].poll()
          if returncode!=None:
            logging.info ('Task' + str(p[1].pid) + ' ' + str(self.idtotask[p[0]]) + ' finished with status ' + str(returncode))
            # account for cleared resources
            self.curmembooked-=float(self.maxmemperid[p[0]])
            self.curcpubooked-=float(self.cpuperid[p[0]])
            self.procstatus[p[0]]='Done'
            finished.append(p[0])
            process_list.remove(p)
            if returncode!=0:
               failuredetected = True      
    
       if failuredetected and self.stoponfailure:
          logging.info('Stoping pipeline due to failure in a stage PID')
          # self.analyse_files_and_connections()
          self.stop_pipeline_and_exit(process_list)

       # empty finished means we have to wait more        
       return len(finished)==0

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
        logging.debug("Submitting task " + str(self.idtotask[tid]))
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
        lines.append('JOBUTILS_SKIPDONE=ON\n')
        for tid in taskorder:
            print ('Doing task ' + self.idtotask[tid])
            self.emit_code_for_task(tid, lines)

        outF.writelines(lines)
        outF.close()


    def execute(self):
        psutil.cpu_percent(interval=None)
        os.environ['JOBUTILS_SKIPDONE'] = "ON"
        # some maintenance / init work
        if args.list_tasks:
          print ('List of tasks in this workflow:')
          for i in self.workflowspec['stages']:
              print (i['name'] + '  (' + str(i['labels']) + ')')
          exit (0)
 
        if args.produce_script != None:
            self.produce_script(args.produce_script)
            exit (0)

        if args.rerun_from:
          if self.tasktoid.get(args.rerun_from)!=None:
              taskid=self.tasktoid[args.rerun_from]
              self.remove_done_flag(find_all_dependent_tasks(self.possiblenexttask, taskid))
          else:
              print('task ' + args.rerun_from + ' not found; cowardly refusing to do anything ')
              exit (1) 

        # *****************
        # main control loop
        # *****************
        currenttimeframe=1
        candidates = [ tid for tid in self.possiblenexttask[-1] ]

        self.process_list=[] # list of tuples of nodes ids and Popen subprocess instances

        finishedtasks=[]
        try:

            while True:
                # sort candidate list according to task weights
                candidates = [ (tid, self.taskweights[tid]) for tid in candidates ]
                candidates.sort(key=lambda tup: tup[1])
                # remove weights
                candidates = [ tid for tid,_ in candidates ]

                finished = []
                logging.debug(candidates)
                self.try_job_from_candidates(candidates, self.process_list, finished)
            
                finished_from_started = []
                while self.waitforany(self.process_list, finished_from_started):
                    if not args.dry_run:
                        self.monitor(self.process_list) #  ---> make async to normal operation?
                        time.sleep(1) # <--- make this incremental (small wait at beginning)
                    else:
                        time.sleep(0.01)

                finished = finished + finished_from_started
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
    
                if len(candidates)==0 and len(self.process_list)==0:
                   break
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)
            print ('Cleaning up ')

            self.SIGHandler(0,0)

        print ('\n**** Pipeline done *****\n')
        # self.analyse_files_and_connections()

import argparse
import psutil
max_system_mem=psutil.virtual_memory().total

parser = argparse.ArgumentParser(description='Parallel execution of a (O2-DPG) DAG data/job pipeline under resource contraints.', 
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-f','--workflowfile', help='Input workflow file name', required=True)
parser.add_argument('-jmax','--maxjobs', help='Number of maximal parallel tasks.', default=100)
parser.add_argument('--dry-run', action='store_true', help='Show what you would do.')
parser.add_argument('--visualize-workflow', action='store_true', help='Saves a graph visualization of workflow.')
parser.add_argument('--target-labels', nargs='+', help='Runs the pipeline by target labels (example "TPC" or "DIGI").\
                    This condition is used as logical AND together with --target-tasks.', default=[])
parser.add_argument('-tt','--target-tasks', nargs='+', help='Runs the pipeline by target tasks (example "tpcdigi"). By default everything in the graph is run. Regular expressions supported.', default=["*"])
parser.add_argument('--produce-script', help='Produces a shell script that runs the workflow in serialized manner and quits.')
parser.add_argument('--rerun-from', help='Reruns the workflow starting from given task. All dependent jobs will be rerun.')
parser.add_argument('--list-tasks', help='Simply list all tasks by name and quit.', action='store_true')

parser.add_argument('--mem-limit', help='Set memory limit as scheduling constraint', default=max_system_mem)
parser.add_argument('--cpu-limit', help='Set CPU limit (core count)', default=8)
parser.add_argument('--cgroup', help='Execute pipeline under a given cgroup (e.g., 8coregrid) emulating resource constraints. This must exist and the tasks file must be writable to with the current user.')
args = parser.parse_args()
print (args)

if args.cgroup!=None:
    myPID=os.getpid()
    command="echo " + str(myPID) + " > /sys/fs/cgroup/cpuset/"+args.cgroup+"/tasks"
    logging.info("applying cgroups " + command)
    os.system(command)

logging.basicConfig(filename='pipeliner_runner.log', filemode='w', level=logging.DEBUG)
executor=WorkflowExecutor(args.workflowfile,jmax=args.maxjobs,args=args)
executor.execute()
