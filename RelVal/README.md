# O2DPG ReleaseValidation (RelVal)

The RelVal is specifically designed to compare 2 sets of QC objects. However, it is also possible to compare ROOT files that contain other objects such as histograms (`TH1`) or also `TTree`s (see further below for the full list of objects that are understood).

At the end of this README are some examples for QC RelVal.

## ROOT macros

There are 2 ROOT macros which can in principle be used as-is. Their functionality and purpose is explained in the following. In general, it is recommended to use the Python wrapper explained further below. It offers additional flexibility and functionality on top of the macros.

### The macro [ReleaseValidation.C](ReleaseValidation.C)

This macro allows to compare 2 ROOT files that contain `TH1` objects. Objects are considered to correspond to each other if they have the same name.
At the moment, 3 different comparisons are implemented:
1. relative difference of bin contents,
1. Chi2 test,
1. simple comparison of number of entries

The first 2 tests are considered critical, hence if the threshold is exceeded, the comparison result is named `BAD`.

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

### Basic usage

If you would like to compare 2 files, simply run
```bash
python o2dpg_release_validation.py rel-val -i <list-of-first-files> -j <list-of-second-files> [-o <output/dir>] [--include-dirs <list-of-directories>]
```
This performs all of the above mentioned tests. If only certain tests should be performed, this can be achieved with the flags `--with-test-<which-test>` where `<which-test>` is one of
1. `chi2`,
1. `bincont`,
1. `numentries`.

By default, all of them are switched on.

If `--include-dirs` is specified, only objects under those directories are taken into account. Note that this is not a patter matching but it needs to start with the top directory. Thus, if for instance `--include-dirs /path/to/interesting`, everything below that path will be considered. However, something placed in `/another/path/to/interesting` will not be considered.
Note that `o2::quality_control::core::MonitorObjectCollection` is treated as a directory in this respect.

### Apply to entire simulation outcome

In addition to simply comparing 2 ROOT files, the script offers the possibility of comparing 2 corresponding directories that contain simulation artifacts (and potentially QC and analysis results). It is not foreseen to run over everything inside those directories but the files must be specifiec via a small config file. See [this example](config/rel_val_sim_dirs_default.json). It is passed via the option `--dirs-config`. In addition, top-level keys can be enabled(disabled) with `--dirs-config-enable <keys>`(`dirs-config-disable <keys>`) where disabling takes precedence.

**NOTE** That each single one of the comparisons is only done if mutual files were found in the 2 corresponding directories. As an example, one could do
```bash
cd ${DIR1}
python o2dpg_workflow_runner.py -f <workflow-json1>
cd ${DIR2}
# potentially something has changed in the software or the simulation/reconstruction parameters
python o2dpg_workflow_runner.py -f <workflow-json2>
python ${O2DPG_ROOT}/ReleaseValidation/o2dpg_release_validation.py rel-val -i ${DIR1} -j ${DIR2} --dirs-config ${O2DPG_ROOT}/RelVal/config/rel_val_sim_dirs_default.json --dirs-config-enable QC [-o <output/dir>] [<test-flags>]
```
This would run the RelVal von everything specified under the top key `QC`.

### Inspection and re-plotting summary grid

This is done via
```bash
python ${O2DPG_ROOT}/ReleaseValidation/o2dpg_release_validation.py inspect <path-to-outputdir-or-file> [--include-patterns <patterns>] [--plot] [--flags <severity-flags>]
```
If only a path is provided, a summary will be printed on the screen showing the number of `GOOD`, `CRIT_NC` and `BAD`.
Adding patterns for `--include-patterns` only objects matching at least one of the patterns will be taken into account for the summary.
If `--plot` is provided, another summary grid will be written into the same directory passed to the `inspect` command and it will be called `SummaryTestUser.png`. If `--flags` are given, only the objects where at least one test has one of the flags will be included in the grid.

### Make ready for InfluxDB

To convert the final output to something that can be digested by InfluxDB, use
```bash
python ${O2DPG_ROOT}/ReleaseValidation/o2dpg_release_validation.py influx --dir <rel-val-out-dir> [--tags k1=v1 k2=v2 ...] [--table-name <chosen-table-name>]
```
When the `--tags` argument is specified, these are injected as TAGS for InfluxDB in addition. The table name can also be specified explicitly; if not given, it defaults to `O2DPG_MC_ReleaseValidation`.

## Plot output

There are various plots created during the RelVal run. For each compared file there are
* overlay plots (to be found in the sub directory `overlayPlots`),
* 2D plots summarising the results in a grid view (called `SummaryTests.png`),
* pie charts showing the fraction of test results per test,
* 1D plots showing the computed value and threshold per test.

## More details of `rel-val` command

As mentioned above, the basic usage of the `rel-val` sub-command is straightforward. But there are quite a few more options available and some of them will be explained briefly below.

### Setting new thresholds from another RelVal run (towards threshold tuning)

Imagine the scenario, where you assume that one has 2 outputs (either custom or full simulation output) which should be compatible. For instance, these could be 2 simulation runs with the same generator seed and reasonably high statistics and also otherwise with the same parameters.
Running the RelVal on these directories will - as usual - yield the `<parent/output/dir/SummaryGlobal.json>` as well as `<parent/output/dir/sub/dirSummary.json>`. Now, assuming there is another simulation output from - for instance - another software version. To check, where this is truly worse in terms of the RelVal comparison, one could compare it to one of the "baseline" runs while setting all thresholds to the computed values of the first comparison. This can be done with
```bash
python ${O2DPG_ROOT}/ReleaseValidation/o2dpg_release_validation.py rel-val -i ${DIR1} ${DIR2} [-o <output/dir>] --use-values-as-thresholds <parent/output/dir/SummaryGlobal.json>
```
which will set each threshold individually per test and per histogram.

In addition each test threshold can be set globally for all histogram comparisons with
* `--chi2-threshold <value>`,
* `--rel-mean-diff-threshold <value>`,
* `--rel-entries-diff-threshold <value>`.

## RelVal for QC (examples)

### Comparing data with MC

MC QC objects are usually distributed over multiple files while those from data are all contained in one single file. It is possible to directly compare them with
```bash
python ${O2DPG_ROOT}/ReleaseValidation/o2dpg_release_validation.py rel-val -i ${MC_PRODUCTION}/QC/*.root -j ${DATA_PRODUCTION}/QC.root [--inlcude-dirs <include-directories]
```
