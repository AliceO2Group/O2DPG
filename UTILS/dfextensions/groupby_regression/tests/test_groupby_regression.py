import pytest
import pandas as pd
import numpy as np
#from groupby_regression import GroupByRegressor
from ..groupby_regression import GroupByRegressor

@pytest.fixture
def sample_data():
    np.random.seed(0)
    n = 100
    df = pd.DataFrame({
        'group': np.random.choice(['A', 'B'], size=n),
        'x1': np.random.normal(loc=0, scale=1, size=n),
        'x2': np.random.normal(loc=5, scale=2, size=n),
    })
    df['y'] = 2.0 * df['x1'] + 3.0 * df['x2'] + np.random.normal(0, 0.5, size=n)
    df['weight'] = np.ones(n)
    return df


def test_make_linear_fit_basic(sample_data):
    df = sample_data.copy()
    df_out, dfGB = GroupByRegressor.make_linear_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        suffix='_fit',
        selection=(df['x1'] > -10),
        addPrediction=True
    )
    assert not dfGB.empty
    assert 'y_fit' in df_out.columns
    assert 'y_slope_x1_fit' in dfGB.columns
    assert 'x1_fit' in dfGB.columns


def test_make_parallel_fit_robust(sample_data):
    df = sample_data.copy()
    df_out, dfGB = GroupByRegressor.make_parallel_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        weights='weight',
        suffix='_rob',
        selection=(df['x1'] > -10),
        addPrediction=True,
        n_jobs=1,
        min_stat=[5, 5]
    )
    assert not dfGB.empty
    assert 'y_rob' in df_out.columns
    assert 'y_slope_x1_rob' in dfGB.columns
    assert 'y_intercept_rob' in dfGB.columns


def test_insufficient_data(sample_data):
    df = sample_data.copy()
    df = df[df['group'] == 'A'].iloc[:5]  # Force small group
    df_out, dfGB = GroupByRegressor.make_linear_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        suffix='_tiny',
        selection=(df['x1'] > -10),
        addPrediction=True,
        min_stat=10
    )
    assert len(dfGB) <= 1  # Could be empty or single group with skipped fit
    assert 'y_tiny' in df_out.columns
    assert dfGB.get('y_slope_x1_tiny') is None or dfGB['y_slope_x1_tiny'].isna().all()
    assert dfGB.get('y_intercept_tiny') is None or dfGB['y_intercept_tiny'].isna().all()


def test_prediction_accuracy(sample_data):
    df = sample_data.copy()
    df_out, dfGB = GroupByRegressor.make_linear_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        suffix='_pred',
        selection=(df['x1'] > -10),
        addPrediction=True
    )
    errors = df_out['y'] - df_out['y_pred']
    assert errors.std() < 1.0  # Should be close to noise level


def test_missing_values():
    df = pd.DataFrame({
        'group': ['A', 'A', 'B', 'B'],
        'x1': [1.0, 2.0, np.nan, 4.0],
        'x2': [2.0, 3.0, 1.0, np.nan],
        'y':  [5.0, 8.0, 4.0, 6.0],
        'weight': [1.0, 1.0, 1.0, 1.0]
    })
    selection = df['x1'].notna() & df['x2'].notna()
    df_out, dfGB = GroupByRegressor.make_linear_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        suffix='_nan',
        selection=selection,
        addPrediction=True
    )
    assert 'y_nan' in df_out.columns
    assert df_out['y_nan'].isna().sum() >= 0  # No crash due to missing data


def test_cast_dtype_effect():
    df = pd.DataFrame({
        'group': ['G1'] * 10,
        'x1': np.linspace(0, 1, 10),
        'x2': np.linspace(1, 2, 10),
    })
    df['y'] = 2.0 * df['x1'] + 3.0 * df['x2']
    df['weight'] = 1.0

    df_out, dfGB = GroupByRegressor.make_linear_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        suffix='_typed',
        selection=(df['x1'] >= 0),
        addPrediction=True,
        cast_dtype='float32'
    )

    assert dfGB['y_slope_x1_typed'].dtype == np.float32
    assert dfGB['y_slope_x2_typed'].dtype == np.float32


def test_robust_outlier_resilience():
    np.random.seed(0)
    x1 = np.random.uniform(0, 1, 100)
    x2 = np.random.uniform(10, 20, 100)
    y = 2.0 * x1 + 3.0 * x2
    y[::10] += 50  # Inject outliers every 10th sample

    df = pd.DataFrame({
        'group': ['G1'] * 100,
        'x1': x1,
        'x2': x2,
        'y': y,
        'weight': 1.0
    })

    _, df_robust = GroupByRegressor.make_parallel_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        weights='weight',
        suffix='_robust',
        selection=(df['x1'] >= 0),
        addPrediction=True,
        n_jobs=1
    )

    assert np.isclose(df_robust['y_slope_x1_robust'].iloc[0], 2.0, atol=0.5)
    assert np.isclose(df_robust['y_slope_x2_robust'].iloc[0], 3.0, atol=0.5)


