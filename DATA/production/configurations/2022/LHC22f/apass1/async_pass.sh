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

# to skip positional arg parsing before the randomizing part.
inputarg="${1}"

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
    sed -rn 's/.*turl="([^"]*)".*/\1/p' $1 > list.list
    export MODE="remote"
    shift
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
    if [[ -n "$ALIEN_JDL_O2DPGPATH" ]]; then
      export O2DPGPATH="$ALIEN_JDL_O2DPGPATH"
    else
      export O2DPGPATH="$PERIOD"
    fi
fi

# pass
if [[ -n "$ALIEN_JDL_O2DPGPASSPATH" ]]; then
  export PASS="$ALIEN_JDL_O2DPGPASSPATH"
elif [[ -n "$ALIEN_JDL_LPMPASSNAME" ]]; then
  export PASS="$ALIEN_JDL_LPMPASSNAME"
fi

if [[ -z $RUNNUMBER ]] || [[ -z $PERIOD ]] || [[ -z $BEAMTYPE ]] || [[ -z $PASS ]]; then
    echo "check env variables we need RUNNUMBER (--> $RUNNUMBER), PERIOD (--> $PERIOD), PASS (--> $PASS), BEAMTYPE (--> $BEAMTYPE)"
    exit 3
fi

echo processing run $RUNNUMBER, from period $PERIOD with $BEAMTYPE collisions and mode $MODE

###if [[ $MODE == "remote" ]]; then
    # common archive
    if [[ ! -f commonInput.tgz ]]; then
	echo "No commonInput.tgz found exiting"
	exit 2
    fi
    tar -xzvf commonInput.tgz
    SELECTSETTINGSSCRIPT="$O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$PASS/selectSettings.sh"
    if [[ -f "selectSettings.sh" ]]; then
      SELECTSETTINGSSCRIPT="selectSettings.sh"
    fi
    source $SELECTSETTINGSSCRIPT
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

if [[ -f "setenv_extra.sh" ]]; then
    source setenv_extra.sh $RUNNUMBER $BEAMTYPE
else
    echo "************************************************************************************"
    echo "No ad-hoc setenv_extra settings for current async processing; using the one in O2DPG"
    echo "************************************************************************************"
    if [[ -f $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$PASS/setenv_extra.sh ]]; then
	ln -s $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$PASS/setenv_extra.sh
	source setenv_extra.sh $RUNNUMBER $BEAMTYPE
    else
	echo "*********************************************************************************************************"
	echo "No setenev_extra for $ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$PASS in O2DPG"
	echo "                No special settings will be used"
	echo "*********************************************************************************************************"
    fi
fi

