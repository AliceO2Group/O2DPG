#!/bin/bash

if [[ -z ${O2DPG_ROOT+x} ]] ; then
    echo "O2DPG is not loaded, probably other packages are missing as well in this environment."
    exit 1
fi

DATE=$(date '+%Y-%m-%d_%H-%M')
OUTPUT=rel_val_${DATE}
LOGFILE=${OUTPUT}/"rel_val.log"

function wait_for_jobs()
{
    local n_parallel=${1:-5}
    local sleep_time=${2:-2}
    while true
    do
        n_packing=$(jobs | grep "include-patterns" | grep "Running" | wc -l )
        if (( $n_packing >= ${n_parallel} ))
        then
            sleep $sleep_time
        else
            break
        fi
    done
}

rel_val_qc()
{
    local file1=${1}
    local file2=${2}
    local label1=${3}
    local label2=${4}
    local output=${OUTPUT}/QC
    local output_all=${output}/all
    local output_all_bad=${output_all}_BAD
    local output_det="${output}/det"
    rm -r ${output} 2>/dev/null

    echo "Full RelVal to ${output_all}" | tee -a ${LOGFILE}
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i ${file1} -j ${file2} -o ${output_all} --labels ${label1} ${label2} 2>&1 | tee -a ${LOGFILE}
    echo "Extract BAD from ${output_all} and write to ${output_all_bad}" | tee -a ${LOGFILE}
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect --path ${output_all} --output ${output_all_bad} --interpretations BAD >> ${LOGFILE} 2>&1
    echo "RelVal per detector..." | tee -a ${LOGFILE}
    for det in CPV EMC FDD FT0 FV0 GLO ITS MCH MFT MID PHS TOF TPC TRD ZDC ; do
        echo "...for ${det} to ${output_det}_${det}, checking for include pattern int_${det}_ ; the latter might need to be changed depending on the internal file structure of the QC ROOT file" | tee -a ${LOGFILE}
        ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect --path ${output_all} --output ${output_det}_${det} --include-patterns "int_${det}_" >> ${LOGFILE} 2>&1 &
        wait_for_jobs 3
    done
    wait_for_jobs 1
}

rel_val_aod()
{
    local file1=${1}
    local file2=${2}
    local label1=${3}
    local label2=${4}
    local output=${OUTPUT}/AOD
    local output_all=${output}/all
    local output_all_bad=${output_all}_BAD
    rm -r ${output} 2>/dev/null

    echo "Full RelVal to ${output_all}" | tee -a ${LOGFILE}
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py rel-val -i ${file1} -j ${file2} -o ${output_all} --labels ${label1} ${label2} 2>&1 | tee -a ${LOGFILE}
    echo "Extract BAD from ${output_all} and write to ${output_all_bad}" | tee -a ${LOGFILE}
    ${O2DPG_ROOT}/RelVal/o2dpg_release_validation.py inspect --path ${output_all} --output ${output_all_bad} --interpretations BAD 2>&1 | tee -a ${LOGFILE}
}

print_help()
{
    echo "Usage:"
    echo "run_data_rel_val.sh [--qc <QCfile1> <QCfile2>] [--aod <AODfile1> <AODfile2>] [--labels <label1> <label2>]"
}

# Files and labels
AOD1=
AOD2=
QC1=
QC2=
LABEL1="label1"
LABEL2="label2"

while [[ $# -gt 0 ]]; do
    key="$1"

    case $key in
        --qc)
            shift
            QC1=${1}
            shift
            QC2=${1}
            shift
            ;;
        --aod)
            shift
            AOD1=${1}
            shift
            AOD2=${1}
            shift
            ;;
        --labels)
            shift
            LABEL1=${1}
            shift
            LABEL2=${1}
            shift
            ;;
        --help|-h)
            print_help
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument ${1}"
            print_help
            exit 1
            ;;
    esac
done

QC_RET=0
AOD_RET=0

mkdir ${OUTPUT} 2>/dev/null
echo "Do RelVal and output to ${OUTPUT}" | tee -a ${LOGFILE}

[[ "${QC1}" != "" && "${QC2}" != "" ]] && { rel_val_qc ${QC1} ${QC2} ${LABEL1} ${LABEL2} ; QC_RET=${?} ; } || { echo "No QC RelVal" | tee -a ${LOGFILE} ; }
[[ "${AOD1}" != "" && "${AOD2}" != "" ]] && { rel_val_aod ${AOD1} ${AOD2} ${LABEL1} ${LABEL2} ; AOD_RET=${?} ; } || { echo "No AOD RelVal" | tee -a ${LOGFILE} ; }

RET=$((QC_RET + AOD_RET))
echo "Exit with ${RET}" | tee -a ${LOGFILE}
exit ${RET}
