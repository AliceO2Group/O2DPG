#!/usr/bin/env python3

# This script creates a template JSON file for the configuration of the hybrid generator
# The generators to be used are passed as a list of strings via the --gen flag, while the
# output filename is set using --output. All the generators available in O2sim are supported.
# Alternatively the --iniFile flag can be used to specify external generators that are configured
# with ini files. The --clone flag allows the user to create multiple instances of the generator list,
# which is a useful feature when running multi-threaded event pool. This can be enabled via setting
# the --mode flag to 'parallel', which is set "sequential" by default.
# Since the script uses the ROOT dictionary to import the parameters names, O2 must be loaded, otherwise
# the template generation will not work.
# Example:
# $O2DPG_ROOT/MC/bin/o2_hybrid_gen.py --gen pythia8 boxgen external extkinO2 hepmc pythia8hf --clone 2 \
#                                     --output config.json --mode parallel --iniFile /path/to/file0.ini /path/to/file1.ini

import argparse
import json
import ROOT
import cppyy
import numpy as np

# Get the TClass object for the struct
tclass = ROOT.TClass.GetClass("o2::eventgen::Pythia8GenConfig")
tclass1 = ROOT.TClass.GetClass("o2::eventgen::BoxGenConfig")

gens_params = {"pythia8": "o2::eventgen::Pythia8GenConfig", "external": "o2::eventgen::ExternalGenConfig",
        "evtpool": "o2::eventgen::EventPoolGenConfig", "extkinO2": "o2::eventgen::O2KineGenConfig",
        "hepmc": "o2::eventgen::HepMCGenConfig", "boxgen": "o2::eventgen::BoxGenConfig"}
cmd_params = "o2::eventgen::FileOrCmdGenConfig"
gens_instances = {"pythia8": ROOT.o2.eventgen.Pythia8GenConfig(), "external": ROOT.o2.eventgen.ExternalGenConfig(),
        "evtpool": ROOT.o2.eventgen.EventPoolGenConfig(), "extkinO2": ROOT.o2.eventgen.O2KineGenConfig(),
        "hepmc": ROOT.o2.eventgen.HepMCGenConfig(), "boxgen": ROOT.o2.eventgen.BoxGenConfig()}
cmd_instance = ROOT.o2.eventgen.FileOrCmdGenConfig()

def get_params(instance, class_name):
    tclass = ROOT.TClass.GetClass(class_name)
    members = tclass.GetListOfDataMembers()
    params = {}
    for member in members:
        if isinstance(member, ROOT.TDataMember):
            member_value = getattr(instance, member.GetName())
            params[member.GetName()] = member_value
    # replace C++ strings and arrays
    for key, value in params.items():
        if isinstance(value, cppyy.gbl.std.string):
            # convert to a JSON serialisable python string
            params[key] = str(value)
        elif hasattr(value, '__len__') and hasattr(value, '__getitem__'):
            # convert C++ numerical array to python array, no string arrays are declared as parameters, so far
            params[key] = np.array(value).tolist()
    return params

def main():
    parser = argparse.ArgumentParser(description='Create a JSON file from command line flags.')
    parser.add_argument('--gen', type=str, nargs='+', help='List of generators to be used')
    parser.add_argument('--iniFile', type=str, nargs='+', help='List of external generators configured with ini files')
    parser.add_argument('--mode', type=str, help='Run generator in sequential or parallel mode for quicker event generation (multi-threading)')
    parser.add_argument('--output', type=str, required=True, help='Output JSON file path')
    parser.add_argument('--clone', type=int, help='Number of clones to make of the generator list')
    parser.add_argument('--trigger', action='store_true', help='Add triggers to the template JSON file')

    args = parser.parse_args()

    # Check if the mode is valid
    valid_modes = ["sequential", "parallel"]
    mode = args.mode if args.mode in valid_modes else "sequential"
    if args.mode and args.mode not in valid_modes:
        print(f"Mode {args.mode} not valid. Please use 'sequential' or 'parallel'")
        print("Setting sequential mode as default")
    else:
        print(f"Running in {mode} mode")

    # Available options for trigger are "off", "or", "and"
    # in all the other cases the trigger is forced "off"

    add_trigger = lambda d: d.update({"triggers": {"mode": "off", "specs": [{"macro": "", "function": ""}]}}) if args.trigger else None

    # put in a list all the elementes in the gen flag
    noConfGen = ["pythia8pp", "pythia8hf", "pythia8hi", "pythia8powheg"]
    gens = []
    if args.gen is None and args.iniFile is None:
        print("No generators specified")
        exit(1)
    if args.gen:
        print(f"Generators to be used: {args.gen}")
        for gen in args.gen:
            if gen in gens_params:
                if gen == "hepmc":
                    configs = [get_params(cmd_instance, cmd_params), get_params(gens_instances[gen], gens_params[gen])]
                    gens.append({
                        'name': gen,
                        'config': {
                            "configcmd": configs[0],
                            "confighepmc": configs[1]
                        }
                    })
                    add_trigger(gens[-1])
                else:
                    configs = get_params(gens_instances[gen],gens_params[gen])
                    gens.append({
                        'name': gen,
                        'config': configs
                    })
                    add_trigger(gens[-1])
            elif gen in noConfGen:
                gens.append({
                    "name": gen,
                    "config": ""
                })
                add_trigger(gens[-1])
            else:
                print(f"Generator {gen} not found in the list of available generators")
                exit(1)

    if args.iniFile:
        print(f"External generators to be used: {args.iniFile}")
        for ini in args.iniFile:
            if ".ini" != ini[-4:]:
                print(f"File {ini} is not an ini file")
                exit(1)
            configs = get_params(gens_instances["external"],gens_params["external"])
            configs["iniFile"] = ini
            gens.append({
                'name': 'external',
                'config': configs
            })
            add_trigger(gens[-1])

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
