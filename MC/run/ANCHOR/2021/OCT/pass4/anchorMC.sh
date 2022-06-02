#!/bin/bash

#
# A example workflow MC->RECO->AOD for a simple pp min bias 
# production, targetting test beam conditions.
#
# In addition, we target to exercise the whole chain of anchoring
# mechanisms, including
# - transfer settings from DATA reconstruction pass scripts
# - anchor to the time of a specific data dating run, so that
#   correct CCDB are fetched
# - apply additional settings like vertex/beam spot etc., not yet coming
#   from elsewhere


# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ------ CREATE AN MC CONFIG STARTING FROM RECO SCRIPT --------
# - this part should not be done on the GRID, where we should rather
#   point to an existing config (O2DPG repo or local disc or whatever)

RUNNUMBER=${ALIEN_JDL_LPMRUNNUMBER:-505673}
INTERACTIONRATE=${INTERACTIONRATE:-2000}

# get the async script (we need to modify it)
# the script location can be configured with a JDL option
cp ${ALIEN_JDL_ASYNCRECOSCRIPT:-$O2DPG_ROOT/DATA/production/configurations/2021/OCT/apass4/async_pass.sh} async_pass.sh
cp $O2DPG_ROOT/DATA/production/configurations/2021/OCT/${ALIEN_JDL_LPMPASSNAME:-apass4}/setenv_extra.sh .
#settings that are MC-specific
sed -i 's/GPU_global.dEdxUseFullGainMap=1;GPU_global.dEdxDisableResidualGainMap=1/GPU_global.dEdxSplineTopologyCorrFile=splines_for_dedx_V1_MC_iter0_PP.root;GPU_global.dEdxDisableTopologyPol=1;GPU_global.dEdxDisableGainMap=1;GPU_global.dEdxDisableResidualGainMap=1;GPU_global.dEdxDisableResidualGain=1/' setenv_extra.sh
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

