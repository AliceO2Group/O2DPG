#!/bin/bash

# Path to the JSON file
JSON_FILE=${1:-HepMC_EventSkip_ALT.json}
tf=$2

# Value to set or add
EVENTS=$(grep "DISTRIBUTING" ../tf${tf}/sgngen_*.log | tail -n 1 | awk '//{print $5}')

[ -f $JSON_FILE ] || echo "[]" > ${JSON_FILE} # init json file if it doesn't exist
# insert event count ... if a count for this tf does not already exist
JQ_COMMAND="jq 'if any(.[]; .tf == ${tf}) then . else . + [{\"tf\": ${tf}, "HepMCEventCount": ${EVENTS}}] end' ${JSON_FILE} > tmp_123.json; mv tmp_123.json ${JSON_FILE}"
eval ${JQ_COMMAND}