#!/usr/bin/env python3
"""Grade one file-graph report against another.

  EXACT   candidate and reference agree edge for edge
  SAFE    candidate is a superset: nothing missing, some extra
  UNSAFE  candidate misses an edge the reference has

The asymmetry is the point: the runner deletes a file once every task
listed against it has finished, so a missing edge deletes a file a later
task still reads, while an extra one only keeps it on disc longer.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, List, Set, Tuple

SECTIONS = ("file_report", "file_template_report")
Edges = Dict[Tuple[str, str], Set[str]]


def _edges(report: Dict, section: str) -> Edges:
    """(file, 'written_by'|'read_by') -> set of task names."""
    out: Edges = {}
    for entry in report.get(section) or []:
        f = entry.get("file")
        if not f:
            continue
        for kind in ("written_by", "read_by"):
            out[(f, kind)] = set(entry.get(kind) or [])
    return out


def _diff(a: Edges, b: Edges) -> List[Tuple[str, str, List[str]]]:
    """Edges present in a and not in b, as (file, kind, tasks)."""
    out = []
    for (f, kind), tasks in a.items():
        extra = tasks - b.get((f, kind), set())
        if extra:
            out.append((f, kind, sorted(extra)))
    return sorted(out)


class SectionDiff:
    def __init__(self, section: str, ref: Dict, cand: Dict):
        self.section = section
        re_, ce = _edges(ref, section), _edges(cand, section)
        self.ref_files = {f for f, _ in re_}
        self.cand_files = {f for f, _ in ce}
        self.only_ref = sorted(self.ref_files - self.cand_files)
        self.only_cand = sorted(self.cand_files - self.ref_files)
        self.missing = _diff(re_, ce)
        self.extra = _diff(ce, re_)
        self.n_ref_edges = sum(len(v) for v in re_.values())
        self.n_cand_edges = sum(len(v) for v in ce.values())
        self.n_missing = sum(len(t) for _, _, t in self.missing)
        self.n_extra = sum(len(t) for _, _, t in self.extra)

    @property
    def verdict(self) -> str:
        if self.n_missing:
            return "UNSAFE"
        return "SAFE" if self.n_extra else "EXACT"

    @property
    def recall(self) -> float:
        if not self.n_ref_edges:
            return 1.0
        return (self.n_ref_edges - self.n_missing) / self.n_ref_edges

    def report(self, limit: int) -> str:
        def block(header, items, fmt):
            if not items:
                return []
            out = [f"  {header} ({len(items)}):"]
            out += [f"    {fmt(i)}" for i in items[:limit]]
            if len(items) > limit:
                out.append(f"    ... {len(items) - limit} more")
            return out

        lines = [
            f"[{self.section}]",
            f"  files      reference={len(self.ref_files)} "
            f"candidate={len(self.cand_files)}  only-ref={len(self.only_ref)} "
            f"only-cand={len(self.only_cand)}",
            f"  edges      reference={self.n_ref_edges} "
            f"candidate={self.n_cand_edges}  missing={self.n_missing} "
            f"extra={self.n_extra}  recall={self.recall * 100:.2f}%",
            f"  verdict    {self.verdict}",
        ]
        lines += block("files the candidate never saw", self.only_ref, str)
        lines += block("MISSING edges", self.missing,
                       lambda e: f"- {e[0]} {e[1]}: {', '.join(e[2])}")
        lines += block("extra edges, harmless", self.extra,
                       lambda e: f"+ {e[0]} {e[1]}: {', '.join(e[2])}")
        return "\n".join(lines)


def compare(ref: Dict, cand: Dict, limit: int = 20) -> Tuple[str, Dict]:
    diffs = [SectionDiff(s, ref, cand) for s in SECTIONS]
    verdicts = [d.verdict for d in diffs]
    overall = ("UNSAFE" if "UNSAFE" in verdicts
               else "SAFE" if "SAFE" in verdicts else "EXACT")
    summary = {
        "verdict": overall,
        "sections": {
            d.section: {
                "verdict": d.verdict,
                "reference_edges": d.n_ref_edges,
                "candidate_edges": d.n_cand_edges,
                "missing_edges": d.n_missing,
                "extra_edges": d.n_extra,
                "recall": d.recall,
                "files_only_in_reference": d.only_ref,
                "files_only_in_candidate": d.only_cand,
                "missing": [list(e) for e in d.missing],
                "extra": [list(e) for e in d.extra],
            } for d in diffs
        },
    }
    return "\n".join(d.report(limit) for d in diffs), summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", required=True, help="the report to be reproduced")
    ap.add_argument("--candidate", required=True, help="the report under test")
    ap.add_argument("--limit", type=int, default=20, help="differences to print per class")
    ap.add_argument("--json", default=None, help="also write the full diff here")
    ap.add_argument("--allow", choices=["EXACT", "SAFE"], default="SAFE",
                    help="worst verdict that still exits 0 (default: SAFE)")
    a = ap.parse_args(argv)

    with open(a.reference) as f:
        ref = json.load(f)
    with open(a.candidate) as f:
        cand = json.load(f)

    text, summary = compare(ref, cand, a.limit)
    print(f"reference: {a.reference}")
    print(f"candidate: {a.candidate}")
    print(text)
    print(f"\nOVERALL: {summary['verdict']}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"wrote {a.json}")

    return 0 if summary["verdict"] in ("EXACT", a.allow) else 1


if __name__ == "__main__":
    sys.exit(main())
