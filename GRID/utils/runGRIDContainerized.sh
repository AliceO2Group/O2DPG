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
if [ "$ARCH" == "aarch64" ]; then
  ISAARCH64="1"
fi
# we just use the default singularity container (if not already set)
APPTAINER_CONTAINER=${APPTAINER_CONTAINER:-/cvmfs/alice.cern.ch/containers/fs/singularity/default${ISAARCH64+"-aarch64"}}

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

# launch job = script inside the container in the workdir
/cvmfs/alice.cern.ch/containers/bin/apptainer/current${ISAARCH64+"-aarch64"}/bin/apptainer exec -C -B /cvmfs:/cvmfs,${WORK_DIR}:/workdir  \
                                                                    --pwd /workdir --env-file ${WORK_DIR}/envfile ${APPTAINER_CONTAINER} /workdir/job.sh
