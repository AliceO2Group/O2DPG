# Review Form: Phase 7 M7.1 - Physical Correctness & Algorithms

**Reviewer:** Gemini (Google)  
**Date:** _____________  
**Files Reviewed:**
- test_groupby_regression_sliding_window.py (923 lines, 26 tests)
- groupby_regression_sliding_window.py (implementation)

---

## 📋 Part 1: Physical Model Validation

### Synthetic Data Realism

| Criterion | Status | Notes |
|-----------|--------|-------|
| **TPC Geometry** | ☐ ✅ ☐ ❌ | Bins reflect realistic detector? |
| **Distortion Physics** | ☐ ✅ ☐ ❌ | y = 2x model reasonable? |
| **Noise Levels** | ☐ ✅ ☐ ❌ | σ=0.5 realistic for TPC? |
| **Bin Spacing** | ☐ ✅ ☐ ❌ | ~1 cm appropriate? |
| **Entry Counts** | ☐ ✅ ☐ ❌ | 50 per bin reasonable? |
| **Sparsity Patterns** | ☐ ✅ ☐ ❌ | 30% empty bins realistic? |

**Comments on physical realism:**
___________________________________________________________________
___________________________________________________________________

---

### Test Data Generators

**_make_synthetic_3d_grid:**
- [ ] Ground truth (y = 2x) is recoverable
- [ ] Noise level appropriate
- [ ] Random seed ensures reproducibility
- [ ] Bin coordinates are integers
- **Issue (if any):** _________________________________________________

**_make_sparse_grid:**
- [ ] Sparsity parameter works correctly
- [ ] Empty bins distributed realistically
- [ ] Preserves data quality in occupied bins
- **Issue (if any):** _________________________________________________

**_make_boundary_test_grid:**
- [ ] Small enough for manual verification
- [ ] Covers corner/edge/center cases
- [ ] Suitable for boundary condition testing
- **Issue (if any):** _________________________________________________

---

## 📋 Part 2: Algorithm Correctness

### Zero-Copy Accumulator

| Criterion | Status | Notes |
|-----------|--------|-------|
| **Hash Map Logic** | ☐ Correct ☐ Flawed | bin → [indices] mapping |
| **Index Lookup** | ☐ Correct ☐ Flawed | O(1) expected? |
| **Memory Efficiency** | ☐ ✅ ☐ ❌ | No data replication? |
| **Correctness Proof** | ☐ Valid ☐ Invalid | Mathematically sound? |

**Mathematical validation:**
- Zero-copy approach equivalent to naive groupby? ☐ Yes ☐ No
- Index slicing preserves data order? ☐ Yes ☐ No
- Edge cases handled (empty bins, single entry)? ☐ Yes ☐ No

**Comments:**
___________________________________________________________________
___________________________________________________________________

---

### Neighbor Generation

**_generate_neighbor_offsets:**
- [ ] Combinatorial product correct
- [ ] Range [-size, +size] inclusive
- [ ] Order doesn't matter (but should be deterministic)
- [ ] Example: window_spec={'x': 1, 'y': 1} → 9 offsets ✅

**Test case verification:**
```
window_spec = {'xBin': 1, 'yBin': 1, 'zBin': 0}
Expected offsets: 9 (3×3×1)
Check: center (0,0,0) + all 9 offsets correct? ☐ Yes ☐ No
```

**_get_neighbor_bins:**
- [ ] Boundary truncation correct
- [ ] Doesn't generate out-of-range bins
- [ ] Corner bins have fewer neighbors ✅
- [ ] Center bins have max neighbors ✅

**Boundary condition test:**
```
Center bin: (1, 1, 1) in 3×3×3 grid, window=1
Expected neighbors: 27 (all in range)
Corner bin: (0, 0, 0) in 3×3×3 grid, window=1
Expected neighbors: 8 (truncated at boundaries)
Check: Implementation matches? ☐ Yes ☐ No
```

---

### Aggregation Functions

| Statistic | Formula Check | Notes |
|-----------|---------------|-------|
| **Mean** | ☐ ✅ ☐ ❌ | np.average(x, weights) |
| **Std** | ☐ ✅ ☐ ❌ | Weighted variance formula correct? |
| **Median** | ☐ ✅ ☐ ❌ | np.median (unweighted OK?) |
| **Entries** | ☐ ✅ ☐ ❌ | Count correct |
| **Q10, Q90** | ☐ ✅ ☐ ❌ | Percentiles |
| **RMS** | ☐ ✅ ☐ ❌ | sqrt(mean(x²)) |

