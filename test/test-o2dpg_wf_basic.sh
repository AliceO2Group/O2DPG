#!/bin/bash

###################################################################
# Test creation of multliple different O2DPG simulation workflows #
###################################################################

SEED=${SEED:--seed 0}
NSIGEVENTS=${NSIGEVENTS:-110}
NBKGEVENTS=${NBKGEVENTS:-110}
NWORKERS=${NWORKERS:-8}
NTIMEFRAMES=${NTIMEFRAMES:-5}
SIMENGINE=${SIMENGINE:-TGeant4}
PYPROCESS=${PYPROCESS:-inel}

# Try to construct some workflows

${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 900 -gen external -j ${NWORKERS} -ns ${NSIGEVENTS} -tf ${NTIMEFRAMES} -e TGeant4 \
    -mod "--skipModules ZDC" \
    -confKey "GeneratorExternal.fileName=${O2DPG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV.C;GeneratorExternal.funcName=GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV();Diamond.width[2]=6"         \
    -genBkg pythia8 -procBkg cdiff -colBkg pp --embedding -nb ${NBKGEVENTS} \
    -interactionRate 10000                                                 \
    -confKeyBkg "Diamond.width[2]=6" --include-analysis                    \
    -productionTag "alibi_O2DPG_PWGDQ_ppJpsi_pilotbeam" -run 301000 -seed 624 -o O2DPG_PWGDQ_ppJpsi_pilotbeam_workflow.json
[ "$?" != "0" ] && exit 1


${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 5020 -col PbPb -gen pythia8 -proc "heavy_ion" -tf 2 \
                                                     -ns 10 -e ${SIMENGINE} -j ${NWORKERS}          \
                                                     --include-qc --include-analysis --with-ZDC     \
                                                     -run 310000 -seed 624 -o O2DPG_PbPb_ZDC_workflow.json
[ "$?" != "0" ] && exit 1

${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 14000  -col pp -gen pythia8 -proc cdiff -tf 5     \
                                                       -ns 2000 -e ${SIMENGINE}                   \
                                                       -j ${NWORKERS} -interactionRate 500000     \
                                                       -run 302000 -seed 624                     \
                                                       -confKey "Diamond.width[2]=6" --include-qc --include-analysis \
                                                       -productionTag "alibi_O2DPG_pp_minbias" -o O2DPG_pp_minbias_workflow.json
[ "$?" != "0" ] && exit 1

${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 5020 -col pp -gen pythia8 -proc ${PYPROCESS} \
                                           -colBkg PbPb -genBkg pythia8 -procBkg "heavy_ion" \
                                           -tf ${NTIMEFRAMES} -nb ${NBKGEVENTS}              \
                                           -ns ${NSIGEVENTS} -e ${SIMENGINE}                 \
                                           -j ${NWORKERS} --embedding -interactionRate 50000 \
                                           --include-analysis -run 310000 ${SEED} -o embedding_workflow.json
[ "$?" != "0" ] && exit 1

exit 0
