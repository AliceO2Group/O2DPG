#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh 

FILEWORKDIR="/home/wiechula/processData/inputFilesTracking/triggeredLaser"

FILEWORKDIR2="/home/epn/odc/files/"

GPUTYPE=${GPUTYPE:-CPU}
HOSTMEMSIZE=0
if workflow_has_parameter GPU; then
  GPUTYPE=HIP
  GPUMEMSIZE=$(( 24 << 30 ))
  HOSTMEMSIZE=$(( 5 << 30 ))
fi

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

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"

CALIB_CONFIG="TPCCalibPulser.FirstTimeBin=450;TPCCalibPulser.LastTimeBin=550;TPCCalibPulser.NbinsQtot=250;TPCCalibPulser.XminQtot=2;TPCCalibPulser.XmaxQtot=502;TPCCalibPulser.MinimumQtot=8;TPCCalibPulser.MinimumQmax=6;TPCCalibPulser.XminT0=450;TPCCalibPulser.XmaxT0=550;TPCCalibPulser.NbinsT0=400;keyval.output_dir=/dev/null"

CCDB_PATH="http://o2-ccdb.internal"

HOST=localhost


QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-raw-qcmn?run_type=${RUNTYPE:-}"
QC_CONFIG="components/qc/ANY/any/tpc-raw-qcmn"

max_events=300
publish_after=440
min_tracks=0
num_lanes=36

if [[ ! -z ${TPC_CALIB_MAX_EVENTS:-} ]]; then
    max_events=${TPC_CALIB_MAX_EVENTS}
fi
if [[ ! -z ${TPC_CALIB_MIN_TRACKS:-} ]]; then
    min_tracks=${TPC_CALIB_MIN_TRACKS}
fi

if [[ ! -z ${TPC_CALIB_PUBLISH_AFTER:-} ]]; then
    publish_after=${TPC_CALIB_PUBLISH_AFTER}
fi
if [[ ! -z ${TPC_CALIB_LANES_PAD_RAW:-} ]]; then
    num_lanes=${TPC_CALIB_LANES_PAD_RAW}
fi

EXTRA_CONFIG="--calib-type ce --publish-after-tfs ${publish_after} --max-events ${max_events} --lanes ${num_lanes} --check-calib-infos" 

LASER_DECODER_ADD=''

if [[ ! -z ${TPC_LASER_ILBZS:-} ]]; then
    LASER_DECODER_ADD="--pedestal-url /home/wiechula/processData/inputFilesTracking/triggeredLaser/pedestals.openchannels.root --decoder-type 0"
fi

EXTRA_CONFIG_TRACKS=""

if [[ ${TPC_CALIB_TRACKS_PUBLISH_EOS:-} == 1 ]]; then
    EXTRA_CONFIG_TRACKS="--only-publish-on-eos"
fi

RAWDIGIT_CONFIG="TPCDigitDump.NoiseThreshold=3;TPCDigitDump.LastTimeBin=600"
REMAP="--condition-remap \"file://${FILEWORKDIR}=GLO/Config/GRPECS,GLO/Config/GRPMagField,TPC/Calib/LaserTracks\" "
RECO_CONFIG="align-geom.mDetectors=none;GPU_global.deviceType=$GPUTYPE;GPU_proc.tpcIncreasedMinClustersPerRow=500000;GPU_proc.ignoreNonFatalGPUErrors=1;$GPU_CONFIG_KEY;GPU_global.tpcTriggeredMode=1;GPU_rec_tpc.clusterError2AdditionalY=0.1;GPU_rec_tpc.clusterError2AdditionalZ=0.15;GPU_rec_tpc.clustersShiftTimebinsClusterizer=35;"
# relax tolerances on tracking and selection cut to deal with very low laser intensities
RECO_CONFIG+="GPU_rec_tpc.trackFollowingMaxRowGap=15;GPU_rec_tpc.trackFollowingMaxRowGapSeed=15;GPU_rec_tpc.minTrackdEdxMax=8;GPU_rec_tpc.adddEdxSubThresholdClusters=0;"

WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\"" "" 0
add_W o2-tpc-raw-to-digits-workflow "--ignore-grp --input-spec \"$CALIB_INSPEC\" --remove-duplicates --pipeline tpc-raw-to-digits-0:20 --send-ce-digits " "${RAWDIGIT_CONFIG}"
add_W o2-tpc-reco-workflow " --disable-ctp-lumi-request --input-type digitizer --output-type \"tracks,disable-writer\" --disable-mc --pipeline tpc-zsEncoder:20,tpc-tracker:8 ${GPU_CONFIG} ${REMAP}" "${RECO_CONFIG}"
add_W o2-tpc-laser-track-filter "" "" 0
add_W o2-tpc-calib-laser-tracks "--use-filtered-tracks ${EXTRA_CONFIG_TRACKS} --min-tfs=${min_tracks}"
add_W o2-tpc-calib-pad-raw " ${EXTRA_CONFIG}" "${CALIB_CONFIG}"
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path ${CCDB_PATH}" "" 0
add_QC_from_apricot "${QC_CONFIG_CONSUL}" "--local --host lcoalhost"

WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"
if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi

#o2-dpl-raw-proxy $ARGS_ALL --inject-missing-data \
#    --dataspec "$PROXY_INSPEC" \
#    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
#    | o2-tpc-raw-to-digits-workflow $ARGS_ALL  ${LASER_DECODER_ADD}\
#    --input-spec "$CALIB_INSPEC"  \
#    --configKeyValues ";$ARGS_ALL_CONFIG" \
#    --pipeline tpc-raw-to-digits-0:20 \
#    --remove-duplicates \
#    --send-ce-digits \
#    | o2-tpc-reco-workflow $ARGS_ALL \
#    --input-type digitizer  \
#    --output-type "tracks,disable-writer" \
#    --disable-mc \
#    --pipeline tpc-zsEncoder:20,tpc-tracker:8 \
#    $GPU_CONFIG \
#    --condition-remap "file:///home/wiechula/processData/inputFilesTracking/triggeredLaser/=GLO/Config/GRPECS;file:///home/wiechula/processData/inputFilesTracking/triggeredLaser/=GLO/Config/GRPMagField;file:///home/wiechula/processData/inputFilesTracking/triggeredLaser=TPC/Calib/LaserTracks" \
#    --configKeyValues "${ARGS_ALL_CONFIG};align-geom.mDetectors=none;GPU_global.deviceType=$GPUTYPE;GPU_proc.tpcIncreasedMinClustersPerRow=500000;GPU_proc.ignoreNonFatalGPUErrors=1;$GPU_CONFIG_KEY;GPU_global.tpcTriggeredMode=1;GPU_rec_tpc.clusterError2AdditionalY=0.1;GPU_rec_tpc.clusterError2AdditionalZ=0.15;GPU_rec_tpc.clustersShiftTimebinsClusterizer=35" \
#    | o2-tpc-laser-track-filter $ARGS_ALL \
#    | o2-tpc-calib-laser-tracks  $ARGS_ALL --use-filtered-tracks ${EXTRA_CONFIG_TRACKS} --min-tfs=${min_tracks}\
#    | o2-tpc-calib-pad-raw ${ARGS_ALL} \
#    --configKeyValues ${CALIB_CONFIG} ${EXTRA_CONFIG} \
#    | o2-calibration-ccdb-populator-workflow  $ARGS_ALL \
#    --ccdb-path ${CCDB_PATH} \
#    | o2-qc ${ARGS_ALL} --config ${QC_CONFIG} --local --host ${HOST} \
#    | o2-dpl-run ${ARGS_ALL} --dds ${WORKFLOWMODE_FILE} ${GLOBALDPLOPT}


