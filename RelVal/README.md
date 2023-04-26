# O2DPG ReleaseValidation (RelVal)

The RelVal is specifically designed to compare 2 sets of QC objects. However, it is also possible to compare ROOT files that contain other objects such as histograms (`TH1`) or also `TTree`s (see further below for the full list of objects that are understood).

At the end of this README are some examples for QC RelVal.

## ROOT macros

There are 2 ROOT macros which can in principle be used as-is. Their functionality and purpose is explained in the following. In general, it is recommended to use the Python wrapper explained further below. It offers additional flexibility and functionality on top of the macros.

### The macro [ReleaseValidation.C](ReleaseValidation.C)

This macro allows to compare 2 ROOT files that contain `TH1` objects. Objects are considered to correspond to each other if they have the same name.
At the moment, 3 different comparisons are implemented:
1. `chi2`: Chi2 test of compared histograms (see also the [ROOT documentation](https://root.cern.ch/doc/master/classTH1.html#ab7d63c7c177ccbf879b5dc31f2311b27)),
1. `kolmogorov`: shape comparison using Kolmogorov test (see also the [ROOT documentation](https://root.cern.ch/doc/master/classTH1.html#aeadcf087afe6ba203bcde124cfabbee4)),
1. `num_entries`: relative difference in the number of entries.

The first 2 tests are considered critical, hence if the threshold is exceeded, the comparison result is named `BAD`. Also the third test is considered critical in case efficiencies are compared coming from `TEfficiency` objects.

There are 5 different test severities per test:
1. `GOOD` if the threshold was not exceeded,
1. `WARNING`: if a non-critical test exceeds the threshold (in this case only when comparing the number of entries),
1. `NONCRIT_NC` if the histograms could not be compared e.g. due to different binning or axis ranges **and** if the test is considered as **non-critical**,
1. `CRIT_NC` if the histograms could not be compared e.g. due to different binning or axis ranges **and** if the test is considered as **critical**,
1. `BAD` if a critical test exceeds the threshold.

### The macro [ExtractAndFlatten.C](ExtractAndFlatten.C)

This macro is used to prepare the input files for `ReleaseValidation.C`. It extracts objects from an input file and turns the objects into `TH1` objects which are then stored in a flat file. The macro browses the input file recursively and the following objects will be recognised and extracted:
* ROOT histograms (deriving from `TH1`)
* ROOT `TProfile`
* ROOT `TEfficiency`
* O2 `o2::quality_control::core::MonitorObjectCollection`
* O2 `o2::quality_control::core::MonitorObject`
* ROOT `TTree` (Here the algorithm does its best to extract as many TLeafs as possible which works when they can be drawn with `TTree::Draw`.)

## Python wrapper and usage

Although the above macro can be used on its own, its application was also wrapped into a [Python script](o2dpg_release_validation.py) for convenience. By doing so, it offers significantly more functionality.

The full help message of this script can be seen by typing
```bash
python o2dpg_release_validation.py [<sub-command>] --help
```
The wrapper includes 3 different sub-commands for now
1. `rel-val` to steer the RelVal,
1. `inspect` to print histograms of specified severity (if any),
1. `compare` to compare the results of 2 RelVal runs,
1. `influx` to convert the summary into a format that can be understood by and sent to an InfluxDB instance.

Each sub-command can be run with `--help` to see all options/flags.

### Basic usage

If you would like to compare 2 files, simply run
```bash
python o2dpg_release_validation.py rel-val -i <first-list-of-files> -j <second-list-of-files> [-o <output/dir>] [--include-dirs <list-of-directories>]
```
This performs all of the above mentioned tests. If only certain tests should be performed, this can be achieved with the flags `--with-test-<which-test>` where `<which-test>` is one of
1. `chi2`,
1. `kolmogorov`,
1. `num-entries`.

By default, all of them are switched on.

If `--include-dirs` is specified, only objects under those directories inside the given ROOT files are taken into account. Note that this is not a pattern matching but it needs to start with the top directory. Thus, if for instance `--include-dirs /path/to/interesting`, everything below that path will be considered. However, something placed in `/another/path/to/interesting` will not be considered.
**Note** that `o2::quality_control::core::MonitorObjectCollection` is treated as a directory in this respect.

### Inspection and re-plotting summary grid

This is done via
```bash
python ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect <path-to-outputdir-or-summary-json> [--include-patterns <patterns>] [--plot] [--flags <severity-flags>] [-o <output-dir>]
```
If only a path is provided, a summary will be printed on the screen showing the number of `GOOD`, `CRIT_NC` and `BAD`.
Adding patterns for `--include-patterns` only objects matching at least one of the patterns will be taken into account for the summary.
If `--plot` is provided, new summary plots (grid, pie charts, values compared to thresholds) will be produced. By default they are written to `<input-directory>/user_summary` or, if the `-o` option is provided, to the custom output directory.
If `--flags` are given, only the objects where at least one test has one of the flags will be included in the grid.

### Make ready for InfluxDB

To convert the final output to something that can be digested by InfluxDB, use
```bash
python ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py influx --dir <rel-val-out-dir> [--tags k1=v1 k2=v2 ...] [--table-name <chosen-table-name>]
```
When the `--tags` argument is specified, these are injected as TAGS for InfluxDB in addition. The table name can also be specified explicitly; if not given, it defaults to `O2DPG_MC_ReleaseValidation`.

## Plot output

There are various plots created during the RelVal run. For each compared file there are
* overlay plots (to be found in the sub directory `overlayPlots`),
* 2D plots summarising the results in a grid view (called `SummaryTests.png`),
* pie charts showing the fraction of test results per test,
* 1D plots showing the computed value and threshold per test.

## More details of `rel-val` command

As mentioned above, the basic usage of the `rel-val` sub-command is straightforward. But there are quite a few more options available and some of them will be explained briefly below. In fact, most of them also apply to the `inspect` sub-command.

### Setting new/custom thresholds from another RelVal run
Each RelVal run produces a `Summary.json` file in the corresponding output directories. Among other things, it contains the computed values of all tests for each compared histogram pair. Such a `Summary.json` can now be used as a input file for a future RelVal to set all thresholds according to the values. In fact, multiple such files can be passed and for each histogram-test combination, the mean or max of the previously calculated values can be used to set the new thresholds.

```bash
python ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i <first-list-of-files> -j <second-list-of-files> --use-values-as-thresholds <list-of-summaries> [--combine-thresholds {mean,max}] [--test-<name>-threshold-margin <value>]
```
In addition, a margin for each test can be provided as shown in the command above. This is a factor by which the threshold is multiplied. So to add a `10%` margin for the chi2 test, simply put `test-chi2-threshold-margin 1.1`.

## RelVal for QC (examples)

### Comparing data with MC

There is an ongoing effort to unify the names of QC objects inside MC and data QC files. Some are already unified and the following command would run comparison of those. However, others are not yet unified and will not be considered in the comparison.

MC QC objects are usually distributed over multiple files while those from data are all contained in one single file. It is possible to directly compare them with
```bash
python ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i ${MC_PRODUCTION}/QC/*.root -j ${DATA_PRODUCTION}/QC.root [--include-dirs <include-directories>]
```
