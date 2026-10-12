#!/usr/bin/env python3
"""Build and upload the slot manifest for the TPC map-creation GRID pipeline.

Bridge between the local Step-1 list discovery (discoverResiduals.sh) and GRID submission.

Cuts each run into time windows of ~--slot-length-min and writes ONE manifest line per window:

    <run> \t <winIdx> \t <winCount> \t <winFirstTS> \t <winLastTS> \t <comma-separated alien:// paths>

paired with `grid_submit.sh --prodsplit <nWindows>`. Every subjob gets nothing but a plain integer
index (ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID), downloads this one manifest and picks its own line, so a
subjob index identifies a (run, window) pair on its own. Both job scripts read the window straight off
that line, which is why they cannot disagree about a slot's identity.

Why the windows are not simply the aggregation labels
-----------------------------------------------------
Each residual filename carries the slot label <firstTS>_<lastTS>_<firstTF>_<lastTF> that its reco
job assigned, and those labels are NOT a uniform grid -- same-length slots are not guaranteed, and a
run's catalog can hold overlapping/nested labels at different granularities (why doesn't matter here,
just that it happens). Slicing per label gives overlapping slots with wildly uneven statistics.
Choosing the window length here instead makes granularity a deliberate decision, uniform across runs.

A file is assigned to a window when its label overlaps it by MORE than --overlap-margin-ms. A bare
overlap test is too generous at the edges: coarse labels routinely begin 1-2 ms before a window ends,
which would drag all of their files into a window whose map they contribute nothing to. The bound is
exact -- if a label overlaps by X ms then at most X ms of that file's data can belong to the window,
and the macro's own per-TF cut discards the rest regardless -- so skipping at X <= margin costs at
most `margin` ms of coverage per window edge.

This was a bash+awk script. It moved to Python because the work is arithmetic over 13-digit
millisecond timestamps and every bug it produced was a property of the shell rather than of the
problem: `(( x += 0 ))` returning 1 under `set -e`, `sed | sort | head` aborting the script by SIGPIPE
under `pipefail`, `<<<` herestrings writing temp files onto Lustre, awk's %d truncating a millisecond
timestamp through a 32-bit int on mawk, and awk holding one output file open per window. Python has
arbitrary-precision ints and none of those failure modes.

Prints the number of manifest lines (windows) to stdout on its own -- pass that as --prodsplit N to
grid_submit.sh. All other output goes to stderr, so `N=$(./stageSlotsForGrid.py ...)` captures just the
count.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# o2tpc_residuals_<firstTS>_<lastTS>_<firstTF>_<lastTF>.root, anchored: the timestamps are always
# exactly 13 digits (ResidualAggregator.cxx formats them from the slot's start/end in ms).
SIG_RE = re.compile(r"o2tpc_residuals_(\d{13})_(\d{13})_\d+_\d+\.root$")


def log(msg):
    print(msg, file=sys.stderr)


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Build and upload the TPC map-creation slot manifest.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--lists-dir", default="./lists",
                   help="root lists dir (discoverResiduals.sh's WORK_DIR), containing one <run>/ "
                        "subdir per run, each with a <run>.residuals_lists.txt index")
    p.add_argument("--alien-dir", default="",
                   help="AliEn directory to upload the manifest into. Ignored with --preview.")
    p.add_argument("--manifest-name", default="mapSlots.tsv",
                   help="manifest filename. Tag it per submission (mapSlots.<JOBNAME>.tsv) so "
                        "concurrent productions do not overwrite each other's.")
    p.add_argument("--runs", default="",
                   help="comma-separated run whitelist. Empty means EVERY run under --lists-dir, "
                        "including ones left from an earlier batch, which would be recalibrated from "
                        "scratch at hours per slot. Naming a run that has no lists is an error.")
    p.add_argument("--slot-length-min", type=float, default=0,
                   help="target length of ONE map, in minutes. 0 = one window per run.")
    p.add_argument("--overlap-margin-ms", type=int, default=1000,
                   help="a file whose label overlaps a window by <= this is not assigned to it")
    p.add_argument("--window-lists", action="store_true",
                   help="also write one plain file list per window, for inspecting which files a "
                        "window got. OFF by default: on Lustre each is a metadata round trip and 120 "
                        "of them cost ~33 s, against ~0.03 s for all the actual work. The manifest "
                        "already holds every window in full, one line each.")
    p.add_argument("--window-dir", default="",
                   help="where --window-lists writes. Default: <manifest stem>.windows. Point it at "
                        "local disk (e.g. /tmp/windows) on a parallel filesystem.")
    p.add_argument("--timing", action="store_true", default=bool(os.environ.get("STAGE_TIMING")),
                   help="print a read/compute/write breakdown to stderr (also via STAGE_TIMING=1)")
    p.add_argument("--preview", action="store_true",
                   default=bool(os.environ.get("PREVIEW_ONLY")),
                   help="write the per-window lists but do not upload (also via PREVIEW_ONLY=1)")
    return p.parse_args(argv)


def read_slot_files(index_path):
    """The per-run index lists the file(s) holding that run's residual paths (normally exactly one)."""
    out = []
    for line in index_path.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(Path(line))
    return out


