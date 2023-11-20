#!/bin/bash

[[ "${#}" != "2" ]] && { echo "ERROR: Need 2 files as arguments" ; exit 1 ; }

if [[ -z ${O2DPG_ROOT+x} ]] ; then
    echo_red "O2DPG is not loaded, probably other packages are missing as well in this environment."
else
    FILE1=${1}
    FILE2=${2}
    DATE=$(date '+%Y-%m-%d_%H-%M')
    OUTPUT=rel_val_${DATE}
    OUTPUT_ALL=${OUTPUT}/rel_val_all
    OUTPUT_ALL_BAD=${OUTPUT_ALL}_BAD
    OUTPUT_DET="${OUTPUT}/rel_val_det"
    rm -r ${OUTPUT} 2>/dev/null

    echo "Full RelVal to ${OUTPUT_ALL}"
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i ${FILE1} -j ${FILE2} -o ${OUTPUT_ALL} # --labels label1 label2
    echo "Extract BAD from ${OUTPUT_ALL} and write to ${OUTPUT_ALL_BAD}"
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect --path ${OUTPUT_ALL} --output ${OUTPUT_ALL_BAD} --interpretations BAD
    echo "RelVal per detector..."
    for det in CPV EMC FDD FT0 FV0 GLO ITS MCH MFT MID PHS TOF TPC TRD ZDC ; do
        echo "...for ${det} to ${OUTPUT_DET}_${det}, checking for include pattern int_${det}_ ; the latter might need to be changed depending on the internal file structure of the QC ROOT file"
        ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect --path ${OUTPUT_ALL} --output ${OUTPUT_DET}_${det} --include-patterns "int_${det}_"
    done
fi
