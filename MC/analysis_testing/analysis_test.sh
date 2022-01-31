#!/usr/bin/bash

# This script performs an analysis task (given as first argument)
# in a directory (produced) where a merged AO2D.root was produced
# and individual timeframe AODs are still located in tf1...n folders.
# The analysis is performed on the merged AOD as well as the original timeframe ones.
# The tasks are executed using the graph pipeline mechanism.

# Optionally, one may connect the analysis graph workflows to the simulation workflow.
# (using the "needs" variable and doing a "merge" operation with the original workflow)

# to be eventually given externally
testanalysis=$1 # Efficiency, EventTrackQA, MCHistograms, Validation, PIDTOF, PIDTPC, WeakDecayTutorial

# find out number of timeframes
NTF=$(find ./ -name "tf*" -type d | wc | awk '//{print $1}')
#

# run the individual AOD part
# $O2DPG_ROOT/MC/bin/o2_dpg_workflow_runner.py -f workflow_ana.json -tt ${testanalysis}_.*$ --rerun-from ${testanalysis}_.*$
# RC1=$?
# echo "EXIT 1: $RC1"

# run on the merged part
wf_name="workflow_test_analysis.json"
# remove if present...
rm ${wf_name} 2>/dev/null
# ...and recreate
$O2DPG_ROOT/MC/analysis_testing/o2dpg_analysis_test_workflow.py -o ${wf_name}
# run requested analysis
$O2DPG_ROOT/MC/bin/o2_dpg_workflow_runner.py -f ${wf_name} -tt Analysis_${testanalysis}$ --rerun-from Analysis_${testanalysis}$
RC2=$?
echo "EXIT 2: $RC2"

RC=0
let RC=RC+RC1
let RC=RC+RC2

exit ${RC}
