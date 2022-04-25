#!/usr/bin/env bash

source common/setenv.sh

calibration_node="epn003-ib:30453"

SEVERITY=warning
source common/getCommonArgs.sh
CTF_DICT="--ctf-dict $FILEWORKDIR/ctf_dictionary.root"
PROXY_INSPEC="x:TOF/CRAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
NTHREADS=1
# Output directory for the CTF, to write to the current dir., remove `--output-dir  $CTFOUT` from o2-ctf-writer-workflow or set to `CTFOUT=\"""\"`
# The directory must exist
CTFOUT="/home/fnoferin/public/out/"
MYDIR="$(dirname $(readlink -f $0))"
OUT_CHANNEL="name=downstream,method=connect,address=tcp://${calibration_node},type=push,transport=zeromq"
PROXY_OUTSPEC="dd:FLP/DISTSUBTIMEFRAME;calclus:TOF/INFOCALCLUS;cosmics:TOF/INFOCOSMICS;trkcos:TOF/INFOTRACKCOS;trksiz:TOF/INFOTRACKSIZE"


o2-dpl-raw-proxy ${ARGS_ALL} --dataspec "${PROXY_INSPEC}" \
--readout-proxy "--channel-config 'name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=1'" \
| o2-tof-reco-workflow --input-type raw --output-type clusters \
${ARGS_ALL} --configKeyValues "$ARGS_ALL_CONFIG;" \
--disable-root-output --calib-cluster --cluster-time-window 10000 --cosmics \
--pipeline "tof-compressed-decoder:${NTHREADS},TOFClusterer:${NTHREADS},tof-entropy-encoder:${NTHREADS}" \
| o2-dpl-output-proxy ${ARGS_ALL} --channel-config ${OUT_CHANNEL} --dataspec ${PROXY_OUTSPEC} \
| o2-dpl-run $ARGS_ALL $GLOBALDPLOPT --dds # option instead iof run to export DDS xml file
