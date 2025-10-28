# Phase 7 Implementation Plan: Sliding Window Regression

**Project:** GroupBy Regression - Sliding Window Extensions  
**Version:** v2.1.0 (target)  
**Date:** 2025-10-27 (Updated after GPT/Gemini review)  
**Lead:** Marian Ivanov (MI) & Claude  
**Reviewers:** GPT-4 ✅, Gemini ✅ (Approved with changes incorporated)  
**Python Version:** 3.9.6+ (type hint compatibility required)

---

## Executive Summary

Phase 7 implements **Sliding Window GroupBy Regression** for multi-dimensional sparse data analysis, targeting ALICE TPC calibration and tracking performance parameterization use cases. The implementation follows the comprehensive specification in `SLIDING_WINDOW_SPEC_DRAFT.md` and reuses the validated v2.0.0 GroupBy Regressor infrastructure.

**Core Innovation:** Enable local PDF estimation and regression in high-dimensional (3D-6D+) sparse binned spaces by aggregating data from neighboring bins according to configurable window sizes and boundary conditions.

**Primary Goals:**
1. Support 3D-6D dimensionality with **integer bin coordinates** (float pre-binning required)
2. Flexible per-dimension window configuration (size, boundary mode, weighting)
3. **Memory-efficient implementation** (<4GB per session) via zero-copy accumulator (MEM-3)
4. Performance target: <30 min for 7M rows × 90 maps (Numba), <5 min for 400k rows (numpy demo)
5. Integration with existing v4 fit logic (no new dependencies for core functionality)

**Key Architectural Decision (from reviews):**
- **Zero-Copy Accumulator (MEM-3):** Prototype in M7.1 (pure NumPy) to validate algorithm, then JIT-compile in M7.2
- **No naive DataFrame expansion:** Use MultiIndex bin→row mapping instead of merge/groupby replication
- **Reuse v4 fit logic:** No statsmodels dependency; simple regex formula parsing + existing OLS/Huber code

---

## Implementation Strategy

### Phased Approach

We adopt a **three-milestone** strategy to balance scope, risk, and validation:

| Milestone | Scope | Duration | Validation |
|-----------|-------|----------|------------|
| **M7.1** | Core API + Zero-Copy Prototype | 1-2 weeks | Unit tests, algorithm validation |
| **M7.2** | Numba Optimization + Advanced Features | 2-3 weeks | Performance benchmarks, stress tests |
| **M7.3** | Polish + Documentation | 1 week | Full validation, user guide |

**Note:** M7.2 timeline extended to 2-3 weeks per reviewer feedback (Numba + boundaries + weighting is dense).

**Total timeline:** 4-6 weeks to v2.1.0 tag

**Key Differences from Original Plan (Post-Review):**
- ✅ M7.1 now includes **zero-copy accumulator prototype** (critical for correctness validation)
- ✅ Simple formula parsing without statsmodels (reuse v4 fit logic)
- ✅ API includes `selection`, `binning_formulas`, `partition_strategy` from start (future-proof)
- ✅ Output includes provenance metadata (RootInteractive compatibility)
- ✅ Dense/sparse mode detection with performance warnings
- ⏱️ M7.2 acknowledged as aggressive (2-3 weeks realistic)

---

## Milestone 7.1: Core Implementation

**Target:** Early November 2025  
**Focus:** Minimum viable product with essential features

### Deliverables

#### D7.1.1: Core API Implementation

**File:** `groupby_regression_sliding_window.py`

**Main function signature (Python 3.9.6 compatible):**
```python
from __future__ import annotations
from typing import List, Dict, Union, Optional, Callable, Tuple, Any

def make_sliding_window_fit(
    df: pd.DataFrame,
    group_columns: List[str],
    window_spec: Dict[str, Union[int, dict]],
    fit_columns: List[str],
    predictor_columns: List[str],
    fit_formula: Optional[Union[str, Callable]] = None,
    aggregation_functions: Optional[Dict[str, List[str]]] = None,
    weights_column: Optional[str] = None,
    selection: Optional[pd.Series] = None,
    binning_formulas: Optional[Dict[str, str]] = None,
    min_entries: int = 10,
    backend: str = 'numba',
    partition_strategy: Optional[dict] = None,
    **kwargs
) -> pd.DataFrame:
    """
    Perform sliding window regression over multi-dimensional bins.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input data with binning columns, targets, and predictors
    
    group_columns : List[str]
        Column names defining the binning dimensions (e.g., ['xBin', 'y2xBin', 'z2xBin'])
        MUST be integer bin coordinates (users must pre-bin float coordinates)
    
    window_spec : Dict[str, Union[int, dict]]
        Window specification for each dimension. Can be:
        - Simple: {'xBin': 2, 'y2xBin': 1}  # ±2, ±1 bins
        - Rich (M7.2): {'xBin': {'size': 2, 'boundary': 'truncate'}, ...}
    
    fit_columns : List[str]
        Target variables to fit (dependent variables)
    
    predictor_columns : List[str]
        Feature variables used as predictors in regression
    
    fit_formula : Optional[Union[str, Callable]]
        Regression specification:
        - String formula: 'dX ~ meanIDC + deltaIDC' (simple regex parsing, no statsmodels)
        - Callable: custom_fit_func(X, y, weights) -> (coefficients, diagnostics)
        - None: aggregation only, no fitting
    
    aggregation_functions : Optional[Dict[str, List[str]]]
        Statistical aggregations to compute per target variable.
        Example: {'dX': ['mean', 'median', 'std', 'q10', 'q90'], 'dY': ['mean', 'rms']}
        Default: ['mean', 'std', 'entries', 'median'] for all fit_columns
    
    weights_column : Optional[str]
        Column name for statistical weights. If None (default), uniform weights (1.0) 
        are assumed. If specified, column must exist in df and contain non-negative floats.
    
    selection : Optional[pd.Series]
        Boolean mask (same length as df) to pre-filter rows before windowing.
        Consistent with v2/v4 GroupByRegressor API. Applied once before bin mapping.
    
    binning_formulas : Optional[Dict[str, str]]
        Metadata: formulas used to bin float coordinates to integers.
        Example: {'time': 'time / 0.5', 'pT': 'log10(pT) * 10'}
        NOT applied by framework (users must pre-bin). Stored in output.attrs for provenance.
    
    min_entries : int, default=10
        Minimum number of entries required in aggregated window to perform fit.
        Bins with fewer entries are flagged in output.
    
    backend : str, default='numba'
        Computation backend: 'numba' (JIT compiled) or 'numpy' (fallback).
        M7.1: 'numpy' only (prototype). M7.2: 'numba' added.
    
    partition_strategy : Optional[dict]
        Memory-efficient partitioning configuration (M7.2+ implementation).
        Example: {'method': 'auto', 'memory_limit_gb': 4, 'overlap': 'full'}
        M7.1: accepted but not used (future-proofing API).
    
    **kwargs
        Additional backend-specific options
    
    Returns
    -------
    pd.DataFrame
        Results with one row per center bin, containing:
        - group_columns: Center bin coordinates
        - Aggregated statistics: {target}_mean, {target}_std, {target}_median, {target}_entries
        - Fit coefficients (if fit_formula provided): {target}_slope_{predictor}, {target}_intercept
        - Diagnostics: {target}_r_squared, {target}_rmse, {target}_n_fitted
        - Quality flags: effective_window_fraction, quality_flag
        
        Metadata in .attrs:
        - window_spec_json: Original window specification
        - binning_formulas_json: Binning formulas (if provided)
        - boundary_mode_per_dim: Boundary handling per dimension
        - backend_used: 'numpy' or 'numba'
        - computation_time_sec: Total runtime
    
    Raises
    ------
    InvalidWindowSpec
        If window_spec format is invalid or window sizes are negative
    ValueError
        If required columns missing, or data types incompatible
    PerformanceWarning
        If backend='numba' unavailable (falls back to numpy), or window volume very large
    
    Notes
    -----
    M7.1 scope (Minimum Viable Product):
    - Integer bin coordinates ONLY (users MUST pre-bin floats)
    - Simple window_spec: {'xBin': 2} means ±2 bins
    - Boundary: 'truncate' only (no mirror/periodic)
    - Weighting: 'uniform' only
    - Backend: 'numpy' (zero-copy accumulator prototype)
    - Linear regression: simple formula parsing + reuse v4 fit logic
    
    Float coordinates deferred to v2.2+. See DH-2 in specification.
    
    Examples
    --------
    >>> # Basic 3D spatial regression
    >>> result = make_sliding_window_fit(
    ...     df=tpc_data,
    ...     group_columns=['xBin', 'y2xBin', 'z2xBin'],
    ...     window_spec={'xBin': 1, 'y2xBin': 1, 'z2xBin': 1},
    ...     fit_columns=['dX', 'dY', 'dZ'],
    ...     predictor_columns=['meanIDC', 'deltaIDC'],
    ...     fit_formula='target ~ meanIDC + deltaIDC',
    ...     min_entries=10
    ... )
    
    >>> # Aggregation only (no fitting)
    >>> stats = make_sliding_window_fit(
    ...     df=data,
    ...     group_columns=['xBin', 'yBin'],
    ...     window_spec={'xBin': 2, 'yBin': 2},
    ...     fit_columns=['observable'],
    ...     predictor_columns=[],
    ...     fit_formula=None,  # No fit
    ...     aggregation_functions={'observable': ['mean', 'median', 'q10', 'q90']}
    ... )
    
    >>> # With selection mask
    >>> result = make_sliding_window_fit(
    ...     df=data,
    ...     selection=(data['quality_flag'] > 0) & (data['entries'] > 100),
    ...     ...
    ... )
    """
    # Implementation in sections below
    pass
```

