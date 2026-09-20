"""Workflow loading, filtering, and DAG construction.

The workflow JSON schema is unchanged from the original. Key fields per
stage:
  - name: str
  - needs: list[str]  (names of upstream stages)
  - cmd: str
  - cwd: str
  - timeframe: int (-1 for global stages)
  - labels: list[str]
  - resources: {cpu, mem, relative_cpu}
  - semaphore: str (optional)
  - retry_count: int (optional)
  - alternative_alienv_package: str (optional)
  - env: dict (optional)

One stage may be the synthetic ``__global_init_task__`` at index 0,
holding global env and an optional init cmd; it is stripped from the
DAG during loading.
"""

from __future__ import annotations

import copy
import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .graph import build_adjacency

log = logging.getLogger(__name__)


@dataclass
class Workflow:
    """In-memory representation of a workflow after filtering.

    Tasks are stored as a list of dicts (the raw JSON objects) and indexed
    by integer ``tid``. The forward/reverse adjacency and derived quantities
    are computed once at construction time.
    """
    stages: List[Dict[str, Any]]
    global_env: Dict[str, str] = field(default_factory=dict)
    global_init_cmd: Optional[str] = None
    full_target_names: List[str] = field(default_factory=list)

    # Derived
    name_to_id: Dict[str, int] = field(default_factory=dict)
    id_to_name: List[str] = field(default_factory=list)
    forward_adj: List[List[int]] = field(default_factory=list)
    reverse_adj: List[List[int]] = field(default_factory=list)
    indegree: List[int] = field(default_factory=list)
    timeframes: Set[int] = field(default_factory=set)

    def __post_init__(self):
        self._rebuild_indices()

    def _rebuild_indices(self):
        self.name_to_id = {s["name"]: i for i, s in enumerate(self.stages)}
        self.id_to_name = [s["name"] for s in self.stages]
        edges: List[Tuple[int, int]] = []
        for i, s in enumerate(self.stages):
            for n in s.get("needs", []):
                if n in self.name_to_id:
                    edges.append((self.name_to_id[n], i))
        self.forward_adj, self.reverse_adj, self.indegree = build_adjacency(
            len(self.stages), edges
        )
        self.timeframes = {s.get("timeframe", -1) for s in self.stages}

    def tid(self, name: str) -> int:
        return self.name_to_id[name]

    def name(self, tid: int) -> str:
        return self.id_to_name[tid]

    def n_tasks(self) -> int:
        return len(self.stages)


def load_json(path: str) -> Dict[str, Any]:
    with open(path) as fp:
        return json.load(fp)


def extract_global_init(raw_spec: Dict[str, Any]) -> Tuple[Dict[str, str], Optional[str]]:
    """Pull out the synthetic __global_init_task__ if present.

    Mutates raw_spec['stages'] in place (removes the init stage).
    """
    env: Dict[str, str] = {}
    init_cmd: Optional[str] = None
    stages = raw_spec.get("stages", [])
    if stages and stages[0].get("name") == "__global_init_task__":
        init = stages[0]
        env_in = init.get("env")
        if env_in:
            env = {k: str(v) for k, v in env_in.items()}
        cmd = init.get("cmd")
        if cmd and cmd != "NO-COMMAND":
            init_cmd = cmd
        del stages[0]
    return env, init_cmd


