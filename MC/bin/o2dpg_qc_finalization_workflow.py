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

from o2dpg_workflow_utils import createTask, dump_workflow, isActive

def getDPL_global_options(bigshm=False, noIPC=None):
   common="-b --run --driver-client-backend ws:// "
   if noIPC != None:
      return common + " --no-IPC "
   if bigshm:
      return common + " --shm-segment-size ${SHMSIZE:-50000000000} "
   else:
      return common


def QC_finalize_name(name):
  return name + "_finalize"

qcdir = "QC"
def include_all_QC_finalization(ntimeframes, standalone, run, productionTag):

  stages = []

  ## Adds a 'remote-batch' part of standard QC workflows
  # taskName     - name of the QC workflow, it should be the same as in the main workflow
  # qcConfigPath - path to the QC config file
  # needs        - a list of tasks to be finished first. By default, the function puts the 'local-batch' part of the QC workflow
  def add_QC_finalization(taskName, qcConfigPath, needs=None):
    if standalone == True:
      needs = []
    elif needs == None:
      needs = [taskName + '_local' + str(tf) for tf in range(1, ntimeframes + 1)]

    task = createTask(name=QC_finalize_name(taskName), needs=needs, cwd=qcdir, lab=["QC"], cpu=1, mem='2000')
    task['cmd'] = f'o2-qc --config {qcConfigPath} --remote-batch {taskName}.root' + \
                  f' --override-values "qc.config.Activity.number={run};qc.config.Activity.periodName={productionTag}"' + \
                  ' ' + getDPL_global_options()
    stages.append(task)

  ## Adds a postprocessing QC workflow
  # taskName     - name of the QC workflow
  # qcConfigPath - path to the QC config file
  # needs        - a list of tasks to be finished first. Usually it should include QC finalization tasks
  #                which produce objects needed for given post-processing
  # runSpecific  - if set as true, a concrete run number is put to the QC config,
  #                thus the post-processing should cover objects only for that run
  # prodSpecific - if set as true, a concrete production name is put to the config,
  #                thus the post-processing should cover objects only for that production
  def add_QC_postprocessing(taskName, qcConfigPath, needs, runSpecific, prodSpecific):
    task = createTask(name=taskName, needs=needs, cwd=qcdir, lab=["QC"], cpu=1, mem='2000')
    overrideValues = '--override-values "'
    overrideValues += f'qc.config.Activity.number={run};' if runSpecific else 'qc.config.Activity.number=0;'
    overrideValues += f'qc.config.Activity.periodName={productionTag}"' if prodSpecific else 'qc.config.Activity.periodName="'
    task['cmd'] = f'o2-qc --config {qcConfigPath} ' + \
                  overrideValues + ' ' + getDPL_global_options()
    stages.append(task)

  ## The list of remote-batch workflows (reading the merged QC tasks results, applying Checks, uploading them to QCDB)
  MFTDigitsQCneeds = []
  for flp in range(5):
    MFTDigitsQCneeds.extend(['mftDigitsQC'+str(flp)+'_local'+str(tf) for tf in range(1, ntimeframes + 1)])
  add_QC_finalization('mftDigitsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/mft-digits-0.json', MFTDigitsQCneeds)
  add_QC_finalization('mftClustersQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/mft-clusters.json')
  add_QC_finalization('mftTracksQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/mft-tracks.json')
  add_QC_finalization('emcRecoQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/emc-reco-tasks.json')
  add_QC_finalization('emcBCQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/emc-reco-tasks.json')
  #add_QC_finalization('tpcTrackingQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tpc-qc-tracking-direct.json')
  add_QC_finalization('tpcStandardQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tpc-qc-standard-direct.json')
  add_QC_finalization('trdDigitsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/trd-digits-task.json')
  add_QC_finalization('vertexQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/vertexing-qc-direct-mc.json')
  add_QC_finalization('ITSTPCmatchQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/ITSTPCmatchedTracks_direct_MC.json')
  add_QC_finalization('TOFMatchQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tofMatchedTracks_ITSTPCTOF_TPCTOF_direct_MC.json')
  add_QC_finalization('tofDigitsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tofdigits.json')
  add_QC_finalization('TOFMatchWithTRDQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tofMatchedTracks_AllTypes_direct_MC.json')
  add_QC_finalization('ITSTrackSimTask', 'json://${O2DPG_ROOT}/MC/config/QC/json/its-mc-tracks-qc.json')
  add_QC_finalization('ITSTracksClusters', 'json://${O2DPG_ROOT}/MC/config/QC/json/its-clusters-tracks-qc.json')
  if isActive('FT0') and isActive('TRD'):
     add_QC_finalization('tofft0PIDQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/pidft0tof.json')
  elif isActive('FT0'):
     add_QC_finalization('tofft0PIDQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/pidft0tofNoTRD.json')
  elif isActive('TRD'):
     add_QC_finalization('tofPIDQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/pidtof.json')
  else:
     add_QC_finalization('tofPIDQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/pidtofNoTRD.json')
  add_QC_finalization('RecPointsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/ft0-reconstruction-config.json')
  add_QC_finalization('CPVDigitsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/cpv-digits-task.json')
  add_QC_finalization('CPVClustersQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/cpv-clusters-task.json')
  add_QC_finalization('PHSCellsClustersQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/phs-cells-clusters-task.json')

  # The list of QC Post-processing workflows
  add_QC_postprocessing('tofTrendingHits', 'json://${O2DPG_ROOT}/MC/config/QC/json/tof-trending-hits.json', [QC_finalize_name('tofDigitsQC')], runSpecific=False, prodSpecific=True)

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
