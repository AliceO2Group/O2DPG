#!/bin/bash
ALIEN_PID=$1

# Epoch-ms the generated reproducer will pin its CCDB queries to (see the
# INJECTION block below for why). This MUST be the moment the *original* job
# ran; "now" is only the same thing when this script runs inside that very job.
#
#   $2 given                     -> use it verbatim (the escape hatch for
#                                   regenerating an old job's reproducer)
#   running inside the job       -> now == the job's start time, correct
#   otherwise                    -> unknown; do NOT guess, skip the pinning
#
# The last case matters: silently pinning to the wrong moment is worse than not
# pinning at all, because it looks authoritative while reconstructing a CCDB
# view that never existed for this job.
NOT_AFTER=$2
if [ -z "${NOT_AFTER}" ]; then
  if [ -n "${ALIEN_PROC_ID}" ] && [ "${ALIEN_PROC_ID}" = "${ALIEN_PID}" ]; then
    NOT_AFTER=$(date +%s%3N)
  else
    echo "[getReproducerScript] Not running inside job ${ALIEN_PID} and no start"
    echo "[getReproducerScript] time given, so CCDB will NOT be pinned: the"
    echo "[getReproducerScript] reproducer will use present-day conditions."
    echo "[getReproducerScript] Re-run as: $0 ${ALIEN_PID} <job-start-epoch-ms>"
  fi
fi

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

# If the JDL already declares a CCDB time-machine timestamp, the job pinned
# itself and that value is restored further down by the MonaLisa env block (and
# consumed by anchorMC.sh). Injecting our own would fight it, and the JDL's is
# the authoritative one, so stand down.
CCDB_PIN_BLOCK=""
if grep -q "ALIEN_JDL_CCDB_CONDITION_NOT_AFTER" "${SCRIPT}"; then
  echo "[getReproducerScript] JDL already sets CCDB_CONDITION_NOT_AFTER; keeping it."
elif [ -n "${NOT_AFTER}" ]; then
  # Pin every CCDB query to the time the ORIGINAL job ran ("time machine").
  # Without this the reproducer resolves each object to whatever is newest in
  # CCDB *today*, so any re-upload since the job ran silently changes the
  # result -- including the collision context, which is otherwise fully
  # deterministic given the fixed seed (cf. O2-7093). This reconstructs the
  # job's CCDB view rather than sharing a declared one, because production jobs
  # are themselves normally unpinned (o2dpg_sim_workflow.py defaults
  # --condition-not-after to year 2077).
  # Unset ALICEO2_CCDB_CONDITION_NOT_AFTER before running to get present-day
  # conditions instead.
  CCDB_PIN_BLOCK="export ALICEO2_CCDB_CONDITION_NOT_AFTER=\${ALICEO2_CCDB_CONDITION_NOT_AFTER:-${NOT_AFTER}}"
  echo "[getReproducerScript] Pinning reproducer CCDB queries to ${NOT_AFTER}."
fi

# Define the Apptainer injection block which makes sure
# that the job script is automatically executed in apptainer
INJECTION='
export ALIEN_PID=#ALIEN_PID#
#CCDB_PIN_BLOCK#
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

# substitute the CCDB pinning placeholder (dropping the line entirely when we
# decided not to pin -- see above)
awk -v blk="$CCDB_PIN_BLOCK" '$0=="#CCDB_PIN_BLOCK#"{ if (blk!="") print blk; next } 1' \
  "$SCRIPT" > tmpfile && mv tmpfile "$SCRIPT"

chmod +x "${SCRIPT}"
