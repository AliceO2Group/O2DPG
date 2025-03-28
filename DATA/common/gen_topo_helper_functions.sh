#!/bin/bash

# used to avoid sourcing this file 2x
if [[ -z ${SOURCE_GUARD_FUNCTIONS:-} ]]; then
SOURCE_GUARD_FUNCTIONS=1

has_detector()
{
  [[ $WORKFLOW_DETECTORS =~ (^|,)"$1"(,|$) ]]
}

has_detector_from_global_reader_clusters()
{
  [[ $WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS =~ (^|,)"$1"(,|$) ]]
}

has_detector_from_global_reader_tracks()
{
  [[ $WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS =~ (^|,)"$1"(,|$) ]]
}

has_detector_from_global_reader()
{
  has_detector_from_global_reader_tracks $1 || has_detector_from_global_reader_clusters $1
}

has_detector_calib()
{
  has_detector $1 && [[ $WORKFLOW_DETECTORS_CALIB =~ (^|,)"$1"(,|$) ]]
}

has_detector_reco()
{
  has_detector $1 && [[ $WORKFLOW_DETECTORS_RECO =~ (^|,)"$1"(,|$) ]]
}

has_detector_ctf()
{
  has_detector $1 && [[ $WORKFLOW_DETECTORS_CTF =~ (^|,)"$1"(,|$) ]]
}

has_detector_flp_processing()
{
  has_detector $1 && [[ $WORKFLOW_DETECTORS_FLP_PROCESSING =~ (^|,)"$1"(,|$) ]]
}

has_detector_matching()
{
  [[ $WORKFLOW_DETECTORS_MATCHING =~ (^|,)"ALL"(,|$) ]] || [[ $WORKFLOW_DETECTORS_MATCHING =~ (^|,)"$1"(,|$) ]]
}

has_detector_gpu()
{
  has_detector $1 && [[ $WORKFLOW_DETECTORS_GPU =~ (^|,)"$1"(,|$) ]]
}

has_secvtx_source()
{
  [[ $SVERTEXING_SOURCES =~ (^|,)"ALL"(,|$) ]] || [[ $SVERTEXING_SOURCES =~ (^|,)"$1"(,|$) ]]
}

has_detector_qc()
{
  has_detector $1 && [[ $WORKFLOW_DETECTORS_QC =~ (^|,)"$1"(,|$) ]]
}

has_matching_qc()
{
  has_detector_matching $1 && [[ $WORKFLOW_DETECTORS_QC =~ (^|,)"$1"(,|$) ]]
}

has_pid_qc()
{
    PIDDETECTORS=$(echo $1 | tr "-" "\n")
    for PIDDETECTOR in $PIDDETECTORS; do
        if [[ $PIDDETECTOR == "TOF" ]]; then
            (! has_detectors_reco ITS TPC TOF || ! has_detector_matching ITSTPCTOF) && return 1
        fi
        ! has_detector_qc $PIDDETECTOR && return 1
    done
    return 0
}

has_track_source()
{
  [[ $TRACK_SOURCES =~ (^|,)"$1"(,|$) ]]
}

has_tof_matching_source()
{
  [[ $TOF_SOURCES =~ (^|,)"$1"(,|$) ]]
}

workflow_has_parameter()
{
  [[ $WORKFLOW_PARAMETERS =~ (^|,)"$1"(,|$) ]]
}

has_processing_step()
{
  [[ ${WORKFLOW_EXTRA_PROCESSING_STEPS:-} =~ (^|,)"$1"(,|$) ]]
}

_check_multiple()
{
  CHECKER=$1
  shift
  while true; do
    if [[ -z ${1:-} ]]; then return 0; fi
    if ! $CHECKER $1; then return 1; fi
    shift
  done
}

has_detectors()
{
  _check_multiple has_detector "$@"
}

has_detectors_qc()
{
  _check_multiple has_detector_qc "$@"
}

has_detectors_calib()
{
  _check_multiple has_detector_calib "$@"
}

has_detectors_reco()
{
  _check_multiple has_detector_reco "$@"
}

has_detectors_ctf()
{
  _check_multiple has_detector_ctf "$@"
}

has_detectors_flp_processing()
{
  _check_multiple has_detector_flp_processing "$@"
}

