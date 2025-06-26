#!/bin/bash

# ALICE HEPscore benchmark workflow
# A toy (few events) workflow MC->RECO->AOD doing signal-background embedding with PbPb + pp signals.
# Background events are reused across timeframes.

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- START ACTUAL JOB  -----------------------------
NSIGEVENTS=${NSIGEVENTS:-5}
NBKGEVENTS=${NBKGEVENTS:-5}
NTIMEFRAMES=${NTIMEFRAMES:-2}
SIMENGINE=TGeant4 
NWORKERS=${NWORKERS:-4}
CPULIMIT=${CPULIMIT:-4}
MODULES="--skipModules ZDC"
PYPROCESS=ccbar 
#
# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 5020 -col pp -gen pythia8 -proc ${PYPROCESS} \
                                           -colBkg PbPb -genBkg pythia8 -procBkg "heavy_ion" \
                                           -tf ${NTIMEFRAMES} -nb ${NBKGEVENTS}              \
                                           -ns ${NSIGEVENTS} -e ${SIMENGINE}                 \
                                           -j ${NWORKERS} --embedding -interactionRate 50000 \
                                           -run 310000 -seed 1

# timestamp chosen to correspond to a real data taking run

# enable (or point to) CCDB cache
if [ -d ${HEPSCORE_CCDB_ROOT}/.ccdb ]; then
  # benchmark is run with published CCDB
  echo "Setting CCDB cache to ${HEPSCORE_CCDB_ROOT}/.ccdb"
  export ALICEO2_CCDB_LOCALCACHE=${HEPSCORE_CCDB_ROOT}/.ccdb
  # fetch bin files (cluster dictionaries)
  cp ${HEPSCORE_CCDB_ROOT}/data/*.bin .
  cp ${HEPSCORE_CCDB_ROOT}/data/*.root .
else
  # benchmark is run in production mode: We fetch objects from server and cache them here.
  export ALICEO2_CCDB_LOCALCACHE=${PWD}/.ccdb
fi

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --cpu-limit ${CPULIMIT} -tt aod
