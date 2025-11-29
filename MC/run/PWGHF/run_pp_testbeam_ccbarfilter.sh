#!/bin/bash

#
# A example workflow MC->RECO->AOD for a simple pp min bias 
# production, targetting test beam conditions.

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- START ACTUAL JOB  ----------------------------- 

NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}
NSIGEVENTS=${NSIGEVENTS:-1}
NBKGEVENTS=${NBKGEVENTS:-1}
NTIMEFRAMES=${NTIMEFRAMES:-1}

# create workflow

#ccbar filter
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 900 -col pp -gen pythia8 -proc "inel" -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -interactionRate 10000 -confKey "Diamond.width[2]=6." -e TGeant4 \
        -ini $O2DPG_ROOT/MC/config/PWGHF/ini/GeneratorHF_ccbar.ini \

# run workflow
# allow increased timeframe parallelism with --cpu-limit 32 
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod --cpu-limit 32