**Weighted statistics validation:**
- Weighted mean formula: μ = Σ(wᵢxᵢ) / Σwᵢ
- Check implementation: ☐ Correct ☐ Incorrect

- Weighted variance: σ² = Σwᵢ(xᵢ - μ)² / Σwᵢ
- Check implementation: ☐ Correct ☐ Incorrect

**Comments:**
___________________________________________________________________

---

### Regression Fitting

**Linear Model Recovery:**
- Ground truth: y = 2x + ε, ε ~ N(0, 0.5)
- Expected slope: ≈ 2.0 ± 0.1
- Expected intercept: ≈ 0.0 ± 0.1
- Check: Tests verify this? ☐ Yes ☐ No

**OLS Fitting:**
- [ ] Uses statsmodels correctly
- [ ] Formula parsing correct
- [ ] Coefficients extracted properly
- [ ] R² calculation correct
- [ ] RMSE calculation correct

**WLS Fitting:**
- [ ] Weights applied to fitting
- [ ] Results differ from OLS ✅
- [ ] Heavier weights → more influence ✅

**GLM/RLM (if implemented):**
- [ ] Family specification correct
- [ ] M-estimator configuration correct
- [ ] Converges reliably

---

## 📋 Part 3: Numerical Stability

### Edge Cases

| Scenario | Handled? | Notes |
|----------|----------|-------|
| **Empty window** | ☐ ✅ ☐ ❌ | No crash, skip or flag |
| **Single data point** | ☐ ✅ ☐ ❌ | Can't fit, but no crash |
| **All same value** | ☐ ✅ ☐ ❌ | Zero variance handled |
| **Extreme outliers** | ☐ ✅ ☐ ❌ | Doesn't break fitting |
| **Division by zero** | ☐ ✅ ☐ ❌ | Protected |
| **NaN/Inf handling** | ☐ ✅ ☐ ❌ | Propagated or filtered |

**Test verification:**
- test_empty_window_handling passes? ☐ Yes ☐ No
- test_all_sparse_bins passes? ☐ Yes ☐ No
- test_single_bin_dataset passes? ☐ Yes ☐ No

---

### Numerical Precision

**Floating-point issues:**
- [ ] No catastrophic cancellation
- [ ] Stable variance calculation (avoids (x̄)² - x̄²)
- [ ] Appropriate tolerances in comparisons
- [ ] Uses np.isclose / np.allclose for tests

**Large dataset concerns:**
- [ ] Memory doesn't grow unboundedly
- [ ] Integer overflow prevented (bin indices)
- [ ] Accumulator precision sufficient

---

## 📋 Part 4: TPC Use Case Validation

### Calibration Workflow Compatibility

| Criterion | Status | Notes |
|-----------|--------|-------|
| **3D-6D Support** | ☐ Ready ☐ Partial | Scales to 6D? |
| **Sparse Data** | ☐ ✅ ☐ ❌ | Handles 30-70% empty bins? |
| **Window Sizes** | ☐ Realistic ☐ Too large/small | For TPC: 1-3 bins typical |
| **Statistical Thresholds** | ☐ ✅ ☐ ❌ | min_entries=10 reasonable? |
| **Performance** | ☐ Meets target ☐ Too slow | <5 min for 400k rows? |
| **Memory Usage** | ☐ ✅ ☐ ❌ | <4GB realistic? |

**TPC-specific checks:**
- Distortion parameterization supported? ☐ Yes ☐ No
- Quality flags match calibration QA? ☐ Yes ☐ No
- Output format RootInteractive-compatible? ☐ Yes ☐ No

---

### Real Data Readiness

**What would break with real TPC data:**
1. _______________________________________________________________
2. _______________________________________________________________
3. _______________________________________________________________

**What additional validation is needed:**
1. _______________________________________________________________
2. _______________________________________________________________

---

## 📋 Part 5: Statistical Validity

### Regression Diagnostics

| Metric | Computed? | Correct? | Notes |
|--------|-----------|----------|-------|
| **R²** | ☐ ✅ ☐ ❌ | ☐ ✅ ☐ ❌ | 1 - SS_res/SS_tot |
| **RMSE** | ☐ ✅ ☐ ❌ | ☐ ✅ ☐ ❌ | sqrt(mean(residuals²)) |
| **Coefficient errors** | ☐ ✅ ☐ ❌ | ☐ ✅ ☐ ❌ | From statsmodels |
| **n_fitted** | ☐ ✅ ☐ ❌ | ☐ ✅ ☐ ❌ | Sample size |

