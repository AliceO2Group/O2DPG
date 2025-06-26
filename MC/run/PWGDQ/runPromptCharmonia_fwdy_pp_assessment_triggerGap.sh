#!/usr/bin/env bash

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1



RNDSEED=${RNDSEED:-0}
NSIGEVENTS=${NSIGEVENTS:-1}
NBKGEVENTS=${NBKGEVENTS:-1}
NWORKERS=${NWORKERS:-8}
NTIMEFRAMES=${NTIMEFRAMES:-1}

${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 13600 -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -e TGeant4 -mod "--skipModules ZDC" \
        -ini $O2DPG_ROOT/MC/config/PWGDQ/ini/Generator_InjectedPromptCharmoniaFwdy_TriggerGap.ini --mft-assessment-full --fwdmatching-assessment-full -interactionRate 500000 

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
