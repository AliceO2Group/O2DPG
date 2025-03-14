#!/bin/bash

export DDMODE=processing                                             # DataDistribution mode - possible options: processing, disk, processing-disk, discard
export DD_DISK_FRACTION=100                                          # In case of disk / processing-disk mode, fraction of raw data to store

# Use these settings to fetch the Workflow Repository using a hash / tag
#export GEN_TOPO_HASH=1                                              # Fetch O2DPG repository using a git hash
#export GEN_TOPO_SOURCE=v0.20                                        # Git hash to fetch

# Use these settings to specify a path to the workflow repository in your home dir
export GEN_TOPO_HASH=0                                               # Specify path to O2DPG repository
export GEN_TOPO_SOURCE=$HOME/alice/O2DPG/DATA                        # Path to O2DPG repository
export OVERRIDE_PDPSUITE_VERSION=                                    # Can be used to override O2PDPSuite version
export SET_QCJSON_VERSION=1                                          # Version of QC JSONs

export GEN_TOPO_LIBRARY_FILE=production/production.desc              # Topology description library file to load
export GEN_TOPO_WORKFLOW_NAME=synchronous-workflow                   # Name of workflow in topology description library
export WORKFLOW_DETECTORS=ALL                                        # Optional parameter for the workflow: Detectors to run reconstruction for (comma-separated list)
export WORKFLOW_DETECTORS_QC=ALL                                     # Optional parameter for the workflow: Detectors to run QC for
export WORKFLOW_DETECTORS_CALIB=ALL                                  # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_DETECTORS_RECO=ALL                                   # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_DETECTORS_FLP_PROCESSING=                            # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_PARAMETERS=QC,CALIB,GPU,CTF,EVENT_DISPLAY            # Additional paramters for the workflow
export RECO_NUM_NODES_OVERRIDE=0                                     # Override the number of EPN compute nodes to use (default is specified in description library file)
export RECO_MAX_FAIL_NODES_OVERRIDE=0                                # Maximum number of nodes allowed to fail during startup
export NHBPERTF=128                                                  # Number of HBF per TF
export MULTIPLICITY_FACTOR_RAWDECODERS=1                             # Factor to scale number of raw decoders with
export MULTIPLICITY_FACTOR_CTFENCODERS=1                             # Factor to scale number of CTF encoders with
export MULTIPLICITY_FACTOR_REST=1                                    # Factor to scale number of other processes with

export SHM_MANAGER_SHMID=                                            # If used with EPN SHM Management tool, SHMID must match the one set in the tool

export OUTPUT_FILE_NAME=gen_topo_output.xml
if [[ "0$GEN_TOPO_RUN_HOME" == "01" ]]; then
  [[ -z $O2DPG_ROOT || -z $O2_ROOT ]] && { echo "ERROR: O2 and O2DPG must be in the environment!"; exit 1; }
  $O2DPG_ROOT/DATA/tools/epn/gen_topo.sh > $OUTPUT_FILE_NAME
else
  [[ ! -f /opt/alisw/el9/GenTopo/bin/gen_topo.sh ]] && { echo "ERROR: EPN installation of gen_topo.sh missing. Are you trying to run at home? Then please set GEN_TOPO_RUN_HOME=1!"; exit 1; }
  /opt/alisw/el9/GenTopo/bin/gen_topo.sh > $OUTPUT_FILE_NAME
fi
if [[ $? == 0 ]]; then
  echo Generated XML topology $OUTPUT_FILE_NAME
else
  cat $OUTPUT_FILE_NAME
fi
