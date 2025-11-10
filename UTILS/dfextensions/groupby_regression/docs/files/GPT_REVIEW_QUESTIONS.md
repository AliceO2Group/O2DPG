# GPT Review Questions - Fit Formula Specification v2.1.1

**Purpose:** Critical review of specification decisions before implementation  
**Reviewers:** GPT-4, Gemini (optional)  
**Context:** See `SPECIFICATION_FIT_FORMULA_v2.1.1.md`

---

## 🎯 Review Focus Areas

### 1. API Design & Usability
### 2. Naming Conventions & Consistency  
### 3. Formula Syntax & Validation
### 4. Testing Strategy
### 5. Implementation Priorities
### 6. Potential Issues & Improvements

---

## 1. API Design & Usability

### Q1.1: List of Dicts vs Current API

**Decision:** Use list of dictionaries for fit specifications:

```python
fit_specs = [
    {
        'input_var': 'dX_meas',
        'output_var': 'dX',
        'formula': 'drift + dr + I(dr**2)',
        'predictors': ['drift', 'dr']
    }
]
```

**Questions for GPT:**
1. Is this API design clear and intuitive for users?
2. Are the dict keys well-named (`input_var`, `output_var`, `formula`, `predictors`)?
3. Should `predictors` be required or optional (inferred from formula)?
4. Is there redundancy between `formula` and `predictors`?
5. Any alternative API designs we should consider?

### Q1.2: Global Suffix Parameter

**Decision:** Add global `suffix` parameter applied to all output_var names:

```python
result = make_sliding_window_fit(..., suffix='_corrected')
# Produces: dX_corrected_mean, dX_corrected_slope_drift, etc.
```

**Questions for GPT:**
1. Is this the right abstraction for output naming?
2. Should suffix be per-target instead of global?
3. Are there use cases where global suffix is insufficient?
4. Better name than `suffix`? (e.g., `output_suffix`, `name_suffix`?)

### Q1.3: Backward Compatibility

**Approach:** Provide helper function to convert old API to new:

```python
fit_specs = make_fit_specs_from_legacy(
    fit_columns=['dX_meas'],
    predictor_columns=['drift', 'dr'],
    fit_formula='dX_meas ~ drift + dr'
)
```

**Questions for GPT:**
1. Is this backward compatibility approach sufficient?
2. Should we support old API directly in main function?
3. When should we deprecate old API (if at all)?
4. How to communicate migration path to users?

---

## 2. Naming Conventions & Consistency

### Q2.1: Output Column Names

**Proposed naming:**
```python
{output_var}{suffix}_{metric}

# Examples:
dX_mean
dX_corrected_slope_drift
dY_slope_I_dr_2
```

**Questions for GPT:**
1. Is this naming convention clear and consistent?
2. Should we use different separators? (e.g., `.` instead of `_`?)
3. How to handle deep nesting? (e.g., `dX_corrected_fitted_slope_drift`?)
4. Are column names too long? Better abbreviations?

### Q2.2: Coefficient Name Sanitization

**Proposed rules:**
```python
'I(dr**2)' → 'slope_I_dr_2'
'I(drift*dr)' → 'slope_I_drift_dr'
'I(np.log(x))' → 'slope_I_np_log_x'
```

**Questions for GPT:**
1. Are sanitization rules clear and unambiguous?
2. Risk of name collisions? (e.g., `I(x*y)` vs `I(x_y)`?)
3. Should we use hashing for complex terms?
4. Better algorithm for sanitization?

### Q2.3: Metadata Columns

**Proposed shared columns:**
```python
n_bins_aggregated
n_rows_aggregated
effective_window_fraction
```

**Questions for GPT:**
1. Should these be prefixed? (e.g., `_n_bins_aggregated`?)
2. Are names descriptive enough?
3. Other metadata that should be included?
4. Risk of name conflicts with user columns?

---

## 3. Formula Syntax & Validation

### Q3.1: Formula Syntax Support (CRITICAL - NEEDS DECISION)

**Current proposal (strict):**
```python
# SUPPORTED:
'x1 + x2'              # Linear
'I(x**2)'              # Power transform
'I(x1*x2)'             # Interaction

# UNCLEAR - NEED DECISION:
'I(np.log(x))'         # Function call - ALLOW?
'I(np.sqrt(x))'        # Function call - ALLOW?

# NOT SUPPORTED:
'x1 * x2'              # statsmodels shorthand
'x1:x2'                # statsmodels interaction
```

