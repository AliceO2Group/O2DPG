The `setenv-sh` script sets the following environment options
* `NTIMEFRAMES`: Number of time frames to process.
* `TFDELAY`: Delay in seconds between publishing time frames (1 / rate).
* `NGPUS`: Number of GPUs to use, data distributed round-robin.
* `GPUTYPE`: GPU Tracking backend to use, can be CPU / CUDA / HIP / OCL / OCL2.
* `SHMSIZE`: Size of the global shared memory segment.
* `DDSHMSIZE`: Size of shared memory unmanaged region for DataDistribution Input.
* `GPUMEMSIZE`: Size of allocated GPU memory (if GPUTYPE != CPU)
* `HOSTMEMSIZE`: Size of allocated host memory for GPU reconstruction (0 = default).
  * For `GPUTYPE = CPU`: TPC Tracking scratch memory size. (Default 0 -> dynamic allocation.)
  * Otherwise : Size of page-locked host memory for GPU processing. (Defauls 0 -> 1 GB.)
* `CREATECTFDICT`: Create CTF dictionary.
* `SAVECTF`: Save the CTF to a root file.
  * 0: Read `ctf_dictionary.root` as input.
  * 1: Create `ctf_dictionary.root`. Note that this was already done automatically if the raw data was simulated with `full_system_test.sh`.
* `SYNCMODE`: Run only reconstruction steps of the synchronous reconstruction.
  * Note that there is no `ASYNCMODE` but instead the `CTFINPUT` option already enforces asynchronous processing.
* `NUMAGPUIDS`: NUMAID-aware GPU id selection. Needed for the full EPN configuration with 8 GPUs, 2 NUMA domains, 4 GPUs per domain.
  In this configuration, 2 instances of `dpl-workflow.sh` must run in parallel.
  To be used in combination with `NUMAID` to select the id per workflow.
  `start_tmux.sh` will set up these variables automatically.
* `NUMAID`: SHM segment id to use for shipping data as well as set of GPUs to use (use `0` / `1` for 2 NUMA domains, 0 = GPUS `0` to `NGPUS - 1`, 1 = GPUS `NGPUS` to `2 * NGPUS - 1`)
* 0: Runs all reconstruction steps, of sync and of async reconstruction, using raw data input.
* 1: Runs only the steps of synchronous reconstruction, using raw data input.
* `EXTINPUT`: Receive input from raw FMQ channel instead of running o2-raw-file-reader.
  * 0: `dpl-workflow.sh` can run as standalone benchmark, and will read the input itself.
  * 1: To be used in combination with either `datadistribution.sh` or `raw-reader.sh` or with another DataDistribution instance.
* `CTFINPUT`: Read input from CTF ROOT file. This option is incompatible to EXTINPUT=1. The CTF ROOT file can be stored via SAVECTF=1.
* `NHBPERTF`: Time frame length (in HBF)
* `GLOBALDPLOPT`: Global DPL workflow options appended to o2-dpl-run.
* `EPNPIPELINES`: Set default EPN pipeline multiplicities.
  Normally the workflow will start 1 dpl device per processor.
  For some of the CPU parts, this is insufficient to keep step with the GPU processing rate, e.g. one ITS-TPC matcher on the CPU is slower than the TPC tracking on multiple GPUs.
  This option adds some multiplicies for CPU processes using DPL's pipeline feature.
  The settings were tuned for EPN processing with 4 GPUs (i.e. the default multiplicities are per NUMA domain).
  The multiplicities are scaled with the `NGPUS` setting, i.e. with 1 GPU only 1/4th are applied.
  You can pass an option different to 1, and than it will be applied as factor on top of the multiplicities.
  It is auto-selected by `start-tmux.sh`.
* `SEVERITY`: Log verbosity (e.g. info or error, default: info)
* `INFOLOGGER_SEVERITY`: Min severity for messages sent to Infologger. (default: `$SEVERITY`)
* `SHMTHROW`: Throw exception when running out of SHM memory.
  It is suggested to leave this enabled (default) on tests on the laptop to get an actual error when it runs out of memory.
  This is disabled in `start_tmux.sh`, to avoid breaking the processing while there is a chance that another process might free memory and we can continue.
* `NORATELOG`: Disable FairMQ Rate Logging.
* `INRAWCHANNAME`: FairMQ channel name used by the raw proxy, must match the name used by DataDistribution.
* `WORKFLOWMODE`: run (run the workflow (default)), print (print the command to stdout), dds (create partial DDS topology)
* `FILEWORKDIR`: directory for all input / output files. E.g. grp / geometry / dictionaries etc. are read from here, and dictionaries / ctf / etc. are written to there.
  Some files have more fine grained control via other environment variables (e.g. to store the CTF to somewhere else). Such variables are initialized to `$FILEWORKDIR` by default but can be overridden.
* `EPNSYNCMODE`: Specify that this is a workflow running on the EPN for synchronous processing, e.g. logging goes to InfoLogger, DPL metrics to to the AliECS monitoring, etc.
* `BEAMTYPE`: Beam type, must be PbPb, pp, pPb, cosmic, technical.
* `IS_SIMULATED_DATA` : 1 for MC data, 0 for RAW data.
