#!/bin/bash
# Static guard against the exit-code-aggregation bug in run_workflow_tests.sh:
# the final RET=$(( ... )) line must include every aggregate return-code
# variable the script computes, and each of those variables must actually be
# assigned somewhere in the script.

set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SCRIPT=${O2DPG_TEST_WORKFLOW_SCRIPT:-"${HERE}/../run_workflow_tests.sh"}
FAILURES=0

check()
{
    local label=$1 expected=$2 actual=$3
    if [[ "${expected}" == "${actual}" ]] ; then
        echo "ok   - ${label}"
    else
        echo "FAIL - ${label}: expected '${expected}', got '${actual}'"
        FAILURES=$((FAILURES + 1))
    fi
}

# The three aggregate return-code variables the final exit code must include.
# Explicit and hard-coded on purpose: a fourth aggregate added later must make
# whoever adds it come here and update this list.
REQUIRED_VARS="ret_global_pwg ret_analysis_qc ret_global_anchored"

RET_LINE=$(grep -m1 -E '^RET=\$\(\(' "${SCRIPT}")

for var in ${REQUIRED_VARS} ; do
    present=$(grep -c -- "${var}" <<< "${RET_LINE}")
    check "RET= line includes ${var}" 1 "${present}"
done

for var in ${REQUIRED_VARS} ; do
    assigned=$(grep -c -E "^[[:space:]]*${var}=" "${SCRIPT}")
    check "${var} is assigned in the script" 1 "$( [[ "${assigned}" -ge 1 ]] && echo 1 || echo 0 )"
done

echo
if [[ "${FAILURES}" == "0" ]] ; then
    echo "All exit-code aggregation checks passed"
else
    echo "${FAILURES} test(s) failed"
fi
exit $(( FAILURES > 0 ? 1 : 0 ))
