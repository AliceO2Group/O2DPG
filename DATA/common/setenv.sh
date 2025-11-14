#!/bin/bash

# used to avoid sourcing this file 2x
if [[ -z ${SOURCE_GUARD_SETENV:-} ]]; then
SOURCE_GUARD_SETENV=1

source $O2DPG_ROOT/DATA/common/gen_topo_helper_functions.sh || { echo "gen_topo_helper_functions.sh failed" 1>&2 && exit 1; }

# Make sure we can open sufficiently many files / allocate enough memory
if [[ ${SETENV_NO_ULIMIT:-} != "1" ]]; then
  ulimit -S -n 4096 && ulimit -S -m unlimited && ulimit -S -v unlimited && [[ -z ${GPUTYPE:-} ]] || [[ ${GPUTYPE:-} == "CPU" ]] || ulimit -S -l unlimited
  if [[ $? != 0 ]]; then
    echo Error setting ulimits
    exit 1
  fi
else
  ULIMIT_S=`ulimit -S -n`
  ULIMIT_H=`ulimit -H -n`
  ULIMIT_REQ=4000
  [[ $ULIMIT_S == "unlimited" ]] && ULIMIT_S=$ULIMIT_REQ
  [[ $ULIMIT_H == "unlimited" ]] && ULIMIT_H=$ULIMIT_REQ
  if [[ $ULIMIT_H -gt $ULIMIT_S ]] && [[ $ULIMIT_S -lt $ULIMIT_REQ ]]; then
    ulimit -S -n $(($ULIMIT_H > $ULIMIT_REQ ? $ULIMIT_REQ : $ULIMIT_H))
  fi
  ULIMIT_FINAL=`ulimit -n`
  if [[ $ULIMIT_FINAL -lt $ULIMIT_REQ ]]; then
    echo "Could not raise 'ulimit -n' to $ULIMIT_REQ, running with $ULIMIT_FINAL" 1>&2
  fi
fi

LIST_OF_DETECTORS="ITS,MFT,TPC,TOF,FT0,MID,EMC,PHS,CPV,ZDC,FDD,HMP,FV0,TRD,MCH,CTP"

LIST_OF_GLORECO="ITSTPC,TPCTRD,ITSTPCTRD,TPCTOF,ITSTPCTOF,MFTMCH,MCHMID,PRIMVTX,SECVTX,STRK,AOD"

LIST_OF_PID="FT0-TOF"

