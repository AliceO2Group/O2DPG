#!/bin/bash

# script to extract statistics from job

PVs=0
CTFsFilesProcessedMsg=$(grep "CTFReader stops processing," $1)
nCTFsFilesOK=`echo $CTFsFilesProcessedMsg | sed 's/.*processing, \([0-9]*\) .*/\1/'`
nCTFsFilesInspected=`grep alien_cp $1 | grep -v ALARM | grep -v non-zero | wc -l`
nCTFsProcessed=`grep "Read CTF" $1 | tail -1 | sed 's/^.*Read CTF \([0-9]*\).*$/\1/'`
while read -r line; do
  currentPVs=`echo $line | sed 's/^.*Found \([0-9]*\) PVs.*/\1/'`
  PVs=$((PVs + currentPVs))
done < <(grep "Found" $1 | grep "PVs")

echo CTFsFilesProcessedMsg = $CTFsFilesProcessedMsg
echo nCTFsFilesInspected = $nCTFsFilesInspected
echo nCTFsFilesOK = $nCTFsFilesOK
echo nCTFsProcessed = $nCTFsProcessed
echo PVs = $PVs

touch ${nCTFsFilesInspected}_${nCTFsFilesOK}_${nCTFsProcessed}_${PVs}_$1_stat.txt

