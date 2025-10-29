#!/bin/bash

######################################
# Add Herwig, GSL, ThePEG and nlohmann_json packages to root include path and library path if not already present
######################################

# ROOT_INCLUDE_PATH
[[ -n "$THEPEG_ROOT" && ":$ROOT_INCLUDE_PATH:" != *":$THEPEG_ROOT/include:"* ]] && ROOT_INCLUDE_PATH="$THEPEG_ROOT/include:$ROOT_INCLUDE_PATH"
[[ -n "$HERWIG_ROOT" && ":$ROOT_INCLUDE_PATH:" != *":$HERWIG_ROOT/include:"* ]] && ROOT_INCLUDE_PATH="$HERWIG_ROOT/include:$ROOT_INCLUDE_PATH"
[[ -n "$GSL_ROOT" && ":$ROOT_INCLUDE_PATH:" != *":$GSL_ROOT/include:"* ]] && ROOT_INCLUDE_PATH="$GSL_ROOT/include:$ROOT_INCLUDE_PATH"
[[ -n "$NLOHMANN_JSON_ROOT" && ":$ROOT_INCLUDE_PATH:" != *":$NLOHMANN_JSON_ROOT/include:"* ]] && ROOT_INCLUDE_PATH="$NLOHMANN_JSON_ROOT/include:$ROOT_INCLUDE_PATH"

# LD_LIBRARY_PATH
[[ -n "$THEPEG_ROOT" && ":$LD_LIBRARY_PATH:" != *":$THEPEG_ROOT/lib/ThePEG:"* ]] && LD_LIBRARY_PATH="$THEPEG_ROOT/lib/ThePEG:$LD_LIBRARY_PATH"
[[ -n "$HERWIG_ROOT" && ":$LD_LIBRARY_PATH:" != *":$HERWIG_ROOT/lib/Herwig:"* ]] && LD_LIBRARY_PATH="$HERWIG_ROOT/lib/Herwig:$LD_LIBRARY_PATH"
[[ -n "$GSL_ROOT" && ":$LD_LIBRARY_PATH:" != *":$GSL_ROOT/lib:"* ]] && LD_LIBRARY_PATH="$GSL_ROOT/lib:$LD_LIBRARY_PATH"

export ROOT_INCLUDE_PATH LD_LIBRARY_PATH

######################################
# Entrypoint for O2DPG related tests #
######################################

CHECK_GENERATORS="Pythia8 External"

# The test parent dir to be cretaed in current directory
TEST_PARENT_DIR="o2dpg_tests/generators"

# unified names of log files for simulation and test macro
LOG_FILE_SIM="o2dpg-test-sim.log"
LOG_FILE_KINE="o2dpg-test-kine.log"
LOG_FILE_GENERIC_KINE="o2dpg-test-generic-kine.log"

# collect any macro files that are not directly used in INI files but that might be included in other macros
MACRO_FILES_POTENTIALLY_INCLUDED=""

# global var to collect all INI files to be tested
INI_FILES=""

# collect test macros that do not have a corresponding INI file
TEST_WITHOUT_INI=""

# a global counter for tests
TEST_COUNTER=1

# whether or not to delete everything except logs (default is to delete)
KEEP_ONLY_LOGS=1

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


# Prevent the script from being soured to omit unexpected surprises when exit is used
SCRIPT_NAME="$(basename "$(test -L "$0" && readlink "$0" || echo "$0")")"
if [ "${SCRIPT_NAME}" != "$(basename ${BASH_SOURCE[0]})" ] ; then
    echo_red "This script cannot not be sourced" >&2
    return 1
fi


##################################
# Core and utility functionality #
##################################


get_test_script_path_for_ini()
{
    local ini_path=${1}
    local test_script=$(basename ${ini_path})
    local path_to_test_script=$(dirname ${ini_path})/tests/${test_script%.ini}.C
    if [[ ! -f ${path_to_test_script} ]] ; then
        # Check if test redirection is applied inside the ini_path file using the #---> syntax
        local redirection=$(grep "#--->" ${ini_path})
        if [[ "${redirection}" != "" ]] ; then
            test_script=$(echo ${redirection} | awk '{print $2}')
            path_to_test_script=$(dirname ${ini_path})/tests/${test_script}.C
        fi
    fi
    echo ${path_to_test_script}
}

get_nevents_from_ini()
{
    # function to force the number of events to be simulated from the ini file (default = 100)
    # Syntax: #NEV_TEST> 10 (space between #NEV_TEST> and the number is mandatory)
    # To be used only if external generator takes too long to run causing timeouts in CI
    local ini_path=${1}
    local nev=$(grep "#NEV_TEST>" ${ini_path} | tail -n 1 | awk '{print $2}' | tr -d ' ')
    [[ "${nev}" == "" ]] && nev=100
    echo ${nev}
}

