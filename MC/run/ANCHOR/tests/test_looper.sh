#!/bin/bash
# loops over all test cases and executes them

# Read the CSV file
INPUT_FILE="test_anchor_cases.csv"
TEMPLATE_FILE="test_anchor_2tag_template.sh"
OUTPUT_FILE="test_anchor_generated"

DAILYTAGTOTEST=${1:-O2sim::v20250804-1}

SITES_FILE="test_GRID_sites.dat"

WORKING_DIR="${PWD}/workdir_$(date +%s)_$RANDOM"
echo "WORKING DIR ${WORKING_DIR}"
mkdir -p ${WORKING_DIR}

INPUT_FILE_STRIPPED=${WORKING_DIR}/${INPUT_FILE}_clean

REQUIRE_STRING=""
{
  while read -r -a values; do
    if [ ! "${REQUIRE_STRING}" == "" ]; then
      REQUIRE_STRING="${REQUIRE_STRING} ||"
    fi
    REQUIRE_STRING="${REQUIRE_STRING} (other.CE == \"${values}\")"
  done
} < ${SITES_FILE}
REQUIRE_STRING="(${REQUIRE_STRING});"

echo "REQUIRE STRING ${REQUIRE_STRING}"

# strip comments from CSV file
grep -v '#' ${INPUT_FILE} > ${INPUT_FILE_STRIPPED}

# Read the header line and convert it into variable names
IFS=',' read -r -a headers < "$INPUT_FILE_STRIPPED"

# Replace placeholders in the header (e.g., %{VAR} → VAR)
for i in "${!headers[@]}"; do
    headers[$i]=$(echo "${headers[$i]}" | sed -E 's/#?%\{//;s/\}//g')
done

TOPWORKDIR=""

# Read and process each subsequent line
{
    read  # Skip the header line

    count=1  # Counter for output files
    datestring=$(date +"%Y%m%d_%H%M%S")
    while IFS=',' read -r -a values; do
        # Assign each value to its corresponding variable
        for i in "${!headers[@]}"; do
            declare "${headers[$i]}"="${values[$i]}"
        done

        PRODUCTION_TAG="2tagtest_${datestring}_${count}"
        # Example: Print assigned variables
        echo "SOFTWARETAG_SIM: $SOFTWARETAG_SIM"
        echo "SOFTWARETAG_ASYNC: $SOFTWARETAG_ASYNC"
        echo "PASSNAME: $PASSNAME"
        echo "COL_SYSTEM: $COL_SYSTEM"
        echo "RUN_NUMBER: $RUN_NUMBER"
        echo "INTERACTIONTYPE: $INTERACTIONTYPE"
        echo "PRODUCTION_TAG: $PRODUCTION_TAG"
        echo "ANCHOR_PRODUCTION: $ANCHOR_PRODUCTION"
        echo "ANCHORYEAR: $ANCHORYEAR"
        echo "SIM_OPTIONS: $SIM_OPTIONS"
        echo "--------------------------------"

        if [ "${DAILYTAGTOTEST}" ]; then
          SOFTWARETAG_SIM=${DAILYTAGTOTEST}
        fi

        OUTPUT_FILE_FINAL="${WORKING_DIR}/${OUTPUT_FILE}_case${count}.sh"
        
        # create final test script with these values
        cp "$TEMPLATE_FILE" "${OUTPUT_FILE_FINAL}"
        for var in "${headers[@]}"; do
            sed -i "s|%{$var}|${!var}|g" "$OUTPUT_FILE_FINAL"
        done
        # put the require spec
        sed -i "s/%{JDL_REQUIREMENT}/${REQUIRE_STRING}/g" "$OUTPUT_FILE_FINAL"

        # inject custom repo if available
        if [ "${O2DPG_CUSTOM_REPO}" ]; then
          sed -i "s|%{O2DPG_CUSTOM_REPO}|${O2DPG_CUSTOM_REPO}|g" "$OUTPUT_FILE_FINAL"
        else
          sed -i "/%{O2DPG_CUSTOM_REPO}/d" "$OUTPUT_FILE_FINAL"
        fi

        TOPWORKDIR=2tag_release_testing_${BUILD_TAG:-${SOFTWARETAG_SIM}}

        # we submit the test to the GRID (multiplicity of 4)
        # ${WORKING_DIR}/submit_case${count}_${SOFTWARETAG_ASYNC//::/-}
        echo "${O2DPG_ROOT}/GRID/utils/grid_submit.sh --prodsplit 4 --singularity --ttl 3600 --script ${OUTPUT_FILE_FINAL} \
              --jobname "anchorTest_${count}" --wait-any --topworkdir ${TOPWORKDIR}" > ${WORKING_DIR}/submit_case${count}.sh
        # TODO: optional local execution with --local option

        ((count++))  # Increment counter for next row
    done
} < "${INPUT_FILE_STRIPPED}" #Redirect file input here to avoid subshell issues

