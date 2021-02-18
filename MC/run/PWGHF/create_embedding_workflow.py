#!/usr/bin/env python3

#
# A script producing a consistent MC->RECO->AOD workflow with optional embedding.
# 

import argparse
from os import environ
import json

parser = argparse.ArgumentParser(description='Create a PWGHF embedding pipeline')
parser.add_argument('-nb',help='number of background events / timeframe', default=20)
parser.add_argument('-ns',help='number of signal events / timeframe', default=20)
parser.add_argument('-tf',help='number of timeframes', default=2)
parser.add_argument('-j',help='number of workers (if applicable)', default=8)
parser.add_argument('-e',help='simengine', default='TGeant4')
parser.add_argument('-o',help='output workflow file', default='workflow.json')
parser.add_argument('--embedding',help='whether to embedd into background', default=True) 
parser.add_argument('--noIPC',help='disable shared memory in DPL') 
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

NSIGEVENTS=args.ns
NTIMEFRAMES=int(args.tf)
NWORKERS=args.j
NBKGEVENTS=args.nb
MODULES="--skipModules ZDC"
SIMENGINE=args.e

workflow={}
workflow['stages'] = []

taskcounter=0
def createTask(name='', needs=[], tf=-1, cwd='./', lab=[], cpu=0, mem=0):
    global taskcounter
    taskcounter = taskcounter + 1
    return { 'name': name, 'cmd':'', 'needs': needs, 'resources': { 'cpu': cpu , 'mem': mem }, 'timeframe' : tf, 'labels' : lab, 'cwd' : cwd }

def getDPL_global_options(bigshm=False):
   if args.noIPC!=None:
      return "-b --run --rate 1 --no-IPC"
   if bigshm:
      return "-b --run --rate 1 --shm-segment-size ${SHMSIZE:-50000000000} --session " + str(taskcounter) + ' --driver-client-backend ws://'
   else:
      return "-b --run --rate 1 --session " + str(taskcounter) + ' --driver-client-backend ws://'

doembedding=True if args.embedding=='True' or args.embedding==True else False

if doembedding:
    # ---- background transport task -------
    BKGtask=createTask(name='bkgsim', lab=["GEANT"], cpu='8')
    BKGtask['cmd']='o2-sim -e ' + SIMENGINE + ' -j ' + str(NWORKERS) + ' -n ' + str(NBKGEVENTS) + ' -g pythia8hi ' +  str(MODULES) + ' -o bkg --configFile ${O2DPG_ROOT}/MC/config/common/ini/basic.ini'
    workflow['stages'].append(BKGtask)

