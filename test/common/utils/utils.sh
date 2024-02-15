#!/bin/bash

#
# Test utility functionality
#

remove_artifacts()
{
    [[ "${KEEP_ONLY_LOGS}" == "1" ]] && find . -type f ! -name '*.log' -and ! -name "*serverlog*" -and ! -name "*mergerlog*" -and ! -name "*workerlog*" -delete
}


get_changed_files()
{
    # in the Github CIs, there are env variables that give us the base and head hashes,
    # so use them if they are there
    # Otherwise, we go a few steps back
    local hash_base_user=${O2DPG_TEST_HASH_BASE:-"HEAD~1"}
    local hash_head_user=${O2DPG_TEST_HASH_HEAD:-"HEAD"}
    local hash_base=${ALIBUILD_BASE_HASH:-${hash_base_user}}
    local hash_head=${ALIBUILD_HEAD_HASH:-${hash_head_user}}

    # check if unstaged changes and ALIBUILD_HEAD_HASH not set, in that case compare to unstaged
    # if there are unstaged changes and no head from user, leave blank
    [[ ! -z "$(git diff)" && -z ${ALIBUILD_HEAD_HASH+x} && -z ${O2DPG_TEST_HASH_HEAD+x} ]] && hash_head=""
    # if there are unstaged changes and no base from user, set to HEAD
    [[ ! -z "$(git diff)" && -z ${ALIBUILD_HEAD_HASH+x} && -z ${O2DPG_TEST_HASH_BASE+x} ]] && hash_base="HEAD"
    git diff --diff-filter=AMR --name-only ${hash_base} ${hash_head}
}


get_workflow_creation_from_script()
{
    # Get the part in the script which creates a workflow as one line
    local wf_script=${1}
    # look for the line where the workflow is created
    local look_for="o2dpg_sim_workflow.py"
    # assemble the whole line which in the file might contain continuation "\"
    local string_wo_line_breaks=
    while read -r line ; do
        [[ "${line}" == *"${look_for}"* ]] && has_started=1
        [[ "${has_started}" != "1" ]] && continue
        string_wo_line_breaks+=${line%%\\}
        [[ "${line}" == *"\\"* ]] && string_wo_line_breaks+=" "
        [[ "${line}" != *"\\"* ]] && break
    done < ${wf_script}
    echo ${string_wo_line_breaks}
}

make_wf_creation_script()
{
    # We only want the WF creation, no runner or anything else

    # The policy
    # Extract everything including the first appearance of the sim workflow creation; then stop
    # This assumes that the WF creation is not enclosed between if-else or in another ""scope"
    # in
    local full_wf_script=${1}
    # out
    local out_script=${2}

    # do not execute the runner
    local look_for="o2dpg_sim_workflow.py"
    # make sure we find the runner line, if the runner name has changed, we don't execute the script at all
    local has_no_wf=1

    while read -r line ; do
        [[ "${line}" == *"${look_for}"* ]] && has_no_wf=0
        [[ "${has_no_wf}" == "0" ]] && break
        echo "${line}" >> ${out_script}
    done < ${full_wf_script}

    echo "$(get_workflow_creation_from_script ${full_wf_script})" >> ${out_script}
    return ${has_no_wf}
}


print_error_logs()
{
    local search_dir=${1}
    local search_pattern="TASK-EXIT-CODE: ([1-9][0-9]*)|[Ss]egmentation violation|[Ss]egmentation fault|Program crashed|[Ee]xception caught|\[FATAL\]|uncaught exception|\(int\) ([1-9][0-9]*)|fair::FatalException"
    local error_files=$(find ${search_dir} -maxdepth 4 -type f \( -name "*.log" -or -name "*serverlog*" -or -name "*workerlog*" -or -name "*mergerlog*" \) | xargs grep -l -E "${search_pattern}" | sort)
    for ef in ${error_files} ; do
        echo_red "Error found in log $(realpath ${ef})"
        # print the match plus additional 10 lines
        grep -n -A 10 -B 10 -E "${search_pattern}" ${ef}
    done
}
