#!/usr/bin/env bash

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh 

RNDSEED=${RNDSEED:-0}
NSIGEVENTS=${NSIGEVENTS:-1}
NBKGEVENTS=${NBKGEVENTS:-1}
NWORKERS=${NWORKERS:-8}
NTIMEFRAMES=${NTIMEFRAMES:-1}

#generate random number
RNDSIG=$((1 + $RANDOM % 100))

if [[ $RNDSIG -ge 0 && $RNDSIG -lt 10 ]];
then
        CONFIGNAME="GeneratorHFcc_lowMassEE.ini"
elif [[ $RNDSIG -ge 10 && $RNDSIG -lt 20 ]];
then
        CONFIGNAME="GeneratorHFbb_lowMassEE.ini"
elif [[ $RNDSIG -ge 20 && $RNDSIG -le 100 ]];
then
        CONFIGNAME="GeneratorHFbtoc_lowMassEE.ini"
fi


${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 900 -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -e TGeant4 -mod "--skipModules ZDC" \
	-trigger "external" -ini $O2DPG_ROOT/MC/config/PWGDQ/ini/$CONFIGNAME  \
	-genBkg pythia8 -procBkg inel -colBkg pp --embedding -nb ${NBKGEVENTS} 

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
