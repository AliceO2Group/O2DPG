#!/usr/bin/env python3
"""Turn per-task strace logs into the file-task dependency report.

The runner wraps each task in its own strace, so the trace file name says
which task made the call and nothing has to be attributed after the fact.
Traces are taken with -y, so the path on the *return* value is the one the
kernel resolved -- which is what makes relative paths, chdir and a
non-AT_FDCWD directory descriptor all come out right.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Dict, List, Set, Tuple

from filegraph_report import (
    add_common_arguments, basedir_prefix, emit, keep_file, relative_to_basedir,
)

#: trace_<tid>_<task>.log, written by the runner's strace backend
TRACEFILE_RE = re.compile(r'^trace_(?P<tid>\d+)_(?P<task>.+)\.log$')

OPEN_CALLS = ("openat", "openat2", "open", "creat")
#: longest first, or 'openat' would match the head of 'openat2'
_OPEN_ALT = "|".join(sorted(OPEN_CALLS, key=len, reverse=True))

_OPEN_RE = re.compile(
    rf'(?:^|\s)(?:{_OPEN_ALT})\((?P<args>.*?)\)\s*=\s*\d+<(?P<path>[^>]*)>')
_RENAME_RE = re.compile(r'(?:^|\s)rename(?:at2?)?\((?P<args>.*?)\)\s*=\s*0')
_UNFINISHED_RE = re.compile(r'^(?P<pid>\d+)\s+(?P<call>\w+)\((?P<args>.*?)<unfinished')
_RESUMED_RE = re.compile(r'^(?P<pid>\d+)\s+<\.\.\.\s+(?P<call>\w+)\s+resumed>(?P<rest>.*)$')
_RESULT_RE = re.compile(r'=\s*\d+<(?P<path>[^>]*)>')
_QUOTED_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')

#: opendir reaches the kernel as an open with O_DIRECTORY; fanotify reports
#: directories only with FAN_ONDIR, so they are in neither graph
_DIRECTORY = "O_DIRECTORY"
_WRITE_FLAGS = ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND")


def _kind(args: str) -> str:
    return "write" if any(f in args for f in _WRITE_FLAGS) else "read"


def parse_trace(path: str) -> Tuple[Set[Tuple[str, str]], int]:
    """Distinct (absolute path, read|write) pairs for one task, and the
    number of calls they were distilled from."""
    seen: Set[Tuple[str, str]] = set()
    calls = 0
    # strace splits a call around another process's entry; the flags are on
    # the half that was interrupted
    pending: Dict[Tuple[str, str], str] = {}

    with open(path, errors="replace") as fh:
        for line in fh:
            if "<unfinished" in line:
                m = _UNFINISHED_RE.match(line)
                if m:
                    pending[(m.group("pid"), m.group("call"))] = m.group("args")
                continue

            if "resumed>" in line:
                m = _RESUMED_RE.match(line)
                if m is None or m.group("call") not in OPEN_CALLS:
                    continue
                res = _RESULT_RE.search(m.group("rest"))
                if res is None or not res.group("path"):
                    continue
                args = (pending.pop((m.group("pid"), m.group("call")), "")
                        + m.group("rest").split("=", 1)[0])
                calls += 1
                if _DIRECTORY not in args:
                    seen.add((res.group("path"), _kind(args)))
                continue

            m = _OPEN_RE.search(line)
            if m is not None:
                calls += 1
                if m.group("path") and _DIRECTORY not in m.group("args"):
                    seen.add((m.group("path"), _kind(m.group("args"))))
                continue

            if "rename" in line:
                m = _RENAME_RE.search(line)
                if m is None:
                    continue
                names = _QUOTED_RE.findall(m.group("args"))
                if names:
                    calls += 1
                    seen.add((names[-1], "write"))  # the destination is produced here

    return seen, calls


def collect(tracedir: str, basedir: str, file_filters):
    written: Dict[str, Set[str]] = {}
    read: Dict[str, Set[str]] = {}
    tasks: List[str] = []
    prefix = basedir_prefix(basedir)
    stats = {"traces": 0, "calls": 0, "kept": 0}

    for name in sorted(os.listdir(tracedir)):
        m = TRACEFILE_RE.match(name)
        if m is None:
            continue
        task = m.group("task")
        tasks.append(task)
        stats["traces"] += 1

        accesses, calls = parse_trace(os.path.join(tracedir, name))
        stats["calls"] += calls
        for target, kind in accesses:
            rel = relative_to_basedir(target, prefix)
            if rel is None or not keep_file(rel, file_filters):
                continue
            stats["kept"] += 1
            (written if kind == "write" else read).setdefault(rel, set()).add(task)

    return written, read, sorted(set(tasks)), stats


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--straceDir", required=True,
                   help="directory of trace_<tid>_<task>.log files")
    add_common_arguments(p)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if not os.path.isdir(a.straceDir):
        print(f"no such directory: {a.straceDir}", file=sys.stderr)
        return 2

    written, read, tasks, stats = collect(
        a.straceDir, a.basedir, [re.compile(f) for f in a.file_filters])
    print(f"strace: {stats['traces']} task trace(s), {stats['calls']} call(s), "
          f"{stats['kept']} access(es) kept under {a.basedir}")
    if not stats["traces"]:
        print(f"WARNING: no trace_*.log in {a.straceDir}", file=sys.stderr)

    emit(a, written, read, tasks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
