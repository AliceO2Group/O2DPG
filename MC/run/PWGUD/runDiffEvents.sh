#!/usr/bin/env bash

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# load utility functions
. ${O2_ROOT}/share/scripts/jobutils.sh 

ECM=${ECM:-13600}
RNDSEED=${RNDSEED:-0}
NSIGPTF=${NSIGPTF:-100}
NWORKERS=${NWORKERS:-4}
NTIMEFRAMES=${NTIMEFRAMES:-1}
SIGINTRATE=${SIGINTRATE:-50000}

# the hepmc3 file with the signal events
FHEPMC=${FHEPMC:-"diffEvents.hepmc3"}
FHEPMC=${PWD}/${FHEPMC}
if [ ! -f ${FHEPMC} ]; then
  echo "Error: Data file ${FHEPMC} is missing" && exit 1
fi

# vertex settings
DVX=0.01
DVY=0.01
DVZ=6.00


# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py \
  -col pp \
  -eCM ${ECM} \
  -gen hepmc \
  -j ${NWORKERS} \
  -ns ${NSIGPTF} \
  -tf ${NTIMEFRAMES} \
  -e TGeant4 \
  -interactionRate ${SIGINTRATE} \
  -confKey "HepMC.fileName="${FHEPMC}";HepMC.version=3;Diamond.width[0]="${DVX}";Diamond.width[1]="${DVY}";Diamond.width[2]="${DVZ}""
  
# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod
