# M7.1 Fit Formula & Output Specification

**Version:** 2.1.1 DRAFT  
**Date:** 2025-10-28  
**Status:** Ready for GPT Review  
**Incorporates:** User decisions from 2025-10-28 discussion

---

## 1. API Design Decision: List of Dictionaries

### 1.1 Fit Specification Structure

**DECISION:** Use list of dictionaries for clarity and flexibility.

```python
def make_sliding_window_fit(
    df: pd.DataFrame,
    group_columns: List[str],
    window_spec: Dict[str, int],
    fit_specs: List[Dict[str, Any]],  # ← PRIMARY SPECIFICATION
    suffix: str = '',                  # ← GLOBAL SUFFIX (optional)
    min_entries: int = 10,
    backend: str = 'numba',
    **kwargs
) -> pd.DataFrame:
    """
    Perform sliding window regression over multi-dimensional bins.
    
    Parameters
    ----------
    fit_specs : List[Dict[str, Any]]
        List of fit specifications, each dict containing:
        - 'input_var': str - Column name to fit (e.g., 'dX_meas')
        - 'output_var': str - Base name for output columns (e.g., 'dX')
        - 'formula': str - RHS of regression formula (e.g., 'drift + dr + I(dr**2)')
        - 'predictors': List[str] - Predictor column names (optional, inferred from formula)
        - 'fitter': str - Fitter type (optional, default 'ols')
        
    suffix : str, optional
        Global suffix appended to ALL output_var names.
        Example: suffix='_corrected' → 'dX_corrected_mean', 'dX_corrected_slope_drift'
        Default: '' (no suffix)
    
    Example
    -------
    >>> fit_specs = [
    ...     {
    ...         'input_var': 'dX_meas',
    ...         'output_var': 'dX',
    ...         'formula': 'drift + dr + I(dr**2) + dsec + meanIDC',
    ...         'predictors': ['drift', 'dr', 'dsec', 'meanIDC']
    ...     },
    ...     {
    ...         'input_var': 'dY_meas',
    ...         'output_var': 'dY',
    ...         'formula': 'drift + dsec',
    ...         'predictors': ['drift', 'dsec']
    ...     }
    ... ]
    >>> result = make_sliding_window_fit(df, group_columns, window_spec, 
    ...                                    fit_specs, suffix='_fit')
    """
```

### 1.2 Backward Compatibility Helper

For users familiar with the old API, provide a conversion helper:

```python
def make_fit_specs_from_legacy(
    fit_columns: List[str],
    predictor_columns: List[str],
    fit_formula: Union[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """
    Convert legacy API parameters to fit_specs list.
    
    Example:
    >>> fit_specs = make_fit_specs_from_legacy(
    ...     fit_columns=['dX_meas', 'dY_meas'],
    ...     predictor_columns=['drift', 'dr', 'dsec'],
    ...     fit_formula={
    ...         'dX_meas': 'dX_meas ~ drift + dr + I(dr**2)',
    ...         'dY_meas': 'dY_meas ~ drift + dsec'
    ...     }
    ... )
    """
    # Implementation converts old API to new list-of-dicts format
```

---

## 2. Output Column Naming Convention

### 2.1 Base Naming Pattern

```python
{output_var}{suffix}_{metric}
```

Where:
- `{output_var}`: From fit_spec['output_var']
- `{suffix}`: Global suffix parameter (optional)
- `{metric}`: Type of output

### 2.2 Output Columns Per Target

For each fit specification, the following columns are produced:

```python
# Aggregation statistics
{output_var}{suffix}_mean              # Mean of input_var in window
{output_var}{suffix}_std               # Std dev of input_var in window
{output_var}{suffix}_median            # Median of input_var in window (optional)
{output_var}{suffix}_entries           # Number of entries in window

# Fit coefficients
{output_var}{suffix}_slope_{predictor} # Coefficient for each predictor
{output_var}{suffix}_intercept         # Intercept term (if included)

# Fit quality metrics
{output_var}{suffix}_r_squared         # R² goodness of fit
{output_var}{suffix}_chi2              # χ² statistic (if weighted)
{output_var}{suffix}_ndof              # Degrees of freedom

# Optional: Standard errors
{output_var}{suffix}_stderr_{predictor}  # Standard error of coefficient
{output_var}{suffix}_stderr_intercept    # Standard error of intercept

# Window metadata (shared across all targets)
n_bins_aggregated                      # Number of bins in window
n_rows_aggregated                      # Total rows in window
effective_window_fraction              # Fraction of possible bins present
```

