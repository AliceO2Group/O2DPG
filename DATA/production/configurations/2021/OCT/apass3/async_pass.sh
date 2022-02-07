#!/bin/bash

# Script to run the async processing
#
# if run locally, you need to export e.g.:
#
# export ALIEN_JDL_LPMRUNNUMBER=505673
# export ALIEN_JDL_LPMINTERACTIONTYPE=pp
# export ALIEN_JDL_LPMPRODUCTIONTAG=OCT
# export ALIEN_JDL_LPMPASSNAME=apass3
# export ALIEN_JDL_ANCHORYEAR=2021


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
fi

# pass
if [[ -n "$ALIEN_JDL_LPMPASSNAME" ]]; then
    export PASS="$ALIEN_JDL_LPMPASSNAME"
fi

if [[ -z $RUNNUMBER ]] || [[ -z $PERIOD ]] || [[ -z $BEAMTYPE ]] || [[ -z $PASS ]]; then
    echo "check env variables we need RUNNUMBER (--> $RUNNUMBER), PERIOD (--> $PERIOD), PASS (--> $PASS), BEAMTYPE (--> $BEAMTYPE)"
    return 3
fi

echo processing run $RUNNUMBER, from period $PERIOD with $BEAMTYPE collisions and mode $MODE

###if [[ $MODE == "remote" ]]; then 
    # common archive
    if [[ ! -f commonInput.tgz ]]; then
	echo "No commonInput.tgz found returning"
	return 2
    fi
    # run specific archive
    if [[ ! -f runInput_$RUNNUMBER.tgz ]]; then
	echo "No runInput_$RUNNUMBER.tgz found returning"
	return 2
    fi
    if [[ ! -f TPC_calibdEdx.211216.tgz ]]; then
	echo "No TPC_calibdEdx.211216.tgz found returning"
	return 2
    fi
    tar -xzvf commonInput.tgz
    ln -s o2sim_geometry.root o2sim_geometry-aligned.root
    tar -xzvf runInput_$RUNNUMBER.tgz
    tar -xzvf TPC_calibdEdx.211216.tgz
    mv calibdEdx.pol/*.* .
    if [[ ! -f calibdEdx.$RUNNUMBER.root ]]; then
	echo "No calibdEdx.$RUNNUMBER.root found returning"
	return 2
    fi
    if [[ ! -f splines_for_dedx_3D_scaled_Threshold_3.5.root ]]; then
	echo "No splines_for_dedx_3D_scaled_Threshold_3.5.root found returning"
	return 2
    fi
    if [[ ! -f GainMap_2021-12-15_krypton_0.5T.v2.root ]]; then
	echo "GainMap_2021-12-15_krypton_0.5T.v2.root"
	return 2
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
    if [[ -f $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$ALIEN_JDL_LPMPRODUCTIONTAG/$ALIEN_JDL_LPMPASSNAME/setenv_extra.sh ]]; then
	ln -s $O2DPG_ROOT/DATA/production/configurations/$ALIEN_JDL_LPMANCHORYEAR/$ALIEN_JDL_LPMPRODUCTIONTAG/$ALIEN_JDL_LPMPASSNAME/setenv_extra.sh
	source setenv_extra.sh $RUNNUMBER $BEAMTYPE
    else
	echo "*********************************************************************************************************"
	echo "No setenev_extra for $ALIEN_JDL_LPMANCHORYEAR/$ALIEN_JDL_LPMPRODUCTIONTAG/$ALIEN_JDL_LPMPASSNAME in O2DPG"
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

# reco and matching
# print workflow
IS_SIMULATED_DATA=0 WORKFLOWMODE=print DISABLE_ROOT_OUTPUT="" TFDELAY=40 NTIMEFRAMES=-1 SHMSIZE=16000000000 DDSHMSIZE=32000 ./run-workflow-on-inputlist.sh CTF list.list > workflowconfig.log
# run it
IS_SIMULATED_DATA=0 WORKFLOWMODE=run DISABLE_ROOT_OUTPUT="" TFDELAY=40 NTIMEFRAMES=-1 SHMSIZE=16000000000 DDSHMSIZE=32000 ./run-workflow-on-inputlist.sh CTF list.list 

# now extract all performance metrics
IFS=$'\n'
if [[ -f "performanceMetrics.json" ]]; then
    for workflow in `grep ': {' performanceMetrics.json`; do
	strippedWorkflow=`echo $workflow | cut -d\" -f2`
	cat performanceMetrics.json | jq '.'\"${strippedWorkflow}\"'' > ${strippedWorkflow}_metrics.json
    done
fi

# now checking AO2D file
if [[ -f "AO2D.root" ]]; then
    root -l -b -q $O2DPG_ROOT/DATA/production/common/readAO2Ds.C > checkAO2D.log
    exitcode=$?
    if [[ $exitcode -ne 0 ]]; then
	echo "exit code from AO2D check is " $exitcode > validation_error.message
	echo "exit code from AO2D check is " $exitcode
	exit $exitcode
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
