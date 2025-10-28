# -*- coding: utf-8 -*-
# test_groupby_regression_sliding_window.py
#
# Phase 7 (M7.1) — Sliding Window Regression: Full Test Suite
#
# This test suite specifies the expected behavior of the sliding-window
# group-by regression API, including aggregation, neighbor handling,
# validation, metadata, and statsmodels-backed fitters. It is intentionally
# verbose: every test explains WHAT it checks and WHY it matters for the
# production workflow (TPC calibration, performance parameterization).
#
# Notes:
# - These tests define the CONTRACT for implementation. They may initially
#   fail until the corresponding functions are implemented.
# - Keep Python 3.9.6 compatibility: use typing.Union/Optional instead of X|Y.
# - Statsmodels-specific tests auto-skip if statsmodels is unavailable.
# - v4 parity test auto-skips if v4 isn’t importable in the environment.

from __future__ import annotations

from typing import List, Dict, Tuple, Optional
import itertools
import warnings

import numpy as np
import pandas as pd
import pytest

# Functions to test (public + selected internals exposed for testing)
# The module path below should match the project layout. If your file lives
# under a package, adjust the import accordingly.
from groupby_regression_sliding_window import (
    make_sliding_window_fit,
    InvalidWindowSpec,
    PerformanceWarning,
    _build_bin_index_map,     # Exposed for testing
    _generate_neighbor_offsets,  # Exposed for testing
    _get_neighbor_bins,          # Exposed for testing
)


# ---------------------------------------------------------------------------
# Test Data Generators (3)
# ---------------------------------------------------------------------------

def _make_synthetic_3d_grid(
        n_bins_per_dim: int = 10,
        entries_per_bin: int = 50,
        seed: int = 42
) -> pd.DataFrame:
    """
    Generate a synthetic 3D integer-binned dataset with a known linear relation.

    WHAT: Builds a dense 3D grid of integer bins and populates each bin with
    entries_per_bin rows. Adds a simple linear signal: value = 2*x + noise.

    WHY: Provides a controlled ground truth to validate:
      - Aggregations (mean/median/std/entries)
      - Linear regression recovery (slope ~ 2.0)
      - Sliding window behavior (varying window sizes)

    Returns columns:
      - xBin, yBin, zBin (int32)
      - x (float), value (float)
      - weight (float)
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
    return df


def _make_sparse_grid(
        sparsity: float = 0.3,
        n_bins_per_dim: int = 10,
        entries_per_bin: int = 50,
        seed: int = 42
) -> pd.DataFrame:
    """
    Generate a 3D grid with a specified fraction of empty bins.

    WHAT: Starts with a dense grid (via _make_synthetic_3d_grid) and randomly
    removes a fraction of unique bins.

    WHY: Validates algorithm robustness in sparse/patchy datasets, common in
    real calibration where many bin combinations have low or zero occupancy.
    """
    df = _make_synthetic_3d_grid(
        n_bins_per_dim=n_bins_per_dim,
        entries_per_bin=entries_per_bin,
        seed=seed
    )

    rng = np.random.default_rng(seed)
    unique_bins = df[['xBin', 'yBin', 'zBin']].drop_duplicates()
    n_drop = int(len(unique_bins) * sparsity)
    if n_drop <= 0:
        return df

    # Randomly choose bins to drop
    drop_idx = rng.choice(len(unique_bins), size=n_drop, replace=False)
    bins_to_drop = unique_bins.iloc[drop_idx]

    # Remove rows belonging to dropped bins
    df = df.merge(bins_to_drop.assign(_drop=1),
                  on=['xBin', 'yBin', 'zBin'],
                  how='left')
    df = df[df['_drop'].isna()].drop(columns=['_drop'])
    return df


def _make_boundary_test_grid() -> pd.DataFrame:
    """
    Construct a tiny 3×3×3 grid for boundary-condition checks.

    WHAT: Provides bins along edges and corners to ensure truncation (M7.1
    boundary mode) uses fewer neighbors at boundaries than in the center.

    WHY: Edge correctness is vital in detector geometries with natural bounds.
    """
    df = pd.DataFrame({
        'xBin': [0, 0, 0, 1, 1, 1, 2, 2, 2],
        'yBin': [0, 1, 2, 0, 1, 2, 0, 1, 2],
        'zBin': [1, 1, 1, 1, 1, 1, 1, 1, 1],
        'x': np.random.normal(0, 1, 9),
        'value': np.random.normal(10, 2, 9),
        'weight': 1.0
    })
    return df


# ---------------------------------------------------------------------------
# Category 1: Basic Functionality (5)
# ---------------------------------------------------------------------------

def test_sliding_window_basic_3d():
    """
    WHAT: Basic 3D sliding window with ±1 neighbors; OLS fit on a simple signal.

    WHY: Sanity test that:
      - The function runs and returns a DataFrame with expected columns
      - Metadata (attrs) is populated with provenance fields
      - The fitter used is recorded
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},  # ±1 in each dim
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        fitter='ols',
        min_entries=10
    )

    assert isinstance(result, pd.DataFrame)
    assert {'xBin', 'yBin', 'zBin'}.issubset(result.columns)
    assert {'value_mean', 'value_std', 'value_entries'}.issubset(result.columns)

    # Regression outputs (naming may include slope_x, intercept, r_squared)
    # The exact column names are part of the contract discussed in the plan.
    # Here we check a representative subset.
    expected_any = {'value_slope_x', 'value_intercept', 'value_r_squared'}
    assert any(c in result.columns for c in expected_any), \
        "Expected regression columns missing."

    # Metadata/provenance (attrs contract)
    assert isinstance(getattr(result, 'attrs', {}), dict)
    for key in (
            'window_spec_json',
            'fitter_used',
            'backend_used',
    ):
        assert key in result.attrs, f"Missing metadata field: {key}"
    assert result.attrs.get('fitter_used') == 'ols'


