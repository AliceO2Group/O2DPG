# script to set extra env variables
# taking some stuff from alien

# process flags passed to the script

if [[ -z "$ALIEN_JDL_USEGPUS" || $ALIEN_JDL_USEGPUS != 1 ]]; then
  export SETENV_NO_ULIMIT=1
fi

# to avoid memory issues - we don't do this on the EPNs, since it can affect the performance
if [[ $ALIEN_JDL_USEGPUS != 1 ]]; then
  export DPL_DEFAULT_PIPELINE_LENGTH=16
fi

# check if this is a production on skimmed data
if grep -q /skimmed/ wn.xml ; then
  export ON_SKIMMED_DATA=1;
fi

if [[ $RUNNUMBER -lt 544772 ]]; then
  # these runs were using external dictionaries
  : ${RANS_OPT:="--ans-version compat"}
  export RANS_OPT
fi   
echo "RSRUNNUMBER = $RUNNUMBER RANS_OPT = $RANS_OPT"

# detector list
if [[ -n $ALIEN_JDL_WORKFLOWDETECTORS ]]; then
  export WORKFLOW_DETECTORS=$ALIEN_JDL_WORKFLOWDETECTORS
else
  export WORKFLOW_DETECTORS=ITS,TPC,TOF,FV0,FT0,FDD,MID,MFT,MCH,TRD,EMC,PHS,CPV,HMP,ZDC,CTP
  if [[ $RUNNUMBER == 528529 ]] || [[ $RUNNUMBER == 528530 ]]; then
    # removing MID for these runs: it was noisy and therefore declared bad, and makes the reco crash
    export WORKFLOW_DETECTORS=ITS,TPC,TOF,FV0,FT0,FDD,MFT,MCH,TRD,EMC,PHS,CPV,HMP,ZDC,CTP
  fi
  # list of detectors to possibly exclude
  if [[ -n $ALIEN_JDL_DETECTORSEXCLUDE ]]; then
    echo "ALIEN_JDL_DETECTORSEXCLUDE = $ALIEN_JDL_DETECTORSEXCLUDE"
    export DETECTORS_EXCLUDE=$ALIEN_JDL_DETECTORSEXCLUDE  # will be used in the async_pass.sh if we run in split mode
    export WORKFLOW_DETECTORS_EXCLUDE=$DETECTORS_EXCLUDE
  fi
fi

# ad-hoc settings for CTF reader: we are on the grid, we read the files remotely
echo "*********************** mode = ${MODE}"
unset ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow

if [[ $MODE == "remote" ]]; then
  if [[ $ALIEN_JDL_REMOTEREADING != 1 ]]; then
    export INPUT_FILE_COPY_CMD="\"alien_cp ?src file://?dst\""
    export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="$ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow --remote-regex \"^alien:///alice/data/.+\""
  else
    export INPUT_FILE_COPY_CMD="no-copy"
  fi
fi

# adjusting for trigger LM_L0 correction, which was not there before July 2022
if [[ $PERIOD == "LHC22c" ]] || [[ $PERIOD == "LHC22d" ]] || [[ $PERIOD == "LHC22e" ]] || [[ $PERIOD == "JUN" ]] || [[ $PERIOD == "LHC22f" ]] ; then
  if [[ $ALIEN_JDL_LPMPRODUCTIONTYPE != "MC" ]]; then
    export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="$ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow --correct-trd-trigger-offset"
  fi
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

# needed if we need more wf
export ADD_EXTRA_WORKFLOW=

# other ad-hoc settings for CTF reader
export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="$ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow --allow-missing-detectors $REMAPPING"
echo RUN = $RUNNUMBER
if [[ $RUNNUMBER -ge 521889 ]]; then
  export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="$ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow --its-digits --mft-digits"
  export DISABLE_DIGIT_CLUSTER_INPUT="--digits-from-upstream"
  MAXBCDIFFTOMASKBIAS_ITS="ITSClustererParam.maxBCDiffToMaskBias=-10"    # this explicitly disables ITS masking
  MAXBCDIFFTOSQUASHBIAS_ITS="ITSClustererParam.maxBCDiffToSquashBias=10" # this explicitly enables ITS squashing
  MAXBCDIFFTOMASKBIAS_MFT="MFTClustererParam.maxBCDiffToMaskBias=-10"    # this explicitly disables MFT masking
  MAXBCDIFFTOSQUASHBIAS_MFT="MFTClustererParam.maxBCDiffToSquashBias=10" # this explicitly enables MFT squashing
fi
# shift by +1 BC TRD(2), PHS(4), CPV(5), EMC(6), HMP(7) and by (orbitShift-1)*3564+1 BCs the ZDC since it internally resets the orbit to 1 at SOR and BC is shifted by -1 like for triggered detectors.
# run 520403: orbitShift = 59839744 --> final shift = 213268844053
# run 520418: orbitShift = 28756480 --> final shift = 102488091157
# The "wrong" +1 offset request for ITS (0) must produce alarm since shifts are not supported there
CTP_BC_SHIFT=0
if [[ $ALIEN_JDL_LPMANCHORYEAR == "2022" ]]; then
  CTP_BC_SHIFT=-294
fi
if [[ $RUNNUMBER -ge 538923 ]] && [[ $RUNNUMBER -le 539700 ]]; then
  # 3 BC offset (future direction) in CTP data observed for LHC23zd - LHC23zs
  CTP_BC_SHIFT=-3
