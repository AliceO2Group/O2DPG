"""Timeframe-first scheduler: exact behavior of the prototype.

Order:
  (timeframe, -num_descendants)   # small TF first, then most-connected tasks

Submit:
  - First pass: default nice. Scan in order; on first non-fitting task, BREAK
    (this is the legacy behavior; it can block light tasks behind a heavy one).
  - Second pass: backfill nice. Scan remaining in order; no break on miss.

This is the default policy so a bare-minimum invocation reproduces the
prototype's scheduling decisions.
"""

from __future__ import annotations

import logging
from typing import Iterator, List, Tuple

from .base import SchedulerPolicy, SchedulerState
from ..resources import ResourceManager

log = logging.getLogger(__name__)


class TimeframeFirstPolicy(SchedulerPolicy):
    name = "timeframe"

    def __init__(self, drop_should_break: bool = False):
        # When True, the default pass does not break on a non-fitting task
        # but keeps scanning, so a light task can slip past a heavy one.
        self.drop_should_break = drop_should_break

    def order(self, candidates: List[int], state: SchedulerState) -> List[int]:
        # sort prefers small timeframe, then more descendants
        return sorted(
            candidates,
            key=lambda t: (state.timeframe_weight[t][0], -state.timeframe_weight[t][1]),
        )

    def pick_submittable(
        self, ordered: List[int], rm: ResourceManager
    ) -> Iterator[Tuple[int, int]]:
        if rm.at_proc_cap():
            return

        # --- default-nice pass ---
        skipped_for_backfill: List[int] = []
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
                if self.drop_should_break:
                    skipped_for_backfill.append(tid)
                    continue
                # legacy behavior: the first non-fit breaks the default pass
                skipped_for_backfill.extend(
                    ordered[ordered.index(tid):]
                )
                break

        # --- backfill pass ---
        if rm.at_proc_cap():
            return
        seen = set()
        for tid in skipped_for_backfill:
            if tid in seen:
                continue
            seen.add(tid)
            res = rm.resources[tid]
            if not rm.can_be_submitted_at_all(res):
                continue
            if rm.fits_backfill(res):
                res.nice_value = rm.nice_backfill
                yield tid, rm.nice_backfill
