#!/bin/bash

#
# A example workflow MC->RECO->AOD doing signal-background embedding, meant
# to study embedding speedups.
# Background events are reused across timeframes. 
# 

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- START ACTUAL JOB  ----------------------------- 

NSIGEVENTS=${NSIGEVENTS:-20}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
NBKGEVENTS=${NBKGEVENTS:-20}
MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}
PYPROCESS=${PYPROCESS:-ccbar} #ccbar, bbar, ...

# create simulation workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 5020 -col pp -gen pythia8 -proc ${PYPROCESS} -tf ${NTIMEFRAMES} -nb ${NBKGEVENTS} \
                                                        -ns ${NSIGEVENTS} -e ${SIMENGINE} -interactionRate 500000   \
                                                        -j ${NWORKERS} -genBkg pythia8 --embedding

# Simulating a user who extends this workflow by an analysis task
${O2DPG_ROOT}/MC/bin/o2dpg-workflow-tools.py create workflow_ana --add-task mchist
needs="aodmerge"

# Comments:
#   1. The output AOD name is the one created by the simulation workflow
#   2. base name of AOD merge tasks is known as well to be aodmerge
${O2DPG_ROOT}/MC/bin/o2dpg-workflow-tools.py modify workflow_ana mchist --cmd "o2-analysistutorial-mc-histograms --aod-file AO2D.root" \
                                                                        --needs $needs --mem 2000 --cpu 1 --labels ANALYSIS

${O2DPG_ROOT}/MC/bin/o2dpg-workflow-tools.py merge workflow workflow_ana -o workflow_merged




# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow_merged.json
