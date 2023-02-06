# script to set extra env variables
# taking some stuff from alien

# process flags passed to the script

export SETENV_NO_ULIMIT=1

# to avoid memory issues
export DPL_DEFAULT_PIPELINE_LENGTH=16

# detector list
if [[ -n $ALIEN_JDL_WORKFLOWDETECTORS ]]; then
  export WORKFLOW_DETECTORS=$ALIEN_JDL_WORKFLOWDETECTORS
else
  export WORKFLOW_DETECTORS=ITS,TPC,TOF,FV0,FT0,FDD,MID,MFT,MCH,TRD,EMC,PHS,CPV,HMP,ZDC,CTP
fi

# ad-hoc settings for CTF reader: we are on the grid, we read the files remotely
echo "*********************** mode = ${MODE}"
unset ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow
if [[ $MODE == "remote" ]]; then
  export INPUT_FILE_COPY_CMD="\"alien_cp ?src file://?dst\""
  export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="--remote-regex \"^alien:///alice/data/.+\""
fi

# checking for remapping
if [[ $remappingITS == 1 ]] || [[ $remappingMFT == 1 ]]; then
  REMAPPING="--condition-remap \"http://alice-ccdb.cern.ch/RecITSMFT="
  if [[ $remappingITS == 1 ]]; then
    REMAPPING=$REMAPPING"ITS/Calib/ClusterDictionary"
    if [[ $remappingMFT == 1 ]]; then
      REMAPPING=$REMAPPING","
    fi
  fi
  if [[ $remappingMFT == 1 ]]; then
    REMAPPING=$REMAPPING"MFT/Calib/ClusterDictionary"
  fi
  REMAPPING=$REMAPPING\"
fi

echo remapping = $REMAPPING
echo "BeamType = $BEAMTYPE"
echo "PERIOD = $PERIOD"
# other ad-hoc settings for CTF reader
export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="$ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow --allow-missing-detectors $REMAPPING"
echo RUN = $RUNNUMBER
if [[ $RUNNUMBER -ge 521889 ]]; then
  export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="$ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow --its-digits --mft-digits"
  export DISABLE_DIGIT_CLUSTER_INPUT="--digits-from-upstream"
  MAXBCDIFFTOMASKBIAS_ITS="ITSClustererParam.maxBCDiffToMaskBias=10"
  MAXBCDIFFTOMASKBIAS_MFT="MFTClustererParam.maxBCDiffToMaskBias=10"
