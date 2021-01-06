#!/usr/bin/env bash

# Generate jet-jet events, PYTHIA8 in a given pt hard bin.
# Select the event depending min Pt and acceptance of decay photons.
# Execute: ./run_decaygammajets.sh 
# Set at least before running PTHATBIN with 1 to 6
# CONFIG_DETECTOR_ACCEPTANCE and CONFIG_DECAYGAMMA_PTMIN, see 
# $O2DPG_ROOT/MC/config/PWGGAJE/trigger/decay_gamma_jet.C

#set -x 

# ----------- LOAD UTILITY FUNCTIONS --------------------------
. ${O2_ROOT}/share/scripts/jobutils.sh

# ----------- START ACTUAL JOB  ----------------------------- 

RNDSEED=${RNDSEED:-0}   # [default = 0] time-based random seed

NSIGEVENTS=${NSIGEVENTS:-20}
NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC" #"PIPE ITS TPC EMCAL"
CONFIG_ENERGY=${CONFIG_ENERGY:-5020.0}
CONFIG_NUCLEUSA=${CONFIG_NUCLEUSA:-2212}
CONFIG_NUCLEUSB=${CONFIG_NUCLEUSB:-2212}

# Recover environmental vars for detector acceptance binning
# accessed inside prompt_gamma.C
export CONFIG_DECAYGAMMA_PTMIN=${CONFIG_DECAYGAMMA_PTMIN:-3.5}

if [ -z "$CONFIG_DECAYGAMMA_PTMIN" ]; then
    echo "Detector acceptance option (env. var. CONFIG_DECAYGAMMA_PTMIN) not set, abort."
    exit 1
fi

echo 'Decay photon minimum pT option ' $CONFIG_DECAYGAMMA_PTMIN "GeV/c" 

# Recover environmental vars for pt binning
PTHATBIN=${PTHATBIN:-1} 

if [ -z "$PTHATBIN" ]; then
    echo "Pt-hat bin (env. var. PTHATBIN) not set, abort."
    exit 1
fi

# Define the pt hat bin arrays and set bin depending threshold
if [ $CONFIG_DECAYGAMMA_PTMIN = "3.5" ]; then 
    pthatbin_loweredges=(5 7 9 12 16 21)
    pthatbin_higheredges=(7 9 12 16 21 -1)

    PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
    PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}
fi

if [ $CONFIG_DECAYGAMMA_PTMIN = "7" ]; then
    pthatbin_loweredges=(8 10 14 19 26 35 48 66)
    pthatbin_higheredges=(10 14 19 26 35 48 66 -1)

    PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
    PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}
fi

echo "Set Pt hard bin " $PTHATBIN ": [" $PTHATMIN " , "  $PTHATMAX "]"

# Recover environmental vars for detector acceptance binning
# accessed inside prompt_gamma.C
export CONFIG_DETECTOR_ACCEPTANCE=${CONFIG_DETECTOR_ACCEPTANCE:-1}

if [ -z "$CONFIG_DETECTOR_ACCEPTANCE" ]; then
    echo "Detector acceptance option (env. var. CONFIG_DETECTOR_ACCEPTANCE) not set, abort."
    exit 1
fi

echo 'Detector acceptance option ' $CONFIG_DETECTOR_ACCEPTANCE

# Generate PYTHIA8 gamma-jet configuration
${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
        --output=pythia8_jets.cfg \
        --seed=${RNDSEED}             \
        --idA=${CONFIG_NUCLEUSA}      \
        --idB=${CONFIG_NUCLEUSB}      \
        --eCM=${CONFIG_ENERGY}        \
        --process=jets                \
        --ptHatMin=${PTHATMIN}        \
        --ptHatMax=${PTHATMAX}

# Generate signal 
taskwrapper sgnsim.log o2-sim -j ${NWORKERS} -n ${NSIGEVENTS}         \
           -m ${MODULES}  -o sgn -g pythia8                           \
           -t external --configFile $O2DPG_ROOT/MC/config/PWGGAJE/ini/trigger_decay_gamma.ini
           
# We need to exit for the ALIEN JOB HANDLER!
exit 0
