# Phase 7 Implementation - Restart Context

**Date:** 2025-10-27  
**Status:** 🟢 APPROVED - Ready to implement M7.1  
**Project:** Sliding Window GroupBy Regression for ALICE TPC Calibration

---

## 🎯 Current State: START M7.1 IMPLEMENTATION

**All approvals obtained:**
- ✅ GPT-4: Approved (with changes incorporated)
- ✅ Gemini: Approved (with changes incorporated)
- ✅ Marian Ivanov (MI): Approved (statsmodels decision confirmed)

**Next action:** Implement `groupby_regression_sliding_window.py` (M7.1)

---

## 📁 Key Documents (All in /mnt/user-data/outputs)

### Planning Documents (Reference Only)
1. **PHASE7_IMPLEMENTATION_PLAN.md** - Complete 27-page implementation plan
2. **PHASE7_KICKOFF_REVISED.md** - Executive summary (5 pages)
3. **PHASE7_REVISION_SUMMARY.md** - Change log from reviews (8 pages)
4. **MI_REVIEW_CHECKLIST.md** - Approval checklist (completed)
5. **MESSAGE_TO_REVIEWERS_STATSMODELS.md** - Statsmodels decision rationale
6. **UPDATED_API_STATSMODELS.md** - Complete API spec with statsmodels

### Source Specification (Reference)
- **SLIDING_WINDOW_SPEC_DRAFT.md** (in uploads) - Full specification (1856 lines)

---

## 🔥 Core Implementation Requirements (M7.1)

### What to Build

**File:** `groupby_regression_sliding_window.py`

**Main function:**
```python
def make_sliding_window_fit(
    df: pd.DataFrame,
    group_columns: List[str],          # Integer bin coordinates ONLY
    window_spec: Dict[str, int],       # {'xBin': 2, 'yBin': 1} = ±2, ±1
    fit_columns: List[str],            # Targets
    predictor_columns: List[str],      # Features
    fit_formula: Optional[Union[str, Callable]] = None,  # 'y ~ x1 + x2'
    fitter: str = 'ols',               # NEW: 'ols', 'wls', 'glm', 'rlm'
    aggregation_functions: Optional[Dict[str, List[str]]] = None,
    weights_column: Optional[str] = None,
    selection: Optional[pd.Series] = None,
    binning_formulas: Optional[Dict[str, str]] = None,
    min_entries: int = 10,
    backend: str = 'numpy',            # M7.1: numpy only
    partition_strategy: Optional[dict] = None,
    **kwargs
) -> pd.DataFrame
```

---

## 🏗️ Architecture: Zero-Copy Accumulator (MEM-3)

**Critical innovation** (from Gemini review):

### Algorithm

```python
# 1. Build bin→rows hash map (ONCE)
bin_map = {}  # {(xBin, yBin, zBin): [row_idx1, row_idx2, ...]}
for idx, row in df[group_columns].iterrows():
    bin_key = tuple(row.values)
    bin_map.setdefault(bin_key, []).append(idx)

# 2. For each center bin
for center_bin in unique_bins:
    # Generate neighbor offsets
    offsets = itertools.product(*[range(-w, w+1) for w in window_sizes])
    
    # Collect row indices (ZERO-COPY!)
    row_indices = []
    for offset in offsets:
        neighbor = tuple(c + o for c, o in zip(center_bin, offset))
        if neighbor in bin_map:
            row_indices.extend(bin_map[neighbor])
    
    # Aggregate at these indices (view, not copy)
    values = df.iloc[row_indices]['target'].values
    mean = np.mean(values)
    std = np.std(values)
    # ... fit regression ...
```

**Why this works:**
- No DataFrame replication (avoids 27-125× memory explosion)
- Integer index slicing is fast
- NumPy aggregations on views are efficient

---

## 📐 Implementation Structure (8 Functions)

