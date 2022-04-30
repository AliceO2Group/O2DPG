#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="A:ITS/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
PROXY_OUTSPEC="tunestring:ITS/TSTR;runtype:ITS/RUNT;fittype:ITS/FITT;scantype:ITS/SCANT"

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --dataspec \"$PROXY_INSPEC\" --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,rateLogging=0,transport=shmem\" | "
WORKFLOW+="o2-itsmft-stf-decoder-workflow ${ARGS_ALL} --configKeyValues \"$ARGS_ALL_CONFIG\" --nthreads 1  --pipeline its-stf-decoder:6 --no-clusters --no-cluster-patterns --enable-calib-data --digits | "
WORKFLOW+="o2-its-threshold-calib-workflow -b --nthreads 4 --enable-eos --chip-mod-selector 0 --chip-mod-base 3 --fittype derivative --output-dir \"/data/calibration\" --meta-output-dir \"/data/epn2eos_tool/epn2eos\" $ARGS_ALL | "
WORKFLOW+="o2-its-threshold-calib-workflow -b --nthreads 4 --enable-eos --chip-mod-selector 1 --chip-mod-base 3 --fittype derivative --output-dir \"/data/calibration\" --meta-output-dir \"/data/epn2eos_tool/epn2eos\" $ARGS_ALL | "
WORKFLOW+="o2-its-threshold-calib-workflow -b --nthreads 4 --enable-eos --chip-mod-selector 2 --chip-mod-base 3 --fittype derivative --output-dir \"/data/calibration\" --meta-output-dir \"/data/epn2eos_tool/epn2eos\" $ARGS_ALL | "
WORKFLOW+="o2-qc --config consul-json://alio2-cr1-hv-aliecs:8500/o2/components/qc/ANY/any/its-qc-calibration --local --host epn $ARGS_ALL -b | "
WORKFLOW+="o2-dpl-output-proxy ${ARGS_ALL} --dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name its-thr-input-proxy --channel-config \"name=its-thr-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0\" | "
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE"
  eval $WORKFLOW
fi
