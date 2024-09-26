#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

INPTYPE=""
#PROXY_INSPEC="A:EMC/PEDDATA/0;eos:***/INFORMATION"
PROXY_INSPEC="A:EMC/PEDDATA/0"

CCDBPATH1="http://o2-ccdb.internal"
CCDBPATH2="$DCSCCDBSERVER_PERS"
if [[ $RUNTYPE == "SYNTHETIC" || "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" || ! -z $ISTEST ]]; then
  CCDBPATH1="http://ccdb-test.cern.ch:8080"
  CCDBPATH2="http://ccdb-test.cern.ch:8080"
fi

QC_STANDALONE=0
if [[ ! -z ${EMC_PEDQC_STANDALONE:-} ]]; then
        QC_STANDALONE=${EMC_PEDQC_STANDALONE}
fi

QC_CONFIG="/o2/components/qc/ANY/any/emc-pedestal-qc"
QC_OPT=
if [ $QC_STANDALONE -gt 0 ]; then
        QC_CONFIG="/o2/components/qc/ANY/any/emc-pedestal-qc-standalone"
else
        QC_CONFIG="/o2/components/qc/ANY/any/emc-pedestal-qc"
        QC_OPT="--local --host localhost"
fi

WORKFLOW=
add_W o2-dpl-raw-proxy "--proxy-name emc-pedestal-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=emc-pedestal-input-proxy,method=bind,type=pull,rateLogging=1,transport=zeromq\"" "" 0
add_W o2-calibration-emcal-pedestal-calib-workflow --addRunNumber
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path=\"$CCDBPATH1\" --sspec-min 0 --sspec-max 0"
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path=\"$CCDBPATH2\" --sspec-min 1 --sspec-max 1 --name-extention dcs"
add_QC_from_consul "${QC_CONFIG}" "${QC_OPT}"
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
