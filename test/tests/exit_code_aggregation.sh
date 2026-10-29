#!/bin/bash
# Static guard against the exit-code-aggregation bugs in run_workflow_tests.sh.
# Two things must hold:
#   1. the final RET= line must reference every aggregate return-code variable
#      the script computes, and each must actually be assigned somewhere;
#   2. no exit code may be produced by *summing* codes. Sums can land on a
#      multiple of 256 — two phases failing with 128 each sum to 256, which
#      exits 0 — so a real failure would report success.

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

RET_LINE=$(grep -m1 -E '^RET=' "${SCRIPT}")

for var in ${REQUIRED_VARS} ; do
    present=$(grep -c -- "${var}" <<< "${RET_LINE}")
    check "RET= line includes ${var}" 1 "${present}"
done

for var in ${REQUIRED_VARS} ; do
    assigned=$(grep -c -E "^[[:space:]]*${var}=" "${SCRIPT}")
    check "${var} is assigned in the script" 1 "$( [[ "${assigned}" -ge 1 ]] && echo 1 || echo 0 )"
done

# No exit code may be a sum of codes. These are the two sites that had it.
summed_ret=$(grep -c -E '^RET=\$\(\(' "${SCRIPT}")
check "RET is not a sum of codes" 0 "${summed_ret}"

summed_this=$(grep -c -E 'ret_this=\$\(\(ret_this[[:space:]]*\+' "${SCRIPT}")
check "test_single_wf does not sum codes" 0 "${summed_this}"

echo
if [[ "${FAILURES}" == "0" ]] ; then
    echo "All exit-code aggregation checks passed"
else
    echo "${FAILURES} test(s) failed"
fi
exit $(( FAILURES > 0 ? 1 : 0 ))
