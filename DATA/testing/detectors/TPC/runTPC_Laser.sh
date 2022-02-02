export GLOBAL_SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM
export GPUTYPE=HIP
export GPUMEMSIZE=$(( 24 << 30 ))
export HOSTMEMSIZE=$(( 5 << 30 ))
DISPLAY=0


#source /home/epn/runcontrol/tpc/qc_test_env.sh > /dev/null
module load O2PDPSuite > /dev/null
PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

### Comment: MAKE SURE the channels match address=ipc://@tf-builder-pipe-0

VERBOSE=""
ARGS_ALL="-b --session default --shm-segment-size $GLOBAL_SHMSIZE"
ARGS_FILES="NameConf.mDirGRP=/home/wiechula/processData/inputFilesTracking/triggeredLaser;NameConf.mDirGeom=/home/epn/odc/files/;keyval.output_dir=/dev/null"
ARGS_ALL+=" --monitoring-backend influxdb-unix:///tmp/telegraf.sock --resources-monitoring 15"


o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
    --severity warning \
    --infologger-severity warning \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "TPCDigitDump.LastTimeBin=600;$ARGS_FILES" \
    --severity warning \
    --pipeline tpc-raw-to-digits-0:32 \
    --remove-duplicates \
    --send-ce-digits \
    --infologger-severity warning \
    | o2-tpc-reco-workflow $ARGS_ALL \
    --input-type digitizer  \
    --output-type "tracks,disable-writer" \
    --disable-mc \
    --pipeline tpc-tracker:4 \
    --environment "ROCR_VISIBLE_DEVICES={timeslice0}" \
    --configKeyValues "align-geom.mDetectors=none;GPU_global.deviceType=$GPUTYPE;GPU_proc.forceMemoryPoolSize=$GPUMEMSIZE;GPU_proc.forceHostMemoryPoolSize=$HOSTMEMSIZE;GPU_proc.deviceNum=0;GPU_proc.tpcIncreasedMinClustersPerRow=500000;GPU_proc.ignoreNonFatalGPUErrors=1;$ARGS_FILES;keyval.output_dir=/dev/null" \
    --severity warning \
    | o2-tpc-laser-track-filter $ARGS_ALL --severity warning \
    | o2-tpc-calib-laser-tracks  $ARGS_ALL --use-filtered-tracks --min-tfs 50 --infologger-severity info \
    | o2-tpc-calib-pad-raw $ARGS_ALL \
    --configKeyValues "TPCCalibPulser.FirstTimeBin=450;TPCCalibPulser.LastTimeBin=550;TPCCalibPulser.NbinsQtot=150;TPCCalibPulser.XminQtot=2;TPCCalibPulser.XmaxQtot=302;TPCCalibPulser.MinimumQtot=8;TPCCalibPulser.MinimumQmax=6;TPCCalibPulser.XminT0=450;TPCCalibPulser.XmaxT0=550;TPCCalibPulser.NbinsT0=400;keyval.output_dir=/dev/null" \
    --lanes 36 \
    --calib-type ce \
    --publish-after-tfs 50 \
    --max-events 50 \
    | o2-calibration-ccdb-populator-workflow  $ARGS_ALL \
    --ccdb-path http://ccdb-test.cern.ch:8080 \
    | o2-dpl-run $ARGS_ALL --dds
    #| o2-tpc-calib-laser-tracks  $ARGS_ALL --use-filtered-tracks --min-tfs 15 --write-debug \
