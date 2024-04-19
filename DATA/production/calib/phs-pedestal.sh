#!/usr/bin/env bash

source common/setenv.sh

source common/getCommonArgs.sh

source common/gen_topo_helper_functions.sh

max_statistics=5000
if [[ ! -z ${PHS_MAX_STATISTICS:-} ]]; then
  max_statistics=$PHS_MAX_STATISTICS
fi

PROXY_INSPEC="A:PHS/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"


push_ccdb_path="http://o2-ccdb.internal"
pull_ccdb_path="http://o2-ccdb.internal"
if [[ ! -z ${PUHS_CCDB_PATH:-} ]]; then
  push_ccdb_path=$PUHS_CCDB_PATH
fi

if [[ ! -z ${PULL_CCDB_PATH:-} ]]; then
  pull_ccdb_path=$PULL_CCDB_PATH
fi

if [[ $RUNTYPE == "SYNTHETIC" || "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" ]]; then
  push_ccdb_path="http://ccdb-test.cern.ch:8080"
fi

QC_CONFIG="/o2/components/qc/ANY/any/phs-pedestal-qc"

WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\"" "" 0
add_W o2-phos-reco-workflow "--input-type raw --output-type cells --pedestal on --disable-root-input --disable-root-output --condition-backend ${pull_ccdb_path}" 
add_W o2-phos-calib-workflow "--pedestals --statistics ${max_statistics} --forceupdate"
#add_W o2-calibration-ccdb-populator-workflow "--ccdb-path ${push_ccdb_path}"
workflow_has_parameter QC && add_QC_from_consul "${QC_CONFIG}"
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path ${push_ccdb_path}"

WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
    echo Workflow command:
    echo $WORKFLOW | sed "s/| */|\n/g"
else
    # Execute the command we have assembled
    WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
    eval $WORKFLOW
fi

#o2-dpl-raw-proxy $ARGS_ALL \
#		 --dataspec "$PROXY_INSPEC" --inject-missing-data \
#		 --readout-proxy '--channel-config "name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1"' \
#    | o2-phos-reco-workflow $ARGS_ALL \
#			    --input-type raw  \
#			    --output-type cells \
#			    --pedestal on \
#			    --disable-root-input \
#			    --disable-root-output \
#    | o2-phos-calib-workflow $ARGS_ALL \
#			     --pedestals \
#			     --statistics $PHS_MAX_STATISTICS \
#			     --configKeyValues "NameConf.mCCDBServer=${PHS_CCDB_PATH}" \
#			     --forceupdate \
#    | o2-qc $ARGS_ALL \
#            --config $QC_CONFIG \
#    | o2-calibration-ccdb-populator-workflow $ARGS_ALL \
#					     --ccdb-path $PHS_CCDB_PATH \
#    | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE}
