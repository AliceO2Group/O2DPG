#!/bin/bash

export GEN_TOPO_PARTITION=test                                       # ECS Partition
export DDMODE=processing                                             # DataDistribution mode - possible options: processing, disk, processing-disk, discard

# Use these settings to fetch the Workflow Repository using a hash / tag
#export GEN_TOPO_HASH=1                                              # Fetch O2DataProcessing repository using a git hash
#export GEN_TOPO_SOURCE=v0.5                                         # Git hash to fetch

# Use these settings to specify a path to the workflow repository in your home dir
export GEN_TOPO_HASH=0                                               # Specify path to O2DataProcessing repository
export GEN_TOPO_SOURCE=$HOME/alice/O2DataProcessing                  # Path to O2DataProcessing repository

export GEN_TOPO_LIBRARY_FILE=testing/private/shahoian/workflows.desc # Topology description library file to load
export WORKFLOW_DETECTORS=ALL                                        # Optional parameter for the workflow: Detectors to run reconstruction for (comma-separated list)
export WORKFLOW_DETECTORS_QC=                                        # Optional parameter for the workflow: Detectors to run QC for
export WORKFLOW_DETECTORS_CALIB=                                     # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_PARAMETERS=                                          # Additional paramters for the workflow
export RECO_NUM_NODES_OVERRIDE=0                                     # Override the number of EPN compute nodes to use (default is specified in description library file)
export NHBPERTF=256                                                  # Number of HBF per TF


##---------------
jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' /home/epn/odc/files/tpcQCTasks_multinode_ALL.json /home/epn/jliu/itsEPNv2.json > /home/shahoian/alice/O2DataProcessing/testing/private/shahoian/qc/qc-tpcMNAll-itsEPNv2.json
jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' /home/epn/odc/files/tpcQCTasks_multinode_ALL.json /home/epn/jliu/itsEPNv2.json /home/epn/odc/files/qc-mft-cluster.json > /home/shahoian/alice/O2DataProcessing/testing/private/shahoian/qc/qc-tpcMNAll-itsEPNv2-mftClus.json
jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' /home/epn/odc/files/tpcQCTasks_multinode_ALL.json /home/epn/odc/files/qc-mft-cluster.json > /home/shahoian/alice/O2DataProcessing/testing/private/shahoian/qc/qc-tpcMNAll-mftClus.json
jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' /home/epn/odc/files/tpcQCTasks_multinode_ALL.json /home/epn/jliu/itsEPNv2.json /home/epn/odc/files/qc-mft-cluster.json /home/fnoferin/public/tof-qc-globalrun.json  > /home/shahoian/alice/O2DataProcessing/testing/private/shahoian/qc/qc-tpcMNAll-itsEPNv2-mftClus-tofglobalrun.json 
jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' /home/epn/odc/files/tpcQCTasks_multinode_ALL.json /home/epn/jliu/itsEPNv2.json /home/fnoferin/public/tof-qc-globalrun.json  > /home/shahoian/alice/O2DataProcessing/testing/private/shahoian/qc/qc-tpcMNAll-itsEPNv2-tofglobalrun.json
#jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' /home/epn/jliu/itsEPNv2.json /home/epn/odc/files/qc-mft-cluster.json > /home/shahoian/alice/O2DataProcessing/testing/private/shahoian/qc/qc-itsEPNv2-mftClus.json
jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' /home/epn/odc/files/tpcQCTasks_multinode_ALL.json /home/fnoferin/public/tof-qc-globalrun.json  > /home/shahoian/alice/O2DataProcessing/testing/private/shahoian/qc/qc-tpcMNAll-tofglobalrun.json 
jq -n 'reduce inputs as $s (input; .qc.tasks += ($s.qc.tasks) | .qc.checks += ($s.qc.checks)  | .qc.externalTasks += ($s.qc.externalTasks) | .qc.postprocessing += ($s.qc.postprocessing)| .dataSamplingPolicies += ($s.dataSamplingPolicies))' /home/epn/odc/files/tpcQCTasks_multinode_ALL.json /home/epn/odc/files/qc-mft-cluster.json /home/fnoferin/public/tof-qc-globalrun.json  > /home/shahoian/alice/O2DataProcessing/testing/private/shahoian/qc/qc-tpcMNAll-mftClus-tofglobalrun.json

for wf in "$@"
do
 export GEN_TOPO_WORKFLOW_NAME=$wf
 /opt/alisw/el9/GenTopo/bin/gen_topo.sh > $HOME/gen_topo/test/${GEN_TOPO_WORKFLOW_NAME}.xml
done
