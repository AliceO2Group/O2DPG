#!/bin/bash
mkdir -p $GEN_TOPO_WORKDIR/cache
cd $GEN_TOPO_WORKDIR || (echo Cannot enter work dir && exit 1)
if [ ! -d O2DataProcessing ]; then git clone https://github.com/AliceO2Group/O2DataProcessing.git || (echo O2DataProcessing checkout failed && exit 1); fi
if [ $GEN_TOPO_HASH == 1 ]; then
  CACHE_HASH=`echo $GEN_TOPO_PARTITION $GEN_TOPO_SOURCE $GEN_TOPO_LIBRARY_FILE $GEN_TOPO_WORKFLOW_NAME $WORKFLOW_DETECTORS $WORKFLOW_DETECTORS_QC $WORKFLOW_DETECTORS_CALIB $WORKFLOW_PARAMETERS $RECO_NUM_NODES_OVERRIDE $DDMODE $DDWORKFLOW $INRAWCHANNAME $FILEWORKDIR $CTF_DIR | md5sum | awk '{print $1}'`
  if [ -f cache/$CACHE_HASH ]; then
    echo Reusing cached XML topology
    touch cache/$CACHE_HASH
    cp cache/$CACHE_HASH $GEN_TOPO_XML_OUTPUT
    exit 0
  fi
  cd O2DataProcessing
  git checkout $GEN_TOPO_SOURCE &> /dev/null
  if [ $? != 0 ]; then
    git fetch origin || (echo Repository update failed && exit 1)
    git checkout $GEN_TOPO_SOURCE &> /dev/null || (echo commit does not exist && exit 1)
  fi
else
  cd $GEN_TOPO_SOURCE || (echo Directory missing && exit 1)
fi
export EPNMODE=1
export O2DATAPROCESSING_ROOT=`pwd`
./tools/parse "$GEN_TOPO_LIBRARY_FILE" $GEN_TOPO_WORKFLOW_NAME $GEN_TOPO_XML_OUTPUT || (echo Error during workflow description parsing && exit 1)
if [ $GEN_TOPO_HASH == 1 ]; then
  cd $GEN_TOPO_WORKDIR
  if [ `ls cache/ | wc -l` -ge 100 ]; then
    ls -t cache/* | tail -n +100 | xargs rm
  fi
  cp $GEN_TOPO_XML_OUTPUT cache/$CACHE_HASH
fi
