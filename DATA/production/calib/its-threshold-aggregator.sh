#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="tunestring:ITS/TSTR;runtype:ITS/RUNT;fittype:ITS/FITT;scantype:ITS/SCANT;eos:***/INFORMATION"

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --proxy-name its-thr-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=its-thr-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq\" | "
WORKFLOW+="o2-its-threshold-aggregator-workflow -b $ARGS_ALL | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://alio2-cr1-flp199.cern.ch:8083\" | "
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE"
  eval $WORKFLOW
fi