fi
if [[ $PERIOD == "LHC22s" ]]; then
  # CTP asked to extract their digits
  add_comma_separated ADD_EXTRA_WORKFLOW "o2-ctp-digit-writer"
  # set all TPC shifts to 86 BCs (= -10.75 TB) as the jitter is due to the bad VDrift calibration
  TPCITSTIMEERR="0.3"
  TPCITSTIMEBIAS="0"
  if [[ $RUNNUMBER -eq 529397 ]]; then
    ZDC_BC_SHIFT=0
    TPCCLUSTERTIMESHIFT="-10.75"
  elif [[ $RUNNUMBER -eq 529399 ]]; then
    ZDC_BC_SHIFT=0
    TPCCLUSTERTIMESHIFT="-10.75"
  elif [[ $RUNNUMBER -eq 529403 ]]; then
    ZDC_BC_SHIFT=213268844053
    TPCCLUSTERTIMESHIFT="-10.75"
  elif [[ $RUNNUMBER -eq 529414 ]]; then
    ZDC_BC_SHIFT=0
    TPCCLUSTERTIMESHIFT="-10.75"
  elif [[ $RUNNUMBER -eq 529418 ]]; then
    ZDC_BC_SHIFT=102488091157
    TPCCLUSTERTIMESHIFT="-10.75"
  else
    ZDC_BC_SHIFT=0
  fi
  CTP_BC_SHIFT=-293
  if [[ $ALIEN_JDL_LPMPRODUCTIONTYPE != "MC" ]]; then
    export CONFIG_EXTRA_PROCESS_o2_ctf_reader_workflow+=";TriggerOffsetsParam.customOffset[2]=1;TriggerOffsetsParam.customOffset[4]=1;TriggerOffsetsParam.customOffset[5]=1;TriggerOffsetsParam.customOffset[6]=1;TriggerOffsetsParam.customOffset[7]=1;TriggerOffsetsParam.customOffset[11]=$ZDC_BC_SHIFT"
  fi
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
  if [[ $ALIEN_JDL_LPMPRODUCTIONTYPE != "MC" ]]; then
    [[ ! -z $ZDC_BC_SHIFT ]] && export CONFIG_EXTRA_PROCESS_o2_ctf_reader_workflow+=";TriggerOffsetsParam.customOffset[11]=$ZDC_BC_SHIFT;"
  fi
fi

# Apply BC shift of CTP IRs (whenever it is defined)
if [[ $CTP_BC_SHIFT -ne 0 ]]; then
  if [[ $ALIEN_JDL_LPMPRODUCTIONTYPE != "MC" ]]; then
    export CONFIG_EXTRA_PROCESS_o2_ctf_reader_workflow+=";TriggerOffsetsParam.customOffset[16]=$CTP_BC_SHIFT"
  fi
fi

# ITSTPC vs FT0 time shift
if [[ -z $TPCCLUSTERTIMESHIFT ]]; then
  SHIFTSCRIPT="$O2DPG_ROOT/DATA/production/configurations/asyncReco/ShiftMap.sh"
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
if [[ $ALIEN_JDL_LPMANCHORYEAR == "2022" ]] && [[ $PERIODLETTER < m ]]; then
  echo "In setenv_extra: time used so far = $timeUsed s"
  timeStart=`date +%s`
  time root -b -q "$O2DPG_ROOT/DATA/production/common/getTPCvdrift.C+($RUNNUMBER)"
  timeEnd=`date +%s`
  timeUsed=$(( $timeUsed+$timeEnd-$timeStart ))
  delta=$(( $timeEnd-$timeStart ))
  echo "Time spent to get VDrift for TPC = $delta s"
  export VDRIFT=`cat vdrift.txt`
  VDRIFTPARAMOPTION="TPCGasParam.DriftV=$VDRIFT"
  echo "Setting TPC vdrift to $VDRIFT"
else
  echo "TPC vdrift will be taken from CCDB"
fi

# IR
if [[ -z $RUN_IR ]] || [[ -z $RUN_DURATION ]] || [[ -z $RUN_BFIELD ]]; then
  cp $O2DPG_ROOT/DATA/production/common/getIRandDuration.C ./
  echo "In setenv_extra: time used so far = $timeUsed"
  timeStart=`date +%s`
  time o2-calibration-get-run-parameters -r $RUNNUMBER
  timeEnd=`date +%s`
  timeUsed=$(( $timeUsed+$timeEnd-$timeStart ))
  delta=$(( $timeEnd-$timeStart ))
  echo "Time spent in getting IR and duration of the run = $delta s"
  export RUN_IR=`cat IR.txt`
  export RUN_DURATION=`cat Duration.txt`
  export RUN_BFIELD=`cat BField.txt`
  export RUN_DETECTOR_LIST=`cat DetList.txt`
fi
echo "DETECTOR LIST for current run ($RUNNUMBER) = $RUN_DETECTOR_LIST"
echo "DURATION for current run ($RUNNUMBER) = $RUN_DURATION"
echo "B FIELD for current run ($RUNNUMBER) = $RUN_BFIELD"
echo "IR for current run ($RUNNUMBER) = $RUN_IR"
if (( $(echo "$RUN_IR <= 0" | bc -l) )); then
  echo "Changing run IR to 1 Hz, because $RUN_IR makes no sense"
  RUN_IR=1
fi

# Let's check if ZDC is in the detector list; this is needed for TPC dist correction scaling in PbPb 2023
SCALE_WITH_ZDC=1
SCALE_WITH_FT0=1
isZDCinDataTaking=`echo $RUN_DETECTOR_LIST | grep ZDC`
isFT0inDataTaking=`echo $RUN_DETECTOR_LIST | grep FT0`
[[ -z $isZDCinDataTaking ]] && SCALE_WITH_ZDC=0
[[ -z $isFT0inDataTaking ]] && SCALE_WITH_FT0=0

