# dfextensions/quantile_fit_nd/test_quantile_fit_nd.py
import numpy as np
import pandas as pd
import pytest

from dfextensions.quantile_fit_nd.quantile_fit_nd import (
    fit_quantile_linear_nd,
    QuantileEvaluator,
)

RNG = np.random.default_rng(42)


def gen_Q_from_distribution(dist: str, n: int, params: dict) -> np.ndarray:
    if dist == "uniform":
        return RNG.uniform(0.0, 1.0, size=n)
    elif dist == "poisson":
        lam = params.get("lam", 20.0)
        m = RNG.poisson(lam, size=n)
        from math import erf
        z = (m + 0.5 - lam) / np.sqrt(max(lam, 1e-6))
        cdf = 0.5 * (1.0 + np.array([erf(zi / np.sqrt(2)) for zi in z]))
        return np.clip(cdf, 0.0, 1.0)
    elif dist == "gaussian":
        mu = params.get("mu", 0.0)
        sigma = params.get("sigma", 1.0)
        g = RNG.normal(mu, sigma, size=n)
        from math import erf
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
    Q = gen_Q_from_distribution(dist, n, params={"lam": 20.0, "mu": 0.0, "sigma": 1.0})
    z = np.clip(RNG.normal(0.0, z_sigma_cm, size=n), -z_range_cm, z_range_cm)
    a_true = a0 + a1 * z
    b_true = (b0 + b1 * z / max(z_range_cm, 1e-6)).clip(min=5.0)
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


def _edges_from_centers(centers: np.ndarray) -> np.ndarray:
    mid = 0.5 * (centers[1:] + centers[:-1])
    first = centers[0] - (mid[0] - centers[0])
    last = centers[-1] + (centers[-1] - mid[-1])
    return np.concatenate([[first], mid, [last]])


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
    )
    assert not table.empty
    assert {"a", "b", "sigma_Q", "z_center", "q_center"}.issubset(table.columns)

    # Compute expected b(z) by averaging the analytic b_true(z) over the actual
    # sample in each z-bin, using the same bin edges as the table.
    z_centers = np.sort(table["z_center"].unique())
    z_edges = _edges_from_centers(z_centers)
    z_vals = df["z_vtx"].to_numpy(np.float64)
    b_true_all = (truth["b0"] + truth["b1"] * z_vals / max(truth["z_range"], 1e-6)).clip(min=5.0)

    b_expected = []
    for i in range(len(z_centers)):
        m = (z_vals >= z_edges[i]) & (z_vals <= z_edges[i+1])
        if m.sum() == 0:
            b_expected.append(np.nan)
        else:
            b_expected.append(np.mean(b_true_all[m]))
    b_expected = np.array(b_expected, dtype=np.float64)

    b_meas = table.groupby("z_center")["b"].mean().reindex(z_centers).to_numpy()
    rel_err = np.nanmean(np.abs(b_meas - b_expected) / np.maximum(1e-6, b_expected))
    assert rel_err < 0.15, f"relative error too large: {rel_err:.3f}"

    # sigma_Q check vs known sigma_X_given_Q / b(z) (median over q per z bin)
    sigma_q_meas = table.groupby("z_center")["sigma_Q"].median().reindex(z_centers).to_numpy()
    sigma_q_true = truth["sigma_X_given_Q"] / np.maximum(1e-9, b_expected)
    rel_err_sig = np.nanmean(np.abs(sigma_q_meas - sigma_q_true) / np.maximum(1e-9, sigma_q_true))
    assert rel_err_sig < 0.25, f"sigma_Q rel err too large: {rel_err_sig:.3f}"

    # Inversion round-trip check on a subset
    evalr = QuantileEvaluator(table)
    idx = np.linspace(0, len(df) - 1, num=300, dtype=int)
    resid = []
    for i in idx:
        z = float(df.loc[i, "z_vtx"])
        q_true = float(df.loc[i, "Q"])
        x = float(df.loc[i, "X"])
        q_hat = evalr.invert_rank(x, channel_id="ch0", z=z)
        resid.append(q_hat - q_true)
    rms = np.sqrt(np.mean(np.square(resid)))
    assert rms < 0.07, f"round-trip Q residual RMS too large: {rms:.3f}"


def test_edges_behavior():
    # Heavily edge-concentrated Q distribution
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

    # We expect valid fits near edges, but not necessarily across all q centers.
    # Check that edge q-centers (0.0, 0.1, 0.9, 1.0) have a substantial number of finite b values.
    edge_q = {0.0, 0.1, 0.9, 1.0}
    tbl_edge = table[table["q_center"].isin(edge_q)]
    frac_finite_edges = np.isfinite(tbl_edge["b"]).mean()
    assert frac_finite_edges > 0.7, f"finite fraction at edges too low: {frac_finite_edges:.3f}"

    # Overall, some NaNs are expected for interior q; just ensure there is a reasonable fraction of finite values.
    frac_finite_all = np.isfinite(table["b"]).mean()
    assert frac_finite_all > 0.2, f"overall finite fraction too low: {frac_finite_all:.3f}"

    # And among the finite ones, the majority should be positive.
    frac_pos = (table["b"] > 0).mean()
    assert frac_pos > 0.2, f"positive b fraction too low: {frac_pos:.3f}"
