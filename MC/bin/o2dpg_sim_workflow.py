#!/usr/bin/env python3

#
# A script producing a consistent MC->RECO->AOD workflow
# It aims to handle the different MC possible configurations
# It just creates a workflow.json txt file, to execute the workflow one must execute right after
#   ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
#
# Execution examples:
#  - pp PYTHIA jets, 2 events, triggered on high pT decay photons on all barrel calorimeters acceptance, eCMS 13 TeV
#     ./o2dpg_sim_workflow.py -e TGeant3 -ns 2 -j 8 -tf 1 -col pp -eCM 13000 \
#                             -proc "jets" -ptHatBin 3 \
#                             -trigger "external" -ini "\$O2DPG_ROOT/MC/config/PWGGAJE/ini/trigger_decay_gamma_allcalo_TrigPt3_5.ini"
#
#  - pp PYTHIA ccbar events embedded into heavy-ion environment, 2 PYTHIA events into 1 bkg event, beams energy 2.510
#     ./o2dpg_sim_workflow.py -e TGeant3 -nb 1 -ns 2 -j 8 -tf 1  \
#                             -col pp -eA 2.510 -proc "ccbar"  --embedding
#

# TODO:
# - pickup the final list of configKey values from the anchorConfig

import sys
import importlib.util
import argparse
from os import environ, mkdir
from os.path import join, dirname, isdir, isabs, isfile
import random
import json
import itertools
import math
import requests, re
from functools import lru_cache

pandas_available = True
try:
    import pandas as pd
except (ImportError, ValueError):  # ARM architecture has problems with pandas + numpy
    pandas_available = False

sys.path.append(join(dirname(__file__), '.', 'o2dpg_workflow_utils'))

from o2dpg_workflow_utils import createTask, createGlobalInitTask, dump_workflow, adjust_RECO_environment, isActive, activate_detector, deactivate_detector, compute_n_workers, merge_dicts
from o2dpg_qc_finalization_workflow import include_all_QC_finalization
from o2dpg_sim_config import create_sim_config, create_geant_config, constructConfigKeyArg, option_if_available, overwrite_config
from o2dpg_dpl_config_tools import dpl_option_from_config, TaskFinalizer, quote_if_needed

# for some JAliEn interaction
from alienpy.alien import JAlien

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
parser.add_argument('--orbitsPerTF', type=int, help="Timeframe size in number of LHC orbits", default=32)
parser.add_argument('--anchor-config',help="JSON file to contextualise workflow with external configs (config values etc.) for instance coming from data reco workflows.", default='')
parser.add_argument('--overwrite-config',help="extra JSON file with configs (config values etc.) overwriting defaults or the config coming from --anchor-config", default='')
parser.add_argument('--dump-config',help="Dump JSON file with all settings used in workflow", default='user_config.json')
parser.add_argument('-ns',type=int,help='number of signal events / timeframe', default=20)
parser.add_argument('-gen',help='generator: pythia8, extgen', default='')
parser.add_argument('-proc',help='process type: inel, dirgamma, jets, ccbar, ...', default='none')
parser.add_argument('-trigger',help='event selection: particle, external', default='')
parser.add_argument('-ini',help='generator init parameters file (full paths required), for example: ${O2DPG_ROOT}/MC/config/PWGHF/ini/GeneratorHF.ini', default='')
parser.add_argument('-confKey',help='o2sim, generator or trigger configuration key values, for example: "GeneratorPythia8.config=pythia8.cfg;A.x=y"', default='')
parser.add_argument('--detectorList',help='pick which version of ALICE should be simulated', default='ALICE2')
parser.add_argument('--readoutDets',help='comma separated string of detectors readout (does not modify material budget - only hit creation)', default='all')
parser.add_argument('--make-evtpool', help='Generate workflow for event pool creation.', action='store_true')

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
parser.add_argument('-confKeyQED',help='Config key parameters influencing the QED background simulator', default='')

parser.add_argument('-e',help='simengine', default='TGeant4', choices=['TGeant4', 'TGeant3', 'TFluka'])
parser.add_argument('-tf',type=int,help='number of timeframes', default=2)
parser.add_argument('--production-offset',help='Offset determining bunch-crossing '
                     + ' range within a (GRID) production. This number sets first orbit to '
                     + 'Offset x Number of TimeFrames x OrbitsPerTimeframe (up for further sophistication)', default=0)
parser.add_argument('-j', '--n-workers', dest='n_workers', help='number of workers (if applicable)', default=8, type=int)
parser.add_argument('--force-n-workers', dest='force_n_workers', action='store_true', help='by default, number of workers is re-computed '
                                                                                           'for given interaction rate; '
                                                                                           'pass this to avoid that')
