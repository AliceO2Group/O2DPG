#!/bin/bash

# accounts for externally set WORKFLOW_DETECTORS, SHMSIZE, SAVECTF, CTF_DIR, QCJSON, WORKFLOWMODE

# HACK
###WORKFLOW_DETECTORS=`echo $WORKFLOW_DETECTORS | tr _ ,`

source /home/shahoian/alice/O2DataProcessing/common/setenv.sh

# EPN script. Including CTF creation and QC.
export GPUTYPE=HIP
export GPUMEMSIZE=$(( 24 << 30 ))
export HOSTMEMSIZE=$(( 5 << 30 ))

SEVERITY=INFO
INFOLOGGER_SEVERITY=WARNING

# global args
ARGS_ALL=" --session default --severity $SEVERITY --infologger-severity $INFOLOGGER_SEVERITY --shm-segment-size $SHMSIZE --monitoring-backend influxdb-unix:///tmp/telegraf.sock"
#ARGS_ALL=" --session default --severity $SEVERITY --infologger-severity $INFOLOGGER_SEVERITY --shm-segment-size $SHMSIZE "

# raw input proxy channel
PROXY_CHANNEL="name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1"
# raw input data filtered by the proxy
PROXY_INSPEC="dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

# add detectors
has_detector ITS && PROXY_INSPEC+=";I:ITS/RAWDATA"
has_detector MFT && PROXY_INSPEC+=";M:MFT/RAWDATA"
has_detector TPC && PROXY_INSPEC+=";T:TPC/RAWDATA"
has_detector TOF && PROXY_INSPEC+=";X:TOF/CRAWDATA"

TPC_INSPEC="dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION;T:TPC/RAWDATA"
TPC_OUTPUT="clusters,tracks,disable-writer"
if [ $SAVECTF == 1 ]; then
  TPC_OUTPUT+=",encoded-clusters"
fi

# directory for external files
#FILEWORKDIR="/home/epn/odc/files"

# Clusterization dictionaries path
ITSCLUSDICT="${FILEWORKDIR}/ITSdictionary.bin"
MFTCLUSDICT="${FILEWORKDIR}/MFTdictionary.bin"

MFT_NOISE="${FILEWORKDIR}/mft_noise_220721_R3C-520.root"

# CTF compression dictionary
CTF_DICT="${FILEWORKDIR}/ctf_dictionary.root"
# min file size for CTF (accumulate CTFs until it is reached)
CTF_MINSIZE="2000000"
# output directory for CTF files
#CTF_DIR="/tmp/eosbuffer"

# key/values config string
CONFKEYVAL="NameConf.mDirGRP=${FILEWORKDIR};NameConf.mDirGeom=${FILEWORKDIR}"

# number of decoding pipelines and threads per pipeline
NITSDECPIPELINES=6
NITSDECTHREADS=2
NMFTDECPIPELINES=6
NMFTDECTHREADS=2

# number of reconstruction pipelines and threads per pipeline
NITSRECPIPELINES=2
NMFTRECPIPELINES=2
NTOFRECPIPELINES=1

# number of compression pipelines
NITSENCODERPIPELINES=1
NMFTENCODERPIPELINES=1
NTOFENCODERPIPELINES=1

# uncomment this to disable intermediate reconstruction output
#DISABLE_RECO_OUTPUT=" --disable-root-output "

HOST=localhost

WORKFLOW="o2-dpl-raw-proxy -b ${ARGS_ALL} --dataspec \"${PROXY_INSPEC}\" --channel-config \"${PROXY_CHANNEL}\" | "
has_detector ITS && WORKFLOW+="o2-itsmft-stf-decoder-workflow -b ${ARGS_ALL} --nthreads ${NITSDECTHREADS} --pipeline its-stf-decoder:${NITSDECPIPELINES}  --configKeyValues \"${CONFKEYVAL}\" --dict-file \"${ITSCLUSDICT}\" | "
has_detector ITS && WORKFLOW+="o2-its-reco-workflow -b ${ARGS_ALL} ${DISABLE_RECO_OUTPUT} --trackerCA --tracking-mode sync --disable-mc --clusters-from-upstream --pipeline its-tracker:${NITSRECPIPELINES} --its-dictionary-path \"${ITSCLUSDICT}\" --configKeyValues \"${CONFKEYVAL}\" | "
#
has_detector MFT && WORKFLOW+="o2-itsmft-stf-decoder-workflow -b ${ARGS_ALL} --nthreads ${NMFTDECTHREADS} --pipeline mft-stf-decoder:${NMFTDECPIPELINES}  --configKeyValues \"${CONFKEYVAL}\" --dict-file \"${MFTCLUSDICT}\" --runmft --noise-file \"${MFT_NOISE}\" | "
#
has_detector TPC && WORKFLOW+="o2-tpc-raw-to-digits-workflow -b ${ARGS_ALL} --input-spec \"${TPC_INSPEC}\" --configKeyValues \"TPCDigitDump.LastTimeBin=1000\" --pipeline tpc-raw-to-digits-0:6 | "
has_detector TPC && WORKFLOW+="o2-tpc-reco-workflow -b ${ARGS_ALL} --input-type digitizer --output-type $TPC_OUTPUT --disable-mc --pipeline tpc-tracker:4 --environment ROCR_VISIBLE_DEVICES={timeslice0} --configKeyValues \"align-geom.mDetectors=none;GPU_global.deviceType=$GPUTYPE;GPU_proc.forceMemoryPoolSize=$GPUMEMSIZE;GPU_proc.forceHostMemoryPoolSize=$HOSTMEMSIZE;GPU_proc.deviceNum=0;GPU_proc.tpcIncreasedMinClustersPerRow=500000;GPU_proc.ignoreNonFatalGPUErrors=1;GPU_proc.memoryScalingFactor=3;${CONFKEYVAL}\" | "
#
has_detector TOF && WORKFLOW+="o2-tof-reco-workflow -b ${ARGS_ALL} --input-type raw --output-type clusters --pipeline TOFClusterer:${NTOFRECPIPELINES} --configKeyValues \"${CONFKEYVAL}\" | "

if [ $SAVECTF == 1 ]; then  
  has_detector ITS && WORKFLOW+="o2-itsmft-entropy-encoder-workflow -b ${ARGS_ALL} --ctf-dict \"${CTF_DICT}\"  --pipeline its-entropy-encoder:${NITSENCODERPIPELINES} | "
  has_detector MFT && WORKFLOW+="o2-itsmft-entropy-encoder-workflow -b ${ARGS_ALL} --ctf-dict \"${CTF_DICT}\"  --pipeline mft-entropy-encoder:${NMFTENCODERPIPELINES} --runmft | "
  has_detector TOF && WORKFLOW+="o2-tof-entropy-encoder-workflow    -b ${ARGS_ALL} --ctf-dict \"${CTF_DICT}\"  --pipeline tof-entropy-encoder:${NTOFENCODERPIPELINES} | "
  WORKFLOW+="o2-ctf-writer-workflow -b ${ARGS_ALL} --configKeyValues \"${CONFKEYVAL}\" --no-grp --onlyDet $WORKFLOW_DETECTORS --ctf-dict \"${CTF_DICT}\" --output-dir \"$CTF_DIR\" --min-file-size ${CTF_MINSIZE} | "
fi

if [ -n "$QCJSON" ]; then
  WORKFLOW+="o2-qc -b ${ARGS_ALL} --config json://$QCJSON --local --host $HOST | "
fi

WORKFLOW+=" o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE"
  eval $WORKFLOW
fi



