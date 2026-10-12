#!/usr/bin/env bash

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ----------- SETUP LOCAL CCDB CACHE --------------------------
export ALICEO2_CCDB_LOCALCACHE=$PWD/.ccdb



RNDSEED=${RNDSEED:-0}
NSIGEVENTS=${NSIGEVENTS:-1}
NBKGEVENTS=${NBKGEVENTS:-1}
NWORKERS=${NWORKERS:-8}
NTIMEFRAMES=${NTIMEFRAMES:-1}

#generate random number
RNDSIG=$(($RANDOM % 100))
echo $RNDSIG

if [[ $RNDSIG -ge 0 && $RNDSIG -lt 20 ]];
then
        CONFIGNAME="GeneratorHF_ccbarToDielectrons.ini"
elif [[ $RNDSIG -ge 20 && $RNDSIG -lt 40 ]];
then
        CONFIGNAME="GeneratorHF_bbbarToDielectrons.ini"
elif [[ $RNDSIG -ge 40 && $RNDSIG -lt 100 ]];
then
        CONFIGNAME="GeneratorHF_bbbarToDDbarToDielectrons.ini"
fi




${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 13600 -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -e TGeant4 \
     -trigger "external" -ini $O2DPG_ROOT/MC/config/PWGEM/ini/$CONFIGNAME  \
    -genBkg pythia8 -procBkg cdiff -colBkg pp --embedding -nb ${NBKGEVENTS} \
    -confKeyBkg "Diamond.width[2]=6" -interactionRate 500000 

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod  -jmax 1
