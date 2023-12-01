# We determine the O2DPG task that failed (as listed in stdout) and extract the relevant log automatically
# Beware that errors might occur outside of O2DPG tasks such as in preprocessing etc or not visible in logs

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
  tar -xvzf debug_log_archive.tgz --wildcards "*${logfile}.log"
  if [[ ${logfile} == *"qedsim"* || ${logfile} == *"sgnsim"* || ${logfile} == *"bkgsim"* ]]; then
    # simulation has few more files to inspect
    tar -xvzf debug_log_archive.tgz --wildcards "*${tf}*serverlog*"
    tar -xvzf debug_log_archive.tgz --wildcards "*${tf}*workerlog*"
    tar -xvzf debug_log_archive.tgz --wildcards "*${tf}*mergerlog*"
  fi
  cd $OLDPWD
done
