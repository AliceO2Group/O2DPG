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
    export MODE="LOCAL"
    shift
elif [[ "${1##*.}" == "xml" ]]; then
    sed -rn 's/.*turl="([^"]*)".*/\1/p' $1 > list.list
    head -1 list.list > list.listtmp && mv list.listtmp list.list
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
    if [[ -f $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/extractCalib/setenv_extra.sh ]]; then
	ln -s $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/extractCalib/setenv_extra.sh
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

if [[ ! -z "$ALIEN_JDL_SHMSIZE" ]]; then export SHMSIZE=$ALIEN_JDL_SHMSIZE; elif [[ -z "$SHMSIZE" ]]; then export SHMSIZE=$(( 16 << 30 )); fi
if [[ ! -z "$ALIEN_JDL_DDSHMSIZE" ]]; then export DDSHMSIZE=$ALIEN_JDL_DDSHMSIZE; elif [[ -z "$DDSHMSIZE" ]]; then export DDSHMSIZE=$(( 32 << 10 )); fi

# root output enabled only for some fraction of the cases
# keeping AO2D.root QC.root o2calib_tof.root mchtracks.root mchclusters.root

SETTING_ROOT_OUTPUT="ENABLE_ROOT_OUTPUT_o2_primary_vertexing_workflow= ENABLE_ROOT_OUTPUT_o2_tfidinfo_writer_workflow= "

if [[ -n $ALIEN_INPUT_TYPE ]] && [[ "$ALIEN_INPUT_TYPE" == "TFs" ]]; then
  export WORKFLOW_PARAMETERS=CTF
  INPUT_TYPE=TF
  if [[ $RUNNUMBER -lt 523141 ]]; then
    export TPC_CONVERT_LINKZS_TO_RAW=1
  fi
else
  INPUT_TYPE=CTF
fi

keep=0

if [[ $keep -eq 1 ]]; then
  SETTING_ROOT_OUTPUT+="DISABLE_ROOT_OUTPUT=0";
fi
echo "SETTING_ROOT_OUTPUT = $SETTING_ROOT_OUTPUT"

# Enabling GPUs
if [[ -n "$ALIEN_JDL_USEGPUS" ]]; then
  echo "Enabling GPUS"
  export GPUTYPE="HIP"
  export GPUMEMSIZE=$((25 << 30))
  if [[ $keep -eq 0 ]]; then
    export MULTIPLICITY_PROCESS_tof_matcher=2
    export MULTIPLICITY_PROCESS_mch_cluster_finder=3
    export MULTIPLICITY_PROCESS_tpc_entropy_decoder=2
    export MULTIPLICITY_PROCESS_itstpc_track_matcher=3
    export MULTIPLICITY_PROCESS_its_tracker=2
  fi
  export SHMSIZE=20000000000
  export SHMTHROW=0
  export TIMEFRAME_RATE_LIMIT=8
  export OMP_NUM_THREADS=8
else
  # David, Oct 13th
  # the optimized settings for the 8 core GRID queue without GPU are
  # (overwriting the values above)
  #
  export TIMEFRAME_RATE_LIMIT=3
  export OMP_NUM_THREADS=5
  export SHMSIZE=16000000000
fi

echo "[INFO (async_pass.sh)] envvars were set to TFDELAYSECONDS ${TFDELAYSECONDS} TIMEFRAME_RATE_LIMIT ${TIMEFRAME_RATE_LIMIT}"

# reco and matching
# print workflow
env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=print TFDELAY=$TFDELAYSECONDS NTIMEFRAMES=-1 ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list > workflowconfig.log
# run it
env $SETTING_ROOT_OUTPUT IS_SIMULATED_DATA=0 WORKFLOWMODE=run TFDELAY=$TFDELAYSECONDS NTIMEFRAMES=-1 ./run-workflow-on-inputlist.sh $INPUT_TYPE list.list

# now extract all performance metrics
IFS=$'\n'
if [[ -f "performanceMetrics.json" ]]; then
    for workflow in `grep ': {' performanceMetrics.json`; do
	strippedWorkflow=`echo $workflow | cut -d\" -f2`
	cat performanceMetrics.json | jq '.'\"${strippedWorkflow}\"'' > ${strippedWorkflow}_metrics.json
    done
fi