def test_exact_coefficient_recovery():
    np.random.seed(0)
    x1 = np.random.uniform(0, 1, 100)
    x2 = np.random.uniform(10, 20, 100)
    df = pd.DataFrame({
        'group': ['G1'] * 100,
        'x1': x1,
        'x2': x2,
    })
    df['y'] = 2.0 * df['x1'] + 3.0 * df['x2']
    df['weight'] = 1.0

    df_out, dfGB = GroupByRegressor.make_linear_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        suffix='_clean',
        selection=(df['x1'] >= 0),
        addPrediction=True
    )

    assert np.isclose(dfGB['y_slope_x1_clean'].iloc[0], 2.0, atol=1e-6)
    assert np.isclose(dfGB['y_slope_x2_clean'].iloc[0], 3.0, atol=1e-6)


def test_exact_coefficient_recovery_parallel():
    np.random.seed(0)
    x1 = np.random.uniform(0, 1, 100)
    x2 = np.random.uniform(10, 20, 100)
    df = pd.DataFrame({
        'group': ['G1'] * 100,
        'x1': x1,
        'x2': x2,
    })
    df['y'] = 2.0 * df['x1'] + 3.0 * df['x2']
    df['weight'] = 1.0

    df_out, dfGB = GroupByRegressor.make_parallel_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        weights='weight',
        suffix='_par',
        selection=(df['x1'] >= 0),
        addPrediction=True,
        n_jobs=1,
        min_stat=[1, 1]
    )

    assert np.isclose(dfGB['y_slope_x1_par'].iloc[0], 2.0, atol=1e-6)
    assert np.isclose(dfGB['y_slope_x2_par'].iloc[0], 3.0, atol=1e-6)


def test_min_stat_per_predictor():
    # Create a group with 20 rows total, but only 5 valid for x2
    df = pd.DataFrame({
        'group': ['G1'] * 20,
        'x1': np.linspace(0, 1, 20),
        'x2': [np.nan] * 15 + list(np.linspace(0, 1, 5)),
    })
    df['y'] = 2.0 * df['x1'] + 3.0 * np.nan_to_num(df['x2']) + np.random.normal(0, 0.01, 20)
    df['weight'] = 1.0

    # Use all 20 rows, but let selection ensure only valid ones go into each predictor fit
    selection = df['x1'].notna() & df['y'].notna()

    df_out, dfGB = GroupByRegressor.make_parallel_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        weights='weight',
        suffix='_minstat',
        selection=selection,
        addPrediction=True,
        min_stat=[10, 10],  # x1: 20 valid rows; x2: only 5
        n_jobs=1
    )

    assert 'y_slope_x1_minstat' in dfGB.columns
    assert not np.isnan(dfGB['y_slope_x1_minstat'].iloc[0])  # x1 passed
    assert 'y_slope_x2_minstat' not in dfGB.columns or np.isnan(dfGB['y_slope_x2_minstat'].iloc[0])  # x2 skipped
def test_sigma_cut_impact():
    np.random.seed(0)
    n_samples = 10000
    df = pd.DataFrame({
        'group': ['G1'] * n_samples,
        'x1': np.linspace(0, 1, n_samples),
    })
    df['y'] = 3.0 * df['x1'] + np.random.normal(0, 0.1, size=n_samples)
    df.loc[::50, 'y'] += 100  # Insert strong outliers every 50th sample
    df['weight'] = 1.0
    selection = df['x1'].notna() & df['y'].notna()

    _, dfGB_all = GroupByRegressor.make_parallel_fit(
        df, ['group'], ['y'], ['x1'], ['x1'], 'weight', '_s100',
        selection=selection, sigmaCut=100, n_jobs=1, addPrediction=True
    )

    _, dfGB_strict = GroupByRegressor.make_parallel_fit(
        df, ['group'], ['y'], ['x1'], ['x1'], 'weight', '_s2',
        selection=selection, sigmaCut=3, n_jobs=1, addPrediction=True
    )

    slope_all = dfGB_all['y_slope_x1_s100'].iloc[0]
    slope_strict = dfGB_strict['y_slope_x1_s2'].iloc[0]

    assert abs(slope_strict - 3.0) < abs(slope_all - 3.0), \
        f"Robust fit with sigmaCut=2 should be closer to truth: slope_strict={slope_strict}, slope_all={slope_all}"



