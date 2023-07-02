#!/usr/bin/env python3

import sys
from os.path import dirname
import argparse
import re
from glob import glob
import json
import math

################################################################
#                                                              #
# Script to exctract CPU/MEM resource estimates from           #
# the log_time files left from the individual tasks            #
#                                                              #
# Outputs a json to be fed to the workflow runnner for dynamic #
# scheduling decisions.                                        #
################################################################

# helper function to find files
def find_files(path, search, depth=0):
  files = []
  for d in range(depth + 1):
    wildcards = "/*" * d
    path_search = path + wildcards + f"/{search}"
    files.extend(glob(path_search))
  return files

# this functions extracts the important metrics from a single resource file (left by O2 jobutils/taskwrapper)
def extract_time_single(path):
  r = {}
  with open(path, "r") as f:
    for l in f:
      if "walltime" in l:
        r["walltime"] = float(l.strip().split()[-1])
      elif "CPU" in l:
        r["cpu"] = float(l.strip().split()[-1].split('%')[0])
      elif "mem" in l:
        r["mem"] = float(l.strip().split()[-1])
  return r

def process(args):
  pipeline_dir = dirname(args.path)
  files = find_files(pipeline_dir, "*.log_time", 1)
  if not files:
      print(f"WARNING: Cannot find time logs in {pipeline_dir}.")
      return

  resource_accum = {} # accumulates resources per task name
  for f in files:
    # name from time log file
    name = f.split("/")[-1]
    name = re.sub("\.log_time$", "", name)
    name_notf = name.split("_")[0]
    resources = extract_time_single(f)
    resources["name"] = name
    resource_accum[name_notf] = resource_accum.get(name_notf,[])
    resource_accum[name_notf].append(resources)


  # finalizes metrics; average for CPU; max for MEM; average for walltime
  # returns final metric result suitable for output to json
  def finalize(resource_list):
    """
    input is map of lists of resource dictionaries
    output is map of final resource estimates
    """
    result = {}
    for task in resource_list:
      finalr = {"walltime": 0, "cpu" : 0, "mem" : 0}
      for r in resource_list[task]: # r is a resource estimate
        finalr["walltime"] += r["walltime"]
        finalr["mem"] = max(r["mem"], finalr["mem"])
        finalr["cpu"] += r["cpu"]
      finalr["walltime"] /= len(resource_list[task])
      finalr["cpu"] /= 100*len(resource_list[task]) # we take the number of CPUs not the percent
      finalr["mem"] /= 1024 # we'd like to have it in MB
      finalr["mem"] = math.ceil(finalr["mem"])
      result[task] = finalr
    return result

  estimate=finalize(resource_accum)
  print (estimate)

  # finally save to JSON
  with open(args.output, "w") as f:
     json.dump(estimate, f, indent=2)


def main():
  parser = argparse.ArgumentParser(description="Produce a O2DPG workflow resource file from existing time logs")
  parser.add_argument('-o','--output', help='Filename of output metric json file', default='learned_O2DPG_resource_metrics.json')
  parser.add_argument('-p','--path', help='Path to O2DPG workspace', default="./")
  args = parser.parse_args()
  process(args)

if __name__ == "__main__":
  sys.exit(main())
