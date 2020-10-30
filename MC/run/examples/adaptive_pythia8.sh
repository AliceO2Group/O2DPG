#!/usr/bin/env bash

### This script run the simulation of signal embedding into a heavy-ion background.
### First the background is generated with Pythia8/Angantyr model and basic settings.
### The signal generation is configured to be embedded into the background (--embedIntoFile).
### The signal event generator is an external event generator which implements adaptive
### features where the number of events to be injected depends on the characteristics
### of the background.
### The details are defined in the INI config files (--configFile).

set -x

MODULES="PIPE ITS TPC"
BKGEVENTS=5
SIGEVENTS=20
NWORKERS=8

# generate background

o2-sim -j ${NWORKERS} -n ${BKGEVENTS} -g pythia8hi -m ${MODULES} -o bkg \
       --configFile ${O2DPG_ROOT}/MC/config/common/ini/basic.ini \
       > logbkg 2>&1

# embed signal into background

o2-sim -j ${NWORKERS} -n ${SIGEVENTS} -g external -m ${MODULES} -o sgn \
       --configFile ${O2DPG_ROOT}/MC/config/examples/ini/adaptive_pythia8.ini \
       --embedIntoFile bkg_Kine.root \
       > logsgn 2>&1
