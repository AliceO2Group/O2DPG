# Phase 7 Kickoff: Sliding Window Regression (REVISED)

**Date:** 2025-10-27  
**Version:** 1.1 (Post-Review)  
**Status:** 🟢 Approved - Ready to Begin  
**Team:** Marian Ivanov (MI) + Claude | Reviewers: GPT-4 ✅, Gemini ✅  
**Python:** 3.9.6+

---

## 🎯 What We're Building

**Sliding Window GroupBy Regression** for multi-dimensional sparse data analysis:
- Aggregate neighboring bins to overcome statistical sparsity
- Support 3D-6D+ dimensionality (**integer bins only**, floats deferred to v2.2+)
- Memory-efficient via **zero-copy accumulator (MEM-3)**
- Fast: <5 min for 400k rows (numpy demo), <30 min for 7M rows (Numba production)

**Primary Use Case:** ALICE TPC distortion maps and tracking performance parameterization

---

## 📋 Implementation Milestones

| Milestone | Scope | Duration | Key Deliverable |
|-----------|-------|----------|-----------------|
| **M7.1** | Zero-Copy Prototype + Tests | 1-2 weeks | Working algorithm validation |
| **M7.2** | Numba + Advanced Features | 2-3 weeks | Production-ready (10-100× speedup) |
| **M7.3** | Documentation + Polish | 1 week | Release v2.1.0 |

**Total:** 4-6 weeks

---

## 🔥 Key Changes from Reviews

### 1. Zero-Copy Accumulator in M7.1 (Critical!)

**What changed:**
- **Original:** Naive merge/groupby (memory explosion risk)
- **Now:** Zero-copy accumulator prototype in pure NumPy

**Why it matters:**
- Validates algorithm correctness early
- Avoids 27-125× memory replication
- Enables realistic <5 min demo target

**Algorithm:**
```python
# Build bin -> row index map (once)
bin_map = {(xBin, yBin, zBin): [row_idx1, row_idx2, ...], ...}

# For each center bin
for center in unique_bins:
    neighbors = generate_neighbors(center, window_spec)
    row_indices = []
    for neighbor in neighbors:
        row_indices.extend(bin_map.get(neighbor, []))
    
    # Aggregate at these indices (zero-copy view!)
    values = df.iloc[row_indices]['target'].values
    mean, std, count = np.mean(values), np.std(values), len(values)
```

**Source:** Gemini review (critical insight)

---

### 2. No Statsmodels Dependency

**What changed:**
- **Original:** Use statsmodels for formula parsing
- **Now:** Simple regex + reuse v4 fit logic (sklearn)

**Benefits:**
- No new dependencies
- Leverage existing tested code
- Simpler, faster

**Implementation:**
```python
def _parse_fit_formula(formula: str) -> Tuple[str, List[str]]:
    """Parse 'target ~ pred1 + pred2' without statsmodels."""
    match = re.match(r'^\s*(\w+)\s*~\s*(.+)\s*$', formula)
    target = match.group(1).strip()
    predictors = [p.strip() for p in match.group(2).split('+')]
    return target, predictors

# Then use sklearn LinearRegression (already in v4)
```

**Source:** Gemini review

---

### 3. API Future-Proofing

**Added parameters (M7.1):**
```python
def make_sliding_window_fit(
    ...
    selection: Optional[pd.Series] = None,            # NEW: Pre-filter rows
    binning_formulas: Optional[Dict[str, str]] = None,  # NEW: Metadata
    partition_strategy: Optional[dict] = None,        # NEW: Stub for M7.2
    ...
)
```

**Purpose:** Avoid breaking changes in M7.2

**Source:** GPT review

---

### 4. Output Metadata for Provenance

**Added to DataFrame.attrs:**
```python
result.attrs = {
    'window_spec_json': ...,
    'binning_formulas_json': ...,
    'boundary_mode_per_dim': ...,
    'backend_used': ...,
    'computation_time_sec': ...,
}
```

**Purpose:** RootInteractive compatibility, reproducibility

**Source:** GPT review (spec requirement)

