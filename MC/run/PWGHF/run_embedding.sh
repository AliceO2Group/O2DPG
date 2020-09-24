#!/usr/bin/env bash

set -x

MODULES="PIPE ITS TPC"
BKGEVENTS=5
SIGEVENTS=20
NWORKERS=8

# generate background

o2-sim -j ${NWORKERS} -n ${BKGEVENTS} -g pythia8hi -m ${MODULES} -o bkg \
       --configFile ${O2DPG_ROOT}/MC/config/common/ini/basic.ini \
       > logbkg 2>&1

# generate Pythia8 configuration

RNDSEED=0    # [default = 0] time-based random seed
PTHATMIN=0.  # [default = 0]
PTHATMAX=-1. # [default = -1]

${O2DPG_ROOT}/MC/config/common/pythia8/utils/mkpy8cfg.py \
	     --output=pythia8.cfg \
	     --seed=${RNDSEED} \
	     --idA=2212 \
	     --idB=2212 \
	     --eCM=13000. \
	     --process=ccbar \
	     --ptHatMin=${PTHATMIN} \
	     --ptHatMax=${PTHATMAX}

# embed signal into background

o2-sim -j ${NWORKERS} -n ${SIGEVENTS} -g extgen -m ${MODULES} -o sgn \
       --configFile ${O2DPG_ROOT}/MC/config/PWGHF/ini/GeneratorHF.ini \
       --configKeyValues "GeneratorPythia8.config=pythia8.cfg" \
       --embedIntoFile bkg_Kine.root \
       > logsgn 2>&1
