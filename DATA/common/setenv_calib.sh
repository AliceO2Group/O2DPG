#!/bin/bash

# ---------------------------------------------------------------------------------------------------------------------

# Check that the requirements to enable the calibrations are met, and
# enabled them by default if they are not yet enabled or
# if they are not explicitly disabled.
# Then, configure data spec according to enabled calibrations

# used to avoid sourcing this file 2x
if [[ -z ${SOURCE_GUARD_SETENV_CALIB:-} ]]; then
SOURCE_GUARD_SETENV_CALIB=1

# define the conditions for each calibration
if has_detector_calib ITS && has_detectors_reco ITS && has_detector_matching PRIMVTX && [[ ! -z "$VERTEXING_SOURCES" ]]; then CAN_DO_CALIB_PRIMVTX_MEANVTX=1; else CAN_DO_CALIB_PRIMVTX_MEANVTX=0; fi
if has_detector_calib TOF && has_detector_reco TOF; then CAN_DO_CALIB_TOF_DIAGNOSTICS=1; else CAN_DO_CALIB_TOF_DIAGNOSTICS=0; fi
if has_detector_calib TOF && has_detector_reco TOF && (( has_detectors_reco ITS TPC && has_detector_matching ITSTPCTOF ) || ( has_detectors_reco ITS TPC TRD && has_detector_matching ITSTPCTRDTOF )); then CAN_DO_CALIB_TOF_LHCPHASE=1; CAN_DO_CALIB_TOF_CHANNELOFFSETS=1; else CAN_DO_CALIB_TOF_LHCPHASE=0; CAN_DO_CALIB_TOF_CHANNELOFFSETS=0; fi
if has_detector_calib TPC && has_detectors ITS TPC TOF TRD && has_detector_matching ITSTPCTRDTOF; then CAN_DO_CALIB_TPC_SCDCALIB=1; else CAN_DO_CALIB_TPC_SCDCALIB=0; fi
if has_detector_calib TPC && has_processing_step TPC_DEDX; then CAN_DO_CALIB_TPC_TIMEGAIN=1; CAN_DO_CALIB_TPC_RESPADGAIN=1; else CAN_DO_CALIB_TPC_TIMEGAIN=0; CAN_DO_CALIB_TPC_RESPADGAIN=0; fi
if has_detector_calib TPC && has_detectors ITS TPC && has_detector_matching ITSTPC; then CAN_DO_CALIB_TPC_VDRIFTTGL=1; else CAN_DO_CALIB_TPC_VDRIFTTGL=0; fi
if has_detector_calib TPC; then CAN_DO_CALIB_TPC_IDC=1; CAN_DO_CALIB_TPC_SAC=1; else CAN_DO_CALIB_TPC_IDC=0; CAN_DO_CALIB_TPC_SAC=0; fi
if [[ ! -z ${FLP_IDS:-} && ! $FLP_IDS =~ (^|,)"145"(,|$) ]]; then CAN_DO_CALIB_TPC_SAC=0; fi
if has_detector_calib TRD && has_detectors ITS TPC TRD && has_detector_matching ITSTPCTRD; then CAN_DO_CALIB_TRD_VDRIFTEXB=1; else CAN_DO_CALIB_TRD_VDRIFTEXB=0; fi
if has_detector_calib EMC && has_detector_reco EMC; then CAN_DO_CALIB_EMC_BADCHANNELCALIB=1; CAN_DO_CALIB_EMC_TIMECALIB=1; else CAN_DO_CALIB_EMC_BADCHANNELCALIB=0; CAN_DO_CALIB_EMC_TIMECALIB=0; fi
if has_detector_calib PHS && has_detector_reco PHS; then CAN_DO_CALIB_PHS_ENERGYCALIB=0; CAN_DO_CALIB_PHS_BADMAPCALIB=1; CAN_DO_CALIB_PHS_TURNONCALIB=1; CAN_DO_CALIB_PHS_RUNBYRUNCALIB=1; CAN_DO_CALIB_PHS_L1PHASE=1; else CAN_DO_CALIB_PHS_ENERGYCALIB=0; CAN_DO_CALIB_PHS_BADMAPCALIB=0; CAN_DO_CALIB_PHS_TURNONCALIB=0; CAN_DO_CALIB_PHS_RUNBYRUNCALIB=0; CAN_DO_CALIB_PHS_L1PHASE=0; fi
if has_detector_calib CPV && has_detector_reco CPV; then CAN_DO_CALIB_CPV_GAIN=1; else CAN_DO_CALIB_CPV_GAIN=0; fi
if has_detector_calib ZDC && has_processing_step ZDC_RECO; then CAN_DO_CALIB_ZDC_TDC=1; else CAN_DO_CALIB_ZDC_TDC=0; fi
# for async recalibration
if has_detector_calib EMC && has_detector_reco EMC && [[ $SYNCMODE != 1 ]]; then CAN_DO_CALIB_EMC_ASYNC_RECALIB=1; else CAN_DO_CALIB_EMC_ASYNC_RECALIB=0; fi

