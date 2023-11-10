#!/usr/bin/env bash

# shellcheck disable=SC1091
source testing/detectors/MID/mid_common.sh

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --dataspec \"$MID_RAW_PROXY_INSPEC\" --inject-missing-data --channel-config \"$MID_DPL_CHANNEL_CONFIG\" | "
WORKFLOW+="o2-mid-raw-to-digits-workflow $ARGS_ALL $MID_RAW_TO_DIGITS_OPTS | "
WORKFLOW+="o2-mid-entropy-encoder-workflow $ARGS_ALL | "
WORKFLOW+="o2-ctf-writer-workflow $ARGS_ALL $MID_CTF_WRITER_OPTS | "
WORKFLOW+="o2-qc $ARGS_ALL --config json://$FILEWORKDIR/mid-qcmn-epn-digits.json $MID_QC_EPN_OPTS | "
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ "$WORKFLOWMODE" == "print" ]; then
    echo Workflow command:
    echo "$WORKFLOW" | sed "s/| */|\n/g"
else
    # Execute the command we have assembled
    WORKFLOW+=" --$WORKFLOWMODE"
    eval "$WORKFLOW"
fi
