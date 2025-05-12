#!/bin/bash

# loops over all test cases and executes them

#!/bin/bash

# Read the CSV file
INPUT_FILE="test_anchor_cases.csv"
INPUT_FILE_STRIPPED=${INPUT_FILE}_clean
TEMPLATE_FILE="test_anchor_2tag_template.sh"
OUTPUT_FILE="test_anchor_generated"

SITES_FILE="test_GRID_sites.dat"

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

# Read and process each subsequent line
{
    read  # Skip the header line
    
    count=1  # Counter for output files
    while IFS=',' read -r -a values; do
        # Assign each value to its corresponding variable
        for i in "${!headers[@]}"; do
            declare "${headers[$i]}"="${values[$i]}"
        done

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

        OUTPUT_FILE_FINAL="${OUTPUT_FILE}_case${count}.sh"
        cp "$TEMPLATE_FILE" "$OUTPUT_FILE_FINAL"
      
        # create final test script with these values
        cp "$TEMPLATE_FILE" "$OUTPUT_FILE_FINAL"
        for var in "${headers[@]}"; do
            sed -i "s|%{$var}|${!var}|g" "$OUTPUT_FILE_FINAL"
        done
        # put the require spec
        sed -i "s/%{JDL_REQUIREMENT}/${REQUIRE_STRING}/g" "$OUTPUT_FILE_FINAL"

        # THIS COULD BE DONE CONDITIONALLY
        # we submit the test to the GRID
        echo "${O2DPG_ROOT}/GRID/utils/grid_submit.sh --prodsplit 1 --local --singularity --ttl 360 --script ${OUTPUT_FILE_FINAL} --jobname "anchorTest${count}" --wait --fetch-output" > submit_case${count}.sh
        # TODO: optional local execution

        ((count++))  # Increment counter for next row
    done
} < "${INPUT_FILE_STRIPPED}" #Redirect file input here to avoid subshell issues
exit 0

# now we submit all the jobs in the background and wait for them to return
for s in `ls submit*.sh`; do
  echo "submitting ${s}"
  bash ${s} &> log_${s} &
done

# for for all (GRID) jobs to return
wait

# verify / validate the output produced from these jobs
# The test is successfull if at least one subjob from each test
# produced the AO2D output.
echo "-- Jobs done ... validating --"

for s in `ls submit*.sh`; do
  # find out output path
  # Local working directory is /tmp/alien_work/anchorTest1-20250306-052755
  TEST_OUTPUT_PATH=$(grep "Local working directory is" log_${s} | awk '//{print $5}')

  # see if there is an AO2D.root and a workflow.json in one of the jobs in that folder
  find ${TEST_OUTPUT_PATH} -name "AO2D.root" 
  SUCCESS_AOD=$?

  find ${TEST_OUTPUT_PATH} -name "workflow.json"
done


echo "-- Cleaning up ... "