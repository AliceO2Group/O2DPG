#!/bin/bash

if [[ -z $SOURCE_GUARD_MULTIPLICITIES ]]; then
SOURCE_GUARD_MULTIPLICITIES=1

# ---------------------------------------------------------------------------------------------------------------------
# Threads

[[ -z $NITSDECTHREADS ]] && NITSDECTHREADS=2
[[ -z $NMFTDECTHREADS ]] && NMFTDECTHREADS=2

[[ -z $NMFTTHREADS ]] && NMFTTHREADS=2

[[ -z $SVERTEX_THREADS ]] && SVERTEX_THREADS=$(( $SYNCMODE == 1 ? 1 : 2 ))
# FIXME: multithreading in the itsmft reconstruction does not work on macOS.
if [[ $(uname) == "Darwin" ]]; then
    NITSDECTHREADS=1
    NMFTDECTHREADS=1
fi

[[ $SYNCMODE == 1 ]] && NTRDTRKTHREADS=1

[[ -z $NGPURECOTHREADS ]] & NGPURECOTHREADS=-1 # -1 = auto-detect

# ---------------------------------------------------------------------------------------------------------------------
# Process multiplicities

N_F_REST=$MULTIPLICITY_FACTOR_REST
N_F_RAW=$MULTIPLICITY_FACTOR_RAWDECODERS
N_F_CTF=$MULTIPLICITY_FACTOR_CTFENCODERS

N_TPCTRK=$NGPUS
if [[ $OPTIMIZED_PARALLEL_ASYNC != 0 ]]; then
  # Tuned multiplicities for async Pb-Pb processing
  if [[ $SYNCMODE == "1" ]]; then echo "Must not use OPTIMIZED_PARALLEL_ASYNC with GPU or SYNCMODE" 1>&2; exit 1; fi
  if [[ $NUMAGPUIDS != 0 ]]; then N_NUMAFACTOR=1; else N_NUMAFACTOR=2; fi
  NGPURECOTHREADS=6
  NTRDTRKTHREADS=2
  if [[ $GPUTYPE == "CPU" ]]; then
    N_TPCENTDEC=$((2 * $N_NUMAFACTOR))
    N_MFTTRK=$((3 * $N_NUMAFACTOR))
    N_ITSTRK=$((3 * $N_NUMAFACTOR))
    N_TPCITS=$((2 * $N_NUMAFACTOR))
    N_MCHTRK=$((1 * $N_NUMAFACTOR))
    N_TOFMATCH=$((9 * $N_NUMAFACTOR))
    N_TPCTRK=$((6 * $N_NUMAFACTOR))
  else
    N_TPCENTDEC=$(math_max $((3 * $NGPUS * $OPTIMIZED_PARALLEL_ASYNC * $N_NUMAFACTOR / 4)) 1)
    N_MFTTRK=$(math_max $((6 * $NGPUS * $OPTIMIZED_PARALLEL_ASYNC * $N_NUMAFACTOR / 4)) 1)
    N_ITSTRK=$(math_max $((6 * $NGPUS * $OPTIMIZED_PARALLEL_ASYNC * $N_NUMAFACTOR / 4)) 1)
    N_TPCITS=$(math_max $((4 * $NGPUS * $OPTIMIZED_PARALLEL_ASYNC * $N_NUMAFACTOR / 4)) 1)
    N_MCHTRK=$(math_max $((2 * $NGPUS * $OPTIMIZED_PARALLEL_ASYNC * $N_NUMAFACTOR / 4)) 1)
    N_TOFMATCH=$(math_max $((20 * $NGPUS * $OPTIMIZED_PARALLEL_ASYNC * $N_NUMAFACTOR / 4)) 1)
  fi
