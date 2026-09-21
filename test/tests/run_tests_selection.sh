#!/bin/bash
# Offline harness for run_tests.sh: stubs the sub-test scripts and checks that
# selection and exit-code aggregation behave.

set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ENTRY="${HERE}/../run_tests.sh"
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

# A stub directory with three scripts whose exit codes we control via env
# vars, and which each record the arguments they received to a sibling
# "*.args" file (one per line) so forwarding can be checked.
make_stubs()
{
    local dir=$1
    mkdir -p "${dir}"
    for name in generator workflow relval ; do
        cat > "${dir}/run_${name}_tests.sh" <<EOF
#!/bin/bash
echo "STUB ${name} ran"
printf '%s\n' "\$@" > '${dir}/run_${name}_tests.args'
exit \${STUB_${name^^}_RC:-0}
EOF
        chmod +x "${dir}/run_${name}_tests.sh"
    done
}

run_entry()
{
    # usage: run_entry <stubdir> [args...]; prints nothing, sets OUT and RC
    local dir=$1 ; shift
    OUT=$(O2DPG_TEST_SUBTEST_DIR="${dir}" O2DPG_ROOT="${HERE}/../.." \
          O2DPG_TEST_REPO_DIR="${HERE}/../.." \
          bash "${ENTRY}" "$@" 2>&1)
    RC=$?
}

TMP=$(mktemp -d)
make_stubs "${TMP}/subtests"

# 1. all three sub-tests run by default and a clean run exits 0
run_entry "${TMP}/subtests"
check "default selection exits 0" 0 "${RC}"
check "default runs generator" 1 "$(grep -c 'STUB generator ran' <<< "${OUT}")"
check "default runs workflow"  1 "$(grep -c 'STUB workflow ran'  <<< "${OUT}")"
check "default runs relval"    1 "$(grep -c 'STUB relval ran'    <<< "${OUT}")"

# 2. an explicit selection runs only what was asked for
run_entry "${TMP}/subtests" relval
check "explicit selection exits 0" 0 "${RC}"
check "explicit selection skips generator" 0 "$(grep -c 'STUB generator ran' <<< "${OUT}")"
check "explicit selection runs relval"     1 "$(grep -c 'STUB relval ran'    <<< "${OUT}")"

# 3. a failing sub-test makes the entrypoint fail, and the others still run
STUB_GENERATOR_RC=3 run_entry "${TMP}/subtests"
check "failing generator propagates" 3 "${RC}"
check "failure does not stop workflow" 1 "$(grep -c 'STUB workflow ran' <<< "${OUT}")"

# 4. --fail-immediately stops after the first failure
STUB_GENERATOR_RC=3 run_entry "${TMP}/subtests" --fail-immediately
check "fail-immediately propagates" 3 "${RC}"
check "fail-immediately stops early" 0 "$(grep -c 'STUB relval ran' <<< "${OUT}")"

# 5. a later failure is not masked by an earlier success
STUB_RELVAL_RC=4 run_entry "${TMP}/subtests"
check "late failure propagates" 4 "${RC}"

# 6. flag forwarding is per sub-test: only "generator" accepts these flags
run_entry "${TMP}/subtests" --keep-artifacts
check "keep-artifacts reaches generator" \
      1 "$(grep -cx -- '--keep-artifacts' "${TMP}/subtests/run_generator_tests.args")"
check "keep-artifacts does not reach workflow" \
      0 "$(grep -cx -- '--keep-artifacts' "${TMP}/subtests/run_workflow_tests.args")"
check "keep-artifacts does not reach relval" \
      0 "$(grep -cx -- '--keep-artifacts' "${TMP}/subtests/run_relval_tests.args")"

echo
if [[ "${FAILURES}" == "0" ]] ; then
    echo "All run_tests.sh selection tests passed"
else
    echo "${FAILURES} test(s) failed"
fi
exit $(( FAILURES > 0 ? 1 : 0 ))
