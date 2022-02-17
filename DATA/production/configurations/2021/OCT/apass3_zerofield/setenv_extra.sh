#!/bin/bash

# script to set extra env variables
# taking some stuff from alien

# process flags passed to the script

export SETENV_NO_ULIMIT=1

# detector list
export WORKFLOW_DETECTORS=ITS,TPC,TOF,TRD,FV0,FT0,FDD,MID,MFT

# ad-hoc settings for CTF reader: we are on the grid, we read the files remotely
echo "*********************** mode = ${MODE}"
unset ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow
if [[ $MODE == "remote" ]]; then
  export INPUT_FILE_COPY_CMD="\"alien_cp ?src file://?dst\""
  export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="--remote-regex \"^alien:///alice/data/.+\""
fi
# other ad-hoc settings for CTF reader
export ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow="$ARGS_EXTRA_PROCESS_o2_ctf_reader_workflow --allow-missing-detectors "

# run-dependent options
if [[ -f "setenv_run.sh" ]]; then
    source setenv_run.sh 
else
    echo "************************************************************"
    echo No ad-hoc run-dependent settings for current async processing
    echo "************************************************************"
fi

# to have better logging
export DDS_SESSION_ID=foo

# remove monitoring-backend
export ENABLE_METRICS=1

# add the performance metrics
#export ARGS_ALL_EXTRA=" --resources-monitoring 10 --resources-monitoring-dump-interval 10"
export ARGS_ALL_EXTRA=" --resources-monitoring 50 --resources-monitoring-dump-interval 50"

# some settings in common between workflows
export ITSEXTRAERR="ITSCATrackerParam.sysErrY2[0]=9e-4;ITSCATrackerParam.sysErrZ2[0]=9e-4;ITSCATrackerParam.sysErrY2[1]=9e-4;ITSCATrackerParam.sysErrZ2[1]=9e-4;ITSCATrackerParam.sysErrY2[2]=9e-4;ITSCATrackerParam.sysErrZ2[2]=9e-4;ITSCATrackerParam.sysErrY2[3]=1e-2;ITSCATrackerParam.sysErrZ2[3]=1e-2;ITSCATrackerParam.sysErrY2[4]=1e-2;ITSCATrackerParam.sysErrZ2[4]=1e-2;ITSCATrackerParam.sysErrY2[5]=1e-2;ITSCATrackerParam.sysErrZ2[5]=1e-2;ITSCATrackerParam.sysErrY2[6]=1e-2;ITSCATrackerParam.sysErrZ2[6]=1e-2;"

export MFT_STROBELGT="MFTAlpideParam.roFrameLengthInBC=198"

# ad-hoc options for ITS reco workflow
export ITS_CONFIG=" --tracking-mode sync_misaligned"
export CONFIG_EXTRA_PROCESS_o2_its_reco_workflow="ITSVertexerParam.phiCut=0.5;ITSVertexerParam.clusterContributorsCut=3;ITSVertexerParam.tanLambdaCut=0.2"

# ad-hoc options for GPU reco workflow
export CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow="$VDRIFT"

# ad-hoc settings for TOF reco
# export ARGS_EXTRA_PROCESS_o2_tof_reco_workflow="--use-ccdb --ccdb-url-tof \"http://alice-ccdb.cern.ch\""
# since commit on Dec, 4
export ARGS_EXTRA_PROCESS_o2_tof_reco_workflow="--use-ccdb"

# ad-hoc options for primary vtx workflow
#export PVERTEXER="pvertexer.acceptableScale2=9;pvertexer.minScale2=2.;pvertexer.nSigmaTimeTrack=4.;pvertexer.timeMarginTrackTime=0.5;pvertexer.timeMarginVertexTime=7.;pvertexer.nSigmaTimeCut=10;pvertexer.dbscanMaxDist2=30;pvertexer.dcaTolerance=3.;pvertexer.pullIniCut=100;pvertexer.addZSigma2=0.1;pvertexer.tukey=20.;pvertexer.addZSigma2Debris=0.01;pvertexer.addTimeSigma2Debris=1.;pvertexer.maxChi2Mean=30;pvertexer.timeMarginReattach=3.;pvertexer.addTimeSigma2Debris=1.;"
# following comment https://alice.its.cern.ch/jira/browse/O2-2691?focusedCommentId=278262&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-278262
export PVERTEXER="pvertexer.acceptableScale2=9;pvertexer.minScale2=2.;pvertexer.nSigmaTimeTrack=4.;pvertexer.timeMarginTrackTime=0.5;pvertexer.timeMarginVertexTime=7.;pvertexer.nSigmaTimeCut=10;pvertexer.dbscanMaxDist2=36;pvertexer.dcaTolerance=3.;pvertexer.pullIniCut=100;pvertexer.addZSigma2=0.1;pvertexer.tukey=20.;pvertexer.addZSigma2Debris=0.01;pvertexer.addTimeSigma2Debris=1.;pvertexer.maxChi2Mean=30;pvertexer.timeMarginReattach=3.;pvertexer.addTimeSigma2Debris=1.;pvertexer.dbscanDeltaT=24;pvertexer.maxChi2TZDebris=100;pvertexer.maxMultRatDebris=1.;pvertexer.dbscanAdaptCoef=20.;"
export SVTX="svertexer.checkV0Hypothesis=false;svertexer.checkCascadeHypothesis=false"

