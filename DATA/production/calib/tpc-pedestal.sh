#!/usr/bin/env bash

source common/setenv.sh

ARGS_ALL="--session default --severity $SEVERITY --shm-segment-id $NUMAID --shm-segment-size $SHMSIZE"
if [ $EPNSYNCMODE == 1 ]; then
  ARGS_ALL+=" --infologger-severity $INFOLOGGER_SEVERITY"
  #ARGS_ALL+=" --monitoring-backend influxdb-unix:///tmp/telegraf.sock"
  ARGS_ALL+=" --monitoring-backend no-op://"
else
  ARGS_ALL+=" --monitoring-backend no-op://"
fi
if [ $SHMTHROW == 0 ]; then
  ARGS_ALL+=" --shm-throw-bad-alloc 0"
fi
if [ $NORATELOG == 1 ]; then
  ARGS_ALL+=" --fairmq-rate-logging 0"
fi
if [ $NUMAGPUIDS != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

max_events=50
publish_after=400

if [[ ! -z ${TPC_CALIB_MAX_EVENTS:-} ]]; then
    max_events=${TPC_CALIB_MAX_EVENTS}
fi

if [[ ! -z ${TPC_CALIB_PUBLISH_AFTER:-} ]]; then
    publish_after=${TPC_CALIB_PUBLISH_AFTER}
fi


CALIB_CONFIG="TPCCalibPedestal.LastTimeBin=12000"
EXTRA_CONFIG=" "
CCDB_PATH="--ccdb-path http://ccdb-test.cern.ch:8080"
EXTRA_CONFIG=" --publish-after-tfs ${publish_after} --max-events ${max_events} --lanes 36"
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
    | o2-dpl-run $ARGS_ALL --dds
