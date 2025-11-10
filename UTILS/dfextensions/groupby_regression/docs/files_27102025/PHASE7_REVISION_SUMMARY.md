# Phase 7 Implementation Plan - Revision Summary

**Date:** 2025-10-27  
**Revision:** v1.1 (Post-Review)  
**Reviewers:** GPT-4 ✅, Gemini ✅  
**Status:** **APPROVED with changes incorporated**

---

## Summary of Changes

This document summarizes all changes made to the Phase 7 Implementation Plan based on feedback from GPT-4 and Gemini reviews.

**Overall Verdict:** Both reviewers approved the plan with minor changes. All requested changes have been incorporated.

---

## Major Architectural Changes

### 1. Zero-Copy Accumulator (MEM-3) - **CRITICAL**

**Original Plan (M7.1):**
- Naive DataFrame merge/groupby approach
- Would create 27-125× memory explosion
- Unlikely to meet <5 min demo target

**Revised Plan (M7.1):**
- **Zero-copy accumulator prototype in pure NumPy**
- Build hash map: `bin_tuple -> [row_indices]`
- Aggregate by scanning index lists (no replication)
- **Benefits:**
  - Validates algorithm correctness before Numba
  - Memory efficient (O(N) overhead, not O(N × window_volume))
  - Realistic chance at <5 min target
  
**Source:** Gemini review (critical insight)

**Impact:** This is the cornerstone of the implementation. Without it, M7.1 would fail performance targets.

---

### 2. Formula Parsing Without Statsmodels

**Original Plan:**
- Use statsmodels for formula parsing
- "statsmodels-style formulas"

**Revised Plan:**
- **Simple regex parsing** for formulas: `'target ~ pred1 + pred2'`
- **Reuse existing v4 fit logic** (sklearn LinearRegression/HuberRegressor)
- No new dependencies for core functionality

**Rationale (Gemini):**
- v4 already has excellent fit logic
- statsmodels is heavy dependency
- Simple formulas don't need full statsmodels parsing

**Implementation:**
```python
def _parse_fit_formula(formula: str) -> Tuple[str, List[str]]:
    match = re.match(r'^\s*(\w+)\s*~\s*(.+)\s*$', formula)
    target = match.group(1).strip()
    predictors = [p.strip() for p in match.group(2).split('+')]
    return target, predictors
```

---

### 3. Float Coordinates Explicitly Deferred

**Clarification Added:**
- M7.1-M7.3: **Integer bins ONLY**
- Users **MUST pre-bin** float coordinates
- Float coordinate support deferred to **v2.2+**
- DH-2 rule is hard requirement

**Source:** Gemini review (scope clarity)

**Documentation Impact:**
- Added explicit statement in API docstring
- Added to non-requirements section
- Added to user guide scope

---

## API Changes (Future-Proofing)

### 4. Additional Parameters (GPT Review)

**Added to signature (M7.1):**

```python
def make_sliding_window_fit(
    ...
    selection: Optional[pd.Series] = None,           # NEW: Pre-filter rows
    binning_formulas: Optional[Dict[str, str]] = None,  # NEW: Metadata
    partition_strategy: Optional[dict] = None,       # NEW: Stub for M7.2
    ...
)
```

**`selection` parameter:**
- Boolean mask to pre-filter rows before windowing
- Consistent with v2/v4 GroupByRegressor API
- Applied once in `_build_bin_index_map`

**`binning_formulas` parameter:**
- Metadata only (not applied by framework)
- Documents how floats were binned to integers
- Stored in output.attrs for provenance

**`partition_strategy` parameter:**
- Accepted but not used in M7.1
- Future-proofs API for M7.2 memory management

---

### 5. Output Metadata (RootInteractive Compatibility)

**Added to output DataFrame.attrs:**

```python
result.attrs = {
    'window_spec_json': ...,           # Original window specification
    'binning_formulas_json': ...,      # Binning formulas (if provided)
    'boundary_mode_per_dim': ...,      # {'xBin': 'truncate', ...}
    'backend_used': ...,               # 'numpy' or 'numba'
    'computation_time_sec': ...,       # Total runtime
    'group_columns': ...,              # List of bin columns
    'python_version': ...              # sys.version
}
```

