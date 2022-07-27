# O2DPG ReleaseValidation (RelVal)

## The macro [ReleaseValidation.C](ReleaseValidation.C)

This macro `ReleaseValidation.C` allows to compare 2 ROOT files that contain objects of the types
* ROOT histograms (deriving from `TH1`)
* ROOT `TProfile`
* ROOT `TEfficiency`
* O2 `o2::quality_control::core::MonitorObjectCollection`
* O2 `o2::quality_control::core::MonitorObject`

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
python o2dpg_release_validation.py rel-val -i <file1> <file2> [-o <output/dir>]
```
This performs all of the above mentioned tests. If only certain tests should be performed, this can be achieved with the flags `--with-test-<which-test>` where `<which-test>` is one of
1. `chi2`,
1. `bincont`,
1. `numentries`.

By default, all of them are switched on.

### Apply to entire simulation outcome

In addition to simply comparing 2 ROOT files, the script offers the possibility of comparing 2 corresponding directories that contain simulation artifacts (and potentially QC and analysis results). This then automatically runs the RelVal on
1. QC output,
1. analysis results output,
1. TPC tracks output,
1. MC kinematics,
1. MC hits.

**NOTE** That each single one of the comparison types if only done if mutual files were found in the 2 corresponding directories. As an example, one could do
```bash
cd ${DIR1}
python o2dpg_workflow_runner.py -f <workflow-json1>
cd ${DIR2}
# potentially something has changed in the software or the simulation/reconstruction parameters
python o2dpg_workflow_runner.py -f <workflow-json2>
python ${O2DPG_ROOT}/ReleaseValidation/o2dpg_release_validation.py rel-val -i ${DIR1} ${DIR2} [-o <output/dir>] [<test-flags>]
```
Again, also here it can be specified explicitly on what the tests should be run by specifying one or more `<test-flags>` such as
1. `--with-type-qc`,
1. `--with-type-analysis`,
1. `--with-type-tpctracks`,
1. `--with-type-kine`,
1. `--with-type-hits`.

### Quick inspection

This is done via
```bash
python ${O2DPG_ROOT}/ReleaseValidation/o2dpg_release_validation.py inspect <path-to-outputdir-or-file> [--severity <severity>]
```
The latter optional argument could be a list of any of the above mentioned severities. If a directory is passed as input, it is expected that there is either a file named `SummaryGlobal.json` or - if that cannot be found - a file named `Summary.json`.

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


## FEATURES TO BE ADDED

* more detailed MC kinematics RelVal
* additional parsing options for `inspect`
* make summary JSON format more efficient
* potential additional requests
