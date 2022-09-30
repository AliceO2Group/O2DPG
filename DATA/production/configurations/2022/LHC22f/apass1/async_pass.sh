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


if [[ "${1##*.}" == "root" ]]; then
    #echo ${1##*.}
    #echo "alien://${1}" > list.list
    #export MODE="remote"
    echo "${1}" > list.list
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
if [[ -n "$ALIEN_JDL_LPMPASSNAME" ]]; then
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
    SELECTSETTINGSSCRIPT="$O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$ALIEN_JDL_LPMPASSNAME/selectSettings.sh"
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

echo "Checking current directory content"
ls -altr

if [[ -f "setenv_extra.sh" ]]; then
    source setenv_extra.sh $RUNNUMBER $BEAMTYPE
else
    echo "************************************************************************************"
    echo "No ad-hoc setenv_extra settings for current async processing; using the one in O2DPG"
    echo "************************************************************************************"
    if [[ -f $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$ALIEN_JDL_LPMPASSNAME/setenv_extra.sh ]]; then
	ln -s $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$ALIEN_JDL_LPMPASSNAME/setenv_extra.sh
	source setenv_extra.sh $RUNNUMBER $BEAMTYPE
    else
	echo "*********************************************************************************************************"
	echo "No setenev_extra for $ALIEN_JDL_LPMANCHORYEAR/$O2DPGPATH/$ALIEN_JDL_LPMPASSNAME in O2DPG"
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
  TFDELAYSECONDS=8
  export TIMEFRAME_RATE_LIMIT=1
fi

echo "[INFO (async_pass.sh)] envvars were set to TFDELAYSECONDS ${TFDELAYSECONDS} TIMEFRAME_RATE_LIMIT ${TIMEFRAME_RATE_LIMIT}"

if [[ ! -z "$ALIEN_JDL_SHMSIZE" ]]; then export SHMSIZE=$ALIEN_JDL_SHMSIZE; elif [[ -z "$SHMSIZE" ]]; then export SHMSIZE=$(( 16 << 30 )); fi
if [[ ! -z "$ALIEN_JDL_DDSHMSIZE" ]]; then export DDSHMSIZE=$ALIEN_JDL_DDSHMSIZE; elif [[ -z "$DDSHMSIZE" ]]; then export DDSHMSIZE=$(( 32 << 10 )); fi

# root output enabled only for some fraction of the cases
# keeping AO2D.root QC.root o2calib_tof.root MFTAssessment.root mchtracks.root mchclusters.root

SETTING_ROOT_OUTPUT="ENABLE_ROOT_OUTPUT_o2_mch_reco_workflow= ENABLE_ROOT_OUTPUT_o2_mft_reco_workflow= ENABLE_ROOT_OUTPUT_o2_tof_matcher_workflow= ENABLE_ROOT_OUTPUT_o2_aod_producer_workflow= ENABLE_ROOT_OUTPUT_o2_qc= "

keep=0

if [[ $MODE == "remote" ]]; then
  if [ -f wn.xml ]; then
    CTF=$(grep alien:// wn.xml | tr ' ' '\n' | grep ^lfn | cut -d\" -f2)
  fi
  SUBJOBIDX=$(grep -B1 $CTF CTFs.xml | head -n1 | cut -d\" -f2)
  echo "CTF                                     : $CTF"
  echo "Index of CTF in collection              : $SUBJOBIDX"
  echo "Number of subjobs for current masterjob : $ALIEN_JDL_SUBJOBCOUNT"

  # JDL can set the permille to keep; otherwise we use 2
  if [[ ! -z "$ALIEN_JDL_NKEEP" ]]; then export NKEEP=$ALIEN_JDL_NKEEP; else NKEEP=2; fi

  KEEPRATIO=$((1000/NKEEP))
  echo "Set to save ${NKEEP} permil intermediate output"
  [[ "$((SUBJOBIDX%KEEPRATIO))" -eq "0" ]] && keep=1
  # if we don't have enough subjobs, we anyway keep the first
  [[ "$ALIEN_JDL_SUBJOBCOUNT" -le "$KEEPRATIO" && "$SUBJOBIDX" -eq 1 ]] && keep=1
  if [[ $keep -eq 1 ]]; then
    echo "Intermediate files WILL BE KEPT";
  else
    echo "Intermediate files WILL BE KEPT ONLY FOR SOME WORKFLOWS";
  fi
else
  # in LOCAL mode, by default we keep all intermediate files
  echo -e "\n\n **** RUNNING IN LOCAL MODE"
  keep=1
  if [[ -z "$DO_NOT_KEEP_OUTPUT_IN_LOCAL" ]]; then
    echo "**** ONLY SOME WORKFLOWS WILL HAVE THE ROOT OUTPUT SAVED\n\n"
    keep=0;
  else
    echo -e "**** WE KEEP ALL ROOT OUTPUT";
    echo -e "**** IF YOU WANT TO REMOVE ROOT OUTPUT FILES FOR PERFORMANCE STUDIES OR SIMILAR, PLEASE SET THE ENV VAR DO_NOT_KEEP_OUTPUT_IN_LOCAL\n\n"
  fi
fi

if [[ $keep -eq 0 ]]; then
  SETTING_ROOT_OUTPUT+="DISABLE_ROOT_OUTPUT=0";
fi
echo SETTING_ROOT_OUTPUT=$SETTING_ROOT_OUTPUT

# Enabling GPUs
if [[ -n "$ALIEN_JDL_USEGPUS" ]]; then
  echo "Enabling GPUS"
  export GPUTYPE="HIP"
  export GPUMEMSIZE=$((25 << 30))
fi

# reco and matching
# print workflow
env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=print TFDELAY=$TFDELAYSECONDS NTIMEFRAMES=-1 ./run-workflow-on-inputlist.sh CTF list.list > workflowconfig.log
# run it
env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=run TFDELAY=$TFDELAYSECONDS NTIMEFRAMES=-1 ./run-workflow-on-inputlist.sh CTF list.list

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

# now checking AO2D file
if [[ -f "AO2D.root" ]]; then
    root -l -b -q $O2DPG_ROOT/DATA/production/common/readAO2Ds.C > checkAO2D.log
    exitcode=$?
    if [[ $exitcode -ne 0 ]]; then
	echo "exit code from AO2D check is " $exitcode > validation_error.message
	echo "exit code from AO2D check is " $exitcode
	exit $exitcode
    fi
    if [[ $ALIEN_JDL_RUNANALYSISQC == 1 ]]; then
      ${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_workflow.py -f AO2D.root
      ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow_analysis_test.json > analysisQC.log
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