# additional individual settings for calibration workflows
if has_detector CTP; then export CALIB_TPC_SCDCALIB_CTP_INPUT="--enable-ctp"; else export CALIB_TPC_SCDCALIB_CTP_INPUT=""; fi
# the slot length needs to be known both on the aggregator and the processing nodes, therefore it is defined (in seconds!) here
: ${CALIB_TPC_SCDCALIB_SLOTLENGTH:=600}

if [[ $BEAMTYPE != "cosmic" ]] || [[ ${FORCECALIBRATIONS:-} == 1 ]] ; then

  # here we won't deal with calibrations only for async! e.g. EMC_ASYNC_RECALIB; we want that they are always explicitly enabled

  # calibrations for primary vertex
  if [[ $CAN_DO_CALIB_PRIMVTX_MEANVTX == 1 ]]; then
    if [[ -z ${CALIB_PRIMVTX_MEANVTX+x} ]]; then CALIB_PRIMVTX_MEANVTX=1; fi
  fi

  # calibrations for TOF
  if [[ $CAN_DO_CALIB_TOF_DIAGNOSTICS == 1 ]]; then
    if [[ -z ${CALIB_TOF_DIAGNOSTICS+x} ]]; then CALIB_TOF_DIAGNOSTICS=1; fi
  fi
  if [[ $CAN_DO_CALIB_TOF_LHCPHASE == 1 ]]; then
    if [[ -z ${CALIB_TOF_LHCPHASE+x} ]]; then CALIB_TOF_LHCPHASE=1; fi
  fi
  if [[ $CAN_DO_CALIB_TOF_CHANNELOFFSETS == 1 ]]; then
    if [[ -z ${CALIB_TOF_CHANNELOFFSETS+x} ]]; then CALIB_TOF_CHANNELOFFSETS=1; fi
  fi

  # calibrations for TPC
  if [[ $CAN_DO_CALIB_TPC_SCDCALIB == 1 ]] ; then
    if [[ -z ${CALIB_TPC_SCDCALIB+x} ]]; then CALIB_TPC_SCDCALIB=1; fi
  fi
  if [[ $CAN_DO_CALIB_TPC_TIMEGAIN == 1 ]]; then
    if [[ -z ${CALIB_TPC_TIMEGAIN+x} ]]; then CALIB_TPC_TIMEGAIN=1; fi
  fi
  if [[ $CAN_DO_CALIB_TPC_RESPADGAIN == 1 ]]; then
    if [[ -z ${CALIB_TPC_RESPADGAIN+x} ]]; then CALIB_TPC_RESPADGAIN=1; fi
  fi
  if [[ $CAN_DO_CALIB_TPC_VDRIFTTGL == 1 ]]; then
    if [[ -z ${CALIB_TPC_VDRIFTTGL+x} ]]; then CALIB_TPC_VDRIFTTGL=1; fi
  fi
  # IDCs
  if [[ $CAN_DO_CALIB_TPC_IDC == 1 ]]; then
    if [[ -z ${CALIB_TPC_IDC+x} ]] || [[ $CALIB_TPC_IDC == 0 ]]; then
      CALIB_TPC_IDC=0; # default is off
    fi
  fi
  # SAC
  if [[ $CAN_DO_CALIB_TPC_SAC == 1 ]]; then
    if [[ -z ${CALIB_TPC_SAC+x} ]]; then CALIB_TPC_SAC=0; fi # default is off
  fi

  # calibrations for TRD
  if [[ $CAN_DO_CALIB_TRD_VDRIFTEXB == 1 ]] ; then
    if [[ -z ${CALIB_TRD_VDRIFTEXB+x} ]]; then CALIB_TRD_VDRIFTEXB=1; fi
  fi

  # calibrations for EMC
  if [[ $CAN_DO_CALIB_EMC_BADCHANNELCALIB == 1 ]]; then
    if [[ -z ${CALIB_EMC_BADCHANNELCALIB+x} ]]; then CALIB_EMC_BADCHANNELCALIB=1; fi
  fi
  if [[ $CAN_DO_CALIB_EMC_TIMECALIB == 1 ]]; then
    if [[ -z ${CALIB_EMC_TIMECALIB+x} ]]; then CALIB_EMC_TIMECALIB=1; fi
  fi

  # calibrations for PHS
  if [[ $CAN_DO_CALIB_PHS_ENERGYCALIB == 1 ]]; then
    if [[ -z ${CALIB_PHS_ENERGYCALIB+x} ]]; then CALIB_PHS_ENERGYCALIB=1; fi
  fi
  if [[ $CAN_DO_CALIB_PHS_BADMAPCALIB == 1 ]]; then
    if [[ -z ${CALIB_PHS_BADMAPCALIB+x} ]]; then CALIB_PHS_BADMAPCALIB=1; fi
  fi
  if [[ $CAN_DO_CALIB_PHS_TURNONCALIB == 1 ]]; then
    if [[ -z ${CALIB_PHS_TURNONCALIB+x} ]]; then CALIB_PHS_TURNONCALIB=1; fi
  fi
  if [[ $CAN_DO_CALIB_PHS_RUNBYRUNCALIB == 1 ]]; then
    if [[ -z ${CALIB_PHS_RUNBYRUNCALIB+x} ]]; then CALIB_PHS_RUNBYRUNCALIB=1; fi
  fi
  if [[ $CAN_DO_CALIB_PHS_L1PHASE == 1 ]]; then
    if [[ -z ${CALIB_PHS_L1PHASE+x} ]]; then CALIB_PHS_L1PHASE=1; fi
  fi

  # calibrations for CPV
  if [[ $CAN_DO_CALIB_CPV_GAIN == 1 ]]; then
    if [[ -z ${CALIB_CPV_GAIN+x} ]]; then CALIB_CPV_GAIN=1; fi
  fi

  # calibrations for ZDC
  if [[ $CAN_DO_CALIB_ZDC_TDC == 1 ]]; then
    if [[ -z ${CALIB_ZDC_TDC+x} ]]; then CALIB_ZDC_TDC=1; fi
  fi
