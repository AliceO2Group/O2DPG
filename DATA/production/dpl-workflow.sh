#!/bin/bash

if [ "0$O2_ROOT" == "0" ]; then
    echo O2 environment not loaded 1>&2
    exit 1
fi

export DPL_CONDITION_BACKEND="http://o2-ccdb.internal"

source $O2_ROOT/prodtests/full-system-test/dpl-workflow.sh
