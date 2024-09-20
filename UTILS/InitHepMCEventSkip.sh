#!/bin/bash

# Path to the JSON file
JSON_FILE=${1:-HepMC_EventSkip_ALT.json}
EVENTS=$2

# insert event count offset
echo "[]" > ${JSON_FILE} # init json file
JQ_COMMAND="jq '. + [{"HepMCEventOffset": ${EVENTS}}]' ${JSON_FILE} > tmp_123.json; mv tmp_123.json ${JSON_FILE}"
eval ${JQ_COMMAND}

echo ${EVENTS}
