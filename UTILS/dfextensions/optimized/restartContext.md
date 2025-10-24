# Restart Context: GroupBy Regression Optimization - Phase 3 (Numba)

**Date:** October 23, 2025  
**Current Phase:** Phase 3 - Numba Implementation (v4)  
**Status:** Awaiting fixes after code review  
**Git Branch:** `feature/groupby-optimization`

---

## Current Situation

You (GPT) implemented Phase 3 Numba optimization (v3/v4). Claude reviewed the code and found it **excellent overall** but identified **2 critical blocking issues** that must be fixed before benchmarking.

**Test Status:** 19/19 tests passing ✅  
**Benchmark Status:** Not yet run (blocked by critical issues)

---

## What You Already Implemented ✅

### v3: Pure NumPy Baseline
- **Function:** `make_parallel_fit_v3()`
- **Lines:** 441-617 in `groupby_regression_optimized.py`
- **Status:** ✅ Complete and correct
- **Features:**
  - Single-process, vectorized NumPy
  - Supports weights
  - Computes RMS/MAD diagnostics
  - Uses `np.linalg.solve` for OLS

### v4: Numba JIT Kernel
- **Function:** `make_parallel_fit_v4()`
- **Lines:** 640-848 in `groupby_regression_optimized.py`
- **Kernel:** `_ols_kernel_numba()` (lines 640-740)
- **Status:** ⚠️ Needs 2 critical fixes
- **Features Implemented:**
  - Numba JIT compilation (`@njit`)
  - Gauss-Jordan solver (correct implementation)
  - Handles singular matrices
  - Partial pivoting for numerical stability
  - Contiguous group processing via sorting

### Test Coverage
- **Test:** `test_numba_backend_consistency()` (line 873 in test file)
- **Result:** ✅ Passes - v4 matches v3 within 1e-6
- **All 19 tests passing**

---

## 🔴 CRITICAL ISSUES TO FIX (BLOCKING)

### Issue 1: Weights Not Implemented in v4

**Problem:**
```python
# v3 correctly implements weights (lines 541-545):
if weights is not None:
    w = g_df[weights].to_numpy(dtype=np.float64, copy=False)
    sw = np.sqrt(w)
    X = X * sw[:, None]
    y = y * sw[:, None]

# v4 accepts 'weights' parameter (line 752) but IGNORES it!
# The kernel doesn't use weights at all
```

**Why Critical:**
- User's TPC calibration workflow requires weighted regression
- Without weights, v4 is **not production-ready**
- All tests pass because test data uses `weight=1.0` (uniform weights)

**What Needs to Change:**

1. **Modify `_ols_kernel_numba` signature** (line 641):
   ```python
   # OLD:
   def _ols_kernel_numba(X_all, Y_all, offsets, n_groups, n_feat, n_tgt, out_beta):
   
   # NEW:
   def _ols_kernel_numba(X_all, Y_all, W_all, offsets, n_groups, n_feat, n_tgt, out_beta):
   ```

2. **Apply sqrt(weights) inside kernel** (around lines 659-663):
   ```python
   # Inside the group loop, after extracting Xg and Yg:
   Xg = X_all[i0:i1]
   Yg = Y_all[i0:i1]
   Wg = W_all[i0:i1]  # NEW
   
   # Build X1 with intercept AND apply weights
   X1 = np.ones((m, n_feat+1))
   for r in range(m):
       sw = np.sqrt(Wg[r])  # NEW: square root of weight
       X1[r, 0] = sw         # NEW: weighted intercept
       for c in range(n_feat):
           X1[r, c+1] = Xg[r, c] * sw  # NEW: weighted predictors
   
   # Also weight Y
   Y_weighted = np.empty((m, Yg.shape[1]))
   for r in range(m):
       sw = np.sqrt(Wg[r])
       for t in range(Yg.shape[1]):
           Y_weighted[r, t] = Yg[r, t] * sw
   
   # Then use Y_weighted instead of Yg in XtY computation (line 674-681)
   ```

3. **Extract W_all in v4 wrapper** (around line 790-791):
   ```python
   X_all = dfs[linear_columns].to_numpy(dtype=np.float64, copy=False)
   Y_all = dfs[fit_columns].to_numpy(dtype=np.float64, copy=False)
   
   # NEW: Extract weights
   if weights is not None:
       W_all = dfs[weights].to_numpy(dtype=np.float64, copy=False)
   else:
       W_all = np.ones(len(dfs), dtype=np.float64)  # Uniform weights
   ```