```python
# 0. Exceptions
class InvalidWindowSpec(ValueError): pass
class PerformanceWarning(UserWarning): pass

# 1. Validation
def _validate_sliding_window_inputs(...) -> None:
    """Check columns exist, bins are integers, specs valid."""

# 2. Bin index map (CRITICAL - Zero-copy foundation)
def _build_bin_index_map(
    df: pd.DataFrame,
    group_columns: List[str],
    selection: Optional[pd.Series]
) -> Dict[Tuple[int, ...], List[int]]:
    """Build hash map: bin_tuple -> [row_indices]."""

# 3. Neighbor generation
def _generate_neighbor_offsets(window_spec: Dict) -> List[Tuple]:
    """Generate all offset combinations."""

def _get_neighbor_bins(
    center_bin: Tuple,
    offsets: List[Tuple],
    bin_ranges: Dict,
    boundary_mode: str = 'truncate'
) -> List[Tuple]:
    """Apply boundary conditions."""

# 4. Zero-copy aggregator (CORE ALGORITHM)
def _aggregate_window_zerocopy(
    df: pd.DataFrame,
    center_bins: List[Tuple],
    bin_map: Dict[Tuple, List[int]],
    window_spec: Dict,
    bin_ranges: Dict,
    fit_columns: List[str],
    aggregation_functions: Dict,
    weights_column: Optional[str]
) -> pd.DataFrame:
    """Aggregate data for each center using zero-copy."""

# 5. Fit regression with statsmodels
def _fit_window_regression_statsmodels(
    aggregated_data: pd.DataFrame,
    bin_map: Dict,
    df: pd.DataFrame,
    fit_formula: Union[str, Callable],
    fit_columns: List[str],
    predictor_columns: List[str],
    min_entries: int,
    weights_column: Optional[str],
    fitter: str,
    **kwargs
) -> pd.DataFrame:
    """Fit using statsmodels (ols, wls, glm, rlm)."""

# 6. Result assembly
def _assemble_results(
    aggregated_stats: pd.DataFrame,
    fit_results: pd.DataFrame,
    group_columns: List[str],
    window_spec: Dict,
    binning_formulas: Optional[Dict],
    backend: str,
    fitter: str,
    computation_time: float
) -> pd.DataFrame:
    """Add metadata to .attrs."""
```

---

## 🔧 Dependencies

```python
# Required
import pandas as pd
import numpy as np
from typing import List, Dict, Union, Optional, Callable, Tuple, Any
import itertools
import warnings
import json
import sys
import time

# Statsmodels (required per MI decision)
try:
    import statsmodels.formula.api as smf
    import statsmodels.api as sm
    STATSMODELS_AVAILABLE = True
except ImportError as e:
    STATSMODELS_AVAILABLE = False
    _STATSMODELS_IMPORT_ERROR = e

# Sklearn (fallback for Huber)
from sklearn.linear_model import HuberRegressor
```

---

## 📋 M7.1 Scope (Strict Boundaries)

### What's Included
- ✅ Integer bin coordinates ONLY (no floats)
- ✅ Zero-copy accumulator (pure NumPy)
- ✅ Simple window_spec: `{'xBin': 2}` = ±2 bins
- ✅ Boundary: 'truncate' only
- ✅ Weighting: 'uniform' only (weights_column for WLS)
- ✅ Aggregations: mean, std, median, entries
- ✅ Statsmodels: ols, wls, glm, rlm + callable
- ✅ Selection mask support
- ✅ Metadata in .attrs
- ✅ Performance warnings

### What's Deferred
- ⏭️ M7.2: Numba JIT compilation
- ⏭️ M7.2: Mirror/periodic boundaries
- ⏭️ M7.2: Distance/Gaussian weighting
- ⏭️ M7.2: Rich window_spec format
- ⏭️ v2.2+: Float coordinates (distance-based neighbors)

---

## 🧪 Testing Requirements

**File:** `test_groupby_regression_sliding_window.py`

**Minimum 20 tests:**

### Basic (5 tests)
- `test_sliding_window_basic_3d()` - Basic 3D window
- `test_sliding_window_aggregation()` - Verify stats
- `test_sliding_window_linear_fit()` - Verify coefficients
- `test_empty_window_handling()` - Empty windows
- `test_min_entries_enforcement()` - Threshold

### Validation (6 tests)
- `test_invalid_window_spec()` - Malformed spec
- `test_missing_columns()` - Missing columns
- `test_float_bins_rejected()` - Float bins error
- `test_negative_min_entries()` - min_entries > 0
- `test_invalid_fit_formula()` - Formula parse error
- `test_selection_mask_length_mismatch()` - Wrong length