fi

( [[ -z ${CALIB_PRIMVTX_MEANVTX:-} ]] || [[ $CAN_DO_CALIB_PRIMVTX_MEANVTX == 0 ]] ) && CALIB_PRIMVTX_MEANVTX=0
( [[ -z ${CALIB_TOF_LHCPHASE:-} ]] || [[ $CAN_DO_CALIB_TOF_LHCPHASE == 0 ]] ) && CALIB_TOF_LHCPHASE=0
( [[ -z ${CALIB_TOF_CHANNELOFFSETS:-} ]] || [[ $CAN_DO_CALIB_TOF_CHANNELOFFSETS == 0 ]] ) && CALIB_TOF_CHANNELOFFSETS=0
( [[ -z ${CALIB_TOF_DIAGNOSTICS:-} ]] || [[ $CAN_DO_CALIB_TOF_DIAGNOSTICS == 0 ]] ) && CALIB_TOF_DIAGNOSTICS=0
( [[ -z ${CALIB_TPC_SCDCALIB:-} ]] || [[ $CAN_DO_CALIB_TPC_SCDCALIB == 0 ]] ) && CALIB_TPC_SCDCALIB=0
( [[ -z ${CALIB_TPC_TIMEGAIN:-} ]] || [[ $CAN_DO_CALIB_TPC_TIMEGAIN == 0 ]] ) && CALIB_TPC_TIMEGAIN=0
( [[ -z ${CALIB_TPC_RESPADGAIN:-} ]] || [[ $CAN_DO_CALIB_TPC_RESPADGAIN == 0 ]] ) && CALIB_TPC_RESPADGAIN=0
( [[ -z ${CALIB_TPC_IDC:-} ]] || [[ $CAN_DO_CALIB_TPC_IDC == 0 ]] ) && CALIB_TPC_IDC=0
( [[ -z ${CALIB_TPC_SAC:-} ]] || [[ $CAN_DO_CALIB_TPC_SAC == 0 ]] ) && CALIB_TPC_SAC=0
( [[ -z ${CALIB_TRD_VDRIFTEXB:-} ]] || [[ $CAN_DO_CALIB_TRD_VDRIFTEXB == 0 ]] ) && CALIB_TRD_VDRIFTEXB=0
( [[ -z ${CALIB_EMC_BADCHANNELCALIB:-} ]] || [[ $CAN_DO_CALIB_EMC_BADCHANNELCALIB == 0 ]] ) && CALIB_EMC_BADCHANNELCALIB=0
( [[ -z ${CALIB_EMC_TIMECALIB:-} ]] || [[ $CAN_DO_CALIB_EMC_TIMECALIB == 0 ]] ) && CALIB_EMC_TIMECALIB=0
( [[ -z ${CALIB_PHS_ENERGYCALIB:-} ]] || [[ $CAN_DO_CALIB_PHS_ENERGYCALIB == 0 ]] ) && CALIB_PHS_ENERGYCALIB=0
( [[ -z ${CALIB_PHS_BADMAPCALIB:-} ]] || [[ $CAN_DO_CALIB_PHS_BADMAPCALIB == 0 ]] ) && CALIB_PHS_BADMAPCALIB=0
( [[ -z ${CALIB_PHS_TURNONCALIB:-} ]] || [[ $CAN_DO_CALIB_PHS_TURNONCALIB == 0 ]] ) && CALIB_PHS_TURNONCALIB=0
( [[ -z ${CALIB_PHS_RUNBYRUNCALIB:-} ]] || [[ $CAN_DO_CALIB_PHS_RUNBYRUNCALIB == 0 ]] ) && CALIB_PHS_RUNBYRUNCALIB=0
( [[ -z ${CALIB_PHS_L1PHASE:-} ]] || [[ $CAN_DO_CALIB_PHS_L1PHASE == 0 ]] ) && CALIB_PHS_L1PHASE=0
( [[ -z ${CALIB_CPV_GAIN:-} ]] || [[ $CAN_DO_CALIB_CPV_GAIN == 0 ]] ) && CALIB_CPV_GAIN=0
( [[ -z ${CALIB_ZDC_TDC:-} ]] || [[ $CAN_DO_CALIB_ZDC_TDC == 0 ]] ) && CALIB_ZDC_TDC=0
# for async:
( [[ -z ${CALIB_EMC_ASYNC_RECALIB:-} ]] || [[ $CAN_DO_CALIB_EMC_ASYNC_RECALIB == 0 ]] ) && CALIB_EMC_ASYNC_RECALIB=0
: ${CALIB_FT0_TIMEOFFSET:=0}

