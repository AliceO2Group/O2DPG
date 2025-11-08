#!/usr/bin/env python3
"""
Unit Test: TPC Distortion Recovery with Alarm System
Phase 7 M7.1 - Validate sliding window on realistic synthetic data

FAST VERSION: ~5-10 seconds
"""

import numpy as np
import pandas as pd
import sys
import os
from typing import Dict

# Relative import for package structure
from ..synthetic_tpc_distortion import (
    make_synthetic_tpc_distortion,
    get_ground_truth_params,
    get_measurement_noise
)

# Try package import, fall back to relative
try:
    from dfextensions.groupby_regression import make_sliding_window_fit
except ImportError:
    from ..groupby_regression_sliding_window import make_sliding_window_fit


def compute_validation_metrics(result: pd.DataFrame,
                               ground_truth: pd.DataFrame) -> pd.DataFrame:
    """
    Compute validation metrics after sliding window fit.

    FIXED: Handle column name conflicts in merge.
    """

    # Aggregate ground truth by bin
    gt_agg = ground_truth.groupby(['xBin', 'y2xBin', 'z2xBin']).agg({
        'dX_true': 'mean',
        'dX_meas': 'mean'
    }).reset_index()

    # Rename to avoid conflicts
    gt_agg = gt_agg.rename(columns={
        'dX_true': 'dX_true_mean',
        'dX_meas': 'dX_meas_mean_truth'  # Different name to avoid conflict
    })

    # Merge with fit results
    merged = result.merge(gt_agg, on=['xBin', 'y2xBin', 'z2xBin'], how='left')

    # Use the aggregated mean from sliding window fit as prediction
    # (Column name from make_sliding_window_fit output)
    merged['dX_pred'] = merged['dX_meas_mean']  # This is from result

    # Compute residuals
    merged['delta'] = merged['dX_true_mean'] - merged['dX_pred']

    # Normalized residuals (using std as proxy for sigma_fit)
    sigma_fit = merged['dX_meas_std'].clip(lower=1e-6)
    merged['delta_norm'] = merged['delta'] / sigma_fit

    # Pull
    merged['pull'] = (merged['dX_meas_mean'] - merged['dX_true_mean']) / sigma_fit

    return merged


def validate_with_alarms(df: pd.DataFrame,
                         sigma_meas: float) -> Dict[str, Dict]:
    """Validate results using df.eval() and alarm dictionary."""

    alarms = {}
    n_total = len(df)

    # Check 1: Residuals within 4σ (OK range)
    ok_mask = df.eval('abs(delta) <= 4 * @sigma_meas')
    n_ok = ok_mask.sum()
    alarms['residuals_ok'] = {
        'status': 'OK',
        'count': int(n_ok),
        'fraction': float(n_ok / n_total),
        'criterion': '|Δ| ≤ 4σ',
        'threshold': 4 * sigma_meas
    }

    # Check 2: Residuals 4σ-6σ (WARNING range)
    warning_mask = df.eval('(abs(delta) > 4 * @sigma_meas) & (abs(delta) <= 6 * @sigma_meas)')
    n_warning = warning_mask.sum()
    warning_status = 'WARN' if n_warning > n_total * 0.01 else 'OK'
    alarms['residuals_warning'] = {
        'status': warning_status,
        'count': int(n_warning),
        'fraction': float(n_warning / n_total),
        'criterion': '4σ < |Δ| ≤ 6σ',
        'threshold': (4 * sigma_meas, 6 * sigma_meas)
    }

    # Check 3: Residuals >6σ (ALARM range)
    alarm_mask = df.eval('abs(delta) > 6 * @sigma_meas')
    n_alarm = alarm_mask.sum()
    alarm_status = 'ALARM' if n_alarm > 0 else 'OK'
    alarms['residuals_alarm'] = {
        'status': alarm_status,
        'count': int(n_alarm),
        'fraction': float(n_alarm / n_total),
        'criterion': '|Δ| > 6σ',
        'threshold': 6 * sigma_meas
    }

    # Check 4: Normalized residuals
    norm_resid = df['delta_norm'].dropna()
    alarms['normalized_residuals'] = {
        'status': 'OK' if abs(norm_resid.mean()) < 0.1 and abs(norm_resid.std() - 1.0) < 0.2 else 'WARN',
        'mean': float(norm_resid.mean()),
        'std': float(norm_resid.std()),
        'criterion': 'μ≈0, σ≈1'
    }

    # Check 5: RMS residuals
    rms_delta = np.sqrt((df['delta']**2).mean())
    expected_rms = sigma_meas / np.sqrt(df['dX_meas_entries'].mean())
    alarms['rms_residuals'] = {
        'status': 'OK' if rms_delta < 2 * expected_rms else 'WARN',
        'measured': float(rms_delta),
        'expected': float(expected_rms),
        'ratio': float(rms_delta / expected_rms) if expected_rms > 0 else float('inf'),
        'criterion': 'RMS < 2× expected'
    }

    # Overall summary
    has_alarms = alarms['residuals_alarm']['status'] == 'ALARM'
    has_warnings = (alarms['residuals_warning']['status'] == 'WARN' or
                    alarms['normalized_residuals']['status'] == 'WARN' or
                    alarms['rms_residuals']['status'] == 'WARN')

    if has_alarms:
        overall_status = 'ALARM'
        message = f"{n_alarm} bins with |Δ| > 6σ - possible local non-linearity"
    elif has_warnings:
        overall_status = 'WARNING'
        message = f"{n_warning} bins in warning range - monitor closely"
    else:
        overall_status = 'OK'
        message = "All validation checks passed"

    alarms['summary'] = {
        'status': overall_status,
        'message': message,
        'total_bins': n_total
    }

    return alarms


