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

# find out if this script is really executed on GRID
# in this case, we should find an environment variable JALIEN_TOKEN_CERT
ONGRID=0
[ "${JALIEN_TOKEN_CERT}" ] && ONGRID=1

JOBTTL=82000
CPUCORES=8
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
        --asuser) ASUSER=$2; shift 2 ;; #
        --label) JOBLABEL=$2; shift 2 ;; # label identifying the production (e.g. as a production identifier)
        --mattermost) MATTERMOSTHOOK=$2; shift 2 ;; # if given, status and metric information about the job will be sent to this hook
        --controlserver) CONTROLSERVER=$2; shift 2 ;; # allows to give a SERVER ADDRESS/IP which can act as controller for GRID jobs
        --prodsplit) PRODSPLIT=$2; shift 2 ;; # allows to set JDL production split level (useful to easily replicate workflows)
        --singularity) SINGULARITY=ON; shift 1 ;; # run everything inside singularity
	-h) Usage ; exit ;;
        *) break ;;
    esac
done
export JOBTTL
export JOBLABEL
export MATTERMOSTHOOK
export CONTROLSERVER
export PRODSPLIT

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
  WORKDIR=${WORKDIR:-/tmp/alien_work/$(basename "$MY_JOBWORKDIR")}
  [ ! -d "${WORKDIR}" ] && mkdir -p ${WORKDIR}
  [ ! "${CONTINUE_WORKDIR}" ] && cp "${MY_JOBSCRIPT}" "${WORKDIR}/alien_jobscript.sh"
fi

# 
# Submitter code (we need to submit whenever a script is given as input and we are not in local mode)
#
[[ ( ! "${LOCAL_MODE}" ) && ( "${SCRIPT}" || "${CONTINUE_WORKDIR}" ) ]] && IS_ALIEN_JOB_SUBMITTER=ON

if [[ "${IS_ALIEN_JOB_SUBMITTER}" ]]; then
  #  --> test if alien is there?
  which alien.py 2> /dev/null
  # check exit code
  if [[ ! "$?" == "0"  ]]; then
    XJALIEN_LATEST=`find /cvmfs/alice.cern.ch/el7-x86_64/Modules/modulefiles/xjalienfs -type f -printf "%f\n" | tail -n1`
    banner "Loading xjalienfs package $XJALIEN_LATEST since not yet loaded"
    eval "$(/cvmfs/alice.cern.ch/bin/alienv printenv xjalienfs::"$XJALIEN_LATEST")"
  fi

  # Create temporary workdir to assemble files, and submit from there (or execute locally)
  cd "$(dirname "$0")"
  THIS_SCRIPT="$PWD/$(basename "$0")"

  cd "${WORKDIR}"

  QUOT='"'
  # ---- Generate JDL ----------------
  # TODO: Make this configurable or read from a preamble section in the jobfile
  cat > "${MY_JOBNAMEDATE}.jdl" <<EOF