**Implementation components:**

**0. Error/Warning Classes** (`_define_exceptions`)
```python
class InvalidWindowSpec(ValueError):
    """Raised when window specification is malformed or invalid."""
    pass

class PerformanceWarning(UserWarning):
    """Warning for suboptimal performance conditions."""
    pass
```

**1. Input validation** (`_validate_sliding_window_inputs`)
```python
def _validate_sliding_window_inputs(
    df: pd.DataFrame,
    group_columns: List[str],
    window_spec: Dict[str, Union[int, dict]],
    fit_columns: List[str],
    predictor_columns: List[str],
    selection: Optional[pd.Series],
    min_entries: int
) -> None:
    """
    Validate all inputs before processing.
    
    Checks:
    - All columns exist in df
    - group_columns are integer dtype (no floats in M7.1)
    - window_spec keys match group_columns
    - Window sizes are positive integers
    - min_entries > 0
    - selection has correct length if provided
    - No duplicate column names
    """
```

**2. Bin index map builder** (`_build_bin_index_map`)
```python
def _build_bin_index_map(
    df: pd.DataFrame,
    group_columns: List[str],
    selection: Optional[pd.Series]
) -> Dict[Tuple[int, ...], List[int]]:
    """
    Build hash map from bin coordinates to row indices.
    
    This is the foundation of the zero-copy accumulator (MEM-3).
    
    Parameters
    ----------
    df : pd.DataFrame
        Input data
    group_columns : List[str]
        Bin coordinate columns
    selection : Optional[pd.Series]
        Boolean mask to pre-filter rows
    
    Returns
    -------
    Dict[Tuple[int, ...], List[int]]
        Mapping: (xBin, y2xBin, z2xBin, ...) -> [row_idx1, row_idx2, ...]
    
    Example
    -------
    >>> df = pd.DataFrame({
    ...     'xBin': [0, 0, 1, 1, 1],
    ...     'yBin': [0, 0, 0, 1, 1],
    ...     'value': [1, 2, 3, 4, 5]
    ... })
    >>> bin_map = _build_bin_index_map(df, ['xBin', 'yBin'], None)
    >>> bin_map
    {(0, 0): [0, 1], (1, 0): [2], (1, 1): [3, 4]}
    
    Notes
    -----
    - Selection mask applied once here (not repeated in aggregation)
    - Uses tuple keys for hashability
    - Preserves row order within each bin
    - Memory: O(N rows) overhead for index lists
    """
    # Apply selection mask if provided
    if selection is not None:
        df_selected = df[selection].copy()
    else:
        df_selected = df
    
    # Build mapping
    bin_map: Dict[Tuple[int, ...], List[int]] = {}
    for idx, row in df_selected[group_columns].iterrows():
        bin_key = tuple(row.values)
        if bin_key not in bin_map:
            bin_map[bin_key] = []
        bin_map[bin_key].append(idx)
    
    return bin_map
```

**3. Window neighbor generation** (`_generate_neighbor_offsets`, `_get_neighbor_bins`)
```python
def _generate_neighbor_offsets(
    window_spec: Dict[str, int]
) -> List[Tuple[int, ...]]:
    """
    Generate all offset combinations for window.
    
    Example:
        window_spec = {'xBin': 1, 'yBin': 1}
        Returns: [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1)]
        Total: 3^2 = 9 offsets
    """
    import itertools
    dims = list(window_spec.keys())
    ranges = [range(-window_spec[dim], window_spec[dim] + 1) for dim in dims]
    offsets = list(itertools.product(*ranges))
    return offsets

def _get_neighbor_bins(
    center_bin: Tuple[int, ...],
    offsets: List[Tuple[int, ...]],
    bin_ranges: Dict[str, Tuple[int, int]],
    boundary_mode: str = 'truncate'
) -> List[Tuple[int, ...]]:
    """
    Get valid neighbor bins for center, applying boundary conditions.
    
    M7.1: boundary_mode='truncate' only (clip to valid range)
    M7.2: adds 'mirror', 'periodic'
    """
    neighbors = []
    for offset in offsets:
        neighbor = tuple(c + o for c, o in zip(center_bin, offset))
        
        # Apply boundary condition (truncate only in M7.1)
        if boundary_mode == 'truncate':
            # Check if all coordinates within valid ranges
            valid = True
            for i, (dim, (min_val, max_val)) in enumerate(bin_ranges.items()):
                if not (min_val <= neighbor[i] <= max_val):
                    valid = False
                    break
            if valid:
                neighbors.append(neighbor)
        else:
            raise InvalidWindowSpec(f"Boundary mode '{boundary_mode}' not supported in M7.1")
    
    return neighbors
```

