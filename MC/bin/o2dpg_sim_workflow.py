#!/usr/bin/env python3

#
# A script producing a consistent MC->RECO->AOD workflow
# It aims to handle the different MC possible configurations
# It just creates a workflow.json txt file, to execute the workflow one must execute right after
#   ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
#
# Execution examples:
#  - pp PYTHIA jets, 2 events, triggered on high pT decay photons on all barrel calorimeters acceptance, eCMS 13 TeV
#     ./o2dpg_sim_workflow.py -e TGeant3 -ns 2 -j 8 -tf 1 -mod "--skipModules ZDC" -col pp -eCM 13000 \
#                             -proc "jets" -ptHatBin 3 \
#                             -trigger "external" -ini "\$O2DPG_ROOT/MC/config/PWGGAJE/ini/trigger_decay_gamma_allcalo_TrigPt3_5.ini"
#
#  - pp PYTHIA ccbar events embedded into heavy-ion environment, 2 PYTHIA events into 1 bkg event, beams energy 2.510
#     ./o2dpg_sim_workflow.py -e TGeant3 -nb 1 -ns 2 -j 8 -tf 1 -mod "--skipModules ZDC"  \
#                             -col pp -eA 2.510 -proc "ccbar"  --embedding
#

import sys
import importlib.util
import argparse
from os import environ, mkdir
from os.path import join, dirname, isdir, isabs
import random
import json
import itertools
import requests, re
pandas_available = True
try:
    import pandas as pd
except (ImportError, ValueError):  # ARM architecture has problems with pandas + numpy
    pandas_available = False

sys.path.append(join(dirname(__file__), '.', 'o2dpg_workflow_utils'))

from o2dpg_workflow_utils import createTask, createGlobalInitTask, dump_workflow, adjust_RECO_environment, isActive, activate_detector, deactivate_detector, compute_n_workers
from o2dpg_qc_finalization_workflow import include_all_QC_finalization
from o2dpg_sim_config import create_sim_config, create_geant_config, constructConfigKeyArg

parser = argparse.ArgumentParser(description='Create an ALICE (Run3) MC simulation workflow')

# the run-number of data taking or default if unanchored
parser.add_argument('-run', type=int, help="Run number for this MC. See https://twiki.cern.ch/twiki/bin/view/ALICE/O2DPGMCSamplingSchema for possible pre-defined choices.", default=300000)
parser.add_argument('-productionTag',help="Production tag for this MC", default='unknown')
# the timestamp at which this MC workflow will be run
# - in principle it should be consistent with the time of the "run" number above
# - some external tool should sample it within
# - we can also sample it ourselfs here
parser.add_argument('--timestamp', type=int, help="Anchoring timestamp (defaults to now)", default=-1)
parser.add_argument('--conditionDB',help="CCDB url for QC workflows", default='http://alice-ccdb.cern.ch')
parser.add_argument('--qcdbHost',help="QCDB url for QC object uploading", default='http://ali-qcdbmc-gpn.cern.ch:8083')
parser.add_argument('--condition-not-after', type=int, help="only consider CCDB objects not created after this timestamp (for TimeMachine)", default=3385078236000)
parser.add_argument('--orbitsPerTF', type=int, help="Timeframe size in number of LHC orbits", default=128)
parser.add_argument('--anchor-config',help="JSON file to contextualise workflow with external configs (config values etc.) for instance comping from data reco workflows.", default='')
parser.add_argument('--dump-config',help="Dump JSON file with all settings used in workflow", default='user_config.json')
parser.add_argument('-ns',help='number of signal events / timeframe', default=20)
parser.add_argument('-gen',help='generator: pythia8, extgen', default='')
parser.add_argument('-proc',help='process type: inel, dirgamma, jets, ccbar, ...', default='none')
parser.add_argument('-trigger',help='event selection: particle, external', default='')
parser.add_argument('-ini',help='generator init parameters file (full paths required), for example: ${O2DPG_ROOT}/MC/config/PWGHF/ini/GeneratorHF.ini', default='')
parser.add_argument('-confKey',help='generator or trigger configuration key values, for example: "GeneratorPythia8.config=pythia8.cfg;A.x=y"', default='')
parser.add_argument('--readoutDets',help='comma separated string of detectors readout (does not modify material budget - only hit creation)', default='all')

parser.add_argument('-interactionRate',help='Interaction rate, used in digitization', default=-1)
parser.add_argument('-bcPatternFile',help='Bunch crossing pattern file, used in digitization (a file name or "ccdb")', default='')
parser.add_argument('-meanVertexPerRunTxtFile',help='Txt file with mean vertex settings per run', default='')
parser.add_argument('-eCM',help='CMS energy', default=-1)
parser.add_argument('-eA',help='Beam A energy', default=-1) #6369 PbPb, 2.510 pp 5 TeV, 4 pPb
parser.add_argument('-eB',help='Beam B energy', default=-1)
parser.add_argument('-col',help='collision system: pp, PbPb, pPb, Pbp, ..., in case of embedding collision system of signal', default='pp')
parser.add_argument('-field',help='L3 field rounded to kGauss, allowed values: +-2,+-5 and 0; +-5U for uniform field; or "ccdb" to take from conditions database', default='ccdb')
parser.add_argument('--with-qed',action='store_true', help='Enable QED background contribution (for PbPb always included)')

parser.add_argument('-ptHatMin',help='pT hard minimum when no bin requested', default=0)
parser.add_argument('-ptHatMax',help='pT hard maximum when no bin requested', default=-1)
parser.add_argument('-weightPow',help='Flatten pT hard spectrum with power', default=-1)

parser.add_argument('--embedding',action='store_true', help='With embedding into background')
parser.add_argument('--embeddPattern',help='How signal is to be injected into background', default='@0:e1')
parser.add_argument('-nb',help='number of background events / timeframe', default=20)
parser.add_argument('-genBkg',help='embedding background generator', default='') #pythia8, not recomended: pythia8hi, pythia8pp
parser.add_argument('-procBkg',help='process type: inel, ..., do not set it for Pythia8 PbPb', default='heavy_ion')
parser.add_argument('-iniBkg',help='embedding background generator init parameters file (full path required)', default='${O2DPG_ROOT}/MC/config/common/ini/basic.ini')
parser.add_argument('-confKeyBkg',help='embedding background configuration key values, for example: "GeneratorPythia8.config=pythia8bkg.cfg"', default='')
parser.add_argument('-colBkg',help='embedding background collision system', default='PbPb')

parser.add_argument('-e',help='simengine', default='TGeant4', choices=['TGeant4', 'TGeant3', 'TFluka'])
parser.add_argument('-tf',help='number of timeframes', default=2)
parser.add_argument('--production-offset',help='Offset determining bunch-crossing '
                     + ' range within a (GRID) production. This number sets first orbit to '
                     + 'Offset x Number of TimeFrames x OrbitsPerTimeframe (up for further sophistication)', default=0)
parser.add_argument('-j', '--n-workers', dest='n_workers', help='number of workers (if applicable)', default=8, type=int)
parser.add_argument('--force-n-workers', dest='force_n_workers', action='store_true', help='by default, number of workers is re-computed '
                                                                                           'for given interaction rate if --pregenCollContext is set; '
                                                                                           'pass this to avoid that')
parser.add_argument('-mod',help='Active modules (deprecated)', default='--skipModules ZDC')
parser.add_argument('--with-ZDC', action='store_true', help='Enable ZDC in workflow')
parser.add_argument('-seed',help='random seed number', default=None)
parser.add_argument('-o',help='output workflow file', default='workflow.json')
parser.add_argument('--noIPC',help='disable shared memory in DPL')

# arguments for background event caching
parser.add_argument('--upload-bkg-to',help='where to upload background event files (alien path)')
parser.add_argument('--use-bkg-from',help='take background event from given alien path')

# argument for early cleanup
parser.add_argument('--early-tf-cleanup',action='store_true', help='whether to cleanup intermediate artefacts after each timeframe is done')

