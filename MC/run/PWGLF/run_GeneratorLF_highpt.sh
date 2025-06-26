#!/bin/bash


# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- START ACTUAL JOB  -----------------------------

NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}
NSIGEVENTS=${NSIGEVENTS:-1}
NTIMEFRAMES=${NTIMEFRAMES:-1}
INTRATE=${INTRATE:-500000}
SYSTEM=${SYSTEM:-pp}
ENERGY=${ENERGY:-13600}
[[ ${SPLITID} != "" ]] && SEED="-seed ${SPLITID}" || SEED=""

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM ${ENERGY} -col ${SYSTEM} -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -interactionRate ${INTRATE} -confKey "Diamond.width[0]=0.005;Diamond.width[1]=0.005;Diamond.width[2]=6." -e ${SIMENGINE} ${SEED} -mod "--skipModules ZDC" \
        -ini $O2DPG_ROOT/MC/config/PWGLF/ini/GeneratorLF_HighPt.ini

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod --cpu-limit 32
