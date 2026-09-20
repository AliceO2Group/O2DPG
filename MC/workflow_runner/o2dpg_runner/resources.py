"""Resource management: per-task estimates, global budget, semaphores.

Structurally equivalent to the prototype's TaskResources / ResourceManager,
with three changes:
  1. is_within_limits() actually checks MEM against mem_limit (not CPU).
  2. No module-level args dependency; n_backfill is passed in.
  3. Booking/unbooking is explicit about which bucket (default / backfill).

Sibling-sampling for --dynamic-resources still runs inside unbook(), same
ordering as before.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

log = logging.getLogger(__name__)


class Semaphore:
    """A named mutual-exclusion flag shared by a group of tasks.

    Deliberately not threading.Semaphore -- this is a logical gate checked
    by the scheduler, not a concurrency primitive.
    """
    __slots__ = ("locked",)

    def __init__(self):
        self.locked = False

    def lock(self):
        self.locked = True

    def unlock(self):
        self.locked = False


@dataclass
class ResourceBoundaries:
    cpu_limit: float
    mem_limit: float
    dynamic_resources: bool = False
    optimistic_resources: bool = False


class TaskResources:
    """Resource accounting for a single task."""

    def __init__(
        self,
        tid: int,
        name: str,
        cpu: float,
        cpu_relative: Optional[float],
        mem: float,
        boundaries: ResourceBoundaries,
    ):
        self.tid = tid
        self.name = name
        # originals (never mutated)
        self.cpu_assigned_original = cpu
        self.mem_assigned_original = mem
        self.cpu_relative = cpu_relative if cpu_relative else 1.0
        # transient assignments (may be updated by sampling)
        self.cpu_assigned = cpu
        self.mem_assigned = mem
        self.boundaries = boundaries
        # sampled (after a sibling finished)
        self.cpu_sampled: Optional[float] = None
        self.mem_sampled: Optional[float] = None
        # live monitor feed
        self.time_collect: List[float] = []
        self.cpu_collect: List[float] = []
        self.mem_collect: List[float] = []
        # siblings (same "global" task name)
        self.related_tasks: Optional[List["TaskResources"]] = None
        self.semaphore: Optional[Semaphore] = None
        self.nice_value: Optional[int] = None
        self.booked = False

    # ----- helpers -----
    @property
    def is_done(self) -> bool:
        return bool(self.time_collect) and not self.booked

    def is_within_limits(self) -> bool:
        """Check the current assignment against global boundaries."""
        ok_cpu = self.cpu_assigned <= self.boundaries.cpu_limit
        ok_mem = self.mem_assigned <= self.boundaries.mem_limit
        if not ok_cpu:
            log.warning("CPU of %s exceeds limit: %.2f > %.2f",
                        self.name, self.cpu_assigned, self.boundaries.cpu_limit)
        if not ok_mem:
            log.warning("MEM of %s exceeds limit: %.2f > %.2f",
                        self.name, self.mem_assigned, self.boundaries.mem_limit)
        return ok_cpu and ok_mem

    def limit_resources(self, cpu_limit: float = None, mem_limit: float = None) -> None:
        if cpu_limit is None:
            cpu_limit = self.boundaries.cpu_limit
        if mem_limit is None:
            mem_limit = self.boundaries.mem_limit
        self.cpu_assigned = min(self.cpu_assigned, cpu_limit)
        self.mem_assigned = min(self.mem_assigned, mem_limit)

    def add_sample(self, time_passed: float, cpu_fraction: float, mem_mb: float) -> None:
        """Record a monitor sample."""
        self.time_collect.append(time_passed)
        self.cpu_collect.append(cpu_fraction)
        self.mem_collect.append(mem_mb)

    def sample_resources(self) -> None:
        """Compute CPU/MEM sample and propagate to un-started siblings."""
        if not self.is_done:
            return

        if len(self.time_collect) < 3:
            self.cpu_sampled = self.cpu_assigned
            self.mem_sampled = self.mem_assigned
            log.debug("Task %s: not enough samples (<3); using assigned as sampled",
                      self.name)
        else:
            # Weighted mean of CPU over sample intervals, skipping the first
            # (cpu_percent(interval=None) first reading is meaningless).
            deltas = [self.time_collect[i + 1] - self.time_collect[i]
                      for i in range(len(self.time_collect) - 1)]
            tot = sum(deltas) or 1.0
            cpu_integral = sum(
                c * dt for c, dt in zip(self.cpu_collect[1:], deltas) if c >= 0
            )
            self.cpu_sampled = cpu_integral / tot
            self.mem_sampled = max(self.mem_collect)

        if self.related_tasks is None:
            return

        # aggregate over finished siblings
        mem_agg = 0.0
        cpu_list: List[float] = []
        for sib in self.related_tasks:
            if sib.is_done and sib.cpu_sampled is not None and sib.mem_sampled is not None:
                mem_agg = max(mem_agg, sib.mem_sampled)
                cpu_list.append(sib.cpu_sampled)
        if not cpu_list:
            return
        cpu_agg = sum(cpu_list) / len(cpu_list)

        if cpu_agg > self.boundaries.cpu_limit:
            log.warning("Sampled CPU (%.2f) exceeds limit (%.2f)",
                        cpu_agg, self.boundaries.cpu_limit)
        elif cpu_agg <= 0:
            # a zero reading is missing information, not a task that needs no
            # CPU; handing it on would let every sibling be admitted at once
            log.debug("Sampled CPU<=0 for %s; reverting to assigned", self.name)
            cpu_agg = self.cpu_assigned

        if mem_agg > self.boundaries.mem_limit:
            log.warning("Sampled MEM (%.2f) exceeds limit (%.2f)",
                        mem_agg, self.boundaries.mem_limit)
        elif mem_agg <= 0:
            log.debug("Sampled MEM<=0 for %s; reverting to assigned", self.name)
            mem_agg = self.mem_assigned

        for sib in self.related_tasks:
            if sib.is_done or sib.booked:
                continue
            sib.cpu_assigned = cpu_agg * sib.cpu_relative
            sib.mem_assigned = mem_agg
            sib.limit_resources()


class ResourceManager:
    """Central accounting: who is booked, which bucket, what's left."""

    def __init__(
        self,
        cpu_limit: float,
        mem_limit: float,
        procs_parallel_max: int = 100,
        n_backfill_max: int = 1,
        backfill_cpu_factor: float = 1.5,
        backfill_mem_factor: float = 1.5,
        dynamic_resources: bool = False,
        optimistic_resources: bool = False,
    ):
        self.boundaries = ResourceBoundaries(
            cpu_limit, mem_limit, dynamic_resources, optimistic_resources
        )
        self.resources: List[TaskResources] = []
        self._related_by_name: Dict[str, List[TaskResources]] = {}
        self._semaphores: Dict[str, Semaphore] = {}

        # default-priority bucket
        self.cpu_booked = 0.0
        self.mem_booked = 0.0
        self.n_procs = 0

        # backfill (niced) bucket
        self.cpu_booked_backfill = 0.0
        self.mem_booked_backfill = 0.0
        self.n_procs_backfill = 0

        self.procs_parallel_max = procs_parallel_max
        self.n_backfill_max = n_backfill_max
        self.backfill_cpu_factor = backfill_cpu_factor
        self.backfill_mem_factor = backfill_mem_factor

        try:
            self.nice_default = os.nice(0)
        except (AttributeError, OSError):
            self.nice_default = 0
        self.nice_backfill = self.nice_default + 19

    # ----- registration -----
    def add_task(
        self,
        name: str,
        related_name: Optional[str],
        cpu: float,
        cpu_relative: Optional[float],
        mem: float,
        semaphore_string: Optional[str] = None,
    ) -> TaskResources:
        res = TaskResources(
            len(self.resources), name, cpu, cpu_relative, mem, self.boundaries
        )
        if not res.is_within_limits() and not self.boundaries.optimistic_resources:
            raise ResourceLimitExceeded(
                f"Task {name} exceeds resource boundaries "
                f"(cpu={cpu}/{self.boundaries.cpu_limit}, "
                f"mem={mem}/{self.boundaries.mem_limit}). "
                f"Use --optimistic-resources to attempt anyway."
            )
        res.limit_resources()
        self.resources.append(res)

        if semaphore_string:
            if semaphore_string not in self._semaphores:
                self._semaphores[semaphore_string] = Semaphore()
            res.semaphore = self._semaphores[semaphore_string]

        if related_name:
            bucket = self._related_by_name.setdefault(related_name, [])
            bucket.append(res)
            res.related_tasks = bucket

        return res

    # ----- monitor hook -----
    def add_monitored(self, tid: int, t_delta: float, cpu_fraction: float, mem_mb: float) -> None:
        self.resources[tid].add_sample(t_delta, cpu_fraction, mem_mb)

    # ----- booking -----
    def book(self, tid: int, nice_value: int) -> None:
        res = self.resources[tid]
        # Prior check is expected to have set nice_value; if not, force backfill.
        if res.nice_value is None:
            log.warning("Task %d booked without prior ok_to_submit check; forcing backfill",
                        tid)
            nice_value = self.nice_backfill

        res.nice_value = nice_value
        res.booked = True
        if res.semaphore is not None:
            res.semaphore.lock()
        if nice_value != self.nice_default:
            self.n_procs_backfill += 1
            self.cpu_booked_backfill += res.cpu_assigned
            self.mem_booked_backfill += res.mem_assigned
        else:
            self.n_procs += 1
            self.cpu_booked += res.cpu_assigned
            self.mem_booked += res.mem_assigned

    def unbook(self, tid: int) -> None:
        res = self.resources[tid]
        res.booked = False
        if self.boundaries.dynamic_resources:
            res.sample_resources()
        if res.semaphore is not None:
            res.semaphore.unlock()
        if res.nice_value != self.nice_default:
            self.cpu_booked_backfill -= res.cpu_assigned
            self.mem_booked_backfill -= res.mem_assigned
            self.n_procs_backfill -= 1
            if self.n_procs_backfill <= 0:
                self.cpu_booked_backfill = 0.0
                self.mem_booked_backfill = 0.0
        else:
            self.n_procs -= 1
            self.cpu_booked -= res.cpu_assigned
            self.mem_booked -= res.mem_assigned
            if self.n_procs <= 0:
                self.cpu_booked = 0.0
                self.mem_booked = 0.0

    # ----- queries -----
    def total_procs(self) -> int:
        return self.n_procs + self.n_procs_backfill

    def at_proc_cap(self) -> bool:
        return self.total_procs() >= self.procs_parallel_max

    def cpu_free_default(self) -> float:
        return self.boundaries.cpu_limit - self.cpu_booked

    def mem_free_default(self) -> float:
        return self.boundaries.mem_limit - self.mem_booked

    def fits_default(self, res: TaskResources) -> bool:
        return (
            self.cpu_booked + res.cpu_assigned <= self.boundaries.cpu_limit
            and self.mem_booked + res.mem_assigned <= self.boundaries.mem_limit
        )

    def fits_backfill(
        self,
        res: TaskResources,
        cpu_factor: float = None,
        mem_factor: float = None,
    ) -> bool:
        if cpu_factor is None:
            cpu_factor = self.backfill_cpu_factor
        if mem_factor is None:
            mem_factor = self.backfill_mem_factor
        if self.n_procs_backfill >= self.n_backfill_max:
            return False
        # don't backfill with huge tasks (originals: avoid tasks too close to limit)
        if res.cpu_assigned > 0.9 * self.boundaries.cpu_limit:
            return False
        # mem per core sanity: don't launch something whose mem is huge relative to
        # the CPU budget (original heuristic: mem/cpu_limit >= 1900).
        if self.boundaries.cpu_limit > 0 and res.mem_assigned / self.boundaries.cpu_limit >= 1900:
            return False

        ok_cpu = (self.cpu_booked_backfill + res.cpu_assigned
                  <= self.boundaries.cpu_limit)
        ok_cpu = ok_cpu and (
            self.cpu_booked + self.cpu_booked_backfill + res.cpu_assigned
            <= cpu_factor * self.boundaries.cpu_limit
        )
        ok_mem = (
            self.mem_booked + self.mem_booked_backfill + res.mem_assigned
            <= mem_factor * self.boundaries.mem_limit
        )
        return ok_cpu and ok_mem

    def can_be_submitted_at_all(self, res: TaskResources) -> bool:
        """True if a task is not blocked by its semaphore and is not already booked."""
        if res.booked:
            return False
        if res.semaphore is not None and res.semaphore.locked:
            return False
        return True


class ResourceLimitExceeded(Exception):
    """Raised when a task's declared resources exceed the global boundaries
    and --optimistic-resources was not given."""
