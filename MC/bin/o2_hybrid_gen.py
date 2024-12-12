#!/usr/bin/env python3

# This script creates a template JSON file for the configuration of the hybrid generator
# The generators to be used are passed as a list of strings via the --gen flag, while the
# output filename is set using --output. All the generators available in O2sim are supported.
# Alternatively the --iniFile flag can be used to specify external generators that are configured
# with ini files. The --clone flag allows the user to create multiple instances of the generator list,
# which is a useful feature when running multi-threaded event pool. This can be enabled via setting
# the --mode flag to 'parallel', which is set "sequential" by default.
# Example:
# $O2DPG_ROOT/MC/bin/o2_hybrid_gen.py --gen pythia8 boxgen external extkinO2 hepmc pythia8hf --clone 2 \
#                                     --output config.json --mode parallel --iniFile /path/to/file0.ini /path/to/file1.ini

import argparse
import json

def main():
    parser = argparse.ArgumentParser(description='Create a JSON file from command line flags.')
    parser.add_argument('--gen', type=str, nargs='+', help='List of generators to be used')
    parser.add_argument('--iniFile', type=str, nargs='+', help='List of external generators configured with ini files')
    parser.add_argument('--mode', type=str, help='Run generator in sequential or parallel mode for quicker event generation (multi-threading)')
    parser.add_argument('--output', type=str, required=True, help='Output JSON file path')
    parser.add_argument('--clone', type=int, help='Number of clones to make of the generator list')

    args = parser.parse_args()

    # Check if the mode is valid
    mode = "sequential"
    if args.mode not in ["sequential", "parallel"]:
        print(f"Mode {args.mode} not valid. Please use 'seq' or 'par'")
        print("Setting sequential mode as default")
    else:
        print(f"Running in {args.mode} mode")
        mode = args.mode

    # put in a list all the elementes in the gen flag
    noConfGen = ["pythia8pp", "pythia8hf", "pythia8hi", "pythia8powheg"]
    gens = []
    if args.gen is None and args.iniFile is None:
        print("No generators specified")
        exit(1)
    if args.gen:
        print(f"Generators to be used: {args.gen}")
        for gen in args.gen:
            if gen == "pythia8":
                gens.append({
                    'name': 'pythia8',
                    'config': {
                        "config": "$O2_ROOT/share/Generators/egconfig/pythia8_inel.cfg",
                        "hooksFileName": "",
                        "hooksFuncName": "",
                        "includePartonEvent": False,
                        "particleFilter": "",
                        "verbose": 0
                    }
                })
            elif gen == "external":
                gens.append({
                    'name': 'external',
                    'config': {
                        "fileName": "${O2DPG_ROOT}/MC/config/PWGDQ/external/generator/GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV.C",
                        "funcName": "GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV()",
                        "iniFile": ""
                    }
                })
            elif gen == "extkinO2":
                gens.append({
                    'name': 'extkinO2',
                    'config': {
                        "skipNonTrackable": True,
                        "continueMode": False,
                        "roundRobin": False, 
                        "randomize": False, 
                        "rngseed": 0, 
                        "randomphi": False, 
                        "fileName": "/path/to/filename.root"
                    }
                })
            elif gen == "hepmc":
                gens.append({
                    "name": "hepmc",
                    "config": {
                        "configcmd": {
                        "fileNames": "",
                        "cmd": ""
                        },
                        "confighepmc": {
                        "version": 2,
                        "eventsToSkip": 0,
                        "fileName": "/path/to/filename.hepmc",
                        "prune": False
                        }
                    }
                })
            elif gen == "boxgen":
                gens.append({
                    "name": "boxgen",
                    "config": {
                        "pdg": 13,
                        "number": 1,
                        "eta": [
                        -4,
                        -2.5
                        ],
                        "prange": [
                        0.1,
                        5
                        ],
                        "phirange": [
                        0,
                        360
                        ]
                    }
                })
            elif gen in noConfGen:
                gens.append({
                    "name": gen,
                    "config": ""
                })
            else:
                print(f"Generator {gen} not found in the list of available generators")
                exit(1)

    if args.iniFile:
        print(f"External generators to be used: {args.iniFile}")
        for ini in args.iniFile:
            if ".ini" != ini[-4:]:
                print(f"File {ini} is not an ini file")
                exit(1)
            gens.append({
                'name': 'external',
                'config': {
                    "fileName": "",
                    "funcName": "",
                    "iniFile": ini
                }
            })

    if args.clone:
        if args.clone < 2:
            print("The cloning value must be greater than 1")
            print("Skipping procedure...")
        else:
            print(f"Cloning the generator list {args.clone} times")
            gens = gens * args.clone


    # fill fractions with 1 for each generator
    fractions = [1] * len(gens)
    
    # Put gens and fractions in the data dictionary
    data = {
        "mode": mode,
        "generators": gens,
        "fractions": fractions
    }
    
    # Write the data dictionary to a JSON file
    with open(args.output, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"JSON file created at {args.output}")

if __name__ == "__main__":
    main()
