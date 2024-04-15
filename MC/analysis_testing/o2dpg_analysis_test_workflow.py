#!/usr/bin/env python3

#
# Analsysis task functionality
#
# --> to inject analysis tasks into an existing workflow <--
#
# From another script one can call (example taken from the o2dpg_sim_workflow)
# add_analysis_tasks(workflow["stages"], needs=[AOD_merge_task["name"]], is_mc=True))
#
# --> create a stand-alone workflow file with only analyses <--
#
# Help message:
# usage: o2dpg_analysis_test_workflow.py [-h] -f INPUT_FILE [-a ANALYSIS_DIR] [-o OUTPUT] [--is-mc] [--with-qc-upload] [--run-number RUN_NUMBER] [--pass-name PASS_NAME] [--period-name PERIOD_NAME] [--config CONFIG] [--only-analyses [ONLY_ANALYSES [ONLY_ANALYSES ...]]]
#
# Create analysi test workflow
#
# optional arguments:
#   -h, --help            show this help message and exit
#   -f INPUT_FILE, --input-file INPUT_FILE
#                         full path to the AO2D input
#   -a ANALYSIS_DIR, --analysis-dir ANALYSIS_DIR
#                         the analysis output and working directory
#   -o OUTPUT, --output OUTPUT
#                         the workflow file name
#   --is-mc               whether the input comes from MC (data assumed otherwise)
#   --with-qc-upload
#   --run-number RUN_NUMBER
#                         the run number
#   --pass-name PASS_NAME
#                         pass name
#   --period-name PERIOD_NAME
#                         prodcution tag
#   --config CONFIG       overwrite the default config JSON. Pass as </path/to/file>, will be automatically configured to json://
#   --only-analyses [ONLY_ANALYSES [ONLY_ANALYSES ...]]
#                         filter only on these analyses
#
# Only the -f/--input-file argument is required in both cases, MC or data
# If run --with-upload-qc is enabled, --period-name is required as well; in addition, when running on data, also --pass-name is required; for MC that is set to passMC
#
# Example for data
# 1. o2dpg_analysis_test_workflow.py -f </path/to/AO2D.root>
# This constructs all analysis workflows compatible with data
# 2. o2dpg_analysis_test_workflow.py -f </path/to/AO2D.root> --with-qc-upload --pass-name <some-pass-name> --period-name <some-period-name>
# This in addition adds tasks to upload data the analysis results to the CCDB
# 3. o2dpg_analysis_test_workflow.py -f </path/to/AO2D.root> --only-analyses MCHistograms EventTrackQA EventSelectionQA
# Filter only desired analyses. NOTE in this case: The analysis MCHistograms would automatically be taken out again by the script since it is not compatible with data
#
# Of course one if free to combine the above arguments
#
# If run on MC, just pass the flag --is-mc
#
# Now it is time to run the workflow
#
# ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
#
# If your analyses are embedded in a wider workflow (e.g. one created with o2dpg_sim_workflow) you can do
# 1. ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --target-labels Analysis
# to run everything which is labelled with "Analysis" (which would basically be all analyses)
# 2. ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt Analysis_<ana_name>
# to run only this specific analysis
#
import sys
import importlib.util
import argparse
from os import environ, makedirs
from os.path import join, exists, abspath, expanduser
import json

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)

# dynamically import required utilities
module_name = "o2dpg_workflow_utils"
spec = importlib.util.spec_from_file_location(module_name, join(O2DPG_ROOT, "MC", "bin", "o2dpg_workflow_utils.py"))
o2dpg_workflow_utils = importlib.util.module_from_spec(spec)
sys.modules[module_name] = o2dpg_workflow_utils
spec.loader.exec_module(o2dpg_workflow_utils)
from o2dpg_workflow_utils import createTask, dump_workflow, createGlobalInitTask

module_name = "o2dpg_analysis_test_utils"
spec = importlib.util.spec_from_file_location(module_name, join(O2DPG_ROOT, "MC", "analysis_testing", "o2dpg_analysis_test_utils.py"))
o2dpg_analysis_test_utils = importlib.util.module_from_spec(spec)
sys.modules[module_name] = o2dpg_analysis_test_utils
spec.loader.exec_module(o2dpg_analysis_test_utils)
from o2dpg_analysis_test_utils import *


