Short answer: **yes — a small update to `restartContext_groupby_regression.md` now will help** keep everyone aligned. We learned that response-only outliers don’t reproduce the slowdown; we set a new 5k/5 default; and we added a 30% scenario. That’s enough to warrant a “delta” refresh so Claude/others don’t chase the wrong thing.

Here’s a **drop-in replacement** you can paste over the current file (keeps the same structure, updated content). If you prefer to append, you can paste the “What changed” + “Action plan” sections at the top.

---

# Restart Context: GroupBy Regression Benchmarking & Documentation

**Date:** October 22, 2025
**Project:** dfextensions (ALICE O2 Physics)
**Focus:** `groupby_regression.py` — benchmarking & performance docs
**Target:** PR by Oct 25, 2025
**Collaborators:** GPT (Primary Coder), Claude (Reviewer), User (Approval)

---

## Executive Summary (updated)

Benchmarks on synthetic data show that **response-only outliers (shift in y)** do **not** slow down the OLS/robust path; runtime remains essentially unchanged even at **30% contamination**. Both Mac and Linux show similar **scaling** (Linux ≈2–2.5× slower wall time per 1k groups due to platform factors).
The **real-data 25× slowdown** is therefore likely due to **sigmaCut-triggered robust re-fits driven by leverage outliers in X** and/or multi-target fits (e.g., `dX,dY,dZ`) compounding the cost.

**New default benchmark:** **5,000 groups × 5 rows/group** (fast, representative).
**New scenarios:** include **30% outliers (5σ)** to demonstrate stability of response-only contamination.

---

## What changed since last update

* **Benchmark defaults:** `--rows-per-group 5 --groups 5000` adopted for docs & CI-friendly runs.
* **Scenarios:** Added **30% outliers (5σ)** in serial + parallel.
* **Findings:**

    * Mac (per 1k groups): serial ~**1.69 s**, parallel(10) ~**0.50 s**.
    * Linux (per 1k groups): serial ~**4.14 s**, parallel(10) ~**0.98 s**.
    * 5–30% response outliers: **no runtime increase** vs clean.
* **Conclusion:** Synthetic setup doesn’t trigger the **re-fit loop**; real data likely has **leverage** characteristics or different fitter path.

---

## Problem Statement (refined)

Observed **~25× slowdown** on real datasets when using `sigmaCut` robust filtering. Root cause is presumed **iterative re-fitting per group** when the mask updates (MAD-based) repeatedly exclude many points — common under **leverage outliers in X** or mixed contamination (X & y). Multi-target fitting (e.g., 3 targets) likely multiplies cost.

---

## Cross-Platform Note

Linux runs are **~2–2.5×** slower in absolute time than Mac, but **parallel speed-ups are consistent** (~4–5×). Differences are due to CPU/BLAS/spawn model (Apptainer), not algorithmic changes.

---

## Action Plan (next 48h)

1. **Add leverage-outlier generator** to benchmarks

    * API: `create_data_with_outliers(..., mode="response|leverage|both", x_mag=8.0)`
    * Goal: Reproduce sigmaCut re-fit slow path (target 10–25×).
2. **Instrument the fitter**

    * Add counters in `process_group_robust()`:

        * `n_refits`, `mask_fraction`, and per-group timings.
    * Emit aggregated stats in `dfGB` (or a side JSON) for diagnostics.
3. **Multi-target cost check**

    * Run with `fit_columns=['dX']`, then `['dX','dY','dZ']` to quantify multiplicative cost.
4. **Config toggles for mitigation** (document in perf section)

    * `sigmaCut=100` (disable re-fit) as a “fast path” when upstream filtering is trusted.
    * Optional `max_refits` (cap iterations), log a warning when hit.
    * Consider `fitter='huber'` fast-path if available.
5. **Finalize docs**

    * Keep 5k/5 as **doc default**; show Mac+Linux tables.
    * Add a **“Stress Test (Leverage)”** table once generator is merged.

---

## Deliverables Checklist