**4. Zero-copy aggregator** (`_aggregate_window_zerocopy`)
```python
def _aggregate_window_zerocopy(
    df: pd.DataFrame,
    center_bins: List[Tuple[int, ...]],
    bin_map: Dict[Tuple[int, ...], List[int]],
    window_spec: Dict[str, int],
    bin_ranges: Dict[str, Tuple[int, int]],
    fit_columns: List[str],
    aggregation_functions: Dict[str, List[str]],
    weights_column: Optional[str]
) -> pd.DataFrame:
    """
    Aggregate data for each center bin using zero-copy accumulator (MEM-3).
    
    This is the CORE algorithm. Prototype in pure NumPy (M7.1), JIT-compile in M7.2.
    
    Algorithm:
    1. For each center bin:
       a. Generate neighbor offsets (combinatorial)
       b. Apply boundary conditions to get valid neighbors
       c. Look up row indices for each neighbor from bin_map (zero-copy!)
       d. Aggregate values at those indices using NumPy views
       e. Compute requested statistics (mean, std, median, entries)
    2. Assemble results into DataFrame
    
    Memory efficiency:
    - No DataFrame replication (avoids 27-125× explosion)
    - Uses integer index slicing (df.iloc[row_indices])
    - NumPy aggregations on views
    
    Returns
    -------
    pd.DataFrame
        One row per center bin with aggregated statistics.
        Columns: group_columns, {target}_mean, {target}_std, {target}_median, {target}_entries,
                 effective_window_fraction, n_neighbors_used
    """
    # Pre-compute neighbor offsets (same for all centers)
    offsets = _generate_neighbor_offsets(window_spec)
    expected_neighbors = len(offsets)
    
    results = []
    for center_bin in center_bins:
        # Get valid neighbor bins
        neighbors = _get_neighbor_bins(center_bin, offsets, bin_ranges, 'truncate')
        
        # Collect row indices for all neighbors (ZERO-COPY!)
        row_indices = []
        for neighbor in neighbors:
            if neighbor in bin_map:
                row_indices.extend(bin_map[neighbor])
        
        if len(row_indices) == 0:
            # Empty window - skip or flag
            continue
        
        # Extract data at these indices (view, not copy)
        window_data = df.iloc[row_indices]
        
        # Compute aggregations
        agg_result = {'center_bin': center_bin}
        for target in fit_columns:
            values = window_data[target].values
            
            # Apply weights if specified
            if weights_column is not None:
                weights = window_data[weights_column].values
            else:
                weights = np.ones(len(values))
            
            # Compute requested aggregations
            agg_funcs = aggregation_functions.get(target, ['mean', 'std', 'entries', 'median'])
            for func in agg_funcs:
                if func == 'mean':
                    agg_result[f'{target}_mean'] = np.average(values, weights=weights)
                elif func == 'std':
                    agg_result[f'{target}_std'] = np.sqrt(np.average((values - np.average(values, weights=weights))**2, weights=weights))
                elif func == 'median':
                    agg_result[f'{target}_median'] = np.median(values)
                elif func == 'entries':
                    agg_result[f'{target}_entries'] = len(values)
                # Additional functions: q10, q90, mad, etc. (M7.2)
        
        # Quality metrics
        agg_result['effective_window_fraction'] = len(neighbors) / expected_neighbors
        agg_result['n_neighbors_used'] = len(neighbors)
        agg_result['n_rows_aggregated'] = len(row_indices)
        
        results.append(agg_result)
    
    return pd.DataFrame(results)
```

**5. Formula parsing** (`_parse_fit_formula`)
```python
def _parse_fit_formula(formula: str) -> Tuple[str, List[str]]:
    """
    Parse simple formula string without statsmodels dependency.
    
    Supports: 'target ~ predictor1 + predictor2 + ...'
    
    Examples:
        'dX ~ meanIDC' -> ('dX', ['meanIDC'])
        'dX ~ meanIDC + deltaIDC' -> ('dX', ['meanIDC', 'deltaIDC'])
    
    Raises:
        InvalidWindowSpec: If formula syntax invalid
    """
    import re
    
    # Pattern: target ~ pred1 + pred2 + ...
    match = re.match(r'^\s*(\w+)\s*~\s*(.+)\s*$', formula)
    if not match:
        raise InvalidWindowSpec(
            f"Invalid formula: '{formula}'. Expected format: 'target ~ predictor1 + predictor2'"
        )
    
    target = match.group(1).strip()
    predictors_str = match.group(2).strip()
    
    # Split by + and clean whitespace
    predictors = [p.strip() for p in predictors_str.split('+') if p.strip()]
    
    if not predictors:
        raise InvalidWindowSpec(f"No predictors found in formula: '{formula}'")
    
    return target, predictors
```

**6. Regression execution** (`_fit_window_regression`)
```python
def _fit_window_regression(
    aggregated_data: pd.DataFrame,
    bin_map: Dict[Tuple[int, ...], List[int]],
    df: pd.DataFrame,
    fit_formula: Union[str, Callable],
    fit_columns: List[str],
    predictor_columns: List[str],
    min_entries: int,
    weights_column: Optional[str]
) -> pd.DataFrame:
    """
    Fit regression for each center bin using aggregated data.
    
    Reuses v4 fit logic (sklearn OLS or Huber) instead of statsmodels.
    
    For each center bin:
    1. Check if n_entries >= min_entries
    2. If yes:
       - Parse formula (or use callable)
       - Extract X (predictors) and y (target) from window data
       - Call existing _fit_linear_robust from v4 code
       - Store coefficients, R², RMSE
    3. If no: Flag as insufficient data
    """
    from sklearn.linear_model import LinearRegression, HuberRegressor
    
    results = []
    for idx, row in aggregated_data.iterrows():
        center_bin = row['center_bin']
        n_entries = row.get(f'{fit_columns[0]}_entries', 0)
        
        result = {'center_bin': center_bin}
        
        if n_entries < min_entries:
            # Insufficient data - skip fit
            result['quality_flag'] = 'insufficient_stats'
            for target in fit_columns:
                result[f'{target}_r_squared'] = np.nan
                result[f'{target}_intercept'] = np.nan
                for pred in predictor_columns:
                    result[f'{target}_slope_{pred}'] = np.nan
            results.append(result)
            continue
        
        # Get row indices for this window
        neighbors = _get_neighbor_bins(center_bin, ...)  # From earlier
        row_indices = []
        for neighbor in neighbors:
            if neighbor in bin_map:
                row_indices.extend(bin_map[neighbor])
        
        window_data = df.iloc[row_indices]
        
        # Fit each target
        for target in fit_columns:
            try:
                # Prepare data
                X = window_data[predictor_columns].values
                y = window_data[target].values
                
                if weights_column:
                    sample_weight = window_data[weights_column].values
                else:
                    sample_weight = np.ones(len(y))
                
                # Fit using sklearn (reuse v4 pattern)
                model = LinearRegression()  # Or HuberRegressor for robust
                model.fit(X, y, sample_weight=sample_weight)
                
                # Store coefficients
                result[f'{target}_intercept'] = model.intercept_
                for i, pred in enumerate(predictor_columns):
                    result[f'{target}_slope_{pred}'] = model.coef_[i]
                
                # Diagnostics
                y_pred = model.predict(X)
                ss_res = np.sum((y - y_pred)**2)
                ss_tot = np.sum((y - np.mean(y))**2)
                result[f'{target}_r_squared'] = 1 - (ss_res / ss_tot) if ss_tot > 0 else np.nan
                result[f'{target}_rmse'] = np.sqrt(np.mean((y - y_pred)**2))
                result[f'{target}_n_fitted'] = len(y)
                
            except Exception as e:
                # Fit failed - flag
                result['quality_flag'] = f'fit_failed_{target}'
                result[f'{target}_r_squared'] = np.nan
        
        results.append(result)
    
    return pd.DataFrame(results)
```

