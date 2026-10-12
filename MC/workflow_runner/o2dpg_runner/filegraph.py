"""Pluggable observation of task file IO during a pilot run.

A backend records which task produces and which tasks consume each
intermediate file and writes ``filegraph_<backend>_<pid>.json``, which a
later production run replays with ``--remove-files-early``.  Several
backends can be active at once so they can be compared on one run; see
UTILS/FileIOGraph/README.md.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional


def filegraph_dir() -> str:
    """The UTILS/FileIOGraph directory holding the monitors and analysers."""
    root = os.getenv("O2DPG_ROOT")
    if not root:
        root = os.path.abspath(__file__)
        while root != "/" and not os.path.isdir(
                os.path.join(root, "UTILS", "FileIOGraph")):
            root = os.path.dirname(root)
    return os.path.join(root, "UTILS", "FileIOGraph")


class FileGraphBackend:
    """One way of observing which task reads and writes which file."""

    name = "none"
    analyser = ""
    #: backends that replace the original fanotify sidecar also write its
    #: report under the name the runner has always used
    legacy_report = False

    def __init__(self, workdir: str, runner_pid: int, action_log: str,
                 logger: logging.Logger):
        self.workdir = workdir
        self.runner_pid = runner_pid
        self.action_log = action_log
        self.log = logger

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def wrap(self, argv: List[str], taskname: str, tid: int) -> List[str]:
        """The argv actually used to launch a task."""
        return argv

    # -- result --------------------------------------------------------
    def recorded(self) -> bool:
        return False

    def analyser_args(self) -> List[str]:
        return []

    def analyse(self, out_json: str) -> bool:
        if not self.recorded():
            return False
        argv = [sys.executable, os.path.join(filegraph_dir(), self.analyser),
                "--basedir", self.workdir, "-o", out_json] + self.analyser_args()
        self.log.info("FileIOGraph analysis: %s", " ".join(argv))
        try:
            subprocess.run(argv, check=True)
            return True
        except (subprocess.CalledProcessError, OSError) as e:
            self.log.error("FileIOGraph analysis failed: %s", e)
            return False


class FanotifyBackend(FileGraphBackend):
    """Mount-wide sidecar; needs CAP_SYS_ADMIN on the monitor binary."""

    name = "fanotify"
    analyser = "analyse_FileIO_v2.py"
    legacy_report = True

    def __init__(self, workdir, runner_pid, action_log, logger,
                 exe: Optional[str] = None):
        super().__init__(workdir, runner_pid, action_log, logger)
        # O2DPG_PRODUCE_FILEGRAPH is the original spelling and still names
        # the monitor to run
        self.exe = (exe or os.getenv("O2DPG_PRODUCE_FILEGRAPH")
                    or os.path.join(filegraph_dir(), "monitor_fileaccess_v2.exe"))
        self.logfile = f"pipeline_fileaccess_{self.name}_{runner_pid}.log"
        self._proc: Optional[subprocess.Popen] = None
        self._fh = None

    def start(self) -> None:
        if not os.path.exists(self.exe):
            self.log.error("filegraph fanotify: no such executable %s", self.exe)
            return
        env = dict(os.environ, FILEACCESS_MON_ROOTPATH=self.workdir,
                   MAXMOTHERPID=str(self.runner_pid))
        self._fh = open(self.logfile, "w")
        try:
            self._proc = subprocess.Popen([self.exe], stdout=self._fh,
                                          stderr=subprocess.STDOUT, env=env)
        except OSError as e:
            self.log.error("filegraph fanotify: could not start %s: %s", self.exe, e)
            self._fh.close()
            self._fh = None
            return
        self.log.info("filegraph fanotify: %s pid=%d -> %s",
                      self.exe, self._proc.pid, self.logfile)

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def recorded(self) -> bool:
        return os.path.exists(self.logfile)

    def analyser_args(self) -> List[str]:
        return ["--actionFile", self.action_log, "--monitorFile", self.logfile]


class StraceBackend(FileGraphBackend):
    """Wraps every task in its own strace; attribution is by construction."""

    name = "strace"
    analyser = "analyse_FileIO_strace.py"
    #: must stay in step with what analyse_FileIO_strace.py parses
    SYSCALLS = "openat,openat2,open,creat,rename,renameat,renameat2"

    def __init__(self, workdir, runner_pid, action_log, logger,
                 exe: str = "strace"):
        super().__init__(workdir, runner_pid, action_log, logger)
        self.exe = exe
        self.tracedir = os.path.join(workdir, f"strace_{runner_pid}")
        self._argv: List[str] = []

    def start(self) -> None:
        if not shutil.which(self.exe):
            self.log.error("filegraph strace: %s not found on PATH", self.exe)
            return
        argv = [self.exe, "-f", "-qq", "-y",
                "-e", f"trace={self.SYSCALLS}", "-e", "status=successful"]
        # without --seccomp-bpf every read() costs two ptrace stops
        if self._seccomp_works(argv):
            argv.insert(1, "--seccomp-bpf")
        os.makedirs(self.tracedir, exist_ok=True)
        self._argv = argv
        self.log.info("filegraph strace: %s -> %s", " ".join(argv), self.tracedir)

    def _seccomp_works(self, argv: List[str]) -> bool:
        try:
            r = subprocess.run(argv[:1] + ["--seccomp-bpf"] + argv[1:]
                               + ["-o", os.devnull, "true"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=60)
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def wrap(self, argv, taskname, tid):
        if not self._argv:
            return argv
        trace = os.path.join(self.tracedir, f"trace_{tid}_{taskname}.log")
        return self._argv + ["-o", trace, "--"] + list(argv)

    def recorded(self) -> bool:
        return os.path.isdir(self.tracedir)

    def analyser_args(self) -> List[str]:
        return ["--straceDir", self.tracedir]


BACKENDS = {b.name: b for b in (FanotifyBackend, StraceBackend)}


class FileGraphManager:
    """Drives zero or more backends over the runner's lifecycle."""

    def __init__(self, backends: List[FileGraphBackend], runner_pid: int,
                 logger: logging.Logger):
        self.backends = backends
        self.runner_pid = runner_pid
        self.log = logger

    @classmethod
    def from_config(cls, spec: str, workdir: str, runner_pid: int,
                    action_log: str, logger: logging.Logger) -> "FileGraphManager":
        names = [n.strip() for n in spec.split(",") if n.strip()]
        if not names and os.getenv("O2DPG_PRODUCE_FILEGRAPH"):
            names = ["fanotify"]
        backends = []
        for n in names:
            factory = BACKENDS.get(n)
            if factory is None:
                logger.error("unknown filegraph backend %r (known: %s)",
                             n, ", ".join(sorted(BACKENDS)))
                continue
            backends.append(factory(workdir, runner_pid, action_log, logger))
        return cls(backends, runner_pid, logger)

    def start(self) -> None:
        for b in self.backends:
            b.start()

    def stop(self) -> None:
        for b in self.backends:
            b.stop()

    def wrap(self, argv: List[str], taskname: str, tid: int) -> List[str]:
        for b in self.backends:
            argv = b.wrap(argv, taskname, tid)
        return argv

    def analyse(self) -> Dict[str, str]:
        """Produce one report per backend; returns backend name -> path."""
        produced: Dict[str, str] = {}
        for b in self.backends:
            out = f"filegraph_{b.name}_{self.runner_pid}.json"
            if not b.analyse(out):
                continue
            produced[b.name] = out
            if b.legacy_report:
                legacy = f"pipeline_fileaccess_report_{self.runner_pid}.json"
                try:
                    shutil.copyfile(out, legacy)
                except OSError as e:
                    self.log.warning("could not write %s: %s", legacy, e)
        return produced