### Edge Cases (5 tests)
- `test_single_bin_dataset()` - One bin
- `test_all_sparse_bins()` - All <min_entries
- `test_boundary_bins()` - Grid boundaries
- `test_multi_target_fit()` - Multiple targets
- `test_weighted_aggregation()` - With weights

### Review-Added (5 tests)
- `test_selection_mask()` - Selection filtering
- `test_metadata_presence()` - .attrs metadata
- `test_performance_warning_numpy_fallback()` - Warnings
- `test_window_size_zero_equivalence_with_v4()` - v4 parity
- `test_multi_target_column_naming()` - Column names
- `test_reference_full_expansion_2d()` - Correctness (small 2D)

### Statsmodels (3 tests)
- `test_statsmodels_fitters()` - OLS, WLS, GLM, RLM
- `test_statsmodels_formula_syntax()` - Interactions, transforms
- `test_statsmodels_not_available()` - ImportError handling

---

## 📊 Benchmark Requirements

**File:** `bench_sliding_window.py`

**3 scenarios:**

```python
# Scenario 1: Small (validation)
bench_small_3d = {
    'n_bins': (10, 10, 10),  # 1K bins
    'entries_per_bin': 20,
    'window_size': 1,
    'expected_time': '<10s'
}

# Scenario 2: Medium (realistic)
bench_medium_3d = {
    'n_bins': (50, 20, 30),  # 30K bins
    'entries_per_bin': 100,
    'window_size': 1,
    'expected_time': '<2min'
}

# Scenario 3: Sparse (stress)
bench_sparse_3d = {
    'n_bins': (100, 50, 50),  # 250K bins
    'entries_per_bin': 10,
    'sparsity': 0.5,
    'window_size': 2,
    'expected_time': '<5min'
}
```

**Metrics to report:**
- Total bins
- Fitted bins (% success)
- Skipped bins (% below min_entries)
- Runtime (seconds)
- Throughput (bins/sec)
- Peak memory (MB)
- Avg window size (neighbors)

---

## 🎯 Success Criteria (M7.1)

### Must Have
- ✅ All 20+ tests pass
- ✅ Zero-copy accumulator implemented and validated
- ✅ Reference test confirms correctness
- ✅ Window=0 matches v4 results
- ✅ Medium benchmark: <2 min (target <5 min acceptable in M7.1)
- ✅ Metadata present in output
- ✅ Performance warnings work
- ✅ Statsmodels integration complete (ols, wls, glm, rlm)
- ✅ Clear ImportError if statsmodels missing

### Nice to Have (OK if deferred to polish)
- Documentation strings complete
- Example notebook
- README updated

---

## 🚨 Common Pitfalls to Avoid

1. **Don't replicate DataFrames** - Use zero-copy accumulator
2. **Don't forget selection mask** - Apply once in bin_map builder
3. **Don't allow float bins** - Validate as integers
4. **Don't forget metadata** - Add to .attrs
5. **Don't silently fail** - Clear errors if statsmodels missing
6. **Test boundary bins** - Truncation must work correctly

---

## 💡 Implementation Tips

### Start Simple
1. Exception classes
2. Input validation (can be basic)
3. Bin index map (CRITICAL - get this right)
4. Neighbor generation (combinatorial, simple)
5. Zero-copy aggregator (CORE - validate with reference test)
6. Statsmodels integration (straightforward with smf)
7. Result assembly (add metadata)
8. Tests (validates everything)

### Test As You Go
- Build bin_map → test it
- Generate neighbors → test it
- Aggregate → test against naive expansion (small data)
- Fit → test coefficients match expected

### Don't Over-Engineer
- M7.1 is a **prototype** - focus on correctness, not optimization
- Numba comes in M7.2
- Keep functions simple and readable
- Add TODO comments for M7.2 features

---

## 📚 Reference Code Patterns

### From v4 (for patterns)
- `/mnt/user-data/uploads/groupby_regression_optimized.py`
- `/mnt/user-data/uploads/test_groupby_regression_optimized.py`

