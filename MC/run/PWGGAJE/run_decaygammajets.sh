#!/usr/bin/env bash

# Generate jet-jet events, PYTHIA8 in a given pt hard bin.
# Select the event depending min Pt and acceptance of decay photons.
# Execute: ./run_decaygammajets.sh 
# Set at least before running PTHATBIN with 1 to 6
# PARTICLE_ACCEPTANCE and CONFIG_DECAYGAMMA_PTMIN, see 
# $O2DPG_ROOT/MC/config/PWGGAJE/trigger/decay_gamma_jet.C

#set -x 

# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh

# ----------- START ACTUAL JOB  ----------------------------- 

RNDSEED=${RNDSEED:-0}   # [default = 0] time-based random seed

NSIGEVENTS=${NSIGEVENTS:-20}
NTIMEFRAMES=${NTIMEFRAMES:-5}
NWORKERS=${NWORKERS:-8}
CONFIG_ENERGY=${CONFIG_ENERGY:-13000.0}
SIMENGINE=${SIMENGINE:-TGeant4}

# Recover environmental vars for detector acceptance binning
# accessed inside prompt_gamma.C
export PTTRIGMIN=${PTTRIGMIN:-3.5}

if [ -z "$PTTRIGMIN" ]; then
    echo "Detector acceptance option (env. var. CONFIG_DECAYGAMMA_PTMIN) not set, abort."
    exit 1
fi

echo 'Decay photon minimum pT option ' $PTTRIGMIN "GeV/c"

# Recover environmental vars for pt binning
#PTHATBIN=${PTHATBIN:-1}

if [ -z "$PTHATBIN" ]; then
    echo "Pt-hat bin (env. var. PTHATBIN) not set, abort."
    exit 1
fi

# Define the pt hat bin arrays and set bin depending threshold
if [ $PTTRIGMIN = "3.5" ]; then
    pthatbin_loweredges=(5 7 9 12 16 21)
    pthatbin_higheredges=(7 9 12 16 21 -1)

    PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
    PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}
fi

if [ $PTTRIGMIN = "7" ]; then
    pthatbin_loweredges=(8 10 14 19 26 35 48 66)
    pthatbin_higheredges=(10 14 19 26 35 48 66 -1)

    PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
    PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}
fi

echo "Set Pt hard bin " $PTHATBIN ": [" $PTHATMIN " , "  $PTHATMAX "]"

# Recover environmental vars for detector acceptance binning
# accessed inside prompt_gamma.C
export PARTICLE_ACCEPTANCE=${PARTICLE_ACCEPTANCE:-1}

if [ -z "$PARTICLE_ACCEPTANCE" ]; then
    echo "Detector acceptance option (env. var. PARTICLE_ACCEPTANCE) not set, abort."
    exit 1
fi

echo 'Detector acceptance option ' $PARTICLE_ACCEPTANCE

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM ${CONFIG_ENERGY} -col pp -gen pythia8 -proc "jets" \
                                            -ptHatMin ${PTHATMIN} -ptHatMax ${PTHATMAX}            \
                                            -tf ${NTIMEFRAMES} -ns ${NSIGEVENTS} -e ${SIMENGINE}   \
                                            -j ${NWORKERS} -mod "--skipModules ZDC"                \
                                            -trigger "external" -ini "\$O2DPG_ROOT/MC/config/PWGGAJE/ini/trigger_decay_gamma.ini"

# run workflow
${O2_ROOT}/bin/o2-workflow-runner.py -f workflow.json

exit 0
