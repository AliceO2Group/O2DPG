#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="A:ITS/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
PROXY_OUTSPEC="downstreamA:ITS/COMPCLUSTERS/0;downstreamB:ITS/PATTERNS/0;downstreamC:ITS/CLUSTERSROF/0"

WORKFLOW="o2-dpl-raw-proxy ${ARGS_ALL} --dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=0\" | "
WORKFLOW+="o2-itsmft-stf-decoder-workflow ${ARGS_ALL} --configKeyValues \"$ARGS_ALL_CONFIG\" --nthreads 4 | "
WORKFLOW+="o2-dpl-output-proxy ${ARGS_ALL} --dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name its-noise-input-proxy --channel-config \"name=its-noise-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0\" | "
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE"
  eval $WORKFLOW
fi
