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
ARGS_ALL_CONFIG="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR;NameConf.mDirCollContext=$FILEWORKDIR;NameConf.mDirMatLUT=$FILEWORKDIR;keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null;$ALL_EXTRA_CONFIG"

PROXY_INSPEC="A:ITS/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"
PROXY_OUTSPEC="downstreamdigits:ITS/DIGITS/0;downstreamdigitsrof:ITS/DIGITSROF/0;downstreamcalib:ITS/GBTCALIB/0"

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --dataspec \"$PROXY_INSPEC\" --channel-config \"name=readout-proxy,type=pull,method=connect,address=ipc://@$INRAWCHANNAME,rateLogging=0,transport=shmem\" | "
WORKFLOW+="o2-itsmft-stf-decoder-workflow ${ARGS_ALL} --configKeyValues \"$ARGS_ALL_CONFIG\" --nthreads 4 --no-clusters --no-cluster-patterns --enable-calib-data --digits | "
WORKFLOW+="o2-dpl-output-proxy ${ARGS_ALL} --dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name its-thr-input-proxy --channel-config \"name=its-thr-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0\" | "
WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE"
  eval $WORKFLOW
fi
