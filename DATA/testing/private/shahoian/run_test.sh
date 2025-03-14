#!/bin/bash

export GEN_TOPO_PARTITION=test                                       # ECS Partition
#export DDMODE=processing-disk                                        # DataDistribution mode - possible options: processing, disk, processing-disk, discard
export DDMODE=processing                                             # DataDistribution mode - possible options: processing, disk, processing-disk, discard

# Use these settings to fetch the Workflow Repository using a hash / tag
#export GEN_TOPO_HASH=1                                              # Fetch O2DataProcessing repository using a git hash
#export GEN_TOPO_SOURCE=v0.5                                         # Git hash to fetch

# Use these settings to specify a path to the workflow repository in your home dir
export GEN_TOPO_HASH=0                                               # Specify path to O2DataProcessing repository
export GEN_TOPO_SOURCE=$HOME/alice/O2DataProcessing                  # Path to O2DataProcessing repository

export EXTINPUT=1
export EPNSYNCMODE=1
export SYNCMODE=0
export CTFINPUT=0
export SHMSIZE=128000000000
export INFOLOGGER_SEVERITY=warning

export EDJSONS_DIR="/home/ed/jsons"

export GEN_TOPO_LIBRARY_FILE=testing/private/shahoian/workflows_test.desc # Topology description library file to load
export WORKFLOW_DETECTORS=ALL                                        # Optional parameter for the workflow: Detectors to run reconstruction for (comma-separated list)
export WORKFLOW_DETECTORS_QC=ALL                                     # Optional parameter for the workflow: Detectors to run QC for
export WORKFLOW_DETECTORS_CALIB=                                     # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_PARAMETERS=QC,CTF,GPU                                # Additional paramters for the workflow: QC, CTF, GPU
export RECO_NUM_NODES_OVERRIDE=0                                     # Override the number of EPN compute nodes to use (default is specified in description library file)
export NHBPERTF=128                                                  # Number of HBF per TF
export ALL_EXTRA_CONFIG="HBFUtils.nHBFPerTF=$NHBPERTF"
#export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow=""
export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow="GPU_proc.debugLevel=1;"


export EPN2EOS_METAFILES_DIR=/data/epn2eos_tool/epn2eos

export MULTIPLICITY_FACTOR_RAWDECODERS=1
export MULTIPLICITY_FACTOR_CTFENCODERS=1
export MULTIPLICITY_FACTOR_REST=1

export WORKFLOWMODE=print

for wf in "$@"
do
 export GEN_TOPO_WORKFLOW_NAME=$wf
 /opt/alisw/el9/GenTopo/bin/gen_topo.sh > $HOME/gen_topo/test/${GEN_TOPO_WORKFLOW_NAME}.xml
done
