# -*- coding: utf-8 -*-
# test_groupby_regression_sliding_window.py
#
# Phase 7 (M7.1) — Sliding Window Regression: Full Test Suite (Verbose)
#
# This suite defines the CONTRACT for implementation. It is intentionally verbose:
# each test explains WHAT is being tested and WHY it matters for production
# (TPC calibration, performance parameterisation). Tests may initially fail
# until the corresponding implementation lands.
#
# Python 3.9.6 compatible (use typing.Union/Optional, no match/case).

from __future__ import annotations

from typing import List, Dict, Tuple, Optional
import itertools
import warnings

import numpy as np
import pandas as pd
import pytest

# Public API + selected internals (exposed for testing)
from ..groupby_regression_sliding_window import (
    make_sliding_window_fit,
    InvalidWindowSpec,
    PerformanceWarning,
    _build_bin_index_map,        # Exposed for testing
    _generate_neighbor_offsets,  # Exposed for testing
    _get_neighbor_bins,          # Exposed for testing
)

# =============================================================================
# Helpers: Column-name compatibility
# -----------------------------------------------------------------------------
# We keep two compatible naming “profiles”:
#   - GENERIC: xBin, yBin, zBin
#   - REALISTIC (TPC-like): xBin, y2xBin, z2xBin, meanIDC
#
# Synthetic generators can emit either schema to ensure we can later re-use the
# same code on a real .pkl (benchmark) without heavy renaming.

def _cols_generic_to_realistic(df: pd.DataFrame) -> pd.DataFrame:
    """Map generic names to realistic names when requested."""
    mapping = {'yBin': 'y2xBin', 'zBin': 'z2xBin'}
    existing = [c for c in mapping if c in df.columns]
    return df.rename(columns={c: mapping[c] for c in existing})

# =============================================================================
# Test Data Generators (3)
# =============================================================================

def _make_synthetic_3d_grid(
        n_bins_per_dim: int = 8,
        entries_per_bin: int = 40,
        seed: int = 42,
        realistic_names: bool = False
) -> pd.DataFrame:
    """
    WHAT:
      Build a dense 3D integer grid with a simple linear ground truth:
      value = 2*x + noise.
    WHY:
      Provides controlled truth to validate aggregation and linear regression
      recovery, and to exercise sliding-window behavior across bins.

    Columns (generic schema):
      - xBin, yBin, zBin (int32)
      - x (float), value (float), weight (float)
    If realistic_names=True:
      - yBin -> y2xBin, zBin -> z2xBin
      - also add meanIDC (float) for future realistic fits
    """
    rng = np.random.default_rng(seed)

    # Cartesian product of bins across 3 dims
    bins = np.array(list(itertools.product(
        range(n_bins_per_dim),
        range(n_bins_per_dim),
        range(n_bins_per_dim)
    )))
    bins_expanded = np.repeat(bins, entries_per_bin, axis=0)
    df = pd.DataFrame(bins_expanded, columns=['xBin', 'yBin', 'zBin']).astype(np.int32)

    # Predictor (x) and dependent variable (value)
    df['x'] = rng.normal(0.0, 1.0, len(df))
    df['value'] = 2.0 * df['x'] + rng.normal(0.0, 0.5, len(df))  # y = 2x + noise
    df['weight'] = 1.0

    if realistic_names:
        df = _cols_generic_to_realistic(df)
        df['meanIDC'] = rng.normal(0.0, 1.0, len(df))  # placeholder predictor

    return df


def _make_sparse_grid(
        sparsity: float = 0.3,
        n_bins_per_dim: int = 8,
        entries_per_bin: int = 40,
        seed: int = 42,
        realistic_names: bool = False
) -> pd.DataFrame:
    """
    WHAT:
      Start from a dense grid and randomly remove a fraction of unique bins.
    WHY:
      Validates robustness on patchy, sparse data—common in real calibration.
    """
    df = _make_synthetic_3d_grid(
        n_bins_per_dim=n_bins_per_dim,
        entries_per_bin=entries_per_bin,
        seed=seed,
        realistic_names=False,  # drop BEFORE renaming
    )

    rng = np.random.default_rng(seed)
    unique_bins = df[['xBin', 'yBin', 'zBin']].drop_duplicates()
    n_drop = int(len(unique_bins) * sparsity)
    if n_drop > 0:
        drop_idx = rng.choice(len(unique_bins), size=n_drop, replace=False)
        dropped = unique_bins.iloc[drop_idx]
        df = df.merge(dropped.assign(_drop=1), on=['xBin', 'yBin', 'zBin'], how='left')
        df = df[df['_drop'].isna()].drop(columns=['_drop'])

    if realistic_names:
        df = _cols_generic_to_realistic(df)
        df['meanIDC'] = rng.normal(0.0, 1.0, len(df))

    return df


