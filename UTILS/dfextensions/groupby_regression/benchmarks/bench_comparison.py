#!/usr/bin/env python3
"""
Comparison benchmark: Robust vs Optimized implementations.

Tier-A (CI-friendly): Quick comparison on small datasets (< 5 min)
- 3 scenarios: tiny/small/medium
- Writes latest/ results
- Appends to history.csv

Usage:
    python bench_comparison.py
    python bench_comparison.py --scenarios all  # More scenarios
"""

import argparse
import time
import csv
import sys
from pathlib import Path
from datetime import datetime
import socket

import numpy as np
import pandas as pd

# Handle imports for both direct execution and module import
try:
    # Try package-relative import first (when run as module)
    from ..groupby_regression import GroupByRegressor
    from ..groupby_regression_optimized import (
        make_parallel_fit_v2,
        make_parallel_fit_v4,
    )
except ImportError:
    # Fall back to adding parent to path (when run as script)
    script_dir = Path(__file__).parent
    package_dir = script_dir.parent
    sys.path.insert(0, str(package_dir))
    
    from groupby_regression import GroupByRegressor
    from groupby_regression_optimized import (
        make_parallel_fit_v2,
        make_parallel_fit_v4,
    )


def create_benchmark_data(n_groups, rows_per_group, seed=42):
    """
    Create synthetic test data matching TPC structure.
    
    Returns:
        df: DataFrame with 3D groupby and 3 targets
        info: Dataset metadata
    """
    rng = np.random.default_rng(seed)
    N = n_groups * rows_per_group
    
    # Build 3D grid (approximate cube root for balanced dimensions)
    x_bins = int(np.ceil(n_groups ** (1/3)))
    y_bins = int(np.ceil((n_groups / x_bins) ** 0.5))
    z_bins = int(np.ceil(n_groups / (x_bins * y_bins)))
    
    # Coordinate arrays
    xBin = np.repeat(np.arange(x_bins), y_bins*z_bins*rows_per_group)[:N]
    y2xBin = np.tile(np.repeat(np.arange(y_bins), z_bins*rows_per_group), x_bins)[:N]
    z2xBin = np.tile(np.repeat(np.arange(z_bins), rows_per_group), x_bins*y_bins)[:N]
    
    # Predictor and targets
    deltaIDC = rng.normal(size=N)
    dX = 2.0 + 1.1*deltaIDC
    dY = -1.0 + 0.8*deltaIDC
    dZ = 0.5 - 0.3*deltaIDC
    
    df = pd.DataFrame({
        'xBin': xBin,
        'y2xBin': y2xBin,
        'z2xBin': z2xBin,
        'deltaIDC': deltaIDC,
        'dX': dX,
        'dY': dY,
        'dZ': dZ,
        'weight': np.ones(N),
    })
    
    info = {
        'n_groups_target': n_groups,
        'rows_per_group': rows_per_group,
        'n_rows': N,
        'grid': (x_bins, y_bins, z_bins)
    }
    
    return df, info


def run_engine(engine_name, df, gb_cols, sel, n_jobs=1):
    """
    Run one engine and return timing + results.
    
    Returns:
        dict with keys: time, per_1k, n_groups, dfGB
    """
    if engine_name == 'robust':
        t0 = time.perf_counter()
        _, dfGB = GroupByRegressor.make_parallel_fit(
            df, gb_columns=gb_cols,
            fit_columns=['dX', 'dY', 'dZ'],
            linear_columns=['deltaIDC'],
            median_columns=[],
            weights='weight',
            suffix='_eng',
            selection=sel,
            n_jobs=n_jobs,
            min_stat=[3, 3, 3]
        )
        elapsed = time.perf_counter() - t0
    
    elif engine_name == 'v2':
        t0 = time.perf_counter()
        _, dfGB = make_parallel_fit_v2(
            df, gb_columns=gb_cols,
            fit_columns=['dX', 'dY', 'dZ'],
            linear_columns=['deltaIDC'],
            median_columns=[],
            weights='weight',
            suffix='_eng',
            selection=sel,
            n_jobs=n_jobs,
            min_stat=[3, 3, 3]
        )
        elapsed = time.perf_counter() - t0
    
    elif engine_name == 'v4':
        t0 = time.perf_counter()
        _, dfGB = make_parallel_fit_v4(
            df=df, gb_columns=gb_cols,
            fit_columns=['dX', 'dY', 'dZ'],
            linear_columns=['deltaIDC'],
            median_columns=[],
            weights='weight',
            suffix='_eng',
            selection=sel,
            min_stat=3
        )
        elapsed = time.perf_counter() - t0
    
    else:
        raise ValueError(f"Unknown engine: {engine_name}")
    
    n_groups = len(dfGB)
    per_1k = elapsed / (n_groups / 1000) if n_groups > 0 else float('inf')
    
    return {
        'time': elapsed,
        'per_1k': per_1k,
        'n_groups': n_groups,
        'dfGB': dfGB
    }


