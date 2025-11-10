"""
Optimized GroupByRegressor with improved parallelization for real-world data.

Key improvements:
1. Array-based data passing (reduce serialization overhead)
2. Smart batching for small groups
3. Memory-efficient group processing
"""

import numpy as np
import pandas as pd
import logging
from typing import Union, List, Tuple, Callable, Optional
from joblib import Parallel, delayed
from sklearn.linear_model import LinearRegression, HuberRegressor


def process_group_array_based(
    key: tuple,
    indices: np.ndarray,
    X_all: np.ndarray,
    y_all: np.ndarray,
    w_all: np.ndarray,
    gb_columns: List[str],
    target_idx: int,
    predictor_indices: List[int],
    min_stat: int,
    sigmaCut: float,
    fitter: Union[str, Callable],
    max_refits: int = 10,
) -> dict:
    """
    Process a single group using pre-extracted arrays.

    This avoids DataFrame slicing overhead by working directly with NumPy arrays.

    Args:
        key: Group key tuple
        indices: Row indices for this group (into X_all, y_all, w_all)
        X_all: Full predictor array [n_total, n_predictors]
        y_all: Full target array [n_total, n_targets]
        w_all: Full weight array [n_total]
        gb_columns: Group-by column names
        target_idx: Which target column to fit
        predictor_indices: Which predictor columns to use
        min_stat: Minimum rows required
        sigmaCut: Outlier threshold (MAD units)
        fitter: "ols", "robust", or callable
        max_refits: Maximum robust iterations

    Returns:
        Dictionary with fit results for this group
    """
    # Handle single vs multiple group columns
    if isinstance(key, tuple):
        group_dict = dict(zip(gb_columns, key))
    else:
        group_dict = {gb_columns[0]: key}

    if len(indices) < min_stat:
        return group_dict  # Will be filled with NaN by caller

    try:
        # Extract data for this group - single operation, contiguous memory
        X = X_all[indices][:, predictor_indices]
        y = y_all[indices]  # y_all is 1D for single target
        w = w_all[indices]

        # Remove any remaining NaN rows
        valid_mask = np.isfinite(X).all(axis=1) & np.isfinite(y) & np.isfinite(w)
        if valid_mask.sum() < min_stat:
            return group_dict

        X = X[valid_mask]
        y = y[valid_mask]
        w = w[valid_mask]

        # Select fitter
        if callable(fitter):
            model = fitter()
        elif fitter == "ols":
            model = LinearRegression()
        elif fitter == "robust":
            model = HuberRegressor(tol=1e-4)
        else:
            model = LinearRegression()

        # Robust fitting with outlier rejection
        mask = np.ones(len(y), dtype=bool)
        n_refits = 0

        for iteration in range(max_refits):
            if mask.sum() < min_stat:
                break

            X_fit = X[mask]
            y_fit = y[mask]
            w_fit = w[mask]

            # Fit with explicit error handling
            try:
                model.fit(X_fit, y_fit, sample_weight=w_fit)
            except LinAlgError as e:
                # Singular matrix / collinearity
                logging.warning(f"LinAlgError in fit for group {key}: {e}")
                return group_dict  # Return NaNs gracefully
            except Exception as e:
                # Catch any other fitting errors
                logging.warning(f"Unexpected error in fit for group {key}: {e}")
                return group_dict  # Return NaNs gracefully

            # Check for convergence
            if iteration == 0 or sigmaCut > 50:  # No outlier rejection
                break

            # Compute residuals and MAD
            pred = model.predict(X)
            residuals = y - pred
            mad = np.median(np.abs(residuals - np.median(residuals)))

            if mad < 1e-9:  # Perfect fit
                break

            # Update mask
            new_mask = np.abs(residuals) < sigmaCut * mad * 1.4826
            if np.array_equal(mask, new_mask):  # Converged
                break

            mask = new_mask
            n_refits += 1

        # Store results
        group_dict['coefficients'] = model.coef_
        group_dict['intercept'] = model.intercept_
        group_dict['n_refits'] = n_refits
        group_dict['n_used'] = mask.sum()
        group_dict['frac_rejected'] = 1.0 - (mask.sum() / len(y))

        # Compute residual statistics
        pred_final = model.predict(X[mask])
        res_final = y[mask] - pred_final
        group_dict['rms'] = np.sqrt(np.mean(res_final**2))
        group_dict['mad'] = np.median(np.abs(res_final - np.median(res_final))) * 1.4826

    except Exception as e:
        logging.warning(f"Fit failed for group {key}: {e}")

    return group_dict


