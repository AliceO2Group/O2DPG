#!/usr/bin/env bash

PROXY_INSPEC="A:EMC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

NCPU=12 #$(grep ^cpu\\scores /proc/cpuinfo | uniq |  awk '{print $4}')
ARGS_ALL="-b --session default --shm-segment-size $SHMSIZE"
#HOST='$(hostname -s)-ib'
HOST=epn

#QC_CONFIG=consul-json://alio2-cr1-hv-aliecs:8500/o2/components/qc/ANY/any/emc-qcmn-epn
QC_CONFIG=json:///home/epn/odc/files/emcQCTasks_multinode.json
INFOLOGGER_SEVERITY_RAWPROXY=warning
SEVERITY_RAWPROXY=warning
INFOLOGGER_SEVERITY=warning
SEVERITY=warning
INFOLOGGER_SEVERITY_QC=warning
SEVERITY_QC=warning

# CTF compression dictionary
CTF_DICT="${FILEWORKDIR}/ctf_dictionary.root"
# min file size for CTF (accumulate CTFs until it is reached)
CTF_MINSIZE="2000000"

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
    --severity $SEVERITY_QC \
    --infologger-severity $INFOLOGGER_SEVERITY_QC \
    | o2-emcal-entropy-encoder-workflow $ARGS_ALL \
    --ctf-dict "${CTF_DICT}" \
    | o2-ctf-writer-workflow $ARGS_ALL \
    --configKeyValues "${CONFKEYVAL}" \
    --no-grp \
    --onlyDet $WORKFLOW_DETECTORS \
    --ctf-dict "${CTF_DICT}" \
    --output-dir $CTF_DIR \
    --meta-output-dir ${CTF_METAFILES_DIR} \
    --min-file-size "${CTF_MINSIZE}" \
    | o2-dpl-run $ARGS_ALL --dds
