#!/usr/bin/env bash

source common/setenv.sh

export GLOBAL_SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM # for kr cluster finder

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
if [ $GPUTYPE != "CPU" ]; then
  ARGS_ALL+="  --shm-mlock-segment-on-creation 1"
fi
ARGS_ALL_CONFIG="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null"

if [ $GPUTYPE == "HIP" ]; then
  if [ $NUMAID == 0 ] || [ $NUMAGPUIDS == 0 ]; then
    export TIMESLICEOFFSET=0
  else
    export TIMESLICEOFFSET=$NGPUS
  fi
  GPU_CONFIG_KEY+="GPU_proc.deviceNum=0;GPU_global.mutexMemReg=true;"
  GPU_CONFIG+=" --environment \"ROCR_VISIBLE_DEVICES={timeslice${TIMESLICEOFFSET}}\""
  export HSA_NO_SCRATCH_RECLAIM=1
  #export HSA_TOOLS_LIB=/opt/rocm/lib/librocm-debug-agent.so.2
else
  GPU_CONFIG_KEY+="GPU_proc.deviceNum=-2;"
fi

if [ $GPUTYPE != "CPU" ]; then
  GPU_CONFIG_KEY+="GPU_proc.forceMemoryPoolSize=$GPUMEMSIZE;"
  if [ $HOSTMEMSIZE == "0" ]; then
    HOSTMEMSIZE=$(( 1 << 30 ))
  fi
fi
if [ $HOSTMEMSIZE != "0" ]; then
  GPU_CONFIG_KEY+="GPU_proc.forceHostMemoryPoolSize=$HOSTMEMSIZE;"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"


WRITER_TYPE="none"
workflow_has_parameter ROOT && export WRITER_TYPE="EPN"
NLANES=1
SESSION="default"
PIPEADD="0"
ARGS_FILES="NameConf.mDirGRP=/home/epn/odc/files/;NameConf.mDirGeom=/home/epn/odc/files/;keyval.output_dir=/dev/null"
QC_CONFIG="consul-json://aliecs.cern.ch:8500/o2/components/qc/ANY/any/tpc-full-qcmn-krypton"
if [ $WRITER_TYPE == "EPN" ]; then
   KR_CONFIG="--writer-type ${WRITER_TYPE} --meta-output-dir /data/epn2eos_tool/epn2eos/ --output-dir /data/tf/raw --max-tf-per-file 2000 "
else
   KR_CONFIG="--writer-type ${WRITER_TYPE} "  
fi



o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-${PIPEADD},transport=shmem,rateLogging=1'" \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "$ARGS_FILES" \
    --remove-duplicates \
    --pipeline tpc-raw-to-digits-0:12 \
    | o2-tpc-krypton-clusterer $ARGS_ALL \
    --lanes $NLANES \
    --configKeyValues "$ARGS_FILES" \
    --configFile="/home/wiechula/processData/inputFilesTracking/krypton/krBoxCluster.largeBox.cuts.krMap.ini" \
    $KR_CONFIG \
    | o2-qc $ARGS_ALL --config $QC_CONFIG --local --host localhost \
    | o2-dpl-run --dds  | grep -v ERROR