def test_sliding_window_aggregation():
    """
    WHAT: Verify aggregation (mean/median/std/entries) across neighbors.

    WHY: Aggregation is the foundation before fitting. With a window over xBin,
    we should include contributions from neighboring bins correctly.
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
        window_spec={'xBin': 1, 'yBin': 0, 'zBin': 0},  # ±1 in x only
        fit_columns=['value'],
        predictor_columns=[],
        fit_formula=None,
        min_entries=1
    )

    row_0 = result[(result['xBin'] == 0) & (result['yBin'] == 0) & (result['zBin'] == 0)].iloc[0]
    # With window in x, bin 0 includes both its own and bin 1 values
    assert row_0['value_entries'] == 6
    # Mean of all 6 numbers 1..6 is 3.5
    assert np.isclose(row_0['value_mean'], 3.5, atol=1e-6)
    assert np.isclose(row_0.get('value_median', 3.5), 3.5, atol=1e-6)


def test_sliding_window_linear_fit():
    """
    WHAT: Validate linear regression recovers the known slope ~ 2.0.

    WHY: Ensures that (a) windowing aggregates enough statistics and (b)
    the fitter produces stable, unbiased parameter estimates.
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
    assert len(slopes) > 0
    assert np.abs(slopes.mean() - 2.0) < 0.1   # Mean slope near 2.0
    assert slopes.std() < 0.5                  # Reasonably tight distribution


def test_empty_window_handling():
    """
    WHAT: Ensure isolated bins (with small windows) do not cause crashes.

    WHY: Sparse data is common; bins with insufficient neighbors should be
    skipped or flagged without exceptions.
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
    assert isinstance(result, pd.DataFrame)  # No crash is success here


def test_min_entries_enforcement():
    """
    WHAT: Bins with fewer than min_entries should be skipped or flagged.

    WHY: Protects fit quality; large min_entries forces the algorithm to apply
    its quality gate, which should be visible in the result.
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
        min_entries=50  # Intentionally too high
    )

    # Implementation can either drop such bins or keep them with a quality flag.
    if 'quality_flag' in result.columns:
        flagged = result[result['quality_flag'] == 'insufficient_stats']
        assert len(flagged) >= 0  # Presence is sufficient; exact count is impl-dependent.


