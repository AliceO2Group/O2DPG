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
import argparse
from os import environ
from os.path import join, dirname
import json
import array as arr

sys.path.append(join(dirname(__file__), '.', 'o2dpg_workflow_utils'))

from o2dpg_workflow_utils import createTask, dump_workflow

parser = argparse.ArgumentParser(description='Create an ALICE (Run3) MC simulation workflow')

parser.add_argument('-ns',help='number of signal events / timeframe', default=20)
parser.add_argument('-gen',help='generator: pythia8, extgen', default='')
parser.add_argument('-proc',help='process type: inel, dirgamma, jets, ccbar, ...', default='')
parser.add_argument('-trigger',help='event selection: particle, external', default='')
parser.add_argument('-ini',help='generator init parameters file (full paths required), for example: ${O2DPG_ROOT}/MC/config/PWGHF/ini/GeneratorHF.ini', default='')
parser.add_argument('-confKey',help='generator or trigger configuration key values, for example: "GeneratorPythia8.config=pythia8.cfg;A.x=y"', default='')

parser.add_argument('-interactionRate',help='Interaction rate, used in digitization', default=-1)
parser.add_argument('-eCM',help='CMS energy', default=-1)
parser.add_argument('-eA',help='Beam A energy', default=-1) #6369 PbPb, 2.510 pp 5 TeV, 4 pPb
parser.add_argument('-eB',help='Beam B energy', default=-1)
parser.add_argument('-col',help='collision system: pp, PbPb, pPb, Pbp, ..., in case of embedding collision system of signal', default='pp')
parser.add_argument('-field',help='L3 field rounded to kGauss, allowed: values +-2,+-5 and 0; +-5U for uniform field', default='-5')

parser.add_argument('-ptHatBin',help='pT hard bin number', default=-1)
parser.add_argument('-ptHatMin',help='pT hard minimum when no bin requested', default=0)
parser.add_argument('-ptHatMax',help='pT hard maximum when no bin requested', default=-1)
parser.add_argument('-weightPow',help='Flatten pT hard spectrum with power', default=-1)

parser.add_argument('--embedding',action='store_true', help='With embedding into background')
parser.add_argument('-nb',help='number of background events / timeframe', default=20)
parser.add_argument('-genBkg',help='embedding background generator', default='') #pythia8, not recomended: pythia8hi, pythia8pp
parser.add_argument('-procBkg',help='process type: inel, ..., do not set it for Pythia8 PbPb', default='heavy_ion')
parser.add_argument('-iniBkg',help='embedding background generator init parameters file (full path required)', default='${O2DPG_ROOT}/MC/config/common/ini/basic.ini')
parser.add_argument('-confKeyBkg',help='embedding background configuration key values, for example: "GeneratorPythia8.config=pythia8bkg.cfg"', default='')
parser.add_argument('-colBkg',help='embedding background collision system', default='PbPb')

parser.add_argument('-e',help='simengine', default='TGeant4')
parser.add_argument('-tf',help='number of timeframes', default=2)
parser.add_argument('-j',help='number of workers (if applicable)', default=8, type=int)
parser.add_argument('-mod',help='Active modules', default='--skipModules ZDC')
parser.add_argument('-seed',help='random seed number', default=0)
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
parser.add_argument('--combine-tpc-clusterization', action='store_true', help=argparse.SUPPRESS) #<--- useful for small productions (pp, low interaction rate, small number of events)

# QC related arguments
parser.add_argument('--include-qc', action='store_true', help='a flag to include QC in the workflow')

args = parser.parse_args()
print (args)

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')
O2_ROOT=environ.get('O2_ROOT')

if O2DPG_ROOT == None: 
   print('Error: This needs O2DPG loaded')
#   exit(1)

if O2_ROOT == None: 
   print('Error: This needs O2 loaded')
#   exit(1)

# ----------- START WORKFLOW CONSTRUCTION ----------------------------- 

NTIMEFRAMES=int(args.tf)
NWORKERS=args.j
MODULES=args.mod #"--skipModules ZDC"
SIMENGINE=args.e
BFIELD=args.field
RNDSEED=args.seed    # 0 means random seed ! Should we set different seed for Bkg and signal?

# add here other possible types

workflow={}
workflow['stages'] = []