* [x] Single-file benchmark with 5k/5 default & 30% outlier scenarios
* [x] Performance section in `groupby_regression.md` (Mac/Linux tables)
* [ ] **Leverage-outlier generator** (+ scenarios)
* [ ] Fitter instrumentation (refit counters, timings)
* [ ] Performance tests (CI thresholds for clean vs stress)
* [ ] `BENCHMARKS.md` with full runs & environment capture

---

## Current Commands

**Default quick run (docs/CI):**

```bash
python3 bench_groupby_regression.py \
  --rows-per-group 5 --groups 5000 \
  --n-jobs 10 --sigmaCut 5 --fitter ols \
  --out bench_out --emit-csv
```

**Stress test placeholder (to be added):**

```bash
python3 bench_groupby_regression.py \
  --rows-per-group 5 --groups 5000 \
  --n-jobs 10 --sigmaCut 5 --fitter ols \
  --mode leverage --x-mag 8.0 \
  --out bench_out_stress --emit-csv
```

---

## Risks & Open Questions

* What outlier **structure** in real data triggers the re-fit? (X leverage? heteroscedasticity? group size variance?)
* Is the slowdown proportional to **targets × refits × groups**?
* Do container spawn/backends (forkserver/spawn) amplify overhead for very small groups?

---

**Last updated:** Oct 22, 2025 (this revision)
# Restart Context: GroupBy Regression Benchmarking & Diagnostics Integration

**Date:** October 23 2025  
**Project:** dfextensions (ALICE O2 Physics)  
**Focus:** `groupby_regression.py` — diagnostic instrumentation and benchmark integration  
**Next Phase:** Real-data performance characterization

---

## Summary of Latest Changes

* **Diagnostics added to core class**
    - `GroupByRegressor.summarize_diagnostics()` and `format_diagnostics_summary()` now compute mean/median/std + quantiles (p50–p99) for all key diagnostic metrics (`time_ms`, `n_refits`, `frac_rejected`, `cond_xtx`, `hat_max`, `n_rows`).
    - Handles both prefixed (`diag_…`) and suffixed (`…_fit`, `…_dIDC`) columns.

* **Benchmark integration**
    - `bench_groupby_regression.py` now:
        - Calls class-level summary after each scenario.
        - Writes per-scenario `diag_summary.csv` and appends human-readable summaries to `benchmark_report.txt`.
        - Saves `diag_top10_time__<scenario>.csv` and `diag_top10_refits__<scenario>.csv` for quick inspection.
    - Default benchmark: `--rows-per-group 5 --groups 1000 --diag`.

* **Validation**
    - Real-data summary confirmed correct suffix handling (`_dIDC`).
    - Pytest and all synthetic benchmarks pass.

---

## Observations from Real Data

* Median per-group fit time ≈ 7 ms (p99 ≈ 12 ms).
* ~99 % of groups perform 3 robust re-fits → robust loop fully active.
* Only ~2 % mean rejection fraction, but 99th percentile ≈ 0.4 → a few heavy-outlier bins drive cost.
* Conditioning (cond_xtx ≈ 1) and leverage (hat_max ≈ 0.18) are stable → slowdown dominated by the sigmaCut iteration.

---

## Next Steps (Real-Use-Case Phase)

1. **Collect diagnostic distributions on full calibration samples**
    - Export `diag_full__*` and `diag_top10_*` CSVs.
    - Aggregate with `summarize_diagnostics()` to study tails and correlations.

2. **Benchmark subsets vs. full parallel runs**
    - Quantify the gain observed when splitting into smaller chunks (cache + spawn effects).

3. **Add leverage-outlier generator** to reproduce re-fit behaviour in synthetic benchmarks.

4. **Consider optimization paths**
    - Cap `max_refits` / early-stop criterion.
    - Introduce `make_parallel_fitFast` minimal version for groups O(10).

5. **Documentation**
    - Update `groupby_regression.md` “Performance & Benchmarking” section with diagnostic summary example and reference to top-violator CSVs.

---

**Last updated:** Oct 23 2025


