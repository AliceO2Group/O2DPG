#!/bin/bash

export GEN_TOPO_PARTITION=test                                       # ECS Partition
export DDMODE=processing-disk                                             # DataDistribution mode - possible options: processing, disk, processing-disk, discard

# Use these settings to fetch the Workflow Repository using a hash / tag
#export GEN_TOPO_HASH=1                                              # Fetch O2DataProcessing repository using a git hash
#export GEN_TOPO_SOURCE=v0.5                                         # Git hash to fetch

# Use these settings to specify a path to the workflow repository in your home dir
export GEN_TOPO_HASH=0                                               # Specify path to O2DataProcessing repository
export GEN_TOPO_SOURCE=/home/afurs/O2DataProcessing                  # Path to O2DataProcessing repository
export GEN_TOPO_LIBRARY_FILE=testing/detectors/FT0/workflows.desc    # Topology description library file to load
export GEN_TOPO_WORKFLOW_NAME=ft0-digits-qc-ctf                # Name of workflow in topology description library
export WORKFLOW_DETECTORS=FT0                                        # Optional parameter for the workflow: Detectors to run reconstruction for (comma-separated list)
export WORKFLOW_DETECTORS_QC=FT0                                     # Optional parameter for the workflow: Detectors to run QC for
export WORKFLOW_DETECTORS_CALIB=                                     # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_PARAMETERS=                                         # Additional paramters for the workflow
export RECO_NUM_NODES_OVERRIDE=0                                     # Override the number of EPN compute nodes to use (default is specified in description library file)
export NHBPERTF=128                                                  # Number of HBF per TF

export MULTIPLICITY_FACTOR_RAWDECODERS=1                             # Factor to scale number of raw decoders with
export MULTIPLICITY_FACTOR_CTFENCODERS=1                             # Factor to scale number of CTF encoders with
export MULTIPLICITY_FACTOR_REST=1                                    # Factor to scale number of other processes with

export OUTPUT_FILE_NAME=$HOME/topologies/ft0-digits-qc-ctf.xml

/opt/alisw/el9/GenTopo/bin/gen_topo.sh > $OUTPUT_FILE_NAME
if [ $? == 0 ]; then
  echo Generated XML topology $OUTPUT_FILE_NAME
fi