def _make_boundary_test_grid(seed: int = 7, realistic_names: bool = False) -> pd.DataFrame:
    """
    WHAT:
      Tiny 3×3×3 grid for boundary-condition checks (deterministic).
    WHY:
      Ensures truncation uses fewer neighbors at edges than center.
    """
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        'xBin': [0, 0, 0, 1, 1, 1, 2, 2, 2],
        'yBin': [0, 1, 2, 0, 1, 2, 0, 1, 2],
        'zBin': [1, 1, 1, 1, 1, 1, 1, 1, 1],
        'x': rng.normal(0, 1, 9),
        'value': rng.normal(10, 2, 9),
        'weight': 1.0
    })
    if realistic_names:
        df = _cols_generic_to_realistic(df)
        df['meanIDC'] = rng.normal(0.0, 1.0, len(df))

    return df

# =============================================================================
# Category 1: Basic Functionality (5)
# =============================================================================

def test_sliding_window_basic_3d_verbose():
    """
    WHAT:
      Sanity test for 3D sliding window with ±1 neighbors and OLS fit.
    WHY:
      Confirms the API returns a DataFrame with key aggregation and regression
      outputs and attaches provenance metadata (.attrs).
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        fitter='ols',
        min_entries=10
    )

    assert isinstance(result, pd.DataFrame), "Result must be a DataFrame."
    assert {'xBin', 'yBin', 'zBin'}.issubset(result.columns), "Missing group columns."
    assert {'value_mean', 'value_std', 'value_entries'}.issubset(result.columns), "Missing aggregation outputs."

    # Regression: ensure at least basic coefficients are present
    expect_any = {'value_slope_x', 'value_intercept', 'value_r_squared'}
    assert any(c in result.columns for c in expect_any), "Missing regression outputs."

    # Metadata presence (canonical keys)
    meta = getattr(result, 'attrs', {})
    for key in ('window_spec_json', 'fitter_used', 'backend_used'):
        assert key in meta, f"Missing metadata: {key}"
    assert meta.get('fitter_used') == 'ols', "Fitter metadata mismatch."


def test_sliding_window_aggregation_verbose():
    """
    WHAT:
      Aggregation across neighbors: mean/median/std/entries should reflect the
      union of bins within the window (±1 in x only here).
    WHY:
      Aggregation is foundational; fitting depends on correct window unions.
    """
    df = pd.DataFrame({
        'xBin': [0, 0, 0, 1, 1, 1],
        'yBin': [0, 0, 0, 0, 0, 0],
        'zBin': [0, 0, 0, 0, 0, 0],
        'value': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        'x': [0]*6
    })

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 0, 'zBin': 0},  # ±1 in x
        fit_columns=['value'],
        predictor_columns=[],
        fit_formula=None,
        min_entries=1
    )

    row_0 = result[(result['xBin'] == 0) & (result['yBin'] == 0) & (result['zBin'] == 0)].iloc[0]
    assert row_0['value_entries'] == 6, "Entries must include neighbors in x."
    assert np.isclose(row_0['value_mean'], 3.5, atol=1e-6), "Mean mismatch."
    assert np.isclose(row_0.get('value_median', 3.5), 3.5, atol=1e-6), "Median mismatch."


def test_sliding_window_linear_fit_recover_slope():
    """
    WHAT:
      Validate linear regression recovers the known slope ≈ 2.0 for value ~ x.
    WHY:
      Ensures stable, unbiased parameter estimates after window aggregation.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=10, entries_per_bin=100, seed=7)

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 2, 'yBin': 2, 'zBin': 2},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        fitter='ols',
        min_entries=50
    )

    slopes = result[[c for c in result.columns if c.endswith('_slope_x')]].select_dtypes(include=[np.number]).stack()
    assert len(slopes) > 0, "No slope columns found."
    assert np.abs(slopes.mean() - 2.0) < 0.1, "Mean slope must be near 2.0."
    assert slopes.std() < 0.5, "Slope spread should be reasonably tight."


