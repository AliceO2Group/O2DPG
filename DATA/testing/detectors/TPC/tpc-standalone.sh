#!/usr/bin/env bash

export GLOBAL_SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM
export NHBPERTF=256
export GPUTYPE=HIP
export GPUMEMSIZE=$(( 24 << 30 ))
export HOSTMEMSIZE=$(( 5 << 30 ))
DISPLAY=0

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

### Comment: MAKE SURE the channels match address=ipc://@tf-builder-pipe-0

hash=$1

module load QualityControl DataDistribution ODC > /dev/null


VERBOSE=""
NCPU=12 #$(grep ^cpu\\scores /proc/cpuinfo | uniq |  awk '{print $4}')
ARGS_ALL="-b --session default --shm-segment-size $GLOBAL_SHMSIZE"
ARGS_FILES="NameConf.mDirGRP=/home/epn/odc/files/;NameConf.mDirGeom=/home/epn/odc/files/;keyval.output_dir=/dev/null"
#HOST='$(hostname -s)-ib'
HOST=localhost

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
    --severity info \
    --infologger-severity warning \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "TPCDigitDump.LastTimeBin=1000;$ARGS_FILES" \
    --severity warning \
    --infologger-severity warning \
    --remove-duplicates \
    --pipeline tpc-raw-to-digits-0:6 \
    | o2-tpc-reco-workflow $ARGS_ALL \
    --input-type digitizer  \
    --output-type clusters,tracks,disable-writer \
    --disable-mc \
    --pipeline tpc-tracker:8 \
    --environment "ROCR_VISIBLE_DEVICES={timeslice0}" \
    --configKeyValues "align-geom.mDetectors=none;GPU_global.deviceType=$GPUTYPE;GPU_proc.forceMemoryPoolSize=$GPUMEMSIZE;GPU_proc.forceHostMemoryPoolSize=$HOSTMEMSIZE;GPU_proc.deviceNum=0;GPU_proc.tpcIncreasedMinClustersPerRow=500000;GPU_proc.ignoreNonFatalGPUErrors=1;GPU_proc.memoryScalingFactor=3;$ARGS_FILES;keyval.output_dir=/dev/null" \
    --severity info \
    --infologger-severity warning \
    | o2-qc $ARGS_ALL --config consul-json://aliecs.cern.ch:8500/o2/components/qc/ANY/any/tpc-full-qcmn --local --host $HOST \
    | o2-dpl-run $ARGS_ALL --dds

