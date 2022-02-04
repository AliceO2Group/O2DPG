#!/bin/bash
mkdir -p $GEN_TOPO_WORKDIR/cache || { echo Error creating directory 1>&2; exit 1; }
if [ $GEN_TOPO_HASH == 1 ]; then
  cd $GEN_TOPO_WORKDIR || { echo Cannot enter work dir 1>&2; exit 1; }
  if [ ! -d O2DPG ]; then git clone https://github.com/AliceO2Group/O2DPG.git 1>&2 || { echo O2DPG checkout failed 1>&2; exit 1; }; fi
  if [ "0$GEN_TOPO_ONTHEFLY" == "01" ]; then
    export GEN_TOPO_CACHEABLE=1
  fi
  CACHE_HASH=`echo $GEN_TOPO_PARTITION $GEN_TOPO_SOURCE $GEN_TOPO_LIBRARY_FILE $GEN_TOPO_WORKFLOW_NAME $OVERRIDE_PDPSUITE_VERSION $SET_QCJSON_VERSION $DD_DISK_FRACTION $SHM_MANAGER_SHMID $WORKFLOW_DETECTORS $WORKFLOW_DETECTORS_QC $WORKFLOW_DETECTORS_CALIB $WORKFLOW_PARAMETERS $RECO_NUM_NODES_OVERRIDE $DDMODE $DDWORKFLOW $INRAWCHANNAME $FILEWORKDIR $CTF_DIR | md5sum | awk '{print $1}'`
  if [ "0$GEN_TOPO_WIPE_CACHE" == "01" ]; then
    rm -f cache/$CACHE_HASH
  fi
  if [ -f cache/$CACHE_HASH ]; then
    echo Reusing cached XML topology 1>&2
    touch cache/$CACHE_HASH
    cat cache/$CACHE_HASH
    exit 0
  fi
  cd O2DPG
  git checkout $GEN_TOPO_SOURCE &> /dev/null
  if [ $? != 0 ]; then
    git fetch origin 1>&2 || { echo Repository update failed 1>&2; exit 1; }
    git checkout $GEN_TOPO_SOURCE &> /dev/null || { echo commit does not exist 1>&2; exit 1; }
  fi
  if ! git describe --exact-match --tags HEAD &> /dev/null; then
    unset GEN_TOPO_CACHEABLE
  fi
  cd DATA
else
  cd $GEN_TOPO_SOURCE || { echo Directory missing 1>&2; exit 1; }
fi
export EPNSYNCMODE=1
export O2DPG_ROOT=`realpath \`pwd\`/../`
echo Running topology generation to temporary file $GEN_TOPO_WORKDIR/output.xml 1>&2
./tools/parse "$GEN_TOPO_LIBRARY_FILE" $GEN_TOPO_WORKFLOW_NAME $GEN_TOPO_WORKDIR/output.xml 1>&2 || { echo Error during workflow description parsing 1>&2; exit 1; }
if [ "0$GEN_TOPO_CACHEABLE" == "01" ]; then
  cd $GEN_TOPO_WORKDIR
  if [ `ls cache/ | wc -l` -ge 1000 ]; then
    ls -t cache/* | tail -n +1000 | xargs rm
  fi
  cp $GEN_TOPO_WORKDIR/output.xml cache/$CACHE_HASH
fi
cat $GEN_TOPO_WORKDIR/output.xml
echo Removing temporary output file $GEN_TOPO_WORKDIR/output.xml 1>&2
rm $GEN_TOPO_WORKDIR/output.xml
