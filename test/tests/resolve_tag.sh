#!/bin/bash
# Offline harness for resolve_o2pdpsuite_tag: builds a fake modulefile
# directory so the function can be checked without CVMFS.

set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=../ci/resolve_tag.sh
source "${HERE}/../ci/resolve_tag.sh"
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

TMP=$(mktemp -d)
D="${TMP}/O2PDPSuite"
mkdir -p "${D}"
# Deliberately out of lexical-creation order, and with non-daily neighbours.
touch "${D}/daily-20260919-0000-1" \
      "${D}/daily-20260921-0000-1" \
      "${D}/daily-20260920-0000-1" \
      "${D}/async-2024-pp-apass1-1" \
      "${D}/slc9-nightly-20260921-1"

out=$(resolve_o2pdpsuite_tag "${D}") ; rc=$?
check "newest daily is chosen" "daily-20260921-0000-1" "${out}"
check "success exit code" 0 "${rc}"

out=$(resolve_o2pdpsuite_tag "${D}" "daily-20260919-0000-1") ; rc=$?
check "requested tag honoured" "daily-20260919-0000-1" "${out}"
check "requested tag exit code" 0 "${rc}"

out=$(resolve_o2pdpsuite_tag "${D}" "daily-20991231-0000-1" 2>/dev/null) ; rc=$?
check "absent requested tag fails" 1 "${rc}"
check "absent requested tag prints nothing on stdout" "" "${out}"

out=$(resolve_o2pdpsuite_tag "${TMP}/does-not-exist" 2>/dev/null) ; rc=$?
check "missing directory fails" 1 "${rc}"

mkdir -p "${TMP}/empty"
out=$(resolve_o2pdpsuite_tag "${TMP}/empty" 2>/dev/null) ; rc=$?
check "directory with no dailies fails" 1 "${rc}"

# A requested tag from a fork PR's body must not be able to escape the
# O2PDPSuite module directory via "..".
mkdir -p "${TMP}/O2"
touch "${TMP}/O2/something"
out=$(resolve_o2pdpsuite_tag "${D}" "../O2/something" 2>/dev/null) ; rc=$?
check "path traversal tag fails" 1 "${rc}"
check "path traversal tag prints nothing on stdout" "" "${out}"

echo
if [[ "${FAILURES}" == "0" ]] ; then
    echo "All resolve_tag tests passed"
else
    echo "${FAILURES} test(s) failed"
fi
exit $(( FAILURES > 0 ? 1 : 0 ))
