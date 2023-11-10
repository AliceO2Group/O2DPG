#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="A:MFT/RAWDATA;B:FLP/DISTSUBTIMEFRAME/0"
PROXY_OUTSPEC="downstream:MFT/DIGITS/0;downstream:MFT/DIGITSROF/0"

WORKFLOW="o2-dpl-raw-proxy ${ARGS_ALL} --dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=0\" | "
WORKFLOW+="o2-itsmft-stf-decoder-workflow ${ARGS_ALL} --configKeyValues \"$ARGS_ALL_CONFIG\" --runmft --digits --no-clusters --no-cluster-patterns --ignore-noise-map --nthreads 5 | "
WORKFLOW+="o2-dpl-output-proxy ${ARGS_ALL} --dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name mft-noise-input-proxy --channel-config \"name=mft-noise-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0\" | "
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
