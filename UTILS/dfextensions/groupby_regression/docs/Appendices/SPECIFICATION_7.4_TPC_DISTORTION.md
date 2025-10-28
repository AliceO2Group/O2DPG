# § 7.4 Synthetic-Data Test Specification (Realistic TPC Distortion Model)

**Version:** 2.1.0  
**Phase:** M7.1 Sliding Window Regression  
**Status:** APPROVED

---

## 7.4.1 Purpose

The synthetic dataset emulates the behavior of TPC distortion maps under controlled yet realistic conditions. It provides ground-truth relationships among drift length, radial coordinate, and sector offset to test:

1. **Correctness** of the sliding-window aggregation and fitting logic
2. **Recovery** of known calibration parameters
3. **Dependence** of statistical precision on neighborhood size and kernel width
4. **Alarm system** for quality assurance gates

This test constitutes the primary validation that M7.1 can recover true distortion fields from noisy measurements, as required for production TPC calibration.

---

## 7.4.2 Physical Model and Variable Definitions

Each synthetic entry represents a tracklet measurement within one TPC sector. All variables are generated with the same naming convention as real calibration data to ensure seamless integration with production workflows.

| Symbol | Column name | Definition | Typical range / units |
|--------|-------------|------------|----------------------|
| $r$ | `r` | Radius at pad row | 82–250 cm |
| $\mathrm{dr}$ | `xBin` | Discrete radial bin index (~1 cm spacing) | 0–170 |
| — | `z2xBin` | Discrete drift coordinate (0=readout, 20=cathode) | 0–20 |
| — | `y2xBin` | Sector coordinate index | 0–20 |
| $\mathrm{drift}$ | `drift` | Drift length along $z$ | $250 - \frac{z2xBin}{20} \cdot r$ [cm] |
| $\mathrm{dsec}$ | `dsec` | Relative position to sector centre | $\frac{y2xBin - 10}{20}$ |
| — | `meanIDC` | Mean current density indicator | random $\sim \mathcal{N}(0, 1)$ |
| — | `dX_true` | True distortion along $x$ | defined below |
| — | `dX_meas` | Measured distortion (with noise) | defined below |
| — | `weight` | Entry weight for fitting | 1.0 (uniform) |

---

## 7.4.3 Distortion Model

The true distortion is modeled as a combination of linear and parabolic dependencies in the key physical variables:

$$
\begin{aligned}
dX_{\text{true}} &= dX_0 + a_{\text{drift}} \cdot \mathrm{drift} \cdot \big(a_{1,\text{dr}} \cdot \mathrm{dr} + a_{2,\text{dr}} \cdot \mathrm{dr}^2\big) \\
&\quad + a_{\text{drift-dsec}} \cdot \mathrm{drift} \cdot \big(a_{1,\text{dsec}} \cdot \mathrm{dsec} + a_{1,\text{dsec-dr}} \cdot \mathrm{dsec} \cdot \mathrm{dr}\big) \\
&\quad + a_{1,\text{IDC}} \cdot \mathrm{meanIDC}
\end{aligned}
$$

### Typical Parameter Values

These parameters are chosen to emulate realistic TPC distortion magnitudes and dependencies observed in ALICE O² production data:

| Parameter | Description | Example value |
|-----------|-------------|---------------|
| $dX_0$ | Global offset | 0.0 |
| $a_{\text{drift}}$ | Drift-scale factor | $1.0 \times 10^{-3}$ |
| $a_{1,\text{dr}}$, $a_{2,\text{dr}}$ | Linear / quadratic radial coefficients | $(1.5 \times 10^{-2}, -4 \times 10^{-5})$ |
| $a_{\text{drift-dsec}}$ | Drift-sector coupling | $5 \times 10^{-4}$ |
| $a_{1,\text{dsec}}$, $a_{1,\text{dsec-dr}}$ | Sector offset and radial coupling | $(0.8, 0.3)$ |
| $a_{1,\text{IDC}}$ | Mean-current sensitivity | $2 \times 10^{-3}$ |

### Measured Quantity

A measured quantity is obtained by adding Gaussian noise:

$$
dX_{\text{meas}} = dX_{\text{true}} + \mathcal{N}(0, \sigma_{\text{meas}}), \quad \sigma_{\text{meas}} \approx 0.02 \text{ cm}
$$

