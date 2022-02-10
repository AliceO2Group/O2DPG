#!/bin/bash

#
# A example workflow MC->RECO->AOD for a simple pp min bias 
# production

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1
[ ! "${O2PHYSICS_ROOT}" ] && echo "Error: This needs O2Physics loaded" && exit 1
[ ! "${QUALITYCONTROL_ROOT}" ] && echo "Error: This needs QualityControl loaded" && exit 1

# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh

# ----------- START ACTUAL JOB  ----------------------------- 

NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 14000  -col pp -gen pythia8 -proc inel -tf 1    \
                                                       -ns 20 -e ${SIMENGINE}                   \
                                                       -j ${NWORKERS} -interactionRate 500000   \
                                                       --include-qc

# run workflow
# ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt vertexQC
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json

# publish the current dir to ALIEN
# copy_ALIEN

