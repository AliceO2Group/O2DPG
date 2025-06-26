#!/usr/bin/env bash

# Generate jet-jet events, Pythia8 in a pre-defined pt hard bin and weighted.
# Execute: ./run_jets.sh

#set -x


# ----------- START ACTUAL JOB  -----------------------------

RNDSEED=${RNDSEED:-0}   # [default = 0] time-based random seed

NSIGEVENTS=${NSIGEVENTS:-20}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC" #"PIPE ITS TPC EMCAL"
CONFIG_ENERGY=${CONFIG_ENERGY:-13000.0}
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
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM ${CONFIG_ENERGY} -col pp -gen pythia8 -proc "jets" \
                                            -ptHatMin ${PTHATMIN} -ptHatMax ${PTHATMAX}            \
                                            -tf ${NTIMEFRAMES} -ns ${NSIGEVENTS} -e ${SIMENGINE}   \
                                            -j ${NWORKERS} -mod "--skipModules ZDC"                \
                                            -weightPow ${WEIGHTPOW} -interactionRate 500000

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