# loop over timeframes
for tf in range(1, NTIMEFRAMES + 1):
   timeframeworkdir='tf'+str(tf)

   # ----  transport task -------
   # function encapsulating the signal sim part
   # first argument is timeframe id
   RNDSEED=0    # 0 means random seed !
   PTHATMIN=0.  # [default = 0]
   PTHATMAX=-1. # [default = -1]

   # produce the signal configuration
   SGN_CONFIG_task=createTask(name='gensgnconf_'+str(tf), tf=tf, cwd=timeframeworkdir)

   SGN_CONFIG_task['cmd'] = '${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
             --output=pythia8_'+ str(tf) +'.cfg \
	     --seed='+str(RNDSEED)+' \
	     --idA=2212 \
	     --idB=2212 \
	     --eCM=13000. \
	     --process=ccbar \
	     --ptHatMin=' + str(PTHATMIN) + ' \
	     --ptHatMax=' + str(PTHATMAX)
   workflow['stages'].append(SGN_CONFIG_task) 

   if doembedding:
       # link background files to current working dir for this timeframe
       LinkBKGtask=createTask(name='linkbkg_'+str(tf), needs=[BKGtask['name']], tf=tf, cwd=timeframeworkdir)
       LinkBKGtask['cmd']='ln -nsf ../bkg*.root .'
       workflow['stages'].append(LinkBKGtask) 

   # transport signals
   signalprefix='sgn_' + str(tf)
   signalneeds=[ SGN_CONFIG_task['name'] ]
   embeddinto= "--embedIntoFile bkg_Kine.root" if doembedding else ""
   if doembedding:
       signalneeds = signalneeds + [ BKGtask['name'], LinkBKGtask['name'] ]
   SGNtask=createTask(name='sgnsim_'+str(tf), needs=signalneeds, tf=tf, cwd='tf'+str(tf), lab=["GEANT"], cpu='5.')
   SGNtask['cmd']='o2-sim -e '+str(SIMENGINE) + ' ' + str(MODULES) + ' -n ' + str(NSIGEVENTS) +  ' -j ' + str(NWORKERS) + ' -g pythia8 '\
       + ' -o ' + signalprefix + ' ' + embeddinto
   workflow['stages'].append(SGNtask)

   # some tasks further below still want geometry + grp in fixed names, so we provide it here
   # Alternatively, since we have timeframe isolation, we could just work with standard o2sim_ files

   # We need to be careful here and distinguish between embedding and non-embedding cases 
   # (otherwise it can confuse itstpcmatching, see O2-2026). This is because only one of the GRPs is updated during digitization.
   if doembedding:
      LinkGRPFileTask=createTask(name='linkGRP_'+str(tf), needs=[BKGtask['name']], tf=tf, cwd=timeframeworkdir)
      LinkGRPFileTask['cmd']='ln -nsf bkg_grp.root o2sim_grp.root ; ln -nsf bkg_geometry.root o2sim_geometry.root'
   else:
      LinkGRPFileTask=createTask(name='linkGRP_'+str(tf), needs=[SGNtask['name']], tf=tf, cwd=timeframeworkdir)
      LinkGRPFileTask['cmd']='ln -nsf ' + signalprefix + '_grp.root o2sim_grp.root ; ln -nsf ' + signalprefix + '_geometry.root o2sim_geometry.root'
   workflow['stages'].append(LinkGRPFileTask)

   CONTEXTFILE='collisioncontext.root'
 
   simsoption=' --sims ' + ('bkg,'+signalprefix if doembedding else signalprefix)

   ContextTask=createTask(name='digicontext_'+str(tf), needs=[SGNtask['name'], LinkGRPFileTask['name']], tf=tf, 
                          cwd=timeframeworkdir, lab=["DIGI"], cpu='8')
   ContextTask['cmd'] = 'o2-sim-digitizer-workflow --only-context --interactionRate 50000 ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption
   workflow['stages'].append(ContextTask)

   TPCDigitask=createTask(name='tpcdigi_'+str(tf), needs=[ContextTask['name'], LinkGRPFileTask['name']],
                          tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu='8', mem='16000')
   TPCDigitask['cmd'] = 'o2-sim-digitizer-workflow ' + getDPL_global_options(bigshm=True) + ' -n ' + str(args.ns) + simsoption + ' --onlyDet TPC --interactionRate 50000 --tpc-lanes ' + str(NWORKERS) + ' --incontext ' + str(CONTEXTFILE)
   workflow['stages'].append(TPCDigitask)

   TRDDigitask=createTask(name='trddigi_'+str(tf), needs=[ContextTask['name']], tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu='8', mem='8000')
   TRDDigitask['cmd'] = 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet TRD --interactionRate 50000 --configKeyValues \"TRDSimParams.digithreads=' + str(NWORKERS) + '\" --incontext ' + str(CONTEXTFILE)
   workflow['stages'].append(TRDDigitask)

