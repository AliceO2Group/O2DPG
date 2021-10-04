#!/usr/bin/env bash

source /home/mfasel/alice/O2DataProcessing/common/setenv.sh

DISPLAY=0

PROXY_INSPEC="A:EMC/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

### Comment: MAKE SURE the channels match address=ipc://@tf-builder-pipe-0

hash=$1

VERBOSE=""
NCPU=12 #$(grep ^cpu\\scores /proc/cpuinfo | uniq |  awk '{print $4}')
ARGS_ALL="-b --session default --shm-segment-size $SHMSIZE"
#HOST='$(hostname -s)-ib'

CTF_OUTDIR=/tmp/datadist/ctf
CTF_DICTDIR=/home/epn/odc/files/ctf_dictionary.root

o2-dpl-raw-proxy $ARGS_ALL \
    --dataspec "$PROXY_INSPEC" \
    --readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1'" \
    --severity info \
    --infologger-severity info \
    | o2-emcal-reco-workflow $ARGS_ALL \
    --input-type raw \
    --output-type cells \
    --disable-root-input \
    --disable-root-output \
    --disable-mc \
    --EMCALRawToCellConverterSpec "--fitmethod=\"gamma2\" --maxmessage=10" \
    --severity warning \
    --infologger-severity warning \
    --pipeline EMCALRawToCellConverterSpec:8 \
    | o2-emcal-entropy-encoder-workflow $ARGS_ALL \
    --ctf-dict $CTF_DICTDIR \
    | o2-ctf-writer-workflow $ARGS_ALL \
    --onlyDet EMC \
    --no-grp \
    --output-dir $CTF_OUTDIR \
    | o2-dpl-run $ARGS_ALL --dds