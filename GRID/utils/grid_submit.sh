#!/bin/bash

# A helper script, making it easy to submit existing
# scripts as an ALIEN GRID job (with the following notation):
#
# grid-submit --script my_script.sh --jobname jobname
#
# The script then handles all interaction with the GRID automatically. The user
# does not need to create JDLs files nor upload them to the GRID manually/herself.
#
# The script can also simulate execution of the job locally. To this end, it suffices
# to say
#
# grid-submit --script my_script.sh --jobname jobname --local
#
# Currently handles only a very basic JDL configuration. Further improvements would be:
#
# -) allow JDL customization via command line arguments or JDL tags inside the script
#
# author: Sandro Wenzel

# set -o pipefail

function per() { printf "\033[31m$1\033[m\n" >&2; }
function pok() { printf "\033[32m$1\033[m\n" >&2; }
function banner() { echo ; echo ==================== $1 ==================== ; }

function Usage() { echo "$0 --script scriptname | -c WORKDIR_RELATIVE_TO_TOP [ --jobname JOBNAME ] [ --topworkdir WORKDIR (ON TOP OF HOME) ] "; }

notify_mattermost() {
  set +x
  if [ "$MATTERMOSTHOOK" ]; then
    text=$1
    COMMAND="curl -X POST -H 'Content-type: application/json' --data '{\"text\":\""${text}"\"}' "${MATTERMOSTHOOK}" &> /dev/null"
    eval "${COMMAND}"  
  fi
}

starthook() {
  notify_mattermost "${ALIEN_PROC_ID}: Starting stage $2"
}

uploadlogs() {
  # MOMENTARILY WE ZIP ALL LOG FILES
  zip logs_PROCID${ALIEN_PROC_ID:-0}_failure.zip *.log* *mergerlog* *serverlog* *workerlog* alien_log_${ALIEN_PROC_ID:-0}_failure.txt
  [ "${ALIEN_JOB_OUTPUTDIR}" ] && upload_to_Alien logs_PROCID${ALIEN_PROC_ID:-0}_failure.zip  ${ALIEN_JOB_OUTPUTDIR}/
}
export -f uploadlogs
failhook() {
  notify_mattermost "${ALIEN_PROC_ID}: **Failure** in stage $2"
  cp alien_log_${ALIEN_PROC_ID:-0}.txt logtmp_${ALIEN_PROC_ID:-0}_failure.txt

  # MOMENTARILY WE ZIP ALL LOG FILES
  uploadlogs
}

export -f starthook
export -f failhook
export JOBUTILS_JOB_STARTHOOK="starthook"
export JOBUTILS_JOB_FAILUREHOOK="failhook"

# uploads a file to an alien path and performs some error checking
upload_to_Alien() {
  set -x
  SOURCEFILE=$1  # needs to be a file in the local dir --> verify
  DEST=$2  # needs to be a path
  notify_mattermost "UPLOADING TO ALIEN: alien.py cp -f file:$SOURCEFILE ${DEST}"
  alien.py cp -f file:$SOURCEFILE ${DEST}
  RC=$?
  [ ! "${RC}" = "0" ] && notify_mattermost "COPY OF FILE ${SOURCEFILE} TO ${DEST} RETURNED ${RC}"
  # make a check 
  alien.py ls ${DEST}/${SOURCEFILE}
  RC=$?
  [ ! "${RC}" = "0" ] && notify_mattermost "LS OF FILE ${DEST}/${SOURCEFILE} RETURNED ${RC}"

  alien.py xrdstat ${DEST}/${SOURCEFILE} | awk 'BEGIN{c=0}/root:/{if($3="OK"){c=c+1}} END {if(c>=2) {exit 0}else{ exit 1}}'
  RC=$?
  notify_mattermost "FINISHED UPLOADING TO ALIEN: alien.py cp -f file:$SOURCEFILE ${DEST} ${RC}"
  set +x
  return ${RC}
}
export -f upload_to_Alien

# This hook is registered and periodically executed 
# in the taskwrapper control loop (assuming individual stages of GRID workflows are 
# executed within taskwrapper).
# We use it here as a means to remote-control GRID jobs. For instance,
# one might want to ask a GRID job to upload its current log files to ALIEN for
# immediate inspection, which may be useful for debugging.
control_hook() {
  # Here we are talking to a remote webserver from which we query
  # control commands to act upon this GRID process. The webserver is
  # supposed to return a single command word.
  command=$(curl ${CONTROLSERVER}/?procid=${ALIEN_PROC_ID} 2> /dev/null)
  if [ "$command" = "uploadlogs" ]; then
    notify_mattermost "Control command **uploadlogs** for ${ALIEN_PROC_ID}"
    uploadlogs & # -> background it in order to return immediately
  elif [ "$command" = "kill" ]; then
    echo "killing job"
    taskwrapper_cleanup $PID SIGKILL
    exit 1
  fi
}
export -f control_hook
export JOBUTILS_JOB_PERIODICCONTROLHOOK="control_hook"

