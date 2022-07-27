#!/usr/bin/env bash

# shellcheck disable=SC1091
source common/setenv.sh

# shellcheck disable=SC1091
source common/getCommonArgs.sh

PROXY_INSPEC_EOS="eos:***/INFORMATION"
PROXY_INSPEC_DD="dd:FLP/DISTSUBTIMEFRAME/0"
PROXY_INSPEC="digits:FT0/DIGITSBC/0;channels:FT0/DIGITSCH/0;${PROXY_INSPEC_DD};${PROXY_INSPEC_EOS}"
PROXY_OUTSPEC="calib:FT0/CALIB_INFO/0"
PROXY_NAME="ft0-timeoffset-input-proxy"

WORKFLOW="o2-dpl-raw-proxy ${ARGS_ALL} --dataspec \"${PROXY_INSPEC}\" --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@${INRAWCHANNAME},transport=shmem,rateLogging=1\" | "
WORKFLOW+="o2-calibration-ft0-tf-processor ${ARGS_ALL} --configKeyValues \"$ARGS_ALL_CONFIG\" | "
WORKFLOW+="o2-dpl-output-proxy ${ARGS_ALL} --dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name ${PROXY_NAME} --channel-config \"name=${PROXY_NAME},method=connect,type=push,transport=zeromq,rateLogging=1\" | "
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
