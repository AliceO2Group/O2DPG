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

# dynamically import required utilities
module_name = "o2dpg_workflow_utils"
spec = importlib.util.spec_from_file_location(module_name, join(O2DPG_ROOT, "MC", "bin", "o2dpg_workflow_utils.py"))
o2dpg_workflow_utils = importlib.util.module_from_spec(spec)
sys.modules[module_name] = o2dpg_workflow_utils
spec.loader.exec_module(o2dpg_workflow_utils)

from o2dpg_workflow_utils import createTask, dump_workflow

# The default analysis tasks that can be created by this script
ANALYSIS_DEFAULT = ("Efficiency", "EventTrackQA", "MCHistograms", "Validation", "PIDFull", "PWGMMMFT", "EventSelectionQA", "WeakDecayTutorial")
# The default DPL JSON configuration to use
CONFIGURATION_JSON_DEFAULT = "json://${O2DPG_ROOT}/MC/config/analysis_testing/json/analysis-testing.json"
# Default analysis label to be put in the workflow JSON per analysis
ANALYSIS_LABEL = "Analysis"
# Default tuple of lists for QC upload task
DEFAULT_ANALYSES_FOR_QC_UPLOAD = [("Efficiency", ("AnalysisResults.root",)),
                                  ("EventTrackQA", ("AnalysisResults.root",)),
                                  ("MCHistograms", ("AnalysisResults.root",)),
                                  ("Validation", ("AnalysisResults.root",)),
                                  ("PIDFull", ("AnalysisResults.root",)),
                                  ("PWGMMMFT", ("AnalysisResults.root",)),
                                  ("EventSelectionQA", ("AnalysisResults.root",))]

def full_ana_name(raw_ana_name):
    """Make the standard name of the analysis how it should appear in the workflow"""
    return f"{ANALYSIS_LABEL}_{raw_ana_name}"

def create_ana_task(name, cmd, output_dir, input_aod, *, needs=None, shmsegmentsize="--shm-segment-size 2000000000",
                    aodmemoryratelimit="--aod-memory-rate-limit 500000000",
                    readers="--readers 1", extraarguments="-b"):
    """Quick helper to create analysis task

    This creates an analysis task from various arguments

    Args:
        name: str
            desired analysis name
        cmd: str
            command line to run
        input_aod: str
            path to input AOD
    Keyword args (optional):
        needs: tuple, list
            list of other tasks to be run before
        shmsegmentsize: str
            O2/DPL argument string for shared mem size
        aodmemoryratelimit: str
            O2/DPL argument string for AOD memory rate limit
        readers: O2/DPL argument string
            number of readers
        extraarguments: str
            O2/DPL argument string for any other desired arguments to be added to the executed cmd
    Return:
        dict: the task dictionary
    """
    # if another workflow want to use it from the outside, allow to inject dependencies before analyses can be run
    if needs is None:
        # set to empty list
        needs = []
    input_aod = f" --aod-file {abspath(input_aod)}"
    task = createTask(name=full_ana_name(name), cwd=join(output_dir, name), lab=[ANALYSIS_LABEL, name], cpu=1, mem='2000', needs=needs)
    task['cmd'] = f"{cmd} {shmsegmentsize} {aodmemoryratelimit} {readers} {input_aod} {extraarguments}"
    return task

def add_analysis_tasks(workflow, input_aod="./AO2D.root", output_dir="./Analysis", *, config_json=CONFIGURATION_JSON_DEFAULT, needs=None):
    """Add default analyses to user workflow

    Args:
        workflow: list
            list of tasks to add the analyses to
        input_aod: str
            path to AOD to be analysed
        output_dir: str
            top-level output directory under which the analysis is executed and potential results are saved
    Keyword arguments:
        config_json: str
            path to DPL JSON configuration
        needs: tuple, list
            list of other tasks to be run before
    """
    # Efficiency
    workflow.append(create_ana_task("Efficiency", f"o2-analysis-timestamp --configuration {config_json} | o2-analysis-trackextension --configuration {config_json} | o2-analysis-trackselection --configuration {config_json} | o2-analysis-event-selection --configuration {config_json} | o2-analysis-qa-efficiency --eff-mc 1 --eff-mc-pos 1 --eff-mc-neg 1 --configuration {config_json} ", output_dir, input_aod, needs=needs))

    # Event and track QA
    workflow.append(create_ana_task("EventTrackQA", f'o2-analysis-timestamp --configuration {config_json} | o2-analysis-event-selection --configuration {config_json} | o2-analysis-trackextension --configuration {config_json} | o2-analysis-trackselection --configuration {config_json} | o2-analysis-qa-event-track --configuration {config_json}', output_dir, input_aod, needs=needs))

    # MCHistograms (no complex workflow / piping required atm)
    workflow.append(create_ana_task("MCHistograms", 'o2-analysistutorial-mc-histograms', output_dir, input_aod, needs=needs))

    # Valitation (no complex workflow / piping required atm)
    workflow.append(create_ana_task("Validation", 'o2-analysis-validation', output_dir, input_aod, needs=needs))

    # Full PID
    workflow.append(create_ana_task("PIDFull", f'o2-analysis-dq-table-maker-mc --configuration {config_json} --severity error --shm-segment-size 12000000000 --aod-writer-json aodWriterTempConfig.json | o2-analysis-timestamp --configuration {config_json} | o2-analysis-event-selection --configuration {config_json} | o2-analysis-multiplicity-table --configuration {config_json} | o2-analysis-trackselection --configuration {config_json} | o2-analysis-trackextension --configuration {config_json} | o2-analysis-pid-tof --configuration {config_json} | o2-analysis-pid-tof-full --configuration {config_json} | o2-analysis-pid-tof-beta --configuration {config_json} | o2-analysis-pid-tpc-full --configuration {config_json}', output_dir, input_aod, needs=needs))

    # PWGMM MFT dNdeta
    workflow.append(create_ana_task("PWGMMMFT", f'o2-analysis-timestamp --configuration {config_json} | o2-analysis-trackselection --configuration {config_json} | o2-analysis-trackextension --configuration {config_json} | o2-analysis-event-selection --configuration {config_json} | o2-analysis-multiplicity-table --configuration {config_json} | o2-analysis-trackselection --configuration {config_json} | o2-analysis-mm-dndeta-mft --configuration {config_json}', output_dir, input_aod, needs=needs))

    # Event selection QA
    workflow.append(create_ana_task("EventSelectionQA", f'o2-analysis-timestamp --configuration {config_json} | o2-analysis-event-selection --configuration {config_json} | o2-analysis-event-selection-qa --configuration {config_json}', output_dir, input_aod, needs=needs))

    # weak decay tutorial task (no complex workflow / piping required atm), NOTE: produces no output
    workflow.append(create_ana_task("WeakDecayTutorial", 'o2-analysistutorial-weak-decay-iteration', output_dir, input_aod, needs=needs))

