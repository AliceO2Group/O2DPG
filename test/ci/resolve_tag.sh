#!/bin/bash

# Pick the O2PDPSuite release to test against. Kept free of CVMFS paths and of
# CI variables so it can be exercised offline.

resolve_o2pdpsuite_tag()
{
    local moduledir=${1:-}
    local requested=${2:-}

    if [[ ! -d "${moduledir}" ]] ; then
        echo "resolve_o2pdpsuite_tag: no such directory: ${moduledir}" >&2
        return 1
    fi

    if [[ -n "${requested}" ]] ; then
        case ${requested} in
            *[!A-Za-z0-9._-]* )
                echo "resolve_o2pdpsuite_tag: invalid tag: ${requested}" >&2
                return 1 ;;
        esac
        if [[ ! -e "${moduledir}/${requested}" ]] ; then
            echo "resolve_o2pdpsuite_tag: requested tag not available: ${requested}" >&2
            return 1
        fi
        echo "${requested}"
        return 0
    fi

    local newest
    newest=$(find "${moduledir}" -maxdepth 1 -name 'daily-*' -printf '%f\n' 2>/dev/null |
                 sort -V | tail -n 1)
    if [[ -z "${newest}" ]] ; then
        echo "resolve_o2pdpsuite_tag: no daily-* tag in ${moduledir}" >&2
        return 1
    fi
    echo "${newest}"
}