# A hook which can be registered at end of "taskwrapper" tasks.
# Here this hook performs a few steps
# a) send task metrics to a mattermost channel
# b) checks if we are approaching TTL and take appropriate action, e.g.
#     - do a checkpoint
#     - upload some files to ALIEN
#     - stop remaining worklow to prevent hard external timeout
checkpoint_hook_ttlbased() {
  RC=$3 # return code of stage
  timepassedsincestart=$SECONDS
  walltime=`cat $2_time`
  text1="${ALIEN_PROC_ID} checkpoint check for $2; ${SECONDS} passed since job start out of ${JOBTTL}"
  notify_mattermost "${text1}"
  cpumodel=`grep -m 1 "model name" /proc/cpuinfo | sed 's/.*://' | tr ' ' '_'`

  # analyse CPU utilization
  corecount=$(grep "processor" /proc/cpuinfo | wc -l)
  path=$PWD
  cpuusage=$(analyse_CPU.py $PWD/$2_cpuusage ${corecount} 2>/dev/null)

  # analyse memory util
  maxmem=$(grep "PROCESS MAX MEM" ${path}/$2 | awk '//{print $5}')
  avgmem=$(grep "PROCESS AVG MEM" ${path}/$2 | awk '//{print $5}')

  metrictext="#pdpmetric:${JOBLABEL},procid:${ALIEN_PROC_ID},CPU:${cpumodel},stage:$2,RC:${RC:-1},walltime:${walltime},${cpuusage},MAXMEM:${maxmem},AVGMEM:${avgmem}"
  notify_mattermost "${metrictext}"

  # do calculation with AWK
  CHECKPOINT=$(awk -v S="${SECONDS}" -v T="${JOBTTL}" '//{} END{if(S/T>0.8){print "OK"}}' < /dev/null);
  if [ "$CHECKPOINT" = "OK" ]; then
    echo "**** TTL CLOSE - CHECKPOINTING *****"
    # upload
    text="CHECKPOINTING NOW"
    # resubmit
    notify_mattermost "${text}"

    # remove garbage (pipes, sockets, etc)  
    find ./ -size 0 -delete

    # make tarball (no compression to be fast and ROOT files are already compressed)
    tar --exclude "output" -cf checkpoint.tar *
 
    text="TARING RETURNED $? and it has size $(ls -al checkpoint.tar)"
    notify_mattermost "${text}"

    
    # This section is experimental: It should allow to resubmit a new job straight away
    # which can continue working on a workflow starting from the created checkpoint

    # upload tarball
    #  [ "${ALIEN_JOB_OUTPUTDIR}" ] && upload_to_Alien checkpoint.tar ${ALIEN_JOB_OUTPUTDIR}/

    # resubmit
    # if [ "$?" = "0" ]; then
    #   notify_mattermost "RESUBMITTING"
    #    [ "${ALIEN_JOB_OUTPUTDIR}" ] && ${ALIEN_DRIVER_SCRIPT} -c `basename ${ALIEN_JOB_OUTPUTDIR}` --jobname CONTINUE_ID${ALIEN_PROC_ID} --topworkdir foo --o2tag ${O2_PACKAGE_LATEST} --asuser aliperf --ttl ${JOBTTL}
    # fi

    # exit current workflow
    exit 0
  fi
}
export -f checkpoint_hook_ttlbased
export -f notify_mattermost
export JOBUTILS_JOB_ENDHOOK=checkpoint_hook_ttlbased

