#!/usr/bin/env python3

# This is a python script which analyses
# a report from a "fanotify" file access report
# convoluted with task information from an O2DPG MC workflow.
# The tool produces:
# - a json report
# - optionally a graphviz visualization of file and task dependencies

import argparse
import re
import json

try:
    from graphviz import Digraph
    havegraphviz=True
except ImportError:
    havegraphviz=False

parser = argparse.ArgumentParser(description='Produce O2DPG MC file dependency reports')

# the run-number of data taking or default if unanchored
parser.add_argument('--actionFile', type=str, help="O2DPG pipeline runner action file")
parser.add_argument('--monitorFile', type=str, help="monitoring file provided by fanotify tool. See O2DPG/UTILS/FileIOGraph.")
parser.add_argument('--basedir', default="/", type=str, help="O2DPG workflow dir")
parser.add_argument('--file-filters', nargs='+', default=[r'.*'], help="Filters (regular expressions) to select files (default all = '.*')")
parser.add_argument('--graphviz', type=str, help="Produce a graphviz plot")
parser.add_argument('-o','--output', type=str, help="Output JSON report")

args = parser.parse_args()

# what do we need to do
# (a) - parse action File for mapping of O2DPG task name to PID
# ---> fills pid_to_task + task_to_pid

# Define the pattern using regular expressions
pid_to_O2DPGtask = {}
O2DPGtask_to_pid = {}

pattern = re.compile(r'.*INFO Task (\d+).*:(\w+) finished with status 0')
# Open the action file and process each line
with open(args.actionFile, 'r') as file:
    for line in file:
        # Try to match the pattern in each line
        match = pattern.match(line)
        
        # If a match is found, extract the information
        if match:
            task_number = match.group(1)
            task_name = match.group(2)
            
            pid_to_O2DPGtask[task_number] = task_name
            O2DPGtask_to_pid[task_name] = task_number


# (b) - parse monitor file for mapping from files to processes and operation
# ---> fills the following structures:
task_reads = { tname : set() for tname in O2DPGtask_to_pid }
task_writes = { tname : set() for tname in O2DPGtask_to_pid }
file_written_task = {}
file_consumed_task = {}

pattern = re.compile(r'"?([^"]+)"?,((?:read|write)),(.*)')
basedir_pattern = re.compile("^" + args.basedir)
# neglecting some framework file names
file_exclude_filter = re.compile(r'(.*)\.log(.*)|(ccdb/log)|(.*)dpl-config\.json')

# construct user-filter regular expressions
file_filter_re = [ re.compile(l) for l in args.file_filters ]

with open(args.monitorFile, 'r') as file:
    for line in file:
        # Try to match the pattern in each line
        match = pattern.match(line)
        if match:
            file_name = match.group(1)
            mode = match.group(2)
            pids = match.group(3).split(";")

            # see if matches the workdir
            if not basedir_pattern.match(file_name):
                continue

            # remove basedir from file_name
            file_name = file_name.replace(args.basedir + '/', "./", 1)

            # implement file name filter
            if file_exclude_filter.match(file_name):
                continue

            # look if file matches one of the user provided filters
            file_matches = False
            for r in file_filter_re:
                if r.match(file_name):
                   file_matches = True
                   break

            if not file_matches:
                continue

            if file_consumed_task.get(file_name) == None:
                file_consumed_task[file_name] = set()
            if file_written_task.get(file_name) == None:
                file_written_task[file_name] = set()
                
            for p in pids:
                if p in pid_to_O2DPGtask:
                    task = pid_to_O2DPGtask.get(p)
                    if mode == 'read':
                       task_reads.get(task).add(file_name)
                       file_consumed_task[file_name].add(task)

                    if mode == 'write':
                       task_writes.get(task).add(file_name)
                       file_written_task[file_name].add(task)


# draws the graph of files and tasks
def draw_graph(graphviz_filename):
    if not havegraphviz:
        print('graphviz not installed, cannot draw workflow')
        return

    dot = Digraph(comment='O2DPG file - task network')
    
    ccdbfilter = re.compile('ccdb(.*)/snapshot.root')

    nametoindex={}
    index=0

    allfiles = set(file_written_task.keys()) | set(file_consumed_task.keys())
    normalfiles = [ s for s in allfiles if not ccdbfilter.match(s) ]
    ccdbfiles = [ (s, ccdbfilter.match(s).group(1)) for s in allfiles if ccdbfilter.match(s) ]

    with dot.subgraph(name='CCDB') as ccdbpartition:
        ccdbpartition.attr(color = 'blue')
        for f in ccdbfiles:
            nametoindex[f[0]] = index
            ccdbpartition.node(str(index), f[1], color = 'blue')
            index = index + 1

    with dot.subgraph(name='normal') as normalpartition:
        normalpartition.attr(color = 'black')
        for f in normalfiles:
            nametoindex[f] = index
            normalpartition.node(str(index), f, color = 'red')
            index = index + 1
        for t in O2DPGtask_to_pid:
            nametoindex[t] = index
            normalpartition.node(str(index), t, shape = 'box', color = 'green', style = 'filled' )
            index = index + 1

    # edges (arrows between files and tasks)
    for node in file_consumed_task:
        # node is a file (source)
        sourceindex = nametoindex[node]
        for task in file_consumed_task[node]:
            toindex = nametoindex[task]
            dot.edge(str(sourceindex), str(toindex))

    # edges (arrows between files and tasks)
    for node in file_written_task:
        # node is a file (target)
        toindex = nametoindex[node]
        for task in file_written_task[node]:
            sourceindex = nametoindex[task]
            dot.edge(str(sourceindex), str(toindex))

    dot.render(graphviz_filename, format='pdf')
    dot.render(graphviz_filename, format='gv')

def write_json_report(json_file_name):
  # produce a JSON report of file dependencies
  all_filenames = set(file_written_task.keys()) | set(file_consumed_task.keys())
  file_written_task_tr = [
   {
     "file" : k,
     "written_by" : list(file_written_task.get(k, [])),
     "read_by" : list(file_consumed_task.get(k, []))
   }
   for k in all_filenames
  ]
  
  tasks_output = [
   {
     "task" : t,
     "writes" : list(task_writes.get(t,[])),
     "reads" : list(task_reads.get(t,[]))
   }
   for t in O2DPGtask_to_pid
  ]

  # Write the dictionary to a JSON file
  with open(json_file_name, 'w') as json_file:
    json.dump({ "file_report" : file_written_task_tr, "task_report" : tasks_output }, json_file, indent=2)

if args.graphviz:
  draw_graph(args.graphviz)

if args.output:
  write_json_report(args.output)