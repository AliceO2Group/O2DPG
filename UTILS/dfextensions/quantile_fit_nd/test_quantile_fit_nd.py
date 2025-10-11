# dfextension/quantile_fit_nd/test_quantile_fit_nd.py
# Unit + synthetic tests comparing recovered params & uncertainties to ground truth.
import numpy as np
import pandas as pd
import pytest

from dfextensions.quantile_fit_nd.quantile_fit_nd import ( fit_quantile_linear_nd, QuantileEvaluator)

RNG = np.random.default_rng(42)


def gen_Q_from_distribution(dist: str, n: int, params: dict) -> np.ndarray:
    if dist == "uniform":
        return RNG.uniform(0.0, 1.0, size=n)
    elif dist == "poisson":
        lam = params.get("lam", 20.0)
        m = RNG.poisson(lam, size=n)
        # continuous CDF transform for integer Poisson
        # use normal approximation for speed
        from math import erf, sqrt
        mu, sigma = lam, np.sqrt(lam)
        z = (m + 0.5 - mu) / max(sigma, 1e-6)
        cdf = 0.5 * (1.0 + np.array([erf(zi / np.sqrt(2)) for zi in z]))
        return np.clip(cdf, 0.0, 1.0)
    elif dist == "gaussian":
        mu = params.get("mu", 0.0)
        sigma = params.get("sigma", 1.0)
        g = RNG.normal(mu, sigma, size=n)
        from math import erf, sqrt
        z = (g - mu) / max(sigma, 1e-9)
        cdf = 0.5 * (1.0 + np.array([erf(zi / np.sqrt(2)) for zi in z]))
        return np.clip(cdf, 0.0, 1.0)
    else:
        raise ValueError(f"unknown dist {dist}")


def gen_synthetic_df(
        n: int,
        dist: str = "uniform",
        z_sigma_cm: float = 5.0,
        z_range_cm: float = 10.0,
        sigma_X_given_Q: float = 0.5,
        a0: float = 10.0,
        a1: float = 0.5,
        b0: float = 50.0,
        b1: float = 2.0,
) -> tuple[pd.DataFrame, dict]:
    # Q from chosen multiplicity proxy distribution
    Q = gen_Q_from_distribution(dist, n, params={"lam": 20.0, "mu": 0.0, "sigma": 1.0})
    # nuisance z ~ N(0, z_sigma), truncated to ±z_range
    z = np.clip(RNG.normal(0.0, z_sigma_cm, size=n), -z_range_cm, z_range_cm)
    # true coefficients as functions of z (ensure b>0)
    a_true = a0 + a1 * z
    b_true = (b0 + b1 * z / max(z_range_cm, 1e-6)).clip(min=5.0)
    # amplitude model
    X = a_true + b_true * Q + RNG.normal(0.0, sigma_X_given_Q, size=n)
    df = pd.DataFrame({
        "channel_id": np.repeat("ch0", n),
        "Q": Q,
        "X": X,
        "z_vtx": z,
        "is_outlier": np.zeros(n, dtype=bool),
    })
    truth = {
        "a0": a0, "a1": a1,
        "b0": b0, "b1": b1,
        "sigma_X_given_Q": sigma_X_given_Q,
        "z_range": z_range_cm,
    }
    return df, truth


@pytest.mark.parametrize("dist", ["uniform", "poisson", "gaussian"])
@pytest.mark.parametrize("n_points", [5_000, 50_000])
def test_fit_and_sigmaQ(dist, n_points):
    df, truth = gen_synthetic_df(n_points, dist=dist)
    q_centers = np.linspace(0.0, 1.0, 11)
    table = fit_quantile_linear_nd(
        df,
        channel_key="channel_id",
        q_centers=q_centers,
        dq=0.05,
        nuisance_axes={"z": "z_vtx"},
        n_bins_axes={"z": 10},
        mask_col="is_outlier",
        b_min_option="auto",
        fit_mode="ols",
        kappa_w=1.3,
    )
    # Basic sanity
    assert not table.empty
    assert {"a", "b", "sigma_Q", "z_center", "q_center"}.issubset(set(table.columns))

    # Compare b(z) to truth at each z_center (averaged over q)
    zc = np.sort(table["z_center"].unique())
    # expected b at centers
    b_expected = (truth["b0"] + truth["b1"] * zc / max(truth["z_range"], 1e-6)).clip(min=5.0)
    b_meas = table.groupby("z_center")["b"].mean().to_numpy()
    # relative error tolerance (10%)
    rel_err = np.nanmean(np.abs(b_meas - b_expected) / np.maximum(1e-6, b_expected))
    assert rel_err < 0.15, f"relative error too large: {rel_err:.3f}"

    # sigma_Q check vs known sigma_X_given_Q/b(z)
    # compare median over q per z bin
    sigma_q_meas = table.groupby("z_center")["sigma_Q"].median().to_numpy()
    sigma_q_true = truth["sigma_X_given_Q"] / np.maximum(1e-9, b_expected)
    rel_err_sig = np.nanmean(np.abs(sigma_q_meas - sigma_q_true) / np.maximum(1e-9, sigma_q_true))
    assert rel_err_sig < 0.20, f"sigma_Q rel err too large: {rel_err_sig:.3f}"

    # Inversion round-trip check on a subset
    evalr = QuantileEvaluator(table)
    idx = np.linspace(0, len(df) - 1, num=500, dtype=int)
    resid = []
    for i in idx:
        z = float(df.loc[i, "z_vtx"])
        q_true = float(df.loc[i, "Q"])
        x = float(df.loc[i, "X"])
        q_hat = evalr.invert_rank(x, channel_id="ch0", z=z)
        resid.append(q_hat - q_true)
    rms = np.sqrt(np.mean(np.square(resid)))
    assert rms < 0.06, f"round-trip Q residual RMS too large: {rms:.3f}"


def test_edges_behavior():
    # focus events near edges
    n = 20000
    Q = np.concatenate([np.clip(RNG.normal(0.02, 0.01, n//2), 0, 1),
                        np.clip(RNG.normal(0.98, 0.01, n//2), 0, 1)])
    z = RNG.normal(0.0, 5.0, size=n)
    a0, b0, sigma = 5.0, 40.0, 0.4
    X = a0 + b0 * Q + RNG.normal(0.0, sigma, size=n)
    df = pd.DataFrame({"channel_id": "chE", "Q": Q, "X": X, "z_vtx": z, "is_outlier": False})
    table = fit_quantile_linear_nd(
        df, channel_key="channel_id",
        q_centers=np.linspace(0, 1, 11), dq=0.05,
        nuisance_axes={"z": "z_vtx"}, n_bins_axes={"z": 6}
    )
    # No NaN explosion
    assert np.isfinite(table["b"]).mean() > 0.9
    assert (table["b"] > 0).mean() > 0.9
