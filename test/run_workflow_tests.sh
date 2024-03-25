#!/bin/bash

# The test parent dir to be cretaed in current directory
TEST_PARENT_DIR_PWG="o2dpg_tests/workflows_pwgs"
TEST_PARENT_DIR_BIN="o2dpg_tests/workflows_analysisqc"
TEST_PARENT_DIR_ANCHORED="o2dpg_tests/anchored"

# unified names of log files
LOG_FILE_WF="o2dpg-test-wf.log"
LOG_FILE_ANCHORED="o2dpg-test-anchored.log"
LOG_FILE_ANALYSISQC="o2dpg-test_analysisqc.log"


get_git_repo_directory()
{
    local look_dir=${1:-$(pwd)}
    look_dir=$(realpath "${look_dir}")
    look_dir=${look_dir%%/.git}
    local repo=
    (
        cd "${look_dir}"
        repo=$(git rev-parse --git-dir 2> /dev/null)
        [[ "${repo}" != "" ]] && { repo=$(realpath "${repo}") ; repo=${repo%%/.git} ; }
    )
    echo ${repo}
}


test_single_wf()
{
    local wf_script=${1}
    local execute=${2}
    make_wf_creation_script ${wf_script} ${wf_script_local}
    local has_wf_script_local=${?}
    echo -n "Test ${TEST_COUNTER}: ${wfs}"
    [[ "${has_wf_script_local}" != "0" ]] && { echo -n " (No WF creation in script)" ; echo_red " -> FAILED" ; return 1 ; }
    # Check if there is an "exit" other than the usual
    # [ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
    # like ones.
    # This is not perfect but might prevent us from running into some checks the WF script does before launching the WF creation
    [[ "$(grep exit ${wf_script_local} | grep -v "This needs")" != "" ]] && { echo -n " (Found \"exit\" in script, not testing automatically)" ; echo_yellow " -> WARNING" ; return 0 ; }
    # one single test
    echo "Test ${wf_line} from ${wfs}" > ${LOG_FILE_WF}
    bash ${wf_script_local} >> ${LOG_FILE_WF} 2>&1
    local ret_this=${?}
    local ret_this_qc=0
    local ret_this_analysis=0
    if [[ "${ret_this}" != "0" ]] ; then
        echo_red " -> FAILED"
        echo "[FATAL]: O2DPG_TEST Workflow creation failed" >> ${LOG_FILE_WF}
    elif [[ "${execute}" != "" ]] ; then
        local memlimit=${O2DPG_TEST_WORKFLOW_MEMLIMIT:+--mem-limit ${O2DPG_TEST_WORKFLOW_MEMLIMIT}}
        ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --cpu-limit 8 -tt aod ${memlimit} >> ${LOG_FILE_WF} 2>&1
        ret_this=${?}
        # use -k|--keep-going feature to not stop after the first failure but see, if there are more
        [[ "${ret_this}" == "0" ]] && { ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --cpu-limit 8 --target-labels QC ${memlimit} -k >> ${LOG_FILE_WF} 2>&1 ; ret_this_qc=${?} ; }
        [[ "${ret_this}" == "0" ]] && { ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --cpu-limit 8 --target-labels Analysis ${memlimit} -k >> ${LOG_FILE_WF} 2>&1 ; ret_this_analysis=${?} ; }
        ret_this=$((ret_this + ret_this_qc + ret_this_analysis))
        [[ "${ret_this}" != "0" ]] && echo "[FATAL]: O2DPG_TEST Workflow execution failed" >> ${LOG_FILE_WF} || echo_green " -> PASSED"
    else
        echo_green " -> PASSED"
    fi
    return ${ret_this}
}

run_workflow_creation()
{
    local wf_scripts=
    local execute=
    while [ "$1" != "" ] ; do
        case $1 in
            --execute ) execute=1
                        shift
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
    done

    return ${RET}
}


