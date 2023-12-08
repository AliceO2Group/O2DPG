#!/bin/bash

#
# procedure setting up and executing an anchored MC 
#


# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ------ CREATE AN MC CONFIG STARTING FROM RECO SCRIPT --------
# - this part should not be done on the GRID, where we should rather
#   point to an existing config (O2DPG repo or local disc or whatever)
export ALIEN_JDL_LPMANCHORYEAR=${ALIEN_JDL_LPMANCHORYEAR:-2022}
RUNNUMBER=${ALIEN_JDL_LPMRUNNUMBER:-517616}
INTERACTIONRATE=${INTERACTIONRATE:-2000}

# get the async script (we need to modify it)
# the script location can be configured with a JDL option
#cp ${ALIEN_JDL_ASYNCRECOSCRIPT:-$O2DPG_ROOT/DATA/production/configurations/2021/OCT/apass4/async_pass.sh} async_pass.sh
alien.py cp /alice/cern.ch/user/a/alidaq/LHC22c/apass1/async_pass.sh file:.

cp $O2DPG_ROOT/DATA/production/configurations/2022/MayJunePilotBeam/apass1/setenv_extra.sh .

#settings that are MC-specific
sed -i 's/GPU_global.dEdxUseFullGainMap=1;GPU_global.dEdxDisableResidualGainMap=1/GPU_global.dEdxSplineTopologyCorrFile=splines_for_dedx_V1_MC_iter0_PP.root;GPU_global.dEdxDisableTopologyPol=1;GPU_global.dEdxDisableGainMap=1;GPU_global.dEdxDisableResidualGainMap=1;GPU_global.dEdxDisableResidualGain=1/' setenv_extra.sh
### ???

chmod +x async_pass.sh

# take out line running the workflow (if we don't have data input)
[ ${CTF_TEST_FILE} ] || sed -i '/WORKFLOWMODE=run/d' async_pass.sh

# remove comments in order to set ALIEN_JDL stuff
# (if not set already)
if [ ! ${ALIEN_JDL_LPMRUNNUMBER} ]; then
  sed -i 's/# export ALIEN/export ALIEN/' async_pass.sh
fi
# fix typo
sed -i 's/JDL_ANCHORYEAR/JDL_LPMANCHORYEAR/' async_pass.sh

# set number of timeframes to xx if necessary
sed -i 's/NTIMEFRAMES=-1/NTIMEFRAMES=1/' async_pass.sh

[[ ! -f commonInput.tgz ]] && alien.py cp /alice/cern.ch/user/a/alidaq/LHC22c/apass1/commonInput.tgz file:.
tar -xzf commonInput.tgz

# hack to have o2sim_geometry.root file present if not part of download but -aligned was
if [[ -f o2sim_geometry-aligned.root && ! -f o2sim_geometry.root ]]; then
   ln -s o2sim_geometry-aligned.root o2sim_geometry.root
fi

# create workflow ---> creates the file that can be parsed
export IGNORE_EXISTING_SHMFILES=1
touch list.list
ALIEN_JDL_LPMPRODUCTIONTAG_KEEP=$ALIEN_JDL_LPMPRODUCTIONTAG
echo "Substituting ALIEN_JDL_LPMPRODUCTIONTAG=$ALIEN_JDL_LPMPRODUCTIONTAG with ALIEN_JDL_LPMANCHORPRODUCTION=$ALIEN_JDL_LPMANCHORPRODUCTION for simulating reco pass..."
ALIEN_JDL_LPMPRODUCTIONTAG=$ALIEN_JDL_LPMANCHORPRODUCTION
./async_pass.sh ${CTF_TEST_FILE:-""} 2&> async_pass_log.log
RECO_RC=$?
echo "RECO finished with ${RECO_RC}"
if [ "${NO_MC}" ]; then
  return ${RECO_RC} 2>/dev/null || exit ${RECO_RC} # optionally quit here and don't do MC (useful for testing)
fi

ALIEN_JDL_LPMPRODUCTIONTAG=$ALIEN_JDL_LPMPRODUCTIONTAG_KEEP
echo "Setting back ALIEN_JDL_LPMPRODUCTIONTAG to $ALIEN_JDL_LPMPRODUCTIONTAG"

# now create the local MC config file --> config-config.json
${O2DPG_ROOT}/UTILS/parse-async-WorkflowConfig.py

# check if config reasonably created
if [[ `grep "o2-ctf-reader-workflow-options" config-json.json 2> /dev/null | wc -l` == "0" ]]; then
  echo "Problem in anchor config creation. Stopping."
  exit 1
fi

# -- CREATE THE MC JOB DESCRIPTION ANCHORED TO RUN --

NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}
SIMENGINE=${ALIEN_JDL_SIMENGINE:-${SIMENGINE}}
NTIMEFRAMES=${NTIMEFRAMES:-50}
NSIGEVENTS=${NSIGEVENTS:-22}

# create workflow
# THIS NEEDS TO COME FROM OUTSIDE
# echo "$" | awk -F' -- ' '{print $1, $3}'

baseargs="-tf ${NTIMEFRAMES} --split-id ${ALIEN_JDL_SPLITID:-1} --prod-split ${ALIEN_JDL_PRODSPLIT:-100} --run-number ${RUNNUMBER} -eCM 900 -col pp"