# For runs shorter than 10 minutes we have only a single slot.
# In that case we have to adopt the slot length in order to
# set the maximum number of processed tracks per TF correctly
if (( RUN_DURATION < 600 )); then
  export CALIB_TPC_SCDCALIB_SLOTLENGTH=$RUN_DURATION
fi

echo "BeamType = $BEAMTYPE"

if [[ $ALIEN_JDL_ENABLEMONITORING != "0" ]]; then
  # add the performance metrics
  export ENABLE_METRICS=1
  export ARGS_ALL_EXTRA="$ARGS_ALL_EXTRA --resources-monitoring 50 --resources-monitoring-dump-interval 50"
else
  # remove monitoring-backend
  export ENABLE_METRICS=0
fi

#ALIGNLEVEL=0: before December 2022 alignment, 1: after December 2022 alignment
ALIGNLEVEL=1
if [[ "0$OLDVERSION" == "01" ]] && [[ $BEAMTYPE == "PbPb" || $PERIOD == "MAY" || $PERIOD == "JUN" || $PERIOD == "LHC22c" || $PERIOD == "LHC22d" || $PERIOD == "LHC22e" || $PERIOD == "LHC22f" ]]; then
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

# some settings in common between workflows and affecting ITS-TPC matching
: ${CUT_MATCH_CHI2:=250}
if [[ $ALIGNLEVEL == 0 ]]; then
  ERRIB="9e-4"
  ERROB="1e-2"
  CUT_MATCH_CHI2=160
  export ITS_CONFIG=" --tracking-mode sync_misaligned"
  export ITSTPCMATCH="tpcitsMatch.safeMarginTimeCorrErr=10.;tpcitsMatch.cutMatchingChi2=$CUT_MATCH_CHI2;tpcitsMatch.crudeAbsDiffCut[0]=5;tpcitsMatch.crudeAbsDiffCut[1]=5;tpcitsMatch.crudeAbsDiffCut[2]=0.3;tpcitsMatch.crudeAbsDiffCut[3]=0.3;tpcitsMatch.crudeAbsDiffCut[4]=10;tpcitsMatch.crudeNSigma2Cut[0]=200;tpcitsMatch.crudeNSigma2Cut[1]=200;tpcitsMatch.crudeNSigma2Cut[2]=200;tpcitsMatch.crudeNSigma2Cut[3]=200;tpcitsMatch.crudeNSigma2Cut[4]=900;"