**7. Result assembly** (`_assemble_results`)
```python
def _assemble_results(
    aggregated_stats: pd.DataFrame,
    fit_results: pd.DataFrame,
    group_columns: List[str],
    window_spec: Dict[str, Union[int, dict]],
    binning_formulas: Optional[Dict[str, str]],
    backend: str,
    computation_time: float
) -> pd.DataFrame:
    """
    Combine aggregated stats + fit results into final DataFrame.
    
    Add metadata to .attrs for provenance (RootInteractive compatibility).
    """
    import json
    
    # Merge aggregated stats and fit results
    result = aggregated_stats.merge(fit_results, on='center_bin', how='left')
    
    # Expand center_bin tuple back to individual columns
    for i, col in enumerate(group_columns):
        result[col] = result['center_bin'].apply(lambda x: x[i])
    result = result.drop('center_bin', axis=1)
    
    # Add metadata
    result.attrs = {
        'window_spec_json': json.dumps(window_spec),
        'binning_formulas_json': json.dumps(binning_formulas) if binning_formulas else None,
        'boundary_mode_per_dim': {dim: 'truncate' for dim in group_columns},  # M7.1: all truncate
        'backend_used': backend,
        'computation_time_sec': computation_time,
        'group_columns': group_columns,
        'python_version': sys.version
    }
    
    return result
```

**Design principles:**
- **Zero-copy accumulator (MEM-3):** Core innovation to avoid memory explosion
- **Pure NumPy + sklearn:** No statsmodels dependency; reuse v4 fit logic
- **Readable code:** Clear separation of concerns, well-documented functions
- **Testable:** Each component function independently testable
- **Python 3.9.6 compatible:** Use `List[str]`, `Dict[str, int]` (not `list[str]`, `dict[str, int]`)
- **Template for M7.2:** Structure enables easy Numba JIT compilation
- **Performance warnings:** Emit `PerformanceWarning` when falling back to numpy or large windows

#### D7.1.2: Test Suite

**File:** `test_groupby_regression_sliding_window.py`

**Test coverage (minimum 20 tests, up from 15):**

```python
from typing import List, Dict, Tuple
import pytest
import pandas as pd
import numpy as np
from groupby_regression_sliding_window import (
    make_sliding_window_fit, InvalidWindowSpec, PerformanceWarning
)

# Basic functionality (5 tests)
def test_sliding_window_basic_3d():
    """Test basic 3D sliding window with ±1 neighbors."""
    
def test_sliding_window_aggregation():
    """Verify mean, std, median, entries calculations."""
    
def test_sliding_window_linear_fit():
    """Verify linear regression coefficients match expected."""
    
def test_empty_window_handling():
    """Handle bins with no neighbors gracefully."""
    
def test_min_entries_enforcement():
    """Skip bins below min_entries threshold."""

# Input validation (6 tests, was 5)
def test_invalid_window_spec():
    """Reject malformed window_spec."""
    
def test_missing_columns():
    """Error on missing group/fit/predictor columns."""
    
def test_float_bins_rejected():
    """Reject float bin coordinates in M7.1 (integer only)."""
    
def test_negative_min_entries():
    """Validate min_entries > 0."""
    
def test_invalid_fit_formula():
    """Parse errors in fit_formula string."""

def test_selection_mask_length_mismatch():
    """Error if selection mask has wrong length."""

# Edge cases (5 tests)
def test_single_bin_dataset():
    """Handle df with only one unique bin."""
    
def test_all_sparse_bins():
    """Dataset where all bins have <min_entries."""
    
def test_boundary_bins():
    """Verify truncation at grid boundaries."""
    
def test_multi_target_fit():
    """Fit multiple targets simultaneously."""
    
def test_weighted_aggregation():
    """Use weights_column in aggregation and fitting."""

# New tests from GPT review (5 tests)
def test_selection_mask():
    """Test selection mask filters rows before windowing."""
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=20)
    selection = df['value'] > df['value'].median()
    
    result = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'], {'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'], fit_formula='value ~ x',
        selection=selection
    )
    # Verify only selected rows used
    assert result is not None

def test_metadata_presence():
    """Verify output contains required metadata in .attrs."""
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    result = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'], {'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value'], predictor_columns=['x'],
        binning_formulas={'xBin': 'x / 0.5'}
    )
    
    # Check required metadata
    assert 'window_spec_json' in result.attrs
    assert 'binning_formulas_json' in result.attrs
    assert 'boundary_mode_per_dim' in result.attrs
    assert 'backend_used' in result.attrs
    assert 'computation_time_sec' in result.attrs

def test_performance_warning_numpy_fallback():
    """Emit PerformanceWarning when backend='numba' unavailable."""
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=10)
    
    with pytest.warns(PerformanceWarning, match="Numba backend unavailable"):
        result = make_sliding_window_fit(
            df, ['xBin', 'yBin', 'zBin'], {'xBin': 1, 'yBin': 1, 'zBin': 1},
            fit_columns=['value'], predictor_columns=['x'],
            backend='numba'  # Will fall back to numpy in M7.1
        )

def test_window_size_zero_equivalence_with_v4():
    """Window size = 0 should match v4 groupby results (no neighbors)."""
    from groupby_regression_optimized import make_parallel_fit_v4
    
    df = _make_synthetic_3d_grid(n_bins_per_dim=5, entries_per_bin=50)
    df['weight'] = 1.0
    
    # Sliding window with size 0 (no aggregation, each bin standalone)
    sw_result = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'], {'xBin': 0, 'yBin': 0, 'zBin': 0},
        fit_columns=['value'], predictor_columns=['x'],
        fit_formula='value ~ x'
    )
    
    # v4 groupby (no windowing)
    v4_result, v4_params = make_parallel_fit_v4(
        df, gb_columns=['xBin', 'yBin', 'zBin'],
        fit_columns=['value'], linear_columns=['x'],
        median_columns=[], weights='weight', suffix='_v4',
        selection=pd.Series(True, index=df.index), min_stat=3
    )
    
    # Compare coefficients (should be identical)
    merged = sw_result.merge(v4_params, on=['xBin', 'yBin', 'zBin'])
    np.testing.assert_allclose(
        merged['value_slope_x'],
        merged['value_slope_x_v4'],
        rtol=1e-6, atol=1e-8
    )

def test_multi_target_column_naming():
    """Verify multi-target output has correct column names."""
    df = _make_synthetic_3d_grid(n_bins_per_dim=3, entries_per_bin=20)
    df['value2'] = df['value'] * 2 + np.random.normal(0, 0.1, len(df))
    
    result = make_sliding_window_fit(
        df, ['xBin', 'yBin', 'zBin'], {'xBin': 1, 'yBin': 1, 'zBin': 1},
        fit_columns=['value', 'value2'], predictor_columns=['x'],
        fit_formula='target ~ x'
    )
    
    # Check column naming convention (matches v4)
    expected_cols = [
        'value_mean', 'value_std', 'value_median', 'value_entries',
        'value_slope_x', 'value_intercept', 'value_r_squared',
        'value2_mean', 'value2_std', 'value2_median', 'value2_entries',
        'value2_slope_x', 'value2_intercept', 'value2_r_squared'
    ]
    for col in expected_cols:
        assert col in result.columns, f"Missing column: {col}"

# Reference test for correctness (new)
def test_reference_full_expansion_2d():
    """
    Property test: Compare zero-copy aggregator with naive full expansion.
    
    For a tiny 2D grid, explicitly expand all neighbors and verify
    zero-copy gives identical mean/count.
    """
    # Create 3×3 grid with known values
    df = pd.DataFrame({
        'xBin': [0, 0, 1, 1, 2, 2],
        'yBin': [0, 1, 0, 1, 0, 1],
        'value': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    })
    
    # Zero-copy result
    result_zerocopy = make_sliding_window_fit(
        df, ['xBin', 'yBin'], {'xBin': 1, 'yBin': 1},
        fit_columns=['value'], predictor_columns=[],
        fit_formula=None  # Aggregation only
    )
    
    # Reference: naive full expansion (warning: slow, only for small test)
    result_reference = _reference_full_expansion_aggregator(
        df, ['xBin', 'yBin'], {'xBin': 1, 'yBin': 1}, ['value']
    )
    
    # Compare means and counts (should be identical)
    merged = result_zerocopy.merge(result_reference, on=['xBin', 'yBin'], suffixes=('', '_ref'))
    np.testing.assert_allclose(merged['value_mean'], merged['value_mean_ref'], rtol=1e-10)
    np.testing.assert_array_equal(merged['value_entries'], merged['value_entries_ref'])

def _reference_full_expansion_aggregator(
    df: pd.DataFrame,
    group_columns: List[str],
    window_spec: Dict[str, int],
    fit_columns: List[str]
) -> pd.DataFrame:
    """
    Reference implementation using full DataFrame expansion (naive, slow).
    
    Only for testing correctness on small datasets.
    """
    import itertools
    
    # Get unique center bins
    centers = df[group_columns].drop_duplicates()
    
    # Generate offsets
    offsets = list(itertools.product(*[range(-w, w+1) for w in window_spec.values()]))
    
    # Expand: for each center, replicate row for each offset
    expanded_rows = []
    for _, center in centers.iterrows():
        for offset in offsets:
            neighbor = {group_columns[i]: center[group_columns[i]] + offset[i] 
                       for i in range(len(group_columns))}
            expanded_rows.append({**neighbor, 'center_xBin': center['xBin'], 'center_yBin': center['yBin']})
    
    expanded = pd.DataFrame(expanded_rows)
    
    # Merge with original data
    merged = expanded.merge(df, on=group_columns, how='left')
    
    # Group by center and aggregate
    result = merged.groupby(['center_xBin', 'center_yBin']).agg({
        fit_columns[0]: ['mean', 'count']
    }).reset_index()
    
    result.columns = ['xBin', 'yBin', f'{fit_columns[0]}_mean_ref', f'{fit_columns[0]}_entries_ref']
    return result
```

