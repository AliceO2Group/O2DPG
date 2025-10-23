#!/usr/bin/env python3
# bench_groupby_regression_optimized.py
# Unified Phase-2 / Phase-3 benchmarking suite
# ----------------------------------------------------------------------
# - Phase 2: legacy demo compatibility
# - Phase 3: warm + repeated timings for loky / threading / fast
# ----------------------------------------------------------------------

from __future__ import annotations

import argparse
import os
import time
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd


# ======================================================================
# Utilities
# ======================================================================

def set_blas_threads_one_v2() -> None:
    """Ensure BLAS libraries run single-threaded to avoid oversubscription."""
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")


def time_call_warm_v2(fn: Callable[[], object], *, warmups: int = 1, repeats: int = 5) -> Tuple[float, List[float]]:
    """Run fn() with warm-up and return (median_time_s, list_of_times)."""
    for _ in range(max(0, warmups)):
        fn()
    times: List[float] = []
    for _ in range(max(1, repeats)):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    return float(np.median(times)), times


def _mk_synth_data_v2(n_groups: int, rows: int, *, seed: int = 123) -> pd.DataFrame:
    """Generate synthetic small-group dataset for benchmarking."""
    rng = np.random.default_rng(seed)
    N = n_groups * rows
    df = pd.DataFrame({
        "group": np.repeat(np.arange(n_groups), rows),
        "x1": rng.normal(size=N),
        "x2": rng.normal(size=N),
    })
    df["y"] = 2.0 * df["x1"] + 3.0 * df["x2"] + rng.normal(scale=0.1, size=N)
    df["weight"] = 1.0
    return df


# ======================================================================
# Phase 3 benchmark core
# ======================================================================

def benchmark_fast_backend_v2(
        *,
        n_groups: int = 1000,
        rows: int = 5,
        n_jobs: int = 4,
        warmups: int = 1,
        repeats: int = 5,
        seed: int = 123,
        verbose: bool = True,
) -> Dict[str, float]:
    """
    Compare make_parallel_fit_v2 (loky/threading) vs make_parallel_fit_fast
    using warm-ups + median repeats. Returns {backend: median_seconds}.
    """
    from groupby_regression_optimized import make_parallel_fit_v2, make_parallel_fit_fast

    set_blas_threads_one_v2()
    df = _mk_synth_data_v2(n_groups=n_groups, rows=rows, seed=seed)
    selection = pd.Series(True, index=df.index)

    def cfg_loky():
        return make_parallel_fit_v2(
            df=df,
            gb_columns=["group"],
            fit_columns=["y"],
            linear_columns=["x1", "x2"],
            median_columns=[],
            weights="weight",
            suffix="_loky",
            selection=selection,
            addPrediction=False,
            n_jobs=n_jobs,
            min_stat=[2],
            backend="loky",
        )

    def cfg_threading():
        return make_parallel_fit_v2(
            df=df,
            gb_columns=["group"],
            fit_columns=["y"],
            linear_columns=["x1", "x2"],
            median_columns=[],
            weights="weight",
            suffix="_thr",
            selection=selection,
            addPrediction=False,
            n_jobs=n_jobs,
            min_stat=[2],
            backend="threading",
        )

    def cfg_fast():
        return make_parallel_fit_fast(
            df=df,
            gb_columns=["group"],
            fit_columns=["y"],
            linear_columns=["x1", "x2"],
            median_columns=[],
            weights="weight",
            suffix="_fast",
            selection=selection,
            cast_dtype="float64",
            min_stat=[2],
            diag=False,
            diag_prefix="diag_",
            addPrediction=False,
        )

    backends = [("loky", cfg_loky), ("threading", cfg_threading), ("fast", cfg_fast)]

    if verbose:
        print("\n" + "=" * 70)
        print("PHASE 3: Fast backend benchmark (warm-up + median)")
        print("=" * 70)
        print(f"Data: {n_groups} groups × {rows} rows = {n_groups*rows} total | n_jobs={n_jobs}")
        print(f"Warm-ups: {warmups}  Repeats: {repeats}\n")

    results: Dict[str, float] = {}
    for name, fn in backends:
        t_med, runs = time_call_warm_v2(fn, warmups=warmups, repeats=repeats)
        results[name] = t_med
        if verbose:
            print(f"{name:10s}: {t_med:.3f}s   (runs: {', '.join(f'{x:.3f}' for x in runs)})")

    base = results.get("loky", np.nan)
    if verbose and np.isfinite(base):
        print("\nSpeedups (relative to loky):")
        for name, t in results.items():
            sp = base / t if t > 0 else np.nan
            print(f"{name:10s}: {sp:5.2f}×")
        print()

    return results