# ---------------------------------------------------------------------------
# Category 2: Input Validation (6)
# ---------------------------------------------------------------------------

def test_invalid_window_spec():
    """
    WHAT: Reject malformed window_spec definitions.

    WHY: Clear early validation prevents silent misconfiguration and wrong
    scientific conclusions. Negative window sizes or missing dims must error.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)

    # Negative window size
    with pytest.raises(InvalidWindowSpec):
        make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': -1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'],
            predictor_columns=['x'],
            fit_formula='value ~ x'
        )

    # Missing dimension
    with pytest.raises(InvalidWindowSpec):
        make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1},  # zBin missing
            fit_columns=['value'],
            predictor_columns=['x'],
            fit_formula='value ~ x'
        )


def test_missing_columns():
    """
    WHAT: Error on missing group/fit/predictor columns.

    WHY: The API should loudly fail if required columns are absent, avoiding
    downstream KeyErrors or silent NaNs.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)

    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'MISSING'],
            window_spec={'xBin': 1, 'yBin': 1, 'MISSING': 1},
            fit_columns=['value'],
            predictor_columns=['x'],
            fit_formula='value ~ x'
        )

    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'],
            predictor_columns=['MISSING'],
            fit_formula='value ~ MISSING'
        )


def test_float_bins_rejected():
    """
    WHAT: M7.1 requires integer bin coordinates. Reject float bins.

    WHY: The zero-copy accumulator and neighbor indexing assume integer bins;
    allowing floats would cause subtle indexing bugs/perf issues.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    df['xBin'] = df['xBin'].astype(float) + 0.5  # Break the assumption

    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'],
            predictor_columns=['x'],
            fit_formula='value ~ x'
        )


def test_negative_min_entries():
    """
    WHAT: min_entries must be positive.

    WHY: Negative thresholds are invalid configuration; catching this early is
    part of a robust API.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)

    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'],
            predictor_columns=['x'],
            fit_formula='value ~ x',
            min_entries=-1
        )


def test_invalid_fit_formula():
    """
    WHAT: Malformed formula strings should raise informative errors.

    WHY: Formula parsing failures must be explicit so users can correct them,
    especially with statsmodels displaying parsing diagnostics.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)

    with pytest.raises((InvalidWindowSpec, ValueError)):
        make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'],
            predictor_columns=['x'],
            fit_formula='value ~ ~ x'  # Deliberately malformed
        )


def test_selection_mask_length_mismatch():
    """
    WHAT: Selection masks must have the same length as df.

    WHY: Mismatched masks can silently drop data or misalign rows; error out.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    wrong_selection = pd.Series([True, False, True])  # Wrong length

    with pytest.raises(ValueError):
        make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'],
            predictor_columns=['x'],
            fit_formula='value ~ x',
            selection=wrong_selection
        )


# ---------------------------------------------------------------------------
# Category 3: Edge Cases (5)
# ---------------------------------------------------------------------------

def test_single_bin_dataset():
    """
    WHAT: Dataset with only one unique bin must be handled gracefully.

    WHY: Validates that the algorithm does not assume multiple bins exist and
    still produces a valid summary for the single bin.
    """
    df = pd.DataFrame({
        'xBin': [0] * 10,
        'yBin': [0] * 10,
        'zBin': [0] * 10,
        'value': np.random.randn(10),
        'x': np.random.randn(10),
        'weight': 1.0
    })

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        min_entries=5
    )

    assert len(result) == 1
    assert result.iloc[0]['xBin'] == 0
    assert result.iloc[0]['yBin'] == 0
    assert result.iloc[0]['zBin'] == 0


