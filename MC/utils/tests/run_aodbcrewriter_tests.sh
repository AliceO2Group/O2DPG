#!/bin/bash
#
# Self-contained regression test for MC/utils/AODBcRewriter.C.
#
#   ${O2DPG_ROOT}/MC/utils/tests/run_aodbcrewriter_tests.sh
#
# Needs nothing but ROOT — no simulation, no O2Physics, no GRID, no committed
# binary fixture.  Runs in a couple of seconds.
#
# It builds a synthetic AO2D carrying every pathology the rewriter exists to
# repair (see makeTestAOD.C), rewrites it, and then applies three independent
# layers of checking:
#
#   1. AODBcRewriterValidate()   — structural invariants of the output alone
#                                  (BC monotonicity, paste-join row parity,
#                                  index ranges, collision-group contiguity,
#                                  and that no fIndex* column is unregistered)
#   2. AODBcRewriterCheckLinks() — input vs output: no row changed what it
#                                  points at.  This is the layer that catches
#                                  O2-7098; the structural checks cannot, since
#                                  a mis-remapped index is still perfectly in
#                                  range.
#   3. testAODBcRewriter()       — named, physics-readable assertions, headed by
#                                  the MFT/MCH same-particle check the bug was
#                                  reported with.
#
# Exit code 0 = pass.

set -o pipefail

MY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$(dirname "${MY_DIR}")"
REWRITER="${UTILS_DIR}/AODBcRewriter.C"

if ! command -v root > /dev/null 2>&1; then
    echo "ERROR: no ROOT in PATH — load an O2/O2Physics/ROOT environment first" >&2
    exit 1
fi
if [ ! -f "${REWRITER}" ]; then
    echo "ERROR: cannot find ${REWRITER}" >&2
    exit 1
fi

WORKDIR=$(mktemp -d "${TMPDIR:-/tmp}/aodbcrewriter-test-XXXXXX")
trap 'rm -rf "${WORKDIR}"' EXIT
cd "${WORKDIR}" || exit 1

IN="AO2D_test.root"
OUT="AO2D_test_rewritten.root"
RC=0

run_step()
{
    local name="$1"; shift
    echo "=== ${name} ==="
    if ! "$@" > "${name}.log" 2>&1; then
        echo "--- ${name} FAILED, log follows ---" >&2
        cat "${name}.log" >&2
        RC=1
        return 1
    fi
    # ROOT macros signal failure through their return value, which the shell
    # does not see; look for the markers as well.
    if grep -q '\[FAIL\]' "${name}.log"; then
        echo "--- ${name} reported [FAIL] lines ---" >&2
        grep -E '\[FAIL\]|FAILED' "${name}.log" >&2
        RC=1
        return 1
    fi
    return 0
}

echo "Working in ${WORKDIR}"

run_step "01-make-fixture" \
    root -l -b -q "${MY_DIR}/makeTestAOD.C(\"${IN}\")"

run_step "02-rewrite" \
    root -l -b -q "${REWRITER}(\"${IN}\",\"${OUT}\")"

# From here on every step needs the rewritten file.
if [ ! -f "${OUT}" ]; then
    echo "ERROR: rewriter produced no output" >&2
    exit 1
fi

run_step "03-validate" \
    root -l -b -q -e ".L ${REWRITER}" -e "if (!AODBcRewriterValidate(\"${OUT}\")) gSystem->Exit(1);"

run_step "04-check-links" \
    root -l -b -q -e ".L ${REWRITER}" -e "if (!AODBcRewriterCheckLinks(\"${IN}\",\"${OUT}\")) gSystem->Exit(1);"

run_step "05-assertions" \
    root -l -b -q -e ".L ${REWRITER}" -e ".L ${MY_DIR}/testAODBcRewriter.C" \
         -e "if (testAODBcRewriter(\"${IN}\",\"${OUT}\") != 0) gSystem->Exit(1);"

# Surface the readable assertion results even on success.
[ -f 05-assertions.log ] && grep -E '\[ ok \]|\[FAIL\]|PASSED|FAILED' 05-assertions.log

if [ "${RC}" -eq 0 ]; then
    echo "AODBcRewriter tests: PASSED"
else
    echo "AODBcRewriter tests: FAILED"
fi
exit "${RC}"
