#!/bin/bash

# This is a wrapper script that sets EPN-related env variables needed for the PDP DPL Topology generation.
# Author: David Rohr

# This script is developed within O2DPG: https://github.com/AliceO2Group/O2DPG/blob/master/DATA/tools/epn/gen_topo.sh
# It is installed as package GenTopo to the updateable RPM path /opt/alisw/el9/GenTopo/bin/ on the EPNs

# The purpose of this script is to separate the topology generation (which is in O2DPG) from the setting of the EPN-related settings
# This script contains only the EPN related settings

# Settings for some EPN paths / names / etc.
[[ -z "$FILEWORKDIR" ]] && export FILEWORKDIR=/home/epn/odc/files # Path to common grp / geometry / etc files
[[ -z "$INRAWCHANNAME" ]] && export INRAWCHANNAME=tf-builder-pipe-0 # Pipe name to get data from TfBuilder
[[ -z "$CTF_DIR" ]] && export CTF_DIR=/data/tf/compressed # Output directory for CTFs
[[ -z "$CALIB_DIR" ]] && export CALIB_DIR=/data/calibration # Output directory for calibration data
if [[ -z "$EPN2EOS_METAFILES_DIR" ]] && [[ "0$WORKFLOWMODE" != "0print" ]]; then
  export EPN2EOS_METAFILES_DIR=/data/epn2eos_tool/epn2eos # Directory for epn2eos meta data files
fi
if [[ $USER == "epn" ]]; then
  if [[ -z "$GEN_TOPO_WORKDIR" ]]; then
    mkdir -p /var/tmp/gen_topo
    export GEN_TOPO_WORKDIR=/var/tmp/gen_topo # Working directory for checkout of O2DPG repository and for XML cache. If this directory is wiped, gen_topo will recreate all necessary content the next time it runs. The folder should be persistent to cache workflows.
  fi
else
  [[ -z "$GEN_TOPO_WORKDIR" ]] && export GEN_TOPO_WORKDIR=$HOME/gen_topo # Working directory for checkout of O2DPG repository and for XML cache. If this directory is wiped, gen_topo will recreate all necessary content the next time it runs. The folder should be persistent to cache workflows.
  mkdir -p $HOME/gen_topo
fi
[[ -z "$GEN_TOPO_EPN_CCDB_SERVER" ]] && export GEN_TOPO_EPN_CCDB_SERVER="http://127.0.0.1:8084" # CCDB server to use
if [[ "0$GEN_TOPO_ONTHEFLY" == "01" ]]; then export SHM_MANAGER_SHMID=1 ;fi

# Command for topology merging
if [[ -z "$GEN_TOPO_ODC_EPN_TOPO_CMD" ]]; then
  export GEN_TOPO_ODC_EPN_TOPO_CMD='env - PYTHONPATH+=/usr/local/lib/python3.9/site-packages:/usr/local/lib64/python3.9/site-packages /usr/local/bin/epn-topo-merger'
fi

# Command for postprocessing of topology generation after topology caching
if [[ -z "$GEN_TOPO_ODC_EPN_TOPO_POST_CACHING_CMD" ]]; then
  export GEN_TOPO_ODC_EPN_TOPO_POST_CACHING_CMD='env - PYTHONPATH+=/usr/local/lib/python3.9/site-packages:/usr/local/lib64/python3.9/site-packages /usr/local/bin/epn-topo-alloc'
fi

# Extra arguments for topology merger
if [[ -z "$GEN_TOPO_ODC_EPN_TOPO_POST_CACHING_ARGS" ]]; then
  if [[ "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" ]]; then
    export GEN_TOPO_ODC_EPN_TOPO_POST_CACHING_ARGS="--recozone staging-mi50 --reco100zone staging-mi100 --calibzone calib"
  else
    export GEN_TOPO_ODC_EPN_TOPO_POST_CACHING_ARGS="--recozone online-mi50 --reco100zone online-mi100 --calibzone calib"
  fi
fi
if [[ -z "$GEN_TOPO_MI100_NODES" ]]; then export GEN_TOPO_MI100_NODES=-1; fi

# GEN_TOPO_RUN_HOME is a debug setting used in some tests. This is not needed for online running.
if [[ "0$GEN_TOPO_RUN_HOME" == "01" ]]; then
  [[ "0$GEN_TOPO_RUN_HOME_TEST" != "01" ]] && [[ $WORKFLOWMODE != "print" ]] && { echo "ERROR: GEN_TOPO_RUN_HOME is only supported with WORKFLOWMODE=print!" 1>&2; exit 1; }
else
  if [ "0$GEN_TOPO_ONTHEFLY" == "01" ]; then
    # We purge the modules, since the topology generation will load the O2PDPSuite with the O2 version that shall run, and that includes ODC.
    module purge &> /dev/null
  fi
fi
# Run stage 2 of GenTopo, which does the PDP part, still from hardcoded updatable RPM path
/opt/alisw/el9/GenTopo/bin/gen_topo_o2dpg.sh
if [ $? != 0 ]; then
  exit 1
fi
