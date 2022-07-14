#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

INPTYPE=""
if [[ -z $USECLUSTERS ]]; then
  PROXY_INSPEC="A:ITS/DIGITS/0;B:ITS/DIGITSROF/0;eos:***/INFORMATION"
else
  PROXY_INSPEC="A:ITS/COMPCLUSTERS/0;B:ITS/PATTERNS/0;C:ITS/CLUSTERSROF/0;eos:***/INFORMATION"
  INPTYPE=" --use-clusters "
fi

if [[ -z $NTHREADS ]] ; then NTHREADS=1; fi

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --proxy-name its-noise-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=its-noise-input-proxy,method=bind,type=pull,rateLogging=1,transport=zeromq\" | "
WORKFLOW+="o2-its-noise-calib-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --prob-threshold 1e-5 --nthreads ${NTHREADS} ${INPTYPE} | "
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
