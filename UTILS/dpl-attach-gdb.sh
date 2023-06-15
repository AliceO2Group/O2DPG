#!/bin/bash
dplname=$1
while [ 1 ] ; do
  proc=$(ps aux | grep "id ${dplname}" | grep -v "grep" | awk '//{print $2}')
  if [ ${proc} ] ; then
    echo "FOUND ${proc} ... attaching gdb"
    gdb --pid ${proc}
    exit 0
  fi
  sleep 0.01
done