**Test data generators:**
```python
def _make_synthetic_3d_grid(
    n_bins_per_dim: int = 10, 
    entries_per_bin: int = 50, 
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic 3D integer grid with known linear relationship.
    
    y = 2*x + noise
    
    Returns DataFrame with columns: xBin, yBin, zBin, x, value, weight
    """
    rng = np.random.default_rng(seed)
    
    # Create all bin combinations
    bins = np.array(list(itertools.product(
        range(n_bins_per_dim),
        range(n_bins_per_dim),
        range(n_bins_per_dim)
    )))
    
    # Replicate each bin entries_per_bin times
    bins_expanded = np.repeat(bins, entries_per_bin, axis=0)
    
    df = pd.DataFrame(bins_expanded, columns=['xBin', 'yBin', 'zBin'])
    df = df.astype(np.int32)
    
    # Generate predictor and target with known relationship
    df['x'] = rng.normal(0, 1.0, len(df))
    df['value'] = 2.0 * df['x'] + rng.normal(0, 0.5, len(df))
    df['weight'] = 1.0
    
    return df
    
def _make_sparse_grid(
    sparsity: float = 0.3, 
    **kwargs
) -> pd.DataFrame:
    """Generate grid with specified fraction of empty bins."""
    df = _make_synthetic_3d_grid(**kwargs)
    
    # Randomly drop bins to create sparsity
    unique_bins = df[['xBin', 'yBin', 'zBin']].drop_duplicates()
    n_bins_to_drop = int(len(unique_bins) * sparsity)
    
    rng = np.random.default_rng(kwargs.get('seed', 42))
    bins_to_drop = unique_bins.sample(n=n_bins_to_drop, random_state=rng)
    
    # Remove rows belonging to dropped bins
    df = df.merge(bins_to_drop, on=['xBin', 'yBin', 'zBin'], how='left', indicator=True)
    df = df[df['_merge'] == 'left_only'].drop('_merge', axis=1)
    
    return df
    
def _make_boundary_test_grid() -> pd.DataFrame:
    """Small grid for testing boundary condition handling."""
    # 3×3×3 grid with entries at boundaries
    df = pd.DataFrame({
        'xBin': [0, 0, 0, 1, 1, 1, 2, 2, 2],
        'yBin': [0, 1, 2, 0, 1, 2, 0, 1, 2],
        'zBin': [1, 1, 1, 1, 1, 1, 1, 1, 1],
        'x': np.random.normal(0, 1, 9),
        'value': np.random.normal(10, 2, 9)
    })
    return df
```

#### D7.1.3: Basic Benchmark

**File:** `bench_sliding_window.py`

**Scenarios (3 simple cases):**

```python
# Scenario 1: Small 3D grid (quick validation)
bench_small_3d = {
    'n_bins': (10, 10, 10),  # 1,000 bins
    'entries_per_bin': 20,
    'window_size': 1,        # ±1 = 3³ = 27 neighbors
    'expected_time': '<10s'
}

# Scenario 2: Medium 3D grid (realistic test data scale)
bench_medium_3d = {
    'n_bins': (50, 20, 30),  # 30,000 bins
    'entries_per_bin': 100,
    'window_size': 1,
    'expected_time': '<2min'
}

# Scenario 3: Sparse grid (stress test)
bench_sparse_3d = {
    'n_bins': (100, 50, 50), # 250,000 bins
    'entries_per_bin': 10,
    'sparsity': 0.5,         # 50% empty
    'window_size': 2,        # ±2 = 5³ = 125 neighbors
    'expected_time': '<5min'
}
```

**Metrics to capture and print (per GPT review):**

