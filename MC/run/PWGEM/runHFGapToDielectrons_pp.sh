#!/usr/bin/env bash

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ----------- SETUP LOCAL CCDB CACHE --------------------------
export ALICEO2_CCDB_LOCALCACHE=$PWD/.ccdb



RNDSEED=${RNDSEED:-0}
NSIGEVENTS=${NSIGEVENTS:-1}
NWORKERS=${NWORKERS:-8}
NTIMEFRAMES=${NTIMEFRAMES:-1}
INTRATE=${INTRATE:-500000}
GAPRATIO=${GAPRATIO:-3} 
[[ ${SPLITID} != "" ]] && SEED="-seed ${SPLITID}" || SEED=""

#generate random number
RNDSIG=$(($RANDOM % 100))
echo $RNDSIG

if [[ $RNDSIG -ge 0 && $RNDSIG -lt 20 ]];
then
        CONFIGNAME="GeneratorHFGapTriggered_Charm_Gap$GAPRATIO.ini"
elif [[ $RNDSIG -ge 20 && $RNDSIG -lt 40 ]];
then
        CONFIGNAME="GeneratorHFGapTriggered_BeautyForcedDecay_Gap$GAPRATIO.ini"
elif [[ $RNDSIG -ge 40 && $RNDSIG -lt 100 ]];
then
        CONFIGNAME="GeneratorHFGapTriggered_BeautyNoForcedDecay_Gap$GAPRATIO.ini"
fi




${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 13600 -col pp -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -e TGeant4 \
     ${SEED} \
     -ini $O2DPG_ROOT/MC/config/PWGEM/ini/$CONFIGNAME  \
     -confKeyBkg "Diamond.width[2]=6" -interactionRate ${INTRATE} 

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod --cpu-limit 32
