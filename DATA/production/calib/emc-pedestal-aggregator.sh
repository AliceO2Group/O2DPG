#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

INPTYPE=""
  PROXY_INSPEC="A:EMC/PEDDATA/0;eos:***/INFORMATION"

CCDBPATH1="http://o2-ccdb.internal"
CCDBPATH2="$DCSCCDBSERVER"
if [[ $RUNTYPE == "SYNTHETIC" || "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" || ! -z $ISTEST ]]; then
  CCDBPATH1="http://ccdb-test.cern.ch:8080"
  CCDBPATH2="http://ccdb-test.cern.ch:8080"
fi

QC_CONFIG="/o2/components/qc/ANY/any/emc-pedestal-qc"

WORKFLOW=
add_W o2-dpl-raw-proxy "--proxy-name emc-pedestal-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=emc-pedestal-input-proxy,method=bind,type=pull,rateLogging=1,transport=zeromq\"" "" 0
add_W o2-calibration-emcal-pedestal-calib-workflow
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path=\"$CCDBPATH1\" --sspec-min 0 --sspec-max 0"
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path=\"$CCDBPATH2\" --sspec-min 1 --sspec-max 1 --name-extention dcs"
add_QC_from_consul "${QC_CONFIG}" "--local --host localhost"
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