sanitize_tokens_with_quotes() {
  string=$1
  result=""
  # Set the IFS to comma (,) to tokenize the string
  IFS=',' read -ra tokens <<< "$string"
  for token in "${tokens[@]}"; do
    [[ $result ]] && result=${result}","
    # Use pattern matching to check if the token is quoted within double quotes
    if [[ $token =~ ^\".*\"$ ]]; then
      result=$result$token
    else
      result=$result"\"${token}\""
    fi
  done
  echo ${result}
}

# find out if this script is really executed on GRID
# in this case, we should find an environment variable JALIEN_TOKEN_CERT
ONGRID=0
[ "${JALIEN_TOKEN_CERT}" ] && ONGRID=1

JOBTTL=82000
CPUCORES=8
PRODSPLIT=${PRODSPLIT:-1}
# this tells us to continue an existing job --> in this case we don't create a new workdir
while [ $# -gt 0 ] ; do
    case $1 in
	      -c) CONTINUE_WORKDIR=$2;  shift 2 ;;   # this should be the workdir of a job to continue (without HOME and ALIEN_TOPWORKDIR)
        --local) LOCAL_MODE="ON"; shift 1 ;;   # if we want emulate execution in the local workdir (no GRID interaction)
        --script) SCRIPT=$2; shift 2 ;;  # the job script to submit
        --jobname) JOBNAME=$2; shift 2 ;; # the job name associated to the job --> determined directory name on GRID
        --topworkdir) ALIEN_TOPWORKDIR=$2; shift 2 ;; # the top workdir relative to GRID home
        --ttl) JOBTTL=$2; shift 2 ;; # allows to specifiy ttl for job
        --partition) GRIDPARTITION=$2; shift 2 ;; # allows to specificy a GRID partition for the job
        --cores) CPUCORES=$2; shift 2 ;; # allow to specify the CPU cores (check compatibility with partition !)
        --dry) DRYRUN="ON"; shift 1 ;; # do a try run and not actually interact with the GRID (just produce local jdl file)
        --o2tag) O2TAG=$2; shift 2 ;; #
	--packagespec) PACKAGESPEC=$2; shift 2 ;; # the alisw, cvmfs package list (command separated - example: '"VO_ALICE@FLUKA_VMC::4-1.1-vmc3-1","VO_ALICE@O2::daily-20230628-0200-1"')
        --asuser) ASUSER=$2; shift 2 ;; #
        --label) JOBLABEL=$2; shift 2 ;; # label identifying the production (e.g. as a production identifier)
        --mattermost) MATTERMOSTHOOK=$2; shift 2 ;; # if given, status and metric information about the job will be sent to this hook
        --controlserver) CONTROLSERVER=$2; shift 2 ;; # allows to give a SERVER ADDRESS/IP which can act as controller for GRID jobs
        --prodsplit) PRODSPLIT=$2; shift 2 ;; # allows to set JDL production split level (useful to easily replicate workflows)
        --singularity) SINGULARITY=ON; shift 1 ;; # run everything inside singularity
        --wait) WAITFORALIEN=ON; shift 1 ;; #wait for alien jobs to finish
        --wait-any) WAITFORALIENANY=ON; WAITFORALIEN=ON; shift 1 ;; #wait for any good==done alien jobs to return
        --outputspec) OUTPUTSPEC=$2; shift 2 ;; #provide comma separate list of JDL file specs to be put as part of JDL Output field (example '"*.log@disk=1","*.root@disk=2"')
	-h) Usage ; exit ;;
        --help) Usage ; exit ;;
        --fetch-output) FETCHOUTPUT=ON; shift 1 ;; # if to fetch all JOB output locally (to make this job as if it ran locally); only works when we block until all JOBS EXIT
        *) break ;;
    esac
done
export JOBTTL
export JOBLABEL
export MATTERMOSTHOOK
export CONTROLSERVER

[[ $PRODSPLIT -gt 100 ]] && echo "Production split needs to be smaller than 100 for the moment" && exit 1

# check for presence of jq (needed in code path to fetch output files)
[[ "$FETCHOUTPUT" ]] && { which jq &> /dev/null || { echo "Could not find jq command. Please load or install" && exit 1; }; }

# check if script is actually a valid file and fail early if not
[[ "${SCRIPT}" ]] && [[ ! -f "${SCRIPT}" ]] && echo "Script file ${SCRIPT} does not exist .. aborting" && exit 1

# analyse options:
# we should either run with --script or with -c
[ "${SCRIPT}" ] && [ "$CONTINUE_WORKDIR" ] && echo "Script and continue mode not possible at same time" && exit 1
if [ "${ONGRID}" = 0 ]; then
  [[ ! ( "${SCRIPT}" || "$CONTINUE_WORKDIR" ) ]] && echo "Either script or continue mode required" && exit 1
fi

# General job configuration
MY_USER=${ALIEN_USER:-`whoami`}

alien.py whois -a ${MY_USER}

if [[ ! $MY_USER ]]; then
  per "Problems retrieving current AliEn user. Did you run alien-token-init?"
  exit 1
fi

[ "${ASUSER}" ] && MY_USER=${ASUSER}

