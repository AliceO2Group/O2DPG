# Production workflows
This folder stores the production workflows for global runs, in the description library file `production.desc`.
There are currently 2 workflows:
- `synchronous-workflow`: the default workflow using 8 GPUs and 2 NUMA domains. (Note that this workflow currently does not terminate correctly: https://alice.its.cern.ch/jira/browse/O2-2375)
- `synchronous-workflow-1numa`: workfloy using only 4 GPUs without NUMA pinning. (Fully sufficient for pp)

Standalone calibration workflows are contained in `standalone-calibration.desc`.

If processing is to be disabled, please use the `no-processing` workflow in `no-processing.desc`.

# Configuration options
You can use the following options to change the workflow behavior:
- `DDMODE` (default `processing`) : Must be `processing` (synchronous processing) or `processing-disk` (synchronous processing + storing of raw time frames to disk, not that this is the raw time frame not the CTF!). The `DDMODE` `discard` and `disk` are not compatible with the synchronous processing workflow, you must use the `no-processing.desc` workflow instead!.
- `WORKFLOW_DETECTORS` (default `ALL`) : Comma-separated list of detectors for which the processing is enabled. If these are less detectors than participating in the run, data of the other detectors is ignored. If these are more detectors than participating in the run, the processes for the additional detectors will be started but will not do anything.
- `WORKFLOW_DETECTORS_QC` (default `ALL`) : Comma-separated list of detectors for which to run QC, can be a subset of `WORKFLOW_DETECTORS` (for standalone detectors QC) and `WORKFLOW_DETECTORS_MATCHING` (for matching/vertexing QC). If a detector (matching/vertexing step) is not listed in `WORKFLOW_DETECTORS` (`WORKFLOW_DETECTORS_MATCHING`), the QC is automatically disabled for that detector. Only active if the `WORKFLOW_PARAMETER=QC` is set.
- `WORKFLOW_DETECTORS_CALIB` (default `ALL`) : Comma-separated list of detectors for which to run calibration, can be a subset of `WORKFLOW_DETECTORS`. If a detector is not listed in `WORKFLOW_DETECTORS`, the calibration is automatically disabled for that detector. Only active if the `WORKFLOW_PARAMETER=CALIB` is set.
- `WORKFLOW_DETECTORS_FLP_PROCESSING` (default `TOF` for sync processing on EPN, `NONE` otherwise) : Signals that these detectors have processing on the FLP enabled. The corresponding steps are thus inactive in the EPN epl-workflow, and the raw-proxy is configured to receive the FLP-processed data instead of the raw data in that case.
- `WORKFLOW_DETECTORS_RECO` (default `ALL`) : Comma-separated list of detectors for which to run reconstruction.
- `WORKFLOW_DETECTORS_CTF` (default `ALL`) : Comma-separated list of detectors to include in CTF.
- `WORKFLOW_DETECTORS_MATCHING` (default selected corresponding to default workflow for sync or async mode respectively) : Comma-separated list of matching / vertexing algorithms to run. Use `ALL` to enable all of them. Currently supported options (see LIST_OF_GLORECO in common/setenv.h): `ITSTPC`, `TPCTRD`, `ITSTPCTRD`, `TPCTOF`, `ITSTPCTOF`, `MFTMCH`, `PRIMVTX`, `SECVTX`.
- `WORKFLOW_EXTRA_PROCESSING_STEPS` Enable additional processing steps not in the preset for the SYNC / ASYNC mode. Possible values are: `MID_RECO` `MCH_RECO` `MFT_RECO` `FDD_RECO` `FV0_RECO` `ZDC_RECO` `ENTROPY_ENCODER` `MATCH_ITSTPC` `MATCH_TPCTRD` `MATCH_ITSTPCTRD` `MATCH_TPCTOF` `MATCH_ITSTPCTOF` `MATCH_MFTMCH` `MATCH_MFTMCH` `MATCH_PRIMVTX` `MATCH_SECVTX`. (Here `_RECO` means full async reconstruction, and can be used to enable it also in sync mode.)
- `WORKFLOW_PARAMETERS` (default `NONE`) : Comma-separated list, enables additional features of the workflow. Currently the following features are available:
  - `GPU` : Performs the TPC processing on the GPU, otherwise everything is processed on the CPU.
  - `CTF` : Write the CTF to disk (CTF creation is always enabled, but if this parameter is missing, it is not stored).
  - `EVENT_DISPLAY` : Enable JSON export for event display.
  - `QC` : Enable QC.
  - `CALIB` : Enable calibration (not yet working!)
- `RECO_NUM_NODES_OVERRIDE` (default `0`) : Overrides the number of EPN nodes used for the reconstruction (`0` or empty means default).
- `MULTIPLICITY_FACTOR_RAWDECODERS` (default `1`) : Scales the number of parallel processes used for raw decoding by this factor.
- `MULTIPLICITY_FACTOR_CTFENCODERS` (default `1`) : Scales the number of parallel processes used for CTF encoding by this factor.
- `MULTIPLICITY_FACTOR_REST` (default `1`) : Scales the number of other reconstruction processes by this factor.
- `QC_JSON_EXTRA` (default `NONE`) : extra QC jsons to add (if does not fit to those defined in WORKFLOW_DETECTORS_QC & (WORKFLOW_DETECTORS | WORKFLOW_DETECTORS_MATCHING)
Most of these settings are configurable in the AliECS GUI. But some of the uncommon settings (`WORKFLOW_DETECTORS_FLP_PROCESSING`, `WORKFLOW_DETECTORS_CTF`, `WORKFLOW_DETECTORS_RECO`, `WORKFLOW_DETECTORS_MATCHING`, `WORKFLOW_EXTRA_PROCESSING_STEPS`, advanced `MULTIPLICITY_FACTOR` settings) can only be set via the "Additional environment variables field" in the GUI using bash syntax, e.g. `WORKFLOW_DETECTORS_FLP_PROCESSING=TPC`.

# Process multiplicity factors
- The production workflow has internally a default value how many instances of a process to run in parallel (which was tuned for Pb-Pb processing)
- Some critical processes for synchronous pp processing are automatically scaled by the inverse of the number of nodes, i.e. the multiplicity is increased by a factor of 2 if 125 instead of 250 nodes are used, to enable the processing using only a subset of the nodes.
- Factors can be provided externally to scale the multiplicity of processes further. All these factors are multiplied.
  - One factor can be provided based on the type of the processes: raw decoder (`MULTIPLICITY_FACTOR_RAWDECODERS`), CTF encoder (`MULTIPLICITY_FACTOR_CTFENCODERS`), or other reconstruction process (`MULTIPLICITY_FACTOR_REST`)
  - One factor can be provided per detector via `MULTIPLICITY_FACTOR_DETECTOR_[DET]` using the 3 character detector representation, or `MATCH` for the global matching and vertexing workflows.
- The multiplicity of an individual process can be overridden externally (this is an override, no scaling factor) by using `MULTIPLICITY_FACTOR_PROCESS_[PROCESS_NAME]`. In the process name, dashes `-` must be replaced by underscores `_`.
- For example, creating the workflow with `MULTIPLICITY_FACTOR_RAWDECODERS=2 MULTIPLICITY_FACTOR_DETECTOR_ITS=3 MULTIPLICITY_FACTOR_PROCESS_mft_stf_decoder=5` will scale the number of ITS raw decoders by 6, of other ITS processes by 3, of other raw decoders by 2, and will run exactly 5 `mft-stf-decoder` processes.

# Additional custom control variables
For user modification of the workflow settings, the folloing *EXTRA* environment variables exist:
- `ARGS_ALL_EXTRA` : Extra command line options added to all workflows
- `ALL_EXTRA_CONFIG` : Extra config key values added to all workflows
- `GPU_EXTRA_CONFIG` : Extra options added to the configKeyValues of the GPU workflow
- `ARGS_EXTRA_PROCESS_[WORKFLOW_NAME]` : Extra command line arguments for the workflow binary `WORKFLOW_NAME`. Dashes `-` must be replaced by underscores `_` in the name! E.g. `ARGS_EXTRA_PROCESS_o2_tof_reco_workflow="--output-type clusters"`
- `CONFIG_EXTRA_PROCESS_[WORKFLOW_NAME]` : Extra `--configKeyValues` arguments for the workflow binary `WORKFLOW_NAME`. Dashes `-` must be replaced by underscores `_` in the name! E.g. `CONFIG_EXTRA_PROCESS_o2_gpu_reco_workflow="GPU_proc.debugLevel=1;GPU_proc.ompKernels=0;"`

In case the CTF dictionaries were created from the data drastically different from the one being compressed, the default memory allocation for the CTF buffer might be insufficient. One can apply scaling factor to the buffer size estimate (default=1.5) of particular detector by defining variable e.g. `TPC_ENC_MEMFACT=3.5`

# File input for ctf-reader / raw-tf-reader
- The variable `$INPUT_FILE_LIST` can be a comma-seperated list of file, or a file with a file-list of CTFs/raw TFs.
- The variable `$INPUT_FILE_COPY_CMD` can provide a custom copy command (default is to fetch the files from EOS).

# Remarks on QC
The JSON files for the individual detectors are merged into one JSON file, which is cached during the run on the shared EPN home folder.
The default JSON file per detector is defined in `qc-workflow.sh`.
JSONs per detector can be overridden by exporting `QC_JSON_[DETECTOR_NAME]`, e.g. `QC_JSON_TPC`, when creating the workflow.
The global section of the merged qc JSON config is taken from qc_global.json

# run-workflow-on-inputlist.sh
`O2/prodtests/full-system-test/run-workflow-on-inputlist.sh` is a small tool to run the `dpl-workflow.sh` on a list of files.
Technically, it is a small wrapper which just launches `dpl-workflow.sh`, and optionally the `StfBuilder` in parallel.

*NOTE*: Currently it uses the `dpl-workflow.sh` in the O2 repo, not the O2DataProcessing repo. During development, there are 2 copies of this script. This will be cleaned up soon.

The syntax is:
```
run-workflow-on-inputlist.sh [CTF | DD | TF] [name of file with list of files to be processed] [Timeout in seconds (optional: default = disabled)] [Log to stdout (optional: default = enabled)]
```
The modes are:
- DD: Read raw timeframes using DataDistribution / StfBuilder
- TF: Read raw timeframes using o2-raw-tf-reader-workflow
- CTF: Read CTFs using the o2-ctf-reader-workflow

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
EPNMODE=1 WORKFLOW_DETECTORS=TPC XrdSecSSSKT=~/.eos/my.key TFDELAY=10 NTIMEFRAMES=10 SHMSIZE=32000000000 DDSHMSIZE=32000 ~/alice/O2/prodtests/full-system-test/run-workflow-on-inputlist.sh DD file_list.txt 500 1
```
