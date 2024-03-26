#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh 

FILEWORKDIR="/home/wiechula/processData/inputFilesTracking/triggeredLaser"

FILEWORKDIR2="/home/epn/odc/files/"

#ARGS_ALL_CONFIG+="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR2;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null"
ARGS_ALL_CONFIG+="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR2;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR"

if [ ${NUMAGPUIDS} != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

if [ ${GPUTYPE} == "HIP" ]; then
  if [ ${NUMAID} == 0 ] || [ ${NUMAGPUIDS} == 0 ]; then
    export TIMESLICEOFFSET=0
  else
    export TIMESLICEOFFSET=${NGPUS}
  fi
  GPU_CONFIG_KEY+="GPU_proc.deviceNum=0;"
  GPU_CONFIG+=" --environment ROCR_VISIBLE_DEVICES={timeslice${TIMESLICEOFFSET}}"
  export HSA_NO_SCRATCH_RECLAIM=1
else
  GPU_CONFIG_KEY+="GPU_proc.deviceNum=-2;"
fi

if [ ${GPUTYPE} != "CPU" ]; then
  GPU_CONFIG_KEY+="GPU_proc.forceMemoryPoolSize=$GPUMEMSIZE;"
  if [ ${HOSTMEMSIZE} == "0" ]; then
    HOSTMEMSIZE=$(( 1 << 30 ))
  fi
fi
if [ ${HOSTMEMSIZE} != "0" ]; then
  GPU_CONFIG_KEY+="GPU_proc.forceHostMemoryPoolSize=$HOSTMEMSIZE;"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
PROXY_OUTSPEC="A:TPC/LASERTRACKS;B:TPC/CEDIGITS;D:TPC/CLUSREFS"


LASER_DECODER_ADD=''

HOST=localhost

QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-laser-calib-qcmn"

if [[ ! -z ${TPC_LASER_ILBZS:-} ]]; then
    LASER_DECODER_ADD="--pedestal-url /home/wiechula/processData/inputFilesTracking/triggeredLaser/pedestals.openchannels.root -decode-type 0"
fi

o2-dpl-raw-proxy ${ARGS_ALL} \
    --dataspec "$PROXY_INSPEC" --inject-missing-data \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
    | o2-tpc-raw-to-digits-workflow ${ARGS_ALL}  ${LASER_DECODER_ADD} \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "TPCDigitDump.NoiseThreshold=3;TPCDigitDump.LastTimeBin=600;$ARGS_ALL_CONFIG" \
    --pipeline tpc-raw-to-digits-0:20 \
    --remove-duplicates \
    --send-ce-digits \
    | o2-tpc-reco-workflow ${ARGS_ALL}  ${TPC_CORR_SCALING:-} \
    --input-type digitizer  \
    --output-type "tracks,disable-writer,clusters" \
    --disable-ctp-lumi-request \
    --disable-mc \
    --pipeline tpc-zsEncoder:20,tpc-tracker:8 \
    ${GPU_CONFIG} \
    --condition-remap "file:///home/wiechula/processData/inputFilesTracking/triggeredLaser/=GLO/Config/GRPECS;file:///home/wiechula/processData/inputFilesTracking/triggeredLaser/=GLO/Config/GRPMagField;file:///home/wiechula/processData/inputFilesTracking/triggeredLaser=TPC/Calib/LaserTracks" \
    --configKeyValues "${ARGS_ALL_CONFIG};align-geom.mDetectors=none;GPU_global.deviceType=$GPUTYPE;GPU_proc.tpcIncreasedMinClustersPerRow=500000;GPU_proc.ignoreNonFatalGPUErrors=1;$GPU_CONFIG_KEY;GPU_global.tpcTriggeredMode=1;GPU_rec_tpc.clusterError2AdditionalY=0.1;GPU_rec_tpc.clusterError2AdditionalZ=0.15;GPU_rec_tpc.clustersShiftTimebinsClusterizer=35;GPU_proc.memoryScalingFactor=2;GPU_proc_param.tpcTriggerHandling=0" \
    | o2-tpc-laser-track-filter ${ARGS_ALL}  \
    | o2-dpl-output-proxy ${ARGS_ALL} \
    --dataspec "$PROXY_OUTSPEC" \
    --proxy-name tpc-laser-input-proxy \
    --proxy-channel-name tpc-laser-input-proxy \
    --channel-config "name=tpc-laser-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0" \
    | o2-qc ${ARGS_ALL} --config ${QC_CONFIG} --local --host ${HOST} \
    | o2-dpl-run ${ARGS_ALL}  --dds ${WORKFLOWMODE_FILE} ${GLOBALDPLOPT}

