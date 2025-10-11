import json
import numpy as np
import pandas as pd
import pytest

from dfextensions.quantile_fit_nd.quantile_fit_nd import (
    fit_quantile_linear_nd,
    QuantileEvaluator,
)
from dfextensions.quantile_fit_nd.utils import discrete_to_uniform_rank_poisson


RNG = np.random.default_rng(42)


def gen_Q_from_distribution(dist: str, n: int, params: dict) -> np.ndarray:
    if dist == "uniform":
        return RNG.uniform(0.0, 1.0, size=n)
    elif dist == "poisson":
        lam = params.get("lam", 20.0)
        k = RNG.poisson(lam, size=n)
        return discrete_to_uniform_rank_poisson(k, lam, mode="randomized", rng=RNG)
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


def _expected_b_per_zbin_from_sample(df: pd.DataFrame, z_edges: np.ndarray, truth: dict) -> np.ndarray:
    z_vals = df["z_vtx"].to_numpy(np.float64)
    b_true_all = (truth["b0"] + truth["b1"] * z_vals / max(truth["z_range"], 1e-6)).clip(min=5.0)
    b_expected = []
    for i in range(len(z_edges) - 1):
        m = (z_vals >= z_edges[i]) & (z_vals <= z_edges[i+1])
        b_expected.append(np.mean(b_true_all[m]) if m.sum() > 0 else np.nan)
    return np.array(b_expected, dtype=np.float64)


def _predicted_se_b_per_zbin(df: pd.DataFrame, z_edges: np.ndarray, q_centers: np.ndarray, dq: float, sigma_X_given_Q: float) -> np.ndarray:
    Q_all = df["Q"].to_numpy(np.float64)
    z_all = df["z_vtx"].to_numpy(np.float64)

    se_bins = np.full(len(z_edges) - 1, np.nan, dtype=np.float64)

    for i in range(len(z_edges) - 1):
        m_z = (z_all >= z_edges[i]) & (z_all <= z_edges[i+1])
        if m_z.sum() < 10:
            continue
        Qz = Q_all[m_z]

        se_ws = []
        for q0 in q_centers:
            in_win = (Qz >= q0 - dq) & (Qz <= q0 + dq)
            n_win = int(in_win.sum())
            if n_win < 6:
                continue
            dq_i = Qz[in_win] - q0
            sxx = float(np.sum((dq_i - dq_i.mean())**2))
            if sxx <= 0:
                continue
            se_b = sigma_X_given_Q / np.sqrt(max(sxx, 1e-12))
            se_ws.append(se_b)

        if len(se_ws) == 0:
            continue
        se_bins[i] = float(np.sqrt(np.mean(np.square(se_ws))))  # conservative RMS

    return se_bins


