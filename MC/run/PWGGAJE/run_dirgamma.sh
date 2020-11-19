#!/usr/bin/env bash

# Generate gamma-jet events, Pythia8 in a given pt hard bin.
# run_dirgamma.sh n_pthatbin

set -x

SIGEVENTS=10
NWORKERS=2
MODULES=
RNDSEED=0    # [default = 0] time-based random seed

# generate Pythia8 gamma-jet configuration

# Define the pt hat bin arrays
pthatbin_loweredges=(5 11 21 36 57 84)
pthatbin_higheredges=(11 21 36 57 84 -1)

# Define environmental vars for pt binning
PTHATBIN=$1 #set it here or externally? Add protection out of array?

PTHATMIN=${pthatbin_loweredges[$PTHATBIN]}
PTHATMAX=${pthatbin_higheredges[$PTHATBIN]}

${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
	     --output=pythia8_dirgamma.cfg \
	     --seed=${RNDSEED} \
	     --idA=2212 \
	     --idB=2212 \
	     --eCM=13000. \
	     --process=dirgamma \
	     --ptHatMin=${PTHATMIN} \
	     --ptHatMax=${PTHATMAX}

# embed signal into background

o2-sim -j ${NWORKERS} -n ${SIGEVENTS} -g pythia8 -m ${MODULES} \
       --configKeyValues "GeneratorPythia8.config=pythia8_dirgamma.cfg" \
       > log 2>&1