rm -f /dev/shm/*

if [[ -f run-workflow-on-inputlist.sh ]]; then
    echo "Use run-workflow-on-inputlist.sh macro passed as input"
else
    echo "Use run-workflow-on-inputlist.sh macro from O2"
    cp $O2_ROOT/prodtests/full-system-test/run-workflow-on-inputlist.sh .
fi

if [[ -z $DPL_WORKFLOW_FROM_OUTSIDE ]]; then
    echo "Use dpl-workflow.sh from O2"
    cp $O2_ROOT/prodtests/full-system-test/dpl-workflow.sh .
else
    echo "Use dpl-workflow.sh passed as input"
    cp $DPL_WORKFLOW_FROM_OUTSIDE .
fi

if [[ ! -z $QC_JSON_FROM_OUTSIDE ]]; then
    echo "QC json from outside is $QC_JSON_FROM_OUTSIDE"
fi

ln -sf $O2DPG_ROOT/DATA/common/setenv.sh
ln -sf $O2DPG_ROOT/DATA/common/getCommonArgs.sh
ln -sf $O2_ROOT/prodtests/full-system-test/workflow-setup.sh

# TFDELAY and throttling
export TFDELAYSECONDS=40
if [[ -n "$ALIEN_JDL_TFDELAYSECONDS" ]]; then
  TFDELAYSECONDS="$ALIEN_JDL_TFDELAYSECONDS"
# ...otherwise, it depends on whether we have throttling
elif [[ -n "$ALIEN_JDL_USETHROTTLING" ]]; then
  TFDELAYSECONDS=1
  export TIMEFRAME_RATE_LIMIT=1
fi

if [[ ! -z "$ALIEN_JDL_SHMSIZE" ]]; then export SHMSIZE=$ALIEN_JDL_SHMSIZE; elif [[ -z "$SHMSIZE" ]]; then export SHMSIZE=$(( 16 << 30 )); fi
if [[ ! -z "$ALIEN_JDL_DDSHMSIZE" ]]; then export DDSHMSIZE=$ALIEN_JDL_DDSHMSIZE; elif [[ -z "$DDSHMSIZE" ]]; then export DDSHMSIZE=$(( 32 << 10 )); fi

# root output enabled only for some fraction of the cases
# keeping AO2D.root QC.root o2calib_tof.root mchtracks.root mchclusters.root

SETTING_ROOT_OUTPUT="ENABLE_ROOT_OUTPUT_o2_mch_reco_workflow= ENABLE_ROOT_OUTPUT_o2_tof_matcher_workflow= ENABLE_ROOT_OUTPUT_o2_aod_producer_workflow= ENABLE_ROOT_OUTPUT_o2_qc= "
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
  keep=1
  if [[ "$DO_NOT_KEEP_OUTPUT_IN_LOCAL" -eq 1 ]]; then
    echo -e "**** ONLY SOME WORKFLOWS WILL HAVE THE ROOT OUTPUT SAVED ****\n\n"
    keep=0;
  else
    echo -e "**** WE KEEP ALL ROOT OUTPUT ****";
    echo -e "**** IF YOU WANT TO REMOVE ROOT OUTPUT FILES FOR PERFORMANCE STUDIES OR SIMILAR, PLEASE SET THE ENV VAR DO_NOT_KEEP_OUTPUT_IN_LOCAL ****\n\n"
  fi
fi

if [[ $keep -eq 1 ]]; then
  SETTING_ROOT_OUTPUT+="DISABLE_ROOT_OUTPUT=0";
fi
echo "SETTING_ROOT_OUTPUT = $SETTING_ROOT_OUTPUT"

# Enabling GPUs
if [[ -n "$ALIEN_JDL_USEGPUS" && $ALIEN_JDL_USEGPUS != 0 ]]; then
  echo "Enabling GPUS"
  export GPUTYPE="HIP"
  export GPUMEMSIZE=$((25 << 30))
  if [[ "0$ASYNC_PASS_NO_OPTIMIZED_DEFAULTS" != "01" ]]; then
    if [[ $keep -eq 0 ]]; then
      export MULTIPLICITY_PROCESS_tof_matcher=2
      export MULTIPLICITY_PROCESS_mch_cluster_finder=3
      export MULTIPLICITY_PROCESS_tpc_entropy_decoder=2
      export MULTIPLICITY_PROCESS_itstpc_track_matcher=3
      export MULTIPLICITY_PROCESS_its_tracker=2
      export TIMEFRAME_RATE_LIMIT=8
    else
      export TIMEFRAME_RATE_LIMIT=4
    fi
    export OMP_NUM_THREADS=8
    export SHMSIZE=20000000000
  fi
else
  # David, Oct 13th
  # the optimized settings for the 8 core GRID queue without GPU are
  # (overwriting the values above)
  #
  if [[ "0$ASYNC_PASS_NO_OPTIMIZED_DEFAULTS" != "01" ]]; then
    export TIMEFRAME_RATE_LIMIT=3
    export OMP_NUM_THREADS=5
    export SHMSIZE=16000000000
  fi
fi

echo "[INFO (async_pass.sh)] envvars were set to TFDELAYSECONDS ${TFDELAYSECONDS} TIMEFRAME_RATE_LIMIT ${TIMEFRAME_RATE_LIMIT}"

[[ -z $NTIMEFRAMES ]] && export NTIMEFRAMES=-1

# reco and matching
# print workflow
env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=print TFDELAY=$TFDELAYSECONDS ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list > workflowconfig.log
# run it
if [[ "0$RUN_WORKFLOW" != "00" ]]; then
  env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=run TFDELAY=$TFDELAYSECONDS ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list
fi

# now extract all performance metrics
IFS=$'\n'
if [[ -f "performanceMetrics.json" ]]; then
    for workflow in `grep ': {' performanceMetrics.json`; do
	strippedWorkflow=`echo $workflow | cut -d\" -f2`
	cat performanceMetrics.json | jq '.'\"${strippedWorkflow}\"'' > ${strippedWorkflow}_metrics.json
    done
fi

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
  echo current size = $CURRENT_SIZE
  PERCENT=`echo "scale=2; $CURRENT_SIZE/($AOD_FILE_SIZE*10^6)*100" | bc -l`
  echo percent = $PERCENT
  if (( $(echo "$PERCENT < $MIN_ALLOWED_AOD_PERCENT_SIZE" | bc -l) )); then
    AOD_LAST_BUT_ONE=`find . -name AO2D.root | sort | tail -2 | head -1`
    echo "Too small, merging $AOD_LAST with previous file $AOD_LAST_BUT_ONE"
    ls $PWD/$AOD_LAST > list.list
    ls $PWD/$AOD_LAST_BUT_ONE >> list.list
    echo "List of files for merging:"
    cat list.list
    mkdir tmpAOD
    cd tmpAOD
    ln -s ../list.list .
    o2-aod-merger --input list.list
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
for (( i = 1; i <=$AOD_LIST_COUNT; i++)); do
  AOD_DIR=`echo $AOD_LIST | cut -d' ' -f$i | sed -e 's/AO2D.root//'`
  echo "Verifying, Merging DFs, and potentially running analysis QC for AOD file in $AOD_DIR"
  cd $AOD_DIR
  if [[ -f "AO2D.root" ]]; then
    echo "Checking AO2Ds with un-merged DFs"
    root -l -b -q $O2DPG_ROOT/DATA/production/common/readAO2Ds.C > checkAO2D.log
    exitcode=$?
    if [[ $exitcode -ne 0 ]]; then
	echo "exit code from AO2D check is " $exitcode > validation_error.message
	echo "exit code from AO2D check is " $exitcode
	exit $exitcode
    fi
    ls AO2D.root > list.list
    o2-aod-merger --input list.list --output AO2D_merged.root
    echo "Checking AO2Ds with merged DFs"
    root -l -b -q '$O2DPG_ROOT/DATA/production/common/readAO2Ds.C("AO2D_merged.root")' > checkAO2D_merged.log
    exitcode=$?
    if [[ $exitcode -ne 0 ]]; then
	echo "exit code from AO2D with merged DFs check is " $exitcode > validation_error.message
	echo "exit code from AO2D with merged DFs check is " $exitcode
	echo "We will keep the AO2Ds with unmerged DFs"
    else
      echo "All ok, replacing initial AO2D.root file with the one with merged DFs"
      mv AO2D_merged.root AO2D.root
    fi
    if [[ $ALIEN_JDL_RUNANALYSISQC == 1 ]]; then
      ${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_workflow.py -f AO2D.root
      ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -k -f workflow_analysis_test.json > analysisQC.log
      if [[ -f "Analysis/MergedAnalyses/AnalysisResults.root" ]]; then
	mv Analysis/MergedAnalyses/AnalysisResults.root .
      else
	echo "No Analysis/MergedAnalyses/AnalysisResults.root found! check analysis QC"
      fi
      if ls Analysis/*/*.log 1> /dev/null 2>&1; then
	mv Analysis/*/*.log .
      fi
    else
      echo "Analysis QC will not be run, ALIEN_JDL_RUNANALYSISQC = $ALIEN_JDL_RUNANALYSISQC"
    fi
  fi
  cd ..
done

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