```python
class BenchmarkResult:
    """Standard benchmark output format."""
    
    scenario_name: str
    total_runtime_sec: float
    n_bins_total: int
    n_bins_fitted: int
    n_bins_skipped: int
    bins_per_sec: float
    peak_memory_mb: float
    avg_window_size: float
    
    def print_summary(self):
        """Print formatted summary for README."""
        print(f"Scenario: {self.scenario_name}")
        print(f"  Total bins: {self.n_bins_total:,}")
        print(f"  Fitted: {self.n_bins_fitted:,} ({100*self.n_bins_fitted/self.n_bins_total:.1f}%)")
        print(f"  Skipped: {self.n_bins_skipped:,} ({100*self.n_bins_skipped/self.n_bins_total:.1f}%)")
        print(f"  Runtime: {self.total_runtime_sec:.2f}s")
        print(f"  Throughput: {self.bins_per_sec:.1f} bins/sec")
        print(f"  Peak memory: {self.peak_memory_mb:.1f} MB")
        print(f"  Avg window size: {self.avg_window_size:.1f} neighbors")
```

**Output example:**
```
Scenario: medium_3d
  Total bins: 30,000
  Fitted: 29,450 (98.2%)
  Skipped: 550 (1.8%)
  Runtime: 45.32s
  Throughput: 662.0 bins/sec
  Peak memory: 180.5 MB
  Avg window size: 24.3 neighbors
```

---

### M7.1 Review Form

**Reviewer:** _________________ (GPT-4 / Gemini / MI)  
**Date:** _________________  
**Review Type:** □ Code  □ Tests  □ Benchmarks  □ Documentation

#### Functionality Review

| Criterion | Pass | Fail | Notes |
|-----------|------|------|-------|
| API signature matches spec | ☐ | ☐ | |
| Window generation correct | ☐ | ☐ | |
| Aggregation functions work | ☐ | ☐ | |
| Linear fitting correct | ☐ | ☐ | |
| Sparse bin handling | ☐ | ☐ | |
| Boundary truncation | ☐ | ☐ | |

#### Code Quality Review

| Criterion | Pass | Fail | Notes |
|-----------|------|------|-------|
| Clear function separation | ☐ | ☐ | |
| Type hints present | ☐ | ☐ | |
| Docstrings complete | ☐ | ☐ | |
| Input validation robust | ☐ | ☐ | |
| Error messages helpful | ☐ | ☐ | |
| No code duplication | ☐ | ☐ | |

#### Test Coverage Review

| Criterion | Pass | Fail | Notes |
|-----------|------|------|-------|
| All basic tests pass | ☐ | ☐ | |
| Edge cases covered | ☐ | ☐ | |
| Validation tests present | ☐ | ☐ | |
| Test data generators work | ☐ | ☐ | |
| Coverage ≥80% | ☐ | ☐ | |

#### Performance Review

| Criterion | Pass | Fail | Notes |
|-----------|------|------|-------|
| Small benchmark <10s | ☐ | ☐ | |
| Medium benchmark <2min | ☐ | ☐ | |
| Sparse benchmark <5min | ☐ | ☐ | |
| Memory usage <500MB | ☐ | ☐ | |

#### Overall Assessment

**Strengths:**
- 
- 
- 

**Issues Found:**
- 
- 
- 

**Required Changes:**
- [ ] Critical: _________________________
- [ ] Major: _________________________
- [ ] Minor: _________________________

**Recommendation:**
- ☐ Approve for M7.2
- ☐ Approve with minor changes
- ☐ Major revision needed

**Signature:** _________________ **Date:** _________________

---

## Milestone 7.2: Production Features

**Target:** Mid November 2025  
**Focus:** Performance optimization and advanced features

### Deliverables

#### D7.2.1: Numba Optimization

**Goal:** 10-100× speedup over M7.1 numpy implementation

**Components:**

1. **JIT-compiled window kernel** (`_sliding_window_kernel_numba`)
   ```python
   @numba.jit(nopython=True, parallel=True)
   def _sliding_window_kernel_numba(
       center_bins: np.ndarray,      # (n_centers, n_dims)
       all_bins: np.ndarray,          # (n_rows, n_dims)
       all_values: np.ndarray,        # (n_rows, n_targets)
       window_sizes: np.ndarray,      # (n_dims,)
       output_aggregated: np.ndarray  # (n_centers, n_targets, n_stats)
   ):
       """
       Numba kernel for sliding window aggregation.
       
       For each center bin:
       - Find all rows within window
       - Compute mean, std, count for each target
       - Write to output_aggregated
       """
   ```

2. **Dense grid accelerator** (`_build_dense_lookup`)
   - For small grids (total_bins < 10M), use dense ND-array lookup
   - O(1) neighbor identification instead of O(N) iteration
   - Trade memory for speed

3. **Backend selection logic**
   ```python
   if backend == 'numba' and numba_available:
       return _sliding_window_fit_numba(...)
   elif backend == 'numpy' or not numba_available:
       return _sliding_window_fit_numpy(...)  # M7.1 implementation
   else:
       raise ValueError(f"Unknown backend: {backend}")
   ```

#### D7.2.2: Boundary Modes

**Add mirror and periodic boundaries:**

1. **Mirror boundary** (`_apply_mirror_boundary`)
   ```python
   def _reflect_bin_index(idx: int, max_idx: int) -> int:
       """Reflect negative indices: -1→1, -2→2, etc."""
       if idx < 0:
           return -idx
       elif idx > max_idx:
           return 2*max_idx - idx
       return idx
   ```

2. **Periodic boundary** (`_apply_periodic_boundary`)
   ```python
   def _wrap_bin_index(idx: int, max_idx: int) -> int:
       """Wrap around: -1→max_idx, max_idx+1→0."""
       return idx % (max_idx + 1)
   ```

3. **Rich window_spec support**
   ```python
   window_spec = {
       'xBin': {'size': 2, 'boundary': 'truncate'},
       'phiBin': {'size': 10, 'boundary': 'periodic'},
       'y2xBin': {'size': 1, 'boundary': 'mirror'}
   }
   ```

#### D7.2.3: Weighting Schemes

**Add distance-based and Gaussian weighting:**

1. **Distance weighting** (`_compute_distance_weights`)
   ```python
   def _compute_distance_weights(
       center: np.ndarray,
       neighbors: np.ndarray,
       scheme: str = 'distance'
   ) -> np.ndarray:
       """
       Compute weights based on bin-space distance.
       
       'distance': w = 1 / (1 + d)
       'gaussian': w = exp(-d² / 2σ²)
       """
   ```

2. **Update aggregation to use weights**
   - Weighted mean: Σ(w_i * x_i) / Σ(w_i)
   - Weighted std: sqrt(Σ(w_i * (x_i - μ)²) / Σ(w_i))

#### D7.2.4: Extended Test Suite

**Add 20+ tests for new features:**

```python
# Boundary modes (6 tests)
def test_mirror_boundary_1d()
def test_mirror_boundary_3d()
def test_periodic_boundary_phi()
def test_mixed_boundaries()
def test_boundary_at_grid_limits()
def test_periodic_wraparound_distance()

# Weighting schemes (6 tests)
def test_uniform_weighting()
def test_distance_weighting()
def test_gaussian_weighting()
def test_custom_sigma_gaussian()
def test_weighted_mean_accuracy()
def test_weighted_fit_coefficients()

# Numba backend (4 tests)
def test_numba_vs_numpy_equivalence()
def test_numba_performance_gain()
def test_numba_parallel_speedup()
def test_numba_fallback_on_error()

# Integration (4 tests)
def test_real_tpc_data_subset()
def test_multiple_targets_advanced()
def test_rich_window_spec_parsing()
def test_end_to_end_pipeline()
```

