#!/bin/bash

# ---------------------------------------------------------------------------------------------------------------------

# Check that the requirements to enable the calibrations are met, and
# enabled them by default if they are not yet enabled or
# if they are not explicitly disabled.
# Then, configure data spec according to enabled calibrations

# used to avoid sourcing this file 2x
if [[ -z $SOURCE_GUARD_SETENV_CALIB ]]; then
SOURCE_GUARD_SETENV_CALIB=1

# For the moment the TPC interpolation will always send also the track parameters in addition to unbinned residuals to the aggregator.
# Remove this line to only send unbinned residuals
if [[ -z "$CALIB_TPC_SCDCALIB_SENDTRKDATA" ]];  then export CALIB_TPC_SCDCALIB_SENDTRKDATA=1; fi

if [[ $BEAMTYPE != "cosmic" ]] || [[ $FORCECALIBRATIONS == 1 ]] ; then
  # calibrations for primary vertex
  if has_detector_calib ITS && has_detectors_reco ITS && has_detector_matching PRIMVTX && [[ ! -z "$VERTEXING_SOURCES" ]]; then
    if [[ -z ${CALIB_PRIMVTX_MEANVTX+x} ]]; then CALIB_PRIMVTX_MEANVTX=1; fi
  fi

  # calibrations for TOF
  if has_detector_calib TOF && has_detector_reco TOF; then
    if ( has_detectors_reco ITS TPC && has_detector_matching ITSTPCTOF ) || ( has_detectors_reco ITS TPC TRD && has_detector_matching ITSTPCTRDTOF ); then
      if [[ -z ${CALIB_TOF_LHCPHASE+x} ]]; then CALIB_TOF_LHCPHASE=1; fi
      if [[ -z ${CALIB_TOF_CHANNELOFFSETS+x} ]]; then CALIB_TOF_CHANNELOFFSETS=1; fi
    fi
    if [[ -z ${CALIB_TOF_DIAGNOSTICS+x} ]]; then CALIB_TOF_DIAGNOSTICS=1; fi
  fi

  # calibrations for TPC
  if has_detector_calib TPC; then
    if has_detectors ITS TPC TOF TRD; then
      if has_detectors TPC ITS TRD TOF && has_detector_matching ITSTPCTRDTOF; then
        if [[ -z ${CALIB_TPC_SCDCALIB+x} ]]; then CALIB_TPC_SCDCALIB=1; fi
      fi
    fi
    if has_processing_step TPC_DEDX; then
      if [[ -z ${CALIB_TPC_TIMEGAIN+x} ]]; then CALIB_TPC_TIMEGAIN=1; fi
      if [[ -z ${CALIB_TPC_RESPADGAIN+x} ]]; then CALIB_TPC_RESPADGAIN=1; fi
    fi
    if ( has_detectors ITS TPC && has_detector_matching ITSTPC ); then
      if [[ -z ${CALIB_TPC_VDRIFTTGL+x} ]]; then CALIB_TPC_VDRIFTTGL=1; fi
    fi
    # IDCs
    if [[ -z ${CALIB_TPC_IDC+x} ]]; then
      CALIB_TPC_IDC=0; # default is off
    else
      if [[ -z {$CALIB_TPC_IDC_BOTH+x} ]]; then
	CALIB_TPC_IDC_BOTH=0;
      fi # by default, A and C side are processed separately
    fi
  fi

  # calibrations for TRD
  if has_detector_calib TRD && has_detectors ITS TPC TRD ; then
    if [[ -z ${CALIB_TRD_VDRIFTEXB+x} ]]; then CALIB_TRD_VDRIFTEXB=1; fi
  fi

  # calibrations for EMC
  if has_detector_calib EMC && has_detector_reco EMC; then
    if [[ -z ${CALIB_EMC_BADCHANNELCALIB+x} ]]; then CALIB_EMC_BADCHANNELCALIB=1; fi
    if [[ -z ${CALIB_EMC_TIMECALIB+x} ]]; then CALIB_EMC_TIMECALIB=1; fi
  fi

  # calibrations for PHS
  if has_detector_calib PHS && has_detector_reco PHS; then
    if [[ -z ${CALIB_PHS_ENERGYCALIB+x} ]]; then CALIB_PHS_ENERGYCALIB=1; fi
    if [[ -z ${CALIB_PHS_BADMAPCALIB+x} ]]; then CALIB_PHS_BADMAPCALIB=1; fi
    if [[ -z ${CALIB_PHS_TURNONCALIB+x} ]]; then CALIB_PHS_TURNONCALIB=1; fi
    if [[ -z ${CALIB_PHS_RUNBYRUNCALIB+x} ]]; then CALIB_PHS_RUNBYRUNCALIB=1; fi
  fi

  # calibrations for CPV
  if has_detector_calib CPV && has_detector_reco CPV; then
    if [[ -z ${CALIB_CPV_GAIN+x} ]]; then CALIB_CPV_GAIN=1; fi
  fi
