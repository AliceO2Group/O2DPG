#!/bin/bash

# Non-zero exit code already if one command in a pipe fails
set -o pipefail

if [[ -z "$NHBPERTF" ]]; then  # try to extract from JDL variables
  NHBPERTF=32
  if [[ ! -z "$ALIEN_JDL_NHBPERTF" ]] && [[ "$ALIEN_JDL_NHBPERTF" != 0 ]]; then
    NHBPERTF=$ALIEN_JDL_NHBPERTF
    echo "Set NHBF per TF to $NHBPERTF from ALIEN_JDL_NHBPERTF"
  elif [[ ! -z "$ALIEN_JDL_LPMRUNNUMBER" ]]; then
    [[ "$ALIEN_JDL_LPMRUNNUMBER" -lt 534125 ]] && NHBPERTF=128 || NHBPERTF=32
    echo "Set NHBF per TF to $NHBPERTF from ALIEN_JDL_LPMRUNNUMBER=$ALIEN_JDL_LPMRUNNUMBER"
  else
    echo "Set NHBF per TF to $NHBPERTF as default"
  fi
else
  echo "Set NHBF per TF to $NHBPERTF as requested explicitly"
fi
export NHBPERTF

# ---------------------------------------------------------------------------------------------------------------------
# Get this script's directory and load common settings (use zsh first (e.g. on Mac) and fallback on `readlink -f` if zsh is not there)
: ${GEN_TOPO_MYDIR:="$O2DPG_ROOT/DATA/production"}
source $GEN_TOPO_MYDIR/gen_topo_helper_functions.sh || { echo "gen_topo_helper_functions.sh failed" 1>&2 && exit 1; }
source $GEN_TOPO_MYDIR/setenv.sh || { echo "setenv.sh failed" 1>&2 && exit 1; }

: ${CTF_MINSIZE:="2000000000"}                    # accumulate CTFs until file size reached
: ${CTF_MAX_PER_FILE:="1000000"}                  # but no more than given number of CTFs per file

TIMEFRAME_RATE_LIMIT=2
: ${NUMAID:="0"}

if [[ ${ALIEN_JDL_CPUCORES:-} == 8 ]] || [[ ${ALIEN_JDL_CPUCORES:-} == 16 ]]; then # 16 is used for jobs on EPNs
  export MULTIPLICITY_PROCESS_tpc_entropy_decoder=3
  export MULTIPLICITY_PROCESS_tpc_entropy_encoder=3
  SHMSIZE=16000000000
  TIMEFRAME_RATE_LIMIT=3
fi

if [[ ! -z "$ALIEN_JDL_SHMSIZE" ]]; then export SHMSIZE=$ALIEN_JDL_SHMSIZE; fi
if [[ ! -z "$ALIEN_JDL_MULTIPLICITYPROCESSTPCENTROPYDECODER" ]]; then export MULTIPLICITY_PROCESS_tpc_entropy_decoder=$ALIEN_JDL_MULTIPLICITYPROCESSTPCENTROPYDECODER; fi
if [[ ! -z "$ALIEN_JDL_MULTIPLICITYPROCESSTPCENTROPYENCODER" ]]; then export MULTIPLICITY_PROCESS_tpc_entropy_encoder=$ALIEN_JDL_MULTIPLICITYPROCESSTPCENTROPYENCODER; fi


# Set general arguments
source $GEN_TOPO_MYDIR/getCommonArgs.sh || { echo "getCommonArgs.sh failed" 1>&2 && exit 1; }

[[ -z ${SHM_MANAGER_SHMID:-} ]] && ( [[ ${EXTINPUT:-} == 1 ]] || [[ ${NUMAGPUIDS:-} != 0 ]] ) && ARGS_ALL+=" --no-cleanup"

# let's set O2JOBID and SHMEMID
O2JOBIDscript="$O2DPG_ROOT/DATA/production/common/setVarsFromALIEN_PROC_ID.sh"
if [[ -f "setVarsFromALIEN_PROC_ID.sh" ]]; then
  O2JOBIDscript="setVarsFromALIEN_PROC_ID.sh"
fi
source $O2JOBIDscript

