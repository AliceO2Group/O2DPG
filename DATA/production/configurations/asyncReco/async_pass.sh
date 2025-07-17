#!/bin/bash

# Script to run the async processing
#
# if run locally, you need to export e.g.:
#
# export ALIEN_JDL_LPMRUNNUMBER=505673
# export ALIEN_JDL_LPMINTERACTIONTYPE=pp
# export ALIEN_JDL_LPMPRODUCTIONTAG=OCT
# export ALIEN_JDL_LPMPASSNAME=apass4
# export ALIEN_JDL_LPMANCHORYEAR=2021

# function to run AOD merging
run_AOD_merging() {
  cd $1
  if [[ -f "AO2D.root" ]]; then
    ls "AO2D.root" > list_$1.list
    echo "Checking AO2Ds with un-merged DFs in $1"
    timeStartCheck=`date +%s`
    time root -l -b -q $O2DPG_ROOT/DATA/production/common/readAO2Ds.C > checkAO2D.log
    exitcode=$?
    timeEndCheck=`date +%s`
    timeUsedCheck=$(( $timeEndCheck-$timeStartCheck ))
    echo "Time spent to check unmerged AODs in dir $1 = $timeUsedCheck s"
    if [[ $exitcode -ne 0 ]]; then
      echo "exit code from AO2D check is " $exitcode > validation_error.message
      echo "exit code from AO2D check is " $exitcode
      echo "This means that the check for unmerged AODs in $1 FAILED, we'll make the whole processing FAIL"
      return $exitcode
    fi
    if [[ -z $ALIEN_JDL_DONOTMERGEAODS ]] || [[ $ALIEN_JDL_DONOTMERGEAODS == 0 ]]; then
      echo "Merging AOD from the list list_$1.list"
      o2-aod-merger --input list_$1.list --verbosity 1 --output AO2D_merged.root > merging.log
      exitcode=$?
      if [[ $exitcode -ne 0 ]]; then
	echo "Exit code from the process merging DFs inside AO2D for $1 is " $exitcode > validation_error.message
	echo "Exit code from the process merging DFs inside AO2D for $1 is " $exitcode
	echo "This means that the merging of DFs for $1 FAILED, we'll make the whole processing FAIL"
	return $exitcode
      fi
      # now checking merged AODs
      echo "Checking AO2Ds with merged DFs in $AOD_DIR"
      timeStartCheckMergedAOD=`date +%s`
      time root -l -b -q '$O2DPG_ROOT/DATA/production/common/readAO2Ds.C("AO2D_merged.root")' > checkAO2D_merged.log
      exitcode=$?
      timeEndCheckMergedAOD=`date +%s`
      timeUsedCheckMergedAOD=$(( $timeEndCheckMergedAOD-$timeStartCheckMergedAOD ))
      echo "Time spent to check unmerged AODs in dir $1 = $timeUsedCheckMergedAOD s"
      if [[ $exitcode -ne 0 ]]; then
	echo "exit code from AO2D in $1 with merged DFs check is " $exitcode > validation_error.message
	echo "exit code from AO2D in $1 with merged DFs check is " $exitcode
	echo "This means that the check for merged AODs in $1 FAILED, we'll make the whole processing FAIL"
      else
	echo "All ok, replacing initial AO2D.root file in $1 with the one with merged DFs"
	mv AO2D_merged.root AO2D.root
      fi
      cd ..
    fi
  fi
  return $exitcode
}

timeStartFullProcessing=`date +%s`

# to skip positional arg parsing before the randomizing part.
export inputarg="${1}"

if [[ "${1##*.}" == "root" ]]; then
  #echo ${1##*.}
  #echo "alien://${1}" > list.list
  #export MODE="remote"
  echo "${1}" > list.list
  if [[ ! -z $ASYNC_BENCHMARK_ITERATIONS ]]; then
    for i in `seq 1 $ASYNC_BENCHMARK_ITERATIONS`; do echo "${1}" >> list.list; done
  fi
  export MODE="LOCAL"
  shift
elif [[ "${1##*.}" == "xml" ]]; then
  if [[ $ALIEN_JDL_DOWNLOADINPUTFILES == "1" ]]; then
    echo "Downloading input files done by the job agent"
    sed -rn 's/.*file\ name="(o2_ctf[^"]*)".*/\1/p' $1 > list.list
  else
    sed -rn 's/.*turl="([^"]*)".*/\1/p' $1 > list.list
  fi
  export MODE="remote"
  shift
elif [[ $1 != "list.list" && "${1##*.}" == "list" ]]; then
  cp $1 list.list
  export MODE="remote"
  shift
fi

# Could need sometimes to iterate just a subset of the input files
#
[ -z ${ALIEN_JDL_INPUTFILELIMIT} ] && ALIEN_JDL_INPUTFILELIMIT=($(cat list.list|wc -l))
head -${ALIEN_JDL_INPUTFILELIMIT} list.list > list.listtmp && mv list.listtmp list.list
echo "Will iterate ${ALIEN_JDL_INPUTFILELIMIT} input files"

if [[ -f list.list ]]; then
  echo "Processing will be on the following list of files:"
  cat list.list
  echo -e "\n"
fi

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -rnb|--run-number)
      RUNNUMBER="$2"
      shift
      shift
      ;;
    -b|--beam-type)
      BEAMTYPE="$2"
      shift
      shift
      ;;
    -m|--mode)
      MODE="$2"
      shift
      shift
      ;;
    -p|--period)
      PERIOD="$2"
      shift
      shift
      ;;
    -pa|--pass)
      PASS="$2"
      shift
      shift
      ;;
    *)
    POSITIONAL+=("$1")
    shift
    ;;
  esac
done

# now we overwrite if we found them in the jdl
if [[ -n "$ALIEN_JDL_LPMRUNNUMBER" ]]; then
    export RUNNUMBER="$ALIEN_JDL_LPMRUNNUMBER"
fi

# beam type
if [[ -n "$ALIEN_JDL_LPMINTERACTIONTYPE" ]]; then
    export BEAMTYPE="$ALIEN_JDL_LPMINTERACTIONTYPE"
fi

# period
if [[ -n "$ALIEN_JDL_LPMPRODUCTIONTAG" ]]; then
    export PERIOD="$ALIEN_JDL_LPMPRODUCTIONTAG"
fi

# pass
if [[ -n "$ALIEN_JDL_LPMPASSNAME" ]]; then
  export PASS="$ALIEN_JDL_LPMPASSNAME"
fi

if [[ -z $RUNNUMBER ]] || [[ -z $PERIOD ]] || [[ -z $BEAMTYPE ]] || [[ -z $PASS ]]; then
    echo "check env variables we need RUNNUMBER (--> $RUNNUMBER), PERIOD (--> $PERIOD), PASS (--> $PASS), BEAMTYPE (--> $BEAMTYPE)"
    exit 3
