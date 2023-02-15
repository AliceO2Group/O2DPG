#!/bin/bash

# This is a wrapper script that runs gen_topo.sh, and logs the status to /var/log/topology/gen-topo.log.
# For more details, see gen_topo.sh
# Author: David Rohr

# Run stage 1 of GenTopo
LOGDATE=$(date -u +%Y%m%d-%H%M%S)
echo "$LOGDATE $ECS_ENVIRONMENT_ID : Starting topology generation" >> /var/log/topology/gen-topo.log

STDERRFILE=$(mktemp)
/opt/alisw/el8/GenTopo/bin/gen_topo.sh 2> $STDERRFILE
RETVAL=$?

echo "$LOGDATE $ECS_ENVIRONMENT_ID : Topology generation return value: $RETVAL" >> /var/log/topology/gen-topo.log
if [[ $RETVAL != 0 ]]; then
  cat $STDERRFILE >> /var/log/topology/gen-topo.log
fi
cat $STDERRFILE 1>&2

exit $RETVAL
