"""Command-line entry point.

Translates argparse -> RunnerConfig, builds loggers, creates the
WorkflowExecutor, and invokes it. All semantics of the original script
are preserved; new flags are additive and default-compatible.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from typing import Optional, Tuple

import psutil

from .config import RunnerConfig
from .filegraph import BACKENDS as FILEGRAPH_BACKENDS, FileGraphManager
from .workflow import build_workflow, load_json
from .executor import WorkflowExecutor

_FORMATTER = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
_IN_SLICE_ENV = "O2DPG_RUNNER_IN_SLICE"


def _setup_logger(name: str, logfile: str, level: int = logging.INFO) -> logging.Logger:
    handler = logging.FileHandler(logfile, mode="w")
    handler.setFormatter(_FORMATTER)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def build_parser() -> argparse.ArgumentParser:
    max_system_mem = psutil.virtual_memory().total
    default_mem = 0.9 * max_system_mem / 1024.0 / 1024.0

    p = argparse.ArgumentParser(
        description="Parallel execution of an O2-DPG data/job DAG under resource constraints.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("-f", "--workflowfile", required=True)
    p.add_argument("-jmax", "--maxjobs", type=int, default=100)
    p.add_argument("-k", "--keep-going", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--visualize-workflow", action="store_true")
    p.add_argument("--target-labels", nargs="+", default=[])
    p.add_argument("-tt", "--target-tasks", nargs="+", default=["*"])
    p.add_argument("--produce-script", default=None)
    p.add_argument("--rerun-from", default=None)
    p.add_argument("--list-tasks", action="store_true")

    # Resources
    p.add_argument("--update-resources", dest="update_resources", default=None)
    p.add_argument("--dynamic-resources", dest="dynamic_resources", action="store_true")
    p.add_argument("--optimistic-resources", dest="optimistic_resources", action="store_true")
    p.add_argument("--n-backfill", dest="n_backfill", type=int, default=1)
    p.add_argument("--mem-limit", type=float, default=default_mem, help="in MB")
    p.add_argument("--cpu-limit", type=float, default=8)

    # systemd-run slice confinement (replaces the old --cgroup option)
    p.add_argument(
        "--systemd-run",
        dest="systemd_run_spec",
        default=None,
        metavar="SPEC",
        help=(
            "Relaunch the whole runner (and all child processes) inside a transient "
            "systemd scope unit with resource limits. SPEC is a slash-separated list "
            "of key:value pairs. Supported keys: ncpus (number of CPU cores, e.g. 8), "
            "mem (memory limit in systemd format, e.g. 16G or 16384M). "
            "Either key may be omitted. Examples: \"ncpus:8/mem:16G\", \"ncpus:4\", \"mem:32G\"."
        ),
    )

    # Scheduling (new)
    p.add_argument("--scheduler-policy", default="timeframe",
                   choices=["timeframe", "critical-path", "best-fit"])
    p.add_argument("--drop-should-break", action="store_true",
                   help="In timeframe policy, don't stop scanning on the first "
                        "non-fitting task (lets light tasks slip past heavy ones).")

    # Monitoring (new)
    p.add_argument("--monitor-interval-cpu", type=float, default=1.0)
    p.add_argument("--monitor-interval-mem", type=float, default=1.0)
    p.add_argument("--monitor-backend", default="psutil", choices=["psutil"])

    # Cache (new)
    p.add_argument("--cache-policy", default="off",
                   choices=["off", "lenient", "strict"])

    # Control
    p.add_argument("--stdout-on-failure", action="store_true")
    p.add_argument("--retry-on-failure", type=int, default=0)
    p.add_argument("--no-rootinit-speedup", action="store_true")
    p.add_argument("--remove-files-early", type=str, default="")
    p.add_argument("--filegraph-backends", type=str,
                   default=os.getenv("O2DPG_FILEGRAPH_BACKENDS", ""),
                   help="comma-separated file-IO-graph backends to learn the "
                        "file dependencies with: "
                        + ", ".join(sorted(FILEGRAPH_BACKENDS)))

    # Accept-and-ignore for backward compatibility of call sites
    # that still pass these flags. They have no effect.
    p.add_argument("--webhook", default=None, help=argparse.SUPPRESS)
    p.add_argument("--checkpoint-on-failure", default=None, help=argparse.SUPPRESS)
    # superseded by --systemd-run; a JDL still passing it must not abort here
    p.add_argument("--cgroup", default=None, help=argparse.SUPPRESS)

    # Logging
    p.add_argument("--action-logfile", default=None)
    p.add_argument("--metric-logfile", default=None)
    p.add_argument("--production-mode", action="store_true")

    return p


def _args_to_config(ns: argparse.Namespace) -> RunnerConfig:
    target_tasks = [f.strip('"').strip("'") for f in ns.target_tasks]
    # Extract slice name from spec so the executor can name child scopes.
    slice_name: Optional[str] = None
    if ns.systemd_run_spec:
        try:
            _, _, slice_name = _parse_systemd_run_spec(ns.systemd_run_spec)
        except ValueError:
            pass  # error already caught at re-exec time
    return RunnerConfig(
        workflowfile=ns.workflowfile,
        maxjobs=ns.maxjobs,
        mem_limit=ns.mem_limit,
        cpu_limit=ns.cpu_limit,
        n_backfill=ns.n_backfill,
        update_resources=ns.update_resources,
        dynamic_resources=ns.dynamic_resources,
        optimistic_resources=ns.optimistic_resources,
        in_systemd_slice=bool(os.environ.get(_IN_SLICE_ENV)),
        systemd_run_spec=ns.systemd_run_spec,
        systemd_slice_name=slice_name,
        scheduler_policy=ns.scheduler_policy,
        drop_should_break=ns.drop_should_break,
        monitor_interval_cpu=ns.monitor_interval_cpu,
        monitor_interval_mem=ns.monitor_interval_mem,
        monitor_backend=ns.monitor_backend,
        cache_policy=ns.cache_policy,
        target_tasks=target_tasks,
        target_labels=list(ns.target_labels),
        keep_going=ns.keep_going,
        dry_run=ns.dry_run,
        visualize_workflow=ns.visualize_workflow,
        produce_script=ns.produce_script,
        rerun_from=ns.rerun_from,
        list_tasks=ns.list_tasks,
        retry_on_failure=ns.retry_on_failure,
        no_rootinit_speedup=ns.no_rootinit_speedup,
        remove_files_early=ns.remove_files_early,
        filegraph_backends=ns.filegraph_backends,
        stdout_on_failure=ns.stdout_on_failure,
        production_mode=ns.production_mode,
        action_logfile=ns.action_logfile,
        metric_logfile=ns.metric_logfile,
    )


def _parse_systemd_run_spec(spec: str) -> Tuple[Optional[str], Optional[str], str]:
    """Parse "ncpus:N/mem:M/name:S" into (cpu_quota_str, mem_str, slice_name).

    ncpus is given as a number of cores and converted to systemd CPUQuota
    format (e.g. 8 cores → "800%").  mem is passed through as-is.
    name sets the systemd slice name (default "o2dpg").  Any part may be absent.
    """
    cpu_quota: Optional[str] = None
    mem: Optional[str] = None
    slice_name: str = "o2dpg"
    for part in spec.split("/"):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"Expected key:value in --systemd-run spec, got: {part!r}")
        key, _, val = part.partition(":")
        key = key.strip().lower()
        val = val.strip()
        if key == "ncpus":
            try:
                cores = float(val)
            except ValueError:
                raise ValueError(f"ncpus must be a number, got: {val!r}")
            cpu_quota = f"{int(cores * 100)}%"
        elif key == "mem":
            mem = val
        elif key == "name":
            slice_name = val
        else:
            raise ValueError(f"Unknown key in --systemd-run spec: {key!r}. "
                             f"Supported: ncpus, mem, name")
    return cpu_quota, mem, slice_name


def _parse_mem_to_bytes(mem_str: str) -> Optional[int]:
    """Convert a memory size string (e.g. "16G", "512M") to bytes."""
    suffixes = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    s = mem_str.strip()
    if s and s[-1].upper() in suffixes:
        try:
            return int(float(s[:-1]) * suffixes[s[-1].upper()])
        except ValueError:
            pass
    try:
        return int(s)
    except ValueError:
        return None


def _apply_slice_cgroup_limits(
    cpu_quota: Optional[str],
    mem_str: Optional[str],
    logger: logging.Logger,
) -> None:
    """Write resource limits to the parent slice's cgroup directory.

    Called after re-exec inside the slice.  The runner's own scope lives at
    .../kaz1.slice/o2dpg-runner-<pid>.scope/; one dirname() up is the slice
    that covers both the runner and all sibling per-task scopes.

    This is the portable fallback for systemd < 246 which lacks
    --slice-property.  Writing directly to cpu.max / memory.max works on
    any cgroup v2 system where the user owns the cgroup.
    """
    cgroup_rel: Optional[str] = None
    try:
        with open("/proc/self/cgroup") as fh:
            for line in fh:
                parts = line.strip().split(":", 2)
                if len(parts) == 3 and parts[0] == "0":
                    cgroup_rel = parts[2].lstrip("/")
                    break
    except OSError:
        pass

    if not cgroup_rel:
        logger.warning("Cannot determine cgroup path; slice limits not applied.")
        return

    scope_dir = f"/sys/fs/cgroup/{cgroup_rel}"
    slice_dir = os.path.dirname(scope_dir)

    if cpu_quota:
        pct = float(cpu_quota.rstrip("%"))
        # cgroup cpu.max format: "<quota_usec> <period_usec>"
        # 100% = 1 core = 100000 usec per 100000 usec period
        quota_usec = int(pct * 1000)
        cpu_max = os.path.join(slice_dir, "cpu.max")
        try:
            with open(cpu_max, "w") as fh:
                fh.write(f"{quota_usec} 100000\n")
            logger.info("Slice CPUQuota=%s applied → %s", cpu_quota, cpu_max)
        except OSError as e:
            logger.warning("Could not set CPUQuota on slice (%s): %s", cpu_max, e)

    if mem_str:
        mem_bytes = _parse_mem_to_bytes(mem_str)
        if mem_bytes is not None:
            mem_max = os.path.join(slice_dir, "memory.max")
            try:
                with open(mem_max, "w") as fh:
                    fh.write(f"{mem_bytes}\n")
                logger.info("Slice MemoryMax=%s (%d bytes) applied → %s",
                            mem_str, mem_bytes, mem_max)
            except OSError as e:
                logger.warning("Could not set MemoryMax on slice (%s): %s", mem_max, e)


def _maybe_reexec_in_slice(ns: argparse.Namespace) -> None:
    """If --systemd-run is set and we are not already in the slice, re-exec.

    Uses os.execvp so the current process image is replaced by systemd-run,
    which creates a transient scope cgroup and then exec's the runner again.
    The child runner sees O2DPG_RUNNER_IN_SLICE=1 and skips this function.
    """
    spec = getattr(ns, "systemd_run_spec", None)
    if not spec:
        return
    if os.environ.get(_IN_SLICE_ENV):
        return  # already inside the slice

    if not shutil.which("systemd-run"):
        print(
            "Warning: --systemd-run requested but systemd-run not found on PATH; "
            "continuing without slice confinement.",
            file=sys.stderr,
        )
        return

    try:
        _, _, slice_name = _parse_systemd_run_spec(spec)
    except ValueError as e:
        print(f"Error in --systemd-run spec: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure the slice name has the .slice suffix expected by systemd.
    systemd_slice = slice_name if slice_name.endswith(".slice") else f"{slice_name}.slice"
    unit_name = f"o2dpg-runner-{os.getpid()}.scope"
    cmd = ["systemd-run", "--user", "--scope", "--collect",
           f"--unit={unit_name}", f"--slice={systemd_slice}"]
    # Resource limits are NOT passed here; they are written directly to the
    # slice cgroup after re-exec via _apply_slice_cgroup_limits().
    # --property=CPUQuota applies only to the scope (runner), not to the
    # sibling task scopes.  --slice-property would be correct but requires
    # systemd ≥ 246.  Direct cgroup writes work on all versions.
    cmd += ["--", sys.executable] + sys.argv

    os.environ[_IN_SLICE_ENV] = "1"
    try:
        os.execvp(cmd[0], cmd)
    except OSError as e:
        # execvp only returns on failure
        del os.environ[_IN_SLICE_ENV]
        print(
            f"Warning: could not exec systemd-run ({e}); "
            "continuing without slice confinement.",
            file=sys.stderr,
        )


def _maybe_draw_workflow(raw_spec):
    try:
        from graphviz import Digraph
    except ImportError:
        print("graphviz not installed; cannot draw workflow")
        return
    dot = Digraph(comment="MC workflow")
    name_to_idx = {}
    for i, node in enumerate(raw_spec["stages"]):
        name_to_idx[node["name"]] = i
        dot.node(str(i), node["name"])
    for node in raw_spec["stages"]:
        to_i = name_to_idx[node["name"]]
        for r in node.get("needs", []):
            if r in name_to_idx:
                dot.edge(str(name_to_idx[r]), str(to_i))
    dot.render("workflow.gv")


def main(argv=None) -> int:
    ns = build_parser().parse_args(argv)
    _maybe_reexec_in_slice(ns)  # may replace this process; returns only if not re-execing
    cfg = _args_to_config(ns)

    # loggers
    action_log = cfg.action_logfile or f"pipeline_action_{os.getpid()}.log"
    metric_log = cfg.metric_logfile or f"pipeline_metric_{os.getpid()}.log"
    action_logger = _setup_logger("pipeline_action_logger", action_log, level=logging.DEBUG)
    metric_logger = _setup_logger("pipeline_metric_logger", metric_log)

    for flag in ("webhook", "checkpoint_on_failure", "cgroup"):
        if getattr(ns, flag, None):
            action_logger.warning("--%s is accepted but has no effect",
                                  flag.replace("_", "-"))

    # also route the package-level log records to the action log
    pkg_log = logging.getLogger("o2dpg_runner")
    pkg_log.setLevel(logging.INFO)
    for h in list(pkg_log.handlers):
        pkg_log.removeHandler(h)
    pkg_log.propagate = False
    for h in action_logger.handlers:
        pkg_log.addHandler(h)

    # Apply slice-level cgroup resource limits now that we are inside the
    # slice and the action logger is ready to record the outcome.
    if cfg.in_systemd_slice and cfg.systemd_run_spec:
        try:
            cpu_quota, mem_str, _ = _parse_systemd_run_spec(cfg.systemd_run_spec)
            _apply_slice_cgroup_limits(cpu_quota, mem_str, action_logger)
        except Exception as e:
            action_logger.warning("Could not apply slice cgroup limits: %s", e)

    # record meta to the metric log (mirrors prototype)
    raw = load_json(cfg.workflowfile)
    meta = raw.get("meta", {}) if isinstance(raw, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    meta.update({
        "cpu_limit": cfg.cpu_limit,
        "mem_limit": cfg.mem_limit,
        "workflow_file": os.path.abspath(cfg.workflowfile),
        "target_task": cfg.target_tasks,
        "rerun_from": cfg.rerun_from,
        "target_labels": cfg.target_labels,
        "scheduler_policy": cfg.scheduler_policy,
        "drop_should_break": cfg.drop_should_break,
        "cache_policy": cfg.cache_policy,
        "systemd_run_spec": cfg.systemd_run_spec,
        "in_systemd_slice": cfg.in_systemd_slice,
        "monitor_interval_cpu": cfg.monitor_interval_cpu,
        "filegraph_backends": cfg.filegraph_backends,
    })
    metric_logger.info(meta)

    # visualize if asked (uses raw spec before filtering)
    if cfg.visualize_workflow:
        _maybe_draw_workflow(raw)

    # build workflow (filters, strips global init, builds DAG)
    wf = build_workflow(raw, cfg.target_tasks, cfg.target_labels)
    if not wf.stages:
        if cfg.target_tasks:
            print("Apparently some of the chosen target tasks are not in the workflow")
        else:
            print("Workflow is empty. Nothing to do")
        return 0

    # Apply global env (as the prototype did at construction time)
    for k, v in wf.global_env.items():
        os.environ.setdefault(k, str(v))

    filegraph = FileGraphManager.from_config(
        cfg.filegraph_backends, os.getcwd(), os.getpid(), action_log, action_logger)
    filegraph.start()

    rc = 0
    try:
        execer = WorkflowExecutor(cfg, wf, action_logger, metric_logger,
                                  filegraph=filegraph)
        rc = int(execer.execute())
    finally:
        filegraph.stop()
        for backend, path in filegraph.analyse().items():
            print(f"FileIOGraph[{backend}] -> {path}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
