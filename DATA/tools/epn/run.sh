#!/bin/bash

export GEN_TOPO_PARTITION=test                                       # ECS Partition
export DDMODE=processing                                             # DataDistribution mode - possible options: processing, disk, processing-disk, discard

# Use these settings to fetch the Workflow Repository using a hash / tag
#export GEN_TOPO_HASH=1                                              # Fetch O2DataProcessing repository using a git hash
#export GEN_TOPO_SOURCE=v0.13                                        # Git hash to fetch

# Use these settings to specify a path to the workflow repository in your home dir
export GEN_TOPO_HASH=0                                               # Specify path to O2DataProcessing repository
export GEN_TOPO_SOURCE=$HOME/alice/O2DataProcessing                  # Path to O2DataProcessing repository

export GEN_TOPO_LIBRARY_FILE=production/production.desc              # Topology description library file to load
export GEN_TOPO_WORKFLOW_NAME=synchronous-workflow                   # Name of workflow in topology description library
export WORKFLOW_DETECTORS=ALL                                        # Optional parameter for the workflow: Detectors to run reconstruction for (comma-separated list)
export WORKFLOW_DETECTORS_QC=ALL                                     # Optional parameter for the workflow: Detectors to run QC for
export WORKFLOW_DETECTORS_CALIB=ALL                                  # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_DETECTORS_RECO=ALL                                   # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_DETECTORS_FLP_PROCESSING=                            # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_PARAMETERS=QC,CALIB,GPU,CTF,EVENT_DISPLAY            # Additional paramters for the workflow
export RECO_NUM_NODES_OVERRIDE=0                                     # Override the number of EPN compute nodes to use (default is specified in description library file)
export NHBPERTF=128                                                  # Number of HBF per TF
export MULTIPLICITY_FACTOR_RAWDECODERS=1                             # Factor to scale number of raw decoders with
export MULTIPLICITY_FACTOR_CTFENCODERS=1                             # Factor to scale number of CTF encoders with
export MULTIPLICITY_FACTOR_REST=1                                    # Factor to scale number of other processes with

export OUTPUT_FILE_NAME=gen_topo_output.xml
if [[ "0$GEN_TOPO_RUN_HOME" == "01" ]]; then
  [[ -z $O2DATAPROCESSING_ROOT || -z $O2_ROOT ]] && { echo "ERROR: O2 and O2DataProcessing must be in the environment!"; exit 1; }
  $O2DATAPROCESSING_ROOT/tools/epn/gen_topo.sh > $OUTPUT_FILE_NAME
else
  [[ ! -f /home/epn/pdp/gen_topo.sh ]] && { echo "ERROR: EPN installation of gen_topo.sh missing. Are you trying to run at home? Then please set GEN_TOPO_RUN_HOME=1!"; exit 1; }
  /home/epn/pdp/gen_topo.sh > $OUTPUT_FILE_NAME
fi
if [[ $? == 0 ]]; then
  echo Generated XML topology $OUTPUT_FILE_NAME
fi
