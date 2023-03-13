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
WORKFLOW+="o2-its-noise-calib-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --prob-threshold 1e-6 --cut-ib 1e-2 --nthreads ${NTHREADSACC} --processing-mode 1 --pipeline its-noise-calibrator:${NITSACCPIPELINES} ${INPTYPE} | "
WORKFLOW+="o2-its-noise-calib-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --prob-threshold 1e-6 --cut-ib 1e-2 --nthreads ${NTHREADSNORM} --processing-mode 2 ${INPTYPE} | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://o2-ccdb.internal\" --sspec-min 0 --sspec-max 0 | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://alio2-cr1-flp199.cern.ch:8083\" --sspec-min 1 --sspec-max 1 --name-extention dcs | "
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
