#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="tunestring:ITS/TSTR;runtype:ITS/RUNT;fittype:ITS/FITT;scantype:ITS/SCANT;chipdonestring:ITS/QCSTR;confdbv:ITS/CONFDBV;PixTypString:ITS/PIXTYP;eos:***/INFORMATION"

CCDBPATH1=""
CCDBPATH2=""
if [ $RUNTYPE == "tuning" ] || [ $RUNTYPE == "digital" ] || [ $RUNTYPE == "tuningbb" ]; then
  CCDBPATH1="http://alio2-cr1-flp199.cern.ch:8083"
  CCDBPATH2="http://o2-ccdb.internal"
elif [ $RUNTYPE == "thrshort" ] || [ $RUNTYPE == "pulselength" ]; then
  CCDBPATH1="http://o2-ccdb.internal"
else
  echo Ccdb paths are empty
fi

if [[ -z $USEEOS ]]; then 

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --exit-transition-timeout 20 --proxy-name its-thr-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=its-thr-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq\" | "
if [[ -z $USEEOS ]]; then#use eos
  WORKFLOW+="o2-its-threshold-aggregator-workflow -b $ARGS_ALL | "
  WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"$CCDBPATH1\" --sspec-min 0 --sspec-max 0 --name-extention dcs | "
  if [ $RUNTYPE == "digital" ]; then
    WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"$CCDBPATH2\" --sspec-min 1 --sspec-max 1 | "
  fi
else#do not use eos
  WORKFLOW+="o2-its-threshold-aggregator-workflow -b --ccdb-url=\"$CCDBPATH1\" $ARGS_ALL | "
fi
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