exec_test()
{
    # execute one test for a given ini file and generator
    # we assume at this point that we are already in the foreseen test directory
    local ini_path=${1}
    local generator=${2} # for now one of "Pythia8" or "External", at this point we know that settings for the generator are defined in this ini
    local generator_lower=$(echo "${generator}" | tr '[:upper:]' '[:lower:]')
    # TODO Potentially, one could run an external generator that derives from GeneratorPythia8 and so could probably use configuration for TriggerPythia8
    local trigger=${3:+-t ${generator_lower}}
    local RET=0
    # this is how our test script is expected to be called
    local test_script=$(get_test_script_path_for_ini ${ini_path})
    # get the number of events to be simulated from the ini file
    local nev=$(get_nevents_from_ini ${ini_path})
    # prepare the header of the log files
    echo "### Testing ${ini_path} with generator ${generator} ###" > ${LOG_FILE_KINE}
    echo "### Testing ${ini_path} with generator ${generator} ###" > ${LOG_FILE_GENERIC_KINE}
    echo "### Testing ${ini_path} with generator ${generator} ###" > ${LOG_FILE_SIM}
    # run the simulation, fail if not successful
    o2-sim -g ${generator_lower} ${trigger} --noGeant -n ${nev} -j 4 --configFile ${ini_path} --configKeyValues "GeneratorPythia8.includePartonEvent=true" >> ${LOG_FILE_SIM} 2>&1
    RET=${?}
    [[ "${RET}" != "0" ]] && { remove_artifacts ; return ${RET} ; }

    # now run the generic test on the kinemtics
    root -l -b -q ${O2DPG_ROOT}/test/common/kine_tests/test_generic_kine.C >> ${LOG_FILE_GENERIC_KINE} 2>&1
    RET=${?}

    # now run the test script that we know at this point exists
    cp ${test_script} ${generator}.C
    root -l -b -q ${generator}.C >> ${LOG_FILE_KINE} 2>&1
    local ret_test=${?}
    [[ "${RET}" != "0" ]] || RET=${ret_test}
    rm ${generator}.C

    remove_artifacts
    return ${RET}
}


check_generators()
{
    # check all possible generators incorporated in the INI file
    local ini_path=${1}
    local generators_to_check=""
    # global return code for this check
    local ret_this=0
    # check if there is a test script
    local test_script=$(get_test_script_path_for_ini ${ini_path})
    local tested_any=
    [[ ! -f ${test_script} ]] && { echo_red "[FATAL]: O2DPG_TEST Script ${test_script} not defined for ini file ${ini_path}" | tee -a ${LOG_FILE_KINE} ; return 1 ; }
    for g in ${CHECK_GENERATORS} ; do
        # check if this generator is mentioned in the INI file and only then test it
        if [[ "$(grep ${g} ${ini_path})" != "" ]] ; then
            local look_for=$(grep " ${g}.*\(\)" ${test_script})
            local has_trigger="$(grep Trigger${g} ${ini_path})"
            [[ -z "${look_for}" ]] && continue
            echo -n "Test ${TEST_COUNTER}: ${ini_path} with generator ${g}"
            tested_any=1
            # prepare the test directory
            local test_dir=${TEST_COUNTER}_$(basename ${ini})_${g}_dir
            rm -rf ${test_dir} 2> /dev/null
            mkdir ${test_dir}
            pushd ${test_dir} > /dev/null
                # one single test
                exec_test ${ini_path} ${g} ${has_trigger}
                RET=${?}
            popd > /dev/null
            if [[ "${RET}" != "0" ]] ; then
                echo_red " -> FAILED"
                ret_this=${RET}
            else
                echo_green " -> PASSED"
            fi
            ((TEST_COUNTER++))
        fi
    done
    [[ -z "${tested_any}" ]] && { echo_red "No test scenario was found for any generator. There must be at least one generator to be tested." ; ret_this=1 ; }
    return ${ret_this}
}