[[ ! -z ${TIMEFRAME_RATE_LIMIT:-} ]] && [[ ${TIMEFRAME_RATE_LIMIT:-} != 0 ]] && ARGS_ALL+=" --timeframes-rate-limit $TIMEFRAME_RATE_LIMIT --timeframes-rate-limit-ipcid ${O2JOBID:-$NUMAID}"
[[ ! -z ${TIMEFRAME_SHM_LIMIT:-} ]] && ARGS_ALL+=" --timeframes-shm-limit $TIMEFRAME_SHM_LIMIT"

{ source $O2DPG_ROOT/DATA/production/workflow-multiplicities.sh; [[ $? != 0 ]] && echo "workflow-multiplicities.sh failed" 1>&2 && exit 1; }

# entropy encoding/decoding mode, '' is equivalent to '--ans-version compat' (compatible with < 09/2023 data),
# use '--ans-version 1.0 --ctf-dict none' for the new per-TF dictionary mode
: ${RANS_OPT:="--ans-version 1.0 --ctf-dict none"}

WORKFLOW= # Make sure we start with an empty workflow

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -f|--irframes-selection)
      IRFRAMES="$2"
      shift
      shift
      ;;
    -c|--ctfs-list)
      CTFLIST=$2
      shift
      shift
      ;;
    *)
    POSITIONAL+=("$1")
    shift
    ;;
  esac
done

if [[ -z ${IRFRAMES:-} ]] || [[ -z ${CTFLIST:-} ]] ; then
  echo "Format: ${0##*/} -f <IRFramesFile> -c <CTFsList>"
  exit 1  
fi

[[ "0${ALLOW_MISSING_DET:-}" == "00" ]] && ALLOW_MISSING_DET= || ALLOW_MISSING_DET="--allow-missing-detectors"
[[ "0${SKIP_SKIMMED_OUT_TF:-}" == "00" ]] && SKIP_SKIMMED_OUT_TF= || SKIP_SKIMMED_OUT_TF="--skip-skimmed-out-tf"

: ${DEF_MARGIN_BWD:=55}                           # default backward margin to account for time misalignments
: ${DEF_MARGIN_FWD:=55}                           # default forward margin to account for time misalignments

if [[ -z ${NO_ITSMFT_MASKING:-} ]] ; then
  has_detector_ctf ITS && export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="$ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow --its-digits"
  has_detector_ctf MFT && export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="$ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow --mft-digits"
fi

add_W o2-ctf-reader-workflow "--ctf-data-subspec 1 --ir-frames-files $IRFRAMES $SKIP_SKIMMED_OUT_TF --ctf-input $CTFLIST ${INPUT_FILE_COPY_CMD+--copy-cmd} ${INPUT_FILE_COPY_CMD} --onlyDet $WORKFLOW_DETECTORS $ALLOW_MISSING_DET --pipeline $(get_N tpc-entropy-decoder TPC REST 1 TPCENTDEC)" "HBFUtils.nHBFPerTF=$NHBPERTF"

if [[ -z ${NO_ITSMFT_MASKING:-} ]] ; then
  has_detector_ctf ITS && add_W o2-its-reco-workflow "--digits-from-upstream --disable-mc --disable-tracking --disable-root-output --pipeline $(get_N its-tracker ITS REST 1 ITSTRK)" "ITSClustererParam.maxBCDiffToMaskBias=10;"
  has_detector_ctf MFT && add_W o2-mft-reco-workflow "--digits-from-upstream --disable-mc --disable-tracking --disable-root-output --pipeline $(get_N mft-tracker MFT REST 1 MFTTRK)" "MFTClustererParam.maxBCDiffToMaskBias=10;"    
fi

