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
from os.path import join, dirname, isdir
import random
import json
import itertools
import time
import requests, re

sys.path.append(join(dirname(__file__), '.', 'o2dpg_workflow_utils'))

from o2dpg_workflow_utils import createTask, dump_workflow
from o2dpg_qc_finalization_workflow import include_all_QC_finalization
from o2dpg_sim_config import create_sim_config

parser = argparse.ArgumentParser(description='Create an ALICE (Run3) MC simulation workflow')

# the run-number of data taking or default if unanchored
parser.add_argument('-run', type=int, help="Run number for this MC", default=300000)
parser.add_argument('-productionTag',help="Production tag for this MC", default='unknown')
# the timestamp at which this MC workflow will be run
# - in principle it should be consistent with the time of the "run" number above
# - some external tool should sample it within
# - we can also sample it ourselfs here
parser.add_argument('--timestamp', type=int, help="Anchoring timestamp (defaults to now)", default=-1)
parser.add_argument('--anchor-config',help="JSON file to contextualise workflow with external configs (config values etc.) for instance comping from data reco workflows.", default='')
parser.add_argument('-ns',help='number of signal events / timeframe', default=20)
parser.add_argument('-gen',help='generator: pythia8, extgen', default='')
parser.add_argument('-proc',help='process type: inel, dirgamma, jets, ccbar, ...', default='')
parser.add_argument('-trigger',help='event selection: particle, external', default='')
parser.add_argument('-ini',help='generator init parameters file (full paths required), for example: ${O2DPG_ROOT}/MC/config/PWGHF/ini/GeneratorHF.ini', default='')
parser.add_argument('-confKey',help='generator or trigger configuration key values, for example: "GeneratorPythia8.config=pythia8.cfg;A.x=y"', default='')

parser.add_argument('-interactionRate',help='Interaction rate, used in digitization', default=-1)
parser.add_argument('-bcPatternFile',help='Bunch crossing pattern file, used in digitization (a file name or "ccdb")', default='')
parser.add_argument('-eCM',help='CMS energy', default=-1)
parser.add_argument('-eA',help='Beam A energy', default=-1) #6369 PbPb, 2.510 pp 5 TeV, 4 pPb
parser.add_argument('-eB',help='Beam B energy', default=-1)
parser.add_argument('-col',help='collision system: pp, PbPb, pPb, Pbp, ..., in case of embedding collision system of signal', default='pp')
parser.add_argument('-field',help='L3 field rounded to kGauss, allowed: values +-2,+-5 and 0; +-5U for uniform field', default='-5')

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

parser.add_argument('-e',help='simengine', default='TGeant4')
parser.add_argument('-tf',help='number of timeframes', default=2)
parser.add_argument('--production-offset',help='Offset determining bunch-crossing '
                     + ' range within a (GRID) production. This number sets first orbit to '
                     + 'Offset x Number of TimeFrames x OrbitsPerTimeframe (up for further sophistication)', default=0)
parser.add_argument('-j',help='number of workers (if applicable)', default=8, type=int)
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

