#!/usr/bin/env python3

#
# Analsysis task utilities
#
import sys
from os import environ
from os.path import join, exists, abspath, expanduser

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
ANALYSIS_CONFIGURATION_PREFIX = "analysis-testing"
ANALYSIS_DEFAULT_CONFIGURATION = {ANALYSIS_COLLISION_SYSTEM_PP: {ANALYSIS_VALID_MC: join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", "default", ANALYSIS_COLLISION_SYSTEM_PP, f"{ANALYSIS_CONFIGURATION_PREFIX}-{ANALYSIS_VALID_MC}.json"),
                                                                 ANALYSIS_VALID_DATA: join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", "default", ANALYSIS_COLLISION_SYSTEM_PP, f"{ANALYSIS_CONFIGURATION_PREFIX}-{ANALYSIS_VALID_DATA}.json")},
                                  ANALYSIS_COLLISION_SYSTEM_PBPB: {ANALYSIS_VALID_MC: join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", "default", ANALYSIS_COLLISION_SYSTEM_PBPB, f"{ANALYSIS_CONFIGURATION_PREFIX}-{ANALYSIS_VALID_MC}.json"),
                                                                   ANALYSIS_VALID_DATA: join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", "default", ANALYSIS_COLLISION_SYSTEM_PBPB, f"{ANALYSIS_CONFIGURATION_PREFIX}-{ANALYSIS_VALID_DATA}.json")}}


def sanitize_configuration_path(path):
    # sanitize path
    path = path.replace("json://", "")
    if path[0] != "$":
        # only do this if there is no potential environment variable given as the first part of the path
        path = abspath(expanduser(path))
    return f"json://{path}"


def get_default_configuration(data_or_mc, collision_system):
    path = ANALYSIS_DEFAULT_CONFIGURATION.get(collision_system, None)
    if not path:
        print(f"ERROR: Unknown collision system {collision_system}")
        return None
    return path[data_or_mc]


def get_configuration(analysis_name, data_or_mc, collision_system):
    path = join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", analysis_name, collision_system, f"{ANALYSIS_CONFIGURATION_PREFIX}-{data_or_mc}.json")
    if not exists(path):
        path = get_default_configuration(data_or_mc, collision_system)
        if not path:
            return None
        print(f"INFO: Use default configuration for {analysis_name}")
        return sanitize_configuration_path(path)

    return sanitize_configuration_path(path)


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
