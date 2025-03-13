#!/bin/bash

export GEN_TOPO_PARTITION=test                                       # ECS Partition
export DDMODE=processing-disk                                        # DataDistribution mode - possible options: processing, disk, processing-disk, discard
#export DDMODE=processing                                             # DataDistribution mode - possible options: processing, disk, processing-disk, discard

# Use these settings to fetch the Workflow Repository using a hash / tag
#export GEN_TOPO_HASH=1                                              # Fetch O2DataProcessing repository using a git hash
#export GEN_TOPO_SOURCE=v0.5                                         # Git hash to fetch

# Use these settings to specify a path to the workflow repository in your home dir
export GEN_TOPO_HASH=0                                               # Specify path to O2DataProcessing repository
export GEN_TOPO_SOURCE=/home/shahoian/alice/O2DataProcessing         # Path to O2DataProcessing repository

export EXTINPUT=1
export EPNSYNCMODE=1
export SYNCMODE=1
export SHMSIZE=128000000000
export INFOLOGGER_SEVERITY=warning

export EDJSONS_DIR="/home/ed/jsons"

export GEN_TOPO_LIBRARY_FILE=testing/private/shahoian/workflows_PB.desc # Topology description library file to load: Pilot Beam
export WORKFLOW_DETECTORS=ALL                                        # Optional parameter for the workflow: Detectors to run reconstruction for (comma-separated list)
export WORKFLOW_DETECTORS_QC=ALL                                     # Optional parameter for the workflow: Detectors to run QC for
export WORKFLOW_DETECTORS_CALIB=                                     # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_PARAMETERS=QC,CTF,GPU                                # Additional paramters for the workflow: QC, CTF, GPU
export RECO_NUM_NODES_OVERRIDE=0                                     # Override the number of EPN compute nodes to use (default is specified in description library file)
export NHBPERTF=128                                                  # Number of HBF per TF
export ALL_EXTRA_CONFIG="HBFUtils.nHBFPerTF=$NHBPERTF"


export MULTIPLICITY_FACTOR_RAWDECODERS=1
export MULTIPLICITY_FACTOR_CTFENCODERS=1
export MULTIPLICITY_FACTOR_REST=1

export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow="GPU_proc.debugLevel=1;GPU_proc.memoryScalingFactor=1.5;GPU_global.synchronousProcessing=0"
export CONFIG_EXTRA_PROCESS_o2_its_reco_workflow="tpcitsMatch.maxVDriftUncertainty=0.2;tpcitsMatch.safeMarginTimeCorrErr=10.;tpcitsMatch.cutMatchingChi2=1000;tpcitsMatch.crudeAbsDiffCut[0]=5;tpcitsMatch.crudeAbsDiffCut[1]=5;tpcitsMatch.crudeAbsDiffCut[2]=0.3;tpcitsMatch.crudeAbsDiffCut[3]=0.3;tpcitsMatch.crudeAbsDiffCut[4]=10;tpcitsMatch.crudeNSigma2Cut[0]=200;tpcitsMatch.crudeNSigma2Cut[1]=200;tpcitsMatch.crudeNSigma2Cut[2]=200;tpcitsMatch.crudeNSigma2Cut[3]=200;tpcitsMatch.crudeNSigma2Cut[4]=900;"
export CONFIG_EXTRA_PROCESS_o2_primary_vertexing_workflow="pvertexer.nSigmaTimeCut=100;pvertexer.dbscanMaxDist2=30;pvertexer.dcaTolerance=3.;pvertexer.pullIniCut=100;pvertexer.addZSigma2=0.1;pvertexer.tukey=20.;pvertexer.addZSigma2Debris=0.01;pvertexer.addTimeSigma2Debris=1.;pvertexer.maxChi2Mean=30;"
export MULTIPLICITY_FACTOR_PROCESS_its_tracker=4
export MULTIPLICITY_FACTOR_PROCESS_its_stf_decoder=4
export MULTIPLICITY_FACTOR_PROCESS_mft_stf_decoder=2
export MULTIPLICITY_FACTOR_PROCESS_itstpc_track_matcher=2
export MULTIPLICITY_FACTOR_PROCESS_tof_matcher=2
export MULTIPLICITY_FACTOR_PROCESS_mch_data_decoder=5

export ITS_CONFIG=" --tracking-mode sync_misaligned "
#export ITS_CONFIG=" --tracking-mode cosmics "

export WORKFLOW_EXTRA_PROCESSING_STEPS="MFT_RECO,MATCH_TPCTRD,MATCH_TPCTOF"  #,MATCH_ITSTPC,MATCH_TPCTRD,MATCH_ITSTPCTRD,MATCH_TPCTOF,MATCH_ITSTPCTOF"
export WORKFLOW_DETECTORS_FLP_PROCESSING="TOF,FT0,FV0,FDD"
#export WORKFLOW_DETECTORS_MATCHING=
export ARGS_EXTRA_PROCESS_o2_tpcits_match_workflow=" --ignore-bc-check "

export ED_TRACKS="ITS,TPC,ITS-TPC,ITS-TPC-TOF,TPC-TOF,MFT"
export ED_CLUSTERS="ITS,TPC,TOF,MFT"

for wf in "$@"
do
 export GEN_TOPO_WORKFLOW_NAME=$wf
 EXT="xml"   
 [ ! -z $WORKFLOWMODE ] && [ $WORKFLOWMODE == "print" ] && EXT="sh"
 /opt/alisw/el9/GenTopo/bin/gen_topo.sh > "$HOME/gen_topo/PB/${GEN_TOPO_WORKFLOW_NAME}.${EXT}"
done
