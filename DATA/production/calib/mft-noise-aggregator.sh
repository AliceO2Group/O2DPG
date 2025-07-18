#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="A:MFT/DIGITS/0;B:MFT/DIGITSROF/0"

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --proxy-name mft-noise-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=mft-noise-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq\" | "
WORKFLOW+="o2-calibration-mft-calib-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --useDigits --prob-threshold 1e-5 --send-to-server DCS-CCDB  --path-CCDB \"/MFT/Calib/NoiseMap\" --path-DCS \"/MFT/Config/NoiseMap\" --path-CCDB-single \"/MFT/Calib/NoiseMapSingle\" | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://o2-ccdb.internal\" --sspec-min 0 --sspec-max 0 | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"$DCSCCDBSERVER_PERS\" --sspec-min 1 --sspec-max 1 --name-extention dcs | "
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
