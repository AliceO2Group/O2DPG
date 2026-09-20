"""Resource monitor running in a background thread.

The main scheduler loop used to poll psutil synchronously at 1 Hz, which
cost 10-20% of one core on realistic workflows. Now the monitor is a
separate thread with independent CPU (cheap, 1 Hz) and MEM (expensive,
0.2 Hz) cadences. The scheduler reads the latest snapshot lock-free via
an atomic dict reference.

Backend interface: a callable
  sample(task_pid_list) -> {pid: {"cpu_pct": float, "pss_mb": float,
                                  "uss_mb": float, "swap_mb": float,
                                  "children": [pid, ...]}}
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import psutil
    HAVE_PSUTIL = True
except ImportError:
    HAVE_PSUTIL = False

log = logging.getLogger(__name__)


@dataclass
class TaskSnapshot:
    """Per-task roll-up of the most recent monitor pass."""
    tid: int
    name: str
    t_delta_ms: int = 0
    cpu_pct: float = 0.0   # 0..100 * n_cores  (psutil)
    uss_mb: float = 0.0
    pss_mb: float = 0.0
    swap_mb: float = 0.0
    nice: int = 0
    labels: List[str] = field(default_factory=list)
    disc_mb: float = -1.0  # global disc usage (same value on all tasks, or -1)
    mem_fresh: bool = False  # did this snapshot's mem numbers come from a fresh read?
    # cgroup-based metrics (None when not in a systemd slice / no per-task scope)
    cgroup_cpu_pct: Optional[float] = None   # aggregate CPU % from cgroup cpu.stat
    cgroup_mem_mb: Optional[float] = None    # aggregate memory from cgroup memory.current


def _get_child_procs_fallback(base_pid: int) -> List[int]:
    """Pure-bash fallback when psutil.Process.children raises AccessDenied."""
    script = r'''
    childprocs() {
      local parent=$1
      if [ ! "$2" ]; then child_pid_list=""; fi
      if [ "$parent" ]; then
        child_pid_list="$child_pid_list $parent"
        for childpid in $(pgrep -P ${parent}); do
          childprocs $childpid "nottoplevel"
        done
      fi
      if [ ! "$2" ]; then echo "${child_pid_list}"; fi
    }
    '''
    full = script + f"\nchildprocs {base_pid}\n"
    out = subprocess.check_output(full, shell=True)
    pids: List[int] = []
    for tok in out.decode().split():
        try:
            pids.append(int(tok))
        except ValueError:
            continue
    return pids


class PsutilBackend:
    """psutil-based monitor backend. Caches per-pid Process objects so that
    cpu_percent(interval=None) has a stable 'previous reading' baseline."""

    def __init__(self):
        if not HAVE_PSUTIL:
            raise RuntimeError("psutil not available")
        self._proc_cache: Dict[int, "psutil.Process"] = {}
        # Prime baseline on the manager process so first delta is sensible.
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

    def _get_or_add(self, pid: int) -> Optional["psutil.Process"]:
        p = self._proc_cache.get(pid)
        if p is not None:
            return p
        try:
            p = psutil.Process(pid)
            # Deliberately DO NOT call p.cpu_percent(interval=None) here to prime.
            # psutil's rule: the first call after Process() construction returns
            # a CPU % relative to process creation -- useful as a "since start"
            # figure, not "since last poll". On multi-process tasks that spawn
            # children between monitor ticks, priming right before the read
            # yields 0 because no time has elapsed. Letting the monitor thread's
            # regular cadence handle both calls produces correct deltas from
            # tick 2 onward (tick 1 returns the since-creation value, which is
            # a reasonable initial estimate anyway).
            self._proc_cache[pid] = p
            return p
        except Exception:
            return None

    def forget(self, pid: int) -> None:
        self._proc_cache.pop(pid, None)

    def sweep_dead(self) -> int:
        """Evict cached Process objects whose underlying PID is gone.

        Called once per monitor pass. Keeps the cache size bounded over
        long runs where short-lived DPL/FAIRMQ children come and go.
        """
        dead = 0
        for pid in list(self._proc_cache.keys()):
            try:
                if not self._proc_cache[pid].is_running():
                    del self._proc_cache[pid]
                    dead += 1
            except Exception:
                self._proc_cache.pop(pid, None)
                dead += 1
        return dead

    def sample(
        self,
        root_pid: int,
        want_mem: bool,
    ) -> Tuple[float, float, float, float, int]:
        """Return (cpu_pct_sum, pss_mb, uss_mb, swap_mb, nice_of_root).

        Sums over root and all descendants. If want_mem is False the
        memory figures are returned as 0 (caller should interpret -> use
        last known).
        """
        root = self._get_or_add(root_pid)
        if root is None:
            return 0.0, 0.0, 0.0, 0.0, 0

        # Enumerate the PIDs of the whole process tree, then look each one
        # up in the cache. CRITICAL: psutil.Process.children() returns NEW
        # Process objects on every call, which means their cpu_percent()
        # baseline is reset each tick -> we'd read 0.0 forever. Always go
        # through _get_or_add so baselines persist between ticks.
        try:
            child_pids = [c.pid for c in root.children(recursive=True)]
        except (psutil.NoSuchProcess,):
            return 0.0, 0.0, 0.0, 0.0, 0
        except (psutil.AccessDenied, PermissionError):
            try:
                child_pids = _get_child_procs_fallback(root_pid)
                if root_pid in child_pids:
                    child_pids.remove(root_pid)
            except Exception:
                child_pids = []

        procs = [root]
        for pid in child_pids:
            p = self._get_or_add(pid)
            if p is not None:
                procs.append(p)

        cpu_sum = 0.0
        pss_sum = 0.0
        uss_sum = 0.0
        swap_sum = 0.0
        for p in procs:
            # CPU: cheap
            try:
                cpu_sum += p.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            if want_mem:
                try:
                    mi = p.memory_full_info()
                    pss_sum += getattr(mi, "pss", 0) or 0
                    uss_sum += getattr(mi, "uss", 0) or 0
                    swap_sum += getattr(mi, "swap", 0) or 0
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        # bytes -> MB
        pss_mb = pss_sum / 1024.0 / 1024.0
        uss_mb = uss_sum / 1024.0 / 1024.0
        swap_mb = swap_sum / 1024.0 / 1024.0

        try:
            nice = root.nice()
        except Exception:
            nice = 0

        return cpu_sum, pss_mb, uss_mb, swap_mb, nice


def _read_cgroup_v2_dir(pid: int) -> Optional[str]:
    """Return the cgroup v2 directory for *pid*, or None if not on cgroup v2."""
    try:
        with open(f"/proc/{pid}/cgroup") as fh:
            for line in fh:
                parts = line.strip().split(":", 2)
                # cgroup v2 unified hierarchy: single entry "0::<rel_path>"
                if len(parts) == 3 and parts[0] == "0":
                    rel = parts[2].lstrip("/")
                    candidate = f"/sys/fs/cgroup/{rel}" if rel else "/sys/fs/cgroup"
                    if os.path.isdir(candidate):
                        return candidate
    except OSError:
        pass
    return None


class CgroupV2Monitor:
    """Reads aggregate CPU time and memory for one cgroup v2 directory.

    Works with cgroup v2 (unified hierarchy) only — the format used by
    systemd on modern Linux.  Instantiating this class is always safe; call
    ``available`` to test whether a valid cgroup path was found/given before
    using ``sample()``.

    If *cgroup_dir* is provided the directory is used directly (for per-task
    monitoring of a known scope).  Otherwise the caller's own cgroup is
    detected from ``/proc/self/cgroup`` (for the global runner-level monitor).

    CPU is computed by differentiating the ``usage_usec`` counter in
    ``cpu.stat``.  The first ``sample()`` call primes the counter and returns
    ``None`` for cpu_pct; subsequent calls give the average utilisation
    (as a percentage of one core, same units as psutil's cpu_percent).

    Memory is read from ``memory.current`` (bytes → MB).  It counts all
    memory mapped by processes in the cgroup including file-backed pages;
    shared pages are counted once per cgroup, not per process.  For an
    apples-to-apples comparison with psutil's PSS metric use the
    ``memory.stat`` anon field (not implemented here — ``memory.current``
    is the right proxy for a hard MemoryMax enforcement budget).
    """

    def __init__(self, cgroup_dir: Optional[str] = None) -> None:
        if cgroup_dir is not None:
            self._cgroup_dir: Optional[str] = cgroup_dir if os.path.isdir(cgroup_dir) else None
        else:
            self._cgroup_dir = _read_cgroup_v2_dir(os.getpid())
        self._last_usage_usec: Optional[int] = None
        self._last_ts: Optional[float] = None

    @property
    def available(self) -> bool:
        return self._cgroup_dir is not None

    def sample(self) -> Tuple[Optional[float], Optional[float]]:
        """Return (cpu_pct, mem_mb).  cpu_pct is None on the first call."""
        if not self._cgroup_dir:
            return None, None

        cpu_pct: Optional[float] = None
        mem_mb: Optional[float] = None

        # --- CPU ---
        try:
            with open(os.path.join(self._cgroup_dir, "cpu.stat")) as fh:
                for line in fh:
                    if line.startswith("usage_usec"):
                        usage_usec = int(line.split()[1])
                        now = time.monotonic()
                        if self._last_usage_usec is not None and self._last_ts is not None:
                            dt = now - self._last_ts
                            if dt > 0:
                                d_usec = usage_usec - self._last_usage_usec
                                # d_usec / (dt * 1e6) is CPU fraction relative to 1 core;
                                # multiply by 100 to match psutil's cpu_percent scale.
                                cpu_pct = (d_usec / (dt * 1e6)) * 100.0
                        self._last_usage_usec = usage_usec
                        self._last_ts = now
                        break
        except OSError:
            pass

        # --- Memory ---
        try:
            with open(os.path.join(self._cgroup_dir, "memory.current")) as fh:
                mem_mb = int(fh.read().strip()) / 1024.0 / 1024.0
        except OSError:
            pass

        return cpu_pct, mem_mb


class MonitorThread(threading.Thread):
    """Background thread polling a set of (tid, pid) pairs.

    The scheduler registers tasks via register()/deregister(). On each
    pass the thread computes the latest snapshot and stores it in
    self.snapshots; the scheduler reads atomically.

    CPU and MEM have independent cadences because PSS reads via
    /proc/<pid>/smaps_rollup are ~10x more expensive than cpu_percent.
    """

    def __init__(
        self,
        cpu_interval: float = 1.0,
        mem_interval: float = 5.0,
        backend: Optional[PsutilBackend] = None,
        monitor_disc: bool = False,
        disc_path: str = ".",
        global_cgroup_dir: Optional[str] = None,
    ):
        super().__init__(daemon=True, name="o2dpg-monitor")
        self.cpu_interval = cpu_interval
        self.mem_interval = mem_interval
        self.backend = backend if backend is not None else PsutilBackend()
        self.monitor_disc = monitor_disc
        self.disc_path = disc_path

        self._lock = threading.Lock()
        # registered[tid] = {"pid": int, "name": str, "labels": list,
        #                    "start_time": float}
        self._registered: Dict[int, Dict] = {}
        self._snapshots: Dict[int, TaskSnapshot] = {}
        self._stop_event = threading.Event()
        self._last_mem_ts: float = 0.0
        self._last_disc_mb: float = -1.0
        self._last_disc_ts: float = 0.0
        # Tick counter: incremented once per monitor pass (roughly once per
        # cpu_interval). Read by the executor when writing metric lines so
        # the "iter" field reflects wall-clock ticks like the prototype did.
        self.tick: int = 0

        # Opportunistic cgroup v2 global monitor.  Only enabled when the
        # caller passes an explicit *slice* directory (i.e. the runner was
        # launched under --systemd-run).  Without an explicit directory we
        # skip cgroup monitoring entirely — the runner's own cgroup outside a
        # dedicated slice covers unrelated user-session processes and gives
        # misleading aggregates.
        # Written only from the monitor thread; read from the executor thread —
        # GIL makes bare float/None assignment atomic.
        self._cgroup: Optional[CgroupV2Monitor] = (
            CgroupV2Monitor(cgroup_dir=global_cgroup_dir) if global_cgroup_dir else None
        )
        self.global_cpu_pct: Optional[float] = None  # cgroup-aggregate CPU %
        self.global_mem_mb: Optional[float] = None   # cgroup-aggregate memory MB
        if self._cgroup is not None and self._cgroup.available:
            log.info("CgroupV2Monitor global active at %s", self._cgroup._cgroup_dir)

    # ----- registration -----
    def register(
        self,
        tid: int,
        pid: int,
        name: str,
        labels: List[str],
        start_time: float,
        resolve_cgroup: bool = False,
    ) -> None:
        """Register a task for monitoring.

        If *resolve_cgroup* is True the monitor thread will lazily locate the
        task's cgroup v2 directory by inspecting the first child process of
        *pid* (which is the systemd-run wrapper when per-task scopes are used).
        Once resolved a per-task CgroupV2Monitor is created and its readings
        are stored in the TaskSnapshot alongside the psutil figures.
        """
        with self._lock:
            self._registered[tid] = {
                "pid": pid,
                "name": name,
                "labels": labels,
                "start_time": start_time,
                "resolve_cgroup": resolve_cgroup,
                "cgroup_monitor": None,  # filled lazily by _one_pass
            }

    def deregister(self, tid: int) -> None:
        with self._lock:
            entry = self._registered.pop(tid, None)
            if entry is not None:
                self.backend.forget(entry["pid"])

    # ----- snapshot access -----
    def latest(self) -> Dict[int, TaskSnapshot]:
        """Return a shallow copy of current snapshots."""
        with self._lock:
            return dict(self._snapshots)

    def latest_for(self, tid: int) -> Optional[TaskSnapshot]:
        with self._lock:
            return self._snapshots.get(tid)

    # ----- control -----
    def stop(self) -> None:
        self._stop_event.set()

    # ----- loop -----
    def _disc_usage_mb(self) -> float:
        try:
            out = subprocess.check_output(["du", "-sb", self.disc_path], text=True)
            return int(out.split()[0]) / 1024.0 / 1024.0
        except Exception:
            return -1.0

    def _one_pass(self, now: float) -> None:
        self.tick += 1

        # cgroup global totals (cheap reads, always done every pass)
        if self._cgroup is not None and self._cgroup.available:
            g_cpu, g_mem = self._cgroup.sample()
            if g_cpu is not None:
                self.global_cpu_pct = g_cpu
            if g_mem is not None:
                self.global_mem_mb = g_mem

        want_mem = (now - self._last_mem_ts) >= self.mem_interval
        if want_mem:
            self._last_mem_ts = now

        if self.monitor_disc and (now - self._last_disc_ts) >= self.mem_interval:
            self._last_disc_mb = self._disc_usage_mb()
            self._last_disc_ts = now

        # snapshot registrations under lock, release for the slow work
        with self._lock:
            registered_copy = dict(self._registered)

        new_snaps: Dict[int, TaskSnapshot] = {}
        for tid, info in registered_copy.items():
            pid = info["pid"]
            cpu_pct, pss_mb, uss_mb, swap_mb, nice = self.backend.sample(pid, want_mem)
            # fall back to previous mem reading if not a mem-interval tick
            prev = self._snapshots.get(tid)
            if not want_mem and prev is not None:
                pss_mb = prev.pss_mb
                uss_mb = prev.uss_mb
                swap_mb = prev.swap_mb

            # --- per-task cgroup monitoring ---
            # Lazy resolution: when the task runs inside a systemd scope, its
            # direct child of the systemd-run wrapper PID lands in that scope's
            # cgroup.  We probe once per pass until the child appears.
            if info.get("resolve_cgroup") and info.get("cgroup_monitor") is None:
                try:
                    p_obj = self.backend._get_or_add(pid)
                    if p_obj is not None:
                        children = p_obj.children()
                        if children:
                            cgroup_dir = _read_cgroup_v2_dir(children[0].pid)
                            if cgroup_dir:
                                info["cgroup_monitor"] = CgroupV2Monitor(cgroup_dir=cgroup_dir)
                                log.info("Per-task cgroup resolved: tid=%d %s → %s",
                                         tid, info["name"], cgroup_dir)
                except Exception:
                    pass

            cgroup_cpu: Optional[float] = None
            cgroup_mem: Optional[float] = None
            cm: Optional[CgroupV2Monitor] = info.get("cgroup_monitor")
            if cm is not None and cm.available:
                cgroup_cpu, cgroup_mem = cm.sample()
                # cgroup_cpu is None on the very first sample() call (no prior
                # baseline yet) and whenever the scope's cpu.stat is unreadable
                # (e.g. after --collect removes the finished scope).  In both
                # cases we leave it as None rather than carrying forward a stale
                # value — one tick with None is preferable to a wrong number.
            # -------------------------------------------------------

            t_delta_ms = int((now - info["start_time"]) * 1000)
            new_snaps[tid] = TaskSnapshot(
                tid=tid, name=info["name"],
                t_delta_ms=t_delta_ms, cpu_pct=cpu_pct,
                uss_mb=uss_mb, pss_mb=pss_mb, swap_mb=swap_mb,
                nice=nice, labels=info["labels"],
                disc_mb=self._last_disc_mb,
                mem_fresh=want_mem,
                cgroup_cpu_pct=cgroup_cpu,
                cgroup_mem_mb=cgroup_mem,
            )

        with self._lock:
            self._snapshots = new_snaps

        # housekeeping: evict dead cached Process objects once per pass
        try:
            self.backend.sweep_dead()
        except Exception:
            pass

    def run(self) -> None:
        log.debug("Monitor thread started (cpu=%.2fs, mem=%.2fs)",
                  self.cpu_interval, self.mem_interval)
        while not self._stop_event.is_set():
            now = time.perf_counter()
            try:
                self._one_pass(now)
            except Exception:
                log.exception("Monitor pass failed (continuing)")
            # Sleep at the CPU cadence; MEM is gated by its own interval.
            self._stop_event.wait(self.cpu_interval)
        log.debug("Monitor thread exiting")
