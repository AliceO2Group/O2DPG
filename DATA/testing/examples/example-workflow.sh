#!/usr/bin/env bash

source common/setenv.sh

SEVERITY=warning
ARGS_ALL="--session default --severity $SEVERITY --shm-segment-size $SHMSIZE"
if [ $EPNSYNCMODE == 1 ]; then
  ARGS_ALL+=" --infologger-severity $INFOLOGGER_SEVERITY"
  ARGS_ALL+=" --monitoring-backend influxdb-unix:///tmp/telegraf.sock --resources-monitoring 15"
elif [ "0$ENABLE_METRICS" != "01" ]; then
  ARGS_ALL+=" --monitoring-backend no-op://"
fi
[ $NORATELOG == 1 ] && ARGS_ALL+=" --fairmq-rate-logging 0"

ARGS_ALL_CONFIG="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null"

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1'" \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$PROXY_INSPEC"  \
    --remove-duplicates \
    --configKeyValues "$ARGS_ALL_CONFIG;TPCDigitDump.LastTimeBin=1000;" \
    | o2-dpl-run $ARGS_ALL $GLOBALDPLOPT --dds
