#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh
source common/gen_topo_helper_functions.sh

PROXY_INSPEC="A:MCH/PDIGITS/0"
CONSUL_ENDPOINT="alio2-cr1-hv-con01.cern.ch:8500"

MCH_MAX_PEDESTAL=${MCH_MAX_PEDESTAL:-500.0}
MCH_MAX_NOISE=${MCH_MAX_NOISE:-2.0}
MCH_MIN_ENTRIES=${MCH_MIN_ENTRIES:-100}
MCH_MIN_FRACTION=${MCH_MIN_FRACTION:-0.5}
MCH_END_OF_STREAM_ONLY=${MCH_END_OF_STREAM_ONLY:-true}
BADCHANNEL_CONFIG="${ARGS_ALL_CONFIG};MCHBadChannelCalibratorParam.maxPed=${MCH_MAX_PEDESTAL};MCHBadChannelCalibratorParam.maxNoise=${MCH_MAX_NOISE};MCHBadChannelCalibratorParam.minRequiredNofEntriesPerChannel=${MCH_MIN_ENTRIES};MCHBadChannelCalibratorParam.minRequiredCalibratedFraction=${MCH_MIN_FRACTION};MCHBadChannelCalibratorParam.onlyAtEndOfStream=${MCH_END_OF_STREAM_ONLY};"

if [ -n "${MCH_NTHREADS}" ]; then
   BADCHANNEL_CONFIG+="MCHBadChannelCalibratorParam.nThreads=${MCH_NTHREADS};"
fi

MCH_LOGGING_OPT=
if [ -n "${MCH_LOGGING_INTERVAL}" ]; then
    MCH_LOGGING_OPT="--logging-interval ${MCH_LOGGING_INTERVAL}"
fi

WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL --proxy-name mch-badchannel-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=mch-badchannel-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq\" | "
WORKFLOW+="o2-calibration-mch-badchannel-calib-workflow $ARGS_ALL --configKeyValues \"$BADCHANNEL_CONFIG\" ${MCH_LOGGING_OPT} | "

if [ -z "${MCH_SKIP_CCDB_UPLOAD}" ]; then
    WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"http://o2-ccdb.internal\" --sspec-min 0 --sspec-max 0 | "
    WORKFLOW+="o2-calibration-ccdb-populator-workflow $ARGS_ALL --configKeyValues \"$ARGS_ALL_CONFIG\" --ccdb-path=\"$DCSCCDBSERVER_PERS\" --sspec-min 1 --sspec-max 1 --name-extention dcs | "
fi

add_QC_from_consul "/o2/components/qc/ANY/any/mch-badchannel" ""
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
