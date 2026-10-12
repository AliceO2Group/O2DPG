"""Main control loop.

Responsibilities:
 - boot sequence (global init, ROOT speedup, FAIRMQ socket setup)
 - candidate management
 - submit / wait / monitor-feedback interplay
 - retry, failure handling, rerun-from
 - end-of-task hooks (file removal, production archival)

Split from the prototype's monolithic WorkflowExecutor and freed from
module-level args.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import psutil

from .config import RunnerConfig
from .workflow import Workflow, update_resource_estimates
from .graph import descendants, longest_path_length, kahn_topological_order
from .resources import ResourceManager, ResourceLimitExceeded
from .monitoring import MonitorThread, PsutilBackend, _read_cgroup_v2_dir
from .filegraph import FileGraphManager
from .scheduler import get_policy
from .scheduler.base import SchedulerState
from .scheduler.timeframe import TimeframeFirstPolicy
from .cache import TaskCache, compute_fingerprint, remove_done_flag
from .alienv import get_alienv_software_environment
from .cleanup import EarlyFileRemover, archive_task_logs

log = logging.getLogger(__name__)

_UNIT_NAME_RE = re.compile(r"[^a-zA-Z0-9_\-.]")


def _unit_name(task_name: str, tid: int) -> str:
    """Build a valid systemd unit name for a per-task scope."""
    safe = _UNIT_NAME_RE.sub("-", task_name)
    return f"task-{safe}-{tid}.scope"


def _start_stderr_drainer(pipe, logger: logging.Logger, tag: str) -> threading.Thread:
    """Drain *pipe* line-by-line in a daemon thread, forwarding to *logger*.

    Used to capture systemd-run's own informational messages (e.g. "Running
    as unit: ...") and route them to the action log instead of the terminal.
    The thread exits naturally when the pipe reaches EOF (process finished).
    """
    def _run() -> None:
        try:
            for raw in pipe:
                line = raw.rstrip() if isinstance(raw, str) else raw.rstrip().decode(errors="replace")
                if line:
                    logger.info("[systemd] %s: %s", tag, line)
        except Exception:
            pass
    t = threading.Thread(target=_run, daemon=True, name=f"stderr-{tag}")
    t.start()
    return t


@dataclass
class _TaskRuntime:
    """Everything we learn about a task at runtime and need to feed back."""
    logfile: str
    fingerprint: Dict[str, str] = field(default_factory=dict)
    start_time: float = 0.0
    pid: int = 0


class WorkflowExecutor:
    """Construct from a config + workflow; call execute()."""

    def __init__(
        self,
        config: RunnerConfig,
        workflow: Workflow,
        action_logger: logging.Logger,
        metric_logger: logging.Logger,
        filegraph=None,
    ):
        self.cfg = config
        self.filegraph = filegraph or FileGraphManager([], os.getpid(), action_logger)
        self.wf = workflow
        self.actionlog = action_logger
        self.metriclog = metric_logger

        # apply update-resources (before building resource manager)
        if config.update_resources:
            update_resource_estimates(
                workflow, config.update_resources,
                logger=action_logger,
            )

        # resource manager
        self.rm = ResourceManager(
            cpu_limit=config.cpu_limit,
            mem_limit=config.mem_limit,
            procs_parallel_max=config.maxjobs,
            n_backfill_max=config.n_backfill,
            dynamic_resources=config.dynamic_resources,
            optimistic_resources=config.optimistic_resources,
        )
        for task in workflow.stages:
            try:
                rel = float(task["resources"].get("relative_cpu") or 1)
            except (TypeError, ValueError):
                rel = 1.0
            try:
                self.rm.add_task(
                    name=task["name"],
                    related_name=self._global_name(task["name"]),
                    cpu=float(task["resources"]["cpu"]),
                    cpu_relative=rel,
                    mem=float(task["resources"]["mem"]),
                    semaphore_string=task.get("semaphore"),
                )
            except ResourceLimitExceeded as e:
                print(e, file=sys.stderr)
                print("Pass --optimistic-resources to the runner to attempt the run anyway.",
                      file=sys.stderr)
                raise

        # scheduler
        if config.scheduler_policy == "timeframe":
            self.policy = TimeframeFirstPolicy(drop_should_break=config.drop_should_break)
        else:
            self.policy = get_policy(config.scheduler_policy)

        # scheduler state: precompute weights once
        self.state = self._build_scheduler_state()

        # task cache (covers _done + optional _done.json)
        self.cache = TaskCache(policy=config.cache_policy)
        # precompute per-task fingerprint so we don't recompute on each check
        self._fingerprint_by_tid: Dict[int, Dict[str, str]] = {}
        for tid, task in enumerate(workflow.stages):
            alienv = task.get("alternative_alienv_package") or ""
            self._fingerprint_by_tid[tid] = compute_fingerprint(task, alienv)

        # alternative alienv envs
        self.alternative_envs: Dict[int, Dict[str, str]] = {}
        self._init_alternative_envs()

        # Compute the global cgroup directory for the aggregate monitor.
        # Cgroup monitoring is only meaningful when the runner was launched
        # under --systemd-run: the runner's own scope is a leaf node
        # (e.g. o2dpg.slice/o2dpg-runner-<pid>.scope/) and task scopes are
        # siblings.  The *parent* slice directory's cpu.stat / memory.current
        # then cover the runner + all task scopes.  Without --systemd-run the
        # runner shares a generic user-session cgroup with unrelated
        # processes, so cgroup readings would be misleading; fall back to
        # plain psutil monitoring instead.
        _global_cgroup: Optional[str] = None
        if config.in_systemd_slice:
            _runner_cgroup = _read_cgroup_v2_dir(os.getpid())
            if _runner_cgroup:
                _global_cgroup = os.path.dirname(_runner_cgroup)
                if not os.path.isdir(_global_cgroup):
                    _global_cgroup = _runner_cgroup  # safety fallback

        # monitor
        self.monitor = MonitorThread(
            cpu_interval=config.monitor_interval_cpu,
            mem_interval=config.monitor_interval_mem,
            backend=PsutilBackend(),
            monitor_disc=bool(os.getenv("MONITOR_DISC_USAGE")),
            disc_path=os.getcwd(),
            global_cgroup_dir=_global_cgroup,
        )

        # process tracking
        self.proc_status: Dict[int, str] = {tid: "ToDo" for tid in range(workflow.n_tasks())}
        self.task_runtime: Dict[int, _TaskRuntime] = {}
        self.process_list: List[Tuple[int, psutil.Popen]] = []
        self.tids_marked_retry: List[int] = []
        self.retry_counter: List[int] = [0] * workflow.n_tasks()
        self.task_retries: List[int] = [
            int(t.get("retry_count", 0)) for t in workflow.stages
        ]

        # early file removal
        self.file_remover: Optional[EarlyFileRemover] = None
        if config.remove_files_early:
            try:
                self.file_remover = EarlyFileRemover(
                    config.remove_files_early,
                    workflow.timeframes,
                    workflow.full_target_names,
                    logger=action_logger,
                )
            except Exception as e:
                log.warning("Could not set up early file removal: %s", e)

        self.start_time: float = 0.0
        self.scheduling_iteration = 0
        self._last_metric_tick: int = -1  # prevents duplicate metric rows per tick

        # signals
        signal.signal(signal.SIGINT, self._sighandler)
        signal.signal(signal.SIGTERM, self._sighandler)
        signal.siginterrupt(signal.SIGINT, False)
        signal.siginterrupt(signal.SIGTERM, False)

    # ----- small helpers -----
    @staticmethod
    def _global_name(name: str) -> str:
        """Strip _<digits> suffix to find sibling group for resource sampling."""
        toks = name.split("_")
        if toks and toks[-1].isdigit() and len(toks) > 1:
            return "_".join(toks[:-1])
        return name

    def _build_scheduler_state(self) -> SchedulerState:
        n = self.wf.n_tasks()
        # descendants via memoized iterative DFS (no recursion limit concerns)
        desc_cache: Dict[int, Set[int]] = {}
        desc_counts = [0] * n
        for tid in range(n):
            desc_counts[tid] = len(descendants(self.wf.forward_adj, tid, desc_cache))

        timeframe_of = [t.get("timeframe", -1) for t in self.wf.stages]
        tf_weight = [(timeframe_of[t], desc_counts[t]) for t in range(n)]

        cpu = [float(t.get("resources", {}).get("cpu", 1.0)) for t in self.wf.stages]
        mem = [float(t.get("resources", {}).get("mem", 0.0)) for t in self.wf.stages]

        # Per-task walltime [s] from learned resources (resources.walltime set
        # by update_resource_estimates when --update-resources is given).
        # Fall back to cpu as a proxy so behaviour is unchanged without
        # learned data.
        walltime = [
            float(t.get("resources", {}).get("walltime") or cpu[i])
            for i, t in enumerate(self.wf.stages)
        ]
        has_walltime = any(
            t.get("resources", {}).get("walltime") for t in self.wf.stages
        )

        # Critical path: longest remaining *wall time* to any leaf.
        # Using walltime as the node weight gives a true makespan estimate;
        # using cpu (the fallback) preserves the original heuristic.
        cp_weight = walltime if has_walltime else cpu
        topo = kahn_topological_order(n, self.wf.forward_adj, self.wf.indegree)
        cp = longest_path_length(self.wf.forward_adj, topo, cp_weight)

        if has_walltime:
            self.actionlog.info("Critical path weighted by learned walltime [s]")

        # self-log weights (matches prototype's informational logging)
        for tid in range(n):
            self.actionlog.info("Score for %s is %s", self.wf.id_to_name[tid], tf_weight[tid])

        return SchedulerState(
            timeframe_of=timeframe_of,
            descendants_count=desc_counts,
            critical_path=cp,
            task_cpu=cpu,
            task_mem=mem,
            task_walltime=walltime,
            timeframe_weight=tf_weight,
        )

    def _init_alternative_envs(self) -> None:
        cache: Dict[str, Dict[str, str]] = {}
        for tid, task in enumerate(self.wf.stages):
            pkg = task.get("alternative_alienv_package")
            if not pkg:
                continue
            if pkg not in cache:
                cache[pkg] = get_alienv_software_environment(pkg)
            self.alternative_envs[tid] = cache[pkg]

    # ----- task-level helpers -----
    def logfile(self, tid: int) -> str:
        task = self.wf.stages[tid]
        return os.path.join(task.get("cwd", "."), f"{task['name']}.log")

    def apply_global_env(self, env: Dict[str, str]) -> None:
        for k, v in self.wf.global_env.items():
            env.setdefault(k, str(v))

    # ----- signal handling -----
    def _sighandler(self, signum, frame):
        self.actionlog.info("Signal %s caught; terminating children", signum)
        try:
            self.monitor.stop()
        except Exception:
            pass
        try:
            procs = psutil.Process().children(recursive=True)
        except psutil.NoSuchProcess:
            procs = []
        except (psutil.AccessDenied, PermissionError):
            procs = []

        for p in procs:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        _, alive = psutil.wait_procs(procs, timeout=3)
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        sys.exit(1)

    # ----- task submission -----
    def submit(self, tid: int, nice: int) -> Optional[psutil.Popen]:
        task = self.wf.stages[tid]
        self.actionlog.debug("Submitting %s with nice=%d", task["name"], nice)
        cmd = task["cmd"]
        workdir = task.get("cwd", ".")
        if workdir:
            if os.path.exists(workdir) and not os.path.isdir(workdir):
                self.actionlog.error("cwd %s exists and is not a directory", workdir)
                return None
            if not os.path.isdir(workdir):
                os.makedirs(workdir, exist_ok=True)

        self.proc_status[tid] = "Running"

        if self.cfg.dry_run:
            dry = f"echo ' {self.scheduling_iteration} : would do {task['name']}'"
            # psutil.Popen so that the dry-run path also answers .nice()
            return psutil.Popen(["/bin/bash", "-c", dry], cwd=workdir)

        env = os.environ.copy()
        alt = self.alternative_envs.get(tid)
        if alt:
            self.actionlog.info("Applying alternative environment to %s", task["name"])
            if alt.get("TERM") is not None:
                env = dict(alt)
            else:
                env.update(alt)
        if task.get("env"):
            env.update({k: str(v) for k, v in task["env"].items()})
        self.apply_global_env(env)

        if os.environ.get("PIPELINE_RUNNER_DUMP_TASKENVS") is not None:
            try:
                with open(f"taskenv_{tid}.log", "w") as f:
                    json.dump(env, f, indent=2)
            except OSError as e:
                log.warning("could not dump taskenv: %s", e)

        # When the runner is inside a systemd slice, wrap each task in its own
        # child scope so per-task cgroup metrics are available alongside psutil.
        slice_name = self.cfg.systemd_slice_name
        use_scope = self.cfg.in_systemd_slice and bool(slice_name)
        if use_scope:
            systemd_slice = (
                slice_name if slice_name.endswith(".slice") else f"{slice_name}.slice"
            )
            unit = _unit_name(task["name"], tid)
            prefix = [
                "systemd-run", "--user", "--scope", "--collect",
                "--expand-environment=no",  # suppress the $VAR warning; bash handles expansion
                f"--unit={unit}", f"--slice={systemd_slice}", "--",
            ]
        else:
            prefix = []

        # a tracer has to sit inside any systemd scope, or it would only ever
        # see systemd-run itself
        inner_argv = self.filegraph.wrap(["/bin/bash", "-c", cmd], task["name"], tid)
        launch_argv = prefix + inner_argv

        if use_scope:
            p = psutil.Popen(launch_argv, cwd=workdir, env=env, stderr=subprocess.PIPE)
            _start_stderr_drainer(p.stderr, self.actionlog, task["name"])
        else:
            p = psutil.Popen(launch_argv, cwd=workdir, env=env)
        try:
            p.nice(nice)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self.actionlog.error("Could not renice %d to %d", p.pid, nice)

        rt = _TaskRuntime(
            logfile=self.logfile(tid),
            fingerprint=self._fingerprint_by_tid[tid],
            start_time=time.perf_counter(),
            pid=p.pid,
        )
        self.task_runtime[tid] = rt
        self.monitor.register(
            tid, p.pid, task["name"], task.get("labels", []) or [], rt.start_time,
            resolve_cgroup=use_scope,
        )
        return p

    # ----- skip logic -----
    def ok_to_skip(self, tid: int) -> bool:
        return self.cache.is_done(self.logfile(tid), self._fingerprint_by_tid[tid])

    # ----- candidate scheduling pass -----
    def try_submit_from_candidates(
        self,
        candidates: List[int],
        finished_out: List[int],
    ) -> None:
        self.scheduling_iteration += 1

        # skip already-done tasks first (in place)
        remaining = []
        for tid in candidates:
            if self.ok_to_skip(tid):
                finished_out.append(tid)
                self.actionlog.info("Skipping %s", self.wf.id_to_name[tid])
                if self.file_remover is not None:
                    self.file_remover.on_task_done(self.wf.id_to_name[tid])
            else:
                remaining.append(tid)
        # mutate the list the caller passed in
        candidates[:] = remaining

        ordered = self.policy.order(candidates, self.state)
        for tid, nice in self.policy.pick_submittable(ordered, self.rm):
            self.actionlog.debug("Submitting tid=%d %s (nice=%d)",
                                 tid, self.wf.id_to_name[tid], nice)
            p = self.submit(tid, nice)
            if p is None:
                continue
            # pin the nice value the OS actually granted
            try:
                actual_nice = p.nice()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                actual_nice = nice
            self.rm.book(tid, actual_nice)
            self.process_list.append((tid, p))
            if tid in candidates:
                candidates.remove(tid)

    # ----- wait / complete / retry -----
    def wait_for_any(
        self,
        finished_out: List[int],
        failing_out: List[int],
    ) -> bool:
        """Return True if we should keep waiting (no completion this pass).

        Polls each process via poll(); pulls latest monitor snapshot and
        feeds it into the ResourceManager for the dynamic-resources path.
        """
        if not self.process_list:
            return False

        # Take each monitor tick exactly once. This loop polls faster than the
        # monitor fires, and a snapshot recorded twice both inflates the sample
        # lists and defeats the "too few samples" guard in sample_resources().
        snapshots = self.monitor.latest()
        tick = self.monitor.tick

        if tick != self._last_metric_tick:
            self._last_metric_tick = tick
            for tid, snap in snapshots.items():
                self.rm.add_monitored(tid, snap.t_delta_ms,
                                      snap.cpu_pct / 100.0, snap.pss_mb)
                self.metriclog.info({
                    "iter": tick, "name": snap.name,
                    "cpu": snap.cpu_pct, "uss": snap.uss_mb, "pss": snap.pss_mb,
                    "nice": snap.nice, "swap": snap.swap_mb,
                    "label": snap.labels, "disc": snap.disc_mb,
                    # cgroup-based readings for comparison with psutil (None when
                    # no per-task scope is active)
                    "cgroup_cpu": snap.cgroup_cpu_pct, "cgroup_mem": snap.cgroup_mem_mb,
                })

            # cgroup-aggregate slice totals
            g_cpu = self.monitor.global_cpu_pct
            g_mem = self.monitor.global_mem_mb
            if g_cpu is not None or g_mem is not None:
                self.metriclog.info({
                    "iter": tick, "name": "__cgroup_global__",
                    "cpu": g_cpu, "uss": None, "pss": g_mem,
                    "nice": 0, "swap": None, "label": [], "disc": -1,
                })

        # check for completions
        newly_done: List[Tuple[int, psutil.Popen, int]] = []
        for tid, p in list(self.process_list):
            rc = 0 if self.cfg.dry_run else p.poll()
            if rc is None:
                continue
            newly_done.append((tid, p, rc))

        failure_detected = False
        for tid, p, rc in newly_done:
            name = self.wf.id_to_name[tid]
            self.actionlog.info("Task pid=%d tid=%d %s finished rc=%d",
                                p.pid, tid, name, rc)
            self.rm.unbook(tid)
            self.proc_status[tid] = "Done"
            self.monitor.deregister(tid)
            self.process_list.remove((tid, p))

            if rc == 0:
                finished_out.append(tid)
                # record fingerprint sidecar (best effort)
                rt = self.task_runtime.get(tid)
                if rt is not None:
                    self.cache.record(rt.logfile, rt.fingerprint)
                if self.file_remover is not None:
                    self.file_remover.on_task_done(name)
                if self.cfg.production_mode:
                    archive_task_logs(self.logfile(tid), logger=self.actionlog)
            else:
                print(f"{name} failed ... checking retry")
                max_retries = max(self.cfg.retry_on_failure, self.task_retries[tid])
                if self._is_worth_retrying(tid) and self.retry_counter[tid] < max_retries:
                    self.actionlog.info("Task %s marked for retry", name)
                    self.tids_marked_retry.append(tid)
                    self.retry_counter[tid] += 1
                else:
                    failure_detected = True
                    failing_out.append(tid)

        if failure_detected and not self.cfg.keep_going:
            self.actionlog.info("Stopping due to failure in tids %s", failing_out)
            if self.cfg.stdout_on_failure:
                self._cat_logfiles(failing_out)
            self.stop_and_exit()

        return not finished_out

    def _is_worth_retrying(self, tid: int) -> bool:
        """Hook for future log-inspection; currently always True (match prototype)."""
        return True

    def _cat_logfiles(self, tids: List[int]) -> None:
        for tid in tids:
            logf = self.logfile(tid)
            if os.path.exists(logf):
                print(f" ----> START OF LOGFILE {logf} -----")
                try:
                    with open(logf) as f:
                        sys.stdout.write(f.read())
                except OSError:
                    pass
                print(f" <---- END OF LOGFILE {logf} -----")

    def stop_and_exit(self) -> None:
        for _, p in self.process_list:
            try:
                p.kill()
            except Exception:
                pass
        self.monitor.stop()
        sys.exit(1)

    # ----- boot helpers -----
    def _speedup_root_init(self) -> None:
        if platform.system() != "Linux":
            return
        if os.environ.get("ROOT_LDSYSPATH") and os.environ.get("ROOT_CPPSYSINCL"):
            return
        if self.cfg.no_rootinit_speedup:
            return
        try:
            cmd = ('LD_DEBUG=libs LD_PRELOAD=DOESNOTEXIST ls /tmp/DOESNOTEXIST 2>&1 | '
                   'grep -m 1 "system search path" | sed \'s/.*=//g\' | '
                   'awk \'//{print $1}\'')
            libpath = subprocess.check_output(cmd, shell=True).decode().strip()
            if libpath:
                os.environ["ROOT_LDSYSPATH"] = libpath
                os.environ["CLING_LDSYSPATH"] = libpath
            cmd2 = ("LC_ALL=C c++ -xc++ -E -v /dev/null 2>&1 | "
                    "sed -n '/^#include/,${/^ \\/.*++/{p}}'")
            incpath = subprocess.check_output(cmd2, shell=True).decode()
            joined = ":".join(line.lstrip() for line in incpath.splitlines())
            if joined:
                os.environ["ROOT_CPPSYSINCL"] = joined
                os.environ["CLING_CPPSYSINCL"] = joined
        except Exception as e:
            log.warning("ROOT init speedup failed: %s", e)

    def _execute_global_init_cmd(self) -> bool:
        cmd = self.wf.global_init_cmd
        if not cmd:
            return True
        self.actionlog.info("Executing global init cmd: %s", cmd)
        p = subprocess.Popen(["/bin/bash", "-c", cmd],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        if p.returncode == 0:
            self.actionlog.info(stdout.decode())
            return True
        self.actionlog.error("global init failed: %s", stderr.decode())
        return False

    def _handle_rerun_from(self) -> None:
        if not self.cfg.rerun_from:
            return
        import re
        matched = False
        for task in self.wf.stages:
            if re.match(self.cfg.rerun_from, task["name"]):
                matched = True
                tid = self.wf.tid(task["name"])
                # remove done flags for tid and all its descendants (iterative)
                for d in descendants(self.wf.forward_adj, tid) | {tid}:
                    name = self.wf.id_to_name[d]
                    self.actionlog.info("Marking %s for rerun", name)
                    if not self.cfg.dry_run:
                        remove_done_flag(self.logfile(d))
                    else:
                        print(f"Would mark {name} as to be done again")
        if not matched:
            print(f"No task matching {self.cfg.rerun_from} found; refusing to proceed")
            sys.exit(1)

    # ----- bash-script emission -----
    def produce_script(self, filename: str) -> None:
        topo = kahn_topological_order(self.wf.n_tasks(),
                                      self.wf.forward_adj,
                                      self.wf.indegree)
        lines = [
            "#!/usr/bin/env bash\n",
            "#THIS FILE IS AUTOGENERATED\n",
            "export JOBUTILS_SKIPDONE=ON\n",
            "#-- GLOBAL INIT SECTION FROM WORKFLOW --\n",
        ]
        for k, v in self.wf.global_env.items():
            lines.append(f"export {k}={v}\n")
        lines.append("#-- TASKS FROM WORKFLOW --\n")
        for tid in topo:
            t = self.wf.stages[tid]
            workdir = t.get("cwd", ".")
            env_pairs = t.get("env") or {}
            env_prefix = " ".join(f"{k}={v}" for k, v in env_pairs.items())
            # Subshell so inner `cd` doesn't leak, and local env doesn't pollute.
            inner = t["cmd"]
            if env_prefix:
                inner = f"{env_prefix} {inner}"
            lines.append(f"( [ -d {workdir} ] || mkdir -p {workdir}; cd {workdir} && {inner} )\n")
        with open(filename, "w") as f:
            f.writelines(lines)

    # ----- main loop -----
    def execute(self) -> bool:
        self.start_time = time.perf_counter()
        psutil.cpu_percent(interval=None)
        os.environ["JOBUTILS_SKIPDONE"] = "ON"
        self._speedup_root_init()

        if not os.path.isdir("./.tmp"):
            os.mkdir("./.tmp")
        if os.environ.get("FAIRMQ_IPC_PREFIX") is None:
            sp = os.path.join(os.getcwd(), ".tmp")
            self.actionlog.info("Setting FAIRMQ_IPC_PREFIX=%s", sp)
            os.environ["FAIRMQ_IPC_PREFIX"] = sp

        if self.cfg.list_tasks:
            print("List of tasks in this workflow:")
            for i, t in enumerate(self.wf.stages):
                label_part = t.get("labels", [])
                print(f"{t['name']}  ({label_part}) ToDo: {not self.ok_to_skip(i)}")
            return False

        if self.cfg.produce_script is not None:
            self.produce_script(self.cfg.produce_script)
            return False

        if not self._execute_global_init_cmd():
            sys.exit(1)

        self._handle_rerun_from()

        # start monitor
        self.monitor.start()

        # initial candidates: tasks with no predecessors
        candidates = [i for i, d in enumerate(self.wf.indegree) if d == 0]
        finishedtasks_set: Set[int] = set()
        error_encountered = False

        try:
            while True:
                finished: List[int] = []
                self.actionlog.debug("candidates: %s",
                                     [(c, self.wf.id_to_name[c]) for c in candidates])
                self.try_submit_from_candidates(candidates, finished)

                if candidates and not self.process_list:
                    self._noprogress_error()
                    error_encountered = True
                    break

                # wait loop
                finished_running: List[int] = []
                failing: List[int] = []
                poll_delay = 0.1  # adaptive; grows up to 1s
                while self.wait_for_any(finished_running, failing):
                    if not self.cfg.dry_run:
                        time.sleep(poll_delay)
                        poll_delay = min(1.0, poll_delay * 1.5)
                    else:
                        time.sleep(0.001)

                finished.extend(finished_running)
                finishedtasks_set.update(finished)

                # take failed tasks out of the "finished" accounting
                if failing:
                    error_encountered = True
                    fs = set(failing)
                    finished = [x for x in finished if x not in fs]
                    finishedtasks_set.difference_update(fs)

                # retries go back onto the candidate list
                if self.tids_marked_retry:
                    rs = set(self.tids_marked_retry)
                    finished = [x for x in finished if x not in rs]
                    finishedtasks_set.difference_update(rs)
                    for t in self.tids_marked_retry:
                        if t not in candidates:
                            candidates.append(t)
                    self.tids_marked_retry.clear()

                # new candidates: successors whose all needs are done
                for tid in finished:
                    for succ in self.wf.forward_adj[tid]:
                        if succ in candidates:
                            continue
                        if self.proc_status[succ] != "ToDo":
                            continue
                        preds = self.wf.reverse_adj[succ]
                        if all(p in finishedtasks_set for p in preds):
                            candidates.append(succ)

                self.actionlog.debug("new candidates %s", candidates)

                if not candidates and not self.process_list:
                    break
        except Exception:
            traceback.print_exc()
            self._sighandler(0, None)

        self.monitor.stop()
        self.monitor.join(timeout=2)
        end = time.perf_counter()
        msg = "with failures" if error_encountered else "success"
        print(f"\n**** Pipeline done {msg} (global_runtime : {end - self.start_time:.3f}s) *****\n")
        self.actionlog.debug("global_runtime : %.3fs", end - self.start_time)
        return error_encountered

    # ----- error message -----
    def _noprogress_error(self) -> None:
        msg = (
            "Scheduler runtime error: cannot make progress although candidates exist.\n\n"
            "This typically means a task's estimated resources exceed the configured\n"
            "--cpu-limit or --mem-limit. On a 16 GB node, try --mem-limit 20000 (MB);\n"
            "the ACTUAL use might be lower than the estimate. Alternatively convert\n"
            "the workflow to a linear shell script via --produce-script <file>.sh and\n"
            "run that directly.\n"
        )
        print(msg, file=sys.stderr)
