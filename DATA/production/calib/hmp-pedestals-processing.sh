#!/bin/bash

# ------------------------------------------------------------------------
#         ALICE HMPID detector
# Workflow to calculate pedestals   v.0.2  = 2/03/2022
#
#  Extra Env Variables:
#     HMP_SIGMACUT : The value of sigams for the threshold cut [=4]
#     HMP_CCDB_REC : True if we want the recording into ALICE CCDB
#     HMP_PED_TAG :  A string that tags the pedestals [=Latest]
#
#
#
#   Auth. A.Franco  - INFN  Sez.BARI - ITALY
# ------------------------------------------------------------------------

source common/setenv.sh
# env  > /home/fap/dump_env.txt

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
ARGS_ALL_CONFIG="NameConf.mDirGRP=$FILEWORKDIR;NameConf.mDirGeom=$FILEWORKDIR;NameConf.mDirCollContext=$FILEWORKDIR;NameCo$

# Define the Input/Output streams
PROXY_INSPEC="A:HMP/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"
PROXY_OUTSPEC="A:HMP/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0"

# assign the HMP extra Env Vars.
if [ -z ${HMP_SIGMACUT+x} ];
then
    HMP_SIGMACUT="4"
fi
if [ -z ${HMP_NODCSCCDB_REC+x} ];
then
    HMP_NODCSCCDB_REC="false"
else
    HMP_NODCSCCDB_REC="true"
fi
if [ -z ${HMP_CCDB_REC+x} ];
then
    HMP_CCDB_REC="false"
else
    HMP_CCDB_REC="true"
fi
if [ -z ${HMP_FILES_REC+x} ];
then
    HMP_FILES_REC="false"
else
    HMP_FILES_REC="true"
fi
if [ -z ${HMP_PED_TAG+x} ];
then
    HMP_PED_TAG="Latest"
fi

#  Here we compose the workflow
WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --dataspec \"$PROXY_INSPEC\" --channel-config \"name=readout-proxy,type=pull,"
WORKFLOW+="method=connect,address=ipc://@$INRAWCHANNAME,rateLogging=1,transport=shmem\" | "

WORKFLOW+="o2-hmpid-raw-to-pedestals-workflow ${ARGS_ALL} --configKeyValues \"$ARGS_ALL_CONFIG\" --fast-decode "

if [ $HMP_NODCSCCDB_REC == 'false' ];
then
  WORKFLOW+="--use-dcsccdb --dcsccdb-uri 'http://alio2-cr1-flp199.cern.ch:8083' --dcsccdb-alivehours 3 "
fi
if [ $HMP_CCDB_REC == 'true' ];
then
  WORKFLOW+="--use-ccdb --ccdb-uri 'http://alice-ccdb.cern.ch' "
fi
if [ $HMP_FILES_REC == 'true' ];
then
  WORKFLOW+="--use-files "
fi

WORKFLOW+="--files-basepath 'HMP/Calib/Pedestals' "
WORKFLOW+="--pedestals-tag ${HMP_PED_TAG} --sigmacut ${HMP_SIGMACUT} | "

# --- WORKFLOW+="o2-dpl-output-proxy ${ARGS_ALL} --dataspec \"$PROXY_OUTSPEC\" --proxy-channel-name its-thr-input-proxy "
# --- WORKFLOW+="--channel-config \"name=its-thr-input-proxy,method=connect,type=push,transport=zeromq,rateLogging=0\" | "

WORKFLOW+="o2-dpl-run ${ARGS_ALL} "

if [ $WORKFLOWMODE == "print" ]; then
  echo "HMPID Pedestals Calculation (v.0.1) Workflow command:"
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE"
  eval $WORKFLOW
fi
