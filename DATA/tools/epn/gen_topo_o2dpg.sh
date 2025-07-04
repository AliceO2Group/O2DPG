#!/bin/bash

# Some defaults
[[ -z "$GEN_TOPO_STDERR_LOGGING" ]] && export GEN_TOPO_STDERR_LOGGING=1 # Enable logging of stderr messages

# Check settings coming from AliECS via env variables
if [[ -z "$GEN_TOPO_HASH" ]]; then echo \$GEN_TOPO_HASH missing; exit 1; fi # Flag whether source is a hash or a folder
if [[ -z "$GEN_TOPO_SOURCE" ]]; then echo \$GEN_TOPO_SOURCE missing; exit 1; fi # O2DPG repository source, either a commit hash or a path
if [[ -z "$GEN_TOPO_LIBRARY_FILE" ]]; then echo \$GEN_TOPO_LIBRARY_FILE missing; exit 1; fi # Topology description library file in the DATA path of the O2DPG repository
if [[ -z "$GEN_TOPO_WORKFLOW_NAME" ]]; then echo \$GEN_TOPO_WORKFLOW_NAME missing; exit 1; fi # Workflow name in library file
if [[ -z "${WORKFLOW_DETECTORS+x}" ]]; then echo \$WORKFLOW_DETECTORS missing; exit 1; fi # Comma-separated list of detectors to run processing for
if [[ -z "${WORKFLOW_DETECTORS_QC+x}" && -z "${WORKFLOW_DETECTORS_EXCLUDE_QC+x}" ]]; then echo \$WORKFLOW_DETECTORS_EXCLUDE_QC missing; exit 1; fi # Comma-separated list of detectors to run QC for
if [[ -z "${WORKFLOW_DETECTORS_CALIB+x}" && -z "${WORKFLOW_DETECTORS_EXCLUDE_CALIB+x}" ]]; then echo \$WORKFLOW_DETECTORS_EXCLUDE_CALIB missing; exit 1; fi # Comma-separated list of detectors to run calibration for
if [[ -z "${WORKFLOW_PARAMETERS+x}" ]]; then echo \$WORKFLOW_PARAMETERS missing; exit 1; fi # Additional parameters for workflow
if [[ -z "${RECO_NUM_NODES_OVERRIDE+x}" ]]; then echo \$RECO_NUM_NODES_OVERRIDE missing; exit 1; fi # Override number of nodes
if [[ -z "${RECO_MAX_FAIL_NODES_OVERRIDE+x}" ]]; then echo \$RECO_MAX_FAIL_NODES_OVERRIDE missing; exit 1; fi # Override number of nodes allowed to fail
if [[ -z "$DDMODE" ]] && [[ -z "$DDWORKFLOW" ]]; then echo Either \$DDMODE or \$DDWORKFLOW must be set; exit 1; fi # Select data distribution workflow
if [[ -z "$MULTIPLICITY_FACTOR_RAWDECODERS" ]]; then echo \$MULTIPLICITY_FACTOR_RAWDECODERS missing; exit 1; fi # Process multiplicity scaling parameter
if [[ -z "$MULTIPLICITY_FACTOR_CTFENCODERS" ]]; then echo \$MULTIPLICITY_FACTOR_CTFENCODERS missing; exit 1; fi # Process multiplicity scaling parameter
if [[ -z "$MULTIPLICITY_FACTOR_REST" ]]; then echo \$MULTIPLICITY_FACTOR_REST missing; exit 1; fi # Process multiplicity scaling parameter
if [[ -z "$RECOSHMSIZE" ]]; then echo \$RECOSHMSIZE missing; exit 1; fi # SHM Size for reconstruction collections
if [[ -z "$DDSHMSIZE" ]]; then echo \$DDSHMSIZE missing; exit 1; fi # SHM Size for DD

# In case of debug mode, overwrite some settings
if [[ "${DEBUG_TOPOLOGY_GENERATION:=0}" == "1" ]]; then
  echo "Debugging mode enabled. Setting options accordingly" 1>&2
  RECO_NUM_NODES_OVERRIDE=1       # to avoid slurm query, specify number of nodes to fixed value
  GEN_TOPO_MI100_NODES=1          # also for MI100 nodes
  GEN_TOPO_OVERRIDE_TEMPDIR=$PWD  # keep temporary files like QC jsons in local directory
  EPN2EOS_METAFILES_DIR=/tmp      # nothing is written here, just needs to be set to something
  unset ECS_ENVIRONMENT_ID
  unset GEN_TOPO_CACHE_HASH
fi

