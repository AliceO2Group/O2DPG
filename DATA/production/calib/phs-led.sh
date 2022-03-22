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

if [ -z $PHS_MAX_STATISTICS ]; then
  PHS_MAX_STATISTICS=1000000
fi

PROXY_INSPEC="A:PHS/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

EXTRA_CONFIG=" "

if [ -z $PHS_CCDB_PATH ]; then
  PHS_CCDB_PATH="http://o2-ccdb.internal"
fi

QC_CONFIG=consul-json://aliecs.cern.ch:8500/o2/components/qc/ANY/any/phs-led-qc

o2-dpl-raw-proxy $ARGS_ALL \
		 --dataspec "$PROXY_INSPEC" \
		 --readout-proxy '--channel-config "name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1"' \
    | o2-phos-reco-workflow $ARGS_ALL \
			    --input-type raw  \
			    --output-type cells \
			    --disable-root-input \
			    --disable-root-output \
			    --keepHGLG on \
    | o2-phos-calib-workflow $ARGS_ALL \
			     --hglgratio on \
			     --statistics $PHS_MAX_STATISTICS \
			     --configKeyValues "NameConf.mCCDBServer=${PHS_CCDB_PATH}" \
			     --forceupdate \
    | o2-qc $ARGS_ALL \
            --config $QC_CONFIG \
    | o2-calibration-ccdb-populator-workflow $ARGS_ALL \
					     --ccdb-path $PHS_CCDB_PATH \
    | o2-dpl-run $ARGS_ALL --dds
