import numpy as np
import pandas as pd
import logging
from sklearn.linear_model import LinearRegression, HuberRegressor
from joblib import Parallel, delayed
from numpy.linalg import inv, LinAlgError


class GroupByRegressor:
    @staticmethod
    def _cast_fit_columns(dfGB, cast_dtype=None):
        if cast_dtype is not None:
            for col in dfGB.columns:
                if ("slope" in col or "intercept" in col or "rms" in col or "mad" in col):
                    dfGB[col] = dfGB[col].astype(cast_dtype)
        return dfGB

    @staticmethod
    def make_linear_fit(df, gb_columns, fit_columns, linear_columns, median_columns, suffix, selection, addPrediction=False, cast_dtype=None, min_stat=10):
        """
        Perform standard linear regression fits for grouped data and compute median values.

        Parameters:
            df (pd.DataFrame): Input dataframe.
            gb_columns (list): Columns to group by.
            fit_columns (list): Target columns for linear regression.
            linear_columns (list): Independent variables used for the fit.
            median_columns (list): Columns for which median values are computed.
            suffix (str): Suffix to append to columns in the output dfGB.
            selection (pd.Series): Boolean mask for selecting rows.
            addPrediction (bool): If True, merge predictions back into df.
            cast_dtype (str or None): If not None, cast fit-related columns to this dtype.
            min_stat (int): Minimum number of rows required to perform regression.

        Returns:
            tuple: (df, dfGB) where
                df is the original dataframe with predicted values appended (if addPrediction is True),
                and dfGB is the group-by statistics dataframe containing medians and fit coefficients.
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
                        for col in linear_columns:
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
        dfGB = dfGB.copy()

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
    def process_group_robust(key, df_group, gb_columns, fit_columns, linear_columns0, median_columns, weights, minStat=[], sigmaCut=4):
        """
        Process a single group: perform robust regression fits on each target column,
        compute median values, RMS and MAD of the residuals.
        After an initial Huber fit, points with residuals > sigmaCut * MAD are removed and the fit is redone
        if enough points remain.

        For each predictor in linear_columns0, the predictor is used only if the number of rows in the group
        is greater than the corresponding value in minStat.

        Parameters:
          key: Group key.
          df_group (pd.DataFrame): Data for the group.
          gb_columns (list): Columns used for grouping.
          fit_columns (list): Target columns to be fit.
          linear_columns0 (list): List of candidate predictor columns.
          median_columns (list): List of columns for which median values are computed.
          weights (str): Column name for weights.
          minStat (list): List of minimum number of rows required to use each predictor in linear_columns0.
          sigmaCut (float): Factor to remove outliers (points with residual > sigmaCut * MAD).

        Returns:
          dict: A dictionary containing group keys, fit parameters, RMS, and MAD.
        """
        group_dict = dict(zip(gb_columns, key))
        n_rows = len(df_group)
        predictors = []

        for i, col in enumerate(linear_columns0):
            if n_rows > minStat[i]:
                predictors.append(col)

        for target_col in fit_columns:
            try:
                if not predictors:
                    continue
                X = df_group[predictors].values
                y = df_group[target_col].values
                w = df_group[weights].values
                if len(y) < min(minStat):
                    continue

                model = HuberRegressor(tol=1e-4)
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
