#!/bin/bash

# Script to merge the TPC currents

# first we create the list of files from the collection
sed -rn 's/.*turl="([^"]*)".*/\1/p' $1 | sort -u > o2currents_tpc.txt

# some extra variables
ARGS_ALL="-b --shm-segment-size 16000000000"
START_TF=$2
END_TF=$3

# sourcing some functionssource
[[ -f gen_topo_helper_functions.sh ]] && rm gen_topo_helper_functions.sh
ln -s $O2DPG_ROOT/DATA/common/gen_topo_helper_functions.sh
source gen_topo_helper_functions.sh
[[ -f workflow-setup.sh ]] && rm workflow-setup.sh
ln -s $O2DPG_ROOT/DATA/production/workflow-setup.sh
source workflow-setup.sh || { echo "workflow-setup.sh failed" 1>&2 && exit 1; }

# we start with an empty wf
WORKFLOW=

# running the workflow
add_W o2-tpc-integrate-cluster-reader-workflow "--time-lanes 10 --tpc-currents-infiles o2currents_tpc.txt --firstTF $START_TF --lastTF $END_TF" ""
add_W o2-tpc-merge-integrate-cluster-workflow "--dump-calib-data --meta-output-dir none  --process-3D-currents true --nthreads 8 --enableWritingPadStatusMap true --max-delay 1 -b" ""

WORKFLOW+="o2-dpl-run $ARGS_ALL"

echo "#Workflow command:\n\n${WORKFLOW}\n" | sed -e "s/\\\\n/\n/g" -e"s/| */| \\\\\n/g"

echo "mergeCurrents.sh : Really starting it"

echo | eval $WORKFLOW

exitcode=$?

echo "mergeCurrents.sh : Workflow finished"

exit $exitcode


