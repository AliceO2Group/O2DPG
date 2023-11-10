#!/usr/bin/env bash

# Make common arguments and helper functions such as add_W available
source common/setenv.sh
source common/getCommonArgs.sh
source common/gen_topo_helper_functions.sh


# Define input data required by DPL (in this case all RAWDATA from TRD)
PROXY_INSPEC="A:TRD/RAWDATA;dd:FLP/DISTSUBTIMEFRAME/0;eos:***/INFORMATION"

# Allow for setting external options

: ${TRD_N_READERS:=16}
: ${TRD_N_ENCODER:=4}

: ${EPN2EOS_METAFILES_DIR:="/data/epn2eos_tool/epn2eos"}
: ${CTF_DIR:="/data/tf/compressed"}
: ${CALIB_DIR:="/data/calibration"}

: ${RANS_OPT:="--ans-version 1.0 --ctf-dict none"}

: ${CTF_MINSIZE:="10000000000"}       # accumulate CTFs until file size reached
: ${CTF_MAX_PER_FILE:="40000"}        # but no more than given number of CTFs per file
: ${CTF_FREE_DISK_WAIT:="10"}         # if disk on EPNs is close to full, wait X seconds before retrying to write
: ${CTF_MAX_FREE_DISK_WAIT:="600"}    # if not enough disk space after this time throw error
: ${CTF_OUTPUT_TYPE:="ctf"}

CTF_CONFIG="--report-data-size-interval 1000"
CTF_CONFIG+=" --output-dir $CTF_DIR --output-type $CTF_OUTPUT_TYPE --min-file-size $CTF_MINSIZE --max-ctf-per-file ${CTF_MAX_PER_FILE} --onlyDet TRD --meta-output-dir $EPN2EOS_METAFILES_DIR"
CTF_CONFIG+=" --require-free-disk 53687091200 --wait-for-free-disk $CTF_FREE_DISK_WAIT --max-wait-for-free-disk $CTF_MAX_FREE_DISK_WAIT"


# Start with an empty workflow
WORKFLOW=
add_W o2-dpl-raw-proxy "--dataspec \"$PROXY_INSPEC\" --inject-missing-data --readout-proxy \"--channel-config \\\"name=readout-proxy,type=pull,method=connect,address=ipc://@tf-builder-pipe-0,transport=shmem,rateLogging=1\\\"\"" "" 0
add_W o2-trd-datareader "--disable-root-output --pipeline trd-datareader:$TRD_N_READERS"
add_W o2-trd-kr-clusterer "--disable-root-input --meta-output-dir $EPN2EOS_METAFILES_DIR --output-dir $CALIB_DIR --autosave-interval 105000 --pipeline trd-kr-clusterer:8"
if workflow_has_parameter QC && has_detector_qc TRD; then
  add_QC_from_consul "/o2/components/qc/ANY/any/trd-full-qcmn-test" "--local --host epn -b"
fi
if workflow_has_parameter CTF; then
  add_W o2-trd-entropy-encoder-workflow "$RANS_OPT --mem-factor ${TRD_ENC_MEMFACT:-1.5} --pipeline trd-entropy-encoder:$TRD_N_ENCODER"
  add_W o2-ctf-writer-workflow "$CTF_CONFIG"
fi

# Finally add the o2-dpl-run workflow manually, allow for either printing the workflow or creating a topology (default)
WORKFLOW+="o2-dpl-run $GLOBALDPLOPT $ARGS_ALL"
[[ $WORKFLOWMODE != "print" ]] && WORKFLOW+=" --${WORKFLOWMODE} ${WORKFLOWMODE_FILE:-}"
[[ $WORKFLOWMODE == "print" || "${PRINT_WORKFLOW:-}" == "1" ]] && echo "#Workflow command:\n\n${WORKFLOW}\n" | sed -e "s/\\\\n/\n/g" -e"s/| */| \\\\\n/g" | eval cat $( [[ $WORKFLOWMODE == "dds" ]] && echo '1>&2')
if [[ $WORKFLOWMODE != "print" ]]; then eval $WORKFLOW; else true; fi