def add_analysis_qc_upload_tasks(workflow, prodcution_tag, run_number, *ana_tasks_expected_outputs):
    """add o2-qc-upload-root-objects to specified analysis tasks

    The analysis name has simply to be present in the workflow. Then adding these upload tasks works
    for any analysis because it does not have to have any knowledge about the analysis.

    Args:
        workflow: list
            current list of tasks
        ana_tasks_expected_outputs: list of tuples
            [(AnalysisName_1, (expected_output_1_1, expected_output_1_2, ...)), ..., (AnalysisName_N, (expected_output_N_1, expected_output_N_2, ...)) ]
    """
    if not ana_tasks_expected_outputs:
        ana_tasks_expected_outputs = DEFAULT_ANALYSES_FOR_QC_UPLOAD

    for ana_name_raw, expcted_outputs in ana_tasks_expected_outputs:
        ana_name = full_ana_name(ana_name_raw)
        for pot_ana in workflow:
            # search through workflow stages if we can find the requested analysis
            if pot_ana["name"] != ana_name:
                continue
            print(f"Adding QC upload task for analysis {ana_name_raw}")
            cwd = pot_ana["cwd"]
            qc_tag = f"Analysis{ana_name_raw}"
            needs = [ana_name]
            for eo in expcted_outputs:
                # this seems unnecessary but to ensure backwards compatible behaviour...
                rename_output = eo.strip(".root")
                rename_output = f"{rename_output}_{ana_name_raw}.root"
                # add upload task for each expected output file
                task = createTask(name=f"{ANALYSIS_LABEL}_finalize_{ana_name_raw}_{rename_output}", cwd=cwd, lab=[f"{ANALYSIS_LABEL}Upload", ana_name_raw], cpu=1, mem='2000', needs=needs)
                # This has now to be renamed for upload, as soon as that is done, the output is renamed back to its original, there is in general no point of renaming it on disk only because one specific tasks needs a renamed version of it
                rename_cmd = f"mv {eo} {rename_output}"
                rename_back_cmd = f"mv {rename_output} {eo}"
                task["cmd"] = f"{rename_cmd} && o2-qc-upload-root-objects --input-file ./{rename_output} --qcdb-url ccdb-test.cern.ch:8080 --task-name Analysis{ana_name_raw} --detector-code AOD --provenance qc_mc --pass-name passMC --period-name {prodcution_tag} --run-number {run_number} && {rename_back_cmd} "
                workflow.append(task)

def run(args):
    """digetsing what comes from the command line"""
    output_dir = expanduser(args.analysis_dir)
    if not exists(output_dir):
        makedirs(output_dir)

    workflow = []
    add_analysis_tasks(workflow, args.input_file, output_dir)
    if args.with_qc_upload:
        add_analysis_qc_upload_tasks(workflow, args.with_qc_upload[0], args.with_qc_upload[1])
    dump_workflow(workflow, args.output)

def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Create analysi test workflow')
    parser.add_argument("-f", "--input-file", dest="input_file", default="./AO2D.root", help="full path to the AO2D input")
    parser.add_argument("-a", "--analysis-dir", dest="analysis_dir", default="./Analysis", help="the analysis output directory")
    parser.add_argument("-o", "--output", default="./workflow_analysis_test.json", help="the workflow output directory")
    parser.add_argument("--with-qc-upload", dest="with_qc_upload", nargs=2, help="2. args: production tag and run number number")
    parser.set_defaults(func=run)

    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
