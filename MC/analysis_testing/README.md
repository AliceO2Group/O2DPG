# Analysis testing (aka AnalysisQC)

A collection of various analyses is managed here. This is meant for testing and it is **not** meant to replace production analysis procedures.

Technically, it is a small set of tools and configurations.

## Definition of analyses

Analyses are defined in a global [configuration](../config/analysis_testing/json/analyses_config.json). Here is an example
```json
{
    "name": "EventTrackQA",
    "enabled": true,
    "expected_output": ["AnalysisResults.root"],
    "valid_mc": true,
    "valid_data": true,
    "tasks": ["o2-analysis-timestamp",
              "o2-analysis-track-propagation",
              "o2-analysis-trackselection",
              "o2-analysis-event-selection",
              "o2-analysis-qa-event-track"]
}
```
Most importantly, the tasks from `O2Physics` need to be put in a list called `tasks`. This will be translated into the common command-line pipeline.
One can specify whether a given analysis can be run on data or mc by setting `valid_mc` or `valid_data`.
To include your analysis automatically, `enabled` needs to be set to `true`.
Of course, it is important to give an analysis a short but meaningful `name`.
In order to be able to do some potentially automatic post-processing, the expected output should be specified in the list `expected_output`.

### Analysis JSON configuration

If no specific configuration for your analysis is found, the [defaults](../config/analysis_testing/json/default/) will be used.
It is advised however, that you add specific configurations for your analysis to not interfere with other configurations which might differ from your needs.
They must be placed at in a sub-directory that matches **exactly** the name of your analysis, see [this](../config/analysis_testing/json/EventSelectionQA/) for an example.
Each of these directories have again a sub-directory that indicates the collision system. Inside, the files **must** have the name `analysis-testing-mc.json` or `analysis-testing-data.json`.
**Note** that, whenever no specific configuration can be found, the default is taken according to the collision system and whether it is data or MC.

## Testing an analysis on some AOD

First, define the workflow to run analyses. This is done with
```bash
${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_workflow.py -f <path-to-aod> [--is-mc] [-a <output-directory>] [--include-disabled]
```
To see all options, run
```bash
${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_workflow.py --help
```
By default, the tool assumes that you will be running on data. Hence, if you are interested in running on MC, you need to add the flag `--is-mc`.
The results of your analysis will be put into `<output-directory>/<analysis-name>`. The default will be `Analysis/<analysis-name>`.

**Note** that if an analysis is disabled (`"enabled": false`, see [above](#definition-of-analyses)), it will not be included. To include it anyway, add the flag `--include-disabled`.

By default, the workflow will be written to `workflow_analysis_test.json` which will be assumed in the following. This can be changed with `-o <workflow-filename>`.

No, you are ready to run your analysis with
```bash
${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow_analysis_test.json -tt Analysis_<analysis-name>
```
The option `-tt` specifies a specific target task that should be executed. If you do not specify it, all tasks in the workflow will be executed.

## AnalysisQC

What is called "AnalysisQC" is build upon the shoulders of this tool set. Basically, it boils down to the usage in MC GRID productions and data reconstruction.
If a certain analysis should be executed during that procedure, the only thing that needs to be done is to add the analysis definition as explained [above](#definition-of-analyses). The `enabled` flag must be set to `true`; only those analyses are considered.
Since the defined analyses will be executed automatically, there might need to be a discussion about runtime and resource needs before corresponding requests/PRs can be taken into account.
The AnalysisQC should not introduce considerable overhead with respect to an MC production or data reconstruction themselves.

## Further options and possibilities

### Check if an analysis was successful

Once you ran the analysis workflow as explained [above](#testing-an-analysis-on-some-aod), you can check if it was technically successful (that does not include any checks of the physics output). To do so, run
```bash
${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_config.py validate-output --tasks <analysis-name1> [<analysis-name2> [...]] [-d <output-directory>]
```
It will check if the analysis went through and also if the expected outputs are there. The output directory is usually `Analysis` but you may have given another one earlier which you can set here with `-d <output-directory>`.

There are more sub-commands and options that can be checked with
```bash
${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_config.py --help # OR
${O2DPG_ROOT}/MC/analysis_testing/o2dpg_analysis_test_config.py <sub-command> --help
```