fi

echo processing run $RUNNUMBER, from period $PERIOD with $BEAMTYPE collisions and mode $MODE

export timeUsed=0

###if [[ $MODE == "remote" ]]; then
    # run specific archive
    if [[ ! -f runInput_$RUNNUMBER.tgz ]]; then
        echo "No runInput_$RUNNUMBER.tgz, let's hope we don't need it"
    else
      tar -xzvf runInput_$RUNNUMBER.tgz
    fi
###fi

##############################
# calibrations
export ADD_CALIB=0

if [[ -n "$ALIEN_JDL_DOEMCCALIB" ]]; then
  export ADD_CALIB=1
fi

if [[ -n "$ALIEN_JDL_DOTPCRESIDUALEXTRACTION" ]]; then
  export DO_TPC_RESIDUAL_EXTRACTION="$ALIEN_JDL_DOTPCRESIDUALEXTRACTION"
  export ADD_CALIB=1
fi

if [[ -n "$ALIEN_JDL_DOTRDVDRIFTEXBCALIB" ]]; then
  export ADD_CALIB=1
fi

if [[ -n "$ALIEN_JDL_DOMEANVTXCALIB" ]]; then
  export ADD_CALIB=1
fi

if [[ "$ALIEN_JDL_EXTRACTCURRENTS" == "1" ]]; then
  export ADD_CALIB=1
fi

if [[ "$ALIEN_JDL_EXTRACTTIMESERIES" == "1" ]]; then
  export ADD_CALIB=1
fi

# AOD file size
if [[ -n "$ALIEN_JDL_AODFILESIZE" ]]; then
  export AOD_FILE_SIZE="$ALIEN_JDL_AODFILESIZE"
else
  export AOD_FILE_SIZE=8000
fi
if [[ $ADD_CALIB == 1 ]]; then
  if [[ -z $CALIB_WORKFLOW_FROM_OUTSIDE ]]; then
    echo "Use calib-workflow.sh from O2"
    cp $O2_ROOT/prodtests/full-system-test/calib-workflow.sh .
  else
    echo "Use calib-workflow.sh passed as input"
    cp $CALIB_WORKFLOW_FROM_OUTSIDE .
  fi
  if [[ -z $AGGREGATOR_WORKFLOW_FROM_OUTSIDE ]]; then
    echo "Use aggregator-workflow.sh from O2"
    cp $O2_ROOT/prodtests/full-system-test/aggregator-workflow.sh .
  else
    echo "Use aggregator-workflow.sh passed as input"
    cp $AGGREGATOR_WORKFLOW_FROM_OUTSIDE .
  fi
fi
##############################

echo "Checking current directory content"
ls -altr

ln -s $O2DPG_ROOT/DATA/common/gen_topo_helper_functions.sh
source gen_topo_helper_functions.sh || { echo "gen_topo_helper_functions.sh failed" && exit 5; }

if [[ -f "setenv_extra.sh" ]]; then
  echo "Time used so far, before setenv_extra = $timeUsed s"
  time source setenv_extra.sh $RUNNUMBER $BEAMTYPE || { echo "setenv_extra.sh (local file) failed" && exit 6; }
  echo "Time used so far, after setenv_extra = $timeUsed s"
else
  echo "************************************************************************************"
  echo "No ad-hoc setenv_extra settings for current async processing; using the one in O2DPG"
  echo "************************************************************************************"
  if [[ -f $O2DPG_ROOT/DATA/production/configurations/asyncReco/setenv_extra.sh ]]; then
    ln -s $O2DPG_ROOT/DATA/production/configurations/asyncReco/setenv_extra.sh
    echo "Time used so far, before setenv_extra = $timeUsed s"
    time source setenv_extra.sh $RUNNUMBER $BEAMTYPE || { echo "setenv_extra.sh (O2DPG) failed" && exit 7; }
    echo "Time used so far, after setenv_extra = $timeUsed s"
  else
    echo "*********************************************************************************************************"
    echo "No setenev_extra from $O2DPG_ROOT/DATA/production/configurations/asyncReco/ in O2DPG"
    echo "                No special settings will be used"
    echo "*********************************************************************************************************"
  fi
fi

if [[ -f run-workflow-on-inputlist.sh ]]; then
  echo "Use run-workflow-on-inputlist.sh macro passed as input"
else
  echo "Use run-workflow-on-inputlist.sh macro from O2"
  cp $O2_ROOT/prodtests/full-system-test/run-workflow-on-inputlist.sh .
fi

if [[ -f dpl-workflow.sh ]]; then
  echo "Use dpl-workflow.sh passed as input"
elif [[ -z $ALIEN_JDL_DPLWORKFLOWFROMOUTSIDE ]]; then
  echo "Use dpl-workflow.sh from O2"
  cp $O2_ROOT/prodtests/full-system-test/dpl-workflow.sh .
else
  echo "Use dpl-workflow.sh passed as input"
  cp $ALIEN_JDL_DPLWORKFLOWFROMOUTSIDE .
fi

if [[ ! -z $QC_JSON_FROM_OUTSIDE ]]; then
  echo "QC json from outside is $QC_JSON_FROM_OUTSIDE"
fi

ln -sf $O2DPG_ROOT/DATA/common/setenv.sh
ln -sf $O2DPG_ROOT/DATA/common/getCommonArgs.sh

# TFDELAY and throttling
export TFDELAYSECONDS=40
if [[ -n "$ALIEN_JDL_TFDELAYSECONDS" ]]; then
  TFDELAYSECONDS="$ALIEN_JDL_TFDELAYSECONDS"
# ...otherwise, it depends on whether we have throttling
elif [[ -n "$ALIEN_JDL_USETHROTTLING" ]]; then
  TFDELAYSECONDS=1
  if [[ -n "$ALIEN_JDL_NOTFDELAY" ]]; then
    TFDELAYSECONDS=0
  fi
  export TIMEFRAME_RATE_LIMIT=1
fi

if [[ ! -z "$ALIEN_JDL_SHMSIZE" ]]; then export SHMSIZE=$ALIEN_JDL_SHMSIZE; elif [[ -z "$SHMSIZE" ]]; then export SHMSIZE=$(( 16 << 30 )); fi
if [[ ! -z "$ALIEN_JDL_DDSHMSIZE" ]]; then export DDSHMSIZE=$ALIEN_JDL_DDSHMSIZE; elif [[ -z "$DDSHMSIZE" ]]; then export DDSHMSIZE=$(( 32 << 10 )); fi

# root output enabled only for some fraction of the cases
# keeping AO2D.root QC.root o2calib_tof.root mchtracks.root mchclusters.root

