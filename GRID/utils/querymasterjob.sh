#!/bin/bash

# A script which queries the (latest) masterjob given an AliEn jobtype

MY_JOBTYPE=$1
if [ ! "${MY_JOBTYPE}" ]; then
  echo "Please provide a job type as first argument"
  exit 1
fi

# use curl to fetch the table of jobs for this jobtype
URL="https://alimonitor.cern.ch/prod/jobs.jsp?t=${MY_JOBTYPE}&res_path=csv"
echo "Querying ${URL}"
latestjob=$(curl --cert ~/.globus/usercert.pem --key ~/.globus/userkey.pem -k -s --no-keepalive -H "Connection: close" ${URL} 2> /dev/null | grep -v "Run" | head -n 1)

#The output format is
#PID;Run number;Packages;Output directory;Total jobs;Done jobs;Running jobs;Waiting jobs;Error jobs;Other jobs;Wall time;Saving time;Output size
# split string on ";"
IFS=';' read -r -a tokens <<< "$latestjob"
masterid=${tokens[0]}
if [ ! "${masterid}" ]; then
  exit 1
fi

totaljobs=${tokens[4]}
donejobs=${tokens[5]}
runningjobs=${tokens[6]}
erroredjobs=${tokens[8]}
echo "MasterID $masterid"
echo "TotalJobs $totaljobs"
echo "DoneJobs $donejobs"
echo "RunningJobs $donejobs"
echo "ErroredJobs $erroredjobs"