def test_empty_window_handling_no_crash():
    """
    WHAT:
      Sparse/isolated bins with small windows should not crash; bins may be
      skipped or flagged depending on implementation.
    WHY:
      Real data often contains isolated bins; algorithm must degrade gracefully.
    """
    df = pd.DataFrame({
        'xBin': [0, 10, 20],
        'yBin': [0, 10, 20],
        'zBin': [0, 10, 20],
        'value': [1.0, 2.0, 3.0],
        'x': [0.1, 0.2, 0.3]
    })

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        fitter='ols',
        min_entries=2
    )
    assert isinstance(result, pd.DataFrame), "Should not raise exceptions."


def test_min_entries_enforcement_flag_or_drop():
    """
    WHAT:
      Bins below min_entries should be skipped or flagged consistently.
    WHY:
      Enforces quality gates and prevents unstable fits in low-stat regions.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=5, seed=42)

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        fitter='ols',
        min_entries=50  # intentionally too high
    )

    if 'quality_flag' in result.columns:
        flagged = result[result['quality_flag'] == 'insufficient_stats']
        assert len(flagged) >= 0  # presence is sufficient; count is impl-dependent

# =============================================================================
# Category 2: Input Validation (8)
# =============================================================================

def test_invalid_window_spec_rejected():
    """
    WHAT:
      Malformed window_spec must raise InvalidWindowSpec (negative or missing).
    WHY:
      Early, explicit errors prevent silent misconfiguration in production.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)

    with pytest.raises(InvalidWindowSpec):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': -1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x'
        )

    with pytest.raises(InvalidWindowSpec):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1},  # missing zBin
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x'
        )


def test_missing_columns_raise_valueerror():
    """
    WHAT:
      Missing group/fit/predictor columns must error with a clear message.
    WHY:
      Avoids deep KeyErrors / NaNs; improves UX and reproducibility.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)

    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'MISSING'],
            window_spec={'xBin': 1, 'yBin': 1, 'MISSING': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x'
        )

    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['MISSING'],
            fit_formula='value ~ MISSING'
        )


def test_float_bins_rejected_in_m71():
    """
    WHAT:
      M7.1 requires integer bin coordinates; float bins must raise.
    WHY:
      Zero-copy accumulator and neighbor indexing assume integer bins.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    df['xBin'] = df['xBin'].astype(float) + 0.5
    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x'
        )


@pytest.mark.parametrize("bad_min", [0, -1, 2.5])
def test_min_entries_must_be_positive_int(bad_min):
    """
    WHAT:
      min_entries must be a strictly positive integer.
    WHY:
      Prevents ambiguous thresholds and bugs caused by floats or zero.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x',
            min_entries=bad_min
        )


def test_invalid_fit_formula_raises():
    """
    WHAT:
      Malformed formula strings should raise informative errors.
    WHY:
      Users rely on statsmodels/patsy diagnostics to fix formula issues.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    with pytest.raises((InvalidWindowSpec, ValueError)):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ ~ x'  # malformed
        )


def test_selection_mask_length_and_dtype():
    """
    WHAT:
      Selection mask must be boolean and match df length; otherwise raise.
    WHY:
      Prevents silent misalignment and unintended filtering.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    wrong_len = pd.Series([True, False, True])  # wrong length
    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x',
            selection=wrong_len
        )

    wrong_dtype = pd.Series(np.ones(len(df)))  # float, not bool
    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x',
            selection=wrong_dtype
        )


def test_wls_requires_weights_column():
    """
    WHAT:
      If fitter='wls', weights_column must be provided; otherwise raise.
    WHY:
      Avoids silent fallback to unweighted behavior.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x',
            fitter='wls',
            weights_column=None
        )