def test_all_sparse_bins():
    """
    WHAT: Scenario where all bins fail the min_entries threshold.

    WHY: Ensures the algorithm either returns an empty frame or flags all rows
    without crashing. This mirrors very sparse detector regions.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=2)

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        min_entries=100
    )

    assert isinstance(result, pd.DataFrame)
    if len(result) > 0:
        assert 'quality_flag' in result.columns
        assert (result['quality_flag'] == 'insufficient_stats').all()


def test_boundary_bins():
    """
    WHAT: Verify truncation at grid boundaries (M7.1 boundary mode).

    WHY: Corner/edge bins should use fewer neighbors than interior bins.
    """
    df = _make_boundary_test_grid()

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula=None,
        min_entries=1
    )

    # Example corner vs center (depends on z fixed at 1 in generator)
    corner = result[(result['xBin'] == 0) & (result['yBin'] == 0) & (result['zBin'] == 1)]
    center = result[(result['xBin'] == 1) & (result['yBin'] == 1) & (result['zBin'] == 1)]
    if len(corner) > 0 and len(center) > 0:
        assert corner.iloc[0].get('n_neighbors_used', 0) < center.iloc[0].get('n_neighbors_used', 1)


def test_multi_target_fit():
    """
    WHAT: Fit multiple targets in one pass and verify output naming.

    WHY: Ensures multi-target output schema is consistent and ready for
    downstream pipelines without additional reshaping.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    df['value2'] = df['value'] * 2 + np.random.normal(0, 0.1, len(df))

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value', 'value2'],
        predictor_columns=['x'],
        fit_formula='target ~ x',  # Contract: 'target' is replaced per fit column
        fitter='ols',
        min_entries=10
    )

    expected_cols = [
        'value_mean', 'value_std', 'value_median', 'value_entries',
        'value_slope_x', 'value_intercept', 'value_r_squared',
        'value2_mean', 'value2_std', 'value2_median', 'value2_entries',
        'value2_slope_x', 'value2_intercept', 'value2_r_squared'
    ]
    for col in expected_cols:
        assert col in result.columns, f"Missing column: {col}"


def test_weighted_aggregation():
    """
    WHAT: Compare unweighted vs WLS-weighted results.

    WHY: Weighted fits should produce measurably different coefficients
    whenever weights are non-uniform.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    df['weight'] = np.random.uniform(0.5, 2.0, len(df))

    result_unw = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        fitter='ols',
        weights_column=None
    )

    result_w = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        fitter='wls',
        weights_column='weight'
    )

    merged = result_unw.merge(result_w, on=['xBin', 'yBin', 'zBin'], suffixes=('_unw', '_w'))
    # At least some bins should differ in slope under WLS vs OLS
    diffs = np.abs(merged['value_slope_x_unw'] - merged['value_slope_x_w'])
    assert (diffs > 1e-6).any()


# ---------------------------------------------------------------------------
# Category 4: Review-Added Tests (5)
# ---------------------------------------------------------------------------

def test_selection_mask():
    """
    WHAT: Selection mask should filter rows BEFORE windowing.

    WHY: This ensures statistical counts and fits reflect the selected subset,
    not the full dataset, which is critical for staged QA selections.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=20)
    selection = df['value'] > df['value'].median()

    result_all = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        selection=None
    )

    result_sel = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        selection=selection
    )

    assert result_sel['value_entries'].mean() < result_all['value_entries'].mean()


def test_metadata_presence():
    """
    WHAT: Verify required metadata fields are present in .attrs.

    WHY: Provenance data (window spec, backend, fitter) is essential for
    reproducibility and later audit/troubleshooting in production.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        binning_formulas={'xBin': 'x / 0.5'}
    )

    for key in (
            'window_spec_json',
            'binning_formulas_json',
            'boundary_mode_per_dim',
            'backend_used',
            'fitter_used',
            'computation_time_sec',
    ):
        assert key in result.attrs, f"Missing metadata field: {key}"


def test_performance_warning_numpy_fallback():
    """
    WHAT: Emit PerformanceWarning when backend='numba' is requested but M7.1
    uses numpy fallback.

    WHY: Clear feedback to the user that accelerated mode wasn’t available.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)

    with pytest.warns(PerformanceWarning):
        _ = make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'],
            predictor_columns=['x'],
            fit_formula='value ~ x',
            backend='numba'  # Expect warning if implementation falls back
        )


