#!/bin/bash

# The test parent dir to be cretaed in current directory
TEST_PARENT_DIR_PWG="o2dpg_tests/workflows_pwgs"
TEST_PARENT_DIR_BIN="o2dpg_tests/workflows_bin"
TEST_PARENT_DIR_ANCHORED="o2dpg_tests/anchored"

# a global counter for tests
TEST_COUNTER=0

# unified names of log files
LOG_FILE_WF="o2dpg-test-wf.log"
LOG_FILE_ANCHORED="o2dpg-test-anchored.log"

# Prepare some colored output
SRED="\033[0;31m"
SGREEN="\033[0;32m"
SEND="\033[0m"


echo_green()
{
    echo -e "${SGREEN}$@${SEND}"
}


echo_red()
{
    echo -e "${SRED}$@${SEND}"
}

get_git_repo_directory()
{
    local repo=
    if [[ -d .git ]] ; then
        pwd
    else
        repo=$(git rev-parse --git-dir 2> /dev/null)
    fi
    [[ "${repo}" != "" ]] && repo=${repo%%/.git}
    echo ${repo}
}


get_all_workflows()
{
    # Collect also those INI files for which the test has been changed
    local repo_dir_head=${REPO_DIR}
    local grep_dir=${1}
    local all_workflows=$(find ${repo_dir_head} -name "*.sh" | grep "${grep_dir}")
    echo ${all_workflows}
}


test_single_wf()
{
    local wf_script=${1}
    local execute=${2}
    make_wf_creation_script ${wf_script} ${wf_script_local}
    local has_wf_script_local=${?}
    echo -n "Test ${TEST_COUNTER}: ${wfs}"
    [[ "${has_wf_script_local}" != "0" ]] && { echo "No WF creation in script ${wfs} ##########" ; return 1 ; }
    # Check if there is an "exit" other than the usual
    # [ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
    # like ones.
    # This is not perfect but might prevent us from running into some checks the WF script does before launching the WF creation
    [[ "$(grep exit ${wf_script_local} | grep -v "This needs")" != "" ]] && { echo -e -n "\nFound \"exit\" in ${wfs} so will not test automatically" ; return 0 ; }
    # one single test
    echo "Test ${wf_line} from ${wfs}" > ${LOG_FILE_WF}
    bash ${wf_script_local} >> ${LOG_FILE_WF} 2>&1
    local ret_this=${?}
    local ret_this_qc=0
    local ret_this_analysis=0
    if [[ "${ret_this}" != "0" ]] ; then
        echo "[FATAL]: O2DPG_TEST Workflow creation failed" >> ${LOG_FILE_WF}
    elif [[ "${execute}" != "" ]] ; then
        ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --cpu-limit 8 -tt aod >> ${LOG_FILE_WF} 2>&1
        ret_this=${?}
        [[ "${ret_this}" == "0" ]] && { ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --cpu-limit 8 --target-labels QC >> ${LOG_FILE_WF} 2>&1 ; ret_this_qc=${?} ; }
        [[ "${ret_this}" == "0" ]] && { ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --cpu-limit 8 --target-labels Analysis >> ${LOG_FILE_WF} 2>&1 ; ret_this_analysis=${?} ; }
        ret_this=$((ret_this + ret_this_qc + ret_this_analysis))
        [[ "${ret_this}" != "0" ]] && echo "[FATAL]: O2DPG_TEST Workflow execution failed" >> ${LOG_FILE_WF}
    fi
    return ${ret_this}
}

run_workflow_creation()
{
    local wf_scripts=
    local execute=
    while [ "$1" != "" ] ; do
        case $1 in
            --execute ) shift
                        execute=1
                        ;;
            * )         wf_scripts+="${1} "
                        shift
                        ;;
        esac
    done

    local RET=0
    local wf_script_local="wf.sh"

    for wfs in ${wf_scripts} ; do
        local wf_line=$(get_workflow_creation_from_script ${wfs})
        [[ "${wf_line}" == "" ]] && continue

        ((TEST_COUNTER++))
        local test_dir=${TEST_COUNTER}_$(basename ${wfs})_dir
        rm -rf ${test_dir} 2> /dev/null
        mkdir ${test_dir}
        pushd ${test_dir} > /dev/null
            test_single_wf ${wfs} ${execute}
            local ret_this=${?}
            [[ "${ret_this}" != "0" ]] && RET=${ret_this}
        popd > /dev/null
        if [[ "${ret_this}" != "0" ]] ; then
            echo_red " -> FAILED"
        else
            echo_green " -> PASSED"
        fi
    done

    return ${RET}
}

