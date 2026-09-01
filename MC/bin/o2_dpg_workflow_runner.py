#!/usr/bin/env python3
"""Run the workflow runner selected by ALIEN_O2DPG_WORKFLOW_RUNNER.

'legacy' (the default) is the original single-file runner, 'new' is the
o2dpg_runner package under MC/workflow_runner. All arguments are passed on
unchanged.
"""

import os
import sys

_HERE = os.path.dirname(os.path.realpath(__file__))

RUNNERS = {
    "legacy": os.path.join(_HERE, "o2dpg_workflow_runner_legacy.py"),
    "new": os.path.join(_HERE, os.pardir, "workflow_runner",
                        "o2dpg_workflow_runner.py"),
}

DEFAULT_RUNNER = "legacy"


def main():
    which = os.getenv("ALIEN_O2DPG_WORKFLOW_RUNNER", DEFAULT_RUNNER).strip()
    script = RUNNERS.get(which)
    if script is None:
        sys.exit(f"ALIEN_O2DPG_WORKFLOW_RUNNER={which!r} is not one of "
                 f"{', '.join(sorted(RUNNERS))}")
    os.execv(sys.executable, [sys.executable, script] + sys.argv[1:])


if __name__ == "__main__":
    main()