**Questions for GPT:**
1. **Should we allow function calls in formulas (`I(np.log(x))`)? Why or why not?**
2. If yes, which functions to whitelist? (log, sqrt, exp, sin, cos?)
3. If no, is "pre-compute columns" requirement reasonable for users?
4. What are security risks of evaluating arbitrary code?
5. Better approach: AST parsing? Expression compiler? statsmodels?

### Q3.2: Formula Validation Strategy

**Options:**
1. Strict: Validate at API entry, fail on any unsupported syntax
2. Permissive: Try to parse, warn on issues, proceed if possible
3. Deferred: Only validate when fit is attempted

**Questions for GPT:**
1. Which validation strategy is most user-friendly?
2. When should validation errors vs warnings be raised?
3. What validation checks are critical vs nice-to-have?
4. How to provide actionable error messages?

### Q3.3: Formula Parser Implementation

**Options:**
1. Use statsmodels/patsy (dependency, robust)
2. Custom regex parser (no dependency, limited)
3. AST-based parser (complex, flexible)

**Questions for GPT:**
1. Which parser implementation approach is best?
2. Is statsmodels dependency acceptable for core functionality?
3. If custom parser, what edge cases will we miss?
4. Trade-offs between simplicity and flexibility?

---

## 4. Testing Strategy

### Q4.1: Multi-Dimensional Testing

**Decision:** Test 1D-4D by default, not just 1D or 3D.

```python
test_1d_simple()      # 50 bins
test_2d_basic()       # 20×10 = 200 bins
test_3d_standard()    # 20×10×10 = 2000 bins
test_4d_tracking()    # 10×10×5×4 = 2000 bins
```

**Questions for GPT:**
1. Is 1D-4D coverage sufficient to catch dimension-dependent bugs?
2. Should we also test 5D-6D in unit tests or only in benchmarks?
3. Are test sizes (bins, entries) appropriate for fast tests?
4. What specific dimension-dependent issues should we test for?

### Q4.2: Test Priorities

**Proposed test hierarchy:**
```
Level 1: Unit tests (fast, <10s total)
  - 1D, 2D, 3D, 4D basic tests
  - Edge cases, error handling
  
Level 2: Integration tests (moderate, <60s)
  - 3D TPC distortion validation
  - Multi-target fits
  - Different window configs
  
Level 3: Benchmarks (slow, <300s)
  - Production-scale data
  - Performance regression
  - Memory profiling
```

**Questions for GPT:**
1. Is this test hierarchy appropriate?
2. Are timing targets realistic?
3. What critical test cases are missing?
4. Should validation tests be in unit tests or integration tests?

---

## 5. Implementation Priorities

### Q5.1: Phased Implementation

**Proposed phases:**
```
M7.1 Phase 1 (Core API):
  - fit_specs parsing
  - output naming
  - formula validation
  
M7.1 Phase 2 (ROOT Export):
  - uproot export (2 lines)
  - test integration
  
M7.1 Phase 3 (Multi-D Tests):
  - 1D-4D test suite
  - TPC validation update
```

**Questions for GPT:**
1. Is this phasing appropriate?
2. Should anything be moved to M7.2 instead?
3. What are critical path items for M7.1?
4. Any parallelizable work?

### Q5.2: Risk Areas

**Identified risks:**
1. Formula parsing complexity
2. Breaking changes to existing code
3. Performance regression with new API
4. Memory issues with multi-target fits

**Questions for GPT:**
1. What are the highest-risk items?
2. How to mitigate each risk?
3. What risks are we missing?
4. Should we prototype risky areas first?

---

## 6. Potential Issues & Improvements

### Q6.1: Scalability Concerns

**Questions for GPT:**
1. How will this API scale to 10+ targets?
2. What happens with very long column names (>100 chars)?
3. Any DataFrame size limitations (columns, rows)?
4. Performance impact of many output columns?

### Q6.2: User Experience

**Questions for GPT:**
1. Is the API self-documenting enough?
2. Are error messages clear and actionable?
3. What common mistakes will users make?
4. How to provide helpful defaults?

### Q6.3: Future Extensibility

**Questions for GPT:**
1. How to add new fit types (e.g., quantile regression)?
2. How to support per-target options (e.g., different fitters)?
3. Room for weighted fits, robust regression?
4. Path to GPU acceleration (CuPy, JAX)?

