#!/bin/bash

# add distortion maps
# https://alice.its.cern.ch/jira/browse/O2-3346?focusedCommentId=300982&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-300982
#
# export O2DPG_ENABLE_TPC_DISTORTIONS=ON
# SCFile=$PWD/distortions_5kG_lowIR.root # file needs to be downloaded
# export O2DPG_TPC_DIGIT_EXTRA=" --distortionType 2 --readSpaceCharge ${SCFile} "

#
# procedure setting up and executing an anchored MC
#

########################
# helper functionality #
########################

echo_info()
{
  echo "INFO [anchorMC]: ${*}"
}

echo_error()
{
  echo "ERROR [anchorMC]: ${*}"
}

print_help()
{
  echo "Usage: ./anchorMC.sh"
  echo
  echo "This needs O2 and O2DPG loaded from alienv."
  echo
  echo "Make sure the following env variables are set:"
  echo "ALIEN_JDL_LPMANCHORPASSNAME or ANCHORPASSNAME,"
  echo "ALIEN_JDL_MCANCHOR or MCANCHOR,"
  echo "ALIEN_JDL_LPMPASSNAME or PASSNAME,"
  echo "ALIEN_JDL_LPMRUNNUMBER or RUNNUMBER,"
  echo "ALIEN_JDL_LPMPRODUCTIONTYPE or PRODUCTIONTYPE,"
  echo "ALIEN_JDL_LPMINTERACTIONTYPE or INTERACTIONTYPE,"
  echo "ALIEN_JDL_LPMPRODUCTIONTAG or PRODUCTIONTAG,"
  echo "ALIEN_JDL_LPMANCHORRUN or ANCHORRUN,"
  echo "ALIEN_JDL_LPMANCHORPRODUCTION or ANCHORPRODUCTION,"
  echo "ALIEN_JDL_LPMANCHORYEAR or ANCHORYEAR,"
  echo
  echo "as well as:"
  echo "NTIMEFRAMES,"
  echo "NSIGEVENTS,"
  echo "SPLITID,"
  echo "CYCLE,"
  echo "PRODSPLIT."
  echo
  echo "Optional are:"
  echo "ALIEN_JDL_CPULIMIT or CPULIMIT, set the CPU limit of the workflow runner, default: 8,"
  echo "NWORKERS, set the number of workers during detector transport, default: 8,"
  echo "ALIEN_JDL_SIMENGINE or SIMENGINE, choose the transport engine, default: TGeant4,"
  echo "ALIEN_JDL_WORKFLOWDETECTORS, set detectors to be taken into account, default: ITS,TPC,TOF,FV0,FT0,FDD,MID,MFT,MCH,TRD,EMC,PHS,CPV,HMP,CTP,"
  echo "ALIEN_JDL_ANCHOR_SIM_OPTIONS, additional options that are passed to the workflow creation, default: -gen pythia8,"
  echo "ALIEN_JDL_ADDTIMESERIESINMC, run TPC time series. Default: 1, switch off by setting to 0,"
  echo "DISABLE_QC, set this to disable QC, e.g. to 1"
}

# Prevent the script from being soured to omit unexpected surprises when exit is used
SCRIPT_NAME="$(basename "$(test -L "$0" && readlink "$0" || echo "$0")")"
if [ "${SCRIPT_NAME}" != "$(basename ${BASH_SOURCE[0]})" ] ; then
    echo_error "This script cannot not be sourced" >&2
    return 1
fi

while [ "$1" != "" ] ; do
    case $1 in
        --help|-h ) shift
                    print_help
                    exit 0
                    ;;
        * ) echo "Unknown argument ${1}"
            exit 1
            ;;
    esac
done

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo_error "This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo_error "This needs O2 loaded" && exit 1

# check if jq is there
which jq >/dev/null 2>&1
[ "${?}" != "0" ] && { echo_error "jq is not found. Install or load via alienv." ; exit 1 ; }

alien-token-info >/dev/null 2>&1
[ "${?}" != "0" ] && { echo_error "No GRID token found, required to run." ; exit 1 ; }

#################################################################
# Set all required variables to identify an anchored production #
#################################################################

# Allow for both "ALIEN_JDL_LPM<KEY>" as well as "KEY"

