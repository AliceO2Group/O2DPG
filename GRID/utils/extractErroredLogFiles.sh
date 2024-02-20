#!/usr/bin/env bash

# We determine the O2DPG task that failed (as listed in stdout) and extract the relevant log automatically
# Beware that errors might occur outside of O2DPG tasks such as in preprocessing etc or not visible in logs

mytar () {
  tar "$@"
}
if [[ $(uname) == "Darwin" ]]; then
    echo "Running on macOS. This needs gnu-tar"
    $(which gtar)
    mytar () {
      gtar "$@"
    }
fi

errored_tasks=""
find ./ -name "stdout*" -exec grep -H "failed.*retry" {} ';' | sed 's/ failed.*//' | tr ":" " " | while IFS= read -r line; do
  stdoutpath=$(echo "$line" | awk '{print $1}')  # Extracting the first column
  logfile=$(echo "$line" | awk '{print $2}')  # Extracting the second column

  dir=$(dirname ${stdoutpath})
  cd ${dir}
  # determine a timeframe number (if applicable)
  # Extracting the timeframe 'tf'
  tf=${logfile#*_} # Removes everything before the first underscore
  tf=${tf%.log} # Removes the ".log" extension
  echo "Extracted timeframe ${tf}"
  
  # extract the general log archive
  unzip -n log_archive.zip
  # extract specific task log from debug archive
  mytar -xvzf debug_log_archive.tgz --wildcards "*${logfile}.log"
  if [[ ${logfile} == *"qedsim"* || ${logfile} == *"sgnsim"* || ${logfile} == *"bkgsim"* ]]; then
    # simulation has few more files to inspect
    mytar -xvzf debug_log_archive.tgz --wildcards "*${tf}*serverlog*"
    mytar -xvzf debug_log_archive.tgz --wildcards "*${tf}*workerlog*"
    mytar -xvzf debug_log_archive.tgz --wildcards "*${tf}*mergerlog*"
  fi
  cd $OLDPWD
done