MY_HOMEDIR="/alice/cern.ch/user/${MY_USER:0:1}/${MY_USER}"
MY_JOBPREFIX="$MY_HOMEDIR/${ALIEN_TOPWORKDIR:-selfjobs}"
MY_JOBSCRIPT="$(cd "$(dirname "${SCRIPT}")" && pwd -P)/$(basename "${SCRIPT}")" # the job script with full path
MY_JOBNAME=${JOBNAME:-$(basename ${MY_JOBSCRIPT})}
MY_JOBNAMEDATE="${MY_JOBNAME}-$(date -u +%Y%m%d-%H%M%S)"
MY_JOBWORKDIR="${MY_JOBPREFIX}/${MY_JOBNAMEDATE}"  # ISO-8601 UTC
[ "${CONTINUE_WORKDIR}" ] && MY_JOBWORKDIR="${MY_JOBPREFIX}/${CONTINUE_WORKDIR}"
MY_BINDIR="$MY_JOBWORKDIR"

pok "Your job's working directory will be $MY_JOBWORKDIR"
pok "Set the job name by running $0 <scriptname> <jobname>"

#
# Generate local workdir
#
if [[ "${ONGRID}" == "0" ]]; then
  GRID_SUBMIT_WORKDIR=${GRID_SUBMIT_WORKDIR:-${TMPDIR:-/tmp}/alien_work/$(basename "$MY_JOBWORKDIR")}
  echo "WORKDIR FOR THIS JOB IS ${GRID_SUBMIT_WORKDIR}"
  [ ! -d "${GRID_SUBMIT_WORKDIR}" ] && mkdir -p ${GRID_SUBMIT_WORKDIR}
  [ ! "${CONTINUE_WORKDIR}" ] && cp "${MY_JOBSCRIPT}" "${GRID_SUBMIT_WORKDIR}/alien_jobscript.sh"
fi

# 
# Submitter code (we need to submit whenever a script is given as input and we are not in local mode)
#
[[ ( ! "${LOCAL_MODE}" ) && ( "${SCRIPT}" || "${CONTINUE_WORKDIR}" ) ]] && IS_ALIEN_JOB_SUBMITTER=ON

if [[ "${IS_ALIEN_JOB_SUBMITTER}" ]]; then
  #  --> test if alien is there?
  which alien.py &> /dev/null
  # check exit code
  if [[ ! "$?" == "0"  ]]; then
    XJALIEN_LATEST=`find /cvmfs/alice.cern.ch/el7-x86_64/Modules/modulefiles/xjalienfs -type f -printf "%f\n" | tail -n1`
    banner "Loading xjalienfs package $XJALIEN_LATEST since not yet loaded"
    eval "$(/cvmfs/alice.cern.ch/bin/alienv printenv xjalienfs::"$XJALIEN_LATEST")"
  fi

 
  # read preamble from job file which is used whenever command line not given
  # -) OutputSpec
  [[ ! ${OUTPUTSPEC} ]] && OUTPUTSPEC=$(grep "^#JDL_OUTPUT=" ${SCRIPT} | sed 's/#JDL_OUTPUT=//')
  echo "Found OutputSpec to be ${OUTPUTSPEC}"
  if [ ! ${OUTPUTSPEC} ]; then
    echo "No file output requested. Please add JDL_OUTPUT preamble to your script"
    echo "Example: #JDL_OUTPUT=*.dat@disk=1,result/*.root@disk=2"
    exit 1
  else
    # check if this is a list and if all parts are properly quoted
    OUTPUTSPEC=$(sanitize_tokens_with_quotes ${OUTPUTSPEC})
  fi
  # -) ErrorOutputSpec
  [[ ! ${ERROROUTPUTSPEC} ]] && ERROROUTPUTSPEC=$(grep "^#JDL_ERROROUTPUT=" ${SCRIPT} | sed 's/#JDL_ERROROUTPUT=//')
  echo "Found ErrorOutputSpec to be ${ERROROUTPUTSPEC}"
  if [ ${ERROROUTPUTSPEC} ]; then
    # check if this is a list and if all parts are properly quoted
    ERROROUTPUTSPEC=$(sanitize_tokens_with_quotes ${ERROROUTPUTSPEC})
  fi
  # -) Special singularity / Apptainer image
  [[ ! ${IMAGESPEC} ]] && IMAGESPEC=$(grep "^#JDL_IMAGE=" ${SCRIPT} | sed 's/#JDL_IMAGE=//')
  echo "Found Container Image to be ${IMAGESPEC}"

  # -) Requirements-Spec
  REQUIRESPEC=$(grep "^#JDL_REQUIRE=" ${SCRIPT} | sed 's/#JDL_REQUIRE=//')
  if [ ! "${REQUIRESPEC}" ]; then
    echo "No Requirement setting found; Setting to default"
    REQUIRESPEC="{member(other.GridPartitions,"${GRIDPARTITION:-multicore_8}")};"
    echo "Requirement is ${REQUIRESPEC}"
  fi

  echo "Requirements JDL entry is ${REQUIRESPEC}"

  # -) PackageSpec
  [[ ! ${PACKAGESPEC} ]] && PACKAGESPEC=$(grep "^#JDL_PACKAGE=" ${SCRIPT} | sed 's/#JDL_PACKAGE=//')
  echo "Found PackagesSpec to be ${PACKAGESPEC}"
  ## sanitize package spec
  ## "no package" defaults to O2sim
  if [ ! ${PACKAGESPEC} ]; then
    PACKAGESPEC="O2sim"
    O2SIM_LATEST=`find /cvmfs/alice.cern.ch/el7-x86_64/Modules/modulefiles/O2sim -type f -printf "%f\n" | tail -n1`
    if [ ! ${O2SIM_LATEST} ]; then
      echo "Cannot lookup latest version of implicit package O2sim from CVFMS"
      exit 1
    else
      PACKAGESPEC="${PACKAGESPEC}::${O2SIM_LATEST}"
      echo "Autosetting Package to ${PACKAGESPEC}"
    fi
  fi
  ## *) add VO_ALICE@ in case not there
  [[ ! ${PACKAGESPEC} == VO_ALICE@* ]] && PACKAGESPEC="VO_ALICE@"${PACKAGESPEC}
  ## *) apply quotes
  PACKAGESPEC=$(sanitize_tokens_with_quotes ${PACKAGESPEC})

   # Create temporary workdir to assemble files, and submit from there (or execute locally)
  cd "$(dirname "$0")"
  THIS_SCRIPT="$PWD/$(basename "$0")"

  cd "${GRID_SUBMIT_WORKDIR}"

  QUOT='"'
  # ---- Generate JDL ----------------
  # TODO: Make this configurable or read from a preamble section in the jobfile
  cat > "${MY_JOBNAMEDATE}.jdl" <<EOF