[[ ! -f commonInput.tgz ]] && alien.py cp /alice/cern.ch/user/a/alidaq/OCT/apass4/commonInput.tgz file:.
[[ ! -f runInput_${RUNNUMBER} ]] && alien.py cp /alice/cern.ch/user/a/alidaq/OCT/apass4/runInput_${RUNNUMBER}.tgz file:.
[[ ! -f TPC_calibdEdx.220301.tgz ]] && alien.py cp /alice/cern.ch/user/a/alidaq/OCT/apass4/TPC_calibdEdx.220301.tgz file:.
tar -xzf TPC_calibdEdx.220301.tgz
cp calibdEdx.pol/*.root .
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

# check if important input file is here
[ ! -f splines_for_dedx_V1_MC_iter0_PP.root ] && echo "TPC calib input file not found" && exit 1

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

baseargs="-tf ${NTIMEFRAMES} --split-id ${ALIEN_JDL_SPLITID:-0} --prod-split ${ALIEN_JDL_PRODSPLIT:-100} --run-number ${RUNNUMBER}"

# THIS NEEDS TO COME FROM OUTSIDE
remainingargs="-eCM 900 -col pp -gen pythia8 -proc cdiff -ns ${NSIGEVENTS}                                                                                                \
               -interactionRate ${INTERACTIONRATE}                                                                                                                        \
               -confKey \"Diamond.width[2]=6.0;Diamond.width[0]=0.01;Diamond.width[1]=0.01;Diamond.position[0]=0.0;Diamond.position[1]=-0.035;Diamond.position[2]=0.41\"  \
              --include-local-qc --include-analysis --mft-reco-full"

remainingargs="${remainingargs} -e ${SIMENGINE} -j ${NWORKERS}"
remainingargs="${remainingargs} -productionTag ${ALIEN_JDL_LPMPRODUCTIONTAG:-alibi_anchorTest_tmp}"
remainingargs="${remainingargs} --anchor-config config-json.json"

echo "baseargs: ${baseargs}"
echo "remainingargs: ${remainingargs}"
              
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow_anchored.py ${baseargs} -- ${remainingargs} &> timestampsampling.log
[ "$?" != "0" ] && echo "Problem during anchor timestamp sampling " && exit 1

TIMESTAMP=`grep "Determined timestamp to be" timestampsampling.log | awk '//{print $6}'`
echo "TIMESTAMP IS ${TIMESTAMP}"

# -- PREFETCH CCDB OBJECTS TO DISC      --
# (make sure the right objects at the right timestamp are fetched
#  until https://alice.its.cern.ch/jira/browse/O2-2852 is fixed)
export ALICEO2_CCDB_LOCALCACHE=$PWD/.ccdb
[ ! -d .ccdb ] && mkdir .ccdb

CCDBOBJECTS="/CTP/Calib/OrbitReset /GLO/Config/GRPMagField/ /GLO/Config/GRPLHCIF /ITS/Align /ITS/Calib/DeadMap /ITS/Calib/NoiseMap /ITS/Calib/ClusterDictionary /TPC/Align /TPC/Calib/PadGainFull /TPC/Calib/TopologyGain /TPC/Calib/TimeGain /TPC/Calib/PadGainResidual /TPC/Config/FEEPad /TRD/Align /TOF/Align /TOF/Calib/Diagnostic /TOF/Calib/LHCphase /TOF/Calib/FEELIGHT /TOF/Calib/ChannelCalib /PHS/Align /CPV/Align /EMC/Align /HMP/Align /MFT/Align /MFT/Calib/DeadMap /MFT/Calib/NoiseMap /MFT/Calib/ClusterDictionary /MCH/Align /MID/Align /FT0/Align /FT0/Calibration/ChannelTimeOffset /FV0/Align /FV0/Calibration/ChannelTimeOffset /FDD/Align"

${O2_ROOT}/bin/o2-ccdb-downloadccdbfile --host http://alice-ccdb.cern.ch/ -p ${CCDBOBJECTS} -d .ccdb --timestamp ${TIMESTAMP}
if [ ! "$?" == "0" ]; then
  echo "Problem during CCDB prefetching of ${CCDBOBJECTS}. Exiting."
  exit 1
fi

# -- DO AD-HOC ADJUSTMENTS TO WORKFLOWS (UNTIL THIS CAN BE DONE NATIVELY) --
sed -i 's/--onlyDet TPC/--onlyDet TPC --TPCuseCCDB/' workflow.json # enables CCDB during TPC digitization

# -- RUN THE MC WORKLOAD TO PRODUCE AOD --

export FAIRMQ_IPC_PREFIX=./

${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt ${ALIEN_JDL_O2DPGWORKFLOWTARGET:-aod} --cpu-limit ${ALIEN_JDL_CPULIMIT:-8}
MCRC=$?  # <--- we'll report back this code

if [ "${MCRC}" = "0" ]; then
  # publish the AODs to ALIEN
  [ ${ALIBI_EXECUTOR_FRAMEWORK} ] && copy_ALIEN "*AO2D*"

  # do QC tasks
  if [[ "${remainingargs}" == *"--include-local-qc"* ]]; then
    echo "Doing QC"
    ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --target-labels QC --cpu-limit ${ALIEN_JDL_CPULIMIT:-8}
    RC=$?
  fi

  # could take this away finally
  if [ ${ALIBI_EXECUTOR_FRAMEWORK} ]; then 
    err_logs=$(get_error_logs $(pwd) --include-grep "QC")
    [ ! "${RC}" -eq 0 ] && send_mattermost "--text QC stage **failed** :x: --files ${err_logs}" || send_mattermost "--text QC **passed** :white_check_mark:"
    unset ALICEO2_CCDB_LOCALCACHE
    # perform some analysis testing
    DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
    . ${DIR}/analysis_testing.sh
  fi

  # do analysis tasks
  if [[ "${remainingargs}" == *"--include-analysis"* ]]; then
    echo "Doing Analysis"
    ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --target-labels Analysis --cpu-limit ${ALIEN_JDL_CPULIMIT:-8}
    RC=$?
  fi

fi

# could take this way finally
if [ ${ALIBI_EXECUTOR_FRAMEWORK} ]; then
  # publish the original data to ALIEN
  find ./ -name "localhos*_*" -delete
  tar -czf mcarchive.tar.gz workflow.json tf* QC pipeline*
  copy_ALIEN mcarchive.tar.gz
fi

#
# full logs tar-ed for output, regardless the error code or validation - to catch also QC logs...
#
if [[ -n "$ALIEN_PROC_ID" ]]; then
  find ./ \( -name "*.log*" -o -name "*mergerlog*" -o -name "*serverlog*" -o -name "*workerlog*" \) | tar -czvf debug_log_archive.tgz -T -
fi

unset FAIRMQ_IPC_PREFIX

return ${MCRC} 2>/dev/null || exit ${MCRC}
