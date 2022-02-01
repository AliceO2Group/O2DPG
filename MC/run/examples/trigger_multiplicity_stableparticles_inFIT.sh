#!/usr/bin/env bash

### This script run the simulation of Pythia8 Pb--Pb events with a multiplicity trigger in the FIT acceptance
### The details of the configuration are defined in the INI config files (--configFile).

set -x

MODULES="PIPE ITS TPC"
EVENTS=10
NWORKERS=8

o2-sim -j ${NWORKERS} -n ${EVENTS} -g pythia8 -t external -m ${MODULES} -o sim \
       --configFile ${O2DPG_ROOT}/MC/config/examples/ini/trigger_multiplicity_stableparticles_inFIT.ini \
       > logsim 2>&1
