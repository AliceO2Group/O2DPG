# Phase 7 Kickoff: Sliding Window Regression Implementation

**Date:** 2025-10-27  
**Status:** 🟢 Ready to Begin  
**Team:** Marian Ivanov (MI) + Claude | Reviewers: GPT-4, Gemini

---

## What We're Building

A **Sliding Window GroupBy Regression** framework that enables:

- **Local PDF estimation** in high-dimensional sparse data (3D-6D+)
- **Multi-dimensional window aggregation** with configurable boundaries
- **Memory-efficient processing** (<4GB, handles 7M+ rows)
- **High performance** (<30 min for production TPC calibration)
- **Integration** with existing v2.0.0 GroupBy Regressor engines

**Primary Use Case:** ALICE TPC distortion maps and tracking performance parameterization

---

## Core Innovation

Transform sparse bin-based analysis:

```
Before: Isolated bins with insufficient statistics (10-100 events)
After:  Local aggregation using ±1 neighbors (270-2700 events)
Result: Reliable PDF estimation and robust regression
```

**Example:** TPC spatial calibration with 405k rows × 5 maps:
- **152 × 20 × 28 = 85k spatial bins**
- **±1 window = 3³ = 27 neighbors per bin**
- **Median aggregation: ~2800 → ~75k events per window**

---

## Implementation Strategy

### Three-Milestone Approach

| Milestone | Scope | Duration | Output |
|-----------|-------|----------|--------|
| **M7.1** | Core API + Basic Tests | 1-2 weeks | Working prototype (numpy) |
| **M7.2** | Numba + Advanced Features | 1-2 weeks | Production-ready (10-100× speedup) |
| **M7.3** | Documentation + Polish | 1 week | Release v2.1.0 |

**Total timeline:** 3-5 weeks to v2.1.0 tag

---

## M7.1: Core Implementation (Priority)

### What We'll Build First

**File:** `groupby_regression_sliding_window.py`

**Main API:**
```python
def make_sliding_window_fit(
    df: pd.DataFrame,
    group_columns: List[str],              # ['xBin', 'y2xBin', 'z2xBin']
    window_spec: Dict[str, int],           # {'xBin': 2, 'y2xBin': 1, 'z2xBin': 1}
    fit_columns: List[str],                # ['dX', 'dY', 'dZ']
    predictor_columns: List[str],          # ['meanIDC', 'deltaIDC']
    fit_formula: Optional[str] = None,     # 'target ~ meanIDC + deltaIDC'
    aggregation_functions: Optional[Dict] = None,
    weights_column: Optional[str] = None,
    min_entries: int = 10,
    backend: str = 'numba',                # M7.1: 'numpy' only
    **kwargs
) -> pd.DataFrame
```

**M7.1 Scope (Minimum Viable Product):**
- ✅ Integer bin coordinates only
- ✅ Simple window_spec: `{'xBin': 2}` means ±2 bins
- ✅ Boundary: 'truncate' only (no mirror/periodic)
- ✅ Weighting: 'uniform' only
- ✅ Aggregation: mean, std, entries (default)
- ✅ Linear regression: statsmodels-style formulas
- ✅ Backend: numpy (Numba in M7.2)

**What's Deferred to M7.2:**
- ❌ Mirror/periodic boundaries
- ❌ Distance/Gaussian weighting
- ❌ Numba optimization
- ❌ Rich window_spec format
- ❌ Custom fit functions (callables)

### Key Functions to Implement

```python
# 1. Input validation
def _validate_sliding_window_inputs(...) -> None

# 2. Window generation (core algorithm)
def _generate_window_bins(
    center_bins: pd.DataFrame,    # Unique group values
    window_spec: Dict[str, int],  # Window sizes
    boundary: str = 'truncate'
) -> pd.DataFrame:
    """
    For each center bin, generate all neighbor bins within window.
    
    Example:
        center = (xBin=10, y2xBin=5, z2xBin=15)
        window_spec = {'xBin': 1, 'y2xBin': 1, 'z2xBin': 1}
        
        Output: 27 rows (3×3×3 neighbors)
        center_xBin  center_y2xBin  center_z2xBin  neighbor_xBin  neighbor_y2xBin  neighbor_z2xBin
        10           5              15             9              4                14
        10           5              15             9              4                15
        ...
        10           5              15             11             6                16
    """

# 3. Data aggregation
def _aggregate_window_data(
    df: pd.DataFrame,
    window_bins: pd.DataFrame,
    agg_funcs: Dict[str, List[str]]
) -> pd.DataFrame:
    """
    Merge df with window_bins, group by center, compute aggregations.
    """

# 4. Regression execution
def _fit_window_regression(
    aggregated_data: pd.DataFrame,
    fit_formula: str,
    min_entries: int
) -> pd.DataFrame:
    """
    For each center bin (with sufficient data), fit linear model.
    """

# 5. Result assembly
def _assemble_results(...) -> pd.DataFrame:
    """
    Combine aggregated stats + fit results into final DataFrame.
    """
```

### Test Suite (15+ tests)

