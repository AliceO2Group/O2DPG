#!/usr/bin/env bash

# Make common arguments and helper functions such as add_W available
source common/setenv.sh
source common/getCommonArgs.sh
source common/gen_topo_helper_functions.sh

# Define input data required by DPL (in this case all RAWDATA from TPC)
PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

# Start with an empty workflow
WORKFLOW=
# Add required workflows via add_W helper (usage: add_W [BINARY] [COMMAND_LINE_OPTIONS] [CONFIG_KEY_VALUES] [Add ARGS_ALL_CONFIG, optional, default = 1])
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --readout-proxy \"--channel-config \\\"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\\\"\"" "" 0
add_W o2-tpc-raw-to-digits-workflow "--input-spec \"$PROXY_INSPEC\" --remove-duplicates" "TPCDigitDump.LastTimeBin=1000"

# Finally add the o2-dpl-run workflow manually, allow for either printing the workflow or creating a topology (default)
WORKFLOW+="o2-dpl-run $GLOBALDPLOPT $ARGS_ALL"
[[ $WORKFLOWMODE != "print" ]] && WORKFLOW+=" --${WORKFLOWMODE} ${WORKFLOWMODE_FILE:-}"
[[ $WORKFLOWMODE == "print" || "${PRINT_WORKFLOW:-}" == "1" ]] && echo "#Workflow command:\n\n${WORKFLOW}\n" | sed -e "s/\\\\n/\n/g" -e"s/| */| \\\\\n/g" | eval cat $( [[ $WORKFLOWMODE == "dds" ]] && echo '1>&2')
if [[ $WORKFLOWMODE != "print" ]]; then eval $WORKFLOW; else true; fi