has_detector_ctf ITS && add_W o2-itsmft-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${ITS_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${ITS_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${ITS_ENC_MEMFACT:-1.5} --pipeline $(get_N its-entropy-encoder ITS CTF 1)"
has_detector_ctf MFT && add_W o2-itsmft-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${MFT_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${MFT_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${MFT_ENC_MEMFACT:-1.5} --runmft true --pipeline $(get_N mft-entropy-encoder MFT CTF 1)"
has_detector_ctf TPC && add_W o2-tpc-reco-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${TPC_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${TPC_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${TPC_ENC_MEMFACT:-1.} --input-type compressed-clusters-flat --output-type encoded-clusters,disable-writer --pipeline $(get_N tpc-entropy-encoder TPC CTF 1 TPCENT)"
has_detector_ctf TRD && add_W o2-trd-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${TRD_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${TRD_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${TRD_ENC_MEMFACT:-1.5} --pipeline $(get_N trd-entropy-encoder TRD CTF 1 TRDENT)"
has_detector_ctf TOF && add_W o2-tof-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${TOF_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${TOF_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${TOF_ENC_MEMFACT:-1.5} --pipeline $(get_N tof-entropy-encoder TOF CTF 1)"
has_detector_ctf FT0 && add_W o2-ft0-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${FT0_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${FT0_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${FT0_ENC_MEMFACT:-1.5} --pipeline $(get_N ft0-entropy-encoder FT0 CTF 1)"
has_detector_ctf FV0 && add_W o2-fv0-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${FV0_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${FV0_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${FV0_ENC_MEMFACT:-1.5} --pipeline $(get_N fv0-entropy-encoder FV0 CTF 1)"
has_detector_ctf FDD && add_W o2-fdd-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${FDD_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${FDD_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${FDD_ENC_MEMFACT:-1.5} --pipeline $(get_N fdd-entropy-encoder FDD CTF 1)"
has_detector_ctf MID && add_W o2-mid-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${MID_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${MID_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${MID_ENC_MEMFACT:-1.5} --pipeline $(get_N mid-entropy-encoder MID CTF 1)"
has_detector_ctf MCH && add_W o2-mch-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${MCH_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${MCH_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${MCH_ENC_MEMFACT:-1.5} --pipeline $(get_N mch-entropy-encoder MCH CTF 1)"
has_detector_ctf PHS && add_W o2-phos-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${PHS_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${PHS_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${PHS_ENC_MEMFACT:-1.5} --pipeline $(get_N phos-entropy-encoder PHS CTF 1)"
has_detector_ctf CPV && add_W o2-cpv-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${CPV_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${CPV_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${CPV_ENC_MEMFACT:-1.5} --pipeline $(get_N cpv-entropy-encoder CPV CTF 1)"
has_detector_ctf EMC && add_W o2-emcal-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${EMC_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${EMC_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${EMC_ENC_MEMFACT:-1.5} --pipeline $(get_N emcal-entropy-encoder EMC CTF 1)"
has_detector_ctf ZDC && add_W o2-zdc-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${ZDC_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${ZDC_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${ZDC_ENC_MEMFACT:-1.5} --pipeline $(get_N zdc-entropy-encoder ZDC CTF 1)"
has_detector_ctf HMP && add_W o2-hmpid-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${HMP_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${HMP_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${HMP_ENC_MEMFACT:-1.5} --pipeline $(get_N hmpid-entropy-encoder HMP CTF 1)"
has_detector_ctf CTP && add_W o2-ctp-entropy-encoder-workflow "$RANS_OPT --select-ir-frames --irframe-margin-bwd ${CTP_MARGIN_BWD:-$DEF_MARGIN_BWD} --irframe-margin-fwd ${CTP_MARGIN_FWD:-$DEF_MARGIN_FWD} --mem-factor ${CTP_ENC_MEMFACT:-1.5} --pipeline $(get_N its-entropy-encoder CTP CTF 1)"

add_W o2-ctf-writer-workflow "--output-dir $CTF_DIR --min-file-size ${CTF_MINSIZE} --max-ctf-per-file ${CTF_MAX_PER_FILE} --onlyDet $WORKFLOW_DETECTORS_CTF $CTF_MAXDETEXT"

# ---------------------------------------------------------------------------------------------------------------------
# DPL run binary
WORKFLOW+="o2-dpl-run $ARGS_ALL $GLOBALDPLOPT -b --run"

PRINT_WORKFLOW=1
[[ ${WORKFLOWMODE:-} == "print" || "0${PRINT_WORKFLOW:-}" == "01" ]] && echo "#Workflow command:\n\n${WORKFLOW}\n" | sed -e "s/\\\\n/\n/g" -e"s/| */| \\\\\n/g" | eval cat $( [[ ${WORKFLOWMODE:-} == "dds" ]] && echo '1>&2')
if [[ ${WORKFLOWMODE:-} != "print" ]]; then eval $WORKFLOW; else true; fi

# Adding a log file with the number of skimmed CTFs. If we arrive here, it means that the processing was fine
ls -l o2_ctf*.root | wc -l > nSkimmedCTFs.log