elif [[ $ALIGNLEVEL == 1 ]]; then
  ERRIB="100e-8"
  ERROB="100e-8"
  [[ -z $TPCITSTIMEERR ]] && TPCITSTIMEERR="0.2"
  [[ -z $ITS_CONFIG || "$ITS_CONFIG" != *"--tracking-mode"* ]] && export ITS_CONFIG+=" --tracking-mode async"
  CUT_MATCH_CHI2=160
  export ITSTPCMATCH="tpcitsMatch.safeMarginTimeCorrErr=2.;tpcitsMatch.cutMatchingChi2=$CUT_MATCH_CHI2;;tpcitsMatch.crudeAbsDiffCut[0]=6;tpcitsMatch.crudeAbsDiffCut[1]=6;tpcitsMatch.crudeAbsDiffCut[2]=0.3;tpcitsMatch.crudeAbsDiffCut[3]=0.3;tpcitsMatch.crudeAbsDiffCut[4]=5;tpcitsMatch.crudeNSigma2Cut[0]=100;tpcitsMatch.crudeNSigma2Cut[1]=100;tpcitsMatch.crudeNSigma2Cut[2]=100;tpcitsMatch.crudeNSigma2Cut[3]=100;tpcitsMatch.crudeNSigma2Cut[4]=100;"

  # enabling TPC calibration scaling
  # the default is to use CTP, unless specified differently in the JDL...
  INST_IR_FOR_TPC=${ALIEN_JDL_INSTIRFORTPC-CTP}
  #...but for 2022 data, where we will rely on different settings depending on the period; note that if ALIEN_JDL_INSTIRFORTPC is set, it has precedence
  if [[ $ALIEN_JDL_LPMANCHORYEAR == "2022" ]]; then
    INST_IR_FOR_TPC=${ALIEN_JDL_INSTIRFORTPC-CTPCCDB}
  fi
  if [[ $PERIOD == "LHC22s" ]]; then
    INST_IR_FOR_TPC=${ALIEN_JDL_INSTIRFORTPC-0} # in this way, only TPC/Calib/CorrectionMaps is applied, and we know that for 22s it is the same as TPC/Calib/CorrectionMapsRef; note that if ALIEN_JDL_INSTIRFORTPC is set, it has precedence
  elif [[ $PERIOD == @(LHC22c|LHC22d|LHC22e|JUN|LHC22f) ]]; then
    INST_IR_FOR_TPC=${ALIEN_JDL_INSTIRFORTPC-1} # scaling with very small value for low IR
  fi
  # in MC, we set it to a negative value to disable completely the corrections (not yet operational though, please check O2);
  # note that if ALIEN_JDL_INSTIRFORTPC is set, it has precedence
  if [[ $ALIEN_JDL_LPMPRODUCTIONTYPE == "MC" ]] && [[ $O2DPG_ENABLE_TPC_DISTORTIONS != "ON" ]]; then
    INST_IR_FOR_TPC=${ALIEN_JDL_INSTIRFORTPC--1}
  fi

  # now we set the options
  if [[ $INST_IR_FOR_TPC -gt 0 ]]; then # externally imposed IR for scaling
    echo "Applying externally provided IR for scaling, $INST_IR_FOR_TPC Hz"
    export TPC_CORR_SCALING+=";TPCCorrMap.lumiInst=$INST_IR_FOR_TPC"
  elif [[ $INST_IR_FOR_TPC == 0 ]]; then # when zero, only the TPC/Calib/CorrectionMaps is applied
    echo "Passed valued for scaling is zero, only TPC/Calib/CorrectionMaps will be applied"
    export TPC_CORR_SCALING+=";TPCCorrMap.lumiInst=$INST_IR_FOR_TPC"
  elif [[ $INST_IR_FOR_TPC -lt 0 ]]; then # do not apply any correction
    echo "Passed valued for scaling is smaller than zero, no scaling will be applied"
    echo "NOTA BENE: In the future, this value will signal to not apply any correction at all, which is not operational yet (but please check, as it depends on O2)"
    export TPC_CORR_SCALING+=";TPCCorrMap.lumiInst=$INST_IR_FOR_TPC"
  elif [[ $INST_IR_FOR_TPC == "CTPCCDB" ]]; then # using what we have in the CCDB CTP counters, extracted at the beginning of the script
    echo "Using CTP CCDB which gave the mean IR of the run at the beginning of the script ($RUN_IR Hz)"
    export TPC_CORR_SCALING+=";TPCCorrMap.lumiInst=$RUN_IR"
  elif [[ $INST_IR_FOR_TPC == "CTP" ]]; then
    if ! has_detector CTP ; then
      echo "TPC correction with CTP Lumi is requested but CTP is not in the WORKFLOW_DETECTORS=$WORKFLOW_DETECTORS"
      return 1
    fi
    echo "Using CTP inst lumi stored in data"
    export TPC_CORR_SCALING+=" --lumi-type 1 "
  elif [[ $INST_IR_FOR_TPC == "IDCCCDB" ]]; then
    echo "TPC correction with IDC from CCDB will be used"
    export TPC_CORR_SCALING+=" --lumi-type 2 "
    if [[ $ALIEN_JDL_USEDERIVATIVESFORSCALING == "1" ]]; then
      export TPC_CORR_SCALING+=" --corrmap-lumi-mode 1 "
    fi
  else
    echo "Unknown setting for INST_IR_FOR_TPC = $INST_IR_FOR_TPC (with ALIEN_JDL_INST_IR_FOR_TPC = $ALIEN_JDL_INST_IR_FOR_TPC)"
    return 1
  fi

  if [[ -n $ALIEN_JDL_MEANIRFORTPC && $ALIEN_JDL_MEANIRFORTPC > 0 ]]; then # externally imposed TPC map mean IR for scaling
    export TPC_CORR_SCALING+=";TPCCorrMap.lumiMean=$ALIEN_JDL_MEANIRFORTPC"
  fi

  if [[ $ALIEN_JDL_LPMANCHORYEAR == "2023" ]] && [[ $BEAMTYPE == "PbPb" ]] && ([[ -z $INST_IR_FOR_TPC ]] || [[ $INST_IR_FOR_TPC == "CTP" ]]); then
    echo "We are in PbPb 2023, the default - for now - is to use CTP in the data"
    unset TPC_CORR_SCALING
    export TPC_CORR_SCALING=";TPCCorrMap.lumiInstFactor=2.414;TPCCorrMap.lumiMean=0 --lumi-type 1 "
    if [[ $SCALE_WITH_ZDC == 0 ]]; then
      # scaling with FT0
      if [[ $SCALE_WITH_FT0 == 1 ]]; then
	export TPC_CORR_SCALING=" --ctp-lumi-source 1 --lumi-type 1 TPCCorrMap.lumiInstFactor=135.;TPCCorrMap.lumiMean=0"
      else
	echo "Neither ZDC nor FT0 are in the run, and this is from 2023 PbPb: we cannot scale TPC ditortion corrections, aborting..."
	return 1
      fi
    fi
  fi

  echo "Final setting for TPC scaling is:"
  echo $TPC_CORR_SCALING

  if [[ $PERIOD != @(LHC22c|LHC22d|LHC22e|JUN|LHC22f) ]] ; then
    echo "Setting TPCCLUSTERTIMESHIFT to 0"
    TPCCLUSTERTIMESHIFT=0
  else
    echo "We are in period $PERIOD, we need to keep the correction for the TPC cluster time, since no new vdrift was extracted"
  fi

  TRACKTUNETPCINNER="trackTuneParams.tpcCovInnerType=1;trackTuneParams.tpcCovInner[0]=0.01;trackTuneParams.tpcCovInner[1]=1.;trackTuneParams.tpcCovInner[2]=4e-7;trackTuneParams.tpcCovInner[3]=4.e-5;trackTuneParams.tpcCovInner[4]=6.8e-6;"
  TRACKTUNETPCOUTER="trackTuneParams.tpcCovOuterType=1;trackTuneParams.tpcCovOuter[0]=0.01;trackTuneParams.tpcCovOuter[1]=1.;trackTuneParams.tpcCovOuter[2]=4e-7;trackTuneParams.tpcCovOuter[3]=4.e-5;trackTuneParams.tpcCovOuter[4]=6.8e-6;"

fi

# adding additional cluster errors
# the values below should be squared, but the validation of those values (0.01 and 0.0225) is ongoing
TPCEXTRAERR=";GPU_rec_tpc.clusterError2AdditionalY=0.1;GPU_rec_tpc.clusterError2AdditionalZ=0.15;"
TRACKTUNETPC="$TPCEXTRAERR"

