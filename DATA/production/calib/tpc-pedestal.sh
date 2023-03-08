#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

if [ $NUMAGPUIDS != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"



CALIB_CONFIG="TPCCalibPedestal.LastTimeBin=12000"
EXTRA_CONFIG=" "
EXTRA_CONFIG=" --publish-after-tfs 400 --max-events 30 --lanes 36"
CCDB_PATH="--ccdb-path http://o2-ccdb.internal"
HOST=localhost
QC_CONFIG="consul-json://aliecs.cern.ch:8500/o2/components/qc/ANY/any/tpc-raw-qcmn"

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy '--channel-config "name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1"' \
    | o2-tpc-calib-pad-raw $ARGS_ALL \
    --input-spec "$CALIB_INSPEC" \
    --configKeyValues "$CALIB_CONFIG;keyval.output_dir=/dev/null" \
    $EXTRA_CONFIG \
    | o2-calibration-ccdb-populator-workflow $ARGS_ALL \
    $CCDB_PATH \
    | o2-qc $ARGS_ALL --config $QC_CONFIG --local --host $HOST \
    | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE}
