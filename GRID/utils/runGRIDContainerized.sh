#!/usr/bin/env bash

# Runs a job containerized ... as would be the case on the GRID.
# Mimics what the AliEn job handler does.

SCRIPT=$1
[ $SCRIPT == "" ] && echo "Please provide a script to run" && exit 1
echo "Trying to run script ${SCRIPT} in a container environment"

# detect architecture (ARM or X86)
ARCH=$(uname -i)
if [ "$ARCH" == "aarch64" ] || [ "$ARCH" == "x86_64" ]; then
    echo "Detected hardware architecture : $ARCH"
else
    echo "Invalid architecture ${ARCH} detected. Exiting"
    exit 1
fi
# we just use the default singularity container (if not already set)
APPTAINER_CONTAINER=${APPTAINER_CONTAINER:-/cvmfs/alice.cern.ch/containers/fs/apptainer/compat_el9-${ARCH}}

# create workdir if not specified externally
if [ ! "${WORK_DIR}" ]; then
  WORK_DIR=$(mktemp -d /tmp/alien-job-XXXXXX)
fi
echo "This job will be run in $WORK_DIR"

if [ ! -d "${WORK_DIR}" ]; then
    echo "working directory ${WORK_DIR} does not exist; Please create before running"
    exit 1
fi

# copy script to WORK_DIR
cp ${SCRIPT} ${WORK_DIR}/job.sh

# export certificates - belonging to current user (need to be created before)
ALIEN_CERTFILE=$(find /tmp -type f -name 'tokencert*pem' -user `whoami` 2> /dev/null)
ALIEN_KEYFILE=$(find /tmp -type f -name 'tokenkey*pem' -user `whoami` 2> /dev/null)

[ "${ALIEN_CERTFILE}" == "" ] && echo "No certificate file found; Initialize a token with alien-init-token or similar" && exit 1
[ "${ALIEN_KEYFILE}" == "" ] && echo "No certificate file found; Initialize a token with alien-init-token or similar" && exit 1

cp ${ALIEN_CERTFILE} ${WORK_DIR}/usercert.pem
cp ${ALIEN_KEYFILE} ${WORK_DIR}/userkey.pem

echo "JALIEN_TOKEN_CERT=/workdir/usercert.pem" > ${WORK_DIR}/envfile
echo "JALIEN_TOKEN_KEY=/workdir/userkey.pem" >> ${WORK_DIR}/envfile
if [ "${GRID_CVMFS_PACKAGE}" ]; then
  echo "GRID_CVMFS_PACKAGE=${GRID_CVMFS_PACKAGE}" >> ${WORK_DIR}/envfile
fi

# load a CVMFS package if we are asked to do so -- but do it as part of the job
LOADER='if [ "${GRID_CVMFS_PACKAGE}" ]; then
  /cvmfs/alice.cern.ch/bin/alienv printenv ${GRID_CVMFS_PACKAGE} > cvmfs_env
  source cvmfs_env
fi'
# Inject the block after the first line (shebang)
JOBSCRIPT=${WORK_DIR}/job.sh
awk -v block="$LOADER" 'NR==1 {print; print block; next} 1' "$JOBSCRIPT" > tmpfile && mv tmpfile "$JOBSCRIPT"
chmod +x "${JOBSCRIPT}"

# launch job = script inside the container in the workdir
APPTAINER_EXEC=${APPTAINER_EXEC:-"/cvmfs/alice.cern.ch/containers/bin/apptainer/${ARCH}/current/bin/apptainer"}
${APPTAINER_SUDO:+sudo} ${APPTAINER_EXEC} exec -C -B /cvmfs:/cvmfs,${WORK_DIR}:/workdir                 \
                  --pwd /workdir --env-file ${WORK_DIR}/envfile ${APPTAINER_CONTAINER} bash /workdir/job.sh