The noise level $\sigma_{\text{meas}} = 0.02$ cm is representative of single-tracklet measurement resolution in ALICE TPC.

### DataFrame Structure

The synthetic DataFrame includes:

```python
columns = [
    'xBin', 'y2xBin', 'z2xBin',       # Discrete bin indices (grouping)
    'r', 'dr', 'dsec', 'drift',       # Physical coordinates (predictors)
    'meanIDC',                         # Current density (predictor)
    'dX_true', 'dX_meas',             # Ground truth and measurement
    'weight'                           # Entry weights
]
```

Ground truth parameters are stored in `df.attrs['ground_truth_params']` for automated validation.

---

## 7.4.4 Evaluation Metrics

For each tested configuration of `window_spec` (neighborhood size) and kernel width (weighting), the following metrics are computed:

### Primary Metrics

1. **Fit coefficients** ($\hat{a}_i$) and their estimated uncertainties ($\sigma_{\hat{a}_i}$)
2. **Residuals**: $\Delta = dX_{\text{true}} - dX_{\text{pred}}$
3. **Normalized residuals**: $\Delta / \sigma_{\text{fit}}$
4. **RMS residuals**: $\text{RMS}(\Delta) = \sqrt{\langle \Delta^2 \rangle}$

### Derived Metrics

5. **Pull distribution**: $\text{Pull} = (dX_{\text{meas,mean}} - dX_{\text{true,mean}}) / \sigma_{\text{fit}}$
6. **Recovery precision**: Fraction of bins where $|\Delta| \leq 4\sigma_{\text{meas}}$
7. **Statistical error scaling**: $\sigma(\Delta)$ vs. effective sample size

### Diagnostic Outputs

- Scatter plots: $dX_{\text{true}}$ vs. $dX_{\text{pred}}$
- Residual distributions: $\Delta$ histograms
- RMS($\Delta$) vs. window size
- Normalized residual distributions (should be $\mathcal{N}(0,1)$)
- Evolution of coefficient uncertainties with neighborhood size

---

## 7.4.5 Validation Rules and Alarm System

Quality validation uses a three-tier alarm system based on statistical significance levels. The alarm dictionary is computed using `df.eval()` for efficient vectorized checks.

### Alarm Criteria

| Check | Criterion | Status | Action |
|-------|-----------|--------|--------|
| **OK Range** | $\|\Delta\| \leq 4\sigma_{\text{meas}}$ | `OK` | No action |
| **Warning Range** | $4\sigma_{\text{meas}} < \|\Delta\| \leq 6\sigma_{\text{meas}}$ | `WARNING` | Monitor, report if >1% of bins |
| **Alarm Range** | $\|\Delta\| > 6\sigma_{\text{meas}}$ | `ALARM` | Investigation required |

### Additional Checks

| Check | Criterion | Purpose |
|-------|-----------|---------|
| Normalized residuals | $\mu \approx 0, \sigma \approx 1$ | Verify error estimation |
| RMS residuals | $\text{RMS}(\Delta) < 2 \times \sigma_{\text{expected}}$ | Check overall precision |
| Worst-case bins | Identify bins with $\max(\|\Delta\|)$ | Locate systematic issues |

When violations occur systematically, the alarm system emits warnings indicating possible:
- Local non-linearity in the distortion field
- Underestimated fit uncertainties
- Insufficient neighborhood size
- Edge effects or boundary artifacts

### Implementation

```python
# Example alarm check using df.eval()
ok_mask = df.eval('abs(delta) <= 4 * @sigma_meas')
warning_mask = df.eval('(abs(delta) > 4 * @sigma_meas) & (abs(delta) <= 6 * @sigma_meas)')
alarm_mask = df.eval('abs(delta) > 6 * @sigma_meas')

alarms = {
    'residuals_ok': {'count': ok_mask.sum(), 'fraction': ok_mask.mean()},
    'residuals_warning': {'count': warning_mask.sum(), 'fraction': warning_mask.mean()},
    'residuals_alarm': {'count': alarm_mask.sum(), 'fraction': alarm_mask.mean()}
}
```

---

## 7.4.6 Test Cases and Requirements

### Minimal Test (Unit Test)

