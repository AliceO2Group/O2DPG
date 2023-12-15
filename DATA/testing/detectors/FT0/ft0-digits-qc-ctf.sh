#!/usr/bin/env bash

# Make common arguments and helper functions such as add_W available
source common/setenv.sh
source common/getCommonArgs.sh
source common/gen_topo_helper_functions.sh

if [ -z $CTF_DIR ];                  then CTF_DIR=$FILEWORKDIR; fi        # Directory where to store dictionary files

CTF_DICT="--ctf-dict $FILEWORKDIR/ctf_dictionary.root"
NTHREADS=2
# Output directory for the CTF, to write to the current dir., remove `--output-dir  $CTFOUT` from o2-ctf-writer-workflow or set to `CTFOUT=\"""\"`
# The directory must exist
ARGS_CTF="--min-file-size 500000000  --max-ctf-per-file 10000 --meta-output-dir /data/epn2eos_tool/epn2eos --append-det-to-period 0"

MYDIR="$(dirname $(readlink -f $0))"
PROXY_INSPEC="x:FT0/RAWDATA;eos:***/INFORMATION;dd:FLP/DISTSUBTIMEFRAME/0"
IN_CHANNEL="--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1'"

# TODO use add_W function from gen_topo_helper_functions.sh to assemble workflow
# as done for example in https://github.com/AliceO2Group/O2DPG/blob/master/DATA/production/calib/its-threshold-processing.sh
o2-dpl-raw-proxy ${ARGS_ALL} --readout-proxy "${IN_CHANNEL}" --dataspec "${PROXY_INSPEC}" \
| o2-ft0-flp-dpl-workflow --disable-root-output ${ARGS_ALL} --configKeyValues "$ARGS_ALL_CONFIG;" --pipeline ft0-datareader-dpl:$NTHREADS \
| o2-ft0-entropy-encoder-workflow ${ARGS_ALL} --configKeyValues "$ARGS_ALL_CONFIG;" ${CTF_DICT} \
| o2-qc ${ARGS_ALL} --local --host epn --config json://${MYDIR}/ft0-digits-ds.json \
| o2-ctf-writer-workflow ${ARGS_ALL} ${ARGS_CTF} --configKeyValues "$ARGS_ALL_CONFIG;" --onlyDet FT0 --output-dir $CTF_DIR --ctf-dict-dir $FILEWORKDIR --output-type ctf \
| o2-dpl-run $ARGS_ALL $GLOBALDPLOPT --dds ${WORKFLOWMODE_FILE} # option instead iof run to export DDS xml file
