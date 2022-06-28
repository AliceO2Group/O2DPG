#!/bin/bash

#
# A example workflow MC->RECO->AOD doing signal-background embedding, meant
# to study embedding speedups.
# Background events are reused across timeframes. 
# 

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh

# ----------- START ACTUAL JOB  ----------------------------- 

NSIGEVENTS=${NSIGEVENTS:-20}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
NBKGEVENTS=${NBKGEVENTS:-20}
MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}
PYPROCESS=${PYPROCESS:-ccbar} #ccbar, bbar, ...
SEED=${SEED:+-seed $SEED}

export ALICEO2_CCDB_LOCALCACHE=$PWD/.ccdb

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 5020 -col pp -gen pythia8 -proc ${PYPROCESS} \
                                           -colBkg PbPb -genBkg pythia8 -procBkg "heavy_ion" \
                                           -tf ${NTIMEFRAMES} -nb ${NBKGEVENTS}              \
                                           -ns ${NSIGEVENTS} -e ${SIMENGINE}                 \
                                           -j ${NWORKERS} --embedding -interactionRate 50000 \
                                           --include-analysis -run 310000 ${SEED}

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --cpu-limit ${CPULIMIT:-8} -tt aod

unset ALICEO2_CCDB_LOCALCACHE
