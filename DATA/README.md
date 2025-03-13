This repository contains the PDP workflows to run on the EPN (in the future also on the FLP) and the parse script which parses the description files and creates the DDS XML files.
For only a quick introduction and an example how to create a workflow on the EPN click [here](#Quick-guide-to-create-and-deploy-detector-workflow).
The options for the production workflow are described [here](production/README.md).

# Terminology:
- A **workflow** refers to a single DPL workflow binary, or multiple workflows binaries merged with the `|` syntax, or a shell script starting such a workflow.
- A **full topology** refers to the final XML file that is passed to DDS to start up a processing chain for one single partition on the EPN.
- A **partial topology** is the XML file created by DPL with the `--dds` option.

# Folder structure:
- **common** contains common scripts that can be used by all workflows, most importantly common environment variable scripts.
- **production** contains the production workflows for global runs, which are maintained by PDP experts.
- **tools** contains the **parser** script and auxiliary tools.
- **testing** contains scripts for tests / standalone runs maintained by detectors or privately. Subfolders are **examples** for example workflows provided, **detectors** for standalone detector workflows, and **private** for workflows of users.

# Topology descriptions and description library files:
Another abstraction layer above the *workflows* are **topology descriptions**. The *parser* tool can generate the *full topology* XML file from such a *description*, using the `–dds` option of DPL and the `odc-topo-epn` tool. *Topology descriptions* are stored in **description library files** in the `DATA` folder of the `O2DPG` repository. A *description library file* can contain multiple *topology descriptions* each identified by a **topology name**

# Remarks:
- The repository does not store *full topologies*, but they are created on the fly. Users can cache the resulting full topology XML files.
- The defaults (particularly also those set in the common environment files in the `common` folder) are tuned for running on a laptop / desktop.

# Workflow requirements:
- Workflows shall support 3 run modes selected via the `WORKFLOWMODE` env variable, the **dds** mode and its ${WORKFLOWMODE_FILE} parameter are mandatory:
  - **run** (default): run the workflow
  - **print**: print the final workflow command to the console
  - **dds**: create a partial topology.
- If applicable, workflows shall use the settings from the `common/setenv.sh` script instead of implementing their own options. Mandatory env variables to respect are
  - `SHMSIZE`
  - `SEVERITY` and `INFOLOGGER_SEVERITY` or they must be set to `warning`
  - `NORATELOG` or the fmq rate logging must be disabled
  - `GPUTYPE` (if the workflow supports GPUs)
  - `GLOBALDPLOPT` This option must be appended to the the workflow (to the final binary if merged with `|` syntax)
  - ... (to be continued).
- DPL metrics and InfoLogger (not a requirement in the sense that something would fail, but without it is difficult to debug):
  - The workflow commands should contain `--monitoring-backend influxdb-unix:///tmp/telegraf.sock --resources-monitoring 60` for the DPL metrics.
  - `--infologger-severity $INFOLOGGER_SEVERITY` enables the infologger.
- Workflows should use as last command in the pipe the `o2-dpl-run` and add to it the `$GLOBALDPLOPT` env variable as command line argument.
- Workflows should source these files to get common functions:
  ```
  source common/getCommonArgs.sh
  source common/gen_topo_helper_functions.sh
  ```
- Workflows should aggregate their workflow parts in the `$WORKFLOW` variable, and use `add_W` to add a workflow, and `add_QC_from_consul` to add a QC workflow with a JSON file from consul.
- Calibration workflows must not pollute the production CCDB in the following case (`if [[ $RUNTYPE == "SYNTHETIC" || "${GEN_TOPO_DEPLOYMENT_TYPE:-}" == "ALICE_STAGING" ]]; then` (bash script)), in this case please e.g. upload to `ccdb-test.cern.ch`.
- If a workflow uses an `o2-dpl-raw-proxy` to receive data from DataDistribution, that device must have the `--inject-missing-data` comand line option.

# Configuring and selecting workflow in AliECS:
There are 3 ways foreseen to configure the *full topology* in AliECS: (currently only the manual XML option exists)
- **version of workflow repository**: In this mode, the following settings are configured in AliECS, and they uniquely identify a *full topology*. The *parser* will then create the final DDS XML file with the *full topology*:
  - A **commit hash** identifying a state of the `O2DPG` repository (this can also be a tag, and in the case of production workflows it is required to be a tag).
  - The path of a **description library file** (path relative to the DATA folder inside the `O2DPG` repository).
  - The **workflow name** inside the *description library file*.
  - **detector list**: Multiple comma-separated lists of detectors participating in the run (global list, list for qc, list for calibration, list of detectors to run reconstruction for, list of detectors to include in the CTF, list of detectors that have processing on the FLP), defaulting to `ALL` for all detectors.
  - **workflow parameters**: text field passed to workflow as environment variable for additional options.
  - **number of nodes override**: Overrides the setting for the number of nodes required in the workflow (meant to quickly increase / decrease the EPN partition size). **NOTE: This setting has become mandatory now, and is used exclusively to set the number of nodes. The number specified in the workflow description is ignored**
  - **process multiplicity overrides**: Scaling factors for the process multiplicities for raw decoders, ctf encoders, and other processes.
  - **extra environment options**: Free text field where the operator can put additional environment variables, that will be forwarded to the workflow.
  - **wipe workflow cache**: Normally the XMLs are cached, when they are created from the same repository version / same workflow / same O2 version. This option clears the cache for the current partition.
- **repository directory**: This is almost identical to the case above, but instead of the commit hash, there is the **repository path** specified, pointing to a checked out repository on the shared home folder in the EPN farm. The procedure is the same as before, the parser will create the full topology XML file from the specified workflow in the repository.
- **manual XML file**: In this mode the `O2DPG` repository is not used at all, but the absolute path of a *full topology* XML file in the EPN's shared home folder is specified. Such an XML file must be prepared manually by the same means as the *parser* would usually do (see paragraph on manual XML file below).

# Topology descriptions:
A *topology description* consists of
- A list of modules to load, both for generating the DDS XML file with DPL's `--dds` option and when running the workflow. It can either be a single module, or a space-separated list of modules in double-quotes. In particular, this setting identifies the O2 version. We provide the `O2PDPSuite` package, which has the same versions as O2 itself, and which contain also corresponding versions `DataDistribution`,`QualityControl` and `ODC`. Thus by default one should just load `O2PDPSuite/[version]`.
- A list of workflows, in the form of commands to run to create XML files by the `–dds` option. The command is executed with the `O2DPG/DATA` path as working directory. The env options used to configure the workflow are prepended in normal shell syntax. Certain env options are set by the EPN and must not be overridden: `FILEWORKDIR`, `INRAWCHANNAME`, `CTF_DIR`.
  - Each workflow is amended with the following parameters (the parameters stand in front of the workflow command, and are separated by commas without spaces, the workflow command must be in double-quotes):
    - Zone where to run the workflow (calib / reco)
    - For reco:
      - Number of nodes to run this workflow on
        - **NOTE: This setting for the number of nodes is ignored now. Please use the number of nodes override in ECS!**
        - If a processor in the workflow needs to identify on which node it is running on, it can use the `$DDS_COLLECTION_INDEX` emvironment variable.
      - Minimum number of nodes required forthe workflow (in case of node failure)
        - In case the there are multiple workflows in the topology description, the largest number of nodes, and the largest minimum number of nodes are used.
    - For calib:
      - Number of physical cores to be reserved on the node to run the workflow.
      - Name of the calibration (used to set DDS properties which are used to make the reconstruction workflows connect to specific calibration workflows)
        - ODC/DDS allocates as many nodes as necessary to have sufficient CPU cores for the calibration workflows. The different calibration workflows may or may not run on the same node.

An example for the topology library file looks like:
- topologies.desc
```
demo-full-topology: O2PDPSuite/nightly-20210801 reco,128,126,"SHMSIZE=320000000000 full-system-test/dpl-workflow.sh" calib,5,"SHMSIZE=2000000000 calibration/some-calib.sh" calib,20,"SHMSIZE=2000000000 calibration/other-calib.sh";
other-topology: O2PDPSuite/v1.0.0 reco,2,1,"tpc-test/tpc-standalone-test-1.sh"
```
- AliECS-config:
```
commit=xxxx|path=xxxx file=topologies.desc topology=demo-full-topology parameters="EVENT_DISPLAY" detectors="TPC,ITS" detectors_qc="TPC" [...]
```

# Calibration workflows with aggregator
Calibration workflows can be different when they use an aggregator. In that case, there is processing running on each EPN, and the output is sent to an aggregator node. Communication happens via the `o2-dpl-raw-proxy` and the `o2-dpl-output-proxy`.
To set up such a workflow, a couple of points must be followed:
- There are 2 different shell scripts, one for the "reco" part running on each EPN, and one for the calibration aggregator "calib" part on the calibration node. There may be more than one aggregator in the topology, in that case it is one *reco* script and multiple *calib* scripts.
- The o2-dpl-raw-proxy on a calib aggrgator workflow MUST NOT use the `--inject-missing-data` command line argument! (This is only for input proxies receiving data from DataDistribution!)
- The *reco* script must contain an `o2-dpl-output-proxy` to send the output and each calib script must contain an `o2-dpl-raw-proxy` for the input.
- Each of the input "raw" proxies must be assigned a unique name via the `--proxy-name [NAME]` option. Note that the *reco* script also contains an input raw proxy, with the default name `readout-proxy`.
- The channel-name of each input proxy must match the proxy name. The *calib* input proxies' channels must use `method=bind`. The output proxies must use `method=connect` and the channel name must match the name of the input proxy they are connecting to.
- The `dataspec` of the proxies is configured in the same way as for the `readout-proxy` and the specs must be equal for corresponding input and output proxies.
- The channels of input and output proxies (except for the *reco* `readout-proxy`) must be configured without address!
- The output proxies must use the command line option `--proxy-channel-name [name]` with `name` being the configured channel name.
- To run on the EPN, the *calib* input proxies of the aggregatornodes must have the command line option `--network-interface ib0` (this ensures data is sent via InfiniBand not via Ethernet). Note that this is only for the aggregator node, not for the normal processing part!

Please note that for a calibration workflow the number of cores used by the workflow must be specified, and the memory limit is derrived from the number of cores (~4 GB per core, with some margin reserved for the system).
If `SHMSIZE` is set for the workflow, it must also fit in this memory constraint. A rough guideline is 50% of the available memory. If it is not set, it defaults to 2 GB pre core.
Please make to request a reasonable number of cores, since there are only 4 calibration nodes which are shared among all workflows.

For an example, chek the calibration workflows [here](testing/examples)

*NOTE* For reference, to run a workflow with calib aggregator on the EPN with AliECS, currently a node from the `calib` zone must be requested, by setting `odc_resources` to `[ {"zone":"online", "n":10}, {"zone":"calib", "n":1 } ]` (adjust the `10` to the number of required reconstruction nodes). This will be improved later and then this extra setting will not be needed anymore.

# The parser script:
The **parser** is a simple python script that parses a *topology description* and generates the DDS XML file with the *full topology*. To do so, it runs all the DPL workflows with the `--dds ${WORKFLOWMODE_FILE}` option and then uses the `odc-topo-epn` tool to merge the *partial topology*  into the final *full topology*.
The *parser* is steered by some command line options and by some environment variables (note that the env variables get also passed through to the workflows).
- The *parser* needs a DataDistribution topology file. Example files are shipped with the parser in the `tools/datadistribution_workflows` folder for: just discarding the TF, store the TF to disk, forward the TF to DPL processing (what we need for a DPL workflow), and forward to processing while storing to disk in parallel.
- *Parser* command line options:
  - The parser is supposed to be executed from the `DATA` folder of the `O2DPG` repository.
  - The syntax is:
```
[ENV_VARIABLES] ./tools/parse [DESCRIPTION_LIBRARY_FILE] [TOPOLOGY_NAME] [OUTPUT_NAME]
```
  - In the above example, this could be:
```
DDWORKFLOW=tools/datadistribution_workflows/dd-processing.xml WORKFLOW_DETECTORS=TPC,ITS WORKFLOW_DETECTORS_QC=TPC WORKFLOW_DETECTORS_CALIB=ALL ./tools/parse topologies.desc demo-full-topology /tmp/output.xml
```
- The following environment variables steer the *Parser*:
  - `$FILEWORKDIR`: This variable must be set and is used by the workflows to specify where all required files (grp, geometry, dictionaries, etc) are located.
  - `$EPNSYNCMODE`: If set the parser assumes it is running on the EPN for synchronous processing. If so it will automatically load the modules specified in the topology description. This variable is further used by the workflows themselves, e.g. to activate the InfoLogger and the Metrics monitoring, and to fetch QC JSONs from consul.
  - `$INRAWCHANNAME`: Propagated to the workflow, defines the raw FMQ channel name used for the communication with DataDistribution.
  - `$RECO_NUM_NODES_OVERRIDE`: Overrides the number of nodes used for reconstruction (empty or 0 to disable)
  - `$DDMODE`: How to operate DataDistribution: **discard** (build TF and discard them), **disk** (build TF and store to disk), **processing** (build TF and run DPL workflow on TF data), **processing-disk** (both store TF to disk and run processing).
  - `$DDWORKFLOW`: (*alternative*): Explicit path to the XML file with the partial workflow for *DataDistribution*.
  - `$WORKFLOWMODE`: Can be set to print. In that case the parser will not create the DDS topology output, but the list of shell commands to start to run the workflows locally.
- When run on the EPN farm for synchronous processing (indicated by the `$EPNSYNCMODE=1` variable), the *parser* will automaticall `module load` the modules specified in the *topology description*. Otherwise the user must load the respective O2 / QC version by himself.
- The parser exports the env variable `$RECO_NUM_NODES_WORKFLOW` that contains on how many nodes the workflow will be running when running the workflow script. This can be used to tune the process multiplicities.

# Creating a full topology DDS XML file manually using the parser:
- **NOTE** This is only for reference, or for running on a private PC. For creating XMLs on the EPN, please refer to [here](#Quick-guide-to-create-and-deploy-detector-workflow).
- Check out the `O2DPG` repository, adjust the workflows and topology description in the `DATA` folder to your need.
- Open a shell and go to the `DATA` folder of `O2DataProcessing`.
- Make sure the `odc-topo-epn` is in your path (e.g. `module load ODC` / `alienv enter ODC/latest`).
- Set the required environment variables, e.g.
```
FILEWORKDIR=/home/epn/odc/files EPNSYNCMODE=1 DDWORKFLOW=tools/datadistribution_workflows/dd-processing.xml INRAWCHANNAME=tf-builder-pipe-0 WORKFLOW_DETECTORS=TPC,ITS,TRD,TOF,FT0
```
- If you are not on the EPN farm and have NOT set `EPNSYNCMODE=1`: Load the required modules for O2 / QC (`alienv load O2PDPSuite/latest`)
- Run the parser, e.g.:
```
./tools/parse production/production.desc synchronous-workflow /tmp/dds-topology.xml
```
- Now you can use `/tmp/dds-topology.xml` to start the workflow via DDS.

# Quick guide to create and deploy detector workflow:
- **Note**: Not all configuration features (see [here](#Configuring-and-selecting-workflow-in-AliECS)) are available in AliECS yet, thus this guide shows only how to create the XML file for DDS. That XML file must then still be entered in the AliECS GUI as topology. While this option will remain also for the future, i.e. you will always be able to create XMLs manually and then run them, the default way will become that the options are configured in AliECS and then the XML is created on-the-fly.
- **Note** the topology must be created on an epn, which has the O2 version installed, which is requested by the topology. In principle any node should do since the installed O2 version should be the same on all nodes.
- Check out the [O2DPG](https://github.com/AliceO2Group/O2DPG) repository to your home folder on the EPN (`$HOME` in the following).
- Copy the content of `O2DPG/DATA/testing/examples` (description library file `workflows.desc` and workflow script `example-workflow.sh`) to another place INSIDE the repository, usually under `testing/detectors/[DETECTOR]` or `testing/private/[USERNAME]`.
- Edit the workflow script to your needs, adjust / rename the workflow in the description library file.
  - See [here](#Topology-descriptions) for the syntax of the library file (in case it is not obvious), and make sure not to override the listed protected environment variables. The workflow script is just a bash script that starts a DPL workflow, which must have the `--dds ${WORKFLOWMODE_FILE}` parameter in order to create a partial DDS topology.
  - Make sure that the workflow script fullfils the [requirements](#Workflow-requirements), particularly that it respects the requested environment variables.
  - Use `O2PDPSuite` for the modules to load to have the latest installed version, or `O2PDPSuite/[version]` to specify a version.
- Create an empty folder in your `$HOME` on the EPN, in the following `$HOME/test`.
- Copy the topology generation template from `O2DPG/DATA/tools/epn/run.sh` to your folder.
  - N.B.: this template script contains all the options that will be provided via AliECS automatically as environment variables. Eventually this file will not be needed any more, but the XML file will be automatically created from the AliECS GUI.
- Edit your copy of the `run.sh` file. The following parameters are relevant for you:
  - Leave the `GEN_TOPO_HASH` setting to 0 and use the respective section of the file, the outcommented part with `GEN_TOPO_HASH=1` will become relevant once AliECS is updated.
  - Place the path to the `DATA` folder of your copy of `O2DPG` in `GEN_TOPO_SOURCE` and put your newly created description library file and the workflow in there as `GEN_TOPO_LIBRARY_FILE` and `GEN_TOPO_WORKFLOW_NAME`.
  - If you want to specify the number of reconstruction nodes to use here, you can use `RECO_NUM_NODES_OVERRIDE`, otherwise the default from your description library file will be used (leave it empty or `=0`).
  - The `WORKFLOW_DETECTORS` and `WORKFLOW_PARAMETERS` options are optional, your workflow does not need to use them. They are mostly for more complex workflows, so you can ignore them for now`.
  - Leave `DDMODE=processing` in order to run a workflow.
  - `NHBPERTF` will be set by AliECS later automatically, no need to change them.
  - Change the output filename to a file somewhere in your `$HOME`, the default is `$HOME`/gen_topo_output.xml. This will be the file you have to enter in AliECS as topology.
- Run `run.sh`
- Put the output file (default is `$HOME/gen_topo_output.xml`) as EPN DDS topology in the AliECS GUI.

When adapting your workflow, please try to follow the style of the existing workflows. The [testing/examples/example-workflow.sh](testing/examples/example-workflow.sh) should be a simple start, for a more complex example you can have a look at [testing/detectors/TPC/tpc-workflow.sh](testing/detectors/TPC/tpc-workflow.sh), and as a fulll complex example of a global workflow please look at [production/full-system-test/dpl-workflow_local.sh](production/full-system-test/dpl-workflow_local.sh)

For reference, the `run.sh` script internally uses the `parser` to create the XML file, it essentially sets some environment variables and then calls the *parser*  with all options set. So in principle, you can also use the *parser* directly to create the workflow as described [here](Creating-a-full-topology-DDS-XML-file-manually).

For comparison, see my console output below:
```
[drohr@head ~]$ ssh epn245
Activate the web console with: systemctl enable --now cockpit.socket

Last login: Wed Sep  1 19:11:47 2021 from 10.162.32.2
[drohr@epn245 ~]$ git clone https://github.com/AliceO2Group/O2DPG
Cloning into 'O2DPG'...
remote: Enumerating objects: 182, done.
remote: Counting objects: 100% (182/182), done.
remote: Compressing objects: 100% (112/112), done.
remote: Total 182 (delta 64), reused 135 (delta 48), pack-reused 0
Receiving objects: 100% (182/182), 36.42 KiB | 5.20 MiB/s, done.
Resolving deltas: 100% (64/64), done.
[drohr@epn245 ~]$ cd O2DPG/DATA/testing/
[drohr@epn245 testing]$ mkdir -p private/drohr
[drohr@epn245 testing]$ ls examples/
example-workflow.sh  workflows.desc       
[drohr@epn245 testing]$ cp examples/* private/drohr/
[drohr@epn245 testing]$ vi private/drohr/workflows.desc
[drohr@epn245 testing]$ mv private/drohr/example-workflow.sh private/drohr/my-workflow.sh
[drohr@epn245 testing]$ vi private/drohr/my-workflow.sh
[drohr@epn245 testing]$ cat private/drohr/workflows.desc
drohr-workflow: "O2PDPSuite" reco,10,10,"SHMSIZE=128000000000 testing/private/drohr/my-workflow.sh"
[drohr@epn245 testing]$ mkdir ~/test
[drohr@epn245 testing]$ cd ~/test
[drohr@epn245 test]$ cp ~/O2DPG/DATA/tools/epn/run.sh .
[drohr@epn245 test]$ vi run.sh
[drohr@epn245 test]$ cat run.sh
#!/bin/bash

export DDMODE=processing                                             # DataDistribution mode - possible options: processing, disk, processing-disk, discard

# Use these settings to fetch the Workflow Repository using a hash / tag
#export GEN_TOPO_HASH=1                                              # Fetch O2DPG repository using a git hash
#export GEN_TOPO_SOURCE=v0.5                                         # Git hash to fetch

# Use these settings to specify a path to the workflow repository in your home dir
export GEN_TOPO_HASH=0                                               # Specify path to O2DPG repository
export GEN_TOPO_SOURCE=/home/drohr/O2DPG/DATA                        # Path to O2DPG repository

export GEN_TOPO_LIBRARY_FILE=testing/private/drohr/workflows.desc    # Topology description library file to load
export GEN_TOPO_WORKFLOW_NAME=drohr-workflow                         # Name of workflow in topology description library
export WORKFLOW_DETECTORS=ALL                                        # Optional parameter for the workflow: Detectors to run reconstruction for (comma-separated list)
export WORKFLOW_DETECTORS_QC=                                        # Optional parameter for the workflow: Detectors to run QC for
export WORKFLOW_DETECTORS_CALIB=                                     # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_PARAMETERS=                                          # Additional paramters for the workflow
export RECO_NUM_NODES_OVERRIDE=0                                     # Override the number of EPN compute nodes to use (default is specified in description library file)
export NHBPERTF=256                                                  # Number of HBF per TF

/opt/alisw/el9/GenTopo/bin/gen_topo.sh > $HOME/gen_topo_output.xml
[drohr@epn245 test]$ ./run.sh
Loading ODC/0.36-1
  Loading requirement: BASE/1.0 GCC-Toolchain/v10.2.0-alice2-3 fmt/7.1.0-10 FairLogger/v1.9.1-7 zlib/v1.2.8-8 OpenSSL/v1.0.2o-9 libpng/v1.6.34-9 sqlite/v3.15.0-2 libffi/v3.2.1-2 FreeType/v2.10.1-8 Python/v3.6.10-12 Python-modules/1.0-16 boost/v1.75.0-13 ZeroMQ/v4.3.3-6 ofi/v1.7.1-8 asio/v1.19.1-2 asiofi/v0.5.1-2 DDS/3.5.16-5 FairMQ/v1.4.40-4
    protobuf/v3.14.0-9 c-ares/v1.17.1-5 re2/2019-09-01-11 grpc/v1.34.0-alice2-1
Using topology drohr-workflow of library testing/private/drohr/workflows.desc
Found topology drohr-workflow - ['drohr-workflow:', 'O2PDPSuite', 'reco,10,10,SHMSIZE=128000000000 testing/private/drohr/my-workflow.sh']
Loading module DataDistribution
Loading DataDistribution/v1.0.6-2
  Loading requirement: libInfoLogger/v2.1.1-5 Ppconsul/v0.2.2-5 utf8proc/v2.6.1-3 lzma/v5.2.3-6 Clang/v12.0.1-2 lz4/v1.9.3-9 arrow/v5.0.0-alice1-4 GSL/v1.16-8 libxml2/v2.9.3-8 ROOT/v6-24-02-12 FairRoot/v18.4.2-7 Vc/1.4.1-11 Monitoring/v3.8.7-4 Configuration/v2.6.2-4 Common-O2/v1.6.0-13 ms_gsl/3.1.0-5 GLFW/3.3.2-10 libuv/v1.40.0-10
    DebugGUI/v0.5.6-6 libjalienO2/0.1.3-5 FFTW3/v3.3.9-6 O2/nightly-20210831-0930-1
Loading module QualityControl
Loading QualityControl/v1.27.0-1
  Loading requirement: Control-OCCPlugin/v0.26.3-1 VecGeom/89a05d148cc708d4efc2e7b0eb6e2118d2610057-40
Adding reco workflow ( 10 - 10 nodes): SHMSIZE=128000000000 testing/private/drohr/my-workflow.sh
Running DPL command SHMSIZE=128000000000 testing/private/drohr/my-workflow.sh | grep -v "^\[INFO" > /tmp/o2_workflowmfld0a0n/wf2.dds && [ `grep "^\[" /tmp/o2_workflowmfld0a0n/wf2.dds | wc -l` == 0 ]
Creating reconstruction collection...
New DDS topology successfully created and saved to a file "/home/drohr/gen_topo/test/output.xml"
DDS topology "topology" successfully opened from file "/home/drohr/gen_topo/test/output.xml"
Done
[drohr@epn245 test]$ cat $HOME/gen_topo_output.xml
<?xml version="1.0" encoding="utf-8"?>
[...]
</topology>
```

For reference, here is the creation of the XML for the full synchronous processing workflow:
```
[drohr@epn245 test]$ cat run.sh
#!/bin/bash

export DDMODE=processing                                             # DataDistribution mode - possible options: processing, disk, processing-disk, discard

# Use these settings to fetch the Workflow Repository using a hash / tag
#export GEN_TOPO_HASH=1                                              # Fetch O2DPG repository using a git hash
#export GEN_TOPO_SOURCE=v0.5                                         # Git hash to fetch

# Use these settings to specify a path to the workflow repository in your home dir
export GEN_TOPO_HASH=0                                               # Specify path to O2DPG repository
export GEN_TOPO_SOURCE=/home/drohr/O2DPG/DATA                        # Path to O2DPG repository

export GEN_TOPO_LIBRARY_FILE=production/production.desc              # Topology description library file to load
export GEN_TOPO_WORKFLOW_NAME=synchronous-workflow                   # Name of workflow in topology description library
export WORKFLOW_DETECTORS=ALL                                        # Optional parameter for the workflow: Detectors to run reconstruction for (comma-separated list)
export WORKFLOW_DETECTORS_QC=                                        # Optional parameter for the workflow: Detectors to run QC for
export WORKFLOW_DETECTORS_CALIB=                                     # Optional parameters for the workflow: Detectors to run calibration for
export WORKFLOW_PARAMETERS=EVENT_DISPLAY,CTF,GPU                     # Additional paramters for the workflow
export RECO_NUM_NODES_OVERRIDE=0                                     # Override the number of EPN compute nodes to use (default is specified in description library file)
export NHBPERTF=256                                                  # Number of HBF per TF

/opt/alisw/el9/GenTopo/bin/gen_topo.sh > $HOME/gen_topo_output.xml
[drohr@epn245 test]$ ./run.sh
Loading ODC/0.36-1
  Loading requirement: BASE/1.0 GCC-Toolchain/v10.2.0-alice2-3 fmt/7.1.0-10 FairLogger/v1.9.1-7 zlib/v1.2.8-8 OpenSSL/v1.0.2o-9 libpng/v1.6.34-9 sqlite/v3.15.0-2 libffi/v3.2.1-2 FreeType/v2.10.1-8 Python/v3.6.10-12 Python-modules/1.0-16 boost/v1.75.0-13 ZeroMQ/v4.3.3-6 ofi/v1.7.1-8 asio/v1.19.1-2 asiofi/v0.5.1-2 DDS/3.5.16-5 FairMQ/v1.4.40-4
    protobuf/v3.14.0-9 c-ares/v1.17.1-5 re2/2019-09-01-11 grpc/v1.34.0-alice2-1
Using topology synchronous-workflow of library production/production.desc
Found topology synchronous-workflow - ['synchronous-workflow:', 'O2PDPSuite', 'reco,128,128,EXTINPUT=1 SYNCMODE=1 NUMAGPUIDS=1 NUMAID=0 SHMSIZE=128000000000 EPNPIPELINES=1 SHMTHROW=0 SEVERITY=warning production/full-system-test/dpl-workflow_local.sh', 'reco,128,128,EXTINPUT=1 SYNCMODE=1 NUMAGPUIDS=1 NUMAID=1 SHMSIZE=128000000000 EPNPIPELINES=1 SHMTHROW=0 SEVERITY=warning production/full-system-test/dpl-workflow_local.sh']
Loading module DataDistribution
Loading DataDistribution/v1.0.6-2
  Loading requirement: libInfoLogger/v2.1.1-5 Ppconsul/v0.2.2-5 utf8proc/v2.6.1-3 lzma/v5.2.3-6 Clang/v12.0.1-2 lz4/v1.9.3-9 arrow/v5.0.0-alice1-4 GSL/v1.16-8 libxml2/v2.9.3-8 ROOT/v6-24-02-12 FairRoot/v18.4.2-7 Vc/1.4.1-11 Monitoring/v3.8.7-4 Configuration/v2.6.2-4 Common-O2/v1.6.0-13 ms_gsl/3.1.0-5 GLFW/3.3.2-10 libuv/v1.40.0-10
    DebugGUI/v0.5.6-6 libjalienO2/0.1.3-5 FFTW3/v3.3.9-6 O2/nightly-20210831-0930-1
Loading module QualityControl
Loading QualityControl/v1.27.0-1
  Loading requirement: Control-OCCPlugin/v0.26.3-1 VecGeom/89a05d148cc708d4efc2e7b0eb6e2118d2610057-40
Adding reco workflow ( 128 - 128 nodes): EXTINPUT=1 SYNCMODE=1 NUMAGPUIDS=1 NUMAID=0 SHMSIZE=128000000000 EPNPIPELINES=1 SHMTHROW=0 SEVERITY=warning production/full-system-test/dpl-workflow_local.sh
Running DPL command EXTINPUT=1 SYNCMODE=1 NUMAGPUIDS=1 NUMAID=0 SHMSIZE=128000000000 EPNPIPELINES=1 SHMTHROW=0 SEVERITY=warning production/full-system-test/dpl-workflow_local.sh | grep -v "^\[INFO" > /tmp/o2_workflowkxkzei9w/wf2.dds && [ `grep "^\[" /tmp/o2_workflowkxkzei9w/wf2.dds | wc -l` == 0 ]
Adding reco workflow ( 128 - 128 nodes): EXTINPUT=1 SYNCMODE=1 NUMAGPUIDS=1 NUMAID=1 SHMSIZE=128000000000 EPNPIPELINES=1 SHMTHROW=0 SEVERITY=warning production/full-system-test/dpl-workflow_local.sh
Running DPL command EXTINPUT=1 SYNCMODE=1 NUMAGPUIDS=1 NUMAID=1 SHMSIZE=128000000000 EPNPIPELINES=1 SHMTHROW=0 SEVERITY=warning production/full-system-test/dpl-workflow_local.sh | grep -v "^\[INFO" > /tmp/o2_workflowkxkzei9w/wf3.dds && [ `grep "^\[" /tmp/o2_workflowkxkzei9w/wf3.dds | wc -l` == 0 ]
Creating reconstruction collection...
New DDS topology successfully created and saved to a file "/home/drohr/gen_topo/test/output.xml"
DDS topology "topology" successfully opened from file "/home/drohr/gen_topo/test/output.xml"
Done
```

# Creating a script to run a workflow locally
- The workflow scripts should support the `WORKFLOWMODE=print` option, in which case they do not start the workflow, but print the command line to start the workflow.
- The parser also supports `WORKFLOWMODE=print` and will in that case write the command line to the output file, in case the full topology will be composed of multiple commands, it will write all command lines.
- Finally the `run.sh` wrapper to simulate the AliECS GUI does support the mode `WORKFLOWMODE=print`. In order to run it locally on your laptop at home, please also set `GEN_TOPO_RUN_HOME=1`.
