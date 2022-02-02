export GLOBAL_SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM # for kr cluster finder
DISPLAY=0

module load O2PDPSuite > /dev/null

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"

NLANES=36
SESSION="default"
PIPEADD="0"
ARGS_ALL="-b --session $SESSION  --shm-segment-size $GLOBAL_SHMSIZE"
ARGS_FILES="NameConf.mDirGRP=/home/epn/odc/files/;NameConf.mDirGeom=/home/epn/odc/files/;keyval.output_dir=/dev/null"
ARGS_ALL+=" --monitoring-backend influxdb-unix:///tmp/telegraf.sock --resources-monitoring 15"
QC_CONFIG="consul-json://aliecs.cern.ch:8500/o2/components/qc/ANY/any/tpc-full-qcmn-krypton"




o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-${PIPEADD},transport=shmem,rateLogging=1'" \
    --severity warning \
    --infologger-severity warning \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "$ARGS_FILES" \
    --remove-duplicates \
    --pipeline tpc-raw-to-digits-0:12 \
    --severity warning \
    --infologger-severity warning \
    | o2-tpc-krypton-clusterer $ARGS_ALL \
    --lanes $NLANES \
    --severity info \
    --configKeyValues "$ARGS_FILES" \
    --infologger-severity warning \
    --configFile="/home/wiechula/processData/inputFilesTracking/krypton/krBoxCluster.largeBox.cuts.krMap.ini" \
    --writer-type EPN \
    --meta-output-dir /data/epn2eos_tool/epn2eos/ \
    --output-dir /data/tf/raw \
    --max-tf-per-file 2000 \
    | o2-qc $ARGS_ALL --config $QC_CONFIG --local --host localhost \
    | o2-dpl-run $ARGS_ALL --dds

