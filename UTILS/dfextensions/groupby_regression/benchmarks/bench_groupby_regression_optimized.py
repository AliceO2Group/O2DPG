#!/usr/bin/env python3
"""
bench_groupby_regression_optimized.py — Optimized-only benchmark for GroupBy Regression

Engines covered:
  - v2 (loky / process-based)
  - v3 (threads)
  - v4 (Numba JIT kernel)

Notes
-----
* Robust (slow) implementation is intentionally omitted.
* Includes Numba warm-up so compilation time is excluded from timings.
* Captures environment info (versions, CPU, threads) at the top of the report.
* Produces three outputs in the output directory (default: benchmarks/bench_out):
    - benchmark_report.txt     (readable report)
    - benchmark_results.json   (structured results)
    - benchmark_summary.csv    (CSV with fixed schema)

Usage
-----
  Quick mode (≤ 2k groups, < 5 min):
      python bench_groupby_regression_optimized.py --quick

  Full mode (≤ 100k groups, < 30 min; assumes fast machine):
      python bench_groupby_regression_optimized.py --full

  Custom output dir:
      python bench_groupby_regression_optimized.py --quick --out benchmarks/bench_out

CSV Schema (locked)
-------------------
run_id, timestamp, mode, engine, scenario_id, n_groups, rows_per_group,
outlier_rate, outlier_sigma, n_jobs, fitter, sigmaCut, elapsed_s,
groups_per_s, rows_total, commit, python, numpy, pandas, numba, sklearn, joblib, cpu
"""

from __future__ import annotations
import argparse, json, os, sys, time, uuid, platform, subprocess, inspect
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd

# ---------------- Environment stamp ----------------
def _safe_version(modname: str) -> str:
    try:
        mod = __import__(modname)
        return getattr(mod, "__version__", "unknown")
    except Exception:
        return "missing"

def get_environment_info() -> Dict[str, Any]:
    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "numpy": _safe_version("numpy"),
        "pandas": _safe_version("pandas"),
        "numba": _safe_version("numba"),
        "sklearn": _safe_version("sklearn"),
        "joblib": _safe_version("joblib"),
    }
    try:
        if sys.platform == "linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        info["cpu"] = line.split(":", 1)[1].strip()
                        break
        elif sys.platform == "darwin":
            brand = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
            info["cpu"] = brand
    except Exception:
        pass
    if "cpu" not in info:
        info["cpu"] = info.get("processor") or "unknown"
    return info

# ---------------- Imports (follow bench_comparison.py pattern) ----------------
def _import_implementations():
    try:
        from groupby_regression_optimized import (
            make_parallel_fit_v2, make_parallel_fit_v3, make_parallel_fit_v4
        )
        return ("package", make_parallel_fit_v2, make_parallel_fit_v3, make_parallel_fit_v4)
    except Exception:
        here = Path(__file__).resolve()
        root = here.parent.parent
        sys.path.insert(0, str(root))
        from groupby_regression_optimized import (
            make_parallel_fit_v2, make_parallel_fit_v3, make_parallel_fit_v4
        )
        return ("local", make_parallel_fit_v2, make_parallel_fit_v3, make_parallel_fit_v4)

