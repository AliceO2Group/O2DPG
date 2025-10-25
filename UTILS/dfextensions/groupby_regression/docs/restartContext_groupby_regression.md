# 🧭 **Restart Context — GroupBy Regression Transition (v2.0)**

*Last updated: 2025-10-25*  
*Status: 85% complete – transition to new package structure finished; benchmark + documentation remaining.*

---

## 🧩 **Project Summary**

The **GroupBy Regression refactoring** separates the **robust (legacy/production)** implementation and the **optimized (v2–v4)** implementations into a proper Python package under `O2DPG/UTILS/dfextensions/groupby_regression/`.

**Status:**
- ✅ All tests passing (41/41)
- ✅ Git history fully preserved via `git mv`
- ✅ Cross-validation and comparison benchmarks working
- 🟡 Remaining: New optimized-only benchmark + unified documentation

---

## 📁 **Current Directory Structure**
```
groupby_regression/
│
├── __init__.py                               # Package exports
│
├── groupby_regression.py                     # Robust / production implementation
├── groupby_regression_optimized.py           # Fast v2/v3/v4 implementations
│
├── docs/
│   └── groupby_regression.md                 # Robust internal documentation
│
├── tests/
│   ├── __init__.py
│   ├── test_groupby_regression.py            # Robust tests (14 tests)
│   ├── test_groupby_regression_optimized.py  # Optimized tests (24 tests)
│   └── test_cross_validation.py              # Cross-validation robust ↔ v2/v4 (3 tests)
│
├── benchmarks/
│   ├── __init__.py
│   ├── bench_groupby_regression.py           # Robust benchmark (working)
│   ├── bench_comparison.py                   # Robust ↔ v2/v4 comparison (working)
│   ├── bench_out/                            # Output directory
│   │   ├── benchmark_report.txt
│   │   └── benchmark_results.json
│   └── (TODO) bench_groupby_regression_optimized.py  # ← NEW: To be created
│
└── benchmark_results/
    ├── latest/                               # Current comparison results
    └── history.csv                           # Performance trend tracking
```

---

## ✅ **Completed Work**

### Phase 0 – Safety Tag
- ✅ Tag `v1.0-pre-restructure` created (safe rollback point)
- ✅ All tests passing at tag (38 tests)

### Phase 1 – Package Structure
- ✅ Created `groupby_regression/` directory with subdirectories
- ✅ Added `__init__.py` files (package, tests, benchmarks)

### Phase 2 – File Migration
- ✅ All files moved via `git mv` (history preserved)
- ✅ History verified: `git log --follow` works correctly

### Phase 3 – Import Updates
- ✅ All imports converted to relative (`..`)
- ✅ Package exports enabled in `__init__.py`
- ✅ All tests passing (41/41)

### Phase 4 – Cross-Validation Tests
- ✅ `tests/test_cross_validation.py` created
- ✅ Verifies structural (v2) and numerical (v4) parity
- ✅ Fast execution (< 3s) suitable for CI

### Phase 5 – Comparison Benchmark
- ✅ `benchmarks/bench_comparison.py` created
- ✅ Compares robust vs v2 vs v4
- ✅ Outputs: TXT report + CSV data + history tracking
- ✅ CI-friendly (≤5 min in quick mode)

---

## 📊 **Performance Findings**

| Engine     | Speed [s/1k groups] | Speedup vs Robust |
|------------|---------------------|-------------------|
| Robust     | ~26 s/1k           | 1× (baseline)     |
| v2 (loky)  | ~0.30 s/1k         | **≈85×**          |
| v4 (Numba) | ~0.0001 s/1k       | **≈17,000×**      |

**Key Insights:**
- ⚠️ Robust implementation degrades significantly on small groups (< 50 rows/group)
- ✅ v2/v4 are numerically stable within 1e-7 on standard scenarios
- ⚠️ Larger numerical differences (~0.57 max absolute slope difference) observed on small-group edge cases

---

## 📝 **Import Changes (v2.0)**