4. **Pass W_all to kernel** (line 798):
   ```python
   # OLD:
   _ols_kernel_numba(X_all, Y_all, offsets, n_groups, n_feat, n_tgt, beta)
   
   # NEW:
   _ols_kernel_numba(X_all, Y_all, W_all, offsets, n_groups, n_feat, n_tgt, beta)
   ```

5. **Update fallback code** (lines 800-812) to also use weights

**Test After Fix:**
```bash
# Modify test to use non-uniform weights:
df["weight"] = np.random.uniform(0.5, 1.5, len(df))

# v4 should still match v3
pytest test_groupby_regression_optimized.py::test_numba_backend_consistency -v
```

---

### Issue 2: Benchmark Expects v3/v4 Naming

**Problem:**
- Benchmark script calls `make_parallel_fit_v3` and `make_parallel_fit_v4`
- Naming is now standardized: v3 = NumPy, v4 = Numba
- No `make_parallel_fit_fast` needed (user confirmed)

**What to Check:**
- Ensure `bench_groupby_regression_optimized.py` uses correct function names
- Should compare: `loky` (v2) vs `v3` (NumPy) vs `v4` (Numba)

**Expected benchmark output:**
```python
def cfg_v3():
    return make_parallel_fit_v3(...)

def cfg_v4():
    return make_parallel_fit_v4(...)
```

---

## 🟡 IMPORTANT (NOT BLOCKING)

### Issue 3: RMS/MAD Diagnostics Missing in v4

**What v3 has (lines 556-558):**
```python
y_pred = X @ beta
resid = y - y_pred
rms = np.sqrt(np.mean(resid ** 2, axis=0))
```

**What v4 needs:**
- After kernel completes (line 813), compute residuals
- Add `rms` column to dfGB output
- Matches v3 schema for compatibility

**Add around line 822:**
```python
# After assembling basic row dict:
row = {key: gid}
for t_idx, tname in enumerate(fit_columns):
    row[f"{tname}_intercept{suffix}"] = beta[gi, 0, t_idx]
    for j, cname in enumerate(linear_columns, start=1):
        row[f"{tname}_slope_{cname}{suffix}"] = beta[gi, j, t_idx]
    
    # NEW: Compute RMS
    i0, i1 = offsets[gi], offsets[gi+1]
    Xg = X_all[i0:i1]
    Yg = Y_all[i0:i1]
    X1 = np.c_[np.ones(len(Xg)), Xg]
    y_pred = X1 @ beta[gi, :, t_idx]
    resid = Yg[:, t_idx] - y_pred
    row[f"{tname}_rms{suffix}"] = float(np.sqrt(np.mean(resid**2)))
```

---

## Files to Modify

### 1. `groupby_regression_optimized.py`
**Changes needed:**
- Line 641: Add `W_all` to kernel signature
- Lines 659-681: Apply sqrt(weights) to X and Y
- Line 790-791: Extract W_all from dataframe
- Line 798: Pass W_all to kernel
- Lines 800-812: Update fallback to use weights
- Line 822+: Add RMS computation (optional but recommended)

### 2. `bench_groupby_regression_optimized.py`
**Changes needed:**
- Verify function names are `make_parallel_fit_v3` and `make_parallel_fit_v4`
- Ensure benchmark compares all three: loky (v2), v3 (NumPy), v4 (Numba)

### 3. `test_groupby_regression_optimized.py`
**Changes needed:**
- Add test with non-uniform weights to verify v4 weights work
- Optional: Fix tolerance message (says "1e-8" but checks "1e-6")

---

## Expected Performance After Fixes

**Benchmark target (1000 groups × 5 rows):**
```
loky (v2, 4 jobs):  0.100s  (baseline)
v3 (NumPy serial):  0.339s  (3.4× slower - no parallelization)
v4 (Numba serial):  0.020s  (5× faster than v2) ← TARGET
```

**Why v4 should be fast:**
- No process spawn overhead
- JIT-compiled to native code
- Optimized memory access
- No Python interpreter in inner loop

