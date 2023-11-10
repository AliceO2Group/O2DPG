#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh 


export GLOBAL_SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM # for kr cluster finder

if [ $NUMAGPUIDS != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"


NLANES=1
SESSION="default"

ARGS_FILES="NameConf.mDirGRP=/home/epn/odc/files/;NameConf.mDirGeom=/home/epn/odc/files/;keyval.output_dir=/dev/null"

QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-krypton-qcmn"




o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" --inject-missing-data \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "$ARGS_FILES" \
    --remove-duplicates \
    --pipeline tpc-raw-to-digits-0:12 \
    | o2-tpc-krypton-clusterer $ARGS_ALL \
    --lanes $NLANES \
    --configKeyValues "$ARGS_FILES" \
    --configFile="/home/wiechula/processData/inputFilesTracking/krypton/krBoxCluster.largeBox.cuts.krMap.ini" \
    --writer-type EPN \
    --meta-output-dir $EPN2EOS_METAFILES_DIR \
    --output-dir $CALIB_DIR \
    | o2-qc $ARGS_ALL --config $QC_CONFIG --local --host localhost \
    | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE} ${GLOBALDPLOPT}