### Q6.4: Alternative Designs

**Questions for GPT:**
1. Should we have considered a class-based API instead?
   ```python
   fitter = SlidingWindowFitter(df, group_columns, window_spec)
   fitter.add_target('dX_meas', formula='...')
   result = fitter.fit()
   ```
2. Should targets be a separate DataFrame instead of dict?
3. Would a declarative YAML/JSON config be better for complex cases?
4. Any design patterns from other libraries we should adopt?

---

## 7. Specification Completeness

### Q7.1: Missing Sections

**Questions for GPT:**
1. What critical details are missing from the specification?
2. Are all edge cases documented?
3. Are examples comprehensive enough?
4. What ambiguities remain?

### Q7.2: Documentation Quality

**Questions for GPT:**
1. Is the specification clear enough for implementation?
2. Are there contradictions or inconsistencies?
3. What needs better explanation?
4. Should we add UML diagrams or flowcharts?

---

## 8. Critical Decisions Needed

### Q8.1: Formula Functions (BLOCKING)

**User said: "Formula - not clear"**

**GPT, please provide clear recommendation:**

**Option A: Allow function calls**
```python
'I(np.log(drift)) + I(np.sqrt(dr))'
```
- Pros: Flexible, convenient
- Cons: Security risk, harder to validate, may slow fits

**Option B: Require pre-computed columns**
```python
# User must do:
df['log_drift'] = np.log(df['drift'])
# Then use:
'log_drift + dr'
```
- Pros: Simple, safe, explicit
- Cons: More user code, less convenient

**Option C: Whitelist specific functions**
```python
# Only allow: log, log10, sqrt, exp, abs, sin, cos
'I(log(drift)) + I(sqrt(dr))'  # OK
'I(custom_func(x))'             # ERROR
```
- Pros: Balance of flexibility and safety
- Cons: Incomplete, still validation complexity

**GPT: Which option do you recommend and why?**

### Q8.2: Standard Errors (BLOCKING)

**Should we include stderr columns by default?**

```python
{output_var}_stderr_drift
{output_var}_stderr_dr
{output_var}_stderr_intercept
```

**GPT: Your recommendation?**
- Include by default (useful for uncertainty)?
- Optional flag (reduce clutter)?
- Omit (add later if needed)?

---

## 9. Final Questions

### Q9.1: Overall Assessment

**GPT, please provide:**
1. Overall quality score (1-10) for this specification
2. Top 3 strengths
3. Top 3 weaknesses
4. Biggest concern / risk
5. Readiness for implementation (Ready / Needs work / Major revisions)

### Q9.2: Comparison to Industry Standards

**Questions for GPT:**
1. How does this API compare to sklearn, statsmodels, pandas?
2. Are we following Python best practices?
3. What would surprise experienced users?
4. Any anti-patterns we should avoid?

### Q9.3: Actionable Next Steps

**GPT, please provide prioritized list:**
1. [ ] Critical fixes (blocking)
2. [ ] Important improvements (should have)
3. [ ] Nice-to-haves (could defer)
4. [ ] Out of scope (M7.2+)

---

## 10. Review Checklist for GPT

Please confirm you've reviewed:

- [ ] API design (fit_specs, suffix)
- [ ] Naming conventions (output columns, sanitization)
- [ ] Formula syntax (support level, validation)
- [ ] Testing strategy (multi-dimensional, coverage)
- [ ] Implementation plan (phases, risks)
- [ ] Scalability concerns
- [ ] User experience
- [ ] Specification completeness

**And provide:**
- [ ] Critical decision on formula functions (Q8.1)
- [ ] Recommendation on stderr columns (Q8.2)
- [ ] Overall assessment (Q9.1)
- [ ] Prioritized action items (Q9.3)

---

**Thank you for your review!**

Once GPT approves (or we make revisions), we can proceed with implementation.

---

## Appendix: Key Specification Sections

For GPT's reference, the key decisions are:

1. **API:** List of dicts with `{input_var, output_var, formula, predictors}`
2. **Suffix:** Global parameter appended to all output_var names
3. **Naming:** `{output_var}{suffix}_{metric}` pattern
4. **ROOT:** Full DataFrame export with uproot (2 lines)
5. **Tests:** 1D-4D by default in unit tests
6. **Formula:** NEEDS DECISION - function calls or not?

**See full specification:** `SPECIFICATION_FIT_FORMULA_v2.1.1.md`