# the only four where there is a real default for
export ALIEN_JDL_CPULIMIT=${ALIEN_JDL_CPULIMIT:-${CPULIMIT:-8}}
export ALIEN_JDL_SIMENGINE=${ALIEN_JDL_SIMENGINE:-${SIMENGINE:-TGeant4}}
export ALIEN_JDL_WORKFLOWDETECTORS=${ALIEN_JDL_WORKFLOWDETECTORS:-ITS,TPC,TOF,FV0,FT0,FDD,MID,MFT,MCH,TRD,EMC,PHS,CPV,HMP,CTP}
# can be passed to contain additional options that will be passed to o2dpg_sim_workflow_anchored.py and eventually to o2dpg_sim_workflow.py
export ALIEN_JDL_ANCHOR_SIM_OPTIONS=${ALIEN_JDL_ANCHOR_SIM_OPTIONS:--gen pythia8}
# all others MUST be set by the user/on the outside
export ALIEN_JDL_LPMANCHORPASSNAME=${ALIEN_JDL_LPMANCHORPASSNAME:-${ANCHORPASSNAME}}
# LPMPASSNAME is used in O2 and O2DPG scripts, however on the other hand, ALIEN_JDL_LPMANCHORPASSNAME is the one that is set in JDL templates; so use ALIEN_JDL_LPMANCHORPASSNAME and set ALIEN_JDL_LPMPASSNAME
export ALIEN_JDL_LPMPASSNAME=${ALIEN_JDL_LPMANCHORPASSNAME}
export ALIEN_JDL_LPMRUNNUMBER=${ALIEN_JDL_LPMRUNNUMBER:-${RUNNUMBER}}
export ALIEN_JDL_LPMPRODUCTIONTYPE=${ALIEN_JDL_LPMPRODUCTIONTYPE:-${PRODUCTIONTYPE}}
export ALIEN_JDL_LPMINTERACTIONTYPE=${ALIEN_JDL_LPMINTERACTIONTYPE:-${INTERACTIONTYPE}}
export ALIEN_JDL_LPMPRODUCTIONTAG=${ALIEN_JDL_LPMPRODUCTIONTAG:-${PRODUCTIONTAG}}
export ALIEN_JDL_LPMANCHORRUN=${ALIEN_JDL_LPMANCHORRUN:-${ANCHORRUN}}
export ALIEN_JDL_LPMANCHORPRODUCTION=${ALIEN_JDL_LPMANCHORPRODUCTION:-${ANCHORPRODUCTION}}
export ALIEN_JDL_LPMANCHORYEAR=${ALIEN_JDL_LPMANCHORYEAR:-${ANCHORYEAR}}
# decide whether to run TPC time series; on by default, switched off by setting to 0
export ALIEN_JDL_ADDTIMESERIESINMC=${ALIEN_JDL_ADDTIMESERIESINMC:-1}

# cache the production tag, will be set to a special anchor tag; reset later in fact
ALIEN_JDL_LPMPRODUCTIONTAG_KEEP=$ALIEN_JDL_LPMPRODUCTIONTAG
echo_info "Substituting ALIEN_JDL_LPMPRODUCTIONTAG=$ALIEN_JDL_LPMPRODUCTIONTAG with ALIEN_JDL_LPMANCHORPRODUCTION=$ALIEN_JDL_LPMANCHORPRODUCTION for simulating reco pass..."
ALIEN_JDL_LPMPRODUCTIONTAG=$ALIEN_JDL_LPMANCHORPRODUCTION

# check variables that need to be set
[ -z "${ALIEN_JDL_LPMANCHORPASSNAME}" ] && { echo_error "Set ALIEN_JDL_LPMANCHORPASSNAME or ANCHORPASSNAME" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMRUNNUMBER}" ] && { echo_error "Set ALIEN_JDL_LPMRUNNUMBER or RUNNUMBER" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMPRODUCTIONTYPE}" ] && { echo_error "Set ALIEN_JDL_LPMPRODUCTIONTYPE or PRODUCTIONTYPE" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMINTERACTIONTYPE}" ] && { echo_error "Set ALIEN_JDL_LPMINTERACTIONTYPE or INTERACTIONTYPE" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMPRODUCTIONTAG}" ] && { echo_error "Set ALIEN_JDL_LPMPRODUCTIONTAG or PRODUCTIONTAG" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMANCHORRUN}" ] && { echo_error "Set ALIEN_JDL_LPMANCHORRUN or ANCHORRUN" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMANCHORPRODUCTION}" ] && { echo_error "Set ALIEN_JDL_LPMANCHORPRODUCTION or ANCHORPRODUCTION" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMANCHORYEAR}" ] && { echo_error "Set ALIEN_JDL_LPMANCHORYEAR or ANCHORYEAR" ; exit 1 ; }

[ -z "${NTIMEFRAMES}" ] && { echo_error "Set NTIMEFRAMES" ; exit 1 ; }
[ -z "${NSIGEVENTS}" ] && { echo_error "Set NSIGEVENTS" ; exit 1 ; }
[ -z "${SPLITID}" ] && { echo_error "Set SPLITID" ; exit 1 ; }
[ -z "${CYCLE}" ] && { echo_error "Set CYCLE" ; exit 1 ; }
[ -z "${PRODSPLIT}" ] && { echo_error "Set PRODSPLIT" ; exit 1 ; }

