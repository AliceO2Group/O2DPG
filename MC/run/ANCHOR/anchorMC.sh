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
  echo "SPLITID,"
  echo "PRODSPLIT."
  echo
  echo "Optional are:"
  echo "ALIEN_JDL_CPULIMIT or CPULIMIT, set the CPU limit of the workflow runner, default: 8,"
  echo "NWORKERS, set the number of workers during detector transport, default: 8,"
  echo "ALIEN_JDL_SIMENGINE or SIMENGINE, choose the transport engine, default: TGeant4,"
  echo "ALIEN_JDL_WORKFLOWDETECTORS, set detectors to be taken into account, default: not-used (take the ones from async-reco)"
  echo "ALIEN_JDL_ANCHOR_SIM_OPTIONS, additional options that are passed to the workflow creation, default: -gen pythia8,"
  echo "ALIEN_JDL_ADDTIMESERIESINMC, run TPC time series. Default: 1, switch off by setting to 0,"
  echo "ALIEN_JDL_MC_ORBITS_PER_TF=N, enforce some orbits per timeframe, instead of determining from CCDB"
  echo "ALIEN_JDL_RUN_TIME_SPAN_FILE=FILE, use a run-time-span file to exclude bad data-taking periods"
  echo "ALIEN_JDL_INVERT_IRFRAME_SELECTION, invertes the choice of ALIEN_JDL_RUN_TIME_SPAN_FILE"
  echo "ALIEN_JDL_CCDB_CONDITION_NOT_AFTER, sets the condition_not_after timestamp for CCDB queries"
  echo "DISABLE_QC, set this to disable QC, e.g. to 1"
  echo "CYCLE, to set a cycle number different than 0"
  echo "NSIGEVENTS, to enforce a specific upper limit of events in a timeframe (not counting orbit-early) events"
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

# check for presence of essential variables that need to be set
[ -z "${ALIEN_JDL_LPMANCHORPASSNAME}" ] && { echo_error "Set ALIEN_JDL_LPMANCHORPASSNAME or ANCHORPASSNAME" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMRUNNUMBER}" ] && { echo_error "Set ALIEN_JDL_LPMRUNNUMBER or RUNNUMBER" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMPRODUCTIONTYPE}" ] && { echo_error "Set ALIEN_JDL_LPMPRODUCTIONTYPE or PRODUCTIONTYPE" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMINTERACTIONTYPE}" ] && { echo_error "Set ALIEN_JDL_LPMINTERACTIONTYPE or INTERACTIONTYPE" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMPRODUCTIONTAG}" ] && { echo_error "Set ALIEN_JDL_LPMPRODUCTIONTAG or PRODUCTIONTAG" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMANCHORRUN}" ] && { echo_error "Set ALIEN_JDL_LPMANCHORRUN or ANCHORRUN" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMANCHORPRODUCTION}" ] && { echo_error "Set ALIEN_JDL_LPMANCHORPRODUCTION or ANCHORPRODUCTION" ; exit 1 ; }
[ -z "${ALIEN_JDL_LPMANCHORYEAR}" ] && { echo_error "Set ALIEN_JDL_LPMANCHORYEAR or ANCHORYEAR" ; exit 1 ; }

[ -z "${NTIMEFRAMES}" ] && { echo_error "Set NTIMEFRAMES" ; exit 1 ; }
[ -z "${SPLITID}" ] && { echo_error "Set SPLITID" ; exit 1 ; }
[ -z "${PRODSPLIT}" ] && { echo_error "Set PRODSPLIT" ; exit 1 ; }


# cache the production tag, will be set to a special anchor tag; reset later in fact
ALIEN_JDL_LPMPRODUCTIONTAG_KEEP=$ALIEN_JDL_LPMPRODUCTIONTAG
echo_info "Substituting ALIEN_JDL_LPMPRODUCTIONTAG=$ALIEN_JDL_LPMPRODUCTIONTAG with ALIEN_JDL_LPMANCHORPRODUCTION=$ALIEN_JDL_LPMANCHORPRODUCTION for simulating reco pass..."
ALIEN_JDL_LPMPRODUCTIONTAG=$ALIEN_JDL_LPMANCHORPRODUCTION