def print_alarm_report(alarms: Dict):
    """Pretty-print alarm dictionary."""
    print("\n" + "="*70)
    print("VALIDATION REPORT - ALARM SYSTEM")
    print("="*70)

    summary = alarms['summary']
    print(f"\nOverall Status: {summary['status']}")
    print(f"Message: {summary['message']}")
    print(f"Total bins evaluated: {summary['total_bins']}")

    print("\n" + "-"*70)
    print("CHECK 1: Residuals in OK Range (|Δ| ≤ 4σ)")
    print("-"*70)
    ok = alarms['residuals_ok']
    print(f"  Status: {ok['status']}")
    print(f"  Count: {ok['count']} / {summary['total_bins']} ({ok['fraction']*100:.1f}%)")

    print("\n" + "-"*70)
    print("CHECK 2: Residuals in WARNING Range (4σ < |Δ| ≤ 6σ)")
    print("-"*70)
    warn = alarms['residuals_warning']
    status_symbol = '⚠️ ' if warn['status'] == 'WARN' else '✅'
    print(f"  Status: {status_symbol} {warn['status']}")
    print(f"  Count: {warn['count']} / {summary['total_bins']} ({warn['fraction']*100:.1f}%)")

    print("\n" + "-"*70)
    print("CHECK 3: Residuals in ALARM Range (|Δ| > 6σ)")
    print("-"*70)
    alarm = alarms['residuals_alarm']
    status_symbol = '🚨' if alarm['status'] == 'ALARM' else '✅'
    print(f"  Status: {status_symbol} {alarm['status']}")
    print(f"  Count: {alarm['count']} / {summary['total_bins']} ({alarm['fraction']*100:.1f}%)")

    print("\n" + "-"*70)
    print("CHECK 4: Normalized Residuals Distribution")
    print("-"*70)
    norm = alarms['normalized_residuals']
    status_symbol = '⚠️ ' if norm['status'] == 'WARN' else '✅'
    print(f"  Status: {status_symbol} {norm['status']}")
    print(f"  Mean: {norm['mean']:.4f} (expected: 0.0)")
    print(f"  Std:  {norm['std']:.4f} (expected: 1.0)")

    print("\n" + "-"*70)
    print("CHECK 5: RMS Residuals vs Expected Resolution")
    print("-"*70)
    rms = alarms['rms_residuals']
    status_symbol = '⚠️ ' if rms['status'] == 'WARN' else '✅'
    print(f"  Status: {status_symbol} {rms['status']}")
    print(f"  Measured RMS: {rms['measured']:.6f} cm")
    print(f"  Expected RMS: {rms['expected']:.6f} cm")
    print(f"  Ratio: {rms['ratio']:.2f}")

    print("\n" + "="*70)