SETTING_ROOT_OUTPUT="ENABLE_ROOT_OUTPUT_o2_mch_reco_workflow= ENABLE_ROOT_OUTPUT_o2_muon_tracks_matcher_workflow= ENABLE_ROOT_OUTPUT_o2_aod_producer_workflow= ENABLE_ROOT_OUTPUT_o2_qc= "

if ([[ -n $ALIEN_JDL_LPMCPASSMODE ]] && [[ $ALIEN_JDL_LPMCPASSMODE != "-1" ]]) || [[ $ALIEN_JDL_KEEPTOFMATCHOUTPUT == "1" ]]; then
  SETTING_ROOT_OUTPUT+="ENABLE_ROOT_OUTPUT_o2_tof_matcher_workflow= "
fi
if [[ $ALIEN_JDL_DOEMCCALIB == "1" ]]; then
  SETTING_ROOT_OUTPUT+="ENABLE_ROOT_OUTPUT_o2_emcal_emc_offline_calib_workflow= "
fi
if [[ $DO_TPC_RESIDUAL_EXTRACTION == "1" ]]; then
  SETTING_ROOT_OUTPUT+="ENABLE_ROOT_OUTPUT_o2_calibration_residual_aggregator= "
fi
if [[ $ALIEN_JDL_DOTRDVDRIFTEXBCALIB == "1" ]]; then
  SETTING_ROOT_OUTPUT+="ENABLE_ROOT_OUTPUT_o2_trd_global_tracking= "
  SETTING_ROOT_OUTPUT+="ENABLE_ROOT_OUTPUT_o2_calibration_trd_workflow= "
fi
if [[ $ALIEN_JDL_DOMEANVTXCALIB == "1" ]]; then
  SETTING_ROOT_OUTPUT+="ENABLE_ROOT_OUTPUT_o2_primary_vertexing_workflow= "
  SETTING_ROOT_OUTPUT+="ENABLE_ROOT_OUTPUT_o2_tfidinfo_writer_workflow= "
fi

# to add extra output to always keep
if [[ -n "$ALIEN_JDL_EXTRAENABLEROOTOUTPUT" ]]; then
  OLD_IFS=$IFS
  IFS=','
  for token in $ALIEN_JDL_EXTRAENABLEROOTOUTPUT; do
    SETTING_ROOT_OUTPUT+=" ENABLE_ROOT_OUTPUT_$token="
  done
  IFS=$OLD_IFS
fi

# to define which extra output to always keep
if [[ -n "$ALIEN_JDL_ENABLEROOTOUTPUT" ]]; then
  OLD_IFS=$IFS
  IFS=','
  SETTING_ROOT_OUTPUT=
  for token in $ALIEN_JDL_ENABLEROOTOUTPUT; do
    SETTING_ROOT_OUTPUT+=" ENABLE_ROOT_OUTPUT_$token="
  done
  IFS=$OLD_IFS
fi

keep=0

if [[ -n $ALIEN_JDL_INPUTTYPE ]] && [[ "$ALIEN_JDL_INPUTTYPE" == "TFs" ]]; then
  export WORKFLOW_PARAMETERS=CTF
  INPUT_TYPE=TF
  if [[ $RUNNUMBER -lt 523141 ]]; then
    export TPC_CONVERT_LINKZS_TO_RAW=1
  fi
else
  INPUT_TYPE=CTF
fi

# enabling time reporting
if [[ -n $ALIEN_JDL_DPLREPORTPROCESSING ]]; then
  export DPL_REPORT_PROCESSING=$ALIEN_JDL_DPLREPORTPROCESSING
fi