# power feature (for playing) --> does not appear in help message
#  help='Treat smaller sensors in a single digitization')
parser.add_argument('--combine-smaller-digi', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--combine-dpl-devices', action='store_true', help=argparse.SUPPRESS)
parser.add_argument('--combine-tpc-clusterization', action='store_true', help=argparse.SUPPRESS) #<--- useful for small productions (pp, low interaction rate, small number of events)
parser.add_argument('--first-orbit', default=0, type=int, help=argparse.SUPPRESS)  # to set the first orbit number of the run for HBFUtils (only used when anchoring)
                                                            # (consider doing this rather in O2 digitization code directly)
parser.add_argument('--run-anchored', action='store_true', help=argparse.SUPPRESS)

# QC related arguments
parser.add_argument('--include-qc', '--include-full-qc', action='store_true', help='includes QC in the workflow, both per-tf processing and finalization')
parser.add_argument('--include-local-qc', action='store_true', help='includes the per-tf QC, but skips the finalization (e.g. to allow for subjob merging first)')

# O2 Analysis related arguments
parser.add_argument('--include-analysis', '--include-an', '--analysis',
                    action='store_true', help='a flag to include O2 analysis in the workflow')

# MFT reconstruction configuration
parser.add_argument('--mft-reco-full', action='store_true', help='enables complete mft reco instead of simplified misaligned version')
parser.add_argument('--mft-assessment-full', action='store_true', help='enables complete assessment of mft reco')

# Global Forward reconstruction configuration
parser.add_argument('--fwdmatching-assessment-full', action='store_true', help='enables complete assessment of global forward reco')

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

# with this we can tailor the workflow to the presence of
# certain detectors
activeDetectors = anchorConfig.get('o2-ctf-reader-workflow-options',{}).get('onlyDet','all')
# convert to set/hashmap
activeDetectors = { det:1 for det in activeDetectors.split(",") }

# see if a detector is in list of activeDetectors
def isActive(detID):
   """
   detID == the usual detID string (3 letters)
   """
   if "all" in activeDetectors:
      return True
   return detID in activeDetectors

def addWhenActive(detID, needslist, appendstring):
   if isActive(detID):
      needslist.append(appendstring)


def retrieve_sor(run_number):
    """
    retrieves start of run (sor)
    from the RCT/RunInformation table with a simple http request
    in case of problems, 0 will be returned
    """
    url="http://alice-ccdb.cern.ch/browse/RCT/RunInformation/"+str(run_number)
    ansobject=requests.get(url)
    tokens=ansobject.text.split("\n")

    SOR=0
    # extract SOR by pattern matching
    for t in tokens:
      match_object=re.match("\s*(SOR\s*=\s*)([0-9]*)\s*", t)
      if match_object != None:
         SOR=match_object[2]
         break

    return int(SOR)


# ----------- START WORKFLOW CONSTRUCTION -----------------------------

# set the time to start of run (if no timestamp specified)
if args.timestamp==-1:
   args.timestamp = retrieve_sor(args.run)
   assert (args.timestamp != 0)

NTIMEFRAMES=int(args.tf)
NWORKERS=args.j
MODULES = "--skipModules ZDC" if not args.with_ZDC else ""
SIMENGINE=args.e
BFIELD=args.field
RNDSEED=args.seed # typically the argument should be the jobid, but if we get None the current time is used for the initialisation
random.seed(RNDSEED)
print ("Using initialisation seed: ", RNDSEED)
SIMSEED = random.randint(1, 900000000 - NTIMEFRAMES - 1) # PYTHIA maximum seed is 900M for some reason

workflow={}
workflow['stages'] = []


def getDPL_global_options(bigshm=False):
   common=" -b --run " # --driver-client-backend ws:// "
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

        CONFKEYBKG=''
        if args.confKeyBkg!= '':
           CONFKEYBKG=' --configKeyValues "' + args.confKeyBkg + '"'

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
            CONFKEYBKG='--configKeyValues "GeneratorPythia8.config=pythia8bkg.cfg;' + args.confKeyBkg + '"'

        workflow['stages'].append(BKG_CONFIG_task)

        # background task configuration
        INIBKG=''
        if args.iniBkg!= '':
           INIBKG=' --configFile ' + args.iniBkg

        BKGtask=createTask(name='bkgsim', lab=["GEANT"], needs=[BKG_CONFIG_task['name']], cpu=NWORKERS )
        BKGtask['cmd']='${O2_ROOT}/bin/o2-sim -e ' + SIMENGINE   + ' -j ' + str(NWORKERS) + ' -n '     + str(NBKGEVENTS) \
                     + ' -g  '      + str(GENBKG) + ' '    + str(MODULES)  + ' -o bkg ' + str(INIBKG)                    \
                     + ' --field '  + str(BFIELD) + ' '    + str(CONFKEYBKG) \
                     + ('',' --timestamp ' + str(args.timestamp))[args.timestamp!=-1] + ' --run ' + str(args.run)

        if not "all" in activeDetectors:
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
smallsensorlist = [ "ITS", "TOF", "FDD", "MCH", "MID", "MFT", "HMP", "EMC", "PHS", "CPV" ]
if args.with_ZDC:
   smallsensorlist += [ "ZDC" ]
# a list of detectors that serve as input for the trigger processor CTP --> these need to be processed together for now
ctp_trigger_inputlist = [ "FT0", "FV0" ]

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
MATBUD_DOWNLOADER_TASK = createTask(name='matbuddownloader', cpu='0')
MATBUD_DOWNLOADER_TASK['cmd'] = '[ -f matbud.root ] || ${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch/ -p GLO/Param/MatLUT -o matbud.root --no-preserve-path --timestamp ' + str(args.timestamp)
workflow['stages'].append(MATBUD_DOWNLOADER_TASK)

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
   CONFKEY=''
   if args.confKey!= '':
      CONFKEY=' --configKeyValues "' + args.confKey + '"'
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

   # produce the signal configuration
   SGN_CONFIG_task=createTask(name='gensgnconf_'+str(tf), tf=tf, cwd=timeframeworkdir)
   SGN_CONFIG_task['cmd'] = 'echo "placeholder / dummy task"'
   if GENERATOR == 'pythia8' and PROCESS!='':
      SGN_CONFIG_task['cmd'] = '${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
                                --output=pythia8.cfg                                     \
                                --seed='+str(TFSEED)+'                                   \
                                --idA='+str(PDGA)+'                                      \
                                --idB='+str(PDGB)+'                                      \
                                --eCM='+str(ECMS)+'                                      \
                                --eA='+str(EBEAMA)+'                                     \
                                --eB='+str(EBEAMB)+'                                     \
                                --process='+str(PROCESS)+'                               \
                                --ptHatMin='+str(PTHATMIN)+'                             \
                                --ptHatMax='+str(PTHATMAX)
      if WEIGHTPOW   > 0:
         SGN_CONFIG_task['cmd'] = SGN_CONFIG_task['cmd'] + ' --weightPow=' + str(WEIGHTPOW)
      # if we configure pythia8 here --> we also need to adjust the configuration
      # TODO: we need a proper config container/manager so as to combine these local configs with external configs etc.
      CONFKEY='--configKeyValues "GeneratorPythia8.config=pythia8.cfg'+';'+args.confKey+'"'

   # elif GENERATOR == 'extgen': what do we do if generator is not pythia8?
       # NOTE: Generator setup might be handled in a different file or different files (one per
       # possible generator)

   #if CONFKEY=='':
   #   print('o2dpg_sim_workflow: Error! configuration file not provided')
   #   exit(1)

   workflow['stages'].append(SGN_CONFIG_task)

   # -----------------
   # transport signals
   # -----------------
   signalprefix='sgn_' + str(tf)
   signalneeds=[ SGN_CONFIG_task['name'] ]

   # add embedIntoFile only if embeddPattern does contain a '@'
   embeddinto= "--embedIntoFile ../bkg_MCHeader.root" if (doembedding & ("@" in args.embeddPattern)) else ""
   #embeddinto= "--embedIntoFile ../bkg_MCHeader.root" if doembedding else ""
   if doembedding:
       if not usebkgcache:
            signalneeds = signalneeds + [ BKGtask['name'] ]
       else:
            signalneeds = signalneeds + [ BKG_HEADER_task['name'] ]
   SGNtask=createTask(name='sgnsim_'+str(tf), needs=signalneeds, tf=tf, cwd='tf'+str(tf), lab=["GEANT"], relative_cpu=5/8, n_workers=NWORKERS, mem='2000')
   SGNtask['cmd']='${O2_ROOT}/bin/o2-sim -e '  + str(SIMENGINE) + ' '    + str(MODULES)  + ' -n ' + str(NSIGEVENTS) + ' --seed ' + str(TFSEED) \
                  + ' --field ' + str(BFIELD)    + ' -j ' + str(NWORKERS) + ' -g ' + str(GENERATOR)   \
                  + ' '         + str(TRIGGER)   + ' '    + str(CONFKEY)  + ' '    + str(INIFILE)     \
                  + ' -o '      + signalprefix   + ' '    + embeddinto                                \
                  + ('', ' --timestamp ' + str(args.timestamp))[args.timestamp!=-1] + ' --run ' + str(args.run)
   if not "all" in activeDetectors:
      SGNtask['cmd'] += ' --readoutDetectors ' + " ".join(activeDetectors)
   workflow['stages'].append(SGNtask)

   # some tasks further below still want geometry + grp in fixed names, so we provide it here
   # Alternatively, since we have timeframe isolation, we could just work with standard o2sim_ files
   # We need to be careful here and distinguish between embedding and non-embedding cases
   # (otherwise it can confuse itstpcmatching, see O2-2026). This is because only one of the GRPs is updated during digitization.
   if doembedding:
      LinkGRPFileTask=createTask(name='linkGRP_'+str(tf), needs=[BKG_HEADER_task['name'] if usebkgcache else BKGtask['name'] ], tf=tf, cwd=timeframeworkdir, cpu='0',mem='0')
      LinkGRPFileTask['cmd']='''
                             ln -nsf ../bkg_grp.root o2sim_grp.root;
                             ln -nsf ../bkg_geometry.root o2sim_geometry.root;
                             ln -nsf ../bkg_geometry.root bkg_geometry.root;
                             ln -nsf ../bkg_geometry-aligned.root bkg_geometry-aligned.root;
                             ln -nsf ../bkg_geometry-aligned.root o2sim_geometry-aligned.root;
                             ln -nsf ../bkg_MCHeader.root bkg_MCHeader.root;
                             ln -nsf ../bkg_grp.root bkg_grp.root
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
   orbitsPerTF = 256
   startOrbit = (tf-1 + int(args.production_offset)*NTIMEFRAMES)*orbitsPerTF
   globalTFConfigValues = { "HBFUtils.orbitFirstSampled" : args.first_orbit + startOrbit,
                            "HBFUtils.nHBFPerTF" : orbitsPerTF,
                            "HBFUtils.orbitFirst" : args.first_orbit,
                            "HBFUtils.runNumber" : args.run }
   # we set the timesamp here only if specified explicitely (otherwise it will come from
   # the simulation GRP and digitization)
   if (args.timestamp != -1):
      globalTFConfigValues["HBFUtils.startTime"] = args.timestamp

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


   # This task creates the basic setup for all digitizers! all digitization configKeyValues need to be given here
   ContextTask = createTask(name='digicontext_'+str(tf), needs=[SGNtask['name'], LinkGRPFileTask['name']], tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu='1')
   # this is just to have the digitizer ini file
   ContextTask['cmd'] = '${O2_ROOT}/bin/o2-sim-digitizer-workflow --only-context --interactionRate ' + str(INTRATE) \
                        + ' ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption         \
                        + ' ' + putConfigValues()

   if BCPATTERN != '':
      ContextTask['cmd'] += ' --bcPatternFile "' + BCPATTERN + '"'

   # in case of embedding we engineer the context directly and allow the user to provide an embedding pattern
   # The :r flag means to shuffle the background events randomly
   if doembedding:
      ContextTask['cmd'] += ';${O2_ROOT}/bin/o2-steer-colcontexttool -i bkg,' + str(INTRATE) + ',' + str(args.ns) + ':' + str(args.nb) + ' ' + signalprefix + ',' + args.embeddPattern + ' --show-context ' + ' --timeframeID ' + str(tf-1 + int(args.production_offset)*NTIMEFRAMES) + ' --orbitsPerTF ' + str(orbitsPerTF)

      if BCPATTERN != '':
         ContextTask['cmd'] += ' --bcPatternFile "' + BCPATTERN + '"'

   workflow['stages'].append(ContextTask)

   tpcdigineeds=[ContextTask['name'], LinkGRPFileTask['name']]
   if usebkgcache:
      tpcdigineeds += [ BKG_HITDOWNLOADER_TASKS['TPC']['name'] ]

   TPCDigitask=createTask(name='tpcdigi_'+str(tf), needs=tpcdigineeds,
                          tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu=NWORKERS, mem='9000')
   TPCDigitask['cmd'] = ('','ln -nfs ../bkg_HitsTPC.root . ;')[doembedding]
   TPCDigitask['cmd'] += '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet TPC --interactionRate ' + str(INTRATE) + '  --tpc-lanes ' + str(NWORKERS) + ' --incontext ' + str(CONTEXTFILE) + ' --tpc-chunked-writer --disable-write-ini ' + putConfigValuesNew(["TPCGasParam"])
   workflow['stages'].append(TPCDigitask)

   trddigineeds = [ContextTask['name']]
   if usebkgcache:
      trddigineeds += [ BKG_HITDOWNLOADER_TASKS['TRD']['name'] ]
   TRDDigitask=createTask(name='trddigi_'+str(tf), needs=trddigineeds,
                          tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu=NWORKERS, mem='8000')
   TRDDigitask['cmd'] = ('','ln -nfs ../bkg_HitsTRD.root . ;')[doembedding]
   TRDDigitask['cmd'] += '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet TRD --interactionRate ' + str(INTRATE) + putConfigValuesNew(localCF={"TRDSimParams.digithreads" : NWORKERS}) + ' --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini'
   if isActive("TRD"):
      workflow['stages'].append(TRDDigitask)

   # these are digitizers which are single threaded
   def createRestDigiTask(name, det='ALLSMALLER'):
      tneeds = needs=[ContextTask['name']]
      commondigicmd = '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --interactionRate ' + str(INTRATE) + '  --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini' + putConfigValuesNew(["MFTAlpideParam, ITSAlpideParam, ITSDigitizerParam"])

      if det=='ALLSMALLER': # here we combine all smaller digits in one DPL workflow
         if usebkgcache:
            for d in itertools.chain(smallsensorlist, ctp_trigger_inputlist):
               tneeds += [ BKG_HITDOWNLOADER_TASKS[d]['name'] ]
         t = createTask(name=name, needs=tneeds,
                        tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
         t['cmd'] = ('','ln -nfs ../bkg_Hits*.root . ;')[doembedding]
         # t['cmd'] += commondigicmd + ' --skipDet TPC,TRD,FT0,FV0,CTP '
         t['cmd'] += commondigicmd + ' --onlyDet TOF,CPV,EMC,HMP,PHS,ITS,MFT,MID,MCH,FDD'
         t['cmd'] += ' --ccdb-tof-sa '
         t['cmd'] += ('',' --combine-devices ')[args.combine_dpl_devices]
         workflow['stages'].append(t)
         return t

      else: # here we create individual digitizers
         if isActive(det):
            if usebkgcache:
              tneeds += [ BKG_HITDOWNLOADER_TASKS[det]['name'] ]
            t = createTask(name=name, needs=tneeds,
                     tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
            t['cmd'] = ('','ln -nfs ../bkg_Hits' + str(det) + '.root . ;')[doembedding]
            t['cmd'] += commondigicmd + ' --onlyDet ' + str(det)
            if det == 'TOF':
               t['cmd'] += ' --ccdb-tof-sa'
            workflow['stages'].append(t)
            return t

   det_to_digitask={}

   if args.combine_smaller_digi==True:
      det_to_digitask['ALLSMALLER']=createRestDigiTask("restdigi_"+str(tf))

   for det in smallsensorlist:
      name=str(det).lower() + "digi_" + str(tf)
      t = det_to_digitask['ALLSMALLER'] if args.combine_smaller_digi==True else createRestDigiTask(name, det)
      det_to_digitask[det]=t

   if True or args.combine_smaller_digi==False:
      # detectors serving CTP need to be treated somewhat special since CTP needs
      # these inputs at the same time --> still need to be made better
      tneeds = [ContextTask['name']]
      t = createTask(name="ft0fv0ctp_digi_" + str(tf), needs=tneeds,
                     tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
      t['cmd'] = ('','ln -nfs ../bkg_HitsFT0.root . ; ln -nfs ../bkg_HitsFV0.root . ;')[doembedding]
      t['cmd'] += '${O2_ROOT}/bin/o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet FT0,FV0,CTP  --interactionRate ' + str(INTRATE) + '  --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini' + putConfigValuesNew() + ('',' --combine-devices')[args.combine_dpl_devices]
      workflow['stages'].append(t)
      det_to_digitask["FT0"]=t
      det_to_digitask["FV0"]=t

   def getDigiTaskName(det):
      t = det_to_digitask.get(det)
      if t == None:
         return "undefined"
      return t['name']

   # -----------
   # reco
   # -----------
   tpcreconeeds=[]
   if not args.combine_tpc_clusterization:
     # We treat TPC clusterization in multiple (sector) steps in order to stay within the memory limit
     # We seem to be needing to ask for 2 sectors at least, otherwise there is a problem with the branch naming.
     tpcclustertasks=[]
     sectorpertask=6
     for s in range(0,35,sectorpertask):
       taskname = 'tpcclusterpart' + str((int)(s/sectorpertask)) + '_' + str(tf)
       tpcclustertasks.append(taskname)
       tpcclussect = createTask(name=taskname, needs=[TPCDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='2', mem='8000')
       tpcclussect['cmd'] = '${O2_ROOT}/bin/o2-tpc-chunkeddigit-merger --tpc-sectors ' + str(s)+'-'+str(s+sectorpertask-1) + ' --tpc-lanes ' + str(NWORKERS)
       tpcclussect['cmd'] += ' | ${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True) + ' --input-type digitizer --output-type clusters,send-clusters-per-sector --outfile tpc-native-clusters-part' + str((int)(s/sectorpertask)) + '.root --tpc-sectors ' + str(s)+'-'+str(s+sectorpertask-1) + ' ' + putConfigValuesNew(["GPU_global"], {"GPU_proc.ompThreads" : 4})
       tpcclussect['env'] = { "OMP_NUM_THREADS" : "4", "SHMSIZE" : "5000000000" }
       workflow['stages'].append(tpcclussect)

     TPCCLUSMERGEtask=createTask(name='tpcclustermerge_'+str(tf), needs=tpcclustertasks, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='10000')
     TPCCLUSMERGEtask['cmd']='${O2_ROOT}/bin/o2-commonutils-treemergertool -i tpc-native-clusters-part*.root -o tpc-native-clusters.root -t tpcrec' #--asfriend preferable but does not work
     workflow['stages'].append(TPCCLUSMERGEtask)
     tpcreconeeds.append(TPCCLUSMERGEtask['name'])
   else:
     tpcclus = createTask(name='tpccluster_' + str(tf), needs=[TPCDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=NWORKERS, mem='2000')
     tpcclus['cmd'] = '${O2_ROOT}/bin/o2-tpc-chunkeddigit-merger --tpc-lanes ' + str(NWORKERS)
     tpcclus['cmd'] += ' | ${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options() + ' --input-type digitizer --output-type clusters,send-clusters-per-sector ' + putConfigValuesNew(["GPU_global","TPCGasParam"],{"GPU_proc.ompThreads" : 1})
     workflow['stages'].append(tpcclus)
     tpcreconeeds.append(tpcclus['name'])

   TPCRECOtask=createTask(name='tpcreco_'+str(tf), needs=tpcreconeeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], relative_cpu=3/8, mem='16000')
   TPCRECOtask['cmd'] = '${O2_ROOT}/bin/o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True) + ' --input-type clusters --output-type tracks,send-clusters-per-sector ' + putConfigValuesNew(["GPU_global","TPCGasParam"], {"GPU_proc.ompThreads":NWORKERS})
   workflow['stages'].append(TPCRECOtask)

   ITSRECOtask=createTask(name='itsreco_'+str(tf), needs=[getDigiTaskName("ITS"), MATBUD_DOWNLOADER_TASK['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   ITSRECOtask['cmd'] = '${O2_ROOT}/bin/o2-its-reco-workflow --trackerCA --tracking-mode async ' + getDPL_global_options() \
                        + putConfigValuesNew(["ITSVertexerParam", "ITSAlpideParam",
                                              'ITSClustererParam'], {"NameConf.mDirMatLUT" : ".."})
   workflow['stages'].append(ITSRECOtask)

   FT0RECOtask=createTask(name='ft0reco_'+str(tf), needs=[getDigiTaskName("FT0")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   FT0RECOtask['cmd'] = '${O2_ROOT}/bin/o2-ft0-reco-workflow ' + getDPL_global_options() + putConfigValues()
   workflow['stages'].append(FT0RECOtask)

   ITSTPCMATCHtask=createTask(name='itstpcMatch_'+str(tf), needs=[TPCRECOtask['name'], ITSRECOtask['name'], FT0RECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='8000', relative_cpu=3/8)
   ITSTPCMATCHtask['cmd']= '${O2_ROOT}/bin/o2-tpcits-match-workflow ' + getDPL_global_options(bigshm=True) + ' --tpc-track-reader \"tpctracks.root\" --tpc-native-cluster-reader \"--infile tpc-native-clusters.root\" --use-ft0' + putConfigValuesNew(['MFTClustererParam', 'ITSCATrackerParam', 'tpcitsMatch', 'TPCGasParam', 'ITSClustererParam'], {"NameConf.mDirMatLUT" : ".."})
   workflow['stages'].append(ITSTPCMATCHtask)

   TRDTRACKINGtask = createTask(name='trdreco_'+str(tf), needs=[TRDDigitask['name'], ITSTPCMATCHtask['name'], TPCRECOtask['name'], ITSRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   TRDTRACKINGtask['cmd'] = '${O2_ROOT}/bin/o2-trd-tracklet-transformer ' + getDPL_global_options() + putConfigValues()
   workflow['stages'].append(TRDTRACKINGtask)

   # FIXME This is so far a workaround to avoud a race condition for trdcalibratedtracklets.root
   TRDTRACKINGtask2 = createTask(name='trdreco2_'+str(tf), needs=[TRDTRACKINGtask['name'],MATBUD_DOWNLOADER_TASK['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   TRDTRACKINGtask2['cmd'] = '${O2_ROOT}/bin/o2-trd-global-tracking ' + getDPL_global_options(bigshm=True) \
                              + putConfigValuesNew(['ITSClustererParam',
                                                   'ITSCATrackerParam',
                                                    'TPCGasParam'], {"NameConf.mDirMatLUT" : ".."})                                    \
                             + " --track-sources " + anchorConfig.get("o2-trd-global-tracking-options",{}).get("track-sources","all")
   workflow['stages'].append(TRDTRACKINGtask2)

   TOFRECOtask = createTask(name='tofmatch_'+str(tf), needs=[ITSTPCMATCHtask['name'], getDigiTaskName("TOF")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   TOFRECOtask['cmd'] = '${O2_ROOT}/bin/o2-tof-reco-workflow --use-ccdb ' + getDPL_global_options() + putConfigValuesNew()
   workflow['stages'].append(TOFRECOtask)

   toftpcmatchneeds = [TOFRECOtask['name'], TPCRECOtask['name']]
   toftracksrcdefault = "TPC,ITS-TPC"
   if isActive('TRD'):
      toftpcmatchneeds.append(TRDTRACKINGtask2['name'])
      toftracksrcdefault+=",TPC-TRD,ITS-TPC-TRD"
   TOFTPCMATCHERtask = createTask(name='toftpcmatch_'+str(tf), needs=toftpcmatchneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   TOFTPCMATCHERtask['cmd'] = '${O2_ROOT}/bin/o2-tof-matcher-workflow ' + getDPL_global_options() \
                              + putConfigValuesNew(["ITSClustererParam",
                                                    'TPCGasParam',
                                                    'ITSCATrackerParam',
                                                    'MFTClustererParam'])                         \
                              + " --track-sources " + anchorConfig.get("o2-tof-matcher-workflow-options",{}).get("track-sources",toftracksrcdefault) + ('',' --combine-devices')[args.combine_dpl_devices]
   workflow['stages'].append(TOFTPCMATCHERtask)

   MFTRECOtask = createTask(name='mftreco_'+str(tf), needs=[getDigiTaskName("MFT")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MFTRECOtask['cmd'] = '${O2_ROOT}/bin/o2-mft-reco-workflow ' + getDPL_global_options() + putConfigValuesNew(['MFTTracking', 'MFTAlpideParam', 'ITSClustererParam','MFTClustererParam'])
   if args.mft_assessment_full == True:
      MFTRECOtask['cmd']+= ' --run-assessment '
   workflow['stages'].append(MFTRECOtask)

   # MCH reco: needing access to kinematics ... so some extra logic needed here
   mchreconeeds = [getDigiTaskName("MCH")]
   if usebkgcache:
      mchreconeeds += [ BKG_KINEDOWNLOADER_TASK['name'] ]

   MCHRECOtask = createTask(name='mchreco_'+str(tf), needs=[getDigiTaskName("MCH")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MCHRECOtask['cmd'] = ('','ln -nfs ../bkg_Kine.root . ;')[doembedding]
   MCHRECOtask['cmd'] += '${O2_ROOT}/bin/o2-mch-reco-workflow ' + getDPL_global_options() + putConfigValues()
   workflow['stages'].append(MCHRECOtask)

   MIDRECOtask = createTask(name='midreco_'+str(tf), needs=[getDigiTaskName("MID")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MIDRECOtask['cmd'] = '${O2_ROOT}/bin/o2-mid-digits-reader-workflow | ${O2_ROOT}/bin/o2-mid-reco-workflow ' + getDPL_global_options() + putConfigValues()
   workflow['stages'].append(MIDRECOtask)

   FDDRECOtask = createTask(name='fddreco_'+str(tf), needs=[getDigiTaskName("FDD")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   FDDRECOtask['cmd'] = '${O2_ROOT}/bin/o2-fdd-reco-workflow ' + getDPL_global_options() + putConfigValues()
   workflow['stages'].append(FDDRECOtask)

   FV0RECOtask = createTask(name='fv0reco_'+str(tf), needs=[getDigiTaskName("FV0")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   FV0RECOtask['cmd'] = '${O2_ROOT}/bin/o2-fv0-reco-workflow ' + getDPL_global_options() + putConfigValues()
   workflow['stages'].append(FV0RECOtask)

   # calorimeters
   EMCRECOtask = createTask(name='emcalreco_'+str(tf), needs=[getDigiTaskName("EMC")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   EMCRECOtask['cmd'] = '${O2_ROOT}/bin/o2-emcal-reco-workflow --input-type digits --output-type cells --infile emcaldigits.root ' + getDPL_global_options() + putConfigValues()
   workflow['stages'].append(EMCRECOtask)

   PHSRECOtask = createTask(name='phsreco_'+str(tf), needs=[getDigiTaskName("PHS")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   PHSRECOtask['cmd'] = '${O2_ROOT}/bin/o2-phos-reco-workflow ' + getDPL_global_options() + putConfigValues()
   workflow['stages'].append(PHSRECOtask)

   CPVRECOtask = createTask(name='cpvreco_'+str(tf), needs=[getDigiTaskName("CPV")], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   CPVRECOtask['cmd'] = '${O2_ROOT}/bin/o2-cpv-reco-workflow ' + getDPL_global_options() + putConfigValues()
   workflow['stages'].append(CPVRECOtask)

   if args.with_ZDC:
      ZDCRECOtask = createTask(name='zdcreco_'+str(tf), needs=[getDigiTaskName("ZDC")], tf=tf, cwd=timeframeworkdir, lab=["ZDC"])
      ZDCRECOtask['cmd'] = '${O2_ROOT}/bin/o2-zdc-digits-reco ' + getDPL_global_options() + putConfigValues()
      workflow['stages'].append(ZDCRECOtask)

   ## forward matching
   MCHMIDMATCHtask = createTask(name='mchmidMatch_'+str(tf), needs=[MCHRECOtask['name'], MIDRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MCHMIDMATCHtask['cmd'] = '${O2_ROOT}/bin/o2-muon-tracks-matcher-workflow ' + getDPL_global_options()
   workflow['stages'].append(MCHMIDMATCHtask)

   MFTMCHMATCHtask = createTask(name='mftmchMatch_'+str(tf), needs=[MCHMIDMATCHtask['name'], MFTRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MFTMCHMATCHtask['cmd'] = '${O2_ROOT}/bin/o2-globalfwd-matcher-workflow ' + putConfigValuesNew(['ITSAlpideConfig','MFTAlpideConfig'],{"FwdMatching.useMIDMatch":"true"})
   if args.fwdmatching_assessment_full == True:
      MFTMCHMATCHtask['cmd']+= ' |  o2-globalfwd-assessment-workflow '
   MFTMCHMATCHtask['cmd']+= getDPL_global_options()
   workflow['stages'].append(MFTMCHMATCHtask)

   if args.fwdmatching_save_trainingdata == True:
      MFTMCHMATCHTraintask = createTask(name='mftmchMatchTrain_'+str(tf), needs=[MCHMIDMATCHtask['name'], MFTRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
      MFTMCHMATCHTraintask['cmd'] = '${O2_ROOT}/bin/o2-globalfwd-matcher-workflow ' + putConfigValuesNew(['ITSAlpideConfig','MFTAlpideConfig'],{"FwdMatching.useMIDMatch":"true"})
      MFTMCHMATCHTraintask['cmd']+= getDPL_global_options()
      workflow['stages'].append(MFTMCHMATCHTraintask)

   pvfinderneeds = [ITSTPCMATCHtask['name']]
   if isActive('FT0'):
      pvfinderneeds += [FT0RECOtask['name']]
   if isActive('TOF'):
      pvfinderneeds += [TOFTPCMATCHERtask['name']]
   if isActive('MFT'):
      pvfinderneeds += [MFTRECOtask['name']]
   if isActive('MCH'):
      pvfinderneeds += [MCHRECOtask['name']]
   if isActive('TRD'):
      pvfinderneeds += [TRDTRACKINGtask2['name']]
   if isActive('FDD'):
      pvfinderneeds += [FDDRECOtask['name']]
   if isActive('MFT') and isActive('MCH'):
      pvfinderneeds += [MFTMCHMATCHtask['name']]

   # Take None as default, we only add more if nothing from anchorConfig
   pvfinder_sources = anchorConfig.get("o2-primary-vertexing-workflow-options",{}).get("vertexing-sources", None)
   pvfinder_matching_sources = anchorConfig.get("o2-primary-vertexing-workflow-options",{}).get("vertex-track-matching-sources", None)
   if not pvfinder_sources:
      pvfinder_sources = "ITS,ITS-TPC,ITS-TPC-TRD,ITS-TPC-TOF"
      if isActive("MID"):
         pvfinder_sources += ",MID"
         pvfinderneeds += [MIDRECOtask['name']]
   if not pvfinder_matching_sources:
      pvfinder_matching_sources = "ITS,MFT,TPC,ITS-TPC,MCH,MFT-MCH,TPC-TOF,TPC-TRD,ITS-TPC-TRD,ITS-TPC-TOF"
      if isActive("MID"):
         pvfinder_matching_sources += ",MID"
         pvfinderneeds += [MIDRECOtask['name']]

   PVFINDERtask = createTask(name='pvfinder_'+str(tf), needs=pvfinderneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=NWORKERS, mem='4000')
   PVFINDERtask['cmd'] = '${O2_ROOT}/bin/o2-primary-vertexing-workflow ' \
                         + getDPL_global_options() + putConfigValuesNew(['ITSAlpideParam','MFTAlpideParam', 'pvertexer', 'TPCGasParam'], {"NameConf.mDirMatLUT" : ".."})
   PVFINDERtask['cmd'] += ' --vertexing-sources ' + pvfinder_sources + ' --vertex-track-matching-sources ' + pvfinder_matching_sources + ('',' --combine-source-devices')[args.combine_dpl_devices]
   workflow['stages'].append(PVFINDERtask)

   if includeFullQC or includeLocalQC:

     def addQCPerTF(taskName, needs, readerCommand, configFilePath, objectsFile=''):
       task = createTask(name=taskName + '_local' + str(tf), needs=needs, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=1, mem='2000')
       objectsFile = objectsFile if len(objectsFile) > 0 else taskName + '.root'
       # the --local-batch argument will make QC Tasks store their results in a file and merge with any existing objects
       task['cmd'] = f'{readerCommand} | o2-qc --config {configFilePath}' + \
                     f' --local-batch ../{qcdir}/{objectsFile}' + \
                     f' --override-values "qc.config.Activity.number={args.run};qc.config.Activity.periodName={args.productionTag}"' + \
                     ' ' + getDPL_global_options()
       # Prevents this task from being run for multiple TimeFrames at the same time, thus trying to modify the same file.
       task['semaphore'] = objectsFile
       workflow['stages'].append(task)

     ### MFT

     # to be enabled once MFT Digits should run 5 times with different configurations
     for flp in range(5):
       addQCPerTF(taskName='mftDigitsQC' + str(flp),
                  needs=[getDigiTaskName("MFT")],
                  readerCommand='o2-qc-mft-digits-root-file-reader --mft-digit-infile=mftdigits.root',
                  configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/qc-mft-digit-' + str(flp) + '.json',
                  objectsFile='mftDigitsQC.root')
     addQCPerTF(taskName='mftClustersQC',
                needs=[MFTRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types none --cluster-types MFT',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/qc-mft-cluster.json')
     addQCPerTF(taskName='mftAsyncQC',
                needs=[MFTRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types MFT --cluster-types MFT',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/qc-mft-async.json')

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
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/trd-digits-task.json')

     ### TOF
     addQCPerTF(taskName='tofDigitsQC',
                needs=[getDigiTaskName("TOF")],
                readerCommand='${O2_ROOT}/bin/o2-tof-reco-workflow --input-type digits --output-type none',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/tofdigits.json',
                objectsFile='tofDigitsQC.root')

     addQCPerTF(taskName='tofft0PIDQC',
                needs=[ITSTPCMATCHtask['name'], TOFRECOtask['name'], FT0RECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC,TPC,ITS-TPC-TOF,TPC-TOF" --cluster-types FT0',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/pidft0tof.json')
     addQCPerTF(taskName='tofPIDQC',
                needs=[ITSTPCMATCHtask['name'], TOFRECOtask['name']],
                readerCommand='o2-global-track-cluster-reader --track-types "ITS-TPC,TPC,ITS-TPC-TOF,TPC-TOF" --cluster-types none',
                configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/pidtof.json')

     ### EMCAL
     if isActive('EMC'):
        addQCPerTF(taskName='emcDigitsQC',
                   needs=[EMCRECOtask['name']],
                   readerCommand='o2-emcal-cell-reader-workflow --infile emccells.root',
                   configFilePath='json://${O2DPG_ROOT}/MC/config/QC/json/emc-digits-task.json')
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
                readerCommand='o2-global-track-cluster-reader --track-types "TPC,ITS-TPC"',
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

   #secondary vertexer
   svfinder_threads = ' --threads 1 '
   svfinder_cpu = 1
   if COLTYPE == "PbPb" or (doembedding and COLTYPEBKG == "PbPb"):
     svfinder_threads = ' --threads 3 '
     svfinder_cpu = 3
   SVFINDERtask = createTask(name='svfinder_'+str(tf), needs=[PVFINDERtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=svfinder_cpu, mem='5000')
   SVFINDERtask['cmd'] = '${O2_ROOT}/bin/o2-secondary-vertexing-workflow '
   SVFINDERtask['cmd'] += getDPL_global_options(bigshm=True) + svfinder_threads + putConfigValuesNew(['svertexer'], {"NameConf.mDirMatLUT" : ".."})
   # Take None as default, we only add more if nothing from anchorConfig
   svfinder_sources = anchorConfig.get("o2-secondary-vertexing-workflow-options",{}).get("vertexing-sources", None)
   if not svfinder_sources:
       svfinder_sources = "ITS,ITS-TPC,TPC-TRD,TPC-TOF,ITS-TPC-TRD,ITS-TPC-TOF"
       if isActive("MID"):
           svfinder_sources += ",MID"
   SVFINDERtask['cmd'] += ' --vertexing-sources ' + svfinder_sources + ('',' --combine-source-devices')[args.combine_dpl_devices]
   workflow['stages'].append(SVFINDERtask)

  # -----------
  # produce AOD
  # -----------
   # TODO This needs further refinement, sources and dependencies should be constructed dynamically
   aodinfosources = 'ITS,MFT,MCH,TPC,ITS-TPC,MFT-MCH,ITS-TPC-TOF,TPC-TOF,FT0,FDD,CTP,TPC-TRD,ITS-TPC-TRD,EMC'
   aodneeds = [PVFINDERtask['name'], SVFINDERtask['name']]
   if isActive('FV0'):
     aodneeds += [ FV0RECOtask['name'] ]
     aodinfosources += ',FV0'
   if isActive('TOF'):
     aodneeds += [ TOFRECOtask['name'] ]
   if isActive('TRD'):
     aodneeds += [ TRDTRACKINGtask2['name'] ]
   if isActive('EMC'):
     aodneeds += [ EMCRECOtask['name'] ]
   if isActive('CPV'):
     aodneeds += [ CPVRECOtask['name'] ]
   if isActive('PHS'):
     aodneeds += [ PHSRECOtask['name'] ]
   if isActive('MID'):
      aodneeds += [ MIDRECOtask['name'] ]
      aodinfosources += ',MID'
   if args.with_ZDC and isActive('ZDC'):
     aodneeds += [ ZDCRECOtask['name'] ]
     aodinfosources += ',ZDC'
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
   AODtask['cmd'] += ' --info-sources ' + anchorConfig.get("o2-aod-producer-workflow-options",{}).get("info-sources",str(aodinfosources))
   AODtask['cmd'] += ' --lpmp-prod-tag ${ALIEN_JDL_LPMPRODUCTIONTAG:-unknown}'
   AODtask['cmd'] += ' --anchor-pass ${ALIEN_JDL_LPMANCHORPASSNAME:-unknown}'
   AODtask['cmd'] += ' --anchor-prod ${ALIEN_JDL_MCANCHOR:-unknown}'
   AODtask['cmd'] += ('',' --combine-source-devices ')[args.combine_dpl_devices]
   if environ.get('O2DPG_AOD_NOTRUNCATE') != None or environ.get('ALIEN_JDL_O2DPG_AOD_NOTRUNCATE') != None:
      AODtask['cmd'] += ' --enable-truncation 0'  # developer option to suppress precision truncation

   workflow['stages'].append(AODtask)

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
     TFcleanup = createTask(name='tfcleanup_'+str(tf), needs= [ AOD_merge_task['name'] ], tf=tf, cwd=timeframeworkdir, lab=["CLEANUP"], mem='0', cpu='1')
     TFcleanup['cmd'] = 'rm *digi*.root;'
     TFcleanup['cmd'] += 'rm *cluster*.root'
     workflow['stages'].append(TFcleanup);

# AOD merging as one global final step
aodmergerneeds = ['aod_' + str(tf) for tf in range(1, NTIMEFRAMES + 1)]
AOD_merge_task = createTask(name='aodmerge', needs = aodmergerneeds, lab=["AOD"], mem='2000', cpu='1')
AOD_merge_task['cmd'] = ' [ -f aodmerge_input.txt ] && rm aodmerge_input.txt; '
AOD_merge_task['cmd'] += ' for i in `seq 1 ' + str(NTIMEFRAMES) + '`; do echo "tf${i}/AO2D.root" >> aodmerge_input.txt; done; '
AOD_merge_task['cmd'] += ' o2-aod-merger --input aodmerge_input.txt --output AO2D.root'
workflow['stages'].append(AOD_merge_task)

job_merging = False
if includeFullQC:
  workflow['stages'].extend(include_all_QC_finalization(ntimeframes=NTIMEFRAMES, standalone=False, run=args.run, productionTag=args.productionTag))


if includeAnalysis:
   # include analyses and potentially final QC upload tasks
    add_analysis_tasks(workflow["stages"], needs=[AOD_merge_task["name"]], is_mc=True)
    if QUALITYCONTROL_ROOT:
        add_analysis_qc_upload_tasks(workflow["stages"], args.productionTag, args.run, "passMC")

dump_workflow(workflow["stages"], args.o)

exit (0)