---

### 5. Enhanced Testing

**Added 5 new tests:**
1. Selection mask functionality
2. Metadata presence validation
3. Performance warning emission
4. Window size = 0 ↔ v4 equivalence
5. Reference full-expansion correctness check

**Total:** 20+ tests (was 15)

**Source:** GPT + Gemini reviews

---

## 📐 M7.1 Architecture

### Core Functions (Implementation Order)

```python
# 0. Exception classes
class InvalidWindowSpec(ValueError): ...
class PerformanceWarning(UserWarning): ...

# 1. Input validation
def _validate_sliding_window_inputs(...) -> None: ...

# 2. Zero-copy foundation (CRITICAL)
def _build_bin_index_map(
    df: pd.DataFrame,
    group_columns: List[str],
    selection: Optional[pd.Series]
) -> Dict[Tuple[int, ...], List[int]]:
    """Build map: bin_tuple -> [row_indices]."""

# 3. Neighbor generation
def _generate_neighbor_offsets(window_spec: Dict) -> List[Tuple]: ...
def _get_neighbor_bins(...) -> List[Tuple]: ...

# 4. Zero-copy aggregator (CORE)
def _aggregate_window_zerocopy(
    df: pd.DataFrame,
    center_bins: List[Tuple],
    bin_map: Dict[Tuple, List[int]],
    ...
) -> pd.DataFrame:
    """
    For each center:
    1. Get neighbors
    2. Look up row indices
    3. Aggregate values (zero-copy view)
    4. Compute mean, std, median, entries
    """

# 5. Simple formula parsing
def _parse_fit_formula(formula: str) -> Tuple[str, List[str]]: ...

# 6. Regression (reuse v4)
def _fit_window_regression(...) -> pd.DataFrame:
    """Use sklearn LinearRegression/HuberRegressor."""

# 7. Result assembly
def _assemble_results(...) -> pd.DataFrame:
    """Add metadata to .attrs."""
```

---

## ✅ M7.1 Scope (Confirmed)

**What's included:**
- ✅ Integer bin coordinates ONLY (floats → v2.2+)
- ✅ Zero-copy accumulator (pure NumPy)
- ✅ Simple window_spec: `{'xBin': 2}` = ±2 bins
- ✅ Boundary: 'truncate' only
- ✅ Weighting: 'uniform' only
- ✅ Aggregations: mean, std, median, entries
- ✅ Linear regression: simple formula parsing + sklearn
- ✅ Selection mask support
- ✅ Metadata output
- ✅ Performance warnings

**What's deferred to M7.2:**
- ⏭️ Numba JIT compilation
- ⏭️ Mirror/periodic boundaries
- ⏭️ Distance/Gaussian weighting
- ⏭️ Rich window_spec format

**What's deferred to v2.2+:**
- ⏭️ Float coordinate support (distance-based neighbors)

---

## 🧪 Test Strategy

### Test Data (from MI answers)

1. **Unit tests:** Synthetic with known ground truth
   ```python
   # Ground truth: y = 2*x + noise
   df = _make_synthetic_3d_grid(n_bins_per_dim=10, entries_per_bin=50)
   ```

2. **Benchmarks:** Both synthetic + real TPC data (MI will provide)

### Test Coverage (20+ tests)

| Category | Count | Examples |
|----------|-------|----------|
| Basic functionality | 5 | 3D window, aggregation, linear fit |
| Input validation | 6 | Invalid specs, missing columns, wrong types |
| Edge cases | 5 | Single bin, sparse data, boundaries |
| New (from reviews) | 5 | Selection, metadata, warnings, v4 parity, reference |

---

## 📊 Benchmark Metrics (Standardized)

```python
class BenchmarkResult:
    scenario_name: str
    total_runtime_sec: float
    n_bins_total: int
    n_bins_fitted: int         # How many had successful fits
    n_bins_skipped: int        # How many skipped (<min_entries)
    bins_per_sec: float        # Throughput
    peak_memory_mb: float      # Memory usage
    avg_window_size: float     # Avg neighbors per bin
```

