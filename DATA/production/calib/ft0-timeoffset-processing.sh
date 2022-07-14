#!/usr/bin/env bash

# shellcheck disable=SC1091
source common/setenv.sh

# shellcheck disable=SC1091
source common/getCommonArgs.sh

FT0_PROXY_INSPEC_EOS="eos:***/INFORMATION"
FT0_PROXY_INSPEC_DD="dd:FLP/DISTSUBTIMEFRAME/0"
FT0_PROXY_INSPEC="digits:FT0/DIGITSBC/0;channels:FT0/DIGITSCH/0;$FT0_PROXY_INSPEC_DD;$FT0_PROXY_INSPEC_EOS"
FT0_DPL_CHANNEL_CONFIG="name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1"

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --dataspec \"$FT0_PROXY_INSPEC\" --channel-config \"$FT0_DPL_CHANNEL_CONFIG\" | "
WORKFLOW+="o2-calibration-ft0-tf-processor $ARGS_ALL | "
WORKFLOW+="o2-calibration-ft0-channel-offset-calibration $ARGS_ALL --tf-per-slot 500 | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://ccdb-test.cern.ch:8080\" --sspec-min 1 --sspec-max 1 | "
WORKFLOW+="o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE}"

if [ "$WORKFLOWMODE" == "print" ]; then
    echo Workflow command:
    echo "$WORKFLOW" | sed "s/| */|\n/g"
else
    # Execute the command we have assembled
    WORKFLOW+=" --$WORKFLOWMODE"
    eval "$WORKFLOW"
fi
