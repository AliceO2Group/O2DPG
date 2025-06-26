#!/usr/bin/env bash

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1



RNDSEED=${RNDSEED:-0}
NEVENTS=${NEVENTS:-2}
NWORKERS=${NWORKERS:-8}
NTIMEFRAMES=${NTIMEFRAMES:-2}
SIMENGINE=${SIMENGINE:-TGeant4}

# ----------- SETUP LOCAL CCDB CACHE --------------------------
export ALICEO2_CCDB_LOCALCACHE=$PWD/.ccdb

${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 5020  -col PbPb -gen pythia8 -tf ${NTIMEFRAMES}   \
             -ns ${NEVENTS} -e ${SIMENGINE}                   \
	     -trigger "external" -ini  ${O2DPG_ROOT}/MC/config/examples/ini/trigger_multiplicity_stableparticles_inFIT.ini \
	     -j ${NWORKERS} -interactionRate 50000     \
	     -run 300000                                \
	     -confKey "Diamond.width[2]=6" --include-qc --include-analysis


export FAIRMQ_IPC_PREFIX=./
# run workflow (highly-parallel)
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod  -jmax 1