elif [[ $EPNPIPELINES != 0 ]]; then
  RECO_NUM_NODES_WORKFLOW_CMP=$((($RECO_NUM_NODES_WORKFLOW > 15 ? $RECO_NUM_NODES_WORKFLOW : 15) * ($NUMAGPUIDS != 0 ? 2 : 1))) # Limit the lower scaling factor, multiply by 2 if we have 2 NUMA domains
  # Tuned multiplicities for sync pp / Pb-Pb processing
  if [[ $BEAMTYPE == "pp" ]]; then
    N_ITSRAWDEC=$(math_max $((6 * $EPNPIPELINES * $NGPUS / 4)) 1)
    N_MFTRAWDEC=$(math_max $((2 * $EPNPIPELINES * $NGPUS / 4)) 1)
    N_MCHCL=$(math_max $((6 * 100 / $RECO_NUM_NODES_WORKFLOW_CMP)) 1)
    if [[ "0$HIGH_RATE_PP" == "01" ]]; then
      N_TPCITS=$(math_max $((5 * $EPNPIPELINES * $NGPUS / 4)) 1)
      N_TPCENT=$(math_max $((4 * $EPNPIPELINES * $NGPUS / 4)) 1)
      N_TOFMATCH=$(math_max $((2 * $EPNPIPELINES * $NGPUS / 4)) 1)
      N_TRDTRKTRANS=$(math_max $((4 * $EPNPIPELINES * $NGPUS / 4)) 1)
      N_ITSTRK=$(math_max $((9 * $EPNPIPELINES * $NGPUS / 4)) 1)
      N_PRIMVTX=$(math_max $((2 * $EPNPIPELINES * $NGPUS / 4)) 1)
      N_PRIMVTXMATCH=$(math_max $((2 * $EPNPIPELINES * $NGPUS / 4)) 1)
    else
      N_TPCITS=$(math_max $((3 * $EPNPIPELINES * $NGPUS / 4)) 1)
      N_TPCENT=$(math_max $((3 * $EPNPIPELINES * $NGPUS / 4)) 1)
      N_ITSTRK=$(math_max $((6 * $EPNPIPELINES * $NGPUS / 4)) 1)
    fi
  else
    N_ITSTRK=$(math_max $((2 * $EPNPIPELINES * $NGPUS / 4)) 1)
    N_ITSRAWDEC=$(math_max $((3 * $EPNPIPELINES * $NGPUS / 4)) 1)
    N_TPCITS=$(math_max $((3 * $EPNPIPELINES * $NGPUS / 4)) 1)
    N_TPCENT=$(math_max $((3 * $EPNPIPELINES * $NGPUS / 4)) 1)
  fi
  N_EMCREC=$(math_max $((3 * $EPNPIPELINES * $NGPUS / 4)) 1)
  N_TRDENT=$(math_max $((3 * $EPNPIPELINES * $NGPUS / 4)) 1)
  N_TRDTRK=$(math_max $((3 * $EPNPIPELINES * $NGPUS / 4)) 1)
  N_MFTTRK=$(math_max $((5 * $EPNPIPELINES * $NGPUS / 4)) 1)
  N_TPCRAWDEC=$(math_max $((12 * $EPNPIPELINES * $NGPUS / 4)) 1)
  if [[ $GPUTYPE == "CPU" ]]; then
    N_TPCTRK=8
    NGPURECOTHREADS=4
  fi
  # Scale some multiplicities with the number of nodes
  N_ITSRAWDEC=$(math_max $((3 * 60 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_ITSRAWDEC:-1}) # This means, if we have 60 EPN nodes, we need at least 3 ITS RAW decoders per NUMA domain (2 * 3 = 6)
  N_MFTRAWDEC=$(math_max $((3 * 60 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_MFTRAWDEC:-1})
  if [[ $BEAMTYPE == "pp" ]]; then
    N_ITSTRK=$(math_max $((9 * 200 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_ITSTRK:-1})
  else
    N_ITSTRK=$(math_max $((2 * 200 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_ITSTRK:-1})
  fi
  N_MFTTRK=$(math_max $((1 * 60 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_MFTTRK:-1})
  N_CTPRAWDEC=$(math_max $((1 * 30 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_CTPRAWDEC:-1})
  N_TRDRAWDEC=$(math_max $((3 * 60 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_TRDRAWDEC:-1})
fi

if [[ -z $EVE_NTH_EVENT ]]; then
  if [[ $BEAMTYPE == "PbPb" ]]; then
    [[ -z $EVE_NTH_EVENT ]] && EVE_NTH_EVENT=2
  elif [[ "0$HIGH_RATE_PP" == "01" ]]; then
    [[ -z $EVE_NTH_EVENT ]] && EVE_NTH_EVENT=10
  elif [[ $BEAMTYPE == "pp" && "0$ED_VERTEX_MODE" == "01" ]]; then
    [[ -z $EVE_NTH_EVENT ]] && EVE_NTH_EVENT=$((4 * 250 / $RECO_NUM_NODES_WORKFLOW_CMP))
  fi
fi

if [[ "0$HIGH_RATE_PP" == "01" ]]; then
  [[ -z $CUT_RANDOM_FRACTION_ITS ]] && CUT_RANDOM_FRACTION_ITS=0.97
else
  [[ -z $CUT_RANDOM_FRACTION_ITS ]] && CUT_RANDOM_FRACTION_ITS=0.95
fi
[[ -z $CUT_RANDOM_FRACTION_MCH ]] && [[ $RUNTYPE != "COSMICS" ]] && CUT_RANDOM_FRACTION_MCH=0.7

#if [[ "0$HIGH_RATE_PP" == "01" ]]; then
  # Extra settings for HIGH_RATE_PP
#fi

fi

true
