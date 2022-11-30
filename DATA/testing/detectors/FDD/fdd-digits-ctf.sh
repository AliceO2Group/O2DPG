#!/usr/bin/env bash

source common/setenv.sh

SEVERITY=WARNING
source common/getCommonArgs.sh
if [ -z $CTF_DIR ];                  then CTF_DIR=$FILEWORKDIR; fi        # Directory where to store dictionary files
CTF_DICT="--ctf-dict $FILEWORKDIR/ctf_dictionary.root"
NTHREADS=2
# Output directory for the CTF, to write to the current dir., remove `--output-dir  $CTFOUT` from o2-ctf-writer-workflow or set to `CTFOUT=\"""\"`
# The directory must exist
ARGS_CTF="--min-file-size 500000000  --max-ctf-per-file 10000 --meta-output-dir /data/epn2eos_tool/epn2eos --append-det-to-period 0"

MYDIR="$(dirname $(readlink -f $0))"
PROXY_INSPEC="x:FDD/RAWDATA;eos:***/INFORMATION;dd:FLP/DISTSUBTIMEFRAME/0"
IN_CHANNEL="--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1'"

o2-dpl-raw-proxy ${ARGS_ALL} --readout-proxy "${IN_CHANNEL}" --dataspec "${PROXY_INSPEC}" \
| o2-fdd-flp-dpl-workflow --disable-root-output ${ARGS_ALL} --configKeyValues "$ARGS_ALL_CONFIG;" --pipeline fdd-datareader-dpl:$NTHREADS \
| o2-fdd-entropy-encoder-workflow ${ARGS_ALL} --configKeyValues "$ARGS_ALL_CONFIG;" ${CTF_DICT} \
| o2-ctf-writer-workflow ${ARGS_ALL} ${ARGS_CTF} --configKeyValues "$ARGS_ALL_CONFIG;" --onlyDet FDD --output-dir $CTF_DIR --ctf-dict-dir $FILEWORKDIR --output-type ctf \
| o2-dpl-run $ARGS_ALL $GLOBALDPLOPT --dds ${WORKFLOWMODE_FILE} # option instead iof run to export DDS xml file