# combining parameters
[[ ! -z ${TRACKTUNETPCINNER:-} || ! -z ${TRACKTUNETPCOUTER:-} ]] && TRACKTUNETPC="$TRACKTUNETPC;trackTuneParams.sourceLevelTPC=true;$TRACKTUNETPCINNER;$TRACKTUNETPCOUTER"

export ITSEXTRAERR="ITSCATrackerParam.sysErrY2[0]=$ERRIB;ITSCATrackerParam.sysErrZ2[0]=$ERRIB;ITSCATrackerParam.sysErrY2[1]=$ERRIB;ITSCATrackerParam.sysErrZ2[1]=$ERRIB;ITSCATrackerParam.sysErrY2[2]=$ERRIB;ITSCATrackerParam.sysErrZ2[2]=$ERRIB;ITSCATrackerParam.sysErrY2[3]=$ERROB;ITSCATrackerParam.sysErrZ2[3]=$ERROB;ITSCATrackerParam.sysErrY2[4]=$ERROB;ITSCATrackerParam.sysErrZ2[4]=$ERROB;ITSCATrackerParam.sysErrY2[5]=$ERROB;ITSCATrackerParam.sysErrZ2[5]=$ERROB;ITSCATrackerParam.sysErrY2[6]=$ERROB;ITSCATrackerParam.sysErrZ2[6]=$ERROB;"

# ad-hoc options for ITS reco workflow
EXTRA_ITSRECO_CONFIG=
if [[ $BEAMTYPE == "PbPb" ]]; then
  EXTRA_ITSRECO_CONFIG="ITSVertexerParam.clusterContributorsCut=16;ITSVertexerParam.lowMultBeamDistCut=0;ITSCATrackerParam.nROFsPerIterations=12;ITSCATrackerParam.perPrimaryVertexProcessing=true"
elif [[ $BEAMTYPE == "pp" ]]; then
  EXTRA_ITSRECO_CONFIG="ITSVertexerParam.phiCut=0.5;ITSVertexerParam.clusterContributorsCut=3;ITSVertexerParam.tanLambdaCut=0.2;"
fi
export CONFIG_EXTRA_PROCESS_o2_its_reco_workflow+=";$MAXBCDIFFTOMASKBIAS_ITS;$MAXBCDIFFTOSQUASHBIAS_ITS;$EXTRA_ITSRECO_CONFIG;"

# in the ALIGNLEVEL there was inconsistency between the internal errors of sync_misaligned and ITSEXTRAERR
if [[ $ALIGNLEVEL != 0 ]]; then
 export CONFIG_EXTRA_PROCESS_o2_its_reco_workflow+=";$ITSEXTRAERR;"
fi

# ad-hoc options for GPU reco workflow
export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow+=";GPU_global.dEdxDisableResidualGainMap=1;$TRACKTUNETPC;$VDRIFTPARAMOPTION;"
if [[ $ALIEN_JDL_LPMPRODUCTIONTYPE == "MC" ]]; then
  export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow+=";GPU_global.dEdxDisableResidualGain=1"
fi
[[ ! -z $TPCCLUSTERTIMESHIFT ]] && [[ $ALIEN_JDL_LPMPRODUCTIONTYPE != "MC" ]] && export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow+=";GPU_rec_tpc.clustersShiftTimebins=$TPCCLUSTERTIMESHIFT;"

# ad-hoc settings for TOF reco
# export ARGS_EXTRA_PROCESS_o2_tof_reco_workflow+="--use-ccdb --ccdb-url-tof \"http://alice-ccdb.cern.ch\""
# since commit on Dec, 4
export ARGS_EXTRA_PROCESS_o2_tof_reco_workflow="$ARGS_EXTRA_PROCESS_o2_tof_reco_workflow --use-ccdb"

# ad-hoc options for primary vtx workflow
#export PVERTEXER="pvertexer.acceptableScale2=9;pvertexer.minScale2=2.;pvertexer.nSigmaTimeTrack=4.;pvertexer.timeMarginTrackTime=0.5;pvertexer.timeMarginVertexTime=7.;pvertexer.nSigmaTimeCut=10;pvertexer.dbscanMaxDist2=30;pvertexer.dcaTolerance=3.;pvertexer.pullIniCut=100;pvertexer.addZSigma2=0.1;pvertexer.tukey=20.;pvertexer.addZSigma2Debris=0.01;pvertexer.addTimeSigma2Debris=1.;pvertexer.maxChi2Mean=30;pvertexer.timeMarginReattach=3.;pvertexer.addTimeSigma2Debris=1.;"
# following comment https://alice.its.cern.ch/jira/browse/O2-2691?focusedCommentId=278262&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-278262
#export PVERTEXER="pvertexer.acceptableScale2=9;pvertexer.minScale2=2.;pvertexer.nSigmaTimeTrack=4.;pvertexer.timeMarginTrackTime=0.5;pvertexer.timeMarginVertexTime=7.;pvertexer.nSigmaTimeCut=10;pvertexer.dbscanMaxDist2=36;pvertexer.dcaTolerance=3.;pvertexer.pullIniCut=100;pvertexer.addZSigma2=0.1;pvertexer.tukey=20.;pvertexer.addZSigma2Debris=0.01;pvertexer.addTimeSigma2Debris=1.;pvertexer.maxChi2Mean=30;pvertexer.timeMarginReattach=3.;pvertexer.addTimeSigma2Debris=1.;pvertexer.dbscanDeltaT=24;pvertexer.maxChi2TZDebris=100;pvertexer.maxMultRatDebris=1.;pvertexer.dbscanAdaptCoef=20.;pvertexer.timeMarginVertexTime=1.3"
# updated on 7 Sept 2022
EXTRA_PRIMVTX_TimeMargin=""
if [[ $BEAMTYPE == "PbPb" || $PERIOD == "MAY" || $PERIOD == "JUN" || $PERIOD == LHC22* || $PERIOD == LHC23* ]]; then
  EXTRA_PRIMVTX_TimeMargin="pvertexer.timeMarginVertexTime=1.3"