has_detectors_gpu()
{
  _check_multiple has_detector_gpu "$@"
}

workflow_has_parameters()
{
  _check_multiple workflow_has_parameter "$@"
}

add_comma_separated()
{
  if (( $# < 2 )); then
    echo "$# parameters received"
    echo "Function name: ${FUNCNAME} expects at least 2 parameters:"
    echo "it concatenates the string in 1st parameter by the following"
    echo "ones, forming comma-separated string. $# parameters received"
    exit 1
  fi

  for ((i = 2; i <= $#; i++ )); do
    if [[ -z ${!1:-} ]]; then
      eval $1+="${!i}"
    else
      eval $1+=",${!i}"
    fi
  done
}

add_semicolon_separated()
{
  if (( $# < 2 )); then
    echo "$# parameters received"
    echo "Function name: ${FUNCNAME} expects at least 2 parameters:"
    echo "it concatenates the string in 1st parameter by the following"
    echo "ones, forming semi-colon-separated string. $# parameters received"
    exit 1
  fi

  for ((i = 2; i <= $#; i++ )); do
    if [[ -z ${!1:-} ]]; then
      eval $1+="${!i}"
    else
      eval $1+="\;${!i}"
    fi
  done
}

add_pipe_separated()
{
  if (( $# < 2 )); then
    echo "$# parameters received"
    echo "Function name: ${FUNCNAME} expects at least 2 parameters:"
    echo "it concatenates the string in 1st parameter by the following"
    echo "ones, forming pipe-separated string. $# parameters received"
    exit 1
  fi

  for ((i = 2; i <= $#; i++ )); do
    eval $1+="\|${!i}"
  done
}

# ---------------------------------------------------------------------------------------------------------------------
# Helper functions for multiplicities

get_N() # USAGE: get_N [processor-name] [DETECTOR_NAME] [RAW|CTF|REST] [threads, to be used for process scaling. 0 = do not scale this one process] [optional name [FOO] of variable "$N_[FOO]" with default, default = 1]
{
  local NAME_FACTOR="N_F_$3"
  local NAME_DET="MULTIPLICITY_FACTOR_DETECTOR_$2"
  local NAME_PROC="MULTIPLICITY_PROCESS_${1//-/_}"
  local NAME_PROC_FACTOR="MULTIPLICITY_FACTOR_PROCESS_${1//-/_}"
  local NAME_DEFAULT="N_${5:-}"
  local MULT=${!NAME_PROC:-$((${!NAME_FACTOR} * ${!NAME_DET:-1} * ${!NAME_PROC_FACTOR:-1} * ${!NAME_DEFAULT:-1}))}
  [[ ! -z ${EPN_GLOBAL_SCALING:-} && $1 != "gpu-reconstruction" ]] && MULT=$(($MULT * $EPN_GLOBAL_SCALING))
  if [[ ${GEN_TOPO_AUTOSCALE_PROCESSES_GLOBAL_WORKFLOW:-} == 1 && -z ${!NAME_PROC:-} && ${GEN_TOPO_AUTOSCALE_PROCESSES:-} == 1 && ($WORKFLOWMODE != "print" || ${GEN_TOPO_RUN_HOME_TEST:-} == 1) && ${4:-} != 0 ]]; then
    echo $1:\$\(\(\($MULT*\$AUTOSCALE_PROCESS_FACTOR/100\) \< 16 ? \($MULT*\$AUTOSCALE_PROCESS_FACTOR/100\) : 16\)\)
  else
    echo $1:$MULT
  fi
}

math_max()
{
  echo $(($1 > $2 ? $1 : $2))
}
math_min()
{
  echo $(($1 < $2 ? $1 : $2))
}

# ---------------------------------------------------------------------------------------------------------------------
# Helper to check if root ouput is requested for certain process

needs_root_output()
{
  local NAME_PROC_ENABLE_ROOT_OUTPUT="ENABLE_ROOT_OUTPUT_${1//-/_}"
  [[ ! -z ${!NAME_PROC_ENABLE_ROOT_OUTPUT+x} ]]
}

# ---------------------------------------------------------------------------------------------------------------------
# Helper to add binaries to workflow adding automatic and custom arguments

add_W() # Add binarry to workflow command USAGE: add_W [BINARY] [COMMAND_LINE_OPTIONS] [CONFIG_KEY_VALUES] [Add ARGS_ALL_CONFIG, optional, default = 1]
{
  local NAME_PROC_ARGS="ARGS_EXTRA_PROCESS_${1//-/_}"
  local NAME_PROC_CONFIG="CONFIG_EXTRA_PROCESS_${1//-/_}"
  local KEY_VALUES=
  [[ "0${4:-}" != "00" ]] && KEY_VALUES+="$ARGS_ALL_CONFIG;"
  [[ ! -z "${3:-}" ]] && KEY_VALUES+="$3;"
  [[ ! -z ${!NAME_PROC_CONFIG:-} ]] && KEY_VALUES+="${!NAME_PROC_CONFIG};"
  [[ ! -z "$KEY_VALUES" ]] && KEY_VALUES="--configKeyValues \"$KEY_VALUES\""
  local WFADD="$1 $ARGS_ALL ${2:-} ${!NAME_PROC_ARGS:-} $KEY_VALUES | "
  local NAME_PROC_ENABLE_ROOT_OUTPUT="ENABLE_ROOT_OUTPUT_${1//-/_}"
  if [[ ! -z $DISABLE_ROOT_OUTPUT ]] && needs_root_output $1 ; then
      WFADD=${WFADD//$DISABLE_ROOT_OUTPUT/}
  fi
  WORKFLOW+=$WFADD
}

if [[ ${EPNSYNCMODE:-0} == 1 ]]; then
  if [[ "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" ]]; then
    GEN_TOPO_QC_CONSUL_SERVER=ali-staging.cern.ch
  else
    GEN_TOPO_QC_CONSUL_SERVER=alio2-cr1-hv-con01.cern.ch
  fi
  GEN_TOPO_QC_APRICOT_SERVER=`curl -s "http://${GEN_TOPO_QC_CONSUL_SERVER}:8500/v1/kv/o2/runtime/aliecs/vars/apricot_endpoint?raw"`
fi

add_QC_from_consul()
{
  [[ ${EPNSYNCMODE:-0} == 1 ]] || { echo "Error fetching QC JSON $1: consul server only set for EPNSYNCMODE == 1 " 1>&2 && exit 1; }
  if [[ ! -z ${GEN_TOPO_QC_JSON_FILE:-} ]]; then
    curl -s -o $GEN_TOPO_QC_JSON_FILE "http://${GEN_TOPO_QC_CONSUL_SERVER}:8500/v1/kv${1}?raw"
    if [[ $? != 0 ]]; then
      echo "Error fetching QC JSON $1 (1)" 1>&2
      exit 1
    fi
    QC_CONFIG_ARG="json://${GEN_TOPO_QC_JSON_FILE}"
  else
    QC_CONFIG_ARG="consul-json://alio2-cr1-hv-con01.cern.ch:8500$1"
  fi
  add_W o2-qc "--config $QC_CONFIG_ARG $2"
}

add_QC_from_apricot()
{
  [[ ${EPNSYNCMODE:-0} == 1 ]] || { echo "Error fetching QC JSON $1: apricot server only set for EPNSYNCMODE == 1 " 1>&2 && exit 1; }
  if [[ ! -z ${GEN_TOPO_QC_JSON_FILE:-} ]]; then
    if [[ ${1} =~ "?" ]]; then
      curl -s -o $GEN_TOPO_QC_JSON_FILE "${GEN_TOPO_QC_APRICOT_SERVER}/${1}\&process=true"
    else
      curl -s -o $GEN_TOPO_QC_JSON_FILE "${GEN_TOPO_QC_APRICOT_SERVER}/${1}?process=true"
    fi
    if [[ $? != 0 ]]; then
      echo "Error fetching QC JSON $1 (2)" 1>&2
      exit 1
    fi
    QC_CONFIG_ARG="json://${GEN_TOPO_QC_JSON_FILE}"
  else
    QC_CONFIG_ARG="apricot://${GEN_TOPO_QC_APRICOT_SERVER}$1"
  fi
  add_W o2-qc "--config $QC_CONFIG_ARG $2"
}

fi # functions.sh sourced
