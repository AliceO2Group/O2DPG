#!/bin/bash

[ -z "$QC_JSON_TPC" ] && QC_JSON_TPC=/home/epn/odc/files/tpcQCTasks_multinode_ALL.json
[ -z "$QC_JSON_ITS" ] && QC_JSON_ITS=/home/epn/jliu/itsEPNv2.json
[ -z "$QC_JSON_MFT" ] && QC_JSON_MFT=/home/epn/odc/files/qc-mft-cluster.json
[ -z "$QC_JSON_TOF" ] && QC_JSON_TOF=/home/fnoferin/public/tof-qc-globalrun.json

if [ -z "$WORKFLOW" ]; then
  echo This script must be called from the dpl-workflow.sh and not standalone 1>&2
  exit 1
fi

if [ -z "$GEN_TOPO_WORKDIR" ]; then
  echo This script must be run via the gen_topo scripts, or a GEN_TOPO_WORKDIR must be provided where merged JSONS are stored 1>&2
  exit 1
fi

JSON_FILES=
OUTPUT_SUFFIX=
for i in ITS MFT TPC TOF FT0 MID EMC PHS CPV ZDC FDD HMP FV0 TRD MCH; do
  DET_JSON_FILE="QC_JSON_$i"
  if has_detector_qc $i && [ ! -z "${!DET_JSON_FILE}" ]; then
     JSON_FILES+=" ${!DET_JSON_FILE}"
     OUTPUT_SUFFIX+="-$i"
  fi
done

if [ ! -z "$JSON_FILES" ]; then
  mkdir -p $GEN_TOPO_WORKDIR/json_cache
  if [ "0$GEN_TOPO_ONTHEFLY" == "01" ]; then
    find $GEN_TOPO_WORKDIR/json_cache/ -maxdepth 1 -type f -mtime +30 | xargs rm -f
  fi
  MERGED_JSON_FILENAME=$GEN_TOPO_WORKDIR/json_cache/`date +%Y%m%d-%H%M%S`-$$-$RANDOM-$OUTPUT_SUFFIX.json
  jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' $JSON_FILES > $MERGED_JSON_FILENAME
  if [ $? != 0 ]; then
    echo Merging QC workflow failed 1>&2
    exit 1
  fi
  MERGED_JSON_FILENAME=`realpath $MERGED_JSON_FILENAME`

  WORKFLOW+="o2-qc $ARGS_ALL --config json://$MERGED_JSON_FILENAME --local --host localhost | "
fi
