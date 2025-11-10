#!/usr/bin/env python3
# Annotate all test_* functions in tests/test_groupby_regression_sliding_window.py
# with concise 1–2 line Claude-style docstrings (only if missing).
import io, os, re, sys
from typing import Dict

PATH = "tests/test_groupby_regression_sliding_window.py"

DESCR: Dict[str, str] = {
    "test_sliding_window_basic_3d_verbose":
        "Basic 3D pipeline smoke-test: offsets, zero-copy aggregation, OLS fit, and attrs.",
    "test_sliding_window_aggregation_verbose":
        "Aggregation contract: mean/std/median/entries computed from zero-copy window.",
    "test_sliding_window_linear_fit_recover_slope":
        "Linear-fit sanity: recovers known slope(s) from synthetic trend within tolerance.",
    "test_empty_window_handling_no_crash":
        "Empty windows: return NaNs + quality flag, no exceptions.",
    "test_min_entries_enforcement_flag_or_drop":
        "min_entries threshold: bins below cut are flagged or skipped per contract.",
    "test_invalid_window_spec_rejected":
        "window_spec must include all dims; radii non-negative; unknown keys rejected.",
    "test_missing_columns_raise_valueerror":
        "Missing fit/predictor/weight columns raise ValueError with clear hint.",
    "test_float_bins_rejected_in_m71":
        "M7.1 requires integer bins: float-typed group columns are rejected with guidance.",
    "test_min_entries_must_be_positive_int":
        "min_entries must be a strictly positive integer; bad values raise ValueError.",
    "test_invalid_fit_formula_raises":
        "Malformed formula strings are caught early via patsy and raise ValueError.",
    "test_selection_mask_length_and_dtype":
        "Selection mask must be boolean and length-match df; else ValueError.",
    "test_wls_requires_weights_column":
        "fitter='wls' requires weights_column; missing weights raise ValueError.",
    "test_numpy_fallback_emits_performance_warning":
        "Requesting numba emits a PerformanceWarning and falls back to numpy.",
    "test_single_bin_dataset_ok":
        "A single observed bin is handled gracefully (aggregation/fit works).",
    "test_all_bins_below_threshold":
        "All bins below min_entries: outputs NaN/flagged per bin without crashing.",
    "test_boundary_bins_truncation_counts":
        "Neighbor counts truncate at edges (corners/edges < interior).",
    "test_multi_target_fit_output_schema":
        "Multiple targets produce complete, disambiguated output columns.",
    "test_weighted_vs_unweighted_coefficients_differ":
        "Non-uniform weights yield WLS coefficients/diagnostics distinct from OLS.",
    "test_selection_mask_filters_pre_windowing":
        "Selection is applied before window assembly, affecting stats and fits.",
    "test_metadata_presence_in_attrs":
        "Provenance stored in .attrs: window_spec, fitter/backend, versions, time.",
    "test_backend_numba_request_warns_numpy_fallback":
        "Explicit numba backend request warns and falls back to numpy.",
    "test_statsmodels_fitters_basic":
        "statsmodels integration: OLS/WLS/GLM/RLM produce sane diagnostics.",
    "test_statsmodels_formula_rich_syntax_relaxed":
        "Richer formula syntax (e.g., interactions) accepted by patsy/statsmodels.",
    "test_statsmodels_not_available_doc_behavior":
        "If statsmodels is unavailable and fit is requested, ImportError with guidance.",
    "test_window_size_zero_parity_with_v4_relaxed":
        "Window size 0 (center-only) relaxed parity check vs v4 (skipped if v4 missing).",
    "test__build_bin_index_map_contract":
        "Zero-copy bin map: each row appears exactly once under its integer-bin key.",
    "test__generate_offsets_and_get_neighbors_truncate_contract":
        "Offsets grid size and truncate-mode neighbor enumeration are consistent.",
    "test_realistic_smoke_normalised_residuals_gate":
        "Realistic smoke: normalized residual gate behaves sensibly on synthetic-ish data.",
}

# Some tests are parametrized; they appear multiple times at runtime (e.g., [ols]/[wls]).
# We annotate the single base function definition only:
PARAM_BASES = {
    "test_min_entries_must_be_positive_int": DESCR["test_min_entries_must_be_positive_int"],
    "test_statsmodels_fitters_basic": DESCR["test_statsmodels_fitters_basic"],
}

def main():
    if not os.path.exists(PATH):
        print(f"ERR: {PATH} not found", file=sys.stderr)
        sys.exit(1)

    with io.open(PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    changed = 0
    while i < len(lines):
        line = lines[i]

        # Find a def line: allow decorators above (we'll detect from 'def test_')
        m = re.match(r"^\s*def\s+(test[^\s(]+)\s*\(", line)
        if not m:
            i += 1
            continue

        name = m.group(1)
        base = name.split("[", 1)[0]  # in case of unusual names

        desc = DESCR.get(base) or DESCR.get(name) or PARAM_BASES.get(base)
        if not desc:
            i += 1
            continue

        # Determine indentation (spaces before 'def')
        indent = re.match(r"^(\s*)", line).group(1)

        # Check next non-empty line for an existing docstring
        j = i + 1
        # Skip possible blank lines
        while j < len(lines) and lines[j].strip() == "":
            j += 1

        has_doc = False
        if j < len(lines):
            nxt = lines[j].lstrip()
            if nxt.startswith('"""') or nxt.startswith("'''"):
                has_doc = True

        if not has_doc:
            # Insert docstring one line after def (keeping indentation)
            doc = f'{indent}    """{desc}"""' + "\n"
            lines.insert(i + 1, doc)
            changed += 1
            i += 1  # skip past inserted docstring

        i += 1

    if changed == 0:
        print("No changes made (all tests already annotated or names not found).")
    else:
        with io.open(PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"Annotated {changed} test functions in {PATH}.")

if __name__ == "__main__":
    main()

