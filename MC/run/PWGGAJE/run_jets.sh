#!/usr/bin/env bash

# Generate jet-jet events, Pythia8 in a pre-defined pt hard bin.
# run_jets.sh n_pthatbin

set -x

SIGEVENTS=10
NWORKERS=2
MODULES=
RNDSEED=0    # [default = 0] time-based random seed

# generate Pythia8 jet-jet configuration

# Define the pt hat bin arrays
pthatbin_loweredges=(0 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235)
pthatbin_higheredges=( 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235 -1)

# Define environmental vars for pt binning
PTHATBIN=$1 #set it here or externally? Add protection out of array?

PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}

${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
	     --output=pythia8_jets.cfg \
	     --seed=${RNDSEED} \
	     --idA=2212 \
	     --idB=2212 \
	     --eCM=5020. \
	     --process=jets \
	     --ptHatMin=${PTHATMIN} \
	     --ptHatMax=${PTHATMAX}

# embed signal into background

o2-sim -j ${NWORKERS} -n ${SIGEVENTS} -g pythia8 -m ${MODULES} \
       --configKeyValues "GeneratorPythia8.config=pythia8_jets.cfg" \
       > log 2>&1
