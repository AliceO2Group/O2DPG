#!/usr/bin/env python3

#
# A script producing the QC finalization workflow.
# If run as main, it will dump the workflow to the specified output file and tasks will not have dependencies.
# For example:
#   ${O2DPG_ROOT}/MC/bin/o2dpg_qc_finalization_workflow.py -o qc_workflow.json 


# The script can be also imported.
# In such case, one can use include_all_QC_finalization to get the QC finalization from within other workflow script.

import sys
import argparse
from os import environ, mkdir
from os.path import join, dirname, isdir

sys.path.append(join(dirname(__file__), '.', 'o2dpg_workflow_utils'))

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
def include_all_QC_finalization(ntimeframes, standalone, run, productionTag):

  stages = []
  def add_QC_finalization(taskName, qcConfigPath, needs=[]):
    if len(needs) == 0 and standalone == False:
      needs = [taskName + '_local' + str(tf) for tf in range(1, ntimeframes + 1)]
    task = createTask(name=taskName + '_finalize', needs=needs, cwd=qcdir, lab=["QC"], cpu=1, mem='2000')
    task['cmd'] = f'o2-qc --config {qcConfigPath} --remote-batch {taskName}.root' + \
                  f' --override-values "qc.config.Activity.number={run};qc.config.Activity.periodName={productionTag}"' + \
                  ' ' + getDPL_global_options()
    stages.append(task)


  # to be enabled once MFT Digits should be ran 5 times with different settings
  MFTDigitsQCneeds = []
  for flp in range(5):
    MFTDigitsQCneeds.extend(['mftDigitsQC'+str(flp)+'_local'+str(tf) for tf in range(1, ntimeframes + 1)])
  #
  add_QC_finalization('mftDigitsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/qc-mft-digit-0.json', MFTDigitsQCneeds)
  add_QC_finalization('mftClustersQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/qc-mft-cluster.json')
  add_QC_finalization('mftAsyncQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/qc-mft-async.json')
  add_QC_finalization('emcDigitsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/emc-digits-task.json')
  #add_QC_finalization('tpcTrackingQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tpc-qc-tracking-direct.json')
  add_QC_finalization('tpcStandardQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tpc-qc-standard-direct.json')
  add_QC_finalization('trdDigitsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/trd-digits-task.json')
  add_QC_finalization('vertexQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/vertexing-qc-direct-mc.json')
  add_QC_finalization('ITSTPCmatchQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/ITSTPCmatchedTracks_direct_MC.json')
  add_QC_finalization('TOFMatchQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tofMatchedTracks_ITSTPCTOF_TPCTOF_direct_MC.json')

  return stages


def main() -> int:
  
  parser = argparse.ArgumentParser(description='Create the ALICE QC finalization workflow')

  parser.add_argument('--noIPC',help='disable shared memory in DPL')
  parser.add_argument('-o',help='output workflow file', default='workflow.json')
  parser.add_argument('-run',help="Run number for this MC", default=300000)
  parser.add_argument('-productionTag',help="Production tag for this MC", default='unknown')

  args = parser.parse_args()
  print (args)

 # make sure O2DPG + O2 is loaded
  O2DPG_ROOT=environ.get('O2DPG_ROOT')
  O2_ROOT=environ.get('O2_ROOT')
  QUALITYCONTROL_ROOT=environ.get('QUALITYCONTROL_ROOT')

  if O2DPG_ROOT == None: 
    print('Error: This needs O2DPG loaded')

  if O2_ROOT == None: 
    print('Error: This needs O2 loaded')

  if QUALITYCONTROL_ROOT is None:
    print('Error: This needs QUALITYCONTROL_ROOT loaded')

  if not isdir(qcdir):
    mkdir(qcdir)

  workflow={}
  workflow['stages'] = include_all_QC_finalization(ntimeframes=1, standalone=True, run=args.run, productionTag=args.productionTag)
  
  dump_workflow(workflow["stages"], args.o)
  
  return 0


if __name__ == '__main__':
  sys.exit(main())
