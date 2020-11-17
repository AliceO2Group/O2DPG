#!/usr/bin/env bash

# Embed jet-jet events in a pre-defined pT hard bin into HI events, both Pythia8
set -x

MODULES="PIPE ITS TPC EMCAL"
BKGEVENTS=5
SIGEVENTS=20
NWORKERS=8

# generate background

o2-sim -j ${NWORKERS} -n ${BKGEVENTS} -g pythia8hi -m ${MODULES} -o bkg \
       --configFile ${O2DPG_ROOT}/MC/config/common/ini/basic.ini \
       > logbkg 2>&1

# generate Pythia8 configuration

RNDSEED=0    # [default = 0] time-based random seed

# Define the pt hat bin arrays
pthatbin_loweredges=(0 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235)
pthatbin_higheredges=( 5 7 9 12 16 21 28 36 45 57 70 85 99 115 132 150 169 190 212 235 -1)

# Define environmental vars for pt binning
PTHATBIN=5 #$1 set it here or externally? Add protection out of array?

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

o2-sim -j ${NWORKERS} -n ${SIGEVENTS} -g pythia8 -m ${MODULES} -o sgn \
       --configKeyValues "GeneratorPythia8.config=pythia8_jets.cfg" \
       --embedIntoFile bkg_Kine.root \
       > logsgn 2>&1
