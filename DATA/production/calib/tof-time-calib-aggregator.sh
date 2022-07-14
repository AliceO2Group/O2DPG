#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh
ARGS_ALL_CONFIG="keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null;$ALL_EXTRA_CONFIG"

PROXY_INSPEC="calclus:TOF/INFOCALCLUS/0;cosmics:TOF/INFOCOSMICS/0;trkcos:TOF/INFOTRACKCOS/0;trksiz:TOF/INFOTRACKSIZE/0;eos:***/INFORMATION"

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --proxy-name tof-time-calib-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=tof-time-calib-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq\" | "
WORKFLOW+="o2-calibration-tof-calib-workflow --cosmics --do-channel-offset --min-entries 1000 $ARGS_ALL | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://ccdb-test.cern.ch:8080\" | "
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