add_ini_files_from_macros()
{
    # given a list of macros, collect all INI files which contain at least one of them
    local macro_files=$@
    for mf in ${macro_files} ; do
        # Strip anything before MC/config/, if any, to get the macro relative path
        if [[ "${mf}" == *"MC/config"* ]] ; then
            mf=${mf#*MC/config/}
            mf="MC/config/${mf}"
        fi
        local other_ini_files=$(grep -r -l ${mf} | grep ".ini$")
        # so this macro is not included in any of the INI file,
        # maybe it is included by another macro which is then included in an INI file
        [[ -z "${other_ini_files}" ]] && { MACRO_FILES_POTENTIALLY_INCLUDED+="${mf} " ; continue ; }
        for oif in ${other_ini_files} ; do
            # add to our collection of INI files if not yet there
            [[ "${INI_FILES}" ==  *"${oif}"* ]] && continue
            INI_FILES+=" ${oif} "
        done
    done
}


get_root_includes()
{
    # check if some R__ADD_INCLUDE_PATH is used in the including macro and check the included file against that
    local including_file=${1}
    local included_file=${2}
    full_includes=""
    while read -r line ; do
        # strip everything in as there is most likely some R__ADD_INCLUDE_PATH($O2DPG/<what/we/are/interested/in>) to only keep the tail
        included_file_this_dir=${line#*/}
        # remove the trailing bracket
        included_file_this_dir=${included_file_this_dir%%")"}
        # construct the full file path
        included_file_this_dir=${included_file_this_dir}/${included_file}
        # check if this file exists and if so, add it to our list if  not yet there
        [[ -f ${included_file_this_dir} && "${full_includes}" != *"${included_file_this_dir}"* ]] && full_includes+="${included_file_this_dir} "
    done <<< "$(grep R__ADD_INCLUDE_PATH ${including_file})"
    echo ${full_includes}
}


find_including_macros()
{
    # figure out the macros that INCLUDE macros that have changed, so that in turn we can check
    # if these including macros are contained in some INI files
    local repo_dir_head=${REPO_DIR}
    local changed_files=$(git_get_changed_files)
    local potentially_included=${MACRO_FILES_POTENTIALLY_INCLUDED}
    # we reset it here but we could fill it again to be able to do it fully recursively
    MACRO_FILES_POTENTIALLY_INCLUDED=""
    # collection of including macros based on w
    local including_macros=""
    for pi in ${potentially_included} ; do
        local base=$(basename ${pi})
        # look into all files that include this one
        while read -r including ; do
            # break when nothing was grepped
            [[ -z "${including}" ]] && break
            # some name gymnastics
            local including_file=${including%:*}
            local included_file=${including##*:}
            # get really only the blank file path that is included
            included_file=${included_file##* }
            included_file=${included_file##\"}
            included_file=${included_file%%\"}
            # check if included relative to this directory
            local included_file_this_dir=$(dirname ${including_file})/${included_file}
            included_file_this_dir=$(realpath $included_file_this_dir)
            included_file_this_dir=${included_file_this_dir##${repo_dir_head}/}
            if [[ -f ${included_file_this_dir} && "${changed_files}" == *"${included_file_this_dir}"* ]] ; then
                [[ "${including_macros}" == *"${including_file}"* ]] && continue
                including_macros+="${including_file} "
                continue
            fi
            # check if some R__ADD_INCLUDE_PATH is used in the including macro and check the included files against that
            for root_included in $(get_root_includes ${including_file} ${included_file}) ; do
                if [[ "${changed_files}" == *"${root_included}"* ]] ; then
                    [[ "${including_macros}" == *"${including_file}"* ]] && continue
                    including_macros+="${including_file} "
                    continue
                fi
            done
        done <<< "$(grep -r include.*${base})"
    done
    echo ${including_macros}
}


add_ini_files_from_tests()
{
    # Collect also those INI files for which the test has been changed
    local test_changed=$@
    for tc in ${test_changed} ; do
        local ini_dir=$(dirname ${tc})
        ini_dir=${ini_dir%%/tests}
        local keep_test_name=${tc}
        tc=$(basename ${tc})
        tc=${tc%.C}.ini
        tc=${ini_dir}/${tc}
        [[ "${INI_FILES}" == *"${tc}"* ]] && continue
        # this INI file actually does not exist, it is an unused test --> to be refined to detect them
        [[ ! -f ${tc} ]] && { TEST_WITHOUT_INI+="${keep_test_name} " ; continue ; }
        INI_FILES+=" ${tc} "
    done
}


collect_ini_files()
{
    # Collect all INI files which have changed
    local changed_files=$(git_get_changed_files)
    for ini in ${changed_files} ; do
        [[ "${ini}" != *"MC/config"*".ini" ]] && continue
        [[ "${INI_FILES}" == *"${ini}"* ]] && continue || INI_FILES+=" ${ini} "
    done

    # this relies on INI_FILES and MACRO_FILES_POTENTIALLY_INCLUDED
    # collect all INI files that might include some changed macros
    local macros=
    for m in ${changed_files} ; do
        [[ "${m}" != *"MC/config"*".C" ]] && continue
        macros+=" ${m} "
    done

    add_ini_files_from_macros ${macros}

    # this relies on MACRO_FILES_POTENTIALLY_INCLUDED
    # collect all INI files that might contain macros which in turn include changed macros
    # for now, just go one level deeper, in principal we could do this fully recursively
    add_ini_files_from_macros $(find_including_macros)

    # also tests might have changed in which case we run them
    local macros=
    for m in ${changed_files} ; do
        [[ "${m}" != *"MC/"*"ini/tests"*".C" ]] && continue
        macros+=" ${m} "
    done
    add_ini_files_from_tests ${macros}
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

print_usage()
{
    echo
    echo "usage: run_generator_tests.sh [--fail-immediately] [--keep-artifacts]"
    echo
    echo "  FLAGS:"
    echo
    echo "  --fail-immediately : abort as soon as the first tests fails"
    echo "  --keep-artifacts : keep simulation and tests artifacts, by default everything but the logs is removed after each test"
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

####################
# Collect cmd args #
####################

# whether or not to exit after first test has failed
fail_immediately=
[[ "${1}" == "--fail_immediately" ]] && fail_immediately=1

while [ "$1" != "" ] ; do
    case $1 in
        --fail_immediately ) shift
                             fail_immediately=1
                             ;;
        --keep-artifacts )   shift
                             KEEP_ONLY_LOGS=0
                             ;;
        --help|-h )          print_usage
                             exit 1
                             ;;
        * )                  echo "Unknown argument ${1}"
                             exit 1
                             ;;
    esac
done

echo
echo "################################"
echo "# Run O2DPG simulation testing #"
echo "################################"
echo

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

# Do the initial steps in the source dir where we have the full git repo
pushd ${REPO_DIR} > /dev/null

# Then add the ini files that have changed as well. We need to do that so we get information
# about missing tests etc.
collect_ini_files

if [[ -z "${INI_FILES}" ]] ; then
    echo
    echo "Nothing found to be tested."
    echo
    exit 0
fi

if [[ ! -z "${TEST_WITHOUT_INI}" ]] ; then
    echo_red "Warning: There are test macros that do not correspond to any INI file:"
    for twi in ${TEST_WITHOUT_INI} ; do
        echo "  - ${twi}"
    done
    exit 1
fi

echo "Following INI files will be tested:"
ini_files_full_paths=
for ini in ${INI_FILES} ; do
    echo "  - ${ini}"
    # convert to full path so that we can find it from anywhere
    ini_files_full_paths+="$(realpath ${ini}) "
done

# go back to where we came from
popd > /dev/null

# Now, do the trick:
# We just use the source dir since O2DPG's installation is basically just a copy of the whole repo.
# This makes sense in particular for local testing but also in the CI it works in the same way. We could do
#         [[ -z {ALIBUILD_HEAD_HASH+x} ]] && export O2DPG_ROOT=${REPO_DIR}
# but let's do the same for both local and CI consistently
export O2DPG_ROOT=${REPO_DIR}
export O2DPG_MC_CONFIG_ROOT=${O2DPG_ROOT}

# prepare our local test directory
rm -rf ${TEST_PARENT_DIR} 2>/dev/null
mkdir -p ${TEST_PARENT_DIR} 2>/dev/null
pushd ${TEST_PARENT_DIR} > /dev/null

# global return code to be returned at the end
ret_global=0

# check each of the INI files
for ini in ${ini_files_full_paths} ; do

    # we can apply some matching if it is asked
    check_this="1"
    echo "Checking ${ini}"
    if [[ "${O2DPG_CHECK_FILTER}" ]]; then
      echo "Checking with filter ${O2DPG_CHECK_FILTER}"
      if [[ "${ini}" == *"${O2DPG_CHECK_FILTER}"* ]]; then
        check_this="1"
      else
        check_this="0"
      fi
    fi

    if [[ "${check_this}" == "0" ]]; then
      continue
    fi

    check_generators ${ini}
    RET=${?}
    if [[ "${RET}" != "0" ]] ; then
        ret_global=${RET}
        [[ "${fail_immediately}" == "1" ]] && break
    fi
done
# return to where we came from
popd > /dev/null

# final printing of log files of failed tests
if [[ "${ret_global}" != "0" ]] ; then
    print_error_logs ${TEST_PARENT_DIR}
    exit ${ret_global}
fi

echo
echo_green "All generator tests successful"
echo

exit 0