def compute_agreement(dfGB_a, dfGB_b, gb_cols, targets, suffix='_eng'):
    """
    Compute max absolute differences between two result sets.
    
    Args:
        suffix: The suffix used when fitting (e.g., '_eng')
    
    Returns:
        dict with max_abs_diff for slopes and intercepts
    """
    merged = dfGB_a.merge(dfGB_b, on=gb_cols, suffixes=('_a', '_b'))
    
    if len(merged) == 0:
        return {f'{t}_{x}': np.nan for t in targets for x in ['slope', 'intercept']}
    
    diffs = {}
    for target in targets:
        # Slopes - account for suffix from fitting
        slope_col_a = f'{target}_slope_deltaIDC{suffix}_a'
        slope_col_b = f'{target}_slope_deltaIDC{suffix}_b'
        
        slope_diff = np.abs(
            merged[slope_col_a] - merged[slope_col_b]
        )
        
        # Intercepts - account for suffix from fitting
        intercept_col_a = f'{target}_intercept{suffix}_a'
        intercept_col_b = f'{target}_intercept{suffix}_b'
        
        intercept_diff = np.abs(
            merged[intercept_col_a] - merged[intercept_col_b]
        )
        
        diffs[f'{target}_slope'] = slope_diff.max()
        diffs[f'{target}_intercept'] = intercept_diff.max()
    
    return diffs


def run_scenario(name, n_groups, rows_per_group, seed=42):
    """
    Run one benchmark scenario across all engines.
    
    Returns:
        dict with scenario info and results per engine
    """
    print(f"\n{'='*70}")
    print(f"Scenario: {name}")
    print(f"Dataset: {n_groups} groups × {rows_per_group} rows = {n_groups*rows_per_group:,} total")
    print(f"{'='*70}")
    
    # Create data
    df, info = create_benchmark_data(n_groups, rows_per_group, seed)
    gb_cols = ['xBin', 'y2xBin', 'z2xBin']
    sel = pd.Series(True, index=df.index)
    
    results = {}
    
    # Run each engine
    for engine_name, n_jobs in [('robust', 1), ('v2', 4), ('v4', 1)]:
        print(f"Running {engine_name}...", end=' ', flush=True)
        res = run_engine(engine_name, df, gb_cols, sel, n_jobs)
        results[engine_name] = res
        print(f"{res['time']:.2f}s ({res['per_1k']:.2f}s/1k, {res['n_groups']} groups)")
    
    # Compute agreement
    print("\nNumerical agreement:")
    diffs_v2 = compute_agreement(
        results['robust']['dfGB'],
        results['v2']['dfGB'],
        gb_cols,
        ['dX', 'dY', 'dZ']
    )
    diffs_v4 = compute_agreement(
        results['robust']['dfGB'],
        results['v4']['dfGB'],
        gb_cols,
        ['dX', 'dY', 'dZ']
    )
    
    max_slope_v2 = max(v for k, v in diffs_v2.items() if 'slope' in k and not np.isnan(v))
    max_slope_v4 = max(v for k, v in diffs_v4.items() if 'slope' in k and not np.isnan(v))
    
    print(f"  robust vs v2: slope max diff = {max_slope_v2:.2e}")
    print(f"  robust vs v4: slope max diff = {max_slope_v4:.2e}")
    
    # Speedups
    print("\nSpeedup vs robust:")
    speedup_v2 = results['robust']['time']/results['v2']['time']
    speedup_v4 = results['robust']['time']/results['v4']['time']
    print(f"  v2: {speedup_v2:.1f}×")
    print(f"  v4: {speedup_v4:.1f}×")
    
    return {
        'scenario': name,
        'info': info,
        'results': results,
        'agreement': {'v2': diffs_v2, 'v4': diffs_v4},
        'speedups': {'v2': speedup_v2, 'v4': speedup_v4}
    }


