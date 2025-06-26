#!/usr/bin/env bash

# Embed jet-jet events in a pre-defined pT hard bin and weighted
# into HI events, both Pythia8
# Execute: ./run_jets_embedding.sh
# Set at least before running PTHATBIN with 1 to 21

#set -x


# ----------- START ACTUAL JOB  -----------------------------

RNDSEED=${RNDSEED:-0}   # [default = 0] time-based random seed
NSIGEVENTS=${NSIGEVENTS:-2}
NBKGEVENTS=${NBKGEVENTS:-1}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC" #"PIPE ITS TPC EMCAL"
CONFIG_ENERGY=${CONFIG_ENERGY:-5020.0}
SIMENGINE=${SIMENGINE:-TGeant4}
WEIGHTPOW=${WEIGHTPOW:-6.0}

# Default for weighted productions
PTHATMIN=${PTHATMIN:-5.0}
PTHATMAX=${PTHATMAX:-300.0}

# Define the pt hat bin arrays
pthatbin_loweredges=(0 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235)
pthatbin_higheredges=( 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235 -1)

# Recover environmental vars for pt binning
#PTHATBIN=${PTHATBIN:-1}

if [ -z "$PTHATBIN" ]; then
    echo "Open Pt-hat range set"
else
  PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
  PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}
fi

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM ${CONFIG_ENERGY} \
                                           -nb ${NBKGEVENTS} --embedding                          \
                                           -colBkg PbPb -genBkg pythia8 -procBkg "heavy_ion"      \
                                           -col    pp   -gen    pythia8 -proc    "jets"           \
                                           -ptHatMin ${PTHATMIN} -ptHatMax ${PTHATMAX}            \
                                           -tf ${NTIMEFRAMES} -ns ${NSIGEVENTS} -e ${SIMENGINE}   \
                                           -j ${NWORKERS} -mod "--skipModules ZDC"                \
                                           -weightPow ${WEIGHTPOW} -interactionRate 500000
# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
