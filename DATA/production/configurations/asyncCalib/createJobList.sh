#!/bin/bash

# Create a list to be used for job submission of the TPC SCD correction map creation
# The scripts assumes to get as input parameter the xml collection of the o2tpc_residuals*.root file
# created for a single run.
# It creates an output file with one line per job that should be submitted and the parameters
# to be passed to each job.


# ===| input parameters |=======================================================
inputCollection=$1

# ===| timebin log file |=======================================================
TIMEBINLOGFILENAME=timeBins.log

# ===| output file creation |===================================================
sed -rn 's|.*turl="([^"]*)".*|\1|;s|.*o2tpc_residuals_([0-9_]+)\.root|\1 0 0|p' $inputCollection | sort -u > $TIMEBINLOGFILENAME

# This could be used for the old file format
if [[ $ALIEN_JDL_OLDFILENAME == "1" ]]; then
  sed -rn 's|.*turl="([^"]*)".*|\1|;s|.*/o2tpc_residuals([0-9]{7})[0-9]+\.root|\1 0 0|p' $inputCollection | sort -u > $TIMEBINLOGFILENAME
fi

# ===| sanity check |===========================================================
declare -i nLines=$(wc -l $TIMEBINLOGFILENAME | awk '{print $1}')

if [[ $nLines -eq 0 ]]; then
  echo "ERROR: Problem creating list for jobs to submit"
else
  # Add line for job over full run
  echo "-1 0 0" >> $TIMEBINLOGFILENAME
  echo "Number of jobs to submit for SCD map creation: $nLines"
fi
