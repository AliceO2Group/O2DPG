#!/usr/bin/env python3
"""Entry point preserving the legacy filename MC/bin/o2dpg_workflow_runner.py.

All behavior lives in the o2dpg_runner package next to this script.
"""

import os
import sys

# Make sure we can import the o2dpg_runner package that sits next to us.
_here = os.path.dirname(os.path.realpath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from o2dpg_runner.cli import main

if __name__ == "__main__":
    sys.exit(main())