# defining whether to keep files
if [[ -n $ALIEN_JDL_PACKAGES ]]; then # if we have this env variable, it means that we are running on the grid
  # JDL can set the permille to keep; otherwise we use 2
  if [[ ! -z "$ALIEN_JDL_NKEEP" ]]; then export NKEEP=$ALIEN_JDL_NKEEP; else NKEEP=2; fi

  KEEPRATIO=0
  (( $NKEEP > 0 )) && KEEPRATIO=$((1000/NKEEP))
  echo "Set to save ${NKEEP} permil intermediate output"

  if [[ -f wn.xml ]]; then
    grep alien:// wn.xml | tr ' ' '\n' | grep ^lfn | cut -d\" -f2 > tmp.tmp
  else
    echo "${inputarg}" > tmp.tmp
  fi
  while read -r INPUT_FILE && (( $KEEPRATIO > 0 )); do
    SUBJOBIDX=$(grep -B1 $INPUT_FILE CTFs.xml | head -n1 | cut -d\" -f2)
    echo "INPUT_FILE                              : $INPUT_FILE"
    echo "Index of INPUT_FILE in collection       : $SUBJOBIDX"
    echo "Number of subjobs for current masterjob : $ALIEN_JDL_SUBJOBCOUNT"
    # if we don't have enough subjobs, we anyway keep the first
    if [[ "$ALIEN_JDL_SUBJOBCOUNT" -le "$KEEPRATIO" && "$SUBJOBIDX" -eq 1 ]]; then
      echo -e "**** NOT ENOUGH SUBJOBS TO SAMPLE, WE WILL FORCE TO KEEP THE OUTPUT ****"
      keep=1
      break
    else
      if [[ "$((SUBJOBIDX%KEEPRATIO))" -eq "0" ]]; then
        keep=1
        break
      fi
    fi
  done < tmp.tmp
  if [[ $keep -eq 1 ]]; then
    echo "Intermediate files WILL BE KEPT";
  else
    echo "Intermediate files WILL BE KEPT ONLY FOR SOME WORKFLOWS";
  fi
else
  # in LOCAL mode, by default we keep all intermediate files
  echo -e "\n\n**** RUNNING IN LOCAL MODE ****"
  if [[ "$DO_NOT_KEEP_OUTPUT_IN_LOCAL" -eq 1 ]]; then
    echo -e "**** DO_NOT_KEEP_OUTPUT_IN_LOCAL ENABLED, NOT SETTING keep=0, NOT ENFORCING FULL ROOT OUTPUT ****\n\n"
    keep=0;
  else
    echo -e "**** WE KEEP ALL ROOT OUTPUT ****";
    echo -e "**** IF YOU WANT TO REMOVE ROOT OUTPUT FILES FOR PERFORMANCE STUDIES OR SIMILAR, PLEASE SET THE ENV VAR DO_NOT_KEEP_OUTPUT_IN_LOCAL ****\n\n"
    keep=1
  fi
fi

if [[ $keep -eq 1 ]]; then
  SETTING_ROOT_OUTPUT+="DISABLE_ROOT_OUTPUT=0";
fi
echo "SETTING_ROOT_OUTPUT = $SETTING_ROOT_OUTPUT"

# Enabling GPUs
if [[ $ASYNC_PASS_NO_OPTIMIZED_DEFAULTS != 1 ]]; then
  export OPTIMIZED_PARALLEL_ASYNC_AUTO_SHM_LIMIT=1
  if [[ $ALIEN_JDL_USEGPUS == 1 ]] ; then
    echo "Enabling GPUS"
    if [[ -z $ALIEN_JDL_SITEARCH ]]; then echo "ERROR: Must set ALIEN_JDL_SITEARCH to define GPU architecture!"; exit 1; fi
    if [[ $ALIEN_JDL_SITEARCH == "NERSC" ]]; then # Disable mlock / ulimit / gpu memory registration - has performance impact, but doesn't work at NERSC for now
      export SETENV_NO_ULIMIT=1
      export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow+="GPU_proc.noGPUMemoryRegistration=1;"
    fi
    ALIEN_JDL_SITEARCH_TMP=$ALIEN_JDL_SITEARCH
    if [[ $ALIEN_JDL_SITEARCH == "EPN_MI100" ]]; then
      ALIEN_JDL_SITEARCH_TMP=EPN
      export EPN_NODE_MI100=1
    elif [[ $ALIEN_JDL_SITEARCH == "EPN_MI50" ]]; then
      ALIEN_JDL_SITEARCH_TMP=EPN
    fi
    if [[ "ALIEN_JDL_USEFULLNUMADOMAIN" == 0 ]]; then
      if [[ $keep -eq 0 ]]; then
        if [[ $ALIEN_JDL_UNOPTIMIZEDGPUSETTINGS != 1 ]]; then
          export OPTIMIZED_PARALLEL_ASYNC=pp_1gpu_${ALIEN_JDL_SITEARCH_TMP} # (16 cores, 1 gpu per job, pp)
        else
          export OPTIMIZED_PARALLEL_ASYNC=pp_1gpu_${ALIEN_JDL_SITEARCH_TMP}_unoptimized # (16 cores, 1 gpu per job, pp, low CPU multiplicities)
        fi
      else
        export OPTIMIZED_PARALLEL_ASYNC=keep_root
      fi
    else
      if [[ $BEAMTYPE == "pp" ]]; then
        export OPTIMIZED_PARALLEL_ASYNC=pp_4gpu_${ALIEN_JDL_SITEARCH_TMP} # (64 cores, 1 NUMA, 4 gpu per job, pp)
      else  # PbPb
        export OPTIMIZED_PARALLEL_ASYNC=PbPb_4gpu_${ALIEN_JDL_SITEARCH_TMP} # (64 cores, 1 NUMA 4 gpu per job, PbPb)
      fi
    fi
  else
    export SETENV_NO_ULIMIT=1
    export DPL_DEFAULT_PIPELINE_LENGTH=16 # to avoid memory issues - affects performance, so don't do with GPUs
    if [[ $ALIEN_JDL_EPNFULLNUMACPUONLY != 1 ]]; then
      export OPTIMIZED_PARALLEL_ASYNC=8cpu # (8 cores per job, grid)
    else
      export OPTIMIZED_PARALLEL_ASYNC=pp_64cpu # (64 cores per job, 1 NUMA, EPN)
    fi
  fi
fi

echo "[INFO (async_pass.sh)] envvars were set to TFDELAYSECONDS ${TFDELAYSECONDS} TIMEFRAME_RATE_LIMIT ${TIMEFRAME_RATE_LIMIT} OPTIMIZED_PARALLEL_ASYNC ${OPTIMIZED_PARALLEL_ASYNC:-NONE}"

[[ -z $NTIMEFRAMES ]] && export NTIMEFRAMES=-1

# let's set O2JOBID and SHMEMID
O2JOBIDscript="$O2DPG_ROOT/DATA/production/common/setVarsFromALIEN_PROC_ID.sh"
if [[ -f "setVarsFromALIEN_PROC_ID.sh" ]]; then
  O2JOBIDscript="setVarsFromALIEN_PROC_ID.sh"
fi
source $O2JOBIDscript

STATSCRIPT="$O2DPG_ROOT/DATA/production/common/getStat.sh"
if [[ -f "getStat.sh" ]]; then
  STATSCRIPT="getStat.sh"
fi

# exclude some detectors QC
WORKFLOW_DETECTORS_EXCLUDE_QC_SCRIPT=${ALIEN_JDL_WORKFLOWDETECTORSEXCLUDEQC:-}

# reco and matching
# print workflow
if [[ $ALIEN_JDL_SSPLITWF != "1" ]]; then
  env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=print TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS_EXCLUDE_QC=$WORKFLOW_DETECTORS_EXCLUDE_QC_SCRIPT ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list > workflowconfig.log
  # run it
  if [[ "0$RUN_WORKFLOW" != "00" ]]; then
    timeStart=`date +%s`
    time env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=run TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS_EXCLUDE_QC=$WORKFLOW_DETECTORS_EXCLUDE_QC_SCRIPT ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list
    exitcode=$?
    timeEnd=`date +%s`
    timeUsed=$(( $timeUsed+$timeEnd-$timeStart ))
    delta=$(( $timeEnd-$timeStart ))
    echo "Time spent in running the workflow = $delta s"
    echo "exitcode = $exitcode"
    if [[ $exitcode -ne 0 ]]; then
      echo "exit code from processing is " $exitcode > validation_error.message
      echo "exit code from processing is " $exitcode
      exit $exitcode
    fi
    mv latest.log latest_reco_1.log
    $STATSCRIPT latest_reco_1.log
    exitcode=$?
    echo "exit code is $exitcode"
    if [[ $exitcode -ne 0 ]]; then
      echo "exit code from processing is " $exitcode > validation_error.message
      echo "exit code from processing is " $exitcode
      exit $exitcode
    fi
  fi
else
  # running the wf in split mode
  echo "We will run the workflow in SPLIT mode!"
  echo "ALIEN_JDL_STARTSPLITSTEP = $ALIEN_JDL_STARTSPLITSTEP"
  echo "ALIEN_JDL_SSPLITSTEP = $ALIEN_JDL_SSPLITSTEP"
  WORKFLOW_PARAMETERS_START=$WORKFLOW_PARAMETERS

  if ([[ -z "$ALIEN_JDL_STARTSPLITSTEP" ]] && [[ -z "$ALIEN_JDL_SSPLITSTEP" ]]) || [[ "$ALIEN_JDL_SSPLITSTEP" -eq 1 ]] || ( [[ -n $ALIEN_JDL_STARTSPLITSTEP ]] && [[ "$ALIEN_JDL_STARTSPLITSTEP" -le 1 ]]) || [[ "$ALIEN_JDL_SSPLITSTEP" == "all" ]]; then
    # 1. TPC decoding + reco
    echo "Step 1) Decoding and reconstructing TPC+CTP"
    echo "Step 1) Decoding and reconstructing TPC+CTP" > workflowconfig.log
    for i in AOD QC CALIB CALIB_LOCAL_INTEGRATED_AGGREGATOR; do
      export WORKFLOW_PARAMETERS=$(echo $WORKFLOW_PARAMETERS | sed -e "s/,$i,/,/g" -e "s/^$i,//" -e "s/,$i"'$'"//" -e "s/^$i"'$'"//")
    done
    env DISABLE_ROOT_OUTPUT=0 IS_SIMULATED_DATA=0 WORKFLOWMODE=print TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS=TPC,CTP WORKFLOW_DETECTORS_MATCHING= ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list >> workflowconfig.log
    # run it
    if [[ "0$RUN_WORKFLOW" != "00" ]]; then
      timeStart=`date +%s`
      time env DISABLE_ROOT_OUTPUT=0 IS_SIMULATED_DATA=0 WORKFLOWMODE=run TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS=TPC,CTP WORKFLOW_DETECTORS_MATCHING= ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list
      exitcode=$?
      timeEnd=`date +%s`
      timeUsed=$(( $timeUsed+$timeEnd-$timeStart ))
      delta=$(( $timeEnd-$timeStart ))
      echo "Time spent in running the workflow, Step 1 = $delta s"
      echo "exitcode = $exitcode"
      if [[ $exitcode -ne 0 ]]; then
        echo "exit code from Step 1 of processing is " $exitcode > validation_error.message
        echo "exit code from Step 1 of processing is " $exitcode
        exit $exitcode
      fi
      mv latest.log latest_reco_1.log
      if [[ -f performanceMetrics.json ]]; then
        mv performanceMetrics.json performanceMetrics_1.json
      fi
      $STATSCRIPT latest_reco_1.log reco_1
      exitcode=$?
      if [[ $exitcode -ne 0 ]]; then
        echo "exit code from processing is " $exitcode > validation_error.message
        echo "exit code from processing is " $exitcode
        exit $exitcode
      fi
    fi
  fi

  if ([[ -z "$ALIEN_JDL_STARTSPLITSTEP" ]] && [[ -z "$ALIEN_JDL_SSPLITSTEP" ]]) || [[ "$ALIEN_JDL_SSPLITSTEP" -eq 2 ]] || ( [[ -n $ALIEN_JDL_STARTSPLITSTEP ]] && [[ "$ALIEN_JDL_STARTSPLITSTEP" -le 2 ]]) || [[ "$ALIEN_JDL_SSPLITSTEP" == "all" ]]; then
    # 2. the other detectors decoding + reco
    WORKFLOW_PARAMETERS=$WORKFLOW_PARAMETERS_START
    echo "Step 2) Decoding and reconstructing ALL-TPC"
    echo -e "\nStep 2) Decoding and reconstructing ALL-TPC" >> workflowconfig.log
    for i in AOD QC CALIB CALIB_LOCAL_INTEGRATED_AGGREGATOR; do
      export WORKFLOW_PARAMETERS=$(echo $WORKFLOW_PARAMETERS | sed -e "s/,$i,/,/g" -e "s/^$i,//" -e "s/,$i"'$'"//" -e "s/^$i"'$'"//")
    done
    env DISABLE_ROOT_OUTPUT=0 IS_SIMULATED_DATA=0 WORKFLOWMODE=print TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS=ALL WORKFLOW_DETECTORS_EXCLUDE=TPC,$DETECTORS_EXCLUDE WORKFLOW_DETECTORS_MATCHING= ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list >> workflowconfig.log
    # run it
    if [[ "0$RUN_WORKFLOW" != "00" ]]; then
      timeStart=`date +%s`
      time env DISABLE_ROOT_OUTPUT=0 IS_SIMULATED_DATA=0 WORKFLOWMODE=run TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS=ALL WORKFLOW_DETECTORS_EXCLUDE=TPC,$DETECTORS_EXCLUDE WORKFLOW_DETECTORS_MATCHING= ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list
      exitcode=$?
      timeEnd=`date +%s`
      timeUsed=$(( $timeUsed+$timeEnd-$timeStart ))
      delta=$(( $timeEnd-$timeStart ))
      echo "Time spent in running the workflow, Step 2 = $delta s"
      echo "exitcode = $exitcode"
      if [[ $exitcode -ne 0 ]]; then
        echo "exit code from Step 2 of processing is " $exitcode > validation_error.message
        echo "exit code from Step 2 of processing is " $exitcode
        exit $exitcode
      fi
      mv latest.log latest_reco_2.log
      if [[ -f performanceMetrics.json ]]; then
        mv performanceMetrics.json performanceMetrics_2.json
      fi
      $STATSCRIPT latest_reco_2.log reco_2
      exitcode=$?
      if [[ $exitcode -ne 0 ]]; then
        echo "exit code from processing is " $exitcode > validation_error.message
        echo "exit code from processing is " $exitcode
        exit $exitcode
      fi
      # let's compare to previous step
      if [[ -f latest_reco_1.log ]]; then
        nCTFsFilesInspected_step1=`ls [0-9]*_[0-9]*_[0-9]*_[0-9]*_[0-9]*_reco_1.stat | sed 's/\(^[0-9]*\)_.*/\1/'`
        nCTFsFilesOK_step1=`ls [0-9]*_[0-9]*_[0-9]*_[0-9]*_[0-9]*_reco_1.stat | sed 's/^[0-9]*_\([0-9]*\)_.*/\1/'`
        nCTFsFilesFailed_step1=`ls [0-9]*_[0-9]*_[0-9]*_[0-9]*_[0-9]*_reco_1.stat | sed 's/^[0-9]*_[0-9]*_\([0-9]*\)_.*/\1/'`
        nCTFsProcessed_step1=`ls [0-9]*_[0-9]*_[0-9]*_[0-9]*_[0-9]*_reco_1.stat | sed 's/^[0-9]*_[0-9]*_[0-9]*_\([0-9]*\).*/\1/'`
        nCTFsFilesInspected_step2=`ls [0-9]*_[0-9]*_[0-9]*_[0-9]*_[0-9]*_reco_2.stat | sed 's/\(^[0-9]*\)_.*/\1/'`
        nCTFsFilesOK_step2=`ls [0-9]*_[0-9]*_[0-9]*_[0-9]*_[0-9]*_reco_1.stat | sed 's/^[0-9]*_\([0-9]*\)_.*/\1/'`
        nCTFsFilesFailed_step2=`ls [0-9]*_[0-9]*_[0-9]*_[0-9]*_[0-9]*_reco_2.stat | sed 's/^[0-9]*_[0-9]*_\([0-9]*\)_.*/\1/'`
        nCTFsProcessed_step2=`ls [0-9]*_[0-9]*_[0-9]*_[0-9]*_[0-9]*_reco_2.stat | sed 's/^[0-9]*_[0-9]*_[0-9]*_\([0-9]*\).*/\1/'`
        if [[ $nCTFsFilesInspected_step1 != $nCTFsFilesInspected_step2 ]] || [[ $nCTFsFilesFailed_step1 != $nCTFsFilesFailed_step2 ]] || [[ $nCTFsFilesOK_step1 != $nCTFsFilesOK_step2 ]] || [[ $nCTFsProcessed_step1 != $nCTFsProcessed_step2 ]]; then
          echo "Inconsistency between step 1 and step 2 in terms of number of CTFs (files or single CTFs) found:"
          echo "nCTFsFilesInspected_step1 = $nCTFsFilesInspected_step1, nCTFsFilesInspected_step2 = $nCTFsFilesInspected_step2"
          echo "nCTFsFilesOK_step1 = $nCTFsFilesOK_step1, nCTFsFilesOK_step2 = $nCTFsFilesOK_step2"
          echo "nCTFsFilesFailed_step1 = $nCTFsFilesFailed_step1, nCTFsFilesFailed_step2 = $nCTFsFilesFailed_step2"
          echo "nCTFsProcessed_step1 = $nCTFsProcessed_step1, nCTFsProcessed_step2 = $nCTFsProcessed_step2"
          echo "Inconsistency between step 1 and step 2 in terms of number of CTFs (files or single CTFs) found:" > validation_error.message
          echo "nCTFsFilesInspected_step1 = $nCTFsFilesInspected_step1, nCTFsFilesInspected_step2 = $nCTFsFilesInspected_step2" > validation_error.message
          echo "nCTFsFilesOK_step1 = $nCTFsFilesOK_step1, nCTFsFilesOK_step2 = $nCTFsFilesOK_step2" > validation_error.message
          echo "nCTFsProcessed_step1 = $nCTFsProcessed_step1, nCTFsProcessed_step2 = $nCTFsProcessed_step2" > validation_error.message
          exit 255
        fi
      fi
    fi
  fi

  if ([[ -z "$ALIEN_JDL_STARTSPLITSTEP" ]] && [[ -z "$ALIEN_JDL_SSPLITSTEP" ]]) || [[ "$ALIEN_JDL_SSPLITSTEP" -eq 3 ]] || ( [[ -n $ALIEN_JDL_STARTSPLITSTEP ]] && [[ "$ALIEN_JDL_STARTSPLITSTEP" -le 3 ]]) || [[ "$ALIEN_JDL_SSPLITSTEP" == "all" ]]; then
    # 3. matching, calib, AOD, potentially QC
    WORKFLOW_PARAMETERS=$WORKFLOW_PARAMETERS_START
    if [[ "$ALIEN_JDL_KEEPQCSEPARATE" == "1" ]]; then
      echo "QC will be run as last step, removing it from 3rd step"
      for i in QC; do
	export WORKFLOW_PARAMETERS=$(echo $WORKFLOW_PARAMETERS | sed -e "s/,$i,/,/g" -e "s/^$i,//" -e "s/,$i"'$'"//" -e "s/^$i"'$'"//")
      done
    fi
    echo "WORKFLOW_PARAMETERS=$WORKFLOW_PARAMETERS"
    echo "Step 3) matching, calib, AOD, potentially QC"
    echo -e "\nStep 3) matching, calib, AOD, potentially QC" >> workflowconfig.log
    export ALIEN_JDL_PROCESSITSDEADMAP=  # disable ITS dead map calibration, if it was requested then it was already done at step 2
    export ALIEN_JDL_PROCESSMFTDEADMAP=  # disable MFT dead map calibration, if it was requested then it was already done at step 2
    # This uses the same time frame rate limiting as in full wf, unless differently specified in the JDL
    export TIMEFRAME_RATE_LIMIT=${ALIEN_JDL_TIMEFRAMERATELIMITSSPLITWF:-${TIMEFRAME_RATE_LIMIT}}
    echo "Removing detectors $DETECTORS_EXCLUDE"
    if [[ $ALIEN_JDL_USEREADERDELAY == 1 ]]; then
      # if we add a delay, the rate limiting should be disabled
      TIMEFRAME_RATE_LIMIT=0
      READER_DELAY=${ALIEN_JDL_READERDELAY:-30}
      export ARGS_EXTRA_PROCESS_o2_global_track_cluster_reader+=" --reader-delay $READER_DELAY "
    fi
    echo "extra args are $ARGS_EXTRA_PROCESS_o2_global_track_cluster_reader"
    WORKFLOW_DETECTORS_EXCLUDE_QC_SCRIPT+=",CPV"
    READ_TRACKS="ALLSINGLE"
    READ_CLUSTERS="ALLSINGLE"
    if [[ "$ALIEN_JDL_KEEPQCSEPARATE" == "1" ]]; then
      STEP_3_ROOT_OUTPUT="DISABLE_ROOT_OUTPUT=0"
    else
      STEP_3_ROOT_OUTPUT=$SETTING_ROOT_OUTPUT
    fi
    env $STEP_3_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=print TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS=ALL WORKFLOW_DETECTORS_EXCLUDE=$DETECTORS_EXCLUDE WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS=$READ_TRACKS WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS=$READ_CLUSTERS WORKFLOW_DETECTORS_EXCLUDE_GLOBAL_READER_TRACKS=HMP WORKFLOW_DETECTORS_EXCLUDE_QC=$WORKFLOW_DETECTORS_EXCLUDE_QC_SCRIPT,$DETECTORS_EXCLUDE ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list >> workflowconfig.log
    # run it
    if [[ "0$RUN_WORKFLOW" != "00" ]]; then
      timeStart=`date +%s`
      time env $STEP_3_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=run TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS=ALL WORKFLOW_DETECTORS_EXCLUDE=$DETECTORS_EXCLUDE WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS=$READ_TRACKS WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS=$READ_CLUSTERS WORKFLOW_DETECTORS_EXCLUDE_GLOBAL_READER_TRACKS=HMP WORKFLOW_DETECTORS_EXCLUDE_QC=$WORKFLOW_DETECTORS_EXCLUDE_QC_SCRIPT,$DETECTORS_EXCLUDE ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list
      exitcode=$?
      timeEnd=`date +%s`
      timeUsed=$(( $timeUsed+$timeEnd-$timeStart ))
      delta=$(( $timeEnd-$timeStart ))
      echo "Time spent in running the workflow, Step 3 = $delta s"
      echo "exitcode = $exitcode"
      if [[ $exitcode -ne 0 ]]; then
        echo "exit code from Step 3 of processing is " $exitcode > validation_error.message
        echo "exit code from Step 3 of processing is " $exitcode
        exit $exitcode
      fi
      mv latest.log latest_reco_3.log
      if [[ -f performanceMetrics.json ]]; then
        mv performanceMetrics.json performanceMetrics_3.json
      fi
    fi
  fi
  if [[ "$ALIEN_JDL_KEEPQCSEPARATE" == "1" ]]; then
    if ([[ -z "$ALIEN_JDL_STARTSPLITSTEP" ]] && [[ -z "$ALIEN_JDL_SSPLITSTEP" ]]) || [[ "$ALIEN_JDL_SSPLITSTEP" -eq 4 ]] || ( [[ -n $ALIEN_JDL_STARTSPLITSTEP ]] && [[ "$ALIEN_JDL_STARTSPLITSTEP" -le 4 ]]) || [[ "$ALIEN_JDL_SSPLITSTEP" == "all" ]]; then
      # 4. QC
      WORKFLOW_PARAMETERS="QC"
      echo "WORKFLOW_PARAMETERS=$WORKFLOW_PARAMETERS"
      echo "Step 4) QC"
      echo -e "\nStep 4) QC" >> workflowconfig.log
      echo "Removing detectors $DETECTORS_EXCLUDE"
      echo "The rate limiting will be the same as in step 3: TIMEFRAME_RATE_LIMIT = ${TIMEFRAME_RATE_LIMIT}"
      READ_TRACKS="ALL"
      READ_CLUSTERS="ALL"
      export GLOBAL_READER_NEEDS_PV="1"
      export GLOBAL_READER_NEEDS_SV="0"
      export SVERTEXING_SOURCES="none"
      WORKFLOW_DETECTORS_EXCLUDE_QC_SCRIPT+=",CPV"
      echo "QC_JSON_FROM_OUTSIDE = $QC_JSON_FROM_OUTSIDE"
      env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=print TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS=ALL WORKFLOW_DETECTORS_EXCLUDE=$DETECTORS_EXCLUDE WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS=$READ_TRACKS WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS=$READ_CLUSTERS WORKFLOW_DETECTORS_EXCLUDE_GLOBAL_READER_TRACKS= WORKFLOW_DETECTORS_EXCLUDE_QC=$WORKFLOW_DETECTORS_EXCLUDE_QC_SCRIPT,$DETECTORS_EXCLUDE ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list >> workflowconfig.log
      # run it
      if [[ "0$RUN_WORKFLOW" != "00" ]]; then
        timeStart=`date +%s`
        time env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=run TFDELAY=$TFDELAYSECONDS WORKFLOW_DETECTORS=ALL WORKFLOW_DETECTORS_EXCLUDE=$DETECTORS_EXCLUDE WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS=$READ_TRACKS WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS=$READ_CLUSTERS WORKFLOW_DETECTORS_EXCLUDE_GLOBAL_READER_TRACKS= WORKFLOW_DETECTORS_EXCLUDE_QC=$WORKFLOW_DETECTORS_EXCLUDE_QC_SCRIPT,$DETECTORS_EXCLUDE ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list
        exitcode=$?
        timeEnd=`date +%s`
        timeUsed=$(( $timeUsed+$timeEnd-$timeStart ))
        delta=$(( $timeEnd-$timeStart ))
        echo "Time spent in running the workflow, Step 4 = $delta s"
        echo "exitcode = $exitcode"
        if [[ $exitcode -ne 0 ]]; then
          echo "exit code from Step 4 of processing is " $exitcode > validation_error.message
          echo "exit code from Step 4 of processing is " $exitcode
          exit $exitcode
        fi
        mv latest.log latest_reco_4.log
        if [[ -f performanceMetrics.json ]]; then
          mv performanceMetrics.json performanceMetrics_4.json
        fi
      fi
    fi
  fi
fi

# now extract all performance metrics
if [[ $ALIEN_JDL_EXTRACTMETRICS == "1" ]]; then
  IFS=$'\n'
  timeStart=`date +%s`
  for perfMetricsFiles in performanceMetrics.json performanceMetrics_1.json performanceMetrics_2.json performanceMetrics_3.json performanceMetrics_4.json ; do
    suffix=`echo $perfMetricsFiles | sed 's/performanceMetrics\(.*\).json/\1/'`
    if [[ -f "performanceMetrics.json" ]]; then
      for workflow in `grep ': {' $perfMetricsFiles`; do
        strippedWorkflow=`echo $workflow | cut -d\" -f2`
        cat $perfMetricsFiles | jq '.'\"${strippedWorkflow}\"'' > ${strippedWorkflow}_metrics${suffix}.json
      done
    fi
  done
  timeEnd=`date +%s`
  timeUsed=$(( $timeUsed+$timeEnd-$timeStart ))
  delta=$(( $timeEnd-$timeStart ))
  echo "Time spent in splitting the metrics files = $delta s"
fi

if [[ $ALIEN_JDL_AODOFF != 1 ]]; then
  # flag to possibly enable Analysis QC
  [[ -z ${ALIEN_JDL_RUNANALYSISQC+x} ]] && ALIEN_JDL_RUNANALYSISQC=1

  # merging last AOD file in case it is too small; threshold put at 80% of the required file size
  AOD_LIST_COUNT=`find . -name AO2D.root | wc -w`
  AOD_LIST=`find . -name AO2D.root`
  if [[ -n $ALIEN_JDL_MINALLOWEDAODPERCENTSIZE ]]; then
    MIN_ALLOWED_AOD_PERCENT_SIZE=$ALIEN_JDL_MINALLOWEDAODPERCENTSIZE
  else
    MIN_ALLOWED_AOD_PERCENT_SIZE=20
  fi
  if [[ $AOD_LIST_COUNT -ge 2 ]]; then
    AOD_LAST=`find . -name AO2D.root | sort | tail -1`
    CURRENT_SIZE=`wc -c $AOD_LAST | awk '{print $1}'`
    echo "current size of last AOD file = $CURRENT_SIZE"
    PERCENT=`echo "scale=2; $CURRENT_SIZE/($AOD_FILE_SIZE*10^6)*100" | bc -l`
    echo "percentage compared to AOD_FILE_SIZE (= $AOD_FILE_SIZE) = $PERCENT"
    if (( $(echo "$PERCENT < $MIN_ALLOWED_AOD_PERCENT_SIZE" | bc -l) )); then
      AOD_LAST_BUT_ONE=`find . -name AO2D.root | sort | tail -2 | head -1`
      echo "Last AOD file too small, merging $AOD_LAST with previous file $AOD_LAST_BUT_ONE"
      ls $PWD/$AOD_LAST > listAOD.list
      ls $PWD/$AOD_LAST_BUT_ONE >> listAOD.list
      echo "List of files for merging:"
      cat listAOD.list
      mkdir tmpAOD
      cd tmpAOD
      ln -s ../listAOD.list .
      timeStart=`date +%s`
      time o2-aod-merger --input listAOD.list > merging_lastAOD.log
      exitcode=$?
      timeEnd=`date +%s`
      timeUsed=$(( $timeUsed+$timeEnd-$timeStart ))
      delta=$(( $timeEnd-$timeStart ))
      echo "Time spent in merging last AOD files, to reach a good size for that too = $delta s"
      echo "exitcode = $exitcode"
      if [[ $exitcode -ne 0 ]]; then
        echo "exit code from aod-merger for latest file is " $exitcode > validation_error.message
        echo "exit code from aod-merger for latest file is " $exitcode
        exit $exitcode
     fi
      MERGED_SIZE=`wc -c AO2D.root | awk '{print $1}'`
      echo "Size of merged file: $MERGED_SIZE"
      cd ..
      AOD_DIR_TO_BE_REMOVED="$(echo $AOD_LAST | sed -e 's/AO2D.root//')"
      AOD_DIR_TO_BE_UPDATED="$(echo $AOD_LAST_BUT_ONE | sed -e 's/AO2D.root//')"
      echo "We will remove $AOD_DIR_TO_BE_REMOVED and update $AOD_DIR_TO_BE_UPDATED"
      rm -rf $AOD_DIR_TO_BE_REMOVED
      mv tmpAOD/AO2D.root $AOD_DIR_TO_BE_UPDATED/.
      rm -rf tmpAOD
    fi
  fi

  # now checking all AO2D files and running the analysis QC
  # retrieving again the list of AOD files, in case it changed after the merging above
  AOD_LIST_COUNT=`find . -name AO2D.root | wc -w`
  AOD_LIST=`find . -name AO2D.root`
  MAX_POOL_SIZE=${ALIEN_JDL_CPUCORES-8}
  if [[ -n $ALIEN_JDL_MAXPOOLSIZEAODMERGING ]]; then
    MAX_POOL_SIZE=$ALIEN_JDL_MAXPOOLSIZEAODMERGING
  fi
  echo "Max number of parallel AOD mergers will be $MAX_POOL_SIZE"
  JOB_LIST=job-list.txt
  if [[ -f $JOB_LIST ]]; then
    rm $JOB_LIST
  fi
  timeStart=`date +%s`
  timeUsedCheck=0
  timeUsedMerge=0
  timeUsedCheckMergedAOD=0
  timeUsedAnalysisQC=0
  # preparing list of AODs to be merged internally
  for (( i = 1; i <=$AOD_LIST_COUNT; i++)); do
    AOD_FILE=`echo $AOD_LIST | cut -d' ' -f$i`
    AOD_DIR=`dirname $AOD_FILE | sed -e 's|./||'`
    echo "$AOD_DIR" >> $JOB_LIST
  done
  # spawning the parallel merging
  timeStartMerge=`date +%s`
  arr=()
  aods=()
  mergedok=()
  i=0
  while IFS= read -r line; do
    while [[ $CURRENT_POOL_SIZE -ge $MAX_POOL_SIZE ]]; do
      CURRENT_POOL_SIZE=`jobs -r | wc -l`
      sleep 1
    done
    run_AOD_merging $line &
    arr[$i]=$!
    aods[$i]=$line
    i=$((i+1))
    CURRENT_POOL_SIZE=`jobs -r | wc -l`
  done < $JOB_LIST
  # collecting return codes of the merging processes
  for i in "${!arr[@]}"; do
    wait ${arr[$i]}
    exitcode=$?
    if [[ $exitcode -ne 0 ]]; then
      echo "Exit code from the process check+merging+check_mergedAODs for ${aods[$i]} is " $exitcode > validation_error.message
      echo "Exit code from the process check+merging+check_mergedAODs for ${aods[$i]} is " $exitcode
      echo "This means that the process check+merging+check_mergedAODs for ${aods[$i]} FAILED, we make the whole processing FAIL"
      exit $exitcode
      mergedok[$((10#${aods[$i]}))]=0
    else
      echo "Merging of DFs inside the AO2D in ${aods[$i]} worked correctly"
      mergedok[$((10#${aods[$i]}))]=1
    fi
  done
  timeEndMerge=`date +%s`
  timeUsedMerge=$(( $timeUsedMerge+$timeEndMerge-$timeStartMerge ))
  echo "--> Total Time spent in checking and merging AODs = $timeUsedMerge s"

  # running analysis QC if requested
  if [[ $ALIEN_JDL_RUNANALYSISQC == 1 ]]; then
    for (( i = 1; i <=$AOD_LIST_COUNT; i++)); do
      AOD_FILE=`echo $AOD_LIST | cut -d' ' -f$i`
      AOD_DIR=`dirname $AOD_FILE | sed -e 's|./||'`
      cd $AOD_DIR
      timeStartAnalysisQC=`date +%s`
      # creating the analysis wf
      time ${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_workflow.py -f AO2D.root
      # running it
      time ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -k -f workflow_analysis_test.json > analysisQC.log
      exitcode=$?
      timeEndAnalysisQC=`date +%s`
      timeUsedAnalysisQC=$(( $timeUsedAnalysisQC+$timeEndAnalysisQC-$timeStartAnalysisQC ))
      echo "exitcode = $exitcode"
      if [[ $exitcode -ne 0 ]]; then
        echo "exit code from Analysis QC is " $exitcode > validation_error.message
        echo "exit code from Analysis QC is " $exitcode
        exit $exitcode
      fi
      if [[ -f "Analysis/MergedAnalyses/AnalysisResults.root" ]]; then
        mv Analysis/MergedAnalyses/AnalysisResults.root .
      else
        echo "No Analysis/MergedAnalyses/AnalysisResults.root found! check analysis QC"
      fi
      if ls Analysis/*/*.log 1> /dev/null 2>&1; then
        mv Analysis/*/*.log .
      fi
      cd ..
    done
    echo "Time spent in AnalysisQC = $timeUsedAnalysisQC s"
  else
    echo "Analysis QC will not be run, ALIEN_JDL_RUNANALYSISQC = $ALIEN_JDL_RUNANALYSISQC"
    echo "No timing reported for Analysis QC, since it was not run"
  fi
fi


timeEndFullProcessing=`date +%s`
timeUsedFullProcessing=$(( $timeEndFullProcessing-$timeStartFullProcessing ))

echo "Total time used for processing = $timeUsedFullProcessing s"

if [[ $ALIEN_JDL_QCOFF != 1 ]]; then
  # copying the QC json file here
  if [[ ! -z $QC_JSON_FROM_OUTSIDE ]]; then
    QC_JSON=$QC_JSON_FROM_OUTSIDE
  else
    if [[ -d $GEN_TOPO_WORKDIR/json_cache ]]; then
      echo "copying latest file found in ${GEN_TOPO_WORKDIR}/json_cache"
      QC_JSON=`ls -dArt $GEN_TOPO_WORKDIR/json_cache/* | tail -n 1`
    else
      echo "No QC files found, probably QC was not run"
    fi
  fi
  if [[ ! -z $QC_JSON ]]; then
    cp $QC_JSON QC_production.json
  fi
fi
