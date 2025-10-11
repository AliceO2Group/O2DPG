# quantile_fit_nd — Generic ND Quantile Linear Fitting Framework
**Version:** v3.1  
**Status:** Implementation Ready

---

## 1. Overview

This module provides a detector-agnostic framework for **quantile-based linear fitting** used in calibration, combined multiplicity estimation, and flow monitoring.

We approximate the local inverse quantile function around each quantile grid point $q_0$ as:

$$
X(Q, \mathbf{n}) \;=\; a(q_0,\mathbf{n}) \;+\; b(q_0,\mathbf{n}) \cdot (Q - q_0)
$$

where:
- $Q$ is the quantile rank of the amplitude,
- $\mathbf{n}$ are nuisance coordinates (e.g., $z_{\mathrm{vtx}}, \eta, t$),
- \(a\) is the OLS intercept at \(q_0\),
- \(b>0\) is the local slope (monotonicity in \(Q\)).

The framework outputs **tabulated coefficients and diagnostics** in a flat DataFrame for time-series monitoring, ML downstream use, and export to Parquet/Arrow/ROOT.

---

## 2. Directory contents

| File | Role |
|---|---|
| `quantile_fit_nd.py` | Implementation (fit, interpolation, evaluator, I/O) |
| `test_quantile_fit_nd.py` | Unit & synthetic tests |
| `quantile_fit_nd.md` | This design & usage document |

---

## 3. Goals

1. Fit local linear inverse-CDF per **channel** with monotonicity in $Q$.
2. Smooth over nuisance axes with separable interpolation (linear/PCHIP).
3. Provide **physics-driven** slope floors to avoid rank blow-ups.
4. Store results as **DataFrames** with rich diagnostics and metadata.
5. Keep the API **detector-independent** (no detector ID in core interface).

---

## 4. Required input columns

| Column | Description |
|---|---|
| `channel_id` | Unique local channel key |
| `Q` | Quantile rank (normalized by detector reference) |
| `X` | Measured amplitude (or normalized signal) |
| `z_vtx`, `eta`, `time` | Nuisance coordinates (configurable subset) |
| `is_outlier` | Optional boolean mask; `True` rows are excluded from fits |

> Preprocessing (e.g., timing outliers) is expected to fill `is_outlier`.

---

## 5. Output table schema

The fit returns a flat, appendable table with explicit grid points.

| Column | Description |
|---|---|
| `channel_id` | Channel identifier |
| `q_center` | Quantile center of the local fit |
| `<axis>_center` | Centers of nuisance bins (e.g., `z_center`) |
| `a` | Intercept (from OLS at $q_0$) |
| `b` | Slope (clipped to $b_{\min}>0$ if needed) |
| `sigma_Q` | Total quantile uncertainty $ \sigma_{X|Q} / |b| $ |
| `sigma_Q_irr` | Irreducible error (from multiplicity fluctuation) |
| `dX_dN` | Sensitivity to multiplicity proxy (optional) |
| `db_d<axis>` | Finite-difference derivative along each nuisance axis |
| `fit_stats` | JSON with `Npoints`, `RMS`, `chi2_ndf`, `masked_frac`, `clipped_frac` |
| `timestamp` | Calibration/run time (optional) |

**Example metadata stored in `DataFrame.attrs`:**
```json
{
  "model": "X = a + b*(Q - q_center)",
  "dq": 0.05,
  "b_min_option": "auto",
  "b_min_formula": "b_min = 0.25 * sigma_X / (2*dq)",
  "axes": ["q", "z"],
  "fit_mode": "ols",
  "kappa_w": 1.3
}
````

---

## 6. Fit procedure (per channel, per grid cell)

1. **Window selection**: select rows with (|Q - q_0| \le \Delta q) (default (\Delta q=0.05)).
2. **Masking**: use rows where `is_outlier == False`. Record masked fraction.
3. **Local regression**: OLS fit of (X) vs ((Q-q_0)) → coefficients (a, b).
4. **Uncertainty**:

- Residual RMS → $\sigma_{X|Q}$
- Total quantile uncertainty: $ \sigma_Q = \sigma_{X|Q} / |b| $
- Irreducible term: $ \sigma_{Q,\mathrm{irr}} = |dX/dN| \cdot \sigma_N / |b| $ with $\sigma_N \approx \kappa_w \sqrt{N_{\text{proxy}}}$
5. **Monotonicity**:

   - Enforce $ b > b_{\min} $.
    * Floor policy:

        * `"auto"`: ( b_{\min} = 0.25 \cdot \sigma_X / (2\Delta q) ) (heuristic)
        * `"fixed"`: constant floor (default (10^{-6}))
    * Record `clipped_frac` in `fit_stats`.
6. **Tabulation**: write row with coefficients, diagnostics, and centers of nuisance bins.

**Edge quantiles**: same $\Delta q$ policy near $q=0,1$ (no special gating by default).

---

## 7. Interpolation and monotonicity preservation

* **Separable interpolation** along nuisance axes (e.g., `z`, `eta`, `time`) using linear or shape-preserving PCHIP.
* **Monotone axis**: (Q). At evaluation: nearest or linear between adjacent `q_center` points.
* **Guarantee**: if all tabulated $b>0$ and nuisance interpolation does not cross zero, monotonicity in $Q$ is preserved. Any interpolated $b \le 0$ is clipped to $b_{\min}$.

Correlations between nuisance axes are **diagnosed** (scores stored) but **not** modeled by tensor interpolation in v3.1.

---

## 8. Public API (summary)

### Fitting

```python
fit_quantile_linear_nd(
    df,
    channel_key="channel_id",
    q_centers=np.linspace(0, 1, 11),
    dq=0.05,
    nuisance_axes={"z": "z_vtx"},   # add {"eta": "eta"}, {"time": "timestamp"} later
    mask_col="is_outlier",
    b_min_option="auto",            # or "fixed"
    fit_mode="ols"                  # "huber" optional in later versions
) -> pandas.DataFrame
```

### Evaluation

```python
eval = QuantileEvaluator(result_table)