cd ${WORKING_DIR}

# now we submit all the jobs in the background and wait for them to return
declare -A logfiles
declare -A urls
for s in submit*.sh; do
  echo "submitting ${s}"
  export GRID_SUBMIT_WORKDIR="${WORKING_DIR}/${s}_workdir"
  (
    bash ${s} &> log_${s}
    echo "Job ${s} returned"
  ) &
  logfiles["$s"]="log_${s}"
done

# Next stage is to wait until all jobs are actually running on
# AliEn
waitcounter=0
maxwait=100
while (( ${#logfiles[@]} > 0 && waitcounter < maxwait )); do
  for script in "${!logfiles[@]}"; do
    logfile=${logfiles["$script"]}
    if grep -q "https://alimonitor.cern.ch/agent/jobs/details.jsp?pid=" "$logfile" 2>/dev/null; then
      # Extract URL: strip ANSI codes, find URL, take first match
      url=$(sed 's/\x1B\[[0-9;]*[a-zA-Z]//g' "$logfile" \
            | grep -o 'https://alimonitor.cern.ch/agent/jobs/details.jsp?pid=[0-9]*' \
            | head -n1)

      echo "Job ${script} has AliEn job URL: ${url}"
      urls["$script"]=${url}
      unset logfiles["$script"]
    fi
  done
  sleep 1
  ((waitcounter++))
done

# wait for all (GRID) jobs to return
echo "Waiting for jobs to return/finish"
wait

# verify / validate the output produced from these jobs
# The test is successfull if at least one subjob from each test
# produced the AO2D output.
echo "-- Jobs done ... validating --"

FINAL_SUCCESS=0
for s in submit*.sh; do
  # find output path
  TEST_OUTPUT_PATH="${WORKING_DIR}/${s}_workdir"   # $(grep "Local working directory is" log_${s} | awk '//{print $5}')

  # get the Output path on JAlien from the JDL
  ALIEN_OUTPUT_FOLDER=$(grep 'OutputDir' ${TEST_OUTPUT_PATH}/*.jdl | cut -d'"' -f2 | sed 's|/[^/]*#.*#.*$||')

  # see if there is an AO2D.root and a workflow.json in one of the jobs in that folder
  AODS_FOUND=$(alien.py find ${ALIEN_OUTPUT_FOLDER} AO2D.root)
  WORKFLOWS_FOUND=$(alien.py find ${ALIEN_OUTPUT_FOLDER} workflow.json)

  if [[ -z ${WORKFLOWS_FOUND} || -z ${AODS_FOUND} ]]; then
    echo "❌ Missing files for case $s: Check here for logs ${urls[${s}]}"
    FINAL_SUCCESS=1  # mark as failure
    # also upload log file to AliEn for later inspection
    alien.py cp file:./log_${s} alien:~/${TOPWORKDIR}
  else
    echo "✅ Files found in $s"
  fi
done

if [[ ${FINAL_SUCCESS} -eq 0 ]]; then
  echo "✅ All submissions have required files."
else
  echo "❌ Some submissions are missing required files."
fi

#TODO: echo "-- Cleaning up ... "
cd ..

exit ${FINAL_SUCCESS}
