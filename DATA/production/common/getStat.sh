#!/bin/bash

# script to extract statistics from job
# $1 is the file to parse
# $2 is the (possible) extension

PVs=0
CTFsFilesProcessedMsg=$(grep "CTFReader stops processing," $1)
nCTFsFilesOK=`echo $CTFsFilesProcessedMsg | sed 's/.*processing, \([0-9]*\) .*/\1/'`
nCTFsFilesInspected=`grep alien_cp $1 | grep -v ALARM | grep -v non-zero | wc -l`
nCTFsFilesFailed=`grep "FileFetcher: non-zero exit code [0-9]*" $1 | wc -l`
nCTFsProcessed=`grep "Read CTF" $1 | tail -1 | sed 's/^.*Read CTF \([0-9]*\).*$/\1/'`
nCTFsProcessed=$((nCTFsProcessed + 1))

if [[ $nCTFsFilesInspected != $((nCTFsFilesFailed + nCTFsFilesOK)) ]]; then
  echo "Something went wrong with parsing the log file: CTF files inspected ($nCTFsFilesInspected) is not the sum of those successfully processed ($nCTFsFilesOK) and those that failed ($nCTFsFilesFailed)"
  exit 8
fi
while read -r line; do
  currentPVs=`echo $line | sed 's/^.*Found \([0-9]*\) PVs.*/\1/'`
  PVs=$((PVs + currentPVs))
done < <(grep "Found" $1 | grep "PVs")

echo CTFsFilesProcessedMsg = $CTFsFilesProcessedMsg
echo nCTFsFilesInspected = $nCTFsFilesInspected
echo nCTFsFilesOK = $nCTFsFilesOK
echo nCTFsFilesFailed = $nCTFsFilesFailed
echo nCTFsProcessed = $nCTFsProcessed
echo PVs = $PVs

if [[ -n $2 ]]; then
  echo "1" > ${nCTFsFilesInspected}_${nCTFsFilesOK}_${nCTFsFilesFailed}_${nCTFsProcessed}_${PVs}_${2}.stat
fi

echo "1" > ${nCTFsFilesInspected}_${nCTFsFilesOK}_${nCTFsFilesFailed}_${nCTFsProcessed}_${PVs}.stat

