#!/usr/bin/env bash

# make sure O2DPG + O2 is loaded
#[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
#[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ----------- SETUP LOCAL CCDB CACHE --------------------------
#export ALICEO2_CCDB_LOCALCACHE=$PWD/.ccdb



#NSIGEVENTS=${NSIGEVENTS:-10}
#NWORKERS=${NWORKERS:-8}
#NTIMEFRAMES=${NTIMEFRAMES:-1}
#INTRATE=${INTRATE:-500000}

#CONFIGNAME="Generator_GapTriggered_LFmumu_np1_gap5.ini"

#${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 13600 -col pp -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -e TGeant4 \
     #-ini $O2DPG_ROOT/MC/config/PWGEM/ini/$CONFIGNAME  \
     #-confKeyBkg "Diamond.width[2]=6" -interactionRate ${INTRATE} 

# run workflow
#${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod --cpu-limit 32

#!/usr/bin/env bash

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ----------- SETUP LOCAL CCDB CACHE --------------------------
export ALICEO2_CCDB_LOCALCACHE=$PWD/.ccdb



NSIGEVENTS=${NSIGEVENTS:-10}
NWORKERS=${NWORKERS:-8}
NTIMEFRAMES=${NTIMEFRAMES:-1}
INTRATE=${INTRATE:-500000}

CONFIGNAME="Generator_GapTriggered_LFmumu.ini"

${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 13600 -col pp -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -e TGeant4 \
     -ini $O2DPG_ROOT/MC/config/PWGEM/ini/$CONFIGNAME  \
     -confKeyBkg "Diamond.width[2]=6" -interactionRate ${INTRATE} 

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod --cpu-limit 32
