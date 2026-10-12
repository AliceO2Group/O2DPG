"""Pluggable scheduler policy interface.

A SchedulerPolicy has two responsibilities:
  1. order(candidates, state) -> ordered list of tids
     (how to prioritize among runnable tasks)
  2. pick_submittable(ordered, resource_manager) -> iterator of (tid, nice)
     (which of the ordered tasks actually fit in the remaining budget,
      at what nice level, subject to policy-specific packing rules)

Resources-aware bookkeeping (what's currently booked, what the limits
are) lives in ResourceManager. Policies only read it; they don't mutate
it. The executor calls rm.book() after picking a task.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..resources import ResourceManager


@dataclass
class SchedulerState:
    """Everything a policy might want to know about the current run.

    Kept lightweight: policies that don't need a field just ignore it.
    """
    # Static data
    timeframe_of: List[int] = field(default_factory=list)   # tid -> timeframe
    descendants_count: List[int] = field(default_factory=list)  # |desc(tid)|
    critical_path: List[float] = field(default_factory=list)   # longest_path_length weighted by walltime (or cpu fallback)
    task_cpu: List[float] = field(default_factory=list)
    task_mem: List[float] = field(default_factory=list)
    task_walltime: List[float] = field(default_factory=list)  # per-task walltime [s]; 0 if unknown
    # Derived weight tuples (static, cached by executor)
    #   timeframe_weight[tid] = (timeframe, -num_descendants)
    timeframe_weight: List[Tuple[int, int]] = field(default_factory=list)


class SchedulerPolicy:
    """Base class. Subclasses override order() and/or pick_submittable()."""

    name = "base"

    def order(self, candidates: List[int], state: SchedulerState) -> List[int]:
        """Return candidates ordered by policy preference (best first)."""
        raise NotImplementedError

    def pick_submittable(
        self,
        ordered: List[int],
        rm: "ResourceManager",
    ) -> Iterator[Tuple[int, int]]:
        """Yield (tid, nice_value) for tasks that fit now.

        Removes nothing; the executor is responsible for calling rm.book()
        and rebuilding candidate lists. pick_submittable is a pure
        read-only view onto rm's current state.
        """
        raise NotImplementedError
