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

#################################################################################
# THIS WILL BE REMOVED WHEN ALL SCRIPTS USING DEPRECATED ARGS HAVE BEEN UPDATED
ARGS_TO_BE_UPDATED = []
ARGS_X_CHECK_REQUIRED = []

def add_args_depr_new(parser, long_option, *args, **kwargs):
    """
    Add argument for deprecated and new style
    """
    arg_depr = f"-{long_option}"
    arg = f"--{long_option}"
    help = kwargs.get("help", None)
    if kwargs.pop("required", False):
        # Pop the required flag and handle that explicitely
        ARGS_X_CHECK_REQUIRED.append(long_option)
    parser.add_argument(arg, *args, **kwargs)
    if help:
        # Add the deprecation info to the help message
        kwargs["help"] = f"{help} (DEPRECATED, use {arg} instead)"
    # By adding both styles, they have the same destination so specifying either of them is enough
    parser.add_argument(arg_depr, *args, **kwargs)

    ARGS_TO_BE_UPDATED.append(long_option)

def check_usage_deprecated_args():
    """
    Explicit checks to handle deprecated arguments

    Issue a deprecation warning in case an "old-style" argument was used

    Exit if a required argument is missing.
    """
    argv = sys.argv
    has_deprecated = False
    required = ""
    for axcr in ARGS_X_CHECK_REQUIRED:
        if f"--{axcr}" not in argv and f"-{axcr}" not in argv:
            # First collect all required to issue a summarised error
            required += f"--{axcr}"
    for atbu in ARGS_TO_BE_UPDATED:
        if f"-{atbu}" in argv:
            has_deprecated = True
            print(f"\nDEPRECATION WARNING: Option -{atbu} will be deprecated, use --{atbu} instead\n")
    if required:
        # We can't continue since at least one required argument is missing
        print(f"o2dpg_sim_workflow.py: error: the following arguments are required: {required}")
        sys.exit(1)

    if has_deprecated:
        # Sleep to give the user the time to read the warnings
        time_sleep = 5
        print(f"There are deprecation warnings. Run with --help to see all deprecated arguments. For now, everything will work as before and it will continue in {time_sleep} seconds...")
        time.sleep(time_sleep)
#################################################################################


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
    if standalone:
      needs = []
    elif needs is None:
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
  add_QC_finalization('tofDigitsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tofdigits.json')
  add_QC_finalization('TOFMatchWithTRDQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/tofMatchedTracks_AllTypes_direct_MC.json')
  add_QC_finalization('ITSTrackSimTask', 'json://${O2DPG_ROOT}/MC/config/QC/json/its-mc-tracks-qc.json')
  add_QC_finalization('tofft0PIDQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/pidft0tof.json')
  add_QC_finalization('tofPIDQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/pidtof.json')
  add_QC_finalization('RecPointsQC', 'json://${O2DPG_ROOT}/MC/config/QC/json/ft0-reconstruction-config.json')
  
  # The list of QC Post-processing workflows
  add_QC_postprocessing('tofTrendingHits', 'json://${O2DPG_ROOT}/MC/config/QC/json/tof-trending-hits.json', [QC_finalize_name('tofDigitsQC')], runSpecific=False, prodSpecific=True)

  return stages


def main() -> int:
  
  parser = argparse.ArgumentParser(description='Create the ALICE QC finalization workflow')

  parser.add_argument('--noIPC',help='disable shared memory in DPL')
  parser.add_argument('-o',help='output workflow file', default='workflow.json')
  add_args_depr_new(parser, "run", type=int, help="Run number for this MC", default=300000)
  add_args_depr_new(parser, "productionTag",help="Production tag for this MC", default='unknown')

  args = parser.parse_args()
  print (args)

 # make sure O2DPG + O2 is loaded
  O2DPG_ROOT=environ.get('O2DPG_ROOT')
  O2_ROOT=environ.get('O2_ROOT')
  QUALITYCONTROL_ROOT=environ.get('QUALITYCONTROL_ROOT')

  if O2DPG_ROOT is None: 
    print('Error: This needs O2DPG loaded')

  if O2_ROOT is None: 
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
