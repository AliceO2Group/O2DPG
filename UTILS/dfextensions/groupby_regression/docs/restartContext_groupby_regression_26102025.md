Perfect — here’s the **`restartContext.md`** prepared for your new phase of work.
It summarizes the current tagged baseline (`v2.0.0`) and defines the next milestone (sliding window + non-linear extensions).
It follows the same format used in previous phases.

---

# restartContext.md

**Project:** GroupBy Regression – Sliding Window and Non-Linear Extensions
**Date:** 2025-10-27
**Stage:** Phase 7 — New Features after v2.0.0 Tag

---

## 🧩 Project Status

The **GroupBy Regression v2.0.0** release has been **successfully tagged** and marks the completion of the optimization and documentation phase.

**Repository baseline:**

* Version: `v2.0.0`
* Commit: *[latest commit before tag]*
* Tag message: *“GroupBy Regression v2.0 — optimized engines + full docs”*
* All tests (41 total) passing on macOS 14.5 / Python 3.9 / Numba 0.59+.
* Benchmarks confirmed:

    * v4 (Numba JIT) = 75–200× speedup vs. robust baseline.
    * v2/v3 ≈ 85× speedup, stable.
* Documentation: finalized README + benchmark figures integrated.

---

## ✅ Completed Work (v2.0.0 baseline)

### Core Engines

| Engine     | Description                | Status             |
| :--------- | :------------------------- | :----------------- |
| **Robust** | Production-proven baseline | ✅ Stable           |
| **v2**     | Process-based (loky)       | ✅ Validated        |
| **v3**     | Thread-based (shared mem)  | ✅ Validated        |
| **v4**     | Numba JIT parallel kernel  | ✅ Production-ready |

### Quality Assurance

* Type-hint cleanup (`Optional[List[str]] = None`)
* Safe parameter defaults (`median_columns=None`)
* Verified JIT warm-up snippets and diagnostics flags (`diag`, `diag_prefix`)
* Updated documentation for `n_jobs` vs. Numba threading
* Added sed/macOS/Linux safety blocks, pip install guidance, and BLAS thread caveats

### Deliverables

* 📘 **README.md:** complete, validated, reproducible examples
* 📊 **Benchmarks:** `benchmarks/bench_out/` contains reference performance results
* 🧪 **Tests:** 41/41 pass (`pytest -v`)
* 🏷️ **Tag:** `v2.0.0` pushed to main

---

## 🧭 Current Focus — Phase 7 Development

### New Workstreams

| Feature                       | Goal                                                                                                                        | Collaborator    | Status         |
| :---------------------------- | :-------------------------------------------------------------------------------------------------------------------------- | :-------------- | :------------- |
| **Sliding Window Regression** | Implement per-group temporal/windowed regression with overlapping intervals (`window_column`, `window_size`, `window_step`) | Claude          | 🧩 In progress |
| **Non-Linear Fits**           | Polynomial / custom λ-model support (prototype API ready)                                                                   | TBD             | ⏳ Next         |
| **Real Use Case Integration** | Apply sliding window to actual TPC calibration or distortion drift dataset                                                  | Marian / Claude | Planned        |

### Design Targets

* API: `make_sliding_window_fit(df, gb_columns, fit_columns, linear_columns, window_column, window_size, window_step, ...)`
* Must reuse existing GroupBy Regressor infrastructure (no code duplication).
* Internal batching via v3/v4 backend; memory reuse emphasized.
* Output: one row per (group × window) with aggregated diagnostics.
* Expected performance ≥ 0.8× v4 per group baseline.
* Include minimal test suite + benchmark scenario (“window scaling test”).

---

## 🔬 Planned Validation

1. **Unit tests:** verify overlapping windows, edge groups, NaN handling.
2. **Benchmark:** scaling with varying window size and step.
3. **Cross-validation:** confirm equivalence to v4 on full window overlap.
4. **Documentation:** extend README with new “Sliding Window Regression” section.

---

## 📅 Next Milestones

| Step | Deliverable                                                  | ETA            |
| :--- | :----------------------------------------------------------- | :------------- |
| M7.1 | Sliding Window prototype (`make_sliding_window_fit`) + tests | early Nov 2025 |
| M7.2 | Add benchmark + plots                                        | mid Nov 2025   |
| M7.3 | Non-linear fit prototype (`make_nonlinear_fit`)              | late Nov 2025  |
| M7.4 | Combined v2.1 documentation + tag                            | Dec 2025       |

---

## 🧾 Context Summary

* **Baseline `v2.0.0` is frozen and validated.**
* Work continues on **Phase 7** focusing on advanced regression modes.
* The next tag will introduce `make_sliding_window_fit` and optionally `make_nonlinear_fit`, both fully integrated into the existing API and benchmark harness.

---

**Next Tag:** `v2.1.0`
**Branch:** `feature/sliding-window`
**Maintainer:** Marian Ivanov (GSI / Heidelberg / CERN ALICE TPC)

---
