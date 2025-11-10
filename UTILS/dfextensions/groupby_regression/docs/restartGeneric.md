# Restart Context - Sliding Window GroupBy Implementation

**Project:** Sliding Window GroupBy Regression Framework for ALICE O² TPC Calibration  
**Phase:** Implementation (Specification Complete)  
**Date:** 2025-10-27  
**Status:** Ready to begin implementation

---

## 🎯 **Current State - Specification Complete**

### **Section 6 Specification: COMMITTED** ✅

**Document:** `SLIDING_WINDOW_SPEC_DRAFT.md` (1855 lines)  
**Status:** Frozen, production-ready, both reviewers approved  
**Commit:** Section 6 complete with all reviewer feedback

**Key Components:**
- 9 Functional Requirements (FR-1 to FR-9)
- 4 API Specifications (API-1 to API-4)
- 8 Data Handling Rules (DH-1 to DH-8)
- 3 Performance Requirements (PERF-1 to PERF-3)
- 4 Memory Requirements (MEM-1 to MEM-4)
- 5 Integration Requirements (INT-1 to INT-5)
- 8 Testing Requirements (TEST-1 to TEST-8)
- 3 Documentation Requirements (DOC-1 to DOC-3)
- 7 Non-Requirements (NS-1 to NS-7)

---

## 🏗️ **Core Technical Decisions**

### **1. Zero-Copy Accumulator Algorithm (MEM-3)**

