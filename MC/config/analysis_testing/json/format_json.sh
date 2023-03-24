#!/bin/bash

# Script to format the json files

for i in $(ls *.json); do
    case "$i" in
    *analyses_config.json*)
        continue
        ;;
    esac
    echo "Formatting $i"
    jq -S . $i >a.json
    mv a.json $i
done