Executable = "${MY_BINDIR}/${MY_JOBNAMEDATE}.sh";
Arguments = "${CONTINUE_WORKDIR:+"-c ${CONTINUE_WORKDIR}"} --local ${O2TAG:+--o2tag ${O2TAG}} --ttl ${JOBTTL} --label ${JOBLABEL:-label} --prodsplit ${PRODSPLIT} ${MATTERMOSTHOOK:+--mattermost ${MATTERMOSTHOOK}} ${CONTROLSERVER:+--controlserver ${CONTROLSERVER}}";
InputFile = "LF:${MY_JOBWORKDIR}/alien_jobscript.sh";
${PRODSPLIT:+Split = ${QUOT}production:1-${PRODSPLIT}${QUOT};}
OutputDir = "${MY_JOBWORKDIR}/${PRODSPLIT:+#alien_counter_03i#}";
Requirements = member(other.GridPartitions,"${GRIDPARTITION:-multicore_8}");
CPUCores = "${CPUCORES}";
MemorySize = "60GB";
TTL=${JOBTTL};
EOF
  echo "Output = {"${OUTPUTSPEC:-\"logs*.zip@disk=1\",\"AO2D.root@disk=1\"}"};" >> "${MY_JOBNAMEDATE}.jdl"  # add output spec
  echo "Packages = {"${PACKAGESPEC}"};" >> "${MY_JOBNAMEDATE}.jdl"   # add package spec
  [ $ERROROUTPUTSPEC ] && echo "OutputErrorE = {"${ERROROUTPUTSPEC}"};" >> "${MY_JOBNAMEDATE}.jdl"   # add error output files
  [ $IMAGESPEC ] && echo "DebugTag = {\"${IMAGESPEC}\"};" >> "${MY_JOBNAMEDATE}.jdl"   # use special singularity image to run job
  # echo "Requirements = {"${REQUIREMENTSSPEC}"} >> "${MY_JOBNAMEDATE}.jdl"
  [ "$REQUIRESPEC" ] && echo "Requirements = ${REQUIRESPEC}" >> "${MY_JOBNAMEDATE}.jdl"