**Key innovation:** Memory = O(#centers), not O(N × window_volume)

**Design:**
- **Dense mode:** Flat NumPy arrays when prod(axis_sizes) ≤ 50M cells
  - Memory: 3 × 8 bytes × prod(axis_sizes)
  - Fast: O(1) array indexing

- **Sparse mode:** Hash map (Numba typed.Dict) for larger grids
  - Memory: ~40-80 bytes × #touched_centers
  - Scales: Any grid size

**Accumulator state per center:**
- `count`: Number of data points (int64)
- `sum_w`: Sum of weights (float64)
- `sum_wy`: Sum of weighted values (float64)
- `sum_wy2`: Sum of weighted squared values (float64)
- Extensible for OLS: `sum_wX`, `sum_wXX`, `sum_wXy`

**Map-reduce pattern:**
- Process data in chunks (default: 1M rows)
- Each chunk → local accumulators
- Merge: dense (array sum), sparse (dict merge)
- Parallelizable with ProcessPoolExecutor

**Linear index packing:**
```python
# Row-major ordering
strides[d] = prod(sizes[d+1:])
linear_index = sum(coords[d] * strides[d] for d in range(D))
```

**Implementation:** Numba @njit for 10-100× speedup

---

### **2. Formula-Based Float Binning (DH-2)**

**Key decision:** User pre-bins floats to integers using df.eval(formula)

**Pattern:**
```python
# Define binning formulas (stored in configuration)
binning_formulas = {
    'time': 'floor(time / 0.5)',      # Uniform bins
    'pT': 'round(log10(pT) * 10)',    # Logarithmic bins
    'eta': 'floor((eta + 1.5) * 20)', # Shifted and scaled
}

# Apply binning
for coord, formula in binning_formulas.items():
    df[f'{coord}Bin'] = df.eval(formula).astype(int)
```

**Benefits:**
- Reproducibility: Formulas stored in configuration
- Flexibility: Supports any pandas.eval() expression
- Traceability: Analysis pipeline self-documenting

**Validation (DH-2):**
- Expression must evaluate to numeric Series
- Result must be finite (no NaN/inf)
- Safe integer conversion required
- InvalidWindowSpec exception on errors

---

### **3. API Design (API-1)**

**Main function signature:**
```python
def make_sliding_window_fit(
    df: pd.DataFrame,
    group_columns: List[str],              # e.g., ['xBin', 'y2xBin', 'z2xBin']
    window_spec: Dict[str, Union[int, float, dict]],
    fit_columns: List[str],                # Target variables
    predictor_columns: List[str],          # Features for regression
    fit_formula: Optional[Union[str, Callable]] = None,
    aggregation_functions: Optional[Dict[str, List[str]]] = None,
    weights_column: Optional[str] = None,
    binning_formulas: Optional[Dict[str, str]] = None,  # For reproducibility
    min_entries: int = 10,
    backend: str = 'numba',
    partition_strategy: Optional[dict] = None,
    **kwargs
) -> pd.DataFrame:
```

**Window specification formats:**

**Simple:**
```python
window_spec = {'xBin': 2, 'y2xBin': 1, 'z2xBin': 1}  # ±bins
```

**Rich:**
```python
window_spec = {
    'xBin': {
        'size': 2,
        'boundary': 'truncate',  # 'truncate', 'mirror', 'periodic'
        'weighting': 'uniform',  # 'uniform', 'distance', 'gaussian'
    },
    'phi': {
        'size': 10,
        'boundary': 'periodic',
        'binning_formula': 'phi * 180 / 3.14159',  # Metadata
    }
}
```

---

### **4. Error Handling (FR-9)**

**Configuration validation:**
- window_spec entries have required fields
- Boundary types valid ('truncate', 'mirror', 'periodic')
- Weighting parameters consistent
- → InvalidWindowSpec exception

**Numerical error handling:**
- Singular matrix → coefficients = NaN, flag bin
- Insufficient data → apply min_entries threshold
- Overflow/underflow → graceful degradation

**Performance warnings:**
- PerformanceWarning when switching dense→sparse
- PerformanceWarning for excessive chunking
- User-controllable via warnings.filterwarnings()

---

## 📋 **Implementation Priorities**

### **Phase 1: Core Zero-Copy Engine** (Week 1-2)
**Goal:** Working zero-copy accumulator with basic stats

**Tasks:**
1. **Numba accumulator kernels** (MEM-3)
  - Dense mode implementation
  - Sparse mode implementation
  - Boundary handling (truncate/mirror/periodic)
  - Linear index packing/unpacking

2. **Basic aggregation** (API-4)
  - Mean, std, count, sum_weights
  - Weighted statistics support
  - Output DataFrame construction

3. **Core tests** (TEST-1, TEST-2)
  - Reference implementation validation
  - Boundary condition tests
  - Dense vs sparse correctness

**Deliverable:** `sliding_window_core.py` with working accumulator

---

### **Phase 2: API & Configuration** (Week 3)
**Goal:** Production API with all configuration options

**Tasks:**
1. **Main API function** (API-1)
  - Parameter validation (FR-9)
  - Window spec parsing (API-2)
  - binning_formulas handling (DH-2)

2. **Window specification** (API-2)
  - Simple/rich format parsing
  - Boundary validation
  - Weighting support (uniform/distance/gaussian)

3. **Formula validation** (DH-2)
  - df.eval() safety checks
  - Finite value validation
  - Error messages

**Deliverable:** `sliding_window_api.py` with full configuration

---

### **Phase 3: Regression & Diagnostics** (Week 4)
**Goal:** Linear regression with quality diagnostics

**Tasks:**
1. **Linear regression** (FR-3)
  - String formula parsing
  - OLS implementation (reuse v4 kernel)
  - Coefficient output

2. **Fit diagnostics** (FR-7)
  - R², RMSE, effective DOF
  - Residual statistics
  - Convergence flags

3. **Custom fit functions** (API-3)
  - Callable interface
  - Signature validation

**Deliverable:** `sliding_window_regression.py`

---

### **Phase 4: Testing & Validation** (Week 5)
**Goal:** Complete test suite + performance benchmarks

**Tasks:**
1. **Unit tests** (TEST-1 to TEST-4)
  - All requirements covered
  - Edge cases tested
  - Boundary conditions verified

2. **Performance benchmarks** (TEST-4, TEST-5)
  - Runtime vs dataset size
  - Memory profiling
  - Scaling tests

3. **Visual validation** (TEST-8)
  - 1D slices
  - 2D heatmaps
  - Smoothness verification

**Deliverable:** Complete test suite + benchmark results

---

## 🔬 **Implementation Workflow**

### **Roles:**
- **Main Coder:** Claude (me)
- **Reviewers:** GPT + Gemini

### **Process:**

**1. Claude implements feature/module**
- Write code following Section 6 requirements
- Include docstrings with requirement IDs
- Add basic tests
- Document design decisions

**2. Submit to GPT for technical review**
- Code quality and patterns
- Performance implications
- Edge cases
- Numba compatibility

**3. Submit to Gemini for scientific review**
- Statistical correctness
- Physics use case fit
- ALICE workflow compatibility
- Numerical stability

**4. Iterate based on feedback**
- Address reviewer concerns
- Refactor if needed
- Add missing tests

**5. Commit when both approve**
- Clean, reviewed, tested code
- Ready for next phase

---

## 📚 **Key Reference Documents**

### **Specification:**
- `SLIDING_WINDOW_SPEC_DRAFT.md` - Section 6 (frozen)
- Requirements: FR-1 to FR-9, MEM-1 to MEM-4, etc.

### **Reviews:**
- `GPT_FINAL_REVIEW.md` - Technical approval
- `GEMINI_FINAL_REVIEW.md` - Scientific approval
- `GPT_FIXES_IMPLEMENTATION_SUMMARY.md` - Final changes

### **Implementation Reference:**
- GPT's zero-copy Numba implementation (prototype)
- Section 5.4: v4 GroupBy kernel (reuse for OLS)
- Section 2: Dataset characteristics (for testing)

---

## 🎯 **Success Criteria**

### **Correctness:**
- ✅ Passes TEST-1 validation vs reference implementation
- ✅ Boundary conditions correct (TEST-2)
- ✅ Dense/sparse produce identical results
- ✅ Weighted statistics match manual calculations

### **Performance:**
- ✅ < 30 min for 10M rows (PERF-1)
- ✅ < 4 GB memory for medium datasets (MEM-1)
- ✅ 10-100× speedup with Numba (PERF-3)
- ✅ Near-linear scaling with dimensions (PERF-2)

### **Quality:**
- ✅ Both reviewers approve (GPT + Gemini)
- ✅ Complete test coverage (TEST-1 to TEST-8)
- ✅ RootInteractive integration works (INT-2)
- ✅ Documentation complete (DOC-1 to DOC-3)

---

## 📝 **First Implementation Task**

### **Start with:** Zero-Copy Dense Accumulator

**Scope:** Implement dense mode accumulator (MEM-3)

**Requirements:**
- Numba @njit function
- Inputs: X (D×N int32), y (N float64), w (N float64 or None)
- Outputs: count, sum_w, sum_wy, sum_wy2 (flat arrays)
- Boundary handling: truncate/mirror/periodic
- Linear index packing

**Tests:**
- Simple 2D case (±1 window)
- Verify mean, std match manual calculation
- Test boundary modes

**Deliverable:** `accumulator_dense.py` + tests

---

## 🚀 **Ready to Start Implementation**

**Next steps:**
1. Create project structure
2. Implement dense accumulator
3. Write tests
4. Submit to GPT/Gemini for review
5. Iterate

**Let me know when you're ready to begin, or if you have questions!**

---

**End of Restart Context**

---

## Quick Reference

**Specification:** Section 6 complete (1855 lines, committed)  
**Phase:** Implementation starting  
**Coder:** Claude  
**Reviewers:** GPT + Gemini  
**First task:** Zero-copy dense accumulator (MEM-3)  
**Target:** < 4 GB memory, < 30 min for 10M rows