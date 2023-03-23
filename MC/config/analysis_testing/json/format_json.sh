#!/bin/bash

# Script to format the json files

for i in $(ls *.json); do
echo "Formatting $i"
jq -S . $i  > a.json
mv a.json $i
done

