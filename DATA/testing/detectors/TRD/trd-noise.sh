#!/usr/bin/env bash

# Make common arguments and helper functions such as add_W available
source common/setenv.sh
source common/getCommonArgs.sh
source common/gen_topo_helper_functions.sh


# Define input data required by DPL (in this case all RAWDATA from TRD)
PROXY_INSPEC="A:TRD/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

# Allow for setting external options
if [ -z $TRD_CCDB_PATH ]; then
  TRD_CCDB_PATH="http://o2-ccdb.internal"
fi
if [ -z $TRD_REJECTION_FACTOR ]; then
  TRD_REJECTION_FACTOR=4
fi
if [ -z $TRD_N_READERS ]; then
  TRD_N_READERS=16
fi

# Start with an empty workflow
WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --readout-proxy \"--channel-config \\\"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\\\"\"" "" 0
add_W o2-trd-datareader "--disable-root-output --every-nth-tf $TRD_REJECTION_FACTOR --pipeline trd-datareader:$TRD_N_READERS"
add_W o2-calibration-trd-workflow "--noise --calib-dds-collection-index 0"
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path $TRD_CCDB_PATH"

# Finally add the o2-dpl-run workflow manually, allow for either printing the workflow or creating a topology (default)
WORKFLOW+="o2-dpl-run $GLOBALDPLOPT $ARGS_ALL"
[[ $WORKFLOWMODE != "print" ]] && WORKFLOW+=" --${WORKFLOWMODE} ${WORKFLOWMODE_FILE:-}"
[[ $WORKFLOWMODE == "print" || "${PRINT_WORKFLOW:-}" == "1" ]] && echo "#Workflow command:\n\n${WORKFLOW}\n" | sed -e "s/\\\\n/\n/g" -e"s/| */| \\\\\n/g" | eval cat $( [[ $WORKFLOWMODE == "dds" ]] && echo '1>&2')
if [[ $WORKFLOWMODE != "print" ]]; then eval $WORKFLOW; else true; fi
