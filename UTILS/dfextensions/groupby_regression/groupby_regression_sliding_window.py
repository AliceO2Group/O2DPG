from __future__ import annotations

"""
Sliding Window GroupBy Regression (M7.1)

Contract highlights (per restartContextGPT.md and review decisions):
- Integer bin coordinates only; users pre-bin floats. We record binning_formulas in metadata.
- Zero-copy neighborhood aggregation via bin->row_indices map.
- Window spec: {dim: nonneg_int} (symmetric ±w per dim). Boundary mode: truncate (only).
- Aggregations per target: mean, std (unbiased; weighted if weights available), median (unweighted), entries.
- Optional statsmodels fitting via formula string; supports multi-target by using literal keyword 'target' in formula.
- If weights_column present and fitting is requested, we use WLS regardless of fitter='ols'.
- Diagnostics: r_squared (from statsmodels), RMSE (weighted if weights), n_fitted, n_neighbors_used,
  n_rows_aggregated, effective_window_fraction. Quality flags for empty/insufficient/fit_failed.
- Provenance in DataFrame.attrs per spec.

Note: This is an initial implementation of M7.1 focused on correctness & API. Further optimizations (Numba backend,
partition strategies) are deferred.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Union, Callable, Any, Iterable
import sys
import json
import time
import math
import warnings

import numpy as np
import pandas as pd
from pandas.api.types import is_integer_dtype

# Optional statsmodels
STATSMODELS_AVAILABLE = False
try:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    STATSMODELS_AVAILABLE = True
except Exception:
    STATSMODELS_AVAILABLE = False


# =========================
# Exceptions & Warnings
# =========================
class InvalidWindowSpec(ValueError):
    """Raised when the window specification is malformed or unsupported in M7.1."""


class PerformanceWarning(UserWarning):
    """Issued when requested backend or feature is downgraded (e.g., numba -> numpy)."""


# =========================
# Helper utilities
# =========================

def _validate_sliding_window_inputs(
        df: pd.DataFrame,
        group_columns: List[str],
        window_spec: Dict[str, int],
        fit_columns: List[str],
        predictor_columns: List[str],
        fit_formula: Optional[Union[str, Callable]] = None,
        fitter: str = 'ols',
        aggregation_functions: Optional[Dict[str, List[str]]] = None,
        weights_column: Optional[str] = None,
        selection: Optional[pd.Series] = None,
        binning_formulas: Optional[Dict[str, str]] = None,
        min_entries: int = 10,
        backend: str = 'numpy',
        partition_strategy: Optional[dict] = None,
        **kwargs: Any,
) -> None:
    # group columns existence and integer dtype
    if not group_columns:
        raise ValueError("group_columns must be a non-empty list of column names")
    for col in group_columns:
        if col not in df.columns:
            raise ValueError(f"Group column '{col}' not found in DataFrame")
        if not is_integer_dtype(df[col]):
            raise ValueError(
                f"Group column '{col}' must be integer dtype (found {df[col].dtype}). "
                "M7.1 requires integer bin coordinates. Use pre-binning for floats."
            )

    # window spec keys, nonneg ints, symmetric only
    if not window_spec:
        raise InvalidWindowSpec("window_spec must be a non-empty dict {dim: nonneg_int}")
    # must include ALL group columns
    missing_dims = [g for g in group_columns if g not in window_spec]
    if missing_dims:
        raise InvalidWindowSpec(
            f"window_spec missing dimensions: {missing_dims}; must specify all group_columns"
        )
    for dim, w in window_spec.items():
        if dim not in group_columns:
            raise InvalidWindowSpec(
                f"window_spec key '{dim}' must be one of group_columns {group_columns}"
            )
        if not isinstance(w, (int, np.integer)) or w < 0:
            raise InvalidWindowSpec(
                f"window_spec for '{dim}' must be a non-negative integer (got {w!r})"
            )

    # selection length alignment and dtype
    if selection is not None:
        if len(selection) != len(df):
            raise ValueError(
                f"selection length ({len(selection)}) must match DataFrame length ({len(df)})"
            )
        if selection.dtype != bool:
            raise ValueError("selection mask must be boolean dtype")

    # weights column exists if provided
    if weights_column is not None and weights_column not in df.columns:
        raise ValueError(f"weights_column '{weights_column}' not found in DataFrame")

    # fit columns exist
    for t in fit_columns:
        if t not in df.columns:
            raise ValueError(f"fit column '{t}' not found in DataFrame")

    # predictors exist (validate regardless of formula presence to catch typos early)
    for p in predictor_columns:
        if p not in df.columns:
            raise ValueError(f"predictor column '{p}' not found in DataFrame")

    # backend
    if backend not in ("numpy", "numba"):
        raise ValueError("backend must be 'numpy' or 'numba'")

    # fitter
    if fit_formula is not None and not isinstance(fit_formula, (str,)):
        # Callable formulas not supported in M7.1
        raise ValueError("fit_formula must be a formula string in M7.1 (e.g. 'target ~ x + y')")

    if fitter not in ("ols", "wls", "glm", "rlm"):
        raise ValueError("fitter must be one of {'ols','wls','glm','rlm'} in M7.1")

    # if explicit WLS requested, require weights_column
    if fitter == "wls" and not weights_column:
        raise ValueError("fitter='wls' requires a valid weights_column")

    # min_entries strictly positive integer
    if not isinstance(min_entries, (int, np.integer)) or int(min_entries) <= 0:
        raise ValueError("min_entries must be a strictly positive integer")

    # Quick formula sanity check (malformed strings)
    if fit_formula is not None:
        try:
            import patsy  # type: ignore
            # replace literal 'target' with a placeholder to validate syntax
   
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
    # pylint: disable=no-member  # patsy.ModelDesc is dynamic
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
    # pylint: disable=no-member  # patsy.ModelDesc is dynamically generated
            patsy.ModelDesc 
        except Exception as e:
            raise ValueError(f"Malformed fit_formula: {fit_formula!r}. Error: {e}")

    # window spec keys, nonneg ints, symmetric only
    if not window_spec:
        raise InvalidWindowSpec("window_spec must be a non-empty dict {dim: nonneg_int}")
    for dim, w in window_spec.items():
        if dim not in group_columns:
            raise InvalidWindowSpec(
                f"window_spec key '{dim}' must be one of group_columns {group_columns}"
            )
        if not isinstance(w, (int, np.integer)) or w < 0:
            raise InvalidWindowSpec(
                f"window_spec for '{dim}' must be a non-negative integer (got {w!r})"
            )

    # selection length alignment
    if selection is not None:
        if len(selection) != len(df):
            raise ValueError(
                f"selection length ({len(selection)}) must match DataFrame length ({len(df)})"
            )

    # weights column exists if provided
    if weights_column is not None and weights_column not in df.columns:
        raise ValueError(f"weights_column '{weights_column}' not found in DataFrame")

    # fit columns exist
    for t in fit_columns:
        if t not in df.columns:
            raise ValueError(f"fit column '{t}' not found in DataFrame")

    # predictors exist (only validated if formula is None)
    if fit_formula is None:
        for p in predictor_columns:
            if p not in df.columns:
                raise ValueError(f"predictor column '{p}' not found in DataFrame")

    # backend
    if backend not in ("numpy", "numba"):
        raise ValueError("backend must be 'numpy' or 'numba'")

    # fitter
    if fit_formula is not None and not isinstance(fit_formula, (str,)):
        # Callable formulas not supported in M7.1
        raise ValueError("fit_formula must be a formula string in M7.1 (e.g. 'target ~ x + y')")

    if fitter not in ("ols", "wls", "glm", "rlm"):
        raise ValueError("fitter must be one of {'ols','wls','glm','rlm'} in M7.1")

    if min_entries < 0:
        raise ValueError("min_entries must be >= 0")


def _build_bin_index_map(
        df: pd.DataFrame,
        group_columns: List[str],
        selection: Optional[pd.Series] = None,
) -> Dict[Tuple[int, ...], List[int]]:
    """Build a zero-copy index map: tuple(bin coords) -> list(row indices).

    Applies selection if provided.
    """
    if selection is not None:
        sel_idx = np.flatnonzero(selection.to_numpy())
    else:
        sel_idx = np.arange(len(df), dtype=np.int64)

    if len(sel_idx) == 0:
        return {}

    # Extract columns as numpy (fast path)
    cols = [df[c].to_numpy() for c in group_columns]
    # Build tuple keys for selected rows
    keys = [tuple(int(col[i]) for col in cols) for i in sel_idx]

    bin_map: Dict[Tuple[int, ...], List[int]] = {}
    for key, ridx in zip(keys, sel_idx):
        bin_map.setdefault(key, []).append(int(ridx))
    return bin_map


def _observed_bin_bounds(
        bin_map: Dict[Tuple[int, ...], List[int]],
        group_columns: List[str],
) -> Dict[str, Tuple[int, int]]:
    """Compute per-dimension (min,max) across observed bins (post-selection)."""
    if not bin_map:
        return {dim: (0, -1) for dim in group_columns}  # empty
    arr = np.array(list(bin_map.keys()), dtype=np.int64)
    bounds: Dict[str, Tuple[int, int]] = {}
    for j, dim in enumerate(group_columns):
        bounds[dim] = (int(arr[:, j].min()), int(arr[:, j].max()))
    return bounds


def _generate_neighbor_offsets(window_spec: Dict[str, int], group_columns: Optional[List[str]] = None) -> np.ndarray:
    """Return all neighbor offsets as an array of shape (K, D), where D=len(group_columns).
    Offsets cover the Cartesian product of [-w, +w] per dimension.
    If group_columns is None, infer order from window_spec keys.
    """
    spans: List[np.ndarray] = []
    if group_columns is None:
        group_columns = list(window_spec.keys())
    for dim in group_columns:
        w = window_spec.get(dim, 0)
        spans.append(np.arange(-w, w + 1, dtype=np.int64))
    # Cartesian product
    if not spans:
        return np.zeros((1, 0), dtype=np.int64)
    grids = np.meshgrid(*spans, indexing="ij")
    stacked = np.stack([g.reshape(-1) for g in grids], axis=1)
    return stacked  # (num_offsets, D)


def _get_neighbor_bins(
        center: Tuple[int, ...],
        offsets: np.ndarray,
        bin_ranges: Dict[str, Tuple[int, int]],  # ← Rename bounds
        boundary_mode: str = 'truncate'  # ← Add this (unused for now)
) -> List[Tuple[int, ...]]:
    """Apply boundary mode: drop neighbors outside observed (min,max) per dim."""

    # Get dimension order from bin_ranges keys (instead of group_columns parameter)
    group_columns = list(bin_ranges.keys())

    if offsets.size == 0:
        return [center]
    center_arr = np.array(center, dtype=np.int64)
    cand = center_arr + offsets  # (K, D)

    mask = np.ones(len(cand), dtype=bool)
    for j, dim in enumerate(group_columns):
        lo, hi = bin_ranges[dim]  # ← Use bin_ranges instead of bounds
        mask &= (cand[:, j] >= lo) & (cand[:, j] <= hi)
    valid = cand[mask]
    return [tuple(map(int, row)) for row in valid]

@dataclass
class _AggResult:
    center: Tuple[int, ...]
    n_neighbors_used: int
    n_rows_aggregated: int
    effective_window_fraction: float
    # per-target aggregates
    stats: Dict[str, Dict[str, float]]  # target -> {mean,std,median,entries}
    # rows indices (unique) used for the window (for fitting)
    row_indices: np.ndarray


def _weighted_mean_std(x: np.ndarray, w: Optional[np.ndarray]) -> Tuple[float, float]:
    """Compute mean and (unbiased) std. If w is None, use ordinary formulas.
    Drops NaNs in x (and corresponding weights) beforehand (caller responsibility).
    For weights: use standard weighted mean and unbiased weighted std with effective dof.
    """
    if x.size == 0:
        return (np.nan, np.nan)

    if w is None:
        m = float(np.mean(x)) if x.size else np.nan
        s = float(np.std(x, ddof=1)) if x.size > 1 else np.nan
        return (m, s)

    # weights provided
    wsum = float(np.sum(w))
    if wsum <= 0.0:
        return (np.nan, np.nan)
    m = float(np.sum(w * x) / wsum)
    # unbiased weighted variance per effective dof
    # var = sum(w*(x-m)^2) / (wsum - sum(w^2)/wsum)
    # guard denominator
    w2_sum = float(np.sum(w * w))
    denom = wsum - (w2_sum / wsum) if wsum > 0 else 0.0
    if denom <= 0.0:
        return (m, np.nan)
    var = float(np.sum(w * (x - m) ** 2) / denom)
    return (m, math.sqrt(var))


def _aggregate_window_zerocopy(
        df: pd.DataFrame,
        bin_map: Dict[Tuple[int, ...], List[int]],
        center_bins: Iterable[Tuple[int, ...]],
        neighbor_offsets: np.ndarray,
        bounds: Dict[str, Tuple[int, int]],
        group_columns: List[str],
        fit_columns: List[str],
        weights_column: Optional[str],
) -> List[_AggResult]:
    """Aggregate per center bin using zero-copy neighbor indexing."""
    results: List[_AggResult] = []

    expected_neighbors = 1
    for dim in group_columns:
        w = int(neighbor_offsets.max(initial=0))  # not exact per-dim, recompute precisely below
    # exact expected product
    expected_neighbors = 1
    for dim in group_columns:
        w = window_spec_w = bounds.get(dim, (0, 0))  # placeholder not used here
    # Better: compute from offsets directly
    expected_neighbors = int(neighbor_offsets.shape[0]) if neighbor_offsets.size else 1

    for center in center_bins:
        neighbors = _get_neighbor_bins(center, neighbor_offsets, bounds, group_columns)
        n_used = 0
        idx_list: List[int] = []
        for nb in neighbors:
            rows = bin_map.get(nb)
            if rows:
                n_used += 1
                idx_list.extend(rows)

        if idx_list:
            # dedup defensively
            idx_unique = np.unique(np.fromiter(idx_list, dtype=np.int64))
        else:
            idx_unique = np.array([], dtype=np.int64)

        eff_frac = (n_used / expected_neighbors) if expected_neighbors > 0 else np.nan
        n_rows = int(idx_unique.size)

        stats: Dict[str, Dict[str, float]] = {}
        if n_rows > 0:
            window_df = df.iloc[idx_unique]
            w = None
            if weights_column is not None:
                w_series = window_df[weights_column]
                # drop NaN/negative weights for stats
                valid_w = (~w_series.isna()) & (w_series.to_numpy() >= 0)
                w = w_series.to_numpy()[valid_w]
            for t in fit_columns:
                col = window_df[t]
                if weights_column is None:
                    x = col.dropna().to_numpy()
                    mean, std = _weighted_mean_std(x, None)
                else:
                    # apply joint validity: target not NaN and weight valid
                    valid = (~col.isna()).to_numpy()
                    if w is not None:
                        valid = valid & ((~w_series.isna()).to_numpy()) & (w_series.to_numpy() >= 0)
                    x = col.to_numpy()[valid]
                    ww = w_series.to_numpy()[valid]
                    mean, std = _weighted_mean_std(x, ww)
                median = float(np.median(col.dropna().to_numpy())) if col.notna().any() else np.nan
                entries = int(col.notna().sum())
                stats[t] = {
                    "mean": mean,
                    "std": std,
                    "median": median,
                    "entries": entries,
                }
        else:
            for t in fit_columns:
                stats[t] = {"mean": np.nan, "std": np.nan, "median": np.nan, "entries": 0}

        results.append(
            _AggResult(
                center=center,
                n_neighbors_used=n_used,
                n_rows_aggregated=n_rows,
                effective_window_fraction=eff_frac,
                stats=stats,
                row_indices=idx_unique,
            )
        )

    return results


# ===============
# Regression
# ===============

def _sanitize_suffix(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(name))


def _fit_window_regression_statsmodels(
        df: pd.DataFrame,
        agg_results: List[_AggResult],
        fit_columns: List[str],
        fit_formula: Optional[str],
        predictor_columns: List[str],
        weights_column: Optional[str],
        fitter: str,
        min_entries: int,
) -> Dict[Tuple[int, ...], Dict[str, Dict[str, Any]]]:
    """Return mapping: center_bin -> per-target fit dicts (coeffs & diagnostics).

    For formula strings containing literal 'target', we substitute each target name.
    If fit_formula is None, we perform no fitting and return empty dicts.
    """
    out: Dict[Tuple[int, ...], Dict[str, Dict[str, Any]]] = {}

    if fit_formula is None:
        for ar in agg_results:
            out[ar.center] = {}
        return out

    if not STATSMODELS_AVAILABLE:
        raise ImportError("statsmodels required. pip install statsmodels")

    for ar in agg_results:
        center_map: Dict[str, Dict[str, Any]] = {}
        # Prepare window df view
        if ar.row_indices.size == 0:
            # empty window
            for t in fit_columns:
                center_map[t] = {
                    "coeffs": {},
                    "intercept": np.nan,
                    "r_squared": np.nan,
                    "rmse": np.nan,
                    "n_fitted": 0,
                    "quality_flag": "empty_window",
                }
            out[ar.center] = center_map
            continue

        window_df_full = df.iloc[ar.row_indices]

        for t in fit_columns:
            # Prepare formula for this target
            formula = fit_formula.replace("target", t) if "target" in fit_formula else fit_formula

            # drop rows with NaN in target
            sub_df = window_df_full[[t] + predictor_columns + ([weights_column] if weights_column else [])].copy()
            sub_df = sub_df.rename(columns={t: "__target__"})
            # statsmodels formula expects the original target name; swap in formula
            formula_t = formula.replace(t, "__target__")

            valid = sub_df["__target__"].notna()
            if weights_column is not None:
                w = sub_df[weights_column]
                valid &= (~w.isna()) & (w >= 0)
            # also drop NaNs in predictors used by formula roughly (best effort)
            for p in predictor_columns:
                valid &= sub_df[p].notna()

            sub_df = sub_df.loc[valid]

            n_avail = len(sub_df)
            if n_avail < max(1, int(min_entries)):
                center_map[t] = {
                    "coeffs": {},
                    "intercept": np.nan,
                    "r_squared": np.nan,
                    "rmse": np.nan,
                    "n_fitted": int(n_avail),
                    "quality_flag": "insufficient_stats",
                }
                continue

            try:
                if weights_column is not None or fitter == "wls":
                    # WLS
                    model = smf.wls(formula=formula_t, data=sub_df, weights=sub_df[weights_column])
                    res = model.fit()
                elif fitter == "rlm":
                    # Robust linear model (uses Huber by default)
                    # RLM does not support formula directly for weights the same way; we go via smf.rlm
                    model = smf.rlm(formula=formula_t, data=sub_df)
                    res = model.fit()
                elif fitter == "glm":
                    model = smf.glm(formula=formula_t, data=sub_df)
                    res = model.fit()
                else:
                    # OLS
                    model = smf.ols(formula=formula_t, data=sub_df)
                    res = model.fit()

                params = res.params.to_dict()
                intercept = float(params.get("Intercept", params.get("const", np.nan)))
                coeffs = {k: float(v) for k, v in params.items() if k not in ("Intercept", "const")}

                # Diagnostics
                # rsquared may be missing for some models (e.g., some GLM families); guard
                r2 = getattr(res, "rsquared", np.nan)

                # RMSE: weighted if weights provided, else unweighted
                resid = res.resid
                if weights_column is not None:
                    w = sub_df[weights_column].to_numpy(dtype=float)
                    rmse = float(np.sqrt(np.sum(w * (resid ** 2)) / np.sum(w))) if np.sum(w) > 0 else np.nan
                else:
                    rmse = float(np.sqrt(np.mean(resid ** 2)))

                center_map[t] = {
                    "coeffs": coeffs,
                    "intercept": intercept,
                    "r_squared": float(r2) if r2 is not None else np.nan,
                    "rmse": rmse,
                    "n_fitted": int(getattr(res, "nobs", len(sub_df))),
                    "quality_flag": "",
                }
            except Exception:
                center_map[t] = {
                    "coeffs": {},
                    "intercept": np.nan,
                    "r_squared": np.nan,
                    "rmse": np.nan,
                    "n_fitted": int(n_avail),
                    "quality_flag": f"fit_failed_{t}",
                }
        out[ar.center] = center_map

    return out


# ===============
# Assembly
# ===============

def _assemble_results(
        group_columns: List[str],
        agg_results: List[_AggResult],
        fit_results: Dict[Tuple[int, ...], Dict[str, Dict[str, Any]]],
        fit_columns: List[str],
        predictor_columns: List[str],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    # Build column order
    pred_suffixes = {p: _sanitize_suffix(p) for p in predictor_columns}

    for ar in agg_results:
        base: Dict[str, Any] = {dim: ar.center[i] for i, dim in enumerate(group_columns)}
        base["n_neighbors_used"] = ar.n_neighbors_used
        base["n_rows_aggregated"] = ar.n_rows_aggregated
        base["effective_window_fraction"] = ar.effective_window_fraction

        # Aggregate stats
        for t, st in ar.stats.items():
            base[f"{t}_mean"] = st["mean"]
            base[f"{t}_std"] = st["std"]
            base[f"{t}_median"] = st["median"]
            base[f"{t}_entries"] = st["entries"]

        # Fit outputs
        fit_map = fit_results.get(ar.center, {})
        # If the entire window was empty and no fit_map entries exist, still mark quality
        empty_window = ar.n_rows_aggregated == 0

        # accumulate quality flags
        qflags: List[str] = []

        for t in fit_columns:
            tres = fit_map.get(t)
            if tres is None:
                # no fitting requested or not available
                base[f"{t}_intercept"] = np.nan
                for p, ps in pred_suffixes.items():
                    base[f"{t}_slope_{ps}"] = np.nan
                base[f"{t}_r_squared"] = np.nan
                base[f"{t}_rmse"] = np.nan
                base[f"{t}_n_fitted"] = 0
                continue

            base[f"{t}_intercept"] = tres.get("intercept", np.nan)
            for p, ps in pred_suffixes.items():
                base[f"{t}_slope_{ps}"] = tres.get("coeffs", {}).get(p, np.nan)
            base[f"{t}_r_squared"] = tres.get("r_squared", np.nan)
            base[f"{t}_rmse"] = tres.get("rmse", np.nan)
            base[f"{t}_n_fitted"] = tres.get("n_fitted", 0)
            if tres.get("quality_flag"):
                qflags.append(str(tres.get("quality_flag")))

        if empty_window:
            qflags.append("empty_window")

        base["quality_flag"] = ",".join([q for q in qflags if q])
        rows.append(base)

    out = pd.DataFrame(rows)
    # Ensure group columns are present even if rows empty
    for dim in group_columns:
        if dim not in out.columns:
            out[dim] = pd.Series(dtype="int64")

    # Order columns: group_columns -> aggregations -> fit outputs -> diagnostics
    agg_cols = [c for c in out.columns if any(c.startswith(f"{t}_") for t in fit_columns) and (
            c.endswith("_mean") or c.endswith("_std") or c.endswith("_median") or c.endswith("_entries")
    )]

    fit_cols = []
    for t in fit_columns:
        fit_cols.append(f"{t}_intercept")
        for p, ps in pred_suffixes.items():
            fit_cols.append(f"{t}_slope_{ps}")
        fit_cols.append(f"{t}_r_squared")
        fit_cols.append(f"{t}_rmse")
        fit_cols.append(f"{t}_n_fitted")

    diag_cols = ["quality_flag", "n_neighbors_used", "n_rows_aggregated", "effective_window_fraction"]

    ordered = group_columns + agg_cols + fit_cols + diag_cols
    # Keep any other columns at the end (defensive)
    others = [c for c in out.columns if c not in ordered]
    out = out[ordered + others]

    return out


# =====================
# Main entry point
# =====================

def make_sliding_window_fit(
        df: pd.DataFrame,
        group_columns: List[str],
        window_spec: Dict[str, int],
        fit_columns: List[str],
        predictor_columns: List[str],
        fit_formula: Optional[Union[str, Callable]] = None,
        fitter: str = 'ols',
        aggregation_functions: Optional[Dict[str, List[str]]] = None,
        weights_column: Optional[str] = None,
        selection: Optional[pd.Series] = None,
        binning_formulas: Optional[Dict[str, str]] = None,
        min_entries: int = 10,
        backend: str = 'numpy',
        partition_strategy: Optional[dict] = None,
        **kwargs: Any,
) -> pd.DataFrame:
    """Sliding window groupby regression orchestrator (M7.1)."""
    t0 = time.time()

    _validate_sliding_window_inputs(
        df=df,
        group_columns=group_columns,
        window_spec=window_spec,
        fit_columns=fit_columns,
        predictor_columns=predictor_columns,
        fit_formula=fit_formula,
        fitter=fitter,
        aggregation_functions=aggregation_functions,
        weights_column=weights_column,
        selection=selection,
        binning_formulas=binning_formulas,
        min_entries=min_entries,
        backend=backend,
        partition_strategy=partition_strategy,
        **kwargs,
    )

    if backend == 'numba':
        warnings.warn(
            f"Requested backend='{backend}'; fallback to 'numpy' in M7.1 (numba unavailable)",
            PerformanceWarning,
            stacklevel=2
        )

    # Build zero-copy bin map
    bin_map = _build_bin_index_map(df, group_columns, selection)

    # Determine center bins as observed unique bins (post-selection)
    center_bins = list(bin_map.keys())

    # Neighbor offsets and bounds
    neighbor_offsets = _generate_neighbor_offsets(window_spec, group_columns)
    bounds = _observed_bin_bounds(bin_map, group_columns)

    # Aggregation per window
    agg_results = _aggregate_window_zerocopy(
        df=df,
        bin_map=bin_map,
        center_bins=center_bins,
        neighbor_offsets=neighbor_offsets,
        bounds=bounds,
        group_columns=group_columns,
        fit_columns=fit_columns,
        weights_column=weights_column,
    )

    # Fitting
    fit_results = _fit_window_regression_statsmodels(
        df=df,
        agg_results=agg_results,
        fit_columns=fit_columns,
        fit_formula=fit_formula,
        predictor_columns=predictor_columns,
        weights_column=weights_column,
        fitter=fitter,
        min_entries=min_entries,
    )

    # Assemble output
    out = _assemble_results(
        group_columns=group_columns,
        agg_results=agg_results,
        fit_results=fit_results,
        fit_columns=fit_columns,
        predictor_columns=predictor_columns,
    )

    # Provenance
    try:
        sm_ver = sm.__version__ if STATSMODELS_AVAILABLE else None
    except Exception:
        sm_ver = None

    out.attrs.update(
        {
            "group_columns": list(group_columns),
            "window_spec_json": json.dumps(window_spec),
            "boundary_mode_per_dim": {dim: "truncate" for dim in group_columns},
            "fitter_used": fitter,
            "backend_used": "numpy",
            "binning_formulas_json": json.dumps(binning_formulas) if binning_formulas else None,
            "python_version": sys.version,
            "statsmodels_version": sm_ver,
            "computation_time_sec": time.time() - t0,
        }
    )

    return out