test_anchored()
{
    local to_run="${1:-${O2DPG_ROOT}/MC/run/ANCHOR/tests/test_anchor_2023_apass2_pp.sh}"
    local RET=0
    for anchored_script in ${to_run} ; do
        [[ ! -f ${anchored_script} ]] && { echo "Desired test script ${anchored_script} does not exist. Skip." ; continue ; }
        ((TEST_COUNTER++))
        local test_dir=${TEST_COUNTER}_$(basename ${anchored_script})_dir
        rm -rf ${test_dir} 2> /dev/null
        mkdir ${test_dir}
        pushd ${test_dir} > /dev/null
            echo -n "Test ${TEST_COUNTER}: ${anchored_script}"
            ${anchored_script} >> ${LOG_FILE_ANCHORED} 2>&1
            local ret_this=${?}
            [[ "${ret_this}" != "0" ]] && RET=${ret_this}
        popd > /dev/null
    done
    return ${RET}
}

collect_changed_pwg_wf_files()
{
    # Collect all INI files which have changed
    local wf_scripts=$(get_changed_files | grep ".sh$" | grep "MC/run")
    for wfs in ${wf_scripts} ; do
        [[ "${WF_FILES}" == *"${wfs}"* ]] && continue || WF_FILES+=" ${wfs} "
    done
}

print_usage()
{
    echo
    echo "usage: run_workflow_tests.sh"
    echo
    echo "  ENVIRONMENT VARIABLES:"
    echo
    echo "  O2DPG_TEST_REPO_DIR : Point to the source repository you want to test."
    echo "  O2DPG_TEST_HASH_BASE : The base hash you want to use for comparison (optional)"
    echo "  O2DPG_TEST_HASH_HEAD : The head hash you want to use for comparison (optional)"
    echo
    echo "  If O2DPG_TEST_HASH_BASE is not set, it will be looked for ALIBUILD_BASE_HASH."
    echo "  If also not set, this will be set to HEAD~1. However, if there are unstaged"
    echo "  changes, it will be set to HEAD."
    echo
    echo "  If O2DPG_TEST_HASH_HEAD is not set, it will be looked for ALIBUILD_HEAD_HASH."
    echo "  If also not set, this will be set to HEAD. However, if there are unstaged"
    echo "  changes, it will left blank."
    echo
}

while [ "$1" != "" ] ; do
    case $1 in
        --help|-h )          print_usage
                             exit 1
                             ;;
        * )                  echo "Unknown argument ${1}"
                             exit 1
                             ;;
    esac
done

echo
echo "##############################"
echo "# Run O2DPG workflow testing #"
echo "##############################"
echo

REPO_DIR=${O2DPG_TEST_REPO_DIR:-$(get_git_repo_directory)}
if [[ ! -d ${REPO_DIR}/.git ]] ; then
    echo_red "Directory \"${REPO_DIR}\" is not a git repository."
    exit 1
fi

if [[ -z ${O2DPG_ROOT+x} ]] ; then
    echo_red "O2DPG is not loaded, probably other packages are missing as well in this environment."
    exit 1
fi

# source the utilities
source ${REPO_DIR}/test/common/utils/utils.sh

# Do the initial steps in the source dir where we have the full git repo
pushd ${REPO_DIR} > /dev/null

# flag if anything changed in the sim workflow bin dir
changed_wf_bin=$(get_changed_files | grep -E "MC/bin")
changed_wf_bin_related=$(get_changed_files | grep -E "MC/analysis_testing|MC/config/analysis_testing/json|MC/config/QC/json")
changed_anchored_related=$(get_changed_files | grep -E "MC/run/ANCHOR/anchorMC.sh|MC/run/ANCHOR/tests|MC/bin|UTILS/parse-async-WorkflowConfig.py")


# collect what has changed for PWGs
collect_changed_pwg_wf_files