# also for this keep a real default
NWORKERS=${NWORKERS:-8}
# set a default seed if not given
SEED=${ALIEN_PROC_ID:-${SEED:-1}}


# default async_pass.sh script
DPGRECO=$O2DPG_ROOT/DATA/production/configurations/asyncReco/async_pass.sh
# default destenv_extra.sh script
DPGSETENV=$O2DPG_ROOT/DATA/production/configurations/asyncReco/setenv_extra.sh

# a specific async_pass.sh script is in the current directory, assume that one should be used
if [[ -f async_pass.sh ]]; then
    # the default is executable, however, this may not be, so make it so
    chmod +x async_pass.sh
    DPGRECO=./async_pass.sh
else
    cp -v $DPGRECO .
fi

# if there is no setenv_extra.sh in this directory (so no special version is "shipped" with this rpodcution), copy the default one
if [[ ! -f setenv_extra.sh ]] ; then
    cp ${DPGSETENV} .
    echo_info "Use default setenv_extra.sh from ${DPGSETENV}."
else
    echo_info "setenv_extra.sh was found in the current working directory, use it."
fi

chmod u+x setenv_extra.sh

echo_info "Setting up DPGRECO to ${DPGRECO}"

# settings that are MC-specific, modify setenv_extra.sh in-place
sed -i 's/GPU_global.dEdxUseFullGainMap=1;GPU_global.dEdxDisableResidualGainMap=1/GPU_global.dEdxSplineTopologyCorrFile=splines_for_dedx_V1_MC_iter0_PP.root;GPU_global.dEdxDisableTopologyPol=1;GPU_global.dEdxDisableGainMap=1;GPU_global.dEdxDisableResidualGainMap=1;GPU_global.dEdxDisableResidualGain=1/' setenv_extra.sh
### ???

# take out line running the workflow (if we don't have data input)
[ ${CTF_TEST_FILE} ] || sed -i '/WORKFLOWMODE=run/d' async_pass.sh

# create workflow ---> creates the file that can be parsed
export IGNORE_EXISTING_SHMFILES=1
touch list.list

# run the async_pass.sh and store output to log file for later inspection and extraction of information
./async_pass.sh ${CTF_TEST_FILE:-""} 2&> async_pass_log.log
RECO_RC=$?

echo_info "async_pass.sh finished with ${RECO_RC}"

if [[ "${RECO_RC}" != "0" ]] ; then
    exit ${RECO_RC}
fi

ALIEN_JDL_LPMPRODUCTIONTAG=$ALIEN_JDL_LPMPRODUCTIONTAG_KEEP
echo_info "Setting back ALIEN_JDL_LPMPRODUCTIONTAG to $ALIEN_JDL_LPMPRODUCTIONTAG"

# now create the local MC config file --> config-config.json
${O2DPG_ROOT}/UTILS/parse-async-WorkflowConfig.py
ASYNC_WF_RC=${?}

# check if config reasonably created
if [[ "${ASYNC_WF_RC}" != "0" || `grep "o2-ctf-reader-workflow-options" config-json.json 2> /dev/null | wc -l` == "0" ]]; then
  echo_error "Problem in anchor config creation. Exiting."
  exit 1
fi

# -- CREATE THE MC JOB DESCRIPTION ANCHORED TO RUN --

MODULES="--skipModules ZDC"
# Since this is used, set it explicitly
ALICEO2_CCDB_LOCALCACHE=${ALICEO2_CCDB_LOCALCACHE:-$(pwd)/ccdb}

# these arguments will be digested by o2dpg_sim_workflow_anchored.py
baseargs="-tf ${NTIMEFRAMES} --split-id ${SPLITID} --prod-split ${PRODSPLIT} --cycle ${CYCLE} --run-number ${ALIEN_JDL_LPMRUNNUMBER}"

# these arguments will be passed as well but only evetually be digested by o2dpg_sim_workflow.py which is called from o2dpg_sim_workflow_anchored.py
remainingargs="-seed ${SEED} -ns ${NSIGEVENTS} --include-local-qc --pregenCollContext"
remainingargs="${remainingargs} -e ${ALIEN_JDL_SIMENGINE} -j ${NWORKERS}"
remainingargs="${remainingargs} -productionTag ${ALIEN_JDL_LPMPRODUCTIONTAG:-alibi_anchorTest_tmp}"
# prepend(!) ALIEN_JDL_ANCHOR_SIM_OPTIONS
# since the last passed argument wins, e.g. -productionTag cannot be overwritten by the user
remainingargs="${ALIEN_JDL_ANCHOR_SIM_OPTIONS} ${remainingargs} --anchor-config config-json.json"

echo_info "baseargs passed to o2dpg_sim_workflow_anchored.py: ${baseargs}"
echo_info "remainingargs forwarded to o2dpg_sim_workflow.py: ${remainingargs}"