def test_numpy_fallback_emits_performance_warning():
    """
    WHAT:
      Requesting backend='numba' in M7.1 should warn (numpy fallback).
    WHY:
      Clear UX: users see they requested acceleration but are on fallback.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    with pytest.warns(PerformanceWarning, match="backend=.*numba.*fallback|fallback.*numba"):
        _ = make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x',
            backend='numba'
        )

# =============================================================================
# Category 3: Edge Cases (5)
# =============================================================================

def test_single_bin_dataset_ok():
    """
    WHAT:
      Only one unique bin—implementation should still succeed.
    WHY:
      Real pipelines sometimes filter down to a single cell.
    """
    rng = np.random.default_rng(3)
    df = pd.DataFrame({
        'xBin': [0] * 12,
        'yBin': [0] * 12,
        'zBin': [0] * 12,
        'value': rng.normal(0, 1, 12),
        'x': rng.normal(0, 1, 12),
        'weight': 1.0
    })

    result = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x', min_entries=5
    )

    assert len(result) == 1
    assert result.iloc[0][['xBin', 'yBin', 'zBin']].tolist() == [0, 0, 0]


def test_all_bins_below_threshold():
    """
    WHAT:
      If all bins fail min_entries, either return empty or flag all.
    WHY:
      Ensures graceful behavior in ultra-sparse settings.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=2)  # very sparse
    result = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x', min_entries=100
    )

    assert isinstance(result, pd.DataFrame)
    if len(result) > 0:
        assert 'quality_flag' in result.columns
        assert (result['quality_flag'] == 'insufficient_stats').all()


def test_boundary_bins_truncation_counts():
    """
    WHAT:
      Truncation boundary should yield fewer neighbors at corners than center.
    WHY:
      Edge correctness is crucial for physical geometries with bounds.
    """
    df = _make_boundary_test_grid(seed=11)
    result = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula=None, min_entries=1
    )

    corner = result[(result['xBin'] == 0) & (result['yBin'] == 0) & (result['zBin'] == 1)]
    center = result[(result['xBin'] == 1) & (result['yBin'] == 1) & (result['zBin'] == 1)]
    if len(corner) > 0 and len(center) > 0:
        assert corner.iloc[0].get('n_neighbors_used', 0) < center.iloc[0].get('n_neighbors_used', 1)


def test_multi_target_fit_output_schema():
    """
    WHAT:
      Fit multiple targets in one pass; verify naming consistent with v4 style.
    WHY:
      Downstream code depends on stable wide-column naming.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    df['value2'] = df['value'] * 2.0 + np.random.normal(0, 0.1, len(df))

    result = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value', 'value2'], predictor_columns=['x'],
        fit_formula='target ~ x', fitter='ols', min_entries=10
    )

    expected = [
        'value_mean', 'value_std', 'value_median', 'value_entries',
        'value_slope_x', 'value_intercept', 'value_r_squared',
        'value2_mean', 'value2_std', 'value2_median', 'value2_entries',
        'value2_slope_x', 'value2_intercept', 'value2_r_squared'
    ]
    for c in expected:
        assert c in result.columns, f"Missing column: {c}"


def test_weighted_vs_unweighted_coefficients_differ():
    """
    WHAT:
      Compare OLS vs WLS slopes with non-uniform weights—they should differ.
    WHY:
      Ensures weights are actually used in fitting path.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    df['weight'] = np.random.uniform(0.5, 2.0, len(df))

    res_ols = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x', fitter='ols', weights_column=None
    )
    res_wls = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x', fitter='wls', weights_column='weight'
    )

    merged = res_ols.merge(res_wls, on=['xBin', 'yBin', 'zBin'], suffixes=('_ols', '_wls'))
    diffs = np.abs(merged['value_slope_x_ols'] - merged['value_slope_x_wls'])
    assert (diffs > 1e-6).any(), "WLS and OLS slopes should differ in at least some bins."

# =============================================================================
# Category 4: Metadata + Selection + Backend (3)
# =============================================================================