if [[ "0${GEN_TOPO_VERBOSE:-}" == "01" ]]; then
  echo "CALIB_PRIMVTX_MEANVTX = $CALIB_PRIMVTX_MEANVTX" 1>&2
  echo "CALIB_TOF_LHCPHASE = $CALIB_TOF_LHCPHASE" 1>&2
  echo "CALIB_TOF_CHANNELOFFSETS = $CALIB_TOF_CHANNELOFFSETS" 1>&2
  echo "CALIB_TOF_DIAGNOSTICS = $CALIB_TOF_DIAGNOSTICS" 1>&2
  echo "CALIB_EMC_BADCHANNELCALIB = $CALIB_EMC_BADCHANNELCALIB" 1>&2
  echo "CALIB_EMC_TIMECALIB = $CALIB_EMC_TIMECALIB" 1>&2
  echo "CALIB_PHS_ENERGYCALIB = $CALIB_PHS_ENERGYCALIB" 1>&2
  echo "CALIB_PHS_BADMAPCALIB = $CALIB_PHS_BADMAPCALIB" 1>&2
  echo "CALIB_PHS_TURNONCALIB = $CALIB_PHS_TURNONCALIB" 1>&2
  echo "CALIB_PHS_RUNBYRUNCALIB = $CALIB_PHS_RUNBYRUNCALIB" 1>&2
  echo "CALIB_PHS_L1PHASE = $CALIB_PHS_L1PHASE" 1>&2
  echo "CALIB_TRD_VDRIFTEXB = $CALIB_TRD_VDRIFTEXB" 1>&2
  echo "CALIB_TPC_TIMEGAIN = $CALIB_TPC_TIMEGAIN" 1>&2
  echo "CALIB_TPC_RESPADGAIN = $CALIB_TPC_RESPADGAIN" 1>&2
  echo "CALIB_TPC_IDC = $CALIB_TPC_IDC" 1>&2
  echo "CALIB_TPC_SAC = $CALIB_TPC_SAC" 1>&2
  echo "CALIB_CPV_GAIN = $CALIB_CPV_GAIN" 1>&2
  echo "CALIB_ZDC_TDC = $CALIB_ZDC_TDC" 1>&2
  echo "Calibrations for async:" 1>&2
  echo "CALIB_EMC_ASYNC_RECALIB = $CALIB_EMC_ASYNC_RECALIB" 1>&2