fi

export PVERTEXER+=";pvertexer.acceptableScale2=9;pvertexer.minScale2=2;$EXTRA_PRIMVTX_TimeMargin;"
if [[ $ALIGNLEVEL == 1 ]]; then
  if [[ $BEAMTYPE == "pp" ]]; then
    export PVERTEXER+=";pvertexer.maxChi2TZDebris=40;pvertexer.maxChi2Mean=12;pvertexer.maxMultRatDebris=1.;pvertexer.addTimeSigma2Debris=1e-2;pvertexer.meanVertexExtraErrSelection=0.03;"
  elif [[ $BEAMTYPE == "PbPb" ]]; then
    export PVERTEXER+=";pvertexer.addTimeSigma2Debris=1e-2;pvertexer.meanVertexExtraErrSelection=0.03;pvertexer.maxITSOnlyFraction=0.85;pvertexer.maxTDiffDebris=1.5;pvertexer.maxZDiffDebris=0.3;pvertexer.addZSigma2Debris=0.09;pvertexer.addTimeSigma2Debris=2.25;pvertexer.maxChi2TZDebris=100;pvertexer.maxMultRatDebris=1.;pvertexer.maxTDiffDebrisExtra=-1.;pvertexer.dbscanDeltaT=-0.55;pvertexer.maxTMAD=1.;pvertexer.maxZMAD=0.04;"
    has_detector_reco FT0 && PVERTEX_CONFIG+=" --validate-with-ft0 "
  fi
fi


# secondary vertexing
if [[ $ALIEN_JDL_DISABLESTRTRACKING == 1 ]]; then
  export STRTRACKING=" --disable-strangeness-tracker "
fi
if [[ $ALIEN_JDL_DISABLECASCADES == 1 ]]; then
  export ARGS_EXTRA_PROCESS_o2_secondary_vertexing_workflow+=" --disable-cascade-finder  "
fi
# allow usage of TPC-only in svertexer (default: do use them, as in default in O2 and CCDB)
if [[ $ALIEN_JDL_DISABLETPCONLYFORV0S == 1 ]]; then
  export CONFIG_EXTRA_PROCESS_o2_secondary_vertexing_workflow+=";svertexer.mExcludeTPCtracks=true"
fi

export CONFIG_EXTRA_PROCESS_o2_primary_vertexing_workflow+=";$PVERTEXER;$VDRIFTPARAMOPTION;"

export CONFIG_EXTRA_PROCESS_o2_tpcits_match_workflow+=";$ITSEXTRAERR;$ITSTPCMATCH;$TRACKTUNETPC;$VDRIFTPARAMOPTION;"
[[ ! -z "${TPCITSTIMEBIAS}" ]] && export CONFIG_EXTRA_PROCESS_o2_tpcits_match_workflow+=";tpcitsMatch.globalTimeBiasMUS=$TPCITSTIMEBIAS;"
[[ ! -z "${TPCITSTIMEERR}" ]] && export CONFIG_EXTRA_PROCESS_o2_tpcits_match_workflow+=";tpcitsMatch.globalTimeExtraErrorMUS=$TPCITSTIMEERR;"

# enabling AfterBurner
has_detector FT0 && export ARGS_EXTRA_PROCESS_o2_tpcits_match_workflow="$ARGS_EXTRA_PROCESS_o2_tpcits_match_workflow --use-ft0"

# ad-hoc settings for TOF matching
export ARGS_EXTRA_PROCESS_o2_tof_matcher_workflow="$ARGS_EXTRA_PROCESS_o2_tof_matcher_workflow --output-type matching-info,calib-info --enable-dia"
export CONFIG_EXTRA_PROCESS_o2_tof_matcher_workflow+=";$ITSEXTRAERR;$TRACKTUNETPC;$VDRIFTPARAMOPTION;"

if [[ $ALIEN_JDL_LPMPASSNAME == "cpass0" ]]; then
   CONFIG_EXTRA_PROCESS_o2_tof_matcher_workflow+=";MatchTOF.nsigmaTimeCut=6;"
fi

# ad-hoc settings for TRD matching
export CONFIG_EXTRA_PROCESS_o2_trd_global_tracking+=";$ITSEXTRAERR;$TRACKTUNETPC;$VDRIFTPARAMOPTION;GPU_rec_trd.minTrackPt=0.3;"

# ad-hoc settings for FT0
export ARGS_EXTRA_PROCESS_o2_ft0_reco_workflow="$ARGS_EXTRA_PROCESS_o2_ft0_reco_workflow --ft0-reconstructor"
if [[ $BEAMTYPE == "PbPb" ]]; then
  export CONFIG_EXTRA_PROCESS_o2_ft0_reco_workflow=";FT0TimeFilterParam.mAmpLower=10;"
fi

# ad-hoc settings for FV0
export ARGS_EXTRA_PROCESS_o2_fv0_reco_workflow="$ARGS_EXTRA_PROCESS_o2_fv0_reco_workflow --fv0-reconstructor"

# ad-hoc settings for FDD
#...