# get realpaths for all changes
wf_files_tmp=${WF_FILES}
WF_FILES=
for wf_tmp in ${wf_files_tmp} ; do
    # convert to full path so that we can find it from anywhere
    WF_FILES+="$(realpath ${wf_tmp}) "
done

# go back to where we came from
popd > /dev/null
REPO_DIR=$(realpath ${REPO_DIR})

# Now, do the trick:
# We just use the source dir since O2DPG's installation is basically just a copy of the whole repo.
# This makes sense in particular for local testing but also in the CI it works in the same way. We could do
#         [[ -z {ALIBUILD_HEAD_HASH+x} ]] && export O2DPG_ROOT=${REPO_DIR}
# but let's do the same for both local and CI consistently
export O2DPG_ROOT=${REPO_DIR}


###############
# ANCHORED MC #
###############
# prepare our local test directory for PWG tests
rm -rf ${TEST_PARENT_DIR_ANCHORED} 2>/dev/null
mkdir -p ${TEST_PARENT_DIR_ANCHORED} 2>/dev/null
pushd ${TEST_PARENT_DIR_ANCHORED} > /dev/null

# global return code for PWGs
ret_global_anchored=0
if [[ "${changed_anchored_related}" != "" ]] ; then
    echo "### Test anchored ###"
    # Run an anchored test
    test_anchored
    ret_global_anchored=${?}
    echo
fi

# return to where we came from
popd > /dev/null

########
# PWGs #
########
# prepare our local test directory for PWG tests
rm -rf ${TEST_PARENT_DIR_PWG} 2>/dev/null
mkdir -p ${TEST_PARENT_DIR_PWG} 2>/dev/null
pushd ${TEST_PARENT_DIR_PWG} > /dev/null

# global return code for PWGs
ret_global_pwg=0
if [[ "${changed_wf_bin}" != "" ]] ; then
    # Run all the PWG related WF creations, hence overwrite what was collected by collect_changed_pwg_wf_files earlier
    WF_FILES=$(get_all_workflows "MC/run/.*/")
    echo
fi

# Test what we found
if [[ "${WF_FILES}" != "" ]] ; then
    echo "### Test PWG-related workflow creation ###"
    echo
    run_workflow_creation ${WF_FILES}
    ret_global_pwg=${?}
    echo
fi

# return to where we came from
popd > /dev/null

####################
# sim workflow bin #
####################
# prepare our local test directory for bin tests
rm -rf ${TEST_PARENT_DIR_BIN} 2>/dev/null
mkdir -p ${TEST_PARENT_DIR_BIN} 2>/dev/null
pushd ${TEST_PARENT_DIR_BIN} > /dev/null

# global return code for PWGs
ret_global_bin=0
if [[ "${changed_wf_bin}" != "" || "${changed_wf_bin_related}" != "" ]] ; then
    echo "### Test bin-related workflow creation ###"
    echo
    # Run all the bin test WF creations
    run_workflow_creation $(get_all_workflows "MC/bin/tests") --execute
    ret_global_bin=${?}
    echo
fi

# return to where we came from
popd > /dev/null

# final printing of log files of failed tests
# For PWG workflows, this triggers only a warning at the moment
if [[ "${ret_global_pwg}" != "0" ]] ; then
    echo
    echo "#####################################"
    echo "# WARNING for PWG-related workflows #"
    echo "#####################################"
    echo
    print_error_logs ${TEST_PARENT_DIR_PWG}
fi

# However, if a central test fails, exit code will be !=0
if [[ "${ret_global_bin}" != "0" ]] ; then
    echo
    echo "###################################"
    echo "# ERROR for bin-related workflows #"
    echo "###################################"
    echo
    print_error_logs ${TEST_PARENT_DIR_BIN}
fi

# However, if a central test fails, exit code will be !=0
if [[ "${ret_global_anchored}" != "0" ]] ; then
    echo
    echo "##########################"
    echo "# ERROR for anchored MCs #"
    echo "##########################"
    echo
    print_error_logs ${TEST_PARENT_DIR_ANCHORED}
fi

RET=$(( ret_global_bin + ret_global_anchored ))

echo
[[ "${RET}" != "0" ]] && echo "There were errors, please check!" || echo_green "All required workflow tests successful"

exit ${RET}
