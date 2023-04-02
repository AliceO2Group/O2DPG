#!/bin/bash

if [ -f o2dpg.tgz ]; then
    echo "Using O2DPG tar ball"
    tar -xzf o2dpg.tgz
    export O2DPG_ROOT=`pwd`/O2DPG
fi

echo "************* Printing environment variables *************"
set
echo "************* DONE *************"

echo "[ORIGINAL] Running $@"

args=""
nevents=0
shellscript=""

while [ ! -z "$1" ]; do
    option="$1"
    shift

    if [ "$option" = "--nevents" ]; then
        nevents=$1
        shift
    else
        if [ -z "$args" ]; then
            args="$option"
        else
            if [[ "$option" == *".sh" ]]; then
              if [[ -f $option ]]; then
                shellscript="${PWD}/$option"
              else
                shellscript=${O2DPG_ROOT}/$option
              fi
              args="$args $shellscript"
            else
              args="$args $option"
            fi
            
        fi
    fi
done

echo "  nevents (for ML counters) $nevents"
echo "  shell script $shellscript"
if [[ ! -z "$shellscript" ]]; then
    echo "************* Steering shell script *************"
    cat $shellscript
    echo "************* DONE *************"
else
    echo "Steering shell script not defined!"
fi

echo "Running ${args}"

# is passed via input files from JDL
chmod +x *.sh
chmod +x *.py

exec ${args}