def _json_stats_to_arrays(subtable: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Extract weights (n_used) and clipped flags from fit_stats JSON."""
    n_used = []
    clipped = []
    for s in subtable["fit_stats"]:
        try:
            d = json.loads(s)
        except Exception:
            d = {}
        n_used.append(d.get("n_used", np.nan))
        clipped.append(bool(d.get("clipped", False)))
    return np.array(n_used, dtype=float), np.array(clipped, dtype=bool)


@pytest.mark.parametrize("dist", ["uniform", "poisson", "gaussian"])
@pytest.mark.parametrize("n_points", [5_000, 50_000])
def test_fit_and_sigmaQ(dist, n_points):
    df, truth = gen_synthetic_df(n_points, dist=dist)
    q_centers = np.linspace(0.0, 1.0, 11)
    dq = 0.05

    table = fit_quantile_linear_nd(
        df,
        channel_key="channel_id",
        q_centers=q_centers,
        dq=dq,
        nuisance_axes={"z": "z_vtx"},
        n_bins_axes={"z": 10},
    )
    assert not table.empty
    assert {"a", "b", "sigma_Q", "z_center", "q_center", "fit_stats"}.issubset(table.columns)

    # Expected b(z) from sample, using fit's z-bin edges
    z_centers = np.sort(table["z_center"].unique())
    z_edges = _edges_from_centers(z_centers)
    b_expected = _expected_b_per_zbin_from_sample(df, z_edges, truth)

    # Weighted measured b(z) using window counts (n_used) per (z,q) cell
    b_meas_w = np.full_like(b_expected, np.nan, dtype=float)
    se_pred = _predicted_se_b_per_zbin(df, z_edges, q_centers, dq, sigma_X_given_Q=truth["sigma_X_given_Q"])
    print("\n=== Per–z-bin diagnostics (dist={}, N={}) ===".format(dist, n_points))
    print("z_center | b_expected | b_meas_w | SE_pred(6σ) | |Δb|/SE6 | windows | clipped%")

    for i, zc in enumerate(z_centers):
        g = table[table["z_center"] == zc]
        if g.empty:
            continue
        weights, clipped = _json_stats_to_arrays(g)
        # Only use rows with finite b and positive weights
        ok = np.isfinite(g["b"].to_numpy()) & (weights > 0)
        if ok.sum() == 0:
            continue
        w = weights[ok]
        bvals = g["b"].to_numpy()[ok]
        b_meas_w[i] = np.average(bvals, weights=w)

        # Diagnostics
        se6 = 6.0 * se_pred[i] if np.isfinite(se_pred[i]) else np.nan
        db = abs((b_meas_w[i] - b_expected[i])) if np.isfinite(b_expected[i]) and np.isfinite(b_meas_w[i]) else np.nan
        ratio = (db / se6) if (np.isfinite(db) and np.isfinite(se6) and se6 > 0) else np.nan
        clip_pct = 100.0 * (clipped[ok].mean() if ok.size else 0.0)

        print(f"{zc:7.3f} | {b_expected[i]:10.3f} | {b_meas_w[i]:8.3f} | {se6:10.3f} | {ratio:7.3f} | {ok.sum():7d} | {clip_pct:7.2f}")

    # 6σ check across valid bins
    ok_mask = np.isfinite(b_expected) & np.isfinite(b_meas_w) & np.isfinite(se_pred)
    assert ok_mask.any(), "No valid z-bins to compare."
    abs_diff = np.abs(b_meas_w[ok_mask] - b_expected[ok_mask])
    bound6 = 6.0 * se_pred[ok_mask]
    # report worst-case ratio for debug
    worst = float(np.nanmax(abs_diff / np.maximum(bound6, 1e-12)))
    assert np.all(abs_diff <= (bound6 + 1e-12)), f"6σ slope check failed in at least one z-bin: max(|Δb|/(6·SE)) = {worst:.2f}"

    # sigma_Q vs truth (pragmatic bound)
    sigma_q_true = truth["sigma_X_given_Q"] / np.maximum(1e-9, b_expected)
    sigma_q_meas = table.groupby("z_center")["sigma_Q"].median().reindex(z_centers).to_numpy()
    m_ok = np.isfinite(sigma_q_true) & np.isfinite(sigma_q_meas)
    rel_err_sig = np.nanmean(np.abs(sigma_q_meas[m_ok] - sigma_q_true[m_ok]) / np.maximum(1e-9, sigma_q_true[m_ok]))
    print(f"sigma_Q: mean relative error = {rel_err_sig:.3f}")
    assert rel_err_sig < 0.30, f"sigma_Q rel err too large: {rel_err_sig:.3f}"

    # Round-trip Q->X->Q diagnostics
    evalr = QuantileEvaluator(table)
    idx = np.linspace(0, len(df) - 1, num=300, dtype=int)
    resid = []
    for irow in idx:
        z = float(df.loc[irow, "z_vtx"])
        q_true = float(df.loc[irow, "Q"])
        x = float(df.loc[irow, "X"])
        q_hat = evalr.invert_rank(x, channel_id="ch0", z=z)
        resid.append(q_hat - q_true)
    resid = np.array(resid, dtype=float)
    rms = float(np.sqrt(np.mean(np.square(resid))))
    mad = float(np.median(np.abs(resid - np.median(resid))))
    q10, q90 = float(np.quantile(resid, 0.10)), float(np.quantile(resid, 0.90))
    print(f"Round-trip residuals: RMS={rms:.4f}, MAD={mad:.4f}, p10={q10:.4f}, p90={q90:.4f}")
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
    q_centers = np.linspace(0, 1, 11)
    dq = 0.05
    n_zbins = 6

    table = fit_quantile_linear_nd(
        df, channel_key="channel_id",
        q_centers=q_centers, dq=dq,
        nuisance_axes={"z": "z_vtx"}, n_bins_axes={"z": n_zbins}
    )

    z_centers = np.sort(table["z_center"].unique())
    z_edges = _edges_from_centers(z_centers)
    Q_all = df["Q"].to_numpy(np.float64)
    z_all = df["z_vtx"].to_numpy(np.float64)

    edge_q = [0.0, 0.1, 0.9, 1.0]
    feasible_flags = []
    for q0 in edge_q:
        for i in range(len(z_edges) - 1):
            m_z = (z_all >= z_edges[i]) & (z_all <= z_edges[i+1])
            Qz = Q_all[m_z]
            n_win = int(((Qz >= q0 - dq) & (Qz <= q0 + dq)).sum())
            feasible_flags.append(n_win >= 6)
    feasible_flags = np.array(feasible_flags, dtype=bool)

    predicted_frac = feasible_flags.mean()
    measured_tbl = table[table["q_center"].isin(edge_q)]
    measured_frac = np.isfinite(measured_tbl["b"]).mean()

    N = feasible_flags.size
    se_binom = np.sqrt(max(predicted_frac * (1 - predicted_frac) / max(N, 1), 1e-12))
    lb = max(0.0, predicted_frac - 6.0 * se_binom)

    print("\n=== Edge coverage diagnostics ===")
    print(f"predicted feasible fraction = {predicted_frac:.3f}, 6σ lower bound = {lb:.3f}, measured finite fraction = {measured_frac:.3f}")

    assert measured_frac >= lb, (
        f"finite fraction at edges too low: measured {measured_frac:.3f}, "
        f"predicted {predicted_frac:.3f}, 6σ lower bound {lb:.3f}"
    )

    frac_pos = (measured_tbl["b"] > 0).mean()
    print(f"edge positive-b fraction = {frac_pos:.3f}")
    assert frac_pos > 0.2, f"positive b fraction too low: {frac_pos:.3f}"