# power features (for playing) --> does not appear in help message
#  help='Treat smaller sensors in a single digitization')
parser.add_argument('--pregenCollContext', action='store_true', help=argparse.SUPPRESS) # the mode where we pregenerate the collision context for each timeframe (experimental)
parser.add_argument('--no-combine-smaller-digi', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--no-combine-dpl-devices', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--no-mc-labels', action='store_true', default=False, help=argparse.SUPPRESS)
parser.add_argument('--no-tpc-digitchunking', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--no-strangeness-tracking', action='store_true', default=False, help="Disable strangeness tracking")
parser.add_argument('--combine-tpc-clusterization', action='store_true', help=argparse.SUPPRESS) #<--- useful for small productions (pp, low interaction rate, small number of events)
parser.add_argument('--first-orbit', default=0, type=int, help=argparse.SUPPRESS)  # to set the first orbit number of the run for HBFUtils (only used when anchoring)
                                                            # (consider doing this rather in O2 digitization code directly)
parser.add_argument('--sor', default=-1, type=int, help=argparse.SUPPRESS) # may pass start of run with this (otherwise it is autodetermined from run number)
parser.add_argument('--run-anchored', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--alternative-reco-software', default="", help=argparse.SUPPRESS) # power feature to set CVFMS alienv software version for reco steps (different from default)
parser.add_argument('--dpl-child-driver', default="", help="Child driver to use in DPL processes (expert mode)")
parser.add_argument('--event-gen-mode', choices=['separated', 'integrated'], default='separated', help="Whether event generation is done before (separated) or within detector simulation (integrated).")

# QC related arguments
parser.add_argument('--include-qc', '--include-full-qc', action='store_true', help='includes QC in the workflow, both per-tf processing and finalization')
parser.add_argument('--include-local-qc', action='store_true', help='includes the per-tf QC, but skips the finalization (e.g. to allow for subjob merging first)')

# O2 Analysis related arguments
parser.add_argument('--include-analysis', '--include-an', '--analysis',
                    action='store_true', help='a flag to include O2 analysis in the workflow')

# MFT reconstruction configuration
parser.add_argument('--mft-reco-full', action='store_true', help='enables complete mft reco instead of simplified misaligned version')
parser.add_argument('--mft-assessment-full', action='store_true', help='enables complete assessment of mft reco')

# TPC options
parser.add_argument('--tpc-distortion-type', default=0, type=int, help='Simulate distortions in the TPC (0=no distortions, 1=distortions without scaling, 2=distortions with CTP scaling)')
parser.add_argument('--ctp-scaler', default=0, type=float, help='CTP raw scaler value used for distortion simulation')
# Global Forward reconstruction configuration
parser.add_argument('--fwdmatching-assessment-full', action='store_true', help='enables complete assessment of global forward reco')
parser.add_argument('--fwdmatching-4-param', action='store_true', help='excludes q/pt from matching parameters')
parser.add_argument('--fwdmatching-cut-4-param', action='store_true', help='apply selection cuts on position and angular parameters')

# Matching training for machine learning
parser.add_argument('--fwdmatching-save-trainingdata', action='store_true', help='enables saving parameters at plane for matching training with machine learning')

args = parser.parse_args()
print (args)

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')
O2_ROOT=environ.get('O2_ROOT')
QUALITYCONTROL_ROOT=environ.get('QUALITYCONTROL_ROOT')
O2PHYSICS_ROOT=environ.get('O2PHYSICS_ROOT')

if O2DPG_ROOT == None:
   print('Error: This needs O2DPG loaded')
#   exit(1)

if O2_ROOT == None:
   print('Error: This needs O2 loaded')
#   exit(1)

if (args.include_qc or args.include_local_qc) and QUALITYCONTROL_ROOT is None:
   print('Error: Arguments --include-qc and --include-local-qc need QUALITYCONTROL_ROOT loaded')
#   exit(1)

if args.include_analysis and (QUALITYCONTROL_ROOT is None or O2PHYSICS_ROOT is None):
   print('Error: Argument --include-analysis needs O2PHYSICS_ROOT and QUALITYCONTROL_ROOT loaded')
#   exit(1)

module_name = "o2dpg_analysis_test_workflow"
spec = importlib.util.spec_from_file_location(module_name, join(O2DPG_ROOT, "MC", "analysis_testing", f"{module_name}.py"))
o2dpg_analysis_test_workflow = importlib.util.module_from_spec(spec)
sys.modules[module_name] = o2dpg_analysis_test_workflow
spec.loader.exec_module(o2dpg_analysis_test_workflow)

from o2dpg_analysis_test_workflow import add_analysis_tasks, add_analysis_qc_upload_tasks

# fetch an external configuration if given
# loads the workflow specification
def load_external_config(configfile):
    fp=open(configfile)
    config=json.load(fp)
    return config

anchorConfig = {}
if args.anchor_config != '':
   print ("** Using external config **")
   anchorConfig = load_external_config(args.anchor_config)
else:
   # we load a generic config
   print ("** Using generic config **")
   anchorConfig = create_sim_config(args)

# write this config
config_key_param_path = args.dump_config
with open(config_key_param_path, "w") as f:
   print(f"INFO: Written additional config key parameters to JSON {config_key_param_path}")
   json.dump(anchorConfig, f, indent=2)

def get_anchor_env_var(key, default):
   return anchorConfig.get('env_vars',{}).get(key, default)

# with this we can tailor the workflow to the presence of
# certain detectors
# these are all detectors that should be assumed active
readout_detectors = args.readoutDets
# here are all detectors that have been set in an anchored script
activeDetectors = anchorConfig.get('o2-ctf-reader-workflow-options',{}).get('onlyDet','all')
if activeDetectors == 'all':
    # if "all" here, there was in fact nothing in the anchored script, set to what is passed to this script (which it either also "all" or a subset)
    activeDetectors = readout_detectors
elif readout_detectors != 'all' and activeDetectors != 'all':
    # in this case both are comma-seperated lists. Take intersection
    r = set(readout_detectors.split(','))
    a = set(activeDetectors.split(','))
    activeDetectors = ','.join(r & a)
# the last case: simply take what comes from the anchored config

# convert to set/hashmap
activeDetectors = { det:1 for det in activeDetectors.split(',') }
for det in activeDetectors:
    activate_detector(det)

if not args.with_ZDC:
   # deactivate to be able to use isActive consistently for ZDC
   deactivate_detector('ZDC')
   if 'ZDC' in activeDetectors:
       del activeDetectors['ZDC']

def addWhenActive(detID, needslist, appendstring):
   if isActive(detID):
      needslist.append(appendstring)

def retrieve_sor(run_number):
    """
    retrieves start of run (sor)
    from the RCT/Info/RunInformation table with a simple http request
    in case of problems, 0 will be returned
    """
    url="http://alice-ccdb.cern.ch/browse/RCT/Info/RunInformation/"+str(run_number)
    ansobject=requests.get(url)
    tokens=ansobject.text.split("\n")

    SOR=0
    # extract SOR by pattern matching
    for t in tokens:
      match_object=re.match(r"\s*(SOR\s*=\s*)([0-9]*)\s*", t)
      if match_object != None:
         SOR=match_object[2]
         break

    return int(SOR)


# check and sanitize config-key values (extract and remove diamond vertex arguments into finalDiamondDict)
def extractVertexArgs(configKeyValuesStr, finalDiamondDict):
  # tokenize configKeyValueStr on ;
  tokens=configKeyValuesStr.split(';')
  for t in tokens:
    if "Diamond" in t:
      left, right = t.split("=")
      value = finalDiamondDict.get(left,None)
      if value == None:
        finalDiamondDict[left] = right
      else:
        # we have seen this before, check if consistent right hand side, otherwise crash
        if value != right:
          print("Inconsistent repetition in Diamond values; Aborting")
          sys.exit(1)

vertexDict = {}
extractVertexArgs(args.confKey, vertexDict)
extractVertexArgs(args.confKeyBkg, vertexDict)
CONFKEYMV=""
# rebuild vertex only config-key string
for e in vertexDict:
  if len(CONFKEYMV) > 0:
    CONFKEYMV+=';'
  CONFKEYMV+=str(e) + '=' + str(vertexDict[e])

print ("Diamond is " + CONFKEYMV)

# Recover mean vertex settings from external txt file
if (pandas_available):
  if  len(args.meanVertexPerRunTxtFile) > 0:
    if len(CONFKEYMV) > 0:
       print("confKey already sets diamond, stop!")
       sys.exit(1)
    df = pd.read_csv(args.meanVertexPerRunTxtFile, delimiter="\t", header=None) # for tabular
    df.columns = ["runNumber", "vx", "vy", "vz", "sx", "sy", "sz"]
    #print(df) # print full table
    MV_SX = float(df.loc[df['runNumber'].eq(args.run), 'sx'])
    MV_SY = float(df.loc[df['runNumber'].eq(args.run), 'sy'])
    MV_SZ = float(df.loc[df['runNumber'].eq(args.run), 'sz'])
    MV_VX = float(df.loc[df['runNumber'].eq(args.run), 'vx'])
    MV_VY = float(df.loc[df['runNumber'].eq(args.run), 'vy'])
    MV_VZ = float(df.loc[df['runNumber'].eq(args.run), 'vz'])
    print("** Using mean vertex parameters from file",args.meanVertexPerRunTxtFile,"for run =",args.run,
    ": \n \t vx =",MV_VX,", vy =",MV_VY,", vz =",MV_VZ,",\n \t sx =",MV_SX,", sy =",MV_SY,", sz =",MV_SZ)
    CONFKEYMV='Diamond.width[2]='+str(MV_SZ)+';Diamond.width[1]='+str(MV_SY)+';Diamond.width[0]='+str(MV_SX)+';Diamond.position[2]='+str(MV_VZ)+';Diamond.position[1]='+str(MV_VY)+';Diamond.position[0]='+str(MV_VX)+';'
    args.confKey=args.confKey + CONFKEYMV
    args.confKeyBkg=args.confKeyBkg + CONFKEYMV
    print("** confKey args + MeanVertex:",args.confKey)
else:
   print ("Pandas not available. Not reading mean vertex from external file")

# ----------- START WORKFLOW CONSTRUCTION -----------------------------

# set the time to start of run (if no timestamp specified)
if args.sor==-1:
   args.sor = retrieve_sor(args.run)
   assert (args.sor != 0)

if args.timestamp==-1:
   args.timestamp = args.sor

NTIMEFRAMES=int(args.tf)
NWORKERS=args.n_workers
MODULES = "--skipModules ZDC" if not isActive("ZDC") else ""
SIMENGINE=args.e
BFIELD=args.field
RNDSEED=args.seed # typically the argument should be the jobid, but if we get None the current time is used for the initialisation
random.seed(RNDSEED)
print ("Using initialisation seed: ", RNDSEED)
SIMSEED = random.randint(1, 900000000 - NTIMEFRAMES - 1) # PYTHIA maximum seed is 900M for some reason

workflow={}
workflow['stages'] = []

### setup global environment variables which are valid for all tasks
global_env = {'ALICEO2_CCDB_CONDITION_NOT_AFTER': args.condition_not_after} if args.condition_not_after else None
globalinittask = createGlobalInitTask(global_env)
globalinittask['cmd'] = 'o2-ccdb-cleansemaphores -p ${ALICEO2_CCDB_LOCALCACHE}'
workflow['stages'].append(globalinittask)
####

def getDPL_global_options(bigshm=False, ccdbbackend=True):
   common=" -b --run "
   if len(args.dpl_child_driver) > 0:
     common=common + ' --child-driver ' + str(args.dpl_child_driver)
   if ccdbbackend:
     common=common + " --condition-not-after " + str(args.condition_not_after)
   if args.noIPC!=None:
      return common + " --no-IPC "
   if bigshm:
      return common + " --shm-segment-size ${SHMSIZE:-50000000000} "
   else:
      return common

doembedding=True if args.embedding=='True' or args.embedding==True else False
usebkgcache=args.use_bkg_from!=None
includeFullQC=args.include_qc=='True' or args.include_qc==True
includeLocalQC=args.include_local_qc=='True' or args.include_local_qc==True
includeAnalysis = args.include_analysis

qcdir = "QC"
if (includeLocalQC or includeFullQC) and not isdir(qcdir):
    mkdir(qcdir)

# create/publish the GRPs and other GLO objects for consistent use further down the pipeline
orbitsPerTF=int(args.orbitsPerTF)
GRP_TASK = createTask(name='grpcreate', cpu='0')
GRP_TASK['cmd'] = 'o2-grp-simgrp-tool createGRPs --timestamp ' + str(args.timestamp) + ' --run ' + str(args.run) + ' --publishto ${ALICEO2_CCDB_LOCALCACHE:-.ccdb} -o grp --hbfpertf ' + str(orbitsPerTF) + ' --field ' + args.field
GRP_TASK['cmd'] += ' --readoutDets ' + " ".join(activeDetectors) + ' --print ' + ('','--lhcif-CCDB')[args.run_anchored]
if (not args.run_anchored == True) and len(args.bcPatternFile) > 0:
    GRP_TASK['cmd'] += '  --bcPatternFile ' + str(args.bcPatternFile)
if len(CONFKEYMV) > 0:
    # this is allowing the possibility to setup/use a different MeanVertex object than the one from CCDB
    GRP_TASK['cmd'] += ' --vertex Diamond --configKeyValues "' + CONFKEYMV + '"'

workflow['stages'].append(GRP_TASK)

if doembedding:
    if not usebkgcache:
        # ---- do background transport task -------
        NBKGEVENTS=args.nb
        GENBKG=args.genBkg
        if GENBKG =='':
           print('o2dpg_sim_workflow: Error! embedding background generator name not provided')
           exit(1)

        PROCESSBKG=args.procBkg
        COLTYPEBKG=args.colBkg
        ECMSBKG=float(args.eCM)
        EBEAMABKG=float(args.eA)
        EBEAMBBKG=float(args.eB)

        if COLTYPEBKG == 'pp':
           PDGABKG=2212 # proton
           PDGBBKG=2212 # proton

        if COLTYPEBKG == 'PbPb':
           PDGABKG=1000822080 # Pb
           PDGBBKG=1000822080 # Pb
           if ECMSBKG < 0:    # assign 5.02 TeV to Pb-Pb
              print('o2dpg_sim_workflow: Set BKG CM Energy to PbPb case 5.02 TeV')
              ECMSBKG=5020.0
           if GENBKG == 'pythia8' and PROCESSBKG != 'heavy_ion':
              PROCESSBKG = 'heavy_ion'
              print('o2dpg_sim_workflow: Process type not considered for Pythia8 PbPb')

        if COLTYPEBKG == 'pPb':
           PDGABKG=2212       # proton
           PDGBBKG=1000822080 # Pb

        if COLTYPEBKG == 'Pbp':
           PDGABKG=1000822080 # Pb
           PDGBBKG=2212       # proton

        # If not set previously, set beam energy B equal to A
        if EBEAMBBKG < 0 and ECMSBKG < 0:
           EBEAMBBKG=EBEAMABKG
           print('o2dpg_sim_workflow: Set beam energy same in A and B beams')
           if COLTYPEBKG=="pPb" or COLTYPEBKG=="Pbp":
              print('o2dpg_sim_workflow: Careful! both beam energies in bkg are the same')

        if ECMSBKG > 0:
           if COLTYPEBKG=="pPb" or COLTYPEBKG=="Pbp":
              print('o2dpg_sim_workflow: Careful! bkg ECM set for pPb/Pbp collisions!')

        if ECMSBKG < 0 and EBEAMABKG < 0 and EBEAMBBKG < 0:
           print('o2dpg_sim_workflow: Error! bkg ECM or Beam Energy not set!!!')
           exit(1)

        # Background PYTHIA configuration
        BKG_CONFIG_task=createTask(name='genbkgconf')
        BKG_CONFIG_task['cmd'] = 'echo "placeholder / dummy task"'
        if  GENBKG == 'pythia8':
            print('Background generator seed: ', SIMSEED)
            BKG_CONFIG_task['cmd'] = '${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
                                   --output=pythia8bkg.cfg                                     \
                                   --seed='+str(SIMSEED)+'                                     \
                                   --idA='+str(PDGABKG)+'                                      \
                                   --idB='+str(PDGBBKG)+'                                      \
                                   --eCM='+str(ECMSBKG)+'                                      \
                                   --eA='+str(EBEAMABKG)+'                                     \
                                   --eB='+str(EBEAMBBKG)+'                                     \
                                   --process='+str(PROCESSBKG)
            # if we configure pythia8 here --> we also need to adjust the configuration
            # TODO: we need a proper config container/manager so as to combine these local configs with external configs etc.
            args.confKeyBkg = 'GeneratorPythia8.config=pythia8bkg.cfg;' + args.confKeyBkg

        workflow['stages'].append(BKG_CONFIG_task)

        # background task configuration
        INIBKG=''
        if args.iniBkg!= '':
           INIBKG=' --configFile ' + args.iniBkg

        # determine final configKey values for background transport
        CONFKEYBKG = constructConfigKeyArg(create_geant_config(args, args.confKeyBkg))

        BKGtask=createTask(name='bkgsim', lab=["GEANT"], needs=[BKG_CONFIG_task['name'], GRP_TASK['name']], cpu=NWORKERS )
        BKGtask['cmd']='${O2_ROOT}/bin/o2-sim -e ' + SIMENGINE   + ' -j ' + str(NWORKERS) + ' -n '     + str(NBKGEVENTS) \
                     + ' -g  '      + str(GENBKG) + ' '    + str(MODULES)  + ' -o bkg ' + str(INIBKG)                    \
                     + ' --field ccdb ' + str(CONFKEYBKG)                                                                \
                     + ('',' --timestamp ' + str(args.timestamp))[args.timestamp!=-1] + ' --run ' + str(args.run)        \
                     + ' --vertexMode kCCDB'

        if not isActive('all'):
           BKGtask['cmd'] += ' --readoutDetectors ' + " ".join(activeDetectors)

        workflow['stages'].append(BKGtask)

        # check if we should upload background event
        if args.upload_bkg_to!=None:
            BKGuploadtask=createTask(name='bkgupload', needs=[BKGtask['name']], cpu='0')
            BKGuploadtask['cmd']='alien.py mkdir ' + args.upload_bkg_to + ';'
            BKGuploadtask['cmd']+='alien.py cp -f bkg* ' + args.upload_bkg_to + ';'
            workflow['stages'].append(BKGuploadtask)

    else:
        # here we are reusing existing background events from ALIEN

        # when using background caches, we have multiple smaller tasks
        # this split makes sense as they are needed at different stages
        # 1: --> download bkg_MCHeader.root + grp + geometry
        # 2: --> download bkg_Hit files (individually)
        # 3: --> download bkg_Kinematics
        # (A problem with individual copying might be higher error probability but
        #  we can introduce a "retry" feature in the copy process)

        # Step 1: header and link files
        BKG_HEADER_task=createTask(name='bkgdownloadheader', cpu='0', lab=['BKGCACHE'])
        BKG_HEADER_task['cmd']='alien.py cp ' + args.use_bkg_from + 'bkg_MCHeader.root .'
        BKG_HEADER_task['cmd']=BKG_HEADER_task['cmd'] + ';alien.py cp ' + args.use_bkg_from + 'bkg_geometry.root .'
        BKG_HEADER_task['cmd']=BKG_HEADER_task['cmd'] + ';alien.py cp ' + args.use_bkg_from + 'bkg_grp.root .'
        workflow['stages'].append(BKG_HEADER_task)

# a list of smaller sensors (used to construct digitization tasks in a parametrized way)
smallsensorlist = [ "ITS", "TOF", "FDD", "MCH", "MID", "MFT", "HMP", "PHS", "CPV", "ZDC" ]
# a list of detectors that serve as input for the trigger processor CTP --> these need to be processed together for now
ctp_trigger_inputlist = [ "FT0", "FV0", "EMC" ]

BKG_HITDOWNLOADER_TASKS={}
for det in [ 'TPC', 'TRD' ] + smallsensorlist + ctp_trigger_inputlist:
   if usebkgcache:
      BKG_HITDOWNLOADER_TASKS[det] = createTask(str(det) + 'hitdownload', cpu='0', lab=['BKGCACHE'])
      BKG_HITDOWNLOADER_TASKS[det]['cmd'] = 'alien.py cp ' + args.use_bkg_from + 'bkg_Hits' + str(det) + '.root .'
      workflow['stages'].append(BKG_HITDOWNLOADER_TASKS[det])
   else:
      BKG_HITDOWNLOADER_TASKS[det] = None

if usebkgcache:
   BKG_KINEDOWNLOADER_TASK = createTask(name='bkgkinedownload', cpu='0', lab=['BKGCACHE'])
   BKG_KINEDOWNLOADER_TASK['cmd'] = 'alien.py cp ' + args.use_bkg_from + 'bkg_Kine.root .'
   workflow['stages'].append(BKG_KINEDOWNLOADER_TASK)


# We download some binary files, necessary for processing
# Eventually, these files/objects should be queried directly from within these tasks?

# We download trivial TPC space charge corrections to be applied during
# reco. This is necessary to have consistency (decalibration and calibration) between digitization and reconstruction ... until digitization can
# also apply this effect via CCDB.
TPC_SPACECHARGE_DOWNLOADER_TASK = createTask(name='tpc_spacecharge_downloader', cpu='0')
TPC_SPACECHARGE_DOWNLOADER_TASK['cmd'] = '[ "${O2DPG_ENABLE_TPC_DISTORTIONS}" ] || { ${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch -p TPC/Calib/CorrectionMapRef --timestamp 1 --created-not-after ' + str(args.condition_not_after) + ' -d ${ALICEO2_CCDB_LOCALCACHE} ; ' \
   '${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch -p TPC/Calib/CorrectionMap --timestamp 1 --created-not-after ' + str(args.condition_not_after) + ' -d ${ALICEO2_CCDB_LOCALCACHE} ; }'
workflow['stages'].append(TPC_SPACECHARGE_DOWNLOADER_TASK)

# Fix (residual) geometry alignment for simulation stage
# Detectors that prefer to apply special alignments (for example residual effects) should be listed here and download these files.
# These object will take precedence over ordinary align objects **and** will only be applied in transport simulation
# and digitization (Det/Calib/Align is only read in simulation since reconstruction tasks use GLO/Config/AlignedGeometry automatically).
SIM_ALIGNMENT_PREFETCH_TASK = createTask(name='sim_alignment', cpu='0')
SIM_ALIGNMENT_PREFETCH_TASK['cmd'] = '${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch -p MID/MisCalib/Align --timestamp ' + str(args.timestamp) + ' --created-not-after '  \
                                      + str(args.condition_not_after) + ' -d ${ALICEO2_CCDB_LOCALCACHE}/MID/Calib/Align --no-preserve-path ; '
SIM_ALIGNMENT_PREFETCH_TASK['cmd'] += '${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch -p MCH/MisCalib/Align --timestamp ' + str(args.timestamp) + ' --created-not-after ' \
                                      + str(args.condition_not_after) + ' -d ${ALICEO2_CCDB_LOCALCACHE}/MCH/Calib/Align --no-preserve-path '
workflow['stages'].append(SIM_ALIGNMENT_PREFETCH_TASK)

# query initial configKey args for signal transport; mainly used to setup generators
simInitialConfigKeys = create_geant_config(args, args.confKey)

# loop over timeframes
for tf in range(1, NTIMEFRAMES + 1):
   TFSEED = SIMSEED + tf
   print("Timeframe " + str(tf) + " seed: ", TFSEED)

   timeframeworkdir='tf'+str(tf)

   # ----  transport task -------
   # function encapsulating the signal sim part
   # first argument is timeframe id
   ECMS=float(args.eCM)
   EBEAMA=float(args.eA)
   EBEAMB=float(args.eB)
   NSIGEVENTS=args.ns
   GENERATOR=args.gen
   if GENERATOR =='':
      print('o2dpg_sim_workflow: Error! generator name not provided')
      exit(1)

   INIFILE=''
   if args.ini!= '':
      INIFILE=' --configFile ' + args.ini
   PROCESS=args.proc
   TRIGGER=''
   if args.trigger != '':
      TRIGGER=' -t ' + args.trigger

   ## Pt Hat productions
   WEIGHTPOW=float(args.weightPow)
   PTHATMIN=float(args.ptHatMin)
   PTHATMAX=float(args.ptHatMax)

   # translate here collision type to PDG
   COLTYPE=args.col
   havePbPb = (COLTYPE == 'PbPb' or (doembedding and COLTYPEBKG == "PbPb"))

   if COLTYPE == 'pp':
      PDGA=2212 # proton
      PDGB=2212 # proton

   if COLTYPE == 'PbPb':
      PDGA=1000822080 # Pb
      PDGB=1000822080 # Pb
      if ECMS < 0:    # assign 5.02 TeV to Pb-Pb
         print('o2dpg_sim_workflow: Set CM Energy to PbPb case 5.02 TeV')
         ECMS=5020.0

   if COLTYPE == 'pPb':
      PDGA=2212       # proton
      PDGB=1000822080 # Pb

   if COLTYPE == 'Pbp':
      PDGA=1000822080 # Pb
      PDGB=2212       # proton

   # If not set previously, set beam energy B equal to A
   if EBEAMB < 0 and ECMS < 0:
      EBEAMB=EBEAMA
      print('o2dpg_sim_workflow: Set beam energy same in A and B beams')
      if COLTYPE=="pPb" or COLTYPE=="Pbp":
         print('o2dpg_sim_workflow: Careful! both beam energies are the same')

   if ECMS > 0:
      if COLTYPE=="pPb" or COLTYPE=="Pbp":
         print('o2dpg_sim_workflow: Careful! ECM set for pPb/Pbp collisions!')

   if ECMS < 0 and EBEAMA < 0 and EBEAMB < 0:
      print('o2dpg_sim_workflow: Error! CM or Beam Energy not set!!!')
      exit(1)

   # Determine interation rate
   signalprefix='sgn_' + str(tf)
   INTRATE=int(args.interactionRate)
   if INTRATE <= 0:
      print('o2dpg_sim_workflow: Error! Interaction rate not >0 !!!')
      exit(1)
   BCPATTERN=args.bcPatternFile
   includeQED = (COLTYPE == 'PbPb' or (doembedding and COLTYPEBKG == "PbPb")) or (args.with_qed == True)

   # preproduce the collision context
   precollneeds=[GRP_TASK['name']]
   NEventsQED=10000  # max number of QED events to simulate per timeframe
   PbPbXSec=8. # expected PbPb cross section
   QEDXSecExpected=35237.5  # expected magnitude of QED cross section
   PreCollContextTask=createTask(name='precollcontext_' + str(tf), needs=precollneeds, tf=tf, cwd=timeframeworkdir, cpu='1')
   PreCollContextTask['cmd']='${O2_ROOT}/bin/o2-steer-colcontexttool -i ' + signalprefix + ',' + str(INTRATE) + ',' + str(args.ns) + ':' + str(args.ns) + ' --show-context ' + ' --timeframeID ' + str(tf-1 + int(args.production_offset)*NTIMEFRAMES) + ' --orbitsPerTF ' + str(orbitsPerTF) + ' --orbits ' + str(orbitsPerTF) + ' --seed ' + str(TFSEED) + ' --noEmptyTF --first-orbit ' + str(args.first_orbit)
   PreCollContextTask['cmd'] += ' --bcPatternFile ccdb'  # <--- the object should have been set in (local) CCDB
   if includeQED:
      qedrate = INTRATE * QEDXSecExpected / PbPbXSec   # hadronic interaction rate * cross_section_ratio
      qedspec = 'qed_' + str(tf) + ',' + str(qedrate) + ',10000000:' + str(NEventsQED)
      PreCollContextTask['cmd'] += ' --QEDinteraction ' + qedspec
   workflow['stages'].append(PreCollContextTask)

   # produce QED background for PbPb collissions

   QEDdigiargs = ""
   if includeQED:
     NEventsQED=10000 # 35K for a full timeframe?
     qedneeds=[GRP_TASK['name']]
     if args.pregenCollContext == True:
       qedneeds.append(PreCollContextTask['name'])
     QED_task=createTask(name='qedsim_'+str(tf), needs=qedneeds, tf=tf, cwd=timeframeworkdir, cpu='1')
     ########################################################################################################
     #
     # ATTENTION: CHANGING THE PARAMETERS/CUTS HERE MIGHT INVALIDATE THE QED INTERACTION RATES USED ELSEWHERE
     #
     ########################################################################################################
     QED_task['cmd'] = 'o2-sim -e TGeant3 --field ccdb -j ' + str('1') +  ' -o qed_' + str(tf)                        \
                        + ' -n ' + str(NEventsQED) + ' -m PIPE ITS MFT FT0 FV0 FDD '                                  \
                        + ('', ' --timestamp ' + str(args.timestamp))[args.timestamp!=-1] + ' --run ' + str(args.run) \
                        + ' --seed ' + str(TFSEED)                                                                    \
                        + ' -g extgen --configKeyValues \"GeneratorExternal.fileName=$O2_ROOT/share/Generators/external/QEDLoader.C;QEDGenParam.yMin=-7;QEDGenParam.yMax=7;QEDGenParam.ptMin=0.001;QEDGenParam.ptMax=1.;Diamond.width[2]=6.\"'  # + (' ',' --fromCollContext collisioncontext.root')[args.pregenCollContext]
     QED_task['cmd'] += '; RC=$?; QEDXSecCheck=`grep xSectionQED qedgenparam.ini | sed \'s/xSectionQED=//\'`'
     QED_task['cmd'] += '; echo "CheckXSection ' + str(QEDXSecExpected) + ' = $QEDXSecCheck"; [[ ${RC} == 0 ]]'
     # TODO: propagate the Xsecion ratio dynamically
     QEDdigiargs=' --simPrefixQED qed_' + str(tf) +  ' --qed-x-section-ratio ' + str(QEDXSecExpected/PbPbXSec)
     workflow['stages'].append(QED_task)

   # recompute the number of workers to increase CPU efficiency
   NWORKERS_TF = compute_n_workers(INTRATE, COLTYPE) if (args.pregenCollContext and not args.force_n_workers) else NWORKERS

   # produce the signal configuration
   SGN_CONFIG_task=createTask(name='gensgnconf_'+str(tf), tf=tf, cwd=timeframeworkdir)
   SGN_CONFIG_task['cmd'] = 'echo "placeholder / dummy task"'
   if GENERATOR == 'pythia8':
      # see if config is given externally
      externalPythia8Config = simInitialConfigKeys.get("GeneratorPythia8", {}).get("config", None)
      if externalPythia8Config != None:
         # check if this refers to a file with ABSOLUTE path
         if not isabs(externalPythia8Config):
            print ('Error: Argument to GeneratorPythia8.config must be absolute path')
            exit (1)
         # in this case, we copy the external config to the local dir (maybe not even necessary)
         SGN_CONFIG_task['cmd'] = 'cp ' + externalPythia8Config + ' pythia8.cfg'
      else:
         SGN_CONFIG_task['cmd'] = '${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
                                  --output=pythia8.cfg                                      \
                                  --seed='+str(TFSEED)+'                                    \
                                  --idA='+str(PDGA)+'                                       \
                                  --idB='+str(PDGB)+'                                       \
                                  --eCM='+str(ECMS)+'                                       \
                                  --eA='+str(EBEAMA)+'                                      \
                                  --eB='+str(EBEAMB)+'                                      \
                                  --process='+str(PROCESS)+'                                \
                                  --ptHatMin='+str(PTHATMIN)+'                              \
                                  --ptHatMax='+str(PTHATMAX)
         if WEIGHTPOW   > 0:
            SGN_CONFIG_task['cmd'] = SGN_CONFIG_task['cmd'] + ' --weightPow=' + str(WEIGHTPOW)
      # if we configure pythia8 here --> we also need to adjust the configuration
      # TODO: we need a proper config container/manager so as to combine these local configs with external configs etc.
      args.confKey = args.confKey + ";GeneratorPythia8.config=pythia8.cfg"

   # elif GENERATOR == 'extgen': what do we do if generator is not pythia8?
       # NOTE: Generator setup might be handled in a different file or different files (one per
       # possible generator)

   workflow['stages'].append(SGN_CONFIG_task)

   # determine final conf key for signal simulation
   CONFKEY = constructConfigKeyArg(create_geant_config(args, args.confKey))
   # -----------------
   # transport signals
   # -----------------
   signalneeds=[ SGN_CONFIG_task['name'], GRP_TASK['name'] ]
   if (args.pregenCollContext == True):
      signalneeds.append(PreCollContextTask['name'])

   # add embedIntoFile only if embeddPattern does contain a '@'
   embeddinto= "--embedIntoFile ../bkg_MCHeader.root" if (doembedding & ("@" in args.embeddPattern)) else ""
   #embeddinto= "--embedIntoFile ../bkg_MCHeader.root" if doembedding else ""
   if doembedding:
       if not usebkgcache:
            signalneeds = signalneeds + [ BKGtask['name'] ]
       else:
            signalneeds = signalneeds + [ BKG_HEADER_task['name'] ]

   # (separate) event generation task
   sep_event_mode = args.event_gen_mode == 'separated'
   SGNGENtask=createTask(name='sgngen_'+str(tf), needs=signalneeds, tf=tf, cwd='tf'+str(tf), lab=["GEN"],
                         cpu=1, mem=1000)
   SGNGENtask['cmd']='${O2_ROOT}/bin/o2-sim --noGeant -j 1 --field ccdb --vertexMode kCCDB'           \
                     + ' --run ' + str(args.run) + ' ' + str(CONFKEY) + str(TRIGGER)                  \
                     + ' -g ' + str(GENERATOR) + ' ' + str(INIFILE) + ' -o genevents ' + embeddinto   \
                     + ('', ' --timestamp ' + str(args.timestamp))[args.timestamp!=-1]                \
                     + ' --seed ' + str(TFSEED) + ' -n ' + str(NSIGEVENTS)
   if args.pregenCollContext == True:
      SGNGENtask['cmd'] += ' --fromCollContext collisioncontext.root:' + signalprefix
   if sep_event_mode == True:
      workflow['stages'].append(SGNGENtask)
      signalneeds = signalneeds + [SGNGENtask['name']]

   sgnmem = 6000 if COLTYPE == 'PbPb' else 4000
   SGNtask=createTask(name='sgnsim_'+str(tf), needs=signalneeds, tf=tf, cwd='tf'+str(tf), lab=["GEANT"],
                      relative_cpu=7/8, n_workers=NWORKERS_TF, mem=str(sgnmem))
   sgncmdbase = '${O2_ROOT}/bin/o2-sim -e ' + str(SIMENGINE) + ' '  + str(MODULES) + ' -n ' + str(NSIGEVENTS) + ' --seed ' + str(TFSEED)       \
              + ' --field ccdb -j ' + str(NWORKERS_TF) + ' ' + str(CONFKEY) + ' ' + str(INIFILE) + ' -o ' + signalprefix + ' ' + embeddinto       \
              + ('', ' --timestamp ' + str(args.timestamp))[args.timestamp!=-1] + ' --run ' + str(args.run)
   if sep_event_mode:
      SGNtask['cmd'] = sgncmdbase + ' -g extkinO2 --extKinFile genevents_Kine.root ' + ' --vertexMode kNoVertex'
   else:
      SGNtask['cmd'] = sgncmdbase + ' -g ' + str(GENERATOR) + ' ' + str(TRIGGER) + ' --vertexMode kCCDB '
   if not isActive('all'):
      SGNtask['cmd'] += ' --readoutDetectors ' + " ".join(activeDetectors)
   if args.pregenCollContext == True:
      SGNtask['cmd'] += ' --fromCollContext collisioncontext.root'

   workflow['stages'].append(SGNtask)

   # some tasks further below still want geometry + grp in fixed names, so we provide it here
   # Alternatively, since we have timeframe isolation, we could just work with standard o2sim_ files
   # We need to be careful here and distinguish between embedding and non-embedding cases
   # (otherwise it can confuse itstpcmatching, see O2-2026). This is because only one of the GRPs is updated during digitization.
   if doembedding:
      LinkGRPFileTask=createTask(name='linkGRP_'+str(tf), needs=[BKG_HEADER_task['name'] if usebkgcache else BKGtask['name'] ], tf=tf, cwd=timeframeworkdir, cpu='0',mem='0')
      LinkGRPFileTask['cmd']='''
                             ln -nsf ../bkg_grp.root o2sim_grp.root;
                             ln -nsf ../bkg_grpecs.root o2sim_grpecs.root;
                             ln -nsf ../bkg_geometry.root o2sim_geometry.root;
                             ln -nsf ../bkg_geometry.root bkg_geometry.root;
                             ln -nsf ../bkg_geometry-aligned.root bkg_geometry-aligned.root;
                             ln -nsf ../bkg_geometry-aligned.root o2sim_geometry-aligned.root;
                             ln -nsf ../bkg_MCHeader.root bkg_MCHeader.root;
                             ln -nsf ../bkg_grp.root bkg_grp.root;
                             ln -nsf ../bkg_grpecs.root bkg_grpecs.root
                             '''
   else:
      LinkGRPFileTask=createTask(name='linkGRP_'+str(tf), needs=[SGNtask['name']], tf=tf, cwd=timeframeworkdir, cpu='0', mem='0')
      LinkGRPFileTask['cmd']='ln -nsf ' + signalprefix + '_grp.root o2sim_grp.root ; ln -nsf ' + signalprefix + '_geometry.root o2sim_geometry.root; ln -nsf ' + signalprefix + '_geometry-aligned.root o2sim_geometry-aligned.root'
   workflow['stages'].append(LinkGRPFileTask)

   # ------------------
   # digitization steps
   # ------------------
   CONTEXTFILE='collisioncontext.root'

   # Determine interation rate
   # it should be taken from CDB, meanwhile some default values
   INTRATE=int(args.interactionRate)
   BCPATTERN=args.bcPatternFile

   # in case of embedding take intended bkg collision type not the signal
   COLTYPEIR=COLTYPE
   if doembedding:
      COLTYPEIR=args.colBkg

   if INTRATE < 0:
      if   COLTYPEIR=="PbPb":
         INTRATE=50000 #Hz
      elif COLTYPEIR=="pp":
         INTRATE=500000 #Hz
      else: #pPb?
         INTRATE=200000 #Hz ???

   # TOF -> "--use-ccdb-tof" (alternatively with CCCDBManager "--ccdb-tof-sa")
   simsoption=' --sims ' + ('bkg,'+signalprefix if doembedding else signalprefix)

   # each timeframe should be done for a different bunch crossing range, depending on the timeframe id
   startOrbit = (tf-1 + int(args.production_offset)*NTIMEFRAMES)*orbitsPerTF
   globalTFConfigValues = { "HBFUtils.orbitFirstSampled" : args.first_orbit + startOrbit,
                            "HBFUtils.nHBFPerTF" : orbitsPerTF,
                            "HBFUtils.orbitFirst" : args.first_orbit,
                            "HBFUtils.runNumber" : args.run }
   # we set the timestamp here only if specified explicitely (otherwise it will come from
   # the simulation GRP and digitization)
   if (args.sor != -1):
      globalTFConfigValues["HBFUtils.startTime"] = args.sor

   def putConfigValues(localCF = {}):
     """
     Creates the final --configValues string to be passed to the workflows.
     Uses the globalTFConfigValues and merges/overrides them with the local settings.
     localCF is supposed to be a dictionary mapping key to param
     """
     returnstring = ' --configKeyValues "'
     cf = globalTFConfigValues.copy()
     isfirst=True
     for e in localCF:
       cf[e] = localCF[e]

     for e in cf:
       returnstring += (';','')[isfirst] + str(e) + "=" + str(cf[e])
       isfirst=False

     returnstring = returnstring + '"'
     return returnstring

   def putConfigValuesNew(listOfMainKeys=[], localCF = {}):
     """
     Creates the final --configValues string to be passed to the workflows.
     Uses the globalTFConfigValues and applies other parameters on top
     listOfMainKeys : list of keys to be applied from the global configuration object
     localCF: a dictionary mapping key to param - possibly overrides settings taken from global config
     """
     returnstring = ' --configKeyValues "'
     cf = globalTFConfigValues.copy()
     isfirst=True

     # now bring in the relevant keys
     # from the external config
     for key in listOfMainKeys:
       # it this key exists
       keydict = anchorConfig.get(key)
       if keydict != None:
          for k in keydict:
             cf[key+"."+k] = keydict[k]

     # apply overrides
     for e in localCF:
       cf[e] = localCF[e]

     for e in cf:
       returnstring += (';','')[isfirst] + str(e) + "=" + str(cf[e])
       isfirst=False

     returnstring = returnstring + '"'
     return returnstring

   # parsing passName from env variable
   PASSNAME='${ALIEN_JDL_LPMANCHORPASSNAME:-unanchored}'

   # This task creates the basic setup for all digitizers! all digitization configKeyValues need to be given here
   contextneeds = [LinkGRPFileTask['name'], SGNtask['name']]
   if includeQED:
     contextneeds += [QED_task['name']]
   ContextTask = createTask(name='digicontext_'+str(tf), needs=contextneeds, tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu='1')
   # this is just to have the digitizer ini file
   ContextTask['cmd'] = '${O2_ROOT}/bin/o2-sim-digitizer-workflow --only-context --interactionRate ' + str(INTRATE) \
                        + ' ' + getDPL_global_options(ccdbbackend=False) + ' -n ' + str(args.ns) + simsoption       \
                        + ' --seed ' + str(TFSEED)                                                                  \
                        + ' ' + putConfigValuesNew({"DigiParams.maxOrbitsToDigitize" : str(orbitsPerTF)},{"DigiParams.passName" : str(PASSNAME)}) + ('',' --incontext ' + CONTEXTFILE)[args.pregenCollContext] + QEDdigiargs
   ContextTask['cmd'] += ' --bcPatternFile ccdb'

   # in case of embedding we engineer the context directly and allow the user to provide an embedding pattern
   # The :r flag means to shuffle the background events randomly
   if doembedding:
      ContextTask['cmd'] += ';ln -nfs ../bkg_Kine.root .;${O2_ROOT}/bin/o2-steer-colcontexttool -i bkg,' + str(INTRATE) + ',' + str(args.ns) + ':' + str(args.nb) + ' ' + signalprefix + ',' + args.embeddPattern + ' --show-context ' + ' --timeframeID ' + str(tf-1 + int(args.production_offset)*NTIMEFRAMES) + ' --orbitsPerTF ' + str(orbitsPerTF) + ' --use-existing-kine'
      ContextTask['cmd'] += ' --bcPatternFile ccdb --seed ' + str(TFSEED) + ' --orbits ' + str(orbitsPerTF) + ' --noEmptyTF --first-orbit ' + str(args.first_orbit)

   workflow['stages'].append(ContextTask)

   # ===| TPC digi part |===
   CTPSCALER = args.ctp_scaler
   tpcDistortionType=args.tpc_distortion_type
   print(f"TPC distortion simulation: type = {tpcDistortionType}, CTP scaler value {CTPSCALER}");
   tpcdigineeds=[ContextTask['name'], LinkGRPFileTask['name'], TPC_SPACECHARGE_DOWNLOADER_TASK['name']]
   if usebkgcache:
      tpcdigineeds += [ BKG_HITDOWNLOADER_TASKS['TPC']['name'] ]

   tpcLocalCF={"DigiParams.maxOrbitsToDigitize" : str(orbitsPerTF), "DigiParams.seed" : str(TFSEED)}

   # handle distortions and scaling using MC maps
   # this assumes the lumi inside the maps is stored in FT0 (pp) scalers
   # in case of PbPb the conversion factor ZDC ->FT0 (pp) must be taken into account in the scalers
   if tpcDistortionType == 2 and CTPSCALER <= 0:
       print('Warning: lumi scaling requested, but no ctp scaler value set. Full map will be applied at face value.')
       tpcDistortionType=1

   lumiInstFactor=1
   if COLTYPE == 'PbPb':
      lumiInstFactor=2.414

   if tpcDistortionType == 2:
      tpcLocalCF['TPCCorrMap.lumiInst'] = str(CTPSCALER * lumiInstFactor)
   tpcdigimem = 12000 if havePbPb else 9000
   TPCDigitask=createTask(name='tpcdigi_'+str(tf), needs=tpcdigineeds,
                          tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu=NWORKERS_TF, mem=str(tpcdigimem))
   TPCDigitask['cmd'] = ('','ln -nfs ../bkg_HitsTPC.root . ;')[doembedding]
   TPCDigitask['cmd'] += '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption       \
                         + ' --onlyDet TPC --TPCuseCCDB --interactionRate ' + str(INTRATE) + '  --tpc-lanes ' + str(NWORKERS_TF)             \
                         + ' --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini --early-forward-policy always --forceSelectedDets ' \
                         + ' --tpc-distortion-type ' + str(tpcDistortionType)                                                             \
                         + putConfigValuesNew(["TPCGasParam","TPCGEMParam","TPCEleParam","TPCITCorr","TPCDetParam"],
                                              localCF=tpcLocalCF)
   TPCDigitask['cmd'] += (' --tpc-chunked-writer','')[args.no_tpc_digitchunking]
   TPCDigitask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   # we add any other extra command line options (power user customization) with an environment variable
   if environ.get('O2DPG_TPC_DIGIT_EXTRA') != None:
      TPCDigitask['cmd'] += ' ' + environ['O2DPG_TPC_DIGIT_EXTRA']
   workflow['stages'].append(TPCDigitask)
   # END TPC digi part

   trddigineeds = [ContextTask['name']]
   if usebkgcache:
      trddigineeds += [ BKG_HITDOWNLOADER_TASKS['TRD']['name'] ]
   TRDDigitask=createTask(name='trddigi_'+str(tf), needs=trddigineeds,
                          tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu=NWORKERS_TF, mem='8000')
   TRDDigitask['cmd'] = ('','ln -nfs ../bkg_HitsTRD.root . ;')[doembedding]
   TRDDigitask['cmd'] += '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption         \
                         + ' --onlyDet TRD --interactionRate ' + str(INTRATE) + ' --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini' \
                         + putConfigValuesNew(localCF={"TRDSimParams.digithreads" : NWORKERS_TF, "DigiParams.seed" : str(TFSEED)}) + " --forceSelectedDets"
   TRDDigitask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(TRDDigitask)

   # these are digitizers which are single threaded
   def createRestDigiTask(name, det='ALLSMALLER'):
      tneeds =[ContextTask['name']]
      if includeQED == True:
        tneeds += [QED_task['name']]
      commondigicmd = '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption \
                      + ' --interactionRate ' + str(INTRATE) + '  --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini'      \
                      + putConfigValuesNew(["MFTAlpideParam", "ITSAlpideParam", "ITSDigitizerParam"],
                                           localCF={"DigiParams.seed" : str(TFSEED), "MCHDigitizer.seed" : str(TFSEED)}) + QEDdigiargs

      if det=='ALLSMALLER': # here we combine all smaller digits in one DPL workflow
         if usebkgcache:
            for d in itertools.chain(smallsensorlist, ctp_trigger_inputlist):
               tneeds += [ BKG_HITDOWNLOADER_TASKS[d]['name'] ]
         t = createTask(name=name, needs=tneeds,
                        tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
         t['cmd'] = ('','ln -nfs ../bkg_Hits*.root . ;')[doembedding]
         detlist = ''
         detlist = ','.join(smallsensorlist)
         t['cmd'] += commondigicmd + ' --onlyDet ' + detlist
         t['cmd'] += ' --ccdb-tof-sa --forceSelectedDets '
         t['cmd'] += (' --combine-devices ','')[args.no_combine_dpl_devices]
         t['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
         workflow['stages'].append(t)
         return t

      else: # here we create individual digitizers
         if usebkgcache:
           tneeds += [ BKG_HITDOWNLOADER_TASKS[det]['name'] ]
         t = createTask(name=name, needs=tneeds, tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
         t['cmd'] = ('','ln -nfs ../bkg_Hits' + str(det) + '.root . ;')[doembedding]
         t['cmd'] += commondigicmd + ' --onlyDet ' + str(det)
         t['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
         if det == 'TOF':
            t['cmd'] += ' --ccdb-tof-sa'
         workflow['stages'].append(t)
         return t

   det_to_digitask={}

   if not args.no_combine_smaller_digi==True:
      det_to_digitask['ALLSMALLER']=createRestDigiTask("restdigi_"+str(tf))

   for det in smallsensorlist:
      name=str(det).lower() + "digi_" + str(tf)
      t = det_to_digitask['ALLSMALLER'] if (not args.no_combine_smaller_digi==True) else createRestDigiTask(name, det)
      det_to_digitask[det]=t

   # detectors serving CTP need to be treated somewhat special since CTP needs
   # these inputs at the same time --> still need to be made better
   tneeds = [ContextTask['name']]
   if includeQED:
     tneeds += [QED_task['name']]
   FT0FV0EMCCTPDIGItask = createTask(name="ft0fv0emcctp_digi_" + str(tf), needs=tneeds,
                  tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
   FT0FV0EMCCTPDIGItask['cmd'] = ('','ln -nfs ../bkg_HitsFT0.root . ; ln -nfs ../bkg_HitsFV0.root . ;')[doembedding]
   FT0FV0EMCCTPDIGItask['cmd'] += '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption \
               + ' --onlyDet FT0,FV0,EMC,CTP  --interactionRate ' + str(INTRATE) + '  --incontext ' + str(CONTEXTFILE)    \
               + ' --disable-write-ini' + putConfigValuesNew(localCF={"DigiParams.seed" : str(TFSEED)})                   \
               + (' --combine-devices','')[args.no_combine_dpl_devices] + ('',' --disable-mc')[args.no_mc_labels] + QEDdigiargs \
               + ' --forceSelectedDets'
   workflow['stages'].append(FT0FV0EMCCTPDIGItask)
   det_to_digitask["FT0"]=FT0FV0EMCCTPDIGItask
   det_to_digitask["FV0"]=FT0FV0EMCCTPDIGItask
   det_to_digitask["EMC"]=FT0FV0EMCCTPDIGItask
   det_to_digitask["CTP"]=FT0FV0EMCCTPDIGItask

   def getDigiTaskName(det):
      t = det_to_digitask.get(det)
      if t == None:
         return "undefined"
      return t['name']

   # -----------
   # reco
   # -----------
   tpcreconeeds=[FT0FV0EMCCTPDIGItask['name']]
   if not args.combine_tpc_clusterization:
     # We treat TPC clusterization in multiple (sector) steps in order to
     # stay within the memory limit or to parallelize over sector from outside (not yet supported within cluster algo)
     tpcclustertasks=[]
     sectorpertask=18
     for s in range(0,35,sectorpertask):
       taskname = 'tpcclusterpart' + str((int)(s/sectorpertask)) + '_' + str(tf)
       tpcclustertasks.append(taskname)
       tpcclussect = createTask(name=taskname, needs=[TPCDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='2', mem='8000')
       digitmergerstr = '${O2_ROOT}/bin/o2-tpc-chunkeddigit-merger --tpc-sectors ' + str(s)+'-'+str(s+sectorpertask-1) + ' --tpc-lanes ' + str(NWORKERS_TF) + ' | '
       tpcclussect['cmd'] = (digitmergerstr,'')[args.no_tpc_digitchunking] + ' ${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True) + ' --input-type ' + ('digitizer','digits')[args.no_tpc_digitchunking] + ' --output-type clusters,send-clusters-per-sector --tpc-native-cluster-writer \" --outfile tpc-native-clusters-part'+ str((int)(s/sectorpertask)) + '.root\" --tpc-sectors ' + str(s)+'-'+str(s+sectorpertask-1) + ' ' + putConfigValuesNew(["GPU_global"], {"GPU_proc.ompThreads" : 4}) + ('',' --disable-mc')[args.no_mc_labels]
       tpcclussect['env'] = { "OMP_NUM_THREADS" : "4", "SHMSIZE" : "16000000000" }
       tpcclussect['semaphore'] = "tpctriggers.root"
       tpcclussect['retry_count'] = 2  # the task has a race condition --> makes sense to retry
       workflow['stages'].append(tpcclussect)

     TPCCLUSMERGEtask=createTask(name='tpcclustermerge_'+str(tf), needs=tpcclustertasks, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='10000')
     TPCCLUSMERGEtask['cmd']='${O2_ROOT}/bin/o2-commonutils-treemergertool -i tpc-native-clusters-part*.root -o tpc-native-clusters.root -t tpcrec' #--asfriend preferable but does not work
     workflow['stages'].append(TPCCLUSMERGEtask)
     tpcreconeeds.append(TPCCLUSMERGEtask['name'])
   else:
     tpcclus = createTask(name='tpccluster_' + str(tf), needs=[TPCDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=NWORKERS_TF, mem='2000')
     tpcclus['cmd'] = '${O2_ROOT}/bin/o2-tpc-chunkeddigit-merger --tpc-lanes ' + str(NWORKERS_TF)
     tpcclus['cmd'] += ' | ${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options() + ' --input-type digitizer --output-type clusters,send-clusters-per-sector ' + putConfigValuesNew(["GPU_global","TPCGasParam","TPCCorrMap"],{"GPU_proc.ompThreads" : 1}) + ('',' --disable-mc')[args.no_mc_labels]
     workflow['stages'].append(tpcclus)
     tpcreconeeds.append(tpcclus['name'])

   # ===| TPC reco |===
   tpcLocalCFreco=dict()

   # handle distortion corrections and scaling using MC maps
   # this assumes the lumi inside the maps is stored in FT0 (pp) scalers
   # in case of PbPb the conversion factor ZDC ->FT0 (pp) must be set
   tpc_corr_options_mc=''

   if tpcDistortionType == 0: # disable distortion corrections
      tpc_corr_options_mc=' --corrmap-lumi-mode 0 '
      tpcLocalCFreco['TPCCorrMap.lumiMean'] = '-1';
   elif tpcDistortionType == 1: # disable scaling
      tpc_corr_options_mc=' --corrmap-lumi-mode 2 '
      tpcLocalCFreco['TPCCorrMap.lumiInst'] = str(CTPSCALER)
      tpcLocalCFreco['TPCCorrMap.lumiMean'] = str(CTPSCALER)
   elif tpcDistortionType == 2: # full scaling with CTP values
      if COLTYPE == 'PbPb':
         tpcLocalCFreco['TPCCorrMap.lumiInstFactor'] = str(lumiInstFactor)
      tpc_corr_options_mc=' --corrmap-lumi-mode 2 '
      tpcLocalCFreco['TPCCorrMap.lumiInst'] = str(CTPSCALER)

   # TODO: Is this still used?
   tpc_corr_scaling_options = anchorConfig.get('tpc-corr-scaling','')
   TPCRECOtask=createTask(name='tpcreco_'+str(tf), needs=tpcreconeeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], relative_cpu=3/8, mem='16000')
   TPCRECOtask['cmd'] = '${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True) + ' --input-type clusters --output-type tracks,send-clusters-per-sector ' \
                        + putConfigValuesNew(["GPU_global","TPCGasParam", "TPCCorrMap", "GPU_rec_tpc", "trackTuneParams"], {"GPU_proc.ompThreads":NWORKERS_TF} | tpcLocalCFreco) + ('',' --disable-mc')[args.no_mc_labels] \
                        + tpc_corr_scaling_options + tpc_corr_options_mc
   workflow['stages'].append(TPCRECOtask)

   # END TPC reco

   ITSMemEstimate = 12000 if havePbPb else 2000 # PbPb has much large mem requirement for now (in worst case)
   ITSRECOtask=createTask(name='itsreco_'+str(tf), needs=[getDigiTaskName("ITS")],
                          tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem=str(ITSMemEstimate))
   ITSRECOtask['cmd'] = '${O2_ROOT}/bin/o2-its-reco-workflow --trackerCA --tracking-mode async ' + getDPL_global_options(bigshm=havePbPb) \
                        + putConfigValuesNew(["ITSVertexerParam", "ITSAlpideParam",
                                              "ITSClustererParam", "ITSCATrackerParam"], {"NameConf.mDirMatLUT" : ".."})
   ITSRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(ITSRECOtask)

   FT0RECOtask=createTask(name='ft0reco_'+str(tf), needs=[getDigiTaskName("FT0")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   # note: when calibrations (or CCDB objects) are reenabled, we need to say ccdbbackend=True
   FT0RECOtask['cmd'] = '${O2_ROOT}/bin/o2-ft0-reco-workflow --disable-time-offset-calib --disable-slewing-calib ' + getDPL_global_options(ccdbbackend=False) + putConfigValues()
   workflow['stages'].append(FT0RECOtask)

   ITSTPCMATCHtask=createTask(name='itstpcMatch_'+str(tf), needs=[TPCRECOtask['name'], ITSRECOtask['name'], FT0RECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='8000', relative_cpu=3/8)
   ITSTPCMATCHtask['cmd'] = '${O2_ROOT}/bin/o2-tpcits-match-workflow ' + getDPL_global_options(bigshm=True) + ' --tpc-track-reader \"tpctracks.root\" --tpc-native-cluster-reader \"--infile tpc-native-clusters.root\" --use-ft0' \
                          + putConfigValuesNew(['MFTClustererParam', 'ITSCATrackerParam', 'tpcitsMatch', 'TPCGasParam', 'TPCCorrMap', 'ITSClustererParam', 'GPU_rec_tpc', 'trackTuneParams', 'ft0tag'], {"NameConf.mDirMatLUT" : ".."} | tpcLocalCFreco) \
                          + tpc_corr_scaling_options + tpc_corr_options_mc
   workflow['stages'].append(ITSTPCMATCHtask)

   TRDTRACKINGtask = createTask(name='trdreco_'+str(tf), needs=[TRDDigitask['name'], ITSTPCMATCHtask['name'], TPCRECOtask['name'], ITSRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   TRDTRACKINGtask['cmd'] = '${O2_ROOT}/bin/o2-trd-tracklet-transformer ' + getDPL_global_options() + putConfigValues() + ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(TRDTRACKINGtask)

   # FIXME This is so far a workaround to avoud a race condition for trdcalibratedtracklets.root
   TRDTRACKINGtask2 = createTask(name='trdreco2_'+str(tf), needs=[TRDTRACKINGtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   trd_track_sources = anchorConfig.get('o2-trd-global-tracking-options', {}).get('track-sources', 'TPC,ITS-TPC')
   TRDTRACKINGtask2['cmd'] = '${O2_ROOT}/bin/o2-trd-global-tracking ' + getDPL_global_options(bigshm=True) + ('',' --disable-mc')[args.no_mc_labels] \
                              + putConfigValuesNew(['ITSClustererParam',
                                                   'ITSCATrackerParam',
                                                   'trackTuneParams',
                                                   'GPU_rec_tpc',
                                                   'TPCGasParam',
                                                   'TPCCorrMap'], {"NameConf.mDirMatLUT" : ".."} | tpcLocalCFreco)                     \
                             + " --track-sources " + trd_track_sources  \
                             + tpc_corr_scaling_options + tpc_corr_options_mc
   workflow['stages'].append(TRDTRACKINGtask2)

   TOFRECOtask = createTask(name='tofmatch_'+str(tf), needs=[ITSTPCMATCHtask['name'], getDigiTaskName("TOF")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   TOFRECOtask['cmd'] = '${O2_ROOT}/bin/o2-tof-reco-workflow --use-ccdb ' + getDPL_global_options() + putConfigValuesNew() + ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(TOFRECOtask)


   toftpcmatchneeds = [TOFRECOtask['name'], TPCRECOtask['name'], ITSTPCMATCHtask['name'], TRDTRACKINGtask2['name']]
   toftracksrcdefault = anchorConfig.get('o2-tof-matcher-workflow-options', {}).get('track-sources', 'TPC,ITS-TPC,TPC-TRD,ITS-TPC-TRD')
   TOFTPCMATCHERtask = createTask(name='toftpcmatch_'+str(tf), needs=toftpcmatchneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   TOFTPCMATCHERtask['cmd'] = '${O2_ROOT}/bin/o2-tof-matcher-workflow ' + getDPL_global_options() \
                              + putConfigValuesNew(["ITSClustererParam",
                                                    'TPCGasParam',
                                                    'TPCCorrMap',
                                                    'ITSCATrackerParam',
                                                    'MFTClustererParam',
                                                    'GPU_rec_tpc',
                                                    'trackTuneParams'], tpcLocalCFreco)                         \
                              + " --track-sources " + toftracksrcdefault + (' --combine-devices','')[args.no_combine_dpl_devices] \
                              + tpc_corr_scaling_options + tpc_corr_options_mc
   workflow['stages'].append(TOFTPCMATCHERtask)

   # MFT reco: needing access to kinematics (when assessment enabled)
   mftreconeeds = [getDigiTaskName("MFT")]
   if usebkgcache:
       mftreconeeds += [ BKG_KINEDOWNLOADER_TASK['name'] ]

   MFTRECOtask = createTask(name='mftreco_'+str(tf), needs=mftreconeeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MFTRECOtask['cmd'] = ('','ln -nfs ../bkg_Kine.root . ;')[doembedding]
   MFTRECOtask['cmd'] += '${O2_ROOT}/bin/o2-mft-reco-workflow ' + getDPL_global_options() + putConfigValuesNew(['MFTTracking', 'MFTAlpideParam', 'ITSClustererParam','MFTClustererParam'])
   MFTRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   if args.mft_assessment_full == True:
      MFTRECOtask['cmd']+= ' --run-assessment '
   workflow['stages'].append(MFTRECOtask)

   # MCH reco: needing access to kinematics ... so some extra logic needed here
   mchreconeeds = [getDigiTaskName("MCH")]
   if usebkgcache:
      mchreconeeds += [ BKG_KINEDOWNLOADER_TASK['name'] ]

   MCHRECOtask = createTask(name='mchreco_'+str(tf), needs=mchreconeeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MCHRECOtask['cmd'] = ('','ln -nfs ../bkg_Kine.root . ;')[doembedding]
   MCHRECOtask['cmd'] += '${O2_ROOT}/bin/o2-mch-reco-workflow ' + getDPL_global_options() + putConfigValues()
   MCHRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(MCHRECOtask)

   MIDRECOtask = createTask(name='midreco_'+str(tf), needs=[getDigiTaskName("MID")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MIDRECOtask['cmd'] = '${O2_ROOT}/bin/o2-mid-digits-reader-workflow ' + ('',' --disable-mc')[args.no_mc_labels] + ' | ${O2_ROOT}/bin/o2-mid-reco-workflow ' + getDPL_global_options() + putConfigValues()
   MIDRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(MIDRECOtask)

   FDDRECOtask = createTask(name='fddreco_'+str(tf), needs=[getDigiTaskName("FDD")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   FDDRECOtask['cmd'] = '${O2_ROOT}/bin/o2-fdd-reco-workflow ' + getDPL_global_options(ccdbbackend=False) + putConfigValues()
   FDDRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(FDDRECOtask)

   FV0RECOtask = createTask(name='fv0reco_'+str(tf), needs=[getDigiTaskName("FV0")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   FV0RECOtask['cmd'] = '${O2_ROOT}/bin/o2-fv0-reco-workflow ' + getDPL_global_options() + putConfigValues()
   FV0RECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(FV0RECOtask)

   # calorimeters
   EMCRECOtask = createTask(name='emcalreco_'+str(tf), needs=[getDigiTaskName("EMC")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   EMCRECOtask['cmd'] = '${O2_ROOT}/bin/o2-emcal-reco-workflow --input-type digits --output-type cells --infile emcaldigits.root --disable-root-output --subspecificationOut 1 ' + putConfigValues()
   EMCRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   EMCRECOtask['cmd'] += ' | ${O2_ROOT}/bin/o2-emcal-cell-recalibrator-workflow --input-subspec 1 --output-subspec 0 --no-timecalib --no-gaincalib ' + putConfigValues()
   EMCRECOtask['cmd'] += (' --isMC','')[args.no_mc_labels]
   EMCRECOtask['cmd'] += ' | ${O2_ROOT}/bin/o2-emcal-cell-writer-workflow --subspec 0 ' + getDPL_global_options()
   EMCRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(EMCRECOtask)

   PHSRECOtask = createTask(name='phsreco_'+str(tf), needs=[getDigiTaskName("PHS")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   PHSRECOtask['cmd'] = '${O2_ROOT}/bin/o2-phos-reco-workflow ' + getDPL_global_options() + putConfigValues()
   PHSRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(PHSRECOtask)

   CPVRECOtask = createTask(name='cpvreco_'+str(tf), needs=[getDigiTaskName("CPV")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   CPVRECOtask['cmd'] = '${O2_ROOT}/bin/o2-cpv-reco-workflow ' + getDPL_global_options() + putConfigValues()
   CPVRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(CPVRECOtask)

   ZDCRECOtask = createTask(name='zdcreco_'+str(tf), needs=[getDigiTaskName("ZDC")], tf=tf, cwd=timeframeworkdir, lab=["RECO", "ZDC"])
   ZDCRECOtask['cmd'] = '${O2_ROOT}/bin/o2-zdc-digits-reco ' + getDPL_global_options() + putConfigValues()
   ZDCRECOtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(ZDCRECOtask)

   ## forward matching
   MCHMIDMATCHtask = createTask(name='mchmidMatch_'+str(tf), needs=[MCHRECOtask['name'], MIDRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MCHMIDMATCHtask['cmd'] = '${O2_ROOT}/bin/o2-muon-tracks-matcher-workflow ' + getDPL_global_options(ccdbbackend=False)
   MCHMIDMATCHtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(MCHMIDMATCHtask)

   MFTMCHMATCHtask = createTask(name='mftmchMatch_'+str(tf), needs=[MCHMIDMATCHtask['name'], MFTRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MFTMCHMATCHtask['cmd'] = '${O2_ROOT}/bin/o2-globalfwd-matcher-workflow ' + putConfigValuesNew(['ITSAlpideConfig','MFTAlpideConfig','FwdMatching'],{"FwdMatching.useMIDMatch":"true"})
   if args.fwdmatching_assessment_full == True:
      MFTMCHMATCHtask['cmd']+= ' |  o2-globalfwd-assessment-workflow '
   MFTMCHMATCHtask['cmd']+= getDPL_global_options() + ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(MFTMCHMATCHtask)

   if args.fwdmatching_save_trainingdata == True:
      MFTMCHMATCHTraintask = createTask(name='mftmchMatchTrain_'+str(tf), needs=[MCHMIDMATCHtask['name'], MFTRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
      MFTMCHMATCHTraintask['cmd'] = '${O2_ROOT}/bin/o2-globalfwd-matcher-workflow ' + putConfigValuesNew(['ITSAlpideConfig','MFTAlpideConfig'],{"FwdMatching.useMIDMatch":"true"})
      MFTMCHMATCHTraintask['cmd']+= getDPL_global_options()
      workflow['stages'].append(MFTMCHMATCHTraintask)

   # HMP tasks
   HMPRECOtask = createTask(name='hmpreco_'+str(tf), needs=[getDigiTaskName('HMP')], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   HMPRECOtask['cmd'] = '${O2_ROOT}/bin/o2-hmpid-digits-to-clusters-workflow ' + getDPL_global_options(ccdbbackend=False) + putConfigValuesNew()
   workflow['stages'].append(HMPRECOtask)

   hmpmatchneeds = [HMPRECOtask['name'], ITSTPCMATCHtask['name'], TOFTPCMATCHERtask['name'], TRDTRACKINGtask2['name']]
   hmp_match_sources = anchorConfig.get('o2-hmpid-matcher-workflow', {}).get('track-sources', 'ITS-TPC,ITS-TPC-TRD,TPC-TRD')
   HMPMATCHtask = createTask(name='hmpmatch_'+str(tf), needs=hmpmatchneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   HMPMATCHtask['cmd'] = '${O2_ROOT}/bin/o2-hmpid-matcher-workflow --track-sources ' + hmp_match_sources + getDPL_global_options() + putConfigValuesNew()
   workflow['stages'].append(HMPMATCHtask)

   # Take None as default, we only add more if nothing from anchorConfig
   pvfinder_sources = anchorConfig.get('o2-primary-vertexing-workflow-options', {}).get('vertexing-sources', 'ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,FDD,HMP,FV0,TRD,MCH,CTP')
   pvfinder_matching_sources = anchorConfig.get('', {}).get('vertex-track-matching-sources', 'ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,ZDC,FDD,HMP,FV0,TRD,MCH,CTP')
   pvfinderneeds = [TRDTRACKINGtask2['name'], FT0RECOtask['name'], FV0RECOtask['name'], EMCRECOtask['name'], PHSRECOtask['name'], CPVRECOtask['name'], FDDRECOtask['name'], ZDCRECOtask['name'], HMPMATCHtask['name'], HMPMATCHtask['name'], ITSTPCMATCHtask['name'], TOFTPCMATCHERtask['name'], MFTMCHMATCHtask['name'], MCHMIDMATCHtask['name']]

   PVFINDERtask = createTask(name='pvfinder_'+str(tf), needs=pvfinderneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=NWORKERS_TF, mem='4000')
   PVFINDERtask['cmd'] = '${O2_ROOT}/bin/o2-primary-vertexing-workflow ' \
                         + getDPL_global_options() + putConfigValuesNew(['ITSAlpideParam','MFTAlpideParam', 'pvertexer', 'TPCGasParam', 'TPCCorrMap', 'ft0tag'], {"NameConf.mDirMatLUT" : ".."})
   PVFINDERtask['cmd'] += ' --vertexing-sources ' + pvfinder_sources + ' --vertex-track-matching-sources ' + pvfinder_matching_sources + (' --combine-source-devices','')[args.no_combine_dpl_devices]
   PVFINDERtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(PVFINDERtask)

   if includeFullQC or includeLocalQC:

     def addQCPerTF(taskName, needs, readerCommand, configFilePath, objectsFile=''):
       task = createTask(name=taskName + '_local' + str(tf), needs=needs, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=1, mem='2000')
       objectsFile = objectsFile if len(objectsFile) > 0 else taskName + '.root'
       # the --local-batch argument will make QC Tasks store their results in a file and merge with any existing objects
       task['cmd'] = f'{readerCommand} | o2-qc --config {configFilePath}' + \
                     f' --local-batch ../{qcdir}/{objectsFile}' + \
                     f' --override-values "qc.config.database.host={args.qcdbHost};qc.config.Activity.number={args.run};qc.config.Activity.periodName={args.productionTag};qc.config.Activity.start={args.timestamp};qc.config.conditionDB.url={args.conditionDB}"' + \
                     ' ' + getDPL_global_options(ccdbbackend=False)
       # Prevents this task from being run for multiple TimeFrames at the same time, thus trying to modify the same file.
       task['semaphore'] = objectsFile
       workflow['stages'].append(task)

     ### MFT

     # to be enabled once MFT Digits should run 5 times with different configurations
     for flp in range(5):
       addQCPerTF(taskName='mftDigitsQC' + str(flp),
                  needs=[getDigiTaskName("MFT")],
                  readerCommand='o2-qc-mft-digits-root-file-reader --mft-digit-infile=mftdigits.root',
                  configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mft-digits-' + str(flp) + '.json',
                  objectsFile='mftDigitsQC.root')
     addQCPerTF(taskName='mftClustersQC',
                needs=[MFTRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types none --cluster-types MFT',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mft-clusters.json')
     addQCPerTF(taskName='mftTracksQC',
                needs=[MFTRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types MFT --cluster-types MFT',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mft-tracks.json')
     addQCPerTF(taskName='mftMCTracksQC',
                needs=[MFTRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types MFT --cluster-types MFT',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mft-tracks-mc.json')

     ### TPC
     # addQCPerTF(taskName='tpcTrackingQC',
     #           needs=,
     #           readerCommand=,
     #           configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/tpc-qc-tracking-direct.json')
     addQCPerTF(taskName='tpcStandardQC',
                 needs=[TPCRECOtask['name']],
                 readerCommand='o2-tpc-file-reader --tpc-track-reader "--infile tpctracks.root" --tpc-native-cluster-reader "--infile tpc-native-clusters.root" --input-type clusters,tracks',
     #            readerCommand='o2-tpc-file-reader --tpc-track-reader "--infile tpctracks.root" --input-type tracks',
                 configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/tpc-qc-standard-direct.json')

     ### TRD
     addQCPerTF(taskName='trdDigitsQC',
                needs=[TRDDigitask['name']],
                readerCommand='o2-trd-trap-sim',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/trd-standalone-task.json')

     addQCPerTF(taskName='trdTrackingQC',
                needs=[TRDTRACKINGtask2['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC-TRD,TPC-TRD" --cluster-types none',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/trd-tracking-task.json')

     ### TOF
     addQCPerTF(taskName='tofDigitsQC',
                needs=[getDigiTaskName("TOF")],
                readerCommand='${O2_ROOT}/bin/o2-tof-reco-workflow --delay-1st-tf 3 --input-type digits --output-type none',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/tofdigits.json',
                objectsFile='tofDigitsQC.root')

     # depending if TRD and FT0 are available
     if isActive('FT0') and isActive('TRD'):
        addQCPerTF(taskName='tofft0PIDQC',
                   needs=[TOFTPCMATCHERtask['name'], FT0RECOtask['name']],
                   readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC-TOF,TPC-TOF,TPC,ITS-TPC-TRD,ITS-TPC-TRD-TOF,TPC-TRD,TPC-TRD-TOF" --cluster-types FT0',
                   configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/pidft0tof.json')
     elif isActive('FT0'):
       addQCPerTF(taskName='tofft0PIDQC',
                   needs=[TOFTPCMATCHERtask['name']],
                   readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC-TOF,TPC-TOF,TPC" --cluster-types FT0',
                  configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/pidft0tofNoTRD.json')
     elif isActive('TRD'):
        addQCPerTF(taskName='tofPIDQC',
                   needs=[TOFTPCMATCHERtask['name']],
                   readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC-TOF,TPC-TOF,TPC,ITS-TPC-TRD,ITS-TPC-TRD-TOF,TPC-TRD,TPC-TRD-TOF" --cluster-types none',
                  configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/pidtof.json')
     else:
       addQCPerTF(taskName='tofPIDQC',
                   needs=[TOFTPCMATCHERtask['name']],
                   readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC-TOF,TPC-TOF,TPC" --cluster-types none',
                  configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/pidtofNoTRD.json')

     ### EMCAL
     if isActive('EMC'):
        addQCPerTF(taskName='emcRecoQC',
                   needs=[EMCRECOtask['name']],
                   readerCommand='o2-emcal-cell-reader-workflow --infile emccells.root',
                   configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/emc-reco-tasks.json')
        if isActive('CTP'):
           addQCPerTF(taskName='emcBCQC',
                      needs=[EMCRECOtask['name'], getDigiTaskName("CTP")],
                      readerCommand='o2-emcal-cell-reader-workflow --infile emccells.root | o2-ctp-digit-reader --inputfile ctpdigits.root --disable-mc',
                      configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/emc-bc-task.json')
     ### FT0
     addQCPerTF(taskName='RecPointsQC',
                   needs=[FT0RECOtask['name']],
                   readerCommand='o2-ft0-recpoints-reader-workflow  --infile o2reco_ft0.root',
                   configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/ft0-reconstruction-config.json')

     ### GLO + RECO
     addQCPerTF(taskName='vertexQC',
                needs=[PVFINDERtask['name']],
                readerCommand='o2-primary-vertex-reader-workflow',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/vertexing-qc-direct-mc.json')
     addQCPerTF(taskName='ITSTPCmatchQC',
                needs=[ITSTPCMATCHtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "ITS,TPC,ITS-TPC" ',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/ITSTPCmatchedTracks_direct_MC.json')
     if isActive('TOF'):
        addQCPerTF(taskName='TOFMatchQC',
                   needs=[TOFTPCMATCHERtask['name']],
                   readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC-TOF,TPC-TOF,TPC" --cluster-types none',
                   configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/tofMatchedTracks_ITSTPCTOF_TPCTOF_direct_MC.json')
     if isActive('TOF') and isActive('TRD'):
        addQCPerTF(taskName='TOFMatchWithTRDQC',
                   needs=[TOFTPCMATCHERtask['name']],
                   readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC-TOF,TPC-TOF,TPC,ITS-TPC-TRD,ITS-TPC-TRD-TOF,TPC-TRD,TPC-TRD-TOF" --cluster-types none',
                   configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/tofMatchedTracks_AllTypes_direct_MC.json')
     ### ITS
     addQCPerTF(taskName='ITSTrackSimTask',
                needs=[ITSRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "ITS" --cluster-types "ITS"',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/its-mc-tracks-qc.json')

     addQCPerTF(taskName='ITSTracksClusters',
                needs=[ITSRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "ITS" --cluster-types "ITS"',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/its-clusters-tracks-qc.json')

     ### CPV
     if isActive('CPV'):
        addQCPerTF(taskName='CPVDigitsQC',
                   needs=[getDigiTaskName("CPV")],
                   readerCommand='o2-cpv-digit-reader-workflow',
                   configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/cpv-digits-task.json')
        addQCPerTF(taskName='CPVClustersQC',
                   needs=[CPVRECOtask['name']],
                   readerCommand='o2-cpv-cluster-reader-workflow',
                   configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/cpv-clusters-task.json')

     ### PHS
     if isActive('PHS'):
        addQCPerTF(taskName='PHSCellsClustersQC',
                   needs=[PHSRECOtask['name']],
                   readerCommand='o2-phos-reco-workflow --input-type cells --output-type clusters --disable-mc --disable-root-output',
                   configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/phs-cells-clusters-task.json')

     ### MID
     if isActive('MID'):
        addQCPerTF(taskName='MIDTaskQC',
                needs=[MIDRECOtask['name']],
                readerCommand='o2-mid-digits-reader-workflow | o2-mid-tracks-reader-workflow',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mid-task.json')

   #secondary vertexer
   svfinder_threads = ' --threads 1 '
   svfinder_cpu = 1
   if COLTYPE == "PbPb" or (doembedding and COLTYPEBKG == "PbPb"):
     svfinder_threads = ' --threads 8 '
     svfinder_cpu = 8
   SVFINDERtask = createTask(name='svfinder_'+str(tf), needs=[PVFINDERtask['name'], FT0FV0EMCCTPDIGItask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=svfinder_cpu, mem='5000')
   SVFINDERtask = createTask(name='svfinder_'+str(tf), needs=[PVFINDERtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=svfinder_cpu, mem='5000')
   SVFINDERtask['cmd'] = '${O2_ROOT}/bin/o2-secondary-vertexing-workflow '
   SVFINDERtask['cmd'] += getDPL_global_options(bigshm=True) + svfinder_threads + putConfigValuesNew(['svertexer', 'TPCCorrMap'], {"NameConf.mDirMatLUT" : ".."} | tpcLocalCFreco) \
                       + tpc_corr_scaling_options + tpc_corr_options_mc
   # Take None as default, we only add more if nothing from anchorConfig
   svfinder_sources = anchorConfig.get('o2-secondary-vertexing-workflow-options', {}). get('vertexing-sources', 'ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,ZDC,FDD,HMP,FV0,TRD,MCH,CTP')
   SVFINDERtask['cmd'] += ' --vertexing-sources ' + svfinder_sources + (' --combine-source-devices','')[args.no_combine_dpl_devices]
   # strangeness tracking is now called from the secondary vertexer
   if args.no_strangeness_tracking:
      SVFINDERtask['cmd'] += ' --disable-strangeness-tracker'
   # if enabled, it may require MC labels
   else:
      SVFINDERtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   workflow['stages'].append(SVFINDERtask)

  # -----------
  # produce AOD
  # -----------
   # TODO This needs further refinement, sources and dependencies should be constructed dynamically
   aodinfosources = anchorConfig.get('o2-aod-producer-workflow-options', {}).get('info-sources', 'ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,ZDC,FDD,HMP,FV0,TRD,MCH,CTP')
   aodneeds = [PVFINDERtask['name'], SVFINDERtask['name']]

   if usebkgcache:
     aodneeds += [ BKG_KINEDOWNLOADER_TASK['name'] ]

   aod_df_id = '{0:03}'.format(tf)

   AODtask = createTask(name='aod_'+str(tf), needs=aodneeds, tf=tf, cwd=timeframeworkdir, lab=["AOD"], mem='4000', cpu='1')
   AODtask['cmd'] = ('','ln -nfs ../bkg_Kine.root . ;')[doembedding]
   AODtask['cmd'] += '[ -f AO2D.root ] && rm AO2D.root; ${O2_ROOT}/bin/o2-aod-producer-workflow --reco-mctracks-only 1 --aod-writer-keep dangling --aod-writer-resfile AO2D'
   # next line needed for meta data writing (otherwise lost)
   AODtask['cmd'] += ' --aod-writer-resmode "UPDATE"'
   AODtask['cmd'] += ' --run-number ' + str(args.run)
   # only in non-anchored runs
   if args.run_anchored == False:
      AODtask['cmd'] += ' --aod-timeframe-id ${ALIEN_PROC_ID}' + aod_df_id
   AODtask['cmd'] += ' ' + getDPL_global_options(bigshm=True)
   AODtask['cmd'] += ' --info-sources ' + aodinfosources
   AODtask['cmd'] += ' --lpmp-prod-tag ${ALIEN_JDL_LPMPRODUCTIONTAG:-unknown}'
   AODtask['cmd'] += ' --anchor-pass ${ALIEN_JDL_LPMANCHORPASSNAME:-unknown}'
   AODtask['cmd'] += ' --anchor-prod ${ALIEN_JDL_LPMANCHORPASSNAME:-unknown}'
   AODtask['cmd'] += (' --combine-source-devices ','')[args.no_combine_dpl_devices]
   AODtask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   if environ.get('O2DPG_AOD_NOTRUNCATE') != None or environ.get('ALIEN_JDL_O2DPG_AOD_NOTRUNCATE') != None:
      AODtask['cmd'] += ' --enable-truncation 0'  # developer option to suppress precision truncation

   if args.no_strangeness_tracking:
      AODtask['cmd'] += ' --disable-strangeness-tracker'

   workflow['stages'].append(AODtask)

   # TPC - time-series objects
   # initial implementation taken from comments in https://its.cern.ch/jira/browse/O2-4612
   # TODO: this needs to be made configurable (as a function of which detectors are actually present)
   tpctsneeds = [ TPCRECOtask['name'],
                  ITSTPCMATCHtask['name'],
                  TOFTPCMATCHERtask['name'],
                  PVFINDERtask['name']
                ]
   TPCTStask = createTask(name='tpctimeseries_'+str(tf), needs=tpctsneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='2000', cpu='1')
   TPCTStask['cmd'] = 'o2-global-track-cluster-reader --disable-mc --cluster-types "TOF" --track-types "ITS,TPC,ITS-TPC,ITS-TPC-TOF,ITS-TPC-TRD-TOF"'
   TPCTStask['cmd'] += ' --primary-vertices '
   TPCTStask['cmd'] += ' | o2-tpc-time-series-workflow --enable-unbinned-root-output --sample-unbinned-tsallis --sampling-factor 0.01 '
   TPCTStask['cmd'] += putConfigValuesNew() + ' ' + getDPL_global_options(bigshm=True)
   workflow['stages'].append(TPCTStask)

   # AOD merging / combination step (as individual stages) --> for the moment deactivated in favor or more stable global merging
   """
   aodmergerneeds = [ AODtask['name'] ]
   if tf > 1:
      # we can only merge this if the previous timeframe was already merged in order
      # to keep time ordering of BCs intact
      aodmergerneeds += [ 'aodmerge_' + str(tf-1) ]

   AOD_merge_task = createTask(name='aodmerge_'+str(tf), needs = aodmergerneeds, tf=tf, cwd=timeframeworkdir, lab=["AOD"], mem='2000', cpu='1')
   AOD_merge_task['cmd'] = ' root -q -b -l ${O2DPG_ROOT}/UTILS/repairAOD.C\\(\\"AO2D.root\\",\\"AO2D_repaired.root\\"\\); '
   # AOD_merge_task['cmd'] += ' mv AO2D.root AO2D_old.root && mv AO2D_repaired.root AO2D.root ; '
   AOD_merge_task['cmd'] += '[ -f ../AO2D.root ] && mv ../AO2D.root ../AO2D_old.root;'
   AOD_merge_task['cmd'] += ' [ -f input.txt ] && rm input.txt; '
   AOD_merge_task['cmd'] += ' [ -f ../AO2D_old.root ] && echo "../AO2D_old.root" > input.txt;'
   AOD_merge_task['cmd'] += ' echo "./AO2D_repaired.root" >> input.txt;'
   AOD_merge_task['cmd'] += ' o2-aod-merger --output ../AO2D.root;'
   AOD_merge_task['cmd'] += ' rm ../AO2D_old.root || true'
   AOD_merge_task['semaphore'] = 'aodmerge' #<---- this is making sure that only one merge is running at any time
   workflow['stages'].append(AOD_merge_task)
   """

  # cleanup
  # --------
  # On the GRID it may be important to cleanup as soon as possible because disc space
  # is limited (which would restrict the number of timeframes). We offer a timeframe cleanup function
  # taking away digits, clusters and other stuff as soon as possible.
  # TODO: cleanup by labels or task names
   if args.early_tf_cleanup == True:
     TFcleanup = createTask(name='tfcleanup_'+str(tf), needs= [ AODtask['name'] ], tf=tf, cwd=timeframeworkdir, lab=["CLEANUP"], mem='0', cpu='1')
     TFcleanup['cmd'] = 'rm *digi*.root;'
     TFcleanup['cmd'] += 'rm *cluster*.root'
     workflow['stages'].append(TFcleanup)

# AOD merging as one global final step
aodmergerneeds = ['aod_' + str(tf) for tf in range(1, NTIMEFRAMES + 1)]
AOD_merge_task = createTask(name='aodmerge', needs = aodmergerneeds, lab=["AOD"], mem='2000', cpu='1')
AOD_merge_task['cmd'] = ' set -e ; [ -f aodmerge_input.txt ] && rm aodmerge_input.txt; '
AOD_merge_task['cmd'] += ' for i in `seq 1 ' + str(NTIMEFRAMES) + '`; do echo "tf${i}/AO2D.root" >> aodmerge_input.txt; done; '
AOD_merge_task['cmd'] += ' o2-aod-merger --input aodmerge_input.txt --output AO2D.root'
# produce MonaLisa event stat file
AOD_merge_task['cmd'] += ' ; ${O2DPG_ROOT}/MC/bin/o2dpg_determine_eventstat.py'
workflow['stages'].append(AOD_merge_task)

job_merging = False
if includeFullQC:
  workflow['stages'].extend(include_all_QC_finalization(ntimeframes=NTIMEFRAMES, standalone=False, run=args.run, productionTag=args.productionTag, conditionDB=args.conditionDB, qcdbHost=args.qcdbHost))


if includeAnalysis:
   # include analyses and potentially final QC upload tasks
    add_analysis_tasks(workflow["stages"], needs=[AOD_merge_task["name"]], is_mc=True, collision_system=COLTYPE)
    if QUALITYCONTROL_ROOT:
        add_analysis_qc_upload_tasks(workflow["stages"], args.productionTag, args.run, "passMC")

# adjust for alternate (RECO) software environments
adjust_RECO_environment(workflow, args.alternative_reco_software)

dump_workflow(workflow['stages'], args.o, meta=vars(args))

exit (0)