# ---------------- Synthetic data ----------------
def _make_synthetic_data(n_groups: int, rows_per_group: int,
                         outlier_rate: float = 0.0, outlier_sigma: float = 0.0, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    g0 = np.repeat(np.arange(n_groups, dtype=np.int32), rows_per_group)
    g1 = rng.integers(0, 10, size=n_groups*rows_per_group, dtype=np.int32)
    g2 = rng.integers(0, 5, size=n_groups*rows_per_group, dtype=np.int32)

    x = rng.normal(0, 1.0, size=n_groups*rows_per_group).astype(np.float64)

    slope = rng.normal(1.5, 0.2, size=n_groups).astype(np.float64)
    intercept = rng.normal(0.0, 0.5, size=n_groups).astype(np.float64)

    grp = g0
    y_clean  = intercept[grp] + slope[grp] * x + rng.normal(0, 0.5, size=x.size)
    y2_clean = (intercept[grp] - 0.2) + (slope[grp] * 0.5) * x + rng.normal(0, 0.5, size=x.size)

    y, y2 = y_clean.copy(), y2_clean.copy()

    if outlier_rate > 0 and outlier_sigma > 0:
        mask = rng.random(x.size) < outlier_rate
        y[mask]  += rng.normal(0, outlier_sigma, size=mask.sum())
        y2[mask] += rng.normal(0, outlier_sigma, size=mask.sum())

    df = pd.DataFrame({
        "g0": g0, "g1": g1, "g2": g2,
        "x": x, "y1": y, "y2": y2,
        "wFit": np.ones_like(x, dtype=np.float64),
    })
    return df

# ---------------- Signature-aware engine wrapper ----------------
_ALIAS_MAP = {
    # canonical -> possible alternates
    "gb_columns": ["gb_columns", "gbColumns", "groupby_columns"],
    "fit_columns": ["fit_columns", "fitColumns", "targets"],
    "linear_columns": ["linear_columns", "linearColumns", "features"],
    "median_columns": ["median_columns", "medianColumns"],
    "weights": ["weights", "weight_column"],
    "suffix": ["suffix"],
    "selection": ["selection", "mask"],
    "addPrediction": ["addPrediction", "add_prediction"],
    "n_jobs": ["n_jobs", "nThreads", "n_workers"],
    "min_stat": ["min_stat", "minStat"],
    "fitter": ["fitter"],
    "sigmaCut": ["sigmaCut", "sigma_cut"],
    "batch_size": ["batch_size", "batchSize"],
}

def _normalize_kwargs_for_signature(fun, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Map/limit kwargs to what `fun` actually accepts."""
    sig = inspect.signature(fun)
    params = set(sig.parameters.keys())
    out: Dict[str, Any] = {}

    # Build reverse alias map keyed by actual parameter names present
    alias_candidates = {}
    for canonical, alts in _ALIAS_MAP.items():
        for alt in alts:
            alias_candidates[alt] = canonical

    # First pass: if kw already matches a param, keep
    for k, v in kwargs.items():
        if k in params:
            out[k] = v

    # Second pass: try alias mapping for missing ones
    for k, v in kwargs.items():
        if k in out:
            continue
        # map k -> canonical, then see if any alias for canonical matches a real param
        canonical = alias_candidates.get(k, None)
        if not canonical:
            continue
        for alt in _ALIAS_MAP.get(canonical, []):
            if alt in params:
                out[alt] = v
                break

    # Special case: if neither 'addPrediction' nor 'add_prediction' present, but one is required
    # we rely on 'params' to decide; otherwise ignore.
    return out

def _call_engine(fun, df: pd.DataFrame, **kwargs):
    filt = _normalize_kwargs_for_signature(fun, kwargs)
    return fun(df, **filt)

# ---------------- Numba warm-up ----------------
def warm_up_numba(make_parallel_fit_v4, *, verbose: bool = True) -> None:
    df = _make_synthetic_data(n_groups=10, rows_per_group=5, seed=123)
    try:
        _call_engine(
            make_parallel_fit_v4, df,
            gb_columns=["g0","g1","g2"],
            fit_columns=["y1","y2"],
            linear_columns=["x"],
            median_columns=[],
            weights="wFit",
            suffix="_warm",
            selection=pd.Series(np.ones(len(df), dtype=bool)),
            addPrediction=False,
            n_jobs=1,            # dropped automatically if v4 doesn't accept it
            min_stat=[3,3],
            fitter="ols",
            sigmaCut=100,
            batch_size="auto"
        )
        if verbose:
            print("[warm-up] Numba v4 compilation done.")
    except Exception as e:
        if verbose:
            print(f"[warm-up] Skipped (v4 not available or failed): {e}")

# ---------------- Scenarios ----------------
@dataclass
class Scenario:
    scenario_id: str
    n_groups: int
    rows_per_group: int
    outlier_rate: float
    outlier_sigma: float
    n_jobs: int
    sigmaCut: float
    fitter: str = "ols"

def quick_scenarios() -> List[Scenario]:
    return [
        Scenario("clean_serial_small",   200, 5,  0.0, 0.0, 1, 100),
        Scenario("clean_parallel_small", 200, 5,  0.0, 0.0, 8, 100),
        Scenario("clean_serial_med",     400, 20, 0.0, 0.0, 1, 100),
        Scenario("clean_parallel_med",   400, 20, 0.0, 0.0, 8, 100),
        Scenario("out3pct_3sigma",       400, 20, 0.03, 3.0, 8, 5),
        Scenario("out10pct_5sigma",      600, 5,  0.10, 5.0, 8, 5),
        Scenario("out10pct_10sigma",     600, 5,  0.10,10.0, 8, 5),
    ]

def full_scenarios() -> List[Scenario]:
    return [
        Scenario("clean_serial_2k5",       2500, 5, 0.0, 0.0, 1, 100),
        Scenario("clean_parallel_2k5",     2500, 5, 0.0, 0.0,16, 100),
        Scenario("clean_serial_5k20",      5000,20, 0.0, 0.0, 1, 100),
        Scenario("clean_parallel_5k20",    5000,20, 0.0, 0.0,16, 100),
        Scenario("out5pct_3sigma_5k20",    5000,20, 0.05,3.0,16, 5),
        Scenario("out10pct_5sigma_10k5",  10000, 5, 0.10,5.0,16, 5),
        Scenario("out10pct_10sigma_10k5", 10000, 5, 0.10,10.0,16, 5),
        Scenario("clean_parallel_20k5",   20000, 5, 0.0, 0.0,24, 100),
        Scenario("clean_parallel_30k5",   30000, 5, 0.0, 0.0,24, 100),
    ]

# ---------------- Core runner ----------------
def _run_once(engine_name: str, fun, df: pd.DataFrame, sc: Scenario) -> Tuple[float, Dict[str, Any]]:
    t0 = time.perf_counter()
    df_out, dfGB = _call_engine(
        fun, df,
        gb_columns=["g0","g1","g2"],
        fit_columns=["y1","y2"],
        linear_columns=["x"],
        median_columns=[],
        weights="wFit",
        suffix="_b",
        selection=pd.Series(np.ones(len(df), dtype=bool)),
        addPrediction=False,
        n_jobs=sc.n_jobs,      # dropped for engines that don't accept it
        min_stat=[3,3],
        fitter=sc.fitter,
        sigmaCut=sc.sigmaCut,
        batch_size="auto"
    )
    elapsed = time.perf_counter() - t0

    rows_total = len(df)
    groups_per_s = sc.n_groups / elapsed if elapsed > 0 else float("inf")
    meta = {
        "elapsed_s": elapsed,
        "rows_total": rows_total,
        "groups_per_s": groups_per_s,
        "df_out_shape": tuple(df_out.shape) if hasattr(df_out, "shape") else None,
        "dfGB_shape": tuple(dfGB.shape) if hasattr(dfGB, "shape") else None,
    }
    return elapsed, meta

# ---------------- Reporting ----------------
def _format_report_header(env: Dict[str, Any]) -> str:
    lines = []
    lines.append("="*72)
    lines.append("Optimized GroupBy Regression Benchmark")
    lines.append("="*72)
    lines.append(f"Python {env.get('python')} | NumPy {env.get('numpy')} | Pandas {env.get('pandas')} | "
                 f"Numba {env.get('numba')} | sklearn {env.get('sklearn')} | joblib {env.get('joblib')}")
    lines.append(f"CPU: {env.get('cpu')} | Cores: {env.get('cpu_count')} | Platform: {env.get('platform')}")
    lines.append("")
    return "\n".join(lines)

def _format_scenario_line(mode: str, engine: str, sc: Scenario, result: Dict[str, Any]) -> str:
    return (f"[{mode}] {engine:>3} | {sc.scenario_id:<24} "
            f"groups={sc.n_groups:>6}, rows/group={sc.rows_per_group:>4}, "
            f"outliers={sc.outlier_rate:>4.0%}@{sc.outlier_sigma:<4.1f}σ, "
            f"n_jobs={sc.n_jobs:<3} | time={result['elapsed_s']:.3f}s, "
            f"speed={result['groups_per_s']:.1f} groups/s")

def write_txt_report(path: Path, env: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [_format_report_header(env)]
    for rec in records:
        lines.append(_format_scenario_line(rec["mode"], rec["engine"], rec["scenario"], rec["result"]))
    with open(path, "w") as f:
        f.write("\n".join(lines))

def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id","timestamp","mode","engine","scenario_id","n_groups","rows_per_group",
        "outlier_rate","outlier_sigma","n_jobs","fitter","sigmaCut","elapsed_s",
        "groups_per_s","rows_total","commit","python","numpy","pandas","numba","sklearn","joblib","cpu"
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

# ---------------- CLI / main ----------------
def parse_args():
    p = argparse.ArgumentParser(description="Optimized-only GroupBy Regression benchmark (v2/v3/v4).")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--quick", action="store_true", help="Run quick suite (≤ ~2k groups, < 5 min).")
    g.add_argument("--full", action="store_true", help="Run full suite (≤ ~100k groups, < 30 min).")
    p.add_argument("--out", type=str, default=str(Path(__file__).resolve().parent / "bench_out"),
                   help="Output directory (default: benchmarks/bench_out)")
    p.add_argument("--commit", type=str, default=os.environ.get("GIT_COMMIT", ""),
                   help="Optional commit SHA or label embedded in artifacts.")
    return p.parse_args()

def main():
    args = parse_args()

    source, v2_raw, v3_raw, v4_raw = _import_implementations()
    # Wrap engines with signature-aware caller to guarantee safe kwargs handling.
    def wrap(fun):
        return lambda df, **kw: _call_engine(fun, df, **kw)
    v2, v3, v4 = wrap(v2_raw), wrap(v3_raw), wrap(v4_raw)

    env = get_environment_info()
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    run_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    mode = "full" if args.full else "quick"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Warm-up JIT (filtered call)
    warm_up_numba(v4_raw, verbose=True)

    scenarios = full_scenarios() if args.full else quick_scenarios()
    engines = [("v2", v2), ("v3", v3), ("v4", v4)]

    records, csv_rows = [], []
    json_dump = {"run_id": run_id, "timestamp": ts, "mode": mode, "env": env, "source": source, "results": []}

    for sc in scenarios:
        df = _make_synthetic_data(
            n_groups=sc.n_groups,
            rows_per_group=sc.rows_per_group,
            outlier_rate=sc.outlier_rate,
            outlier_sigma=sc.outlier_sigma,
            seed=abs(hash(sc.scenario_id)) % (2**31-1)
        )
        for eng_name, fun in engines:
            elapsed, meta = _run_once(eng_name, fun, df, sc)
            records.append({"mode": mode, "engine": eng_name, "scenario": sc, "result": meta})
            json_dump["results"].append({"engine": eng_name, "scenario": asdict(sc), "metrics": meta})
            csv_rows.append({
                "run_id": run_id, "timestamp": ts, "mode": mode, "engine": eng_name,
                "scenario_id": sc.scenario_id, "n_groups": sc.n_groups, "rows_per_group": sc.rows_per_group,
                "outlier_rate": sc.outlier_rate, "outlier_sigma": sc.outlier_sigma, "n_jobs": sc.n_jobs,
                "fitter": sc.fitter, "sigmaCut": sc.sigmaCut, "elapsed_s": meta["elapsed_s"],
                "groups_per_s": meta["groups_per_s"], "rows_total": meta["rows_total"],
                "commit": args.commit, "python": env.get("python",""), "numpy": env.get("numpy",""),
                "pandas": env.get("pandas",""), "numba": env.get("numba",""), "sklearn": env.get("sklearn",""),
                "joblib": env.get("joblib",""), "cpu": env.get("cpu",""),
            })

    txt_path = out_dir / "benchmark_report.txt"
    json_path = out_dir / "benchmark_results.json"
    csv_path = out_dir / "benchmark_summary.csv"
    write_txt_report(txt_path, env, records)
    write_json(json_path, json_dump)
    write_csv(csv_path, csv_rows)

    print(_format_report_header(env))
    for rec in records:
        print(_format_scenario_line(rec["mode"], rec["engine"], rec["scenario"], rec["result"]))
    print("\nSaved outputs:")
    print(" -", txt_path)
    print(" -", json_path)
    print(" -", csv_path)

if __name__ == "__main__":
    main()
