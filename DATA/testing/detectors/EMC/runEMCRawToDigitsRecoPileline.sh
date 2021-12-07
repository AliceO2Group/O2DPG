#!/usr/bin/env bash

PROXY_INSPEC="A:EMC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

NCPU=12 #$(grep ^cpu\\scores /proc/cpuinfo | uniq |  awk '{print $4}')
ARGS_ALL="-b --session default --shm-segment-size $SHMSIZE"
#HOST='$(hostname -s)-ib'

INFOLOGGER_SEVERITY_RAWPROXY=warning
SEVERITY_RAWPROXY=warning
INFOLOGGER_SEVERITY=warning
SEVERITY=warning

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
    --severity $INFOLOGGER_SEVERITY_RAWPROXY \
    --infologger-severity $SEVERITY_RAWPROXY \
    | o2-emcal-reco-workflow $ARGS_ALL \
    --input-type raw \
    --output-type cells \
    --disable-root-input \
    --disable-root-output \
    --EMCALRawToCellConverterSpec "--fitmethod=\"gamma2\" --maxmessage=10" \
    --disable-mc \
    --severity $SEVERITY \
    --infologger-severity $INFOLOGGER_SEVERITY \
    --pipeline EMCALRawToCellConverterSpec:$NCPU \
    | o2-dpl-run $ARGS_ALL --dds