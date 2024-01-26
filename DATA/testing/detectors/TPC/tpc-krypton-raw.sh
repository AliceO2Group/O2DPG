#!/usr/bin/env bash

source common/setenv.sh
source common/getCommonArgs.sh
source common/gen_topo_helper_functions.sh

export SHMSIZE=$(( 128 << 30 )) #  GB for the global SHMEM # for kr cluster finder


PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
CALIB_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"

NLANES=36
SESSION="default"
ARGS_FILES="keyval.output_dir=/dev/null"
HOST=localhost



if [[ ! -z ${TPC_KRYPTON_LANES:-} ]]; then
    NLANES=${TPC_KRYPTON_LANES}
fi

QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-krypton-raw-qcmn"
#QC_CONFIG="/o2/components/qc/ANY/any/tpc-krypton-raw-qcmn"



WRITER_TYPE="--writer-type EPN --meta-output-dir $EPN2EOS_METAFILES_DIR --output-dir $CALIB_DIR --max-tf-per-file 8000"

if [[ ! -z ${TPC_KRYPTON_NO_WRITEOUT:-} ]]; then
        WRITER_TYPE="--writer-type none"
fi



# TODO use add_W function from gen_topo_helper_functions.sh to assemble workflow
# as done for example in https://github.com/AliceO2Group/O2DPG/blob/master/DATA/production/calib/its-threshold-processing.sh

WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\"" "" 0
add_W o2-tpc-raw-to-digits-workflow "--ignore-grp --input-spec \"$CALIB_INSPEC\" --remove-duplicates --pedestal-url \"http://o2-ccdb.internal\"  --pipeline tpc-raw-to-digits-0:24 " "\"${ARGS_FILES}\";TPCDigitDump.LastTimeBin=446"
add_W o2-tpc-krypton-raw-filter "${WRITER_TYPE} --lanes $NLANES --threshold-max 20 --time-bins-before 20"  "\"${ARGS_FILES}\""
add_W o2-qc "--config $QC_CONFIG --local --host localhost"
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi

