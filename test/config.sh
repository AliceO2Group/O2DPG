#!/bin/bash

DISABLE_MACOS="pwgdq_generator "

check_test_enabled()
{
    local check_test=$1
    if [[ "${OSTYPE}" == "darwin"* && "$(echo ${DISABLE_MACOS} | grep ${check_test})" != "" ]] ; then
        echo ""
    else
        echo "ENABLED"
    fi
}

export -f check_test_enabled