### New Package Structure (v2.0+)
```python
# Correct imports for v2.0
from dfextensions.groupby_regression import GroupByRegressor
from dfextensions.groupby_regression import (
    make_parallel_fit_v2,
    make_parallel_fit_v3,
    make_parallel_fit_v4,
    GroupByRegressorOptimized,
)

# Example usage - Robust
_, dfGB = GroupByRegressor.make_parallel_fit(df, gb_columns=..., ...)

# Example usage - Fast
_, dfGB = make_parallel_fit_v4(df, gb_columns=..., ...)
```

### Old Paths (no longer work - breaking change)
```python
# ❌ These imports no longer work:
from dfextensions import GroupByRegressor  # FAILS
from dfextensions import make_parallel_fit_v4  # FAILS
```

---

## 🔄 **Quick Reference Commands**
```bash
# Run all tests
cd ~/alicesw/O2DPG/UTILS/dfextensions/groupby_regression
pytest tests/ -v

# Run specific test suites
pytest tests/test_groupby_regression.py -v          # Robust (14 tests)
pytest tests/test_groupby_regression_optimized.py -v  # Optimized (24 tests)
pytest tests/test_cross_validation.py -v            # Cross-val (3 tests)

# Run benchmarks
python benchmarks/bench_comparison.py --scenarios quick
python benchmarks/bench_groupby_regression.py --quick

# Check git history preservation
git log --follow --oneline groupby_regression/groupby_regression.py | head -10

# Check current status
git status
git log --oneline -5
```

---

## 🔧 **Remaining Work**

### 1️⃣ **Create Optimized-Only Benchmark** 🎯 NEXT TASK

**File:** `benchmarks/bench_groupby_regression_optimized.py`

**Purpose:** Benchmark v2/v3/v4 only – omit slow robust implementation to enable large-scale tests.

**Requirements:**
- Use `benchmarks/bench_groupby_regression.py` as template
- Test engines: v2 (loky), v3 (threads), v4 (Numba JIT)
- Add JIT warm-up for v4 (exclude compilation from timing)
- Add environment stamp (capture versions/hardware)
- Support large-scale scenarios (up to 100k groups)
- CLI: `--quick` (≤2k groups, <5min) and `--full` (≤100k groups, <30min)
- Outputs: TXT report + JSON results + CSV summary

**CSV Schema (locked):**
```
date,host,commit,scenario,engine,n_groups,rows_per_group,
duration_s,per_1k_s,speedup,max_abs_delta_slope,max_abs_delta_intercept,notes
```

**Tolerances:**
- Default: ≤1e-7 (numerical precision only)
- Small-group exceptions: ≤1e-5 (Huber vs OLS differences)
- Apply to: slopes and intercepts of all fitted coefficients

**Benchmark Tiers:**
- **Tier-A (CI):** `--quick` mode, ≤2k groups, <5min
- **Tier-B (Manual):** `--full` mode, ≤100k groups, <30min

**Environment Stamp Template:**
```python
def get_environment_info():
    """Capture environment for benchmark reproducibility."""
    import sys, platform, os
    import numpy as np, pandas as pd, numba, joblib
    
    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "numba": numba.__version__,
        "numba_threads": numba.config.NUMBA_DEFAULT_NUM_THREADS,
        "threading_layer": numba.threading_layer(),
        "joblib": joblib.__version__,
        "cpu": platform.processor(),
        "cpu_cores": os.cpu_count(),
        "os": platform.platform(),
    }
```

**JIT Warm-up Pattern:**
```python
def warm_up_numba():
    """Trigger Numba compilation before timing (call once at start)."""
    # Small dataset to trigger JIT compilation
    df_warmup = create_benchmark_data(10, 5, seed=999)
    gb_cols = ['xBin', 'y2xBin', 'z2xBin']
    sel = pd.Series(True, index=df_warmup.index)
    
    # Discard result - only purpose is to compile kernels
    _ = make_parallel_fit_v4(
        df=df_warmup,
        gb_columns=gb_cols,
        fit_columns=['dX'],
        linear_columns=['deltaIDC'],
        median_columns=[],
        weights='weight',
        suffix='_warmup',
        selection=sel,
        min_stat=3
    )
```