fi

[[ -z ${CALIB_PRIMVTX_MEANVTX} ]] && CALIB_PRIMVTX_MEANVTX=0
[[ -z ${CALIB_TOF_LHCPHASE} ]] && CALIB_TOF_LHCPHASE=0
[[ -z ${CALIB_TOF_CHANNELOFFSETS} ]] && CALIB_TOF_CHANNELOFFSETS=0
[[ -z ${CALIB_TOF_DIAGNOSTICS} ]] && CALIB_TOF_DIAGNOSTICS=0
[[ -z ${CALIB_TPC_SCDCALIB} ]] && CALIB_TPC_SCDCALIB=0
[[ -z ${CALIB_TPC_TIMEGAIN} ]] && CALIB_TPC_TIMEGAIN=0
[[ -z ${CALIB_TPC_RESPADGAIN} ]] && CALIB_TPC_RESPADGAIN=0
( [[ -z ${CALIB_TPC_IDC} ]] || ! has_detector TPC ) && CALIB_TPC_IDC=0
[[ -z ${CALIB_TRD_VDRIFTEXB} ]] && CALIB_TRD_VDRIFTEXB=0
[[ -z ${CALIB_EMC_BADCHANNELCALIB} ]] && CALIB_EMC_BADCHANNELCALIB=0
[[ -z ${CALIB_EMC_TIMECALIB} ]] && CALIB_EMC_TIMECALIB=0
[[ -z ${CALIB_PHS_ENERGYCALIB} ]] && CALIB_PHS_ENERGYCALIB=0
[[ -z ${CALIB_PHS_BADMAPCALIB} ]] && CALIB_PHS_BADMAPCALIB=0
[[ -z ${CALIB_PHS_TURNONCALIB} ]] && CALIB_PHS_TURNONCALIB=0
[[ -z ${CALIB_PHS_RUNBYRUNCALIB} ]] && CALIB_PHS_RUNBYRUNCALIB=0
[[ -z ${CALIB_CPV_GAIN} ]] && CALIB_CPV_GAIN=0

if [[ "0$GEN_TOPO_VERBOSE" == "01" ]]; then
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
  echo "CALIB_TRD_VDRIFTEXB = $CALIB_TRD_VDRIFTEXB" 1>&2
  echo "CALIB_TPC_TIMEGAIN = $CALIB_TPC_TIMEGAIN" 1>&2
  echo "CALIB_TPC_RESPADGAIN = $CALIB_TPC_RESPADGAIN" 1>&2
  echo "CALIB_TPC_IDC = $CALIB_TPC_IDC" 1>&2
  if [[ $CALIB_TPC_IDC == 1 ]]; then
    if [[ ! -z $CALIB_TPC_IDC_BOTH == 1 ]]; then
      echo "CALIB_TPC_IDC_BOTH = $CALIB_TPC_IDC_BOTH" 1>&2
    else
      echo "CALIB_TPC_IDC_BOTH not set, A and C side will be run separately"
    fi
  fi
  echo "CALIB_CPV_GAIN = $CALIB_CPV_GAIN" 1>&2
fi

