"""Critical-path-first scheduler.

Sorts candidates by state.critical_path[tid] — the longest remaining
path weight to any leaf.  The weight is walltime [s] when --update-resources
has been used to inject learned lifetime data (resources.walltime per task);
it falls back to cpu cores otherwise.  Both give a valid makespan proxy;
the walltime variant is strictly more accurate for multithreaded tasks.

Submit discipline: scan ordered list, submit everything that fits at default
nice, then do a second backfill pass at elevated nice.  No should_break —
there is no reason to stop scanning once we have committed to CP ordering.
"""

from __future__ import annotations

from typing import Iterator, List, Tuple

from .base import SchedulerPolicy, SchedulerState
from ..resources import ResourceManager


class CriticalPathPolicy(SchedulerPolicy):
    name = "critical-path"

    def order(self, candidates: List[int], state: SchedulerState) -> List[int]:
        cp = state.critical_path
        tfw = state.timeframe_weight
        # primary: longest path (largest first); tie-break: timeframe, tid
        return sorted(
            candidates,
            key=lambda t: (-cp[t] if cp else 0, tfw[t][0], t),
        )

    def pick_submittable(
        self, ordered: List[int], rm: ResourceManager
    ) -> Iterator[Tuple[int, int]]:
        if rm.at_proc_cap():
            return
        skipped: List[int] = []
        for tid in ordered:
            if rm.at_proc_cap():
                return
            res = rm.resources[tid]
            if not rm.can_be_submitted_at_all(res):
                continue
            if rm.fits_default(res):
                res.nice_value = rm.nice_default
                yield tid, rm.nice_default
            else:
                skipped.append(tid)

        if rm.at_proc_cap():
            return
        for tid in skipped:
            res = rm.resources[tid]
            if not rm.can_be_submitted_at_all(res):
                continue
            if rm.fits_backfill(res):
                res.nice_value = rm.nice_backfill
                yield tid, rm.nice_backfill
