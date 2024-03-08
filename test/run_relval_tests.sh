#!/bin/bash

# The test parent dir to be cretaed in current directory
TEST_PARENT_DIR="o2dpg_tests/relval"

# unified names of log files
LOG_FILE="o2dpg-test-relval.log"

# Prepare some colored output
SRED="\033[0;31m"
SGREEN="\033[0;32m"
SEND="\033[0m"


echo_green()
{
    echo -e "${SGREEN}${*}${SEND}"
}


echo_red()
{
    echo -e "${SRED}${*}${SEND}"
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


test_relval()
{
    # make 3 files to run on
    local filename1="file1.root"
    local filename2="file2.root"
    local filename3="file3.root"
    root -l -b -q ${O2DPG_ROOT}/test/RelVal/createTestFile.C\(\"${filename1}\"\) >> ${LOG_FILE} 2>&1
    root -l -b -q ${O2DPG_ROOT}/test/RelVal/createTestFile.C\(\"${filename2}\"\) >> ${LOG_FILE} 2>&1
    root -l -b -q ${O2DPG_ROOT}/test/RelVal/createTestFile.C\(\"${filename3}\"\) >> ${LOG_FILE} 2>&1
    echo "### Testing RelVal ###" > ${LOG_FILE}
    # rel-val
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i ${filename1} -j ${filename2} -o rel_val_${filename1}_${filename2}_dir >> ${LOG_FILE} 2>&1
    local ret=$?
    [[ ${ret} != "0" ]] && { echo "[FATAL]: O2DPG_TEST failed" >> ${LOG_FILE} ; return ${ret} ; }
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i ${filename1} -j ${filename3} -o rel_val_${filename1}_${filename3}_dir >> ${LOG_FILE} 2>&1
    ret=$?
    [[ ${ret} != "0" ]] && { echo "[FATAL]: O2DPG_TEST failed" >> ${LOG_FILE} ; return ${ret} ; }
    # inspect
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect --path rel_val_${filename1}_${filename2}_dir >> ${LOG_FILE} 2>&1
    ret=$?
    [[ ${ret} != "0" ]] && { echo "[FATAL]: O2DPG_TEST failed" >> ${LOG_FILE} ; return ${ret} ; }
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect --path rel_val_${filename1}_${filename3}_dir >> ${LOG_FILE} 2>&1
    ret=$?
    [[ ${ret} != "0" ]] && { echo "[FATAL]: O2DPG_TEST failed" >> ${LOG_FILE} ; return ${ret} ; }
    # compare
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py compare -i rel_val_${filename1}_${filename2}_dir -j rel_val_${filename1}_${filename3}_dir -o compare >> ${LOG_FILE} 2>&1
    ret=$?
    [[ ${ret} != "0" ]] && { echo "[FATAL]: O2DPG_TEST failed" >> ${LOG_FILE} ; return ${ret} ; }
    # influx
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py influx --path rel_val_${filename1}_${filename2}_dir >> ${LOG_FILE} 2>&1
    ret=$?
    [[ ${ret} != "0" ]] && { echo "[FATAL]: O2DPG_TEST failed" >> ${LOG_FILE} ; return ${ret} ; }
    # view
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py print --object-names --interpretations GOOD --path rel_val_${filename1}_${filename2}_dir >> ${LOG_FILE} 2>&1
    ret=$?
    [[ ${ret} != "0" ]] && { echo "[FATAL]: O2DPG_TEST failed" >> ${LOG_FILE} ; return ${ret} ; }
    return ${ret}
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
echo "############################"
echo "# Run O2DPG RelVal testing #"
echo "############################"
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

# flag if anything changed for RelVal
need_testing=$(get_changed_files | grep "RelVal/")

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
# Let's do it #
###############
ret_global=0
# prepare our local test directory for PWG tests
rm -rf ${TEST_PARENT_DIR} 2>/dev/null
mkdir -p ${TEST_PARENT_DIR} 2>/dev/null
pushd ${TEST_PARENT_DIR} > /dev/null

# Test what we found
if [[ "${need_testing}" != "" ]] ; then
    test_relval
    ret_global=${?}
else
    echo "Nothing to test"
    exit 0
fi

# return to where we came from
popd > /dev/null

# However, if a central test fails, exit code will be !=0
if [[ "${ret_global}" != "0" ]] ; then
    echo
    echo "####################"
    echo "# ERROR for RelVal #"
    echo "####################"
    echo
    print_error_logs ${TEST_PARENT_DIR}
    exit ${ret_global}
fi

echo
echo_green "RelVal tests successful"
echo

exit 0