**Purpose:**
- Provenance tracking
- Reproducibility
- Integration with RootInteractive dashboards
- Quality assurance

**Source:** GPT review (requirement from spec)

---

## Error Handling & Warnings

### 6. Exception Classes Defined

**Added (M7.1):**

```python
class InvalidWindowSpec(ValueError):
    """Raised when window specification is malformed or invalid."""
    
class PerformanceWarning(UserWarning):
    """Warning for suboptimal performance conditions."""
```

**Usage:**
- `InvalidWindowSpec`: Malformed window_spec, invalid formula syntax, negative window sizes
- `PerformanceWarning`: Numpy fallback, large window volume, dense→sparse switch

**Source:** GPT review (spec requirement FR-9)

---

### 7. Performance Warning Emission

**Warnings will be emitted for:**

1. **Numba unavailable:**
   ```python
   warnings.warn(
       "Numba backend unavailable, falling back to NumPy. "
       "Expected 10-100× slowdown.",
       PerformanceWarning
   )
   ```

2. **Large window volume:**
   ```python
   if window_volume > 1000:
       warnings.warn(
           f"Window volume ({window_volume} bins) is very large. "
           "Consider reducing window size for better performance.",
           PerformanceWarning
       )
   ```

3. **Dense→sparse mode switch:**
   ```python
   total_cells = np.prod(bin_counts)
   if total_cells > MAX_DENSE_CELLS:
       warnings.warn(
           f"Grid size ({total_cells:,} cells) exceeds max_dense_cells. "
           "Switching to sparse mode.",
           PerformanceWarning
       )
   ```

---

## Testing Changes

### 8. Additional Tests (5 new tests)

**Added to test suite:**

1. **`test_selection_mask()`**
   - Verify selection parameter filters rows correctly
   
2. **`test_metadata_presence()`**
   - Check all required metadata in output.attrs
   
3. **`test_performance_warning_numpy_fallback()`**
   - Verify PerformanceWarning emitted when Numba unavailable
   
4. **`test_window_size_zero_equivalence_with_v4()`**
   - Window size = 0 should match v4 groupby results
   - Critical sanity check
   
5. **`test_multi_target_column_naming()`**
   - Verify output columns match v4 naming convention
   
6. **`test_reference_full_expansion_2d()`** (NEW - correctness)
   - Property test comparing zero-copy vs. naive expansion
   - Only for small 2D/3D test grids
   - Validates algorithm correctness

**Source:** GPT review + Gemini (reference test)

**Total tests:** 20+ (up from 15)

---

### 9. Default Aggregations Updated

**Changed from:**
- `['mean', 'std', 'entries']`

**Changed to:**
- `['mean', 'std', 'entries', 'median']`

**Rationale:** FR-2 requires median for robust statistics

**Source:** GPT review

---

## Benchmark Changes

### 10. Standard Metrics Output

**Added structured output class:**

```python
class BenchmarkResult:
    scenario_name: str
    total_runtime_sec: float
    n_bins_total: int
    n_bins_fitted: int           # NEW
    n_bins_skipped: int          # NEW
    bins_per_sec: float          # NEW
    peak_memory_mb: float
    avg_window_size: float       # NEW
```

**Print format:**
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

**Purpose:** Standardized format for README and documentation

**Source:** GPT review

---

## Timeline Changes

### 11. M7.2 Duration Extended

**Original:** 1-2 weeks  
**Revised:** 2-3 weeks (acknowledged as aggressive)

**Rationale (Gemini):**
- M7.2 scope is dense: Numba kernel + 3 boundaries + 2 weightings
- Better to be realistic than over-promise

**Mitigation:**
- Prioritize: Numba first, then boundaries, then weighting
- Allow extension without pressure

---

## Python 3.9.6 Compatibility

### 12. Type Hint Syntax

**All code updated for Python 3.9.6:**

**Use:**
```python
from __future__ import annotations
from typing import List, Dict, Optional, Union, Tuple, Callable

def func(x: List[str], y: Dict[str, int]) -> Optional[pd.DataFrame]:
    ...
```

**Avoid (Python 3.10+ syntax):**
```python
def func(x: list[str], y: dict[str, int]) -> pd.DataFrame | None:  # ❌ Won't work in 3.9
    ...
```

