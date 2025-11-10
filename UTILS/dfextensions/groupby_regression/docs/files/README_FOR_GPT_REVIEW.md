# Specification Review Package - Ready for GPT

**Date:** 2025-10-28  
**Status:** Ready for GPT review  
**Next Step:** Get GPT feedback, finalize, implement

---

## 📦 Package Contents

### 1. [SPECIFICATION_FIT_FORMULA_v2.1.1.md](computer:///mnt/user-data/outputs/SPECIFICATION_FIT_FORMULA_v2.1.1.md)
**Complete specification with user decisions incorporated**

Key decisions made:
- ✅ API: List of dictionaries (fit_specs)
- ✅ Output naming: Global suffix parameter
- ✅ ROOT export: Full DataFrame with uproot
- ✅ Testing: Multi-dimensional (1D-4D) by default
- ❓ Formula syntax: **NEEDS CLARIFICATION**

### 2. [GPT_REVIEW_QUESTIONS.md](computer:///mnt/user-data/outputs/GPT_REVIEW_QUESTIONS.md)
**Structured questions for GPT review**

10 review areas:
1. API Design & Usability
2. Naming Conventions
3. Formula Syntax (critical)
4. Testing Strategy
5. Implementation Priorities
6. Scalability
7. Specification Completeness
8. **Critical Decisions Needed**
9. Overall Assessment
10. Review Checklist

---

## 🎯 Your Decisions Incorporated

### ✅ Decision 1: List of Dicts
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

### ✅ Decision 2: Global Suffix
```python
result = make_sliding_window_fit(..., suffix='_corrected')
# Produces: dX_corrected_mean, dX_corrected_slope_drift
```

### ✅ Decision 3: ROOT Export
```python
import uproot
uproot.recreate("test_tpc_distortion_recovery.root", {"validation": df})
```

### ❓ Decision 4: Formula Syntax
**Your comment:** "Formula - not clear"

**Questions prepared for GPT:**
- Allow `I(np.log(x))` function calls?
- Or require pre-computed columns?
- Which validation level?

### ✅ Decision 5: Multi-Dimensional Tests
```python
test_1d_simple()    # Find issues early
test_2d_basic()
test_3d_standard()
test_4d_tracking()
```

---

## 🚨 Critical for GPT: Formula Syntax Decision (BLOCKING)

**Need GPT recommendation on:**

**Option A: Allow function calls**
```python
'I(np.log(drift)) + I(np.sqrt(dr))'
```

**Option B: Require pre-computed columns**
```python
df['log_drift'] = np.log(df['drift'])
# Then use: 'log_drift + dr'
```

**Option C: Whitelist specific functions**
```python
'I(log(drift)) + I(sqrt(dr))'  # Only allow: log, sqrt, exp, etc.
```

**This blocks implementation!**

---

## 📊 Files Ready for GPT Review

1. **[SPECIFICATION_FIT_FORMULA_v2.1.1.md](computer:///mnt/user-data/outputs/SPECIFICATION_FIT_FORMULA_v2.1.1.md)** - Full spec
2. **[GPT_REVIEW_QUESTIONS.md](computer:///mnt/user-data/outputs/GPT_REVIEW_QUESTIONS.md)** - Structured questions

---

## ✅ Ready to Send to GPT

Forward these two files to GPT with your questions about formula syntax!