fi
# shift by +1 BC TRD(2), PHS(4), CPV(5), EMC(6), HMP(7) and by (orbitShift-1)*3564+1 BCs the ZDC since it internally resets the orbit to 1 at SOR and BC is shifted by -1 like for triggered detectors.
# run 520403: orbitShift = 59839744 --> final shift = 213268844053
# run 520418: orbitShift = 28756480 --> final shift = 102488091157
# The "wrong" +1 offset request for ITS (0) must produce alarm since shifts are not supported there
if [[ $PERIOD == "LHC22s" ]]; then
  # CTP asked to extract their digits
  export ADD_EXTRA_WORKFLOW="o2-ctp-digit-writer"

  TPCITSTIMEERR="0.3"
  TPCITSTIMEBIAS="0"
  if [[ $RUNNUMBER -eq 529397 ]]; then
    TPCCLUSTERTIMESHIFT="-11.25" # 90 BC
  elif [[ $RUNNUMBER -eq 529399 ]]; then
    TPCCLUSTERTIMESHIFT="-10.75" # 86 BC
  elif [[ $RUNNUMBER -eq 529403 ]]; then
    ZDC_BC_SHIFT=213268844053
    TPCCLUSTERTIMESHIFT="-10.75" # 86 BC
  elif [[ $RUNNUMBER -eq 529414 ]]; then
    TPCCLUSTERTIMESHIFT="-3."  # 24/62 BC
    if [[ -f list.list ]]; then
      threshCTF="/alice/data/2022/LHC22s/529414/raw/2340/o2_ctf_run00529414_orbit0010200192_tf0000072971_epn086.root"
      ctf0=`head -n1 list.list`
      ctf0=${ctf0/alien:\/\//}
      [[ $ctf0 < $threshCTF ]] && TPCCLUSTERTIMESHIFT="-3." || TPCCLUSTERTIMESHIFT="-7.75"
    fi
  elif [[ $RUNNUMBER -eq 529418 ]]; then
    ZDC_BC_SHIFT=102488091157
    TPCCLUSTERTIMESHIFT="-5.5"  # 44 BC
  else
    ZDC_BC_SHIFT=0
  fi
  export CONFIG_EXTRA_PROCESS_o2_ctf_reader_workflow+="TriggerOffsetsParam.customOffset[2]=1;TriggerOffsetsParam.customOffset[4]=1;TriggerOffsetsParam.customOffset[5]=1;TriggerOffsetsParam.customOffset[6]=1;TriggerOffsetsParam.customOffset[7]=1;TriggerOffsetsParam.customOffset[11]=$ZDC_BC_SHIFT;"
  export PVERTEXER+=";pvertexer.dbscanDeltaT=1;pvertexer.maxMultRatDebris=1.;"
fi

# fix also ZDC in the pp run 529038
if [[ $PERIOD == "LHC22q" ]]; then
  if [[ $RUNNUMBER -eq 529003 ]]; then
    ZDC_BC_SHIFT=427744319508;
  elif [[ $RUNNUMBER -eq 529005 ]]; then
    ZDC_BC_SHIFT=585290682900
  elif [[ $RUNNUMBER -eq 529006 ]]; then
    ZDC_BC_SHIFT=1007373207060
  elif [[ $RUNNUMBER -eq 529008 ]]; then
    ZDC_BC_SHIFT=1379963461140
  elif [[ $RUNNUMBER -eq 529009 ]]; then
    ZDC_BC_SHIFT=1454804952084
  elif [[ $RUNNUMBER -eq 529015 ]]; then
    ZDC_BC_SHIFT=2244823203348
  elif [[ $RUNNUMBER -eq 529037 ]]; then
    ZDC_BC_SHIFT=256033194516
  elif [[ $RUNNUMBER -eq 529038 ]]; then
    ZDC_BC_SHIFT=486590350356
  elif [[ $RUNNUMBER -eq 529039 ]]; then
    ZDC_BC_SHIFT=1399525886484
  elif [[ $RUNNUMBER -eq 529043 ]]; then
    ZDC_BC_SHIFT=3079675091988
  fi
  [[ ! -z $ZDC_BC_SHIFT ]] && export CONFIG_EXTRA_PROCESS_o2_ctf_reader_workflow+="TriggerOffsetsParam.customOffset[11]=$ZDC_BC_SHIFT;"
fi

# ITSTPC vs FT0 time shift
if [[ -z $TPCCLUSTERTIMESHIFT ]]; then
  SHIFTSCRIPT="$O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$PASS/ShiftMap.sh"
  if [[ -f "ShiftMap.sh" ]]; then
    SHIFTSCRIPT="ShiftMap.sh"
  fi
  source $SHIFTSCRIPT $RUNNUMBER
fi
if [[ -z $TPCCLUSTERTIMESHIFT ]]; then
  echo "TPC cluster time shift not defined for current run"
  TPCCLUSTERTIMESHIFT=0
fi
echo "TPC cluster time will be shifted by $TPCCLUSTERTIMESHIFT"

# run-dependent options
if [[ -f "setenv_run.sh" ]]; then
    source setenv_run.sh
else
    echo "************************************************************"
    echo No ad-hoc run-dependent settings for current async processing
    echo "************************************************************"
fi

# TPC vdrift
PERIODLETTER=${PERIOD: -1}
VDRIFTPARAMOPTION=
if [[ $PERIODLETTER < m ]]; then
  root -b -q "$O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$PASS/getTPCvdrift.C+($RUNNUMBER)"
  export VDRIFT=`cat vdrift.txt`
  VDRIFTPARAMOPTION="TPCGasParam.DriftV=$VDRIFT"
  echo "Setting TPC vdrift to $VDRIFT"
else
  echo "TPC vdrift will be taken from CCDB"
fi

# IR
cp $O2DPG_ROOT/DATA/production/common/getIRandDuration.C ./
root -b -q "getIRandDuration.C+($RUNNUMBER)"
export RUN_IR=`cat IR.txt`
echo "IR for current run ($RUNNUMBER) = $RUN_IR"
export RUN_DURATION=`cat Duration.txt`
echo "Duration of current run ($RUNNUMBER) = $RUN_DURATION"

# For runs shorter than 10 minutes we have only a single slot.
# In that case we have to adopt the slot length in order to
# set the maximum number of processed tracks per TF correctly
if (( RUN_DURATION < 600 )); then
  export CALIB_TPC_SCDCALIB_SLOTLENGTH=$RUN_DURATION
fi

echo "BeamType = $BEAMTYPE"

if [[ $ALIEN_JDL_ENABLEMONITORING == "0" ]]; then
  export ENABLE_METRICS=0
else
  # remove monitoring-backend
  export ENABLE_METRICS=1
  # add the performance metrics
  export ARGS_ALL_EXTRA=" --resources-monitoring 50 --resources-monitoring-dump-interval 50"
fi

#ALIGNLEVEL=0: before December 2022 alignment, 1: after December 2022 alignment
ALIGNLEVEL=1
if [[ $BEAMTYPE == "PbPb" || $PERIOD == "MAY" || $PERIOD == "JUN" || $PERIOD == "LHC22c" || $PERIOD == "LHC22d" || $PERIOD == "LHC22e" || $PERIOD == "LHC22f" ]]; then
  ALIGNLEVEL=0
  if [[ $ALIEN_JDL_LPMPRODUCTIONTYPE == "MC" ]]; then
    # extract pass number
    ANCHORED_PASS=$ALIEN_JDL_LPMANCHOREPASSNAME
    ANCHORED_PASS_NUMBER=`echo $ANCHORED_PASS | sed 's/^apass//'`
    echo "ANCHORED_PASS_NUMER = $ANCHORED_PASS_NUMBER"
    if [[ $PERIOD == "MAY" || $PERIOD == "JUN" ]] && [[ $ANCHORED_PASS_NUMBER -gt 1 ]]; then
      ALIGNLEVEL=1
    elif [[ $PERIOD == "LHC22c" || $PERIOD == "LHC22d" || $PERIOD == "LHC22e" || $PERIOD == "LHC22f" ]] && [[ $ANCHORED_PASS_NUMBER -gt 2 ]]; then
      ALIGNLEVEL=1
    fi
  fi
fi

# some settings in common between workflows
if [[ $ALIGNLEVEL == 0 ]]; then
  ERRIB="9e-4"
  ERROB="1e-2"
  export ITS_CONFIG=" --tracking-mode sync_misaligned"
elif [[ $ALIGNLEVEL == 1 ]]; then
  ERRIB="100e-8"
  ERROB="100e-8"
  [[ -z $TPCITSTIMEERR ]] && TPCITSTIMEERR="0.2"
  export ITS_CONFIG=" --tracking-mode async"
fi

export ITSEXTRAERR="ITSCATrackerParam.sysErrY2[0]=$ERRIB;ITSCATrackerParam.sysErrZ2[0]=$ERRIB;ITSCATrackerParam.sysErrY2[1]=$ERRIB;ITSCATrackerParam.sysErrZ2[1]=$ERRIB;ITSCATrackerParam.sysErrY2[2]=$ERRIB;ITSCATrackerParam.sysErrZ2[2]=$ERRIB;ITSCATrackerParam.sysErrY2[3]=$ERROB;ITSCATrackerParam.sysErrZ2[3]=$ERROB;ITSCATrackerParam.sysErrY2[4]=$ERROB;ITSCATrackerParam.sysErrZ2[4]=$ERROB;ITSCATrackerParam.sysErrY2[5]=$ERROB;ITSCATrackerParam.sysErrZ2[5]=$ERROB;ITSCATrackerParam.sysErrY2[6]=$ERROB;ITSCATrackerParam.sysErrZ2[6]=$ERROB;"

# ad-hoc options for ITS reco workflow
EXTRA_ITSRECO_CONFIG=
if [[ $BEAMTYPE == "PbPb" ]]; then
  EXTRA_ITSRECO_CONFIG="ITSCATrackerParam.trackletsPerClusterLimit=5.;ITSCATrackerParam.cellsPerClusterLimit=5.;ITSVertexerParam.clusterContributorsCut=16;"
elif [[ $BEAMTYPE == "pp" ]]; then
  EXTRA_ITSRECO_CONFIG="ITSVertexerParam.phiCut=0.5;ITSVertexerParam.clusterContributorsCut=3;ITSVertexerParam.tanLambdaCut=0.2;"
fi
export CONFIG_EXTRA_PROCESS_o2_its_reco_workflow="$MAXBCDIFFTOMASKBIAS_ITS;$EXTRA_ITSRECO_CONFIG;"

# in the ALIGNLEVEL there was inconsistency between the internal errors of sync_misaligned and ITSEXTRAERR
if [[ $ALIGNLEVEL != 0 ]]; then
 export CONFIG_EXTRA_PROCESS_o2_its_reco_workflow+="$ITSEXTRAERR;"
fi

# ad-hoc options for GPU reco workflow
export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow="GPU_global.dEdxDisableResidualGainMap=1;$VDRIFTPARAMOPTION;"
[[ ! -z $TPCCLUSTERTIMESHIFT ]] && export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow+="GPU_rec_tpc.clustersShiftTimebins=$TPCCLUSTERTIMESHIFT;"

# ad-hoc settings for TOF reco
# export ARGS_EXTRA_PROCESS_o2_tof_reco_workflow="--use-ccdb --ccdb-url-tof \"http://alice-ccdb.cern.ch\""
# since commit on Dec, 4
export ARGS_EXTRA_PROCESS_o2_tof_reco_workflow="--use-ccdb"

# ad-hoc options for primary vtx workflow
#export PVERTEXER="pvertexer.acceptableScale2=9;pvertexer.minScale2=2.;pvertexer.nSigmaTimeTrack=4.;pvertexer.timeMarginTrackTime=0.5;pvertexer.timeMarginVertexTime=7.;pvertexer.nSigmaTimeCut=10;pvertexer.dbscanMaxDist2=30;pvertexer.dcaTolerance=3.;pvertexer.pullIniCut=100;pvertexer.addZSigma2=0.1;pvertexer.tukey=20.;pvertexer.addZSigma2Debris=0.01;pvertexer.addTimeSigma2Debris=1.;pvertexer.maxChi2Mean=30;pvertexer.timeMarginReattach=3.;pvertexer.addTimeSigma2Debris=1.;"
# following comment https://alice.its.cern.ch/jira/browse/O2-2691?focusedCommentId=278262&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-278262
#export PVERTEXER="pvertexer.acceptableScale2=9;pvertexer.minScale2=2.;pvertexer.nSigmaTimeTrack=4.;pvertexer.timeMarginTrackTime=0.5;pvertexer.timeMarginVertexTime=7.;pvertexer.nSigmaTimeCut=10;pvertexer.dbscanMaxDist2=36;pvertexer.dcaTolerance=3.;pvertexer.pullIniCut=100;pvertexer.addZSigma2=0.1;pvertexer.tukey=20.;pvertexer.addZSigma2Debris=0.01;pvertexer.addTimeSigma2Debris=1.;pvertexer.maxChi2Mean=30;pvertexer.timeMarginReattach=3.;pvertexer.addTimeSigma2Debris=1.;pvertexer.dbscanDeltaT=24;pvertexer.maxChi2TZDebris=100;pvertexer.maxMultRatDebris=1.;pvertexer.dbscanAdaptCoef=20.;pvertexer.timeMarginVertexTime=1.3"
# updated on 7 Sept 2022
EXTRA_PRIMVTX_TimeMargin=""
if [[ $BEAMTYPE == "PbPb" || $PERIOD == "MAY" || $PERIOD == "JUN" || $PERIOD == LHC22* ]]; then
  EXTRA_PRIMVTX_TimeMargin="pvertexer.timeMarginVertexTime=1.3"
fi

export PVERTEXER+="pvertexer.acceptableScale2=9;pvertexer.minScale2=2;$EXTRA_PRIMVTX_TimeMargin;"
if [[ $ALIGNLEVEL == 1 ]]; then
  if [[ $BEAMTYPE == "pp" ]]; then
    export PVERTEXER+="pvertexer.maxChi2TZDebris=40;pvertexer.maxChi2Mean=12;pvertexer.maxMultRatDebris=1.;pvertexer.addTimeSigma2Debris=1e-2;pvertexer.meanVertexExtraErrSelection=0.03;"
  elif [[ $BEAMTYPE == "PbPb" ]]; then
    # at the moment placeholder
    export PVERTEXER+="pvertexer.maxChi2Mean=12;pvertexer.addTimeSigma2Debris=1e-2;pvertexer.meanVertexExtraErrSelection=0.03;"
  fi
fi


# secondary vertexing
export SVTX="svertexer.checkV0Hypothesis=false;svertexer.checkCascadeHypothesis=false"

export CONFIG_EXTRA_PROCESS_o2_primary_vertexing_workflow="$PVERTEXER;$VDRIFTPARAMOPTION;"
export CONFIG_EXTRA_PROCESS_o2_secondary_vertexing_workflow="$SVTX"

# ad-hoc settings for its-tpc matching
CUT_MATCH_CHI2=160
if [[ $ALIGNLEVEL == 0 ]]; then
  export ITSTPCMATCH="tpcitsMatch.safeMarginTimeCorrErr=10.;tpcitsMatch.cutMatchingChi2=$CUT_MATCH_CHI2;tpcitsMatch.crudeAbsDiffCut[0]=5;tpcitsMatch.crudeAbsDiffCut[1]=5;tpcitsMatch.crudeAbsDiffCut[2]=0.3;tpcitsMatch.crudeAbsDiffCut[3]=0.3;tpcitsMatch.crudeAbsDiffCut[4]=10;tpcitsMatch.crudeNSigma2Cut[0]=200;tpcitsMatch.crudeNSigma2Cut[1]=200;tpcitsMatch.crudeNSigma2Cut[2]=200;tpcitsMatch.crudeNSigma2Cut[3]=200;tpcitsMatch.crudeNSigma2Cut[4]=900;"
elif [[ $ALIGNLEVEL == 1 ]]; then
  export ITSTPCMATCH="tpcitsMatch.safeMarginTimeCorrErr=10.;tpcitsMatch.cutMatchingChi2=$CUT_MATCH_CHI2;tpcitsMatch.crudeAbsDiffCut[0]=6;tpcitsMatch.crudeAbsDiffCut[1]=6;tpcitsMatch.crudeAbsDiffCut[2]=0.3;tpcitsMatch.crudeAbsDiffCut[3]=0.3;tpcitsMatch.crudeAbsDiffCut[4]=5;"
fi

export CONFIG_EXTRA_PROCESS_o2_tpcits_match_workflow="$ITSEXTRAERR;$ITSTPCMATCH;$VDRIFTPARAMOPTION;"
[[ ! -z "${TPCITSTIMEBIAS}" ]] && export CONFIG_EXTRA_PROCESS_o2_tpcits_match_workflow+="tpcitsMatch.globalTimeBiasMUS=$TPCITSTIMEBIAS;"
[[ ! -z "${TPCITSTIMEERR}" ]] && export CONFIG_EXTRA_PROCESS_o2_tpcits_match_workflow+="tpcitsMatch.globalTimeExtraErrorMUS=$TPCITSTIMEERR;"

# enabling AfterBurner
if [[ $WORKFLOW_DETECTORS =~ (^|,)"FT0"(,|$) ]] ; then
  export ARGS_EXTRA_PROCESS_o2_tpcits_match_workflow="--use-ft0"
fi

# ad-hoc settings for TOF matching
export ARGS_EXTRA_PROCESS_o2_tof_matcher_workflow="--output-type matching-info,calib-info --enable-dia"
export CONFIG_EXTRA_PROCESS_o2_tof_matcher_workflow="$ITSEXTRAERR;$VDRIFTPARAMOPTION;"

# ad-hoc settings for TRD matching
export CONFIG_EXTRA_PROCESS_o2_trd_global_tracking="$ITSEXTRAERR;$VDRIFTPARAMOPTION;"

# ad-hoc settings for FT0
export ARGS_EXTRA_PROCESS_o2_ft0_reco_workflow="--ft0-reconstructor"

# ad-hoc settings for FV0
export ARGS_EXTRA_PROCESS_o2_fv0_reco_workflow="--fv0-reconstructor"

# ad-hoc settings for FDD
#...

# ad-hoc settings for MFT
if [[ $BEAMTYPE == "pp" || $PERIOD == "LHC22s" ]]; then
  export CONFIG_EXTRA_PROCESS_o2_mft_reco_workflow="MFTTracking.RBins=20;MFTTracking.PhiBins=60;MFTTracking.MFTRadLength=0.084;$MAXBCDIFFTOMASKBIAS_MFT"
else
  export CONFIG_EXTRA_PROCESS_o2_mft_reco_workflow="MFTTracking.MFTRadLength=0.084;$MAXBCDIFFTOMASKBIAS_MFT"
fi
# ad-hoc settings for MCH
export CONFIG_EXTRA_PROCESS_o2_mch_reco_workflow="MCHClustering.lowestPadCharge=20;MCHClustering.defaultClusterResolution=0.4;MCHTracking.chamberResolutionX=0.4;MCHTracking.chamberResolutionY=0.4;MCHTracking.sigmaCutForTracking=7;MCHTracking.sigmaCutForImprovement=6;MCHDigitFilter.timeOffset=126"

# possibly adding calib steps as done online
# could be done better, so that more could be enabled in one go
if [[ $ADD_CALIB == "1" ]]; then
  export WORKFLOW_PARAMETERS="CALIB,CALIB_LOCAL_INTEGRATED_AGGREGATOR,${WORKFLOW_PARAMETERS}"
  export CALIB_DIR="./"
  export CALIB_TPC_SCDCALIB_SENDTRKDATA=0
  export CALIB_PRIMVTX_MEANVTX=0
  export CALIB_TOF_LHCPHASE=0
  export CALIB_TOF_CHANNELOFFSETS=0
  export CALIB_TOF_DIAGNOSTICS=0
  export CALIB_EMC_BADCHANNELCALIB=0
  export CALIB_EMC_TIMECALIB=0
  export CALIB_PHS_ENERGYCALIB=0
  export CALIB_PHS_BADMAPCALIB=0
  export CALIB_PHS_TURNONCALIB=0
  export CALIB_PHS_RUNBYRUNCALIB=0
  export CALIB_PHS_L1PHASE=0
  export CALIB_TRD_VDRIFTEXB=0
  export CALIB_TPC_TIMEGAIN=0
  export CALIB_TPC_RESPADGAIN=0
  export CALIB_TPC_VDRIFTTGL=0
  export CALIB_CPV_GAIN=0
  export CALIB_ZDC_TDC=0
  export CALIB_FT0_TIMEOFFSET=0
  export CALIB_TPC_SCDCALIB=0
  if [[ $DO_TPC_RESIDUAL_EXTRACTION == "1" ]]; then
    export CALIB_TPC_SCDCALIB=1
    export CALIB_TPC_SCDCALIB_SENDTRKDATA=1
    # ad-hoc settings for TPC residual extraction
    export ARGS_EXTRA_PROCESS_o2_calibration_residual_aggregator="--output-type trackParams,unbinnedResid,binnedResid"
    if [[ $ALIEN_JDL_DEBUGRESIDUALEXTRACTION == "1" ]]; then
      export ARGS_EXTRA_PROCESS_o2_tpc_scdcalib_interpolation_workflow="--enable-itsonly --tracking-sources ITS,TPC,TRD,TOF,ITS-TPC,ITS-TPC-TRD,ITS-TPC-TRD-TOF"
      export CONFIG_EXTRA_PROCESS_o2_tpc_scdcalib_interpolation_workflow="scdcalib.maxTracksPerCalibSlot=-1;scdcalib.minPtNoOuterPoint=0.8;scdcalib.minTPCNClsNoOuterPoint=120"
      export ARGS_EXTRA_PROCESS_o2_trd_global_tracking="--enable-qc"
    fi
  fi
  export CALIB_EMC_ASYNC_RECALIB="$ALIEN_JDL_DOEMCCALIB"
  if [[ $ALIEN_JDL_DOTRDVDRIFTEXBCALIB == "1" ]]; then
    export CALIB_TRD_VDRIFTEXB="$ALIEN_JDL_DOTRDVDRIFTEXBCALIB"
    export ARGS_EXTRA_PROCESS_o2_calibration_trd_workflow="--enable-root-output"
    export ARGS_EXTRA_PROCESS_o2_trd_global_tracking="--enable-qc"
  fi
  if [[ $ALIEN_JDL_DOMEANVTXCALIB == 1 ]]; then
    export CALIB_PRIMVTX_MEANVTX="$ALIEN_JDL_DOMEANVTXCALIB"
    export TFPERSLOTS_MEANVTX=550000 # 1 hour
    export DELAYINTFS_MEANVTX=55000  # 10 minutes
  fi
  if [[ $ALIEN_JDL_DOUPLOADSLOCALLY == 1 ]]; then
    export CCDB_POPULATOR_UPLOAD_PATH="file://$PWD"
  fi
fi


# Enabling AOD
if [[ $ALIEN_JDL_AODOFF != "1" ]]; then
  export WORKFLOW_PARAMETERS="AOD,${WORKFLOW_PARAMETERS}"
fi

# ad-hoc settings for AOD
export ARGS_EXTRA_PROCESS_o2_aod_producer_workflow="--aod-writer-maxfilesize $AOD_FILE_SIZE"

# Enabling QC
if [[ $ALIEN_JDL_QCOFF != "1" ]]; then
  export WORKFLOW_PARAMETERS="QC,${WORKFLOW_PARAMETERS}"
fi
export QC_CONFIG_PARAM="--local-batch=QC.root --override-values \"qc.config.Activity.number=$RUNNUMBER;qc.config.Activity.passName=$PASS;qc.config.Activity.periodName=$PERIOD\""
export GEN_TOPO_WORKDIR="./"
#export QC_JSON_FROM_OUTSIDE="QC-20211214.json"

if [[ ! -z $QC_JSON_FROM_OUTSIDE ]]; then
    sed -i 's/REPLACE_ME_RUNNUMBER/'"${RUNNUMBER}"'/g' $QC_JSON_FROM_OUTSIDE
    sed -i 's/REPLACE_ME_PASS/'"${PASS}"'/g' $QC_JSON_FROM_OUTSIDE
    sed -i 's/REPLACE_ME_PERIOD/'"${PERIOD}"'/g' $QC_JSON_FROM_OUTSIDE
fi
