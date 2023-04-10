#!/bin/bash

# used to avoid sourcing this file 2x
if [[ -z ${SOURCE_GUARD_FUNCTIONS:-} ]]; then
SOURCE_GUARD_FUNCTIONS=1

has_detector()
{
  [[ $WORKFLOW_DETECTORS =~ (^|,)"$1"(,|$) ]]
}

has_detector_from_global_reader()
{
  [[ $WORKFLOW_DETECTORS_USE_GLOBAL_READER =~ (^|,)"$1"(,|$) ]]
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
  _check_multiple has_detector $@
}

has_detectors_qc()
{
  _check_multiple has_detector_qc $@
}

has_detectors_calib()
{
  _check_multiple has_detector_calib $@
}

has_detectors_reco()
{
  _check_multiple has_detector_reco $@
}

has_detectors_ctf()
{
  _check_multiple has_detector_ctf $@
}

has_detectors_flp_processing()
{
  _check_multiple has_detector_flp_processing $@
}

workflow_has_parameters()
{
  _check_multiple workflow_has_parameter $@
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

fi # functions.sh sourced
