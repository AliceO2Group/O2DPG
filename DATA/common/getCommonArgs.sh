#!/bin/bash

# used to avoid sourcing this file 2x
if [[ -z ${SOURCE_GUARD_GETCOMMONARGS:-} ]]; then
SOURCE_GUARD_GETCOMMONARGS=1

if [[ -z $SEVERITY || -z $NUMAID || -z $SHMSIZE || -z $FILEWORKDIR || -z $EPNSYNCMODE || -z $INFOLOGGER_SEVERITY || -z $SHMTHROW || -z $NORATELOG ]]; then
  echo "Configuration Environment Variable Missing in getCommonArgs.sh" 1>&2
  exit 1
fi

ARGS_ALL="--session ${OVERRIDE_SESSION:-default} --severity $SEVERITY --shm-segment-id ${O2JOBSHMID:-$NUMAID} --shm-segment-size $SHMSIZE ${ARGS_ALL_EXTRA:-} --early-forward-policy noraw"
ARGS_ALL_CONFIG="keyval.input_dir=$FILEWORKDIR;keyval.output_dir=/dev/null;${ALL_EXTRA_CONFIG:-}"
if [[ $EPNSYNCMODE == 1 ]]; then
  ARGS_ALL+=" --infologger-severity $INFOLOGGER_SEVERITY"
  ARGS_ALL+=" --monitoring-backend influxdb-unix:///tmp/telegraf.sock --resources-monitoring ${GEN_TOPO_RESOURCE_MONITORING:-15}"
  ARGS_ALL_CONFIG+="NameConf.mCCDBServer=$GEN_TOPO_EPN_CCDB_SERVER;"
  export DPL_CONDITION_BACKEND=$GEN_TOPO_EPN_CCDB_SERVER
  [[ -z ${O2_DPL_DEPLOYMENT_MODE:-} ]] && O2_DPL_DEPLOYMENT_MODE=OnlineECS
elif [[ "${ENABLE_METRICS:-}" != "1" ]]; then
  ARGS_ALL+=" --monitoring-backend no-op://"
fi
[[ $SHMTHROW == 0 ]] && ARGS_ALL+=" --bad-alloc-max-attempts 60 --bad-alloc-attempt-interval 1000"
[[ ! -z ${SHM_MANAGER_SHMID:-} && ${GEN_TOPO_CALIB_WORKFLOW:-} != 1 ]] && ARGS_ALL+=" --no-cleanup --shm-no-cleanup on --shmid $SHM_MANAGER_SHMID"
[[ $NORATELOG == 1 ]] && ARGS_ALL+=" --fairmq-rate-logging 0"

[[ ! -z ${O2_DPL_EXIT_TRANSITION_TIMEOUT_DEFAULT:-} ]] && ARGS_ALL+=" --exit-transition-timeout $O2_DPL_EXIT_TRANSITION_TIMEOUT_DEFAULT"

true

fi # getCommonArgs.sh sourced
