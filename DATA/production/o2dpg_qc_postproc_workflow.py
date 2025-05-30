#!/usr/bin/env python3

#
# A script producing the QC finalization workflow.
# If run as main, it will dump the workflow to the specified output file and tasks will not have dependencies.
# For example:
#   ${O2DPG_ROOT}/DATA/production/o2dpg_qc_postproc_workflow.py -o qc_workflow.json


# The script can be also imported.
# In such case, one can use include_all_QC_finalization to get the QC finalization from within other workflow script.

import sys
import importlib.util
import argparse
from os import environ, mkdir
from os.path import join, dirname, isdir

# make sure O2DPG, O2 and QC are loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')
O2_ROOT=environ.get('O2_ROOT')
QUALITYCONTROL_ROOT=environ.get('QUALITYCONTROL_ROOT')

if O2DPG_ROOT == None: 
  print('Error: This needs O2DPG loaded')
  sys.exit(1)

if O2_ROOT == None: 
  print('Error: This needs O2 loaded')
  sys.exit(1)

if QUALITYCONTROL_ROOT is None:
  print('Error: This needs QUALITYCONTROL_ROOT loaded')
  sys.exit(1)

# dynamically import required utilities
module_name = "o2dpg_workflow_utils"
spec = importlib.util.spec_from_file_location(module_name, join(O2DPG_ROOT, "MC", "bin", "o2dpg_workflow_utils.py"))
o2dpg_workflow_utils = importlib.util.module_from_spec(spec)
sys.modules[module_name] = o2dpg_workflow_utils
spec.loader.exec_module(o2dpg_workflow_utils)
from o2dpg_workflow_utils import createTask, dump_workflow

def getDPL_global_options(bigshm=False, noIPC=None):
   common="-b --run --driver-client-backend ws:// "
   if noIPC != None:
      return common + " --no-IPC "
   if bigshm:
      return common + " --shm-segment-size ${SHMSIZE:-50000000000} "
   else:
      return common

qcdir = "QC"
def QC_postprocessing_workflow(runNumber, periodName, passName, qcdbUrl):

  stages = []

  ## Adds a postprocessing QC workflow
  # taskName       - name of the QC workflow
  # qcConfigPath   - path to the QC config file
  # needs          - a list of tasks to be finished before (e.g. if one post-processing workflow needs another to finish first)
  # runSpecific    - if set as true, a concrete run number is put to the QC config,
  #                  thus the post-processing should cover objects only for this run
  # periodSpecific - if set as true, a concrete period name is put to the config,
  #                  thus the post-processing should cover objects only for this period
  # passSpecific   - if set as true, a concrete pass name is put to the config,
  #                  thus the post-processing should cover objects only for this pass
  def add_QC_postprocessing(taskName, qcConfigPath, needs, runSpecific, periodSpecific, passSpecific):
    task = createTask(name=taskName, needs=needs, cwd=qcdir, lab=["QC"], cpu=1, mem='2000')
    overrideValues = '--override-values "'
    overrideValues += f'qc.config.database.host={qcdbUrl};'
    overrideValues += f'qc.config.Activity.type=PHYSICS;'
    overrideValues += f'qc.config.Activity.number={runNumber};' if runSpecific else 'qc.config.Activity.number=0;'
    overrideValues += f'qc.config.Activity.periodName={periodName};' if periodSpecific else 'qc.config.Activity.periodName=;'
    overrideValues += f'qc.config.Activity.passName={passName};' if passSpecific else 'qc.config.Activity.passName=;'
    overrideValues += '"'
    task['cmd'] = f'o2-qc --config {qcConfigPath} ' + overrideValues + ' ' + getDPL_global_options()
    stages.append(task)

  ## The list of QC Post-processing workflows, add the new ones below
  add_QC_postprocessing('example', 'json://${O2DPG_ROOT}/DATA/production/qc-postproc-async/example.json', needs=[], runSpecific=False, periodSpecific=True, passSpecific=True)
  add_QC_postprocessing('EMC', 'json://${O2DPG_ROOT}/DATA/production/qc-postproc-async/emc.json', needs=[], runSpecific=False, periodSpecific=True, passSpecific=True)
  add_QC_postprocessing('MCH', 'json://${O2DPG_ROOT}/DATA/production/qc-postproc-async/mch.json', needs=[], runSpecific=True, periodSpecific=True, passSpecific=True)
  add_QC_postprocessing('ZDC', 'json://${O2DPG_ROOT}/DATA/production/qc-postproc-async/zdc.json', needs=[], runSpecific=True, periodSpecific=True, passSpecific=True)

  return stages


def main() -> int:
  
  parser = argparse.ArgumentParser(description='Create the ALICE data QC postprocessing workflow')

  parser.add_argument('--noIPC',help='disable shared memory in DPL')
  parser.add_argument('-o',help='output workflow file', default='workflow.json')
  parser.add_argument('--run',help="Run number (0 for any", default=0)
  parser.add_argument('--periodName',help="Period name", default='')
  parser.add_argument('--passName',help="Pass name", default='')
  parser.add_argument('--qcdbUrl',help="Quality Control Database URL", default='ccdb-test.cern.ch:8080')

  args = parser.parse_args()
  print (args)

  if not isdir(qcdir):
    mkdir(qcdir)

  workflow={}
  workflow['stages'] = QC_postprocessing_workflow(runNumber=args.run, periodName=args.periodName, passName=args.passName, qcdbUrl=args.qcdbUrl)
  
  dump_workflow(workflow["stages"], args.o)
  
  return 0


if __name__ == '__main__':
  sys.exit(main())
