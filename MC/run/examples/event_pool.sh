#!/usr/bin/env bash

# Example on how to produce an event pool and how to feed it
# to the O2DPG simulation workflow 

# make sure O2DPG + O2 is loaded
[ ! "${O2DPG_ROOT}" ] && echo "Error: This needs O2DPG loaded" && exit 1
[ ! "${O2_ROOT}" ] && echo "Error: This needs O2 loaded" && exit 1

# Parse arguments
MAKE=false
INPUT=""

help() {
    echo "Usage: $0 [--make] [-i|--input <input_file>]"
    echo "  --make: Create the event pool"
    echo "  -i|--input: Input event pool file to be used in the simulation workflow. Alien paths are supported."
    echo "              A full path must be provided (use of environment variables allowed), otherwise generation will fail."
    echo "  -h|--help: Display this help message"
    exit 0
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --make) MAKE=true ;;
        -i|--input) INPUT="$2"; shift ;;
        -h|--help) help ;;
        *) echo "Unknown operation requested: $1"; help ;;
    esac
    shift
done

if $MAKE; then
    echo "Started generation of event pool"
    # Workflow creation. All the parameters are used as examples
    # No transport will be executed. The workflow will stop at the event generation and will conclude with the merging of all the
    # kinematic root files of the timeframes in a file called evtpool.root in the current working directory
    ${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 14000 -col pp -gen pythia8 -proc cdiff -tf 2 -ns 5000 --make-evtpool -seed 546 -interactionRate 500000 -productionTag "evtpoolcreation" -o evtpool
    # Workflow runner
    ${O2DPG_ROOT}/MC/bin/o2dpg_workflow_runner.py -f evtpool.json -tt pool
elif [[ -n "$INPUT" ]]; then
    echo "Input file provided: $INPUT"
    if [[ -f "$INPUT" && -s "$INPUT" ]] || [[ "$INPUT" == alien://* ]]; then
        # Workflow creation. Phi Rotation is set manually, while the event randomisation of the pool is set by default
        ${O2DPG_ROOT}/MC/bin/o2dpg_sim_workflow.py -eCM 14000 -confKey "GeneratorFromO2Kine.randomphi=true;GeneratorFromO2Kine.fileName=$INPUT" -gen extkinO2 -tf 2 -ns 10 -e TGeant4 -j 4 -interactionRate 500000 -seed 546 -productionTag "evtpooltest"
        # Workflow runner. The rerun option is set in case you will run directly the script in the same folder (no need to manually delete files)
        ${O2DPG_ROOT}/MC/bin/o2dpg_workflow_runner.py -f workflow.json -tt aod --rerun-from grpcreate
    else
        echo "Error: File does not exist or is empty: $INPUT"
        exit 1
    fi
else
    echo "Usage: $0 [--make] [-i|--input <input_file>]"
    exit 1
fi