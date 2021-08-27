THis repository contains the PDP workflows to run on the EPN (in the future also on the FLP) and the parse script which parses the description files and creates the DDS XML files

**Terminology**
- A **workflow** refers to a single DPL workflow binary, or multiple workflows binaries merged with the `|` syntax, or a shell script starting such a workflow.
- A **full topology** refers to the final XML file that is passed to DDS to start up a processing chain for one single partition on the EPN.
- A **partial topology** is the XML file created by DPL with the `--dds` option.

**Folder structure**:
- **common** contains common scripts that can be used by all workflows, most importantly common environment variable scripts.
- **production** contains the production workflows for global runs, which are maintained by PDP experts.
- **tools** contains the **parser** script and auxiliary tools.
- **testing** contains scripts for tests / standalone runs maintained by detectors or privately.

**Topology descriptions and description library files**:
Another abstraction layer above the *workflows* are **topology descriptions**. The *parser* tool can generate the *full topology* XML file from such a *description*, using the `–dds` option of DPL and the `odc-topo-epn` tool. *Topology descriptions* are stored in **description library files** in the `O2DataProcessing` repository. A *description library file* can contain multiple *topology descriptions* each identified by a **topology name**

**Remarks**:
- The repository does not store *full topologies*, but they are created on the fly. Users can cache the resulting full topology XML files.
- The defaults (particularly also those set in the common environment files in the `common` folder) are tuned for running on a laptop / desktop.
- Workflows support 3 run modes selected via the `WORKFLOWMODE` env variable:
  - **run** (default): run the workflow
  - **print**: print the final workflow command to the console
  - **dds**: create a partial topology.

**Configuring / selecting workflow in AliECS**:
There are 3 ways foreseenm to configure the *full topology* in AliECS: (currently only the manual XML option exists)
- **hash of workflow repository**: In this mode, the following settings are configured in AliECS, and they uniquely identify a *full topology*. The *parser* will then create the final DDS XML file with the *full topology*:
  - A **commit hash** identifying a state of the `O2DataProcessing` repository (this can also be a tag, and in the case of production workflows it is required to be a tag).
  - The path of a **description library file** (relative path inside the `O2DataProcessing` repository).
  - The **workflow name** inside the *description library file*.
  - A **detector list**: comma-separated list of detectors participating in the run, defaulting to `ALL` for all detectors.
  - **workflow parameters**: text field passed to workflow as environment variable for additional options.
- **repository directory**: This is almost identical to the case above, but instead of the commit hash, there is the **repository path** specified, pointing to a checked out repository on the shared home folder in the EPN farm. The procedure is the same as before, the parser will create the full topology XML file from the specified workflow in the repository.
- **manual XML file**: In this mode the `O2DataProcessing` repository is not used at all, but the absolute path of a *full topology* XML file in the EPN's shared home folder is specified. Such an XML file must be prepared manually by the same means as the *parser* would usually do (see paragraph on manual XML file below).

**Topology descriptions**:
A *topology description* consists of
- A list of modules to load, both for generating the DDS XML file with DPL's `--dds` option and when running the workflow. It can either be a single module, or a space-separated list of modules in double-quotes. In particular, this setting identifies the O2 version. We provide the `O2PDPSuite` package, which has the same versions as O2 itself, and which contain also corresponding versions `DataDistribution` and `QualityControl`, thus it is usually sufficient to just load `O2PDPSuite/[version]`.
- A list of workflows, in the form of commands to run to create XML files by the `–dds` option. The command is executed with the `O2DataProcessing` path as working directory. The env options used to configure the workflow are prepended in normal shell syntax.
  - Each workflow is amended with the following parameters (the parameters stand in front of the workflow command, and are separated by commas without spaces, the workflow command must be in double-quotes):
    - Zone where to run the workflow (calib / reco)
    - For reco:
      - Number of nodes to run this workflow on
        - If a processor in the workflow needs to identify on which node it is running on, it can use the `$DDS_COLLECTION_INDEX` emvironment variable.
      - Minimum number of nodes required forthe workflow (in case of node failure)
        - In case the there are multiple workflows in the topology description, the largest number of nodes, and the largest minimum number of nodes are used.
    - For calib:
      - Number of physical cores to be reserved on the node to run the workflow.
      - Name of the calibration (used to set DDS properties which are used to make the reconstruction workflows connect to specific calibration workflows)
        - ODC/DDS allocates as many nodes as necessary to have sufficient CPU cores for the calibration workflows. The different calibration workflows may or may not run on the same node.

An example for the topology library file looks like:
topologies.txt
```
demo-full-topology: O2/nightly-20210801 reco,128,126,"SHMSIZE=320000000000 full-system-test/dpl-workflow.sh" calib,5,"SHMSIZE=2000000000 calibration/some-calib.sh" calib,20,"SHMSIZE=2000000000 calibration/other-calib.sh";
other-topology: O2/v1.0.0 reco,2,1,"tpc-test/tpc-standalone-test-1.sh"
```
AliECS-config:
```
commit=xxxx file=topologies.txt topology=demo-full-topology detectors="TPC,ITS" parameters=""
```
