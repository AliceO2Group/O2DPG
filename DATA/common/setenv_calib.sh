#!/bin/bash

# ---------------------------------------------------------------------------------------------------------------------

# Check that the requirements to enable the calibrations are met, and
# enabled them by default if they are not yet enabled or
# if they are not explicitly disabled.
# Then, configure data spec according to enabled calibrations

# used to avoid sourcing this file 2x
if [[ -z $SOURCE_GUARD_SETENV_CALIB ]]; then
SOURCE_GUARD_SETENV_CALIB=1

if [[ $BEAMTYPE != "cosmic" ]] || [[ $FORCECALIBRATIONS == 1 ]] ; then
  # calibrations for primary vertex
  if has_detector_calib ITS && has_detectors_reco ITS && has_detector_matching PRIMVTX && [[ ! -z "$VERTEXING_SOURCES" ]]; then
    if [[ -z ${CALIB_PRIMVTX_MEANVTX+x} ]]; then CALIB_PRIMVTX_MEANVTX=1; fi
  else
    CALIB_PRIMVTX_MEANVTX=0
  fi

  # calibrations for TOF
  if has_detector_calib TOF && has_detector_reco TOF; then
    if ( has_detectors_reco ITS TPC && has_detector_matching ITSTPCTOF ) || ( has_detectors_reco ITS TPC TRD && has_detector_matching ITSTPCTRDTOF ); then
      if [[ -z ${CALIB_TOF_LHCPHASE+x} ]]; then CALIB_TOF_LHCPHASE=1; fi
      if [[ -z ${CALIB_TOF_CHANNELOFFSETS+x} ]]; then CALIB_TOF_CHANNELOFFSETS=1; fi
    else
      CALIB_TOF_LHCPHASE=0
      CALIB_TOF_CHANNELOFFSETS=0
    fi
    if [[ -z ${CALIB_TOF_DIAGNOSTICS+x} ]]; then CALIB_TOF_DIAGNOSTICS=1; fi
  else
    CALIB_TOF_DIAGNOSTICS=0
  fi

  # calibrations for TPC
  if has_detector_calib TPC; then
    if has_detectors ITS TPC TOF TRD; then
      if has_detectors TPC ITS TRD TOF && has_detector_matching ITSTPCTRDTOF; then
        if [[ -z ${CALIB_TPC_SCDCALIB+x} ]]; then CALIB_TPC_SCDCALIB=1; fi
      else
        CALIB_TPC_SCDCALIB=0
      fi
    fi
    if [[ -z ${CALIB_TPC_TIMEGAIN+x} ]]; then CALIB_TPC_TIMEGAIN=1; fi
    if [[ -z ${CALIB_TPC_RESPADGAIN+x} ]]; then CALIB_TPC_RESPADGAIN=1; fi
  else
    CALIB_TPC_TIMEGAIN=0
    CALIB_TPC_RESPADGAIN=0
  fi

  # calibrations for TRD
  if has_detector_calib TRD && has_detectors ITS TPC TRD ; then
    if [[ -z ${CALIB_TRD_VDRIFTEXB+x} ]]; then CALIB_TRD_VDRIFTEXB=1; fi
  else
    CALIB_TRD_VDRIFTEXB=0
  fi

  # calibrations for EMC
  if has_detector_calib EMC && has_detector_reco EMC; then
    if [[ -z ${CALIB_EMC_CHANNELCALIB+x} ]]; then CALIB_EMC_CHANNELCALIB=1; fi
  else
    CALIB_EMC_CHANNELCALIB=0
  fi

  # calibrations for PHS
  if has_detector_calib PHS && has_detector_reco PHS; then
    if [[ -z ${CALIB_PHS_ENERGYCALIB+x} ]]; then CALIB_PHS_ENERGYCALIB=1; fi
    if [[ -z ${CALIB_PHS_BADMAPCALIB+x} ]]; then CALIB_PHS_BADMAPCALIB=1; fi
    if [[ -z ${CALIB_PHS_TURNONCALIB+x} ]]; then CALIB_PHS_TURNONCALIB=1; fi
    if [[ -z ${CALIB_PHS_RUNBYRUNCALIB+x} ]]; then CALIB_PHS_RUNBYRUNCALIB=1; fi
  else
    CALIB_PHS_ENERGYCALIB=0
    CALIB_PHS_BADMAPCALIB=0
    CALIB_PHS_TURNONCALIB=0
    CALIB_PHS_RUNBYRUNCALIB=0
  fi
fi

