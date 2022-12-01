#!/usr/bin/env bash

source common/setenv.sh
export SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM
export GPUMEMSIZE=$(( 24 << 30 ))
export HOSTMEMSIZE=$(( 5 << 30 ))
export GPUTYPE="HIP"

FILEWORKDIR="/home/wiechula/processData/inputFilesTracking/triggeredLaser"

FILEWORKDIR2="/home/epn/odc/files/"

source common/getCommonArgs.sh
ARGS_ALL_CONFIG="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR2;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null"

if [ $NUMAGPUIDS != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

if [ $GPUTYPE == "HIP" ]; then
  if [ $NUMAID == 0 ] || [ $NUMAGPUIDS == 0 ]; then
    export TIMESLICEOFFSET=0
  else
    export TIMESLICEOFFSET=$NGPUS
  fi
  GPU_CONFIG_KEY+="GPU_proc.deviceNum=0;"
  GPU_CONFIG+=" --environment ROCR_VISIBLE_DEVICES={timeslice${TIMESLICEOFFSET}}"
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

#source /home/epn/runcontrol/tpc/qc_test_env.sh > /dev/null
PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

### Comment: MAKE SURE the channels match address=ipc://@tf-builder-pipe-0

if [ -z $TPC_LASER_EVENTS ]; then
    TPC_LASER_EVENTS=10
fi

#VERBOSE=""

#echo GPU_CONFIG $GPU_CONFIG_KEYS;

HOST=localhost
QC_CONFIG="consul-json://aliecs.cern.ch:8500/o2/components/qc/ANY/any/tpc-raw-qcmn"

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "TPCDigitDump.NoiseThreshold=3;TPCDigitDump.LastTimeBin=600;$ARGS_ALL_CONFIG" \
    --pedestal-url /home/wiechula/processData/inputFilesTracking/triggeredLaser/pedestals.openchannels.root \
    --pipeline tpc-raw-to-digits-0:20 \
    --remove-duplicates \
    --send-ce-digits \
    --decoder-type 0 \
    | o2-tpc-reco-workflow $ARGS_ALL \
    --input-type digitizer  \
    --output-type "tracks,disable-writer" \
    --disable-mc \
    --pipeline tpc-zsEncoder:20,tpc-tracker:8 \
    $GPU_CONFIG \
    --condition-remap file:///home/wiechula/processData/inputFilesTracking/triggeredLaser/=GLO/Config/GRPECS \
    --configKeyValues "$ARGS_ALL_CONFIG;align-geom.mDetectors=none;GPU_global.deviceType=$GPUTYPE;GPU_proc.tpcIncreasedMinClustersPerRow=500000;GPU_proc.ignoreNonFatalGPUErrors=1;$GPU_CONFIG_KEY;GPU_global.tpcTriggeredMode=1" \
    | o2-tpc-laser-track-filter $ARGS_ALL \
    | o2-tpc-calib-laser-tracks  $ARGS_ALL --use-filtered-tracks --min-tfs ${TPC_LASER_EVENTS}\
    | o2-tpc-calib-pad-raw $ARGS_ALL \
    --configKeyValues "TPCCalibPulser.FirstTimeBin=450;TPCCalibPulser.LastTimeBin=550;TPCCalibPulser.NbinsQtot=250;TPCCalibPulser.XminQtot=2;TPCCalibPulser.XmaxQtot=502;TPCCalibPulser.MinimumQtot=8;TPCCalibPulser.MinimumQmax=6;TPCCalibPulser.XminT0=450;TPCCalibPulser.XmaxT0=550;TPCCalibPulser.NbinsT0=400;keyval.output_dir=/dev/null" \
    --lanes 36 \
    --calib-type ce \
    --publish-after-tfs 50 \
    --max-events 200 \
    | o2-calibration-ccdb-populator-workflow  $ARGS_ALL \
    --ccdb-path http://o2-ccdb.internal \
    | o2-qc $ARGS_ALL --config $QC_CONFIG --local --host $HOST \
    | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE}

#    --pipeline tpc-tracker:4 \

#    --configKeyValues "align-geom.mDetectors=none;GPU_global.deviceType=$GPUTYPE;GPU_proc.forceMemoryPoolSize=$GPUMEMSIZE;GPU_proc.forceHostMemoryPoolSize=$HOSTMEMSIZE;GPU_proc.deviceNum=0;GPU_proc.tpcIncreasedMinClustersPerRow=500000;GPU_proc.ignoreNonFatalGPUErrors=1;$ARGS_FILES;keyval.output_dir=/dev/null" \
