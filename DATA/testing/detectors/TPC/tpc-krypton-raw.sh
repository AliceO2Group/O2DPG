export GLOBAL_SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM # for kr cluster finder
DISPLAY=0

module load O2PDPSuite > /dev/null 
#source /home/rmunzer/scripts/qc_test_env.sh > /dev/null
#source /home/wiechula/software/alicesw.global/env.sh > /dev/null

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"

NLANES=36
SESSION="default"
PIPEADD="0"
ARGS_ALL="-b --session $SESSION  --shm-segment-size $GLOBAL_SHMSIZE" 
ARGS_FILES="NameConf.mDirGRP=/home/epn/odc/files/;NameConf.mDirGeom=/home/epn/odc/files/;keyval.output_dir=/dev/null"
ARGS_ALL+=" --monitoring-backend influxdb-unix:///tmp/telegraf.sock --resources-monitoring 15"
HOST=localhost

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy '--channel-config "name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1"' \
    --severity warning \
    --infologger-severity warning \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "$ARGS_FILES" \
    --remove-duplicates \
    --pipeline tpc-raw-to-digits-0:24 \
    --severity info \
    --infologger-severity warning \
    --pedestal-url "http://ccdb-test.cern.ch:8080" \
    | o2-tpc-krypton-raw-filter $ARGS_ALL \
    --configKeyValues "$ARGS_FILES" \
    --lanes $NLANES \
    --severity info \
    --infologger-severity warning \
    --writer-type EPN \
    --meta-output-dir /data/epn2eos_tool/epn2eos/ \
    --output-dir /data/tf/raw \
    --threshold-max 20 \
    --max-tf-per-file 8000 \
    --time-bins-before 20 \
    | o2-qc $ARGS_ALL --config json:///home/rmunzer/odc/config/tpcQCTasks_multinode_raw_epn_merger.json --local --host localhost \
    | o2-dpl-run $ARGS_ALL --dds

#--ccdb-path "test" \

