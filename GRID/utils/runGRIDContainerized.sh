#!/usr/bin/env bash

# Runs a job containerized ... as would be the case on the GRID.
# Mimics what the AliEn job handler does.

SCRIPT=$1
[ $SCRIPT == "" ] && echo "Please provide a script to run" && exit 1
echo "Trying to run script ${SCRIPT} in a container environment"

# we just use the default singularity container
APPTAINER_CONTAINER=/cvmfs/alice.cern.ch/containers/fs/singularity/default

# create workdir
WORK_DIR=$(mktemp -d /tmp/alien-job-XXXXXX)
echo "This job will be run in $WORK_DIR"

# copy script to WORK_DIR
cp ${SCRIPT} ${WORK_DIR}/job.sh

# export certificates (need to be created before)
ALIEN_CERTFILE=$(ls -t /tmp/tokencert_*.pem 2> /dev/null | head -n 1)
ALIEN_KEYFILE=$(ls -t /tmp/tokenkey_*.pem 2> /dev/null | head -n 1)

[ "${ALIEN_CERTFILE}" == "" ] && echo "No certificate file found; Initialize a token with alien-init-token or similar" && exit 1
[ "${ALIEN_KEYFILE}" == "" ] && echo "No certificate file found; Initialize a token with alien-init-token or similar" && exit 1

cp ${ALIEN_CERTFILE} ${WORK_DIR}/usercert.pem
cp ${ALIEN_KEYFILE} ${WORK_DIR}/userkey.pem

echo "JALIEN_TOKEN_CERT=/workdir/usercert.pem" > ${WORK_DIR}/envfile
echo "JALIEN_TOKEN_KEY=/workdir/userkey.pem" >> ${WORK_DIR}/envfile

# launch job = script inside the container in the workdir
/cvmfs/alice.cern.ch/containers/bin/apptainer/current/bin/apptainer exec -C -B /cvmfs:/cvmfs,${WORK_DIR}:/workdir  \
                                                                    --pwd /workdir --env-file ${WORK_DIR}/envfile ${APPTAINER_CONTAINER} /workdir/job.sh
