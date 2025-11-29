#!/bin/bash

#
# A example workflow MC->RECO->AOD for a simple pp min bias
# production, targetting test beam conditions.

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- START ACTUAL JOB  -----------------------------

NWORKERS=${NWORKERS:-8}
CPU_LIMIT=${CPU_LIMIT:-32}
MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}
NSIGEVENTS=${NSIGEVENTS:-30}
NTIMEFRAMES=${NTIMEFRAMES:-1}
[[ ${SPLITID} != "" ]] && SEED="-seed ${SPLITID}" || SEED=""
# create workflow

#ccbar filter
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 13600 -col pp -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -interactionRate 500000 -confKey "Diamond.width[2]=6." -e ${SIMENGINE} ${SEED} \
        -ini $O2DPG_ROOT/MC/config/PWGHF/ini/GeneratorHFTrigger_Xi_Omega_C.ini \

# run workflow
# allow increased timeframe parallelism with --cpu-limit 32
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod --cpu-limit ${CPU_LIMIT}