#!/bin/bash

# A common workflow MC->RECO->AOD for a simple pp min bias production, targetting test beam conditions.
# We should have at lease one argument, the name of the CFGINIFILE to be used.
# Example: ./run_DeTrHeInjected.sh ${O2DPG_ROOT}/MC/config/PWGLF/ini/GeneratorLFDeTrHe_pp.ini

# The following variables can be set from the outside:
# - NWORKERS: number of workers to use (default 8)
# - MODULES: modules to be run (default "--skipModules ZDC")
# - SIMENGINE: simulation engine (default TGeant4)
# - NSIGEVENTS: number of signal events (default 1)
# - NBKGEVENTS: number of background events (default 1)
# - NTIMEFRAMES: number of time frames (default 1)
# - INTRATE: interaction rate (default 50000)
# - SYSTEM: collision system (default pp)
# - ENERGY: collision energy (default 900)
# - CFGINIFILE: path to the ini file (example ${O2DPG_ROOT}/MC/config/PWGLF/ini/GeneratorLFDeTrHe_pp.ini)
# - SPLITID: split ID (default "")
# - O2_SIM_WORKFLOW: path to the workflow script (default ${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py)
# - O2_SIM_WORKFLOW_RUNNER: path to the workflow runner script (default ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py)

# If we don't have at least one argument, we print the usage
# and exit
if [ $# -lt 1 ]; then
    echo "Usage: $0 <CFGINIFILE>"
    exit 1
fi
echo "CFGINIFILE = $1"

# ----------- LOAD O2DPG --------------------------------------
# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# ----------- CONFIGURE ---------------------------------------
export IGNORE_VALIDITYCHECK_OF_CCDB_LOCALCACHE=1
#export ALICEO2_CCDB_LOCALCACHE=.ccdb


# ----------- START ACTUAL JOB  -------------------------------

NWORKERS=${NWORKERS:-8}
MODULES=${MODULES:---skipModules ZDC}
SIMENGINE=${SIMENGINE:-TGeant4}
NSIGEVENTS=${NSIGEVENTS:-1}
NBKGEVENTS=${NBKGEVENTS:-1}
NTIMEFRAMES=${NTIMEFRAMES:-1}
INTRATE=${INTRATE:-50000}
SYSTEM=${SYSTEM:-pp}
ENERGY=${ENERGY:-900}
CFGINIFILE=$1
[[ ${SPLITID} != "" ]] && SEED="-seed ${SPLITID}" || SEED=""

echo "NWORKERS = $NWORKERS"
echo "MODULES = $MODULES"
echo "SIMENGINE = $SIMENGINE"
echo "NSIGEVENTS = $NSIGEVENTS"
echo "NBKGEVENTS = $NBKGEVENTS"
echo "NTIMEFRAMES = $NTIMEFRAMES"
echo "INTRATE = $INTRATE"
echo "SYSTEM = $SYSTEM"
echo "ENERGY = $ENERGY"
echo "CFGINIFILE = $CFGINIFILE"

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM ${ENERGY} -col ${SYSTEM} -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -interactionRate ${INTRATE} -confKey "Diamond.width[2]=6." -e ${SIMENGINE} ${SEED} -mod "${MODULES}" \
        -ini ${CFGINIFILE}

# run workflow
O2_SIM_WORKFLOW_RUNNER=${O2_SIM_WORKFLOW_RUNNER:-"${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py"}
$O2_SIM_WORKFLOW_RUNNER -f workflow.json -tt aod --cpu-limit $NWORKERS