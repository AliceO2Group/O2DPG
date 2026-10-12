"""Build the file-task dependency report from two file->tasks maps.

Holds the exclusion rules, the ./tfN -> ./tfX templating, the JSON schema
that --remove-files-early reads back, and the graphviz rendering.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Dict, Optional, Sequence, Set

#: log files, the CCDB log and the DPL config are noise, not data flow
EXCLUDE_RE = re.compile(r'(.*\.log.*|ccdb/log|.*dpl-config\.json)')
TF_PATH_RE = re.compile(r'^\./tf(?P<tf>\d+)/')


def basedir_prefix(basedir: str) -> str:
    return basedir.rstrip("/") + "/"


def relative_to_basedir(fname: str, prefix: str) -> Optional[str]:
    """'./x/y' for a path under the prefix from basedir_prefix(), else None."""
    if not fname.startswith(prefix):
        return None
    return "./" + fname[len(prefix):]


def keep_file(rel: str, file_filters: Sequence) -> bool:
    if EXCLUDE_RE.match(rel):
        return False
    return any(r.match(rel) for r in file_filters)


def task_template_for_timeframe(task_name: str, source_tf: int) -> str:
    suffix = f"_{source_tf}"
    if task_name.endswith(suffix):
        return f"{task_name[:-len(suffix)]}_X"
    return task_name


def build_report(file_written: Dict[str, Set[str]],
                 file_read: Dict[str, Set[str]],
                 tasks: Sequence[str]) -> Dict:
    """Assemble the JSON document from the two file->tasks maps."""
    all_files = sorted(set(file_written) | set(file_read))
    file_report = [
        {
            "file": f,
            "written_by": sorted(file_written.get(f, set())),
            "read_by": sorted(file_read.get(f, set())),
        }
        for f in all_files
    ]

    templates: Dict[str, Dict] = {}
    for entry in file_report:
        match = TF_PATH_RE.match(entry["file"])
        if match is None:
            continue
        source_tf = int(match.group("tf"))
        merged = templates.setdefault(
            TF_PATH_RE.sub("./tfX/", entry["file"], count=1),
            {"written_by": set(), "read_by": set(), "source_timeframes": set()},
        )
        merged["source_timeframes"].add(source_tf)
        for kind in ("written_by", "read_by"):
            for task in entry[kind]:
                merged[kind].add(task_template_for_timeframe(task, source_tf))

    file_template_report = [
        {
            "file": f,
            "written_by": sorted(v["written_by"]),
            "read_by": sorted(v["read_by"]),
            "source_timeframes": sorted(v["source_timeframes"]),
        }
        for f, v in sorted(templates.items())
    ]

    task_reads: Dict[str, Set[str]] = {}
    task_writes: Dict[str, Set[str]] = {}
    for f, ts in file_read.items():
        for t in ts:
            task_reads.setdefault(t, set()).add(f)
    for f, ts in file_written.items():
        for t in ts:
            task_writes.setdefault(t, set()).add(f)
    task_report = [
        {
            "task": t,
            "writes": sorted(task_writes.get(t, set())),
            "reads": sorted(task_reads.get(t, set())),
        }
        for t in sorted(tasks)
    ]

    return {
        "file_report": file_report,
        "file_template_report": file_template_report,
        "task_report": task_report,
    }


def draw_graph(filename: str, file_written: Dict[str, Set[str]],
               file_read: Dict[str, Set[str]], tasks: Sequence[str]) -> None:
    try:
        from graphviz import Digraph
    except ImportError:
        print("graphviz not installed, skipping graph", file=sys.stderr)
        return

    ccdb_re = re.compile(r"ccdb(.*)/snapshot\.root")
    dot = Digraph(comment="O2DPG file-task network")
    idx: Dict[str, int] = {}

    # CCDB snapshots are labelled by object path; a real workflow pulls
    # dozens and the full names swamp the picture
    ccdb, normal = [], []
    for f in set(file_written) | set(file_read):
        m = ccdb_re.match(f)
        (ccdb if m else normal).append((f, m.group(1) if m else f))

    with dot.subgraph(name="CCDB") as sg:
        sg.attr(color="blue")
        for f, label in ccdb:
            idx[f] = len(idx)
            sg.node(str(idx[f]), label, color="blue")

    with dot.subgraph(name="normal") as sg:
        sg.attr(color="black")
        for f, label in normal:
            idx[f] = len(idx)
            sg.node(str(idx[f]), label, color="red")
        for t in tasks:
            idx[t] = len(idx)
            sg.node(str(idx[t]), t, shape="box", color="green", style="filled")

    for f, ts in file_read.items():
        for t in ts:
            dot.edge(str(idx[f]), str(idx[t]))
    for f, ts in file_written.items():
        for t in ts:
            dot.edge(str(idx[t]), str(idx[f]))

    dot.render(filename, format="pdf")
    dot.render(filename, format="gv")
    print(f"Wrote {filename}.pdf and {filename}.gv")


def add_common_arguments(parser) -> None:
    parser.add_argument("--basedir", default="/",
                        help="Workflow working directory (default: /)")
    parser.add_argument("--file-filters", nargs="+", default=[r".*"],
                        help="Regex filters to select file paths (default: all)")
    parser.add_argument("--graphviz", default=None,
                        help="also render the file/task network with this "
                             "base filename")
    parser.add_argument("-o", "--output", required=True,
                        help="Output JSON report path")


def emit(args, file_written: Dict[str, Set[str]], file_read: Dict[str, Set[str]],
         tasks: Sequence[str]) -> None:
    """Render and write what add_common_arguments() asked for."""
    if args.graphviz:
        draw_graph(args.graphviz, file_written, file_read, tasks)
    doc = build_report(file_written, file_read, tasks)
    with open(args.output, "w") as fh:
        json.dump(doc, fh, indent=2)
    print(f"Wrote {args.output}: {len(doc['file_report'])} file(s) referenced, "
          f"{len(doc['file_template_report'])} timeframe file template(s), "
          f"{len(doc['task_report'])} task(s) mapped")
