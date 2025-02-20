#!/bin/bash

# Simple script to find corrupted AO2Ds using the checkCorruptedAO2Ds.C macro

PRODUCTION=LHC24h2
RUN=* # use * for all runs
NJOBS=90

OUTPUTFILE=corrupted_files_$PRODUCTION.txt
if [ -e "$OUTPUTFILE" ]; then
  rm $OUTPUTFILE
fi

# find all files in alien
if [ "$variable" == "*" ]; then
  alien_find alien:///alice/sim/2024/${PRODUCTION} 5*/AOD/*/AO2D.root > files_to_check.txt
else
  alien_find alien:///alice/sim/2024/${PRODUCTION} ${RUN}/AOD/*/AO2D.root > files_to_check.txt
fi
mapfile -t FILESTOCHECK < files_to_check.txt

# process AO2Ds
process_file() {
  IFS='/' read -a num <<< "$1"
  INPUT=$1
  echo '.x checkCorruptedAO2Ds.C("'${INPUT}'", true)' | root -l -b > log_${num[5]}_${num[7]}
  echo '.q'
}
export -f process_file

parallel -j $NJOBS process_file ::: "${FILESTOCHECK[@]}"

# create list of corrupted files
touch $OUTPUTFILE
ERRORSTR="Found corrupted file!"
REPAIRSTR="Found file in need of repair!"
for FILE in "${FILESTOCHECK[@]}"; do
  IFS='/' read -a num <<< "$FILE"
  if grep -q "$ERRORSTR" log_${num[5]}_${num[7]}; then
    echo $FILE >> $OUTPUTFILE
  else grep -q "$REPAIRSTR" log_${num[5]}_${num[7]}; then
    echo $FILE >> $OUTPUTFILE
  fi
done

rm files_to_check.txt
rm log*