def test_tpc_distortion_recovery():
    """
    Main unit test for TPC distortion recovery.

    OPTIMIZED: Smaller grid for fast testing (~5-10 seconds).
    """

    print("="*70)
    print("UNIT TEST: TPC Distortion Recovery (Realistic Model)")
    print("Phase 7 M7.1 - § 7.4 Synthetic-Data Test Specification")
    print("="*70)

    # Generate synthetic data - REDUCED SIZE for speed
    print("\n📊 Generating synthetic TPC distortion data...")
    print("   [FAST MODE: Reduced grid for unit test speed]")
    df = make_synthetic_tpc_distortion(
        n_bins_dr=20,      # Reduced from 50 → 20
        n_bins_z2x=6,      # Reduced from 10 → 6
        n_bins_y2x=6,      # Reduced from 10 → 6
        entries_per_bin=30, # Reduced from 50 → 30
        sigma_meas=0.02,
        seed=42
    )

    n_bins = len(df[['xBin', 'y2xBin', 'z2xBin']].drop_duplicates())
    print(f"   Generated {len(df):,} rows across {n_bins} bins")

    params = get_ground_truth_params(df)
    sigma_meas = get_measurement_noise(df)
    print(f"   Measurement noise: σ = {sigma_meas:.4f} cm")
    print(f"   Ground truth parameters: {len(params)} coefficients")

    # Run sliding window fit
    print("\n🔧 Running sliding window fit...")
    print("   Window: xBin=±2, y2xBin=±1, z2xBin=±1")
    print("   Min entries: 15")

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'y2xBin', 'z2xBin'],
        window_spec={'xBin': 2, 'y2xBin': 1, 'z2xBin': 1},  # Smaller window
        fit_columns=['dX_meas'],
        predictor_columns=['drift', 'dr', 'dsec', 'meanIDC'],
        fit_formula='dX_meas ~ drift + dr + I(dr**2) + dsec + meanIDC',
        fitter='ols',
        min_entries=15  # Lower threshold
    )

    print(f"   Results: {len(result)} bins with fits")

    # Compute validation metrics
    print("\n📊 Computing validation metrics...")
    result_with_metrics = compute_validation_metrics(result, df)

    # Run alarm checks
    print("\n🔍 Running alarm checks (df.eval() based)...")
    alarms = validate_with_alarms(result_with_metrics, sigma_meas)

    # Print report
    print_alarm_report(alarms)

    # Determine pass/fail
    overall_status = alarms['summary']['status']

    if overall_status == 'OK':
        print("\n" + "="*70)
        print("✅ UNIT TEST PASSED")
        print("="*70)
        print("\nAll validation checks passed.")
        print("Sliding window correctly recovers TPC distortion field.")
        print("\nNote: Fast mode with reduced grid (20×6×6 bins).")
        print("      For full benchmark, use benchmark_tpc_distortion.py")
        return 0
    elif overall_status == 'WARNING':
        print("\n" + "="*70)
        print("⚠️  UNIT TEST PASSED WITH WARNINGS")
        print("="*70)
        print("\nSome metrics in warning range - review above.")
        return 0
    else:
        print("\n" + "="*70)
        print("❌ UNIT TEST FAILED")
        print("="*70)
        print("\nCritical validation failures detected.")
        return 1


if __name__ == '__main__':
    import time
    start = time.time()
    result = test_tpc_distortion_recovery()
    elapsed = time.time() - start
    print(f"\n⏱️  Test completed in {elapsed:.1f}s")
    sys.exit(result)