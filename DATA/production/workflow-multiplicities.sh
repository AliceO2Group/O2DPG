#!/bin/bash

if [[ -z ${SOURCE_GUARD_MULTIPLICITIES:-} ]]; then
SOURCE_GUARD_MULTIPLICITIES=1

# ---------------------------------------------------------------------------------------------------------------------
# Threads

: ${NITSDECTHREADS:=2}
: ${NMFTDECTHREADS:=2}

: ${NMFTTHREADS:=2}

: ${SVERTEX_THREADS:=$(( $SYNCMODE == 1 ? 1 : 2 ))}

: ${ITSTRK_THREADS:=1}
: ${ITSTPC_THREADS:=1}

: ${HIGH_RATE_PP:=0}

# FIXME: multithreading in the itsmft reconstruction does not work on macOS.
if [[ $(uname) == "Darwin" ]]; then
    NITSDECTHREADS=1
    NMFTDECTHREADS=1
fi

if [[ $SYNCMODE == 1 ]]; then NTRDTRKTHREADS=1; else NTRDTRKTHREADS=; fi

: ${NGPURECOTHREADS:=-1} # -1 = auto-detect

# ---------------------------------------------------------------------------------------------------------------------
# Process multiplicities

N_F_REST=$MULTIPLICITY_FACTOR_REST
N_F_RAW=$MULTIPLICITY_FACTOR_RAWDECODERS
N_F_CTF=$MULTIPLICITY_FACTOR_CTFENCODERS

N_TPCTRK=$NGPUS
if [[ ! -z ${OPTIMIZED_PARALLEL_ASYNC:-} ]]; then
  # Tuned multiplicities for async processing
  if [[ $OPTIMIZED_PARALLEL_ASYNC == "pp_8cpu" ]]; then
    [[ -z $TIMEFRAME_RATE_LIMIT ]] && TIMEFRAME_RATE_LIMIT=3
    NGPURECOTHREADS=5
  elif [[ $OPTIMIZED_PARALLEL_ASYNC == "pp_16cpu" ]]; then
    [[ -z $TIMEFRAME_RATE_LIMIT ]] && TIMEFRAME_RATE_LIMIT=8
    [[ -z $SHMSIZE ]] && SHMSIZE=22000000000
    NGPURECOTHREADS=9
    NTRDTRKTHREADS=3
    ITSTRK_THREADS=3
    ITSTPC_THREADS=3
  elif [[ $OPTIMIZED_PARALLEL_ASYNC == "pp_64cpu" ]]; then
    [[ -z $TIMEFRAME_RATE_LIMIT ]] && TIMEFRAME_RATE_LIMIT=32
    [[ -z $SHMSIZE ]] && SHMSIZE=90000000000
    NGPURECOTHREADS=12
    NTRDTRKTHREADS=3
    ITSTRK_THREADS=3
    ITSTPC_THREADS=3
    N_TPCTRK=3
    N_ITSTRK=3
    N_TPCITS=3
    N_TRDTRK=2
    N_MCHCL=3
    N_TOFMATCH=2
    N_TPCENTDEC=3
  elif [[ $OPTIMIZED_PARALLEL_ASYNC == "pp_1gpu" ]]; then
    [[ -z $TIMEFRAME_RATE_LIMIT ]] && TIMEFRAME_RATE_LIMIT=8
    [[ -z $SHMSIZE ]] && SHMSIZE=20000000000
    N_TOFMATCH=2
    N_MCHCL=3
    N_TPCENTDEC=2
    N_TPCITS=3
    N_MCHTRK=2
    N_ITSTRK=3
    NGPURECOTHREADS=8
    NTRDTRKTHREADS=3
    ITSTRK_THREADS=2
    ITSTPC_THREADS=2
  elif [[ $OPTIMIZED_PARALLEL_ASYNC == "pp_4gpu" ]]; then
    [[ -z $TIMEFRAME_RATE_LIMIT ]] && TIMEFRAME_RATE_LIMIT=45
    [[ -z $SHMSIZE ]] && SHMSIZE=100000000000
    NGPURECOTHREADS=8
    NTRDTRKTHREADS=2
    ITSTRK_THREADS=2
    ITSTPC_THREADS=2
    NGPUS=4
    N_TPCTRK=4
    N_FWDMATCH=2
    N_PRIMVTXMATCH=1
    N_PRIMVTX=1
    N_SECVTX=2
    N_TRDTRKTRANS=1
    N_AODPROD=4
    N_TRDTRK=5
    N_TOFMATCH=8
    N_MCHCL=12
    N_MCHTRK=6
    N_TPCENTDEC=6
    N_TPCITS=12
    N_ITSTRK=12
  elif [[ $OPTIMIZED_PARALLEL_ASYNC == "PbPb_4gpu" ]]; then
    [[ -z $TIMEFRAME_RATE_LIMIT ]] && TIMEFRAME_RATE_LIMIT=20
    [[ -z $SHMSIZE ]] && SHMSIZE=128000000000 # SHM_LIMIT 3/4
    NGPURECOTHREADS=8
    NTRDTRKTHREADS=4
    NGPUS=4
    N_TPCTRK=4
    # time in s: pvtx 16, tof 30, trd 82 itstpc 53 its 200 mfttr 30 tpcent 23 hmp-clus 40 (25.11.22)
    N_TPCENTDEC=$(math_max $((2 * $NGPUS / 4)) 1)
    N_ITSTRK=$(math_max $((10 * $NGPUS / 4)) 1)
    N_TPCITS=$(math_max $((4 * $NGPUS / 4)) 1)
    N_MFTTRK=$(math_max $((3 * $NGPUS / 4)) 1)
    N_TRDTRK=$(math_max $((7 * $NGPUS / 4)) 1)
    N_TOFMATCH=$(math_max $((3 * $NGPUS / 4)) 1)
    N_HMPCLUS=$(math_max $((3 * $NGPUS / 4)) 1)
    CONFIG_EXTRA_PROCESS_o2_its_reco_workflow="ITSVertexerParam.nThreads=3;ITSCATrackerParam.nThreads=3;"
    N_MCHCL=2
    N_PRIMVTXMATCH=2
    N_PRIMVTX=3
  elif [[ $OPTIMIZED_PARALLEL_ASYNC == "PbPb_64cpu" ]]; then
    NGPURECOTHREADS=6
    NTRDTRKTHREADS=2
    N_TPCENTDEC=2
    N_MFTTRK=3
    N_ITSTRK=3
    N_TPCITS=2
    N_MCHTRK=1
    N_TOFMATCH=9
    N_TPCTRK=6
  else
    echo "Invalid optimized setting '$OPTIMIZED_PARALLEL_ASYNC'" 1>&2
    exit 1
  fi
