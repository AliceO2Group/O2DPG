#!/usr/bin/env bash

# shellcheck disable=SC1091
source common/setenv.sh

source common/getCommonArgs.sh

MID_PROXY_INSPEC_EOS="eos:***/INFORMATION"
MID_PROXY_INSPEC_DD="dd:FLP/DISTSUBTIMEFRAME/0"
MID_RAW_PROXY_INSPEC="A:MID/RAWDATA;$MID_PROXY_INSPEC_DD;$MID_PROXY_INSPEC_EOS"
MID_DIGITS_PROXY_INSPEC="A:MID/DATA/0;B:MID/DATAROF/0;$MID_PROXY_INSPEC_DD;$MID_PROXY_INSPEC_EOS"
MID_DPL_CHANNEL_CONFIG="name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1"
export FILEWORKDIR="/home/dstocco/config" #FIXME: this should be removed from gen_topo.sh
MID_RAW_TO_DIGITS_OPTS="--feeId-config-file \"$FILEWORKDIR/feeId_mapper.txt\""
MID_CTF_WRITER_OPTS="--output-dir \"$CTF_DIR\" --onlyDet \"MID\" --no-grp --min-file-size 500000000 --max-ctf-per-file 10000 --meta-output-dir \"$CTF_METAFILES_DIR\""
MID_EPN_QC_OPTS="--local --host epn"
