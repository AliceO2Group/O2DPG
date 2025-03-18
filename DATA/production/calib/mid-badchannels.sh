#!/usr/bin/env bash

# shellcheck disable=SC1091
# Common environment. Notice that this sources common/gen_topo_helper_functions.sh
source common/setenv.sh

# Set general arguments
source common/getCommonArgs.sh

MID_PROXY_INSPEC_EOS="eos:***/INFORMATION"
MID_PROXY_INSPEC_DD="dd:FLP/DISTSUBTIMEFRAME/0"
MID_RAW_PROXY_INSPEC="A:MID/RAWDATA;$MID_PROXY_INSPEC_DD;$MID_PROXY_INSPEC_EOS"
MID_DPL_CHANNEL_CONFIG="name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1"

if [[ -z $CTF_CONFIG ]]; then CTF_CONFIG="--report-data-size-interval 250"; fi
if [[ -z $CTF_DIR ]]; then CTF_DIR="$FILEWORKDIR"; fi
if [[ -z $CTF_MINSIZE ]]; then CTF_MINSIZE="2000000000"; fi
if [[ -z $CTF_MAX_PER_FILE ]]; then CTF_MAX_PER_FILE="10000"; fi
if [[ -z $EPN2EOS_METAFILES_DIR ]]; then EPN2EOS_METAFILES_DIR="/dev/null"; fi
CONFIG_CTF="--output-dir \"$CTF_DIR\" $CTF_CONFIG --output-type ctf --min-file-size ${CTF_MINSIZE} --max-ctf-per-file ${CTF_MAX_PER_FILE} --onlyDet MID $CTF_MAXDETEXT --meta-output-dir $EPN2EOS_METAFILES_DIR"

# CCDB destination for uploads
if [[ -z ${CCDB_POPULATOR_UPLOAD_PATH} ]]; then
    if [[ $RUNTYPE == "SYNTHETIC" || "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" ]]; then
        CCDB_POPULATOR_UPLOAD_PATH="http://ccdb-test.cern.ch:8080"
        CCDB_POPULATOR_UPLOAD_PATH_DCS="$CCDB_POPULATOR_UPLOAD_PATH"
    else
        CCDB_POPULATOR_UPLOAD_PATH="http://o2-ccdb.internal"
        CCDB_POPULATOR_UPLOAD_PATH_DCS="$DCSCCDBSERVER_PERS"
    fi
fi
if [[ "${GEN_TOPO_VERBOSE:-}" == "1" ]]; then
    echo "CCDB_POPULATOR_UPLOAD_PATH = $CCDB_POPULATOR_UPLOAD_PATH" 1>&2
    echo "CCDB_POPULATOR_UPLOAD_PATH_DCS = $CCDB_POPULATOR_UPLOAD_PATH_DCS" 1>&2
fi

WORKFLOW=""
add_W o2-dpl-raw-proxy "--dataspec \"$MID_RAW_PROXY_INSPEC\" --channel-config \"$MID_DPL_CHANNEL_CONFIG\"" "" 0
add_W o2-mid-raw-to-digits-workflow "" "" 0
workflow_has_parameter CTF && {
    add_W o2-mid-entropy-encoder-workflow "" "" 0
    add_W o2-ctf-writer-workflow "$CONFIG_CTF" "" 0
}
add_W o2-mid-calibration-workflow "" "" 0
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path=\"$CCDB_POPULATOR_UPLOAD_PATH\" --sspec-min 0 --sspec-max 0"
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path=\"$CCDB_POPULATOR_UPLOAD_PATH_DCS\" --sspec-min 1 --sspec-max 1 --name-extention dcs"
workflow_has_parameter QC && add_QC_from_apricot "components/qc/ANY/any/mid-calib-qcmn" "--local --host localhost"
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ "$WORKFLOWMODE" == "print" ]; then
    echo Workflow command:
    echo "$WORKFLOW" | sed "s/| */|\n/g"
else
    # Execute the command we have assembled
    WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
    eval "$WORKFLOW"
fi