# Interpolated parameters at coordinates:
a, b, sigma_Q = eval.params(channel_id=42, q=0.40, z=2.1)

# Invert amplitude to rank (clip to [0,1]):
Q = eval.invert_rank(X=123.0, channel_id=42, z=2.1)
```

### Persistence

```python
save_table(df, "calibration.parquet")
save_table(df, "calibration.arrow", fmt="arrow")
save_table(df, "calibration.root",  fmt="root")  # requires uproot/PyROOT
df2 = load_table("calibration.parquet")
```

---

## 9. Derivatives & irreducible error

* **Finite differences** for `db_dz`, `db_deta` at grid centers (central where possible; forward/backward at edges).
* **Irreducible error** (stored as `sigma_Q_irr`):
$ \sigma_{Q,\mathrm{irr}} = |dX/dN| \cdot \sigma_N / |b| $, with $\sigma_N = \kappa_w \sqrt{N_{\text{proxy}}}$.  
  `kappa_w` (default 1.3) reflects weight fluctuations (documented constant; can be overridden).

> For data without truth $N$, $dX/dN$ may be estimated against a stable multiplicity proxy from the combined estimator.

---

## 10. QA & summaries

Optional **per-channel summary** rows per calibration period:

* mean/median of `sigma_Q`,
* `%` of cells clipped by `b_min`,
* masked fraction,
* residual RMS, `chi2_ndf`,
* counts of fitted vs. skipped cells.

Drift/stability analysis is expected in external tooling by **chaining** calibration tables over time.

---

## 11. Unit & synthetic tests (see `test_quantile_fit_nd.py`)

| Test ID | Purpose                                       |
| ------- | --------------------------------------------- |
| T00     | Smoke test (single channel, (q,z) grid)       |
| T01     | Monotonicity enforcement (all (b > b_{\min})) |
| T02     | Edge behavior near (q\in{0,1}) per policy     |
| T03     | Outlier masking stability                     |
| T04     | (\sigma_Q) scaling vs injected noise          |
| T05     | `db_dz` finite-diff accuracy on known slope   |
| T06     | Round-trip (Q \to X \to Q) small residual     |
| T07     | Parquet/Arrow/ROOT save/load parity           |

---

## 12. Performance expectations

| Aspect          | Estimate                                                 |
| --------------- | -------------------------------------------------------- |
| Complexity      | (O(N \cdot \Delta q)) per channel                        |
| CPU             | (q,z) fit: seconds; ND adds ~20–30% from interpolation   |
| Parallelization | Natural via Pandas/Dask groupby                          |
| Table size      | (O(\text{grid points} \times \text{channels})), MB-scale |
| Storage         | Parquet typically < 10 MB per calibration slice          |

---

## 13. Configurable parameters

| Name            | Default          | Meaning                                  |
| --------------- | ---------------- | ---------------------------------------- |
| `dq`            | 0.05             | Quantile window half-width               |
| `b_min_option`  | `auto`           | Slope floor policy (`auto` or `fixed`)   |
| `fit_mode`      | `ols`            | Regression type                          |
| `mask_col`      | `is_outlier`     | Outlier flag column                      |
| `kappa_w` | 1.3 | Weight-fluctuation factor (doc/override) |
| `nuisance_axes` | `{"z": "z_vtx"}` | Axes for smoothing                       |

---

## 14. Future extensions

* Optional **Huber** robust regression mode.
* Degree-2 local fits with derivative-based monotonicity checks.
* Covariance modeling across nuisance axes.
* Adaptive time binning based on drift thresholds.
* ML-ready derivatives and cost-function integration.

---

## 15. References

* PWG-P context: combined multiplicity/flow estimator materials.
* RootInteractive / AliasDataFrame pipelines for calibration QA.

---
