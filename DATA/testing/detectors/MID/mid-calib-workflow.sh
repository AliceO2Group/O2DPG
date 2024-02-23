#!/usr/bin/env bash

# shellcheck disable=SC1091
source testing/detectors/MID/mid_common.sh

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --dataspec \"$MID_RAW_PROXY_INSPEC\" --inject-missing-data --channel-config \"$MID_DPL_CHANNEL_CONFIG\" | "
WORKFLOW+="o2-mid-raw-to-digits-workflow $ARGS_ALL $MID_RAW_TO_DIGITS_OPTS | "
WORKFLOW+="o2-mid-calibration-workflow $ARGS_ALL | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://o2-ccdb.internal\" --sspec-min 0 --sspec-max 0 | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"${DCSCCDBSERVER:-http://alio2-cr1-flp199-ib:8083}\" --sspec-min 1 --sspec-max 1 --name-extention dcs | "
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ "$WORKFLOWMODE" == "print" ]; then
    echo Workflow command:
    echo "$WORKFLOW" | sed "s/| */|\n/g"
else
    # Execute the command we have assembled
    WORKFLOW+=" --$WORKFLOWMODE"
    eval "$WORKFLOW"
fi