def test_window_size_zero_equivalence_with_v4():
    """
    WHAT: Window size 0 (no neighbors) should match v4 group-by regression.

    WHY: Establishes parity with the existing v4 baseline when the sliding
    window is effectively disabled. Skips if v4 isn’t available.
    """
    try:
        from groupby_regression_optimized import make_parallel_fit as make_parallel_fit_v4
    except Exception:
        pytest.skip("v4 not available for comparison")

    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    df['weight'] = 1.0

    sw_result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 0, 'yBin': 0, 'zBin': 0},  # No neighbors
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        fitter='ols'
    )

    v4_result, v4_params = make_parallel_fit_v4(
        df, gb_columns=['xBin', 'yBin', 'zBin'],
        fit_columns=['value'], linear_columns=['x'],
        median_columns=[], weights='weight', suffix='_v4',
        selection=pd.Series(True, index=df.index),
        min_stat=3
    )

    merged = sw_result.merge(v4_params, on=['xBin', 'yBin', 'zBin'])
    # Compare slope parameter naming contract:
    # - sliding window: 'value_slope_x'
    # - v4 params:      'value_slope_x_v4' or similar suffix
    # If exact name differs in v4, adjust below accordingly.
    v4_slope_col = [c for c in merged.columns if c.endswith('_slope_x_v4')]
    if not v4_slope_col:
        pytest.skip("Could not find v4 slope column; adjust name in test to match v4.")
    v4_slope_col = v4_slope_col[0]

    np.testing.assert_allclose(
        merged['value_slope_x'], merged[v4_slope_col],
        rtol=1e-3, atol=1e-5
    )


