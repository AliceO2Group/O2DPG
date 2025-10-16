#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh 

FILEWORKDIR="/home/wiechula/processData/inputFilesTracking/triggeredLaser"

FILEWORKDIR2="/home/epn/odc/files/"

#ARGS_ALL_CONFIG+="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR2;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null"
#ARGS_ALL_CONFIG+="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR2;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR"

GPUTYPE=${GPUTYPE:-CPU}
HOSTMEMSIZE=0
if workflow_has_parameter GPU; then
  GPUTYPE=HIP
  GPUMEMSIZE=$(( 24 << 30 ))
  HOSTMEMSIZE=$(( 5 << 30 ))
fi

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

HOST=localhost

QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-laser-calib-qcmn?run_type=${RUNTYPE:-}"
QC_CONFIG="components/qc/ANY/any/tpc-laser-calib-qcmn?run_type=${RUNTYPE:-}"


RAWDIGIT_CONFIG="TPCDigitDump.NoiseThreshold=3;TPCDigitDump.LastTimeBin=600;NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR2;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR"
REMAP="--condition-remap \"file://${FILEWORKDIR}=GLO/Config/GRPECS,GLO/Config/GRPMagField,TPC/Calib/LaserTracks\" "
RECO_CONFIG="NameConf.mDirGRP=$FILEWORKDIR;"
RECO_CONFIG+="NameConf.mDirGeom=$FILEWORKDIR2;"
RECO_CONFIG+="NameConf.mDirCollContext=$FILEWORKDIR;"
RECO_CONFIG+="NameConf.mDirMatLUT=$FILEWORKDIR;"   
RECO_CONFIG+="align-geom.mDetectors=none;"
RECO_CONFIG+="GPU_global.deviceType=$GPUTYPE;"
RECO_CONFIG+="GPU_proc.tpcIncreasedMinClustersPerRow=500000;"
RECO_CONFIG+="GPU_proc.ignoreNonFatalGPUErrors=1;$GPU_CONFIG_KEY;"
RECO_CONFIG+="GPU_global.tpcTriggeredMode=1;"
RECO_CONFIG+="GPU_rec_tpc.clusterError2AdditionalY=0.1;"
RECO_CONFIG+="GPU_rec_tpc.clusterError2AdditionalZ=0.15;"
RECO_CONFIG+="GPU_rec_tpc.clustersShiftTimebinsClusterizer=35;"
RECO_CONFIG+="GPU_proc.memoryScalingFactor=2;"
RECO_CONFIG+="GPU_proc_param.tpcTriggerHandling=0;"
# relax tolerances on tracking and selection cut to deal with very low laser intensities
RECO_CONFIG+="GPU_rec_tpc.trackFollowingMaxRowGap=15;GPU_rec_tpc.trackFollowingMaxRowGapSeed=15;GPU_rec_tpc.minTrackdEdxMax=8;GPU_rec_tpc.adddEdxSubThresholdClusters=0;"


WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\"" "" 0
add_W o2-tpc-raw-to-digits-workflow "--ignore-grp --input-spec \"$CALIB_INSPEC\" --remove-duplicates --pipeline tpc-raw-to-digits-0:20 --send-ce-digits " "${RAWDIGIT_CONFIG}"
add_W o2-tpc-reco-workflow " ${TPC_CORR_SCALING:-} --disable-ctp-lumi-request --input-type digitizer --output-type \"tracks,disable-writer,clusters\" --disable-mc --pipeline tpc-zsEncoder:20,tpc-tracker:8 ${GPU_CONFIG} ${REMAP} " "${RECO_CONFIG}"
add_W o2-tpc-laser-track-filter "" "" 0
add_W o2-dpl-output-proxy " --proxy-name tpc-laser-input-proxy --proxy-channel-name tpc-laser-input-proxy --dataspec \"$PROXY_OUTSPEC\" --channel-config \"name=tpc-laser-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0\" " "" 0
add_QC_from_apricot "${QC_CONFIG}" "--local --host localhost"

WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"
if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi

