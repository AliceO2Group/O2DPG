#!/bin/bash
ALIEN_PID=$1

if [ ${JALIEN_TOKEN_CERT} ]; then
  TOKENCERT=${JALIEN_TOKEN_CERT}
  TOKENKEY=${JALIEN_TOKEN_KEY}
else
  if [ -f ${TMPDIR:-/tmp}/tokencert_`id -u`.pem ]; then
    TOKENCERT=${TMPDIR:-/tmp}/tokencert_`id -u`.pem;
  fi
  if [ -f ${TMPDIR:-/tmp}/tokenkey_`id -u`.pem ]; then
    TOKENKEY=${TMPDIR:-/tmp}/tokenkey_`id -u`.pem;
  fi
fi

if [ ! ${TOKENCERT} ]; then
  echo "This needs a tokencert and tokenkey file in the tmp folder"
  exit 1
fi

SCRIPT=reproducer_script_${ALIEN_PID}.sh
# talk to MonaLisa to fetch the script provided by Costin
curl 'https://alimonitor.cern.ch/users/jobenv.jsp?pid='${ALIEN_PID}                                                                      \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36' \
  --insecure --cert ${TOKENCERT} --key ${TOKENKEY} -o ${SCRIPT}

# Define the Apptainer injection block which makes sure
# that the job script is automatically executed in apptainer
INJECTION='
export ALIEN_PID=#ALIEN_PID#
# Check if the script is running inside an Apptainer (Singularity) container
if [ -z "$APPTAINER_NAME" ] && [ -z "$SINGULARITY_NAME" ]; then
  # Relaunch this script inside the container

  export WORKDIR=/tmp/foo-${ALIEN_PID}
  if [ ! -d ${WORKDIR} ]; then
    mkdir ${WORKDIR}
  fi

  # - copy the certificate token into /tmp/ inside the container
  mkdir ${WORKDIR}/tmp
  cp /tmp/token*pem ${WORKDIR}/tmp

  # - copy the job script into workdir
  cp $0 ${WORKDIR}

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
  ${APPTAINER_EXEC} exec -C -B /cvmfs:/cvmfs,${WORKDIR}:/workdir,${WORKDIR}/tmp:/tmp --pwd /workdir -C ${CONTAINER} "$0"
  exit $?
fi
'

# Inject the block after the first line (shebang)
awk -v block="$INJECTION" 'NR==1 {print; print block; next} 1' "$SCRIPT" > tmpfile && mv tmpfile "$SCRIPT"

# take out sandboxing structure
sed -i "/echo \"Create a fresh sandbox at every attempt of running the job: alien-job-$ALIEN_PID\"/d" "$SCRIPT"
sed -i "/rm -rf alien-job-$ALIEN_PID/d" "$SCRIPT"
sed -i "/mkdir -p alien-job-$ALIEN_PID\/tmp/d" "$SCRIPT"
sed -i "/cd alien-job-$ALIEN_PID/d" "$SCRIPT"

# replace the PID
sed -i "s/#ALIEN_PID#/${ALIEN_PID}/g" "$SCRIPT"

chmod +x "${SCRIPT}"