def write_results(scenario_results, output_dir):
    """
    Write results to latest/ directory.
    
    Files created:
    - comparison_report.txt: Human-readable summary
    - comparison_results.csv: Machine-readable data
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write text report
    txt_path = output_dir / 'comparison_report.txt'
    with open(txt_path, 'w') as f:
        f.write("GroupBy Regression: Engine Comparison\n")
        f.write("="*70 + "\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Host: {socket.gethostname()}\n")
        f.write("\n")
        
        for sr in scenario_results:
            f.write(f"\nScenario: {sr['scenario']}\n")
            f.write(f"Dataset: {sr['info']['n_groups_target']} groups × "
                   f"{sr['info']['rows_per_group']} rows\n")
            f.write("-" * 70 + "\n")
            
            for engine in ['robust', 'v2', 'v4']:
                res = sr['results'][engine]
                f.write(f"{engine:8s}: {res['time']:6.2f}s ({res['per_1k']:6.2f}s/1k) "
                       f"[{res['n_groups']} groups]\n")
            
            f.write(f"\nSpeedup vs robust:\n")
            f.write(f"  v2: {sr['speedups']['v2']:.1f}×\n")
            f.write(f"  v4: {sr['speedups']['v4']:.1f}×\n")
    
    print(f"\n✅ Report written: {txt_path}")
    
    # Write CSV
    csv_path = output_dir / 'comparison_results.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'scenario', 'engine', 'n_groups', 'rows_per_group',
            'duration_s', 'per_1k_s', 'n_groups_actual', 'speedup'
        ])
        
        for sr in scenario_results:
            for engine in ['robust', 'v2', 'v4']:
                res = sr['results'][engine]
                speedup = sr['speedups'].get(engine, 1.0) if engine != 'robust' else 1.0
                writer.writerow([
                    sr['scenario'],
                    engine,
                    sr['info']['n_groups_target'],
                    sr['info']['rows_per_group'],
                    f"{res['time']:.3f}",
                    f"{res['per_1k']:.3f}",
                    res['n_groups'],
                    f"{speedup:.2f}"
                ])
    
    print(f"✅ CSV written: {csv_path}")


def append_to_history(scenario_results, history_file, commit_hash=None):
    """
    Append results to history.csv for trend tracking.
    """
    history_file = Path(history_file)
    
    # Create if doesn't exist
    if not history_file.exists():
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(history_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'date', 'host', 'commit', 'scenario', 'engine',
                'n_groups', 'rows_per_group', 'duration_s', 'per_1k_s',
                'speedup', 'notes'
            ])
    
    # Append results
    with open(history_file, 'a', newline='') as f:
        writer = csv.writer(f)
        for sr in scenario_results:
            for engine in ['robust', 'v2', 'v4']:
                res = sr['results'][engine]
                speedup = sr['speedups'].get(engine, 1.0) if engine != 'robust' else 1.0
                
                writer.writerow([
                    datetime.now().isoformat(),
                    socket.gethostname(),
                    commit_hash or 'unknown',
                    sr['scenario'],
                    engine,
                    sr['info']['n_groups_target'],
                    sr['info']['rows_per_group'],
                    f"{res['time']:.3f}",
                    f"{res['per_1k']:.3f}",
                    f"{speedup:.2f}",
                    ''
                ])
    
    print(f"✅ History updated: {history_file}")


def main():
    parser = argparse.ArgumentParser(description="Compare robust vs optimized engines")
    parser.add_argument('--scenarios', choices=['quick', 'all'], default='quick',
                       help="Scenario set: quick (3) or all (5)")
    parser.add_argument('--output', default='../benchmark_results/latest',
                       help="Output directory")
    parser.add_argument('--commit', help="Git commit hash (for history tracking)")
    args = parser.parse_args()
    
    # Define scenarios
    if args.scenarios == 'quick':
        scenarios = [
            ("Tiny (100×5)", 100, 5),
            ("Small (1k×5)", 1000, 5),
            ("Medium (5k×5)", 5000, 5),
        ]
    else:  # all
        scenarios = [
            ("Tiny (100×5)", 100, 5),
            ("Small (1k×5)", 1000, 5),
            ("Medium (5k×5)", 5000, 5),
            ("Large (10k×5)", 10000, 5),
            ("XLarge (20k×5)", 20000, 5),
        ]
    
    # Run all scenarios
    all_results = []
    for name, n_groups, rows_per in scenarios:
        sr = run_scenario(name, n_groups, rows_per)
        all_results.append(sr)
    
    # Write results
    write_results(all_results, args.output)
    
    # Append to history
    history_file = Path(args.output).parent / 'history.csv'
    append_to_history(all_results, history_file, args.commit)
    
    print(f"\n{'='*70}")
    print("✅ Comparison complete!")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    main()
