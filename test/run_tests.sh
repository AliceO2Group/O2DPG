#!/bin/bash

######################################
# Entrypoint for O2DPG related tests #
######################################

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

print_usage()
{
    echo "Script ${SCRIPT_NAME}"
    echo "Usage:"
    echo "${SCRIPT_NAME} <test-names>"
}

SCRIPT_NAME="$(basename "$(test -L "$0" && readlink "$0" || echo "$0")")"

# Prevent the script from being soured to omit unexpected surprises when exit is used
if [ "${SCRIPT_NAME}" != "$(basename ${BASH_SOURCE[0]})" ] ; then
  echo_red "This script should not be sourced" >&2
  return 1
fi

[[ "$#" == "1" && "$1" == "-h" || "$1" == "--help" ]] && { print_usage ; exit 0 ; }

# Don't run if O2DPG_ROOT is missing. That is the only one we ask for,everything else is in the hands of the users 
[[ -z ${O2DPG_ROOT+x} ]] && { echo_red "O2DPG_ROOT and potentially also other packages not loaded." ; exit 1 ; }

TESTS_AVAILABLE=$(find ${O2DPG_ROOT}/test -maxdepth 1 -type f -name "test-*.sh")

if [ "$#" != "0" ] ; then
    # all the tests that should be run
    TESTS_PROPOSED=$@

    TESTS_RUN=""
    TESTS_NOT_FOUND=""

    for t in ${TESTS_PROPOSED} ; do
        # construct the full test name and fill the tests to be run
        t="test-${t}.sh"
        test_available="$(echo ${TESTS_AVAILABLE} | grep ${t} )"
        echo ${test_available}
        [ "${test_available}" != "" ] && TESTS_RUN+=${O2DPG_ROOT}/test/${t} || TESTS_NOT_FOUND+=${t}
    done

    if [[ "${TESTS_RUN}" == "" ]] ; then
        # apparently, nothing to run
        if [[ "${TESTS_PROPOSED}" != "" ]] ; then
        # but if something was proposed, exit with error
            echo "There were the following tests proposed:"
            for tp in ${TESTS_PROPOSED} ; do
                echo ${tp}
            done
            echo "But none of them corresponds to an available test."
            exit 1
        fi
        exit 0
    fi

    [[ "${TESTS_NOT_FOUND}" != "" ]] && echo "WARNING: Following tests were not found: ${TESTS_NOT_FOUND}"
else
    TESTS_RUN=${TESTS_AVAILABLE}
fi

echo_green "Tests to be run"
for tr in ${TESTS_RUN} ; do
    echo "  - ${tr##${O2DPG_ROOT}/test/}"
done

# final return code
RET=0

# Now run all found tests
for tr in ${TESTS_RUN} ; do
    # Basename of full path to next test script
    suffix=${tr##${O2DPG_ROOT}/test/}
    test_dir=${suffix}_dir
    rm -rf ${test_dir} 2>/dev/null
    mkdir ${test_dir}
    logfile=${suffix}.log
    pushd ${test_dir} > /dev/null
        echo "Running test ${suffix}"
        ${tr} > ${logfile} 2>&1
        RET=$?
        if [ "${RET}" != "0" ] ; then
            echo_red "There was an error (exit code was ${RET}), here is the log $(pwd)/${logfile}"
            cat ${logfile}
            # Mark failure in the log file
            echo -e "\n### O2DPG TEST FAILED ###\n" >> ${logfile}
            exit ${RET}
        fi
        echo -e "\n### O2DPG TEST PASSED ###\n" >> ${logfile}
    popd > /dev/null
done

echo_green "All tests successful!"
exit 0
 