**Grid size:** 50 × 10 × 10 bins  
**Entries per bin:** 50  
**Window spec:** `{'xBin': 3, 'y2xBin': 2, 'z2xBin': 2}`  
**Min entries:** 20  
**Expected runtime:** <10 seconds  

**Pass criteria:**
- ✅ No bins in ALARM range
- ✅ <1% bins in WARNING range
- ✅ Normalized residuals: $|\mu| < 0.1$, $|1 - \sigma| < 0.2$
- ✅ RMS residuals: $< 2\times$ expected

### Full Benchmark Test

**Grid size:** 170 × 20 × 20 bins (production scale)  
**Entries per bin:** 200  
**Window spec:** Multiple configurations  
**Expected runtime:** <5 minutes (numpy backend)  

**Pass criteria:**
- ✅ All unit test criteria
- ✅ Parameter recovery within 1$\sigma$ accuracy
- ✅ Scaling of errors with effective sample size
- ✅ Performance: >10k rows/sec

---

## 7.4.7 Integration with Test Suite

### File Structure

```
dfextensions/groupby_regression/
├── synthetic_tpc_distortion.py          # Data generator
├── tests/
│   ├── test_tpc_distortion_recovery.py  # Unit test (alarm-based)
│   ├── test_sliding_window_*.py         # Other unit tests
│   └── benchmark_tpc_distortion.py      # Full benchmark
└── validation/
    └── alarm_system.py                   # Reusable alarm utilities
```

### Usage in Unit Tests

```python
from synthetic_tpc_distortion import make_synthetic_tpc_distortion
from dfextensions.groupby_regression import make_sliding_window_fit

def test_distortion_recovery():
    # Generate data
    df = make_synthetic_tpc_distortion(...)
    
    # Run fit
    result = make_sliding_window_fit(df, ...)
    
    # Validate with alarms
    alarms = validate_with_alarms(result, df)
    
    # Assert
    assert alarms['summary']['status'] in ['OK', 'WARNING']
```

### Benchmark Usage

```python
# Benchmark both speed and correctness
df = make_synthetic_tpc_distortion(n_bins_dr=170, entries_per_bin=200)

start = time.time()
result = make_sliding_window_fit(df, ...)
elapsed = time.time() - start

# Check speed
assert len(df) / elapsed > 10000  # rows/sec

# Check correctness
alarms = validate_with_alarms(result, df)
assert alarms['summary']['status'] == 'OK'
```

---

## 7.4.8 Outcome and Deliverables

The synthetic-data tests will:

1. ✅ **Confirm recovery** of known coefficients within 1$\sigma$ accuracy
2. ✅ **Demonstrate scaling** of parameter errors with effective sample size
3. ✅ **Provide benchmark plots** for documentation and calibration validation
4. ✅ **Supply reproducible ground-truth** reference files (`synthetic_tpc_distortion.parquet`) for continuous-integration tests
5. ✅ **Validate alarm system** for production QA gates

### Expected Test Results

| Metric | Expected Value | Unit Test | Benchmark |
|--------|---------------|-----------|-----------|
| Bins in OK range | >99% | ✅ | ✅ |
| Bins in WARNING range | <1% | ✅ | ✅ |
| Bins in ALARM range | 0% | ✅ | ✅ |
| RMS residuals | <2× expected | ✅ | ✅ |
| Normalized residuals | $\mu=0 \pm 0.1$, $\sigma=1 \pm 0.2$ | ✅ | ✅ |
| Performance | >10k rows/sec | — | ✅ |

---

## 7.4.9 Future Extensions (M7.2+)

- **Weighted fits**: Test with non-uniform entry weights
- **Boundary conditions**: Test edge/corner bins explicitly
- **Missing data**: Test with sparse/missing bins
- **Non-Gaussian noise**: Test robustness to outliers
- **Multi-target fits**: Test multiple distortion components simultaneously
- **Numba acceleration**: Benchmark speed improvements

---

**Status:** ✅ Specification approved, implementation ready  
**Implementation files:** `synthetic_tpc_distortion.py`, `test_tpc_distortion_recovery.py`  
**Integration:** Phase M7.1 unit tests and benchmark suite

---

## References

- Phase 7 M7.1 Implementation Plan
- ALICE O² TPC Calibration Framework Documentation
- Statistical Methods for Physics Analysis (Cowan, 1998)
- Pandas DataFrame.eval() Documentation
