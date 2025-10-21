#!/bin/bash

## WORKFLOW FOR ALL ITS CALIBRATION SCANS (TODO: ADD FULL THR SCAN)

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh
source common/gen_topo_helper_functions.sh

PROXY_INSPEC="A:ITS/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
PROXY_OUTSPEC="tunestring:ITS/TSTR;runtype:ITS/RUNT;fittype:ITS/FITT;scantype:ITS/SCANT;chipdonestring:ITS/QCSTR;confdbv:ITS/CONFDBV;PixTypString:ITS/PIXTYP"

CHIPMODBASE=5
NDECODERS=6
ADDITIONAL_OPTIONS_DEC=""
ADDITIONAL_OPTIONS_CAL=""
if [ $RUNTYPE_ITS == "digital" ]; then
  CHIPMODBASE=10
fi
if [ $RUNTYPE_ITS == "digitalnomask" ]; then
  CHIPMODBASE=10
  ADDITIONAL_OPTIONS_CAL="--ninj 5"
fi
if [ $RUNTYPE_ITS == "thrfull" ]; then
  CHIPMODBASE=20
  NDECODERS=10
fi
if [ $RUNTYPE_ITS == "tuningbb" ]; then
  ADDITIONAL_OPTIONS_CAL="--min-vcasn 30 --max-vcasn 130"
fi
if [[ $RUNTYPE_ITS == "tot1row" || $RUNTYPE_ITS == "vresetd-2d" ]]; then
  ADDITIONAL_OPTIONS_CAL="--ninj 10"
fi
if [ $RUNTYPE_ITS == "totfullfast" ]; then
  ADDITIONAL_OPTIONS_CAL="--calculate-slope --charge-a 30 --charge-b 60 --ninj 10"
fi

WORKFLOW=
add_W o2-dpl-raw-proxy "--exit-transition-timeout 20 --dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,rateLogging=0,transport=shmem\"" "" 0
add_W o2-itsmft-stf-decoder-workflow "${ADDITIONAL_OPTIONS_DEC} --allow-empty-rofs --always-parse-trigger --condition-tf-per-query -1 --condition-backend \"http://localhost:8084\" --ignore-dist-stf --nthreads 1  --no-clusters --no-cluster-patterns --pipeline its-stf-decoder:${NDECODERS} --enable-calib-data --digits"
for i in $(seq 0 $((CHIPMODBASE-1)))
do
  add_W o2-its-threshold-calib-workflow "-b ${ADDITIONAL_OPTIONS_CAL} --enable-single-pix-tag --ccdb-mgr-url=\"http://localhost:8084\" --nthreads 1 --chip-mod-selector $i --chip-mod-base $CHIPMODBASE --fittype derivative --output-dir \"/data/calibration\" --meta-output-dir \"/data/epn2eos_tool/epn2eos\" --meta-type \"calibration\"" "" 0
done
if workflow_has_parameter QC && has_detector_qc ITS; then
  add_QC_from_consul "/o2/components/qc/ANY/any/its-qc-calibration" "--local --host epn -b"
fi
add_W o2-dpl-output-proxy "--dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name its-thr-input-proxy --channel-config \"name=its-thr-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0\"" "" 0
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