# ad-hoc settings for MFT
if [[ $BEAMTYPE == "pp" || $PERIOD == "LHC22s" ]]; then
  export CONFIG_EXTRA_PROCESS_o2_mft_reco_workflow+=";MFTTracking.RBins=30;MFTTracking.PhiBins=120;MFTTracking.ZVtxMin=-13;MFTTracking.ZVtxMax=13;MFTTracking.MFTRadLength=0.084;$MAXBCDIFFTOMASKBIAS_MFT;$MAXBCDIFFTOSQUASHBIAS_MFT"
else
  export CONFIG_EXTRA_PROCESS_o2_mft_reco_workflow+=";MFTTracking.MFTRadLength=0.084;$MAXBCDIFFTOMASKBIAS_MFT;$MAXBCDIFFTOSQUASHBIAS_MFT"
fi

# ad-hoc settings for MCH
if [[ $BEAMTYPE == "pp" ]]; then
  export CONFIG_EXTRA_PROCESS_o2_mch_reco_workflow+=";MCHTracking.chamberResolutionX=0.4;MCHTracking.chamberResolutionY=0.4;MCHTracking.sigmaCutForTracking=7;MCHTracking.sigmaCutForImprovement=6"
fi

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
  export CALIB_TRD_T0=0
  export CALIB_TRD_GAIN=0
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
    export CONFIG_EXTRA_PROCESS_o2_tpc_scdcalib_interpolation_workflow="scdcalib.maxTracksPerCalibSlot=35000000;scdcalib.minPtNoOuterPoint=0.2;scdcalib.maxQ2Pt=5;scdcalib.minITSNClsNoOuterPoint=6;scdcalib.minITSNCls=4;scdcalib.minTPCNClsNoOuterPoint=90"
    export ARGS_EXTRA_PROCESS_o2_tpc_scdcalib_interpolation_workflow="$ARGS_EXTRA_PROCESS_o2_tpc_scdcalib_interpolation_workflow --tracking-sources ITS-TPC"
    # ad-hoc settings for TPC residual extraction
    export ARGS_EXTRA_PROCESS_o2_calibration_residual_aggregator="$ARGS_EXTRA_PROCESS_o2_calibration_residual_aggregator --output-type trackParams,unbinnedResid"
    if [[ $ALIEN_JDL_DEBUGRESIDUALEXTRACTION == "1" ]]; then
      export CONFIG_EXTRA_PROCESS_o2_tpc_scdcalib_interpolation_workflow+=";scdcalib.maxTracksPerCalibSlot=-1;scdcalib.minPtNoOuterPoint=0.8;scdcalib.minTPCNClsNoOuterPoint=120"
      export ARGS_EXTRA_PROCESS_o2_trd_global_tracking+="$ARGS_EXTRA_PROCESS_o2_trd_global_tracking --enable-qc"
    fi
  fi
  export CALIB_EMC_ASYNC_RECALIB="$ALIEN_JDL_DOEMCCALIB"
  if [[ $ALIEN_JDL_DOTRDVDRIFTEXBCALIB == "1" ]]; then
    export CALIB_TRD_VDRIFTEXB="$ALIEN_JDL_DOTRDVDRIFTEXBCALIB"
    export ARGS_EXTRA_PROCESS_o2_calibration_trd_workflow="$ARGS_EXTRA_PROCESS_o2_calibration_trd_workflow --enable-root-output"
    export ARGS_EXTRA_PROCESS_o2_trd_global_tracking="$ARGS_EXTRA_PROCESS_o2_trd_global_tracking --enable-qc"
  fi
  if [[ $ALIEN_JDL_DOMEANVTXCALIB == 1 ]]; then
    export CALIB_PRIMVTX_MEANVTX="$ALIEN_JDL_DOMEANVTXCALIB"
    export TFPERSLOTS_MEANVTX=550000 # 1 hour
    export DELAYINTFS_MEANVTX=55000  # 10 minutes
    export SVERTEXING_SOURCES=none # disable secondary vertexing
  fi
  if [[ $ALIEN_JDL_DOTRDGAINCALIB == 1 ]]; then
    export CONFIG_EXTRA_PROCESS_o2_calibration_trd_workflow="TRDCalibParams.minEntriesChamberGainCalib=999999999;TRDCalibParams.minEntriesTotalGainCalib=10000;TRDCalibParams.nTrackletsMinGainCalib=4"
    export ARGS_EXTRA_PROCESS_o2_calibration_trd_workflow="$ARGS_EXTRA_PROCESS_o2_calibration_trd_workflow --enable-root-output"
    export CALIB_TRD_GAIN=1
  fi
  if [[ $ALIEN_JDL_DOUPLOADSLOCALLY == 1 ]]; then
    export CCDB_POPULATOR_UPLOAD_PATH="file://$PWD"
  fi
fi

# extra workflows in case we want to process the currents for FT0, FV0, TOF, TPC
if [[ $ALIEN_JDL_EXTRACTCURRENTS == 1 ]]; then
  if [[ -z "${WORKFLOW_DETECTORS_RECO+x}" ]] || [[ "0$WORKFLOW_DETECTORS_RECO" == "0ALL" ]]; then export WORKFLOW_DETECTORS_RECO=$WORKFLOW_DETECTORS; fi
  has_detector_reco FT0 && add_comma_separated ADD_EXTRA_WORKFLOW "o2-ft0-integrate-cluster-workflow"
  has_detector_reco FV0 && add_comma_separated ADD_EXTRA_WORKFLOW "o2-fv0-integrate-cluster-workflow"
  has_detector_reco TOF && add_comma_separated ADD_EXTRA_WORKFLOW "o2-tof-integrate-cluster-workflow"
  if [[ $ALIEN_JDL_DISABLE3DCURRENTS != 1 ]]; then
    export ARGS_EXTRA_PROCESS_o2_tpc_integrate_cluster_workflow="$ARGS_EXTRA_PROCESS_o2_tpc_integrate_cluster_workflow--process-3D-currents --nSlicesTF 1"
  fi
  has_detector_reco TPC && add_comma_separated ADD_EXTRA_WORKFLOW "o2-tpc-integrate-cluster-workflow"