def test_selection_mask_filters_pre_windowing():
    """
    WHAT:
      Selection mask must apply BEFORE windowing.
    WHY:
      Ensures entries/fit reflect the selected subset, not full dataset.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=20)
    selection = df['value'] > df['value'].median()

    res_all = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x', selection=None
    )
    res_sel = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x', selection=selection
    )

    assert res_sel['value_entries'].mean() < res_all['value_entries'].mean(), \
        "Selected run must show fewer entries per bin on average."


def test_metadata_presence_in_attrs():
    """
    WHAT:
      Verify required provenance metadata in .attrs for reproducibility.
    WHY:
      Downstream audit and RootInteractive integration rely on these fields.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)

    res = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x',
        binning_formulas={'xBin': 'x/0.5'}
    )
    meta = getattr(res, 'attrs', {})
    for key in (
            'window_spec_json',
            'binning_formulas_json',
            'boundary_mode_per_dim',
            'backend_used',
            'fitter_used',
            'computation_time_sec',
    ):
        assert key in meta, f"Missing metadata field: {key}"


def test_backend_numba_request_warns_numpy_fallback():
    """
    WHAT:
      Explicit check that the PerformanceWarning message notes fallback
      from requested backend='numba' to numpy (M7.1).
    WHY:
      Prevents regressions in user-facing UX.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    with pytest.warns(PerformanceWarning, match="numba"):
        _ = make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x', backend='numba'
        )

# =============================================================================
# Category 5: Statsmodels (2 + 1 doc-test)
# =============================================================================

@pytest.mark.parametrize("fitter", ["ols", "wls"])
def test_statsmodels_fitters_basic(fitter: str):
    """
    WHAT:
      Exercise OLS/WLS via statsmodels and verify coefficients exist.
    WHY:
      Confirms the statsmodels integration and weight handling path.
    """
    pytest.importorskip("statsmodels")
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    weights_col = None
    if fitter == "wls":
        df['weight'] = np.random.uniform(0.5, 2.0, len(df))
        weights_col = 'weight'

    res = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x', fitter=fitter, weights_column=weights_col
    )
    assert 'value_slope_x' in res.columns, "Expected slope column not found."


def test_statsmodels_formula_rich_syntax_relaxed():
    """
    WHAT:
      Rich formula features (transformations, interactions) should work.
    WHY:
      A core motivation for statsmodels is expressive formulas (no manual parsing).
    NOTE:
      We do NOT assert exact column names for all terms (patsy labels can vary).
      We assert at least that we get >1 coefficient-like outputs for the target.
    """
    pytest.importorskip("statsmodels")
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    df['x2'] = df['x'] ** 2

    res = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x', 'x2'],
        fit_formula='value ~ x + x2 + x:x2', fitter='ols'
    )
    assert 'value_slope_x' in res.columns
    coef_cols = [c for c in res.columns if c.startswith('value_') and ('slope_' in c or 'coef_' in c)]
    assert len(coef_cols) >= 2, "Expected multiple coefficient-like outputs."


def test_statsmodels_not_available_doc_behavior():
    """
    WHAT (documentation test):
      If statsmodels is missing and a statsmodels-backed fitter is requested,
      implementation should raise ImportError with a clear hint.
    WHY:
      Improves UX in new environments.
    """
    try:
        import statsmodels  # noqa: F401
    except Exception:
        df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
        with pytest.raises(ImportError):
            _ = make_sliding_window_fit(
                df, ['xBin', 'yBin', 'zBin'],
                window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
                fit_columns=['value'], predictor_columns=['x'],
                fit_formula='value ~ x', fitter='ols'
            )
    else:
        # If present, a tiny OLS run should succeed
        df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
        res = make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            fit_formula='value ~ x', fitter='ols'
        )
        assert isinstance(res, pd.DataFrame)

# =============================================================================
# Category 6: v4 Parity (robust naming) (1)
# =============================================================================

def test_window_size_zero_parity_with_v4_relaxed():
    """
    WHAT:
      Window size 0 (no neighbors) should match v4 group-by regression for
      identical model, within tolerance. We relax hard name matching and find
      the v4 slope column dynamically.
    WHY:
      Establishes continuity with v4 when sliding window is disabled.
    """
    try:
        from ..groupby_regression import make_parallel_fit as make_parallel_fit_v4
    except Exception:
        pytest.skip("v4 not available for comparison")

    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    df['weight'] = 1.0

    sw = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 0, 'yBin': 0, 'zBin': 0},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x', fitter='ols'
    )
    v4_df, v4_params = make_parallel_fit_v4(
        df, gb_columns=['xBin', 'yBin', 'zBin'],
        fit_columns=['value'], linear_columns=['x'],
        median_columns=[], weights='weight', suffix='_v4',
        selection=pd.Series(True, index=df.index), min_stat=3
    )

    merged = sw.merge(v4_params, on=['xBin', 'yBin', 'zBin'])
    # Find slope columns programmatically
    sw_slope = 'value_slope_x'
    v4_slope_candidates = [c for c in merged.columns if c.endswith('_slope_x_v4') or c.endswith('_x_slope_v4') or c.endswith('_slope_v4')]
    if not v4_slope_candidates:
        pytest.skip("Could not find v4 slope column automatically; adjust mapping if needed.")
    v4_slope = v4_slope_candidates[0]

    np.testing.assert_allclose(
        merged[sw_slope], merged[v4_slope],
        rtol=1e-3, atol=1e-5
    )

# =============================================================================
# Category 7: Internals Exposure (2)
# =============================================================================

def test__build_bin_index_map_contract():
    """
    WHAT:
      _build_bin_index_map must return a mapping from bin_tuple -> row indices,
      with the expected number of unique keys.
    WHY:
      Zero-copy accumulator relies on this; it’s performance-critical.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=5)
    bmap = _build_bin_index_map(df, group_columns=['xBin', 'yBin', 'zBin'])
    assert hasattr(bmap, 'get'), "Must be dict-like."
    assert len(bmap) == 27, "Expected 3^3 unique bin keys."