# Check settings coming from the EPN
if [[ -z "$FILEWORKDIR" ]]; then echo \$FILEWORKDIR missing; exit 1; fi
if [[ -z "$INRAWCHANNAME" ]]; then echo \$INRAWCHANNAME missing; exit 1; fi
if [[ -z "$CTF_DIR" ]]; then echo \$CTF_DIR missing; exit 1; fi
if [[ -z "$CALIB_DIR" ]]; then echo \$CALIB_DIR missing; exit 1; fi
if [[ -z "$EPN2EOS_METAFILES_DIR" ]]; then echo \$EPN2EOS_METAFILES_DIR missing; exit 1; fi
if [[ -z "$GEN_TOPO_WORKDIR" ]]; then echo \$GEN_TOPO_WORKDIR missing; exit 1; fi
if [[ -z "$GEN_TOPO_ODC_EPN_TOPO_CMD" ]]; then echo \$GEN_TOPO_ODC_EPN_TOPO_CMD missing; exit 1; fi
if [[ -z "$GEN_TOPO_EPN_CCDB_SERVER" ]]; then echo \$GEN_TOPO_EPN_CCDB_SERVER missing; exit 1; fi

# Replace TRG by CTP
if [[ ! -z "$WORKFLOW_DETECTORS"  ]]; then export WORKFLOW_DETECTORS=${WORKFLOW_DETECTORS/TRG/CTP} ; fi
if [[ ! -z "$WORKFLOW_DETECTORS_QC"  ]]; then export WORKFLOW_DETECTORS_QC=${WORKFLOW_DETECTORS_QC/TRG/CTP} ; fi
if [[ ! -z "$WORKFLOW_DETECTORS_CALIB"  ]]; then export WORKFLOW_DETECTORS_CALIB=${WORKFLOW_DETECTORS_CALIB/TRG/CTP} ; fi

mkdir -p $GEN_TOPO_WORKDIR || { echo Error creating directory 1>&2; exit 1; }
for i in `seq 1 100`; do
  exec 100>${GEN_TOPO_WORKDIR}/${i}.lock || { echo Cannot create file descriptor for lock file 1>&2; exit 1; }
  flock -n -E 100 100
  RETVAL=$?
  [[ $RETVAL == 100 ]] && continue
  [[ $RETVAL != 0 ]] && { echo Cannot open lock file, retval $RETVAL 1>&2; exit 1; }
  export GEN_TOPO_WORKDIR=$GEN_TOPO_WORKDIR/${i}_${GEN_TOPO_ONTHEFLY}
  GEN_TOPO_LOCKFILE=${GEN_TOPO_WORKDIR}/${i}.lock
  break
done
[[ -z "$GEN_TOPO_LOCKFILE" ]] && { echo Topology generation could not obtained a work dir 1>&1; exit 1; }

if [[ "0$DDMODE" == "0discard" ]] || [[ "0$DDMODE" == "0disk" ]]; then
  export GEN_TOPO_LIBRARY_FILE="production/no-processing.desc"
  export GEN_TOPO_WORKFLOW_NAME="no-processing"
fi