Executable = "${MY_BINDIR}/${MY_JOBNAMEDATE}.sh";
Arguments = "${CONTINUE_WORKDIR:+"-c ${CONTINUE_WORKDIR}"} --local ${O2TAG:+--o2tag ${O2TAG}} --ttl ${JOBTTL} --label ${JOBLABEL:-label} ${MATTERMOSTHOOK:+--mattermost ${MATTERMOSTHOOK}} ${CONTROLSERVER:+--controlserver ${CONTROLSERVER}}";
InputFile = "LF:${MY_JOBWORKDIR}/alien_jobscript.sh";
Output = {
  "logs*.zip@disk=2",
  "AO2D.root@disk=1"
};
${PRODSPLIT:+Split = ${QUOT}production:1-${PRODSPLIT}${QUOT};}
OutputDir = "${MY_JOBWORKDIR}/${PRODSPLIT:+#alien_counter_03i#}";
Requirements = member(other.GridPartitions,"${GRIDPARTITION:-multicore_8}");
CPUCores = "${CPUCORES}";
MemorySize = "60GB";
TTL=${JOBTTL};
EOF
# "output_arch.zip:output/*@disk=2",
# "checkpoint*.tar@disk=2"

  pok "Local working directory is $PWD"
  if [ ! "${DRYRUN}" ]; then
    command_file="alien_commands.txt"

    pok "Preparing job \"$MY_JOBNAMEDATE\""
    (
      # assemble all GRID interaction in a single script / transaction
      [ -f "${command_file}" ] && rm ${command_file}
      [ ! "${CONTINUE_WORKDIR}" ] && echo "rmdir ${MY_JOBWORKDIR}" >> ${command_file}    # remove existing job dir
      # echo "mkdir ${MY_BINDIR}" >> ${command_file}                      # create bindir
      echo "mkdir ${MY_JOBPREFIX}" >> ${command_file}                   # create job output prefix
      [ ! "${CONTINUE_WORKDIR}" ] && echo "mkdir ${MY_JOBWORKDIR}" >> ${command_file}
      [ ! "${CONTINUE_WORKDIR}" ] && echo "mkdir ${MY_JOBWORKDIR}/output" >> ${command_file}
      echo "rm ${MY_BINDIR}/${MY_JOBNAMEDATE}.sh" >> ${command_file}    # remove current job script
      echo "cp ${PWD}/${MY_JOBNAMEDATE}.jdl alien://${MY_JOBWORKDIR}/${MY_JOBNAMEDATE}.jdl" >> ${command_file}  # copy the jdl
      echo "cp ${THIS_SCRIPT} alien://${MY_BINDIR}/${MY_JOBNAMEDATE}.sh" >> ${command_file}  # copy current job script to AliEn
      [ ! "${CONTINUE_WORKDIR}" ] && echo "cp ${MY_JOBSCRIPT} alien://${MY_JOBWORKDIR}/alien_jobscript.sh" >> ${command_file}
    ) &> alienlog.txt

    pok "Submitting job \"${MY_JOBNAMEDATE}\" from $PWD"
    (
      echo "submit ${MY_JOBWORKDIR}/${MY_JOBNAMEDATE}.jdl" >> ${command_file}

      # finally we do a single call to alien:
      alien.py < ${command_file}
    ) &>> alienlog.txt

    MY_JOBID=$( (grep 'Your new job ID is' alienlog.txt | grep -oE '[0-9]+' || true) | sort -n | tail -n1)
    if [[ $MY_JOBID ]]; then
      pok "OK, display progress on https://alimonitor.cern.ch/agent/jobs/details.jsp?pid=$MY_JOBID"
    else
      per "Job submission failed: error log follows"
      cat alienlog.txt
    fi
  fi

  exit 0
fi  # <---- end if ALIEN_JOB_SUBMITTER

####################################################################################################
# The following part is executed on the worker node or locally
####################################################################################################
if [[ ${SINGULARITY} ]]; then
  # if singularity was asked we restart this script within a container
  # it's actually much like the GRID mode --> which is why we set JALIEN_TOKEN_CERT
  set -x
  cp $0 ${WORKDIR}
  singularity exec -C -B /cvmfs:/cvmfs,${WORKDIR}:/workdir --env JALIEN_TOKEN_CERT="foo" --pwd /workdir /cvmfs/alice.cern.ch/containers/fs/singularity/centos7 $0 \
  ${CONTINUE_WORKDIR:+"-c ${CONTINUE_WORKDIR}"} --local ${O2TAG:+--o2tag ${O2TAG}} --ttl ${JOBTTL} --label ${JOBLABEL:-label} ${MATTERMOSTHOOK:+--mattermost ${MATTERMOSTHOOK}} ${CONTROLSERVER:+--controlserver ${CONTROLSERVER}}
  set +x
  exit $?
fi

if [[ "${ONGRID}" == 0 ]]; then
  banner "Executing job in directory ${WORKDIR}"
  cd "${WORKDIR}" 2> /dev/null
fi

exec &> >(tee -a alien_log_${ALIEN_PROC_ID:-0}.txt)

# ----------- START JOB PREAMBLE  ----------------------------- 
env | grep "SINGULARITY" &> /dev/null
if [ "$?" = "0" ]; then
  echo "Singularity containerized execution detected"
fi

banner "Environment"
env

banner "OS detection"
lsb_release -a || true
cat /etc/os-release || true
cat /etc/redhat-release || true

