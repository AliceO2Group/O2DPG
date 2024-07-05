#!/bin/bash

source common/setenv.sh

source common/getCommonArgs.sh

FILEWORKDIR="/home/wiechula/processData/inputFilesTracking/triggeredLaser"

PROXY_INSPEC="A:TPC/LASERTRACKS;B:TPC/CEDIGITS;D:TPC/CLUSREFS"

CALIB_CONFIG="TPCCalibPulser.FirstTimeBin=450;TPCCalibPulser.LastTimeBin=550;TPCCalibPulser.NbinsQtot=300;TPCCalibPulser.XminQtot=2;TPCCalibPulser.XmaxQtot=602;TPCCalibPulser.MinimumQtot=8;TPCCalibPulser.MinimumQmax=6;TPCCalibPulser.XminT0=450;TPCCalibPulser.XmaxT0=550;TPCCalibPulser.NbinsT0=400;keyval.output_dir=/dev/null"

CCDB_PATH="http://o2-ccdb.internal"

HOST=localhost

QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-raw-qcmn?run_type=${RUNTYPE:-}"

QC_CONFIG="components/qc/ANY/any/tpc-raw-qcmn"
max_events=300
publish_after=440
min_tracks=0
num_lanes=36

REMAP="--condition-remap \"file://${FILEWORKDIR}=GLO/Config/GRPECS,GLO/Config/GRPMagField,TPC/Calib/LaserTracks\" "
if [[ ! -z ${TPC_CALIB_MAX_EVENTS:-} ]]; then
    max_events=${TPC_CALIB_MAX_EVENTS}
fi
if [[ ! -z ${TPC_CALIB_MIN_TRACKS:-} ]]; then
    min_tracks=${TPC_CALIB_MIN_TRACKS}
fi

if [[ ! -z ${TPC_CALIB_PUBLISH_AFTER:-} ]]; then
    publish_after=${TPC_CALIB_PUBLISH_AFTER}
fi
if [[ ! -z ${TPC_CALIB_LANES_PAD_RAW:-} ]]; then
    num_lanes=${TPC_CALIB_LANES_PAD_RAW}
fi

EXTRA_CONFIG="--calib-type ce --publish-after-tfs ${publish_after} --max-events ${max_events} --lanes ${num_lanes} --check-calib-infos"

EXTRA_CONFIG_TRACKS=""

if [[ ${TPC_CALIB_TRACKS_PUBLISH_EOS:-} == 1 ]]; then
    EXTRA_CONFIG_TRACKS="--only-publish-on-eos"
fi



WORKFLOW=
add_W o2-dpl-raw-proxy " --proxy-name tpc-laser-input-proxy --dataspec \"$PROXY_INSPEC\" --network-interface ib0 --channel-config \"name=tpc-laser-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq\"" "" 0
add_W o2-tpc-calib-laser-tracks "${REMAP} --use-filtered-tracks ${EXTRA_CONFIG_TRACKS} --min-tfs=${min_tracks} "
add_W o2-tpc-calib-pad-raw " ${EXTRA_CONFIG}" "${CALIB_CONFIG}"
add_W o2-calibration-ccdb-populator-workflow "--ccdb-path ${CCDB_PATH}" "" 0
#add_QC_from_apricot "${QC_CONFIG_CONSUL}" "--local --host lcoalhost"

WORKFLOW+="o2-dpl-run ${ARGS_ALL} ${GLOBALDPLOPT}"
if [ $WORKFLOWMODE == "print" ]; then
  echo Workflow command:
  echo $WORKFLOW | sed "s/| */|\n/g"
else
  # Execute the command we have assembled
  WORKFLOW+=" --$WORKFLOWMODE ${WORKFLOWMODE_FILE}"
  eval $WORKFLOW
fi


