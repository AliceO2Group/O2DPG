This folder stores the production workflows for global runs, in the description library file `production.desc`.
There are currently 2 workflows:
- `synchronous-workflow`: the default workflow using 8 GPUs and 2 NUMA domains. (Note that this workflow currently does not terminate correctly: https://alice.its.cern.ch/jira/browse/O2-2375)
- `synchronous-workflow-1numa`: workfloy using only 4 GPUs without NUMA pinning. (Fully sufficient for pp)

If processing is to be disabled, please use the `no-processing` workflow in `no-processing.desc`.

You can use the following options to change the workflow behavior:
- `DDMODE` (default `processing`) : Must be `processing` (synchronous processing) or `processing-disk` (synchronous processing + storing of raw time frames to disk, not that this is the raw time frame not the CTF!). The `DDMODE` `discard` and `disk` are not compatible with the synchronous processing workflow, you must use the `no-processing.desc` workflow instead!.
- `WORKFLOW_DETECTORS` (default `ALL`) : Comma-separated list of detectors for which the processing is enabled. If these are less detectors than participating in the run, data of the other detectors is ignored. If these are more detectors than participating in the run, the processes for the additional detectors will be started but will not do anything.
- `WORKFLOW_DETECTORS_QC` (default `ALL`) : Comma-separated list of detectors for which to run QC, can be a subset of `WORKFLOW_DETECTORS`. If a detector is not listed in `WORKFLOW_DETECTORS`, the QC is automatically disabled for that detector. Only active if the `WORKFLOW_PARAMETER=QC` is set.
- `WORKFLOW_DETECTORS_CALIB` (default `ALL`) : Comma-separated list of detectors for which to run calibration, can be a subset of `WORKFLOW_DETECTORS`. If a detector is not listed in `WORKFLOW_DETECTORS`, the calibration is automatically disabled for that detector. Only active if the `WORKFLOW_PARAMETER=CALIB` is set.
- `WORKFLOW_DETECTORS_FLP_PROCESSING` (default `TOF` for sync processing on EPN, `NONE` otherwise) : Signals that these detectors have processing on the FLP enabled. The corresponding steps are thus inactive in the EPN epl-workflow, and the raw-proxy is configured to receive the FLP-processed data instead of the raw data in that case.
- `WORKFLOW_PARAMETERS` (default `NONE`) : Comma-separated list, enables additional features of the workflow. Currently the following features are available:
  - `GPU` : Performs the TPC processing on the GPU, otherwise everything is processed on the CPU.
  - `CTF` : Write the CTF to disk (CTF creation is always enabled, but if this parameter is missing, it is not stored).
  - `EVENT_DISPLAY` : Enable JSON export for event display.
  - `QC` : Enable QC.
  - `CALIB` : Enable calibration (not yet working!)
  - `CTF_ONLY` : Disables all processing except what is needed for the CTF (currently partially incompatible to `QC` and `CALIB` depending on the detectors).
- `RECO_NUM_NODES_OVERRIDE` (default `0`) : Overrides the number of EPN nodes used for the reconstruction (`0` or empty means default).
- `MULTIPLICITY_FACTOR_RAWDECODERS` (default `1`) : Scales the number of parallel processes used for raw decoding by this factor.
- `MULTIPLICITY_FACTOR_CTFENCODERS` (default `1`) : Scales the number of parallel processes used for CTF encoding by this factor.
- `MULTIPLICITY_FACTOR_REST` (default `1`) : Scales the number of other reconstruction processes by this factor.

Most of these settings are configurable in the AliECS GUI. But some of the uncommon settings (`WORKFLOW_DETECTORS_FLP_PROCESSING`) can only be set via the "Additional environment variables field" in the GUI using bash syntax, e.g. `WORKFLOW_DETECTORS_FLP_PROCESSING=TPC`.

For user modification of the workflow settings, the folloing *EXTRA* environment variables exist:
- `ARGS_ALL_EXTRA` : Extra command line options added to all workflows
- `ALL_EXTRA_CONFIG` : Extra config key values added to all workflows
- `GPU_EXTRA_CONFIG` : Extra options added to the configKeyValues of the GPU workflow

Some remarks for the QC:
The JSON files for the individual detectors are merged into one JSON file, which is cached during the run on the shared EPN home folder.
The default JSON file per detector is defined in `qc-workflow.sh`.
JSONs per detector can be overridden by exporting `QC_JSON_[DETECTOR_NAME]`, e.g. `QC_JSON_TPC`, when creating the workflow.
