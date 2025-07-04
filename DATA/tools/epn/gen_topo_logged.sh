#!/bin/bash

# This is a wrapper script that runs gen_topo.sh, and logs the status to /var/log/topology/gen-topo.log.
# For more details, see gen_topo.sh
# Author: David Rohr

# Run stage 1 of GenTopo
if [[ ! -z $ECS_ENVIRONMENT_ID && -d "/var/log/topology/" && $USER == "epn" ]]; then
  GEN_TOPO_LOGDATE=$(date -u +%Y%m%d-%H%M%S)
fi

if [[ ! -z $GEN_TOPO_LOGDATE ]]; then
  echo "$GEN_TOPO_LOGDATE $ECS_ENVIRONMENT_ID : Starting topology generation" >> /var/log/topology/gen-topo.log
  if [[ ! -z $ODC_TOPO_GEN_CMD ]]; then
    echo "$GEN_TOPO_LOGDATE $ECS_ENVIRONMENT_ID : Command line: $ODC_TOPO_GEN_CMD" >> /var/log/topology/gen-topo.log
  fi
fi

STDERRFILE=$(mktemp)
/opt/alisw/el9/GenTopo/bin/gen_topo.sh 2> $STDERRFILE
RETVAL=$?

if [[ ! -z $GEN_TOPO_LOGDATE ]]; then
  echo "$GEN_TOPO_LOGDATE $ECS_ENVIRONMENT_ID : Topology generation return value: $RETVAL" >> /var/log/topology/gen-topo.log
  if [[ $RETVAL != 0 ]]; then
    while read STDERRLINE; do
      echo "$GEN_TOPO_LOGDATE $ECS_ENVIRONMENT_ID :     $STDERRLINE" >> /var/log/topology/gen-topo.log
    done < $STDERRFILE
    echo "FATAL $(tail -n 1 $STDERRFILE)" 1>&2
    echo -e "\n - full stderr output:" 1>&2
  fi
fi

cat $STDERRFILE 1>&2
exit $RETVAL
