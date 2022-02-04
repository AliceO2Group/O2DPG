#!/bin/bash
# Settings coming from AliECS via env variables
if [ -z $GEN_TOPO_PARTITION ]; then echo \$GEN_TOPO_PARTITION missing; exit 1; fi # Partition
if [ -z $GEN_TOPO_HASH ]; then echo \$GEN_TOPO_HASH missing; exit 1; fi # Flag whether source is a hash or a folder
if [ -z $GEN_TOPO_SOURCE ]; then echo \$GEN_TOPO_SOURCE missing; exit 1; fi # O2DPG repository source, either a commit hash or a path
if [ -z $GEN_TOPO_LIBRARY_FILE ]; then echo \$GEN_TOPO_LIBRARY_FILE missing; exit 1; fi # Topology description library file in the DATA path of the O2DPG repository
if [ -z $GEN_TOPO_WORKFLOW_NAME ]; then echo \$GEN_TOPO_WORKFLOW_NAME missing; exit 1; fi # Workflow name in library file
if [ -z ${WORKFLOW_DETECTORS+x} ]; then echo \$WORKFLOW_DETECTORS missing; exit 1; fi # Comma-separated list of detectors to run processing for
if [ -z ${WORKFLOW_DETECTORS_QC+x} ]; then echo \$WORKFLOW_DETECTORS_QC missing; exit 1; fi # Comma-separated list of detectors to run QC for
if [ -z ${WORKFLOW_DETECTORS_CALIB+x} ]; then echo \$WORKFLOW_DETECTORS_CALIB missing; exit 1; fi # Comma-separated list of detectors to run calibration for
if [ -z ${WORKFLOW_PARAMETERS+x} ]; then echo \$WORKFLOW_PARAMETERS missing; exit 1; fi # Additional parameters for workflow
if [ -z ${RECO_NUM_NODES_OVERRIDE+x} ]; then echo \$RECO_NUM_NODES_OVERRIDE missing; exit 1; fi # Override number of nodes
if [ -z $DDMODE ] && [ -z $DDWORKFLOW ]; then echo Either \$DDMODE or \$DDWORKFLOW must be set; exit 1; fi # Select data distribution workflow
if [ -z "$MULTIPLICITY_FACTOR_RAWDECODERS" ]; then echo \$MULTIPLICITY_FACTOR_RAWDECODERS missing; exit 1; fi # Process multiplicity scaling parameter
if [ -z "$MULTIPLICITY_FACTOR_CTFENCODERS" ]; then echo \$MULTIPLICITY_FACTOR_CTFENCODERS missing; exit 1; fi # Process multiplicity scaling parameter
if [ -z "$MULTIPLICITY_FACTOR_REST" ]; then echo \$MULTIPLICITY_FACTOR_REST missing; exit 1; fi # Process multiplicity scaling parameter

# Settings for some EPN paths / names / etc.
[ -z "$FILEWORKDIR" ] && export FILEWORKDIR=/home/epn/odc/files # Path to common grp / geometry / etc files
[ -z "$INRAWCHANNAME" ] && export INRAWCHANNAME=tf-builder-pipe-0 # Pipe name to get data from TfBuilder
[ -z "$CTF_DIR" ] && export CTF_DIR=/data/tf/compressed # Output directory for CTFs
[ -z "$CTF_METAFILES_DIR" ] && [ "0$WORKFLOWMODE" != "0print" ] && export CTF_METAFILES_DIR=/data/epn2eos_tool/epn2eos #CTF Metafiles directory
[ -z "$GEN_TOPO_WORKDIR" ] && export GEN_TOPO_WORKDIR=$HOME/gen_topo/${GEN_TOPO_PARTITION}_${GEN_TOPO_ONTHEFLY} # Persistent working directory for checkout of O2DPG repository and for XML cache. Must be per partition. This script must not run twice in parallel with the same workdir
[ -z "$GEN_TOPO_STDERR_LOGGING" ] && export GEN_TOPO_STDERR_LOGGING=1
[ -z "$IS_SIMULATED_DATA" ] && export IS_SIMULATED_DATA=0 # by default we are processing raw data

if [[ "0$DDMODE" == "0discard" ]] || [[ "0$DDMODE" == "0disk" ]]; then
  export GEN_TOPO_LIBRARY_FILE="production/no-processing.desc"
  export GEN_TOPO_WORKFLOW_NAME="no-processing"
fi

if [[ "0$GEN_TOPO_RUN_HOME" == "01" ]]; then
  [[ $WORKFLOWMODE != "print" ]] && { echo "ERROR: GEN_TOPO_RUN_HOME is only supported with WORKFLOWMODE=print!" 1>&2; exit 1; }
else
  # Load required module and run gen_topo_o2dpg (PDP part of this script)
  module load ODC O2DPG 1>&2 || { echo Error loading ODC / O2DPG 1>&2; exit 1; }
fi
$O2DPG_ROOT/DATA/tools/epn/gen_topo_o2dpg.sh
if [ $? != 0 ]; then
  echo topology generation failed 1>&2
  exit 1
fi