def test_make_parallel_fit_robust_v2(sample_data):
    df = sample_data.copy()
    df_out, dfGB = GroupByRegressor.make_parallel_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        weights='weight',
        suffix='_rob',
        selection=(df['x1'] > -10),
        addPrediction=True,
        n_jobs=1,
        min_stat=[5, 5],
        fitter="robust"
    )
    assert not dfGB.empty
    assert 'y_rob' in df_out.columns
    assert 'y_slope_x1_rob' in dfGB.columns
    assert 'y_intercept_rob' in dfGB.columns


def test_make_parallel_fit_with_linear_regression(sample_data):
    df = sample_data.copy()
    df_out, dfGB = GroupByRegressor.make_parallel_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1', 'x2'],
        median_columns=['x1'],
        weights='weight',
        suffix='_ols',
        selection=(df['x1'] > -10),
        addPrediction=True,
        n_jobs=1,
        min_stat=[5, 5],
        fitter="ols"
    )
    assert not dfGB.empty
    assert 'y_ols' in df_out.columns
    assert 'y_slope_x1_ols' in dfGB.columns
    assert 'y_intercept_ols' in dfGB.columns

def test_make_parallel_fit_with_custom_fitter(sample_data):
    class DummyFitter:
        def fit(self, X, y, sample_weight=None):
            self.coef_ = np.zeros(X.shape[1])
            self.intercept_ = 42
            return self

        def predict(self, X):
            return np.full(X.shape[0], self.intercept_)

    df = sample_data.copy()
    df_out, dfGB = GroupByRegressor.make_parallel_fit(
        df,
        gb_columns=['group'],
        fit_columns=['y'],
        linear_columns=['x1'],
        median_columns=['x1'],
        weights='weight',
        suffix='_dummy',
        selection=(df['x1'] > -10),
        addPrediction=True,
        n_jobs=1,
        min_stat=[5],
        fitter=DummyFitter
    )
    predicted = df_out['y_dummy'].dropna()
    assert not predicted.empty
    assert np.allclose(predicted.unique(), 42)
    assert 'y_slope_x1_dummy' in dfGB.columns
    assert dfGB['y_slope_x1_dummy'].iloc[0] == 0
    assert dfGB['y_intercept_dummy'].iloc[0] == 42


def _make_groups(n_rows, n_groups, seed=0):
    rng = np.random.default_rng(seed)
    base = np.repeat(np.arange(n_groups, dtype=np.int32), n_rows // n_groups)
    rem = n_rows - base.size
    if rem > 0:
        base = np.concatenate([base, rng.choice(n_groups, size=rem, replace=False)])
    rng.shuffle(base)
    return base

def _create_clean(n_rows=1000, n_groups=200, seed=0):
    rng = np.random.default_rng(seed)
    g = _make_groups(n_rows, n_groups, seed)
    x = rng.normal(size=(n_rows, 2)).astype(np.float32)
    y = (2*x[:,0] + 3*x[:,1] + rng.normal(0,1.0,size=n_rows)).astype(np.float32)
    df = pd.DataFrame({"group": g, "x1": x[:,0], "x2": x[:,1], "y": y})
    df["group2"] = df["group"]
    df["weight"] = 1.0
    return df

def test_diagnostics_columns_present():
    df = _create_clean()
    sel = pd.Series(True, index=df.index)
    _, dfGB = GroupByRegressor.make_parallel_fit(
        df,
        gb_columns=["group", "group2"],
        fit_columns=["y"],
        linear_columns=["x1", "x2"],
        median_columns=[],
        weights="weight",
        suffix="_fit",
        selection=sel,
        addPrediction=False,
        n_jobs=1,
        min_stat=[3, 4],
        sigmaCut=5,
        fitter="ols",
        batch_size="auto",
        diag=True,                # <-- exercise diagnostics
        diag_prefix="diag_",
    )
    # Change the expected column names to include the suffix
    suffix = "_fit" # <-- Add this line for clarity
    cols = [
        f"diag_n_refits{suffix}", f"diag_frac_rejected{suffix}", f"diag_hat_max{suffix}",
        f"diag_cond_xtx{suffix}", f"diag_time_ms{suffix}", f"diag_n_rows{suffix}",
    ]

    for c in cols:
        assert c in dfGB.columns, f"missing diagnostic column {c}"
    # The original un-suffixed assertion: assert (dfGB["diag_n_refits"] >= 0).all()
    # must also be updated to:
    assert (dfGB[f"diag_n_refits{suffix}"] >= 0).all()
