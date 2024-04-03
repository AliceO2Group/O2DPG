#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh

if [ $NUMAGPUIDS != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"

NLANES=36
SESSION="default"
PIPEADD="0"

HOST=localhost
QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-raw-qcmn"
QC_CONFIG_CONSUL=/o2/components/qc/ANY/any/tpc-raw-qcmn
# TODO use add_W function from gen_topo_helper_functions.sh to assemble workflow
# as done for example in https://github.com/AliceO2Group/O2DPG/blob/master/DATA/production/calib/its-threshold-processing.sh

WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\"" "" 0
add_W o2-tpc-raw-to-digits-workflow "--ignore-grp --input-spec \"$CALIB_INSPEC\" --remove-duplicates --pipeline tpc-raw-to-digits-0:20"
add_W o2-tpc-krypton-raw-filter "tpc-raw-to-digits-0:24  --lanes $NLANES --writer-type EPN --meta-output-dir $EPN2EOS_METAFILES_DIR --output-dir $CALIB_DIR --threshold-max 20 --max-tf-per-file 8000 --time-bins-before 20 --max-time-bins 650"
add_QC_from_consul "${QC_CONFIG_CONSUL}" "--local --host localhost"



WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"
if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi

#o2-dpl-raw-proxy $ARGS_ALL \
#    --dataspec "$PROXY_INSPEC" --inject-missing-data \
#    --readout-proxy '--channel-config "name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1"' \
#    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
#    --input-spec "$CALIB_INSPEC"  \
#    --configKeyValues "$ARGS_FILES;$ARGS_ALL_CONFIG" \
#    --remove-duplicates \
#    --pipeline tpc-raw-to-digits-0:24 \
#    | o2-tpc-krypton-raw-filter $ARGS_ALL \
#    --configKeyValues "$ARGS_FILES" \
#   --lanes $NLANES \
#    --writer-type EPN \
#    --meta-output-dir $EPN2EOS_METAFILES_DIR \
#    --output-dir $CALIB_DIR \
#    --threshold-max 20 \
#    --max-tf-per-file 8000 \
#    --time-bins-before 20 \
#    --max-time-bins 650 \
#    | o2-qc $ARGS_ALL --config ${QC_CONFIG} --local --host $HOST \
#    | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE} ${GLOBALDPLOPT}
