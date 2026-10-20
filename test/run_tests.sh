#!/bin/bash

# Single entrypoint for the O2DPG tests. Runs the generator, workflow and
# RelVal sub-tests, aggregates their exit codes and prints the collected log.

set -u

SUBTEST_DIR=${O2DPG_TEST_SUBTEST_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}

ALL_SUBTESTS="generator workflow relval"

print_usage()
{
    echo
    echo "usage: run_tests.sh [--fail-immediately] [--keep-artifacts] [SUBTEST...]"
    echo
    echo "  SUBTEST : one or more of: ${ALL_SUBTESTS} (default: all)"
    echo
    echo "  FLAGS:"
    echo
    echo "  --fail-immediately : stop after the first failing sub-test"
    echo "  --keep-artifacts   : keep simulation artifacts, not just the logs"
    echo
    echo "  ENVIRONMENT VARIABLES:"
    echo
    echo "  O2DPG_TEST_REPO_DIR  : the source repository to test"
    echo "  O2DPG_TEST_HASH_BASE : base hash for the changed-file diff (optional)"
    echo "  O2DPG_TEST_HASH_HEAD : head hash for the changed-file diff (optional)"
    echo
}

fail_immediately=
subtest_args=()
selected=()

while [ "$#" -gt 0 ] ; do
    case $1 in
        --fail-immediately ) fail_immediately=1 ; subtest_args+=("$1") ; shift ;;
        --keep-artifacts )   subtest_args+=("$1") ; shift ;;
        --help|-h )          print_usage ; exit 1 ;;
        generator|workflow|relval ) selected+=("$1") ; shift ;;
        * )                  echo "Unknown argument ${1}" ; print_usage ; exit 1 ;;
    esac
done

[[ "${#selected[@]}" == "0" ]] && read -r -a selected <<< "${ALL_SUBTESTS}"

# Geant4 dataset variables, if a Geant4 installation is in the environment.
if [[ -n "${G4INSTALL:-}" ]] ; then
    eval "$("${G4INSTALL}/bin/geant4-config" --datasets |
              sed -e 's/[^ ]* //' -e 's/G4/export G4/' -e 's/DATA /DATA=/')"
fi

# O2's CCDB dictionary payload includes <curl/curl.h>. An aliBuild build
# environment has curl's headers; a plain runtime environment from CVMFS does
# not, and cling then dies compiling the payload. Derive the prefix from
# curl-config rather than hardcoding a version.
if command -v curl-config > /dev/null 2>&1 ; then
    curl_include=$(curl-config --prefix 2>/dev/null)/include
    if [[ -f "${curl_include}/curl/curl.h" && ":${ROOT_INCLUDE_PATH:-}:" != *":${curl_include}:"* ]] ; then
        export ROOT_INCLUDE_PATH="${curl_include}${ROOT_INCLUDE_PATH:+:${ROOT_INCLUDE_PATH}}"
        echo "Added ${curl_include} to ROOT_INCLUDE_PATH for the CCDB dictionary"
    fi
fi

# LHAPDF data, needed by several generator configurations.
if [[ -z "${LHAPDF_DATA_PATH:-}" && -n "${LHAPDF_ROOT:-}" ]] ; then
    export LHAPDF_DATA_PATH="${LHAPDF_ROOT}/share/LHAPDF:${LHAPDF_PDFSETS_ROOT:-}/share/LHAPDF"
    echo "Set LHAPDF_DATA_PATH to ${LHAPDF_DATA_PATH}"
fi

ret_global=0
for subtest in "${selected[@]}" ; do
    script="${SUBTEST_DIR}/run_${subtest}_tests.sh"
    if [[ ! -x "${script}" ]] ; then
        echo "ERROR: sub-test script ${script} not found or not executable"
        ret_global=1
        [[ "${fail_immediately}" == "1" ]] && break
        continue
    fi
    echo
    echo "==> START SUBTEST: ${subtest} <=="
    # Only run_generator_tests.sh accepts --fail-immediately/--keep-artifacts;
    # run_workflow_tests.sh and run_relval_tests.sh accept only --help/-h.
    case ${subtest} in
        generator ) forward=("${subtest_args[@]:-}") ;;
        * )         forward=() ;;
    esac
    "${script}" "${forward[@]}"
    ret_this=$?
    echo "==> END SUBTEST: ${subtest} (exit ${ret_this}) <=="
    if [[ "${ret_this}" != "0" ]] ; then
        ret_global=${ret_this}
        [[ "${fail_immediately}" == "1" ]] && break
    fi
done

echo
if [[ "${ret_global}" != "0" ]] ; then
    echo "error detected in O2DPG tests, see above"
else
    echo "O2DPG tests passed"
fi

exit ${ret_global}