**Output format (for README):**
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

## 🎯 Success Criteria

### M7.1 Acceptance

- ✅ 20+ tests pass with >80% coverage
- ✅ Zero-copy accumulator implemented and validated
- ✅ Reference test confirms correctness vs. naive expansion
- ✅ Window=0 matches v4 results (parity test)
- ✅ Basic benchmark <5 min for 400k rows
- ✅ All metadata present in output
- ✅ Performance warnings work correctly
- ✅ Code review approved by MI + 1 AI reviewer

### M7.2 Acceptance

- ✅ Numba speedup ≥10× over M7.1
- ✅ TPC Spatial (405k rows): <1 min
- ✅ TPC Temporal (7M rows): <30 min
- ✅ Memory: <4GB
- ✅ All boundary modes work
- ✅ Weighting schemes implemented

---

## 🚀 Implementation Sequence

### Week 1-2: M7.1 Core

**Day 1-2:** Exception classes + input validation + bin index map
**Day 3-4:** Neighbor generation + zero-copy aggregator
**Day 5-6:** Formula parsing + fit logic (reuse v4)
**Day 7-8:** Result assembly + metadata
**Day 9-10:** Tests (20+) + documentation
**Day 11-12:** Benchmarks + review preparation

### Week 3-4 (possibly 5): M7.2 Numba

**Day 1-4:** Numba JIT compilation of core kernel
**Day 5-7:** Mirror/periodic boundaries
**Day 8-10:** Distance/Gaussian weighting
**Day 11-14:** Performance testing + optimization

### Week 5 (or 6): M7.3 Documentation

**Day 1-3:** User guide + API docs
**Day 4-5:** Example notebooks
**Day 6-7:** Final validation + v2.1.0 tag

---

## 🐍 Python 3.9.6 Compatibility

**Always use:**
```python
from __future__ import annotations
from typing import List, Dict, Optional, Union, Tuple, Callable

def func(x: List[str], y: Dict[str, int]) -> Optional[pd.DataFrame]:
    ...
```

**Never use (3.10+ only):**
```python
def func(x: list[str], y: dict[str, int]) -> pd.DataFrame | None:  # ❌
    ...
```

---

## 📚 Key Documents

**Primary references:**
1. **PHASE7_IMPLEMENTATION_PLAN.md** (27 pages, detailed plan)
2. **PHASE7_REVISION_SUMMARY.md** (this document's companion, change log)
3. **SLIDING_WINDOW_SPEC_DRAFT.md** (1856 lines, full specification)

**Existing code to reuse:**
- `groupby_regression_optimized.py` (v4 fit logic)
- `test_groupby_regression_optimized.py` (test patterns)
- `bench_groupby_regression_optimized.py` (benchmark patterns)

---

## ✅ Approval Status

| Reviewer | Status | Date | Notes |
|----------|--------|------|-------|
| GPT-4 | ✅ Approved | 2025-10-27 | With changes (all incorporated) |
| Gemini | ✅ Approved | 2025-10-27 | With changes (all incorporated) |
| Marian Ivanov | ⏳ Pending | - | Final approval needed |

---

## 🎬 Ready to Start?

**Upon MI approval, Claude will:**

1. Create `groupby_regression_sliding_window.py`
2. Implement zero-copy accumulator (MEM-3)
3. Write 20+ tests
4. Create benchmarks
5. Request M7.1 review

**Estimated M7.1 completion:** 1-2 weeks

---

## 💬 Questions Already Answered

✅ **Test Data:** Synthetic for tests, real for benchmarks  
✅ **Code Organization:** Standalone file `groupby_regression_sliding_window.py`  
✅ **Dependencies:** statsmodels/scipy OK, but not using statsmodels  
✅ **Priority Features:** Non-linear models via callable interface (included)  
✅ **Performance Target:** Numba from start if possible (M7.1 prototype, M7.2 optimized)  

---

**Status:** 🟢 **Ready to begin M7.1 implementation**

**Next Action:** MI final approval → Claude starts coding
