#!/usr/bin/env bash

# make sure O2DPG + O2 is loaded
# alienv enter O2/latest-dev-o2 O2DPG/latest-master-o2 AEGIS/latest-o2 EVTGEN/latest-o2
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1



RNDSEED=${RNDSEED:-0}
NSIGEVENTS=${NSIGEVENTS:-1}
NBKGEVENTS=${NBKGEVENTS:-1}
NWORKERS=${NWORKERS:-8}
NTIMEFRAMES=${NTIMEFRAMES:-1}
NBOXMUONS=${NBOXMUONS:-2}

${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 13600 -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -e TGeant4 \
	-confKey "GeneratorExternal.fileName=${O2DPG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorBoxFwd.C;GeneratorExternal.funcName=fwdMuBoxGen()" -interactionRate 500000  \
	-genBkg pythia8 -procBkg inel -colBkg pp --embedding -nb ${NBKGEVENTS} --mft-assessment-full --fwdmatching-assessment-full --fwdmatching-save-trainingdata

# run workflow (MFT-related tasks)
NMUONS=$NBOXMUONS ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt "(mft.*)"
