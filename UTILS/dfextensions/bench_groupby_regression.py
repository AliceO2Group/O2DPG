#!/usr/bin/env python3
"""
bench_groupby_regression.py — Single-file benchmark suite and reporter

Scenarios covered (configurable via CLI):
  1) Clean baseline (serial & parallel)
  2) Outliers: 5% @ 3σ, 10% @ 5σ, 10% @ 10σ
  3) Group sizes: 5, 20, 100 rows/group
  4) n_jobs: 1, 4, 10
  5) fitters: ols, robust, huber (if supported by implementation)
  6) sigmaCut: 3, 5, 10, 100

Outputs:
  - Pretty text report
  - JSON results (per scenario, with timing and configuration)
  - Optional CSV summary

Usage examples:
  python3 bench_groupby_regression.py --quick
  python3 bench_groupby_regression.py --rows 50000 --groups 10000 --out out_dir
  python3 bench_groupby_regression.py --emit-csv

Note:
  This script expects 'groupby_regression.py' in PYTHONPATH or next to it and
  uses GroupByRegressor.make_parallel_fit(...). See the wiring in _run_one().
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Tuple

import numpy as np
import pandas as pd

# --- Import the project module ---
try:
    import groupby_regression as gr
    from groupby_regression import GroupByRegressor
except Exception as e:
    print("[ERROR] Failed to import groupby_regression.py:", e, file=sys.stderr)
    raise

# --- Data Generators (Phase 1) ---
def _make_groups(n_rows: int, n_groups: int, rng: np.random.Generator) -> np.ndarray:
    base = np.repeat(np.arange(n_groups, dtype=np.int32), n_rows // n_groups)
    rem = n_rows - base.size
    if rem > 0:
        extra = rng.choice(n_groups, size=rem, replace=False)
        base = np.concatenate([base, extra.astype(np.int32, copy=False)])
    rng.shuffle(base)
    return base

def create_clean_data(n_rows: int, n_groups: int, *, seed: int = 42, noise_sigma: float = 1.0, x_corr: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    group = _make_groups(n_rows, n_groups, rng)
    mean = np.array([0.0, 0.0])
    cov = np.array([[1.0, x_corr], [x_corr, 1.0]])
    x = rng.multivariate_normal(mean, cov, size=n_rows, method="cholesky")
    x1 = x[:, 0].astype(np.float32); x2 = x[:, 1].astype(np.float32)
    eps = rng.normal(0.0, noise_sigma, size=n_rows).astype(np.float32)
    y = (2.0 * x1 + 3.0 * x2 + eps).astype(np.float32)
    df = pd.DataFrame({"group": group, "x1": x1, "x2": x2, "y": y})
    return df

def create_data_with_outliers(n_rows: int, n_groups: int, *, outlier_pct: float = 0.10, outlier_magnitude: float = 5.0,
                              seed: int = 42, noise_sigma: float = 1.0, x_corr: float = 0.0) -> pd.DataFrame:
    df = create_clean_data(n_rows, n_groups, seed=seed, noise_sigma=noise_sigma, x_corr=x_corr)
    rng = np.random.default_rng(seed + 1337)
    k = int(math.floor(outlier_pct * n_rows))
    if k > 0:
        idx = rng.choice(n_rows, size=k, replace=False)
        signs = rng.choice(np.array([-1.0, 1.0], dtype=np.float32), size=k, replace=True)
        shift = (outlier_magnitude * noise_sigma * signs).astype(np.float32)
        y = df["y"].to_numpy(copy=True)
        y[idx] = (y[idx] + shift).astype(np.float32)
        df["y"] = y
    return df

# --- Benchmark Plumbing ---
@dataclass
class Scenario:
    name: str
    outlier_pct: float
    outlier_mag: float
    rows_per_group: int
    n_groups: int
    n_jobs: int
    fitter: str
    sigmaCut: float

def _run_one(df: pd.DataFrame, scenario: Scenario) -> Dict[str, Any]:
    # Workaround for module expecting tuple keys: duplicate group
    df = df.copy()
    df["group2"] = df["group"].astype(np.int32)
    df["weight"] = 1.0
    selection = pd.Series(True, index=df.index)

    t0 = time.perf_counter()
    _, df_params = GroupByRegressor.make_parallel_fit(
        df,
        gb_columns=["group", "group2"],
        fit_columns=["y"],
        linear_columns=["x1", "x2"],
        median_columns=[],
        weights="weight",
        suffix="_fit",
        selection=selection,
        addPrediction=False,
        n_jobs=scenario.n_jobs,
        min_stat=[3, 4],
        sigmaCut=scenario.sigmaCut,
        fitter=scenario.fitter,
        batch_size="auto",
    )
    dt = time.perf_counter() - t0
    n_groups = int(df_params.shape[0])
    per_1k = dt / (n_groups / 1000.0) if n_groups else float("nan")
    return {
        "scenario": scenario.name,
        "config": {
            "n_jobs": scenario.n_jobs,
            "sigmaCut": scenario.sigmaCut,
            "fitter": scenario.fitter,
            "rows_per_group": scenario.rows_per_group,
            "n_groups": scenario.n_groups,
            "outlier_pct": scenario.outlier_pct,
            "outlier_mag": scenario.outlier_mag,
        },
        "result": {
            "total_sec": dt,
            "sec_per_1k_groups": per_1k,
            "n_groups_effective": n_groups,
        },
    }

def _make_df(s: Scenario, seed: int = 7) -> pd.DataFrame:
    n_rows = s.rows_per_group * s.n_groups
    if s.outlier_pct > 0.0:
        return create_data_with_outliers(n_rows, s.n_groups, outlier_pct=s.outlier_pct, outlier_magnitude=s.outlier_mag, seed=seed)
    else:
        return create_clean_data(n_rows, s.n_groups, seed=seed)

def _format_report(rows: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append("=" * 64); lines.append("BENCHMARK: GroupBy Regression"); lines.append("=" * 64)
    for r in rows:
        cfg = r["config"]; res = r["result"]
        lines.append("")
        lines.append(f"Scenario: {r['scenario']}")
        lines.append(f"  Config: n_jobs={cfg['n_jobs']}, sigmaCut={cfg['sigmaCut']}, fitter={cfg['fitter']}")
        lines.append(f"  Data: {cfg['rows_per_group']*cfg['n_groups']:,} rows, {res['n_groups_effective']:,} groups (target {cfg['n_groups']:,}), ~{cfg['rows_per_group']} rows/group")
        if cfg['outlier_pct']>0:
            lines.append(f"  Outliers: {cfg['outlier_pct']*100:.0f}% at {cfg['outlier_mag']}σ")
        lines.append(f"  Result: {res['total_sec']:.2f}s ({res['sec_per_1k_groups']:.2f}s per 1k groups)")
    lines.append("")
    return "\n".join(lines)

def run_suite(args) -> Tuple[List[Dict[str, Any]], str, str, str | None]:
    # Build scenarios
    scenarios: List[Scenario] = []

    # Baselines
    scenarios.append(Scenario("Clean Data, Serial", 0.0, 0.0, args.rows_per_group, args.groups, 1, args.fitter, args.sigmaCut))
    if not args.serial_only:
        scenarios.append(Scenario("Clean Data, Parallel", 0.0, 0.0, args.rows_per_group, args.groups, args.n_jobs, args.fitter, args.sigmaCut))

    # Outlier sets
    scenarios.append(Scenario("5% Outliers (3σ), Serial", 0.05, 3.0, args.rows_per_group, args.groups, 1, args.fitter, args.sigmaCut))
    scenarios.append(Scenario("10% Outliers (5σ), Serial", 0.10, 5.0, args.rows_per_group, args.groups, 1, args.fitter, args.sigmaCut))
    if not args.serial_only:
        scenarios.append(Scenario("10% Outliers (5σ), Parallel", 0.10, 5.0, args.rows_per_group, args.groups, args.n_jobs, args.fitter, args.sigmaCut))
    scenarios.append(Scenario("10% Outliers (10σ), Serial", 0.10, 10.0, args.rows_per_group, args.groups, 1, args.fitter, args.sigmaCut))

    # Prepare output
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run
    results: List[Dict[str, Any]] = []
    for s in scenarios:
        df = _make_df(s, seed=args.seed)
        results.append(_run_one(df, s))

    # Save
    txt_path = out_dir / "benchmark_report.txt"
    json_path = out_dir / "benchmark_results.json"
    with open(txt_path, "w") as f:
        f.write(_format_report(results))
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    csv_path = None
    if args.emit_csv:
        import csv
        csv_path = out_dir / "benchmark_results.csv"
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["scenario","n_jobs","sigmaCut","fitter","rows_per_group","n_groups","outlier_pct","outlier_mag","total_sec","sec_per_1k_groups","n_groups_effective"])
            for r in results:
                cfg = r["config"]; res = r["result"]
                w.writerow([r["scenario"], cfg["n_jobs"], cfg["sigmaCut"], cfg["fitter"], cfg["rows_per_group"], cfg["n_groups"], cfg["outlier_pct"], cfg["outlier_mag"], res["total_sec"], res["sec_per_1k_groups"], res["n_groups_effective"]])

    return results, str(txt_path), str(json_path), (str(csv_path) if csv_path else None)

def parse_args():
    p = argparse.ArgumentParser(description="GroupBy Regression Benchmark Suite")
    p.add_argument("--rows-per-group", type=int, default=5, help="Rows per group.")
    p.add_argument("--groups", type=int, default=10000, help="Number of groups.")
    p.add_argument("--n-jobs", type=int, default=4, help="Workers for parallel scenarios.")
    p.add_argument("--sigmaCut", type=float, default=5.0, help="Sigma cut for robust fitting.")
    p.add_argument("--fitter", type=str, default="ols", help="Fitter: ols|robust|huber depending on implementation.")
    p.add_argument("--seed", type=int, default=7, help="Random seed.")
    p.add_argument("--out", type=str, default="bench_out", help="Output directory.")
    p.add_argument("--emit-csv", action="store_true", help="Also emit CSV summary.")
    p.add_argument("--serial-only", action="store_true", help="Skip parallel scenarios.")
    p.add_argument("--quick", action="store_true", help="Small quick run: groups=200.")
    args = p.parse_args()
    if args.quick:
        args.groups = min(args.groups, 200)
    return args

def main():
    args = parse_args()
    results, txt_path, json_path, csv_path = run_suite(args)
    print(_format_report(results))
    print("\nSaved outputs:")
    print(" -", txt_path)
    print(" -", json_path)
    if csv_path: print(" -", csv_path)

if __name__ == "__main__":
    main()