def getDPL_global_options(bigshm=False):
   common="-b --run --fairmq-ipc-prefix ${FAIRMQ_IPC_PREFIX:-./} --driver-client-backend ws:// "
   if args.noIPC!=None:
      return common + " --no-IPC "
   if bigshm:
      return common + " --shm-segment-size ${SHMSIZE:-50000000000} "
   else:
      return common

doembedding=True if args.embedding=='True' or args.embedding==True else False
usebkgcache=args.use_bkg_from!=None
includeQC=True if args.include_qc=='True' or args.include_qc==True else False

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
           if GENBKG == 'pythia8':
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
           CONFKEYBKG=' --configKeyValues "' + args.CONFKEYBKG + '"'

        # Background PYTHIA configuration
        BKG_CONFIG_task=createTask(name='genbkgconf')
        BKG_CONFIG_task['cmd'] = 'echo "placeholder / dummy task"'
        if  GENBKG == 'pythia8':
            BKG_CONFIG_task['cmd'] = '${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
                                   --output=pythia8bkg.cfg                                     \
                                   --seed='+str(RNDSEED)+'                                     \
                                   --idA='+str(PDGABKG)+'                                      \
                                   --idB='+str(PDGBBKG)+'                                      \
                                   --eCM='+str(ECMSBKG)+'                                      \
                                   --eA='+str(EBEAMABKG)+'                                     \
                                   --eB='+str(EBEAMBBKG)+'                                     \
                                   --process='+str(PROCESSBKG)
            # if we configure pythia8 here --> we also need to adjust the configuration
            # TODO: we need a proper config container/manager so as to combine these local configs with external configs etc.
            CONFKEYBKG='--configKeyValues "GeneratorPythia8.config=pythia8bkg.cfg"'

        workflow['stages'].append(BKG_CONFIG_task)

        # background task configuration
        INIBKG=''
        if args.iniBkg!= '':
           INIBKG=' --configFile ' + args.iniBkg

        BKGtask=createTask(name='bkgsim', lab=["GEANT"], needs=[BKG_CONFIG_task['name']], cpu=NWORKERS )
        BKGtask['cmd']='o2-sim -e ' + SIMENGINE   + ' -j ' + str(NWORKERS) + ' -n '     + str(NBKGEVENTS) \
                     + ' -g  '      + str(GENBKG) + ' '    + str(MODULES)  + ' -o bkg ' + str(INIBKG)     \
                     + ' --field '  + str(BFIELD) + ' '    + str(CONFKEYBKG)
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
smallsensorlist = [ "ITS", "TOF", "FT0", "FV0", "FDD", "MCH", "MID", "MFT", "HMP", "EMC", "PHS", "CPV" ]

BKG_HITDOWNLOADER_TASKS={}
for det in [ 'TPC', 'TRD' ] + smallsensorlist:
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