# "output_arch.zip:output/*@disk=2",
# "checkpoint*.tar@disk=2"

  pok "Local working directory is $PWD"
  if [ ! "${DRYRUN}" ]; then
    command_file="alien_commands.txt"

    pok "Preparing job \"$MY_JOBNAMEDATE\""
    (
      # assemble all GRID interaction in a single script / transaction
      [ -f "${command_file}" ] && rm ${command_file}
      echo "user ${MY_USER}" >> ${command_file}
      echo "whoami" >> ${command_file}
      [ ! "${CONTINUE_WORKDIR}" ] && echo "rmdir ${MY_JOBWORKDIR}" >> ${command_file}    # remove existing job dir
      # echo "mkdir ${MY_BINDIR}" >> ${command_file}                      # create bindir
      echo "mkdir ${MY_JOBPREFIX}" >> ${command_file}                   # create job output prefix
      [ ! "${CONTINUE_WORKDIR}" ] && echo "mkdir ${MY_JOBWORKDIR}" >> ${command_file}
      [ ! "${CONTINUE_WORKDIR}" ] && echo "mkdir ${MY_JOBWORKDIR}/output" >> ${command_file}
      echo "rm ${MY_BINDIR}/${MY_JOBNAMEDATE}.sh" >> ${command_file}    # remove current job script
      echo "cp file:${PWD}/${MY_JOBNAMEDATE}.jdl alien://${MY_JOBWORKDIR}/${MY_JOBNAMEDATE}.jdl@DISK=1" >> ${command_file}  # copy the jdl
      echo "cp file:${THIS_SCRIPT} alien://${MY_BINDIR}/${MY_JOBNAMEDATE}.sh@DISK=1" >> ${command_file}  # copy current job script to AliEn
      [ ! "${CONTINUE_WORKDIR}" ] && echo "cp file:${MY_JOBSCRIPT} alien://${MY_JOBWORKDIR}/alien_jobscript.sh" >> ${command_file}
    ) > alienlog.txt 2>&1

    pok "Submitting job \"${MY_JOBNAMEDATE}\" from $PWD"
    (
      echo "submit ${MY_JOBWORKDIR}/${MY_JOBNAMEDATE}.jdl" >> ${command_file}

      # finally we do a single call to alien:
      alien.py < ${command_file}
    ) >> alienlog.txt 2>&1

    MY_JOBID=$( (grep 'Your new job ID is' alienlog.txt | grep -oE '[0-9]+' || true) | sort -n | tail -n1)
    if [[ $MY_JOBID ]]; then
      pok "OK, display progress on https://alimonitor.cern.ch/agent/jobs/details.jsp?pid=$MY_JOBID"
    else
      per "Job submission failed: error log follows"
      cat alienlog.txt
      exit 1
    fi
  fi


  # wait here until all ALIEN jobs have returned
  spin[3]="-"
  spin[2]="/"
  spin[1]="|"
  spin[0]="\\"
  JOBSTATUS="I"
  if [ "${WAITFORALIEN}" ]; then
    echo -n "Waiting for jobs to return ... Last status : ${spin[0]} ${JOBSTATUS}"
  fi
  counter=0
  while [ "${WAITFORALIEN}" ]; do
    # consider making this a "you call me when you are done with curl hook or something"
    sleep 0.5
    echo -ne "\b\b\b${spin[$((counter%4))]} ${JOBSTATUS}"
    let counter=counter+1
    if [ ! "${counter}" == "100" ]; then
      # ensures that we see spinner ... but only check for new job
      # status every 100 * 0.5 = 50s?
      continue
    fi
    let counter=0 # reset counter

    # this is the global job status (a D here means the production is done)
    JOBSTATUS=$(alien.py ps -j ${MY_JOBID} | awk '//{print $3}') # this is the global job status
    # in addition we may query individual splits
    if [ -n "${WAITFORALIENANY}" ]; then
      DETAILED_STATUS_JSON=$(ALIENPY_JSON=true alien.py ps -a -m "${MY_JOBID}")
      # check if any is already marked as DONE
      if jq -e '.results | any(.status == "DONE")' <<<"${DETAILED_STATUS_JSON}" >/dev/null; then
        JOBSTATUS="D"
        echo "At least one good job"
      else
        # check if there are still jobs running/waiting; if not also finish
        # this could happen when all jobs are zombies (in which case we also finish)
        if ! jq -e '.results | any(.status == "WAITING" or .status == "RUNNING" or .status == "SAVING" or .status == "INSERTING")' \
            <<<"${DETAILED_STATUS_JSON}" >/dev/null; then
              JOBSTATUS="D"  # some job finished successfully
              echo "No remaining good job"
        fi
      fi
    fi

    if [ "${JOBSTATUS}" == "D" ]; then
      echo "${WAITFORALIENANY:+At least one }Job(s) done"
      WAITFORALIEN=""  # guarantees to go out of outer while loop

      if [ "${FETCHOUTPUT}" ]; then
          SUBJOBIDS=()
          SUBJOBSTATUSES=()
          echo "Fetching subjob info"
          while [ "${#SUBJOBIDS[@]}" == "0" ]; do
            QUERYRESULT=$(ALIENPY_JSON=true alien.py ps -a -m ${MY_JOBID})
            SUBJOBIDS=($(echo ${QUERYRESULT} | jq -r '.results[].id' | tr '\n' ' '))
            SUBJOBSTATUSES=($(echo ${QUERYRESULT} | jq -r '.results[].status' | tr '\n' ' '))
            # echo "LENGTH SUBJOBS ${#SUBJOBIDS[@]}"
            sleep 1
          done
          # TODO: make this happen with parallel copying
          echo "Fetching results for ${PRODSPLIT} sub-jobs"
          for splitcounter in `seq 1 ${PRODSPLIT}`; do
            let jobindex=splitcounter-1
            THIS_STATUS=${SUBJOBSTATUSES[jobindex]}
            THIS_JOB=${SUBJOBIDS[jobindex]}
            echo "Fetching for job ${THIS_JOB}"
            if [ "${THIS_STATUS}" == "DONE" ]; then
               SPLITOUTDIR=$(printf "%03d" ${splitcounter})
               [ ! -f ${SPLITOUTDIR} ] && mkdir ${SPLITOUTDIR}
               echo "Fetching result files for subjob ${splitcounter} into ${PWD}"
	             CPCMD="alien.py cp ${MY_JOBWORKDIR}/${SPLITOUTDIR}/* file:./${SPLITOUTDIR}"
	             eval "${CPCMD}" 2> /dev/null
            else
	            echo "Not fetching files for subjob ${splitcounter} since job code is ${THIS_STATUS}"
	          fi
          done
      fi
    fi
  done
  # get the job data products locally if requested

  exit 0
