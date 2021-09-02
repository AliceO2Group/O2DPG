#!/bin/bash

MYDIR="$(dirname $(readlink -f $0))"

has_detector TPC && WORKFLOW+="o2-qc $ARGS_ALL --config json:///home/epn/odc/files/tpcQCTasks_multinode_ALL.json --local --host localhost | "