### 2.3 Coefficient Name Sanitization

Transform predictor names to valid column names:

```python
# Simple predictors: use as-is
'drift' → 'slope_drift'
'dr' → 'slope_dr'

# I() wrapped terms: sanitize
'I(dr**2)' → 'slope_I_dr_2'
'I(drift*dr)' → 'slope_I_drift_dr'
'I(np.log(x))' → 'slope_I_np_log_x'

# Sanitization rules:
- Replace '(' with '_'
- Replace ')' with '_'
- Replace '**' with '_'
- Replace '*' with '_'
- Remove duplicate underscores
- Strip trailing underscores
```

### 2.4 Example Output

**Input:**
```python
fit_specs = [
    {
        'input_var': 'dX_meas',
        'output_var': 'dX',
        'formula': 'drift + dr + I(dr**2) + dsec',
        'predictors': ['drift', 'dr', 'dsec']
    }
]
suffix = '_corrected'
```

**Output columns:**
```python
# Group columns (unchanged)
'xBin', 'y2xBin', 'z2xBin',

# Aggregation
'dX_corrected_mean',
'dX_corrected_std',
'dX_corrected_entries',

# Coefficients
'dX_corrected_slope_drift',
'dX_corrected_slope_dr',
'dX_corrected_slope_I_dr_2',
'dX_corrected_slope_dsec',
'dX_corrected_intercept',

# Quality
'dX_corrected_r_squared',
'dX_corrected_chi2',
'dX_corrected_ndof',

# Window metadata (shared)
'n_bins_aggregated',
'n_rows_aggregated',
'effective_window_fraction'
```

---

## 3. ROOT Export Specification

### 3.1 Export Strategy

**DECISION:** Export full DataFrame with all variables (input + predictions) to ROOT file.

```python
def export_to_root(
    df: pd.DataFrame,
    output_file: str = "validation.root",
    tree_name: str = "validation"
) -> None:
    """
    Export DataFrame to ROOT file using uproot.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Complete DataFrame with:
        - Group columns (xBin, y2xBin, z2xBin)
        - Input variables (dX_meas, dY_meas, ...)
        - Predictor variables (drift, dr, dsec, ...)
        - Ground truth (dX_true, if synthetic)
        - Fit results (dX_mean, dX_slope_*, dX_r_squared, ...)
        - Validation metrics (delta, pull, alarm_status, ...)
        
    output_file : str
        Path to output ROOT file
        
    tree_name : str
        Name of TTree in ROOT file
        
    Example:
    --------
    >>> # After validation
    >>> export_to_root(result_with_metrics, "test_tpc_distortion_recovery.root")
    >>> 
    >>> # In ROOT:
    >>> # root -l test_tpc_distortion_recovery.root
    >>> # validation->Draw("delta")
    >>> # validation->Draw("dX_true:dX_pred", "alarm_status==0")
    """
    import uproot
    
    uproot.recreate(output_file, {tree_name: df})
    
    print(f"✅ Exported to: {output_file}")
    print(f"   Tree: {tree_name}")
    print(f"   Entries: {len(df)}")
    print(f"   Branches: {len(df.columns)}")
```

### 3.2 Exported Data Structure

**Single TTree per file containing:**

1. **Bin indices** (grouping variables)
   - xBin, y2xBin, z2xBin, ...

2. **Input measurements** (per bin aggregates)
   - dX_meas_mean, dX_meas_std, dX_meas_entries

3. **Predictor averages** (per bin)
   - drift_mean, dr_mean, dsec_mean, ...

4. **Fit results** (per bin)
   - dX_slope_drift, dX_slope_dr, dX_intercept, dX_r_squared

5. **Ground truth** (if synthetic data)
   - dX_true_mean

6. **Validation metrics** (if computed)
   - delta (residual: true - pred)
   - delta_norm (normalized residual)
   - pull
   - alarm_status (0=OK, 1=WARNING, 2=ALARM)

7. **Window metadata** (per bin)
   - n_bins_aggregated
   - n_rows_aggregated
   - effective_window_fraction

### 3.3 Implementation

```python
# In test file
def test_tpc_distortion_recovery():
    # ... generate data, run fit, compute metrics ...
    
    # Export to ROOT
    import uproot
    uproot.recreate(
        "test_tpc_distortion_recovery.root",
        {"validation": result_with_metrics}
    )
    
    print("✅ Exported to test_tpc_distortion_recovery.root")
    print("   Inspect with: root -l test_tpc_distortion_recovery.root")
```

