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

# get the async script (we need to modify it)
# the script location can be configured with a JDL option
cp ${ALIEN_JDL_ASYNCRECOSCRIPT:-$O2DPG_ROOT/DATA/production/configurations/2021/OCT/apass4/async_pass.sh} async_pass.sh
cp $O2DPG_ROOT/DATA/production/configurations/2021/OCT/${ALIEN_JDL_LPMPASSNAME:-apass4}/setenv_extra.sh .
chmod +x async_pass.sh

# take out line running the workflow (we don't have data input)
sed -i '/WORKFLOWMODE=run/d' async_pass.sh

# remove comments in order to set ALIEN_JDL stuff
# (if not set already)
if [ ! ${ALIEN_JDL_LPMRUNNUMBER} ]; then
  sed -i 's/# export ALIEN/export ALIEN/' async_pass.sh
fi
# fix typo
sed -i 's/JDL_ANCHORYEAR/JDL_LPMANCHORYEAR/' async_pass.sh

# set number of timeframes to xx if necessary
# sed -i 's/NTIMEFRAMES=-1/NTIMEFRAMES=xx/' async_pass.sh

[[ ! -f commonInput.tgz ]] && alien.py cp /alice/cern.ch/user/a/alidaq/OCT/apass4/commonInput.tgz file:.
[[ ! -f runInput_${RUNNUMBER} ]] && alien.py cp /alice/cern.ch/user/a/alidaq/OCT/apass4/runInput_${RUNNUMBER}.tgz file:.
[[ ! -f TPC_calibdEdx.220301.tgz ]] && alien.py cp /alice/cern.ch/user/a/alidaq/OCT/apass4/TPC_calibdEdx.220301.tgz file:.

# create workflow ---> creates the file that can be parsed
export IGNORE_EXISTING_SHMFILES=1
touch list.list
./async_pass.sh

# now create the local MC config file --> config-config.json
${O2DPG_ROOT}/UTILS/parse-async-WorkflowConfig.py

# check if config reasonably created
if [[ `grep "o2-ctf-reader-workflow-options" config-json.json 2> /dev/null | wc` == "0" ]]; then
  echo "Problem in anchor config creation"
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

baseargs="-tf ${NTIMEFRAMES} --split-id ${ALIEN_JDL_SPLITID:-0} --prod-split ${ALIEN_JDL_PRODSPLIT:-100} --run-number ${RUNNUMBER}"

# THIS NEEDS TO COME FROM OUTSIDE
remainingargs="-eCM 900 -col pp -gen pythia8 -proc inel -ns ${NSIGEVENTS}                                                                                                 \
               -interactionRate 2000                                                                                                                                      \
               -confKey \"Diamond.width[2]=6.0;Diamond.width[0]=0.01;Diamond.width[1]=0.01;Diamond.position[0]=0.0;Diamond.position[1]=-0.035;Diamond.position[2]=0.41\"  \
              --include-qc --include-analysis"

remainingargs="${remainingargs} -e ${SIMENGINE} -j ${NWORKERS}"
remainingargs="${remainingargs} -productionTag ${ALIEN_JDL_LPMPRODUCTIONTAG:-alibi_anchorTest_tmp}"
remainingargs="${remainingargs} --anchor-config config-json.json"
              
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow_anchored.py ${baseargs} -- ${remainingargs}
# -- RUN THE MC WORKLOAD TO PRODUCE AOD --

export FAIRMQ_IPC_PREFIX=./
export ALICEO2_CCDB_LOCALCACHE=$PWD/.ccdb
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt ${ALIEN_JDL_O2DPGWORKFLOWTARGET:-aod} --cpu-limit ${ALIEN_JDL_CPULIMIT:-8}
MCRC=$?  # <--- we'll report back this code

if [ "${MCRC}" = "0" ]; then
  # publish the AODs to ALIEN
  [ ${ALIBI_EXECUTOR_FRAMEWORK} ] && copy_ALIEN "*AO2D*"

  # do QC tasks
  if [[ "${remainingargs}" == *"--include-qc"* ]]; then
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
fi

# could take this way finally
if [ ${ALIBI_EXECUTOR_FRAMEWORK} ]; then 
  # publish the original data to ALIEN
  find ./ -name "localhos*_*" -delete
  tar -czf mcarchive.tar.gz workflow.json tf* QC pipeline*
  copy_ALIEN mcarchive.tar.gz
fi

unset FAIRMQ_IPC_PREFIX

return ${MCRC} 2>/dev/null || exit ${MCRC}
