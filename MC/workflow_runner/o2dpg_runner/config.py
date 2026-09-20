"""Runtime configuration for the runner.

A dataclass that holds everything the old module-level ``args`` exposed,
so nothing in the code needs to import argparse. Constructed from the
argparse Namespace in cli.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RunnerConfig:
    # --- required ---
    workflowfile: str

    # --- scheduling / resources ---
    maxjobs: int = 100
    mem_limit: float = 0.0  # MB; 0 means "auto from psutil"
    cpu_limit: float = 8.0
    n_backfill: int = 1
    update_resources: Optional[str] = None
    dynamic_resources: bool = False
    optimistic_resources: bool = False
    in_systemd_slice: bool = False  # True when runner was re-exec'd under systemd-run --scope

    # --- new scheduler knobs ---
    scheduler_policy: str = "timeframe"   # timeframe | critical-path | best-fit
    drop_should_break: bool = False        # let timeframe policy scan past non-fitting

    # --- systemd-run slice ---
    systemd_run_spec: Optional[str] = None    # raw "ncpus:N/mem:M/name:S" spec, kept for metric meta
    systemd_slice_name: Optional[str] = None  # parsed "name:" value; used for child scope names

    # --- new monitor knobs ---
    monitor_interval_cpu: float = 1.0
    monitor_interval_mem: float = 1.0      # match prototype cadence; raise for cheaper monitor
    monitor_backend: str = "psutil"        # psutil | auto (auto reserved for future cgroup backend)

    # --- cache policy (v1 _done.json) ---
    cache_policy: str = "off"              # off | lenient | strict

    # --- selection / control ---
    target_tasks: List[str] = field(default_factory=lambda: ["*"])
    target_labels: List[str] = field(default_factory=list)
    keep_going: bool = False
    dry_run: bool = False
    visualize_workflow: bool = False
    produce_script: Optional[str] = None
    rerun_from: Optional[str] = None
    list_tasks: bool = False
    retry_on_failure: int = 0
    no_rootinit_speedup: bool = False
    remove_files_early: str = ""
    stdout_on_failure: bool = False
    production_mode: bool = False

    # --- logging ---
    action_logfile: Optional[str] = None
    metric_logfile: Optional[str] = None
