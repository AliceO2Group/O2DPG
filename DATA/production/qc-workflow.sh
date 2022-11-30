#!/bin/bash

if [[ -z "$WORKFLOW" ]] || [[ -z "$MYDIR" ]]; then
  echo This script must be called from the dpl-workflow.sh and not standalone 1>&2
  exit 1
fi

if [[ ! -z $GEN_TOPO_QC_JSON_FILE ]]; then
  exec 101>$GEN_TOPO_QC_JSON_FILE.lock || exit 1
  flock 101 || exit 1
fi

QC_CONFIG=
QC_CONFIG_OVERRIDE=
if [[ -z $QC_JSON_FROM_OUTSIDE && ! -z $GEN_TOPO_QC_JSON_FILE && -f $GEN_TOPO_QC_JSON_FILE ]]; then
  QC_JSON_FROM_OUTSIDE=$GEN_TOPO_QC_JSON_FILE
elif [[ -z $QC_JSON_FROM_OUTSIDE ]]; then
  if [[ $EPNSYNCMODE == 1 || "0$GEN_TOPO_LOAD_QC_JSON_FROM_CONSUL" == "01" ]]; then
    [[ -z "$QC_JSON_TPC" ]] && QC_JSON_TPC=consul://o2/components/qc/ANY/any/tpc-full-qcmn
    [[ -z "$QC_JSON_ITS" ]] && QC_JSON_ITS=consul://o2/components/qc/ANY/any/its-qcmn-epn-full
    if [[ -z "$QC_JSON_MFT" ]]; then
      if has_detector MFT && has_processing_step MFT_RECO; then
        QC_JSON_MFT=consul://o2/components/qc/ANY/any/mft-track-full-qcmn
      else
        QC_JSON_MFT=consul://o2/components/qc/ANY/any/mft-full-qcmn
      fi
    fi
    if [[ -z "$QC_JSON_TOF" ]]; then
      if has_detector_flp_processing TOF; then
        QC_JSON_TOF=consul://o2/components/qc/ANY/any/tof-full-qcmn-on-epn
      else
        QC_JSON_TOF=consul://o2/components/qc/ANY/any/tof-full-epn-qcmn-on-epn
      fi
    fi
    [[ -z "$QC_JSON_FDD" ]] && QC_JSON_FDD=consul://o2/components/qc/ANY/any/fdd-digits-qc-epn
    [[ -z "$QC_JSON_FT0" ]] && QC_JSON_FT0=consul://o2/components/qc/ANY/any/ft0-digits-qc-epn
    [[ -z "$QC_JSON_FV0" ]] && QC_JSON_FV0=consul://o2/components/qc/ANY/any/fv0-digits-qc-epn
    [[ -z "$QC_JSON_EMC" ]] && QC_JSON_EMC=consul://o2/components/qc/ANY/any/emc-qcmn-epnall
    [[ -z "$QC_JSON_ZDC" ]] && has_processing_step ZDC_RECO && QC_JSON_ZDC=consul://o2/components/qc/ANY/any/zdc-rec-epn
    if [[ -z "$QC_JSON_MCH" ]]; then
      if has_detector MCH && has_processing_step MCH_RECO; then
        if has_track_source "MCH-MID"; then
          QC_JSON_MCH=consul://o2/components/qc/ANY/any/mch-qcmn-epn-full-track-matching
        else
          QC_JSON_MCH=consul://o2/components/qc/ANY/any/mch-qcmn-epn-full
        fi
      else
        QC_JSON_MCH=consul://o2/components/qc/ANY/any/mch-qcmn-epn-digits
      fi
    fi
    if [[ -z "$QC_JSON_MID" ]]; then
      if has_detector MID && has_processing_step MID_RECO; then
        QC_JSON_MID=consul://o2/components/qc/ANY/any/mid-full-qcmn
      else
        QC_JSON_MID=consul://o2/components/qc/ANY/any/mid-flp_raw-epn_digits-qcmn
      fi
    fi
    [[ -z "$QC_JSON_CPV" ]] && QC_JSON_CPV=consul://o2/components/qc/ANY/any/cpv-physics-qcmn-epn
    [[ -z "$QC_JSON_TRD" ]] && QC_JSON_TRD=consul://o2/components/qc/ANY/any/trd-full-qcmn-nopulseheight-epn
    [[ -z "$QC_JSON_PHS" ]] && QC_JSON_PHS=consul://o2/components/qc/ANY/any/phos-raw-clusters-epn
    [[ -z "$QC_JSON_GLO_PRIMVTX" ]] && QC_JSON_GLO_PRIMVTX=consul://o2/components/qc/ANY/any/glo-vtx-qcmn-epn
    [[ -z "$QC_JSON_GLO_ITSTPC" ]] && QC_JSON_GLO_ITSTPC=consul://o2/components/qc/ANY/any/glo-itstpc-mtch-qcmn-epn
    if [[ -z "$QC_JSON_TOF_MATCH" ]]; then
      if has_tof_matching_source ITS-TPC && has_tof_matching_source ITS-TPC-TRD; then
        QC_JSON_TOF_MATCH=consul://o2/components/qc/ANY/any/tof-qcmn-match-itstpctrdtof
      elif has_tof_matching_source ITS-TPC; then
        QC_JSON_TOF_MATCH=consul://o2/components/qc/ANY/any/tof-qcmn-match-itstpctof
      fi
    fi
    [[ -z "$QC_JSON_GLOBAL" ]] && QC_JSON_GLOBAL=$O2DPG_ROOT/DATA/production/qc-sync/qc-global-epn.json # this must be last
  elif [[ $SYNCMODE == 1 ]]; then
    [[ -z "$QC_JSON_TPC" ]] && QC_JSON_TPC=$O2DPG_ROOT/DATA/production/qc-sync/tpc.json
    [[ -z "$QC_JSON_ITS" ]] && QC_JSON_ITS=$O2DPG_ROOT/DATA/production/qc-sync/its.json
    if [[ -z "$QC_JSON_MFT" ]]; then
      if has_processing_step MFT_RECO; then
        QC_JSON_MFT=$O2DPG_ROOT/DATA/production/qc-sync/mft_track.json
      else
        QC_JSON_MFT=$O2DPG_ROOT/DATA/production/qc-sync/mft.json
      fi
    fi
    [[ -z "$QC_JSON_TOF" ]] && QC_JSON_TOF=$O2DPG_ROOT/DATA/production/qc-sync/tof.json
    [[ -z "$QC_JSON_FDD" ]] && QC_JSON_FDD=$O2DPG_ROOT/DATA/production/qc-sync/fdd.json
    [[ -z "$QC_JSON_FT0" ]] && QC_JSON_FT0=$O2DPG_ROOT/DATA/production/qc-sync/ft0.json
    [[ -z "$QC_JSON_FV0" ]] && QC_JSON_FV0=$O2DPG_ROOT/DATA/production/qc-sync/fv0.json
    [[ -z "$QC_JSON_EMC" ]] && QC_JSON_EMC=$O2DPG_ROOT/DATA/production/qc-sync/emc.json
    [[ -z "$QC_JSON_ZDC" ]] && has_processing_step ZDC_RECO && QC_JSON_ZDC=$O2DPG_ROOT/DATA/production/qc-sync/zdc.json
    [[ -z "$QC_JSON_MCH" ]] && QC_JSON_MCH=$O2DPG_ROOT/DATA/production/qc-sync/mch.json
    [[ -z "$QC_JSON_MID" ]] && QC_JSON_MID=$O2DPG_ROOT/DATA/production/qc-sync/mid-digits.json && has_processing_step MID_RECO && QC_JSON_MID=$O2DPG_ROOT/DATA/production/qc-sync/mid.json
    [[ -z "$QC_JSON_CPV" ]] && QC_JSON_CPV=$O2DPG_ROOT/DATA/production/qc-sync/cpv.json
    [[ -z "$QC_JSON_PHS" ]] && QC_JSON_PHS=$O2DPG_ROOT/DATA/production/qc-sync/phs.json
    [[ -z "$QC_JSON_TRD" ]] && QC_JSON_TRD=$O2DPG_ROOT/DATA/production/qc-sync/trd.json
    [[ -z "$QC_JSON_GLO_PRIMVTX" ]] && QC_JSON_GLO_PRIMVTX=$O2DPG_ROOT/DATA/production/qc-sync/glo-vtx-qcmn-epn.json
    [[ -z "$QC_JSON_GLO_ITSTPC" ]] && QC_JSON_GLO_ITSTPC=$O2DPG_ROOT/DATA/production/qc-sync/glo-itstpc-mtch-qcmn-epn.json
    if [[ -z "$QC_JSON_TOF_MATCH" ]]; then
      if has_tof_matching_source ITS-TPC && has_tof_matching_source ITS-TPC-TRD; then
        QC_JSON_TOF_MATCH=$O2DPG_ROOT/DATA/production/qc-sync/itstpctrdtof.json
      elif has_tof_matching_source ITS-TPC; then
        QC_JSON_TOF_MATCH=$O2DPG_ROOT/DATA/production/qc-sync/itstpctof.json
      fi
    fi
    [[ -z "$QC_JSON_GLOBAL" ]] && QC_JSON_GLOBAL=$O2DPG_ROOT/DATA/production/qc-sync/qc-global.json # this must be last
  else
    [[ -z "$QC_JSON_TPC" ]] && QC_JSON_TPC=$O2DPG_ROOT/DATA/production/qc-async/tpc.json
    [[ -z "$QC_JSON_ITS" ]] && QC_JSON_ITS=$O2DPG_ROOT/DATA/production/qc-async/its.json
    [[ -z "$QC_JSON_MFT" ]] && QC_JSON_MFT=$O2DPG_ROOT/DATA/production/qc-async/mft.json
    [[ -z "$QC_JSON_TOF" ]] && QC_JSON_TOF=$O2DPG_ROOT/DATA/production/qc-async/tof.json
    [[ -z "$QC_JSON_FT0" ]] && QC_JSON_FT0=$O2DPG_ROOT/DATA/production/qc-async/ft0.json
    [[ -z "$QC_JSON_FV0" ]] && QC_JSON_FV0=$O2DPG_ROOT/DATA/production/qc-async/fv0.json
    [[ -z "$QC_JSON_FDD" ]] && QC_JSON_FDD=$O2DPG_ROOT/DATA/production/qc-async/fdd.json
    [[ -z "$QC_JSON_EMC" ]] && QC_JSON_EMC=$O2DPG_ROOT/DATA/production/qc-async/emc.json
    [[ -z "$QC_JSON_MID" ]] && QC_JSON_MID=$O2DPG_ROOT/DATA/production/qc-async/mid.json
    [[ -z "$QC_JSON_CPV" ]] && QC_JSON_CPV=$O2DPG_ROOT/DATA/production/qc-async/cpv.json
    [[ -z "$QC_JSON_PHS" ]] && QC_JSON_PHS=$O2DPG_ROOT/DATA/production/qc-async/phs.json
    [[ -z "$QC_JSON_TRD" ]] && QC_JSON_TRD=$O2DPG_ROOT/DATA/production/qc-async/trd.json
    # the following two ($QC_JSON_PRIMVTX and $QC_JSON_ITSTPC) replace $QC_JSON_GLO for async processing
    [[ -z "$QC_JSON_GLO_PRIMVTX" ]] && QC_JSON_GLO_PRIMVTX=$O2DPG_ROOT/DATA/production/qc-async/primvtx.json
    [[ -z "$QC_JSON_GLO_ITSTPC" ]] && QC_JSON_GLO_ITSTPC=$O2DPG_ROOT/DATA/production/qc-async/itstpc.json
    if [[ -z "$QC_JSON_TOF_MATCH" ]]; then
      if has_tof_matching_source ITS-TPC && has_tof_matching_source ITS-TPC-TRD; then
        QC_JSON_TOF_MATCH=$O2DPG_ROOT/DATA/production/qc-async/itstpctofwtrd.json
      elif has_tof_matching_source ITS-TPC; then
        QC_JSON_TOF_MATCH=$O2DPG_ROOT/DATA/production/qc-async/itstpctof.json
      fi
    fi
    if [[ -z "$QC_JSON_PID_FT0TOF" ]]; then
      if has_tof_matching_source ITS-TPC && has_tof_matching_source ITS-TPC-TRD; then
        QC_JSON_PID_FT0TOF=$O2DPG_ROOT/DATA/production/qc-async/pidft0tofwtrd.json
      elif has_tof_matching_source ITS-TPC; then
        QC_JSON_PID_FT0TOF=$O2DPG_ROOT/DATA/production/qc-async/pidft0tof.json
      fi
    fi
    [[ -z "$QC_JSON_GLOBAL" ]] && QC_JSON_GLOBAL=$O2DPG_ROOT/DATA/production/qc-async/qc-global.json # this must be last
  fi

  if [[ -z "$GEN_TOPO_WORKDIR" ]]; then
    echo This script must be run via the gen_topo scripts, or a GEN_TOPO_WORKDIR must be provided where merged JSONS are stored 1>&2
    exit 1
  fi

  FETCHTMPDIR=$(mktemp -d -t GEN_TOPO_DOWNLOAD_JSON-XXXXXX)

  add_QC_JSON() {
    if [[ ${2} =~ ^consul://.* ]]; then
      TMP_FILENAME=$FETCHTMPDIR/$1.$RANDOM.$RANDOM.json
      curl -s -o $TMP_FILENAME "http://alio2-cr1-hv-aliecs.cern.ch:8500/v1/kv/${2/consul:\/\//}?raw"
      if [[ $? != 0 ]]; then
        echo "Error fetching QC JSON $2"
        exit 1
      fi
    else
      TMP_FILENAME=$2
    fi
    JSON_FILES+=" $TMP_FILENAME"
    jq -rM '""' > /dev/null < $TMP_FILENAME
    if [[ $? != 0 ]]; then
      echo "Invalid QC JSON $2" 1>&2
      exit 1
    fi
    OUTPUT_SUFFIX+="-$1"
  }

  JSON_FILES=
  OUTPUT_SUFFIX=

  # TOF matching
  if has_detector_qc TOF && [[ $WORKFLOW_DETECTORS_QC =~ (^|,)"TOF_MATCH"(,|$) ]] && [ ! -z "$QC_JSON_TOF_MATCH" ]; then
    add_QC_JSON matchTOF ${QC_JSON_TOF_MATCH}
  fi

  for i in ${LIST_OF_DETECTORS//,/ }; do
    DET_JSON_FILE="QC_JSON_$i"
    if has_detector_qc $i && [ ! -z "${!DET_JSON_FILE}" ]; then
      add_QC_JSON $i ${!DET_JSON_FILE}
    fi
  done

  for i in ${LIST_OF_GLORECO//,/ }; do
    DET_JSON_FILE="QC_JSON_GLO_$i"
    if has_matching_qc $i && [ ! -z "${!DET_JSON_FILE}" ]; then
      if [[ $i == "PRIMVTX" ]] && ! has_detector_reco ITS; then continue; fi
      if [[ $i == "ITSTPC" ]] && ! has_detectors_reco ITS TPC; then continue; fi
      add_QC_JSON GLO_$i ${!DET_JSON_FILE}
    fi
  done

  # PID QC
  for i in ${LIST_OF_PID//,/ }; do
    PIDDETFORFILE=${i//-/}
    PID_JSON_FILE="QC_JSON_PID_$PIDDETFORFILE"
    if has_pid_qc $i && [ ! -z "${!PID_JSON_FILE}" ]; then
      add_QC_JSON pid$i ${!PID_JSON_FILE}
    fi
  done

  # arbitrary extra QC
  if [[ ! -z "$QC_JSON_EXTRA" ]]; then
    add_QC_JSON EXTRA ${QC_JSON_EXTRA}
  fi

  if [[ ! -z "$JSON_FILES" ]]; then
    if [[ -z "$GEN_TOPO_QC_JSON_FILE" ]]; then
      mkdir -p $GEN_TOPO_WORKDIR/json_cache
      if [[ "0$GEN_TOPO_ONTHEFLY" == "01" ]]; then
        find $GEN_TOPO_WORKDIR/json_cache/ -maxdepth 1 -type f -mtime +30 | xargs rm -f
      fi
      MERGED_JSON_FILENAME=$GEN_TOPO_WORKDIR/json_cache/$(date +%Y%m%d-%H%M%S)-$$-$RANDOM-$OUTPUT_SUFFIX.json
    else
      MERGED_JSON_FILENAME=$GEN_TOPO_QC_JSON_FILE
    fi
    jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' $QC_JSON_GLOBAL $JSON_FILES > $MERGED_JSON_FILENAME
    if [[ $? != 0 ]]; then
      echo Merging QC workflow with JSON files $JSON_FILES failed 1>&2
      exit 1
    fi
    MERGED_JSON_FILENAME=$(realpath $MERGED_JSON_FILENAME)

    if [[ "0$QC_REDIRECT_MERGER_TO_LOCALHOST" == "01" ]]; then
      sed -i.bak -E 's/( *)"remoteMachine" *: *".*"(,?) *$/\1"remoteMachine": "127.0.0.1"\2/' $MERGED_JSON_FILENAME
      unlink $MERGED_JSON_FILENAME.bak
      QC_CONFIG_OVERRIDE+="qc.config.database.host=ccdb-test.cern.ch:8080;"
    fi

    if [[ "0$GEN_TOPO_QC_OVERRIDE_CCDB_SERVER" != "0" ]]; then
      sed -i "s,https://alice-ccdb.cern.ch,$GEN_TOPO_QC_OVERRIDE_CCDB_SERVER,g" $MERGED_JSON_FILENAME
    fi
    QC_JSON_FROM_OUTSIDE="$MERGED_JSON_FILENAME"
  fi

  rm -Rf $FETCHTMPDIR
fi

[[ $EPNSYNCMODE == 1 && $NUMAGPUIDS == 1 ]] && QC_CONFIG_OVERRIDE+="qc.config.infologger.filterDiscardFile=../../qc-_ID_-${NUMAID}.log;"

[[ ! -z $QC_CONFIG_OVERRIDE ]] && QC_CONFIG+=" --override-values \"$QC_CONFIG_OVERRIDE\""

if [[ ! -z "$QC_JSON_FROM_OUTSIDE" ]]; then
  if [[ ! -f $QC_JSON_FROM_OUTSIDE ]]; then
    echo QC JSON FILE $QC_JSON_FROM_OUTSIDE missing 1>&2
    exit 1
  fi
  jq -rM '""' > /dev/null < $QC_JSON_FROM_OUTSIDE
  if [[ $? != 0 ]]; then
    echo "Final QC JSON FILE $QC_JSON_FROM_OUTSIDE has invalid syntax" 1>&2
    #cat $QC_JSON_FROM_OUTSIDE 1>&2
    exit 1
  fi
  if [[ -z $QC_CONFIG_PARAM ]]; then
    if [[ $SYNCMODE == 1 ]]; then
      QC_CONFIG_PARAM="--local --host ${QC_HOST:-localhost}"
    else
      QC_CONFIG_PARAM="--local-batch=QC.root"
    fi
  fi
  add_W o2-qc "--config json://$QC_JSON_FROM_OUTSIDE ${QC_CONFIG_PARAM} ${QC_CONFIG}"
fi

if [[ ! -z $GEN_TOPO_QC_JSON_FILE ]]; then
  flock -u 101 || exit 1
fi

true # everything OK up to this point, so the script should return 0 (it is !=0 if the last check failed)
