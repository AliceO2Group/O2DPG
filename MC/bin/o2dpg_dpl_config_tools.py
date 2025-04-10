#!/usr/bin/env python3

import json
import re
import sys
from collections import defaultdict
from copy import deepcopy
import os
from o2dpg_workflow_utils import merge_dicts
import shlex

BUILTIN_BLACKLIST = {
    "--session", "--severity", "--shm-segment-id", "--shm-segment-size",
    "--resources-monitoring", "--resources-monitoring-dump-interval",
    "--delay", "--loop", "--early-forward-policy", "--fairmq-rate-logging",
    "--pipeline", "--disable-mc", "--disable-root-input", "--timeframes-rate-limit",
    "--timeframes-rate-limit-ipcid",
    "--lumi-type",  # TPC corrections are treated separately in o2dpg_sim_workflow
    "--corrmap-lumi-mode", # TPC corrections are treated separately in o2dpg_sim_workflow
    "--enable-M-shape-correction" # TPC correction option not needed in MC
}

def parse_command_string(cmd_str):
    """
    Parse a DPL command string into structured config_base:
    {
        "executable": str,
        "options": {key: val, ...},
        "configKeyValues": {"Group": {subkey: val}}
    }
    """
    try:
        tokens = shlex.split(cmd_str, posix=False)
    except ValueError as e:
        print(f"[ERROR] Failed to parse command string: {cmd_str}")
        raise e

    if not tokens:
        return {}

    exe = tokens[0]
    opts = {}
    config_keyvals_raw = None

    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token.startswith('--') or (token.startswith('-') and len(token) == 2):
            key = token  # preserve the dash prefix: "-b" or "--run-number"
            if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
                value = tokens[i + 1].strip('"').strip("'")
                i += 1
            else:
                value = True
            if key == "--configKeyValues":
                config_keyvals_raw = value
            else:
                opts[key] = value
        i += 1

    config_kv_parsed, config_groups = {}, set()
    if config_keyvals_raw:
        config_kv_parsed, config_groups = parse_configKeyValues_block(config_keyvals_raw)

    return {
        "executable": exe,
        "options": opts,
        "configKeyValues": config_kv_parsed,
        "configKeyGroups": sorted(config_groups)
    }

def parse_command_string_symmetric(cmd_str, configname = None):
    """
    Parses a DPL command string into the same structure as parse_workflow_config(...):
    {
      "ConfigParams": { group: {key: value, ...} },
      "Executables": {
        "o2-executable": {
          "full": {...},
          "filtered": {...},
          "blacklisted": [],
          "configKeyValues": [group, ...]
        }
      }
    }
    """
    try:
        tokens = shlex.split(cmd_str, posix=False)
    except ValueError as e:
        print(f"[ERROR] Failed to parse command string: {cmd_str}")
        raise e

    if not tokens:
        return {}

    exe = os.path.basename(tokens[0]) if configname == None else configname
    opts = {}
    config_kv_raw = None

    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token.startswith('--') or (token.startswith('-') and len(token) == 2):
            key = token  # preserve the dash prefix: "-b" or "--run-number"
            if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
                value = tokens[i + 1].strip('"').strip("'")
                i += 1
            else:
                value = True
            if key == "--configKeyValues":
                config_kv_raw = value
            else:
                opts[key] = value
        i += 1

    config_params = {}
    config_key_groups = []

    if config_kv_raw:
        parsed_kv, groups = parse_configKeyValues_block(config_kv_raw)
        config_params = parsed_kv
        config_key_groups = sorted(groups)

    return {
        "ConfigParams": config_params,
        "Executables": {
            exe: {
                "full": opts,
                "filtered": dict(opts),
                "blacklisted": [],
                "configKeyValues": config_key_groups
            }
        }
    }


def parse_configKeyValues_block(raw_value):
    result = defaultdict(dict)
    seen_groups = set()
    raw_value = raw_value.replace('\\"', '"').replace("\\'", "'")
    parts = raw_value.split(";")
    for part in parts:
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.strip()
        val = val.strip()
        if "." in key:
            group, subkey = key.split(".", 1)
            result[group][subkey] = val
            seen_groups.add(group)
    return dict(result), seen_groups

def log_line(logger, message):
    if logger is None or logger == sys.stdout:
        print(message)
    elif isinstance(logger, str):
        with open(logger, "a") as f:
            f.write(message + "\n")
    else:
        logger.write(message + "\n")