#   RESTDigitask=createTask(name='restdigi_'+str(tf), needs=[ContextTask['name'], LinkGRPFileTask['name']], tf=tf, cwd=timeframeworkdir, lab=["DIGI"], cpu='medium', mem='8000')
#   RESTDigitask['cmd'] = 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --skipDet TRD,TPC --interactionRate 50000 --incontext ' + str(CONTEXTFILE)
#   workflow['stages'].append(RESTDigitask)

   # we split the digitizers for improved load balancing --> the precise list needs to be made consistent with geometry and active sensors
   sensorlist = [ "ITS", "TOF", "FT0", "FV0", "FDD", "MCH", "MID", "MFT", "HMP", "EMC", "PHS", "CPV" ]
   # these are digitizers which are single threaded
   def createRestDigiTask(name):
      t = createTask(name=name, needs=[ContextTask['name']], tf=tf, cwd=timeframeworkdir, lab=["DIGI","SMALLDIGI"], cpu='1')
      t['cmd'] = 'o2-sim-digitizer-workflow ' + getDPL_global_options() + ' -n ' + str(args.ns) + simsoption + ' --onlyDet ' + str(det) + ' --interactionRate 50000 --incontext ' + str(CONTEXTFILE)
      workflow['stages'].append(t)
      return t

   det_to_digitask={}

   for det in sensorlist:
      name=str(det).lower() + "digi_"+str(tf)
      t=createRestDigiTask(name)
      det_to_digitask[det]=t

   # -----------
   # reco
   # -----------

   # TODO: check value for MaxTimeBin; A large value had to be set tmp in order to avoid crashes bases on "exceeding timeframe limit"
   TPCRECOtask=createTask(name='tpcreco_'+str(tf), needs=[TPCDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='3', mem='16000')
   TPCRECOtask['cmd'] = 'o2-tpc-reco-workflow ' + getDPL_global_options(bigshm=True) + ' --tpc-digit-reader "--infile tpcdigits.root" --input-type digits --output-type clusters,tracks,send-clusters-per-sector  --configKeyValues "GPU_global.continuousMaxTimeBin=100000;GPU_proc.ompThreads='+str(NWORKERS)+'"'
   workflow['stages'].append(TPCRECOtask)

   ITSRECOtask=createTask(name='itsreco_'+str(tf), needs=[det_to_digitask["ITS"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='1', mem='2000')
   ITSRECOtask['cmd'] = 'o2-its-reco-workflow --trackerCA --tracking-mode async ' + getDPL_global_options()
   workflow['stages'].append(ITSRECOtask)

   FT0RECOtask=createTask(name='ft0reco_'+str(tf), needs=[det_to_digitask["FT0"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"])
   FT0RECOtask['cmd'] = 'o2-ft0-reco-workflow ' + getDPL_global_options()
   workflow['stages'].append(FT0RECOtask)

   ITSTPCMATCHtask=createTask(name='itstpcMatch_'+str(tf), needs=[TPCRECOtask['name'], ITSRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], mem='8000', cpu='3')
   ITSTPCMATCHtask['cmd']= 'o2-tpcits-match-workflow ' + getDPL_global_options(bigshm=True) + ' --tpc-track-reader \"tpctracks.root\" --tpc-native-cluster-reader \"--infile tpc-native-clusters.root\"'
   workflow['stages'].append(ITSTPCMATCHtask)

   # this can be combined with TRD digitization if benefical
   TRDTRAPtask = createTask(name='trdtrap_'+str(tf), needs=[TRDDigitask['name']], tf=tf, cwd=timeframeworkdir, lab=["DIGI"])
   TRDTRAPtask['cmd'] = 'o2-trd-trap-sim'
   workflow['stages'].append(TRDTRAPtask)

   TRDTRACKINGtask = createTask(name='trdreco_'+str(tf), needs=[TRDTRAPtask['name'], ITSTPCMATCHtask['name'], TPCRECOtask['name'], ITSRECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"])
   TRDTRACKINGtask['cmd'] = 'echo "would do TRD tracking"' # 'o2-trd-global-tracking'
   workflow['stages'].append(TRDTRACKINGtask)

   TOFRECOtask = createTask(name='tofmatch_'+str(tf), needs=[ITSTPCMATCHtask['name'], det_to_digitask["TOF"]['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"])
   TOFRECOtask['cmd'] = 'o2-tof-reco-workflow ' + getDPL_global_options()
   workflow['stages'].append(TOFRECOtask)

   PVFINDERtask = createTask(name='pvfinder_'+str(tf), needs=[ITSTPCMATCHtask['name'], FT0RECOtask['name']], tf=tf, cwd=timeframeworkdir, lab=["RECO"], cpu='4')
   PVFINDERtask['cmd'] = 'o2-primary-vertexing-workflow ' + getDPL_global_options()
   workflow['stages'].append(PVFINDERtask)
 
  # -----------
  # produce AOD
  # -----------
  
  # enable later. It still has memory access problems 
  # taskwrapper aod_${tf}.log o2-aod-producer-workflow --aod-writer-keep dangling --aod-writer-resfile "AO2D" --aod-writer-resmode UPDATE --aod-timeframe-id ${tf} $gloOpt
   AODtask = createTask(name='aod_'+str(tf), needs=[PVFINDERtask['name'], TOFRECOtask['name'], TRDTRACKINGtask['name']], tf=tf, cwd=timeframeworkdir, lab=["AOD"])
   AODtask['cmd'] = ' echo "Would do AOD (enable later)" '
   workflow['stages'].append(AODtask)

   # cleanup step for this timeframe (we cleanup disc space early so as to make possible checkpoint dumps smaller)
   CLEANUPtask = createTask(name='cleanup_'+str(tf), needs=[AODtask['name']], tf=tf, cwd=timeframeworkdir)
   CLEANUPtask['cmd'] = ' echo "Doing cleanup" '
   workflow['stages'].append(CLEANUPtask)


def trimString(cmd):
  return ' '.join(cmd.split())

# insert taskwrapper stuff
for s in workflow['stages']:
  s['cmd']='. ${O2_ROOT}/share/scripts/jobutils.sh; taskwrapper ' + s['name']+'.log \'' + s['cmd'] + '\''

# remove whitespaces etc
for s in workflow['stages']:
  s['cmd']=trimString(s['cmd'])


# write workflow to json
workflowfile=args.o
with open(workflowfile, 'w') as outfile:
    json.dump(workflow, outfile, indent=2)

exit (0)
