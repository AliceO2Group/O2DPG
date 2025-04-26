# Production workflows
This folder stores the production workflows for global runs, in the description library file `production.desc`.
There are currently 2 workflows:
- `synchronous-workflow`: the default workflow using 8 GPUs and 2 NUMA domains.
- `synchronous-workflow-1numa`: workfloy using only 4 GPUs without NUMA pinning. (Fully sufficient for pp)

Standalone calibration workflows are contained in `standalone-calibration.desc`.

If processing is to be disabled, please use the `no-processing` workflow in `no-processing.desc`.

# Options for dpl-workflow.sh
Refer to https://github.com/AliceO2Group/AliceO2/blob/dev/prodtests/full-system-test/documentation/dpl-workflow-options.md

# run-workflow-on-inputlist.sh
`O2/prodtests/full-system-test/run-workflow-on-inputlist.sh` is a small tool to run the `dpl-workflow.sh` on a list of files.
Technically, it is a small wrapper which just launches `dpl-workflow.sh`, and optionally the `StfBuilder` in parallel.

The syntax is:
```
run-workflow-on-inputlist.sh [CTF | DD | TF] [name of file with list of files to be processed] [Timeout in seconds (optional: default = disabled)] [Log to stdout (optional: default = enabled)]
```
The modes are:
- DD: Read raw timeframes using DataDistribution / StfBuilder
- TF: Read raw timeframes using o2-raw-tf-reader-workflow
- CTF: Read CTFs using the o2-ctf-reader-workflow

> **NOTE:** The DD mode does not support a list of local files as input. For processing a few local files one should use the TF mode.

The second argument is the name of a list-files containing a list of files to be processed.
In the CTF and TF modes, it can also be a comma-separated list, but this is not supported in the DD mode.
- (The work `LOCAL` may be used to fetch files from the local folder.)
- (In case the copy command must be adjusted, use `$INPUT_FILE_COPY_CMD`)

The third parameter is an optional timeout in seconds, after which the processing is aborted.

The forth parameter enables writing of all workflow output to stdout in addition.
In any case the output is logged to files log_[date]_*.log.

The tool passes all env variables on to `dpl-workflow.sh` thus it can be used in the same way.
*Note* Not that when running in `DD` mode, the SHM size for the StfBuilder must be provided. *NOTE* that this is in MB not in bytes.

An example command line is:
```
EPNSYNCMODE=1 WORKFLOW_DETECTORS=TPC XrdSecSSSKT=~/.eos/my.key TFDELAY=10 NTIMEFRAMES=10 SHMSIZE=32000000000 DDSHMSIZE=32000 ~/alice/O2/prodtests/full-system-test/run-workflow-on-inputlist.sh DD file_list.txt 500 1
```

# Local QC testing
For testing a workflow with QC locally, the sending of data to QC mergers must be disabled. For this, the qc-workflow.sh supports the option `QC_REDIRECT_MERGER_TO_LOCALHOST=1` which redirects all messages to the remote machines to `localhost`.
Since the channels are `pub/sub` they are non-blocking.
