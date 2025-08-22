#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="tunestring:ITS/TSTR;runtype:ITS/RUNT;fittype:ITS/FITT;scantype:ITS/SCANT;chipdonestring:ITS/QCSTR;confdbv:ITS/CONFDBV;PixTypString:ITS/PIXTYP;eos:***/INFORMATION"

CCDBPATH1=""
CCDBPATH2=""
if [[ $RUNTYPE_ITS == "tuning" ]] || [[ $RUNTYPE_ITS == *digital* ]] || [[ $RUNTYPE_ITS == "tuningbb" ]]; then
  CCDBPATH1="$DCSCCDBSERVER_PERS"
  CCDBPATH2="http://o2-ccdb.internal"
else 
  CCDBPATH1="http://o2-ccdb.internal"
fi

if [[ $RUNTYPE == "SYNTHETIC" || "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" ]]; then
  CCDBPATH1="http://ccdb-test.cern.ch:8080"
  CCDBPATH2="http://ccdb-test.cern.ch:8080"
fi

WORKFLOW=
add_W o2-dpl-raw-proxy "--exit-transition-timeout 20 --proxy-name its-thr-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=its-thr-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq\"" "" 0
add_W o2-its-threshold-aggregator-workflow "-b" "" 0
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path=\"$CCDBPATH1\" --sspec-min 0 --sspec-max 0 --name-extention dcs"
if [[ $RUNTYPE_ITS == *digital* ]]; then
  add_W o2-calibration-ccdb-populator-workflow "--ccdb-path=\"$CCDBPATH2\" --sspec-min 1 --sspec-max 1"
fi

WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
