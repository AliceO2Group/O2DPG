#!/bin/bash

source common/setenv.sh

source common/getCommonArgs.sh

PROXY_INSPEC="A:TPC/LASERTRACKS;B:TPC/CEDIGITS;eos:***/INFORMATION;D:TPC/CLUSREFS"

CALIB_CONFIG="TPCCalibPulser.FirstTimeBin=450;TPCCalibPulser.LastTimeBin=550;TPCCalibPulser.NbinsQtot=250;TPCCalibPulser.XminQtot=2;TPCCalibPulser.XmaxQtot=502;TPCCalibPulser.MinimumQtot=8;TPCCalibPulser.MinimumQmax=6;TPCCalibPulser.XminT0=450;TPCCalibPulser.XmaxT0=550;TPCCalibPulser.NbinsT0=400;keyval.output_dir=/dev/null"

CCDB_PATH="http://o2-ccdb.internal"

HOST=localhost

QC_CONFIG="consul-json://alio2-cr1-hv-con01.cern.ch:8500/o2/components/qc/ANY/any/tpc-raw-qcmn"

max_events=300
publish_after=440
min_tracks=0
num_lanes=36


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



o2-dpl-raw-proxy $ARGS_ALL \
  --proxy-name tpc-laser-input-proxy \
  --dataspec "${PROXY_INSPEC}" \
  --network-interface ib0 \
  --channel-config "name=tpc-laser-input-proxy,method=bind,type=pull,rateLogging=0,transport=zeromq" \
 | o2-tpc-calib-laser-tracks  ${ARGS_ALL} --use-filtered-tracks ${EXTRA_CONFIG_TRACKS} --min-tfs=${min_tracks} \
 --condition-remap "file:///home/wiechula/processData/inputFilesTracking/triggeredLaser/=GLO/Config/GRPECS;file:///home/wiechula/processData/inputFilesTracking/triggeredLaser/=GLO/Config/GRPMagField;file:///home/wiechula/processData/inputFilesTracking/triggeredLaser=TPC/Calib/LaserTracks" \
 | o2-tpc-calib-pad-raw ${ARGS_ALL} \
 --configKeyValues ${CALIB_CONFIG}  ${EXTRA_CONFIG} \
 | o2-calibration-ccdb-populator-workflow  ${ARGS_ALL} \
 --ccdb-path ${CCDB_PATH} \
 | o2-dpl-run $ARGS_ALL --dds ${WORKFLOWMODE_FILE}