# Detectors used in the workflow / enabled parameters
# Available options: WORKFLOW_DETECTORS, WORKFLOW_DETECTORS_EXCLUDE, WORKFLOW_DETECTORS_QC, WORKFLOW_DETECTORS_EXCLUDE_QC, WORKFLOW_DETECTORS_CALIB, WORKFLOW_DETECTORS_EXCLUDE_CALIB, ...
if [[ -z "${WORKFLOW_DETECTORS+x}" ]] || [[ "0$WORKFLOW_DETECTORS" == "0ALL" ]]; then export WORKFLOW_DETECTORS=$LIST_OF_DETECTORS; fi
if [[ ! -z ${WORKFLOW_DETECTORS_EXCLUDE:-} ]]; then
  for i in ${WORKFLOW_DETECTORS_EXCLUDE//,/ }; do
    export WORKFLOW_DETECTORS=$(echo $WORKFLOW_DETECTORS | sed -e "s/,$i,/,/g" -e "s/^$i,//" -e "s/,$i"'$'"//" -e "s/^$i"'$'"//")
  done
fi

if [[ -z "${WORKFLOW_DETECTORS_GPU+x}" ]]; then export WORKFLOW_DETECTORS_GPU="TPC"; fi
if [[ -z "${WORKFLOW_DETECTORS_QC+x}" ]] || [[ "0$WORKFLOW_DETECTORS_QC" == "0ALL" ]]; then export WORKFLOW_DETECTORS_QC="$WORKFLOW_DETECTORS,$LIST_OF_GLORECO,TOF_MATCH"; fi
if [[ -z "${WORKFLOW_DETECTORS_CALIB+x}" ]] || [[ "0$WORKFLOW_DETECTORS_CALIB" == "0ALL" ]]; then export WORKFLOW_DETECTORS_CALIB=$WORKFLOW_DETECTORS; fi
if [[ -z "${WORKFLOW_DETECTORS_RECO+x}" ]] || [[ "0$WORKFLOW_DETECTORS_RECO" == "0ALL" ]]; then export WORKFLOW_DETECTORS_RECO=$WORKFLOW_DETECTORS; fi
if [[ -z "${WORKFLOW_DETECTORS_CTF+x}" ]] || [[ "0$WORKFLOW_DETECTORS_CTF" == "0ALL" ]]; then export WORKFLOW_DETECTORS_CTF=$WORKFLOW_DETECTORS; fi
if [[ "0${WORKFLOW_DETECTORS_FLP_PROCESSING:-}" == "0ALL" ]]; then export WORKFLOW_DETECTORS_FLP_PROCESSING=$WORKFLOW_DETECTORS; fi
if [[ "0${WORKFLOW_DETECTORS_USE_GLOBAL_READER:-}" == "0ALL" ]]; then export WORKFLOW_DETECTORS_USE_GLOBAL_READER=$WORKFLOW_DETECTORS; else export WORKFLOW_DETECTORS_USE_GLOBAL_READER=${WORKFLOW_DETECTORS_USE_GLOBAL_READER:-}; fi
if [[ -z "${WORKFLOW_PARAMETERS:-}" ]]; then export WORKFLOW_PARAMETERS=; fi

if [[ ! -z ${WORKFLOW_DETECTORS_EXCLUDE_QC:-} ]]; then
  for i in ${WORKFLOW_DETECTORS_EXCLUDE_QC//,/ }; do
    export WORKFLOW_DETECTORS_QC=$(echo $WORKFLOW_DETECTORS_QC | sed -e "s/,$i,/,/g" -e "s/^$i,//" -e "s/,$i"'$'"//" -e "s/^$i"'$'"//")
  done
fi
if [[ ! -z ${WORKFLOW_DETECTORS_EXCLUDE_CALIB:-} ]]; then
  for i in ${WORKFLOW_DETECTORS_EXCLUDE_CALIB//,/ }; do
    export WORKFLOW_DETECTORS_CALIB=$(echo $WORKFLOW_DETECTORS_CALIB | sed -e "s/,$i,/,/g" -e "s/^$i,//" -e "s/,$i"'$'"//" -e "s/^$i"'$'"//")
  done
fi

if [[ -z "${TFLOOP:-}" ]];         then export TFLOOP=0; fi                    # loop over timeframes
if [[ -z "${NTIMEFRAMES:-}" ]];    then export NTIMEFRAMES=-1; fi              # max number of time frames to process, <=0 : unlimited
if [[ -z "${CTFDICT_NTF:-}" ]];    then export CTFDICT_NTF=100; fi             # auto-save CTF dictionary after each CTFDICT_NTF TFs (if > 0)
if [[ -z "${CTF_MAXDETEXT:-}" ]];  then export CTF_MAXDETEXT=0; fi             # extend CTF output dir.name by detectors names if their number does not exceed this
if [[ -z "${TFDELAY:-}" ]];        then export TFDELAY=0; fi                   # Delay in seconds between publishing time frames
if [[ -z "${GPUTYPE:-}" ]];        then export GPUTYPE=CPU; fi                 # GPU Tracking backend to use, can be CPU / CUDA / HIP / OCL / OCL2
if [[ -z "${DDSHMSIZE:-}" ]];      then export DDSHMSIZE=$(( 8 << 10 )); fi    # Size of shared memory for DD Input
if [[ -z "${DDHDRSIZE:-}" ]];      then export DDHDRSIZE=$(( 1 << 10 )); fi    # Size of shared memory for DD Input
if [[ -z "${GPUMEMSIZE:-}" ]];     then export GPUMEMSIZE=$(( 14 << 30 )); fi  # Size of allocated GPU memory (if GPUTYPE != CPU)
if [[ -z "${HOSTMEMSIZE:-}" ]];    then export HOSTMEMSIZE=0; fi               # Size of allocated host memory for GPU reconstruction (0 = default)
if [[ -z "${CREATECTFDICT:-}" ]];  then export CREATECTFDICT=0; fi             # Create CTF dictionary
if [[ -z "${SAVECTF:-}" ]];        then export SAVECTF=0; fi                   # Save the CTF to a ROOT file
if [[ -z "${SYNCMODE:-}" ]];       then export SYNCMODE=0; fi                  # Run only reconstruction steps of the synchronous reconstruction
if [[ -z "${NUMAID:-}" ]];         then export NUMAID=0; fi                    # SHM segment id to use for shipping data as well as set of GPUs to use (use 0 / 1 for 2 NUMA domains)
if [[ -z "${NUMAGPUIDS:-}" ]];     then export NUMAGPUIDS=0; fi                # NUMAID-aware GPU id selection
if [[ -z "${CTFINPUT:-}" ]];       then export CTFINPUT=0; fi                  # Read input from CTF using o2-ctf-reader (incompatible to EXTINPUT=1 and RAWTFINPUT)
if [[ -z "${RAWTFINPUT:-}" ]];     then export RAWTFINPUT=0; fi                # Read input from raw TFs using o2-raw-tf-reader (incompatible to EXTINPUT=1 and CTFINPUT=1)
if [[ -z "${DIGITINPUT:-}" ]];     then export DIGITINPUT=0; fi                # Read input from digit files (incompatible to EXTINPUT / CTFINPUT / RAWTFINPUT)
if [[ -z "${NHBPERTF:-}" ]];       then export NHBPERTF=128; fi                # Time frame length (in HBF)
if [[ -z "${GLOBALDPLOPT:-}" ]];   then export GLOBALDPLOPT=; fi               # Global DPL workflow options appended at the end
if [[ -z "${SEVERITY:-}" ]];       then export SEVERITY="info"; fi             # Log verbosity
if [[ -z "${NORATELOG:-}" ]];      then export NORATELOG=1; fi                 # Disable FairMQ Rate Logging
if [[ -z "${INRAWCHANNAME:-}" ]];  then export INRAWCHANNAME=stfb-to-dpl; fi   # Raw channel name used to communicate with DataDistribution
if [[ -z "${WORKFLOWMODE:-}" ]];   then export WORKFLOWMODE=run; fi            # Workflow mode, must be run, print, od dds
if [[ -z "${FILEWORKDIR:-}" ]];    then export FILEWORKDIR=`pwd`; fi           # Override folder where to find grp, etc.
if [[ -z "${FILEWORKDIRRUN:-}" ]]; then export FILEWORKDIRRUN=$FILEWORKDIR; fi # directory where to find the run-related files (grp, collision context)
if [[ -z "${RAWINPUTDIR:-}" ]];    then export RAWINPUTDIR=$FILEWORKDIR; fi    # Directory where to find input files (raw files / raw tf files / ctf files)
if [[ -z "${EPNSYNCMODE:-}" ]];    then export EPNSYNCMODE=0; fi               # Is this workflow supposed to run on EPN for sync processing? Will enable InfoLogger / metrics / fetching QC JSONs from consul...
if [[ -z "${BEAMTYPE:-}" ]];       then export BEAMTYPE=PbPb; fi               # Beam type, must be PbPb, pp, pPb, pO, Op, OO, NeNe cosmic, technical
if [[ -z "${RUNTYPE:-}" ]];        then export RUNTYPE=Standalone; fi          # Run Type, standalone for local tests, otherwise PHYSICS, COSMICS, TECHNICAL, SYNTHETIC
if [[ -z "${IS_SIMULATED_DATA:-}" && $RUNTYPE == "SYNTHETIC" ]]; then export IS_SIMULATED_DATA=1; fi # For SYNTHETIC runs we always process simulated data
if [[ -z "${IS_SIMULATED_DATA:-}" && ( $RUNTYPE == "PHYSICS" || $RUNTYPE == "COSMICS" ) ]]; then export IS_SIMULATED_DATA=0; fi # For PHYSICS runs we always process simulated data
if [[ -z "${IS_SIMULATED_DATA:-}" ]]; then export IS_SIMULATED_DATA=1; fi      # processing simulated data
if [[ -z "${IS_TRIGGERED_DATA:-}" ]]; then export IS_TRIGGERED_DATA=0; fi      # processing triggered data (TPC triggered instead of continuous)
if [[ -z "${CTF_DIR:-}" ]];           then CTF_DIR=$FILEWORKDIR; fi            # Directory where to store CTFs
if [[ -z "${CALIB_DIR:-}" ]];         then CALIB_DIR="/dev/null"; fi           # Directory where to store output from calibration workflows, /dev/null : skip their writing
if [[ -z "${EPN2EOS_METAFILES_DIR:-}" ]]; then EPN2EOS_METAFILES_DIR="/dev/null"; fi # Directory where to store epn2eos files metada, /dev/null : skip their writing
if [[ -z "${DCSCCDBSERVER:-}" ]];  then export DCSCCDBSERVER="http://alio2-cr1-flp199-ib:8083"; fi # server for transvering calibration data to DCS
if [[ -z "${DCSCCDBSERVER_PERS:-}" ]]; then export DCSCCDBSERVER_PERS="http://alio2-cr1-flp199-ib:8084"; fi # persistent server for transvering calibration data to DCS

if [[ $BEAMTYPE == "pO" ]] || [[ $BEAMTYPE == "Op" ]] || [[ $BEAMTYPE == "Op" ]] || [[ $BEAMTYPE == "OO" ]] || [[ $BEAMTYPE == "NeNe" ]] ; then
  export LIGHTNUCLEI=1
else
  export LIGHTNUCLEI=0
fi

if [[ $EPNSYNCMODE == 0 ]]; then
  if [[ -z "${SHMSIZE:-}" ]];       then export SHMSIZE=$(( 8 << 30 )); fi    # Size of shared memory for messages
  if [[ -z "${NGPUS:-}" ]];         then export NGPUS=1; fi                   # Number of GPUs to use, data distributed round-robin
  if [[ -z "${EXTINPUT:-}" ]];      then export EXTINPUT=0; fi                # Receive input from raw FMQ channel instead of running o2-raw-file-reader
  if [[ -z "${EPNPIPELINES:-}" ]];  then export EPNPIPELINES=0; fi            # Set default EPN pipeline multiplicities
  if [[ -z "${SHMTHROW:-}" ]];      then export SHMTHROW=1; fi                # Throw exception when running out of SHM
  if [[ -z "${EDJSONS_DIR:-}" ]];   then export EDJSONS_DIR="jsons"; fi       # output directory for ED json files
  if [[ -z "${WORKFLOW_DETECTORS_FLP_PROCESSING+x}" ]]; then export WORKFLOW_DETECTORS_FLP_PROCESSING=""; fi # No FLP processing by default when we do not run the sync EPN workflow, e.g. full system test will also run full FLP processing
else # Defaults when running on the EPN
  if [[ "0${GEN_TOPO_CALIB_WORKFLOW:-}" != "01" ]]; then
    if [[ -z "${GEN_TOPO_CALIB_NCORES:-}" ]]; then
      if [[ -z "${SHMSIZE:-}" ]];          then export SHMSIZE=$(( 32 << 30 )); fi
    else
      if [[ -z "${SHMSIZE:-}" ]];          then export SHMSIZE=$(( ($GEN_TOPO_CALIB_NCORES * 2) << 30 )); fi
    fi
  else
    if [[ -z "${SHMSIZE:-}" ]];            then export SHMSIZE=$(( 112 << 30 )); fi
  fi
  if [[ -z "${NGPUS:-}" ]];                then export NGPUS=4; fi
  if [[ -z "${EXTINPUT:-}" ]];             then export EXTINPUT=1; fi
  if [[ -z "${EPNPIPELINES:-}" ]];         then export EPNPIPELINES=1; fi
  if [[ -z "${SHMTHROW:-}" ]];             then export SHMTHROW=0; fi
  if [[ -z "${TIMEFRAME_SHM_LIMIT:-}" ]];  then export TIMEFRAME_SHM_LIMIT=$(( $SHMSIZE / 2 )); fi
  if [[ -z "${EDJSONS_DIR:-}" ]];          then export EDJSONS_DIR="/scratch/services/ed/jsons_${RUNTYPE}"; fi
  if [[ -z "${WORKFLOW_DETECTORS_FLP_PROCESSING+x}" ]]; then export WORKFLOW_DETECTORS_FLP_PROCESSING="CTP"; fi # Current default in sync processing is that FLP processing is only enabled for TOF
  if [[ -z "${GEN_TOPO_AUTOSCALE_PROCESSES:-}" ]];      then export GEN_TOPO_AUTOSCALE_PROCESSES=1; fi # On the EPN we should make sure to always use the node to the full extent
fi
# Some more options for running on the EPN
if [[ -z "${INFOLOGGER_SEVERITY:-}" ]]; then export INFOLOGGER_SEVERITY="important"; fi
if [[ -z "${MULTIPLICITY_FACTOR_RAWDECODERS:-}" ]]; then export MULTIPLICITY_FACTOR_RAWDECODERS=1; fi
if [[ -z "${MULTIPLICITY_FACTOR_CTFENCODERS:-}" ]]; then export MULTIPLICITY_FACTOR_CTFENCODERS=1; fi
if [[ -z "${MULTIPLICITY_FACTOR_REST:-}" ]]; then export MULTIPLICITY_FACTOR_REST=1; fi

[[ -z "${SEVERITY_TPC+x}" ]] && SEVERITY_TPC="info" # overrides severity for the tpc workflow
[[ -z "${DISABLE_MC+x}" ]] && DISABLE_MC="--disable-mc"
[[ -z "${DISABLE_ROOT_OUTPUT+x}" ]] && DISABLE_ROOT_OUTPUT="--disable-root-output"

if [[ `uname` == Darwin ]]; then export UDS_PREFIX=; else export UDS_PREFIX="@"; fi

# Env variables required for workflow setup
if [[ $SYNCMODE == 1 ]]; then
  if [[ -z "${WORKFLOW_DETECTORS_MATCHING+x}" ]]; then export WORKFLOW_DETECTORS_MATCHING="ITSTPC,ITSTPCTRD,ITSTPCTOF,ITSTPCTRDTOF,PRIMVTX,SECVTX"; fi # Select matchings that are enabled in sync mode
else
  if [[ -z "${WORKFLOW_DETECTORS_MATCHING+x}" ]]; then export WORKFLOW_DETECTORS_MATCHING="ALL"; fi # All matching / vertexing enabled in async mode
fi

LIST_OF_ASYNC_RECO_STEPS="MID MCH MFT FDD FV0 ZDC HMP"

DISABLE_DIGIT_ROOT_INPUT="--disable-root-input"
DISABLE_ROOT_INPUT="--disable-root-input"
: ${DISABLE_DIGIT_CLUSTER_INPUT="--clusters-from-upstream"}

# Special detector related settings
if [[ -z "${TPC_CORR_SCALING:-}" ]]; then # TPC corr.map lumi scaling options, any combination of --lumi-type <0,1,2> --corrmap-lumi-mode <0,1>  and TPCCorrMap... configurable param
 TPC_CORR_SCALING=
 if [[ $BEAMTYPE == "pp" || $LIGHTNUCLEI == "1" ]] && has_detector CTP; then TPC_CORR_SCALING+="--lumi-type 1"; fi
 if [[ $BEAMTYPE == "PbPb" ]] && has_detector CTP; then TPC_CORR_SCALING+="--lumi-type 1 TPCCorrMap.lumiInstFactor=2.414"; fi
 if [[ $BEAMTYPE == "cosmic" ]]; then TPC_CORR_SCALING=" TPCCorrMap.lumiMean=-1;"; fi # for COSMICS we disable all corrections
 export TPC_CORR_SCALING=$TPC_CORR_SCALING
fi

MID_FEEID_MAP="$FILEWORKDIR/mid-feeId_mapper.txt"

ITSMFT_STROBES=""
[[ ! -z ${ITS_STROBE:-} ]] && ITSMFT_STROBES+="ITSAlpideParam.roFrameLengthInBC=$ITS_STROBE;"
[[ ! -z ${MFT_STROBE:-} ]] && ITSMFT_STROBES+="MFTAlpideParam.roFrameLengthInBC=$MFT_STROBE;"


# Set active reconstruction steps (defaults added according to SYNCMODE)
for i in `echo $LIST_OF_GLORECO | sed "s/,/ /g"`; do
  has_processing_step MATCH_$i && add_comma_separated WORKFLOW_DETECTORS_MATCHING $i # Enable extra matchings requested via WORKFLOW_EXTRA_PROCESSING_STEPS
done
if [[ $SYNCMODE == 1 ]]; then # Add default steps for synchronous mode
  add_comma_separated WORKFLOW_EXTRA_PROCESSING_STEPS ENTROPY_ENCODER
else # Add default steps for async mode
  for i in $LIST_OF_ASYNC_RECO_STEPS; do
    has_detector_reco $i && add_comma_separated WORKFLOW_EXTRA_PROCESSING_STEPS ${i}_RECO
  done
  add_comma_separated WORKFLOW_EXTRA_PROCESSING_STEPS TPC_DEDX
fi

# Assemble matching sources
TRD_SOURCES=
TOF_SOURCES=
HMP_SOURCES=
TRACK_SOURCES=
: ${TRACK_SOURCES_GLO:=}
has_detectors_reco ITS TPC && has_detector_matching ITSTPC && add_comma_separated TRACK_SOURCES "ITS-TPC"
has_detectors_reco TPC TRD && has_detector_matching TPCTRD && { add_comma_separated TRD_SOURCES TPC; add_comma_separated TRACK_SOURCES "TPC-TRD"; }
has_detectors_reco ITS TPC TRD && has_detector_matching ITSTPC && has_detector_matching ITSTPCTRD && { add_comma_separated TRD_SOURCES ITS-TPC; add_comma_separated TRACK_SOURCES "ITS-TPC-TRD"; }
has_detectors_reco TPC TOF && has_detector_matching TPCTOF && { add_comma_separated TOF_SOURCES TPC; add_comma_separated TRACK_SOURCES "TPC-TOF"; }
has_detectors_reco ITS TPC TOF && has_detector_matching ITSTPC && has_detector_matching ITSTPCTOF && { add_comma_separated TOF_SOURCES ITS-TPC; add_comma_separated TRACK_SOURCES "ITS-TPC-TOF"; }
has_detectors_reco TPC TRD TOF && has_detector_matching TPCTRD && has_detector_matching TPCTRDTOF && { add_comma_separated TOF_SOURCES TPC-TRD; add_comma_separated TRACK_SOURCES "TPC-TRD-TOF"; }
has_detectors_reco ITS TPC TRD TOF && has_detector_matching ITSTPC && has_detector_matching ITSTPCTRD && has_detector_matching ITSTPCTRDTOF && { add_comma_separated TOF_SOURCES ITS-TPC-TRD; add_comma_separated TRACK_SOURCES "ITS-TPC-TRD-TOF"; }
has_detectors_reco HMP ITS TPC && has_detector_matching ITSTPC && add_comma_separated HMP_SOURCES "ITS-TPC"
has_detectors_reco HMP ITS TPC TRD && has_detector_matching ITSTPC && has_detector_matching ITSTPCTRD && add_comma_separated HMP_SOURCES "ITS-TPC-TRD"
has_detectors_reco HMP ITS TPC TOF && has_detector_matching ITSTPC && has_detector_matching ITSTPCTOF && add_comma_separated HMP_SOURCES "ITS-TPC-TOF"
has_detectors_reco HMP ITS TPC TRD TOF && has_detector_matching ITSTPC && has_detector_matching ITSTPCTRD && has_detector_matching ITSTPCTRDTOF && add_comma_separated HMP_SOURCES "ITS-TPC-TRD-TOF"
has_detectors_reco HMP TPC TRD && has_detector_matching TPCTRD && add_comma_separated HMP_SOURCES "TPC-TRD"
has_detectors_reco HMP TPC TOF && has_detector_matching TPCTOF && add_comma_separated HMP_SOURCES "TPC-TOF"
has_detectors_reco HMP TPC TRD TOF && has_detector_matching TPCTRD && has_detector_matching TPCTRDTOF && add_comma_separated HMP_SOURCES "TPC-TRD-TOF"
has_detectors_reco MFT MCH && has_detector_matching MFTMCH && add_comma_separated TRACK_SOURCES "MFT-MCH"
has_detectors_reco MCH MID && has_detector_matching MCHMID && add_comma_separated TRACK_SOURCES "MCH-MID"
[[ "0$TRACK_SOURCES_GLO" == "0" ]] && TRACK_SOURCES_GLO=$TRACK_SOURCES

for det in `echo $LIST_OF_DETECTORS | sed "s/,/ /g"`; do
  if [[ $LIST_OF_ASYNC_RECO_STEPS =~ (^| )${det}( |$) ]]; then
    has_detector ${det} && has_processing_step ${det}_RECO && add_comma_separated TRACK_SOURCES "$det"
  else
    has_detector_reco $det && add_comma_separated TRACK_SOURCES "$det"
  fi
done

if [[ "0${WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS:-}" == "0ALL" ]]; then export WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS=$TRACK_SOURCES;
elif [[ "0${WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS:-}" == "0ALLSINGLE" ]]; then export WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS=$WORKFLOW_DETECTORS;
else export WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS=${WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS:-}; fi
if [[ "0${WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS:-}" == "0ALL" ]]; then export WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS=$TRACK_SOURCES;
elif [[ "0${WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS:-}" == "0ALLSINGLE" ]]; then export WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS=$WORKFLOW_DETECTORS;
else export WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS=${WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS:-}; fi
if [[ ! -z ${WORKFLOW_DETECTORS_EXCLUDE_GLOBAL_READER_TRACKS:-} ]]; then
  for i in ${WORKFLOW_DETECTORS_EXCLUDE_GLOBAL_READER_TRACKS//,/ }; do
    export WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS=$(echo $WORKFLOW_DETECTORS_USE_GLOBAL_READER_TRACKS | sed -e "s/,$i,/,/g" -e "s/^$i,//" -e "s/,$i"'$'"//" -e "s/^$i"'$'"//")
  done
fi
if [[ ! -z ${WORKFLOW_DETECTORS_EXCLUDE_GLOBAL_READER_CLUSTERS:-} ]]; then
  for i in ${WORKFLOW_DETECTORS_EXCLUDE_GLOBAL_READER_CLUSTERS//,/ }; do
    export WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS=$(echo $WORKFLOW_DETECTORS_USE_GLOBAL_READER_CLUSTERS | sed -e "s/,$i,/,/g" -e "s/^$i,//" -e "s/,$i"'$'"//" -e "s/^$i"'$'"//")
  done
fi

: ${VERTEXING_SOURCES:="$TRACK_SOURCES"}
: ${VERTEX_TRACK_MATCHING_SOURCES:="$TRACK_SOURCES"}
[[ ! -z $VERTEXING_SOURCES ]] && PVERTEX_CONFIG+=" --vertexing-sources $VERTEXING_SOURCES"
[[ ! -z $VERTEX_TRACK_MATCHING_SOURCES ]] && PVERTEX_CONFIG+=" --vertex-track-matching-sources $VERTEX_TRACK_MATCHING_SOURCES"

# this option requires well calibrated timing beween different detectors, at the moment suppress it
#has_detector_reco FT0 && PVERTEX_CONFIG+=" --validate-with-ft0"

# Sanity checks on env variables
if [[ $(( $EXTINPUT + $CTFINPUT + $RAWTFINPUT + $DIGITINPUT )) -ge 2 ]]; then
  echo Only one of EXTINPUT / CTFINPUT / RAWTFINPUT / DIGITINPUT must be set
  exit 1
fi
if [[ $SAVECTF == 1 ]] && [[ $CTFINPUT == 1 ]]; then
  echo SAVECTF and CTFINPUT are incompatible
  exit 1
fi
if [[ $SYNCMODE == 1 ]] && [[ $CTFINPUT == 1 ]]; then
  echo SYNCMODE and CTFINPUT are incompatible
  exit 1
fi
if [[ $WORKFLOWMODE != "run" ]] && [[ $WORKFLOWMODE != "print" ]] && [[ $WORKFLOWMODE != "dds" ]] && [[ $WORKFLOWMODE != "dump" ]]; then
  echo Invalid workflow mode
  exit 1
fi


fi # setenv.sh sourced