---

## 4. Formula Syntax Specification

### 4.1 Supported Syntax

**NOTE:** This section needs clarification from user. Current proposal:

```python
# Linear terms (SUPPORTED)
'x1 + x2 + x3'

# Intercept control (SUPPORTED)
'1 + x1 + x2'          # With intercept (default)
'0 + x1 + x2'          # Without intercept
'-1 + x1 + x2'         # Without intercept (alternative)

# Power transforms (SUPPORTED - requires I() wrapper)
'x + I(x**2)'          # Quadratic
'x + I(x**2) + I(x**3)'  # Cubic

# Interactions (SUPPORTED - requires I() wrapper)
'x1 + x2 + I(x1*x2)'   # Explicit interaction

# Complex transforms (UNCLEAR - needs decision)
'I(np.log(x))'         # Logarithm - ALLOW or REQUIRE pre-compute?
'I(np.sqrt(x))'        # Square root - ALLOW or REQUIRE pre-compute?
'I(np.exp(x))'         # Exponential - ALLOW or REQUIRE pre-compute?

# statsmodels shortcuts (NOT SUPPORTED - too ambiguous)
'x1 * x2'              # NO - use explicit I(x1*x2)
'x1 : x2'              # NO - use explicit I(x1*x2)
'C(category)'          # NO - use integer bins

# Patsy formulas (NOT SUPPORTED)
'x1 ** 2'              # NO - use I(x**2)
```

### 4.2 Open Questions on Formula Syntax

**NEED USER DECISION:**

1. **Function calls in I():**
   - ✅ ALLOW: `I(np.log(drift))` - evaluate at fit time?
   - ❌ DISALLOW: Require user to pre-compute `df['log_drift'] = np.log(df['drift'])`?

2. **Validation level:**
   - Strict: Fail on any unsupported syntax
   - Permissive: Try to parse, warn on issues
   - Deferred: Only validate at fit time

3. **Formula parsing:**
   - Use statsmodels/patsy parser?
   - Write custom parser?
   - Regex-based extraction?

**RECOMMENDATION:** 
- Start strict: Only `term`, `I(term**power)`, `I(term1*term2)`
- Disallow function calls (require pre-compute)
- Can relax later if needed

---

## 5. Multi-Dimensional Test Strategy

### 5.1 Test Dimensionality

**DECISION:** Use n-dimensional tests by default to find problems early.

**Test hierarchy:**

```python
# Level 1: Unit tests (fast, multiple dimensions)
test_1d_simple()      # 1D: xBin only (50 bins, 2 windows)
test_2d_basic()       # 2D: xBin × yBin (20×10, 4 windows)
test_3d_standard()    # 3D: xBin × yBin × zBin (20×10×10, 8 windows)
test_4d_tracking()    # 4D: xBin × yBin × zBin × pBin (10×10×5×4, 16 windows)

# Level 2: Integration tests (realistic scale)
test_3d_tpc_distortion()  # TPC: 50×10×10 bins
test_6d_tracking_qa()     # Tracking: 10×10×5×5×3×3 bins

# Level 3: Benchmark (production scale)
benchmark_3d_full()       # TPC: 170×20×20 bins
benchmark_6d_full()       # Tracking: 15×15×10×8×5×4 bins
```

### 5.2 Why Multi-Dimensional by Default

**Problems found only in high dimensions:**

1. **Memory scaling:** 1D looks fine, 6D explodes
2. **Window edge effects:** More corners in high-D
3. **Sparse data:** Missing bins more common in high-D
4. **Index overflow:** Integer indexing bugs
5. **Performance bottlenecks:** Nested loops scale badly

**Strategy:**
- Run 1D-4D in every test suite
- Catches most issues early
- Fast enough for CI (~10s total)

---

## 6. Complete API Example

### 6.1 Single Target (TPC Distortion)

