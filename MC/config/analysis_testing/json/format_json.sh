#!/bin/bash

# Script to format the json files

jq -S . analysis-testing-data.json  > a.json
mv a.json analysis-testing-data.json
jq -S . analysis-testing-mc.json  > b.json
mv b.json analysis-testing-mc.json
jq -S . analysis-testing-EventTrackQA-data.json  > c.json
mv c.json analysis-testing-EventTrackQA-data.json

