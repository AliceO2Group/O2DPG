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

---

### Commit message

```
docs(restartContext): update with 5k/5 default, 30% outliers, and leverage-outlier plan

- Record new cross-platform results (Mac vs Linux) and observation that response-only outliers do not slow runtime
- Add action plan: leverage-outlier generator + refit counters + multi-target cost check
- Keep PR target; align benchmarks and docs with 5k/5 default
```