fi

# define spec for proxy for TF-based outputs from BARREL
if [[ -z ${CALIBDATASPEC_BARREL_TF:-} ]]; then
  # prim vtx
  if [[ $CALIB_PRIMVTX_MEANVTX == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "pvtx:GLO/PVTX/0"; fi

  # TOF
  if [[ $CALIB_TOF_LHCPHASE == 1 ]] || [[ $CALIB_TOF_CHANNELOFFSETS == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "calibTOF:TOF/CALIBDATA/0"; fi
  if [[ $CALIB_TOF_DIAGNOSTICS == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "diagWords:TOF/DIAFREQ/0"; fi

  # TPC
  if [[ $CALIB_TPC_SCDCALIB == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC_BARREL_TF "unbinnedTPCResiduals:GLO/UNBINNEDRES/0"
    add_semicolon_separated CALIBDATASPEC_BARREL_TF "trackReferences:GLO/TRKREFS/0"
  fi
  if [[ $CALIB_TPC_SCDCALIB == 1 ]] && [[ ${CALIB_TPC_SCDCALIB_SENDTRKDATA:-} == "1" ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "tpcInterpTrkData:GLO/TRKDATA/0"; fi
  if [[ $CALIB_TPC_SCDCALIB == 1 ]] && [[ ${CALIB_TPC_SCDCALIB_CTP_INPUT:-} == "--enable-ctp" ]]; then
    add_semicolon_separated CALIBDATASPEC_BARREL_TF "lumi:CTP/LUMI/0"
    add_semicolon_separated CALIBDATASPEC_BARREL_TF "ctpdigi:CTP/DIGITS/0"
  fi
  if [[ $CALIB_TPC_VDRIFTTGL == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "tpcvdtgl:GLO/TPCITS_VDTGL/0"; fi

  # TRD
  if [[ $CALIB_TRD_VDRIFTEXB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "angResHistoTRD:TRD/ANGRESHISTS/0"; fi
fi

# define spec for proxy for sporadic outputs from BARREL
if [[ -z ${CALIBDATASPEC_BARREL_SPORADIC:-} ]]; then
  # TPC
  if [[ $CALIB_TPC_RESPADGAIN == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_SPORADIC "trackGainHistoTPC:TPC/TRACKGAINHISTOS/0"; fi
  if [[ $CALIB_TPC_TIMEGAIN == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_SPORADIC "tpcmips:TPC/MIPS/0"; fi
fi

# define spec for proxy for TPC IDCs - Side A
if [[ -z ${CALIBDATASPEC_TPCIDC_A:-} ]]; then
  # TPC
  if [[ $CALIB_TPC_IDC == 1 ]]; then add_semicolon_separated CALIBDATASPEC_TPCIDC_A "idcsgroupa:TPC/IDCGROUPA"; fi
fi

# define spec for proxy for TPC IDCs - Side C
if [[ -z ${CALIBDATASPEC_TPCIDC_C:-} ]]; then
  # TPC
  if [[ $CALIB_TPC_IDC == 1 ]]; then add_semicolon_separated CALIBDATASPEC_TPCIDC_C "idcsgroupc:TPC/IDCGROUPC"; fi
fi

# define spec for proxy for TPC SAC
if [[ -z ${CALIBDATASPEC_TPCSAC:-} ]]; then
  # TPC
  if [[ $CALIB_TPC_SAC == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC_TPCSAC "sacdec:TPC/DECODEDSAC/0"
    add_semicolon_separated CALIBDATASPEC_TPCSAC "sacreftime:TPC/REFTIMESAC/0"
  fi
fi

# define spec for proxy for TF-based outputs from CALO
if [[ -z ${CALIBDATASPEC_CALO_TF:-} ]]; then
  # EMC
  if [[ $CALIB_EMC_BADCHANNELCALIB == 1 ]] || [[ $CALIB_EMC_TIMECALIB == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC_CALO_TF "cellsEMC:EMC/CELLS/0"
    add_semicolon_separated CALIBDATASPEC_CALO_TF "cellsTrgREMC:EMC/CELLSTRGR/0"
  fi

  # PHS
  if [[ $CALIB_PHS_ENERGYCALIB == 1 ]] || [[ $CALIB_PHS_TURNONCALIB == 1 ]] || [[ $CALIB_PHS_RUNBYRUNCALIB == 1 ]] || [[ $CALIB_PHS_L1PHASE == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC_CALO_TF "clsPHS:PHS/CLUSTERS/0"
    add_semicolon_separated CALIBDATASPEC_CALO_TF "clTRPHS:PHS/CLUSTERTRIGREC/0"
  fi
  if [[ $CALIB_PHS_ENERGYCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_CALO_TF "cluelementsPHS:PHS/CLUELEMENTS/0"; fi
  if [[ $CALIB_PHS_BADMAPCALIB == 1 ]] || [[ $CALIB_PHS_TURNONCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_CALO_TF "cellsPHS:PHS/CELLS/0"; fi
  if [[ $CALIB_PHS_TURNONCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_CALO_TF "cellsTRPHS:PHS/CELLTRIGREC/0"; fi

  # CPV
  if [[ $CALIB_CPV_GAIN == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC_CALO_TF "calibdCPV:CPV/CALIBDIGITS/0"
  fi
fi

# define spec for proxy for TF-based outputs from forward detectors
if [[ -z ${CALIBDATASPEC_FORWARD_TF:-} ]]; then
  # ZDC
  if [[ $CALIB_ZDC_TDC == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC_FORWARD_TF "tdcZDC:ZDC/TDCCALIBDATA/0"
    add_semicolon_separated CALIBDATASPEC_FORWARD_TF "histoZDC:ZDC/TDC_1DH"
  fi
fi

if [[ "0${GEN_TOPO_VERBOSE:-}" == "01" ]]; then
  # printing for debug
  echo CALIBDATASPEC_BARREL_TF = $CALIBDATASPEC_BARREL_TF 1>&2
  echo CALIBDATASPEC_BARREL_SPORADIC = $CALIBDATASPEC_BARREL_SPORADIC 1>&2
  echo CALIBDATASPEC_TPCIDC_A = $CALIBDATASPEC_TPCIDC_A 1>&2
  echo CALIBDATASPEC_TPCIDC_C = $CALIBDATASPEC_TPCIDC_C 1>&2
  echo CALIBDATASPEC_CALO_TF = $CALIBDATASPEC_CALO_TF 1>&2
  echo CALIBDATASPEC_CALO_SPORADIC = $CALIBDATASPEC_CALO_SPORADIC 1>&2
  echo CALIBDATASPEC_MUON_TF = $CALIBDATASPEC_MUON_TF 1>&2
  echo CALIBDATASPEC_MUON_SPORADIC = $CALIBDATASPEC_MUON_SPORADIC 1>&2
  echo CALIBDATASPEC_FORWARD_TF = $CALIBDATASPEC_FORWARD_TF 1>&2
fi

# proxies properties
get_proxy_connection()
{
  if (( $# < 3 )); then
    echo "$# parameters received"
    echo "Function name: ${FUNCNAME} expects at least 3 parameters:"
    echo "first parameter is the string id of the proxy"
    echo "second parameter is the type of connection (input/output)"
    echo "third parameter is (sporadic|timeframe)"
    exit 1
  fi

  # setting the type of connection
  if [[ $2 == "input" ]]; then
    local CONNECTION="method=bind"
    local NAMEPROXY="--proxy-name aggregator-proxy-$1"
    local NAMEPROXYCHANNEL=
    if workflow_has_parameter CALIB_LOCAL_AGGREGATOR; then
      CONNECTION+=",type=pull"
    else
      CONNECTION+=",type=sub"
    fi
  elif [[ $2 == "output" ]]; then
    local CONNECTION="method=connect"
    local NAMEPROXY="--proxy-name calib-output-proxy-$1"
    local NAMEPROXYCHANNEL="--proxy-channel-name aggregator-proxy-$1"
    if workflow_has_parameter CALIB_LOCAL_AGGREGATOR; then
      CONNECTION+=",type=push"
    else
      CONNECTION+=",type=pub"
    fi
  else
    echo "parameter 2 should be either 'input' or 'output'"
    exit 2
  fi

  if workflow_has_parameter CALIB_LOCAL_AGGREGATOR; then
    CONNECTION+=",transport=shmem,address=ipc://${UDS_PREFIX}aggregator-shm-$1"
  else
    CONNECTION+=",transport=zeromq"
  fi
  local PROXY_CONN="$NAMEPROXY $NAMEPROXYCHANNEL --channel-config \"name=aggregator-proxy-$1,$CONNECTION,rateLogging=10\""
  [[ $EPNSYNCMODE == 1 ]] && PROXY_CONN+=" --network-interface ib0"
  [[ $2 == "input" && ! -z ${TIMEFRAME_SHM_LIMIT:-} ]] && PROXY_CONN+=" --timeframes-shm-limit $TIMEFRAME_SHM_LIMIT"
  if [[ $2 == "output" ]]; then
    if [[ $3 == "timeframe" ]]; then
      PROXY_CONN+=" --environment DPL_OUTPUT_PROXY_ORDERED=1"
    elif [[ $3 == "sporadic" ]]; then
      PROXY_CONN+=" --environment \"DPL_OUTPUT_PROXY_WHENANY=1 DPL_DONT_DROP_OLD_TIMESLICE=1\""
    else
      echo "invalid option $3, must be (sporadic|timeframe)" 1>&2
      exit 1
    fi
  fi
  if [[ "0${GEN_TOPO_VERBOSE:-}" == "01" ]]; then
    echo PROXY_CONN = $PROXY_CONN 1>&2
  fi
  echo $PROXY_CONN
}
fi # setenv_calib.sh sourced
