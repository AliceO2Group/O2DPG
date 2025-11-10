# Restart Context for GPT - Phase 7 M7.1 Implementation

**Date:** 2025-10-27  
**Status:** Tests approved ✅ → Ready for implementation  
**Your task:** Implement `groupby_regression_sliding_window.py`

---

## 🎯 Where We Are

**Completed:**
- ✅ Phase 7 specification finalized
- ✅ Test suite written (26 tests, 923 lines)
- ✅ Test suite reviewed and approved by Claude
- ✅ Minor test refinements completed

**Your current task:**
- Implement `groupby_regression_sliding_window.py` to make tests pass
- Target: 24+ of 26 tests passing
- Timeline: 2-4 hours

---

## 📋 What to Implement

**File:** `groupby_regression_sliding_window.py` (~800-1000 lines)

**Functions (10 total):**

1. **Exceptions (2)**
   - `InvalidWindowSpec(ValueError)` - for malformed window specs
   - `PerformanceWarning(UserWarning)` - for backend fallbacks

2. **Helper Functions (6)**
   - `_validate_sliding_window_inputs()` - input validation
   - `_build_bin_index_map()` - **CRITICAL: zero-copy hash map**
   - `_generate_neighbor_offsets()` - combinatorial neighbor generation
   - `_get_neighbor_bins()` - boundary truncation
   - `_aggregate_window_zerocopy()` - **CORE: aggregation algorithm**
   - `_fit_window_regression_statsmodels()` - regression fitting
   - `_assemble_results()` - output formatting

3. **Main Function (1)**
   - `make_sliding_window_fit()` - orchestrator

---

## 🔑 Critical Specifications

### Function Signatures (EXACT)

```python
from __future__ import annotations
from typing import List, Dict, Union, Optional, Callable, Tuple, Any
import pandas as pd
import numpy as np

# Exceptions
class InvalidWindowSpec(ValueError):
    """Raised when window specification is malformed."""
    pass

class PerformanceWarning(UserWarning):
    """Warning for suboptimal performance conditions."""
    pass

# Main function
def make_sliding_window_fit(
    df: pd.DataFrame,
    group_columns: List[str],
    window_spec: Dict[str, int],
    fit_columns: List[str],
    predictor_columns: List[str],
    fit_formula: Optional[Union[str, Callable]] = None,
    fitter: str = 'ols',
    aggregation_functions: Optional[Dict[str, List[str]]] = None,
    weights_column: Optional[str] = None,
    selection: Optional[pd.Series] = None,
    binning_formulas: Optional[Dict[str, str]] = None,
    min_entries: int = 10,
    backend: str = 'numpy',
    partition_strategy: Optional[dict] = None,
    **kwargs
) -> pd.DataFrame:
    """Sliding window groupby regression."""
    pass

# Helpers (signatures from spec)
def _validate_sliding_window_inputs(...) -> None:
    """Validate all inputs."""
    pass

def _build_bin_index_map(
    df: pd.DataFrame,
    group_columns: List[str],
    selection: Optional[pd.Series] = None
) -> Dict[Tuple[int, ...], List[int]]:
    """Build hash map: bin_coords -> [row_indices]."""
    pass

def _generate_neighbor_offsets(
    window_spec: Dict[str, int]
) -> List[Tuple[int, ...]]:
    """Generate all offset combinations."""
    pass

def _get_neighbor_bins(
    center_bin: Tuple[int, ...],
    offsets: List[Tuple[int, ...]],
    bin_ranges: Dict[str, Tuple[int, int]],
    boundary_mode: str = 'truncate'
) -> List[Tuple[int, ...]]:
    """Get valid neighbors with boundary handling."""
    pass
```

---

## 🏗️ Implementation Order

**Follow this sequence:**

### Phase 1: Exceptions & Validation (30 min)
```python
# 1. Define exceptions
class InvalidWindowSpec(ValueError): pass
class PerformanceWarning(UserWarning): pass

# 2. Implement validation
def _validate_sliding_window_inputs(...):
    # Check columns exist
    # Check group_columns are integers
    # Check window_spec keys match group_columns
    # Check window sizes non-negative
    # Check min_entries > 0
    # Check selection length matches df
```

**Test:** 6 validation tests should pass

---

### Phase 2: Helper Functions (1 hour)

