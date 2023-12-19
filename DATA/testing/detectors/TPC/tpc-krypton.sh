#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh


export GLOBAL_SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM # for kr cluster finder

if [ $NUMAGPUIDS != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"


NLANES=1
SESSION="default"

ARGS_FILES="keyval.output_dir=/dev/null"

QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-krypton-qcmn"

WRITER_TYPE="--writer-type EPN --meta-output-dir $EPN2EOS_METAFILES_DIR --output-dir $CALIB_DIR"

if [[ ! -z ${TPC_KRYPTON_NO_WRITEOUT:-} ]]; then
	WRITER_TYPE="--writer-type none"
fi

# TODO use add_W function from gen_topo_helper_functions.sh to assemble workflow
# as done for example in https://github.com/AliceO2Group/O2DPG/blob/master/DATA/production/calib/its-threshold-processing.sh
o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" --inject-missing-data \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --ignore-grp \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "$ARGS_FILES" \
    --remove-duplicates \
    --pipeline tpc-raw-to-digits-0:20 \
    | o2-tpc-krypton-clusterer $ARGS_ALL \
    ${WRITER_TYPE} \
    --lanes $NLANES \
    --configKeyValues "$ARGS_FILES" \
    --configFile="/home/wiechula/processData/inputFilesTracking/krypton/krBoxCluster.largeBox.cuts.krMap.ini" \
    | o2-qc $ARGS_ALL --config $QC_CONFIG --local --host localhost \
    | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE} ${GLOBALDPLOPT}