mkdir -p $GEN_TOPO_WORKDIR/cache || { echo Error creating directory 1>&2; exit 1; }
while true; do
  if [[ $GEN_TOPO_HASH == 1 ]]; then
    cd $GEN_TOPO_WORKDIR || { echo Cannot enter work dir 1>&2; exit 1; }
    if [[ "0$GEN_TOPO_ONTHEFLY" == "01" && ! -z "$GEN_TOPO_CACHE_HASH" ]]; then
      export GEN_TOPO_CACHEABLE=1
    fi
    if [[ "0$GEN_TOPO_CACHEABLE" == "01" && -f cache/$GEN_TOPO_CACHE_HASH ]]; then
      if [[ "0$GEN_TOPO_WIPE_CACHE" == "01" ]]; then
        rm -f cache/$GEN_TOPO_CACHE_HASH
      else
        echo Reusing cached XML topology $GEN_TOPO_CACHE_HASH 1>&2
        touch cache/$GEN_TOPO_CACHE_HASH
        cp cache/$GEN_TOPO_CACHE_HASH $GEN_TOPO_WORKDIR/output.xml
        break
      fi
    fi
    for CHECKOUTATTEMPT in 1 2; do
      if [[ ! -d O2DPG ]]; then git clone https://github.com/AliceO2Group/O2DPG.git 1>&2 || { echo O2DPG checkout failed 1>&2; exit 1; }; fi
      cd O2DPG
      rm -f DATA/core_dump_*
      git reset --hard HEAD &> /dev/null && git clean -d -f &> /dev/null && break
      [[ $CHECKOUTATTEMPT -eq 2 ]] && { echo git reset error 1>&2; exit 1; }
      echo "Clean-up of O2DPG repository failed. Removing repository and cloning it from scratch" 1>&2
      cd $GEN_TOPO_WORKDIR || { echo Cannot enter work dir 1>&2; exit 1; }
      rm -rf O2DPG
    done
    git checkout $GEN_TOPO_SOURCE &> /dev/null
    if [[ $? != 0 ]]; then
      git fetch --tags origin 1>&2 || { echo Repository update failed 1>&2; exit 1; }
      git checkout $GEN_TOPO_SOURCE &> /dev/null || { echo commit does not exist 1>&2; exit 1; }
    fi
    # At a tag, or a detached non-dirty commit, but not on a branch
    if ! git describe --exact-match --tags HEAD &> /dev/null && ( git symbolic-ref -q HEAD &> /dev/null || ! git diff-index --quiet HEAD &> /dev/null ); then
      unset GEN_TOPO_CACHEABLE
    fi
    cd DATA
  else
    cd $GEN_TOPO_SOURCE || { echo Directory missing 1>&2; exit 1; }
  fi
  export EPNSYNCMODE=1
  export O2DPG_ROOT=`realpath \`pwd\`/../`
  echo Running topology generation to temporary file $GEN_TOPO_WORKDIR/output.xml 1>&2
  # Run stage 3 of GenTopo, now from the O2DPG version specified by the user
  ./tools/parse "$GEN_TOPO_LIBRARY_FILE" $GEN_TOPO_WORKFLOW_NAME $GEN_TOPO_WORKDIR/output.xml 1>&2 || { echo Error during workflow description parsing 1>&2; exit 1; }
  if [[ "0$GEN_TOPO_CACHEABLE" == "01" ]]; then
    cd $GEN_TOPO_WORKDIR
    if [[ `ls cache/ | wc -l` -ge 1000 ]]; then
      ls -t cache/* | tail -n +1000 | xargs rm
    fi
    cp $GEN_TOPO_WORKDIR/output.xml cache/$GEN_TOPO_CACHE_HASH
  fi

  break
done


if [[ ! -z "$GEN_TOPO_ODC_EPN_TOPO_POST_CACHING_CMD" ]] && [[ "0$WORKFLOWMODE" != "0print" ]]; then
  TMP_POST_CACHING_CMD="$GEN_TOPO_ODC_EPN_TOPO_POST_CACHING_CMD $GEN_TOPO_ODC_EPN_TOPO_POST_CACHING_ARGS"
  TMP_POST_CACHING_NMIN=$(( $RECO_NUM_NODES_OVERRIDE > $RECO_MAX_FAIL_NODES_OVERRIDE ? $RECO_NUM_NODES_OVERRIDE - $RECO_MAX_FAIL_NODES_OVERRIDE : 0 ))
  TMP_POST_CACHING_CMD+=" --nodes-mi50 $RECO_NUM_NODES_OVERRIDE --nmin-mi50 $TMP_POST_CACHING_NMIN"
  if [[ -z $GEN_TOPO_MI100_NODES || $GEN_TOPO_MI100_NODES == "0" ]]; then
    TMP_POST_CACHING_CMD+=" --force-exact-node-numbers --nodes-mi100 0 --nmin-mi100 0"
  elif [[ ! -z $GEN_TOPO_MI100_NODES && $GEN_TOPO_MI100_NODES != "-1" ]]; then
    TMP_POST_CACHING_NMIN=$(( $GEN_TOPO_MI100_NODES > $RECO_MAX_FAIL_NODES_OVERRIDE ? $GEN_TOPO_MI100_NODES - $RECO_MAX_FAIL_NODES_OVERRIDE : 0 ))
    TMP_POST_CACHING_CMD+=" --force-exact-node-numbers --nodes-mi100 $GEN_TOPO_MI100_NODES --nmin-mi100 $TMP_POST_CACHING_NMIN"
  fi
  TMP_POST_CACHING_CMD+=" -o $GEN_TOPO_WORKDIR/output.xml.new $GEN_TOPO_WORKDIR/output.xml"
  echo "Running post-caching topo-merger command: $TMP_POST_CACHING_CMD" 1>&2
  eval $TMP_POST_CACHING_CMD 1>&2 || { echo Error during EPN resource allocation 1>&2; exit 1; }
  mv -f $GEN_TOPO_WORKDIR/output.xml.new $GEN_TOPO_WORKDIR/output.xml 1>&2
fi

if [[ ! -z "$ECS_ENVIRONMENT_ID" && -d "/var/log/topology/" && $USER == "epn" ]]; then
  GEN_TOPO_LOG_FILE=/var/log/topology/topology-$(date -u +%Y%m%d-%H%M%S)-$ECS_ENVIRONMENT_ID.xml
  cp $GEN_TOPO_WORKDIR/output.xml $GEN_TOPO_LOG_FILE
  nohup gzip $GEN_TOPO_LOG_FILE &> /dev/null &
fi

cat $GEN_TOPO_WORKDIR/output.xml

if [[ "$DEBUG_TOPOLOGY_GENERATION" == "0" ]]; then
  echo Removing temporary output file $GEN_TOPO_WORKDIR/output.xml 1>&2
  rm $GEN_TOPO_WORKDIR/output.xml
fi
rm -f $GEN_TOPO_LOCKFILE
