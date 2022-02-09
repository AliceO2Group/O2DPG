
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
ARGS_ALL_CONFIG="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKD
IR;keyval.output_dir=/dev/null"

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

CALIB_CONFIG="TPCCalibPulser.FirstTimeBin=80;TPCCalibPulser.LastTimeBin=160;TPCCalibPulser.NbinsQtot=250;TPCCalibPulser.XminQtot=10;TPCCalibPulser.XmaxQtot=510;TPCCalibPulser.NbinsWidth=100;TPCCalibPulser.XminWidth=0.3;TPCCalibPulser.XmaxWidth=0.7;TPCCalibPulser.MinimumQtot=30;TPCCalibPulser.MinimumQmax=25;TPCCalibPulser.XminT0=115;TPCCalibPulser.XmaxT0=130;TPCCalibPulser.NbinsT0=600"

EXTRA_CONFIG=" "
EXTRA_CONFIG="--calib-type pulser --publish-after-tfs 1000 --max-events 1200 --lanes 36"

CCDB_PATH="--ccdb-path http://ccdb-test.cern.ch:8080"


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
