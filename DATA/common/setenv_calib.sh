#!/bin/bash

# ---------------------------------------------------------------------------------------------------------------------

# Check that the requirements to enable the calibrations are met, and
# enabled them by default if they are not yet enabled or
# if they are not explicitly disabled.
# Then, configure data spec according to enabled calibrations

source $O2DPG_ROOT/DATA/common/setenv.sh

if [[ $BEAMTYPE != "cosmic" ]] && [[ $FORCECALIBRATIONS != 1 ]] ; then

    # calibrations for primary vertex
    if has_detector_calib ITS && has_detectors_reco ITS && has_detector_matching PRIMVTX && [[ ! -z "$VERTEXING_SOURCES" ]]; then
	if [[ -z $CALIB_PRIMVTX_MEANVTX ]]; then CALIB_PRIMVTX_MEANVTX=1; fi
    else
	CALIB_PRIMVTX_MEANVTX=0
    fi

    # calibrations for TOF
    if has_detector_calib TOF && has_detector_reco TOF; then
	if has_detector_matching ITSTPCTOF || has_detector_matching ITSTPCTRDTOF; then
	    if [[ -z $CALIB_TOF_LHCPHASE ]]; then CALIB_TOF_LHCPHASE=1; fi
	    if [[ -z $CALIB_TOF_CHANNELOFFSETS ]]; then CALIB_TOF_CHANNELOFFSETS=1; fi
	else
	    CALIB_TOF_LHCPHASE=0
	    CALIB_TOF_CHANNELOFFSETS=0
	fi
	if [[ -z $CALIB_TOF_DIAGNOSTICS ]]; then CALIB_TOF_DIAGNOSTICS=1; fi    
    else
	CALIB_TOF_DIAGNOSTICS=0
    fi

    # calibrations for TPC
    if has_detector_calib TPC && has_detectors ITS TPC TOF TRD; then
	if has_detectors TPC ITS TRD TOF && has_detector_matching ITSTPCTRDTOF; then
	    if [[ -z $CALIB_TPC_SCDCALIB ]]; then CALIB_TPC_SCDCALIB=1; fi
	else
	    CALIB_TPC_SCDCALIB=0
	fi
    fi
fi

if [[ $CALIB_PRIMVTX_MEANVTX == 1 ]] ; then add_semicolon_separated CALIBDATASPEC "pvtx:GLO/PVTX/0"; fi
if [[ $CALIB_TOF_LHCPHASE == 1 ]] || [[ $CALIB_TOF_CHANNELOFFSETS == 1 ]]; then add_semicolon_separated CALIBDATASPEC "calibTOF:TOF/CALIBDATA/0"; fi
if [[ $CALIB_TOF_DIAGNOSTICS == 1 ]]; then add_semicolon_separated CALIBDATASPEC "diagWords:TOF/DIAFREQ/0"; fi

echo CALIBDATASPEC = $CALIBDATASPEC 1>&2

