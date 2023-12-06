#!/bin/bash

# a script which fetches error files for each failing subjob of an AliEn GRID masterjob
MY_JOBID=$1

if [ ! "${MY_JOBID}" ]; then
  echo "Please provide a master job id as first argument"
  exit 1
fi

# these are all subjobids
SUBJOBIDS=($(alien.py ps --trace ${MY_JOBID} | awk '/Subjob submitted/' | sed 's/.*submitted: //' | tr '\n' ' '))

# these are the one that failed
FAILEDSUBJOBIDS=($(alien.py ps -a -m ${MY_JOBID} -f ERROR_ALL | awk '/EE/{print $2}' | tr '\n' ' '))

CurrDir=${PWD}
OutputDir=/tmp/AlienLogs_${MY_JOBID}

job_number=${#FAILEDSUBJOBIDS[@]}
echo "Found ${job_number} failed job ids"
echo "Registering output for retrieval"
RecycleBase=""
# First pass to do register output
for ((i = 0; i < job_number; i++)); do
  jobid=${FAILEDSUBJOBIDS[i]}
  if [ ! "${RecycleBase}" ]; then
    RecycleOutputDir=$(alien.py ps --trace ${jobid} | awk '/Going to uploadOutputFiles/' | sed 's/.*outputDir=//' | sed 's/)//')
    # /alice/cern.ch/user/a/aliprod/recycle/alien-job-2974093751
    RecycleBase=${RecycleOutputDir%-${jobid}} # Removes the ${jobid} and yields the recycle base path
  fi
  $(alien.py registerOutput ${jobid}) 2> /dev/null
done

# wait a bit to allow propagation of "registerOutput"
sleep 1

echo "Downloading output"
# Second pass to copy files
for ((i = 0; i < job_number; i++)); do
  jobid=${FAILEDSUBJOBIDS[i]}
  RecycleOutputDir="${RecycleBase}-${jobid}"
  alien.py cp ${RecycleOutputDir}/'*archive*' file:${OutputDir}/${jobid}
  [ -f ${OutputDir}/${jobid}/log_archive.zip ] && unzip -q -o ${OutputDir}/${jobid}/log_archive.zip -d ${OutputDir}/${jobid}
done

echo " ... Going to automatic extraction of log files ... "

# We determine the O2DPG task that failed (as listed in stdout) and extract the relevant log automatically
# Beware that errors might occur outside of O2DPG tasks such as in preprocessing etc or not visible in logs
cd ${OutputDir}
# call the extraction script
${O2DPG_ROOT}/GRID/utils/extractErroredLogFiles.sh
echo "Files have been extracted to ${OutputDir}"
cd ${CurrDir}
