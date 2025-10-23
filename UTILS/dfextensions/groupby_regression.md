# GroupBy Linear Regression Utilities

This module provides utilities for computing group-wise linear fits and robust statistics on pandas DataFrames. It is designed to support workflows that require fitting separate models across grouped subsets of data.

Originally developed for **distortion correction** and **dE/dx calibration** in high-energy physics experiments, the code has since been generalized to support broader applications involving grouped linear regression and statistical feature extraction.

## Functions

### `GroupByRegressor.make_linear_fit(...)`

Performs group-wise **ordinary least squares (OLS)** regression fits.

#### Parameters:

* `df (pd.DataFrame)`: Input data
* `gb_columns (list[str])`: Columns to group by
* `fit_columns (list[str])`: Dependent (target) variables
* `linear_columns (list[str])`: Independent variables
* `median_columns (list[str])`: Columns for which medians are computed
* `suffix (str)`: Suffix for generated columns
* `selection (pd.Series)`: Boolean mask selecting rows to use
* `addPrediction (bool)`: If True, predictions are added to the original DataFrame
* `cast_dtype (str | None)`: Optional type casting (e.g., 'float32', 'float16') for fit results
* `min_stat (int)`: Minimum number of rows in a group to perform fitting

#### Returns:

* `(df_out, dfGB)`:

  * `df_out`: Original DataFrame with predictions (if enabled)
  * `dfGB`: Per-group statistics, including slopes, intercepts, medians, and bin counts

---

### `GroupByRegressor.make_parallel_fit(...)`

Performs **robust group-wise regression** using `HuberRegressor`, with optional parallelization.

#### Additional Parameters:

* `weights (str)`: Column to use as weights during regression
* `n_jobs (int)`: Number of parallel processes to use
* `min_stat (list[int])`: Minimum number of points required for each predictor in `linear_columns`
* `sigmaCut (float)`: Threshold multiplier for MAD to reject outliers

#### Notes:

* Supports partial predictor exclusion per group based on `min_stat`
* Uses robust iteration with outlier rejection (MAD filtering)
* Falls back to NaNs when fits are ill-conditioned or predictors are skipped

## Example

```python
from groupby_regression import GroupByRegressor

df_out, dfGB = GroupByRegressor.make_parallel_fit(
  df,
  gb_columns=['detector_sector'],
  fit_columns=['dEdx'],
  linear_columns=['path_length', 'momentum'],
  median_columns=['path_length'],
  weights='w_dedx',
  suffix='_calib',
  selection=(df['track_quality'] > 0.9),
  cast_dtype='float32',
  addPrediction=True,
  min_stat=[20, 20],
  n_jobs=4
)
```

## Output Columns (in `dfGB`):

| Column Name                               | Description                              |
| ----------------------------------------- | ---------------------------------------- |
| `<target>_slope_<predictor>_<suffix>`     | Regression slope for predictor           |
| `<target>_intercept_<suffix>`             | Regression intercept                     |
| `<target>_rms_<suffix>` / `_mad_<suffix>` | Residual stats (robust only)             |
| `<median_column>_<suffix>`                | Median of the specified column per group |
| `bin_count_<suffix>`                      | Number of entries in each group          |

## Regression Flowchart

```text
+-------------+
|  Input Data |
+------+------+
       |
       v
+------+------+
|  Apply mask |
|  (selection)|
+------+------+
       |
       v
+----------------------------+
|  Group by gb_columns       |
+----------------------------+
       |
       v
+----------------------------+
|  For each group:           |
|  - Check min_stat          |
|  - Fit model               |
|  - Estimate residual stats |
+----------------------------+
       |
       v
+-------------+    +-------------+
|  df_out     |    |   dfGB      |
| (with preds)|    | (fit params)|
+-------------+    +-------------+
```

## Use Cases

* Detector distortion correction
* dE/dx signal calibration
* Grouped trend removal in sensor data
* Statistical correction of multi-source measurements

## Test Coverage

* Basic regression fit and prediction verification
* Edge case handling (missing data, small groups)
* Outlier injection and robust fit evaluation
* Exact recovery of known coefficients
* `cast_dtype` precision testing

## Performance & Benchmarking

### Overview

To evaluate scaling and performance trade-offs, a dedicated benchmark tool is provided:

```bash
python3 bench_groupby_regression.py \
  --rows-per-group 5 --groups 5000 \
  --n-jobs 10 --sigmaCut 5 --fitter ols \
  --out bench_out --emit-csv
```

Each run generates:

* `benchmark_report.txt` – human-readable summary
* `benchmark_results.json` / `.csv` – structured outputs for analysis



### Example Results (25k rows / 5k groups ≈ 5 rows/group)

**Command**

```bash
python3 bench_groupby_regression.py \
  --rows-per-group 5 --groups 5000 \
  --n-jobs 10 --sigmaCut 5 --fitter ols \
  --out bench_out --emit-csv
```

**Laptop (Mac):**

| Scenario                        | Config                    | Result (s / 1k groups) |
| ------------------------------- | ------------------------- | ---------------------- |
| Clean Serial                    | n_jobs=1, sigmaCut=5, OLS | **1.69**               |
| Clean Parallel (10)             | n_jobs=10                 | **0.50**               |
| 5% Outliers (3σ), Serial        | n_jobs=1                  | **1.68**               |
| 10% Outliers (5σ), Serial       | n_jobs=1                  | **1.67**               |
| **30% Outliers (5σ), Serial**   | n_jobs=1                  | **1.66**               |
| **30% Outliers (5σ), Parallel** | n_jobs=10                 | **0.30**               |
| 10% Outliers (10σ), Serial      | n_jobs=1                  | **1.67**               |

**Server (Linux, Apptainer):**

