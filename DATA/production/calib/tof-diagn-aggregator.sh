#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh
source common/gen_topo_helper_functions.sh

PROXY_INSPEC="diagWords:TOF/DIAFREQ/0;eos:***/INFORMATION"

WORKFLOW=
add_W o2-dpl-raw-proxy "$ARGS_ALL --proxy-name tof-diagn-input-proxy --dataspec ${PROXY_INSPEC} --network-interface ib0 --channel-config \"name=tof-diagn-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq\" "
add_W o2-calibration-tof-diagnostic-workflow "--tf-per-slot 25000 --max-delay 1 ${ARGS_ALL}"

if [[ $RUNTYPE == "SYNTHETIC" || "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" ]]; then
    CCDB_POPULATOR_UPLOAD_PATH="http://ccdb-test.cern.ch:8080"
else
    CCDB_POPULATOR_UPLOAD_PATH="http://localhost:8084"
fi
add_W o2-calibration-ccdb-populator-workflow "${ARGS_ALL} --configKeyValues ${ARGS_ALL_CONFIG} --ccdb-path=${CCDB_POPULATOR_UPLOAD_PATH} "


WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