### Existing test data generators
```python
def _make_synthetic_3d_grid(n_bins_per_dim=10, entries_per_bin=50, seed=42):
    """Generate test data with known y = 2*x + noise."""
```

---

## 🐍 Python 3.9.6 Compatibility

**Always use:**
```python
from __future__ import annotations
from typing import List, Dict, Optional, Union, Tuple

def func(x: List[str]) -> Optional[pd.DataFrame]:
    ...
```

**Never use:**
```python
def func(x: list[str]) -> pd.DataFrame | None:  # ❌ 3.10+ only
    ...
```

---

## 📝 Output Requirements

**Return DataFrame with columns:**
- Group columns: xBin, yBin, zBin, ...
- Aggregated stats: {target}_mean, {target}_std, {target}_median, {target}_entries
- Fit coefficients: {target}_intercept, {target}_slope_{predictor}
- Diagnostics: {target}_r_squared, {target}_rmse, {target}_n_fitted
- Quality: effective_window_fraction, n_neighbors_used, quality_flag

**Metadata in .attrs:**
```python
result.attrs = {
    'window_spec_json': json.dumps(window_spec),
    'binning_formulas_json': json.dumps(binning_formulas),
    'boundary_mode_per_dim': {'xBin': 'truncate', ...},
    'backend_used': 'numpy',
    'fitter_used': fitter,
    'computation_time_sec': elapsed,
    'statsmodels_version': sm.__version__
}
```

---

## 🚀 Execution Plan

### Day 1-2: Core Infrastructure
- Exception classes
- Input validation
- Bin index map builder
- Tests for above

### Day 3-4: Zero-Copy Aggregator
- Neighbor generation
- Boundary handling
- Zero-copy aggregation
- Reference correctness test

### Day 5-6: Fitting
- Statsmodels integration (ols, wls, glm, rlm)
- Error handling
- Result extraction

### Day 7-8: Assembly & Polish
- Result assembly with metadata
- Remaining tests
- Documentation

### Day 9-10: Benchmarks
- Three benchmark scenarios
- Performance metrics
- README updates

### Day 11-12: Review Prep
- Code review
- Final validation
- Prepare M7.1 review document

---

## 📋 Final Checklist

Before declaring M7.1 complete:

- [ ] All 20+ tests pass
- [ ] Zero-copy accumulator validated
- [ ] Window=0 ↔ v4 parity test passes
- [ ] Statsmodels fitters work (ols, wls, glm, rlm)
- [ ] ImportError clear if statsmodels missing
- [ ] Metadata present in output
- [ ] Performance warnings emit correctly
- [ ] Benchmarks run and report metrics
- [ ] Code reviewed
- [ ] Documentation strings complete

---

## 🎯 Project Size Assessment

**Is M7.1 too large?**

**NO.** Here's why:

**Scope:**
- 1 main file (~800-1000 lines)
- 8 functions (already specified)
- 20-25 tests (patterns known)
- 1 benchmark file (simple)

**Complexity:**
- Core algorithm: Zero-copy accumulator (well-defined)
- Integration: Statsmodels (straightforward API)
- Innovation: Already designed (just implement)

**Timeline:**
- 1-2 weeks is realistic
- Can implement incrementally
- Test as we go

**Comparison:**
- Simpler than v4 (which you already have)
- No Numba yet (M7.2)
- Well-specified (no ambiguity)

**Verdict: M7.1 is VERY DOABLE in current conversation or next**

---

## 🔄 How to Continue

**In new conversation, start with:**

"I'm implementing Phase 7 M7.1 (Sliding Window Regression).

Please read /mnt/user-data/outputs/restartContext.md for full context.

Key points:
- Implement groupby_regression_sliding_window.py
- Use zero-copy accumulator (MEM-3)
- Integrate statsmodels (ols, wls, glm, rlm)
- 20+ tests required
- Reference: PHASE7_IMPLEMENTATION_PLAN.md, UPDATED_API_STATSMODELS.md

Let's start with the bin index map builder (_build_bin_index_map)."

---

**Status:** 🟢 Ready to implement  
**Confidence:** High - specification is complete, architecture is sound  
**Next:** Write code!