echo "CALIB_PRIMVTX_MEANVTX = $CALIB_PRIMVTX_MEANVTX" 1>&2
echo "CALIB_TOF_LHCPHASE = $CALIB_TOF_LHCPHASE" 1>&2
echo "CALIB_TOF_CHANNELOFFSETS = $CALIB_TOF_CHANNELOFFSETS" 1>&2
echo "CALIB_TOF_DIAGNOSTICS = $CALIB_TOF_DIAGNOSTICS" 1>&2
echo "CALIB_EMC_CHANNELCALIB = $CALIB_EMC_CHANNELCALIB" 1>&2
echo "CALIB_PHS_ENERGYCALIB = $CALIB_PHS_ENERGYCALIB" 1>&2
echo "CALIB_PHS_BADMAPCALIB = $CALIB_PHS_BADMAPCALIB" 1>&2
echo "CALIB_PHS_TURNONCALIB = $CALIB_PHS_TURNONCALIB" 1>&2
echo "CALIB_PHS_RUNBYRUNCALIB = $CALIB_PHS_RUNBYRUNCALIB" 1>&2
echo "CALIB_TRD_VDRIFTEXB = $CALIB_TRD_VDRIFTEXB" 1>&2
echo "CALIB_TPC_TIMEGAIN = $CALIB_TPC_TIMEGAIN" 1>&2
echo "CALIB_TPC_RESPADGAIN = $CALIB_TPC_RESPADGAIN" 1>&2

if [[ -z $CALIBDATASPEC_BARREL ]]; then
  # prim vtx
  if [[ $CALIB_PRIMVTX_MEANVTX == 1 ]] ; then add_semicolon_separated CALIBDATASPEC_BARREL "pvtx:GLO/PVTX/0"; fi

  # TOF
  if [[ $CALIB_TOF_LHCPHASE == 1 ]] || [[ $CALIB_TOF_CHANNELOFFSETS == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL "calibTOF:TOF/CALIBDATA/0"; fi
  if [[ $CALIB_TOF_DIAGNOSTICS == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL "diagWords:TOF/DIAFREQ/0"; fi

  # TPC
  if [[ $CALIB_TPC_TIMEGAIN == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL "tpcmips:TPC/MIPS/0"; fi
  if [[ $CALIB_TPC_RESPADGAIN == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL "trackGainHistoTPC:TPC/TRACKGAINHISTOS/0"; fi

  # TRD
  if [[ $CALIB_TRD_VDRIFTEXB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL "angResHistoTRD:TRD/ANGRESHISTS/0"; fi
fi

if [[ -z $CALIBDATASPEC_CALO ]]; then
  # EMC
  if [[ $CALIB_EMC_CHANNELCALIB == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC_CALO "cellsEMC:EMC/CELLS/0"
    add_semicolon_separated CALIBDATASPEC_CALO "cellsTrgREMC:EMC/CELLSTRGR/0"
  fi

  # PHS
  if [[ $CALIB_PHS_ENERGYCALIB == 1 ]] || [[ $CALIB_PHS_TURNONCALIB == 1 ]] || [[ $CALIB_PHS_RUNBYRUNCALIB == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC_CALO "clsPHS:PHS/CLUSTERS/0;"
    add_semicolon_separated CALIBDATASPEC_CALO "clTRPHS:PHS/CLUSTERTRIGREC/0;"
  fi
  if [[ $CALIB_PHS_ENERGYCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_CALO "cluelementsPHS:PHS/CLUELEMENTS/0;"; fi
  if [[ $CALIB_PHS_BADMAPCALIB == 1 ]] || [[ $CALIB_PHS_TURNONCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_CALO "cellsPHS:PHS/CELLS/0;"; fi
  if [[ $CALIB_PHS_TURNONCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_CALO "cellsTRPHS:PHS/CELLTRIGREC/0;"; fi
fi

# printing for debug
echo CALIBDATASPEC_BARREL = $CALIBDATASPEC_BARREL 1>&2
echo CALIBDATASPEC_CALO = $CALIBDATASPEC_CALO 1>&2

# proxies properties
get_proxy_connection()
{
  if (( $# < 2 )); then
    echo "$# parameters received"
    echo "Function name: ${FUNCNAME} expects at least 3 parameters:"
    echo "first parameter is the string id of the proxy"
    echo "second parameter is the type of connection (input/output)"
    exit 1
  fi

  # setting the type of connection
  if [[ $2 == "input" ]]; then
    local CONNECTION="method=bind,type=pull"
    local NAMEPROXY="--proxy-name aggregator-proxy-$1"
    local NAMEPROXYCHANNEL=
  elif [[ $2 == "output" ]]; then
    local CONNECTION="method=connect,type=push"
    local NAMEPROXY="--proxy-name calib-output-proxy-$1"
    local NAMEPROXYCHANNEL="--proxy-channel-name aggregator-proxy-$1"
  else
    echo "parameter 2 should be either 'input' or 'output'"
    exit 2
  fi

  if workflow_has_parameter CALIB_LOCAL_AGGREGATOR; then
    CONNECTION+=",transport=shmem,address=ipc://${UDS_PREFIX}aggregator-shm-$1"
  else
    CONNECTION+=",transport=zeromq"
  fi
  local PROXY_CONN="$NAMEPROXY $NAMEPROXYCHANNEL --channel-config \"name=aggregator-proxy-$1,$CONNECTION,rateLogging=1\""

  echo PROXY_CONN = $PROXY_CONN 1>&2
  echo $PROXY_CONN
}
fi # setenv_calib.sh sourced