fi

# extra workflows in case we want to process the currents for time series
if [[ $ALIEN_JDL_EXTRACTTIMESERIES == 1 ]]; then
  if [[ -z "${WORKFLOW_DETECTORS_RECO+x}" ]] || [[ "0$WORKFLOW_DETECTORS_RECO" == "0ALL" ]]; then export WORKFLOW_DETECTORS_RECO=$WORKFLOW_DETECTORS; fi
  has_detector_reco TPC && has_detector_reco ITS && has_detector_reco FT0 && add_comma_separated ADD_EXTRA_WORKFLOW "o2-tpc-time-series-workflow"
  if [[ ! -z "$ALIEN_JDL_ENABLEUNBINNEDTIMESERIES" ]]; then
    export ARGS_EXTRA_PROCESS_o2_tpc_time_series_workflow="$ARGS_EXTRA_PROCESS_o2_tpc_time_series_workflow --enable-unbinned-root-output --sample-unbinned-tsallis --threads 1"
  fi
  if [[ $ON_SKIMMED_DATA == 1 ]] || [[ ! -z "$ALIEN_JDL_SAMPLINGFACTORTIMESERIES" ]] ; then
    if [[ $ON_SKIMMED_DATA == 1 ]] ; then
      SAMPLINGFACTORTIMESERIES=0.1f
    fi
    if [[ ! -z "$ALIEN_JDL_SAMPLINGFACTORTIMESERIES" ]]; then # this takes priority
      export SAMPLINGFACTORTIMESERIES=${ALIEN_JDL_SAMPLINGFACTORTIMESERIES}
    fi
    export ARGS_EXTRA_PROCESS_o2_tpc_time_series_workflow="$ARGS_EXTRA_PROCESS_o2_tpc_time_series_workflow --sampling-factor ${ALIEN_JDL_SAMPLINGFACTORTIMESERIES}"
  fi
fi

# Enabling AOD
if [[ $ALIEN_JDL_AODOFF != "1" ]]; then
  export WORKFLOW_PARAMETERS="AOD,${WORKFLOW_PARAMETERS}"
fi

# ad-hoc settings for AOD
echo ALIEN_JDL_LPMPRODUCTIONTAG = $ALIEN_JDL_LPMPRODUCTIONTAG
echo ALIEN_JDL_LPMPASSNAME = $ALIEN_JDL_LPMPASSNAME
export ARGS_EXTRA_PROCESS_o2_aod_producer_workflow="$ARGS_EXTRA_PROCESS_o2_aod_producer_workflow --aod-writer-maxfilesize $AOD_FILE_SIZE --lpmp-prod-tag $ALIEN_JDL_LPMPRODUCTIONTAG --reco-pass $ALIEN_JDL_LPMPASSNAME"
if [[ $PERIOD == "LHC22c" ]] || [[ $PERIOD == "LHC22d" ]] || [[ $PERIOD == "LHC22e" ]] || [[ $PERIOD == "JUN" ]] || [[ $PERIOD == "LHC22f" ]] || [[ $PERIOD == "LHC22m" ]] || [[ "$RUNNUMBER" == @(526463|526465|526466|526467|526468|526486|526505|526508|526510|526512|526525|526526|526528|526534|526559|526596|526606|526612|526638|526639|526641|526643|526647|526649|526689|526712|526713|526714|526715|526716|526719|526720|526776|526886|526926|526927|526928|526929|526934|526935|526937|526938|526963|526964|526966|526967|526968|527015|527016|527028|527031|527033|527034|527038|527039|527041|527057|527076|527108|527109|527228|527237|527259|527260|527261|527262|527345|527347|527349|527446|527518|527523|527734) ]] ; then
  export ARGS_EXTRA_PROCESS_o2_aod_producer_workflow="$ARGS_EXTRA_PROCESS_o2_aod_producer_workflow --ctpreadout-create 1"
fi

# Enabling QC
if [[ $ALIEN_JDL_QCOFF != "1" ]]; then
  export WORKFLOW_PARAMETERS="QC,${WORKFLOW_PARAMETERS}"
fi
export QC_CONFIG_PARAM="--local-batch=QC.root --override-values \"qc.config.Activity.number=$RUNNUMBER;qc.config.Activity.passName=$PASS;qc.config.Activity.periodName=$PERIOD\""
export GEN_TOPO_WORKDIR="./"
#export QC_JSON_FROM_OUTSIDE="QC-20211214.json"

if [[ -n $ALIEN_JDL_QCJSONFROMOUTSIDE ]]; then
  QC_JSON_FROM_OUTSIDE=$ALIEN_JDL_QCJSONFROMOUTSIDE
fi
if [[ ! -z $QC_JSON_FROM_OUTSIDE ]]; then
    sed -i 's/REPLACE_ME_RUNNUMBER/'"${RUNNUMBER}"'/g' $QC_JSON_FROM_OUTSIDE
    sed -i 's/REPLACE_ME_PASS/'"${PASS}"'/g' $QC_JSON_FROM_OUTSIDE
    sed -i 's/REPLACE_ME_PERIOD/'"${PERIOD}"'/g' $QC_JSON_FROM_OUTSIDE
fi
