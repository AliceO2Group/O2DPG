#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh 

export SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM # for kr cluster finder

if [ $NUMAGPUIDS != 0 ]; then
  ARGS_ALL+=" --child-driver 'numactl --membind $NUMAID --cpunodebind $NUMAID'"
fi

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

NLANES=36
SESSION="default"
PIPEADD="0"
ARGS_FILES="NameConf.mDirGRP=/home/epn/odc/files/;NameConf.mDirGeom=/home/epn/odc/files/;keyval.output_dir=/dev/null"

HOST=localhost

QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-raw-qcmn"


o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" --inject-missing-data \
    --readout-proxy '--channel-config "name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1"' \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$CALIB_INSPEC"  \
    --configKeyValues "$ARGS_FILES" \
    --remove-duplicates \
    --pipeline tpc-raw-to-digits-0:24 \
    | o2-tpc-krypton-raw-filter $ARGS_ALL \
    --configKeyValues "$ARGS_FILES" \
    --lanes $NLANES \
    --writer-type EPN \
    --meta-output-dir $EPN2EOS_METAFILES_DIR \
    --output-dir $CALIB_DIR \
    --threshold-max 20 \
    --max-tf-per-file 8000 \
    --time-bins-before 20 \
    --max-time-bins 650 \
    | o2-qc $ARGS_ALL --config ${QC_CONFIG} --local --host $HOST \
    | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE} ${GLOBALDPLOPT}
