#!/bin/bash

if [[ -z "$WORKFLOW" ]] || [[ -z "$MYDIR" ]]; then
  echo This script must be called from the dpl-workflow.sh and not standalone 1>&2
  exit 1
fi

if [[ -z $QC_JSON_FROM_OUTSIDE ]]; then
  [[ -z "$QC_JSON_TPC" ]] && QC_JSON_TPC=/home/rmunzer/odc/config/tpcQCTasks_multinode_ALL.json
  [[ -z "$QC_JSON_ITS" ]] && QC_JSON_ITS=/home/jian/jliu/itsEPN-merger.json
  [[ -z "$QC_JSON_MFT" ]] && QC_JSON_MFT=/home/epn/odc/files/qc-mft-cluster-merger-raw-cluster.json
  [[ -z "$QC_JSON_TOF" ]] && QC_JSON_TOF=/home/fnoferin/public/tof-qc-globalrun.json
  [[ -z "$QC_JSON_FDD" ]] && QC_JSON_FDD=/home/afurs/O2DataProcessing/testing/detectors/FDD/fdd-digits-ds.json
  [[ -z "$QC_JSON_FT0" ]] && QC_JSON_FT0=/home/afurs/O2DataProcessing/testing/detectors/FT0/ft0-digits-ds.json
  [[ -z "$QC_JSON_FV0" ]] && QC_JSON_FV0=/home/afurs/O2DataProcessing/testing/detectors/FV0/fv0-digits-ds.json
  [[ -z "$QC_JSON_EMC" ]] && QC_JSON_EMC=/home/mfasel/alice/O2DataProcessing/testing/detectors/EMC/qc/emcQCTasksAll_multinode.json
  [[ -z "$QC_JSON_MCH" ]] && QC_JSON_MCH=/home/laphecet/qc_configs/mch-qc-physics.json
  [[ -z "$QC_JSON_MID" ]] && QC_JSON_MID=/home/dstocco/config/mid-qcmn-epn-digits.json
  [[ -z "$QC_JSON_PRIMVTX" ]] && QC_JSON_PRIMVTX=/home/shahoian/jsons/vertexing-qc.json

  if [[ -z "$GEN_TOPO_WORKDIR" ]]; then
    echo This script must be run via the gen_topo scripts, or a GEN_TOPO_WORKDIR must be provided where merged JSONS are stored 1>&2
    exit 1
  fi

  JSON_FILES=
  OUTPUT_SUFFIX=
  for i in `echo $LIST_OF_DETECTORS | sed "s/,/ /g"`; do
    DET_JSON_FILE="QC_JSON_$i"
    if has_detector_qc $i && [ ! -z "${!DET_JSON_FILE}" ]; then
       JSON_FILES+=" ${!DET_JSON_FILE}"
       OUTPUT_SUFFIX+="-$i"
    fi
  done

  # matching / vertexing QC
  for i in `echo $LIST_OF_GLORECO | sed "s/,/ /g"`; do
    GLO_JSON_FILE="QC_JSON_$i"
    if has_detector_matching $i && has_matching_qc $i && [ ! -z "${!GLO_JSON_FILE}" ]; then
       JSON_FILES+=" ${!GLO_JSON_FILE}"
       OUTPUT_SUFFIX+="-$i"
    fi
  done

  # arbitrary extra QC
  if [[ ! -z "$QC_JSON_EXTRA" ]]; then
      JSON_FILES+=" ${QC_JSON_EXTRA}"
      OUTPUT_SUFFIX+="-EXTRA"
  fi

  if [[ ! -z "$JSON_FILES" ]]; then
    mkdir -p $GEN_TOPO_WORKDIR/json_cache
    if [[ "0$GEN_TOPO_ONTHEFLY" == "01" ]]; then
      find $GEN_TOPO_WORKDIR/json_cache/ -maxdepth 1 -type f -mtime +30 | xargs rm -f
    fi
    MERGED_JSON_FILENAME=$GEN_TOPO_WORKDIR/json_cache/`date +%Y%m%d-%H%M%S`-$$-$RANDOM-$OUTPUT_SUFFIX.json
    jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' $MYDIR/qc_global.json $JSON_FILES > $MERGED_JSON_FILENAME
    if [[ $? != 0 ]]; then
      echo Merging QC workflow with JSON files $JSON_FILES failed 1>&2
      exit 1
    fi
    MERGED_JSON_FILENAME=`realpath $MERGED_JSON_FILENAME`

    if [[ "0$QC_REDIRECT_MERGER_TO_LOCALHOST" == "01" ]]; then
      sed -i -E 's/( *)"remoteMachine" *: *".*"(,|) *$/\1"remoteMachine": "127.0.0.1"\2/' $MERGED_JSON_FILENAME
    fi
    QC_JSON_FROM_OUTSIDE="$MERGED_JSON_FILENAME"
  fi
fi

if [[ ! -z "$QC_JSON_FROM_OUTSIDE" ]]; then
  add_W o2-qc "--config json://$QC_JSON_FROM_OUTSIDE ${QC_CONFIG_PARAM:---local --host ${QC_HOST:-localhost}}" "" 0
fi
