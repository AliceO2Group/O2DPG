"""Put the FileIOGraph tools and the runner package on sys.path.

Imported first by every test module here, so there is one bootstrap
instead of one per file.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
FILEGRAPH_DIR = os.path.dirname(_HERE)
REPO = os.path.dirname(os.path.dirname(FILEGRAPH_DIR))
RUNNER_BIN = os.path.join(REPO, "MC", "workflow_runner")

for _p in (FILEGRAPH_DIR, RUNNER_BIN):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from o2dpg_runner import filegraph  # noqa: E402

__all__ = ["FILEGRAPH_DIR", "REPO", "RUNNER_BIN", "filegraph"]