test_analysisqc_cli()
{
    ((TEST_COUNTER++))
    local test_dir="${TEST_COUNTER}_analysisqc_cli"
    rm -rf ${test_dir} 2> /dev/null
    mkdir ${test_dir}
    pushd ${test_dir} > /dev/null
        echo "### Testing AnalysisQC creation for MC ###" > ${LOG_FILE_ANALYSISQC}
        echo -n "Test ${TEST_COUNTER}: Running AnalysisQC CLI"
        ${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_workflow.py -f AO2D.root --is-mc -o wokflow_test_mc.json >> ${LOG_FILE_ANALYSISQC} 2>&1
        local ret=${?}
        [[ "${ret}" != "0" ]] && echo "[FATAL]: O2DPG_TEST failed" >> ${LOG_FILE_ANALYSISQC}
        echo "### Testing AnalysisQC creation for data ###" >> ${LOG_FILE_ANALYSISQC}
        ${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_workflow.py -f AO2D.root -o wokflow_test_data.json >> ${LOG_FILE_ANALYSISQC} 2>&1
        local ret_data=${?}
        [[ "${ret_data}" != "0" ]] && { echo "[FATAL]: O2DPG_TEST failed" >> ${LOG_FILE_ANALYSISQC} ; ret=${ret_data} ; }
    popd > /dev/null
    [[ "${ret}" != "0" ]] && echo_red " -> FAILED" || echo_green " -> PASSED"
    return ${ret}
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
            if [[ "${ret_this}" != "0" ]] ; then
                echo_red " -> FAILED"
                RET=${ret_this}
            else
                echo_green " -> PASSED"
            fi
        popd > /dev/null
    done
    return ${RET}
}

print_usage()
{

    echo
    echo "usage: run_workflow_tests.sh"
    echo
    echo "  ENVIRONMENT VARIABLES TO DETERMINE WHAT TO COMPARE:"
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
    echo "  SPECIFIC ENVIRONMENT VARIABLES FOR THIS TEST:"
    echo "  O2DPG_TEST_WORKFLOW_MEMLIMIT : The memory limit that is passed to the workflow runner in case a workflow is executed (optional)"
    echo
}


#############
# Main part #
#############
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

# determine the repository directory
REPO_DIR=${O2DPG_TEST_REPO_DIR:-$(get_git_repo_directory)}
if [[ ! -d ${REPO_DIR}/.git ]] ; then
    echo "ERROR: Directory \"${REPO_DIR}\" is not a git repository."
    exit 1
fi

if [[ -z ${O2DPG_ROOT+x} ]] ; then
    echo "ERROR: O2DPG is not loaded, probably other packages are missing as well in this environment."
    exit 1
fi

# source the utilities
source ${REPO_DIR}/test/common/utils/utils.sh


echo "##############################"
echo "# Run O2DPG workflow testing #"
echo "##############################"

# Do the initial steps in the source dir where we have the full git repo
pushd ${REPO_DIR} > /dev/null

# flag if anything changed in the sim workflow bin dir
changed_sim_bin=$(get_changed_files | grep -E "MC/bin")
# collect if anything has changed related to AnalysisQC
changed_analysis_qc=$(get_changed_files | grep -E "MC/analysis_testing|MC/config/analysis_testing/json|MC/config/QC/json")
# check if anything has changed concerning anchoring
changed_anchored=$(get_changed_files | grep -E "MC/bin|MC/run/ANCHOR/anchorMC.sh|MC/run/ANCHOR/tests|MC/bin|UTILS/parse-async-WorkflowConfig.py|DATA/production/configurations/asyncReco/setenv_extra.sh|DATA/production/configurations/asyncReco/async_pass.sh|DATA/common/setenv.sh|DATA/production/workflow-multiplicities.sh")
# collect changed workflow scripts
changed_workflows=
# workflows to be executed
execute_workflows=
echo "==> Test outline"
if [[ "${changed_sim_bin}" != "" ]] ; then
    # in this case, something central has changed, test creation of all workflows against it
    echo "  - The creation of simulation workflows from all run scripts (MC/run/**/*.sh) will be tested."
    for p in $(find MC/run -name "*.sh") ; do
        changed_workflows+="$(realpath ${p}) "
    done
    # definitely run anchored if central python scripts have changed
    echo "    - Changes in MC/bin/ detected, mark anchored MC test to be run."
    changed_anchored="1"
else
    # otherwise, only take the changed shell scripts
    changed_workflows=
    changed_files=$(get_changed_files)
    for cf in ${changed_files} ; do
        [[ "${cf}" != *"MC/run"*".sh" ]] && continue
        changed_workflows+="${cf} "
    done
    [[ "${changed_workflows}" != "" ]] && echo "  - The creation of simulation workflows from changed run scripts (sub-sect of MC/run/**/*.sh) will be tested."
fi

if [[ "${changed_analysis_qc}" != "" || "${changed_sim_bin}" ]] ; then
    for p in $(find "MC/bin/tests" -name "*.sh") ; do
        execute_workflows+="$(realpath ${p}) "
    done
    echo "  - Test AnalysisQC CLI and execution with a simulation."
fi

[[ "${changed_anchored}" != "" ]] && echo "  - Test anchored simulation."

# everything collected, go back to where we came from
popd > /dev/null
REPO_DIR=$(realpath ${REPO_DIR})

# Now, do the trick:
# We just use the source dir since O2DPG's installation is basically just a copy of the whole repo.
# This makes sense in particular for local testing but also in the CI it works in the same way. We could do
#         [[ -z {ALIBUILD_HEAD_HASH+x} ]] && export O2DPG_ROOT=${REPO_DIR}
# but let's do the same for both local and CI consistently
export O2DPG_ROOT=${REPO_DIR}


##############################
# PWG workflow shell scripts #
##############################
# global return code for PWGs
ret_global_pwg=0

# Test what we found
if [[ "${changed_workflows}" != "" ]] ; then
    # prepare our local test directory for PWG tests
    rm -rf ${TEST_PARENT_DIR_PWG} 2>/dev/null
    mkdir -p ${TEST_PARENT_DIR_PWG} 2>/dev/null
    pushd ${TEST_PARENT_DIR_PWG} > /dev/null

    echo
    echo "==> START BLOCK: Test PWG-related workflow creation <=="
    run_workflow_creation ${changed_workflows}
    ret_global_pwg=${?}
    [[ "${ret_global_pwg}" != "0" ]] && { echo "WARNING for workflows creations, some could not be built." ;  print_error_logs ./ ; }
    echo "==> END BLOCK: Test PWG-related workflow creation <=="

    # return to where we came from
    popd > /dev/null
fi


####################################
# sim workflow bin with AnalysisQC #
####################################
# prepare our local test directory for bin tests
# global return code for PWGs
ret_analysis_qc=0
if [[ "${changed_analysis_qc}" != "" ]] ; then
    rm -rf ${TEST_PARENT_DIR_BIN} 2>/dev/null
    mkdir -p ${TEST_PARENT_DIR_BIN} 2>/dev/null
    pushd ${TEST_PARENT_DIR_BIN} > /dev/null

    echo
    echo "==> START BLOCK: Test running workflow with AnalysisQC <=="
    # test command line interface
    test_analysisqc_cli
    ret_analysis_qc=${?}
    # Run all the bin test WF creations
    [[ "${ret_analysis_qc}" == "0" ]] && { run_workflow_creation ${execute_workflows} --execute ; ret_analysis_qc=${?} ; }
    [[ "${ret_analysis_qc}" != "0" ]] && { echo "ERROR for workflows execution and AnalysisQC." ;  print_error_logs ./ ; }
    echo "==> END BLOCK: Test running workflow with AnalysisQC <=="

    # return to where we came from
    popd > /dev/null
fi


###############
# ANCHORED MC #
###############
# global return code for PWGs
ret_global_anchored=0
if [[ "${changed_anchored}" != "" ]] ; then
    # prepare our local test directory for PWG tests
    rm -rf ${TEST_PARENT_DIR_ANCHORED} 2>/dev/null
    mkdir -p ${TEST_PARENT_DIR_ANCHORED} 2>/dev/null
    pushd ${TEST_PARENT_DIR_ANCHORED} > /dev/null

    echo
    echo "==> START BLOCK: Test anchored simulation"
    # Run an anchored test
    test_anchored
    ret_global_anchored=${?}
    [[ "${ret_global_anchored}" != "0" ]] && { echo "ERROR executing anchored simulation." ;  print_error_logs ./ ; }
    echo "==> END BLOCK: Test anchored simulation"

    # return to where we came from
    popd > /dev/null
fi

RET=$(( ret_analysis_qc + ret_global_anchored ))

echo
[[ "${RET}" != "0" ]] && echo_red "There were errors, please check!" || echo_green "All required workflow tests successful"

exit ${RET}
