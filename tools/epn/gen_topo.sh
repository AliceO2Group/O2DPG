#!/bin/bash
# Settings coming from AliECS via env variables
if [ -z $GEN_TOPO_HASH ]; then echo \$GEN_TOPO_HASH missing; exit 1; fi # Flag whether source is a hash or a folder
if [ -z $GEN_TOPO_SOURCE ]; then echo \$GEN_TOPO_SOURCE missing; exit 1; fi # O2DataProcessing repository source, either a commit hash or a path
if [ -z $GEN_TOPO_LIBRARY_FILE ]; then echo \$GEN_TOPO_LIBRARY_FILE missing; exit 1; fi # Topology description library file in O2DataProcessing repository
if [ -z $GEN_TOPO_WORKFLOW_NAME ]; then echo \$GEN_TOPO_WORKFLOW_NAME missing; exit 1; fi # Workflow name in library file
if [ -z ${WORKFLOW_DETECTORS+x} ]; then echo \$WORKFLOW_DETECTORS missing; exit 1; fi # Comma-separated list of detectors to run processing for
if [ -z ${WORKFLOW_DETECTORS_QC+x} ]; then echo \$WORKFLOW_DETECTORS_QC missing; exit 1; fi # Comma-separated list of detectors to run QC for
if [ -z ${WORKFLOW_DETECTORS_CALIB+x} ]; then echo \$WORKFLOW_DETECTORS_CALIB missing; exit 1; fi # Comma-separated list of detectors to run calibration for
if [ -z ${WORKFLOW_PARAMETERS+x} ]; then echo \$WORKFLOW_PARAMETERS missing; exit 1; fi # Additional parameters for workflow
if [ -z ${RECO_NUM_NODES_OVERRIDE+x} ]; then echo \$RECO_NUM_NODES_OVERRIDE missing; exit 1; fi # Override number of nodes

# Settings for some EPN paths / names / etc.
export FILEWORKDIR=/home/epn/odc/files # Path to common grp / geometry / etc files
export DDWORKFLOW=/home/epn/odc/dd-data.xml # DataDistribution workflow XML file to use for incooperating in final topology
export INRAWCHANNAME=tf-builder-pipe-0 # Pipe name to get data from TfBuilder
export CTF_DIR=/tmp/datadist/ctf # Output directory for CTFs
export GEN_TOPO_XML_OUTPUT=/tmp/gen_topo.xml # Name of output XML file for full DDS topology
export GEN_TOPO_WORKDIR=/home/epn/gen_topo/dir0 # Persistent working directory for checkout O2DataProcessing repository and for XML cache. Must be per partition. This script must not run twice in parallel with the same workdir

# Load required module and run gen_topo_o2dataprocessing (PDP part of this script)
module load ODC O2DataProcessing || (echo Error loading ODC / O2DataProcessing && exit 1)
$O2DATAPROCESSING_ROOT/tools/epn/gen_topo_o2dataprocessing.sh
if [ $? != 0 ]; then
  echo topology generation failed
  exit 1
fi
