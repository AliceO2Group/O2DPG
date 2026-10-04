#!/bin/bash

#
# A pp workflow MC->RECO->AOD with ITS and MFT staggering enabled
#

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- START ACTUAL JOB  -----------------------------

NSIGEVENTS=${NSIGEVENTS:-5}
SIGPROC=${SIGPROC:-cdiff}
NTIMEFRAMES=${NTIMEFRAMES:-2}
SIMENGINE=${SIMENGINE:-TGeant3}
NWORKERS=${NWORKERS:-1}
SEED=${SEED:-624}
INTERACTIONRATE=${INTERACTIONRATE:-50000}

# enable ITS and MFT staggering in all consumers
export ALIEN_JDL_ITS_STAGGERED=1
export ALIEN_JDL_MFT_STAGGERED=1

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 5020 -col pp -gen pythia8 -proc ${SIGPROC} -ns ${NSIGEVENTS} \
                                           -tf ${NTIMEFRAMES} -e ${SIMENGINE} -j ${NWORKERS} -seed ${SEED} \
                                           --include-analysis -run 310000 -interactionRate ${INTERACTIONRATE} \
                                           --include-local-qc