fi  # <---- end if ALIEN_JOB_SUBMITTER

####################################################################################################
# The following part is executed on the worker node or locally
####################################################################################################
if [[ ${SINGULARITY} ]]; then
  # if singularity was asked we restart this script within a container
  # it's actually much like the GRID mode --> which is why we set JALIEN_TOKEN_CERT
  set -x
  cp $0 ${GRID_SUBMIT_WORKDIR}

  # detect architecture (ARM or X86)
  ARCH=$(uname -i)
  if [ "$ARCH" == "aarch64" ] || [ "$ARCH" == "x86_64" ]; then
    echo "Detected hardware architecture : $ARCH"
  else
    echo "Invalid architecture ${ARCH} detected. Exiting"
    exit 1
  fi
  if [ "$ARCH" == "aarch64" ]; then
    ISAARCH64="1"
  fi

  CONTAINER="/cvmfs/alice.cern.ch/containers/fs/apptainer/compat_el9-${ARCH}"
  APPTAINER_EXEC="/cvmfs/alice.cern.ch/containers/bin/apptainer/${ARCH}/current/bin/apptainer"

  # we can actually analyse the local JDL to find the package and set it up for the container
  ${APPTAINER_EXEC} exec -C -B /cvmfs:/cvmfs,${GRID_SUBMIT_WORKDIR}:/workdir --pwd /workdir -C ${CONTAINER} /workdir/grid_submit.sh \
  ${CONTINUE_WORKDIR:+"-c ${CONTINUE_WORKDIR}"} --local ${O2TAG:+--o2tag ${O2TAG}} --ttl ${JOBTTL} --label ${JOBLABEL:-label} ${MATTERMOSTHOOK:+--mattermost ${MATTERMOSTHOOK}} ${CONTROLSERVER:+--controlserver ${CONTROLSERVER}}
  set +x
  exit $?
fi

if [[ "${ONGRID}" == 0 ]]; then
  banner "Executing job in directory ${GRID_SUBMIT_WORKDIR}"
  cd "${GRID_SUBMIT_WORKDIR}" 2> /dev/null
fi

exec &> >(tee -a alien_log_${ALIEN_PROC_ID:-0}.txt)

# ----------- START JOB PREAMBLE  ----------------------------- 
env | grep "SINGULARITY" &> /dev/null
if [ "$?" = "0" ]; then
  echo "Singularity containerized execution detected"