elif [[ $EPNPIPELINES != 0 ]]; then
  NTRDTRKTHREADS=2
  ITSTRK_THREADS=2
  ITSTPC_THREADS=2
  RECO_NUM_NODES_WORKFLOW_CMP=$((($RECO_NUM_NODES_WORKFLOW > 15 ? $RECO_NUM_NODES_WORKFLOW : 15) * ($NUMAGPUIDS != 0 ? 2 : 1))) # Limit the lower scaling factor, multiply by 2 if we have 2 NUMA domains
  # Tuned multiplicities for sync pp / Pb-Pb processing
  if [[ $BEAMTYPE == "pp" ]]; then
    N_ITSRAWDEC=$(math_max $((6 * $EPNPIPELINES * $NGPUS / 4)) 1)
    N_MFTRAWDEC=$(math_max $((2 * $EPNPIPELINES * $NGPUS / 4)) 1)
    if [[ "${GEN_TOPO_AUTOSCALE_PROCESSES:-}" == "1" && $RUNTYPE == "PHYSICS" ]]; then
      N_MCHCL=$(math_max $((6 * 100 / $RECO_NUM_NODES_WORKFLOW_CMP)) 1)
    fi
    if [[ "$HIGH_RATE_PP" == "1" ]]; then
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
    if [[ $BEAMTYPE == "PbPb" ]]; then
      N_ITSTRK=$(math_max $((2 * $EPNPIPELINES * $NGPUS / 4)) 1)
    elif [[ $BEAMTYPE == "cosmic" ]]; then
      N_ITSTRK=$(math_max $((4 * $EPNPIPELINES * $NGPUS / 4)) 1)
    fi
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
  if [[ "${GEN_TOPO_AUTOSCALE_PROCESSES:-}" == "1" ]]; then
    # Scale some multiplicities with the number of nodes
    N_ITSRAWDEC=$(math_max $((3 * 60 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_ITSRAWDEC:-1}) # This means, if we have 60 EPN nodes, we need at least 3 ITS RAW decoders (will be scaled down by a factor of two automatically if we have 2 NUMA domains)
    N_MFTRAWDEC=$(math_max $((3 * 60 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_MFTRAWDEC:-1})
    if [[ $RUNTYPE == "PHYSICS" || $RUNTYPE == "COSMICS" ]]; then
      if [[ $BEAMTYPE == "pp" ]]; then
        N_ITSTRK=$(math_max $((9 * 200 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_ITSTRK:-1})
      elif [[ $BEAMTYPE == "cosmic" ]]; then
        N_ITSTRK=$(math_max $((5 * 200 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_ITSTRK:-1})
      else
        N_ITSTRK=$(math_max $((2 * 200 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_ITSTRK:-1})
      fi
      N_ITSTRK=$(( $N_ITSTRK < 7 ? $N_ITSTRK : 7 ))
      N_MFTTRK=$(math_max $((1 * 60 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_MFTTRK:-1})
      N_CTPRAWDEC=$(math_max $((1 * 30 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_CTPRAWDEC:-1})
      N_TRDRAWDEC=$(math_max $((3 * 60 / $RECO_NUM_NODES_WORKFLOW_CMP)) ${N_TRDRAWDEC:-1})
    fi
  fi
fi

if [[ -z ${EVE_NTH_EVENT:-} ]]; then
  if [[ $BEAMTYPE == "PbPb" ]]; then
    EVE_NTH_EVENT=2
  elif [[ "$HIGH_RATE_PP" == "1" ]]; then
    EVE_NTH_EVENT=10
  elif [[ $BEAMTYPE == "pp" && "${ED_VERTEX_MODE:-}" == "1" ]]; then
    EVE_NTH_EVENT=$((4 * 250 / $RECO_NUM_NODES_WORKFLOW_CMP))
  fi
  [[ ! -z ${EPN_GLOBAL_SCALING:-} ]] && EVE_NTH_EVENT=$(($EVE_NTH_EVENT * $EPN_GLOBAL_SCALING))
fi

if [[ "$HIGH_RATE_PP" == "1" ]]; then
  : ${CUT_RANDOM_FRACTION_ITS:=0.97}
else
  : ${CUT_RANDOM_FRACTION_ITS:=0.95}
fi
[[ $RUNTYPE != "COSMICS" ]] && : ${CUT_RANDOM_FRACTION_MCH:=0.7}

#if [[ "$HIGH_RATE_PP" == "1" ]]; then
  # Extra settings for HIGH_RATE_PP
#fi

fi

true