**Import Pattern (from bench_comparison.py):**
```python
# Handle imports for both direct execution and module import
try:
    # Try package-relative import first (when run as module)
    from ..groupby_regression_optimized import (
        make_parallel_fit_v2,
        make_parallel_fit_v3,
        make_parallel_fit_v4,
    )
except ImportError:
    # Fall back to adding parent to path (when run as script)
    script_dir = Path(__file__).parent
    package_dir = script_dir.parent
    sys.path.insert(0, str(package_dir))
    
    from groupby_regression_optimized import (
        make_parallel_fit_v2,
        make_parallel_fit_v3,
        make_parallel_fit_v4,
    )
```

---

### 2️⃣ **Unified Documentation**

**File:** `docs/README.md`

**Sections needed:**
1. Quick Start (both implementations)
2. **Choosing Between Robust and Optimized** (critical guidance)
3. API Reference (both implementations)
4. Performance Benchmarks (how to run + interpret results)
5. Migration Guide (v1.0 → v2.0 import changes)
6. Future Extensions (Sliding Window / Non-linear)

---

## 🧠 **Technical Decisions Made**

### Key Choices:
✅ **No backward compatibility shims** (clean break)  
✅ **Preserve git history** via `git mv`  
✅ **Realistic tolerances** (1e-5 for implementation differences)  
✅ **Two-tier benchmarking** (CI quick + manual full)  
✅ **Both implementations maintained** (neither deprecated)  
✅ **JIT warm-up excluded** from timing measurements  
✅ **Environment stamping** in all benchmarks

### Known Issues (Deferred):
📝 **0.57 slope difference on small groups:**
- **Metric:** Max absolute difference in slope coefficients
- **Conditions:** 100 groups × 5 rows/group, minimal noise
- **Expected:** <1e-7 (numerical precision)
- **Observed:** 0.57 (unexpectedly large)
- **Hypothesis:** Robust implementation may fail silently on very small groups
- **Status:** Investigation deferred until after restructuring complete

---

## 🎯 **Implementation Status**

| Component | Status | Tests | Notes |
|-----------|--------|-------|-------|
| Package structure | ✅ Complete | - | All `__init__.py` files in place |
| File migration | ✅ Complete | - | History preserved with `git mv` |
| Import updates | ✅ Complete | 41/41 ✅ | All relative imports working |
| Cross-validation tests | ✅ Complete | 3/3 ✅ | Fast (<3s), always enabled |
| Comparison benchmark | ✅ Complete | - | Working, committed |
| Robust benchmark | ✅ Complete | - | Working, import fixed |
| **Optimized benchmark** | 🟡 **In Progress** | - | **← CURRENT TASK** |
| Documentation | 🟡 Pending | - | Next after benchmark |

---

## 🗓️ **Next-Step Plan**

| Step | Owner | Duration | Status |
|------|-------|----------|--------|
| 1. Create `bench_groupby_regression_optimized.py` | GPT | ≈1h | 🟡 **CURRENT** |
| 2. Test benchmark (`--quick` mode) | User | 30min | 🟡 Pending |
| 3. Commit benchmark + results | User | 15min | 🟡 Pending |
| 4. Write `docs/README.md` | Claude | 2-3h | 🟡 Pending |
| 5. Final validation (all tests + benchmarks) | User | 1h | 🟡 Pending |

---

## ✅ **Success Criteria**

- [x] All tests passing (41/41)
- [x] Package structure complete
- [x] Comparison benchmark working
- [x] Robust benchmark working
- [ ] **Optimized benchmark working** ← CURRENT GOAL
- [ ] **Documentation complete**
- [ ] Real TPC calibration data validated

---

## 📌 **Notes for Implementation**

### Deprecation Policy
- **Robust:** Maintained, production-proven, NOT deprecated
- **Optimized:** Maintained, performance-optimized
- Both are supported, first-class implementations