**Critical: _build_bin_index_map (ZERO-COPY foundation)**
```python
def _build_bin_index_map(df, group_columns, selection=None):
    # Apply selection mask if provided
    # Build hash map: (xBin, yBin, zBin) -> [row_idx1, row_idx2, ...]
    # Return dict with tuple keys
```

**Critical: _aggregate_window_zerocopy (CORE algorithm)**
```python
def _aggregate_window_zerocopy(df, center_bins, bin_map, window_spec, ...):
    # For each center bin:
    #   1. Generate neighbor offsets
    #   2. Apply boundary conditions
    #   3. Look up row indices from bin_map (ZERO-COPY!)
    #   4. Aggregate using df.iloc[indices]
    #   5. Compute stats (mean, std, median, entries)
    # Return DataFrame with aggregated stats
```

**Test:** After helpers, 10+ tests should pass

---

### Phase 3: Statsmodels Integration (45 min)

```python
def _fit_window_regression_statsmodels(...):
    # Check statsmodels availability
    if fitter != 'huber' and not STATSMODELS_AVAILABLE:
        raise ImportError("statsmodels required. pip install statsmodels")
    
    # For each center bin with enough entries:
    #   - Get window data
    #   - Fit using statsmodels (OLS, WLS, GLM, RLM)
    #   - Extract coefficients
    #   - Compute diagnostics (R², RMSE)
    # Return DataFrame with fit results
```

**Test:** After fitting, 20+ tests should pass

---

### Phase 4: Assembly & Main (30 min)

```python
def _assemble_results(...):
    # Merge aggregated stats + fit results
    # Expand bin tuples to columns
    # Add metadata to .attrs
    # Return formatted DataFrame

def make_sliding_window_fit(...):
    # Validate inputs
    # Warn if backend='numba' (not available in M7.1)
    # Build bin index map
    # Aggregate window data
    # Fit regressions (if formula provided)
    # Assemble results
    # Return DataFrame
```

**Test:** All 24-26 tests should pass ✅

---

## 🎯 Output Requirements

### DataFrame Columns

**Must include:**
- Group columns: `xBin`, `yBin`, `zBin` (first)
- Aggregations: `{target}_mean`, `{target}_std`, `{target}_median`, `{target}_entries`
- Fit results: `{target}_slope_{pred}`, `{target}_intercept`, `{target}_r_squared`
- Optional: `quality_flag`, `n_neighbors_used`, `effective_window_fraction`

### Metadata (.attrs)

**Required keys:**
```python
result.attrs = {
    'window_spec_json': json.dumps(window_spec),
    'fitter_used': fitter,
    'backend_used': backend,
    'boundary_mode_per_dim': {dim: 'truncate' for dim in group_columns},
    'binning_formulas_json': json.dumps(binning_formulas) if binning_formulas else None,
    'computation_time_sec': elapsed_time,
}
```

---

## 🚨 Critical Implementation Rules

### 1. Zero-Copy Accumulator (MEM-3)

**DO:**
- Use hash map: `bin → [row indices]`
- Use `df.iloc[indices]` for data access
- Aggregate using NumPy on views

**DON'T:**
- Replicate DataFrames
- Use merge/groupby with replication
- Create copies of data

### 2. Statsmodels Integration

```python
# Import with fallback
try:
    import statsmodels.formula.api as smf
    import statsmodels.api as sm
    STATSMODELS_AVAILABLE = True
except ImportError as e:
    STATSMODELS_AVAILABLE = False
    _STATSMODELS_IMPORT_ERROR = e

# Check before use
if fitter in ['ols', 'wls', 'glm', 'rlm'] and not STATSMODELS_AVAILABLE:
    raise ImportError(
        f"fitter='{fitter}' requires statsmodels.\n"
        f"Install: pip install statsmodels\n"
        f"Original error: {_STATSMODELS_IMPORT_ERROR}"
    )
```

### 3. Error Messages

**Make them helpful:**
```python
# Good
raise ValueError(
    f"Group column '{col}' must be integer dtype (found {df[col].dtype}). "
    "M7.1 requires integer bin coordinates. Use pre-binning for floats."
)

# Bad
raise ValueError("Invalid dtype")
```

### 4. Boundary Handling (M7.1)

**Only 'truncate' mode:**
```python
if boundary_mode != 'truncate':
    raise InvalidWindowSpec(
        f"Boundary mode '{boundary_mode}' not supported in M7.1. "
        "Only 'truncate' is available."
    )
```

---

## 📚 Reference Documents

