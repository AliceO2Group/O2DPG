
#!/bin/bash

########################################################################
# A very basic test to test a custom generator implementation of PWGDQ #
########################################################################

[[ -z ${O2_ROOT+x} ]] && { echo "O2_ROOT not loaded." ; exit 1 ; }
[[ -z ${O2DPG_ROOT+x} ]] && { echo "O2DPG_ROOT not loaded." ; exit 1 ; }


# run the workflow up to signal simulation (included)
# so far that is what we need for the subsequent test on the kinematics file
NSIGEVENTS=1 NBKGEVENTS=1 NTIMEFRAMES=1 TARGETTASK=sgnsim ${O2DPG_ROOT}/MC/run/PWGHF/run_OmegaCInjected.sh > sim_workflow.log 2>&1

# quit aleady if this didn't work
[ "$?" != "0" ] && { cat sim_workflow.log ; exit 1 ; }

# now, do some checks, for now only on kinematics
root -l -b -q ${O2DPG_ROOT}/test/PWGHF/checkKine.C'("tf1/sgn_1_Kine.root", 4332, {3334, 211})' > checkKine.log 2>&1
[ "$?" != "0" ] && { cat checkKine.log ; exit 1 ; }

# Other potential tests...


exit 0