### Future Extensions (Reserved Names)
```python
# Reserved for future versions (not yet implemented):
#   make_sliding_window_fit(...)  # Rolling window regression
#   make_nonlinear_fit(...)        # Non-linear models
```

### Test Discovery
A `pytest.ini` file may be added:
```ini
[pytest]
testpaths = groupby_regression/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

---

---

# 🚀 **RESTART PROMPT FOR GPT**

*Use this section when restarting a GPT session to create the optimized benchmark.*

---

## Project Restart: GroupBy Regression Optimized Benchmark

### 📎 Attached Files
- `restartContext.md` - This file (complete project context)
- `benchmarks/bench_groupby_regression.py` - Template to adapt
- `benchmarks/bench_comparison.py` - Import pattern reference
- `groupby_regression_optimized.py` - v2/v3/v4 implementations to benchmark
- `__init__.py` - Package structure reference

### 🎯 Immediate Goal
Create `benchmarks/bench_groupby_regression_optimized.py` - a comprehensive benchmark script for v2/v3/v4 engines only (omit slow robust implementation to enable large-scale tests up to 100k groups).

### 📚 Context Loading Instructions

**Please follow these steps IN ORDER:**

#### Step 1: Read and Absorb Context
Read all sections of `restartContext.md` above, especially:
- "Remaining Work" section (your task details)
- "Performance Findings" (speedup data)
- "Technical Decisions Made" (constraints)
- Code templates (environment stamp, JIT warm-up, import pattern)

#### Step 2: Demonstrate Understanding
Before writing any code, confirm you understand:

1. **Task:** Create what file, for what purpose?
2. **Template:** Which existing file should you adapt?
3. **Engines:** Which implementations to test (v2/v3/v4)?
4. **Key additions:** What must you add beyond the template (JIT warm-up, environment stamp)?
5. **Output format:** What files should the benchmark produce?
6. **CLI tiers:** What's the difference between `--quick` and `--full` modes?

**Respond with:** A brief summary (2-3 sentences) showing you understand the task.

#### Step 3: Ask Clarifying Questions
If ANYTHING is unclear or ambiguous, ask questions NOW. Examples of good questions:
- "Should v3 use the same scenarios as v2, or different ones?"
- "In the warm-up function, should I test all three engines or just v4?"
- "Should I match the exact CLI arguments of bench_groupby_regression.py?"
- "What should `--rows-per-group` default to in --full mode?"

**If everything is clear, say:** "All clear, ready to proceed."

#### Step 4: Propose Implementation Approach
Briefly outline your plan:
- File structure (functions, classes, main flow)
- How you'll integrate warm-up and environment stamping
- How you'll handle the three engines (v2, v3, v4)
- CLI argument design

**Wait for confirmation** before coding.

#### Step 5: Implementation
Only after Steps 1-4 complete and confirmed, provide the complete, runnable script.

### 🚫 What NOT to Do
- ❌ Don't jump straight to code
- ❌ Don't make assumptions about unclear requirements
- ❌ Don't provide partial implementations without asking
- ❌ Don't skip the warm-up or environment stamping

### ✅ Success Criteria
A Python script that:
- ✅ Runs successfully: `python bench_groupby_regression_optimized.py --quick`
- ✅ Tests all three engines: v2, v3, v4
- ✅ Completes in <5 minutes (quick mode)
- ✅ Outputs TXT report + JSON results + (optional) CSV summary
- ✅ Includes JIT warm-up for v4
- ✅ Includes environment info in output
- ✅ Uses correct import pattern (try/except from bench_comparison.py)

### 📝 Additional Context
**You recently passed a self-check demonstrating you understand:**
- Difference between v2 (loky), v3 (threads), v4 (Numba JIT)
- Why v4 needs warm-up (compilation time would distort results)
- Speedup numbers (v4 is ~17,000× faster than robust)

**This knowledge is correct - use it in your implementation.**

---

**Ready? Start with Step 2: Demonstrate your understanding of the task.**