if [[ $ALIEN_JDL_ANCHOR_SIM_OPTIONS == *"--tpc-distortion-type 2"* ]]; then
  export O2DPG_ENABLE_TPC_DISTORTIONS=ON
  # set the SCALING SOURCE to CTP for MC unless explicitely given from outside
  export ALIEN_JDL_TPCSCALINGSOURCE=${ALIEN_JDL_TPCSCALINGSOURCE:-"CTP"}
fi


# The number of signal events can be given, but should be useful only in
# certain expert modes. In the default case, the final event number is determined by the timeframe length.
if [ -z "${NSIGEVENTS}" ]; then
  NSIGEVENTS=10000 # this is just some big number; In the simulation the event number is the minimum of this number and what fits into a single timeframe
                   # based on the interaction rate. The number is a reasonable upper limit related to ~5696 collisions that fit into 32 LHC orbits at 2MHz interaction rate.
fi

if [ -z "${CYCLE}" ]; then
  echo_info "No CYCLE number given ... defaulting to 0"
  CYCLE=0
fi

# this generates an exact reproducer script for this job
# that can be used locally for debugging etc.
if [[ -n "${ALIEN_PROC_ID}" && -n "${JALIEN_WSPORT}" ]]; then
  ${O2DPG_ROOT}/GRID/utils/getReproducerScript.sh ${ALIEN_PROC_ID}
fi

# also for this keep a real default
NWORKERS=${NWORKERS:-8}
# set a default seed if not given
SEED=${ALIEN_PROC_ID:-${SEED:-1}}

ONCVMFS=0

if [ "${ALIEN_JDL_O2DPG_OVERWRITE}" ]; then
  echo "Setting O2DPG_ROOT to overwritten path ${ALIEN_JDL_O2DPG_OVERWRITE}"
  export O2DPG_ROOT=${ALIEN_JDL_O2DPG_OVERWRITE}
fi

export > env_base.env

if ! declare -F module > /dev/null; then
  module() {
    eval "$(/usr/bin/modulecmd bash "$@")";
  }
  export -f module
fi