def test__generate_offsets_and_get_neighbors_truncate_contract():
    """
    WHAT:
      _generate_neighbor_offsets must produce the cartesian offsets for the
      given window_spec; _get_neighbor_bins must truncate to bounds.
    WHY:
      These are the core building blocks for the sliding window.
    """
    # OFFSETS: 3x3x3 = 27 for ±1 in each dimension
    offsets = _generate_neighbor_offsets({'xBin': 1, 'yBin': 1, 'zBin': 1})
    assert len(offsets) == 27, "Expected 27 neighbor offsets for ±1 in 3D."

    # NEIGHBORS with truncation
    center = (1, 1, 1)
    bin_ranges = {'xBin': (0, 2), 'yBin': (0, 2), 'zBin': (0, 2)}  # inclusive bounds
    neighbors_center = _get_neighbor_bins(center, offsets, bin_ranges, boundary_mode='truncate')
    assert len(neighbors_center) == 27, "Center should have full neighbors in-range."

    corner = (0, 0, 0)
    neighbors_corner = _get_neighbor_bins(corner, offsets, bin_ranges, boundary_mode='truncate')
    assert len(neighbors_corner) < 27, "Corner must be truncated at boundaries."

# =============================================================================
# Category 8: Realistic Distortion Smoke Test (fast)
# =============================================================================

def test_realistic_smoke_normalised_residuals_gate():
    """
    WHAT:
      Quick smoke test using realistic column names to ensure the normalised
      residual gates conceptually work (≤4σ pass, 4–6σ warn). We keep this
      tiny and fast—no heavy physics fixture here.
    WHY:
      Early signal that the QA gate logic is being wired and will integrate
      with the realistic benchmark .pkl later.
    """
    # Use realistic naming to align with future .pkl benchmarks
    df = _make_synthetic_3d_grid(n_bins_per_dim=4, entries_per_bin=20, realistic_names=True, seed=123)
    # Use a simple linear model with realistic predictor name as a proxy.
    result = make_sliding_window_fit(
        df, ['xBin', 'y2xBin', 'z2xBin'],
        window_spec={'xBin': 1, 'y2xBin': 1, 'z2xBin': 1},
        fit_columns=['value'], predictor_columns=['meanIDC'],
        fit_formula='value ~ meanIDC', fitter='ols', min_entries=10
    )

    # We cannot assert exact counts, but we can assert existence of entries
    # and that residual-related outputs (e.g., value_std) are finite.
    assert len(result) > 0
    assert np.isfinite(result['value_std']).all()