#### D7.2.5: Production Benchmarks

**File:** `bench_sliding_window_production.py`

**Scenarios matching spec requirements:**

```python
# Realistic TPC scenario
bench_tpc_spatial = {
    'name': 'TPC Spatial (5 maps)',
    'data_source': 'tpc_realistic_test.parquet',
    'n_rows': 405_423,
    'n_maps': 5,
    'dimensions': {'xBin': 152, 'y2xBin': 20, 'z2xBin': 28},
    'window': {'xBin': 1, 'y2xBin': 1, 'z2xBin': 1},
    'target_time': '<1min',
    'target_memory': '<2GB'
}

# Production scale
bench_tpc_temporal = {
    'name': 'TPC Temporal (90 maps)',
    'n_rows': 7_000_000,
    'n_maps': 90,
    'dimensions': {'xBin': 152, 'y2xBin': 20, 'z2xBin': 28},
    'window': {'xBin': 1, 'y2xBin': 1, 'z2xBin': 1},
    'target_time': '<30min',
    'target_memory': '<4GB'
}

# High-dimensional tracking performance
bench_tracking_5d = {
    'name': '5D Tracking Performance',
    'n_rows': 10_000_000,
    'dimensions': {
        'pTBin': 50, 'etaBin': 40, 'phiBin': 36,
        'occBin': 20, 'timeBin': 100
    },
    'window': {'pTBin': 1, 'etaBin': 1, 'phiBin': 1, 'occBin': 1, 'timeBin': 3},
    'target_time': '<1hr',
    'target_memory': '<4GB'
}
```

**Comparison table:**
```
| Backend  | TPC Spatial | TPC Temporal | 5D Tracking | Notes          |
|----------|-------------|--------------|-------------|----------------|
| numpy    | 45s         | 27min        | OOM         | M7.1 baseline  |
| numba    | 0.8s        | 15min        | 45min       | Target: 10-100×|
| v4-reuse | 0.5s        | 8min         | 30min       | If integrated  |
```

---

### M7.2 Review Form

**Reviewer:** _________________ (GPT-4 / Gemini / MI)  
**Date:** _________________

#### Performance Review

| Criterion | Target | Actual | Pass/Fail | Notes |
|-----------|--------|--------|-----------|-------|
| TPC Spatial <1min | 60s | | ☐/☐ | |
| TPC Temporal <30min | 1800s | | ☐/☐ | |
| Memory <4GB | 4096MB | | ☐/☐ | |
| Numba speedup ≥10× | 10× | | ☐/☐ | |

#### Feature Completeness

| Feature | Implemented | Tested | Pass | Notes |
|---------|-------------|--------|------|-------|
| Mirror boundary | ☐ | ☐ | ☐ | |
| Periodic boundary | ☐ | ☐ | ☐ | |
| Distance weighting | ☐ | ☐ | ☐ | |
| Gaussian weighting | ☐ | ☐ | ☐ | |
| Numba backend | ☐ | ☐ | ☐ | |
| Rich window_spec | ☐ | ☐ | ☐ | |

#### Integration Testing

| Test | Pass | Notes |
|------|------|-------|
| Real TPC data | ☐ | |
| vs v4 baseline | ☐ | |
| Mixed boundaries | ☐ | |
| Weighted regression | ☐ | |

**Overall Assessment:**

**Recommendation:**
- ☐ Approve for M7.3
- ☐ Approve with changes
- ☐ Major revision needed

**Signature:** _________________ **Date:** _________________

---

## Milestone 7.3: Documentation & Polish

**Target:** Late November 2025  
**Focus:** User documentation, examples, final validation

### Deliverables

#### D7.3.1: User Guide

**File:** `docs/sliding_window_user_guide.md`

**Sections:**

1. **Quick Start** (5 min read)
   - Minimal example with real data
   - Common use cases (TPC, tracking)
   
2. **Conceptual Overview** (10 min read)
   - Why sliding windows?
   - When to use vs. standard groupby
   - Boundary conditions explained
   
3. **API Reference** (reference)
   - All parameters documented
   - Examples for each parameter
   - Common patterns and idioms
   
4. **Advanced Topics** (20 min read)
   - Custom fit functions
   - Performance optimization
   - Memory management
   - Integration with RootInteractive
   
5. **Troubleshooting** (reference)
   - Common errors and solutions
   - Performance debugging
   - Data preparation tips

#### D7.3.2: Example Notebooks

**Files:** `examples/sliding_window_*.ipynb`

1. **`sliding_window_intro.ipynb`**
   - Basic 3D spatial example
   - Visualizations of window aggregation
   - Step-by-step walkthrough

2. **`tpc_distortion_workflow.ipynb`**
   - Realistic TPC calibration workflow
   - Load real data, fit, visualize
   - Integration with RootInteractive

3. **`tracking_performance.ipynb`**
   - 5D tracking performance parameterization
   - Multi-target fitting
   - QA plots and diagnostics

4. **`custom_fits.ipynb`**
   - Polynomial regression example
   - User-defined fit function
   - Non-linear models

#### D7.3.3: README Update

**File:** `README.md` (update)

Add new section:

```markdown
## Sliding Window Regression (v2.1+)

For multi-dimensional sparse binned data analysis, `make_sliding_window_fit` 
enables local PDF estimation and regression by aggregating neighboring bins.

### Quick Example

```python
from groupby_regression_sliding_window import make_sliding_window_fit

# Define window: ±1 bin in each dimension
window_spec = {'xBin': 1, 'y2xBin': 1, 'z2xBin': 1}

# Fit dX ~ meanIDC for each spatial bin using neighbors
result = make_sliding_window_fit(
    df=tpc_data,
    group_columns=['xBin', 'y2xBin', 'z2xBin'],
    window_spec=window_spec,
    fit_columns=['dX', 'dY', 'dZ'],
    predictor_columns=['meanIDC', 'deltaIDC'],
    fit_formula='target ~ meanIDC + deltaIDC',
    min_entries=10,
    backend='numba'
)
```

### Use Cases

- **ALICE TPC distortion maps:** Smooth spatial corrections with temporal evolution
- **Tracking performance:** Resolution and bias parameterization in 5D+ spaces
- **Particle physics:** Invariant mass spectra in multi-dimensional kinematic bins

[See full documentation](docs/sliding_window_user_guide.md)
```

#### D7.3.4: API Documentation

**File:** `groupby_regression_sliding_window.py` (complete docstrings)

Ensure every public function has:
- One-line summary
- Detailed description
- Parameters (type, description, default)
- Returns (type, description)
- Raises (exception types and conditions)
- Examples (minimal working code)
- See Also (related functions)
- Notes (important caveats)

#### D7.3.5: Final Validation

**Validation checklist:**

