#!/bin/bash

#
# A example workflow doing signal-background embedding, meant
# to study embedding speedups.
# Background events are reused across timeframes. 
# 

# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh

# ----------- START ACTUAL JOB  ----------------------------- 

NSIGEVENTS=${NSIGEVENTS:-20}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
NBKGEVENTS=${NBKGEVENTS:-20}
MODULES="--skipModules ZDC"


# background task -------
taskwrapper bkgsim.log o2-sim -j ${NWORKERS} -n ${NBKGEVENTS} -g pythia8hi ${MODULES} -o bkg \
            --configFile ${O2DPG_ROOT}/MC/config/common/ini/basic.ini

# loop over timeframes
for tf in `seq 1 ${NTIMEFRAMES}`; do

  RNDSEED=0
  PTHATMIN=0.  # [default = 0]
  PTHATMAX=-1. # [default = -1]

  # produce the signal configuration
  ${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
    	     --output=pythia8.cfg \
	     --seed=${RNDSEED} \
	     --idA=2212 \
	     --idB=2212 \
	     --eCM=13000. \
	     --process=ccbar \
	     --ptHatMin=${PTHATMIN} \
	     --ptHatMax=${PTHATMAX}
 
  # simulate the signals for this timeframe
  taskwrapper sgnsim_${tf}.log o2-sim ${MODULES} -n ${NSIGEVENTS} -e TGeant3 -j ${NWORKERS} -g extgen \
       --configFile ${O2DPG_ROOT}/MC/config/PWGHF/ini/GeneratorHF.ini                                 \
       --configKeyValues "GeneratorPythia8.config=pythia8.cfg"                                        \
       --embedIntoFile bkg_Kine.root                                                                  \
       -o sgn${tf}

  CONTEXTFILE=collisioncontext_${tf}.root

  cp sgn${tf}_grp.root o2sim_grp.root

  # now run digitization phase
  echo "Running digitization for $intRate kHz interaction rate"
  
  gloOpt="-b --run --shm-segment-size ${SHMSIZE:-20000000000}" # TODO: decide shared mem based on event number - default should be ok for 100PbPb timeframes

  taskwrapper tpcdigi_${tf}.log o2-sim-digitizer-workflow $gloOpt -n ${NSIGEVENTS} --sims bkg,sgn${tf} --onlyDet TPC --interactionRate 50000 --tpc-lanes ${NWORKERS} --outcontext ${CONTEXTFILE}
  [ ! -f tpcdigits_${tf}.root ] && mv tpcdigits.root tpcdigits_${tf}.root
  # --> a) random seeding
  # --> b) propagation of collisioncontext and application in other digitization steps

  echo "Return status of TPC digitization: $?"
  taskwrapper trddigi_${tf}.log o2-sim-digitizer-workflow $gloOpt -n ${NSIGEVENTS} --sims bkg,sgn${tf} --onlyDet TRD --interactionRate 50000 --configKeyValues "TRDSimParams.digithreads=10" --incontext ${CONTEXTFILE}
  echo "Return status of TRD digitization: $?"

  taskwrapper restdigi_${tf}.log o2-sim-digitizer-workflow $gloOpt -n ${NSIGEVENTS} --sims bkg,sgn${tf} --skipDet TRD,TPC,FT0 --interactionRate 50000 --incontext ${CONTEXTFILE}
  echo "Return status of OTHER digitization: $?"

  # TODO: check value for MaxTimeBin; A large value had to be set tmp in order to avoid crashes bases on "exceeding timeframe limit"
  taskwrapper tpcreco_${tf}.log o2-tpc-reco-workflow $gloOpt --tpc-digit-reader \"--infile tpcdigits_${tf}.root\" --input-type digits --output-type clusters,tracks  --tpc-track-writer \"--treename events --track-branch-name Tracks --trackmc-branch-name TracksMCTruth\" --configKeyValues \"GPU_global.continuousMaxTimeBin=100000\"
  echo "Return status of tpcreco: $?"

  # we need to move these products somewhere
  mv tpctracks.root tpctracks_${tf}.root

done

# We need to exit for the ALIEN JOB HANDLER!
exit 0