if [ ! "$O2_ROOT" ]; then
  O2_PACKAGE_LATEST=`find /cvmfs/alice.cern.ch/el7-x86_64/Modules/modulefiles/O2 -name "*nightl*" -type f -printf "%f\n" | tail -n1`
  banner "Loading O2 package $O2_PACKAGE_LATEST"
  [ "${O2TAG}" ] && O2_PACKAGE_LATEST=${O2TAG}
  eval "$(/cvmfs/alice.cern.ch/bin/alienv printenv O2::"$O2_PACKAGE_LATEST")"
fi
#if [ ! "$XJALIEN_ROOT" ]; then
#  XJALIEN_LATEST=`find /cvmfs/alice.cern.ch/el7-x86_64/Modules/modulefiles/xjalienfs -type f -printf "%f\n" | tail -n1`
#  banner "Loading XJALIEN package $XJALIEN_LATEST"
#  eval "$(/cvmfs/alice.cern.ch/bin/alienv printenv xjalienfs::"$XJALIEN_LATEST")"
#fi
if [ ! "$O2DPG_ROOT" ]; then
  O2DPG_LATEST=`find /cvmfs/alice.cern.ch/el7-x86_64/Modules/modulefiles/O2DPG -type f -printf "%f\n" | tail -n1`
  banner "Loading O2DPG package $O2DPG_LATEST"
  eval "$(/cvmfs/alice.cern.ch/bin/alienv printenv O2DPG::"$O2DPG_LATEST")"
fi

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

  #OutputDir = "/alice/cern.ch/user/a/aliperf/foo/MS3-20201118-094030"; 
  #notify_mattermost "ALIEN JOB OUTDIR IS ${ALIEN_JOB_OUTPUTDIR}" 

  export ALIEN_JOB_OUTPUTDIR
  export ALIEN_DRIVER_SCRIPT
  export O2_PACKAGE_LATEST

  # ----------- FETCH PREVIOUS CHECKPOINT IN CASE WE CONTINUE A JOB ----
  if [ "${CONTINUE_WORKDIR}" ]; then
    alien.py cp alien://${ALIEN_JOB_OUTPUTDIR}/checkpoint.tar .
    if [ -f checkpoint.tar ]; then
       tar -xf checkpoint.tar
       rm checkpoint.tar
    else
       notify_mattermost "Could not download checkpoint; Quitting"
       exit 0
    fi
  fi
fi

# ----------- DOWNLOAD ADDITIONAL HELPERS ----------------------------
curl -o analyse_CPU.py https://raw.githubusercontent.com/sawenzel/AliceO2/swenzel/cpuana/Utilities/Tools/analyse_CPU.py &> /dev/null
chmod +x analyse_CPU.py
export PATH=$PATH:$PWD
export JOBUTILS_MONITORCPU=ON
export JOBUTILS_WRAPPER_SLEEP=5
#export JOBUTILS_JOB_KILLINACTIVE=180 # kill inactive jobs after 3 minutes --> will be the task of pipeline runner? (or make it optional)
export JOBUTILS_MONITORMEM=ON 

# ----------- EXECUTE ACTUAL JOB  ------------------------------------ 
# source the actual job script from the work dir
chmod +x ./alien_jobscript.sh
./alien_jobscript.sh

# just to be sure that we get the logs
cp alien_log_${ALIEN_PROC_ID:-0}.txt logtmp_${ALIEN_PROC_ID:-0}.txt
[ "${ALIEN_JOB_OUTPUTDIR}" ] && upload_to_Alien logtmp_${ALIEN_PROC_ID:-0}.txt ${ALIEN_JOB_OUTPUTDIR}/

# MOMENTARILY WE ZIP ALL LOG FILES
ziparchive=logs_PROCID${ALIEN_PROC_ID:-0}.zip
find ./ -name "*.log*" -exec zip ${ziparchive} {} ';'
find ./ -name "*mergerlog*" -exec zip ${ziparchive} {} ';'
find ./ -name "*serverlog*" -exec zip ${ziparchive} {} ';'
find ./ -name "*workerlog*" -exec zip ${ziparchive} {} ';'
find ./ -name "alien_log*.txt" -exec zip ${ziparchive} {} ';'

# We need to exit for the ALIEN JOB HANDLER!
exit 0