**Uncertainty propagation:**
- Window aggregation increases n_eff ✅
- Parameter errors should decrease with window size ✅
- Check: Tests verify this? ☐ Yes ☐ No

---

### Test Coverage of Statistical Properties

**Tests verify:**
- [ ] Mean recovery correct
- [ ] Variance scales with sample size
- [ ] Regression coefficients unbiased
- [ ] Weighted regression differs from unweighted
- [ ] Larger windows → smaller uncertainties

**Missing statistical tests:**
1. _______________________________________________________________
2. _______________________________________________________________

---

## 📋 Part 6: Test Execution Analysis

### Pytest Results

**Paste test output:**
```
[pytest output here]
```

**Categorized results:**
| Category | Expected | Passed | Failed | Skipped |
|----------|----------|--------|--------|---------|
| Data generators | 3 | __ | __ | __ |
| Basic functionality | 5 | __ | __ | __ |
| Input validation | 6 | __ | __ | __ |
| Edge cases | 5 | __ | __ | __ |
| Review-added | 5 | __ | __ | __ |
| Statsmodels | 3 | __ | __ | __ |
| Bonus tests | 2 | __ | __ | __ |
| **TOTAL** | **26+** | **__** | **__** | **__** |

---

## 🐛 Issues Found

### Mathematical/Algorithmic Errors

**Error #1:**
- **Location:** function/line
- **Issue:** Mathematical mistake description
- **Impact:** Incorrect results / wrong values
- **Fix:** Corrected formula/algorithm

**Error #2:**
...

---

### Physical Model Issues

**Issue #1:**
- **Location:** synthetic data generator
- **Issue:** Unrealistic parameter/assumption
- **Impact:** Tests may pass but not reflect reality
- **Fix:** ...

---

### Numerical Instability

**Issue #1:**
- **Scenario:** When this happens...
- **Problem:** Numerical issue (overflow, cancellation, etc.)
- **Fix:** ...

---

## ✅ Domain Expert Assessment

### Overall Algorithm Quality

**Zero-copy accumulator:**
- [ ] Mathematically sound
- [ ] Computationally efficient
- [ ] Handles edge cases
- **Rating:** ☐ Excellent ☐ Good ☐ Needs work

**Sliding window logic:**
- [ ] Neighbor generation correct
- [ ] Boundary handling appropriate
- [ ] Scales to higher dimensions
- **Rating:** ☐ Excellent ☐ Good ☐ Needs work

**Statistical methods:**
- [ ] Aggregations correct
- [ ] Regression fitting sound
- [ ] Uncertainty handling proper
- **Rating:** ☐ Excellent ☐ Good ☐ Needs work

---

### Suitability for TPC Calibration

**Strengths:**
1. _______________________________________________________________
2. _______________________________________________________________
3. _______________________________________________________________

**Weaknesses:**
1. _______________________________________________________________
2. _______________________________________________________________

**Risks for production:**
1. _______________________________________________________________
2. _______________________________________________________________

---

## 🎯 Recommendation

**Select ONE:**

☐ **APPROVE M7.1** - Algorithms correct, ready for production
- Mathematical correctness verified
- Physical model reasonable
- Numerical stability adequate
- TPC use case validated

☐ **APPROVE WITH FIXES** - Minor corrections needed
- Issues to fix:
  1. _______________
  2. _______________
- Re-review: ☐ Not needed ☐ Quick check

☐ **REQUEST MAJOR FIXES** - Algorithm flaws found
- Critical errors:
  1. _______________
  2. _______________
- Re-review: Full validation required

☐ **REJECT** - Fundamental problems
- Reasons:
  1. _______________
  2. _______________
- Action: Algorithmic redesign needed

---

## 📝 Detailed Comments

### Algorithm Strengths

1. _______________________________________________________________
2. _______________________________________________________________
3. _______________________________________________________________

### Algorithm Concerns

1. _______________________________________________________________
2. _______________________________________________________________
3. _______________________________________________________________

### Recommendations for M7.2

1. _______________________________________________________________
2. _______________________________________________________________

---

**Reviewer Signature:** Gemini  
**Date:** ______________  
**Review Duration:** ______ hours  
**Domain Confidence:** ☐ High ☐ Medium ☐ Low

---

## 📎 Supporting Analysis

- [ ] Manual calculation verification (for small test case)
- [ ] Comparison with reference implementation
- [ ] Benchmark results (if performance measured)
- [ ] Additional test suggestions for M7.2
