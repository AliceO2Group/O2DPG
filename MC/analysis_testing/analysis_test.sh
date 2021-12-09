#!/usr/bin/bash

# This script performs an analysis task (given as first argument)
# in a directory (produced) where a merged AO2D.root was produced
# and individual timeframe AODs are still located in tf1...n folders.
# The analysis is performed on the merged AOD as well as the original timeframe ones.
# The tasks are executed using the graph pipeline mechanism.

# Optionally, one may connect the analysis graph workflows to the simulation workflow.
# (using the "needs" variable and doing a "merge" operation with the original workflow)

# to be eventually given externally
testanalysis=$1 # o2-analysistutorial-mc-histograms o2-analysis-spectra-tof-tiny o2-analysis-spectra-tpc-tiny o2-analysis-correlations

# find out number of timeframes
NTF=$(find ./ -name "tf*" -type d | wc | awk '//{print $1}')
#

commonDPL="-b --run --driver-client-backend ws://"
annaCMD="RC=0; if [ -f AO2D.root ]; then timeout 600s ${testanalysis} ${commonDPL} --aod-file AO2D.root; RC=\$?; fi; [ -f AnalysisResults.root ] && mv AnalysisResults.root AnalysisResults_${testanalysis}.root; [ -f QAResult.root ] && mv QAResults.root QAResults_${testanalysis}.root; [ \${RC} -eq 0 ]"

rm workflow_ana.json
# this is to analyse the global (merged) AOD
${O2DPG_ROOT}/MC/bin/o2dpg-workflow-tools.py create workflow_ana --add-task ${testanalysis}
needs=""
for i in $(seq 1 ${NTF})
do
  needs="${needs} aodmerge_$i "
done

${O2DPG_ROOT}/MC/bin/o2dpg-workflow-tools.py modify workflow_ana ${testanalysis} --cmd "${annaCMD}" \
                                                                        --cpu 1 --labels ANALYSIS

# let's also add a task per timeframe (might expose different errors)
for i in $(seq 1 ${NTF})
do
  ${O2DPG_ROOT}/MC/bin/o2dpg-workflow-tools.py create workflow_ana --add-task ${testanalysis}_${i}
  needs="aod_${i}"
  ${O2DPG_ROOT}/MC/bin/o2dpg-workflow-tools.py modify workflow_ana ${testanalysis}_${i} --cmd "${annaCMD}" \
                                                                        --cpu 1 --labels ANALYSIS --cwd tf${i}
done

# run the individual AOD part
# $O2DPG_ROOT/MC/bin/o2_dpg_workflow_runner.py -f workflow_ana.json -tt ${testanalysis}_.*$ --rerun-from ${testanalysis}_.*$
# RC1=$?
# echo "EXIT 1: $RC1"

# run on the merged part
$O2DPG_ROOT/MC/bin/o2_dpg_workflow_runner.py -f workflow_ana.json -tt ${testanalysis}$ --rerun-from ${testanalysis}$
RC2=$?
echo "EXIT 2: $RC2"

RC=0
let RC=RC+RC1
let RC=RC+RC2

exit ${RC}
