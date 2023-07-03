#!/bin/bash

## WORKFLOW FOR ALL ITS CALIBRATION SCANS (TODO: ADD FULL THR SCAN)

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="A:ITS/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
PROXY_OUTSPEC="tunestring:ITS/TSTR;runtype:ITS/RUNT;fittype:ITS/FITT;scantype:ITS/SCANT;chipdonestring:ITS/QCSTR;confdbv:ITS/CONFDBV;PixTypString:ITS/PIXTYP"

CHIPMODBASE=5
NDECODERS=6
if [ $RUNTYPE == "digital" ]; then
  CHIPMODBASE=10
fi
if [ $RUNTYPE == "thrfull" ]; then
  CHIPMODBASE=20
  NDECODERS=10
fi
ADDITIONAL_OPTIONS_DEC=""
ADDITIONAL_OPTIONS_CAL=""
if [ $RUNTYPE == "tuningbb" ]; then
  ADDITIONAL_OPTIONS_CAL="--min-vcasn 30 --max-vcasn 130"
fi
if [ $RUNTYPE == "tot1row" ]; then
  ADDITIONAL_OPTIONS_DEC="--allow-empty-rofs"
  ADDITIONAL_OPTIONS_CAL="--ninj 10"
fi
if [ $RUNTYPE == "totfullfast" ]; then
  ADDITIONAL_OPTIONS_DEC="--allow-empty-rofs"
  ADDITIONAL_OPTIONS_CAL="--calculate-slope --charge-a 30 --charge-b 60 --ninj 10"
fi

WORKFLOW="o2-dpl-raw-proxy --exit-transition-timeout 20 $ARGS_ALL --dataspec \"$PROXY_INSPEC\" --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,rateLogging=0,transport=shmem\" | "
WORKFLOW+="o2-itsmft-stf-decoder-workflow ${ARGS_ALL} ${ADDITIONAL_OPTIONS_DEC} --condition-tf-per-query -1 --condition-backend \"http://localhost:8084\" --ignore-dist-stf --configKeyValues \"$ARGS_ALL_CONFIG\" --nthreads 1  --no-clusters --no-cluster-patterns --pipeline its-stf-decoder:${NDECODERS} --enable-calib-data --digits | "
for i in $(seq 0 $((CHIPMODBASE-1)))
do
  WORKFLOW+="o2-its-threshold-calib-workflow -b ${ADDITIONAL_OPTIONS_CAL} --enable-single-pix-tag --ccdb-mgr-url=\"http://localhost:8084\" --nthreads 1 --chip-mod-selector $i --chip-mod-base $CHIPMODBASE --fittype derivative --output-dir \"/data/calibration\" --meta-output-dir \"/data/epn2eos_tool/epn2eos\" --meta-type \"calibration\" $ARGS_ALL | "
done
if workflow_has_parameter QC && has_detector_qc ITS; then
  WORKFLOW+="o2-qc --config consul-json://aliecs.cern.ch:8500/o2/components/qc/ANY/any/its-qc-calibration --local --host epn -b $ARGS_ALL | "
fi
WORKFLOW+="o2-dpl-output-proxy ${ARGS_ALL} --dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name its-thr-input-proxy --channel-config \"name=its-thr-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0\" | "
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