```python
# Basic functionality
test_sliding_window_basic_3d()
test_sliding_window_aggregation()
test_sliding_window_linear_fit()
test_empty_window_handling()
test_min_entries_enforcement()

# Input validation
test_invalid_window_spec()
test_missing_columns()
test_mixed_data_types()
test_negative_min_entries()
test_invalid_fit_formula()

# Edge cases
test_single_bin_dataset()
test_all_sparse_bins()
test_boundary_bins()
test_multi_target_fit()
test_weighted_aggregation()
```

### Benchmarks (3 scenarios)

```python
# Quick validation
bench_small_3d:   10×10×10 bins, ±1 window → <10s

# Realistic test data
bench_medium_3d:  50×20×30 bins, ±1 window → <2min

# Stress test
bench_sparse_3d:  100×50×50 bins (50% empty), ±2 window → <5min
```

---

## Technical Challenges & Solutions

### Challenge 1: Memory Explosion

**Problem:** Naive expansion creates 27× (or 125×) data replication

**Solution:**
- Use window_bins DataFrame (center → neighbor mapping) instead of replicating df
- Merge only once during aggregation
- Zero-copy views where possible

### Challenge 2: Neighbor Generation Efficiency

**Problem:** Nested loops over dimensions slow for large grids

**Solution (M7.1):**
```python
# Use itertools.product for combinatorial generation
import itertools

def _generate_offsets(window_sizes: Dict[str, int]) -> List[Tuple[int, ...]]:
    """
    Generate all offset combinations.
    
    Example:
        window_sizes = {'xBin': 1, 'yBin': 1}
        Returns: [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 0), (0, 1), (1, -1), (1, 0), (1, 1)]
    """
    ranges = [range(-w, w+1) for w in window_sizes.values()]
    return list(itertools.product(*ranges))
```

**Solution (M7.2):**
- Numba-compiled nested loops (faster than Python)
- Dense array lookup for small grids

### Challenge 3: Boundary Handling

**M7.1 Approach (Truncate only):**
```python
def _clip_to_valid_range(bins: np.ndarray, min_val: int, max_val: int) -> np.ndarray:
    """
    Remove out-of-range bins (truncate).
    
    Example:
        bins = [-1, 0, 1, 2, 150, 151, 152]  # xBin with max=151
        Returns: [0, 1, 2, 150, 151]
    """
    mask = (bins >= min_val) & (bins <= max_val)
    return bins[mask]
```

---

## Code Structure & Style

### Follow Existing Patterns

Reference `groupby_regression_optimized.py` for:
- Function naming: `make_*`, `_private_helper`
- Type hints: `List[str]`, `Optional[Dict]`, `pd.DataFrame`
- Docstrings: NumPy style with sections (Parameters, Returns, Examples)
- Error handling: Raise `ValueError` with clear messages

### Example Function Template

```python
def _generate_window_bins(
    center_bins: pd.DataFrame,
    window_spec: Dict[str, int],
    boundary: str = 'truncate'
) -> pd.DataFrame:
    """
    Generate neighbor bins for each center bin within sliding window.

    Parameters
    ----------
    center_bins : pd.DataFrame
        Unique combinations of group_columns values (center bins).
        Must contain columns matching window_spec keys.
    
    window_spec : Dict[str, int]
        Window size for each dimension. Keys are column names, values are
        integer half-widths (e.g., {'xBin': 2} means ±2 bins = 5 total).
    
    boundary : str, default='truncate'
        Boundary handling mode. M7.1 supports 'truncate' only.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - center_* : Original group column values (center bin)
        - neighbor_* : Neighbor bin values within window
        
        Length: n_centers × n_neighbors_per_window

    Examples
    --------
    >>> centers = pd.DataFrame({'xBin': [5, 10], 'yBin': [3, 8]})
    >>> window_spec = {'xBin': 1, 'yBin': 1}
    >>> result = _generate_window_bins(centers, window_spec)
    >>> len(result)
    18  # 2 centers × 9 neighbors (3×3)

    Notes
    -----
    - For ±1 window in N dimensions, generates 3^N neighbors per center
    - Boundary='truncate' removes out-of-range bins (partial windows at edges)
    - Output is sorted by center_*, then neighbor_*
    """
    # Implementation here
    pass
```

---

## Review Process

### Review Forms Provided

Each milestone has a dedicated review form in `PHASE7_IMPLEMENTATION_PLAN.md`:

1. **M7.1 Review Form** (page 12)
   - Functionality review (6 criteria)
   - Code quality review (6 criteria)
   - Test coverage review (5 criteria)
   - Performance review (4 criteria)

2. **M7.2 Review Form** (page 18)
   - Performance review (4 metrics)
   - Feature completeness (6 features)
   - Integration testing (4 tests)

3. **M7.3 Review Form** (page 23)
   - Documentation review (5 criteria)
   - Completeness review (7 features)
   - Quality gates (6 gates)

### Review Workflow

```
Claude implements → MI reviews (mandatory) → AI review (GPT or Gemini) → Iterate or approve
```

