#!/usr/bin/env bash

# shellcheck disable=SC1091
source common/setenv.sh

SEVERITY=warning
INFOLOGGER_SEVERITY=warning
ARGS_ALL="--session default --severity $SEVERITY --shm-segment-size $SHMSIZE"
ARGS_ALL+=" --infologger-severity $INFOLOGGER_SEVERITY"
ARGS_ALL+=" --monitoring-backend influxdb-unix:///tmp/telegraf.sock --resources-monitoring 60"

ARGS_ALL_CONFIG="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null;$ALL_EXTRA_CONFIG"

MID_PROXY_INSPEC_EOS="eos:***/INFORMATION"
MID_PROXY_INSPEC_DD="dd:FLP/DISTSUBTIMEFRAME/0"
MID_RAW_PROXY_INSPEC="A:MID/RAWDATA;$MID_PROXY_INSPEC_DD;$MID_PROXY_INSPEC_EOS"
MID_DIGITS_PROXY_INSPEC="A:MID/DATA/0;B:MID/DATAROF/0;$MID_PROXY_INSPEC_DD;$MID_PROXY_INSPEC_EOS"
MID_DPL_CHANNEL_CONFIG="name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1"
export FILEWORKDIR="/home/dstocco/config" #FIXME: this should be removed from gen_topo.sh
MID_RAW_TO_DIGITS_OPTS="--feeId-config-file \"$FILEWORKDIR/feeId_mapper.txt\""
MID_CTF_WRITER_OPTS="--output-dir \"$CTF_DIR\" --onlyDet \"MID\" --no-grp --min-file-size 500000000 --max-ctf-per-file 10000 --meta-output-dir \"$CTF_METAFILES_DIR\""
MID_EPN_QC_OPTS="--local --host epn"
