# README

## Configuration of anchored MC production [DEMONSTRATOR]

The procedure is the following
```bash
# create a configuration for anchored MC workflow creation
# 1. accessing CCDB and get SOR and EOR for each run number
# 2. sample time stamps
$O2DPG_ROOT/MC/bin/o2dpg_sim_configure_anchored.py --run-numbers 129747 129744 --tag myTag [--samples 10] [--lumi-fraction 0.2] [-o config_anchored_mc.json]

# create workflows
# workflows will be dumped into a dedicated directory anchored_mc_<tag>
$O2DPG_ROOT/MC/bin/o2dpg_sim_workflow.py --anchored-config config_anchored_mc.json
```
After that, the single workflows written to `anchored_mc_<tag>/workflow_<tag>_<run_number>_<timestamp>.json` can be run.

## Workflow editing

The tool `$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py` provides some management of workflow files.

### General help

```bash
$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py [sub-command] --help
```
shows the available sub-commands and for each sub-command, a dedicated help message is provided.


### Create an empty workflow file

```bash
$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py create my_workflow
```
creates a new file `my_workflow.json` (the extension `.json` can be left out in the command and would be added automatically)

### Add task skeletons to a workflow file

New task skeletons can be added with its name by
```bash
$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py create my_workflow --add-task task1 [task2 [...]]
```

Regarding the command line to be executet, the required `${O2_ROOT}/share/scripts/jobutils.sh; taskwrapper` is prepended automatically.

### Update number of workers (in case of using relative number of workers)

The number of workers can be updated by (in this case specifying 9 workers)
```bash
$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py nworkers my_workflow 9
```

### Merge 2 workflow files

Merging of 2 workflow files is done via
```bash
$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py merge workflow1 workflow2 [-o workflow_merged]
```

If no output filename is provided, the default will be `workflow_merged`. Of course, after that the number of workers can be updated based on the merged one.

### Inspect workflow

This doesn't do much at the moment, but can be foreseen to be equipped with more functionality
```bash
$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py inspect my_workflow --summary
```
yields a very brief summary of `my_workflow`, whereas
```bash
$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py inspect my_workflow --check
```
conducts a quick sanity check, for instance checking whether any task names are duplicated or any dependencies are missing.

### Modifying a single task
A task can be updated via the command line and the is no need to do so inside the `JSON` file. To change the dependent tasks, for instance, do
```bash
$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py modify --needs dep_task_1 [dep_task_2 [...]]
```
As usual, type
```bash
$O2DPG_ROOT/MC/bin/o2dpg-workflow-tools.py modify --help
```
to see all options.
