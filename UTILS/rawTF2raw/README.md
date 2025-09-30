 The script `generate_rawtf_indices.sh` provides functions to extract a list of consecutive TFs form a list of `*rawtf*.tf` files and create the corresponding `*.raw` files, e.g. for REPLAY datasets at P2.

Input parameters for sourcing the script:
- param1: list with input `*rawtf*.tf` files; expected file name (for extraction of period and run number): rawtflist_<period>_<run number>.txt, e.g. rawtflist_LHC25ab_563041.txt
- param2: directory to store output `*.raw` files
- param3: number of TFs to store as `*.raw` files
- param4: tfCounter id of first TF to process, e.g. at least 3500 to skip ITS ROF rate ramp up
- param5: number of input Blocks to be expected per TF to select only TFs with all inputs / detectors present
      - if number of inputs is irrelevant, it can be set to 0 to be ignored

Available functions by sourcing the script:
- `check_tfs_per_file`
  - print the average number of TFs per file from a small subset of rawtf files from the input file list
- `sort_tfs`
  - sort the TFs from the input file list in continuous order and save the corresponding timeslice ids in the order they appear in the input file list
  - if nBlocks (parameter 5) is not 0, then there is an additional check on the number of requested inputs defined by nBlocks
  - outputs:
    - tf-reader_*.log: full log output from o2-raw-tf-reader-workflow which is used to grep for the timeslice and tfCounter ids
    - tfids_*.txt: list with timeslice and tfCounter ids, sorted by tfCounter
    - timeslices_*.txt: sorted list of \$nTFs timeslice indices to be used for raw data creation
- `create_raw_files`
  - use sorted list of timeslice ids created with sort_tfs as input to create *.raw files for those timeslices
  - the final command (for reference) and the full log output is written to \$outputDir.log

Example usage:
```
# source functions and set input / output parameters
# in this case: process 125 TFs, start at tfCounter id 3500, check `*rawtf*.tf` files for number of inputs and only use TFs with (in this case) 14 inputs to ensure all detectors from this run are present
source $O2DPG_ROOT/UTILS/rawTF2raw/generate_rawtf_indices.sh rawtflist_LHC25ab_563041.txt 2025-05-19-pp-750khz-replay-LHC25ab-563041 125 3500 14

# create input list of timeslice IDs to be processed for `*.raw` file creation (`timeslices_*.txt`)
# timeslice IDs from this list correspond to \$nTFs consecutive tfCounter ids
# intermediate outputs from o2-raw-tf-reader-workflow and the sorted list of all tfCounter ids will also be stored (`reader_*.log` and `tfids_*.txt`)
sort_tfs

# create `*.raw` files for timeslices in `timeslices_*.txt` created in the previous step
create_raw_files
```


