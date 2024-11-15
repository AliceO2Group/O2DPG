#!/usr/bin/env python3

import argparse
import json

def main():
    parser = argparse.ArgumentParser(description='Create a JSON file from command line flags.')
    parser.add_argument('--gen', type=str, nargs='+', required=True, help='List of generators to be used')
    parser.add_argument('--output', type=str, required=True, help='Output JSON file path')

    args = parser.parse_args()

    # put in a list all the elementes in the gen flag
    noConfGen = ["pythia8pp", "pythia8hf", "pythia8hi", "pythia8powheg"]
    gens = []
    for gen in args.gen:
        # if gen is equal to pythia8, then get the Pythia8GenConfig struct from GeneratorPythia8Param.h
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
                    "funcName": "GeneratorParamPromptJpsiToElectronEvtGen_pp13TeV()"
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

    # fill fractions with 1 for each generator
    fractions = [1] * len(gens)
    
    # Put gens and fractions in the data dictionary
    data = {
        "generators": gens,
        "fractions": fractions
    }
    
    # Write the data dictionary to a JSON file
    with open(args.output, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"JSON file created at {args.output}")

if __name__ == "__main__":
    main()