export CONFIG_EXTRA_PROCESS_o2_primary_vertexing_workflow="$VDRIFT;$PVERTEXER;$MFT_STROBELGT"
export CONFIG_EXTRA_PROCESS_o2_secondary_vertexing_workflow="$SVTX"

# ad-hoc settings for its-tpc matching
export ITSTPCMATCH="tpcitsMatch.maxVDriftUncertainty=0.2;tpcitsMatch.safeMarginTimeCorrErr=10.;tpcitsMatch.cutMatchingChi2=1000;tpcitsMatch.crudeAbsDiffCut[0]=5;tpcitsMatch.crudeAbsDiffCut[1]=5;tpcitsMatch.crudeAbsDiffCut[2]=0.3;tpcitsMatch.crudeAbsDiffCut[3]=0.3;tpcitsMatch.crudeAbsDiffCut[4]=10;tpcitsMatch.crudeNSigma2Cut[0]=200;tpcitsMatch.crudeNSigma2Cut[1]=200;tpcitsMatch.crudeNSigma2Cut[2]=200;tpcitsMatch.crudeNSigma2Cut[3]=200;tpcitsMatch.crudeNSigma2Cut[4]=900;"
export CONFIG_EXTRA_PROCESS_o2_tpcits_match_workflow="$VDRIFT;$ITSEXTRAERR;$ITSTPCMATCH"

# ad-hoc settings for TOF matching
export ARGS_EXTRA_PROCESS_o2_tof_matcher_workflow="--output-type matching-info"
export CONFIG_EXTRA_PROCESS_o2_tof_matcher_workflow="$VDRIFT;$ITSEXTRAERR"

# ad-hoc settings for TRD matching
export CONFIG_EXTRA_PROCESS_o2_trd_global_tracking="$VDRIFT;$ITSEXTRAERR"

# ad-hoc settings for FT0
export ARGS_EXTRA_PROCESS_o2_ft0_reco_workflow="--ft0-reconstructor"

# ad-hoc settings for FV0
export ARGS_EXTRA_PROCESS_o2_fv0_reco_workflow="--fv0-reconstructor"

# ad-hoc settings for FDD
#...

# ad-hoc settings for MFT 
export CONFIG_EXTRA_PROCESS_o2_mft_reco_workflow="$MFT_STROBELGT"

# Enabling AOD
export WORKFLOW_PARAMETERS="AOD,${WORKFLOW_PARAMETERS}"

# ad-hoc settings for AOD
#...

# Enabling QC
export WORKFLOW_PARAMETERS="QC,${WORKFLOW_PARAMETERS}"
export QC_CONFIG_PARAM="--local-batch=QC.root --override-values \"qc.config.Activity.number=$RUNNUMBER;qc.config.Activity.passName=$PASS;qc.config.Activity.periodName=$PERIOD\""
export GEN_TOPO_WORKDIR="./"
#export QC_JSON_FROM_OUTSIDE="QC-20211214.json"

if [[ ! -z $QC_JSON_FROM_OUTSIDE ]]; then
    sed -i 's/REPLACE_ME_RUNNUMBER/'"${RUNNUMBER}"'/g' $QC_JSON_FROM_OUTSIDE
    sed -i 's/REPLACE_ME_PASS/'"${PASS}"'/g' $QC_JSON_FROM_OUTSIDE
    sed -i 's/REPLACE_ME_PERIOD/'"${PERIOD}"'/g' $QC_JSON_FROM_OUTSIDE
fi


