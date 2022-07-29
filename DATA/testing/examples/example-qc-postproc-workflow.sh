#!/bin/bash

[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1
[ ! "${QUALITYCONTROL_ROOT}" ] && echo "Error: This needs QUALITYCONTROL loaded" && exit 1


# create workflow
${O2DPG_ROOT}/DATA/production/o2dpg_qc_postproc_workflow.py --passName apass1 --qcdbUrl ccdb-test.cern.ch:8080 -o qc_postproc_workflow.json

# run workflow
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f qc_postproc_workflow.json --cpu-limit 4