# define spec for proxy for TF-based outputs from BARREL
if [[ -z $CALIBDATASPEC_BARREL_TF ]]; then
  # prim vtx
  if [[ $CALIB_PRIMVTX_MEANVTX == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "pvtx:GLO/PVTX/0"; fi

  # TOF
  if [[ $CALIB_TOF_LHCPHASE == 1 ]] || [[ $CALIB_TOF_CHANNELOFFSETS == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "calibTOF:TOF/CALIBDATA/0"; fi
  if [[ $CALIB_TOF_DIAGNOSTICS == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "diagWords:TOF/DIAFREQ/0"; fi

  # TPC
  if [[ $CALIB_TPC_TIMEGAIN == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "tpcmips:TPC/MIPS/0"; fi
  if [[ $CALIB_TPC_SCDCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "unbinnedTPCResiduals:GLO/UNBINNEDRES/0"; fi
  if [[ $CALIB_TPC_SCDCALIB == 1 ]] && [[ 0$CALIB_TPC_SCDCALIB_SENDTRKDATA == "01" ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "tpcInterpTrkData:GLO/TRKDATA/0"; fi
  if [[ $CALIB_TPC_VDRIFTTGL == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "tpcvdtgl:GLO/TPCITS_VDTGL/0"; fi

  # TRD
  if [[ $CALIB_TRD_VDRIFTEXB == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_TF "angResHistoTRD:TRD/ANGRESHISTS/0"; fi
fi

# define spec for proxy for sporadic outputs from BARREL
if [[ -z $CALIBDATASPEC_BARREL_SPORADIC ]]; then
  # TPC
  if [[ $CALIB_TPC_RESPADGAIN == 1 ]]; then add_semicolon_separated CALIBDATASPEC_BARREL_SPORADIC "trackGainHistoTPC:TPC/TRACKGAINHISTOS/0"; fi
fi

# define spec for proxy for TPC IDCs - Side A
if [[ -z $CALIBDATASPEC_TPCIDC_A ]]; then
  # TPC
  if [[ $CALIB_TPC_IDC == 1 ]]; then add_semicolon_separated CALIBDATASPEC_TPCIDC_A "idcsgroupa:TPC/IDCGROUPA"; fi
fi

# define spec for proxy for TPC IDCs - Side C
if [[ -z $CALIBDATASPEC_TPCIDC_C ]]; then
  # TPC
  if [[ $CALIB_TPC_IDC == 1 ]]; then add_semicolon_separated CALIBDATASPEC_TPCIDC_C "idcsgroupc:TPC/IDCGROUPC"; fi
fi


# define spec for proxy for TF-based outputs from CALO
if [[ -z $CALIBDATASPEC_CALO_TF ]]; then
  # EMC
  if [[ $CALIB_EMC_BADCHANNELCALIB == 1 ]] || [[ $CALIB_EMC_TIMECALIB == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC_CALO_TF "cellsEMC:EMC/CELLS/0"
    add_semicolon_separated CALIBDATASPEC_CALO_TF "cellsTrgREMC:EMC/CELLSTRGR/0"
  fi

  # PHS
  if [[ $CALIB_PHS_ENERGYCALIB == 1 ]] || [[ $CALIB_PHS_TURNONCALIB == 1 ]] || [[ $CALIB_PHS_RUNBYRUNCALIB == 1 ]]; then
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

if [[ "0$GEN_TOPO_VERBOSE" == "01" ]]; then
  # printing for debug
  echo CALIBDATASPEC_BARREL_TF = $CALIBDATASPEC_BARREL_TF 1>&2
  echo CALIBDATASPEC_BARREL_SPORADIC = $CALIBDATASPEC_BARREL_SPORADIC 1>&2
  echo CALIBDATASPEC_TPCIDC_A = $CALIBDATASPEC_TPCIDC_A 1>&2
  echo CALIBDATASPEC_TPCIDC_C = $CALIBDATASPEC_TPCIDC_C 1>&2
  echo CALIBDATASPEC_CALO_TF = $CALIBDATASPEC_CALO_TF 1>&2
  echo CALIBDATASPEC_CALO_SPORADIC = $CALIBDATASPEC_CALO_SPORADIC 1>&2
  echo CALIBDATASPEC_MUON_TF = $CALIBDATASPEC_MUON_TF 1>&2
  echo CALIBDATASPEC_MUON_SPORADIC = $CALIBDATASPEC_MUON_SPORADIC 1>&2
fi

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
  [[ $2 == "input" && ! -z $TIMEFRAME_SHM_LIMIT ]] && PROXY_CONN+=" --timeframes-shm-limit $TIMEFRAME_SHM_LIMIT"
  if [[ "0$GEN_TOPO_VERBOSE" == "01" ]]; then
    echo PROXY_CONN = $PROXY_CONN 1>&2
  fi
  echo $PROXY_CONN
}
fi # setenv_calib.sh sourced
