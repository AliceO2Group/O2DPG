#!/bin/bash

DETSTOREPACK="FT0,FV0,FDD"

if [[ "${1##*.}" == "root" ]]; then
    echo "${1}" > list.list
    export MODE="LOCAL"
    shift
elif [[ "${1##*.}" == "xml" ]]; then
    sed -rn 's/.*turl="([^"]*)".*/\1/p' $1 > list.list
    export MODE="remote"
    shift
fi

# ad-hoc settings for CTF reader
echo -e "\n*** mode = ${MODE} ***\n"
CTFREADEROPT=
if [[ $MODE == "remote" ]]; then
  CTFREADEROPT=" --copy-cmd no-copy "
fi

TIMEFRAME_RATE_LIMIT=500
GLOBALDPLOPT="--timeframes-rate-limit $TIMEFRAME_RATE_LIMIT --timeframes-rate-limit-ipcid 0"

WORKFLOW="o2-ctf-reader-workflow $CTFREADEROPT --ctf-input list.list --onlyDet $DETSTOREPACK --allow-missing-detectors $GLOBALDPLOPT | o2-ctf-writer-workflow --onlyDet $DETSTOREPACK --min-file-size 2000000000 $GLOBALDPLOPT -b"

echo "Printing workflow:"
echo -e "$WORKFLOW \n"

echo $WORKFLOW | bash
