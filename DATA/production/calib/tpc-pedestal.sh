#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh 

if [ $NUMAGPUIDS != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"

CCDB_PATH="http://o2-ccdb.internal"

HOST=localhost

#QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-pedestal-calib-qcmn"
QC_CONFIG="components/qc/ANY/any/tpc-pedestal-calib-qcmn?run_type=${RUNTYPE:-}"
CALIB_CONFIG="TPCCalibPedestal.ADCMin=20"
 
# ===| configuration from environment variables |===============================
max_events=${TPC_CALIB_MAX_EVENTS:-50}
publish_after=${TPC_CALIB_PUBLISH_AFTER:-400}
sendToDCS=${TPC_CALIB_SEND_TO_DCS:-1}

# ===| ccdb populator setup |===================================================
# the production CCDB populator will accept subspecs in this range
CCDBPRO_SUBSPEC_MIN=0
CCDBPRO_SUBSPEC_MAX=32767
CCDBPATHPRO="http://o2-ccdb.internal"

# the DCS CCDB populator will accept subspecs in this range
CCDBDCS_SUBSPEC_MIN=32768
CCDBDCS_SUBSPEC_MAX=65535
CCDBPATHDCS="$DCSCCDBSERVER_PERS"

#################################################################################################################################


WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\"" "" 0
add_W o2-tpc-calib-pad-raw "--input-spec \"$CALIB_INSPEC\" --publish-after-tfs ${publish_after} --max-events ${max_events} --lanes 36 --send-to-dcs-ccdb $sendToDCS" "${CALIB_CONFIG}"
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path \"$CCDBPATHPRO\"  --sspec-min $CCDBPRO_SUBSPEC_MIN --sspec-max $CCDBPRO_SUBSPEC_MAX" "" 0
if [[ $sendToDCS -eq 1 ]]; then
  add_W o2-calibration-ccdb-populator-workflow "--ccdb-path \"$CCDBPATHDCS\"  --sspec-min $CCDBDCS_SUBSPEC_MIN --sspec-max $CCDBDCS_SUBSPEC_MAX  --name-extention dcs" "" 0
fi
add_QC_from_apricot "${QC_CONFIG}" "--local --host localhost"

WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi

