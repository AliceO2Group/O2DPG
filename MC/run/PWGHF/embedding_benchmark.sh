#!/bin/bash

#
# A example workflow MC->RECO->AOD doing signal-background embedding, meant
# to study embedding speedups.
# Background events are reused across timeframes. 
# 

# make sure O2DPG + O2 is loaded
[ ! "{O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "{O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh

# ----------- START ACTUAL JOB  ----------------------------- 

NSIGEVENTS=${NSIGEVENTS:-20}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
NBKGEVENTS=${NBKGEVENTS:-20}
MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}

# We will collect output files of the workflow in a dedicated output dir
# (these are typically the files that should be left-over from a GRID job)
[ ! -d output ] && mkdir output

copypersistentsimfiles() {
  simprefix=$1
  outputdir=$2
  cp ${simprefix}_Kine.root ${simprefix}_grp.root ${simprefix}*.ini ${outputdir}
}

# background task -------
taskwrapper bkgsim.log o2-sim -e ${SIMENGINE} -j ${NWORKERS} -n ${NBKGEVENTS} -g pythia8hi ${MODULES} -o bkg \
            --configFile ${O2DPG_ROOT}/MC/config/common/ini/basic.ini
echo "Return status of background sim: $?"
# register some background output --> make this declarative
copypersistentsimfiles bkg output

# loop over timeframes
for tf in `seq 1 ${NTIMEFRAMES}`; do

  RNDSEED=0
  PTHATMIN=0.  # [default = 0]
  PTHATMAX=-1. # [default = -1]

  # produce the signal configuration
  taskwrapper gensgnconf${tf}.log ${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
    	     --output=pythia8.cfg \
	     --seed=${RNDSEED} \
	     --idA=2212 \
	     --idB=2212 \
	     --eCM=13000. \
	     --process=ccbar \
	     --ptHatMin=${PTHATMIN} \
	     --ptHatMax=${PTHATMAX}
 
  # simulate the signals for this timeframe
  taskwrapper sgnsim_${tf}.log o2-sim -e ${SIMENGINE} ${MODULES} -n ${NSIGEVENTS} -j ${NWORKERS} -g extgen \
       --configFile ${O2DPG_ROOT}/MC/config/PWGHF/ini/GeneratorHF.ini                                 \
       --configKeyValues "GeneratorPythia8.config=pythia8.cfg"                                        \
       --embedIntoFile bkg_Kine.root                                                                  \
       -o sgn${tf}

  # register some signal output --> make this declarative
  # copypersistentsimfiles sgn${tf} output
  # we need to copy the current geometry file for its-reco
  cp sgn${tf}_geometry.root o2sim_geometry.root

  CONTEXTFILE=collisioncontext_${tf}.root

  # now run digitization phase
  echo "Running digitization for $intRate kHz interaction rate"
  
  gloOpt="-b --run --shm-segment-size ${SHMSIZE:-50000000000}" # TODO: decide shared mem based on event number - default should be ok for 100PbPb timeframes

  taskwrapper tpcdigi_${tf}.log o2-sim-digitizer-workflow $gloOpt -n ${NSIGEVENTS} --sims bkg,sgn${tf} --onlyDet TPC --interactionRate 50000 --tpc-lanes ${NWORKERS} --outcontext ${CONTEXTFILE}
  echo "Return status of TPC digitization: $?"

  [ ! -f tpcdigits_${tf}.root ] && mv tpcdigits.root tpcdigits_${tf}.root
  # --> a) random seeding
  # --> b) propagation of collisioncontext and application in other digitization steps

  taskwrapper trddigi_${tf}.log o2-sim-digitizer-workflow $gloOpt -n ${NSIGEVENTS} --sims bkg,sgn${tf} --onlyDet TRD --interactionRate 50000 --configKeyValues "TRDSimParams.digithreads=10" --incontext ${CONTEXTFILE}
  echo "Return status of TRD digitization: $?"

  taskwrapper restdigi_${tf}.log o2-sim-digitizer-workflow $gloOpt -n ${NSIGEVENTS} --sims bkg,sgn${tf} --skipDet TRD,TPC --interactionRate 50000 --incontext ${CONTEXTFILE}
  echo "Return status of OTHER digitization: $?"

  cp bkg_grp.root o2sim_grp.root
  cp collisioncontext_${tf}.root collisioncontext.root
  # -----------
  # reco
  # -----------

  # TODO: check value for MaxTimeBin; A large value had to be set tmp in order to avoid crashes bases on "exceeding timeframe limit"
  taskwrapper tpcreco_${tf}.log o2-tpc-reco-workflow $gloOpt --tpc-digit-reader \"--infile tpcdigits_${tf}.root\" --input-type digits --output-type clusters,tracks,send-clusters-per-sector  --configKeyValues "\"GPU_global.continuousMaxTimeBin=100000;GPU_proc.ompThreads=${NWORKERS}\""
  echo "Return status of tpcreco: $?"

  echo "Running ITS reco flow"
  taskwrapper itsreco_${tf}.log  o2-its-reco-workflow --trackerCA --async-phase $gloOpt
  echo "Return status of itsreco: $?"

  echo "Running FT0 reco flow"
  #needs FT0 digitized data
  taskwrapper ft0reco_${tf}.log o2-ft0-reco-workflow $gloOpt
  echo "Return status of ft0reco: $?"

  echo "Running ITS-TPC macthing flow"
  #needs results of o2-tpc-reco-workflow, o2-its-reco-workflow and o2-fit-reco-workflow
  taskwrapper itstpcMatch_${tf}.log o2-tpcits-match-workflow $gloOpt --tpc-track-reader \"tpctracks.root\" --tpc-native-cluster-reader \"--infile tpc-native-clusters.root\"
  echo "Return status of itstpcMatch: $?"

  echo "Running ITSTPC-TOF macthing flow"
  #needs results of TOF digitized data and results of o2-tpcits-match-workflow
  taskwrapper tofMatch_${tf}.log o2-tof-reco-workflow $gloOpt
  echo "Return status of its-tpc-tof match: $?"

  echo "Running primary vertex finding flow"
  #needs results of TPC-ITS matching and FIT workflows
  taskwrapper pvfinder_${tf}.log o2-primary-vertexing-workflow $gloOpt
  echo "Return status of primary vertexing: $?"

  # -----------
  # produce AOD
  # -----------
  
  # enable later. It still has memory access problems 
  # taskwrapper aod_${tf}.log o2-aod-producer-workflow --aod-writer-keep dangling --aod-writer-resfile "AO2D" --aod-writer-resmode UPDATE --aod-timeframe-id ${tf} $gloOpt

  cp ${CONTEXTFILE} output

  # cleanup step for this timeframe (we cleanup disc space early so as to make possible checkpoint dumps smaller)
  taskwrapper cleanup_${tf}.log "[ -f aod${tf}.log_done ] && rm sgn${tf}* && rm *digits*.root; exit 0"
done

# We need to exit for the ALIEN JOB HANDLER!
exit 0
