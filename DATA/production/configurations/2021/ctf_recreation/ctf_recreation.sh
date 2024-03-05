#!/bin/bash

# Script to run the async processing
#
# if run locally, you need to export e.g.:
#
# export ALIEN_JDL_LPMRUNNUMBER=505673
# export ALIEN_JDL_LPMINTERACTIONTYPE=pp
# export ALIEN_JDL_LPMPRODUCTIONTAG=OCT
# export ALIEN_JDL_LPMPASSNAME=apass3
# export ALIEN_JDL_LPMANCHORYEAR=2021
# export ALIEN_JDL_DETCONFIG=centralBarrel [muon, cpv, emcal, phos]


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
    -dc|--detector-config)  
      export DETCONFIG="$2"
      shift
      shift
      ;;
    -b|--beam-type)
      export BEAMTYPE="$2"
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
# year
if [[ -n "$ALIEN_JDL_LPMANCHORYEAR" ]]; then
    export YEAR="$ALIEN_JDL_LPMANCHORYEAR"
fi
# period
if [[ -n "$ALIEN_JDL_LPMPRODUCTIONTAG" ]]; then
    export PERIOD="$ALIEN_JDL_LPMPRODUCTIONTAG"
fi
# beam type
if [[ -n "$ALIEN_JDL_LPMINTERACTIONTYPE" ]]; then
    export BEAMTYPE="$ALIEN_JDL_LPMINTERACTIONTYPE"
fi
# pass
if [[ -n "$ALIEN_JDL_LPMPASSNAME" ]]; then
    export PASS="$ALIEN_JDL_LPMPASSNAME"
fi

# detector configuration to be processed
# if the option "-dc" or "--detector-config" is passed, this has precedence on all other ways to set this;
# if "$DETCONFIG" is set explicitly, this has the second highest priority
# last option is to have it from the JDL
if [[ -z "$DETCONFIG" ]]; then
    if [[ -z "$ALIEN_JDL_DETCONFIG" ]]; then
	echo "nothing set the detector configuration to use, exiting"
	exit 4
    else
	DETCONFIG="$ALIEN_JDL_DETCONFIG"
    fi
fi

if [[ -z $RUNNUMBER ]] || [[ -z $YEAR ]] || [[ -z $PERIOD ]] || [[ -z $DETCONFIG ]] || [[ -z $BEAMTYPE ]] || [[ -z $PASS ]]; then
    echo "check env variables we need RUNNUMBER (--> $RUNNUMBER), YEAR (--> $YEAR), PERIOD (--> $PERIOD), DETCONFIG (--> $DETCONFIG), BEAMTYPE (--> $BEAMTYPE), PASS (--> $PASS)"
    exit 3
fi

echo "processing run $RUNNUMBER, from year $YEAR and period $PERIOD with beamtype $BEAMTYPE, pass $PASS. Detector config will be $DETCONFIG"

###if [[ $MODE == "remote" ]]; then 
    # common archive
    if [[ ! -f commonInput.tgz ]]; then
	echo "No commonInput.tgz found exiting"
	exit 2
    fi
    # run specific archive
    if [[ $DETCONFIG == "muon" ]] || [[ $DETCONFIG == "centralBarrel" ]]; then
	if [[ ! -f runInput_$RUNNUMBER.tgz ]]; then
	    echo "No runInput_$RUNNUMBER.tgz found exiting"
	    exit 2
	else
	    tar -xzvf runInput_$RUNNUMBER.tgz
	fi
    fi
    tar -xzvf commonInput.tgz

###fi

echo "Checking current directory content"
ls -altr 

export WORKFLOW_PARAMETERS=CTF
if [[ -f "setenv_extra_ctf_recreation_$DETCONFIG.sh" ]]; then
    source setenv_extra_ctf_recreation_$DETCONFIG.sh 
else
    echo "************************************************************************************"
    echo "No ad-hoc setenv_extra_ctf_recreation_$DETCONFIG settings for current async processing; using the one in O2DPG"
    echo "************************************************************************************"
    if [[ -f $O2DPG_ROOT/DATA/production/configurations/$YEAR/ctf_recreation/setenv_extra_ctf_recreation_$DETCONFIG.sh ]]; then
	ln -s $O2DPG_ROOT/DATA/production/configurations/$YEAR/ctf_recreation/setenv_extra_ctf_recreation_$DETCONFIG.sh
	source setenv_extra_ctf_recreation_$DETCONFIG.sh
    else
	echo "*********************************************************************************************************"
	echo "No setenv_extra_ctf_recreation_$DETCONFIG for $ALIEN_JDL_LPMANCHORYEAR in O2DPG"
	echo "                Processing cannot start"
	echo "*********************************************************************************************************"
	exit 5
    fi
fi

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

ln -sf $O2DPG_ROOT/DATA/common/setenv.sh
ln -sf $O2DPG_ROOT/DATA/common/getCommonArgs.sh

export TFDELAY=0.1
if [[ $DETCONFIG == "centralBarrel" ]]; then
    export TFDELAY=10
fi

# print workflow
IS_SIMULATED_DATA=0 WORKFLOWMODE=print SYNCMODE=1 NTIMEFRAMES=-1 SHMSIZE=16000000000 DDSHMSIZE=32000 TPC_CONVERT_LINKZS_TO_RAW=1 ./run-workflow-on-inputlist.sh TF list.list > workflowconfig.log
# run it
IS_SIMULATED_DATA=0 WORKFLOWMODE=run   SYNCMODE=1 NTIMEFRAMES=-1 SHMSIZE=16000000000 DDSHMSIZE=32000 TPC_CONVERT_LINKZS_TO_RAW=1 ./run-workflow-on-inputlist.sh TF list.list 


