#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="A:ITS/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

OUTTYPE=""
if [[ -z $USECLUSTERS ]]; then
  PROXY_OUTSPEC="downstreamA:ITS/DIGITS/0;downstreamB:ITS/DIGITSROF/0"
  OUTTYPE=" --no-clusters --digits "
else
  PROXY_OUTSPEC="downstreamA:ITS/COMPCLUSTERS/0;downstreamB:ITS/PATTERNS/0;downstreamC:ITS/CLUSTERSROF/0"
fi

[[ -z $NITSDECTHREADS ]] && NITSDECTHREADS=4
[[ -z $NITSDECTPIPELINES ]] && NITSDECTPIPELINES=6
  
WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1\"" "" 0
add_W o2-itsmft-stf-decoder-workflow "${OUTTYPE} --nthreads ${NITSDECTHREADS} --pipeline its-stf-decoder:${NITSDECTPIPELINES} --ignore-noise-map"
add_W o2-dpl-output-proxy "--dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name its-noise-input-proxy --channel-config \"name=its-noise-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=1\"" "" 0
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