# THIS NEEDS TO COME FROM OUTSIDE
remainingargs="-gen pythia8 -proc cdiff -ns ${NSIGEVENTS}                                                                                                                 \
               -interactionRate ${INTERACTIONRATE}                                                                                                                        \
               -confKey \"Diamond.width[2]=6.0;Diamond.width[0]=0.01;Diamond.width[1]=0.01;Diamond.position[0]=0.0;Diamond.position[1]=-0.035;Diamond.position[2]=0.41;MFTBase.buildAlignment=true\"  \
              --include-local-qc --include-analysis"

remainingargs="${remainingargs} -e ${SIMENGINE} -j ${NWORKERS}"
remainingargs="${remainingargs} -productionTag ${ALIEN_JDL_LPMPRODUCTIONTAG:-alibi_anchorTest_tmp}"
remainingargs="${remainingargs} --anchor-config config-json.json"

echo "baseargs: ${baseargs}"
echo "remainingargs: ${remainingargs}"
              
# query CCDB has changed, w/o "_"
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow_anchored.py ${baseargs} -- ${remainingargs} &> timestampsampling_${RUNNUMBER}.log
[ "$?" != "0" ] && echo "Problem during anchor timestamp sampling " && exit 1

TIMESTAMP=`grep "Determined timestamp to be" timestampsampling_${RUNNUMBER}.log | awk '//{print $6}'`
echo "TIMESTAMP IS ${TIMESTAMP}"

# -- PREFETCH CCDB OBJECTS TO DISC      --
# (make sure the right objects at the right timestamp are fetched
#  until https://alice.its.cern.ch/jira/browse/O2-2852 is fixed)
export ALICEO2_CCDB_LOCALCACHE=$PWD/.ccdb
[ ! -d .ccdb ] && mkdir .ccdb

CCDBOBJECTS="/CTP/Calib/OrbitReset /GLO/Config/GRPMagField/ /GLO/Config/GRPLHCIF /ITS/Calib/DeadMap /ITS/Calib/NoiseMap /ITS/Calib/ClusterDictionary /TPC/Calib/PadGainFull /TPC/Calib/TopologyGain /TPC/Calib/TimeGain /TPC/Calib/PadGainResidual /TPC/Config/FEEPad /TOF/Calib/Diagnostic /TOF/Calib/LHCphase /TOF/Calib/FEELIGHT /TOF/Calib/ChannelCalib /MFT/Calib/DeadMap /MFT/Calib/NoiseMap /MFT/Calib/ClusterDictionary /MFT/Calib/Align /FT0/Calibration/ChannelTimeOffset /FV0/Calibration/ChannelTimeOffset /GLO/GRP/BunchFilling"

${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch/ -p ${CCDBOBJECTS} -d .ccdb --timestamp ${TIMESTAMP}
if [ ! "$?" == "0" ]; then
  echo "Problem during CCDB prefetching of ${CCDBOBJECTS}. Exiting."
  exit 1
fi

# -- Create aligned geometry using ITS ideal alignment to avoid overlaps in geant
CCDBOBJECTS_IDEAL_MC="ITS/Calib/Align"
TIMESTAMP_IDEAL_MC=1
${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch/ -p ${CCDBOBJECTS_IDEAL_MC} -d .ccdb --timestamp ${TIMESTAMP_IDEAL_MC}
if [ ! "$?" == "0" ]; then
  echo "Problem during CCDB prefetching of ${CCDBOBJECTS_IDEAL_MC}. Exiting."
  exit 1
fi

${O2_ROOT}/bin/o2-create-aligned-geometry-workflow --configKeyValues "HBFUtils.startTime=TIMESTAM" --condition-remap=file://${ALICEO2_CCDB_LOCALCACHE}=ITS/Calib/Align,MFT/Calib/Align -b 
mkdir -p $ALICEO2_CCDB_LOCALCACHE/GLO/Config/GeometryAligned
ln -s -f $PWD/o2sim_geometry-aligned.root $ALICEO2_CCDB_LOCALCACHE/GLO/Config/GeometryAligned/snapshot.root

# -- RUN THE MC WORKLOAD TO PRODUCE AOD --

export FAIRMQ_IPC_PREFIX=./

echo "Ready to start main workflow"

${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt ${ALIEN_JDL_O2DPGWORKFLOWTARGET:-aod} --cpu-limit ${ALIEN_JDL_CPULIMIT:-8}
MCRC=$?  # <--- we'll report back this code
exit 0

if [[ "${MCRC}" = "0" && "${remainingargs}" == *"--include-local-qc"* ]] ; then
  # do QC tasks
  echo "Doing QC"
  ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --target-labels QC --cpu-limit ${ALIEN_JDL_CPULIMIT:-8} -k
  RC=$?
fi

#
# full logs tar-ed for output, regardless the error code or validation - to catch also QC logs...
#
if [[ -n "$ALIEN_PROC_ID" ]]; then
  find ./ \( -name "*.log*" -o -name "*mergerlog*" -o -name "*serverlog*" -o -name "*workerlog*" \) | tar -czvf debug_log_archive.tgz -T -
fi

unset FAIRMQ_IPC_PREFIX

return ${MCRC} 2>/dev/null || exit ${MCRC}
