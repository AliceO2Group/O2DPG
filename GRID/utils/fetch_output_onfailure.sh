#!/bin/bash

# a script which fetches error files for each failing subjob of an AliEn GRID masterjob
MY_JOBID=$1

if [ ! "${MY_JOBID}" ]; then
  echo "Please provide a master job id as first argument"
  exit 1
fi

SUBJOBIDS=($(alien.py ps --trace ${MY_JOBID} | awk '/Subjob submitted/' | sed 's/.*submitted: //' | tr '\n' ' '))

CurrDir=${PWD}
OutputDir=/tmp/AlienLogs_${MY_JOBID}

# 
job_number=${#SUBJOBIDS[@]}


# We fetch the error files locally
for ((i = 0; i < job_number; i++)); do
  jobid=${SUBJOBIDS[i]}
  STATUS=$(alien.py ps -j ${jobid} | awk '//{print $4}')
  echo "Status of ${jobid} is $STATUS"
  if [ ${STATUS} == "EE" ]; then
    # nothing
    RecycleOutputDir=$(alien.py ps --trace ${jobid} | awk '/Going to uploadOutputFiles/' | sed 's/.*outputDir=//' | sed 's/)//')
    alien.py registerOutput ${jobid}
    echo "Recycle out is ${RecycleOutputDir}"
    alien.py cp ${RecycleOutputDir}/'*' file:${OutputDir}/${jobid}
  fi
done

echo " ... Going to automatic extraction of log files ... "

# We determine the O2DPG task that failed (as listed in stdout) and extract the relevant log automatically
# Beware that errors might occur outside of O2DPG tasks such as in preprocessing etc or not visible in logs
cd ${OutputDir}
# call the extraction script
${O2DPG_ROOT}/GRID/utils/extractErroredLogFiles.sh
echo "Files have been extracted to ${OutputDir}"
cd ${CurrDir}
