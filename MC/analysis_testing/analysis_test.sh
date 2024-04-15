#!/usr/bin/env bash

# This script performs an analysis task (given as first argument)
# in a directory (produced) where a merged AO2D.root was produced
# and individual timeframe AODs are still located in tf1...n folders.
# The analysis is performed on the merged AOD as well as the original timeframe ones.
# The tasks are executed using the graph pipeline mechanism.

# Optionally, one may connect the analysis graph workflows to the simulation workflow.
# (using the "needs" variable and doing a "merge" operation with the original workflow)

# to be eventually given externally
 # Efficiency, EventTrackQA, MCHistograms, Validation, PIDTOF, PIDTPC, WeakDecayTutorial

# find out number of timeframes
NTF=$(find ./ -name "tf*" -type d | wc | awk '//{print $1}')
#

# run the individual AOD part
# $O2DPG_ROOT/MC/bin/o2_dpg_workflow_runner.py -f workflow_ana.json -tt ${testanalysis}_.*$ --rerun-from ${testanalysis}_.*$
# RC1=$?
# echo "EXIT 1: $RC1"

include_disabled=
testanalysis=
aod=
add_common_args=

if [[ "${#}" == "1" ]] ; then
    # make it backward-compatible
    aod=$(find . -maxdepth 1 -type f -name "AO2D.root")
    testanalysis=${1}
else
    while [[ $# -gt 0 ]]; do
        key="$1"

        case $key in
            --include-disabled)
                include_disabled=1
                shift
                ;;
            --aod)
                aod=${2}
                shift
                shift
                ;;
            --analysis)
                testanalysis=${2}
                shift
                shift
                ;;
            *)
                echo "ERROR: Unknown argument ${1}"
                exit 1
                ;;
        esac
    done
fi

# basic checks
[[ "${testanalysis}" == "" ]] && { echo "ERROR: No analysis specified to be run" ; exit 1 ; }
[[ "${aod}" == "" ]] && { echo "ERROR: No AOD found to be analysed" ; exit 1 ; }

# check if enabled
enabled=$($O2DPG_ROOT/MC/analysis_testing/o2dpg_analysis_test_config.py check -t ${testanalysis} --status)
[[ "${enabled}" == "UNKNOWN" ]] && { echo "ERROR: Analysis ${testanalysis} unknown" ; exit 1 ; }
[[ "${enabled}" == "DISABLED" && "${include_disabled}" == "" ]] && { echo "WARNING: Analysis ${testanalysis} is disabled" ; exit 0 ; }

mkdir Analysis 2>/dev/null
include_disabled=${include_disabled:+--include-disabled}
workflow_path="Analysis/workflow_analysis_test_${testanalysis}.json"
rm ${workflow_path} 2>/dev/null
$O2DPG_ROOT/MC/analysis_testing/o2dpg_analysis_test_workflow.py --is-mc --split-analyses -f ${aod} -o ${workflow_path} --only-analyses ${testanalysis} ${include_disabled}
[[ ! -f "${workflow_path}" ]] && { echo "Could not construct workflow for analysis ${testanalysis}" ; exit 1 ; }
$O2DPG_ROOT/MC/bin/o2_dpg_workflow_runner.py -f ${workflow_path} -tt Analysis_${testanalysis}$ --rerun-from Analysis_${testanalysis}$

RC=$?
echo "EXIT with: $RC"
exit ${RC}
