import numpy as np
import pandas as pd
import logging
from sklearn.linear_model import LinearRegression, HuberRegressor
from joblib import Parallel, delayed
from numpy.linalg import inv, LinAlgError
from typing import Union, List, Tuple, Callable
from random import shuffle

class GroupByRegressor:
    @staticmethod
    def _cast_fit_columns(dfGB: pd.DataFrame, cast_dtype: Union[str, None] = None) -> pd.DataFrame:
        if cast_dtype is not None:
            for col in dfGB.columns:
                if ("slope" in col or "intercept" in col or "rms" in col or "mad" in col):
                    dfGB[col] = dfGB[col].astype(cast_dtype)
        return dfGB

    @staticmethod
    def make_linear_fit(
            df: pd.DataFrame,
            gb_columns: List[str],
            fit_columns: List[str],
            linear_columns: List[str],
            median_columns: List[str],
            suffix: str,
            selection: pd.Series,
            addPrediction: bool = False,
            cast_dtype: Union[str, None] = None,
            min_stat: int = 10
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Perform grouped ordinary least squares linear regression and compute medians.

        Parameters:
            df (pd.DataFrame): Input dataframe.
            gb_columns (List[str]): Columns to group by.
            fit_columns (List[str]): Target columns for regression.
            linear_columns (List[str]): Predictor columns.
            median_columns (List[str]): Columns to compute median.
            suffix (str): Suffix for output columns.
            selection (pd.Series): Boolean mask to filter rows.
            addPrediction (bool): If True, add predicted values to df.
            cast_dtype (str|None): Data type to cast result coefficients.
            min_stat (int): Minimum number of rows per group to perform regression.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: (df with predictions, group-level regression results)
        """
        df_selected = df.loc[selection]
        group_results = []
        group_sizes = {}

        for group_vals, df_group in df_selected.groupby(gb_columns):
            group_dict = dict(zip(gb_columns, group_vals))
            group_sizes[group_vals] = len(df_group)

            for target_col in fit_columns:
                try:
                    X = df_group[linear_columns].values
                    y = df_group[target_col].values
                    if len(X) < min_stat:
                        for i, col in enumerate(linear_columns):
                            group_dict[f"{target_col}_slope_{col}"] = np.nan
                        group_dict[f"{target_col}_intercept"] = np.nan
                        continue
                    model = LinearRegression()
                    model.fit(X, y)
                    for i, col in enumerate(linear_columns):
                        group_dict[f"{target_col}_slope_{col}"] = model.coef_[i]
                    group_dict[f"{target_col}_intercept"] = model.intercept_
                except Exception as e:
                    logging.warning(f"Linear regression failed for {target_col} in group {group_vals}: {e}")
                    for col in linear_columns:
                        group_dict[f"{target_col}_slope_{col}"] = np.nan
                    group_dict[f"{target_col}_intercept"] = np.nan

            for col in median_columns:
                group_dict[col] = df_group[col].median()

            group_results.append(group_dict)

        dfGB = pd.DataFrame(group_results)
        dfGB = GroupByRegressor._cast_fit_columns(dfGB, cast_dtype)

        bin_counts = np.array([group_sizes.get(tuple(row), 0) for row in dfGB[gb_columns].itertuples(index=False)], dtype=np.int32)
        dfGB["bin_count"] = bin_counts
        dfGB = dfGB.rename(columns={col: f"{col}{suffix}" for col in dfGB.columns if col not in gb_columns})

        if addPrediction:
            df = df.merge(dfGB, on=gb_columns, how="left")
            for target_col in fit_columns:
                intercept_col = f"{target_col}_intercept{suffix}"
                if intercept_col not in df.columns:
                    continue
                df[f"{target_col}{suffix}"] = df[intercept_col]
                for col in linear_columns:
                    slope_col = f"{target_col}_slope_{col}{suffix}"
                    if slope_col in df.columns:
                        df[f"{target_col}{suffix}"] += df[slope_col] * df[col]

        return df, dfGB

    @staticmethod
    def process_group_robustBackup(
            key: tuple,
            df_group: pd.DataFrame,
            gb_columns: List[str],
            fit_columns: List[str],
            linear_columns0: List[str],
            median_columns: List[str],
            weights: str,
            minStat: List[int],
            sigmaCut: float = 4,
            fitter: Union[str, Callable] = "auto"
    ) -> dict:
        # TODO handle the case os single gb column
        group_dict = dict(zip(gb_columns, key))
        predictors = []
        if isinstance(weights, str) and weights not in df_group.columns:
            raise ValueError(f"Weight column '{weights}' not found in input DataFrame.")

        for i, col in enumerate(linear_columns0):
            required_columns = [col] + fit_columns + [weights]
            df_valid = df_group[required_columns].dropna()
            if len(df_valid) >= minStat[i]:
                predictors.append(col)

        for target_col in fit_columns:
            try:
                if not predictors:
                    continue

                subset_columns = predictors + [target_col, weights]
                df_clean = df_group.dropna(subset=subset_columns)

                if len(df_clean) < min(minStat):
                    continue

                X = df_clean[predictors].values
                y = df_clean[target_col].values
                w = df_clean[weights].values

                model = None
                if callable(fitter):
                    model = fitter()
                elif fitter == "robust":
                    model = HuberRegressor(tol=1e-4)
                elif fitter == "ols":
                    model = LinearRegression()
                else:
                    model = HuberRegressor(tol=1e-4)

                try:
                    model.fit(X, y, sample_weight=w)
                except Exception as e:
                    logging.warning(f"{model.__class__.__name__} failed for {target_col} in group {key}: {e}. Falling back to LinearRegression.")
                    model = LinearRegression()
                    model.fit(X, y, sample_weight=w)

                predicted = model.predict(X)
                residuals = y - predicted
                n, p = X.shape
                denom = n - p if n > p else 1e-9
                s2 = np.sum(residuals ** 2) / denom

                try:
                    cov_matrix = inv(X.T @ X) * s2
                    std_errors = np.sqrt(np.diag(cov_matrix))
                except LinAlgError:
                    std_errors = np.full(len(predictors), np.nan)

                rms = np.sqrt(np.mean(residuals ** 2))
                mad = np.median(np.abs(residuals))

                mask = np.abs(residuals) <= sigmaCut * mad
                if mask.sum() >= min(minStat):
                    try:
                        model.fit(X[mask], y[mask], sample_weight=w[mask])
                    except Exception as e:
                        logging.warning(f"{model.__class__.__name__} re-fit with outlier mask failed for {target_col} in group {key}: {e}. Falling back to LinearRegression.")
                        model = LinearRegression()
                        model.fit(X[mask], y[mask], sample_weight=w[mask])

                    predicted = model.predict(X)
                    residuals = y - predicted
                    rms = np.sqrt(np.mean(residuals ** 2))
                    mad = np.median(np.abs(residuals))

                for col in linear_columns0:
                    if col in predictors:
                        idx = predictors.index(col)
                        group_dict[f"{target_col}_slope_{col}"] = model.coef_[idx]
                        group_dict[f"{target_col}_err_{col}"] = std_errors[idx] if idx < len(std_errors) else np.nan
                    else:
                        group_dict[f"{target_col}_slope_{col}"] = np.nan
                        group_dict[f"{target_col}_err_{col}"] = np.nan

                group_dict[f"{target_col}_intercept"] = model.intercept_
                group_dict[f"{target_col}_rms"] = rms
                group_dict[f"{target_col}_mad"] = mad
            except Exception as e:
                logging.warning(f"Robust regression failed for {target_col} in group {key}: {e}")
                for col in linear_columns0:
                    group_dict[f"{target_col}_slope_{col}"] = np.nan
                    group_dict[f"{target_col}_err_{col}"] = np.nan
                group_dict[f"{target_col}_intercept"] = np.nan
                group_dict[f"{target_col}_rms"] = np.nan
                group_dict[f"{target_col}_mad"] = np.nan

        for col in median_columns:
            group_dict[col] = df_group[col].median()

        return group_dict

@staticmethod
def process_group_robust(
        key: tuple,
        df_group: pd.DataFrame,
        gb_columns: List[str],
        fit_columns: List[str],
        linear_columns0: List[str],
        median_columns: List[str],
        weights: str,
        minStat: List[int],
        sigmaCut: float = 4,
        fitter: Union[str, Callable] = "auto",
        # --- NEW (optional) diagnostics ---
        diag: bool = False,
        diag_prefix: str = "diag_",
) -> dict:
    """
    Per-group robust/OLS fit with optional diagnostics.

    Diagnostics (only when diag=True; added once per group into the result dict):
      - {diag_prefix}n_refits       : int, number of extra fits after the initial one (0 or 1 in this implementation)
      - {diag_prefix}frac_rejected  : float, fraction rejected by sigmaCut at final mask
      - {diag_prefix}hat_max        : float, max leverage proxy via QR (max rowwise ||Q||^2)
      - {diag_prefix}cond_xtx       : float, condition number of X^T X
      - {diag_prefix}time_ms        : float, wall-time per group (ms) excluding leverage/cond computation
      - {diag_prefix}n_rows         : int, number of rows in the group (after dropna for predictors/target/weights)

    Notes:
      - n_refits counts *additional* iterations beyond the first fit. With this one-pass sigmaCut scheme,
        it will be 0 (no re-fit) or 1 (re-fit once on inliers).
    """
    import time
    import numpy as np
    import logging
    from sklearn.linear_model import HuberRegressor, LinearRegression

    # TODO handle the case of single gb column
    group_dict = dict(zip(gb_columns, key))

    if isinstance(weights, str) and weights not in df_group.columns:
        raise ValueError(f"Weight column '{weights}' not found in input DataFrame.")

    # Select predictors that meet per-predictor minStat (based on non-null rows with target+weights)
    predictors: List[str] = []
    for i, col in enumerate(linear_columns0):
        required_columns = [col] + fit_columns + [weights]
        df_valid = df_group[required_columns].dropna()
        if len(df_valid) >= minStat[i]:
            predictors.append(col)

    # Prepare diagnostics state (group-level)
    n_refits_group = 0        # extra fits after initial fit
    frac_rejected_group = np.nan
    hat_max_group = np.nan
    cond_xtx_group = np.nan
    time_ms_group = np.nan
    n_rows_group = int(len(df_group))  # raw group size (will refine to cleaned size later)

    # Start timing the *fitting* work (we will stop before leverage/cond to avoid polluting time)
    t0_group = time.perf_counter()

    # Loop over target columns
    for target_col in fit_columns:
        try:
            if not predictors:
                # No valid predictors met minStat; emit NaNs for this target
                for col in linear_columns0:
                    group_dict[f"{target_col}_slope_{col}"] = np.nan
                    group_dict[f"{target_col}_err_{col}"] = np.nan
                group_dict[f"{target_col}_intercept"] = np.nan
                group_dict[f"{target_col}_rms"] = np.nan
                group_dict[f"{target_col}_mad"] = np.nan
                continue

            subset_columns = predictors + [target_col, weights]
            df_clean = df_group.dropna(subset=subset_columns)
            if len(df_clean) < min(minStat):
                # Not enough rows to fit
                for col in linear_columns0:
                    group_dict[f"{target_col}_slope_{col}"] = np.nan
                    group_dict[f"{target_col}_err_{col}"] = np.nan
                group_dict[f"{target_col}_intercept"] = np.nan
                group_dict[f"{target_col}_rms"] = np.nan
                group_dict[f"{target_col}_mad"] = np.nan
                continue

            # Update cleaned group size for diagnostics
            n_rows_group = int(len(df_clean))

            X = df_clean[predictors].to_numpy(copy=False)
            y = df_clean[target_col].to_numpy(copy=False)
            w = df_clean[weights].to_numpy(copy=False)

            # Choose model
            if callable(fitter):
                model = fitter()
            elif fitter == "robust":
                model = HuberRegressor(tol=1e-4)
            elif fitter == "ols":
                model = LinearRegression()
            else:
                model = HuberRegressor(tol=1e-4)

            # Initial fit
            try:
                model.fit(X, y, sample_weight=w)
            except Exception as e:
                logging.warning(
                    f"{model.__class__.__name__} failed for {target_col} in group {key}: {e}. "
                    f"Falling back to LinearRegression."
                )
                model = LinearRegression()
                model.fit(X, y, sample_weight=w)

            # Residuals and robust stats
            predicted = model.predict(X)
            residuals = y - predicted
            rms = float(np.sqrt(np.mean(residuals ** 2)))
            mad = float(np.median(np.abs(residuals)))

            # One-pass sigmaCut masking (current implementation supports at most a single re-fit)
            final_mask = None
            if np.isfinite(mad) and mad > 0 and sigmaCut is not None and sigmaCut < np.inf:
                mask = (np.abs(residuals) <= sigmaCut * mad)
                if mask.sum() >= min(minStat):
                    # Re-fit on inliers
                    n_refits_group += 1  # <-- counts *extra* fits beyond the first
                    try:
                        model.fit(X[mask], y[mask], sample_weight=w[mask])
                    except Exception as e:
                        logging.warning(
                            f"{model.__class__.__name__} re-fit with outlier mask failed for {target_col} "
                            f"in group {key}: {e}. Falling back to LinearRegression."
                        )
                        model = LinearRegression()
                        model.fit(X[mask], y[mask], sample_weight=w[mask])

                    # Recompute residuals on full X (to report global rms/mad)
                    predicted = model.predict(X)
                    residuals = y - predicted
                    rms = float(np.sqrt(np.mean(residuals ** 2)))
                    mad = float(np.median(np.abs(residuals)))
                    final_mask = mask
                else:
                    final_mask = np.ones_like(residuals, dtype=bool)
            else:
                final_mask = np.ones_like(residuals, dtype=bool)

            # Parameter errors from final fit (on the design actually used to fit)
            try:
                if final_mask is not None and final_mask.any():
                    X_used = X[final_mask]
                    y_used = y[final_mask]
                else:
                    X_used = X
                    y_used = y

                n, p = X_used.shape
                denom = n - p if n > p else 1e-9
                s2 = float(np.sum((y_used - model.predict(X_used)) ** 2) / denom)
                cov_matrix = np.linalg.inv(X_used.T @ X_used) * s2
                std_errors = np.sqrt(np.diag(cov_matrix))
            except np.linalg.LinAlgError:
                std_errors = np.full(len(predictors), np.nan, dtype=float)

            # Store results for this target
            for col in linear_columns0:
                if col in predictors:
                    idx = predictors.index(col)
                    group_dict[f"{target_col}_slope_{col}"] = float(model.coef_[idx])
                    group_dict[f"{target_col}_err_{col}"] = float(std_errors[idx]) if idx < len(std_errors) else np.nan
                else:
                    group_dict[f"{target_col}_slope_{col}"] = np.nan
                    group_dict[f"{target_col}_err_{col}"] = np.nan

            group_dict[f"{target_col}_intercept"] = float(model.intercept_) if hasattr(model, "intercept_") else np.nan
            group_dict[f"{target_col}_rms"] = rms
            group_dict[f"{target_col}_mad"] = mad

            # Update group-level diagnostics that depend on the final mask
            if diag:
                # Capture timing up to here (pure fitting + residuals + errors); exclude leverage/cond below
                time_ms_group = (time.perf_counter() - t0_group) * 1e3
                if final_mask is not None and len(final_mask) > 0:
                    frac_rejected_group = 1.0 - (float(np.count_nonzero(final_mask)) / float(len(final_mask)))
                else:
                    frac_rejected_group = np.nan

        except Exception as e:
            logging.warning(f"Robust regression failed for {target_col} in group {key}: {e}")
            for col in linear_columns0:
                group_dict[f"{target_col}_slope_{col}"] = np.nan
                group_dict[f"{target_col}_err_{col}"] = np.nan
            group_dict[f"{target_col}_intercept"] = np.nan
            group_dict[f"{target_col}_rms"] = np.nan
            group_dict[f"{target_col}_mad"] = np.nan

    # Medians
    for col in median_columns:
        try:
            group_dict[col] = df_group[col].median()
        except Exception:
            group_dict[col] = np.nan

    # Compute leverage & conditioning proxies (kept OUTSIDE the timed span)
    if diag:
        try:
            X_cols = [c for c in linear_columns0 if c in df_group.columns and c in predictors]
            if X_cols:
                X_diag = df_group[X_cols].dropna().to_numpy(dtype=np.float64, copy=False)
            else:
                X_diag = None

            hat_max_group = np.nan
            cond_xtx_group = np.nan
            if X_diag is not None and X_diag.size and X_diag.shape[1] > 0:
                # cond(X^T X)
                try:
                    s = np.linalg.svd(X_diag.T @ X_diag, compute_uv=False)
                    cond_xtx_group = float(s[0] / s[-1]) if (s.size > 0 and s[-1] > 0) else float("inf")
                except Exception:
                    cond_xtx_group = float("inf")
                # leverage via QR
                try:
                    Q, _ = np.linalg.qr(X_diag, mode="reduced")
                    hat_max_group = float(np.max(np.sum(Q * Q, axis=1)))
                except Exception:
                    pass
        except Exception:
            pass

        # Attach diagnostics (once per group)
        group_dict[f"{diag_prefix}n_refits"] = int(n_refits_group)
        group_dict[f"{diag_prefix}frac_rejected"] = float(frac_rejected_group) if np.isfinite(frac_rejected_group) else np.nan
        group_dict[f"{diag_prefix}hat_max"] = float(hat_max_group) if np.isfinite(hat_max_group) else np.nan
        group_dict[f"{diag_prefix}cond_xtx"] = float(cond_xtx_group) if np.isfinite(cond_xtx_group) else np.nan
        group_dict[f"{diag_prefix}time_ms"] = float(time_ms_group) if np.isfinite(time_ms_group) else np.nan
        group_dict[f"{diag_prefix}n_rows"] = int(n_rows_group)

    return group_dict


    @staticmethod
    def make_parallel_fit(
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
            min_stat: List[int] = [10, 10],
            sigmaCut: float = 4.0,
            fitter: Union[str, Callable] = "auto",
            batch_size: Union[int, None] = None,  # ← new argument
        # --- NEW: diagnostics switch ---
            diag: bool = False,
            diag_prefix: str = "diag_"
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Perform grouped robust linear regression using HuberRegressor in parallel.

        Parameters:
            df (pd.DataFrame): Input dataframe.
            gb_columns (List[str]): Columns to group by.
            fit_columns (List[str]): Target columns for regression.
            linear_columns (List[str]): Predictor columns.
            median_columns (List[str]): Columns to compute medians.
            weights (str): Column name of weights for fitting.
            suffix (str): Suffix to append to output columns.
            selection (pd.Series): Boolean selection mask.
            addPrediction (bool): If True, add prediction columns to df.
            cast_dtype (Union[str, None]): Optional dtype cast for fit outputs.
            n_jobs (int): Number of parallel jobs.
            min_stat (List[int]): Minimum number of rows required to use each predictor.
            sigmaCut (float): Outlier threshold in MAD units.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: DataFrame with predictions and group-level statistics.
        """
        if isinstance(weights, str) and weights not in df.columns:
            raise ValueError(f"Weight column '{weights}' not found in input DataFrame")

        df_selected = df.loc[selection]
        grouped = df_selected.groupby(gb_columns)

        filtered_items = [(key, idxs) for key, idxs in grouped.groups.items() if len(idxs) >= min_stat[0]/2]
        # shuffle(filtered_items) # Shuffle to ensure random order in parallel processing - should be an option

        results = Parallel(n_jobs=n_jobs,batch_size=batch_size)(
            delayed(GroupByRegressor.process_group_robust)(
                key, df_selected.loc[idxs], gb_columns, fit_columns, linear_columns,
                median_columns, weights, min_stat, sigmaCut, fitter
            )
            for key, idxs in filtered_items
        )

        dfGB = pd.DataFrame(results)
        dfGB = GroupByRegressor._cast_fit_columns(dfGB, cast_dtype)

        bin_counts = np.array([
            len(grouped.get_group(key)) if key in grouped.groups else 0
            for key in dfGB[gb_columns].itertuples(index=False, name=None)
        ], dtype=np.int32)
        dfGB["bin_count"] = bin_counts
        dfGB = dfGB.rename(columns={col: f"{col}{suffix}" for col in dfGB.columns if col not in gb_columns})

        if addPrediction:
            df = df.merge(dfGB, on=gb_columns, how="left")
            for target_col in fit_columns:
                intercept_col = f"{target_col}_intercept{suffix}"
                if intercept_col not in df.columns:
                    continue
                df[f"{target_col}{suffix}"] = df[intercept_col]
                for col in linear_columns:
                    slope_col = f"{target_col}_slope_{col}{suffix}"
                    if slope_col in df.columns:
                        df[f"{target_col}{suffix}"] += df[slope_col] * df[col]

        return df, dfGB

def summarize_diagnostics(dfGB, diag_prefix: str = "diag_", top: int = 50):
    """
    Quick look at diagnostic columns emitted by make_parallel_fit(..., diag=True).
    Returns a dict of small DataFrames for top offenders, and prints a short summary.

    Example:
        summ = summarize_diagnostics(dfGB, top=20)
        summ["slowest"].head()
    """
    import pandas as pd
    cols = {
        "time": f"{diag_prefix}time_ms",
        "refits": f"{diag_prefix}n_refits",
        "rej": f"{diag_prefix}frac_rejected",
        "lev": f"{diag_prefix}hat_max",
        "cond": f"{diag_prefix}cond_xtx",
        "nrows": f"{diag_prefix}n_rows",
    }
    missing = [c for c in cols.values() if c not in dfGB.columns]
    if missing:
        print("[diagnostics] Missing columns (did you run diag=True?):", missing)
        return {}

    summary = {}
    # Defensive: numeric coerce
    d = dfGB.copy()
    for k, c in cols.items():
        d[c] = pd.to_numeric(d[c], errors="coerce")

    summary["slowest"] = d.sort_values(cols["time"], ascending=False).head(top)[list({*dfGB.columns[:len(dfGB.columns)//4], *cols.values()})]
    summary["most_refits"] = d.sort_values(cols["refits"], ascending=False).head(top)[list({*dfGB.columns[:len(dfGB.columns)//4], *cols.values()})]
    summary["most_rejected"] = d.sort_values(cols["rej"], ascending=False).head(top)[list({*dfGB.columns[:len(dfGB.columns)//4], *cols.values()})]
    summary["highest_leverage"] = d.sort_values(cols["lev"], ascending=False).head(top)[list({*dfGB.columns[:len(dfGB.columns)//4], *cols.values()})]
    summary["worst_conditioned"] = d.sort_values(cols["cond"], ascending=False).head(top)[list({*dfGB.columns[:len(dfGB.columns)//4], *cols.values()})]

    # Console summary
    print("[diagnostics] Groups:", len(dfGB))
    print("[diagnostics] mean time (ms):", float(d[cols["time"]].mean()))
    print("[diagnostics] pct with refits>0:", float((d[cols["refits"]] > 0).mean()) * 100.0)
    print("[diagnostics] mean frac_rejected:", float(d[cols["rej"]].mean()))
    print("[diagnostics] 99p cond_xtx:", float(d[cols["cond"]].quantile(0.99)))
    print("[diagnostics] 99p hat_max:", float(d[cols["lev"]].quantile(0.99)))
    return summary
