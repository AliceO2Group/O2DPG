#!/bin/bash

#
# Inject OmegaC (decaying to Xi pi) signal into background with a pythia8 box gun generator

# make sure O2DPG + O2 is loaded

[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- START ACTUAL JOB  -----------------------------

NWORKERS=${NWORKERS:-8}
TARGETTASK=${TARGETTASK:-aod}
CPU_LIMIT=${CPU_LIMIT:-8}

MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}
NSIGEVENTS=${NSIGEVENTS:-1}
NBKGEVENTS=${NBKGEVENTS:-1}

NTIMEFRAMES=${NTIMEFRAMES:-1}
SYSTEM=${SYSTEM:-pp}
ENERGY=${ENERGY:-13600}
[[ ${SPLITID} != "" ]] && SEED="-seed ${SPLITID}" || SEED=""

${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -e ${SIMENGINE} ${SEED} -eCM 13600 -col pp -colBkg pp -gen external -genBkg pythia8 -procBkg inel -j ${NWORKERS} -ns ${NSIGEVENTS} -nb ${NBKGEVENTS} -tf ${NTIMEFRAMES} -interactionRate 500000 -confKey "Diamond.width[2]=6." \
        --embedding -ini $O2DPG_ROOT/MC/config/PWGHF/ini/GeneratorHFOmegaCToXiPiEmb.ini 


# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt ${TARGETTASK} --cpu-limit ${CPU_LIMIT}
