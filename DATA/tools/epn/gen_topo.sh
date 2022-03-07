#!/bin/bash

# This is a wrapper script that sets EPN-related env variables needed for the PDP DPL Topology generation.
# Author: David Rohr

# A reference version of this script is contained in the O2DPG repository: https://github.com/AliceO2Group/O2DPG/blob/master/DATA/tools/epn/gen_topo.sh

# The purpose of this script is to separate the topology generation (which is in O2DPG) from the setting of the EPN-related settings

# Settings for some EPN paths / names / etc.
[ -z "$FILEWORKDIR" ] && export FILEWORKDIR=/home/epn/odc/files # Path to common grp / geometry / etc files
[ -z "$INRAWCHANNAME" ] && export INRAWCHANNAME=tf-builder-pipe-0 # Pipe name to get data from TfBuilder
[ -z "$CTF_DIR" ] && export CTF_DIR=/data/tf/compressed # Output directory for CTFs
[ -z "$CTF_METAFILES_DIR" ] && [ "0$WORKFLOWMODE" != "0print" ] && export CTF_METAFILES_DIR=/data/epn2eos_tool/epn2eos #CTF Metafiles directory
[ -z "$GEN_TOPO_WORKDIR" ] && export GEN_TOPO_WORKDIR=$HOME/gen_topo/ # Working directory for checkout of O2DPG repository and for XML cache. If this directory is wiped, gen_topo will recreate all necessary content the next time it runs. The folder should be persistent to cache workflows.
[ -z "$GEN_TOPO_STDERR_LOGGING" ] && export GEN_TOPO_STDERR_LOGGING=1 # Enable logging of stderr messages
[ -z "$IS_SIMULATED_DATA" ] && export IS_SIMULATED_DATA=0 # by default we are processing raw data
[ -z "$GEN_TOPO_ODC_EPN_TOPO_ARGS" ] && export GEN_TOPO_ODC_EPN_TOPO_ARGS="--recown 'wn_(?"'!'"online-calib).*_.*' --calibwn 'wn_online-calib_.*'" # Arguments to pass to odc-epn-topo command
[ -z "$GEN_TOPO_EPN_CCDB_SERVER" ] && export GEN_TOPO_EPN_CCDB_SERVER="http://o2-ccdb.internal" # CCDB server to use

# GEN_TOPO_RUN_HOME is a debug setting used in some tests. This is not needed for online running.
if [[ "0$GEN_TOPO_RUN_HOME" == "01" ]]; then
  [[ $WORKFLOWMODE != "print" ]] && { echo "ERROR: GEN_TOPO_RUN_HOME is only supported with WORKFLOWMODE=print!" 1>&2; exit 1; }
else
  # Load required module and run gen_topo_o2dpg (PDP part of this script)
  # This makes sure to load ODC only when it is not already in the environment.
  # The background is that in the online system ODC is already loaded, but for tests it might not be loaded thus we just load the latest available versions for convenience.
  if [[ `module info-loaded ODC 2> /dev/null | grep ODC | wc -l` == 0 ]]; then
    module load ODC 1>&2 || { echo Error loading ODC / O2DPG 1>&2; exit 1; }
  fi
  # Set O2DPG_ROOT from the latest available O2DPG module, if not already set.
  # Note that this does not load the module, but just needs an O2DPG path to find, which then does the bulk of the topology generation.
  # gen_topo_o2dpg.sh is kept compatible between O2DPG versions, thus it doesn't really depend on which O2DPG version we use at this point.
  if [[ -z $O2DPG_ROOT ]]; then
    O2DPG_ROOT=`bash -c "module load O2DPG > /dev/null; echo \\\$O2DPG_ROOT;"`
  fi
fi
# Now we know which gen_topo_o2dpg.sh we can use, and all EPN related env variables are set, so we can run the topology generation.
$O2DPG_ROOT/DATA/tools/epn/gen_topo_o2dpg.sh
if [ $? != 0 ]; then
  echo topology generation failed 1>&2
  exit 1
fi