def plan_windows(run_first, run_last, slot_ms, margin_ms):
    """Whole steps of slot_ms across [run_first, run_last].

    A trailing remainder shorter than half a step is absorbed into the last window rather than left as
    a runt that would fail minTracksPerSlice. Returns [(winFirst, winLast, effectiveMargin)].
    """
    span = run_last - run_first
    if slot_ms <= 0 or span <= 0:
        n_win = 1
    else:
        n_win = max(1, span // slot_ms)
        if (span - n_win * slot_ms) * 2 >= slot_ms:
            n_win += 1

    wins = []
    for w in range(n_win):
        if n_win == 1:
            ws, we = run_first, run_last
        else:
            ws = run_first + w * slot_ms
            we = run_last if w + 1 == n_win else run_first + (w + 1) * slot_ms - 1
        # Clamp the margin to a tenth of the window so a short window can never be emptied by it.
        wins.append((ws, we, min(margin_ms, (we - ws) // 10)))
    return wins


def assign(paths, wins, run_first, slot_ms):
    """Fan every file out to the windows its label overlaps by more than that window's margin.

    Only the windows a label can possibly touch are examined, derived directly from the label bounds,
    rather than scanning all of them per file: with 10-minute labels and 5-minute windows that is 2-3
    candidates instead of the whole run's worth. Returns (buckets, grazed, orphans).
    """
    n_win = len(wins)
    buckets = [[] for _ in range(n_win)]
    grazed = [0] * n_win
    orphans = []

    for lo, hi, line in paths:
        if slot_ms > 0 and n_win > 1:
            # Windows are contiguous steps of slot_ms from run_first, so a label maps to an index
            # range. +/-1 guards the boundaries and the last window, which extends to run_last.
            first = max(0, (lo - run_first) // slot_ms - 1)
            last = min(n_win - 1, (hi - run_first) // slot_ms + 1)
        else:
            first, last = 0, n_win - 1

        hit = False
        for i in range(first, last + 1):
            ws, we, margin = wins[i]
            if hi < ws or lo > we:
                continue
            if min(hi, we) - max(lo, ws) > margin:
                buckets[i].append(line)
                hit = True
            else:
                grazed[i] += 1
        if not hit:
            orphans.append(line)

    return buckets, grazed, orphans


def main(argv):
    args = parse_args(argv)

    if not args.preview and not args.alien_dir:
        log("ERROR: --alien-dir is required unless --preview is given")
        return 1

    lists_dir = Path(args.lists_dir)
    index_files = sorted(lists_dir.glob("*/*.residuals_lists.txt"))
    if not index_files:
        log(f"ERROR: no *.residuals_lists.txt files found under {lists_dir}")
        return 1

    slot_ms = int(round(args.slot_length_min * 60_000))
    wanted = [r for r in args.runs.split(",") if r] if args.runs else []

    # Rebuilt from scratch each time so it always reflects THIS invocation's slot length and margin
    # rather than a stale earlier split.
    window_dir = Path(args.window_dir) if args.window_dir else \
        Path(Path(args.manifest_name).with_suffix("").name + ".windows")
    t_rm = time.monotonic()
    if args.window_lists:
        if window_dir.exists():
            shutil.rmtree(window_dir)
        window_dir.mkdir(parents=True)
    t_rm = time.monotonic() - t_rm
    t_read = t_calc = t_write = 0.0

    manifest_lines = []
    runs_included = []
    empty_runs = []
    n_missing = 0
    n_orphan_total = 0

    for idx in index_files:
        run = idx.name[: -len(".residuals_lists.txt")]
        if wanted and run not in wanted:
            log(f"Run {run}: not in runs filter, skipping")
            continue
        runs_included.append(run)
        log(f"Run {run}: adding slots from {idx.name}")

        n_slots_run = 0
        for slot_file in read_slot_files(idx):
            if not slot_file.is_file():
                log(f"  WARNING: missing local file {slot_file}, skipping")
                n_missing += 1
                continue

            _t = time.monotonic()
            _text = slot_file.read_text()
            t_read += time.monotonic() - _t
            _t = time.monotonic()
            parsed = []
            for line in _text.splitlines():
                m = SIG_RE.search(line)
                if m:
                    parsed.append((int(m.group(1)), int(m.group(2)), line))
            if not parsed:
                log(f"  WARNING: no parseable residual signature in {slot_file}, skipping")
                continue

            t_calc += time.monotonic() - _t
            _t = time.monotonic()
            run_first = min(p[0] for p in parsed)
            run_last = max(p[1] for p in parsed)
            wins = plan_windows(run_first, run_last, slot_ms, args.overlap_margin_ms)
            buckets, grazed, orphans = assign(parsed, wins, run_first, slot_ms)
            n_win = len(wins)
            t_calc += time.monotonic() - _t

            for w, ((ws, we, _), files) in enumerate(zip(wins, buckets)):
                if grazed[w]:
                    log(f"      (skipped {grazed[w]} file(s) grazing this window)")
                if not files:
                    log(f"  WARNING: run {run} window {w}/{n_win} [{ws},{we}] has no files, skipping")
                    continue
                if args.window_lists:
                    _t = time.monotonic()
                    out = window_dir / f"{run}.TD{w}of{n_win}.{ws}_{we}.txt"
                    out.write_text("\n".join(files) + "\n")
                    t_write += time.monotonic() - _t
                manifest_lines.append(f"{run}\t{w}\t{n_win}\t{ws}\t{we}\t{','.join(files)}")
                log(f"    window {w}/{n_win} [{ws},{we}] {(we - ws) // 1000}s {len(files)} file(s)")
                n_slots_run += 1

            # Safety net for the overlap margin: every file must still land in at least one window. It
            # always should -- an aggregation label is minutes long, so it overlaps some window by far
            # more than the margin -- but a file in no window at all is silent data loss.
            if orphans:
                log(f"  WARNING: {len(orphans)} file(s) of run {run} landed in NO window -- "
                    f"their data is not in any map.")
                log(f"           --overlap-margin-ms ({args.overlap_margin_ms}) is too large for a "
                    f"slot length of {args.slot_length_min} min.")
                for o in orphans[:3]:
                    log(f"             {o}")
                n_orphan_total += len(orphans)

        log(f"  {n_slots_run} slot(s) added for run {run}")
        if n_slots_run == 0:
            empty_runs.append(run)

    # A run named in --runs but absent from --lists-dir is a typo or a missed discovery step, not a
    # request for a smaller production.
    missing_runs = [r for r in wanted if r not in runs_included]
    if missing_runs:
        log(f"ERROR: run(s) requested in --runs have no *.residuals_lists.txt under {lists_dir}: "
            f"{' '.join(missing_runs)}")
        log("       Run discoverResiduals.sh for them first, or drop them from --runs.")
        return 1

    if n_missing or empty_runs or n_orphan_total:
        log("")
        log("  ****************************************************************")
        log("  ** INCOMPLETE INPUT -- this manifest is smaller than expected  **")
        if n_missing:
            log(f"  **   {n_missing} slot file(s) referenced by an index but missing on disk")
        if empty_runs:
            log(f"  **   run(s) contributing 0 slots: {' '.join(empty_runs)}")
        if n_orphan_total:
            log(f"  **   {n_orphan_total} file(s) landed in no window -- lower --overlap-margin-ms")
        log("  **   -> re-run discoverResiduals.sh for those runs, or accept")
        log("  **      that they are simply absent from this production.")
        log("  ****************************************************************")
        log("")

    manifest_text = "".join(l + "\n" for l in manifest_lines)
    # The manifest is always written locally, as a single file -- it is the complete record of the
    # split and costs one create.
    _t = time.monotonic()
    Path(args.manifest_name).write_text(manifest_text)
    t_write += time.monotonic() - _t
    n_total = len(manifest_lines)

    if args.timing:
        log(f"timing: clear={t_rm:.2f}s read={t_read:.2f}s compute={t_calc:.2f}s "
            f"write={t_write:.2f}s ({n_total} window file(s))")

    if args.preview:
        log("PREVIEW_ONLY set -- manifest NOT uploaded.")
        log(f"Manifest written to: {args.manifest_name} ({n_total} window(s))")
        if args.window_lists:
            log(f"Per-window file lists in: {window_dir}/")
        else:
            log("Pass --window-lists to also dump one file list per window "
                "(slow on Lustre; add --window-dir /tmp/... )")
        print(n_total)
        return 0

    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as fh:
        fh.write(manifest_text)
        tmp_manifest = fh.name
    try:
        dest = f"alien://{args.alien_dir.rstrip('/')}/{args.manifest_name}"
        subprocess.run(["alien.py", "cp", "-f", f"file:{tmp_manifest}", dest],
                       check=True, stdout=sys.stderr.fileno())
        log(f"Manifest uploaded: {dest} ({n_total} slot(s) across {len(runs_included)} run(s))")
    finally:
        os.unlink(tmp_manifest)

    log(f"Manifest also written locally to: {args.manifest_name}")
    if args.window_lists:
        log(f"Per-window file lists in: {window_dir}/")
    log(f"Runs in this manifest: {' '.join(runs_included)}")
    print(n_total)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