def modify_dpl_command(cmd_str, config_anchor, allow_overwrite=False, logger=None, configname=None):
    # check if cmd_str is given as list, in which case we transfrom to string
    if isinstance(cmd_str, list) == True:
       cmd_str = " ".join(filter(None, cmd_str))

    base = parse_command_string(cmd_str)
    exe = base["executable"]
    existing_opts = base["options"]
    existing_kv = base["configKeyValues"]

    # Start building new command
    new_cmd = [exe]
    added = []
    overwritten = []
   
    exe_basename = os.path.basename(exe) if configname == None else configname
    anchor_exec = None
    if "Executables" in config_anchor:
       anchor_exec = config_anchor["Executables"].get(exe_basename, None)
    if anchor_exec == None:
       # try without the Executable section
       anchor_exec = config_anchor.get(exe_basename, None)

    if anchor_exec == None:
       print(f"[WARN] No anchor config found for {exe}")
       return cmd_str    

    anchor_opts = anchor_exec.get("filtered", {})
    anchor_kv_groups = anchor_exec.get("configKeyValues", [])

    # --- Step 1: Reconstruct executable and its CLI options
    new_cmd = [exe]
    added = []
    overwritten = []

    def quote_if_needed(val):
        s = str(val)
        if " " in s and not (s.startswith('"') and s.endswith('"')):
           return f'"{s}"'
        return s

    # Step 1: Existing options (preserved or overwritten)
    for key, val in existing_opts.items():
        if allow_overwrite and key in anchor_opts:
            val = anchor_opts[key]
            overwritten.append(key)
        new_cmd.append(f"{key} {quote_if_needed(val)}" if val is not True else f"{key}")

    # Step 2: Add missing options from anchor
    for key, val in anchor_opts.items():
        if key not in existing_opts:
            new_cmd.append(f"{key} {quote_if_needed(val)}" if val is not True else f"{key}")
            added.append(key)

    # what about config-key values (should already be done) Merge configKeyValues
    merged_kv = deepcopy(existing_kv)
    # for group in anchor_kv_groups:
    #     group_kvs = config_anchor.get("ConfigParams", {}).get(group, {})
    #     if group not in merged_kv:
    #         merged_kv[group] = group_kvs
    #     elif allow_overwrite:
    #         merged_kv[group].update(group_kvs)

    if merged_kv:
        kv_flat = [f"{g}.{k}={v}" for g, kv in merged_kv.items() for k, v in kv.items()]
        new_cmd.append('--configKeyValues "' + ";".join(kv_flat) + '"')

    # log changes
    log_line(logger, f"\n[Executable: {exe}]")
    if added:
        log_line(logger, f"  Added options: {added}")
    if overwritten:
        log_line(logger, f"  Overwritten options: {overwritten}")
    if not added and not overwritten:
        log_line(logger, f"  No changes made to command.")

    return " ".join(new_cmd)

# CLI: Parse log + blacklist into output.json
def parse_configKeyValues(raw_value):
    return parse_configKeyValues_block(raw_value)

def parse_workflow_config(log_path):
    config_params = defaultdict(dict)
    executables = {}

    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parsed = parse_command_string(line)
            exe = parsed["executable"]
            config_groups_used = parsed["configKeyGroups"]
            full_opts = parsed["options"]

            for group, kv in parsed["configKeyValues"].items():
                config_params[group].update(kv)

            executables[exe] = {
                "configKeyValues": sorted(config_groups_used),
                "full": full_opts
            }

    return config_params, executables


def apply_blacklist(executables, blacklist_cfg):
    for exe, data in executables.items():
        full_opts = data["full"]
        exe_blacklist = set(blacklist_cfg.get(exe, []))
        total_blacklist = BUILTIN_BLACKLIST.union(exe_blacklist)

        blacklisted = []
        filtered = {}

        for key, val in full_opts.items():
            if key in total_blacklist:
                blacklisted.append(key)
            else:
                filtered[key] = val

        data["blacklisted"] = sorted(blacklisted)
        data["filtered"] = filtered
        data["full"] = deepcopy(full_opts)  # keep original
    return executables

def dpl_option_from_config(config, dpl_workflow, key, section = "filtered", default_value = None):
      """
      Utility to extract a DPL option for workflow dpl_workflow from
      the configuration dict "config". The configuration is:
      - either a flattish JSON produced by older tool parse-async-WorkflowConfig.py
      - more structured version produced by o2dpg_dpl_config_tools (this tool)
      """
      if "Executables" in config:
        # new standard
        return config["Executables"].get(dpl_workflow,{}).get(section,{}).get(key, default_value)
      else:
        # backward compatible versions
        dpl_workflow_key = dpl_workflow + '-options'
        if dpl_workflow_key in config:
           return config.get(dpl_workflow_key, {}).get(key, default_value)
        dpl_workflow_key = dpl_workflow_key
        if dpl_workflow_key in config:
           return config.get(dpl_workflow_key, {}).get(key, default_value)
        return default_value    

def main():
    if len(sys.argv) == 4:
        log_path = sys.argv[1]
        blacklist_path = sys.argv[2]
        output_path = sys.argv[3]

        with open(blacklist_path) as f:
            blacklist_data = json.load(f)

        config_params, executables = parse_workflow_config(log_path)
        executables = apply_blacklist(executables, blacklist_data)

        result = {
            "ConfigParams": dict(config_params),
            "Executables": executables
        }

        with open(output_path, "w") as out:
            json.dump(result, out, indent=2)

        print(f"[INFO] Wrote structured config to: {output_path}")
    else:
        print("Usage:")
        print("  CLI parsing: python3 dpl_config_tools.py workflowconfig.log blacklist.json output.json")
        print("  Python usage: import and call parse_command_string() or modify_dpl_command()")


class TaskFinalizer:
    def __init__(self, anchor_config, allow_overwrite=False, logger=None):
        self.anchor_config = anchor_config
        self.allow_overwrite = allow_overwrite
        self.logger = logger
        self.final_config = {
            "ConfigParams": {},
            "Executables": {}
        }

    def __call__(self, cmd_str_or_list, configname = None):
        final_cmd = modify_dpl_command(cmd_str_or_list, self.anchor_config.get("Executables",{}), logger=self.logger, configname=configname)
        this_config_final = parse_command_string_symmetric(final_cmd, configname)
        print (this_config_final)
        merge_dicts (self.final_config, this_config_final)
        return final_cmd

    def dump_collected_config(self, path):
        with open(path, "w") as f:
            json.dump(self.final_config, f, indent=2)


if __name__ == "__main__":
    main()
