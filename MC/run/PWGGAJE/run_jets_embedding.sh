#!/usr/bin/env bash

# Embed jet-jet events in a pre-defined pT hard bin into HI events, both Pythia8
# Execute: ./run_jets_embedding.sh 
# Set at least before running PTHATBIN with 1 to 21

#set -x

# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh

# ----------- START ACTUAL JOB  ----------------------------- 

RNDSEED=${RNDSEED:-0}   # [default = 0] time-based random seed
NSIGEVENTS=${NSIGEVENTS:-2}
NBKGEVENTS=${NBKGEVENTS:-1}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
CONFIG_ENERGY=${CONFIG_ENERGY:-5020.0}
SIMENGINE=${SIMENGINE:-TGeant4}

# Define the pt hat bin arrays
pthatbin_loweredges=(0 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235)
pthatbin_higheredges=( 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235 -1)

# Recover environmental vars for pt binning
#PTHATBIN=${PTHATBIN:-1} 

if [ -z "$PTHATBIN" ]; then
    echo "Pt-hat bin (env. var. PTHATBIN) not set, abort."
    exit 1
fi

PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM ${CONFIG_ENERGY} -col pp -gen pythia8 -proc "jets" \
                                            -ptHatMin ${PTHATMIN} -ptHatMax ${PTHATMAX}            \
                                            -tf ${NTIMEFRAMES} -ns ${NSIGEVENTS} -e ${SIMENGINE}   \
                                            -nb ${NBKGEVENTS} --embedding                          \
                                            -j ${NWORKERS} -mod "--skipModules ZDC"

# run workflow
${O2_ROOT}/bin/o2-workflow-runner.py -f workflow.json

exit 0
