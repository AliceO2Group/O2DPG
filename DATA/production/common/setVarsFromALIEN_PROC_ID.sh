#!/bin/bash

# Script to set a couple of variables that depend on ALIEN_PROC_ID.
# Since several scripts might need this, it is in a separate script.

# let's get the last 9 (for int) and 8 (for int16) digits of ALIEN_PROC_ID, to be passed to define NUMAID and shm-segment-id via O2JOBID, which are int and int16 respectively. Then we make them an int or int16
ALIEN_PROC_ID_MAX_NDIGITS_INT32=9
ALIEN_PROC_ID_MAX_NDIGITS_INT16=8
echo "ALIEN_PROC_ID for current job = ${ALIEN_PROC_ID}"

if [[ -n ${ALIEN_JDL_PACKAGES} ]] && [[ ${#ALIEN_PROC_ID} -lt ${ALIEN_PROC_ID_MAX_NDIGITS_INT32} ]]; then # we are on the grid, and we expect to have the PROC_ID
  echo "We cannot determine O2JOBID, the job id is too short (${ALIEN_PROC_ID}), we need at least ${ALIEN_PROC_ID_MAX_NDIGITS_INT32} digits, returning error"
  exit 2
fi

ALIEN_PROC_ID_OFFSET_INT32=$((10#${ALIEN_PROC_ID:-${ALIEN_PROC_ID_MAX_NDIGITS_INT32}}))
echo "ALIEN_PROC_ID_OFFSET_INT32 = $ALIEN_PROC_ID_OFFSET_INT32"

ALIEN_PROC_ID_OFFSET_INT16=$((10#${ALIEN_PROC_ID:-${ALIEN_PROC_ID_MAX_NDIGITS_INT16}}))
echo "ALIEN_PROC_ID_OFFSET_INT16 = $ALIEN_PROC_ID_OFFSET_INT16"

# let's make them int32 or int16, but not with the max possible value (which would be 0x7fffffff and 0x7fff respectively)
# but a bit less, to allow to add [0, 15] on top afterwards if needed (e.g. we usually add
# the NUMAID), see https://github.com/AliceO2Group/O2DPG/pull/993#pullrequestreview-1393401475
export O2JOBID=$(((ALIEN_PROC_ID_OFFSET_INT32 & 0x7ffffff) * 16))
export O2JOBSHMID=$(((ALIEN_PROC_ID_OFFSET_INT16 & 0x7ff) * 16))
echo "ALIEN_PROC_ID = $ALIEN_PROC_ID, we will set O2JOBID = $O2JOBID, SHMEMID = $O2JOBSHMID"
