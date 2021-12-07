#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
ARGS_ALL="--session default --severity $SEVERITY --shm-segment-size $SHMSIZE $ARGS_ALL_EXTRA"
ARGS_ALL+=" --infologger-severity $INFOLOGGER_SEVERITY"
ARGS_ALL+=" --monitoring-backend influxdb-unix:///tmp/telegraf.sock --resources-monitoring 60"
if [ $SHMTHROW == 0 ]; then
  ARGS_ALL+=" --shm-throw-bad-alloc 0"
fi
if [ $NORATELOG == 1 ]; then
  ARGS_ALL+=" --fairmq-rate-logging 0"
fi
ARGS_ALL_CONFIG="HBFUtils.nHBFPerTF=128;NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null;$ALL_EXTRA_CONFIG"

PROXY_INSPEC="x:TOF/CRAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
NTHREADS=1
PROXY_OUTSPEC="calclus:TOF/INFOCALCLUS;cosmics:TOF/INFOCOSMICS;trkcos:TOF/INFOTRACKCOS;trksiz:TOF/INFOTRACKSIZE"
MYDIR="$(dirname $(readlink -f $0))/../../testing/detectors/TOF"

WORKFLOW="o2-dpl-raw-proxy ${ARGS_ALL} --dataspec \"$PROXY_INSPEC\" --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,transport=shmem,rateLogging=0\" | "
WORKFLOW+="o2-tof-reco-workflow --input-type raw --output-type clusters ${ARGS_ALL} --configKeyValues \"$ARGS_ALL_CONFIG\" --disable-root-output --calib-cluster --cluster-time-window 10000 --cosmics --pipeline \"tof-compressed-decoder:${NTHREADS},TOFClusterer:${NTHREADS}\" | "
WORKFLOW+="o2-qc ${ARGS_ALL} --config json://${MYDIR}/qc-full.json --local --host epn | "
WORKFLOW+="o2-dpl-output-proxy ${ARGS_ALL} --dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name tof-time-calib-input-proxy --channel-config \"name=tof-time-calib-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0\" | "
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE"
  eval $WORKFLOW
fi
