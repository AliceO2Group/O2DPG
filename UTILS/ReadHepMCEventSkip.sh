#!/bin/bash

# Path to the JSON file
JSON_FILE=$1
tf=$2
JQCOMMAND="jq '[.[] | select(.tf < ${tf}) | .HepMCEventCount] | add' ${JSON_FILE}"
eval ${JQCOMMAND}