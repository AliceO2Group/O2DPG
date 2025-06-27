import numpy as np
import pandas as pd
import logging
from sklearn.linear_model import LinearRegression, HuberRegressor
from joblib import Parallel, delayed
from numpy.linalg import inv, LinAlgError
from typing import Union, List, Tuple, Callable


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
            fitter: Union[str, Callable] = "auto"
    ) -> dict:
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
            fitter: Union[str, Callable] = "auto"
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

        results = Parallel(n_jobs=n_jobs)(
            delayed(GroupByRegressor.process_group_robust)(
                key, group_df, gb_columns, fit_columns, linear_columns,
                median_columns, weights, min_stat, sigmaCut, fitter
            )
            for key, group_df in grouped
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
