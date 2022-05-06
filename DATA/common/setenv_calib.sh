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
	if [[ -z ${CALIB_PRIMVTX_MEANVTX+x} ]]; then CALIB_PRIMVTX_MEANVTX=1; fi
    else
	CALIB_PRIMVTX_MEANVTX=0
    fi

    # calibrations for TOF
    if has_detector_calib TOF && has_detector_reco TOF; then
	if has_detector_matching ITSTPCTOF || has_detector_matching ITSTPCTRDTOF; then
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
    if has_detector_calib TPC && has_detectors ITS TPC TOF TRD; then
	if has_detectors TPC ITS TRD TOF && has_detector_matching ITSTPCTRDTOF; then
	    if [[ -z ${CALIB_TPC_SCDCALIB+x} ]]; then CALIB_TPC_SCDCALIB=1; fi
	else
	    CALIB_TPC_SCDCALIB=0
	fi
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

# prim vtx
if [[ $CALIB_PRIMVTX_MEANVTX == 1 ]] ; then add_semicolon_separated CALIBDATASPEC "pvtx:GLO/PVTX/0"; fi

# TOF
if [[ $CALIB_TOF_LHCPHASE == 1 ]] || [[ $CALIB_TOF_CHANNELOFFSETS == 1 ]]; then add_semicolon_separated CALIBDATASPEC "calibTOF:TOF/CALIBDATA/0"; fi
if [[ $CALIB_TOF_DIAGNOSTICS == 1 ]]; then add_semicolon_separated CALIBDATASPEC "diagWords:TOF/DIAFREQ/0"; fi

# EMC
if [[ $CALIB_EMC_CHANNELCALIB == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC "cellsEMC:EMC/CELLS/0"
    add_semicolon_separated CALIBDATASPEC "cellsTrgREMC:EMC/CELLSTRGR/0"
fi

# PHS
if [[ $CALIB_PHS_ENERGYCALIB == 1 ]] || [[ $CALIB_PHS_TURNONCALIB == 1 ]] || [[ $CALIB_PHS_RUNBYRUNCALIB == 1 ]]; then
    add_semicolon_separated CALIBDATASPEC "clsPHS:PHS/CLUSTERS/0;"
    add_semicolon_separated CALIBDATASPEC "clTRPHS:PHS/CLUSTERTRIGREC/0;"
fi
if [[ $CALIB_PHS_ENERGYCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC "cluelementsPHS:PHS/CLUELEMENTS/0;"; fi
if [[ $CALIB_PHS_BADMAPCALIB == 1 ]] || [[ $CALIB_PHS_TURNONCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC "cellsPHS:PHS/CELLS/0;"; fi
if [[ $CALIB_PHS_TURNONCALIB == 1 ]]; then add_semicolon_separated CALIBDATASPEC "cellsTRPHS:PHS/CELLTRIGREC/0;"; fi

# printing for debug
echo CALIBDATASPEC = $CALIBDATASPEC 1>&2

