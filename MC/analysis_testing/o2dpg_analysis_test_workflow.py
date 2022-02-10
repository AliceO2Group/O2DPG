#!/usr/bin/env python3

#
# A script producing a consistent MC->RECO->AOD workflow 
# It aims to handle the different MC possible configurations 
# It just creates a workflow.json txt file, to execute the workflow one must execute right after
#   ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json 
#
# Execution examples:
#  - pp PYTHIA jets, 2 events, triggered on high pT decay photons on all barrel calorimeters acceptance, eCMS 13 TeV
#     ./o2dpg_sim_workflow.py -e TGeant3 -ns 2 -j 8 -tf 1 -mod "--skipModules ZDC" -col pp -eCM 13000 \
#                             -proc "jets" -ptHatBin 3 \
#                             -trigger "external" -ini "\$O2DPG_ROOT/MC/config/PWGGAJE/ini/trigger_decay_gamma_allcalo_TrigPt3_5.ini"
#
#  - pp PYTHIA ccbar events embedded into heavy-ion environment, 2 PYTHIA events into 1 bkg event, beams energy 2.510
#     ./o2dpg_sim_workflow.py -e TGeant3 -nb 1 -ns 2 -j 8 -tf 1 -mod "--skipModules ZDC"  \
#                             -col pp -eA 2.510 -proc "ccbar"  --embedding
# 

import sys
import importlib.util
import argparse
from os import environ, makedirs
from os.path import join, exists, abspath, expanduser

# make sure O2DPG + O2 is loaded
O2_ROOT=environ.get('O2_ROOT')
O2PHYSICS_ROOT=environ.get('O2PHYSICS_ROOT')
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None or O2_ROOT is None or O2PHYSICS_ROOT is None:
    print('ERROR: This needs O2, O2DPG and O2PHYICS loaded')
    sys.exit(1)

module_name = "o2dpg_workflow_utils"
spec = importlib.util.spec_from_file_location(module_name, join(O2DPG_ROOT, "MC", "bin", "o2dpg_workflow_utils.py"))
o2dpg_workflow_utils = importlib.util.module_from_spec(spec)
sys.modules[module_name] = o2dpg_workflow_utils
spec.loader.exec_module(o2dpg_workflow_utils)

from o2dpg_workflow_utils import createTask, dump_workflow


def create_ana_task(name, cmd, output_dir, input_aod, shmsegmentsize="--shm-segment-size 2000000000",
                    aodmemoryratelimit="--aod-memory-rate-limit 500000000",
                    readers="--readers 1", extraarguments="-b"):
    """Quick helper to create analysis task
    """
    input_aod = f" --aod-file {abspath(input_aod)}"
    task = createTask(name=f"Analysis_{name}", cwd=join(output_dir, name), lab=["ANALYSIS", name], cpu=1, mem='2000')
    task['cmd'] = f"{cmd} {shmsegmentsize} {aodmemoryratelimit} {readers} {input_aod} {extraarguments}"
    return task


def run(args):

    input_file = expanduser(args.input_file)
    output_dir = expanduser(args.analysis_dir)
    if not exists(output_dir):
        makedirs(output_dir)

    workflow = []

    # Efficiency
    workflow.append(create_ana_task("Efficiency", "o2-analysis-timestamp --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json | o2-analysis-trackextension --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json | o2-analysis-trackselection --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json | o2-analysis-event-selection --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json | o2-analysis-qa-efficiency --eff-mc 1 --eff-mc-pos 1 --eff-mc-neg 1 --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json ", output_dir, input_file))

    # Event and track QA
    workflow.append(create_ana_task("EventTrackQA", 'o2-analysis-timestamp --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json | o2-analysis-event-selection --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json | o2-analysis-trackextension --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json | o2-analysis-trackselection --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json | o2-analysis-qa-event-track --configuration json://${O2DPG_ROOT}/MC/config/QC/json/event-track-qa.json', output_dir, input_file))

    # MCHistograms (no complex workflow / piping required atm)
    workflow.append(create_ana_task("MCHistograms", 'o2-analysistutorial-mc-histograms', output_dir, input_file))

    # Valitation (no complex workflow / piping required atm)
    workflow.append(create_ana_task("Validation", 'o2-analysis-validation', output_dir, input_file))

    # PID TOF (no complex workflow / piping required atm), NOTE: produces no output
    workflow.append(create_ana_task("PIDTOF", 'o2-analysis-pid-tof', output_dir, input_file))

    # PID TPC (no complex workflow / piping required atm), NOTE: produces no output
    workflow.append(create_ana_task("PIDTPC", 'o2-analysis-pid-tpc', output_dir, input_file))

    # weak decay tutorial task (no complex workflow / piping required atm), NOTE: produces no output
    workflow.append(create_ana_task("WeakDecayTutorial", 'o2-analysistutorial-weak-decay-iteration', output_dir, input_file))

    dump_workflow(workflow, args.output)


def main():
    parser = argparse.ArgumentParser(description='Create analysi test workflow')
    parser.add_argument("-f", "--input-file", dest="input_file", default="./AO2D.root", help="full path to the AO2D input")
    parser.add_argument("-a", "--analysis-dir", dest="analysis_dir", default="./Analysis", help="the analysis output directory")
    parser.add_argument("-o", "--output", default="./workflow_analysis_test.json", help="the workflow output directory")
    parser.set_defaults(func=run)

    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
