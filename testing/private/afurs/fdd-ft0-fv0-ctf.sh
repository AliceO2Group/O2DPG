#!/usr/bin/env bash

source common/setenv.sh

SEVERITY=INFO
ARGS_ALL="--session default --severity $SEVERITY --shm-segment-id $NUMAID --shm-segment-size $SHMSIZE"
ARGS_ALL+=" --infologger-severity $SEVERITY"
#CTFOUT="/home/afurs/public/out/"
#CTFOUT="${EPN_DATA_DIR}"
if [ -z $CTF_DIR ];                  then CTF_DIR=$FILEWORKDIR; fi        # Directory where to store dictionary files
#CTFOUT=$FILEWORKDIR
#CTFOUT=$FILEWORKDIR
#FILEWORKDIR=$CTFOUT
#ARGS_ALL+=" --monitoring-backend influxdb-unix:///tmp/telegraf.sock"
ARGS_ALL_CONFIG="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null"
CTF_DICT="--ctf-dict $FILEWORKDIR/ctf_dictionary.root"
NTHREADS=2
# Output directory for the CTF, to write to the current dir., remove `--output-dir  $CTFOUT` from o2-ctf-writer-workflow or set to `CTFOUT=\"""\"`
# The directory must exist
# ARGS_CTF=""

ARGS_CTF="--min-file-size 500000000 --max-ctf-per-file 200 --meta-output-dir /data/epn2eos_tool/epn2eos"
MYDIR="$(dirname $(readlink -f $0))"
PROXY_INSPEC="digfdd:FDD/DIGITSBC/0;chanfdd:FDD/DIGITSCH/0;digft0:FT0/DIGITSBC/0;chanft0:FT0/DIGITSCH/0;digfv0:FV0/DIGITSBC/0;chanfv0:FV0/DIGITSCH/0;eos:***/INFORMATION;dd:FLP/DISTSUBTIMEFRAME"
IN_CHANNEL="--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1'"

o2-dpl-raw-proxy ${ARGS_ALL} --readout-proxy "${IN_CHANNEL}" --dataspec "${PROXY_INSPEC}" \
| o2-fdd-entropy-encoder-workflow ${ARGS_ALL} --configKeyValues "$ARGS_ALL_CONFIG;" ${CTF_DICT} \
| o2-ft0-entropy-encoder-workflow ${ARGS_ALL} --configKeyValues "$ARGS_ALL_CONFIG;" ${CTF_DICT} \
| o2-fv0-entropy-encoder-workflow ${ARGS_ALL} --configKeyValues "$ARGS_ALL_CONFIG;" ${CTF_DICT} \
| o2-ctf-writer-workflow ${ARGS_ALL} ${ARGS_CTF} --configKeyValues "$ARGS_ALL_CONFIG;" --onlyDet FDD,FT0,FV0 --output-dir $CTF_DIR --ctf-dict-dir $FILEWORKDIR --output-type ctf \
| o2-dpl-run $ARGS_ALL $GLOBALDPLOPT --dds
