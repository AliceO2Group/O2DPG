#!/usr/bin/env python3
"""Discrete-event simulator for the O2DPG workflow scheduler.

Loads a workflow (and optionally applies learned resources), then
simulates scheduling under one or more policies in microseconds —
no processes are spawned.

Assumptions (matching a kernel-enforced hard CPU limit):
  - No nice / backfill tier: all tasks are submitted at the default
    nice level against a single hard CPU budget.
  - Memory is also a hard limit.
  - Tasks run for exactly their `resources.walltime` seconds (set by
    --update-resources).  If walltime is absent, cpu * --walltime-per-core
    is used as a proxy.
  - Task parallelism is limited only by cpu_limit and mem_limit, not
    by --maxjobs (the simulator sets the process cap to infinity).

Usage examples
--------------
Compare all three policies with learned resources:

    o2dpg_schedule_simulator.py \\
        -f workflow.json \\
        --update-resources learned.json \\
        --cpu-limit 8 --mem-limit 16384 \\
        --policies timeframe critical-path best-fit

Single policy, verbose per-task schedule:

    o2dpg_schedule_simulator.py \\
        -f workflow.json --update-resources learned.json \\
        --cpu-limit 8 --mem-limit 16384 \\
        --policies critical-path --verbose

JSON output for downstream analysis:

    o2dpg_schedule_simulator.py ... --output sim.json
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import statistics
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from o2dpg_runner.workflow import (
    build_workflow,
    load_json,
    replicate_workflow_for_timeframes,
    update_resource_estimates,
)
from o2dpg_runner.resources import ResourceManager, ResourceLimitExceeded
from o2dpg_runner.scheduler import get_policy
from o2dpg_runner.scheduler.base import SchedulerState
from o2dpg_runner.scheduler.timeframe import TimeframeFirstPolicy
from o2dpg_runner.graph import descendants, longest_path_length, kahn_topological_order


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SimTask:
    tid: int
    name: str
    start: float       # wall seconds from t=0
    finish: float
    cpu: float         # effective average cores consumed over [start, finish]
    cpu_booked: float  # cores booked for scheduler admission
    mem: float         # MB booked
    walltime: float    # finish - start


@dataclass
class _RunningBackfill:
    task: SimTask
    nominal_work: float
    remaining_work: float
    launch_seq: int
    overhead_until: Optional[float] = None


@dataclass
class SimResult:
    policy: str
    makespan: float                        # total wall seconds
    tasks: List[SimTask] = field(default_factory=list)
    deadlocked_tids: List[int] = field(default_factory=list)

    def cpu_utilization(self, cpu_limit: float) -> float:
        """Mean CPU utilisation as a fraction of cpu_limit."""
        if self.makespan <= 0 or cpu_limit <= 0:
            return 0.0
        total = sum(t.cpu * t.walltime for t in self.tasks)
        return total / (self.makespan * cpu_limit)

    def peak_mem_mb(self) -> float:
        """Peak concurrent memory usage in MB (sweep-line)."""
        events: List[Tuple[float, float]] = []
        for t in self.tasks:
            events.append((t.start,  +t.mem))
            events.append((t.finish, -t.mem))
        events.sort()
        peak = cur = 0.0
        for _, delta in events:
            cur += delta
            peak = max(peak, cur)
        return peak

    def to_dict(self) -> dict:
        return {
            "policy": self.policy,
            "makespan_s": round(self.makespan, 3),
            "tasks": [
                {
                    "tid": t.tid, "name": t.name,
                    "start": round(t.start, 3), "finish": round(t.finish, 3),
                    "cpu": round(t.cpu, 3), "cpu_booked": round(t.cpu_booked, 3),
                    "mem": round(t.mem, 1),
                    "walltime": round(t.walltime, 3),
                }
                for t in sorted(self.tasks, key=lambda x: x.start)
            ],
            "deadlocked_tids": self.deadlocked_tids,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _global_name(name: str) -> str:
    toks = name.split("_")
    if toks and toks[-1].isdigit() and len(toks) > 1:
        return "_".join(toks[:-1])
    return name


def _task_walltime(task: dict, cpu_fallback_factor: float) -> float:
    """Return walltime [s] for a task, falling back to cpu * factor."""
    wt = task.get("resources", {}).get("walltime")
    if wt is not None:
        try:
            return max(1e-3, float(wt))
        except (TypeError, ValueError):
            pass
    cpu = float(task.get("resources", {}).get("cpu", 1.0))
    return max(1e-3, cpu * cpu_fallback_factor)


_LEARN_ALL: Set[str] = frozenset({"cpu", "mem", "lifetime"})


def _apply_learned_fields(workflow, learned: Dict, fields: Set[str]) -> int:
    """Patch workflow stages in-place with a subset of learned resource fields.

    *fields* is a subset of ``{"cpu", "mem", "lifetime"}``.  Only the named
    dimensions are written; the rest keep the values from workflow.json.
    Returns the count of stages that received at least one update.
    """
    n_updated = 0
    for task in workflow.stages:
        tf = task.get("timeframe", -1)
        name = task["name"]
        gname = "_".join(name.split("_")[:-1]) if tf >= 1 else name
        data = learned.get(gname)
        if not isinstance(data, dict):
            continue
        updated = False
        if "lifetime" in fields:
            wt = data.get("lifetime", {}).get("mean")
            if wt is not None:
                task["resources"]["walltime"] = float(wt)
                updated = True
        if "mem" in fields:
            mem = data.get("pss", {}).get("max")
            if mem is not None:
                task["resources"]["mem"] = float(mem)
                updated = True
        if "cpu" in fields:
            cpu = data.get("cpu", {}).get("mean")
            if cpu is not None:
                task["resources"]["cpu"] = float(cpu)
                updated = True
        if updated:
            n_updated += 1
    return n_updated


@dataclass
class AmdahlModel:
    """Amdahl scaling model derived from a single measurement point.

    walltime(n) = t_serial + t_parallel_tot / n

    t_serial and t_parallel_tot are solved from:
      walltime_ref  = t_serial + t_parallel_tot / n_ref
      cpu_mean_ref  = (t_serial + t_parallel_tot) / walltime_ref
    """
    t_serial: float
    t_parallel_tot: float
    n_ref: int
    cpu_mean_ref: float
    min_workers: int = 1
    max_workers: int = 1

    def walltime(self, n: int) -> float:
        return max(1e-3, self.t_serial + self.t_parallel_tot / max(1, n))

    @property
    def worker_range(self) -> List[int]:
        return list(range(self.min_workers, self.max_workers + 1))

    @classmethod
    def from_dict(cls, d: dict) -> "AmdahlModel":
        model = cls(
            t_serial=float(d["t_serial"]),
            t_parallel_tot=float(d["t_parallel_tot"]),
            n_ref=int(d["n_ref"]),
            cpu_mean_ref=float(d["cpu_mean_ref"]),
            min_workers=int(d.get("min_workers", 1)),
            max_workers=int(d.get("max_workers", d["n_ref"])),
        )
        if model.t_serial < 0 or model.t_parallel_tot < 0:
            raise ValueError("Amdahl model has negative serial/parallel component")
        if model.n_ref < 1 or model.min_workers < 1 or model.max_workers < model.min_workers:
            raise ValueError("Amdahl model has invalid worker bounds")
        return model


def _sample_walltime(mean: float, std: float, rng: random.Random) -> float:
    """Draw a walltime sample from a log-normal distribution.

    Log-normal is a natural model for walltime: always positive, right-skewed
    (occasional slow outliers).  When std=0 the mean is returned unchanged.
    """
    if std <= 1e-9 or mean <= 1e-9:
        return max(1e-3, mean)
    cv = std / mean
    sigma2 = math.log(1.0 + cv * cv)
    mu = math.log(mean) - 0.5 * sigma2
    return max(1e-3, rng.lognormvariate(mu, math.sqrt(sigma2)))


def _build_rm(
    workflow,
    cpu_limit: float,
    mem_limit: float,
    cpu_overrides: Optional[Dict[int, float]] = None,
    n_backfill_max: int = 0,
    backfill_cpu_factor: float = 1.5,
    backfill_mem_factor: float = 1.5,
    maxjobs: int = 10_000,
) -> Tuple[ResourceManager, Set[int]]:
    """Fresh ResourceManager with no backfill tier and unlimited job slots.

    *cpu_overrides* maps tid → cpu to override resources.cpu for specific
    tasks (used by the worker-count optimizer).
    """
    rm = ResourceManager(
        cpu_limit=cpu_limit,
        mem_limit=mem_limit,
        procs_parallel_max=maxjobs,
        n_backfill_max=n_backfill_max,
        backfill_cpu_factor=backfill_cpu_factor,
        backfill_mem_factor=backfill_mem_factor,
        dynamic_resources=False,
        optimistic_resources=True,
    )
    impossible_tids: Set[int] = set()
    for i, task in enumerate(workflow.stages):
        rel = None
        try:
            rv = task["resources"].get("relative_cpu")
            rel = float(rv) if rv is not None else None
        except (TypeError, ValueError):
            pass
        cpu = float(task["resources"]["cpu"])
        if cpu_overrides and i in cpu_overrides:
            cpu = cpu_overrides[i]
        mem = float(task["resources"]["mem"])
        if cpu > cpu_limit or mem > mem_limit:
            impossible_tids.add(i)
        try:
            rm.add_task(
                name=task["name"],
                related_name=_global_name(task["name"]),
                cpu=cpu,
                cpu_relative=rel,
                mem=mem,
                semaphore_string=task.get("semaphore"),
            )
        except ResourceLimitExceeded as e:
            print(f"  WARNING: task {task['name']} exceeds limits and will never run: {e}",
                  file=sys.stderr)
    if impossible_tids:
        names = [workflow.stages[i]["name"] for i in sorted(impossible_tids)]
        print(
            "  WARNING: tasks exceed the hard simulator limits and will remain unscheduled: "
            f"{names[:5]}{'...' if len(names) > 5 else ''}",
            file=sys.stderr,
        )
    return rm, impossible_tids


def _build_state(
    workflow,
    cpu_fallback_factor: float,
    cpu_overrides: Optional[Dict[int, float]] = None,
    walltime_overrides: Optional[Dict[int, float]] = None,
) -> SchedulerState:
    n = workflow.n_tasks()
    desc_cache: Dict = {}
    desc_counts = [len(descendants(workflow.forward_adj, tid, desc_cache))
                   for tid in range(n)]

    timeframe_of = [t.get("timeframe", -1) for t in workflow.stages]
    tf_weight = [(timeframe_of[i], desc_counts[i]) for i in range(n)]

    cpu = [float(t.get("resources", {}).get("cpu", 1.0)) for t in workflow.stages]
    if cpu_overrides:
        for tid, value in cpu_overrides.items():
            cpu[tid] = float(value)
    mem = [float(t.get("resources", {}).get("mem", 0.0)) for t in workflow.stages]
    walltime = [_task_walltime(t, cpu_fallback_factor) for t in workflow.stages]
    if walltime_overrides:
        for tid, value in walltime_overrides.items():
            walltime[tid] = float(value)

    has_walltime = any(t.get("resources", {}).get("walltime") for t in workflow.stages)
    cp_weight = walltime if has_walltime else cpu
    topo = kahn_topological_order(n, workflow.forward_adj, workflow.indegree)
    cp = longest_path_length(workflow.forward_adj, topo, cp_weight)

    return SchedulerState(
        timeframe_of=timeframe_of,
        descendants_count=desc_counts,
        critical_path=cp,
        task_cpu=cpu,
        task_mem=mem,
        task_walltime=walltime,
        timeframe_weight=tf_weight,
    )


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

def simulate(
    workflow,
    policy_name: str,
    cpu_limit: float,
    mem_limit: float,
    cpu_fallback_factor: float = 10.0,
    task_overhead: float = 0.1,
    walltime_stds: Optional[Dict[str, float]] = None,
    cv_fallback: float = 0.15,
    rng: Optional[random.Random] = None,
    amdahl_models: Optional[Dict[str, "AmdahlModel"]] = None,
    worker_assignment: Optional[Dict[str, int]] = None,
    backfill_model: str = "off",
    n_backfill: int = 1,
    backfill_cpu_factor: float = 1.5,
    backfill_mem_factor: float = 1.5,
    backfill_slowdown_factor: float = 1.15,
    maxjobs: int = 10_000,
) -> SimResult:
    """Run one discrete-event simulation; return SimResult.

    When *rng* is provided, each task's walltime is sampled from
    log-normal(mean, std).  The std is taken from *walltime_stds* when
    available; otherwise *cv_fallback* × mean is used as a noise floor.

    When *amdahl_models* and *worker_assignment* are both provided, walltime
    and cpu booking for scalable tasks are derived from the Amdahl model at
    the assigned worker count rather than from the workflow resources.
    """
    mean_walltimes = [_task_walltime(t, cpu_fallback_factor) for t in workflow.stages]

    # Apply Amdahl model overrides for scalable tasks.
    cpu_overrides: Dict[int, float] = {}
    walltime_overrides: Dict[int, float] = {}
    if amdahl_models and worker_assignment:
        for i, task in enumerate(workflow.stages):
            base = _global_name(task["name"])
            model = amdahl_models.get(base)
            n = worker_assignment.get(base)
            if model is not None and n is not None:
                mean_walltimes[i] = model.walltime(n)
                walltime_overrides[i] = mean_walltimes[i]
                cpu_overrides[i] = float(n)

    state = _build_state(
        workflow,
        cpu_fallback_factor,
        cpu_overrides=cpu_overrides or None,
        walltime_overrides=walltime_overrides or None,
    )

    # Sample walltimes for this simulation run.
    if rng is not None:
        walltimes = []
        for i, task in enumerate(workflow.stages):
            mean_wt = mean_walltimes[i]
            base = _global_name(task["name"])
            std_wt = (walltime_stds or {}).get(base, 0.0)
            if std_wt <= 0 and cv_fallback > 0:
                std_wt = mean_wt * cv_fallback
            walltimes.append(_sample_walltime(mean_wt, std_wt, rng))
    else:
        walltimes = mean_walltimes

    if policy_name == "timeframe":
        policy = TimeframeFirstPolicy(drop_should_break=False)
    else:
        policy = get_policy(policy_name)

    use_backfill = backfill_model in ("structural", "slowdown", "holefill")
    rm, impossible_tids = _build_rm(
        workflow,
        cpu_limit,
        mem_limit,
        cpu_overrides=cpu_overrides or None,
        n_backfill_max=n_backfill if use_backfill else 0,
        backfill_cpu_factor=backfill_cpu_factor,
        backfill_mem_factor=backfill_mem_factor,
        maxjobs=maxjobs,
    )

    n = workflow.n_tasks()
    proc_status = ["ToDo"] * n
    candidates: List[int] = [
        i for i in range(n) if workflow.indegree[i] == 0 and i not in impossible_tids
    ]
    finished: Set[int] = set()
    running: List[Tuple[int, float]] = []   # (tid, finish_time)
    result = SimResult(policy=policy_name, makespan=0.0)
    t = 0.0

    if backfill_model == "holefill":
        running_fg: List[Tuple[int, float]] = []
        running_bf: Dict[int, _RunningBackfill] = {}
        launch_seq = 0

        for _guard in range(n * n + 1):
            ordered = policy.order(candidates, state)
            for tid, nice in policy.pick_submittable(ordered, rm):
                if nice != rm.nice_default and rm.cpu_free_default() <= 1e-9:
                    continue
                rm.book(tid, nice)
                candidates.remove(tid)
                proc_status[tid] = "Running"
                res = rm.resources[tid]
                if nice == rm.nice_default:
                    compute_wt = walltimes[tid]
                    wt = compute_wt + task_overhead
                    finish = t + wt
                    fg_cpu = res.cpu_assigned * (compute_wt / wt) if wt > 0 else 0.0
                    task = SimTask(
                        tid=tid,
                        name=workflow.id_to_name[tid],
                        start=t,
                        finish=finish,
                        cpu=fg_cpu,
                        cpu_booked=res.cpu_assigned,
                        mem=res.mem_assigned,
                        walltime=wt,
                    )
                    running_fg.append((tid, finish))
                    result.tasks.append(task)
                else:
                    launch_seq += 1
                    task = SimTask(
                        tid=tid,
                        name=workflow.id_to_name[tid],
                        start=t,
                        finish=t,
                        cpu=0.0,
                        cpu_booked=res.cpu_assigned,
                        mem=res.mem_assigned,
                        walltime=0.0,
                    )
                    nominal_work = res.cpu_assigned * walltimes[tid]
                    running_bf[tid] = _RunningBackfill(
                        task=task,
                        nominal_work=nominal_work,
                        remaining_work=nominal_work,
                        launch_seq=launch_seq,
                    )
                    result.tasks.append(task)

            if not running_fg and not running_bf:
                break

            next_fg = min((ft for _, ft in running_fg), default=float("inf"))
            cpu_fg = sum(
                next(task.cpu_booked for task in result.tasks if task.tid == tid)
                for tid, _ in running_fg
            )
            hole_cpu = max(0.0, cpu_limit - cpu_fg)
            remaining_hole = hole_cpu
            bf_alloc: Dict[int, float] = {}
            for tid, rb in sorted(running_bf.items(), key=lambda item: item[1].launch_seq):
                if rb.overhead_until is not None:
                    bf_alloc[tid] = 0.0
                    continue
                alloc = min(rb.task.cpu_booked, remaining_hole)
                bf_alloc[tid] = alloc
                remaining_hole -= alloc

            next_bf = float("inf")
            for tid, rb in running_bf.items():
                if rb.overhead_until is not None:
                    next_bf = min(next_bf, rb.overhead_until)
                else:
                    alloc = bf_alloc.get(tid, 0.0)
                    if alloc > 1e-12:
                        next_bf = min(next_bf, t + rb.remaining_work / alloc)

            next_t = min(next_fg, next_bf)
            if not math.isfinite(next_t):
                break
            dt = max(0.0, next_t - t)
            for tid, rb in running_bf.items():
                if rb.overhead_until is None:
                    alloc = bf_alloc.get(tid, 0.0)
                    if alloc > 0.0:
                        rb.remaining_work = max(0.0, rb.remaining_work - alloc * dt)
            t = next_t

            new_running_fg: List[Tuple[int, float]] = []
            for tid, ft in running_fg:
                if abs(ft - t) < 1e-9:
                    rm.unbook(tid)
                    proc_status[tid] = "Done"
                    finished.add(tid)
                    for succ in workflow.forward_adj[tid]:
                        if proc_status[succ] == "ToDo":
                            if succ in impossible_tids:
                                continue
                            if all(p in finished for p in workflow.reverse_adj[succ]):
                                candidates.append(succ)
                else:
                    new_running_fg.append((tid, ft))
            running_fg = new_running_fg

            done_bf: List[int] = []
            for tid, rb in running_bf.items():
                if rb.overhead_until is not None:
                    if abs(rb.overhead_until - t) < 1e-9:
                        done_bf.append(tid)
                    continue
                if rb.remaining_work <= 1e-9:
                    if task_overhead > 0:
                        rb.overhead_until = t + task_overhead
                    else:
                        done_bf.append(tid)

            for tid in done_bf:
                rb = running_bf.pop(tid)
                rb.task.finish = t
                rb.task.walltime = max(1e-9, rb.task.finish - rb.task.start)
                rb.task.cpu = rb.nominal_work / rb.task.walltime
                rm.unbook(tid)
                proc_status[tid] = "Done"
                finished.add(tid)
                for succ in workflow.forward_adj[tid]:
                    if proc_status[succ] == "ToDo":
                        if succ in impossible_tids:
                            continue
                        if all(p in finished for p in workflow.reverse_adj[succ]):
                            candidates.append(succ)

            if not candidates and not running_fg and not running_bf:
                break
        else:
            print(f"  WARNING [{policy_name}]: simulation hit guard limit — possible deadlock",
                  file=sys.stderr)

        result.makespan = t
        result.deadlocked_tids = [
            i for i, s in enumerate(proc_status) if s == "ToDo"
        ]
        if result.deadlocked_tids:
            names = [workflow.id_to_name[i] for i in result.deadlocked_tids]
            print(f"  WARNING [{policy_name}]: {len(names)} tasks never scheduled "
                  f"(resource limits too tight?): {names[:5]}{'...' if len(names) > 5 else ''}",
                  file=sys.stderr)
        return result

    for _guard in range(n * n + 1):   # at most n rounds to completion
        # --- schedule everything that fits right now ---
        ordered = policy.order(candidates, state)
        for tid, nice in policy.pick_submittable(ordered, rm):
            # book immediately so subsequent picks in this pass see the
            # updated resource availability (mirrors executor behaviour)
            rm.book(tid, nice)
            slowdown = 1.0
            if backfill_model == "slowdown" and nice != rm.nice_default:
                slowdown = backfill_slowdown_factor
            compute_wt = walltimes[tid] * slowdown   # time spent doing actual work
            wt = compute_wt + task_overhead           # total slot duration (incl. idle overhead)
            finish = t + wt
            running.append((tid, finish))
            candidates.remove(tid)
            proc_status[tid] = "Running"
            res = rm.resources[tid]
            # Overhead is idle time (process start/stop, alienv load, I/O flush).
            # Average CPU over the full slot = booked_cpu × compute_fraction only.
            effective_cpu = res.cpu_assigned / slowdown * (compute_wt / wt) if wt > 0 else 0.0
            result.tasks.append(SimTask(
                tid=tid,
                name=workflow.id_to_name[tid],
                start=t,
                finish=finish,
                cpu=effective_cpu,
                cpu_booked=res.cpu_assigned,
                mem=res.mem_assigned,
                walltime=wt,
            ))

        if not running:
            break

        # --- advance to next task completion ---
        next_t = min(ft for _, ft in running)
        t = next_t

        # --- complete all tasks finishing at t (within float tolerance) ---
        still_running: List[Tuple[int, float]] = []
        for tid, ft in running:
            if abs(ft - t) < 1e-9:
                rm.unbook(tid)
                proc_status[tid] = "Done"
                finished.add(tid)
                for succ in workflow.forward_adj[tid]:
                    if proc_status[succ] == "ToDo":
                        if succ in impossible_tids:
                            continue
                        if all(p in finished for p in workflow.reverse_adj[succ]):
                            candidates.append(succ)
            else:
                still_running.append((tid, ft))
        running = still_running

        if not candidates and not running:
            break
    else:
        print(f"  WARNING [{policy_name}]: simulation hit guard limit — possible deadlock",
              file=sys.stderr)

    result.makespan = t
    result.deadlocked_tids = [
        i for i, s in enumerate(proc_status) if s == "ToDo"
    ]
    if result.deadlocked_tids:
        names = [workflow.id_to_name[i] for i in result.deadlocked_tids]
        print(f"  WARNING [{policy_name}]: {len(names)} tasks never scheduled "
              f"(resource limits too tight?): {names[:5]}{'...' if len(names) > 5 else ''}",
              file=sys.stderr)
    return result


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

def _fmt_time(s: float) -> str:
    return f"{s:.1f}s"


def print_summary(
    results_by_policy: Dict[str, List[SimResult]],
    cpu_limit: float,
    n_samples: int,
) -> None:
    w = 16
    stoch = n_samples > 1
    mk_hdr = f"{'Makespan (mean±std)':>22}" if stoch else f"{'Makespan':>10}"
    cpu_hdr = f"{'CPU util (mean±std)':>20}" if stoch else f"{'CPU util':>9}"
    mem_hdr = f"{'Peak mem (mean±std)':>22}" if stoch else f"{'Peak mem':>10}"
    header = f"{'Policy':<{w}} {mk_hdr} {cpu_hdr} {mem_hdr} {'Tasks':>6}"
    print()
    print(header)
    print("-" * len(header))
    for policy, runs in results_by_policy.items():
        makespans = [r.makespan for r in runs]
        mean_mk = statistics.mean(makespans)
        util_pct = statistics.mean(r.cpu_utilization(cpu_limit) * 100 for r in runs)
        peak = statistics.mean(r.peak_mem_mb() for r in runs)
        n_tasks = runs[0].tasks.__len__() if runs else 0
        if stoch:
            std_mk   = statistics.stdev(makespans) if len(makespans) > 1 else 0.0
            std_util = statistics.stdev(r.cpu_utilization(cpu_limit)*100 for r in runs) if len(runs)>1 else 0.0
            std_peak = statistics.stdev(r.peak_mem_mb() for r in runs) if len(runs)>1 else 0.0
            mk_str   = f"{_fmt_time(mean_mk)} ± {_fmt_time(std_mk)}"
            print(f"{policy:<{w}} {mk_str:>22} {util_pct:>7.1f}±{std_util:.1f}% {peak:>8.0f}±{std_peak:.0f}MB {n_tasks:>6}")
        else:
            print(f"{policy:<{w}} {_fmt_time(mean_mk):>10} {util_pct:>8.1f}% "
                  f"{peak:>9.0f}MB {n_tasks:>6}")
    print()


def print_verbose(result: SimResult) -> None:
    print(f"\n--- Schedule: {result.policy} ---")
    prev_t = -1.0
    for task in sorted(result.tasks, key=lambda x: (x.start, x.name)):
        if abs(task.start - prev_t) > 1e-9:
            print(f"  t={_fmt_time(task.start)}")
            prev_t = task.start
        print(f"    START  {task.name:<40}  "
              f"cpu={task.cpu:.1f}"
              + (f" ({task.cpu_booked:.1f} booked)" if abs(task.cpu - task.cpu_booked) > 1e-9 else "")
              + f"  mem={task.mem:.0f}MB  "
              f"dur={_fmt_time(task.walltime)}")
    print(f"  Makespan: {_fmt_time(result.makespan)}")


def _print_sweep_table(
    sweep_results: "List[Tuple]",   # (M, results_by_policy, n_stages, worker_assignment|None)
    cpu_limit: float,
    n_samples: int,
) -> None:
    """Print a compact table summarising a timeframe-sweep simulation run."""
    stoch = n_samples > 1

    # Collect all scalable task names that appear in any worker assignment.
    scalable_names: List[str] = []
    seen_names: "Set[str]" = set()
    for _, _, _, wa in sweep_results:
        if wa:
            for name in sorted(wa):
                if name not in seen_names:
                    scalable_names.append(name)
                    seen_names.add(name)

    # Build header with optional per-task worker columns.
    worker_cols = "  ".join(f"{n[:12]:>12}" for n in scalable_names)
    cpu_col_hdr = f"{'CPU util(±std)':>14}" if stoch else f"{'CPU util':>9}"
    hdr = (f"  {'M':>4}  {'Policy':<16}  {'N tasks':>7}  "
           f"{'Makespan':>12}  {cpu_col_hdr}  {'Peak mem':>9}"
           + (f"  {worker_cols}" if scalable_names else ""))
    cpu_col_w = 14 if stoch else 9
    print("\nTimeframe sweep results:")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    for M, results_by_policy, n_stages, worker_assignment in sweep_results:
        m_str = str(M) if M is not None else "orig"
        for policy, runs in results_by_policy.items():
            makespans = [r.makespan for r in runs]
            mean_mk = statistics.mean(makespans)
            util_pct = statistics.mean(r.cpu_utilization(cpu_limit) * 100 for r in runs)
            peak = statistics.mean(r.peak_mem_mb() for r in runs)
            if stoch and len(runs) > 1:
                std_mk = statistics.stdev(makespans)
                mk_str = f"{_fmt_time(mean_mk)}±{_fmt_time(std_mk)}"
                std_util = statistics.stdev(r.cpu_utilization(cpu_limit) * 100 for r in runs)
                util_str = f"{util_pct:.1f}±{std_util:.1f}%"
            else:
                mk_str = _fmt_time(mean_mk)
                util_str = f"{util_pct:.1f}%"
            row = (f"  {m_str:>4}  {policy:<16}  {n_stages:>7}  "
                   f"{mk_str:>12}  {util_str:>{cpu_col_w}}  {peak:>7.0f}MB")
            if scalable_names and worker_assignment:
                wvals = "  ".join(
                    f"{worker_assignment.get(n, '-'):>12}"
                    for n in scalable_names
                )
                row += f"  {wvals}"
            print(row)
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def optimize_workers(
    workflow,
    policy_name: str,
    cpu_limit: float,
    mem_limit: float,
    amdahl_models: Dict[str, AmdahlModel],
    cpu_fallback_factor: float = 10.0,
    task_overhead: float = 0.1,
    n_eval_samples: int = 3,
    rng_seed: int = 0,
    backfill_model: str = "off",
    n_backfill: int = 1,
    backfill_cpu_factor: float = 1.5,
    backfill_mem_factor: float = 1.5,
    backfill_slowdown_factor: float = 1.15,
    maxjobs: int = 10_000,
) -> Tuple[Dict[str, int], float]:
    """Coordinate-descent search for the best worker assignment.

    For each scalable task, iterates over its valid worker range (from the
    Amdahl model) and picks the count that minimises mean makespan while
    holding all other tasks fixed.  Repeats until no improvement is found.

    Returns (best_assignment, best_makespan_s).
    """
    # Start from the current assignment implied by each model's cpu_mean_ref
    # (what update_resource_estimates already set via round(cpu_mean)).
    assignment: Dict[str, int] = {
        name: max(model.min_workers,
                  min(model.max_workers, max(1, round(model.cpu_mean_ref))))
        for name, model in amdahl_models.items()
    }

    walltime_stds: Dict[str, float] = {}   # no learned std for optimizer runs

    def _evaluate(asgn: Dict[str, int]) -> float:
        makespans = []
        for s in range(n_eval_samples):
            rng = random.Random(rng_seed + s) if n_eval_samples > 1 else None
            r = simulate(
                workflow, policy_name, cpu_limit, mem_limit,
                cpu_fallback_factor=cpu_fallback_factor,
                task_overhead=task_overhead,
                walltime_stds=walltime_stds,
                cv_fallback=0.1,
                rng=rng,
                amdahl_models=amdahl_models,
                worker_assignment=asgn,
                backfill_model=backfill_model,
                n_backfill=n_backfill,
                backfill_cpu_factor=backfill_cpu_factor,
                backfill_mem_factor=backfill_mem_factor,
                backfill_slowdown_factor=backfill_slowdown_factor,
                maxjobs=maxjobs,
            )
            makespans.append(r.makespan)
        return statistics.mean(makespans)

    best_score = _evaluate(assignment)
    improved = True
    while improved:
        improved = False
        for name, model in amdahl_models.items():
            best_n = assignment[name]
            for n in model.worker_range:
                if n == best_n:
                    continue
                trial = dict(assignment)
                trial[name] = n
                score = _evaluate(trial)
                if score < best_score - 0.1:   # 0.1 s improvement threshold
                    best_score = score
                    best_n = n
                    improved = True
            assignment[name] = best_n
    return assignment, best_score


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Simulate O2DPG workflow scheduling without running tasks.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("-f", "--workflowfile", required=True)
    p.add_argument("--update-resources", dest="update_resources", default=None,
                   metavar="JSON[:FIELDS]",
                   help="Apply learned resources from JSON (same file as "
                        "--update-resources in the runner). Enables walltime-based "
                        "critical path. Optionally restrict which dimensions are "
                        "patched with a colon-separated field list chosen from "
                        "{cpu,mem,lifetime}. Example: learned.json:lifetime applies "
                        "only walltimes, keeping cpu/mem from workflow.json.")
    p.add_argument("--cpu-limit", type=float, default=8.0)
    p.add_argument("--mem-limit", type=float, default=60000.0, help="in MB")
    p.add_argument("--policies", nargs="+",
                   default=["timeframe", "critical-path", "best-fit"],
                   choices=["timeframe", "critical-path", "best-fit"])
    p.add_argument("-tt", "--target-tasks", nargs="+", default=["*"])
    p.add_argument("--target-labels", nargs="+", default=[])
    p.add_argument("--walltime-per-core", type=float, default=10.0, metavar="S",
                   help="Fallback walltime per CPU core [s] when no learned "
                        "walltime is available.")
    p.add_argument("--task-overhead", type=float, default=0.1, metavar="S",
                   help="Per-task idle overhead [s] added to every task's slot "
                        "duration (models alienv load, process startup, I/O flush, "
                        "and scheduler reaction time).  This time contributes zero "
                        "CPU to the utilisation numerator, so larger values lower "
                        "both predicted makespan and CPU efficiency.  "
                        "Default 0.1 s is conservative; calibration against "
                        "measurements typically gives 5–7 s for production "
                        "ALICE MC workflows.")
    p.add_argument("--backfill-model", default="off",
                   choices=["off", "structural", "slowdown", "holefill"],
                   help="Backfill approximation used by the simulator. "
                        "'structural' replays the runner's second admission lane; "
                        "'slowdown' adds a fitted walltime penalty to backfill tasks; "
                        "'holefill' lets backfill tasks consume only the CPU left idle "
                        "by foreground tasks, slowing them proportionally.")
    p.add_argument("--n-backfill", type=int, default=1, metavar="N",
                   help="Maximum concurrent backfill tasks when backfill simulation is enabled.")
    p.add_argument("--backfill-cpu-factor", type=float, default=1.5, metavar="X",
                   help="Total CPU oversubscription factor allowed for backfill admission.")
    p.add_argument("--backfill-mem-factor", type=float, default=1.5, metavar="X",
                   help="Total memory oversubscription factor allowed for backfill admission.")
    p.add_argument("--backfill-slowdown-factor", type=float, default=1.15, metavar="X",
                   help="Walltime multiplier applied to backfill tasks in "
                        "--backfill-model slowdown.")
    p.add_argument("--samples", type=int, default=1, metavar="N",
                   help="Number of Monte Carlo samples for stochastic simulation. "
                        "When >1, walltime for each task is drawn from a log-normal "
                        "distribution parameterised by lifetime.mean and lifetime.std "
                        "from the learned JSON.  Output shows mean ± std of makespan.")
    p.add_argument("--cv-fallback", type=float, default=0.15, metavar="CV",
                   help="Coefficient of variation (std/mean) used as a noise floor "
                        "for tasks whose learned walltime std is zero or absent "
                        "(single-TF runs, old learned files, etc.). "
                        "0 disables fallback and makes those tasks deterministic.")
    p.add_argument("-j", "--maxjobs", type=int, default=0, metavar="N",
                   help="Maximum concurrent tasks. -1 = serial mode (1 task at a time): "
                        "reproduces the learning-run conditions (-jmax 1) and makes the "
                        "optimizer prefer maximum workers per task. 0 = unlimited (default). "
                        "N > 0 = at most N concurrent tasks.")
    p.add_argument("--optimize-workers", action="store_true",
                   help="Run coordinate-descent optimizer to find the best worker "
                        "assignment for scalable tasks.  Requires --update-resources "
                        "with a learned.json that contains 'amdahl' blocks (produced "
                        "by json-stat --workflow workflow.json).")
    p.add_argument("--opt-eval-samples", type=int, default=3, metavar="N",
                   help="Simulator evaluations per candidate during optimization "
                        "(more = less noise, slower).")
    p.add_argument("--write-optimized", default=None, metavar="FILE",
                   help="After --optimize-workers, write a copy of the learned JSON "
                        "with updated lifetime.mean and cpu.mean for scalable tasks. "
                        "Pass this file to --update-resources in the runner to apply "
                        "optimized worker counts.  When multiple --policies are given "
                        "the policy with the best (lowest) optimized makespan is used.")
    p.add_argument("--verbose", action="store_true",
                   help="Print per-task schedule for each policy.")
    p.add_argument("--output", default=None, metavar="FILE",
                   help="Write results as JSON to FILE.")
    p.add_argument("--timeframes", type=int, nargs="+", default=None, metavar="M",
                   help="Simulate with M timeframes instead of the workflow's original count. "
                        "Detects the per-TF template structure automatically and replicates it. "
                        "Pass multiple values for a sweep (e.g. --timeframes 1 2 5 10 20) to "
                        "produce a table of makespan and CPU utilisation vs timeframe count.")
    return p


def main(argv=None) -> int:
    ns = build_parser().parse_args(argv)

    raw = load_json(ns.workflowfile)
    target_tasks = [t.strip('"').strip("'") for t in ns.target_tasks]

    # ── Parse --update-resources path[:field,field,...] ───────────────────────
    ur_path: Optional[str] = None
    ur_fields: Optional[Set[str]] = None   # None = all three fields
    if ns.update_resources:
        _parts = ns.update_resources.split(":", 1)
        ur_path = _parts[0]
        if len(_parts) > 1:
            _raw_fields = {f.strip().lower() for f in _parts[1].split(",")}
            _bad = _raw_fields - _LEARN_ALL
            if _bad:
                print(f"ERROR: unknown field(s) in --update-resources specifier: "
                      f"{sorted(_bad)}.  Valid: cpu, mem, lifetime", file=sys.stderr)
                return 1
            ur_fields = _raw_fields

    # ── Load learned JSON once (independent of timeframe count) ──────────────
    walltime_stds: Dict[str, float] = {}
    learned_full: Dict = {}
    amdahl_models: Dict[str, AmdahlModel] = {}

    if ur_path:
        _active = ur_fields if ur_fields is not None else _LEARN_ALL
        _fields_str = ", ".join(sorted(_active))
        print(f"Applying learned resources from {ur_path}"
              + (f" (fields: {_fields_str})" if ur_fields is not None else "")
              + " ...")
        with open(ur_path) as fh:
            learned_full = json.load(fh)
        apply_lifetime = "lifetime" in _active
        for name, data in learned_full.items():
            if name == "count":
                continue
            if ns.samples > 1 and apply_lifetime:
                std = data.get("lifetime", {}).get("std", 0.0) or 0.0
                if std > 0:
                    walltime_stds[name] = float(std)
            if isinstance(data, dict) and "amdahl" in data:
                try:
                    amdahl_models[name] = AmdahlModel.from_dict(data["amdahl"])
                except (KeyError, ValueError):
                    pass
        if amdahl_models:
            print(f"  Amdahl models loaded for {len(amdahl_models)} scalable task(s): "
                  f"{', '.join(sorted(amdahl_models))}")
    else:
        print(f"No learned resources; using cpu * {ns.walltime_per_core}s as walltime proxy.")

    stochastic = ns.samples > 1
    if stochastic:
        n_with_std = len(walltime_stds)
        print(f"  Stochastic: {n_with_std} tasks use learned std, "
              f"cv_fallback={ns.cv_fallback:.2f} for the rest.")
    if ns.backfill_model != "off":
        print(
            "Backfill simulation: "
            f"model={ns.backfill_model}, n_backfill={ns.n_backfill}, "
            f"cpu_factor={ns.backfill_cpu_factor}, mem_factor={ns.backfill_mem_factor}, "
            + (
                f"slowdown={ns.backfill_slowdown_factor:.2f}x\n"
                if ns.backfill_model == "slowdown"
                else "foreground-hole driven\n"
                if ns.backfill_model == "holefill"
                else "\n"
            )
        )

    # Verbose Amdahl model summary (shown once, outside the sweep loop).
    if amdahl_models and ns.verbose:
        print()
        for name, model in sorted(amdahl_models.items()):
            n_cur = max(model.min_workers,
                        min(model.max_workers, max(1, round(model.cpu_mean_ref))))
            print(f"  Amdahl: {name}  "
                  f"(n_ref={model.n_ref}, cpu_mean={model.cpu_mean_ref:.2f}, "
                  f"t_serial={model.t_serial:.1f}s, "
                  f"t_parallel_tot={model.t_parallel_tot:.1f}s)")
            print(f"    {'n':>4}  {'walltime':>10}  {'Δ vs current':>14}")
            wt_cur = model.walltime(n_cur)
            for n in model.worker_range:
                wt = model.walltime(n)
                marker = " ← current" if n == n_cur else ""
                print(f"    {n:>4}  {_fmt_time(wt):>10}  "
                      f"{wt - wt_cur:>+12.1f}s{marker}")
            print()

    # Resolve maxjobs — must come before optimizer and policy loops.
    # -j -1 → serial + n_ref workers  -j 1 → serial + round(cpu_mean) workers
    # -j  0 → unlimited (default)      -j N → at most N concurrent tasks
    serial_mode = ns.maxjobs == -1
    procs_limit = 1 if (serial_mode or ns.maxjobs == 1) else (10_000 if ns.maxjobs <= 0 else ns.maxjobs)
    if serial_mode:
        print("Serial mode (-j -1): reproducing learning-run conditions "
              "(1 task at a time, n_ref workers per scalable task).")

    # Default worker assignment: Amdahl-based, same for all M values in a sweep.
    default_worker_assignment: Optional[Dict[str, int]] = None
    if amdahl_models:
        if serial_mode:
            default_worker_assignment = {name: m.n_ref for name, m in amdahl_models.items()}
            parts = [f"{n}: {w}w (n_ref)" for n, w in sorted(default_worker_assignment.items())]
        else:
            default_worker_assignment = {
                name: max(m.min_workers, min(m.max_workers, max(1, round(m.cpu_mean_ref))))
                for name, m in amdahl_models.items()
            }
            parts = [f"{n}: {w}w" for n, w in sorted(default_worker_assignment.items())]
        print(f"Worker counts for simulation: {', '.join(parts)}\n")

    # ── Timeframe sweep ───────────────────────────────────────────────────────
    tf_list: List[Optional[int]] = sorted(set(ns.timeframes)) if ns.timeframes else [None]
    sweep_mode = len(tf_list) > 1
    if sweep_mode:
        print(f"Timeframe sweep: M={tf_list}  policies={ns.policies}  "
              f"cpu_limit={ns.cpu_limit}  mem_limit={ns.mem_limit} MB\n")

    all_sweep_results: List[Tuple] = []   # (M, results_by_policy, n_stages, worker_assignment)
    last_opt_results: List[Tuple[str, Dict[str, int], float]] = []

    for M in tf_list:
        if sweep_mode:
            print(f"  M={M} ...", end=" ", flush=True)

        cur_raw = replicate_workflow_for_timeframes(raw, M) if M is not None else raw
        wf = build_workflow(cur_raw, target_tasks, ns.target_labels)
        if not wf.stages:
            print(f"Workflow is empty after filtering (M={M}).")
            continue

        if ur_path:
            if ur_fields is None:
                update_resource_estimates(wf, ur_path)
            else:
                _apply_learned_fields(wf, learned_full, ur_fields)
            has_wt = sum(1 for t in wf.stages if t.get("resources", {}).get("walltime"))
            if not sweep_mode:
                print(f"  {has_wt}/{len(wf.stages)} tasks have learned walltime.")
                if stochastic:
                    n_fallback = len(wf.stages) - len(walltime_stds)
                    print(f"  Stochastic: {len(walltime_stds)} tasks use learned std, "
                          f"{n_fallback} use cv_fallback={ns.cv_fallback:.2f}.")
        if not sweep_mode:
            print(f"Workflow: {len(wf.stages)} tasks, cpu_limit={ns.cpu_limit}, "
                  f"mem_limit={ns.mem_limit} MB, samples={ns.samples}"
                  + (" (stochastic)" if stochastic else " (deterministic)") + "\n")

        # Worker-count optimizer (--optimize-workers): runs per-M so that the
        # simulated workflow matches the actual task count.
        cur_worker_assignment = default_worker_assignment
        opt_results: List[Tuple[str, Dict[str, int], float]] = []
        if ns.optimize_workers:
            if not amdahl_models:
                print("WARNING: --optimize-workers requires Amdahl models in learned.json. "
                      "Re-run json-stat with --workflow workflow.json first.", file=sys.stderr)
            else:
                if not sweep_mode:
                    print(f"\nOptimizing worker assignment over "
                          f"{len(amdahl_models)} scalable task(s)...")
                for policy_name in ns.policies:
                    best_asgn, best_mk = optimize_workers(
                        wf, policy_name, ns.cpu_limit, ns.mem_limit,
                        amdahl_models=amdahl_models,
                        cpu_fallback_factor=ns.walltime_per_core,
                        task_overhead=ns.task_overhead,
                        n_eval_samples=ns.opt_eval_samples,
                        backfill_model=ns.backfill_model,
                        n_backfill=ns.n_backfill,
                        backfill_cpu_factor=ns.backfill_cpu_factor,
                        backfill_mem_factor=ns.backfill_mem_factor,
                        backfill_slowdown_factor=ns.backfill_slowdown_factor,
                        maxjobs=procs_limit,
                    )
                    opt_results.append((policy_name, best_asgn, best_mk))
                    if not sweep_mode:
                        print(f"\n  [{policy_name}] best makespan: {_fmt_time(best_mk)}")
                        print(f"  {'Task':<35} {'n_ref':>6} {'current':>8} {'→ opt':>6}  "
                              f"{'wt(current)':>12}  {'wt(opt)':>10}  {'Δwt':>8}")
                        print(f"  {'-'*85}")
                        for name, model in sorted(amdahl_models.items()):
                            n_cur = max(model.min_workers,
                                        min(model.max_workers, max(1, round(model.cpu_mean_ref))))
                            n_opt = best_asgn[name]
                            wt_cur = model.walltime(n_cur)
                            wt_opt = model.walltime(n_opt)
                            delta = wt_opt - wt_cur
                            changed = "←" if n_opt != n_cur else ""
                            print(f"  {name:<35} {model.n_ref:>6} {n_cur:>8} {n_opt:>6}  "
                                  f"{_fmt_time(wt_cur):>12}  {_fmt_time(wt_opt):>10}  "
                                  f"{delta:>+7.1f}s  {changed}")
                if not sweep_mode:
                    print()
                _, best_asgn_opt, _ = min(opt_results, key=lambda x: x[2])
                cur_worker_assignment = best_asgn_opt
                last_opt_results = opt_results

        # ── Run simulations ───────────────────────────────────────────────────
        results_by_policy: Dict[str, List[SimResult]] = {}
        for policy_name in ns.policies:
            runs: List[SimResult] = []
            for s in range(ns.samples):
                rng = random.Random(s) if stochastic else None
                r = simulate(
                    wf, policy_name,
                    cpu_limit=ns.cpu_limit,
                    mem_limit=ns.mem_limit,
                    cpu_fallback_factor=ns.walltime_per_core,
                    task_overhead=ns.task_overhead,
                    walltime_stds=walltime_stds,
                    cv_fallback=ns.cv_fallback,
                    rng=rng,
                    amdahl_models=amdahl_models if amdahl_models else None,
                    worker_assignment=cur_worker_assignment,
                    backfill_model=ns.backfill_model,
                    n_backfill=ns.n_backfill,
                    backfill_cpu_factor=ns.backfill_cpu_factor,
                    backfill_mem_factor=ns.backfill_mem_factor,
                    backfill_slowdown_factor=ns.backfill_slowdown_factor,
                    maxjobs=procs_limit,
                )
                runs.append(r)
            results_by_policy[policy_name] = runs
            if not sweep_mode:
                makespans = [r.makespan for r in runs]
                summary = _fmt_time(statistics.mean(makespans))
                if stochastic:
                    summary += f" ± {_fmt_time(statistics.stdev(makespans))}"
                print(f"  {policy_name:<16} makespan={summary}")

        all_sweep_results.append((M, results_by_policy, len(wf.stages), cur_worker_assignment))

        if sweep_mode:
            best_mk = min(
                statistics.mean(r.makespan for r in runs)
                for runs in results_by_policy.values()
            )
            print(f"{len(wf.stages)} tasks, best makespan={_fmt_time(best_mk)}")

    if not all_sweep_results:
        return 1

    # ── Summary ───────────────────────────────────────────────────────────────
    if sweep_mode:
        _print_sweep_table(all_sweep_results, ns.cpu_limit, ns.samples)
    else:
        _, results_by_policy, _, _ = all_sweep_results[0]
        print_summary(results_by_policy, ns.cpu_limit, ns.samples)
        if ns.verbose:
            for policy_name, runs in results_by_policy.items():
                print_verbose(runs[0])

    # ── Write optimized learned.json ──────────────────────────────────────────
    if ns.write_optimized and last_opt_results and learned_full:
        if sweep_mode:
            print(f"NOTE: --write-optimized in sweep mode writes the optimisation "
                  f"result from the last M={tf_list[-1]}.")
        best_policy, best_asgn, best_mk = min(last_opt_results, key=lambda x: x[2])
        if len(ns.policies) > 1:
            print(f"Writing optimized resources: policy '{best_policy}' "
                  f"selected (best makespan {_fmt_time(best_mk)}).")
        else:
            print(f"Writing optimized resources (makespan {_fmt_time(best_mk)}).")
        out_learned = copy.deepcopy(learned_full)
        n_changed = 0
        for name, model in amdahl_models.items():
            if name not in out_learned:
                continue
            n_opt = best_asgn[name]
            n_cur = max(model.min_workers,
                        min(model.max_workers, max(1, round(model.cpu_mean_ref))))
            if "lifetime" not in out_learned[name]:
                out_learned[name]["lifetime"] = {}
            out_learned[name]["lifetime"]["mean"] = round(model.walltime(n_opt), 3)
            if "cpu" not in out_learned[name]:
                out_learned[name]["cpu"] = {}
            out_learned[name]["cpu"]["mean"] = float(n_opt)
            if n_opt != n_cur:
                n_changed += 1
        with open(ns.write_optimized, "w") as fh:
            json.dump(out_learned, fh, indent=2)
        print(f"  Wrote {ns.write_optimized}  "
              f"({len(amdahl_models)} scalable tasks updated, "
              f"{n_changed} changed from current assignment).")

    # ── JSON output ───────────────────────────────────────────────────────────
    if ns.output:
        out_list = []
        for M, results_by_policy, n_stages, _ in all_sweep_results:
            for policy_name, runs in results_by_policy.items():
                for i, r in enumerate(runs):
                    d = r.to_dict()
                    d["sample"] = i
                    d["n_stages"] = n_stages
                    if M is not None:
                        d["timeframes"] = M
                    out_list.append(d)
        with open(ns.output, "w") as fh:
            json.dump(out_list, fh, indent=2)
        print(f"Results written to {ns.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
