"""Resolving alternative software environments via alienv."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Dict, Optional

log = logging.getLogger(__name__)


def _load_env_file(path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("declare -x "):
                line = line.replace("declare -x ", "", 1)
            if "=" not in line:
                env[line.strip()] = ""
            else:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip('"')
    return env


def get_alienv_software_environment(packagestring: Optional[str]) -> Dict[str, str]:
    """Resolve ``packagestring`` to an env dict.

    Accepts:
      - None / '' / 'None'   -> empty dict
      - a path to a file     -> 'export > env.txt' format, parsed
      - an alienv spec       -> calls /cvmfs/alice.cern.ch/bin/alienv printenv
    """
    if not packagestring or packagestring == "None":
        return {}

    if os.path.exists(packagestring) and os.path.isfile(packagestring):
        log.info("Taking software environment from file %s", packagestring)
        return _load_env_file(packagestring)

    cmd = "/cvmfs/alice.cern.ch/bin/alienv printenv " + packagestring
    proc = subprocess.Popen(
        [cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    envstring, err = proc.communicate()
    if err:
        err_s = err.decode()
        if err_s.strip():
            print(err_s)
            raise RuntimeError(f"alienv printenv failed for {packagestring}")

    envmap: Dict[str, str] = {}
    for t in envstring.decode().split(";"):
        if "=" in t:
            k, v = t.rstrip().split("=", 1)
            envmap[k] = v
        elif "export" in t:
            tokens = t.split()
            if len(tokens) >= 2:
                variable = tokens[1]
                envmap.setdefault(variable, "")
    return envmap
