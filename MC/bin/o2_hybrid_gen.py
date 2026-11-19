#!/usr/bin/env python3

# This script creates a template JSON file for the configuration of the hybrid generator
# The generators to be used are passed as a list of strings via the --gen flag, while the
# output filename is set using --output. All the generators available in O2sim are supported.
# Alternatively the --iniFile flag can be used to specify external generators that are configured
# with ini files. The --clone flag allows the user to create multiple instances of the generator list,
# which is a useful feature when running multi-threaded event pool. This can be enabled via setting
# the --mode flag to 'parallel', which is set "sequential" by default.
# Each --cocktail flag adds one cocktail, which is one entry of the generators list and takes a single fraction.
# A cocktail member given as a path ending in .ini is an external generator configured with that file.
# Cocktails cannot be used in parallel mode, where the hybrid generator takes the event from a shared
# queue and would merge the particles of no generator at all, producing empty events.
# The fractions, which are 1 for each entry by default, can be set with --fractions: one integer per
# entry of the generators list, cocktails included. The entries are ordered as --gen, then --iniFile,
# then --cocktail, independently of the order the flags are given in, and are counted after cloning.
# Since the script uses the ROOT dictionary to import the parameters names, O2 must be loaded, otherwise
# the template generation will not work.
# Example:
# $O2DPG_ROOT/MC/bin/o2_hybrid_gen.py --gen pythia8 boxgen external hepmc pythia8hf --clone 2 \
#                                     --output config.json --mode parallel --iniFile /path/to/file0.ini /path/to/file1.ini
# $O2DPG_ROOT/MC/bin/o2_hybrid_gen.py --gen pythia8pp --cocktail pythia8hf boxgen \
#                                     --cocktail boxgen /path/to/external.ini \
#                                     --fractions 10 2 1 --output config.json

import argparse
import json
import ROOT

# The hybrid generator builds the configuration of a generator by deserialising the JSON with
# TBufferJSON::FromJSON, see GeneratorHybrid::confSetter. The template is therefore written with the
# symmetric serialisation of a default constructed configuration class, so that the parameters and
# their default values always match the loaded O2sim.
ROOT.gInterpreter.Declare(r'''
#include "TBufferJSON.h"
#include <string>
template <typename T>
std::string o2dpgHybridDefaultJSON() { T conf{}; return std::string(TBufferJSON::ToJSON(&conf).Data()); }
''')

gens_params = {"pythia8": "o2::eventgen::Pythia8GenConfig", "external": "o2::eventgen::ExternalGenConfig",
        "evtpool": "o2::eventgen::EventPoolGenConfig",
        "hepmc": "o2::eventgen::HepMCGenConfig", "boxgen": "o2::eventgen::BoxGenConfig"}
cmd_params = "o2::eventgen::FileOrCmdGenConfig"

# generators for which the hybrid generator uses a fixed configuration file
noConfGen = ["pythia8pp", "pythia8hf", "pythia8hi", "pythia8powheg"]

def get_params(class_name):
    params = json.loads(str(ROOT.o2dpgHybridDefaultJSON[class_name]()))
    params.pop("_typename", None) # ROOT bookkeeping, not a parameter
    return params

def make_gen(gen, add_trigger):
    # one entry of the generators list, with the parameters of the loaded O2sim at their default
    if gen.endswith(".ini"):
        # an external generator configured with the given ini file
        configs = get_params(gens_params["external"])
        configs["iniFile"] = gen
        entry = {
            'name': 'external',
            'config': configs
        }
    elif gen in gens_params:
        if gen == "hepmc":
            entry = {
                'name': gen,
                'config': {
                    "configcmd": get_params(cmd_params),
                    "confighepmc": get_params(gens_params[gen])
                }
            }
        else:
            entry = {
                'name': gen,
                'config': get_params(gens_params[gen])
            }
    elif gen in noConfGen:
        entry = {
            "name": gen,
            "config": ""
        }
    else:
        print(f"Generator {gen} not found in the list of available generators")
        if gen == "extkinO2":
            print("The hybrid generator has no branch for 'extkinO2', use 'evtpool' to read O2 kinematics files")
        exit(1)
    add_trigger(entry)
    return entry

def main():
    parser = argparse.ArgumentParser(description='Create a JSON file from command line flags.')
    parser.add_argument('--gen', type=str, nargs='+', help='List of generators to be used')
    parser.add_argument('--iniFile', type=str, nargs='+', help='List of external generators configured with ini files')
    parser.add_argument('--cocktail', type=str, nargs='+', action='append', metavar='GEN',
                        help='Generators of one cocktail, whose particles are merged into a single event; '
                             'a member ending in .ini is an external generator configured with that file. '
                             'Not available in parallel mode')
    parser.add_argument('--mode', type=str, help='Run generator in sequential or parallel mode for quicker event generation (multi-threading)')
    parser.add_argument('--output', type=str, required=True, help='Output JSON file path')
    parser.add_argument('--clone', type=int, help='Number of clones to make of the generator list')
    parser.add_argument('--fractions', type=int, nargs='+',
                        help='Fraction of each entry of the generators list, a cocktail counting as one entry; '
                             'the entries are ordered as --gen, --iniFile, --cocktail and counted after cloning')
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
    gens = []
    if args.gen is None and args.iniFile is None and args.cocktail is None:
        print("No generators specified")
        exit(1)
    if args.gen:
        print(f"Generators to be used: {args.gen}")
        for gen in args.gen:
            gens.append(make_gen(gen, add_trigger))

    if args.iniFile:
        print(f"External generators to be used: {args.iniFile}")
        for ini in args.iniFile:
            if not ini.endswith(".ini"):
                print(f"File {ini} is not an ini file")
                exit(1)
            gens.append(make_gen(ini, add_trigger))

    # each cocktail is a single entry of the generators list, grouping generators whose
    # particles are merged into the same event
    if args.cocktail:
        if mode == "parallel":
            # in parallel mode the hybrid generator picks the event from a shared queue and never
            # collects the members of a cocktail, so every event would come out empty
            print("Cocktails cannot be used in parallel mode, where they would produce empty events")
            print("Please use the sequential mode for a configuration containing cocktails")
            exit(1)
        for cocktail in args.cocktail:
            print(f"Cocktail to be used: {cocktail}")
            gens.append({
                'cocktail': [make_gen(gen, add_trigger) for gen in cocktail]
            })

    if args.clone:
        if args.clone < 2:
            print("The cloning value must be greater than 1")
            print("Skipping procedure...")
        else:
            print(f"Cloning the generator list {args.clone} times")
            gens = gens * args.clone


    # fill fractions with 1 for each generator, unless they are provided
    if args.fractions:
        if len(args.fractions) != len(gens):
            print(f"{len(args.fractions)} fractions provided for {len(gens)} entries of the generators list")
            print("One fraction per entry is needed, a cocktail counting as one entry")
            exit(1)
        if any(fraction < 0 for fraction in args.fractions):
            print("The fractions cannot be negative")
            exit(1)
        fractions = args.fractions
    else:
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
