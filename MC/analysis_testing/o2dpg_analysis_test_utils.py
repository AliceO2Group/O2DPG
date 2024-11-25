#!/usr/bin/env python3

#
# Analsysis task utilities
#
import sys
from os import environ, listdir
from os.path import join, abspath

import json

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)


# some commong definitions
ANALYSIS_LABEL = "Analysis"
ANALYSIS_LABEL_ON_MC = f"{ANALYSIS_LABEL}MC"
ANALYSIS_VALID_MC = "mc"
ANALYSIS_VALID_DATA = "data"
ANALYSIS_COLLISION_SYSTEM_PP = "pp"
ANALYSIS_COLLISION_SYSTEM_PBPB = "pbpb"
ANALYSIS_MERGED_ANALYSIS_NAME = "MergedAnalyses"


def adjust_configuration_line(line, data_or_mc, collision_system):
    line = line.replace('!ANALYSIS_QC_is_mc!', str(data_or_mc == ANALYSIS_VALID_MC).lower())
    line = line.replace('!ANALYSIS_QC_is_data!', str(data_or_mc == ANALYSIS_VALID_DATA).lower())
    if collision_system == "pp":
        line = line.replace('!OVERWRITEAXISRANGEFORPBPBVALUE!', "false")
    else:
        line = line.replace('!OVERWRITEAXISRANGEFORPBPBVALUE!', "true")
    if collision_system == "pbpb":
        line = line.replace('!ISLOWFLUX!', "false")
    else:
        line = line.replace('!ISLOWFLUX!', "true")
    return line


def adjust_and_get_configuration_path(data_or_mc, collision_system, output_dir):

    final_config = {}
    path = join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", "dpl")
    for config_path in listdir(path):
        if not config_path.endswith('.json'):
            continue
        json_string = ""
        with open(join(path, config_path), 'r') as f:
            for line in f:
                json_string += adjust_configuration_line(line, data_or_mc, collision_system)
            final_config |= json.loads(json_string)
        # now we can do some adjustments
    output_path = abspath(join(output_dir, 'dpl-config.json'))
    with open(output_path, 'w') as f:
        json.dump(final_config, f, indent=2)

    return output_path


def get_collision_system(collision_system=None):
    if not collision_system:
        return environ.get("ALIEN_JDL_LPMINTERACTIONTYPE", "pp").lower()
    return collision_system.lower()


def full_ana_name(raw_ana_name):
    """Make the standard name of the analysis how it should appear in the workflow"""
    return f"{ANALYSIS_LABEL}_{raw_ana_name}"


def get_common_args_as_string(ana, all_common_args):
    """
    all_common_args is of the form
    [<ana_name1>-shm-segment-size <value>, <ana_name2>-readers <value>, ...]

    Find common arguments for this specific analysis
    """

    def make_args_string(args_map_in):
        out_string = ""
        for key, value in args_map_in.items():
            out_string += f" --{key} {value}"
        return out_string

    # default arguments for all analyses
    args_map = {"shm-segment-size": 2000000000,
                "readers": 1,
                "aod-memory-rate-limit": 500000000}

    # get common args from analysis configuration and add to args_map
    common_args_from_config = ana.get("common_args", {})
    for key, value in common_args_from_config.items():
        args_map[key] = value

    # arguments dedicated for this analysis
    args_map_overwrite = {}

    if not all_common_args:
        return make_args_string(args_map)

    if len(all_common_args) % 2:
        print("ERROR: Cannot digest common args.")
        return None

    analysis_name = ana["name"]

    for i in range(0, len(all_common_args), 2):
        tokens = all_common_args[i].split("-")
        key = "-".join(tokens[1:])
        if tokens[0] == analysis_name:
            # for this analysis, add to dedicated dict
            args_map_overwrite[key] = all_common_args[i+1]
            continue
        if tokens[0] == "ALL":
            # otherwise add to default dict
            args_map[key] = all_common_args[i+1]

    # overwrite default dict with dedicated arguments
    for key, value in args_map_overwrite.items():
        args_map[key] = value

    return make_args_string(args_map)
