# O2DPG ReleaseValidation (RelVal)

The RelVal is specifically designed to compare 2 sets of QC objects. However, it is also possible to compare ROOT files that contain other objects such as histograms (`TH1`) or also `TTree`s:
* ROOT histograms (deriving from `TH1`)
* ROOT `TProfile`
* ROOT `TEfficiency`
* O2 `o2::quality_control::core::MonitorObjectCollection`
* O2 `o2::quality_control::core::MonitorObject`
* ROOT `TTree` (Here the algorithm does its best to extract as many TLeafs as possible which works when they can be drawn with `TTree::Draw`.)

Objects from compared files are extracted recursively and so all objects in sub-directories are compared.

The convention is, that only those objects that have the exact same path are compared to one another so the 2 ROOT files must have the same structure. Note though, that all possible pairs are compared. If there are singular objects in one or the other file, they will be safely ignored.

At the end of this README are some examples for QC RelVal.

## Quick start

To jump right in, please check out [this](#run-for-qc)

## Definitions

### Metric
A metric is a way to compare 2 corresponding objects and assign a number to that comparison. There are currently 3 definitions:
1. `chi2`: Chi2 test of compared histograms (see also the [ROOT documentation](https://root.cern.ch/doc/master/classTH1.html#ab7d63c7c177ccbf879b5dc31f2311b27)),
1. `kolmogorov`: shape comparison using Kolmogorov test (see also the [ROOT documentation](https://root.cern.ch/doc/master/classTH1.html#aeadcf087afe6ba203bcde124cfabbee4)),
1. `num_entries`: relative difference in the number of entries.
So for each pair of histograms there can be multiple metrics.

### Test
A test is the comparison of a computed metric to certain limits (upper,lower). How these limits came about is the property of such a test. For instance, a simple **threshold** test, where lower is better, would mean to have limits of `(<threhsold>, -infty)`.
There can hence be multiple tests for one metric.

### Interpretation
A test can be assigned an interpretation. There are
1. `GOOD` if a metric passes a test,
1. `WARNING`: if a **non-critical** metric fails a test,
1. `NONCRIT_NC` if the objects could not be compared e.g. due to different binning or axis ranges **and** if the metric is considered **non-critical**,
1. `CRIT_NC` if the histograms could not be compared e.g. due to different binning or axis ranges **and** if the metric is considered **critical**,
1. `BAD` if a test of a amtric fails that is considered **critical**
1. `UNKNOWN` used for instance when a test might have been defined but no metric was passed to be tested.

## Usage

The [Python script](o2dpg_release_validation.py) is the entrypoint of the RelVal and it has multiple sub-commands.

The full help message of this script can be seen by typing
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py [<sub-command>] --help
```
The wrapper includes 3 different sub-commands for now
1. `rel-val` to steer the RelVal,
1. `inspect` to print histograms of specified severity (if any),
1. `compare` to compare the results of 2 RelVal runs,
1. `print` simply print object names, metric names or test names line-by-line to the command line; convenient to further digest the output,
1. `influx` to convert the summary into a format that can be understood by and sent to an InfluxDB instance.

Each sub-command can be run with `--help` to see all options/flags.

### `rel-val`

If you would like to compare 2 files (or sets of files), simply run
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i <first-list-of-files> -j <second-list-of-files> \
                                                         [--include-dirs <list_of_include_patterns>]
```
It will run the full release validation, dumps plots and further artifacts in the directory `rel_val` and prints a result summary in the terminal.
Via the optional `--include-patterns` a list of patterns can be passed so that only those ROOT sub-directories are taken into consideration which contain at least on of those patters, **Note** though, that regular expressions cannot (yet) be used.

For the comparison of 2 sets of files this is always the first necessary step and of the most important outputs produced is `rel_val/Summary.json` which contains all the test results. It can be used for further and also more in-depth studies as mentioned in the following.

There are also various plots created during the RelVal run. For each compared file there are
* overlay plots, 1D and 2D (to be found in the sub directory `overlayPlots`),
* 2D plots summarising the interpretations in a grid (called `SummaryTest.png`),
* pie charts showing the fraction of interpretations per metric (and potentially per test, if there are multiple),
* 1D plots showing the computed value and test means per metric (and potentially per test, if there are multiple).


### `inspect`
This command requires that a `rel-val` was run previously which produced a `<output_dir>/Summary.json`.

Imagine you would like to change or experiment with some settings, e.g. you would like to only take objects with certain names into account or only enable certain metrics etc. These things you like to see reflected in the summary as well as in the produced plots.
This is possible with
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect --path <path-to-outputdir-or-summary-json> \
                                                        [--include-patterns <patterns>] [--exclude-patterns <patterns>] \
                                                        [--enable-metric <metric_names>] [--disable-metric <metric_names>] \
                                                        [--interpretations <interpretations_of_interest>] \
                                                        [--critical <metric_names_considered_critical>] \
                                                        [--output|-o <target_directory>]
```
All of those options, except for `--include-patterns` and `--exclude-patterns` also work with the `rel-val` command.
The output will by default be written to `rel_val_inspect`. All plots which are produced by the `rel-val` command are produced again for a potential given sub-set depending on the given options. Only the overlay plots are not produced again.

**NOTE** that with `inspect` the original overlay plots satisfying your selection criteria (e.g. `--include-patters` or `--interpretations`) are also copied over to the target directory.

**Other additional optional arguments**
* `--use-values-as-thresholds [<list_of_other_Summary.json_files>]`: By passing a set of summaries that where produced from `rel-val`, the computed metric values can be used as **new** thresholds. To decide how to combine the values for multiple metrics referring to the same object, the option `--combine-thresholds mean|extreme` can be used. Also, an additional relative margin can be added for each metric with `--margin-threshold <metric> <percent>`; this argument must be repeated for if it should be used for multiple metrics.
* `--regions [<list_of_other_Summary.json_files>]`: This computes means and standard deviations for each metric from previously computed values. The corresponding test is passed, if the value lies around the mean within the standard deviations. The deviation from the mean is also given as number-of-sigmas in the summary grid.
* `rel-val -i <file1> -j <file2> --no-extract` runs RelVal on **flat** ROOT files that have only histogram objects in them.

### `print`
This command has the same optional arguments as the `inspect` command. But the only thing it does is writing some information line-by-line. For instance, to get the object names that were flagged `BAD` by the `chi2` metric, do
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py print --path <path-to-outputdir-or-summary-json> --enable-metric chi2 --interpretations BAD
```
If no RelVal was run but one would like to know the available metrics, one can check with
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py print --metric-names
```

### `influx`

To convert the final output to something that can be digested by InfluxDB, use
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py influx --dir <rel-val-out-dir> [--tags k1=v1 k2=v2 ...] [--table-name <chosen-table-name>]
```
When the `--tags` argument is specified, these are injected as TAGS for InfluxDB in addition. The table name can also be specified explicitly; if not given, it defaults to `O2DPG_MC_ReleaseValidation`.

## RelVal for QC (examples)

### Comparing data with MC

There is an ongoing effort to unify the names of QC objects inside MC and data QC files. Some are already unified and the following command would run comparison of those. However, others are not yet unified and will not be considered in the comparison.

MC QC objects are usually distributed over multiple files while those from data are all contained in one single file. It is possible to directly compare them with
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i ${MC_PRODUCTION}/QC/*.root -j ${DATA_PRODUCTION}/QC.root [--include-dirs <include-directories>]
```

## Run for QC
This is a simple guide to run RelVal for QC.

Here is also a [working example](run/run_data_rel_val.sh), run it with
```bash
${O2DPG_ROOT}/RelVal/run/run_data_rel_val.sh [--qc QC1.root QC2.root ] [--aod AOD1.root AOD2.root] [ --labels LABEL1 LABEL2]
```

### If you are interested in all QC plots
To have everything and to use this as a starting point for deeper inspections, first run
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i QC_file_1.root -j QC_file_2.root -o rel_val_all [--labels meaningfulLabel1 meaningfulLabel2]
```
Now, there is of course a lot but from now on you are fully flexible.

In order to get some insight into a specific detector, say ITS, run
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect --path rel_val_all --include-patterns "^ITS_" -o rel_val_ITS
```
This will only print pie charts and summaries for ITS and also copies all overlay plots related to ITS to your target directory `rel_val_ITS`.

The `inspect` command is much faster now since no new plots are generated and metrics do not have to be recomputed. It simply filters the results according to your criteria. However, what can be re-evaluated are the computed values against new thresholds.

### If you are only interested in some ROOT sub-directories to begin with
If you only want to study for instance the ITS and CPV and there is no interest at this point to study any other detector, run
```bash
${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i QC_file_1.root -j QC_file_2.root -o rel_val_all --include-dirs ITS CPV [--labels meaningfulLabel1 meaningfulLabel2]
```
From here on, you can use the `inspect` command as usual. But there will never be detectors other than ITS and CPV.

### Troubleshooting

If there are unexpected segmentation faults or similar, most likely the `QualityControl` software is not properly linked against `O2`. Most likely, the reason is that `QC` was not rebuild against the loaded `O2` version.
The easiest solution would be to load either `QualityControl` or meta packages such as `O2sim`.
Loading like `O2/latest,QualityControl/latest` can cause problems depending on how the single packages were build.

## Expert section

### Adding a new metric
A new metric can be added in [ReleaseValidationMetrics.C](ReleaseValidationMetrics.C) by extending the function `void initialiseMetrics(MetricRunner& metricRunner)`.

## Future plans

* Store a JSON/JSONs on CCDB for central derivation of more refined thresholds or regions.