def process_batch_of_groups(
    batch: List[Tuple[tuple, np.ndarray]],
    X_all: np.ndarray,
    y_all: np.ndarray,
    w_all: np.ndarray,
    gb_columns: List[str],
    target_idx: int,
    predictor_indices: List[int],
    min_stat: int,
    sigmaCut: float,
    fitter: Union[str, Callable],
    max_refits: int,
) -> List[dict]:
    """
    Process multiple small groups in a single worker task.

    This reduces process spawn overhead for datasets with many small groups.
    """
    results = []
    for key, indices in batch:
        result = process_group_array_based(
            key, indices, X_all, y_all, w_all, gb_columns,
            target_idx, predictor_indices, min_stat, sigmaCut, fitter, max_refits
        )
        results.append(result)
    return results


class GroupByRegressorOptimized:
    """
    Optimized version of GroupByRegressor with improved parallelization.
    """

    @staticmethod
    def make_parallel_fit_optimized(
            df: pd.DataFrame,
            gb_columns: List[str],
            fit_columns: List[str],
            linear_columns: List[str],
            median_columns: List[str],
            weights: str,
            suffix: str,
            selection: pd.Series,
            addPrediction: bool = False,
            cast_dtype: Union[str, None] = None,
            n_jobs: int = 1,
            min_stat: Union[int, List[int]] = 10,
            sigmaCut: float = 5.0,
            fitter: Union[str, Callable] = "ols",
            batch_size: Union[str, int] = "auto",
            batch_strategy: str = "auto",
            max_refits: int = 10,
            small_group_threshold: int = 30,
            min_batch_size: int = 10,
            backend: str = 'loky',
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Optimized parallel fitting with array-based data passing and smart batching.
        """
        logger = logging.getLogger(__name__)
        if isinstance(min_stat, list):
            min_stat = min(min_stat) if len(min_stat) > 0 else 1

        # Apply selection
        df_selected = df[selection].copy()
        if df_selected.empty:
            return df.assign(**{f"{col}{suffix}": np.nan for col in fit_columns}), \
                pd.DataFrame(columns=gb_columns)

        # Prepare arrays (array-based path)
        y_matrix = df_selected[fit_columns].to_numpy()
        X_all = df_selected[linear_columns].to_numpy()
        w_all = df_selected[weights].to_numpy() if isinstance(weights, str) else np.ones(len(df_selected))

        # Group indices (array-based)
        grouped = df_selected.groupby(gb_columns, sort=False, observed=True)
        groups_items = list(grouped.groups.items())

        # Choose batching strategy
        def choose_strategy():
            if batch_strategy in ("no_batching", "size_bucketing"):
                return batch_strategy
            # auto
            sizes = np.array([len(idxs) for _, idxs in groups_items])
            if (sizes <= small_group_threshold).mean() > 0.7 and len(groups_items) > 50:
                return "size_bucketing"
            return "no_batching"

        strategy = choose_strategy()

        # Pre-build y index per target
        target_indices = {t: i for i, t in enumerate(fit_columns)}

        target_results: List[Tuple[str, List[dict]]] = []

        for target_col in fit_columns:
            target_idx = target_indices[target_col]

            # batching
            if strategy == "size_bucketing":
                small = [(k, idxs) for k, idxs in groups_items if len(idxs) < small_group_threshold]
                large = [(k, idxs) for k, idxs in groups_items if len(idxs) >= small_group_threshold]

                # Bucket small groups
                small_sorted = sorted(small, key=lambda kv: len(kv[1]), reverse=True)
                buckets: List[List[Tuple[tuple, np.ndarray]]] = []
                current: List[Tuple[tuple, np.ndarray]] = []
                current_size = 0
                for k, idxs in small_sorted:
                    current.append((k, idxs))
                    current_size += len(idxs)
                    if current_size >= max(min_batch_size, small_group_threshold):
                        buckets.append(current)
                        current = []
                        current_size = 0
                if current:
                    buckets.append(current)

                def process_bucket(bucket):
                    out = []
                    for key, idxs in bucket:
                        out.append(process_group_array_based(
                            key, idxs, X_all, y_matrix[:, target_idx], w_all,
                            gb_columns, target_idx, list(range(len(linear_columns))),
                            min_stat, sigmaCut, fitter, max_refits
                        ))
                    return out

                results_small = Parallel(n_jobs=n_jobs, backend=backend)(
                    delayed(process_bucket)(b) for b in buckets
                )
                results_small = [r for sub in results_small for r in sub]

                # Large groups individually
                results_large = Parallel(n_jobs=n_jobs, batch_size=batch_size, backend=backend)(
                    delayed(process_group_array_based)(
                        key, idxs, X_all, y_matrix[:, target_idx], w_all,
                        gb_columns, target_idx, list(range(len(linear_columns))),
                        min_stat, sigmaCut, fitter, max_refits
                    )
                    for key, idxs in large
                )

                results = results_small + results_large

            else:
                # Original approach: each group is a task
                results = Parallel(n_jobs=n_jobs, batch_size=batch_size, backend=backend)(
                    delayed(process_group_array_based)(
                        key, idxs, X_all, y_matrix[:, target_idx], w_all,
                        gb_columns, target_idx, list(range(len(linear_columns))),
                        min_stat, sigmaCut, fitter, max_refits
                    )
                    for key, idxs in groups_items
                )

            target_results.append((target_col, results))

        # Construct dfGB: merge target results horizontally (one row per group)
        dfGB = None
        for t_idx, (target_col, results) in enumerate(target_results):
            df_t = pd.DataFrame(results)
            if df_t.empty:
                continue
            # Expand coefficients into per-predictor columns for this target
            # Expand coefficients into per-predictor columns for this target
            if 'coefficients' in df_t.columns:
                for idx, pred_col in enumerate(linear_columns):
                    colname = f"{target_col}_slope_{pred_col}"
                    df_t[colname] = [
                        (arr[idx] if isinstance(arr, (np.ndarray, list, tuple)) and len(arr) > idx else np.nan)
                        for arr in df_t['coefficients']
                    ]
            if 'intercept' in df_t.columns:
                df_t[f"{target_col}_intercept"] = df_t['intercept']
            if 'rms' in df_t.columns:
                df_t[f"{target_col}_rms"] = df_t['rms']
            if 'mad' in df_t.columns:
                df_t[f"{target_col}_mad"] = df_t['mad']

            # Drop temp columns; for additional targets keep only gb keys + target-specific cols
            drop_cols = ['coefficients', 'intercept', 'rms', 'mad']
            if t_idx > 0:
                keep_cols = set(gb_columns) | {c for c in df_t.columns if c.startswith(f"{target_col}_")}
                df_t = df_t[[c for c in df_t.columns if c in keep_cols]]
            df_t = df_t.drop(columns=[c for c in drop_cols if c in df_t.columns], errors='ignore')

            if dfGB is None:
                dfGB = df_t
            else:
                dfGB = dfGB.merge(df_t, on=gb_columns, how='left')

        if dfGB is None:
            dfGB = pd.DataFrame(columns=gb_columns)

        # Add medians (per-group)
        if median_columns:
            median_results = []
            for key, idxs in grouped.groups.items():
                group_dict = dict(zip(gb_columns, key))
                for col in median_columns:
                    group_dict[col] = df_selected.loc[idxs, col].median()
                median_results.append(group_dict)
            df_medians = pd.DataFrame(median_results)
            dfGB = dfGB.merge(df_medians, on=gb_columns, how='left')

        # Cast dtypes for numeric fit metrics
        if cast_dtype:
            for col in dfGB.columns:
                if any(x in col for x in ['slope', 'intercept', 'rms', 'mad']):
                    dfGB[col] = dfGB[col].astype(cast_dtype)

        # Add suffix (keep gb_columns unchanged)
        dfGB = dfGB.rename(columns={col: f"{col}{suffix}" for col in dfGB.columns if col not in gb_columns})

        # Optionally add predictions back to the input df
        if addPrediction and not dfGB.empty:
            df = df.merge(dfGB, on=gb_columns, how="left")
            for target_col in fit_columns:
                intercept_col = f"{target_col}_intercept{suffix}"
                if intercept_col not in df.columns:
                    continue
                df[f"{target_col}{suffix}"] = df[intercept_col]
                for pred_col in linear_columns:
                    slope_col = f"{target_col}_slope_{pred_col}{suffix}"
                    if slope_col in df.columns:
                        df[f"{target_col}{suffix}"] += df[slope_col] * df[pred_col]

        return df, dfGB



# Convenience wrapper for backward compatibility
def make_parallel_fit_v2(
    df: pd.DataFrame,
    gb_columns: List[str],
    fit_columns: List[str],
    linear_columns: List[str],
    median_columns: List[str],
    weights: str,
    suffix: str,
    selection: pd.Series,
    **kwargs
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Drop-in replacement for GroupByRegressor.make_parallel_fit with optimizations.

    Usage:
        # Old way:
        df_out, dfGB = GroupByRegressor.make_parallel_fit(df, ...)

        # New way (same API):
        df_out, dfGB = make_parallel_fit_v2(df, ...)
    """
    return GroupByRegressorOptimized.make_parallel_fit_optimized(
        df, gb_columns, fit_columns, linear_columns, median_columns,
        weights, suffix, selection, **kwargs
    )


# ======================================================================
# Phase 3 – Fast, Vectorized Implementation (NumPy / Numba-ready)
# ======================================================================

import numpy as np
import pandas as pd
import time

def make_parallel_fit_v3(
        df: pd.DataFrame,
        *,
        gb_columns,
        fit_columns,
        linear_columns,
        median_columns=None,
        weights=None,
        suffix: str = "_fast",
        selection=None,
        addPrediction: bool = False,
        cast_dtype: Union[str, None] ="float32",
        diag: bool = True,
        diag_prefix: str = "diag_",
        min_stat:  3,
):
    """
    Phase 3 – High-performance NumPy implementation of per-group OLS.

    * Single-process, vectorized; no joblib overhead.
    * Fully API-compatible with make_parallel_fit_v2.
    * Ready for later Numba acceleration.

    Parameters
    ----------
    df : pandas.DataFrame
        Input data.
    gb_columns : list[str]
        Columns to group by.
    fit_columns : list[str]
        Target variable(s).
    linear_columns : list[str]
        Predictor variable(s).
    median_columns : list[str], optional
        Columns for per-group medians.
    weights : str, optional
        Column with sample weights.
    suffix : str
        Suffix for output columns.
    selection : pandas.Series[bool], optional
        Row mask to select subset.
    addPrediction : bool
        Add fitted predictions to df_out.
    cast_dtype : str, optional
        Down-cast output coefficients.
    diag : bool
        Include diagnostics.
    diag_prefix : str
        Prefix for diagnostic columns.
    min_stat : int | list[int]
        Minimum number of points per group.

    Returns
    -------
    df_out : pandas.DataFrame
    dfGB : pandas.DataFrame
    """
    t_start = time.perf_counter()

    # ------------------------------------------------------------------
    # 0. Pre-filter / selection
    # ------------------------------------------------------------------
    if selection is not None:
        df = df.loc[selection]

    if median_columns is None:
        median_columns = []

    if isinstance(min_stat, (list, tuple)):
        min_stat = int(np.max(min_stat))

    if len(gb_columns) == 1:
        gb = df.groupby(gb_columns[0], observed=True, sort=False)
    else:
        gb = df.groupby(gb_columns, observed=True, sort=False)

    for g_name, g_df in gb:
        G = len(gb)

    # Prepare result containers
    res_rows = []
    fit_cols = list(fit_columns)
    X_cols = list(linear_columns)
    med_cols = list(median_columns)

    # ------------------------------------------------------------------
    # 1. Loop over groups (NumPy vectorized inside)
    # ------------------------------------------------------------------
    for g_name, g_df in gb:
        t0 = time.perf_counter()

        if len(g_df) < min_stat:
            continue

        X = g_df[X_cols].to_numpy(dtype=np.float64, copy=False)
        y = g_df[fit_cols].to_numpy(dtype=np.float64, copy=False)

        # add intercept
        X = np.c_[np.ones(len(X)), X]

        if weights is not None:
            w = g_df[weights].to_numpy(dtype=np.float64, copy=False)
            sw = np.sqrt(w)
            X = X * sw[:, None]
            y = y * sw[:, None]

        # closed-form OLS: β = (XᵀX)⁻¹ Xᵀy
        try:
            XtX = X.T @ X
            XtY = X.T @ y
            beta = np.linalg.solve(XtX, XtY)
        except np.linalg.LinAlgError:
            continue

        # predictions + RMS
        y_pred = X @ beta
        resid = y - y_pred
        rms = np.sqrt(np.mean(resid ** 2, axis=0))

        t1 = time.perf_counter()

        row = dict(zip(gb_columns, g_name if isinstance(g_name, tuple) else (g_name,)))

        # store coefficients
        for t_idx, tname in enumerate(fit_cols):
            row[f"{tname}_intercept{suffix}"] = beta[0, t_idx]
            for j, cname in enumerate(X_cols, start=1):
                row[f"{tname}_slope_{cname}{suffix}"] = beta[j, t_idx]
            row[f"{tname}_rms{suffix}"] = rms[t_idx]

        # medians
        for c in med_cols:
            row[f"{c}{suffix}"] = float(np.median(g_df[c].to_numpy()))

        # diagnostics
        if diag:
            row[f"{diag_prefix}time_ms"] = (t1 - t0) * 1e3
            row[f"{diag_prefix}n_rows"] = len(g_df)
            row[f"{diag_prefix}cond_xtx"] = float(np.linalg.cond(XtX))

        res_rows.append(row)

    # ------------------------------------------------------------------
    # 2. Assemble results
    # ------------------------------------------------------------------
    dfGB = pd.DataFrame(res_rows)
    if dfGB.empty:
        return df.copy(), pd.DataFrame(columns=list(gb_columns))

    # casting
    if cast_dtype is not None:
        cast_map = {
            c: cast_dtype
            for c in dfGB.columns
            if c not in gb_columns and dfGB[c].dtype == "float64"
        }
        dfGB = dfGB.astype(cast_map)

    # attach predictions if requested
    df_out = df.copy()
    if addPrediction:
        # build index map for fast join
        keycols = gb_columns
        dfGB_key = dfGB[keycols].astype(df_out[keycols].dtypes.to_dict())
        df_out = df_out.merge(dfGB, on=keycols, how="left")
        for t in fit_cols:
            intercept = df_out[f"{t}_intercept{suffix}"]
            pred = intercept.copy()
            for cname in X_cols:
                pred += df_out[f"{t}_slope_{cname}{suffix}"] * df_out[cname]
            df_out[f"{t}_pred{suffix}"] = pred.astype(df_out[t].dtype, copy=False)

    if diag:
        t_end = time.perf_counter()
        dfGB[f"{diag_prefix}wall_ms"] = (t_end - t_start) * 1e3

    return df_out, dfGB.reset_index(drop=True)



# ======================================================================
# Phase 4 — Numba-accelerated per-group OLS (weighted)  — make_parallel_fit_v4
# ======================================================================

# Numba import (safe; we fall back if absent)
try:
    from numba import njit
    _NUMBA_OK = True
except Exception:
    _NUMBA_OK = False


if _NUMBA_OK:
    @njit(fastmath=True)
    def _ols_kernel_numba_weighted(X_all, Y_all, W_all, offsets, n_groups, n_feat, n_tgt, min_stat, out_beta):
        """
        Weighted per-group OLS with intercept, compiled in nopython mode.

        Parameters
        ----------
        X_all   : (N, n_feat) float64
        Y_all   : (N, n_tgt)  float64
        W_all   : (N,)        float64  (weights; use 1.0 if unweighted)
        offsets : (G+1,)      int32    (group start indices in sorted arrays)
        n_groups: int
        n_feat  : int
        n_tgt   : int
        min_stat: int
        out_beta: (G, n_feat+1, n_tgt) float64  (beta rows: [intercept, slopes...])
        """
        p = n_feat + 1  # intercept + features
        for g in range(n_groups):
            i0 = offsets[g]
            i1 = offsets[g + 1]
            m = i1 - i0
            if m < min_stat or m <= n_feat:
                # insufficient stats to solve (or underdetermined)
                continue

            # Build X1 with intercept
            # X1 shape: (m, p)
            # X1[:,0] = 1
            # X1[:,1:] = X_all[i0:i1]
            X1 = np.ones((m, p))
            Xg = X_all[i0:i1]
            for r in range(m):
                for c in range(n_feat):
                    X1[r, c + 1] = Xg[r, c]

            # Weighted normal equations:
            #   XtX = Σ_r w_r * x_r x_r^T
            #   XtY = Σ_r w_r * x_r y_r^T
            XtX = np.empty((p, p))
            for i in range(p):
                for j in range(p):
                    s = 0.0
                    for r in range(m):
                        wr = W_all[i0 + r]
                        s += wr * X1[r, i] * X1[r, j]
                    XtX[i, j] = s

            Yg = Y_all[i0:i1]
            XtY = np.empty((p, n_tgt))
            for i in range(p):
                for t in range(n_tgt):
                    s = 0.0
                    for r in range(m):
                        wr = W_all[i0 + r]
                        s += wr * X1[r, i] * Yg[r, t]
                    XtY[i, t] = s

            # Solve XtX * B = XtY via Gauss–Jordan with partial pivoting
            A = XtX.copy()
            B = XtY.copy()

            for k in range(p):
                # pivot search
                piv = k
                amax = abs(A[k, k])
                for i in range(k + 1, p):
                    v = abs(A[i, k])
                    if v > amax:
                        amax = v
                        piv = i
                # robust guard for near singular
                if amax < 1e-12:
                    # singular; leave zeros for this group
                    for ii in range(p):
                        for tt in range(n_tgt):
                            out_beta[g, ii, tt] = 0.0
                    break

                # row swap if needed
                if piv != k:
                    for j in range(p):
                        tmp = A[k, j]; A[k, j] = A[piv, j]; A[piv, j] = tmp
                    for tt in range(n_tgt):
                        tmp = B[k, tt]; B[k, tt] = B[piv, tt]; B[piv, tt] = tmp

                pivval = A[k, k]
                invp = 1.0 / pivval
                A[k, k] = 1.0
                for j in range(k + 1, p):
                    A[k, j] *= invp
                for tt in range(n_tgt):
                    B[k, tt] *= invp

                for i in range(p):
                    if i == k:
                        continue
                    f = A[i, k]
                    if f != 0.0:
                        A[i, k] = 0.0
                        for j in range(k + 1, p):
                            A[i, j] -= f * A[k, j]
                        for tt in range(n_tgt):
                            B[i, tt] -= f * B[k, tt]

            # write solution β
            for i in range(p):
                for tt in range(n_tgt):
                    out_beta[g, i, tt] = B[i, tt]

def make_parallel_fit_v4(
        *,
        df,
        gb_columns,
        fit_columns,
        linear_columns,
        median_columns=None,
        weights=None,
        suffix="_v4",
        selection=None,
        addPrediction=False,
        cast_dtype="float64",
        min_stat=3,
        diag=False,
        diag_prefix="diag_",
):
    """
    Phase 3 (v4): Numba JIT weighted OLS with *fast* multi-column groupby support.
    Key points:
      - Group boundaries via vectorized adjacent-row comparisons per key column.
      - Vectorized dfGB assembly (no per-group iloc).
    """
    import numpy as np
    import pandas as pd

    if median_columns is None:
        median_columns = []

    # Filter
    if selection is not None:
        df = df.loc[selection]

    # Normalize group columns
    gb_cols = [gb_columns] if isinstance(gb_columns, str) else list(gb_columns)

    # Validate columns
    needed = set(gb_cols) | set(linear_columns) | set(fit_columns)
    if weights is not None:
        needed.add(weights)
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    # Stable sort by all group columns so groups are contiguous
    df_sorted = df.sort_values(gb_cols, kind="mergesort")

    # Dense arrays
    dtype_num = np.float64 if cast_dtype is None else cast_dtype
    X_all = df_sorted[linear_columns].to_numpy(dtype=dtype_num, copy=False)
    Y_all = df_sorted[fit_columns].to_numpy(dtype=dtype_num, copy=False)
    W_all = (np.ones(len(df_sorted), dtype=np.float64) if weights is None
             else df_sorted[weights].to_numpy(dtype=np.float64, copy=False))

    N = X_all.shape[0]
    if N == 0:
        return df_sorted.copy(), pd.DataFrame(columns=gb_cols + [f"n_refits{suffix}", f"n_used{suffix}", f"frac_rejected{suffix}"])

    n_feat = X_all.shape[1]
    n_tgt  = Y_all.shape[1]

    # ---------- FAST multi-column group offsets ----------
    # boundaries[0] = True; boundaries[i] = True if any key column changes at i vs i-1
    boundaries = np.empty(N, dtype=bool)
    boundaries[0] = True
    if N > 1:
        boundaries[1:] = False
        # OR-adjacent compare for each group column (vectorized)
        for col in gb_cols:
            a = df_sorted[col].to_numpy()
            boundaries[1:] |= (a[1:] != a[:-1])

    starts = np.flatnonzero(boundaries)
    offsets = np.empty(len(starts) + 1, dtype=np.int64)
    offsets[:-1] = starts
    offsets[-1] = N
    n_groups = len(starts)
    # ----------------------------------------------------

    # Allocate beta [n_groups, 1+n_feat, n_tgt]
    beta = np.zeros((n_groups, n_feat + 1, n_tgt), dtype=np.float64)

    # Numba kernel (weighted) or NumPy fallback
    try:
        _ols_kernel_numba_weighted(X_all, Y_all, W_all, offsets, n_groups, n_feat, n_tgt, int(min_stat), beta)
    except NameError:
        for gi in range(n_groups):
            i0, i1 = offsets[gi], offsets[gi + 1]
            m = i1 - i0
            if m < int(min_stat):
                continue
            Xg = X_all[i0:i1]
            Yg = Y_all[i0:i1]
            Wg = W_all[i0:i1].reshape(-1)
            X1 = np.c_[np.ones(m), Xg]
            XtX = (X1.T * Wg).dot(X1)
            XtY = (X1.T * Wg).dot(Yg)
            try:
                coeffs = np.linalg.solve(XtX, XtY)
                beta[gi, :, :] = coeffs
            except np.linalg.LinAlgError:
                pass

    # ---------- Vectorized dfGB assembly ----------
    # Pre-take first-row-of-group keys without iloc in a Python loop
    key_arrays = {col: df_sorted[col].to_numpy()[starts] for col in gb_cols}

    # Diagnostics & coeff arrays
    n_refits_arr = np.zeros(n_groups, dtype=np.int32)
    n_used_arr   = (offsets[1:] - offsets[:-1]).astype(np.int32)
    frac_rej_arr = np.zeros(n_groups, dtype=np.float64)

    out_dict = {col: key_arrays[col] for col in gb_cols}
    out_dict[f"n_refits{suffix}"] = n_refits_arr
    out_dict[f"n_used{suffix}"]   = n_used_arr
    out_dict[f"frac_rejected{suffix}"] = frac_rej_arr

    # Intercept + slopes
    for t_idx, tname in enumerate(fit_columns):
        out_dict[f"{tname}_intercept{suffix}"] = beta[:, 0, t_idx].astype(np.float64, copy=False)
        for j, cname in enumerate(linear_columns, start=1):
            out_dict[f"{tname}_slope_{cname}{suffix}"] = beta[:, j, t_idx].astype(np.float64, copy=False)

    # Optional diag: compute in one pass per group
    if diag:
        for t_idx, tname in enumerate(fit_columns):
            rms = np.zeros(n_groups, dtype=np.float64)
            mad = np.zeros(n_groups, dtype=np.float64)
            for gi in range(n_groups):
                i0, i1 = offsets[gi], offsets[gi + 1]
                m = i1 - i0
                if m == 0:
                    continue
                Xg = X_all[i0:i1]
                y  = Y_all[i0:i1, t_idx]
                X1 = np.c_[np.ones(m), Xg]
                resid = y - (X1 @ beta[gi, :, t_idx])
                rms[gi] = np.sqrt(np.mean(resid ** 2))
                mad[gi] = np.median(np.abs(resid - np.median(resid)))
            out_dict[f"{diag_prefix}{tname}_rms{suffix}"] = rms
            out_dict[f"{diag_prefix}{tname}_mad{suffix}"] = mad

    dfGB = pd.DataFrame(out_dict)
    # ---------- end dfGB assembly ----------

    return df_sorted, dfGB
