"""Best-fit bin-packing scheduler.

Instead of following the ordered list linearly, it picks the candidate
that maximizes a fitness score given the current remaining budget.
Iterates until nothing fits. The backfill pass uses the same idea.

Fitness = critical_path_weight * packing_tightness, where:
  - critical_path_weight is state.critical_path[tid] — remaining walltime
    on the longest path (walltime-weighted when learned data is available,
    cpu-weighted otherwise).  This is the "hybrid CP + packing" heuristic:
    prefer tasks on the longest critical path, but among those that fit
    similarly, pick the one that uses capacity most tightly.
  - packing_tightness = max(c/cpu_free, m/mem_free) — dominant-resource
    utilisation fraction.  A task scores high when it fills at least one
    resource bin well; unlike 1/max(ratio), this is not dominated by a
    resource with extreme slack (e.g. 60 GB mem_limit with tasks using 1 GB).

Default ordering is still critical-path (good baseline); pick_submittable
re-ranks on the fly within the fitting set.
"""

from __future__ import annotations

from typing import Iterator, List, Optional, Tuple

from .base import SchedulerPolicy, SchedulerState
from .critical_path import CriticalPathPolicy
from ..resources import ResourceManager


class BestFitBackfillPolicy(SchedulerPolicy):
    name = "best-fit"

    def __init__(self):
        self._ordering = CriticalPathPolicy()
        self._state: Optional[SchedulerState] = None

    def order(self, candidates: List[int], state: SchedulerState) -> List[int]:
        self._state = state
        return self._ordering.order(candidates, state)

    @staticmethod
    def _fitness(res, state: SchedulerState, cpu_free: float, mem_free: float) -> float:
        """Higher is better; negative if it doesn't fit."""
        c = max(res.cpu_assigned, 0.01)
        m = max(res.mem_assigned, 1.0)
        cpu_ratio = cpu_free / c
        mem_ratio = mem_free / m
        if cpu_ratio < 1 or mem_ratio < 1:
            return -1.0
        # Dominant-resource utilisation: fraction of the most-used resource.
        # max(c/cpu_free, m/mem_free) = max(1/cpu_ratio, 1/mem_ratio).
        # Higher means the task fills at least one resource bin well.
        # This is correct in both constrained and resource-ample (serial) modes:
        # unlike 1/max(ratio), it is not dominated by a resource with extreme slack.
        tightness = max(c / cpu_free, m / mem_free)
        # CP weight: remaining walltime on the longest path from this task.
        # Rewards placing tasks that unblock the most remaining work first.
        # Falls back to descendants_count+1 when no critical_path available.
        cp = state.critical_path[res.tid] if state.critical_path else 0.0
        cp_weight = cp if cp > 0 else (state.descendants_count[res.tid] + 1 if state.descendants_count else 1)
        return cp_weight * tightness

    def pick_submittable(
        self, ordered: List[int], rm: ResourceManager
    ) -> Iterator[Tuple[int, int]]:
        if rm.at_proc_cap():
            return

        state = self._state
        assert state is not None, "order() must be called before pick_submittable()"

        # --- default-nice: iterative best-fit ---
        pool = list(ordered)
        while pool and not rm.at_proc_cap():
            cpu_free = rm.cpu_free_default()
            mem_free = rm.mem_free_default()
            best_tid = -1
            best_score = -1.0
            for tid in pool:
                res = rm.resources[tid]
                if not rm.can_be_submitted_at_all(res):
                    continue
                s = self._fitness(res, state, cpu_free, mem_free)
                if s > best_score:
                    best_score = s
                    best_tid = tid
            if best_tid < 0 or best_score < 0:
                break
            pool.remove(best_tid)
            res = rm.resources[best_tid]
            res.nice_value = rm.nice_default
            yield best_tid, rm.nice_default

        # --- backfill pass ---
        if rm.at_proc_cap():
            return
        for tid in pool:
            res = rm.resources[tid]
            if not rm.can_be_submitted_at_all(res):
                continue
            if rm.fits_backfill(res):
                res.nice_value = rm.nice_backfill
                yield tid, rm.nice_backfill
