#!/bin/bash

export GEN_TOPO_PARTITION=test                                       # ECS Partition
export DDMODE=processing                                             # DataDistribution mode - possible options: processing, disk, processing-disk, discard

# Use these settings to fetch the Workflow Repository using a hash / tag
#export GEN_TOPO_HASH=1                                              # Fetch O2DataProcessing repository using a git hash
#export GEN_TOPO_SOURCE=v0.5                                         # Git hash to fetch

# Use these settings to specify a path to the workflow repository in your home dir
export GEN_TOPO_HASH=0                                               # Specify path to O2DataProcessing repository
export GEN_TOPO_SOURCE=/home/drohr/alice/O2DataProcessing            # Path to O2DataProcessing repository

export GEN_TOPO_LIBRARY_FILE=testing/detectors/TPC/workflows.desc    # Topology description library file to load
export GEN_TOPO_WORKFLOW_NAME=ctf-and-display                        # Name of workflow in topology description library
export WORKFLOW_DETECTORS=ALL                                        # Optional parameter for the workflow: Detectors to run reconstruction for (comma-separated list)
export WORKFLOW_DETECTORS_QC=                                        # Optional parameter for the workflow: Detectors to run QC for
export WORKFLOW_DETECTORS_CALIB=                                     # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_PARAMETERS=                                          # Additional paramters for the workflow
export RECO_NUM_NODES_OVERRIDE=0                                     # Override the number of EPN compute nodes to use (default is specified in description library file)
export NHBPERTF=256                                                  # Number of HBF per TF

/home/epn/pdp/gen_topo.sh > $HOME/gen_topo_output.xml
