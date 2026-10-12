"""
o2dpg_runner: modular rewrite of the O2DPG workflow runner.

Originally started February 2021 by sandro.wenzel@cern.ch as a single-file
prototype (MC/bin/o2dpg_workflow_runner.py). This package is the modular
refactor, keeping full CLI and behavioral compatibility by default while
exposing pluggable scheduling policies, a threaded resource monitor, and
a cleaner testable structure.
"""

__version__ = "2.0.0"