**If v4 is slower than expected:**
- Check BLAS threads set to 1
- Verify JIT compilation happening
- Profile with Numba profiler

---

## Testing Protocol

### Step 1: Fix Code
1. Implement weights in v4 kernel
2. Add RMS diagnostics (optional)
3. Verify benchmark names correct

### Step 2: Run Tests
```bash
pytest test_groupby_regression_optimized.py -v -s
```
**Expected:** All 19 tests pass (including weighted test if added)

### Step 3: Run Benchmark
```bash
python bench_groupby_regression_optimized.py --phase3
```
**Expected output:**
```
loky     : 0.100s   (1.00×)
v3       : 0.339s   (0.29×)
v4       : 0.020s   (5.00×)  ← Target
```

### Step 4: Share Results
**Share with user:**
1. Modified files
2. Test output (all passing)
3. Benchmark output (showing speedup)
4. Brief summary of changes

---

## Code Quality Guidelines

### What Claude Praised ✅
- Clean separation of v3/v4
- Correct Gauss-Jordan implementation
- Proper partial pivoting
- Good test coverage
- Numerical accuracy validation

### What to Maintain
- Keep v3 unchanged (it's the reference)
- Match v3 API exactly in v4
- Same output schema (columns, dtypes)
- Same error handling (singular matrices → skip)

### What to Avoid
- Don't change v3 (it's working perfectly)
- Don't break existing tests
- Don't change API signatures
- Don't remove diagnostics

---

## Questions to Ask User (If Needed)

1. **If weights implementation is complex:**
   "Should I implement full weighted regression or defer to later?"
   (Answer: It's critical - must implement now)

2. **If RMS computation is slow:**
   "Should I compute RMS or skip for performance?"
   (Answer: Add it - users need it for quality checks)

3. **If benchmark shows v4 slower than expected:**
   "Benchmark shows v4 at XXXs (vs 0.020s target). Should I profile?"
   (Answer: Yes, and share profiling results)

---

## Success Criteria

**Code is ready when:**
- [x] v4 implements weights correctly
- [x] v4 adds RMS diagnostics
- [x] All 19+ tests pass
- [x] Benchmark shows v4 >3× faster than v2
- [x] Numerical accuracy maintained (<1e-6 error)
- [x] No regressions in v2/v3

**Then:**
- ✅ User will test on real TPC data
- ✅ Deploy to production
- ✅ Phase 3 complete!

---

## Current File Locations

```
/path/to/O2DPG/UTILS/dfextensions/optimized/
├── groupby_regression_optimized.py    ← MODIFY (add weights to v4)
├── test_groupby_regression_optimized.py  ← TEST (verify weights work)
├── bench_groupby_regression_optimized.py ← RUN (get speedup numbers)
└── [other docs...]
```

**Git branch:** `feature/groupby-optimization`

---

## Priority Actions (In Order)

1. 🔴 **CRITICAL:** Implement weights in v4 kernel (30 min)
2. 🔴 **CRITICAL:** Test weighted regression (10 min)
3. 🟡 **IMPORTANT:** Add RMS diagnostics (15 min)
4. ✅ **RUN:** Execute benchmark (5 min)
5. 📊 **SHARE:** Results with user (5 min)

**Total estimated time:** ~65 minutes

---

## Summary for Quick Restart

**You are here:**
- Phase 3 implementation done
- Code works but missing weights
- Need to fix 2 issues before benchmark
- User is waiting for benchmark results

**Next immediate action:**
1. Add `W_all` parameter to `_ols_kernel_numba`
2. Apply `sqrt(weights)` to X and Y inside kernel
3. Pass weights from v4 wrapper to kernel
4. Test and benchmark

**Goal:**
Get v4 to be 5× faster than v2 with correct weighted regression.

---

## Contact Context

**User's workflow:**
- TPC detector calibration (ALICE experiment)
- Thousands of small groups (3-10 rows each)
- Weighted regression is essential
- Needs 10× speedup for production

**User's preference:**
- Thorough reviews (Option B)
- Git feature branch strategy
- Fix issues before testing on real data

**Reviewers:**
- Claude: Detailed code review (this context file)
- Gemini: Confirmed warm-up methodology, approved approach

---

**Ready to continue! Please implement the weights fix first, then run tests and benchmark.** 🚀