def create_ana_task(name, cmd, output_dir, *, cpu=1, mem='2000', needs=None, extraarguments="-b", is_mc=False):
    """Quick helper to create analysis task

    This creates an analysis task from various arguments

    Args:
        name: str
            desired analysis name
        cmd: str
            command line to run
        output_dir: str
            analysis output and work directory
    Keyword args (optional):
        needs: tuple, list
            list of other tasks to be run before
        extraarguments: str
            O2/DPL argument string for any other desired arguments to be added to the executed cmd
    Return:
        dict: the task dictionary
    """
    # if another workflow want to use it from the outside, allow to inject dependencies before analyses can be run
    if needs is None:
        # set to empty list
        needs = []
    task = createTask(name=full_ana_name(name), cwd=join(output_dir, name), lab=[ANALYSIS_LABEL, name], cpu=cpu, mem=mem, needs=needs)
    if is_mc:
        task["labels"].append(ANALYSIS_LABEL_ON_MC)
    task['cmd'] = f"{cmd} {extraarguments}"
    return task


def load_analyses(analyses_only=None, include_disabled_analyses=False):
    analyses_config = join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", "analyses_config.json")
    with open (analyses_config, "r") as f:
        analyses_config = json.load(f)["analyses"]

    collect_analyses = []
    for ana in analyses_config:
        if analyses_only and ana["name"] not in analyses_only:
            continue
        if not ana.get("enabled", False) and not include_disabled_analyses:
            print(f"INFO: Analysis {ana['name']} not added since it is disabled")
            continue
        collect_analyses.append(ana)

    return collect_analyses


def get_additional_workflows(input_aod):
    additional_workflows = []

    # Treat case we have a text file as input. Use the first line in this case
    if input_aod.endswith(".txt"):
        if input_aod.startswith("@"):
            input_aod = input_aod[1:]
        with open(input_aod) as f:
            input_aod = f.readline().strip('\n')

    if input_aod.endswith(".root"):
        from ROOT import TFile
        if input_aod.startswith("alien://"):
            from ROOT import TGrid
            TGrid.Connect("alien")
        froot = TFile.Open(input_aod, "READ")
        # Link of tables and converters
        o2_analysis_converters = {"O2collision_001": "o2-analysis-collision-converter --doNotSwap",
                                  "O2zdc_001": "o2-analysis-zdc-converter",
                                  "O2bc_001": "o2-analysis-bc-converter",
                                  "O2v0_002": "o2-analysis-v0converter",
                                  "O2trackextra_001": "o2-analysis-tracks-extra-converter",
                                  "O2ft0corrected": "o2-analysis-ft0-corrected-table"}
        for i in froot.GetListOfKeys():
            if "DF_" not in i.GetName():
                continue
            df_dir = froot.Get(i.GetName())
            # print(i)
            for j in df_dir.GetListOfKeys():
                # print(j)
                if j.GetName() in o2_analysis_converters:
                    o2_analysis_converters.pop(j.GetName())
        for i in o2_analysis_converters:
            additional_workflows.append(o2_analysis_converters[i])
    return additional_workflows


