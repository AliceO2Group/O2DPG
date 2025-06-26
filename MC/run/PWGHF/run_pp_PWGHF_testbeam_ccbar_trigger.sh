#!/bin/bash

#
# A example workflow MC->RECO->AOD for a simple pp min bias 
# production, targetting test beam conditions.

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- START ACTUAL JOB  ----------------------------- 

NWORKERS=${NWORKERS:-8}
MODULES="--skipModules ZDC"
SIMENGINE=${SIMENGINE:-TGeant4}
#NBKGEVENTS=${NBKGEVENTS:-1}

#ccbar trigger
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 900 -col pp -gen pythia8 -proc "inel" -tf 25 \
	                                            -ns 22 -e ${SIMENGINE}                  \
						    -j ${NWORKERS} -interactionRate 10000 \
						    -confKey "Diamond.width[2]=6."        \
						    -trigger "external" -ini "$O2DPG_ROOT/MC/config/PWGHF/ini/trigger_hf.ini"


# run workflow
# allow increased timeframe parallelism with --cpu-limit 32 
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod --cpu-limit 32