fi

banner "Environment"
env

banner "Limits"
ulimit -a

banner "OS detection"
cat /etc/os-release || true
cat /etc/redhat-release || true

# we load the asked package list (this should now be done by JDL)
#if [ ! "$O2_ROOT" ]; then
#  O2_PACKAGE_LATEST=`find /cvmfs/alice.cern.ch/el7-x86_64/Modules/modulefiles/O2 -name "*nightl*" -type f -printf "%f\n" | tail -n1`
#  banner "Loading O2 package $O2_PACKAGE_LATEST"
#  [ "${O2TAG}" ] && O2_PACKAGE_LATEST=${O2TAG}
#  #eval "$(/cvmfs/alice.cern.ch/bin/alienv printenv O2::"$O2_PACKAGE_LATEST")"
#fi
#if [ ! "$O2DPG_ROOT" ]; then
#  O2DPG_LATEST=`find /cvmfs/alice.cern.ch/el7-x86_64/Modules/modulefiles/O2DPG -type f -printf "%f\n" | tail -n1`
#  banner "Loading O2DPG package $O2DPG_LATEST"
#  #eval "$(/cvmfs/alice.cern.ch/bin/alienv printenv O2DPG::"$O2DPG_LATEST")"
#fi

banner "Running workflow"

# collect some common information
echo "CONT_WORKDIR ${CONTINUE_WORKDIR}"

cat /proc/cpuinfo > alien_cpuinfo.log 
cat /proc/meminfo > alien_meminfo.log

# ----------- PREPARE SOME ALIEN ENV -- useful for the job -----------

if [ "${ONGRID}" = "1" ]; then
  notify_mattermost "STARTING GRID ${ALIEN_PROC_ID} CHECK $(which alien.py)"
  alien.py ps --jdl ${ALIEN_PROC_ID} > this_jdl.jdl
  ALIEN_JOB_OUTPUTDIR=$(grep "OutputDir" this_jdl.jdl | awk '//{print $3}' | sed 's/"//g' | sed 's/;//')
  ALIEN_DRIVER_SCRIPT=$0

  # determine subjob id from the structure of the outputfolder
  # can use basename tool since this is like a path
  SUBJOBID=$(echo $(basename "${ALIEN_JOB_OUTPUTDIR}") | sed 's/^0*//')  # Remove leading zeros if present

  # we expose some information about prodsplit and subjob id to the jobs
  # so that they can adjust/contextualise the payload
  export ALIEN_O2DPG_GRIDSUBMIT_PRODSPLIT=${PRODSPLIT}
  export ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID=${SUBJOBID}

  #notify_mattermost "ALIEN JOB OUTDIR IS ${ALIEN_JOB_OUTPUTDIR}" 

  export ALIEN_JOB_OUTPUTDIR
  export ALIEN_DRIVER_SCRIPT
  export O2_PACKAGE_LATEST

  # ----------- FETCH PREVIOUS CHECKPOINT IN CASE WE CONTINUE A JOB ----
  if [ "${CONTINUE_WORKDIR}" ]; then
    alien.py cp alien://${ALIEN_JOB_OUTPUTDIR}/checkpoint.tar file:/.
    if [ -f checkpoint.tar ]; then
       tar -xf checkpoint.tar
       rm checkpoint.tar
    else
       notify_mattermost "Could not download checkpoint; Quitting"
       exit 0
    fi
  fi
fi

# export JOBUTILS_MONITORCPU=ON
# export JOBUTILS_WRAPPER_SLEEP=5
# export JOBUTILS_JOB_KILLINACTIVE=180 # kill inactive jobs after 3 minutes --> will be the task of pipeline runner? (or make it optional)
# export JOBUTILS_MONITORMEM=ON 

# ----------- EXECUTE ACTUAL JOB  ------------------------------------ 
# source the actual job script from the work dir
chmod +x ./alien_jobscript.sh
./alien_jobscript.sh
# fetch the return code
RC=$?

# just to be sure that we get the logs (temporarily disabled since the copy seems to hang sometimes)
#cp alien_log_${ALIEN_PROC_ID:-0}.txt logtmp_${ALIEN_PROC_ID:-0}.txt
#[ "${ALIEN_JOB_OUTPUTDIR}" ] && upload_to_Alien logtmp_${ALIEN_PROC_ID:-0}.txt ${ALIEN_JOB_OUTPUTDIR}/

echo "Job done ... exiting with ${RC}"

# We need to exit for the ALIEN JOB HANDLER!
exit ${RC}