| Scenario                    | Config                    | Result (s / 1k groups) |
| --------------------------- | ------------------------- | ---------------------- |
| Clean Serial                | n_jobs=1, sigmaCut=5, OLS | **4.14**               |
| Clean Parallel (10)         | n_jobs=10                 | **0.98**               |
| 5% Outliers (3σ), Serial    | n_jobs=1                  | **4.03**               |
| 10% Outliers (5σ), Serial   | n_jobs=1                  | **4.01**               |
| 10% Outliers (5σ), Parallel | n_jobs=10                 | **0.65**               |
| 10% Outliers (10σ), Serial  | n_jobs=1                  | **4.01**               |

*Dataset:* synthetic (y = 2·x₁ + 3·x₂ + ε)

#### High Outlier Fraction (Stress Test)

Even at **30% response outliers**, runtime remains essentially unchanged (no robust re-fit triggered by sigmaCut).
To emulate worst-case slowdowns seen on real data, a **leverage-outlier** mode (X-contamination) will be added in a follow-up.


### Diagnostic Summary Utilities

The regression framework can optionally emit per-group diagnostics when `diag=True`
is passed to `make_parallel_fit()`.

Diagnostics include:

| Field | Meaning |
|:------|:--------|
| `diag_time_ms` | Wall-time spent per group (ms) |
| `diag_n_refits` | Number of extra robust re-fits required |
| `diag_frac_rejected` | Fraction of rejected points after sigma-cut |
| `diag_cond_xtx` | Condition number proxy for design matrix |
| `diag_hat_max` | Maximum leverage in predictors |
| `diag_n_rows` | Number of rows in the group |

Summaries can be generated directly:

```python
summary = GroupByRegressor.summarize_diagnostics(dfGB, diag_prefix="diag_", suffix="_fit")
print(GroupByRegressor.format_diagnostics_summary(summary))
```

### Interpretation

* The **OLS path** scales linearly with group count.
* **Parallelization** provides 4–5× acceleration for thousands of small groups.
* Current synthetic *y‑only* outliers do **not** trigger re‑fitting overhead.
* Real‑data slowdowns (up to 25×) occur when **sigmaCut** forces iterative robust refits.

### Recommendations

| Use case                       | Suggested settings                                      |
| ------------------------------ | ------------------------------------------------------- |
| Clean data                     | `sigmaCut=100` (disable refit), use `n_jobs≈CPU cores`  |
| Moderate outliers              | `sigmaCut=5–10`, enable parallelization                 |
| Heavy outliers (detector data) | Use `fitter='robust'` or `huber` and accept higher cost |
| Quick validation               | `bench_groupby_regression.py --quick`                   |

Here’s a concise, ready-to-paste paragraph you can drop directly **under the “Interpretation”** section in your `groupby_regression.md` file:

---

### Cross-Platform Comparison (Mac vs Linux)

Benchmark results on a Linux server (Apptainer, Python 3.11, joblib 1.4) show similar scaling but roughly **2–2.5 × longer wall-times** than on a MacBook (Pro/i7).
For the baseline case of 50 k rows / 10 k groups (~5 rows/group):

| Scenario                    | Mac (s / 1 k groups) | Linux (s / 1 k groups) | Ratio (Linux / Mac) |
| --------------------------- | -------------------- | ---------------------- | ------------------- |
| Clean Serial                | 1.75                 | 3.98                   | ≈ 2.3 × slower      |
| Clean Parallel (10)         | 0.41                 | 0.78                   | ≈ 1.9 × slower      |
| 10 % Outliers (5 σ, Serial) | 1.77                 | 4.01                   | ≈ 2.3 × slower      |

Parallel efficiency on Linux (≈ 5 × speed-up from 1 → 10 jobs) matches the Mac results exactly.
The difference reflects platform-specific factors such as CPU frequency, BLAS implementation, and process-spawn overhead in Apptainer—not algorithmic changes.
Overall, **scaling behavior and outlier stability are identical across platforms.**

---



### Future Work

A future extension will introduce **leverage‑outlier** generation (outliers in X and Y) to replicate the observed 25× slowdown and allow comparative testing of different robust fitters.

## Tips

💡 Use `cast_dtype='float16'` for storage savings, but ensure it is compatible with downstream numerical precision requirements.

### Usage Example for `cast_dtype`

```python
import pandas as pd
import numpy as np
from dfextensions.groupby_regression import GroupByRegressor

# Sample DataFrame
df = pd.DataFrame({
  'group': ['A'] * 10 + ['B'] * 10,
  'x': np.linspace(0, 1, 20),
  'y': np.linspace(0, 2, 20) + np.random.normal(0, 0.1, 20),
  'weight': 1.0,
})

# Linear fit with casting to float32
df_out, dfGB = GroupByRegressor.make_parallel_fit(
  df,
  gb_columns=['group'],
  fit_columns=['y'],
  linear_columns=['x'],
  median_columns=['x'],
  weights='weight',
  suffix='_f32',
  selection=df['x'].notna(),
  cast_dtype='float32',
  addPrediction=True
)

# Check resulting data types
print(dfGB.dtypes)
```

### Output (Example)

```
group                      object
x_f32                    float64
y_slope_x_f32            float32
y_err_x_f32              float32
y_intercept_f32          float32
y_rms_f32                float32
y_mad_f32                float32
bin_count_f32              int64
dtype: object
```

## Recent Changes

* ✅ Unified `min_stat` interface for both OLS and robust fits
* ✅ Type casting via `cast_dtype` param (e.g. `'float16'` for storage efficiency)
* ✅ Stable handling of singular matrices and small group sizes
* ✅ Test coverage for missing values, outliers, and exact recovery scenarios
* ✅ Logging replaces print-based diagnostics for cleaner integration
