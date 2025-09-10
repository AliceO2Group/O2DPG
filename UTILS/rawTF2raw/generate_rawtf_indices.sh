#!/bin/bash

# source $O2DPG_ROOT/UTILS/rawTF2raw/generate_rawtf_indices.sh

print_help() {
  cat <<EOF
  Script to source functions to extract list of consecutive timeframes from a list of rawtf files and create the corresponding raw data files for the selected TFs

  Functions:
    - check_tfs_per_file
      - print the average number of TFs per file from a small subset of rawtf files from the input file list
    - sort_tfs
      - sort the TFs from the input file list in continuous order and save the corresponding timeslice ids in the order they appear in the input file list
      - if nBlocks (parameter 5) is not 0, then there is an additional check on the number of requested inputs defined by nBlocks
      - outputs:
        - tf-reader_*.log: full log output from o2-raw-tf-reader-workflow which is used to grep for the timeslice and tfCounter ids
        - tfids_*.txt: list with timeslice and tfCounter ids, sorted by tfCounter
        - timeslices_*.txt: sorted list of \$nTFs timeslice indices to be used for raw data creation
    - create_raw_files
      - use sorted list of timeslice ids created with sort_tfs as input to create *.raw files for those timeslices
      - the final command (for reference) and the full log output is written to \$outputDir.log

  Parameters:
    - param1: rawtf input file list
    - param2: output directory
    - param3: number of TFs to process
    - param4: tfCounter id of first TF to process 
    - param5: number of Blocks to be expected per TF to select only TFs with all inputs / detectors present
          - if number of inputs is irrelevant, it can be set to 0 to be ignored
  
  Example usage:

  source $O2DPG_ROOT/UTILS/rawTF2raw/generate_rawtf_indices.sh rawtflist_LHC25ab_563041.txt 2025-05-19-pp-750khz-replay-LHC25ab-563041 125 3500 14
  sort_tfs
  create_raw_files

EOF

  return
}
[[ $# == 0 ]] && print_help

# input parameters
rawtfFileList=$1
outputDir=$2
nTFs=$3
firstTF=${4:-3500}
nBlocks=${5:-0}

# add # TFs to output directory name
outputDir=$(echo $outputDir | sed "s/$/-${nTFs}tf/g")

# rawtfFileList=rawtflist_LHC24ak_553146.txt
# outputDir=$(date +"%Y-%m-%d")-pp-500kHz-replay-LHC24ak_553146_500tf
# nTFs=500
# firstTF=3500
# nBlocks=15

# output file names
tfreader_log=tf-reader_$(echo ${rawtfFileList} | sed -e 's/.txt//g' -e 's/rawtflist_//g').log
tfs_sorted=tfids_$(echo ${rawtfFileList} | sed -e 's/.txt//g' -e 's/rawtflist_//g')_sorted.txt
timeslices_sorted=timeslices_$(echo ${rawtfFileList} | sed -e 's/.txt//g' -e 's/rawtflist_//g')_sorted.txt

# export env variables
## print prcoessing time info
export DPL_REPORT_PROCESSING=1

# sourced functions
check_tfs_per_file() {
  nFiles=${1:-10}
  nTFs=$(o2-raw-tf-reader-workflow --raw-only-det all --shm-segment-size 16000000000 --input-data $(cat ${rawtfFileList} | head -n ${nFiles} | sed -z 's/\n/,/g') -b --run | grep 'loops were sent' | awk -F' ' '{print $3}')
  echo "${nTFs} TFs found in ${nFiles} files: $(echo $((nTFs * 10000 / nFiles)) | sed -e 's/....$/.&/;t' -e 's/.$/.0&/') TFs per file"
}

sort_tfs() {
  [[ ! -f ${tfreader_log} ]] && time o2-raw-tf-reader-workflow --raw-only-det all --shm-segment-size 16000000000 --input-data ${rawtfFileList} -b --run > ${tfreader_log}
  if [ "0$nBlocks" -eq "00" ]; then
    grep 'tf-reader.*Done processing' ${tfreader_log} | sed 's/,//g' | awk '{print $5,$6,$7,$9}' | sort -t ':' -k 3 -h >${tfs_sorted}
  else
    grep 'tf-reader' ${tfreader_log} | grep -v -e 'Executing sh' -e 'Resuming reading' -e 'Processing file' | grep "Block:${nBlocks}" -A 6 | grep 'Done processing' | sed 's/,//g' | awk '{print $5,$6,$7,$9}' | sort -t ':' -k 3 -h >${tfs_sorted}
  fi
  firstTFtmp=${firstTF}
  while true; do
    firstLine=$(grep -nr tfCounter:${firstTFtmp} ${tfs_sorted} | awk -F ':' '{print $1}')
    [[ ! -z ${firstLine} ]] && break
    firstTFtmp=$((firstTFtmp+1))
  done
  tail -n +${firstLine} ${tfs_sorted} | head -n ${nTFs} | awk '{print $1}' | sort -V | sed -z -e 's/timeslice://g ;  s/\n/,/g ; s/,$//g' >${timeslices_sorted}
}

# creation of raw data
create_raw_files() {
  mkdir -p ${outputDir}
  echo "LID=\"$(cat ${timeslices_sorted})\"" | tee ${outputDir}.log
  LID=$(cat ${timeslices_sorted})
  echo "o2-raw-tf-reader-workflow --raw-only-det all  --shm-segment-size 16000000000  --input-data ${rawtfFileList} --select-tf-ids " '$LID' " | o2-raw-data-dump-workflow --tof-input-uncompressed  --shm-segment-size 16000000000 --fatal-on-deadbeef --output-directory  ${outputDir} --dump-verbosity 1 --run | tee -a ${outputDir}.log" | tee -a ${outputDir}.log
  o2-raw-tf-reader-workflow --raw-only-det all --shm-segment-size 16000000000 --input-data ${rawtfFileList} --select-tf-ids "$LID" | o2-raw-data-dump-workflow --tof-input-uncompressed --shm-segment-size 16000000000 --fatal-on-deadbeef --output-directory ${outputDir} --dump-verbosity 1 --run | tee -a ${outputDir}.log
}
