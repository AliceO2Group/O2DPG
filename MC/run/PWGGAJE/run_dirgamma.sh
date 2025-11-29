#!/usr/bin/env bash

# Generate gamma-jet events, PYTHIA8 in a given pt hard bin and weighted.
# Select the event depending detector acceptance and/or outgoing parton flavour.
# Execute: ./run_dirgamma.sh
# Set at least before running PTHATBIN with 1 to 6
# and PARTICLE_ACCEPTANCE, see
# $O2DPG_ROOT/MC/config/PWGGAJE/trigger/prompt_gamma.C

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
pthatbin_loweredges=(5 11 21 36 57 84)
pthatbin_higheredges=(11 21 36 57 84 -1)

# Recover environmental vars for pt binning
#PTHATBIN=${PTHATBIN:-1}

if [ -z "$PTHATBIN" ]; then
    echo "Open Pt-hat range set"
else
  PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
  PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}
fi

# Recover environmental vars for detector acceptance binning
# accessed inside prompt_gamma.C
export PARTICLE_ACCEPTANCE=${PARTICLE_ACCEPTANCE:-1}

if [ -z "$PARTICLE_ACCEPTANCE" ]; then
    echo "Detector acceptance option (env. var. PARTICLE_ACCEPTANCE) not set, abort."
    exit 1
fi

echo 'Detector acceptance option ' $PARTICLE_ACCEPTANCE

# Recover environmental vars for outgoing parton flavour
# accessed inside prompt_gamma.C
export CONFIG_OUTPARTON_PDG=${CONFIG_OUTPARTON_PDG:-0}

echo 'Parton PDG option ' $CONFIG_OUTPARTON_PDG

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM ${CONFIG_ENERGY} -col pp -gen pythia8 -proc "dirgamma" \
                                            -ptHatMin ${PTHATMIN} -ptHatMax ${PTHATMAX}                \
                                            -tf ${NTIMEFRAMES} -ns ${NSIGEVENTS} -e ${SIMENGINE}       \
                                            -j ${NWORKERS}                    \
                                            -weightPow ${WEIGHTPOW}                                    \
                                            -trigger "external" -ini "\$O2DPG_ROOT/MC/config/PWGGAJE/ini/trigger_prompt_gamma.ini"

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