# loop over timeframes
for tf in range(1, NTIMEFRAMES + 1):
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

   # Recover PTHATMIN and PTHATMAX from pre-defined array depending bin number PTHATBIN
   # I think these arrays can be removed and rely on scripts where the arrays are hardcoded
   # it depends how this will be handled on grid execution
   # like in run/PWGGAJE/run_decaygammajets.sh run/PWGGAJE/run_jets.sh, run/PWGGAJE/run_dirgamma.sh
   # Also, if flat pT hard weigthing become standard this will become obsolete. Let's keep it for the moment.
   PTHATBIN=int(args.ptHatBin)

   # I would move next lines to a external script, not sure how to do it (GCB)
   if PTHATBIN > -1:
           # gamma-jet 
      if   PROCESS == 'dirgamma': 
           low_edge = arr.array('l', [5,  11, 21, 36, 57, 84])
           hig_edge = arr.array('l', [11, 21, 36, 57, 84, -1])
           PTHATMIN=low_edge[PTHATBIN]
           PTHATMAX=hig_edge[PTHATBIN]
           # jet-jet
      elif PROCESS == 'jets': 
          # Biased jet-jet
          # Define the pt hat bin arrays and set bin depending threshold
           if   "TrigPt3_5" in INIFILE:
                low_edge = arr.array('l', [5, 7,  9, 12, 16, 21])
                hig_edge = arr.array('l', [7, 9, 12, 16, 21, -1])
                PTHATMIN=low_edge[PTHATBIN]
                PTHATMAX=hig_edge[PTHATBIN]
           elif  "TrigPt7" in INIFILE:
                low_edge = arr.array('l', [ 8, 10, 14, 19, 26, 35, 48, 66])
                hig_edge = arr.array('l', [10, 14, 19, 26, 35, 48, 66, -1])
                PTHATMIN=low_edge[PTHATBIN]
                PTHATMAX=hig_edge[PTHATBIN]
           #unbiased
           else:
                low_edge = arr.array('l', [ 0, 5, 7,  9, 12, 16, 21, 28, 36, 45, 57, 70, 85,  99, 115, 132, 150, 169, 190, 212, 235])
                hig_edge = arr.array('l', [ 5, 7, 9, 12, 16, 21, 28, 36, 45, 57, 70, 85, 99, 115, 132, 150, 169, 190, 212, 235,  -1])
                PTHATMIN=low_edge[PTHATBIN]
                PTHATMAX=hig_edge[PTHATBIN]
      else:
           low_edge = arr.array('l', [ 0, 5, 7,  9, 12, 16, 21, 28, 36, 45, 57, 70, 85,  99, 115, 132, 150, 169, 190, 212, 235])
           hig_edge = arr.array('l', [ 5, 7, 9, 12, 16, 21, 28, 36, 45, 57, 70, 85, 99, 115, 132, 150, 169, 190, 212, 235,  -1])
           PTHATMIN=low_edge[PTHATBIN]
           PTHATMAX=hig_edge[PTHATBIN]
           
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
                                --seed='+str(RNDSEED)+'                                  \
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
      CONFKEY='--configKeyValues "GeneratorPythia8.config=pythia8.cfg"'

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
   embeddinto= "--embedIntoFile ../bkg_MCHeader.root" if doembedding else ""
   if doembedding:
       if not usebkgcache:
            signalneeds = signalneeds + [ BKGtask['name'] ]
       else:
            signalneeds = signalneeds + [ BKG_HEADER_task['name'] ]
   SGNtask=createTask(name='sgnsim_'+str(tf), needs=signalneeds, tf=tf, cwd='tf'+str(tf), lab=["GEANT"], relative_cpu=5/8, mem='2000')
   SGNtask['cmd']='o2-sim -e '  + str(SIMENGINE) + ' '    + str(MODULES)  + ' -n ' + str(NSIGEVENTS)  \
                  + ' --field ' + str(BFIELD)    + ' -j ' + str(NWORKERS) + ' -g ' + str(GENERATOR)   \
                  + ' '         + str(TRIGGER)   + ' '    + str(CONFKEY)  + ' '    + str(INIFILE)     \
                  + ' -o '      + signalprefix   + ' '    + embeddinto
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
                             ln -nsf ../bkg_MCHeader.root bkg_MCHeader.root;
                             ln -nsf ../bkg_grp.root bkg_grp.root
                             '''
   else:
      LinkGRPFileTask=createTask(name='linkGRP_'+str(tf), needs=[SGNtask['name']], tf=tf, cwd=timeframeworkdir, cpu='0', mem='0')
      LinkGRPFileTask['cmd']='ln -nsf ' + signalprefix + '_grp.root o2sim_grp.root ; ln -nsf ' + signalprefix + '_geometry.root o2sim_geometry.root'
   workflow['stages'].append(LinkGRPFileTask)

   # ------------------
   # digitization steps
   # ------------------
   CONTEXTFILE='collisioncontext.root'
 
   # Determine interation rate
   # it should be taken from CDB, meanwhile some default values
   INTRATE=int(args.interactionRate)

   # in case of embedding take intended bkg collision type not the signal
   COLTYPEIR=COLTYPE
   if doembedding:
      COLTYPEIR=args.colBkg

   if INTRATE < 0:
      if   COLTYPEIR=="PbPb":
         INTRATE=50000 #Hz
      elif COLTYPEIR=="pp":
         INTRATE=400000 #Hz
      else: #pPb?
         INTRATE=200000 #Hz ???

   simsoption=' --sims ' + ('bkg,'+signalprefix if doembedding else signalprefix)

   # This task creates the basic setup for all digitizers! all digitization configKeyValues need to be given here
   ContextTask=createTask(name='digicontext_'+str(tf), needs=[SGNtask['name'], LinkGRPFileTask['name']], tf=tf,
                          cwd=timeframeworkdir, lab=["DIGI"], cpu='1')
   ContextTask['cmd'] = 'o2-sim-digitizer-workflow --only-context --interactionRate ' + str(INTRATE) + ' ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption
   workflow['stages'].append(ContextTask)

   tpcdigineeds=[ContextTask['name'], LinkGRPFileTask['name']]
   if usebkgcache:
      tpcdigineeds += [ BKG_HITDOWNLOADER_TASKS['TPC']['name'] ]

   TPCDigitask=createTask(name='tpcdigi_'+str(tf), needs=tpcdigineeds,
                          tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu=NWORKERS, mem='9000')
   TPCDigitask['cmd'] = ('','ln -nfs ../bkg_HitsTPC.root . ;')[doembedding]
   TPCDigitask['cmd'] += 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet TPC --interactionRate ' + str(INTRATE) + '  --tpc-lanes ' + str(NWORKERS) + ' --incontext ' + str(CONTEXTFILE) + ' --tpc-chunked-writer --disable-write-ini'
   workflow['stages'].append(TPCDigitask)

   trddigineeds = [ContextTask['name']]
   if usebkgcache:
      trddigineeds += [ BKG_HITDOWNLOADER_TASKS['TRD']['name'] ]
   TRDDigitask=createTask(name='trddigi_'+str(tf), needs=trddigineeds,
                          tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu=NWORKERS, mem='8000')
   TRDDigitask['cmd'] = ('','ln -nfs ../bkg_HitsTRD.root . ;')[doembedding]
   TRDDigitask['cmd'] += 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet TRD --interactionRate ' + str(INTRATE) + '  --configKeyValues \"TRDSimParams.digithreads=' + str(NWORKERS) + '\" --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini'
   workflow['stages'].append(TRDDigitask)

   # these are digitizers which are single threaded
   def createRestDigiTask(name, det='ALLSMALLER'):
      tneeds = needs=[ContextTask['name']]
      if det=='ALLSMALLER':
         if usebkgcache:
            for d in smallsensorlist:
               tneeds += [ BKG_HITDOWNLOADER_TASKS[d]['name'] ]
         t = createTask(name=name, needs=tneeds,
                     tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu=NWORKERS)
         t['cmd'] = ('','ln -nfs ../bkg_Hits*.root . ;')[doembedding]
         t['cmd'] += 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --skipDet TPC,TRD --interactionRate ' + str(INTRATE) + '  --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini'
         workflow['stages'].append(t)
         return t

      else:
         if usebkgcache:
            tneeds += [ BKG_HITDOWNLOADER_TASKS[det]['name'] ]
         t = createTask(name=name, needs=tneeds,
                     tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
         t['cmd'] = ('','ln -nfs ../bkg_Hits' + str(det) + '.root . ;')[doembedding]
         t['cmd'] += 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet ' + str(det) + ' --interactionRate ' + str(INTRATE) + '  --incontext ' + str(CONTEXTFILE) + ' --disable-write-ini'
         workflow['stages'].append(t)
         return t

   det_to_digitask={}

   if args.combine_smaller_digi==True:
      det_to_digitask['ALLSMALLER']=createRestDigiTask("restdigi_"+str(tf))

   for det in smallsensorlist:
      name=str(det).lower() + "digi_" + str(tf)
      t = det_to_digitask['ALLSMALLER'] if args.combine_smaller_digi==True else createRestDigiTask(name, det)
      det_to_digitask[det]=t

   # -----------
   # reco
   # -----------
   tpcreconeeds=[]
   if not args.combine_tpc_clusterization:
     # TODO: check value for MaxTimeBin; A large value had to be set tmp in order to avoid crashes based on "exceeding timeframe limit"
     # We treat TPC clusterization in multiple (sector) steps in order to stay within the memory limit
     # We seem to be needing to ask for 2 sectors at least, otherwise there is a problem with the branch naming.
     tpcclustertasks=[]
     sectorpertask=6
     for s in range(0,35,sectorpertask):
       taskname = 'tpcclusterpart' + str((int)(s/sectorpertask)) + '_' + str(tf)
       tpcclustertasks.append(taskname)
       tpcclussect = createTask(name=taskname, needs=[TPCDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='2', mem='8000')
       tpcclussect['cmd'] = 'o2-tpc-chunkeddigit-merger --tpc-sectors ' + str(s)+'-'+str(s+sectorpertask-1) + ' --tpc-lanes ' + str(NWORKERS)
       tpcclussect['cmd'] += ' | o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True) + ' --input-type digitizer --output-type clusters,send-clusters-per-sector --outfile tpc-native-clusters-part' + str((int)(s/sectorpertask)) + '.root --tpc-sectors ' + str(s)+'-'+str(s+sectorpertask-1) + ' --configKeyValues "GPU_global.continuousMaxTimeBin=100000;GPU_proc.ompThreads=4"'
       tpcclussect['env'] = { "OMP_NUM_THREADS" : "4", "SHMSIZE" : "5000000000" }
       workflow['stages'].append(tpcclussect)

     TPCCLUSMERGEtask=createTask(name='tpcclustermerge_'+str(tf), needs=tpcclustertasks, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='10000')
     TPCCLUSMERGEtask['cmd']='o2-commonutils-treemergertool -i tpc-native-clusters-part*.root -o tpc-native-clusters.root -t tpcrec' #--asfriend preferable but does not work
     workflow['stages'].append(TPCCLUSMERGEtask)
     tpcreconeeds.append(TPCCLUSMERGEtask['name'])
   else:
     tpcclus = createTask(name='tpccluster_' + str(tf), needs=[TPCDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=NWORKERS, mem='2000')
     tpcclus['cmd'] = 'o2-tpc-chunkeddigit-merger --rate 1000 --tpc-lanes ' + str(NWORKERS)
     tpcclus['cmd'] += ' | o2-tpc-reco-workflow ' + getDPL_global_options() + ' --input-type digitizer --output-type clusters,send-clusters-per-sector --configKeyValues "GPU_global.continuousMaxTimeBin=100000;GPU_proc.ompThreads=1"'
     workflow['stages'].append(tpcclus)
     tpcreconeeds.append(tpcclus['name'])

   TPCRECOtask=createTask(name='tpcreco_'+str(tf), needs=tpcreconeeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], relative_cpu=3/8, mem='16000')
   TPCRECOtask['cmd'] = 'o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True) + ' --input-type clusters --output-type tracks,send-clusters-per-sector --configKeyValues "GPU_global.continuousMaxTimeBin=100000;GPU_proc.ompThreads='+str(NWORKERS)+'"'
   workflow['stages'].append(TPCRECOtask)

   ITSRECOtask=createTask(name='itsreco_'+str(tf), needs=[det_to_digitask["ITS"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   ITSRECOtask['cmd'] = 'o2-its-reco-workflow --trackerCA --tracking-mode async ' + getDPL_global_options()
   workflow['stages'].append(ITSRECOtask)

   FT0RECOtask=createTask(name='ft0reco_'+str(tf), needs=[det_to_digitask["FT0"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   FT0RECOtask['cmd'] = 'o2-ft0-reco-workflow ' + getDPL_global_options()
   workflow['stages'].append(FT0RECOtask)

   ITSTPCMATCHtask=createTask(name='itstpcMatch_'+str(tf), needs=[TPCRECOtask['name'], ITSRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='8000', relative_cpu=3/8)
   ITSTPCMATCHtask['cmd']= 'o2-tpcits-match-workflow ' + getDPL_global_options(bigshm=True) + ' --tpc-track-reader \"tpctracks.root\" --tpc-native-cluster-reader \"--infile tpc-native-clusters.root\"'
   workflow['stages'].append(ITSTPCMATCHtask)

   TRDTRACKINGtask = createTask(name='trdreco_'+str(tf), needs=[TRDDigitask['name'], ITSTPCMATCHtask['name'], TPCRECOtask['name'], ITSRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   TRDTRACKINGtask['cmd'] = 'o2-trd-tracklet-transformer ' + getDPL_global_options()
   TRDTRACKINGtask['cmd'] += ' | o2-trd-global-tracking ' + getDPL_global_options()
   workflow['stages'].append(TRDTRACKINGtask)

   TOFRECOtask = createTask(name='tofmatch_'+str(tf), needs=[ITSTPCMATCHtask['name'], det_to_digitask["TOF"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   TOFRECOtask['cmd'] = 'o2-tof-reco-workflow ' + getDPL_global_options()
   workflow['stages'].append(TOFRECOtask)

   TOFTPCMATCHERtask = createTask(name='toftpcmatch_'+str(tf), needs=[TOFRECOtask['name'], TPCRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1000')
   TOFTPCMATCHERtask['cmd'] = 'o2-tof-matcher-workflow ' + getDPL_global_options()
   workflow['stages'].append(TOFTPCMATCHERtask)

   MFTRECOtask = createTask(name='mftreco_'+str(tf), needs=[det_to_digitask["MFT"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='1500')
   MFTRECOtask['cmd'] = 'o2-mft-reco-workflow ' + getDPL_global_options()
   workflow['stages'].append(MFTRECOtask)

   pvfinderneeds = [ITSTPCMATCHtask['name'], FT0RECOtask['name'], TOFTPCMATCHERtask['name'], MFTRECOtask['name'], TRDTRACKINGtask['name']]
   PVFINDERtask = createTask(name='pvfinder_'+str(tf), needs=pvfinderneeds, tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=NWORKERS, mem='4000')
   PVFINDERtask['cmd'] = 'o2-primary-vertexing-workflow ' + getDPL_global_options()
   # PVFINDERtask['cmd'] += ' --vertexing-sources "ITS,ITS-TPC,ITS-TPC-TOF" --vetex-track-matching-sources "ITS,ITS-TPC,ITS-TPC-TOF"'
   workflow['stages'].append(PVFINDERtask)

   if includeQC:

     ### ITS
     # fixme: not working yet, ITS will prepare a way to read clusters and tracks. Also ITSDictionary will be needed. 
     # ITSClustersTracksQCneeds = [ITSRECOtask['name']] 
     # ITSClustersTracksQCtask = createTask(name='itsClustersTracksQC_'+str(tf), needs=ITSClustersTracksQCneeds, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=1, mem='2000')
     # ITSClustersTracksQCtask['cmd'] = 'o2-missing-reader | o2-qc --config json://${O2DPG_ROOT}/MC/config/QC/json/its-clusters-tracks-qc.json ' + getDPL_global_options()
     # workflow['stages'].append(ITSClustersTracksQCtask)

     ### MFT
     # fixme: there is a bug in Check which causes a segfault, uncomment when the fix is merged
     # MFTDigitsQCneeds = [det_to_digitask["MFT"]['name']]
     # MFTDigitsQCtask = createTask(name='mftDigitsQC_'+str(tf), needs=MFTDigitsQCneeds, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=1, mem='2000')
     # MFTDigitsQCtask['cmd'] = 'o2-qc-mft-digits-root-file-reader --mft-digit-infile=mftdigits.root | o2-qc --config json://${O2DPG_ROOT}/MC/config/QC/json/qc-mft-digit.json ' + getDPL_global_options()
     # workflow['stages'].append(MFTDigitsQCtask)

     MFTClustersQCneeds = [MFTRECOtask['name']]
     MFTClustersQCtask = createTask(name='mftClustersQC_'+str(tf), needs=MFTClustersQCneeds, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=1, mem='2000')
     MFTClustersQCtask['cmd'] = 'o2-qc-mft-clusters-root-file-reader --mft-cluster-infile=mftclusters.root | o2-qc --config json://${O2DPG_ROOT}/MC/config/QC/json/qc-mft-cluster.json ' + getDPL_global_options()
     workflow['stages'].append(MFTClustersQCtask)

     MFTTracksQCneeds = [MFTRECOtask['name']]
     MFTTracksQCtask = createTask(name='mftTracksQC_'+str(tf), needs=MFTTracksQCneeds, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=1, mem='2000')
     MFTTracksQCtask['cmd'] = 'o2-qc-mft-tracks-root-file-reader --mft-track-infile=mfttracks.root | o2-qc --config json://${O2DPG_ROOT}/MC/config/QC/json/qc-mft-track.json ' + getDPL_global_options()
     workflow['stages'].append(MFTTracksQCtask)

     ### TPC
     TPCTrackingQCneeds = [TPCRECOtask['name']]
     TPCTrackingQCtask = createTask(name='tpcTrackingQC_'+str(tf), needs=TPCTrackingQCneeds, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=2, mem='2000')
     TPCTrackingQCtask['cmd'] = 'o2-tpc-track-reader | o2-tpc-reco-workflow --input-type clusters --infile tpc-native-clusters.root --output-type disable-writer | o2-qc --config json://${O2DPG_ROOT}/MC/config/QC/json/tpc-qc-tracking-direct.json ' + getDPL_global_options()
     workflow['stages'].append(TPCTrackingQCtask)

     ### TRD
     TRDDigitsQCneeds = [TRDDigitask['name']]
     TRDDigitsQCtask = createTask(name='trdDigitsQC_'+str(tf), needs=TRDDigitsQCneeds, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=1, mem='2000')
     TRDDigitsQCtask['cmd'] = 'o2-trd-trap-sim | o2-qc --config json://${O2DPG_ROOT}/MC/config/QC/json/trd-digits-task.json ' + getDPL_global_options()
     workflow['stages'].append(TRDDigitsQCtask)

     ### RECO
     vertexQCneeds = [PVFINDERtask['name']]
     vertexQCtask = createTask(name='vertexQC_'+str(tf), needs=vertexQCneeds, tf=tf, cwd=timeframeworkdir, lab=["QC"], cpu=1, mem='2000')
     vertexQCtask['cmd'] = 'o2-primary-vertex-reader-workflow | o2-qc --config json://${O2DPG_ROOT}/MC/config/QC/json/vertexing-qc-direct-mc.json ' + getDPL_global_options()
     workflow['stages'].append(vertexQCtask)

     
 
   #secondary vertexer
   SVFINDERtask = createTask(name='svfinder_'+str(tf), needs=[PVFINDERtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu=1, mem='2000')
   SVFINDERtask['cmd'] = 'o2-secondary-vertexing-workflow ' + getDPL_global_options()
   workflow['stages'].append(SVFINDERtask)

  # -----------
  # produce AOD
  # -----------
   aodneeds = [PVFINDERtask['name'], SVFINDERtask['name'], TOFRECOtask['name'], TRDTRACKINGtask['name']]
   if usebkgcache:
     aodneeds += [ BKG_KINEDOWNLOADER_TASK['name'] ]

   aod_df_id = '{0:03}'.format(tf)

   AODtask = createTask(name='aod_'+str(tf), needs=aodneeds, tf=tf, cwd=timeframeworkdir, lab=["AOD"], mem='4000', cpu='1')
   AODtask['cmd'] = ('','ln -nfs ../bkg_Kine.root . ;')[doembedding]
   AODtask['cmd'] += 'o2-aod-producer-workflow --reco-mctracks-only 1 --aod-writer-keep dangling --aod-writer-resfile AO2D'
   AODtask['cmd'] += ' --aod-timeframe-id ${ALIEN_PROC_ID}' + aod_df_id + ' ' + getDPL_global_options(bigshm=True)
   workflow['stages'].append(AODtask)

   # AOD merging / combination step
   AOD_merge_task = createTask(name='aodmerge_'+str(tf), needs= [ AODtask['name'] ], tf=tf, cwd=timeframeworkdir, lab=["AOD"], mem='2000', cpu='1')
   AOD_merge_task['cmd'] = '[ -f ../AO2D.root ] && mv ../AO2D.root ../AO2D_old.root;'
   AOD_merge_task['cmd'] += ' echo "./AO2D.root" > input.txt;'
   AOD_merge_task['cmd'] += ' [ -f ../AO2D_old.root ] && echo "../AO2D_old.root" >> input.txt;'
   AOD_merge_task['cmd'] += ' o2-aod-merger --output ../AO2D.root;'
   AOD_merge_task['cmd'] += ' rm ../AO2D_old.root || true'
   AOD_merge_task['semaphore'] = 'aodmerge' #<---- this is making sure that only one merge is running at any time
   workflow['stages'].append(AOD_merge_task)

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


dump_workflow(workflow["stages"], args.o)

exit (0)
