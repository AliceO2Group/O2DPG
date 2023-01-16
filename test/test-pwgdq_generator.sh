#!/bin/bash

########################################################################
# A very basic test to test a custom generator implementation of PWGDQ #
########################################################################

[[ -z ${O2_ROOT+x} ]] && { echo "O2_ROOT not loaded." ; exit 1 ; }
[[ -z ${O2PHYSICS_ROOT+x} ]] && { echo "O2PHYSICS_ROOT not loaded." ; exit 1 ; }
[[ -z ${EVTGEN_ROOT+x} ]] && { echo "EVTGEN_ROOT not loaded." ; exit 1 ; }
[[ -z ${AEGIS_ROOT+x} ]] && { echo "EVTGEN_ROOT not loaded." ; exit 1 ; }

# run the workflow up to signal simulation (included)
# so far that is what we need for the subsequent test on the kinematics file
NSIGEVENTS=20 NBKGEVENTS=20 NTIMEFRAMES=2 TARGETTASK=sgnsim ${O2DPG_ROOT}/MC/run/PWGDQ/runPromptCharmonia_fwdy_pp.sh > sim_workflow.log 2>&1

# quit aleady if this didn't work
[ "$?" != "0" ] && { cat sim_workflow.log ; exit 1 ; }

# now, do some checks, for now only on kinematics
root -l -b -q ${O2DPG_ROOT}/test/PWGDQ/checkKine.C\(\"tf1/sgn_1_Kine.root\",443,13\) > checkKine.log 2>&1
[ "$?" != "0" ] && { cat checkKine.log ; exit 1 ; }

# Other potential tests...


exit 0