**Review criteria:**
- ✅ **Pass:** Approve to next milestone
- ⚠️ **Approve with changes:** Minor issues, proceed with fixes
- ❌ **Major revision:** Block until critical issues resolved

---

## Next Actions

### Immediate (Today)

1. **MI:** Review `PHASE7_IMPLEMENTATION_PLAN.md`
   - Check milestone scope and timeline
   - Verify technical approach
   - Sign plan review form (page 26)

2. **GPT or Gemini:** Review plan for completeness
   - Identify gaps or risks
   - Suggest improvements
   - Sign plan review form

3. **All:** Approve plan OR provide revision requests

### After Plan Approval

4. **Claude:** Begin M7.1 implementation
   - Create `groupby_regression_sliding_window.py`
   - Implement core functions
   - Write initial tests

5. **MI:** Provide test data
   - Share `tpc_realistic_test.parquet` (if available)
   - Or specify synthetic data requirements

---

## Questions for MI

Before starting implementation:

1. **Test Data:** Do you have `tpc_realistic_test.parquet` (405k rows, 5 maps)?
   - If yes: Claude can use real data for validation
   - If no: Claude will generate synthetic 3D grid data

2. **Existing Code Integration:** Should M7.1 be:
   - ☐ Standalone file (`groupby_regression_sliding_window.py`)
   - ☐ Integrated into `groupby_regression_optimized.py`
   
   **Recommendation:** Standalone for M7.1 (easier to test), integrate in M7.2 if desired

3. **Dependencies:** Any constraints on new dependencies?
   - Current: pandas, numpy, numba, sklearn
   - Potential additions: statsmodels (formula parsing), scipy (LTM)

4. **Priority Features:** If timeline is tight, which M7.2 features are must-have?
   - ☐ Mirror boundary (ALICE TPC symmetry)
   - ☐ Periodic boundary (φ angles)
   - ☐ Distance weighting
   - ☐ Gaussian weighting
   
   **All are "nice to have" but can be prioritized**

5. **Performance Baseline:** What's acceptable M7.1 performance?
   - Spec target: <30 min for 7M rows (M7.2 with Numba)
   - M7.1 numpy: 10-100× slower = 5-50 hours (impractical)
   - **Suggested M7.1 target:** <5 min for 400k rows (demo scale)

---

## Resources

**Documents:**
- **Full Plan:** `/mnt/user-data/outputs/PHASE7_IMPLEMENTATION_PLAN.md` (27 pages)
- **Specification:** `SLIDING_WINDOW_SPEC_DRAFT.md` (1856 lines, comprehensive)
- **Baseline Code:**
  - `groupby_regression.py` (robust baseline)
  - `groupby_regression_optimized.py` (v2/v3/v4 engines)
- **Test Templates:**
  - `test_groupby_regression.py`
  - `test_groupby_regression_optimized.py`
- **Benchmark Templates:**
  - `bench_groupby_regression.py`
  - `bench_groupby_regression_optimized.py`

**Key Sections in Spec:**
- Section 1: Motivation (lines 1-220)
- Section 2: Example Data (lines 221-450)
- Section 6: Requirements (lines 645-1720)
  - 6.2.1: API signature (lines 809-900)
  - 6.2.2: Window specification (lines 901-976)
  - 6.2.3: Fit function interface (lines 977-1059)

---

## Success Metrics

### M7.1 Success

- ✅ 15+ tests pass with >80% coverage
- ✅ Basic benchmark <5 min for 400k rows
- ✅ Real TPC data (if available) processes without errors
- ✅ Code review approved by MI + 1 AI reviewer

### M7.2 Success

- ✅ 35+ tests pass with >85% coverage
- ✅ TPC Spatial (405k rows): <1 min
- ✅ TPC Temporal (7M rows): <30 min
- ✅ Numba speedup: ≥10×
- ✅ Memory: <4GB

### M7.3 Success (Release Criteria)

- ✅ Complete user guide + 4 example notebooks
- ✅ All API docstrings complete
- ✅ README updated
- ✅ Zero critical bugs
- ✅ All review forms approved

---

## Contact & Collaboration

**Primary collaboration mode:** This conversation interface

**Artifacts:**
- Implementation plan: Available now
- Code files: Will be created in `/mnt/user-data/outputs/`
- Review forms: Printable from plan document

**Async workflow:**
1. Claude implements → saves to `/mnt/user-data/outputs/`
2. MI downloads → reviews locally → provides feedback
3. AI reviewers (GPT/Gemini) review shared artifacts
4. Iterate until approval

---

## Ready to Start?

Once the plan is approved, Claude will:

1. Create `groupby_regression_sliding_window.py` with M7.1 scope
2. Implement core functions following existing code patterns
3. Write 15+ tests in `test_groupby_regression_sliding_window.py`
4. Create basic benchmark suite
5. Generate synthetic test data (or use provided TPC data)
6. Request M7.1 review

**Estimated time for M7.1 implementation:** 1-2 weeks of focused work

---

**Status:** 🟢 Plan complete, awaiting approval to proceed

**Next Reviewer:** Marian Ivanov (MI) - please review and provide feedback