def filter_workflow(
    raw_spec: Dict[str, Any],
    targets: List[str],
    target_labels: List[str],
) -> Tuple[Dict[str, Any], List[str]]:
    """Filter the raw spec down to tasks matching target selectors.

    Returns (new_spec, full_target_names). When no filter is requested,
    returns (raw_spec, []). The returned spec is always a fresh top-level
    dict (no aliasing bug like in the prototype), but the per-stage dicts
    are shared.
    """
    stages = raw_spec.get("stages", [])
    if not targets:
        return {**raw_spec, "stages": list(stages)}, []
    if not target_labels and len(targets) == 1 and targets[0] == "*":
        return {**raw_spec, "stages": list(stages)}, []

    name_to_idx = {t["name"]: i for i, t in enumerate(stages)}

    def task_matches(name: str) -> bool:
        for f in targets:
            if f == "*":
                return True
            if re.match(f, name) is not None:
                return True
        return False

    def task_matches_labels(t: Dict[str, Any]) -> bool:
        if not target_labels:
            return True
        for lbl in t.get("labels", []):
            if lbl in target_labels:
                return True
        return False

    # Memoized canBeDone using iterative traversal.
    ok_cache: Dict[str, bool] = {}

    def can_be_done(name: str) -> bool:
        if name in ok_cache:
            return ok_cache[name]
        idx = name_to_idx.get(name)
        if idx is None:
            ok_cache[name] = False
            return False
        # iterative post-order DFS
        order: List[str] = []
        seen: Set[str] = {name}
        stack: List[Tuple[str, int]] = [(name, 0)]
        while stack:
            cur, ci = stack[-1]
            needs = stages[name_to_idx[cur]].get("needs", []) if cur in name_to_idx else []
            if ci < len(needs):
                stack[-1] = (cur, ci + 1)
                child = needs[ci]
                if child not in seen and child not in ok_cache:
                    if child not in name_to_idx:
                        ok_cache[child] = False
                    else:
                        seen.add(child)
                        stack.append((child, 0))
            else:
                stack.pop()
                order.append(cur)
        for cur in order:
            if cur in ok_cache:
                continue
            idx2 = name_to_idx.get(cur)
            if idx2 is None:
                ok_cache[cur] = False
                continue
            ok = all(ok_cache.get(r, False) for r in stages[idx2].get("needs", []))
            ok_cache[cur] = ok
            if not ok:
                log.info("Disabling target %s due to unsatisfied requirements", cur)
        return ok_cache[name]

    full_target_list = [
        t for t in stages
        if task_matches(t["name"]) and task_matches_labels(t) and can_be_done(t["name"])
    ]
    full_target_names = [t["name"] for t in full_target_list]

    # Collect all upstream requirements (iterative, deduped).
    needed: Set[str] = set(full_target_names)
    stack2 = list(full_target_names)
    while stack2:
        cur = stack2.pop()
        idx = name_to_idx.get(cur)
        if idx is None:
            continue
        for r in stages[idx].get("needs", []):
            if r not in needed:
                needed.add(r)
                stack2.append(r)

    new_stages = [t for t in stages if t["name"] in needed]
    new_spec = {**raw_spec, "stages": new_stages}
    return new_spec, full_target_names


def build_workflow(
    raw_spec: Dict[str, Any],
    targets: List[str],
    target_labels: List[str],
) -> Workflow:
    """End-to-end: strip global-init, filter, build DAG."""
    # Operate on a shallow copy at top level so we don't mutate caller's dict.
    spec = {**raw_spec, "stages": list(raw_spec.get("stages", []))}
    # extract_global_init mutates spec['stages']
    env, init_cmd = extract_global_init(spec)
    filtered, target_names = filter_workflow(spec, targets, target_labels)
    wf = Workflow(
        stages=filtered["stages"],
        global_env=env,
        global_init_cmd=init_cmd,
        full_target_names=target_names,
    )
    return wf


def update_resource_estimates(
    workflow: Workflow,
    resource_json_path: str,
    logger=None,
) -> None:
    """Apply learned resource estimates from a JSON file.

    The JSON is produced by o2dpg_sim_metrics.py json-stat and is keyed on
    the "global" task name (i.e. with the _<timeframe> suffix stripped).

    MEM is taken from pss.max (peak proportional set size).
    CPU is taken from cpu.mean (average cores used during the task).

    Note on relative_cpu: the workflow JSON carries a relative_cpu field
    that historically scaled a "max" CPU estimate down to an "expected"
    usage.  When injecting *measured* cpu.mean values that scaling must NOT
    be applied again — the measurement already reflects actual usage.
    relative_cpu remains untouched and continues to be used by the dynamic-
    resources sampler (resources.py) for sibling reassignment, which is
    correct behaviour: the sampler scales a freshly-observed aggregate back
    to an expected per-task assignment.
    """
    _log = logger if logger is not None else log
    _log.info("Applying learned resource estimates from: %s", resource_json_path)

    with open(resource_json_path) as fp:
        resource_dict = json.load(fp)

    # Remove the metadata key so task lookup doesn't match it.
    resource_dict.pop("count", None)

    n_stages = len(workflow.stages)
    n_updated = 0
    missing_base_names: set = set()

    for task in workflow.stages:
        tf = task.get("timeframe", -1)
        name = task["name"]
        global_name = "_".join(name.split("_")[:-1]) if tf >= 1 else name

        if global_name not in resource_dict:
            missing_base_names.add(global_name)
            continue

        new_res = resource_dict[global_name]
        task_updated = False

        walltime = new_res.get("lifetime", {}).get("mean")
        if walltime is not None:
            # Store even when walltime=0 (sub-10ms tasks that GNU time rounds
            # to zero).  The simulator clamps to a 1ms minimum so zero is
            # handled gracefully; the fallback (cpu * factor) is always worse.
            task["resources"]["walltime"] = float(walltime)
            _log.info("  WALLTIME %-40s  %.3f s", name, float(walltime))
            task_updated = True

        new_mem = new_res.get("pss", {}).get("max")
        if new_mem is not None:
            old_mem = task["resources"]["mem"]
            task["resources"]["mem"] = new_mem
            _log.info("  MEM  %-40s  %.1f MB -> %.1f MB", name, float(old_mem), new_mem)
            task_updated = True

        new_cpu = new_res.get("cpu", {}).get("mean")
        if new_cpu is not None:
            old_cpu = task["resources"]["cpu"]
            uses_dynamic_workers = "O2DPG_DYNAMIC_NWORKER_OVERWRITE" in task.get("cmd", "")

            if uses_dynamic_workers:
                # Round cpu.mean to the nearest integer worker count and use
                # that value for BOTH the scheduler's cpu booking and the
                # actual NWORKERS setting.  This keeps them consistent: the
                # task will run with n_workers processes each using ~1 core,
                # so total cpu ≈ n_workers = what we book.
                n_workers = max(1, round(new_cpu))
                task["resources"]["cpu"] = float(n_workers)
                if not isinstance(task.get("env"), dict):
                    task["env"] = {}
                task["env"]["O2DPG_DYNAMIC_NWORKER_OVERWRITE"] = str(n_workers)
                _log.info(
                    "  CPU+NWORKERS %-36s  cpu.mean=%.2f -> %d workers, %.0f cores booked",
                    name, new_cpu, n_workers, float(n_workers),
                )
            else:
                # No dynamic worker override: book cpu.mean directly.
                # Do NOT apply relative_cpu scaling — the measurement already
                # reflects actual usage.
                task["resources"]["cpu"] = new_cpu
                _log.info("  CPU  %-40s  %.3f cores -> %.3f cores",
                          name, float(old_cpu), new_cpu)
            task_updated = True

        if task_updated:
            n_updated += 1

    if missing_base_names:
        _log.info("  No learned data for: %s", ", ".join(sorted(missing_base_names)))
    _log.info(
        "Resource update done: %d/%d task stages updated (%d base name(s) not in learned data).",
        n_updated, n_stages, len(missing_base_names),
    )