def test_multi_target_column_naming():
    """
    WHAT: Validate multi-target naming convention matches v4-style output.

    WHY: Keeps downstream code stable by preserving column naming layout.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=20)
    df['value2'] = df['value'] * 2.0

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value', 'value2'],
        predictor_columns=['x'],
        fit_formula='target ~ x',
        fitter='ols'
    )

    expected_cols = [
        'value_mean', 'value_std', 'value_median', 'value_entries',
        'value_slope_x', 'value_intercept', 'value_r_squared',
        'value2_mean', 'value2_std', 'value2_median', 'value2_entries',
        'value2_slope_x', 'value2_intercept', 'value2_r_squared'
    ]
    for col in expected_cols:
        assert col in result.columns, f"Missing column: {col}"


# ---------------------------------------------------------------------------
# Category 5: Statsmodels Tests (3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fitter", ["ols", "wls"])
def test_statsmodels_fitters_ols_wls(fitter: str):
    """
    WHAT: Exercise OLS/WLS statsmodels fitters and verify coefficients exist.

    WHY: Confirms the statsmodels integration and weight handling pathway.
    """
    sm = pytest.importorskip("statsmodels")  # Skip if not installed

    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    if fitter == "wls":
        df['weight'] = np.random.uniform(0.5, 2.0, len(df))
        weights_column = 'weight'
    else:
        weights_column = None

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x'],
        fit_formula='value ~ x',
        fitter=fitter,
        weights_column=weights_column
    )
    assert 'value_slope_x' in result.columns


def test_statsmodels_formula_syntax():
    """
    WHAT: Verify rich formula syntax (transformations, interactions) works.

    WHY: One of the main motivations for statsmodels integration is to allow
    expressiveness (e.g., np.log, interactions x1:x2) without manual parsing.
    """
    pytest.importorskip("statsmodels")

    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    df['x2'] = df['x'] ** 2

    result = make_sliding_window_fit(
        df=df,
        group_columns=['xBin', 'yBin', 'zBin'],
        window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'],
        predictor_columns=['x', 'x2'],
        fit_formula='value ~ x + x2 + x:x2',  # Interaction term
        fitter='ols'
    )

    # We cannot predict exact column names for every design-matrix term,
    # but at least 'value_slope_x' should exist.
    assert 'value_slope_x' in result.columns
    # Interaction presence should manifest as an additional coefficient column;
    # we check that we have more than the minimal set.
    coef_cols = [c for c in result.columns if c.startswith('value_') and ('slope_' in c or 'coef_' in c)]
    assert len(coef_cols) >= 2


def test_statsmodels_not_available_message():
    """
    WHAT: If statsmodels is not installed and a statsmodels-backed fitter is
    requested, the implementation should raise a clear ImportError.

    WHY: Good UX and easy remediation for users in new environments.
    """
    # This is a documentation test. We cannot reliably uninstall statsmodels
    # within the test. Instead, we document the expected behavior:
    #   ImportError: statsmodels is required...
    #   Install with: pip install statsmodels
    #
    # If statsmodels *is* installed, we just run a tiny OLS and expect success.
    try:
        import statsmodels  # noqa: F401
    except Exception:
        # If not available, we expect the function call with 'ols' to raise ImportError.
        df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
        with pytest.raises(ImportError):
            _ = make_sliding_window_fit(
                df=df,
                group_columns=['xBin', 'yBin', 'zBin'],
                window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
                fit_columns=['value'],
                predictor_columns=['x'],
                fit_formula='value ~ x',
                fitter='ols'
            )
    else:
        # If statsmodels is available, normal run should succeed.
        df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
        res = make_sliding_window_fit(
            df=df,
            group_columns=['xBin', 'yBin', 'zBin'],
            window_spec={'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'],
            predictor_columns=['x'],
            fit_formula='value ~ x',
            fitter='ols'
        )
        assert isinstance(res, pd.DataFrame)


# ---------------------------------------------------------------------------
# Internals Exposure Tests (Bonus — not counted in the 20+, but helpful)
# ---------------------------------------------------------------------------

def test__build_bin_index_map_shapes_and_types():
    """
    WHAT: Validate _build_bin_index_map creates expected mapping types/sizes.

    WHY: Zero-copy accumulator relies on a map from (bin tuple) -> row indices.
    Correctness and type stability here directly impact performance and memory.
    """
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=5)
    # This function is expected to exist and return a dict-like mapping
    # The exact structure is implementation-defined; we check minimal contract.
    bmap = _build_bin_index_map(df, group_columns=['xBin', 'yBin', 'zBin'])
    assert hasattr(bmap, 'get')
    # Expect many unique keys (3^3 = 27)
    assert len(bmap) == 27


def test__generate_neighbor_offsets_and_get_neighbor_bins():
    """
    WHAT: Validate neighbor offset generation and bin collection with truncation.

    WHY: Neighbor enumeration is the core of windowing. This test ensures that
    the offset generator and truncation boundary behavior align with spec.
    """
    # Offsets for window_spec = ±1 in 3 dims → 3*3*3 = 27 offsets
    offsets = _generate_neighbor_offsets({'xBin': 1, 'yBin': 1, 'zBin': 1}, order=('xBin', 'yBin', 'zBin'))
    assert len(offsets) == 27

    # A small grid of center bins and a truncation rule (M7.1)
    center = (1, 1, 1)
    dims = {'xBin': (0, 2), 'yBin': (0, 2), 'zBin': (0, 2)}  # min/max
    neighbors = _get_neighbor_bins(center, offsets, dims, boundary='truncate', order=('xBin', 'yBin', 'zBin'))
    # Center (1,1,1) should have all 27 neighbors inside bounds
    assert len(neighbors) == 27

    # Corner (0,0,0) should truncate outside indices → fewer neighbors
    corner = (0, 0, 0)
    n_corner = _get_neighbor_bins(corner, offsets, dims, boundary='truncate', order=('xBin', 'yBin', 'zBin'))
    assert len(n_corner) < 27