def add_analysis_tasks(workflow, input_aod="./AO2D.root", output_dir="./Analysis", *, analyses_only=None, is_mc=True, collision_system=None, needs=None, autoset_converters=False, include_disabled_analyses=False, timeout=None, split_analyses=False):
    """Add default analyses to user workflow

    Args:
        workflow: list
            list of tasks to add the analyses to
        input_aod: str
            path to AOD to be analysed
        output_dir: str
            top-level output directory under which the analysis is executed and potential results are saved
    Keyword arguments:
        analyses_only: iter (optional)
            pass iterable of analysis names so only those will be considered
        is_mc: bool
            whether or not MC is expected, otherwise data is assumed
        needs: iter (optional)
            if specified, list of other tasks which need to be run before
    """

    if not input_aod.startswith("alien://"):
        input_aod = abspath(input_aod)
    if input_aod.endswith(".txt") and not input_aod.startswith("@"):
        input_aod = f"@{input_aod}"

    additional_workflows = []
    if autoset_converters:  # This is needed to run with the latest TAG of the O2Physics with the older data
        additional_workflows = get_additional_workflows(input_aod)

    data_or_mc = ANALYSIS_VALID_MC if is_mc else ANALYSIS_VALID_DATA
    collision_system = get_collision_system(collision_system)

    # list of lists, each sub-list corresponds to one analysis pipe to be executed
    analysis_pipes = []
    # collect the names corresponding to analysis pipes
    analysis_names = []
    # cpu and mem of each task
    analysis_cpu_mem = []
    # a list of all tasks to be put together
    merged_analysis_pipe = additional_workflows.copy()
    # cpu and mem of merged analyses
    merged_analysis_cpu_mem = [0, 0]
    # expected output of merged analysis
    merged_analysis_expected_output = []
    # analyses config to write
    analyses_config = []

    for ana in load_analyses(analyses_only, include_disabled_analyses=include_disabled_analyses):
        if is_mc and not ana.get("valid_mc", False):
            print(f"INFO: Analysis {ana['name']} not added since not valid in MC")
            continue
        if not is_mc and not ana.get("valid_data", False):
            print(f"INFO: Analysis {ana['name']} not added since not valid in data")
            continue
        if analyses_only and ana['name'] not in analyses_only:
            # filter on analyses if requested
            continue

        if split_analyses:
            # only the individual analyses, no merged
            analysis_pipes.append(ana['tasks'])
            analysis_names.append(ana['name'])
            analysis_cpu_mem.append((1, 2000))
            analyses_config.append(ana)
            continue

        merged_analysis_pipe.extend(ana['tasks'])
        # underestimate what a single analysis would take in the merged case.
        # Putting everything into one big pipe does not mean that the resources scale the same!
        merged_analysis_cpu_mem[0] += 0.5
        merged_analysis_cpu_mem[1] += 700
        merged_analysis_expected_output.extend(ana['expected_output'])

    if not split_analyses:
        # add the merged analysis
        analysis_pipes.append(merged_analysis_pipe)
        analysis_names.append(ANALYSIS_MERGED_ANALYSIS_NAME)
        # take at least the resources estimated for a single analysis
        analysis_cpu_mem.append((max(1, merged_analysis_cpu_mem[0]), max(2000, merged_analysis_cpu_mem[1])))
        merged_analysis_expected_output = list(set(merged_analysis_expected_output))
        # config of the merged analysis. Since it doesn't exist in the previous config, but we would like to have it defined, do it here
        analyses_config.append({'name': ANALYSIS_MERGED_ANALYSIS_NAME,
                                'valid_mc': is_mc,
                                'valid_data': not is_mc,
                                'enabled': True,
                                'tasks': merged_analysis_pipe,
                                'expected_output': merged_analysis_expected_output})


    # now we need to create the output directory where we want the final configurations to go
    output_dir_config = join(output_dir, 'config')
    if not exists(output_dir_config):
        makedirs(output_dir_config)

    # write the analysis config of this
    with open(join(output_dir, 'analyses_config.json'), 'w') as f:
        json.dump({'analyses': analyses_config}, f, indent=2)

    configuration = adjust_and_get_configuration_path(data_or_mc, collision_system, output_dir_config)

    for analysis_name, analysis_pipe, analysis_res in zip(analysis_names, analysis_pipes, analysis_cpu_mem):
        # remove duplicates if they are there for nay reason (especially in the merged case)
        analysis_pipe = list(set(analysis_pipe))
        analysis_pipe_assembled = []
        for executable_string in analysis_pipe:
            # the input executable might come already with some configurations, the very first token is the actual executable
            executable_string += f' --configuration json://{configuration}'
            analysis_pipe_assembled.append(executable_string)

        # put together, add AOD and timeout if requested
        analysis_pipe_assembled = ' | '.join(analysis_pipe_assembled)
        analysis_pipe_assembled += f' --aod-file {input_aod} --shm-segment-size 3000000000 --readers 1 --aod-memory-rate-limit 500000000'
        if timeout is not None:
            analysis_pipe_assembled += f' --time-limit {timeout}'

        workflow.append(create_ana_task(analysis_name, analysis_pipe_assembled, output_dir, cpu=analysis_res[0], mem=analysis_res[1], needs=needs, is_mc=is_mc))