def replicate_workflow_for_timeframes(raw_spec: Dict[str, Any], M: int) -> Dict[str, Any]:
    """Return a synthetic M-timeframe workflow derived from *raw_spec*.

    The original workflow may have N timeframes.  This function:
      1. Detects per-TF stages (``timeframe >= 1``) and uses the
         lowest-numbered timeframe as the canonical template.
      2. Instantiates the template for TF=1..M.
      3. Updates global stage dependencies so they reference exactly TF=1..M.

    Works for both M < N (shrink) and M > N (expand).
    The returned dict shares no mutable state with *raw_spec*.
    """
    stages = raw_spec.get("stages", [])
    per_tf = [s for s in stages if s.get("timeframe", -1) >= 1]
    global_stgs = [s for s in stages if s.get("timeframe", -1) < 1]

    if not per_tf:
        return raw_spec  # no per-TF template structure detected

    original_tf_set = {s["timeframe"] for s in per_tf}
    min_tf = min(original_tf_set)
    template_stages = [s for s in per_tf if s.get("timeframe") == min_tf]
    template_names = {s["name"] for s in template_stages}
    all_per_tf_names = {s["name"] for s in per_tf}

    def _base(name: str, tf: int) -> str:
        sfx = f"_{tf}"
        return name[:-len(sfx)] if name.endswith(sfx) else name

    # Replicate per-TF tasks for i = 1 .. M.
    new_per_tf: List[Dict[str, Any]] = []
    for i in range(1, M + 1):
        for tmpl in template_stages:
            s = copy.deepcopy(tmpl)
            base = _base(s["name"], min_tf)
            s["name"] = f"{base}_{i}"
            s["timeframe"] = i
            new_needs: List[str] = []
            for need in tmpl.get("needs", []):
                if need in template_names:
                    new_needs.append(f"{_base(need, min_tf)}_{i}")
                else:
                    new_needs.append(need)
            s["needs"] = new_needs
            new_per_tf.append(s)

    # Update global stages: replace all per-TF deps with the full 1..M set,
    # expanding each unique base name exactly once (deduplicates cross-TF refs).
    new_global: List[Dict[str, Any]] = []
    for gstage in global_stgs:
        s = copy.deepcopy(gstage)
        new_needs_g: List[str] = []
        seen: Set[str] = set()
        expanded_bases: Set[str] = set()
        for need in gstage.get("needs", []):
            if need not in all_per_tf_names:
                if need not in seen:
                    new_needs_g.append(need)
                    seen.add(need)
                continue
            # Identify the base name (strip whichever TF suffix this entry has).
            base = need
            for otf in original_tf_set:
                if need.endswith(f"_{otf}"):
                    base = need[:-len(f"_{otf}")]
                    break
            if base in expanded_bases:
                continue
            expanded_bases.add(base)
            for j in range(1, M + 1):
                n = f"{base}_{j}"
                if n not in seen:
                    new_needs_g.append(n)
                    seen.add(n)
        s["needs"] = new_needs_g
        new_global.append(s)

    return {**raw_spec, "stages": new_per_tf + new_global}