[[ "${BASEDIR}" == /cvmfs/* ]] && ONCVMFS=1
if [ ! "${MODULEPATH}" ]; then
  export MODULEPATH=${BASEDIR}/../Modules/modulefiles
  if [ "${ONCVMFS}" == "1" ]; then
    PLATFORM=$(echo "${BASEDIR}" | sed -E 's|.*/([^/]+)/Packages|\1|')
    export MODULEPATH=${MODULEPATH}:${BASEDIR}/../../etc/toolchain/modulefiles/${PLATFORM}
  fi
  echo "Determined Modulepath to be ${MODULEPATH}"
fi

#<----- START OF part that should run under a clean alternative software environment if this was given ------
if [ "${ALIEN_JDL_O2DPG_ASYNC_RECO_TAG}" ]; then
  if [ "${LOADEDMODULES}" ]; then
    printenv > env_before_stashing.printenv
    echo "Stashing initial modules"
    module save initial_modules.list # we stash the current modules environment
    module list --no-pager
    module purge --no-pager
    printenv > env_after_stashing.printenv
    echo "Modules after purge"
    module list --no-pager
  fi
  echo_info "Using tag ${ALIEN_JDL_O2DPG_ASYNC_RECO_TAG} to setup anchored MC"
  /cvmfs/alice.cern.ch/bin/alienv printenv "${ALIEN_JDL_O2DPG_ASYNC_RECO_TAG}" &> async_environment.env
  source async_environment.env
  export > env_async.env
fi

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

# check that workflowconfig.log was created correctly
if [[ ! -f workflowconfig.log ]]; then
  echo "Workflowconfig.log file not found"
  exit 1
fi

export ALIEN_JDL_LPMPRODUCTIONTAG=$ALIEN_JDL_LPMPRODUCTIONTAG_KEEP
echo_info "Setting back ALIEN_JDL_LPMPRODUCTIONTAG to $ALIEN_JDL_LPMPRODUCTIONTAG"

# get rid of the temporary software environment
if [ "${ALIEN_JDL_O2DPG_ASYNC_RECO_TAG}" ]; then
  module purge --no-pager
  # restore the initial software environment
  echo "Restoring initial environment"
  module --no-pager restore initial_modules.list
  module saverm initial_modules.list

  # Restore overwritten O2DPG variables set by modules but changed by user
  # (in particular custom O2DPG_ROOT and O2DPG_MC_CONFIG_ROOT)
  printenv > env_after_restore.printenv
  comm -12 <(grep '^O2DPG' env_before_stashing.printenv | cut -d= -f1 | sort) \
         <(grep '^O2DPG' env_after_restore.printenv  | cut -d= -f1 | sort) |
  while read -r var; do
    b=$(grep "^$var=" env_before_stashing.printenv | cut -d= -f2-)
    a=$(grep "^$var=" env_after_restore.printenv  | cut -d= -f2-)
    [[ "$b" != "$a" ]] && export "$var=$b" && echo "Reapplied: $var to ${b}"
  done
fi
#<----- END OF part that should run under a clean alternative software environment if this was given ------

# now create the local MC config file --> config-json.json
# we create the new config output with blacklist functionality
ASYNC_CONFIG_BLACKLIST=${ASYNC_CONFIG_BLACKLIST:-${O2DPG_ROOT}/MC/run/ANCHOR/anchor-dpl-options-blacklist.json}
${O2DPG_ROOT}/MC/bin/o2dpg_dpl_config_tools.py workflowconfig.log ${ASYNC_CONFIG_BLACKLIST} config-json.json
ASYNC_WF_RC=${?}

# check if config reasonably created
if [[ "${ASYNC_WF_RC}" != "0" || `grep "ConfigParams" config-json.json 2> /dev/null | wc -l` == "0" ]]; then
  echo_error "Problem in anchor config creation. Exiting."
  exit 1
fi

# -- CREATE THE MC JOB DESCRIPTION ANCHORED TO RUN --

MODULES="--skipModules ZDC"

# publish MCPRODINFO for first few jobs of a production
# if external script exported PUBLISH_MCPRODINFO, it will be published anyways
if [ -z "$PUBLISH_MCPRODINFO" ] && [ "$SPLITID" -lt 20 ]; then
  PUBLISH_MCPRODINFO_OPTION="--publish-mcprodinfo"
  echo "Will publish MCProdInfo"
else
  echo "Will not publish MCProdInfo"
fi

# these arguments will be digested by o2dpg_sim_workflow_anchored.py
baseargs="-tf ${NTIMEFRAMES} --split-id ${SPLITID} --prod-split ${PRODSPLIT} --cycle ${CYCLE} --run-number ${ALIEN_JDL_LPMRUNNUMBER}                                \
          ${ALIEN_JDL_RUN_TIME_SPAN_FILE:+--run-time-span-file ${ALIEN_JDL_RUN_TIME_SPAN_FILE} ${ALIEN_JDL_INVERT_IRFRAME_SELECTION:+--invert-irframe-selection}}   \
          ${ALIEN_JDL_MC_ORBITS_PER_TF:+--orbitsPerTF ${ALIEN_JDL_MC_ORBITS_PER_TF}} ${PUBLISH_MCPRODINFO_OPTION}"

# these arguments will be passed as well but only eventually be digested by o2dpg_sim_workflow.py which is called from o2dpg_sim_workflow_anchored.py
remainingargs="-seed ${SEED} -ns ${NSIGEVENTS} --include-local-qc --pregenCollContext"
remainingargs="${remainingargs} -e ${ALIEN_JDL_SIMENGINE} -j ${NWORKERS}"
remainingargs="${remainingargs} -productionTag ${ALIEN_JDL_LPMPRODUCTIONTAG:-alibi_anchorTest_tmp}"
# prepend(!) ALIEN_JDL_ANCHOR_SIM_OPTIONS
# since the last passed argument wins, e.g. -productionTag cannot be overwritten by the user
remainingargs="${ALIEN_JDL_ANCHOR_SIM_OPTIONS} ${remainingargs} --anchor-config config-json.json"
# apply software tagging choice
# remainingargs="${remainingargs} ${ALIEN_JDL_O2DPG_ASYNC_RECO_TAG:+--alternative-reco-software ${ALIEN_JDL_O2DPG_ASYNC_RECO_TAG}}"
ALIEN_JDL_O2DPG_ASYNC_RECO_FROMSTAGE=${ALIEN_JDL_O2DPG_ASYNC_RECO_FROMSTAGE:-RECO}
remainingargs="${remainingargs} ${ALIEN_JDL_O2DPG_ASYNC_RECO_TAG:+--alternative-reco-software ${PWD}/env_async.env@${ALIEN_JDL_O2DPG_ASYNC_RECO_FROMSTAGE}}"
# potentially add CCDB timemachine timestamp
remainingargs="${remainingargs} ${ALIEN_JDL_CCDB_CONDITION_NOT_AFTER:+--condition-not-after ${ALIEN_JDL_CCDB_CONDITION_NOT_AFTER}}"

echo_info "baseargs passed to o2dpg_sim_workflow_anchored.py: ${baseargs}"
echo_info "remainingargs forwarded to o2dpg_sim_workflow.py: ${remainingargs}"

anchoringLogFile=timestampsampling_${ALIEN_JDL_LPMRUNNUMBER}.log
# query CCDB has changed, w/o "_"
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow_anchored.py ${baseargs} -- ${remainingargs} &> ${anchoringLogFile}
WF_RC="${?}"
if [ "${WF_RC}" != "0" ] ; then
    echo_error "Problem during anchor timestamp sampling and workflow creation. Exiting."
    exit ${WF_RC}
fi

TIMESTAMP=`grep "Determined timestamp to be" ${anchoringLogFile} | awk '//{print $6}'`
echo_info "TIMESTAMP IS ${TIMESTAMP}"

if [ "${ONLY_WORKFLOW_CREATION}" ]; then
  exit 0
fi

# check if this job is exluded because it falls inside a bad data-taking period
ISEXCLUDED=$(grep "TIMESTAMP IS EXCLUDED IN RUN" ${anchoringLogFile})
if [ "${ISEXCLUDED}" ]; then
  # we can quit here; there is nothing to do
  # (apart from maybe creating a fake empty AO2D.root file or the like)
  echo "Timestamp is excluded from run. Nothing to do here"
  exit 0
fi

# -- RUN THE MC WORKLOAD TO PRODUCE TARGETS --

export FAIRMQ_IPC_PREFIX=./

echo_info "Ready to start main workflow"

# Let us construct the workflow targets
targetString=""
if [ "${ALIEN_JDL_O2DPGWORKFLOWTARGET}" ]; then
   # The user gave ${ALIEN_JDL_O2DPGWORKFLOWTARGET}. This is an expert mode not used in production.
   # In this case, we will build just that. No QC, no TPC timeseries, ...
   targetString=${ALIEN_JDL_O2DPGWORKFLOWTARGET}
else
   targetString="'aodmerge.*'"
   # Now add more targets depending on options
   # -) The TPC timeseries targets
   if [[ "${ALIEN_JDL_ADDTIMESERIESINMC}" == "1" ]]; then
     targetString="${targetString} 'tpctimes.*'"
   fi
   # -) TPC residual calibration
   if [ "${ALIEN_JDL_DOTPCRESIDUALEXTRACTION}" ]; then
     targetString="${targetString} 'tpcresidmerge.*'"
   fi
   # -) QC tasks
   if [[ -z "${DISABLE_QC}" && "${remainingargs}" == *"--include-local-qc"* ]]; then
     targetString="${targetString} '^.*QC.*'" # QC tasks should have QC in the name
   fi
fi
echo_info "Workflow will run with target specification ${targetString}"

${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt ${targetString}                                    \
                                               --cpu-limit ${ALIEN_JDL_CPULIMIT:-8} --dynamic-resources                \
                                               ${ALIEN_O2DPG_FILEGRAPH:+--remove-files-early ${ALIEN_O2DPG_FILEGRAPH}} \
                                               ${ALIEN_O2DPG_ADDITIONAL_WORKFLOW_RUNNER_ARGS}

MCRC=$?  # <--- we'll report back this code

#
# full logs tar-ed for output, regardless the error code or validation - to catch also QC logs...
#
if [[ -n "$ALIEN_PROC_ID" ]]; then
  find ./ \( -name "*.log*" -o -name "*mergerlog*" -o -name "*serverlog*" -o -name "*workerlog*" -o -name "pythia8.cfg" -o -name "reproducer*.sh" \) | tar -czvf debug_log_archive.tgz -T -
  if [[ "$ALIEN_JDL_CREATE_TAR_IN_MC" == "1" ]]; then
    find ./ \( -name "*.log*" -o -name "*mergerlog*" -o -name "*serverlog*" -o -name "*workerlog*" -o -name "*.root" \) | tar -czvf debug_full_archive.tgz -T -
  fi
fi

unset FAIRMQ_IPC_PREFIX

exit ${MCRC}