```python
import pandas as pd
from dfextensions.groupby_regression import make_sliding_window_fit
from synthetic_tpc_distortion import make_synthetic_tpc_distortion

# Generate synthetic data
df = make_synthetic_tpc_distortion(
    n_bins_dr=50, n_bins_z2x=10, n_bins_y2x=10,
    entries_per_bin=50, seed=42
)

# Define fit specification
fit_specs = [
    {
        'input_var': 'dX_meas',
        'output_var': 'dX',
        'formula': 'drift + dr + I(dr**2) + dsec + meanIDC',
        'predictors': ['drift', 'dr', 'dsec', 'meanIDC'],
        'fitter': 'ols'
    }
]

# Run sliding window fit
result = make_sliding_window_fit(
    df=df,
    group_columns=['xBin', 'y2xBin', 'z2xBin'],
    window_spec={'xBin': 3, 'y2xBin': 2, 'z2xBin': 2},
    fit_specs=fit_specs,
    suffix='_fitted',
    min_entries=20,
    backend='numpy'
)

# Export to ROOT
import uproot
uproot.recreate("tpc_distortion_fit.root", {"fit_results": result})
```

### 6.2 Multiple Targets (3D Distortion)

```python
# Fit dX, dY, dZ simultaneously
fit_specs = [
    {
        'input_var': 'dX_meas',
        'output_var': 'dX',
        'formula': 'drift + dr + I(dr**2) + dsec',
        'predictors': ['drift', 'dr', 'dsec']
    },
    {
        'input_var': 'dY_meas',
        'output_var': 'dY',
        'formula': 'drift + dsec',
        'predictors': ['drift', 'dsec']
    },
    {
        'input_var': 'dZ_meas',
        'output_var': 'dZ',
        'formula': 'drift + I(drift**2)',
        'predictors': ['drift']
    }
]

result = make_sliding_window_fit(
    df=df,
    group_columns=['xBin', 'y2xBin', 'z2xBin'],
    window_spec={'xBin': 3, 'y2xBin': 2, 'z2xBin': 2},
    fit_specs=fit_specs,
    suffix='',  # No global suffix
    min_entries=20
)

# Output columns:
# - dX_mean, dX_slope_drift, dX_slope_dr, dX_slope_I_dr_2, dX_slope_dsec, dX_intercept, dX_r_squared
# - dY_mean, dY_slope_drift, dY_slope_dsec, dY_intercept, dY_r_squared
# - dZ_mean, dZ_slope_drift, dZ_slope_I_drift_2, dZ_intercept, dZ_r_squared
```

---

## 7. Open Items for Discussion

### 7.1 Formula Syntax (CRITICAL)

**Need decision on:**
1. Allow `I(np.log(x))` or require pre-computed columns?
2. Validation strictness level?
3. Parser implementation (statsmodels vs custom)?

**My recommendation:**
- Start strict: only `term`, `I(term**N)`, `I(term1*term2)`
- Require pre-computed transforms
- Custom regex parser (simple, no dependencies)

### 7.2 Standard Errors in Output

**Question:** Include stderr columns by default?

```python
# If yes:
{output_var}_stderr_drift
{output_var}_stderr_dr
{output_var}_stderr_intercept
```

**Pros:**
- Useful for uncertainty propagation
- Available from fit anyway

**Cons:**
- Doubles number of columns
- Not always needed

**Recommendation:** Include, but document as optional for future removal if unused.

### 7.3 Additional Fit Statistics

**Question:** What other fit statistics to include?

```python
# Currently planned:
- r_squared
- chi2 (if weighted)
- ndof

# Could add:
- adjusted_r_squared
- f_statistic
- condition_number (for collinearity detection)
- residual_std
```

**Recommendation:** Start with r_squared, chi2, ndof. Add others if needed.

---

## 8. Implementation Checklist

**Phase 1: Core API (M7.1)**
- [ ] Update function signature (fit_specs, suffix)
- [ ] Implement fit_specs parsing
- [ ] Implement output column naming
- [ ] Add formula validation
- [ ] Update tests to use fit_specs
- [ ] Document API changes

**Phase 2: ROOT Export (M7.1)**
- [ ] Add uproot export function (2 lines)
- [ ] Update test to export ROOT file
- [ ] Document ROOT inspection

**Phase 3: Multi-Dimensional Tests (M7.1)**
- [ ] Add 1D-4D test suite
- [ ] Update TPC test to use 3D by default
- [ ] Add performance assertions

**Phase 4: Documentation (M7.1)**
- [ ] Update PHASE7_IMPLEMENTATION_PLAN.md
- [ ] Update API documentation
- [ ] Add examples to README
- [ ] Update specification appendix

---

## 9. Review Questions for GPT

See separate document: `GPT_REVIEW_QUESTIONS.md`

---

**Status:** DRAFT - Ready for GPT review and user approval  
**Next steps:**
1. GPT reviews this specification
2. User approves decisions
3. Finalize formula syntax
4. Begin implementation