parser.add_argument('--skipModules',nargs="*", help="List of modules to skip in geometry budget (and therefore processing)", default=["ZDC"])
parser.add_argument('--skipReadout',nargs="*", help="List of modules to take out from readout", default=[""])
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
parser.add_argument('--pregenCollContext', action='store_true', help=argparse.SUPPRESS) # Now the default, giving this option or not makes not difference. We keep it for backward compatibility
parser.add_argument('--data-anchoring', type=str, default='', help="Take collision contexts (from data) stored in this path")
parser.add_argument('--no-combine-smaller-digi', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--no-combine-dpl-devices', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--no-mc-labels', action='store_true', default=False, help=argparse.SUPPRESS)
parser.add_argument('--no-tpc-digitchunking', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--no-strangeness-tracking', action='store_true', default=False, help="Disable strangeness tracking")
parser.add_argument('--combine-tpc-clusterization', action='store_true', help=argparse.SUPPRESS) #<--- useful for small productions (pp, low interaction rate, small number of events)
parser.add_argument('--first-orbit', default=256, type=int, help=argparse.SUPPRESS)  # to set the first orbit number of the run for HBFUtils (only used when anchoring); default 256 for convenience to allow for some orbits-early
                                                            # (consider doing this rather in O2 digitization code directly)
parser.add_argument('--orbits-early', default=1, type=float, help=argparse.SUPPRESS) # number of orbits to start simulating earlier
                                                                                   # to reduce start of timeframe effects in MC --> affects collision context
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
parser.add_argument('--tpc-corrmap-lumi-mode', default=2, type=int, help='TPC corrections mode (0=linear, 1=derivative, 2=derivative for special MC maps')
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
anchorConfig_generic = { "ConfigParams": create_sim_config(args) }
if args.anchor_config != '':
   print ("** Using external config **")
   anchorConfig = load_external_config(args.anchor_config)
   # adjust the anchorConfig with keys from the generic config, not mentioned in the external config
   # (useful for instance for digitization parameters or others not usually mentioned in async reco)
   for key in anchorConfig_generic["ConfigParams"]:
      if not key in anchorConfig["ConfigParams"]:
         print (f"Transcribing key {key} from generic config into final config")
         anchorConfig["ConfigParams"][key] = anchorConfig_generic["ConfigParams"][key]

else:
   # we load a generic config
   print ("** Using generic config **")
   anchorConfig = anchorConfig_generic
# we apply additional external user choices for the configuration
# this will overwrite config from earlier stages
if args.overwrite_config != '':
   # apply final JSON overwrite
   config_overwrite = load_external_config(args.overwrite_config)
   # let's make sure the configs follow the same format
   if ("ConfigParams" in anchorConfig) != ("ConfigParams" in config_overwrite):
      print ("Error: overwrite config not following same format as base config; Cannot merge")
      exit (1)
   
   # merge the dictionaries into anchorConfig, the latter takes precedence
   merge_dicts(anchorConfig, config_overwrite)

# We still may need adjust configurations manually for consistency:
#
# * Force simpler TPC digitization of if TPC reco does not have the mc-time-gain option:
async_envfile = 'env_async.env' if environ.get('ALIEN_JDL_O2DPG_ASYNC_RECO_TAG') is not None else None
tpcreco_mctimegain = option_if_available('o2-tpc-reco-workflow', '--tpc-mc-time-gain', envfile=async_envfile)
if tpcreco_mctimegain == '':
   # this was communicated by Jens Wiechula@TPC; avoids dEdX issue https://its.cern.ch/jira/browse/O2-5486 for the 2tag mechanism
   print ("TPC reco does not support --tpc-mc-time-gain. Adjusting some config for TPC digitization")
   overwrite_config(anchorConfig['ConfigParams'],'TPCGasParam','OxygenCont',5e-6)
   overwrite_config(anchorConfig['ConfigParams'],'TPCGEMParam','TotalGainStack',2000)
   overwrite_config(anchorConfig['ConfigParams'],'GPU_global','dEdxDisableResidualGain',1)
# TODO: put into it's own function for better modularity

# with the config, we'll create a task_finalizer functor
# this object takes care of customizing/finishing task command with externally given (anchor) config
task_finalizer = TaskFinalizer(anchorConfig, logger="o2dpg_config_replacements.log")

# write this config
config_key_param_path = args.dump_config
with open(config_key_param_path, "w") as f:
   print(f"INFO: Written additional config key parameters to JSON {config_key_param_path}")
   json.dump(anchorConfig, f, indent=2)

# Processing skipped material budget (modules):
# - If user did NOT specify --with-ZDC
# - AND ZDC is not already in the list
# --> append ZDC automatically
if args.with_ZDC:
   # User wants ZDC to *not* be skipped → ensure it's removed
   args.skipModules = [m for m in args.skipModules if m != "ZDC"]
else:
   # If user did not request --with-ZDC,
   # auto-append ZDC unless already present
   if "ZDC" not in args.skipModules:
      args.skipModules.append("ZDC")

# with this we can tailor the workflow to the presence of
# certain detectors
# these are all detectors that should be assumed active
readout_detectors = args.readoutDets
# here are all detectors that have been set in an anchored script
activeDetectors = dpl_option_from_config(anchorConfig, 'o2-ctf-reader-workflow', key='--onlyDet', default_value='all')
if activeDetectors == 'all':
    # if "all" here, there was in fact nothing in the anchored script, set to what is passed to this script (which it either also "all" or a subset)
    activeDetectors = readout_detectors
elif readout_detectors != 'all' and activeDetectors != 'all':
    # in this case both are comma-separated lists. Take intersection
    r = set(readout_detectors.split(','))
    a = set(activeDetectors.split(','))
    activeDetectors = ','.join(r & a)
# the last case: simply take what comes from the anchored config

# convert to set/hashmap
activeDetectors = { det:1 for det in activeDetectors.split(',') if det not in args.skipModules and det not in args.skipReadout}
for det in activeDetectors:
    activate_detector(det)

# function to finalize detector source lists based on activeDetectors
# detector source lists are comma separated lists of DET1, DET2, DET1-DET2, ...
def cleanDetectorInputList(inputlist):
   sources_list = inputlist.split(",")
   # Filter the sources
   filtered_sources = [
      src for src in sources_list
      if all(isActive(part) for part in src.split("-"))
   ]
   # Recompose into a comma-separated string
   return ",".join(filtered_sources)

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
    in case of problems, 0 will be returned. Simple http request has advantage
    of not needing to initialize a Ccdb object.
    """

    url="http://alice-ccdb.cern.ch/browse/RCT/Info/RunInformation/"+str(run_number)
    ansobject=requests.get(url)
    tokens=ansobject.text.split("\n")

    # determine start of run, earlier values take precedence (see also implementation in BasicCCDBManager::getRunDuration)
    STF=0
    # extract SOR by pattern matching
    for t in tokens:
      match_object=re.match(r"\s*(STF\s*=\s*)([0-9]*)\s*", t)
      if match_object != None:
         STF=int(match_object[2])
         break
    if STF > 0:
      return STF

    SOX=0
    # extract SOX by pattern matching
    for t in tokens:
      match_object=re.match(r"\s*(STF\s*=\s*)([0-9]*)\s*", t)
      if match_object != None:
         SOX=int(match_object[2])
         break
    if SOX > 0:
      return SOX

    SOR=0
    # extract SOR by pattern matching
    for t in tokens:
      match_object=re.match(r"\s*(SOR\s*=\s*)([0-9]*)\s*", t)
      if match_object != None:
         SOR=int(match_object[2])
         break
    
    return SOR


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


SKIPMODULES = " ".join(["--skipModules"] + args.skipModules) if len(args.skipModules) > 0 else ""
SIMENGINE=args.e
BFIELD=args.field
RNDSEED=args.seed # typically the argument should be the jobid, but if we get None the current time is used for the initialisation
random.seed(RNDSEED)
print ("Using initialisation seed: ", RNDSEED)
SIMSEED = random.randint(1, 900000000 - NTIMEFRAMES - 1) # PYTHIA maximum seed is 900M for some reason

# ---- initialize global (physics variables) for signal parts ----
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

colsys = {'pp':[2212,2212], 'pPb':[2212,1000822080], 'Pbp':[1000822080,2212], 'PbPb':[1000822080,1000822080], 'pO':[2212,1000080160], 'Op':[1000080160,2212], 'HeO':[1000020040,1000080160], 'OHe':[1000080160,1000020040], 'OO':[1000080160,1000080160], 'NeNe':[1000100200,1000100200]}
# translate here collision type to PDG of allowed particles
COLTYPE=args.col
if COLTYPE in colsys.keys():
   PDGA=colsys[COLTYPE][0]
   PDGB=colsys[COLTYPE][1]
else:
   print('o2dpg_sim_workflow: Error! Unknown collision system %s' % COLTYPE)
   exit(1)

doembedding=True if args.embedding=='True' or args.embedding==True else False

# If not set previously, set beam energy B equal to A
if EBEAMB < 0 and ECMS < 0:
   EBEAMB=EBEAMA
   print('o2dpg_sim_workflow: Set beam energy same in A and B beams')
   if PDGA != PDGB:
      print('o2dpg_sim_workflow: Careful! Set same energies for different particle beams!')

if ECMS > 0:
   if PDGA != PDGB:
      print('o2dpg_sim_workflow: Careful! ECM set for for different particle beams!')

if ECMS < 0 and EBEAMA < 0 and EBEAMB < 0:
   print('o2dpg_sim_workflow: Error! CM or Beam Energy not set!!!')
   exit(1)

# Determine interaction rate
INTRATE=int(args.interactionRate)
if INTRATE <= 0:
   print('o2dpg_sim_workflow: Error! Interaction rate not >0 !!!')
   exit(1)
BCPATTERN=args.bcPatternFile

# ----- global background specific stuff -------
COLTYPEBKG=args.colBkg
havePbPb = (COLTYPE == 'PbPb' or (doembedding and COLTYPEBKG == "PbPb"))

workflow={}
workflow['stages'] = []

### setup global environment variables which are valid for all tasks
global_env = {'ALICEO2_CCDB_CONDITION_NOT_AFTER': args.condition_not_after} if args.condition_not_after else None
globalinittask = createGlobalInitTask(global_env)
globalinittask['cmd'] = 'o2-ccdb-cleansemaphores -p ${ALICEO2_CCDB_LOCALCACHE}'
workflow['stages'].append(globalinittask)
####

usebkgcache=args.use_bkg_from!=None
includeFullQC=args.include_qc=='True' or args.include_qc==True
includeLocalQC=args.include_local_qc=='True' or args.include_local_qc==True
includeAnalysis = args.include_analysis
includeTPCResiduals=True if environ.get('ALIEN_JDL_DOTPCRESIDUALEXTRACTION') == '1' else False
includeTPCSyncMode=True if environ.get('ALIEN_JDL_DOTPCSYNCMODE') == '1' else False
ccdbRemap = environ.get('ALIEN_JDL_REMAPPINGS')

qcdir = "QC"
if (includeLocalQC or includeFullQC) and not isdir(qcdir):
    mkdir(qcdir)

def getDPL_global_options(bigshm=False, ccdbbackend=True, runcommand=True):
   common=" "
   if runcommand:
      common=common + ' -b --run '
   if len(args.dpl_child_driver) > 0:
     common=common + ' --child-driver ' + str(args.dpl_child_driver)
   if ccdbbackend:
     common=common + " --condition-not-after " + str(args.condition_not_after)
     if ccdbRemap != None:
        common=common + f" --condition-remap {quote_if_needed(ccdbRemap)} "
   if args.noIPC!=None:
      return common + " --no-IPC "
   if bigshm:
      return common + " --shm-segment-size ${SHMSIZE:-50000000000} "
   else:
      return common


# prefetch the aligned geometry object (for use in reconstruction)
GEOM_PREFETCH_TASK = createTask(name='geomprefetch', cpu='0')
# We need to query the config if this is done with or without parallel world. This needs to be improved
# as it could be defaulted in the ConfigKey system
with_parallel_world = 1 if args.confKey.find("useParallelWorld=1") != -1 else 0
geom_cmd = f'''
# -- Create aligned geometry using ITS ideal alignment to avoid overlaps in geant
ENABLEPW={with_parallel_world}

# when parallel world processing is disabled we need to switch off ITS alignment
if [ "${{ENABLEPW}}" == "0" ]; then
   CCDBOBJECTS_IDEAL_MC="ITS/Calib/Align"
   TIMESTAMP_IDEAL_MC=1
   ${{O2_ROOT}}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch/ -p ${{CCDBOBJECTS_IDEAL_MC}} \
      -d ${{ALICEO2_CCDB_LOCALCACHE}} --timestamp ${{TIMESTAMP_IDEAL_MC}}
   CCDB_RC="$?"
   if [ ! "${{CCDB_RC}}" == "0" ]; then
     echo "Problem during CCDB prefetching of ${{CCDBOBJECTS_IDEAL_MC}}. Exiting."
     exit ${{CCDB_RC}}
   fi
fi

if [ "$ENABLEPW" == "0" ]; then
  REMAP_OPT="--condition-remap=file://${{ALICEO2_CCDB_LOCALCACHE}}=ITS/Calib/Align"
else
  REMAP_OPT=""
fi

# fetch the global alignment geometry
${{O2_ROOT}}/bin/o2-create-aligned-geometry-workflow ${{ALIEN_JDL_CCDB_CONDITION_NOT_AFTER:+--condition-not-after $ALIEN_JDL_CCDB_CONDITION_NOT_AFTER}} \
      --configKeyValues "HBFUtils.startTime={args.timestamp}" -b --run ${{REMAP_OPT}}

# copy the object into the CCDB cache
mkdir -p $ALICEO2_CCDB_LOCALCACHE/GLO/Config/GeometryAligned
ln -s -f $PWD/o2sim_geometry-aligned.root $ALICEO2_CCDB_LOCALCACHE/GLO/Config/GeometryAligned/snapshot.root
if [ "$ENABLEPW" == "0" ]; then
   [[ -f $PWD/its_GeometryTGeo.root ]] && mkdir -p $ALICEO2_CCDB_LOCALCACHE/ITS/Config/Geometry && ln -s -f $PWD/its_GeometryTGeo.root $ALICEO2_CCDB_LOCALCACHE/ITS/Config/Geometry/snapshot.root
fi

# MFT
[[ -f $PWD/mft_GeometryTGeo.root ]] && mkdir -p $ALICEO2_CCDB_LOCALCACHE/MFT/Config/Geometry && ln -s -f $PWD/mft_GeometryTGeo.root $ALICEO2_CCDB_LOCALCACHE/MFT/Config/Geometry/snapshot.root
'''

with open("geomprefetcher_script.sh",'w') as f:
   f.write(geom_cmd)
GEOM_PREFETCH_TASK['cmd'] = 'chmod +x ${PWD}/geomprefetcher_script.sh; ${PWD}/geomprefetcher_script.sh'
workflow['stages'].append(GEOM_PREFETCH_TASK)


# create/publish the GRPs and other GLO objects for consistent use further down the pipeline
orbitsPerTF=int(args.orbitsPerTF)
GRP_TASK = createTask(name='grpcreate', needs=["geomprefetch"], cpu='0')
GRP_TASK['cmd'] = 'o2-grp-simgrp-tool createGRPs --timestamp ' + str(args.timestamp) + ' --run ' + str(args.run) + ' --publishto ${ALICEO2_CCDB_LOCALCACHE:-.ccdb} -o grp --hbfpertf ' + str(orbitsPerTF) + ' --field ' + args.field
GRP_TASK['cmd'] += ' --detectorList ' + args.detectorList + ' --readoutDets ' + " ".join(activeDetectors) + ' --print ' + ('','--lhcif-CCDB')[args.run_anchored]
if len(args.bcPatternFile) > 0:
    GRP_TASK['cmd'] += '  --bcPatternFile ' + str(args.bcPatternFile)
if len(CONFKEYMV) > 0:
    # this is allowing the possibility to setup/use a different MeanVertex object than the one from CCDB
    GRP_TASK['cmd'] += ' --vertex Diamond --configKeyValues "' + CONFKEYMV + '"'

workflow['stages'].append(GRP_TASK)

# QED is enabled only for same beam species for now
QED_enabled = True if (PDGA==PDGB and PDGA!=2212) else False
includeQED = (QED_enabled or (doembedding and QED_enabled)) or (args.with_qed == True)
signalprefix='sgn'

# No vertexing for event pool generation; otherwise the vertex comes from CCDB and later from CollContext
# (Note that the CCDB case covers the kDiamond case, since this is picked up in GRP_TASK)
vtxmode_precoll = 'kNoVertex' if args.make_evtpool else 'kCCDB'
vtxmode_sgngen = 'kCollContext'

# preproduce the collision context / timeframe structure for all timeframes at once
precollneeds=[GRP_TASK['name']]
# max number of QED events simulated per timeframe.
# A large pool of QED events (0.6*INTRATE) is needed to avoid repetition of events in the same or
# neighbouring ITS readout frames, which would fire already activated pixel, discarding the event.
# Discussed in detail in https://its.cern.ch/jira/browse/O2-5861
NEventsQED = max(10000, int(INTRATE*0.6))
# Hadronic cross section values are taken from Glauber MC
XSecSys = {'PbPb': 8., 'OO': 1.273, 'NeNe': 1.736}
# QED cross section values were calculated with TEPEMGEN
# OO and NeNe at 5.36 TeV, while the old PbPb value was kept as before
# If the collision energy changes these values need to be updated
# More info on the calculation can be found in the TEPEMGEN folder of AEGIS
# specifically in the epemgen.f file
QEDXSecExpected = {'PbPb': 35237.5, 'OO': 3.17289, 'NeNe': 7.74633} # expected magnitude of QED cross section from TEPEMGEN
Zsys = {'PbPb': 82, 'OO': 8, 'NeNe': 10} # atomic number of colliding species
PreCollContextTask=createTask(name='precollcontext', needs=precollneeds, cpu='1')

# adapt timeframeID + orbits + seed + qed
# apply max-collisision offset
# apply vertexing
interactionspecification = signalprefix + ',' + str(INTRATE) + ',' + str(1000000) + ':' + str(1000000)
if doembedding:
   interactionspecification = 'bkg,' + str(INTRATE) + ',' + str(NTIMEFRAMES*args.ns) + ':' + str(args.nb) + ' ' + signalprefix + ',' + args.embeddPattern

PreCollContextTask['cmd']='${O2_ROOT}/bin/o2-steer-colcontexttool -i ' + interactionspecification                          \
                            + ' --show-context '                                                                           \
                            + ' --timeframeID ' + str(int(args.production_offset)*NTIMEFRAMES)                             \
                            + ' --orbitsPerTF ' + str(orbitsPerTF)                                                         \
                            + ' --orbits ' + str(NTIMEFRAMES * (orbitsPerTF))                                              \
                            + ' --seed ' + str(RNDSEED)                                                                    \
                            + ' --noEmptyTF --first-orbit ' + str(args.first_orbit)                                        \
                            + ' --extract-per-timeframe tf:sgn'                                                            \
                            + ' --with-vertices ' + vtxmode_precoll                                                        \
                            + ' --maxCollsPerTF ' + str(args.ns)                                                           \
                            + ' --orbitsEarly ' + str(args.orbits_early)                                                   \
                            + ('',f" --import-external {args.data_anchoring}")[len(args.data_anchoring) > 0]

PreCollContextTask['cmd'] += ' --bcPatternFile ccdb'  # <--- the object should have been set in (local) CCDB
if includeQED:
   if PDGA==2212 or PDGB==2212:
      # QED is not enabled for pp and pA collisions
      print('o2dpg_sim_workflow: Warning! QED is not enabled for pp or pA collisions')
      includeQED = False
   else:
      qedrate = INTRATE * QEDXSecExpected[COLTYPE] / XSecSys[COLTYPE]   # hadronic interaction rate * cross_section_ratio
      qedspec = 'qed' + ',' + str(qedrate) + ',10000000:' + str(NEventsQED)
      PreCollContextTask['cmd'] += ' --QEDinteraction ' + qedspec
workflow['stages'].append(PreCollContextTask)


if doembedding:
    if not usebkgcache:
        # ---- do background transport task -------
        NBKGEVENTS=args.nb
        GENBKG=args.genBkg
        if GENBKG =='':
           print('o2dpg_sim_workflow: Error! embedding background generator name not provided')
           exit(1)

        # PDG translation for background
        if COLTYPEBKG in colsys.keys():
           PDGABKG=colsys[COLTYPEBKG][0]
           PDGBBKG=colsys[COLTYPEBKG][1]
        else:
           print('o2dpg_sim_workflow: Error! Unknown background collision system %s' % COLTYPEBKG)
           exit(1)

        PROCESSBKG=args.procBkg
        ECMSBKG=float(args.eCM)
        EBEAMABKG=float(args.eA)
        EBEAMBBKG=float(args.eB)

        if COLTYPEBKG == 'PbPb':
           if ECMSBKG < 0:    # assign 5.02 TeV to Pb-Pb
              print('o2dpg_sim_workflow: Set BKG CM Energy to PbPb case 5.02 TeV')
              ECMSBKG=5020.0
           if GENBKG == 'pythia8' and PROCESSBKG != 'heavy_ion':
              PROCESSBKG = 'heavy_ion'
              print('o2dpg_sim_workflow: Process type not considered for Pythia8 PbPb')

        # If not set previously, set beam energy B equal to A
        if EBEAMBBKG < 0 and ECMSBKG < 0:
           EBEAMBBKG=EBEAMABKG
           print('o2dpg_sim_workflow: Set beam energy same in A and B beams')
           if PDGABKG != PDGBBKG:
              print('o2dpg_sim_workflow: Careful! Set same energies for different background beams!')

        if ECMSBKG > 0:
           if PDGABKG != PDGBBKG:
              print('o2dpg_sim_workflow: Careful! ECM set for different background beams!')

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

        bkgsimneeds = [BKG_CONFIG_task['name'], GRP_TASK['name'], PreCollContextTask['name']]
        BKGtask=createTask(name='bkgsim', lab=["GEANT"], needs=bkgsimneeds, cpu=NWORKERS)
        BKGtask['cmd']='${O2_ROOT}/bin/o2-sim -e ' + SIMENGINE   + ' -j ' + str(NWORKERS) + ' -n '     + str(NBKGEVENTS) \
                     + ' -g  '      + str(GENBKG) + ' '    + str(SKIPMODULES)  + ' -o bkg ' + str(INIBKG)                \
                     + ' --field ccdb ' + str(CONFKEYBKG)                                                                \
                     + ('',' --timestamp ' + str(args.timestamp))[args.timestamp!=-1] + ' --run ' + str(args.run)        \
                     + ' --vertexMode ' + vtxmode_sgngen                                                                 \
                     + ' --fromCollContext collisioncontext.root:bkg '                                                   \
                     + ' --detectorList ' + args.detectorList

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
if args.detectorList == 'ALICE2.1':
    smallsensorlist = ['IT3' if sensor == 'ITS' else sensor for sensor in smallsensorlist]

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
   # produce QED background for PbPb collissions

   QEDdigiargs = ""
   if includeQED:
     qedneeds=[GRP_TASK['name'], PreCollContextTask['name']]
     QED_task=createTask(name='qedsim_'+str(tf), needs=qedneeds, tf=tf, cwd=timeframeworkdir, cpu='1')
     ########################################################################################################
     #
     # ATTENTION: CHANGING THE PARAMETERS/CUTS HERE MIGHT INVALIDATE THE QED INTERACTION RATES USED ELSEWHERE
     #
     ########################################################################################################

     # determine final conf key for QED simulation
     QEDBaseConfig = "GeneratorExternal.fileName=$O2_ROOT/share/Generators/external/QEDLoader.C;QEDGenParam.yMin=-7;QEDGenParam.yMax=7;QEDGenParam.ptMin=0.001;QEDGenParam.ptMax=1.;QEDGenParam.xSectionHad="+str(XSecSys[COLTYPE])+";QEDGenParam.Z="+str(Zsys[COLTYPE])+";QEDGenParam.cmEnergy="+str(ECMS)+";Diamond.width[2]=6.;"
     QEDCONFKEY = constructConfigKeyArg(create_geant_config(args, QEDBaseConfig + args.confKeyQED))
     qed_detectorlist = ' ITS MFT FT0 FV0 FDD '
     if args.detectorList == 'ALICE2.1':
         qed_detectorlist = qed_detectorlist.replace('ITS', 'IT3')
     QED_task['cmd'] = 'o2-sim -e TGeant3 --field ccdb -j ' + str('1') +  ' -o qed'                                   \
                        + ' -n ' + str(NEventsQED) + ' -m ' + qed_detectorlist                                        \
                        + ('', ' --timestamp ' + str(args.timestamp))[args.timestamp!=-1] + ' --run ' + str(args.run) \
                        + ' --seed ' + str(TFSEED)                                                                    \
                        + ' -g extgen '                                                                               \
                        + ' --detectorList ' + args.detectorList + ' '                                                \
                        + QEDCONFKEY
     QED_task['cmd'] += '; RC=$?; QEDXSecCheck=`grep xSectionQED qedgenparam.ini | sed \'s/xSectionQED=//\'`'
     QED_task['cmd'] += '; echo "CheckXSection ' + str(QEDXSecExpected[COLTYPE]) + ' = $QEDXSecCheck"; [[ ${RC} == 0 ]]'
     # TODO: propagate the Xsecion ratio dynamically
     QEDdigiargs=' --simPrefixQED qed' +  ' --qed-x-section-ratio ' + str(QEDXSecExpected[COLTYPE]/XSecSys[COLTYPE])
     workflow['stages'].append(QED_task)

   # recompute the number of workers to increase CPU efficiency
   NWORKERS_TF = compute_n_workers(INTRATE, COLTYPE, n_workers_user = NWORKERS) if (not args.force_n_workers) else NWORKERS

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
   
   # default flags for extkinO2 signal simulation (no transport)
   extkinO2Config = ''
   if GENERATOR == 'extkinO2':
      extkinO2Config = ';GeneratorFromO2Kine.randomize=true;GeneratorFromO2Kine.rngseed=' + str(TFSEED)

   # determine final conf key for signal simulation
   CONFKEY = constructConfigKeyArg(create_geant_config(args, args.confKey + extkinO2Config))
   # -----------------
   # transport signals
   # -----------------
   signalneeds=[ SGN_CONFIG_task['name'], GRP_TASK['name'] ]
   signalneeds.append(PreCollContextTask['name'])

   # add embedIntoFile only if embeddPattern does contain a '@'
   embeddinto= "--embedIntoFile ../bkg_MCHeader.root" if (doembedding & ("@" in args.embeddPattern)) else ""
   if doembedding:
       if not usebkgcache:
            signalneeds = signalneeds + [ BKGtask['name'] ]
       else:
            signalneeds = signalneeds + [ BKG_HEADER_task['name'] ]

   # (separate) event generation task
   sep_event_mode = args.event_gen_mode == 'separated'
   sgngenneeds=signalneeds
   # for HepMC we need some special treatment since we need
   # to ensure that different timeframes read different events from this file
   if GENERATOR=="hepmc" and tf > 1:
      sgngenneeds=signalneeds + ['sgngen_' + str(tf-1)] # we serialize event generation
   SGNGENtask=createTask(name='sgngen_'+str(tf), needs=sgngenneeds, tf=tf, cwd='tf'+str(tf), lab=["GEN"],
                         cpu=8 if args.make_evtpool else 1, mem=1000)

   SGNGENtask['cmd']=''
   if GENERATOR=="hepmc":
     if tf == 1:
      # determine the offset number
       eventOffset = environ.get('HEPMCOFFSET')
       print("HEPMCOFFSET: ", eventOffset)
       if eventOffset == None:
        eventOffset = 0
       cmd = 'export HEPMCEVENTSKIP=$(${O2DPG_ROOT}/UTILS/InitHepMCEventSkip.sh ../HepMCEventSkip.json ' + str(eventOffset) + ');'
     elif tf > 1:
       # determine the skip number
       cmd = 'export HEPMCEVENTSKIP=$(${O2DPG_ROOT}/UTILS/ReadHepMCEventSkip.sh ../HepMCEventSkip.json ' + str(tf) + ');'
     SGNGENtask['cmd'] = cmd

   generationtimeout = -1 # possible timeout for event pool generation
   if args.make_evtpool:
     JOBTTL=environ.get('JOBTTL', None)
     if JOBTTL != None:
       generationtimeout = 0.95*int(JOBTTL) # for GRID jobs, determine timeout automatically
   SGNGENtask['cmd'] +=('','timeout ' + str(generationtimeout) + ' ')[args.make_evtpool and generationtimeout>0] \
                     + '${O2_ROOT}/bin/o2-sim --noGeant -j 1 --field ccdb --vertexMode ' + vtxmode_sgngen  \
                     + ' --run ' + str(args.run) + ' ' + str(CONFKEY) + str(TRIGGER)                  \
                     + ' -g ' + str(GENERATOR) + ' ' + str(INIFILE) + ' -o genevents ' + embeddinto   \
                     + ('', ' --timestamp ' + str(args.timestamp))[args.timestamp!=-1]                \
                     + ' --seed ' + str(TFSEED) + ' -n ' + str(NSIGEVENTS)                            \
                     + ' --detectorList ' + args.detectorList                                         \
                     + ' --fromCollContext collisioncontext.root:' + signalprefix
   if GENERATOR=="hepmc":
      SGNGENtask['cmd'] += "; RC=$?; ${O2DPG_ROOT}/UTILS/UpdateHepMCEventSkip.sh ../HepMCEventSkip.json " + str(tf) + '; [[ ${RC} == 0 ]]'
   if sep_event_mode == True:
      workflow['stages'].append(SGNGENtask)
      signalneeds = signalneeds + [SGNGENtask['name']]
   if args.make_evtpool:
      if generationtimeout > 0:
         # final adjustment of command for event pools and timeout --> we need to analyse the return code
         # if we have a timeout then we finish what we can and are also happy with return code 124
         SGNGENtask['cmd'] += ' ; RC=$? ; [[ ${RC} == 0 || ${RC} == 124 ]]'
      continue

   # GeneratorFromO2Kine parameters are needed only before the transport
   CONFKEY = re.sub(r'GeneratorFromO2Kine.*?;', '', CONFKEY)

   sgnmem = 6000 if COLTYPE == 'PbPb' else 4000
   SGNtask=createTask(name='sgnsim_'+str(tf), needs=signalneeds, tf=tf, cwd='tf'+str(tf), lab=["GEANT"],
                      relative_cpu=7/8, n_workers=NWORKERS_TF, mem=str(sgnmem))
   sgncmdbase = '${O2_ROOT}/bin/o2-sim -e ' + str(SIMENGINE) + ' '  + str(SKIPMODULES) + ' -n ' + str(NSIGEVENTS) + ' --seed ' + str(TFSEED)      \
              + ' --field ccdb -j ' + str(NWORKERS_TF) + ' ' + str(CONFKEY) + ' ' + str(INIFILE) + ' -o ' + signalprefix + ' ' + embeddinto       \
              + ' --detectorList ' + args.detectorList                                                                                            \
              + ('', ' --timestamp ' + str(args.timestamp))[args.timestamp!=-1] + ' --run ' + str(args.run)
   if sep_event_mode:
      SGNtask['cmd'] = sgncmdbase + ' -g extkinO2 --extKinFile genevents_Kine.root ' + ' --vertexMode kNoVertex'
   else:
      SGNtask['cmd'] = sgncmdbase + ' -g ' + str(GENERATOR) + ' ' + str(TRIGGER) + ' --vertexMode kCCDB '
   if not isActive('all'):
      SGNtask['cmd'] += ' --readoutDetectors ' + " ".join(activeDetectors)
   
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

   def putConfigValues(listOfMainKeys=[], localCF = {}, globalTFConfig = True):
     """
     Creates the final --configValues string to be passed to the workflows.
     Uses the globalTFConfigValues and applies other parameters on top
     listOfMainKeys : list of keys to be applied from the global configuration object
     localCF: a dictionary mapping key to param - possibly overrides settings taken from global config
     """
     returnstring = ' --configKeyValues "'     
     cf = globalTFConfigValues.copy() if globalTFConfig else {}
     isfirst=True

     # now bring in the relevant keys
     # from the external config
     for key in listOfMainKeys:
       # try to find key flat in dict (backward compatible)
       keydict = anchorConfig.get(key)
       if keydict == None:
         # try to find under the ConfigurableKey entry (standard)
         keydict = anchorConfig.get("ConfigParams",{}).get(key)
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
   # The purpose of this short task is to generate the digi INI file which all other tasks may use
   contextneeds = [LinkGRPFileTask['name'], SGNtask['name']]
   if includeQED:
     contextneeds += [QED_task['name']]
   ContextTask = createTask(name='digicontext_'+str(tf), needs=contextneeds, tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu='1')
   # this is just to have the digitizer ini file
   ContextTask['cmd'] = '${O2_ROOT}/bin/o2-sim-digitizer-workflow --only-context --interactionRate ' + str(INTRATE)                               \
                        + ' ' + getDPL_global_options(ccdbbackend=False) + ' -n ' + str(args.ns) + simsoption                                     \
                        + ' --seed ' + str(TFSEED)                                                                                                \
                        + ' ' + putConfigValues({"DigiParams.maxOrbitsToDigitize" : str(orbitsPerTF)},{"DigiParams.passName" : str(PASSNAME)}) \
                        + ' --incontext ' + CONTEXTFILE + QEDdigiargs
   ContextTask['cmd'] += ' --bcPatternFile ccdb'
   workflow['stages'].append(ContextTask)

   # ===| TPC digi part |===
   CTPSCALER = args.ctp_scaler
   tpcDistortionType=args.tpc_distortion_type
   print(f"TPC distortion simulation: type = {tpcDistortionType}, CTP scaler value {CTPSCALER}");
   tpcdigineeds=[ContextTask['name'], LinkGRPFileTask['name']]
   if usebkgcache:
      tpcdigineeds += [ BKG_HITDOWNLOADER_TASKS['TPC']['name'] ]

   tpcLocalCF={"DigiParams.maxOrbitsToDigitize" : str(orbitsPerTF), "DigiParams.seed" : str(TFSEED)}

   # force TPC common mode correction in all cases to avoid issues the CMk values stored in the CCDB
   tpcLocalCF['TPCEleParam.DigiMode'] = str(2) # 2 = o2::tpc::DigitzationMode::ZeroSuppressionCMCorr from TPCBase/ParameterElectronics.h

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
   TPCDigitask['cmd'] += '${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch -p TPC/Config/RunInfoV2 --timestamp '   \
                         + str(args.timestamp) + ' --created-not-after ' + str(args.condition_not_after) + ' -d ${ALICEO2_CCDB_LOCALCACHE} ; '
   TPCDigitask['cmd'] += '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options(bigshm=True) + ' -n ' + str(args.ns) + simsoption       \
                         + ' --onlyDet TPC --TPCuseCCDB --interactionRate ' + str(INTRATE) + '  --tpc-lanes ' + str(NWORKERS_TF)             \
                         + ' --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini --early-forward-policy always --forceSelectedDets ' \
                         + ' --tpc-distortion-type ' + str(tpcDistortionType)                                                             \
                         + ' --n-threads-distortions 1 '                                                                                  \
                         + putConfigValues(["TPCGasParam","TPCGEMParam","TPCEleParam","TPCITCorr","TPCDetParam"],
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
                         + putConfigValues(localCF={"TRDSimParams.digithreads" : NWORKERS_TF, "DigiParams.seed" : str(TFSEED)}) + " --forceSelectedDets"
   TRDDigitask['cmd'] += ('',' --disable-mc')[args.no_mc_labels]
   if isActive("TRD"):
      workflow['stages'].append(TRDDigitask)

   # these are digitizers which are single threaded
   def createRestDigiTask(name, det='ALLSMALLER'):
      tneeds =[ContextTask['name']]
      if includeQED == True:
        tneeds += [QED_task['name']]
      commondigicmd = '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption \
                      + ' --interactionRate ' + str(INTRATE) + '  --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini'      \
                      + putConfigValues(["MFTAlpideParam", "ITSAlpideParam", "ITSDigitizerParam" if args.detectorList == 'ALICE2' else "IT3DigitizerParam"],
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
         detlist = cleanDetectorInputList(detlist)
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
   # these inputs at the same time --> still need to be made better.
   tneeds = [ContextTask['name']]
   if includeQED:
     tneeds += [QED_task['name']]
   FT0FV0EMCCTPDIGItask = createTask(name="ft0fv0emcctp_digi_" + str(tf), needs=tneeds,
                                     tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
   FT0FV0EMCCTPDIGItask['cmd'] = ('','ln -nfs ../bkg_HitsFT0.root . ; ln -nfs ../bkg_HitsFV0.root . ; ln -nfs ../bkg_HitsEMC.root; ln -nfs ../bkg_Kine.root; ')[doembedding]
   FT0FV0EMCCTPDIGItask['cmd'] += task_finalizer([
      '${O2_ROOT}/bin/o2-sim-digitizer-workflow', 
      getDPL_global_options(), 
      f'-n {args.ns}', 
      simsoption,
      '--onlyDet FT0,FV0,EMC,CTP', 
      f'--interactionRate {INTRATE}',
      f'--incontext {CONTEXTFILE}',
      f'--store-ctp-lumi {CTPSCALER}',
      '--disable-write-ini',
      putConfigValues(listOfMainKeys=['EMCSimParam','FV0DigParam','FT0DigParam'], localCF={"DigiParams.seed" : str(TFSEED)}),
      ('--combine-devices','')[args.no_combine_dpl_devices],
      ('',' --disable-mc')[args.no_mc_labels], 
      QEDdigiargs,
      '--forceSelectedDets'], configname = 'ft0fv0emcctp_digi')
   
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
   tpcclusterneed=[TPCDigitask['name'], FT0FV0EMCCTPDIGItask['name']]
   if not args.combine_tpc_clusterization:
     # We treat TPC clusterization in multiple (sector) steps in order to
     # stay within the memory limit or to parallelize over sector from outside (not yet supported within cluster algo)
     tpcclustertasks=[]
     sectorpertask=18
     for s in range(0,35,sectorpertask):
       taskname = 'tpcclusterpart' + str((int)(s/sectorpertask)) + '_' + str(tf)
       tpcclustertasks.append(taskname)
       tpcclussect = createTask(name=taskname, needs=tpcclusterneed, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='2', mem='8000')
       digitmergerstr = '${O2_ROOT}/bin/o2-tpc-chunkeddigit-merger --tpc-sectors ' + str(s)+'-'+str(s+sectorpertask-1) + ' --tpc-lanes ' + str(NWORKERS_TF) + ' | '
       tpcclussect['cmd'] = (digitmergerstr,'')[args.no_tpc_digitchunking] + ' ${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True) + ' --input-type ' + ('digitizer','digits')[args.no_tpc_digitchunking] + ' --output-type clusters,send-clusters-per-sector --tpc-native-cluster-writer \" --outfile tpc-native-clusters-part'+ str((int)(s/sectorpertask)) + '.root\" --tpc-sectors ' + str(s)+'-'+str(s+sectorpertask-1) + ' ' + putConfigValues(["GPU_global"], {"GPU_proc.ompThreads" : 4}) + ('',' --disable-mc')[args.no_mc_labels]
       tpcclussect['env'] = { "OMP_NUM_THREADS" : "4" , "TBB_NUM_THREADS" : "4" }
       tpcclussect['semaphore'] = "tpctriggers.root"
       tpcclussect['retry_count'] = 2  # the task has a race condition --> makes sense to retry
       workflow['stages'].append(tpcclussect)

     TPCCLUSMERGEtask=createTask(name='tpcclustermerge_'+str(tf), needs=tpcclustertasks, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='10000')
     TPCCLUSMERGEtask['cmd']='${O2_ROOT}/bin/o2-commonutils-treemergertool -i tpc-native-clusters-part*.root -o tpc-native-clusters.root -t tpcrec' #--asfriend preferable but does not work
     workflow['stages'].append(TPCCLUSMERGEtask)
     tpcreconeeds.append(TPCCLUSMERGEtask['name'])
   else:
     tpcclus = createTask(name='tpccluster_' + str(tf), needs=tpcclusterneed, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=NWORKERS_TF, mem='2000')
     tpcclus['cmd'] = '${O2_ROOT}/bin/o2-tpc-chunkeddigit-merger --tpc-lanes ' + str(NWORKERS_TF)
     tpcclus['cmd'] += ' | ${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options() + ' --input-type digitizer --output-type clusters,send-clusters-per-sector ' + putConfigValues(["GPU_global","TPCGasParam","TPCCorrMap"],{"GPU_proc.ompThreads" : 1}) + ('',' --disable-mc')[args.no_mc_labels]
     workflow['stages'].append(tpcclus)
     tpcreconeeds.append(tpcclus['name'])

   # ===| TPC reco |===
   tpcLocalCFreco=dict()

   # handle distortion corrections and scaling using MC maps
   # this assumes the lumi inside the maps is stored in FT0 (pp) scalers
   # in case of PbPb the conversion factor ZDC ->FT0 (pp) must be set
   tpc_corr_options_mc=''

   tpcCorrmapLumiMode = args.tpc_corrmap_lumi_mode

   if tpcDistortionType == 0: # disable distortion corrections
      tpc_corr_options_mc=' --corrmap-lumi-mode 0 '
      tpcLocalCFreco['TPCCorrMap.lumiMean'] = '-1';
   elif tpcDistortionType == 1: # disable scaling
      tpc_corr_options_mc=' --corrmap-lumi-mode ' + str(tpcCorrmapLumiMode) + ' '
      tpcLocalCFreco['TPCCorrMap.lumiInst'] = str(CTPSCALER)
      tpcLocalCFreco['TPCCorrMap.lumiMean'] = str(CTPSCALER)
   elif tpcDistortionType == 2: # full scaling with CTP values
      if COLTYPE == 'PbPb':
         tpcLocalCFreco['TPCCorrMap.lumiInstFactor'] = str(lumiInstFactor)
      tpc_corr_options_mc=' --corrmap-lumi-mode ' + str(tpcCorrmapLumiMode) + ' '
      tpcLocalCFreco['TPCCorrMap.lumiInst'] = str(CTPSCALER)

   # Setup the TPC correction scaling options for reco; They come from the anchoring setup
   # Some useful comments from Ruben:
   # - lumi-type == 0 means no-scaling of corrections with any measure of the lumi rather than no corrections at all.
   # - The "no corrections" mode is imposed by the TPCCorrMap.lumiMean configurable being negative, in this case all other options in the corrections treatment are ignored.
   # - But if the MC simulation was done with distortions, then the reco needs --lumy-type 1 (i.e. scale with the CTP lumi) even if the corresponding anchor run reco was using --lumy-type 2
   #   (i.e. scaling according to the TPC IDC, which don't exist in the MC).

   anchor_lumi_type = dpl_option_from_config(anchorConfig, 'o2-tpcits-match-workflow', '--lumi-type', section = 'full', default_value = '')
   if anchor_lumi_type != '':
      anchor_lumi_type = '--lumi-type ' + anchor_lumi_type
   anchor_corrmaplumi_mode = dpl_option_from_config(anchorConfig, 'o2-tpcits-match-workflow', '--corrmap-lumi-mode', section = 'full', default_value = '')
   if anchor_corrmaplumi_mode != '':
      anchor_corrmaplumi_mode = '--corrmap-lumi-mode ' + anchor_corrmaplumi_mode
   
   tpc_corr_scaling_options = anchor_lumi_type + ' ' + anchor_corrmaplumi_mode
   
   # why not simply?
   # tpc_corr_scaling_options = ('--lumi-type 1', '')[tpcDistortionType != 0]

   #<--------- TPC reco task
   if includeTPCSyncMode:
      tpcSyncreconeeds = tpcreconeeds.copy()
      TPCSyncRECOtask=createTask(name='tpcSyncreco_'+str(tf), needs=tpcSyncreconeeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], relative_cpu=3/8, mem='16000')
      TPCSyncRECOtask['cmd'] = '${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True, ccdbbackend=False, runcommand=False) \
                               + '--input-type clusters --output-type clusters,disable-writer ' \
                               + putConfigValues()
      TPCSyncRECOtask['cmd'] += ' | ${O2_ROOT}/bin/o2-gpu-reco-workflow' + getDPL_global_options(bigshm=True, ccdbbackend=True, runcommand=False) \
                                + '--input-type clusters --output-type compressed-clusters-flat,clusters,send-clusters-per-sector --filtered-output-specs ' \
                                + tpc_corr_scaling_options + ' ' + tpc_corr_options_mc \
                                + putConfigValues(["TPCGasParam", "TPCCorrMap", "trackTuneParams"], 
                                                  localCF={"GPU_proc.ompThreads":NWORKERS_TF, \
                                                           "GPU_proc.tpcWriteClustersAfterRejection":1, \
                                                           "GPU_rec_tpc.compressionTypeMask":0, \
                                                           "GPU_global.synchronousProcessing":1, \
                                                           "GPU_proc.tpcIncreasedMinClustersPerRow":500000},
                                                  globalTFConfig=False)
      TPCSyncRECOtask['cmd'] += ' | ${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True, ccdbbackend=False, runcommand=True) + ' --filtered-input --input-type pass-through --output-type clusters,send-clusters-per-sector '
      TPCSyncRECOtask['cmd'] += ' ; mv tpc-filtered-native-clusters.root tpc-native-clusters.root'
      workflow['stages'].append(TPCSyncRECOtask)
      tpcreconeeds.append(TPCSyncRECOtask['name'])

   TPCRECOtask=createTask(name='tpcreco_'+str(tf), needs=tpcreconeeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], relative_cpu=3/8, mem='16000')
   TPCRECOtask['cmd'] = task_finalizer([
     '${O2_ROOT}/bin/o2-tpc-reco-workflow',
     getDPL_global_options(bigshm=True),
     '--input-type clusters',
     '--output-type tracks,send-clusters-per-sector',
     putConfigValues(["GPU_global",
                      "TPCGasParam", 
                      "TPCCorrMap", 
                      "GPU_rec_tpc", 
                      "trackTuneParams"], 
                      {"GPU_proc.ompThreads":NWORKERS_TF} | tpcLocalCFreco),
     ('',' --disable-mc')[args.no_mc_labels],
     tpc_corr_scaling_options, 
     tpc_corr_options_mc,
     tpcreco_mctimegain])
   workflow['stages'].append(TPCRECOtask)

   #<--------- ITS reco task 
   ITSMemEstimate = 12000 if havePbPb else 2000 # PbPb has much large mem requirement for now (in worst case)
   ITSRECOtask=createTask(name='itsreco_'+str(tf), needs=[getDigiTaskName("ITS" if args.detectorList == 'ALICE2' else "IT3")],
                          tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem=str(ITSMemEstimate))
   ITSRECOtask['cmd'] = task_finalizer([
     "${O2_ROOT}/bin/o2-its-reco-workflow" if args.detectorList == 'ALICE2' else "${O2_ROOT}/bin/o2-its3-reco-workflow",
     getDPL_global_options(bigshm=havePbPb),
     '--trackerCA' if args.detectorList == 'ALICE2' else '',
     '--tracking-mode async',
     putConfigValues(["ITSVertexerParam", 
                      "ITSAlpideParam",
                      "ITSClustererParam", 
                      "ITSCATrackerParam"], 
                      {"NameConf.mDirMatLUT" : ".."}),
     ('',' --disable-mc')[args.no_mc_labels]
   ])
   workflow['stages'].append(ITSRECOtask)

   #<--------- FT0 reco task 
   FT0RECOtask = createTask(name='ft0reco_'+str(tf), needs=[getDigiTaskName("FT0")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   FT0RECOtask["cmd"] = task_finalizer([
     '${O2_ROOT}/bin/o2-ft0-reco-workflow',
     getDPL_global_options(ccdbbackend=False), # note: when calibrations (or CCDB objects) are reenabled, we need to say ccdbbackend=True
     '--disable-time-offset-calib', # because effect not simulated in MC
     '--disable-slewing-calib', # because effect not simulated in MC
     putConfigValues()
   ])
   workflow['stages'].append(FT0RECOtask)

   #<--------- ITS-TPC track matching task 
   ITSTPCMATCHtask=createTask(name='itstpcMatch_'+str(tf), needs=[TPCRECOtask['name'], ITSRECOtask['name'], FT0RECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='8000', relative_cpu=3/8)
   ITSTPCMATCHtask["cmd"] = task_finalizer([
     '${O2_ROOT}/bin/o2-tpcits-match-workflow',
     getDPL_global_options(bigshm=True),
     ' --tpc-track-reader tpctracks.root',
     '--tpc-native-cluster-reader \"--infile tpc-native-clusters.root\"',
     '--use-ft0',
     putConfigValues(['MFTClustererParam', 
                      'ITSCATrackerParam', 
                      'tpcitsMatch', 
                      'TPCGasParam', 
                      'TPCCorrMap', 
                      'ITSClustererParam', 
                      'GPU_rec_tpc', 
                      'trackTuneParams', 
                      'GlobalParams',
                      'ft0tag'], 
                      {"NameConf.mDirMatLUT" : ".."} | tpcLocalCFreco),
     tpc_corr_scaling_options,
     tpc_corr_options_mc
   ])
   workflow['stages'].append(ITSTPCMATCHtask)

   #<--------- ITS-TPC track matching task 
   TRDTRACKINGtask = createTask(name='trdreco_'+str(tf), needs=[TRDDigitask['name'], ITSTPCMATCHtask['name'], TPCRECOtask['name'], ITSRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   TRDTRACKINGtask['cmd'] = task_finalizer(['${O2_ROOT}/bin/o2-trd-tracklet-transformer',
                                                getDPL_global_options(), 
                                                putConfigValues(),
                                                ('',' --disable-mc')[args.no_mc_labels]])
   if isActive("TRD"):
      workflow['stages'].append(TRDTRACKINGtask)

   #<--------- TRD global tracking 
   # FIXME This is so far a workaround to avoud a race condition for trdcalibratedtracklets.root
   TRDTRACKINGtask2 = createTask(name='trdreco2_'+str(tf), needs=[TRDTRACKINGtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   trd_track_sources = cleanDetectorInputList(dpl_option_from_config(anchorConfig, 'o2-trd-global-tracking', '--track-sources', default_value='TPC,ITS-TPC'))
   TRDTRACKINGtask2['cmd'] = task_finalizer([
      '${O2_ROOT}/bin/o2-trd-global-tracking',
      getDPL_global_options(bigshm=True), 
      ('',' --disable-mc')[args.no_mc_labels],
      putConfigValues(['ITSClustererParam',
                       'ITSCATrackerParam',
                       'trackTuneParams',
                       'GPU_rec_tpc',
                       'TPCGasParam',
                       'GlobalParams',
                       'TPCCorrMap'], {"NameConf.mDirMatLUT" : ".."} | tpcLocalCFreco),
      '--track-sources ' + trd_track_sources,
      tpc_corr_scaling_options, 
      tpc_corr_options_mc])
   if isActive("TRD"):
      workflow['stages'].append(TRDTRACKINGtask2)

   #<--------- TOF reco task
   TOFRECOtask = createTask(name='tofmatch_'+str(tf), needs=[ITSTPCMATCHtask['name'], getDigiTaskName("TOF")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   TOFRECOtask["cmd"] = task_finalizer([
     '${O2_ROOT}/bin/o2-tof-reco-workflow',
     getDPL_global_options(),
     '--use-ccdb',
     putConfigValues(),
     ('',' --disable-mc')[args.no_mc_labels]
   ])
   if isActive('TOF'):
      workflow['stages'].append(TOFRECOtask)

   #<--------- TOF-TPC(-ITS) global track matcher workflow
   toftpcmatchneeds = [TOFRECOtask['name'],
                       TPCRECOtask['name'],
                       ITSTPCMATCHtask['name'],
                       TRDTRACKINGtask2['name'] if isActive("TRD") else None]
   toftracksrcdefault = cleanDetectorInputList(dpl_option_from_config(anchorConfig, 'o2-tof-matcher-workflow', '--track-sources', default_value='TPC,ITS-TPC,TPC-TRD,ITS-TPC-TRD'))
   tofusefit = option_if_available('o2-tof-matcher-workflow', '--use-fit', envfile=async_envfile)
   TOFTPCMATCHERtask = createTask(name='toftpcmatch_'+str(tf), needs=toftpcmatchneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   tofmatcher_cmd_parts = [
     '${O2_ROOT}/bin/o2-tof-matcher-workflow',
     getDPL_global_options(),
     putConfigValues(['ITSClustererParam',
                      'TPCGasParam',
                      'TPCCorrMap',
                      'ITSCATrackerParam',
                      'MFTClustererParam',
                      'GPU_rec_tpc',
                      'ft0tag',
                      'trackTuneParams'], tpcLocalCFreco),
     ' --track-sources ' + toftracksrcdefault,
     (' --combine-devices','')[args.no_combine_dpl_devices],
     tofusefit,
     tpc_corr_scaling_options,
     tpc_corr_options_mc
   ]
   TOFTPCMATCHERtask['cmd'] = task_finalizer(tofmatcher_cmd_parts)
   if isActive('TOF'):
      workflow['stages'].append(TOFTPCMATCHERtask)

   # MFT reco: needing access to kinematics (when assessment enabled)
   mftreconeeds = [getDigiTaskName("MFT")]
   if usebkgcache:
       mftreconeeds += [ BKG_KINEDOWNLOADER_TASK['name'] ]

   #<--------- MFT reco workflow
   MFTRECOtask = createTask(name='mftreco_'+str(tf), needs=mftreconeeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MFTRECOtask['cmd'] = ('','ln -nfs ../bkg_Kine.root . ;')[doembedding]
   MFTRECOtask['cmd'] += task_finalizer([
      '${O2_ROOT}/bin/o2-mft-reco-workflow', 
      getDPL_global_options(), 
      putConfigValues(['MFTTracking', 
                       'MFTAlpideParam', 
                       'ITSClustererParam',
                       'MFTClustererParam']),
      ('','--disable-mc')[args.no_mc_labels],
      ('','--run-assessment')[args.mft_assessment_full]])
   workflow['stages'].append(MFTRECOtask)

   # MCH reco: needing access to kinematics ... so some extra logic needed here
   mchreconeeds = [getDigiTaskName("MCH")]
   if usebkgcache:
      mchreconeeds += [ BKG_KINEDOWNLOADER_TASK['name'] ]

   #<--------- MCH reco workflow
   MCHRECOtask = createTask(name='mchreco_'+str(tf), needs=mchreconeeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MCHRECOtask['cmd'] = ('','ln -nfs ../bkg_Kine.root . ;')[doembedding]
   MCHRECOtask['cmd'] += task_finalizer(
      ['${O2_ROOT}/bin/o2-mch-reco-workflow', 
       getDPL_global_options(), 
       putConfigValues(), 
       ('',' --disable-mc')[args.no_mc_labels],
       '--enable-clusters-root-output'])
   workflow['stages'].append(MCHRECOtask)

   #<--------- MID reco workflow
   MIDRECOtask = createTask(name='midreco_'+str(tf), needs=[getDigiTaskName("MID")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MIDRECOtask['cmd'] = task_finalizer(
      ['${O2_ROOT}/bin/o2-mid-digits-reader-workflow',
       ('',' --disable-mc')[args.no_mc_labels]])
   MIDRECOtask['cmd'] += ' | '
   MIDRECOtask['cmd'] += task_finalizer(['${O2_ROOT}/bin/o2-mid-reco-workflow', 
                                             getDPL_global_options(), 
                                             putConfigValues(),('',' --disable-mc')[args.no_mc_labels]])
   if isActive('MID'):
      workflow['stages'].append(MIDRECOtask)

   #<--------- FDD reco workflow
   FDDRECOtask = createTask(name='fddreco_'+str(tf), needs=[getDigiTaskName("FDD")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   FDDRECOtask['cmd'] = task_finalizer(['${O2_ROOT}/bin/o2-fdd-reco-workflow', 
                                            getDPL_global_options(ccdbbackend=False), 
                                            putConfigValues(),
                                            ('',' --disable-mc')[args.no_mc_labels]])
   workflow['stages'].append(FDDRECOtask)

   #<--------- FV0 reco workflow
   FV0RECOtask = createTask(name='fv0reco_'+str(tf), needs=[getDigiTaskName("FV0")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   FV0RECOtask['cmd'] = task_finalizer(['${O2_ROOT}/bin/o2-fv0-reco-workflow', 
                                            getDPL_global_options(), 
                                            putConfigValues(),
                                            ('',' --disable-mc')[args.no_mc_labels]])
   workflow['stages'].append(FV0RECOtask)

   # calorimeters
   #<--------- EMC reco workflow
   EMCRECOtask = createTask(name='emcalreco_'+str(tf), needs=[getDigiTaskName("EMC")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   # first part   
   EMCRECOtask['cmd'] = task_finalizer([
      '${O2_ROOT}/bin/o2-emcal-reco-workflow', 
      putConfigValues(),
      '--input-type digits',
      '--output-type cells', 
      '--infile emcaldigits.root',
      '--disable-root-output', 
      '--subspecificationOut 1',
      ('',' --disable-mc')[args.no_mc_labels]])
   # second part
   EMCRECOtask['cmd'] += ' | ' 
   EMCRECOtask['cmd'] += task_finalizer([
      '${O2_ROOT}/bin/o2-emcal-cell-recalibrator-workflow', 
      putConfigValues(),
      '--input-subspec 1', 
      '--output-subspec 0',
      '--no-timecalib', 
      '--no-gaincalib',
      (' --isMC','')[args.no_mc_labels]])
   # third part
   EMCRECOtask['cmd'] += ' | ' 
   EMCRECOtask['cmd'] += task_finalizer([
      '${O2_ROOT}/bin/o2-emcal-cell-writer-workflow',
      getDPL_global_options(),
      '--subspec 0', 
      ('',' --disable-mc')[args.no_mc_labels]])
   workflow['stages'].append(EMCRECOtask)

    #<--------- PHS reco workflow
   PHSRECOtask = createTask(name='phsreco_'+str(tf), needs=[getDigiTaskName("PHS")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   PHSRECOtask['cmd'] = task_finalizer([
      '${O2_ROOT}/bin/o2-phos-reco-workflow', 
      getDPL_global_options(), 
      putConfigValues(), 
      ('',' --disable-mc')[args.no_mc_labels]])
   if isActive("PHS"):
      workflow['stages'].append(PHSRECOtask)

   #<--------- CPV reco workflow
   CPVRECOtask = createTask(name='cpvreco_'+str(tf), needs=[getDigiTaskName("CPV")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   CPVRECOtask['cmd'] = task_finalizer(
      ['${O2_ROOT}/bin/o2-cpv-reco-workflow', 
       getDPL_global_options(), 
       putConfigValues(), 
       ('',' --disable-mc')[args.no_mc_labels]])
   if isActive("CPV"):
      workflow['stages'].append(CPVRECOtask)

   #<--------- ZDC reco workflow
   ZDCRECOtask = createTask(name='zdcreco_'+str(tf), needs=[getDigiTaskName("ZDC")], tf=tf, cwd=timeframeworkdir, lab=["RECO", "ZDC"])
   ZDCRECOtask['cmd'] = task_finalizer(
      ['${O2_ROOT}/bin/o2-zdc-digits-reco', 
       getDPL_global_options(), 
       putConfigValues(), 
       ('',' --disable-mc')[args.no_mc_labels]])
   if isActive("ZDC"):
      workflow['stages'].append(ZDCRECOtask)

   ## forward matching
   #<--------- MCH-MID forward matching
   MCHMIDMATCHtask = createTask(name='mchmidMatch_'+str(tf), needs=[MCHRECOtask['name'], MIDRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MCHMIDMATCHtask['cmd'] = task_finalizer(
      ['${O2_ROOT}/bin/o2-muon-tracks-matcher-workflow', 
       getDPL_global_options(ccdbbackend=False),
       putConfigValues(),
       ('',' --disable-mc')[args.no_mc_labels]])
   if isActive("MID") and isActive("MCH"):
      workflow['stages'].append(MCHMIDMATCHtask)

   #<--------- MFT-MCH forward matching
   forwardmatchneeds = [MCHRECOtask['name'],
                        MFTRECOtask['name'],
                        MCHMIDMATCHtask['name'] if isActive("MID") else None]
   MFTMCHMATCHtask = createTask(name='mftmchMatch_'+str(tf), needs=forwardmatchneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MFTMCHMATCHtask['cmd'] = task_finalizer(
      ['${O2_ROOT}/bin/o2-globalfwd-matcher-workflow',
        putConfigValues(['ITSAlpideConfig',
                         'MFTAlpideConfig',
                         'FwdMatching'],{"FwdMatching.useMIDMatch": "true" if isActive("MID") else "false"}),
       ('',' --disable-mc')[args.no_mc_labels]])

   if args.fwdmatching_assessment_full == True:
      MFTMCHMATCHtask['cmd'] += ' | '
      MFTMCHMATCHtask['cmd'] += task_finalizer(
         ['${O2_ROOT}/bin/o2-globalfwd-assessment-workflow',
          getDPL_global_options(),
          ('',' --disable-mc')[args.no_mc_labels]])
   workflow['stages'].append(MFTMCHMATCHtask)

   if args.fwdmatching_save_trainingdata == True:
      MFTMCHMATCHTraintask = createTask(name='mftmchMatchTrain_'+str(tf), needs=[MCHMIDMATCHtask['name'], MFTRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
      MFTMCHMATCHTraintask['cmd'] = '${O2_ROOT}/bin/o2-globalfwd-matcher-workflow ' + putConfigValues(['ITSAlpideConfig','MFTAlpideConfig'],{"FwdMatching.useMIDMatch":"true"})
      MFTMCHMATCHTraintask['cmd']+= getDPL_global_options()
      workflow['stages'].append(MFTMCHMATCHTraintask)

   # HMP tasks
   #<--------- HMP forward matching
   HMPRECOtask = createTask(name='hmpreco_'+str(tf), needs=[getDigiTaskName('HMP')], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   HMPRECOtask['cmd'] = task_finalizer(
      ['${O2_ROOT}/bin/o2-hmpid-digits-to-clusters-workflow', 
       getDPL_global_options(ccdbbackend=False), 
       putConfigValues()])
   workflow['stages'].append(HMPRECOtask)

   #<--------- HMP forward matching
   hmpmatchneeds = [HMPRECOtask['name'], 
                    ITSTPCMATCHtask['name'], 
                    TOFTPCMATCHERtask['name'] if isActive("TOF") else None, 
                    TRDTRACKINGtask2['name'] if isActive("TRD") else None]
   hmpmatchneeds = [ n for n in hmpmatchneeds if n != None ]
   hmp_match_sources = cleanDetectorInputList(dpl_option_from_config(anchorConfig, 'o2-hmpid-matcher-workflow', '--track-sources', default_value='ITS-TPC,ITS-TPC-TRD,TPC-TRD'))
   HMPMATCHtask = createTask(name='hmpmatch_'+str(tf), needs=hmpmatchneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   HMPMATCHtask['cmd'] = task_finalizer(
      ['${O2_ROOT}/bin/o2-hmpid-matcher-workflow',
       '--track-sources ' + hmp_match_sources,
        getDPL_global_options(), 
        putConfigValues()
      ])
   workflow['stages'].append(HMPMATCHtask)

   #<---------- primary vertex finding
   pvfinder_sources = dpl_option_from_config(anchorConfig,
                                             'o2-primary-vertexing-workflow',
                                             '--vertexing-sources',
                                             default_value='ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,FDD,HMP,FV0,TRD,MCH,CTP')
   pvfinder_sources = cleanDetectorInputList(pvfinder_sources)

   pvfinder_matching_sources = dpl_option_from_config(anchorConfig,
                                                      'o2-primary-vertexing-workflow',
                                                      '--vertex-track-matching-sources',
                                                      default_value='ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,FDD,HMP,FV0,TRD,MCH,CTP')
   pvfinder_matching_sources = cleanDetectorInputList(pvfinder_matching_sources)

   pvfinderneeds = [TRDTRACKINGtask2['name'] if isActive("TRD") else None,
                    FT0RECOtask['name'] if isActive("FT0") else None,
                    FV0RECOtask['name'] if isActive("FV0") else None,
                    EMCRECOtask['name'] if isActive("EMC") else None,
                    PHSRECOtask['name'] if isActive("PHS") else None,
                    CPVRECOtask['name'] if isActive("CPV") else None,
                    FDDRECOtask['name'] if isActive("FDD") else None,
                    ZDCRECOtask['name'] if isActive("ZDC") else None,
                    HMPMATCHtask['name'] if isActive("HMP") else None,
                    ITSTPCMATCHtask['name'] if isActive("ITS") and isActive("TPC") else None,
                    TOFTPCMATCHERtask['name'] if isActive("TPC") and isActive("TOF") else None,
                    MFTMCHMATCHtask['name'] if isActive("MFT") and isActive("MCH") else None,
                    MCHMIDMATCHtask['name'] if isActive("MCH") and isActive("MID") else None]
   pvfinderneeds = [ p for p in pvfinderneeds if p != None ]

   PVFINDERtask = createTask(name='pvfinder_'+str(tf), needs=pvfinderneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=NWORKERS_TF, mem='4000')
   PVFINDERtask['cmd'] = task_finalizer(
      [ '${O2_ROOT}/bin/o2-primary-vertexing-workflow', 
         getDPL_global_options(),
         putConfigValues(['ITSAlpideParam',
                          'MFTAlpideParam', 
                          'pvertexer', 
                          'TPCGasParam', 
                          'TPCCorrMap', 
                          'ft0tag'], 
                          {"NameConf.mDirMatLUT" : ".."}),
         '--vertexing-sources ' + pvfinder_sources,
         '--vertex-track-matching-sources ' + pvfinder_matching_sources,
         (' --combine-source-devices','')[args.no_combine_dpl_devices],
         ('',' --disable-mc')[args.no_mc_labels]
     ])
   workflow['stages'].append(PVFINDERtask)

   #<------------- secondary vertexer
   svfinder_threads = ' --threads 1 '
   svfinder_cpu = 1
   if COLTYPE == "PbPb" or (doembedding and COLTYPEBKG == "PbPb"):
     svfinder_threads = ' --threads 8 '
     svfinder_cpu = 8
   
   svfinder_sources = dpl_option_from_config(anchorConfig,
                          'o2-primary-vertexing-workflow',
                          '--vertex-track-matching-sources',
                          default_value='ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,ZDC,FDD,HMP,FV0,TRD,MCH,CTP')
   svfinder_sources = cleanDetectorInputList(svfinder_sources)
   SVFINDERtask = createTask(name='svfinder_'+str(tf), needs=[PVFINDERtask['name'], FT0FV0EMCCTPDIGItask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=svfinder_cpu, mem='5000')   
   SVFINDERtask['cmd'] = task_finalizer(
   [ '${O2_ROOT}/bin/o2-secondary-vertexing-workflow', 
      getDPL_global_options(bigshm=True),
      svfinder_threads,
      putConfigValues(['svertexer', 'TPCCorrMap', 'GlobalParams'], {"NameConf.mDirMatLUT" : ".."} | tpcLocalCFreco),
      tpc_corr_scaling_options,
      tpc_corr_options_mc,
      '--vertexing-sources ' + svfinder_sources,
      ('--combine-source-devices','')[args.no_combine_dpl_devices],
      ('',' --disable-strangeness-tracker')[args.no_strangeness_tracking],
      ('',' --disable-mc')[args.no_mc_labels and not args.no_strangeness_tracking] # strangeness tracking may require MC labels
   ])
   workflow['stages'].append(SVFINDERtask)

   #<------------- AOD producer
   # TODO This needs further refinement, sources and dependencies should be constructed dynamically
   aod_info_souces_default = 'ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,ZDC,FDD,HMP,FV0,TRD,MCH,CTP'
   aodinfosources = dpl_option_from_config(anchorConfig, 'o2-aod-producer-workflow', '--info-sources', default_value=aod_info_souces_default)
   aodinfosources = cleanDetectorInputList(aodinfosources)
   aodneeds = [PVFINDERtask['name'], SVFINDERtask['name']]

   if usebkgcache:
     aodneeds += [ BKG_KINEDOWNLOADER_TASK['name'] ]

   aod_df_id = '{0:03}'.format(tf)

   import os
   aod_creator = os.getenv("JALIEN_USER")
   if aod_creator == None:
      # we use JAliEn to determine the user and capture it's output into a variable via redirect_stdout
      import io
      from contextlib import redirect_stdout
      f = io.StringIO()
      with redirect_stdout(f):
         if JAlien(['whoami']) == 0:
            aod_creator = f.getvalue().strip()
            print (f"Determined GRID username {aod_creator}")

   # this option might not be universally available
   created_by_option = option_if_available('o2-aod-producer-workflow', '--created-by', envfile=async_envfile)
   if created_by_option != '':
      created_by_option += ' ' + aod_creator

   AODtask = createTask(name='aod_'+str(tf), needs=aodneeds, tf=tf, cwd=timeframeworkdir, lab=["AOD"], mem='4000', cpu='1')
   AODtask['cmd'] = ('','ln -nfs ../bkg_Kine.root . ;')[doembedding]
   AODtask['cmd'] += '[ -f AO2D.root ] && rm AO2D.root; '
   AODtask['cmd'] += task_finalizer([
      "${O2_ROOT}/bin/o2-aod-producer-workflow",
      "--reco-mctracks-only 1",
      "--aod-writer-keep dangling",
      "--aod-writer-resfile AO2D",
      '--aod-writer-resmode "UPDATE"',
      f"--run-number {args.run}",
      getDPL_global_options(bigshm=True),
      f"--info-sources {aodinfosources}",
      f"--lpmp-prod-tag {args.productionTag}",
      "--anchor-pass ${ALIEN_JDL_LPMANCHORPASSNAME:-unknown}",
      "--anchor-prod ${ALIEN_JDL_LPMANCHORPRODUCTION:-unknown}",
      created_by_option,
      "--combine-source-devices" if not args.no_combine_dpl_devices else "",
      "--disable-mc" if args.no_mc_labels else "",
      "--enable-truncation 0" if environ.get("O2DPG_AOD_NOTRUNCATE") or environ.get("ALIEN_JDL_O2DPG_AOD_NOTRUNCATE") else "",
      "--disable-strangeness-tracker" if args.no_strangeness_tracking else "",
      f"--aod-timeframe-id ${{ALIEN_PROC_ID}}{aod_df_id}" if not args.run_anchored else "",
   ])
   # Consider in future: AODtask['disable_alternative_reco_software'] = True # do not apply reco software here (we prefer latest aod converter)
   workflow['stages'].append(AODtask)

   if includeTPCResiduals:
      print ("Adding TPC residuals extraction and aggregation")

      #<------------- TPC residuals extraction
      scdcalib_vertex_sources = cleanDetectorInputList(dpl_option_from_config(anchorConfig,
                                                       'o2-tpc-scdcalib-interpolation-workflow',
                                                       '--vtx-sources',
                                                       default_value='ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,FDD,HMP,FV0,TRD,MCH,CTP'))

      scdcalib_track_sources = cleanDetectorInputList(dpl_option_from_config(anchorConfig,
                                                      'o2-tpc-scdcalib-interpolation-workflow',
                                                      '--tracking-sources',
                                                      default_value='ITS-TPC,TPC-TRD,ITS-TPC-TRD,TPC-TOF,ITS-TPC-TOF,TPC-TRD-TOF,ITS-TPC-TRD-TOF,MFT-MCH,MCH-MID,ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,FDD,HMP,FV0,TRD,MCH,CTP'))

      scdcalib_track_extraction = cleanDetectorInputList(dpl_option_from_config(anchorConfig,
                                                         'o2-tpc-scdcalib-interpolation-workflow',
                                                         '--tracking-sources-map-extraction',
                                                         default_value='ITS-TPC'))

      SCDCALIBtask = createTask(name='scdcalib_'+str(tf), needs=[PVFINDERtask['name']], tf=tf, cwd=timeframeworkdir, lab=["CALIB"], mem='4000')
      SCDCALIBtask['cmd'] = task_finalizer(
         [ '${O2_ROOT}/bin/o2-tpc-scdcalib-interpolation-workflow',
           getDPL_global_options(bigshm=True),
           putConfigValues(['scdcalib']),
           '--vtx-sources ' + scdcalib_vertex_sources,
           '--tracking-sources ' + scdcalib_track_sources,
           '--tracking-sources-map-extraction ' + scdcalib_track_extraction,
           '--sec-per-slot 1 ',
           '--send-track-data'
        ])
      workflow['stages'].append(SCDCALIBtask)

      #<------------- TPC residuals aggregator
      scdaggreg_secperslot = dpl_option_from_config(anchorConfig,
                                                    'o2-calibration-residual-aggregator',
                                                    '--sec-per-slot',
                                                    default_value='600')
      scdaggreg_outputtype = dpl_option_from_config(anchorConfig,
                                                    'o2-calibration-residual-aggregator',
                                                    '--output-type',
                                                    default_value='trackParams,unbinnedResid')

      SCDAGGREGtask = createTask(name='scdaggreg_'+str(tf), needs=[SCDCALIBtask['name']], tf=tf, cwd=timeframeworkdir, lab=["CALIB"], mem='1500')
      SCDAGGREGtask['cmd'] = task_finalizer(
         [ '${O2_ROOT}/bin/o2-calibration-residual-aggregator',
           getDPL_global_options(bigshm=True),
           '--sec-per-slot ' + scdaggreg_secperslot,
           '--enable-ctp ',
           '--enable-track-input',
           '--output-dir ./',
           '--output-type ' +  scdaggreg_outputtype,
           '--meta-output-dir /dev/null'
         ])
      workflow['stages'].append(SCDAGGREGtask)

   # conditional
   #
   # QC tasks follow
   #

   if includeFullQC or includeLocalQC:

     def addQCPerTF(taskName, needs, readerCommand, configFilePath, objectsFile=''):
       task = createTask(name=taskName + '_local_' + str(tf), needs=needs, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=1, mem='2000')
       objectsFile = objectsFile if len(objectsFile) > 0 else taskName + '.root'

       def remove_json_prefix(path):
           return re.sub(r'^json://', '', path)

       configFilePathOnDisk = remove_json_prefix(configFilePath)
       # we check if the configFilePath actually exists in the currently loaded software. Otherwise we exit immediately and gracefully
       task['cmd'] = ' if [ -f ' + configFilePathOnDisk + ' ]; then { '
        # The actual QC command
        # the --local-batch argument will make QC Tasks store their results in a file and merge with any existing objects
       task['cmd'] += f'{readerCommand} | o2-qc --config {configFilePath}' + \
                     f' --local-batch ../{qcdir}/{objectsFile}' + \
                     f' --override-values "qc.config.database.host={args.qcdbHost};qc.config.Activity.number={args.run};qc.config.Activity.type=PHYSICS;qc.config.Activity.periodName={args.productionTag};qc.config.Activity.beamType={args.col};qc.config.Activity.start={args.timestamp};qc.config.conditionDB.url={args.conditionDB}"' + \
                     ' ' + getDPL_global_options(ccdbbackend=False)
       task['cmd'] += ' ;} else { echo "Task ' + taskName + ' not performed due to config file not found "; } fi'

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
     # TODO: check if the readerCommand also reperforms tracklet construction (which already done in digitization)
     if isActive('TRD'):
         addQCPerTF(taskName='trdDigitsQC',
                needs=[TRDDigitask['name']],
                readerCommand='o2-trd-trap-sim --disable-root-output true',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/trd-standalone-task.json')

         addQCPerTF(taskName='trdTrackingQC',
                needs=[TRDTRACKINGtask2['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC-TRD,TPC-TRD" --cluster-types none',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/trd-tracking-task.json')

     ### TOF
     if isActive('TOF'):
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
                readerCommand='o2-ft0-recpoints-reader-workflow --infile o2reco_ft0.root',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/ft0-reconstruction-config.json')

     ### FV0
     addQCPerTF(taskName='FV0DigitsQC',
                needs=[getDigiTaskName("FV0")],
                readerCommand='o2-fv0-digit-reader-workflow --fv0-digit-infile fv0digits.root',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/fv0-digits.json')

     ### FDD
     addQCPerTF(taskName='FDDRecPointsQC',
                needs=[FDDRECOtask['name']],
                readerCommand='o2-fdd-recpoints-reader-workflow --fdd-recpoints-infile o2reco_fdd.root',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/fdd-recpoints.json')

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
     addQCPerTF(taskName='ITSTrackSimTaskQC',
                needs=[ITSRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "ITS" --cluster-types "ITS"',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/its-mc-tracks-qc.json')

     addQCPerTF(taskName='ITSTracksClustersQC',
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
                
     ### MCH
     if isActive('MCH'):
        addQCPerTF(taskName='MCHDigitsTaskQC',
                needs=[MCHRECOtask['name']],
                readerCommand='o2-mch-digits-reader-workflow',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mch-digits-task.json')
        addQCPerTF(taskName='MCHErrorsTaskQC',
                needs=[MCHRECOtask['name']],
                readerCommand='o2-mch-errors-reader-workflow',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mch-errors-task.json')
        addQCPerTF(taskName='MCHRecoTaskQC',
                needs=[MCHRECOtask['name']],
                readerCommand='o2-mch-reco-workflow --disable-root-output',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mch-reco-task.json')
        addQCPerTF(taskName='MCHTracksTaskQC',
                needs=[MCHRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types MCH --cluster-types MCH',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mch-tracks-task.json')

     ### MCH + MID
     if isActive('MCH') and isActive('MID'):
        addQCPerTF(taskName='MCHMIDTracksTaskQC',
                needs=[MCHMIDMATCHtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "MCH,MID,MCH-MID" --cluster-types "MCH,MID"',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mchmid-tracks-task.json')
  
     ### MCH && MID && MFT || MCH && MFT
     if isActive('MCH') and isActive('MID') and isActive('MFT') :
        addQCPerTF(taskName='MUONTracksMFTTaskQC',
                needs=[MFTMCHMATCHtask['name'], MCHMIDMATCHtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "MFT,MCH,MID,MCH-MID,MFT-MCH,MFT-MCH-MID" --cluster-types "MCH,MID,MFT"',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mftmchmid-tracks-task.json')
     elif isActive('MCH') and isActive('MFT') :
        addQCPerTF(taskName='MCHMFTTaskQC',
                needs=[MFTMCHMATCHtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "MCH,MFT,MFT-MCH" --cluster-types "MCH,MFT"',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/mftmch-tracks-task.json')

 
   #<------------------ TPC - time-series objects
   # initial implementation taken from comments in https://its.cern.ch/jira/browse/O2-4612
   # TODO: this needs to be made configurable (as a function of which detectors are actually present)
   tpctsneeds = [ TPCRECOtask['name'],
                  ITSTPCMATCHtask['name'],
                  TOFTPCMATCHERtask['name'],
                  PVFINDERtask['name']
                ]
   TPCTStask = createTask(name='tpctimeseries_'+str(tf), needs=tpctsneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='2000', cpu='1')
   TPCTStask['cmd'] = 'o2-global-track-cluster-reader --disable-mc --cluster-types "FT0,TOF,TPC" --track-types "ITS,TPC,ITS-TPC,ITS-TPC-TOF,ITS-TPC-TRD-TOF"'
   TPCTStask['cmd'] += ' --primary-vertices '
   TPCTStask['cmd'] += ' | o2-tpc-time-series-workflow --enable-unbinned-root-output --sample-unbinned-tsallis --sampling-factor 0.01 '
   TPCTStask['cmd'] += putConfigValues() + ' ' + getDPL_global_options(bigshm=True)
   workflow['stages'].append(TPCTStask)

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

if not args.make_evtpool:
   # AOD merging as one global final step
   aodmergerneeds = ['aod_' + str(tf) for tf in range(1, NTIMEFRAMES + 1)]
   AOD_merge_task = createTask(name='aodmerge', needs = aodmergerneeds, lab=["AOD"], mem='2000', cpu='1')
   AOD_merge_task['cmd'] = ' set -e ; [ -f aodmerge_input.txt ] && rm aodmerge_input.txt; '
   AOD_merge_task['cmd'] += ' for i in `seq 1 ' + str(NTIMEFRAMES) + '`; do echo "tf${i}/AO2D.root" >> aodmerge_input.txt; done; '
   AOD_merge_task['cmd'] += ' o2-aod-merger --input aodmerge_input.txt --output AO2D_pre.root'
   # reindex the BC + connected tables because it there could be duplicate BC entries due to the orbit-early treatment
   # see https://its.cern.ch/jira/browse/O2-6227
   AOD_merge_task['cmd'] += ' ; root -q -b -l "${O2DPG_ROOT}/MC/utils/AODBcRewriter.C(\\\"AO2D_pre.root\\\",\\\"AO2D.root\\\")"'
   # produce MonaLisa event stat file
   AOD_merge_task['cmd'] += ' ; ${O2DPG_ROOT}/MC/bin/o2dpg_determine_eventstat.py'
   AOD_merge_task['alternative_alienv_package'] = "None" # we want latest software for this step
   workflow['stages'].append(AOD_merge_task)

   job_merging = False
   if includeFullQC:
      workflow['stages'].extend(include_all_QC_finalization(ntimeframes=NTIMEFRAMES, standalone=False, run=args.run, productionTag=args.productionTag, conditionDB=args.conditionDB, qcdbHost=args.qcdbHost, beamType=args.col))

   if includeAnalysis:
      # include analyses and potentially final QC upload tasks
      add_analysis_tasks(workflow["stages"], needs=[AOD_merge_task["name"]], is_mc=True, collision_system=COLTYPE)
      if QUALITYCONTROL_ROOT:
         add_analysis_qc_upload_tasks(workflow["stages"], args.productionTag, args.run, "passMC")
else:
   wfneeds=['sgngen_' + str(tf) for tf in range(1, NTIMEFRAMES + 1)]
   tfpool=['tf' + str(tf) + '/genevents_Kine.root' for tf in range(1, NTIMEFRAMES + 1)]
   POOL_merge_task = createTask(name='poolmerge', needs=wfneeds, lab=["POOL"], mem='2000', cpu='1')
   POOL_merge_task['cmd'] = '${O2DPG_ROOT}/UTILS/root_merger.py -o evtpool.root -i ' + ','.join(tfpool)
   # also create the stat file with the event count
   POOL_merge_task['cmd'] += '; RC=$?; root -l -q -b -e "auto f=TFile::Open(\\\"evtpool.root\\\"); auto t=(TTree*)f->Get(\\\"o2sim\\\"); int n=t->GetEntries(); std::ofstream((\\\"0_0_0_\\\"+std::to_string(n)+\\\".stat\\\").c_str()) << \\\"# MonaLisa stat file for event pools\\\";" ; [[ ${RC} == 0 ]]'
   workflow['stages'].append(POOL_merge_task)

# if TPC residuals extraction was requested, we have to merge per-tf trees
if includeTPCResiduals:
   tpcResidMergingNeeds = ['scdaggreg_' + str(tf) for tf in range(1, NTIMEFRAMES + 1)]
   TPCResid_merge_task = createTask(name='tpcresidmerge', needs = tpcResidMergingNeeds, lab=["CALIB"], mem='2000', cpu='1')
   TPCResid_merge_task['cmd'] = ' set -e ; [ -f tpcresidmerge_input.txt ] && rm tpcresidmerge_input.txt; '
   TPCResid_merge_task['cmd'] += ' for i in `seq 1 ' + str(NTIMEFRAMES) + '`; do find tf${i} -name "o2tpc_residuals_*.root" >> tpcresidmerge_input.txt; done; '
   TPCResid_merge_task['cmd'] += '${O2DPG_ROOT}/UTILS/root_merger.py -o o2tpc_residuals.root -i $(grep -v \"^$\" tpcresidmerge_input.txt | paste -sd, -)'
   workflow['stages'].append(TPCResid_merge_task)


# adjust for alternate (RECO) software environments
adjust_RECO_environment(workflow, args.alternative_reco_software)

dump_workflow(workflow['stages'], args.o, meta=vars(args))

# dump a config that can be used to reproduce this workflow
task_finalizer.dump_collected_config("final_config.json")

exit (0)
