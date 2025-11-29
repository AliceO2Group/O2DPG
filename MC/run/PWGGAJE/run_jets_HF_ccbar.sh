#!/usr/bin/env bash

# Generate jet-jet events with ccbar HF injected, Pythia8 in a pre-defined pt hard bin and weighted.
# Execute: ./run_jets_HF_ccbar.sh

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1



# ----------- START ACTUAL JOB  -----------------------------

RNDSEED=${RNDSEED:-0}   # [default = 0] time-based random seed

NSIGEVENTS=${NSIGEVENTS:-5}
NTIMEFRAMES=${NTIMEFRAMES:-1}
NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC" #"PIPE ITS TPC EMCAL"
CONFIG_ENERGY=${CONFIG_ENERGY:-13600.0}
SIMENGINE=${SIMENGINE:-TGeant4}
[[ ${SPLITID} != "" ]] && SEED="-seed ${SPLITID}" || SEED=""

#ccbar filter and bias2SelectionPow and PtHat settings are in the ini file given below
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM ${CONFIG_ENERGY} -col pp -gen external -proc "jets"                 \
                                            -tf ${NTIMEFRAMES} -ns ${NSIGEVENTS} -e ${SIMENGINE}                    \
                                            -j ${NWORKERS}                                 \
                                            -interactionRate 500000 -confKey "Diamond.width[2]=6." ${SEED}          \
                                            -ini $O2DPG_ROOT/MC/config/PWGGAJE/ini/GeneratorHFJETrigger_ccbar.ini


# run workflow
# allow increased timeframe parallelism with --cpu-limit 32
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod --cpu-limit 32