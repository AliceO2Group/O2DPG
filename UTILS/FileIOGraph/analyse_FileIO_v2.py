#!/usr/bin/env python3
"""Turn a fanotify file-access log plus the runner action log into the
file-task dependency report.

Attribution comes from the process chain the monitor records: an access is
a task's if any pid in the chain is the pid the action log gives that task.
Both action-log formats are accepted:

  Old runner:  "... INFO Task <PID> <tid>:<name> finished with status 0"
  New runner:  "... INFO Task pid=<PID> tid=<TID> <name> finished rc=0"
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Dict, List, Set, Tuple

from filegraph_report import (
    add_common_arguments, basedir_prefix, emit, keep_file, relative_to_basedir,
)


# ── action-log patterns ───────────────────────────────────────────────────────

# Old runner: "... INFO Task <PID> <tid>:<name> finished with status 0"
_PAT_OLD = re.compile(r'.*INFO Task (\d+)[^:]*:(\w+) finished with status 0')
# New runner: "... INFO Task pid=<PID> tid=<TID> <name> finished rc=0"
_PAT_NEW = re.compile(r'.*INFO Task pid=(\d+) tid=\d+ (\S+) finished rc=0')


def parse_action_log(path: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Parse task-PID associations from an action log.

    Returns (pid_to_task, task_to_pid).  Only successfully completed tasks
    are included (rc=0 / status 0) so failed retries don't pollute the map.
    """
    pid_to_task: Dict[str, str] = {}
    task_to_pid: Dict[str, str] = {}
    with open(path) as fh:
        for line in fh:
            m = _PAT_OLD.match(line) or _PAT_NEW.match(line)
            if m:
                pid, name = m.group(1), m.group(2)
                pid_to_task[pid] = name
                task_to_pid[name] = pid
    return pid_to_task, task_to_pid


# ── monitor-log parsing ───────────────────────────────────────────────────────

_RECORD_RE = re.compile(r'"?([^"]+)"?,(read|write),(.*)')


def parse_monitor_log(
    path: str,
    pid_to_task: Dict[str, str],
    basedir: str,
    file_filters: List[re.Pattern],
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Parse the fanotify raw log and map files to the tasks that touched them.

    Returns (file_written_by, file_read_by) where each value is a set of
    task names.  Only files inside *basedir* that pass *file_filters* and
    are not excluded by the built-in exclude pattern are included.

    A file access is attributed to a task when any PID in the process-chain
    column of the monitor log appears in *pid_to_task*.  This works for both
    direct children and children-of-children of the task process because the
    fanotify monitor records the full ancestor chain up to the root PID.
    """
    file_written: Dict[str, Set[str]] = {}
    file_read: Dict[str, Set[str]] = {}
    prefix = basedir_prefix(basedir)

    with open(path) as fh:
        for line in fh:
            m = _RECORD_RE.match(line)
            if not m:
                continue
            fname, mode, chain = m.group(1), m.group(2), m.group(3)

            rel = relative_to_basedir(fname, prefix)
            if rel is None or not keep_file(rel, file_filters):
                continue

            for pid in chain.split(";"):
                task = pid_to_task.get(pid)
                if task is None:
                    continue
                if mode == "write":
                    file_written.setdefault(rel, set()).add(task)
                else:
                    file_read.setdefault(rel, set()).add(task)

    return file_written, file_read


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--actionFile", required=True,
                   help="O2DPG pipeline runner action log")
    p.add_argument("--monitorFile", required=True,
                   help="fanotify raw log from monitor_fileaccess_v2.exe")
    add_common_arguments(p)
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)

    file_filters = [re.compile(f) for f in args.file_filters]

    pid_to_task, task_to_pid = parse_action_log(args.actionFile)
    if not pid_to_task:
        print(
            f"WARNING: no task completions found in {args.actionFile}.\n"
            "Check that the action log is from a completed run and that\n"
            "its format matches either the old or new O2DPG runner.",
            file=sys.stderr,
        )
    else:
        print(f"Action log: {len(pid_to_task)} completed task(s) found")

    file_written, file_read = parse_monitor_log(
        args.monitorFile, pid_to_task, args.basedir, file_filters,
    )

    emit(args, file_written, file_read, sorted(task_to_pid))


if __name__ == "__main__":
    main()
