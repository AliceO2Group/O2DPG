#!/usr/bin/env bash

source common/setenv.sh

SEVERITY=warning
source common/getCommonArgs.sh

PROXY_INSPEC="A:TPC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" --inject-missing-data \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1'" \
    | o2-tpc-raw-to-digits-workflow $ARGS_ALL \
    --input-spec "$PROXY_INSPEC"  \
    --remove-duplicates \
    --configKeyValues "$ARGS_ALL_CONFIG;TPCDigitDump.LastTimeBin=1000;" \
    | o2-dpl-run $ARGS_ALL $GLOBALDPLOPT --dds ${WORKFLOWMODE_FILE}
