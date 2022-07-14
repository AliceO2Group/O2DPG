#!/usr/bin/env bash

# shellcheck disable=SC1091
source common/setenv.sh

# shellcheck disable=SC1091
source common/getCommonArgs.sh

MID_PROXY_INSPEC_EOS="eos:***/INFORMATION"
MID_PROXY_INSPEC_DD="dd:FLP/DISTSUBTIMEFRAME/0"
MID_RAW_PROXY_INSPEC="A:MID/RAWDATA;$MID_PROXY_INSPEC_DD;$MID_PROXY_INSPEC_EOS"
MID_DPL_CHANNEL_CONFIG="name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1"

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --dataspec \"$MID_RAW_PROXY_INSPEC\" --channel-config \"$MID_DPL_CHANNEL_CONFIG\" | "
WORKFLOW+="o2-mid-raw-to-digits-workflow $ARGS_ALL | "
WORKFLOW+="o2-mid-calibration-workflow $ARGS_ALL | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://o2-ccdb.internal\" --sspec-min 0 --sspec-max 0 | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://alio2-cr1-flp199.cern.ch:8083\" --sspec-min 1 --sspec-max 1 --name-extention dcs | "
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ "$WORKFLOWMODE" == "print" ]; then
    echo Workflow command:
    echo "$WORKFLOW" | sed "s/| */|\n/g"
else
    # Execute the command we have assembled
    WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
    eval "$WORKFLOW"
fi