def run_phase3_benchmarks_v2(
        *,
        n_groups: int = 1000,
        rows: int = 5,
        n_jobs: int = 4,
        warmups: int = 1,
        repeats: int = 5,
        seed: int = 123,
        csv_path: str | None = None,
        verbose: bool = True,
) -> Dict[str, float]:
    """Convenience wrapper; optionally log results to CSV."""
    results = benchmark_fast_backend_v2(
        n_groups=n_groups,
        rows=rows,
        n_jobs=n_jobs,
        warmups=warmups,
        repeats=repeats,
        seed=seed,
        verbose=verbose,
    )
    if csv_path:
        write_results_csv_v2(
            results,
            csv_path=csv_path,
            extra_meta=dict(
                n_groups=n_groups,
                rows=rows,
                n_jobs=n_jobs,
                warmups=warmups,
                repeats=repeats,
                seed=seed,
            ),
        )
    return results


# ======================================================================
# Phase 2 compatibility shim
# ======================================================================

def run_phase2_suite_v2() -> None:
    """
    Try to run your existing Phase-2 demo/benchmark suite.
    Attempts to find it in this file or import from phase2_demo.py.
    """
    candidates = [
        "run_phase2_suite",
        "phase2_main",
        "run_phase2",
        "demo_phase2",
        "main_phase2",
        "run_phase2_benchmarks",
        "run_phase2_demo",
    ]
    for name in candidates:
        fn = globals().get(name)
        if callable(fn):
            print(f"[Phase-2] Running entry point: {name}()")
            return fn()

    try:
        import phase2_demo as _p2
        for name in candidates:
            fn = getattr(_p2, name, None)
            if callable(fn):
                print(f"[Phase-2] Running entry point: phase2_demo.{name}()")
                return fn()
        print("[Phase-2] Found phase2_demo module, but no known entry point found.")
    except Exception:
        pass

    print("[Phase-2] No entry point found. "
          "Paste your Phase-2 runner into this file "
          "and name it one of: " + ", ".join(candidates))


# ======================================================================
# CSV writer for result tracking
# ======================================================================

def write_results_csv_v2(
        results: Dict[str, float],
        *,
        csv_path: str,
        extra_meta: Dict[str, object] | None = None,
) -> None:
    """Append benchmark results with metadata to a CSV file."""
    row = {"timestamp": pd.Timestamp.now(tz="UTC").isoformat()}
    row.update({f"time_{k}_s": float(v) for k, v in results.items()})
    if extra_meta:
        row.update(extra_meta)
    df = pd.DataFrame([row])
    header = not os.path.exists(csv_path)
    df.to_csv(csv_path, mode="a", index=False, header=header)
    print(f"[log] Results appended to {csv_path}")


# ======================================================================
# CLI entry point (no symmetry break)
# ======================================================================

def main_v2(argv: List[str] | None = None) -> None:
    """Command-line interface for benchmarks."""
    p = argparse.ArgumentParser(description="Benchmarks for GroupByRegressor (v2/v3)")
    p.add_argument("--phase2", action="store_true", help="Run Phase-2 legacy suite")
    p.add_argument("--phase3", action="store_true", help="Run Phase-3 fast benchmark")
    p.add_argument("--n-groups", type=int, default=1000)
    p.add_argument("--rows", type=int, default=5)
    p.add_argument("--n-jobs", type=int, default=4)
    p.add_argument("--warmups", type=int, default=1)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--csv", type=str, help="Optional path to append CSV results")
    args = p.parse_args(argv)

    if args.phase2:
        run_phase2_suite_v2()
    else:
        run_phase3_benchmarks_v2(
            n_groups=args.n_groups,
            rows=args.rows,
            n_jobs=args.n_jobs,
            warmups=args.warmups,
            repeats=args.repeats,
            csv_path=args.csv,
        )


if __name__ == "__main__":
    main_v2()
