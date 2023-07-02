#!/bin/bash

source common/setenv.sh

# ---------------------------------------------------------------------------------------------------------------------
# Set general arguments
source common/getCommonArgs.sh

PROXY_INSPEC="A:TPC/LASERTRACKS;B:TPC/CEDIGITS;eos:***/INFORMATION;D:TPC/CLUSREFS"

max_events=200
publish_after=430


if [[ ! -z ${TPC_CALIB_MAX_EVENTS:-} ]]; then
    max_events=${TPC_CALIB_MAX_EVENTS}
fi

if [[ ! -z ${TPC_CALIB_PUBLISH_AFTER:-} ]]; then
    publish_after=${TPC_CALIB_PUBLISH_AFTER}
fi




WORKFLOW="o2-dpl-raw-proxy $ARGS_ALL \
  --proxy-name tpc-laser-input-proxy \
  --dataspec \"$PROXY_INSPEC\" \
  --network-interface ib0 \
  --channel-config \"name=tpc-laser-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq\" \
 | o2-tpc-calib-laser-tracks  $ARGS_ALL \
 --use-filtered-tracks --only-publish-on-eos \
 | o2-tpc-calib-pad-raw $ARGS_ALL \
  --configKeyValues \"TPCCalibPulser.FirstTimeBin=450;TPCCalibPulser.LastTimeBin=550;TPCCalibPulser.NbinsQtot=250;TPCCalibPulser.XminQtot=2;TPCCalibPulser.XmaxQtot=502;TPCCalibPulser.MinimumQtot=8;TPCCalibPulser.MinimumQmax=6;TPCCalibPulser.XminT0=450;TPCCalibPulser.XmaxT0=550;TPCCalibPulser.NbinsT0=400;keyval.output_dir=/dev/null\" \
 --lanes 1 \
 --publish-after-tfs ${publish_after} \
 --max-events ${max_events}
 --calib-type ce \
 --check-calib-infos \
 | o2-calibration-ccdb-populator-workflow  $ARGS_ALL \
 --ccdb-path http://o2-ccdb.internal \
 | o2-dpl-run $ARGS_ALL $GLOBALDPLOPT"

if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi
