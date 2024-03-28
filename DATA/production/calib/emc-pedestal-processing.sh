#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="A:EMC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

PROXY_OUTSPEC="downstream:EMC/PEDDATA/0"

[[ -z $NEMCPROCPIPELINES ]] && NEMCPROCPIPELINES=30

WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1\"" "" 0
add_W o2-calibration-emcal-pedestal-processor-workflow "--pipeline PedestalProcessor:${NEMCPROCPIPELINES}"
add_W o2-dpl-output-proxy "--dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name emc-pedestal-input-proxy --channel-config \"name=emc-pedestal-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=1\"" "" 0
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi