#!/usr/bin/env bash

### This script run the simulation of Pythia8 pp INEL events with a multiplicity trigger.
### The details of the configuration are defined in the INI config files (--configFile).

set -x

MODULES="PIPE ITS TPC"
EVENTS=20
NWORKERS=8

o2-sim -j ${NWORKERS} -n ${EVENTS} -g pythia8 -m ${MODULES} -o sim \
       --configFile ${O2DPG_ROOT}/MC/config/examples/ini/trigger_multiplicity.ini \
       > logsim 2>&1
