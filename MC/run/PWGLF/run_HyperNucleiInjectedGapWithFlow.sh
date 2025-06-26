#!/bin/bash

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ----------- CONFIGURE --------------------------
export IGNORE_VALIDITYCHECK_OF_CCDB_LOCALCACHE=1
#export ALICEO2_CCDB_LOCALCACHE=.ccdb


# ----------- START ACTUAL JOB  -----------------------------

NWORKERS=${NWORKERS:-8}
SIMENGINE=${SIMENGINE:-TGeant4}
NSIGEVENTS=${NSIGEVENTS:-1}
NTIMEFRAMES=${NTIMEFRAMES:-1}
INTRATE=${INTRATE:-50000}
SYSTEM=${SYSTEM:-PbPb}
ENERGY=${ENERGY:-5360}
CFGINIFILE=${CFGINIFILE:-"${O2DPG_ROOT}/MC/config/PWGLF/ini/GeneratorLFHyperNucleiPbPbGapWithFlow.ini"}

[[ ${SPLITID} != "" ]] && SEED="-seed ${SPLITID}" || SEED="-seed 0"

echo "NWORKERS = $NWORKERS"

# create workflow
O2_SIM_WORKFLOW=${O2_SIM_WORKFLOW:-"${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py"}
$O2_SIM_WORKFLOW -eCM ${ENERGY} -col ${SYSTEM} -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -interactionRate ${INTRATE} -confKey "Diamond.width[0]=0.1;Diamond.width[1]=0.1;Diamond.width[2]=6." -e ${SIMENGINE} ${SEED} -ini $CFGINIFILE

# run workflow
O2_SIM_WORKFLOW_RUNNER=${O2_SIM_WORKFLOW_RUNNER:-"${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py"}
$O2_SIM_WORKFLOW_RUNNER -f workflow.json -tt aod --cpu-limit $NWORKERS