**Source:** MI specification

---

## Documentation Changes

### 13. Scope Clarifications

**Added explicit statements:**

1. **Integer bins requirement:**
   - "group_columns MUST be integer bin coordinates"
   - "Users must pre-bin float coordinates"
   - "See DH-2 in specification"

2. **M7.1 scope limitations:**
   - Boundary: truncate only
   - Weighting: uniform only
   - Backend: numpy (Numba in M7.2)

3. **Deferred features:**
   - Float coordinates: v2.2+
   - Mirror/periodic: M7.2
   - Gaussian weighting: M7.2

---

## Code Quality Changes

### 14. Function Signatures

**All functions now have:**
- Complete type hints (Python 3.9.6 compatible)
- NumPy-style docstrings
- Parameter descriptions with types and defaults
- Return value specification
- Examples section
- Notes section (caveats, limitations)

**Example:**
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
    ...
    
    Returns
    -------
    ...
    
    Examples
    --------
    ...
    
    Notes
    -----
    ...
    """
```

---

## Implementation Structure Changes

### 15. Function Decomposition

**Core M7.1 functions (in order):**

0. `_define_exceptions()` - Error classes
1. `_validate_sliding_window_inputs()` - Input validation
2. `_build_bin_index_map()` - **Zero-copy foundation**
3. `_generate_neighbor_offsets()` - Combinatorial offset generation
4. `_get_neighbor_bins()` - Boundary-aware neighbor lookup
5. `_aggregate_window_zerocopy()` - **Core algorithm (MEM-3)**
6. `_parse_fit_formula()` - Simple regex parsing
7. `_fit_window_regression()` - Reuse v4 fit logic
8. `_assemble_results()` - Output assembly with metadata

**Key:** Functions 2 and 5 implement the zero-copy accumulator

---

## What Remains Unchanged

**Kept from original plan:**
- ✅ Three-milestone structure (M7.1, M7.2, M7.3)
- ✅ Core use cases (TPC, tracking performance)
- ✅ Performance targets (<30 min for 7M rows in M7.2)
- ✅ Memory targets (<4GB)
- ✅ Review forms and acceptance criteria
- ✅ File structure (standalone `groupby_regression_sliding_window.py`)
- ✅ Reuse v2.0.0 infrastructure strategy

---

## Risk Mitigation Updates

### 16. New Risks Identified

**From Gemini:**
- M7.2 timeline aggressive → **Mitigated:** Extended to 2-3 weeks, prioritize features

**From GPT:**
- API stability concerns → **Mitigated:** Added future-proof parameters now (selection, binning_formulas, partition_strategy)

**From both:**
- Memory explosion risk → **Mitigated:** Zero-copy accumulator in M7.1 validates approach

---

## Approval Status

**GPT-4 Review:**
- ✅ Verdict: Approve with minor changes
- ✅ All changes incorporated

**Gemini Review:**
- ✅ Verdict: Approve with minor changes
- ✅ All changes incorporated

**Marian Ivanov:**
- ⏳ Awaiting final approval on updated plan

---

## Next Steps

1. **MI:** Review this summary + updated plan
2. **If approved:** Claude begins M7.1 implementation
3. **First deliverable:** `groupby_regression_sliding_window.py` with zero-copy accumulator

---

## Key Takeaways

**Most Important Changes:**
1. 🔥 **Zero-copy accumulator in M7.1** (not M7.2) - validates algorithm
2. 🔥 **No statsmodels** - reuse v4 fit logic with simple parsing
3. 🔥 **Integer bins only** - explicit scope boundary
4. ✅ API future-proofed with selection, binning_formulas, partition_strategy
5. ✅ Metadata output for provenance
6. ✅ Performance warnings for user guidance
7. ✅ Reference tests for correctness validation

**Implementation Impact:**
- M7.1 is now more ambitious (zero-copy prototype) but more valuable
- M7.1 success = validated algorithm + working demo
- M7.2 = "just" add Numba + advanced features on proven foundation

---

**Document Status:** ✅ Complete  
**Plan Status:** ✅ Ready for final MI approval  
**Implementation Status:** 🟡 Ready to begin upon approval