# query CCDB has changed, w/o "_"
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow_anchored.py ${baseargs} -- ${remainingargs} &> timestampsampling_${ALIEN_JDL_LPMRUNNUMBER}.log
WF_RC="${?}"
if [ "${WF_RC}" != "0" ] ; then
    echo_error "Problem during anchor timestamp sampling and workflow creation. Exiting."
    exit ${WF_RC}
fi

TIMESTAMP=`grep "Determined timestamp to be" timestampsampling_${ALIEN_JDL_LPMRUNNUMBER}.log | awk '//{print $6}'`
echo_info "TIMESTAMP IS ${TIMESTAMP}"

# -- Create aligned geometry using ITS ideal alignment to avoid overlaps in geant
CCDBOBJECTS_IDEAL_MC="ITS/Calib/Align"
TIMESTAMP_IDEAL_MC=1
${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch/ -p ${CCDBOBJECTS_IDEAL_MC} -d ${ALICEO2_CCDB_LOCALCACHE} --timestamp ${TIMESTAMP_IDEAL_MC}
CCDB_RC="${?}"
if [ ! "${CCDB_RC}" == "0" ]; then
  echo_error "Problem during CCDB prefetching of ${CCDBOBJECTS_IDEAL_MC}. Exiting."
  exit ${CCDB_RC}
fi

# TODO This can potentially be removed or if needed, should be taken over by o2dpg_sim_workflow_anchored.py and O2_dpg_workflow_runner.py
echo "run with echo in pipe" | ${O2_ROOT}/bin/o2-create-aligned-geometry-workflow --configKeyValues "HBFUtils.startTime=${TIMESTAMP}" --condition-remap=file://${ALICEO2_CCDB_LOCALCACHE}=ITS/Calib/Align -b --run
mkdir -p $ALICEO2_CCDB_LOCALCACHE/GLO/Config/GeometryAligned
ln -s -f $PWD/o2sim_geometry-aligned.root $ALICEO2_CCDB_LOCALCACHE/GLO/Config/GeometryAligned/snapshot.root
[[ -f $PWD/its_GeometryTGeo.root ]] && mkdir -p $ALICEO2_CCDB_LOCALCACHE/ITS/Config/Geometry && ln -s -f $PWD/its_GeometryTGeo.root $ALICEO2_CCDB_LOCALCACHE/ITS/Config/Geometry/snapshot.root
[[ -f $PWD/mft_GeometryTGeo.root ]] && mkdir -p $ALICEO2_CCDB_LOCALCACHE/MFT/Config/Geometry && ln -s -f $PWD/mft_GeometryTGeo.root $ALICEO2_CCDB_LOCALCACHE/MFT/Config/Geometry/snapshot.root

# -- RUN THE MC WORKLOAD TO PRODUCE AOD --

export FAIRMQ_IPC_PREFIX=./

echo_info "Ready to start main workflow"

${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt ${ALIEN_JDL_O2DPGWORKFLOWTARGET:-aod} --cpu-limit ${ALIEN_JDL_CPULIMIT:-8} --dynamic-resources
MCRC=$?  # <--- we'll report back this code
if [[ "${ALIEN_JDL_ADDTIMESERIESINMC}" != "0" ]]; then
  # Default value is 1 so this is run by default.
  echo_info "Running TPC time series"
  ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt tpctimes
fi

[[ ! -z "${DISABLE_QC}" ]] && echo_info "QC is disabled, skip it."

if [[ -z "${DISABLE_QC}" && "${MCRC}" = "0" && "${remainingargs}" == *"--include-local-qc"* ]] ; then
  # do QC tasks
  echo_info "Doing QC"
  ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --target-labels QC --cpu-limit ${ALIEN_JDL_CPULIMIT:-8} -k
  # NOTE that with the -k|--keep-going option, the runner will try to keep on executing even if some tasks fail.
  # That means, even if there is a failing QC task, the return code will be 0
  MCRC=$?
fi

#
# full logs tar-ed for output, regardless the error code or validation - to catch also QC logs...
#
if [[ -n "$ALIEN_PROC_ID" ]]; then
  find ./ \( -name "*.log*" -o -name "*mergerlog*" -o -name "*serverlog*" -o -name "*workerlog*" -o -name "pythia8.cfg" \) | tar -czvf debug_log_archive.tgz -T -
  if [[ "$ALIEN_JDL_CREATE_TAR_IN_MC" == "1" ]]; then
    find ./ \( -name "*.log*" -o -name "*mergerlog*" -o -name "*serverlog*" -o -name "*workerlog*" -o -name "*.root" \) | tar -czvf debug_full_archive.tgz -T -
  fi
fi

unset FAIRMQ_IPC_PREFIX

exit ${MCRC}
