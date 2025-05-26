#!/bin/bash

if [[ -z "$WORKFLOW" || -z "$GEN_TOPO_MYDIR" ]]; then
  echo This script must be called from the dpl-workflow.sh and not standalone 1>&2
  exit 1
fi

source $GEN_TOPO_MYDIR/gen_topo_helper_functions.sh || { echo "gen_topo_helper_functions.sh failed" 1>&2 && exit 1; }
source $GEN_TOPO_MYDIR/setenv.sh || { echo "setenv.sh failed" 1>&2 && exit 1; }

if [[ ! -z ${GEN_TOPO_QC_JSON_FILE:-} ]]; then
  exec 101>$GEN_TOPO_QC_JSON_FILE.lock || exit 1
  flock 101 || exit 1
fi

FETCHTMPDIR=$(mktemp -d -t GEN_TOPO_DOWNLOAD_JSON-XXXXXX)

JSON_FILES=
OUTPUT_SUFFIX=

add_QC_JSON() {
  if [[ ${2} =~ ^consul://.* ]]; then
    [[ $EPNSYNCMODE == 1 ]] ||  { echo "Error fetching QC JSON $2: consul server is used for EPNSYNCMODE == 1 only" 1>&2 && exit 1; }
    TMP_FILENAME=$FETCHTMPDIR/$1.$RANDOM.$RANDOM.json
    curl -s -o $TMP_FILENAME "http://${GEN_TOPO_QC_CONSUL_SERVER}:8500/v1/kv/${2/consul:\/\//}?raw"
    if [[ $? != 0 ]]; then
      echo "Error fetching QC JSON $2 (3)" 1>&2
      exit 1
    fi
  elif [[ ${2} =~ ^apricot://.* ]]; then
    [[ $EPNSYNCMODE == 1 ]] || { echo "Error fetching QC JSON $2: apricot server is used for EPNSYNCMODE == 1 only" 1>&2 && exit 1; }
    TMP_FILENAME=$FETCHTMPDIR/$1.$RANDOM.$RANDOM.json
	  if [[ ${2} =~ "?" ]]; then
		  curl -s -o $TMP_FILENAME "${GEN_TOPO_QC_APRICOT_SERVER}/${2/apricot:\/\/o2\//}\&run_type=${RUNTYPE:-}\&beam_type=${BEAMTYPE:-}\&process=true"
	  else
		  curl -s -o $TMP_FILENAME "${GEN_TOPO_QC_APRICOT_SERVER}/${2/apricot:\/\/o2\//}?run_type=${RUNTYPE:-}\&beam_type=${BEAMTYPE:-}\&process=true"
	  fi

    if [[ $? != 0 ]]; then
      echo "Error fetching QC JSON $2 (4)" 1>&2
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

JSON_TEMP_FILES="()"

QC_CONFIG=
: ${QC_CONFIG_OVERRIDE:=} # set to empty string only if not already set externally
: ${QC_DETECTOR_CONFIG_OVERRIDE:=} # set to empty string only if not already set externally
if [[ -z ${QC_JSON_FROM_OUTSIDE:-} && ! -z ${GEN_TOPO_QC_JSON_FILE:-} && -f $GEN_TOPO_QC_JSON_FILE ]]; then
  QC_JSON_FROM_OUTSIDE=$GEN_TOPO_QC_JSON_FILE
elif [[ -z ${QC_JSON_FROM_OUTSIDE:-} ]]; then
  if [[ $EPNSYNCMODE == 1 || "${GEN_TOPO_LOAD_QC_JSON_FROM_CONSUL:-}" == "1" ]]; then # Sync processing running on the EPN
    [[ -z "${QC_JSON_TPC:-}" ]] && QC_JSON_TPC=apricot://o2/components/qc/ANY/any/tpc-full-qcmn
    [[ -z "${QC_JSON_ITS:-}" ]] && QC_JSON_ITS=apricot://o2/components/qc/ANY/any/its-qcmn-epn-full
    if [[ -z "${QC_JSON_MFT:-}" ]]; then
      if has_detector MFT && has_processing_step MFT_RECO; then
        QC_JSON_MFT=apricot://o2/components/qc/ANY/any/mft-full-qcmn
      else
        QC_JSON_MFT=apricot://o2/components/qc/ANY/any/mft-full-no-tracks-qcmn
      fi
    fi
    if [[ -z "${QC_JSON_TOF:-}" ]]; then
      if has_detector_flp_processing TOF; then
        QC_JSON_TOF=apricot://o2/components/qc/ANY/any/tof-full-qcmn-on-epn
      else
        QC_JSON_TOF=apricot://o2/components/qc/ANY/any/tof-full-epn-qcmn-on-epn
      fi
    fi
    [[ -z "${QC_JSON_FDD:-}" ]] && QC_JSON_FDD=apricot://o2/components/qc/ANY/any/fdd-digits-qc-epn
    [[ -z "${QC_JSON_FT0:-}" ]] && QC_JSON_FT0=apricot://o2/components/qc/ANY/any/ft0-digits-qc-epn
    [[ -z "${QC_JSON_FV0:-}" ]] && QC_JSON_FV0=apricot://o2/components/qc/ANY/any/fv0-digits-qc-epn
    if [[ -z "${QC_JSON_EMC:-}" ]]; then
      if [[ "$BEAMTYPE" == "PbPb" ]]; then
        if has_detector CTP; then
          QC_JSON_EMC=apricot://o2/components/qc/ANY/any/emc-qcmn-epnall-withCTP-PbPb
        else
          QC_JSON_EMC=apricot://o2/components/qc/ANY/any/emc-qcmn-epnall-PbPb
        fi
      else
        if has_detector CTP; then
          QC_JSON_EMC=apricot://o2/components/qc/ANY/any/emc-qcmn-epnall-withCTP
        else
          QC_JSON_EMC=apricot://o2/components/qc/ANY/any/emc-qcmn-epnall
        fi
      fi
    fi
    [[ -z "${QC_JSON_ZDC:-}" ]] && has_processing_step ZDC_RECO && QC_JSON_ZDC=apricot://o2/components/qc/ANY/any/zdc-full-qcmn
    if [[ -z "${QC_JSON_MCH:-}" ]]; then
      if has_detector MCH && has_processing_step MCH_RECO; then
        if has_track_source "MCH-MID"; then
          QC_JSON_MCH=apricot://o2/components/qc/ANY/any/mch-qcmn-epn-full-track-matching
        else
          QC_JSON_MCH=apricot://o2/components/qc/ANY/any/mch-qcmn-epn-full
        fi
      else
        QC_JSON_MCH=apricot://o2/components/qc/ANY/any/mch-qcmn-epn-digits
      fi
    fi
    if [[ -z "${QC_JSON_MID:-}" ]]; then
      if has_detector MID && has_processing_step MID_RECO; then
        QC_JSON_MID=apricot://o2/components/qc/ANY/any/mid-full-qcmn
      else
        QC_JSON_MID=apricot://o2/components/qc/ANY/any/mid-flp_raw-epn_digits-qcmn
      fi
    fi
    [[ -z "${QC_JSON_CPV:-}" ]] && QC_JSON_CPV=apricot://o2/components/qc/ANY/any/cpv-physics-qcmn-epn
    [[ -z "${QC_JSON_TRD:-}" ]] && QC_JSON_TRD=apricot://o2/components/qc/ANY/any/trd-full-qcmn
    [[ -z "${QC_JSON_PHS:-}" ]] && QC_JSON_PHS=apricot://o2/components/qc/ANY/any/phos-raw-clusters-epn
    [[ -z "${QC_JSON_GLO_PRIMVTX:-}" ]] && QC_JSON_GLO_PRIMVTX=apricot://o2/components/qc/ANY/any/glo-vtx-qcmn-epn
    [[ -z "${QC_JSON_GLO_ITSTPC:-}" ]] && QC_JSON_GLO_ITSTPC=apricot://o2/components/qc/ANY/any/glo-itstpc-mtch-qcmn-epn
    if [[ -z "${QC_JSON_TOF_MATCH:-}" ]]; then
      if has_tof_matching_source ITS-TPC && has_tof_matching_source ITS-TPC-TRD; then
        QC_JSON_TOF_MATCH=apricot://o2/components/qc/ANY/any/tof-qcmn-match-itstpctrdtof
      elif has_tof_matching_source ITS-TPC; then
        QC_JSON_TOF_MATCH=apricot://o2/components/qc/ANY/any/tof-qcmn-match-itstpctof
      fi
    fi
    if has_detectors_reco MFT MCH MID && has_matching_qc MFTMCH && has_matching_qc MCHMID; then
        [[ -z "${QC_JSON_GLO_MFTMCH:-}" ]] && QC_JSON_GLO_MFTMCH=apricot://o2/components/qc/ANY/any/glo-mftmchmid-mtch-qcmn-epn
    elif has_detectors_reco MFT MCH && has_matching_qc MFTMCH; then
        [[ -z "${QC_JSON_GLO_MFTMCH:-}" ]] && QC_JSON_GLO_MFTMCH=apricot://o2/components/qc/ANY/any/glo-mftmch-mtch-qcmn-epn
    elif has_detectors_reco MCH MID && has_matching_qc MCHMID; then
        [[ -z "${QC_JSON_GLO_MCHMID:-}" ]] && QC_JSON_GLO_MCHMID=apricot://o2/components/qc/ANY/any/glo-mchmid-mtch-qcmn-epn
    fi
    if has_processing_step ENTROPY_ENCODER && [[ ! -z "$WORKFLOW_DETECTORS_CTF" ]] && [[ $WORKFLOW_DETECTORS_CTF != "NONE" ]] && has_detector CTP; then
      [[ -z "${QC_JSON_CTF_SIZE:-}" ]] && QC_JSON_CTF_SIZE=apricot://o2/components/qc/ANY/any/glo-qc-data-size
    fi
    if [[ "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" ]]; then
      [[ -z "${QC_JSON_GLOBAL:-}" ]] && QC_JSON_GLOBAL=$O2DPG_ROOT/DATA/production/qc-sync/qc-global-epn-staging.json # this must be last
    else
      [[ -z "${QC_JSON_GLOBAL:-}" ]] && QC_JSON_GLOBAL=$O2DPG_ROOT/DATA/production/qc-sync/qc-global-epn.json # this must be last
    fi
  elif [[ $SYNCMODE == 1 ]]; then # Sync processing running locally (CI, laptop)
    [[ -z "${QC_JSON_TPC:-}" ]] && QC_JSON_TPC=$O2DPG_ROOT/DATA/production/qc-sync/tpc.json
    [[ -z "${QC_JSON_ITS:-}" ]] && QC_JSON_ITS=$O2DPG_ROOT/DATA/production/qc-sync/its.json
    if [[ -z "${QC_JSON_MFT:-}" ]]; then
      if has_processing_step MFT_RECO; then
        QC_JSON_MFT=$O2DPG_ROOT/DATA/production/qc-sync/mft-full.json
      else
        QC_JSON_MFT=$O2DPG_ROOT/DATA/production/qc-sync/mft-full-no-tracks.json
      fi
    fi
    [[ -z "${QC_JSON_TOF:-}" ]] && QC_JSON_TOF=$O2DPG_ROOT/DATA/production/qc-sync/tof.json
    [[ -z "${QC_JSON_FDD:-}" ]] && QC_JSON_FDD=$O2DPG_ROOT/DATA/production/qc-sync/fdd.json
    [[ -z "${QC_JSON_FT0:-}" ]] && QC_JSON_FT0=$O2DPG_ROOT/DATA/production/qc-sync/ft0.json
    [[ -z "${QC_JSON_FV0:-}" ]] && QC_JSON_FV0=$O2DPG_ROOT/DATA/production/qc-sync/fv0.json
    [[ -z "${QC_JSON_EMC:-}" ]] && QC_JSON_EMC=$O2DPG_ROOT/DATA/production/qc-sync/emc.json
    [[ -z "${QC_JSON_ZDC:-}" ]] && has_processing_step ZDC_RECO && QC_JSON_ZDC=$O2DPG_ROOT/DATA/production/qc-sync/zdc.json
    [[ -z "${QC_JSON_MCH:-}" ]] && QC_JSON_MCH=$O2DPG_ROOT/DATA/production/qc-sync/mch.json
    [[ -z "${QC_JSON_MID:-}" ]] && QC_JSON_MID=$O2DPG_ROOT/DATA/production/qc-sync/mid-digits.json && has_processing_step MID_RECO && QC_JSON_MID=$O2DPG_ROOT/DATA/production/qc-sync/mid.json
    [[ -z "${QC_JSON_CPV:-}" ]] && QC_JSON_CPV=$O2DPG_ROOT/DATA/production/qc-sync/cpv.json
    [[ -z "${QC_JSON_PHS:-}" ]] && QC_JSON_PHS=$O2DPG_ROOT/DATA/production/qc-sync/phs.json
    [[ -z "${QC_JSON_TRD:-}" ]] && QC_JSON_TRD=$O2DPG_ROOT/DATA/production/qc-sync/trd.json

    [[ -z "${QC_JSON_GLO_PRIMVTX:-}" ]] && QC_JSON_GLO_PRIMVTX=$O2DPG_ROOT/DATA/production/qc-sync/glo-vtx-qcmn-epn.json
    [[ -z "${QC_JSON_GLO_ITSTPC:-}" ]] && QC_JSON_GLO_ITSTPC=$O2DPG_ROOT/DATA/production/qc-sync/glo-itstpc-mtch-qcmn-epn.json
    if [[ -z "${QC_JSON_TOF_MATCH:-}" ]]; then
      if has_tof_matching_source ITS-TPC && has_tof_matching_source ITS-TPC-TRD; then
        QC_JSON_TOF_MATCH=$O2DPG_ROOT/DATA/production/qc-sync/itstpctrdtof.json
      elif has_tof_matching_source ITS-TPC; then
        QC_JSON_TOF_MATCH=$O2DPG_ROOT/DATA/production/qc-sync/itstpctof.json
      fi
    fi
    if has_detectors_reco MFT MCH MID && has_matching_qc MFTMCH && has_matching_qc MCHMID; then
        [[ -z "${QC_JSON_GLO_MFTMCH:-}" ]] && QC_JSON_GLO_MFTMCH=$O2DPG_ROOT/DATA/production/qc-sync/glo-mftmchmid-mtch-qcmn-epn.json
    elif has_detectors_reco MFT MCH && has_matching_qc MFTMCH; then
        [[ -z "${QC_JSON_GLO_MFTMCH:-}" ]] && QC_JSON_GLO_MFTMCH=$O2DPG_ROOT/DATA/production/qc-sync/glo-mftmch-mtch-qcmn-epn.json
    elif has_detectors_reco MCH MID && has_matching_qc MCHMID; then
        [[ -z "${QC_JSON_GLO_MCHMID:-}" ]] && QC_JSON_GLO_MCHMID=$O2DPG_ROOT/DATA/production/qc-sync/glo-mchmid-mtch-qcmn-epn.json
    fi
    [[ -z "${QC_JSON_GLOBAL:-}" ]] && QC_JSON_GLOBAL=$O2DPG_ROOT/DATA/production/qc-sync/qc-global.json # this must be last

    QC_CONFIG_OVERRIDE+="qc.config.conditionDB.url=${DPL_CONDITION_BACKEND:-http://alice-ccdb.cern.ch};"
  else # Async processing
    [[ -z "${QC_JSON_TPC:-}" ]] && QC_JSON_TPC=$O2DPG_ROOT/DATA/production/qc-async/tpc.json
    [[ -z "${QC_JSON_ITS:-}" ]] && QC_JSON_ITS=$O2DPG_ROOT/DATA/production/qc-async/its.json
    [[ -z "${QC_JSON_MFT:-}" ]] && QC_JSON_MFT=$O2DPG_ROOT/DATA/production/qc-async/mft.json
    [[ -z "${QC_JSON_TOF:-}" ]] && QC_JSON_TOF=$O2DPG_ROOT/DATA/production/qc-async/tof.json
    [[ -z "${QC_JSON_HMP:-}" ]] && QC_JSON_HMP=$O2DPG_ROOT/DATA/production/qc-async/hmp.json
    [[ -z "${QC_JSON_FT0:-}" ]] && QC_JSON_FT0=$O2DPG_ROOT/DATA/production/qc-async/ft0.json
    [[ -z "${QC_JSON_FV0:-}" ]] && QC_JSON_FV0=$O2DPG_ROOT/DATA/production/qc-async/fv0.json
    [[ -z "${QC_JSON_FDD:-}" ]] && QC_JSON_FDD=$O2DPG_ROOT/DATA/production/qc-async/fdd.json
    [[ -z "${QC_JSON_MID:-}" ]] && QC_JSON_MID=$O2DPG_ROOT/DATA/production/qc-async/mid.json
    if [[ -z "${QC_JSON_ZDC:-}" ]] && has_processing_step ZDC_RECO; then
      if [[ "$BEAMTYPE" == "PbPb" ]]; then
        QC_JSON_ZDC=$O2DPG_ROOT/DATA/production/qc-async/zdcPbPb.json
      else
        QC_JSON_ZDC=$O2DPG_ROOT/DATA/production/qc-async/zdc.json
      fi
    fi
    if [[ -z "${QC_JSON_EMC:-}" ]]; then
      if [[ "$BEAMTYPE" == "PbPb" ]]; then
        QC_JSON_EMC=$O2DPG_ROOT/DATA/production/qc-async/emc_PbPb.json
      else
        QC_JSON_EMC=$O2DPG_ROOT/DATA/production/qc-async/emc.json
      fi
    fi
    if has_detector_qc MCH && [[ -z "${QC_JSON_MCH:-}" ]]; then
      add_QC_JSON MCH_DIGITS $O2DPG_ROOT/DATA/production/qc-async/mch-digits.json
      if has_processing_step "MCH_RECO"; then
        add_QC_JSON MCH_RECO $O2DPG_ROOT/DATA/production/qc-async/mch-reco.json
        add_QC_JSON MCH_ERRORS $O2DPG_ROOT/DATA/production/qc-async/mch-errors.json
      fi
      if has_track_source "MCH"; then
        add_QC_JSON MCH_TRACKS $O2DPG_ROOT/DATA/production/qc-async/mch-tracks.json
      fi
    fi
    if has_detectors_reco MFT MCH MID && has_matching_qc MFTMCH && has_matching_qc MCHMID; then
        [[ -z "${QC_JSON_GLO_MFTMCH:-}" ]] && QC_JSON_GLO_MFTMCH=$O2DPG_ROOT/DATA/production/qc-async/mftmchmid-tracks.json
    elif has_detectors_reco MFT MCH && has_matching_qc MFTMCH; then
        [[ -z "${QC_JSON_GLO_MFTMCH:-}" ]] && QC_JSON_GLO_MFTMCH=$O2DPG_ROOT/DATA/production/qc-async/mftmch-tracks.json
    elif has_detectors_reco MCH MID && has_matching_qc MCHMID; then
        [[ -z "${QC_JSON_GLO_MCHMID:-}" ]] && QC_JSON_GLO_MCHMID=$O2DPG_ROOT/DATA/production/qc-async/mchmid-tracks.json
    fi
    [[ -z "${QC_JSON_CPV:-}" ]] && QC_JSON_CPV=$O2DPG_ROOT/DATA/production/qc-async/cpv.json
    [[ -z "${QC_JSON_PHS:-}" ]] && QC_JSON_PHS=$O2DPG_ROOT/DATA/production/qc-async/phs.json
    [[ -z "${QC_JSON_TRD:-}" ]] && QC_JSON_TRD=$O2DPG_ROOT/DATA/production/qc-async/trd.json
    # the following two ($QC_JSON_PRIMVTX and $QC_JSON_ITSTPC) replace $QC_JSON_GLO for async processing
    [[ -z "${QC_JSON_GLO_PRIMVTX:-}" ]] && QC_JSON_GLO_PRIMVTX=$O2DPG_ROOT/DATA/production/qc-async/primvtx.json
    [[ -z "${QC_JSON_GLO_ITSTPC:-}" ]] && QC_JSON_GLO_ITSTPC=$O2DPG_ROOT/DATA/production/qc-async/itstpc.json
    if [[ -z "${QC_JSON_TOF_MATCH:-}" ]]; then
      if has_tof_matching_source ITS-TPC && has_tof_matching_source ITS-TPC-TRD; then
        QC_JSON_TOF_MATCH=$O2DPG_ROOT/DATA/production/qc-async/itstpctofwtrd.json
      elif has_tof_matching_source ITS-TPC; then
        QC_JSON_TOF_MATCH=$O2DPG_ROOT/DATA/production/qc-async/itstpctof.json
      fi
    fi
    if [[ -z "${QC_JSON_PID_FT0TOF:-}" ]]; then
      if has_tof_matching_source ITS-TPC && has_tof_matching_source ITS-TPC-TRD; then
        QC_JSON_PID_FT0TOF=$O2DPG_ROOT/DATA/production/qc-async/pidft0tofwtrd.json
      elif has_tof_matching_source ITS-TPC; then
        QC_JSON_PID_FT0TOF=$O2DPG_ROOT/DATA/production/qc-async/pidft0tof.json
      fi
    fi
    [[ -z "${QC_JSON_GLOBAL:-}" ]] && QC_JSON_GLOBAL=$O2DPG_ROOT/DATA/production/qc-async/qc-global.json # this must be last
  fi

  if [[ -z "${GEN_TOPO_WORKDIR:-}" ]]; then
    echo This script must be run via the gen_topo scripts, or a GEN_TOPO_WORKDIR must be provided where merged JSONS are stored 1>&2
    exit 1
  fi


  # TOF matching
  if has_detector_qc TOF && [[ $WORKFLOW_DETECTORS_QC =~ (^|,)"TOF_MATCH"(,|$) ]] && [ ! -z "${QC_JSON_TOF_MATCH:-}" ]; then
    add_QC_JSON matchTOF ${QC_JSON_TOF_MATCH}
  fi

  # Detector QC
  for i in ${LIST_OF_DETECTORS//,/ }; do
    DET_JSON_FILE="QC_JSON_$i"
    if has_detector_qc $i && [ ! -z "${!DET_JSON_FILE:-}" ]; then
      add_QC_JSON $i ${!DET_JSON_FILE}
    fi
  done

  # Global reconstruction QC
  for i in ${LIST_OF_GLORECO//,/ }; do
    DET_JSON_FILE="QC_JSON_GLO_$i"
    if has_matching_qc $i && [ ! -z "${!DET_JSON_FILE:-}" ]; then
      if [[ $i == "PRIMVTX" ]] && ! has_detector_reco ITS; then continue; fi
      if [[ $i == "ITSTPC" ]] && ! has_detectors_reco ITS TPC; then continue; fi
      add_QC_JSON GLO_$i ${!DET_JSON_FILE}

      if [[ $i == "ITSTPC" ]]; then
        LOCAL_FILENAME=${JSON_FILES//*\ /}
        # replace the input sources depending on the detector compostition and matching detectors
        ITSTPCMatchQuery="trackITSTPC:GLO/TPCITS/0;trackITSTPCABREFS:GLO/TPCITSAB_REFS/0;trackITSTPCABCLID:GLO/TPCITSAB_CLID/0;trackTPC:TPC/TRACKS;trackTPCClRefs:TPC/CLUSREFS/0;trackITS:ITS/TRACKS/0;trackITSROF:ITS/ITSTrackROF/0;trackITSClIdx:ITS/TRACKCLSID/0;alpparITS:ITS/ALPIDEPARAM/0?lifetime=condition&ccdb-path=ITS/Config/AlpideParam;SVParam:GLO/SVPARAM/0?lifetime=condition&ccdb-path=GLO/Config/SVertexerParam"
        TRACKSOURCESK0="ITS,TPC,ITS-TPC"
        if [[ $BEAMTYPE != "cosmic" ]] && (has_processing_step MATCH_SECVTX || has_detector_matching SECVTX); then
          if [[ $SYNCMODE == 1 ]] || [[ $EPNSYNCMODE == 1 ]]; then
            HAS_K0_ENABLED=$(jq -r .qc.tasks.MTCITSTPC.taskParameters.doK0QC "${LOCAL_FILENAME}")
          else
            HAS_K0_ENABLED=$(jq -r .qc.tasks.GLOMatchTrITSTPC.taskParameters.doK0QC "${LOCAL_FILENAME}")
          fi
          if [[ $HAS_K0_ENABLED == "true" ]]; then
            ITSTPCMatchQuery+=";p2decay3body:GLO/PVTX_3BODYREFS/0;decay3body:GLO/DECAYS3BODY/0;decay3bodyIdx:GLO/DECAYS3BODY_IDX/0;p2cascs:GLO/PVTX_CASCREFS/0;cascs:GLO/CASCS/0;cascsIdx:GLO/CASCS_IDX/0;p2v0s:GLO/PVTX_V0REFS/0;v0s:GLO/V0S/0;v0sIdx:GLO/V0S_IDX/0;pvtx_tref:GLO/PVTX_TRMTCREFS/0;pvtx_trmtc:GLO/PVTX_TRMTC/0;pvtx:GLO/PVTX/0;clusTPCoccmap:TPC/TPCOCCUPANCYMAP/0;clusTPC:TPC/CLUSTERNATIVE;clusTPCshmap:TPC/CLSHAREDMAP/0;trigTPC:TPC/TRIGGERWORDS/0"
            if has_secvtx_source ITS-TPC-TRD; then
              ITSTPCMatchQuery+=";trigITSTPCTRD:TRD/TRGREC_ITSTPC/0;trackITSTPCTRD:TRD/MATCH_ITSTPC/0"
              TRACKSOURCESK0+=",ITS-TPC-TRD"
            fi
            if has_secvtx_source ITS-TPC-TOF; then
              ITSTPCMatchQuery+=";matchITSTPCTOF:TOF/MTC_ITSTPC/0"
              TRACKSOURCESK0+=",ITS-TPC-TOF"
            fi
            if has_secvtx_source ITS-TPC-TRD-TOF; then
              ITSTPCMatchQuery+=";matchITSTPCTRDTOF:TOF/MTC_ITSTPCTRD/0"
              TRACKSOURCESK0+=",ITS-TPC-TRD-TOF"
            fi
            if has_secvtx_source TPC-TRD; then
              ITSTPCMatchQuery+=";trigTPCTRD:TRD/TRGREC_TPC/0;trackTPCTRD:TRD/MATCH_TPC/0"
              TRACKSOURCESK0+=",TPC-TRD"
            fi
            if has_secvtx_source TPC-TOF; then
              ITSTPCMatchQuery+=";matchTPCTOF:TOF/MTC_TPC/0;trackTPCTOF:TOF/TOFTRACKS_TPC/0"
              TRACKSOURCESK0+=",TPC-TOF"
            fi
            if has_secvtx_source TPC-TRD-TOF; then
              ITSTPCMatchQuery+=";matchTPCTRDTOF/TOF/MTC_TPCTRD/0"
              TRACKSOURCESK0+=",TPC-TRD-TOF"
            fi
            if has_secvtx_source TOF; then
              ITSTPCMatchQuery+=";tofcluster:TOF/CLUSTERS/0"
              TRACKSOURCESK0+=",TOF"
            fi
            if has_secvtx_source TRD; then
              TRACKSOURCESK0+=",TRD"
            fi
          fi
          TEMP_FILE=$(mktemp "${GEN_TOPO_WORKDIR:+$GEN_TOPO_WORKDIR/}${i}"_XXXXXXX)
          if [[ $SYNCMODE == 1 ]] || [[ $EPNSYNCMODE == 1 ]]; then
            cat "${LOCAL_FILENAME}" | jq "(.dataSamplingPolicies[] | select(.id == \"ITSTPCmSampK0\") | .query) = \"$ITSTPCMatchQuery\" | .qc.tasks.MTCITSTPC.taskParameters.trackSourcesK0 = \"$TRACKSOURCESK0\"" >"$TEMP_FILE"
          else
            cat "${LOCAL_FILENAME}" | jq ".qc.tasks.GLOMatchTrITSTPC.dataSource.query = \"$ITSTPCMatchQuery\" | .qc.tasks.GLOMatchTrITSTPC.taskParameters.trackSourcesK0 = \"$TRACKSOURCESK0\"" >"$TEMP_FILE"
          fi
        else
          # we need to force that the K0s part is disabled
          TEMP_FILE=$(mktemp "${GEN_TOPO_WORKDIR:+$GEN_TOPO_WORKDIR/}${i}"_XXXXXXX)
          if [[ $SYNCMODE == 1 ]] || [[ $EPNSYNCMODE == 1 ]]; then
            cat "${LOCAL_FILENAME}" | jq "(.dataSamplingPolicies[] | select(.id == \"ITSTPCmSampK0\") | .query) = \"$ITSTPCMatchQuery\" | .qc.tasks.MTCITSTPC.taskParameters.trackSourcesK0 = \"$TRACKSOURCESK0\" | .qc.tasks.MTCITSTPC.taskParameters.doK0QC = \"false\"" >"$TEMP_FILE"
          else
            cat "${LOCAL_FILENAME}" | jq ".qc.tasks.GLOMatchTrITSTPC.dataSource.query = \"$ITSTPCMatchQuery\" | .qc.tasks.GLOMatchTrITSTPC.taskParameters.trackSourcesK0 = \"$TRACKSOURCESK0\" | .qc.tasks.GLOMatchTrITSTPC.taskParameters.doK0QC = \"false\"" >"$TEMP_FILE"
          fi
        fi
        JSON_FILES=${JSON_FILES/$LOCAL_FILENAME/$TEMP_FILE}
        JSON_TEMP_FILES+=("$TEMP_FILE")
      fi
    fi
  done

  # PID QC
  for i in ${LIST_OF_PID//,/ }; do
    PIDDETFORFILE=${i//-/}
    PID_JSON_FILE="QC_JSON_PID_$PIDDETFORFILE"
    if has_pid_qc $i && [ ! -z "${!PID_JSON_FILE:-}" ]; then
      add_QC_JSON pid$i ${!PID_JSON_FILE}
    fi
  done

  # CTF QC
  if [[ ! -z "${QC_JSON_CTF_SIZE:-}" ]]; then
    add_QC_JSON GLO_CTF ${QC_JSON_CTF_SIZE}
#  add_pipe_separated QC_DETECTOR_CONFIG_OVERRIDE '.qc.tasks.CTFSize.taskParameters.detectors=\"${WORKFLOW_DETECTORS}\"'
  fi

  # arbitrary extra QC
  if [[ ! -z "${QC_JSON_EXTRA:-}" ]]; then
    add_QC_JSON EXTRA ${QC_JSON_EXTRA}
  fi

  # extra settings depending on available detectors
  # for strings remember to escape e.g. " and ;
  # e.g. .qc.tasks.Tracking.taskParameters.dataSource.query=\"tracks:TPC/TRACKS\;clusters:TPC/CLUSTERS\"
  if [[ -z "${DISABLE_QC_DETECTOR_CONFIG_OVERRIDE:-}" ]]; then
    if has_detector_qc TRD && [[ ! -z ${QC_JSON_TRD:-} ]]; then # extra settings for TRD QC
      if ! has_matching_qc ITSTPCTRD || ! has_detectors_reco ITS TPC TRD; then
        add_pipe_separated QC_DETECTOR_CONFIG_OVERRIDE '.qc.tasks.Tracking.active=false'
        add_pipe_separated QC_DETECTOR_CONFIG_OVERRIDE '.qc.tasks.PHTrackMatch.active=false'
      fi
      if has_matching_qc TPCTRD && has_detectors_reco TPC TRD; then # should be only enabled in async
        add_pipe_separated QC_DETECTOR_CONFIG_OVERRIDE '.qc.tasks.Tracking.dataSource.query=\"trackITSTPCTRD:TRD/MATCH_ITSTPC\;trigITSTPCTRD:TRD/TRGREC_ITSTPC\;trackTPCTRD:TRD/MATCH_TPC\;trigTPCTRD:TRD/TRGREC_TPC\"'
        add_pipe_separated QC_DETECTOR_CONFIG_OVERRIDE '.qc.tasks.Tracking.taskParameters.trackSources=\"ITS-TPC-TRD,TPC-TRD\"'
      fi
    fi
  fi

  if [[ ! -z "$JSON_FILES" ]]; then
    if [[ -z "${GEN_TOPO_QC_JSON_FILE:-}" ]]; then
      mkdir -p $GEN_TOPO_WORKDIR/json_cache
      if [[ "${GEN_TOPO_ONTHEFLY:-}" == "1" ]]; then
        find $GEN_TOPO_WORKDIR/json_cache/ -maxdepth 1 -type f -mtime +30 | xargs rm -f
      fi
      MERGED_JSON_FILENAME=$GEN_TOPO_WORKDIR/json_cache/$(date +%Y%m%d-%H%M%S)-$$-$RANDOM-$OUTPUT_SUFFIX.json
    else
      MERGED_JSON_FILENAME=$GEN_TOPO_QC_JSON_FILE
    fi
    jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))'${QC_DETECTOR_CONFIG_OVERRIDE} $QC_JSON_GLOBAL $JSON_FILES > $MERGED_JSON_FILENAME
    if [[ $? != 0 ]]; then
      echo Merging QC workflow with JSON files $JSON_FILES failed 1>&2
      exit 1
    fi
    MERGED_JSON_FILENAME=$(realpath $MERGED_JSON_FILENAME)

    # Clean up: delete the temporary files after use
    for tf in "${JSON_TEMP_FILES[@]}"; do
      rm -f "$tf"
    done

    if [[ "${QC_REDIRECT_MERGER_TO_LOCALHOST:-}" == "1" ]]; then
      sed -i.bak -E 's/( *)"remoteMachine" *: *".*"(,?) *$/\1"remoteMachine": "127.0.0.1"\2/' $MERGED_JSON_FILENAME
      unlink $MERGED_JSON_FILENAME.bak
      QC_CONFIG_OVERRIDE+="qc.config.database.host=ccdb-test.cern.ch:8080;"
    fi

    if [[ ! -z ${GEN_TOPO_QC_OVERRIDE_CCDB_SERVER:-} ]]; then
      sed -i "s,http://alice-ccdb.cern.ch,$GEN_TOPO_QC_OVERRIDE_CCDB_SERVER,g" $MERGED_JSON_FILENAME
    fi
    QC_JSON_FROM_OUTSIDE="$MERGED_JSON_FILENAME"
  fi

  rm -Rf $FETCHTMPDIR
fi

[[ $EPNSYNCMODE == 1 && $NUMAGPUIDS == 1 ]] && QC_CONFIG_OVERRIDE+="qc.config.infologger.filterDiscardFile=../../qc-_ID_-${NUMAID}.log;"
[[ $EPNSYNCMODE == 0 ]] && QC_CONFIG+=" --no-infologger"

[[ ! -z $QC_CONFIG_OVERRIDE ]] && QC_CONFIG+=" --override-values \"$QC_CONFIG_OVERRIDE\""

if [[ ! -z "${QC_JSON_FROM_OUTSIDE:-}" ]]; then
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
  if [[ -z ${QC_CONFIG_PARAM:-} ]]; then
    if [[ $SYNCMODE == 1 ]]; then
      QC_CONFIG_PARAM="--local --host ${QC_HOST:-localhost}"
    else
      QC_CONFIG_PARAM="--local-batch=QC.root"
    fi
  fi

  add_W o2-qc "--config json://$QC_JSON_FROM_OUTSIDE ${QC_CONFIG_PARAM} ${QC_CONFIG}"

fi

if [[ ! -z ${GEN_TOPO_QC_JSON_FILE:-} ]]; then
  flock -u 101 || exit 1
fi

true # everything OK up to this point, so the script should return 0 (it is !=0 if the last check failed)
