#!/bin/bash

# Path to the JSON file
JSON_FILE=$1
tf=$2

# get event offset
JQCOMMAND="jq '.[] | select(.HepMCEventOffset) | .HepMCEventOffset' ${JSON_FILE}"
offset=`eval ${JQCOMMAND}`
if [ ! $offset ]
then
  offset=0
fi

# count generated events
JQCOMMAND="jq '[.[] | select(.tf < ${tf}) | .HepMCEventCount] | add' ${JSON_FILE}"
events=`eval ${JQCOMMAND}`
if [ ! $events ]
then
  events=0
fi

# total number of events to skip
echo $((offset + events))