def add_analysis_qc_upload_tasks(workflow, period_name, run_number, pass_name):
    """add o2-qc-upload-root-objects to specified analysis tasks

    The analysis name has simply to be present in the workflow. Then adding these upload tasks works
    for any analysis because it does not have to have any knowledge about the analysis.

    Args:
        workflow: list
            current list of tasks
        ana_tasks_expected_outputs: list of tuples
            [(AnalysisName_1, (expected_output_1_1, expected_output_1_2, ...)), ..., (AnalysisName_N, (expected_output_N_1, expected_output_N_2, ...)) ]
    """
    analyses_to_add_for = {}
    # collect analyses in current workflow
    for task in workflow:
        if ANALYSIS_LABEL in task["labels"]:
            analyses_to_add_for[task["name"]] = task

    for ana in load_analyses(include_disabled_analyses=True):
        if not ana["expected_output"]:
            continue
        ana_name_raw = ana["name"]
        ana_name = full_ana_name(ana_name_raw)
        if ana_name not in analyses_to_add_for:
            continue
        # search through workflow stages if we can find the requested analysis
        pot_ana = analyses_to_add_for[ana_name]
        cwd = pot_ana["cwd"]
        needs = [ana_name]
        provenance = "qc_mc" if ANALYSIS_LABEL_ON_MC in pot_ana["labels"] else "qc"
        for eo in ana["expected_output"]:
            # this seems unnecessary but to ensure backwards compatible behaviour...
            rename_output = eo.strip(".root")
            rename_output = f"{rename_output}_{ana_name_raw}.root"
            # add upload task for each expected output file
            task = createTask(name=f"{ANALYSIS_LABEL}_finalize_{ana_name_raw}_{rename_output}", cwd=cwd, lab=[f"{ANALYSIS_LABEL}Upload", ana_name_raw], cpu=1, mem='2000', needs=needs)
            # This has now to be renamed for upload, as soon as that is done, the output is renamed back to its original, there is in general no point of renaming it on disk only because one specific tasks needs a renamed version of it
            rename_cmd = f"mv {eo} {rename_output}"
            rename_back_cmd = f"mv {rename_output} {eo}"
            task["cmd"] = f"{rename_cmd} && o2-qc-upload-root-objects --input-file ./{rename_output} --qcdb-url ccdb-test.cern.ch:8080 --task-name Analysis{ana_name_raw} --detector-code AOD --provenance {provenance} --pass-name {pass_name} --period-name {period_name} --run-number {run_number} && {rename_back_cmd} "
            workflow.append(task)


def run(args):
    """digesting what comes from the command line"""
    if args.with_qc_upload and (not args.pass_name or not args.period_name):
        print("ERROR: QC upload was requested, however in that case a --pass-name and --period-name are required")
        return 1

    ### setup global environment variables which are valid for all tasks, set as first task
    global_env = {"ALICEO2_CCDB_CONDITION_NOT_AFTER": args.condition_not_after} if args.condition_not_after else None
    workflow = [createGlobalInitTask(global_env)]
    add_analysis_tasks(workflow, args.input_file, expanduser(args.analysis_dir), is_mc=args.is_mc, analyses_only=args.only_analyses, autoset_converters=args.autoset_converters, include_disabled_analyses=args.include_disabled, timeout=args.timeout, collision_system=args.collision_system, split_analyses=args.split_analyses)
    if args.with_qc_upload:
        add_analysis_qc_upload_tasks(workflow, args.period_name, args.run_number, args.pass_name)
    if not workflow:
        print("WARNING: Nothing was added")
    dump_workflow(workflow, args.output)
    print("Now you can run the workflow e.g.", "`${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py" + f" -f {args.output}`")
    return 0


def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Create analysis test workflow')
    parser.add_argument("-f", "--input-file", dest="input_file", default="./AO2D.root", help="full path to the AO2D input", required=True)
    parser.add_argument("-a", "--analysis-dir", dest="analysis_dir", default="./Analysis", help="the analysis output and working directory")
    parser.add_argument("-o", "--output", default="workflow_analysis_test.json", help="the workflow file name")
    parser.add_argument("--is-mc", dest="is_mc", action="store_true", help="whether the input comes from MC (data assumed otherwise)")
    parser.add_argument("--with-qc-upload", dest="with_qc_upload", action="store_true")
    parser.add_argument("--run-number", dest="run_number", type=int, default=300000, help="the run number")
    parser.add_argument("--pass-name", dest="pass_name", help="pass name")
    parser.add_argument("--period-name", dest="period_name", help="period name")
    parser.add_argument("--only-analyses", dest="only_analyses", nargs="*", help="filter only on these analyses")
    parser.add_argument("--include-disabled", dest="include_disabled", action="store_true", help="ignore if an analysis is disabled an run anyway")
    parser.add_argument("--autoset-converters", dest="autoset_converters", action="store_true", help="Compatibility mode to automatically set the converters for the analysis")
    parser.add_argument("--timeout", type=int, default=None, help="Timeout for analysis tasks in seconds.")
    parser.add_argument("--collision-system", dest="collision_system", help="Set the collision system. If not set, tried to be derived from ALIEN_JDL_LPMInterationType. Fallback to pp")
    parser.add_argument('--condition-not-after', dest="condition_not_after", type=int, help="only consider CCDB objects not created after this timestamp (for TimeMachine)", default=3385078236000)
    parser.add_argument('--split-analyses', dest='split_analyses', action='store_true', help='Split into single analyses pipes to be executed.')

    parser.set_defaults(func=run)
    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
