#!/bin/bash

#
# A example workflow MC->RECO->AOD for a simple pp min bias
# production
#

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1


# ----------- START ACTUAL JOB  -----------------------------

# decide whether or not to do QC (if simulation was successful, default is not doing it)
DOQC=${DOQC:+1}
[ "${DOQC}" != "" ] && [ ! "${QUALITYCONTROL_ROOT}" ] && echo "Error: This needs QualityControl loaded" && exit 1
# decide whether or not to do test analyses (if simulation was successful, default is not doing it)
DOANALYSIS=${DOANALYSIS:+1}
[ "${DOANALYSIS}" != "" ] && [ ! "${O2PHYSICS_ROOT}" ] && echo "Error: This needs O2Physics loaded" && exit 1

# select transport engine
SIMENGINE=${SIMENGINE:-TGeant4}
# number of timeframes to simulate
NTFS=${NTFS:-3}
# number of simulation workers per timeframe
NWORKERS=${NWORKERS:-8}
# number of events to be simulated per timeframe
NEVENTS=${NEVENTS:-20}
# interaction rate
INTRATE=${INTRATE:-500000}

# memory limit in MB
MEMLIMIT=${MEMLIMIT:+--mem-limit ${MEMLIMIT}}
# number of CPUs
CPULIMIT=${CPULIMIT:+--cpu-limit ${CPULIMIT}}

# create workflow
${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 13600  -seed 12345 -col pp -gen pythia8 -proc inel -tf ${NTFS} \
                                                       -ns ${NEVENTS} -e ${SIMENGINE} -run 301000  \
                                                       -j ${NWORKERS} -interactionRate ${INTRATE}  \
                                                       --include-qc --include-analysis

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt aod ${MEMLIMIT} ${CPULIMIT}
RETMC=${?}


RETQC=0
if [ "${DOQC}" != "" ] && [ "${RETMC}" = "0" ]; then
    # run QC if requested
    ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --target-labels QC ${MEMLIMIT} ${CPULIMIT}
    RETQC=${?}
fi

RETANA=0
if [ "${DOANALYSIS}" != "" ] && [ "${RETMC}" = "0" ]; then
    # run test analyses if requested
    ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --target-labels Analysis ${MEMLIMIT} ${CPULIMIT}
    RETANA=${?}
fi

RET=$((${RETMC} + ${RETQC} + ${RETANA}))

return ${RET} 2>/dev/null || exit ${RET}
