#!/usr/bin/env python3
"""Build a workflow whose file-IO graph is known, run it under one or more
backends, and grade every report against that graph and against a reference.

    equivalence_test.py --backends strace --reference fanotify --ntf 8
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

from filegraph_test_support import REPO, filegraph

from compare_reports import compare  # noqa: E402
from filegraph_report import build_report  # noqa: E402

RESOURCES = {"cpu": 1, "mem": 100, "relative_cpu": 1.0}


def build_workflow(ntf: int, sleep: str):
    """A workflow plus the file->tasks maps its commands imply.

    Covers what makes attribution hard: a global task consuming every
    timeframe, a file with two readers, a subdirectory created at run time,
    four different libc entry points, and tasks that overlap in time.
    """
    stages, written, read = [], {}, {}

    def w(f, t):
        written.setdefault(f, set()).add(t)

    def r(f, t):
        read.setdefault(f, set()).add(t)

    def stage(name, cmd, needs, cwd, tf, label):
        stages.append({"name": name, "cmd": f"sleep {sleep}; {cmd}",
                       "needs": needs, "cwd": cwd, "timeframe": tf,
                       "labels": [label], "resources": RESOURCES})

    stage("bkg", "echo bkgdata > bkg.dat", [], "./", -1, "SIM")
    w("./bkg.dat", "bkg")

    for i in range(1, ntf + 1):
        tf = f"tf{i}"
        # shell redirection and Python open() in one task
        stage(f"sgnsim_{i}",
              f"cat ../bkg.dat > sgn.dat; "
              f"python3 -c \"open('kine.dat','w').write('kine{i}')\"",
              ["bkg"], f"./{tf}", i, "SIM")
        r("./bkg.dat", f"sgnsim_{i}")
        w(f"./{tf}/sgn.dat", f"sgnsim_{i}")
        w(f"./{tf}/kine.dat", f"sgnsim_{i}")

        # cp, and a subdirectory created while the workflow is running
        stage(f"digi_{i}", "cp sgn.dat digi.dat; mkdir -p sub; "
                           "cp digi.dat sub/extra.dat",
              [f"sgnsim_{i}"], f"./{tf}", i, "DIGI")
        r(f"./{tf}/sgn.dat", f"digi_{i}")
        w(f"./{tf}/digi.dat", f"digi_{i}")
        r(f"./{tf}/digi.dat", f"digi_{i}")
        w(f"./{tf}/sub/extra.dat", f"digi_{i}")

        # awk opens its output file itself, through fopen
        stage(f"reco_{i}", "awk '{print > \"reco.dat\"}' digi.dat; "
                           "cat kine.dat >> reco.dat",
              [f"digi_{i}"], f"./{tf}", i, "RECO")
        r(f"./{tf}/digi.dat", f"reco_{i}")
        r(f"./{tf}/kine.dat", f"reco_{i}")
        w(f"./{tf}/reco.dat", f"reco_{i}")

        stage(f"aod_{i}", "cat reco.dat sub/extra.dat > AO2D.dat",
              [f"reco_{i}"], f"./{tf}", i, "AOD")
        r(f"./{tf}/reco.dat", f"aod_{i}")
        r(f"./{tf}/sub/extra.dat", f"aod_{i}")
        w(f"./{tf}/AO2D.dat", f"aod_{i}")
        r(f"./tf{i}/AO2D.dat", "aodmerge")

    inputs = " ".join(f"tf{i}/AO2D.dat" for i in range(1, ntf + 1))
    stage("aodmerge", f"cat {inputs} > AO2D_merged.dat",
          [f"aod_{i}" for i in range(1, ntf + 1)], "./", -1, "AOD")
    w("./AO2D_merged.dat", "aodmerge")

    truth = build_report(written, read, [s["name"] for s in stages])
    return {"stages": stages}, truth


def run(argv, **kw):
    print("+ " + " ".join(argv), flush=True)
    return subprocess.run(argv, **kw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default=None,
                    help="scratch directory (default: a fresh one under $TMPDIR)")
    ap.add_argument("--backends", default=None,
                    help="comma-separated backends to test (default: all but "
                         f"the reference; known: {', '.join(sorted(filegraph.BACKENDS))})")
    ap.add_argument("--reference", default="fanotify",
                    help="backend to compare the others against ('' to skip)")
    ap.add_argument("--ntf", type=int, default=4)
    ap.add_argument("--cpu-limit", type=int, default=4)
    ap.add_argument("--sleep", default="0.4")
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args(argv)

    runner = os.path.join(REPO, "MC", "workflow_runner",
                          "o2dpg_workflow_runner.py")
    if not os.path.exists(runner):
        print(f"no runner at {runner}", file=sys.stderr)
        return 2

    ref = a.reference.strip()
    candidates = ([b.strip() for b in a.backends.split(",") if b.strip()]
                  if a.backends is not None
                  else [b for b in sorted(filegraph.BACKENDS) if b != ref])
    active = list(dict.fromkeys(([ref] if ref else []) + candidates))
    if not active:
        print("nothing to run", file=sys.stderr)
        return 2

    workdir = a.workdir or os.path.join(
        os.getenv("TMPDIR", "/tmp"), f"filegraph_equiv_{os.getpid()}")
    os.makedirs(workdir, exist_ok=True)
    print(f"workdir: {workdir}")

    wf, truth = build_workflow(a.ntf, a.sleep)
    for name, doc in (("workflow.json", wf), ("truth.json", truth)):
        with open(os.path.join(workdir, name), "w") as f:
            json.dump(doc, f, indent=2)
    print(f"{len(wf['stages'])} stages, {len(truth['file_report'])} files expected")

    t0 = time.time()
    r = run([a.python, runner, "-f", "workflow.json",
             "--cpu-limit", str(a.cpu_limit), "--mem-limit", "8000",
             "--filegraph-backends", ",".join(active)],
            cwd=workdir, env=dict(os.environ, O2DPG_ROOT=REPO))
    if r.returncode != 0:
        print(f"runner failed with rc={r.returncode}", file=sys.stderr)
        return 2
    print(f"workflow finished in {time.time() - t0:.1f}s")

    reports = {}
    for b in active:
        found = glob.glob(os.path.join(workdir, f"filegraph_{b}_*.json"))
        if found:
            with open(found[0]) as f:
                reports[b] = json.load(f)

    failures = []

    def grade(title, reference, candidate, backend, why):
        print(f"\n{'=' * 72}\n== {title}\n{'=' * 72}")
        text, summary = compare(reference, candidate, limit=10)
        print(text)
        print(f"OVERALL: {summary['verdict']}")
        if summary["verdict"] == "UNSAFE":
            failures.append((backend, why))
        return summary

    for backend in active:
        if backend not in reports:
            print(f"\nNO REPORT from {backend}", file=sys.stderr)
            if backend != ref:
                failures.append((backend, "no report"))
            continue

        if backend == ref:
            # fanotify resolves the process chain from /proc after the event,
            # so on a fast machine it loses accesses by processes that exited
            print(f"\n{'=' * 72}\n== {backend} (reference) vs truth\n{'=' * 72}")
            text, summary = compare(truth, reports[backend], limit=10)
            print(text)
            print(f"OVERALL: {summary['verdict']}")
            if summary["verdict"] == "UNSAFE":
                print(f"NOTE: the reference {backend} itself misses edges")
            continue

        grade(f"{backend} vs truth", truth, reports[backend], backend,
              "misses edges the truth has")
        if ref in reports:
            summary = grade(f"{backend} vs {ref} (reference)", reports[ref],
                            reports[backend], backend, f"misses edges {ref} has")
            with open(os.path.join(workdir, f"diff_{backend}_vs_{ref}.json"), "w") as f:
                json.dump(summary, f, indent=2)

    print(f"\n{'=' * 72}")
    for b, why in failures:
        print(f"FAIL  {b}: {why}")
    if not failures:
        print("PASS  every backend is at least SAFE against truth"
              + (f" and against {ref}" if ref else ""))
    print(f"workdir kept at {workdir}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
