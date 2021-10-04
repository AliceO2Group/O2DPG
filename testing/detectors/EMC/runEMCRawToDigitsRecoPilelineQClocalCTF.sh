#!/usr/bin/env bash

source /home/mfasel/alice/O2DataProcessing/common/setenv.sh

PROXY_INSPEC="A:EMC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

NCPU=20 #$(grep ^cpu\\scores /proc/cpuinfo | uniq |  awk '{print $4}')
ARGS_ALL="-b --session default --shm-segment-size $SHMSIZE"
#HOST='$(hostname -s)-ib'
HOST=epn

QC_CONFIG=consul-json://aliecs.cern.ch:8500/o2/components/qc/ANY/any/emc-qcmn-flpepn
#QC_CONFIG=json:///home/epn/odc/files/emcQCTasks_multinode.json
INFOLOGGER_SEVERITY_RAWPROXY=warning
SEVERITY_RAWPROXY=warning
INFOLOGGER_SEVERITY=warning
SEVERITY=warning
INFOLOGGER_SEVERITY_QC=warning
SEVERITY_QC=warning
CTF_OUTDIR=/tmp/datadist/ctf
CTF_DICTDIR=/home/epn/odc/files/ctf_dictionary.root

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
    --severity $SEVERITY_RAWPROXY \
    --infologger-severity $INFOLOGGER_SEVERITY_RAWPROXY \
    | o2-emcal-reco-workflow $ARGS_ALL \
    --input-type raw \
    --output-type cells \
    --disable-root-input \
    --disable-root-output \
    --disable-mc \
    --EMCALRawToCellConverterSpec "--fitmethod=\"gamma2\" --maxmessage=10" \
    --severity $SEVERITY \
    --infologger-severity $INFOLOGGER_SEVERITY \
    --pipeline EMCALRawToCellConverterSpec:$NCPU \
    | o2-qc $ARGS_ALL \
    --config $QC_CONFIG \
    --local \
    --host $HOST \
    --severity $SEVERITY_QC \
    --infologger-severity $INFOLOGGER_SEVERITY_QC \
    | o2-emcal-entropy-encoder-workflow $ARGS_ALL \
    --ctf-dict $CTF_DICTDIR \
    | o2-ctf-writer-workflow $ARGS_ALL \
    --onlyDet EMC \
    --no-grp \
    --output-dir $CTF_OUTDIR \
    | o2-dpl-run $ARGS_ALL --dds