```python
# Test matrix
test_matrix = {
    'dimensionality': [3, 4, 5, 6],
    'window_sizes': [1, 2, 3],
    'boundary_modes': ['truncate', 'mirror', 'periodic'],
    'weighting': ['uniform', 'distance', 'gaussian'],
    'backends': ['numpy', 'numba'],
    'data_scales': ['small', 'medium', 'production']
}

# Run full test suite
pytest test_groupby_regression_sliding_window.py -v --cov

# Run all benchmarks
python bench_sliding_window_production.py --full

# Performance regression check vs v4 baseline
python bench_comparison_v4_vs_sliding_window.py
```

---

### M7.3 Review Form

**Reviewer:** _________________ (GPT-4 / Gemini / MI)  
**Date:** _________________

#### Documentation Review

| Criterion | Complete | Clear | Accurate | Notes |
|-----------|----------|-------|----------|-------|
| User guide | ☐ | ☐ | ☐ | |
| API docstrings | ☐ | ☐ | ☐ | |
| Example notebooks | ☐ | ☐ | ☐ | |
| README update | ☐ | ☐ | ☐ | |
| Troubleshooting | ☐ | ☐ | ☐ | |

#### Completeness Review

| Feature | Implemented | Tested | Documented | Pass |
|---------|-------------|--------|------------|------|
| 3D-6D support | ☐ | ☐ | ☐ | ☐ |
| All boundary modes | ☐ | ☐ | ☐ | ☐ |
| All weighting schemes | ☐ | ☐ | ☐ | ☐ |
| Linear regression | ☐ | ☐ | ☐ | ☐ |
| Custom fit functions | ☐ | ☐ | ☐ | ☐ |
| Sparse data handling | ☐ | ☐ | ☐ | ☐ |
| Numba optimization | ☐ | ☐ | ☐ | ☐ |

#### Quality Gates

| Gate | Pass | Fail | Notes |
|------|------|------|-------|
| All tests pass | ☐ | ☐ | |
| Coverage ≥85% | ☐ | ☐ | |
| Benchmarks meet targets | ☐ | ☐ | |
| No critical bugs | ☐ | ☐ | |
| Docs reviewed | ☐ | ☐ | |
| Examples work | ☐ | ☐ | |

**Release Readiness:**
- ☐ Approve for v2.1.0 tag
- ☐ Minor issues to fix
- ☐ Not ready for release

**Signature:** _________________ **Date:** _________________

---

## Technical Architecture

### File Structure

```
groupby_regression/
├── groupby_regression.py                    # Existing (v2.0.0)
├── groupby_regression_optimized.py          # Existing (v2.0.0)
├── groupby_regression_sliding_window.py     # NEW (M7.1)
│   ├── make_sliding_window_fit()            # Main API
│   ├── _validate_inputs()
│   ├── _generate_window_bins()
│   ├── _aggregate_window_data()
│   ├── _fit_window_regression()
│   └── _assemble_results()
│
├── test_groupby_regression_sliding_window.py # NEW (M7.1)
├── bench_sliding_window.py                   # NEW (M7.1)
├── bench_sliding_window_production.py        # NEW (M7.2)
│
└── docs/
    ├── sliding_window_user_guide.md          # NEW (M7.3)
    └── examples/
        ├── sliding_window_intro.ipynb        # NEW (M7.3)
        ├── tpc_distortion_workflow.ipynb     # NEW (M7.3)
        ├── tracking_performance.ipynb        # NEW (M7.3)
        └── custom_fits.ipynb                 # NEW (M7.3)
```

### Code Reuse Strategy

**Leverage v2.0.0 infrastructure:**

1. **From `groupby_regression_optimized.py`:**
   - Numba compilation patterns
   - Parallel execution logic
   - Memory management utilities
   - Diagnostic collection framework

2. **From `groupby_regression.py`:**
   - Formula parsing (`_parse_fit_formula`)
   - Robust fitting logic (`_robust_fit_single_group`)
   - Parameter validation patterns
   - Output DataFrame assembly

**New components specific to sliding window:**
- Window neighbor generation (multi-dimensional)
- Boundary condition handling (truncate/mirror/periodic)
- Distance-based weighting
- Sparse bin aggregation

---

## Risk Management

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Memory explosion** (27-125× expansion) | High | Use zero-copy accumulator (MEM-3), partitioning |
| **Numba compatibility issues** | Medium | Numpy fallback, thorough testing |
| **Performance targets unmet** | High | Phased optimization, early benchmarks |
| **Complex boundary logic bugs** | Medium | Extensive edge case tests |

### Schedule Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Scope creep | Medium | Strict milestone boundaries, defer non-critical features |
| Integration issues with v4 | Medium | Early compatibility tests |
| Review cycle delays | Low | Clear review criteria, async reviews |

---

## Success Criteria

### Functional Success

- ✅ All 15+ M7.1 tests pass
- ✅ All 35+ M7.2 tests pass
- ✅ Support 3D-6D dimensionality
- ✅ All boundary modes work correctly
- ✅ Linear regression coefficients accurate to 1e-6
- ✅ Sparse data handled gracefully (no crashes)

### Performance Success

- ✅ TPC Spatial (405k rows, ±1 window): <1 minute
- ✅ TPC Temporal (7M rows, ±1 window): <30 minutes
- ✅ Memory usage: <4GB for all benchmarks
- ✅ Numba speedup: ≥10× over numpy baseline

### Quality Success

- ✅ Test coverage: ≥85%
- ✅ Documentation: Complete user guide + 4 example notebooks
- ✅ Zero critical bugs at release
- ✅ All review forms approved by MI + at least one AI reviewer

---

## Next Steps

1. **MI + Claude:** Review this plan, provide feedback
2. **GPT + Gemini:** Review plan for completeness, identify gaps
3. **All:** Approve to proceed OR request revisions
4. **Claude:** Begin M7.1 implementation upon approval

---

**Plan Version:** 1.0  
**Status:** 🟡 Awaiting Review  
**Approvals Required:** MI (mandatory), GPT or Gemini (at least one)

---

## Plan Review Form

**Reviewer:** _________________ (MI / GPT-4 / Gemini)  
**Date:** _________________

### Clarity & Completeness

| Aspect | Clear | Complete | Notes |
|--------|-------|----------|-------|
| Overall strategy | ☐ | ☐ | |
| Milestone scope | ☐ | ☐ | |
| Deliverables defined | ☐ | ☐ | |
| Success criteria | ☐ | ☐ | |
| Risk mitigation | ☐ | ☐ | |

### Technical Soundness

| Aspect | Sound | Concerns | Notes |
|--------|-------|----------|-------|
| Architecture | ☐ | ☐ | |
| Code reuse strategy | ☐ | ☐ | |
| Testing approach | ☐ | ☐ | |
| Performance plan | ☐ | ☐ | |

### Feasibility

| Aspect | Feasible | Concerns | Notes |
|--------|----------|----------|-------|
| M7.1 scope (1-2 weeks) | ☐ | ☐ | |
| M7.2 scope (1-2 weeks) | ☐ | ☐ | |
| M7.3 scope (1 week) | ☐ | ☐ | |
| Resource requirements | ☐ | ☐ | |

### Recommendations

**Strengths:**
1. 
2. 
3. 

**Suggested Changes:**
1. 
2. 
3. 

**Missing Elements:**
1. 
2. 

**Overall Assessment:**
- ☐ Approve as-is
- ☐ Approve with minor changes
- ☐ Major revision required

**Signature:** _________________ **Date:** _________________
