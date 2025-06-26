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
NBKGEVENTS=${NBKGEVENTS:-1}

# create workflow
# with a low interaction rate, the number of signals per tf is low (~11ms timeframe)

#Lc trigger

${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 900 -col pp -gen pythia8 -proc "ccbar" -tf 1 -ns 100 -e ${SIMENGINE} -j ${NWORKERS} -interactionRate 10000 -trigger "particle" -confKey "Diamond.width[2]=6.;TriggerParticle.pdg=4122;TriggerParticle.ptMin=0.5;TriggerParticle.yMin=-0.5;TriggerParticle.yMax=0.5" -ini $O2DPG_ROOT/MC/config/PWGHF/ini/GeneratorHF_decay.ini 

# run workflow
# allow increased timeframe parallelism with --cpu-limit 32 
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod --cpu-limit 32
MCRC=$?  # <--- we'll report back this code

# publish the current dir to ALIEN
#copy_ALIEN "*AO2D*"

# perform some analysis testing
#DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
#. ${DIR}/analysis_testing.sh


return ${MCRC} 2>/dev/null || exit ${MCRC}