**In /mnt/user-data/outputs:**
1. **GPT_IMPLEMENTATION_INSTRUCTIONS.md** - Detailed guide with code templates
2. **PHASE7_IMPLEMENTATION_PLAN.md** - Full specification
3. **TEST_REVIEW_FOR_GPT.md** - Test review with guidance
4. **UPDATED_API_STATSMODELS.md** - API reference

**Test file:**
- `test_groupby_regression_sliding_window.py` - Your contract (26 tests)

---

## ⚡ Quick Start

**Step 1: Read key references (10 min)**
```
1. This file (restartContextGPT.md)
2. GPT_IMPLEMENTATION_INSTRUCTIONS.md (code templates)
3. test_groupby_regression_sliding_window.py (understand tests)
```

**Step 2: Implement in order (2-3 hours)**
```
1. Exceptions (5 min)
2. Validation (30 min)
3. Helpers (1 hour) ← CRITICAL: zero-copy accumulator
4. Statsmodels (45 min)
5. Assembly + Main (30 min)
```

**Step 3: Test frequently**
```bash
# Run all tests
pytest test_groupby_regression_sliding_window.py -v

# Run specific category
pytest test_groupby_regression_sliding_window.py -k "basic" -v

# Stop at first failure
pytest test_groupby_regression_sliding_window.py -x
```

---

## ✅ Success Criteria

**Minimum (M7.1 approval):**
- [ ] 20+ of 26 tests pass
- [ ] Zero-copy accumulator working
- [ ] Statsmodels OLS, WLS working
- [ ] No critical bugs
- [ ] Python 3.9.6 compatible

**Target:**
- [ ] 24-26 of 26 tests pass
- [ ] Clear error messages
- [ ] Complete docstrings
- [ ] Metadata in .attrs

---

## 🎯 Implementation Checklist

**Phase 1: Exceptions & Validation**
- [ ] InvalidWindowSpec exception
- [ ] PerformanceWarning warning
- [ ] _validate_sliding_window_inputs function
- [ ] Tests: 6 validation tests pass

**Phase 2: Core Algorithm**
- [ ] _build_bin_index_map (hash map)
- [ ] _generate_neighbor_offsets (combinatorial)
- [ ] _get_neighbor_bins (boundary handling)
- [ ] _aggregate_window_zerocopy (CORE!)
- [ ] Tests: 10+ tests pass

**Phase 3: Fitting**
- [ ] Statsmodels import with fallback
- [ ] _fit_window_regression_statsmodels
- [ ] Support OLS, WLS fitters
- [ ] Tests: 20+ tests pass

**Phase 4: Assembly**
- [ ] _assemble_results
- [ ] make_sliding_window_fit (main)
- [ ] Add metadata to .attrs
- [ ] Tests: 24-26 tests pass

---

## 💡 Key Insights from Test Review

**From Claude's review:**
1. Tests are excellent (26/20+ required)
2. Clear documentation (WHAT/WHY)
3. One signature fix already applied
4. Implementation straightforward if following order

**From Gemini's refinements:**
1. Tests now more robust (seeds added)
2. Formula tests relaxed for statsmodels quirks
3. Extra validations for common errors
4. v4 parity test more flexible

**Bottom line:**
- Tests define clear contract
- Follow implementation order
- Test frequently
- 24+ tests passing = success!

---

## 🚀 Ready to Start

**Your mission:**
Create `groupby_regression_sliding_window.py` that makes 24+ tests pass.

**Strategy:**
1. Start with exceptions (easy wins)
2. Build helpers carefully (test each)
3. Implement zero-copy aggregator (most important!)
4. Add statsmodels fitting
5. Wire up main function

**Timeline:**
- 2-3 hours if following order
- 4-5 hours if exploring/debugging

**Next step:**
Read GPT_IMPLEMENTATION_INSTRUCTIONS.md and start coding!

---

## 📞 Quick Reference

**Test file:**
- test_groupby_regression_sliding_window.py (26 tests)

**Implementation guides:**
- GPT_IMPLEMENTATION_INSTRUCTIONS.md (detailed)
- PHASE7_IMPLEMENTATION_PLAN.md (specification)

**Python version:**
- 3.9.6+ (use `from __future__ import annotations`)

**Dependencies:**
- pandas, numpy, statsmodels, sklearn

**Run tests:**
```bash
pytest test_groupby_regression_sliding_window.py -v
```

---

**Status:** Ready to implement

**Expected outcome:** 24-26 tests passing in 2-4 hours

**Let's go!** 🚀
