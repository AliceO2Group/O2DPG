#!/usr/bin/env bash

# must be loaded in the manifest
# eval $(aliswmod load DataDistribution/v0.9.7-5 QualityControl/v1.13.0-1)

module load DataDistribution QualityControl > /dev/null 


DISPLAY=0

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_CONFIG="TPCCalibPedestal.LastTimeBin=12000"
EXTRA_CONFIG=" "
EXTRA_CONFIG=" --publish-after-tfs 100 --max-events 120"
#EXTRA_CONFIG="--publish-after-tfs 50 --direct-file-dump"

### Comment: MAKE SURE the channels match address=ipc://@tf-builder-pipe-0

VERBOSE=""
#NCPU=$(grep ^cpu\\scores /proc/cpuinfo | uniq |  awk '{print $4}')
NCPU=36
ARGS_ALL="-b --session default"

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy '--channel-config "name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1"' \
    | o2-tpc-calib-pad-raw $ARGS_ALL \
    --severity info \
    --input-spec "$CALIB_INSPEC" \
    --configKeyValues "$CALIB_CONFIG;keyval.output_dir=/dev/null" \
    $EXTRA_CONFIG \
    --lanes $NCPU \
    | o2-calibration-ccdb-populator-workflow $ARGS_ALL \
    --ccdb-path http://ccdb-test.cern.ch:8080 \
    | o2-dpl-run $ARGS_ALL --dds
