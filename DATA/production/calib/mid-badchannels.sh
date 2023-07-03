#!/usr/bin/env bash

# shellcheck disable=SC1091
source common/setenv.sh

# shellcheck disable=SC1091
source common/getCommonArgs.sh

MID_PROXY_INSPEC_EOS="eos:***/INFORMATION"
MID_PROXY_INSPEC_DD="dd:FLP/DISTSUBTIMEFRAME/0"
MID_RAW_PROXY_INSPEC="A:MID/RAWDATA;$MID_PROXY_INSPEC_DD;$MID_PROXY_INSPEC_EOS"
MID_DPL_CHANNEL_CONFIG="name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1"
CONSUL_ENDPOINT="alio2-cr1-hv-con01.cern.ch:8500"
if [[ -z $CTF_CONFIG ]]; then CTF_CONFIG="--report-data-size-interval 250"; fi
if [[ -z $CTF_DIR ]]; then CTF_DIR="$FILEWORKDIR"; fi
if [[ -z $CTF_MINSIZE ]]; then CTF_MINSIZE="2000000000"; fi
if [[ -z $CTF_MAX_PER_FILE ]]; then CTF_MAX_PER_FILE="10000"; fi
if [[ -z $EPN2EOS_METAFILES_DIR ]]; then EPN2EOS_METAFILES_DIR="/dev/null"; fi
CONFIG_CTF="--output-dir \"$CTF_DIR\" $CTF_CONFIG --output-type ctf --min-file-size ${CTF_MINSIZE} --max-ctf-per-file ${CTF_MAX_PER_FILE} --onlyDet MID $CTF_MAXDETEXT --meta-output-dir $EPN2EOS_METAFILES_DIR"

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --dataspec \"$MID_RAW_PROXY_INSPEC\" --channel-config \"$MID_DPL_CHANNEL_CONFIG\" | "
WORKFLOW+="o2-mid-raw-to-digits-workflow $ARGS_ALL | "
workflow_has_parameter CTF && WORKFLOW+="o2-mid-entropy-encoder-workflow $ARGS_ALL | o2-ctf-writer-workflow $ARGS_ALL $CONFIG_CTF | "
WORKFLOW+="o2-mid-calibration-workflow $ARGS_ALL | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://o2-ccdb.internal\" --sspec-min 0 --sspec-max 0 | "
WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://alio2-cr1-flp199.cern.ch:8083\" --sspec-min 1 --sspec-max 1 --name-extention dcs | "
workflow_has_parameter QC && WORKFLOW+="o2-qc $ARGS_ALL --config consul-json://${CONSUL_ENDPOINT}/o2/components/qc/ANY/any/mid-calib-qcmn --local --host localhost | "
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ "$WORKFLOWMODE" == "print" ]; then
    echo Workflow command:
    echo "$WORKFLOW" | sed "s/| */|\n/g"
else
    # Execute the command we have assembled
    WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
    eval "$WORKFLOW"
fi
