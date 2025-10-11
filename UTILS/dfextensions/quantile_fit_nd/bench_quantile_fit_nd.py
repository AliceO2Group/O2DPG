#!/usr/bin/env python3
# dfextensions/quantile_fit_nd/bench_quantile_fit_nd.py
"""
Benchmark speed + precision for fit_quantile_linear_nd with scaling checks.

- Distributions: uniform, poisson (via randomized PIT), gaussian
- q_centers step = 0.025; dq = 0.05 (more points per z-bin)
- Precision metrics per N:
  * rms_b    := sqrt(mean( (b_meas(z) - b_exp(z))^2 )) over informative z-bins
  * rel_err_sigmaQ := median relative error of sigma_Q vs truth per z-bin
  * rms_rt   := round-trip inversion RMS for a random subset of events
- Scaling check:
  * expect alpha_b  ≈ -0.5   (rms_b ∝ N^{-1/2})
  * expect alpha_rt ≈  0.0   (rms_rt roughly flat; per-event noise)
- Prints E*sqrt(N) for rms_b as a constancy sanity check.
- Optional: PNG plots (log-log), CSV export, memory profiling, strict assertions.
"""

import argparse
import json
import warnings
from math import erf, sqrt
import time
import numpy as np
import pandas as pd

from dfextensions.quantile_fit_nd.quantile_fit_nd import (
    fit_quantile_linear_nd,
    QuantileEvaluator,
)
from dfextensions.quantile_fit_nd.utils import discrete_to_uniform_rank_poisson

RNG = np.random.default_rng(123456)


# ----------------------- Synthetic data generation -----------------------

def gen_Q_from_distribution(dist: str, n: int, *, lam: float) -> np.ndarray:
    if dist == "uniform":
        return RNG.uniform(0.0, 1.0, size=n)
    elif dist == "poisson":
        k = RNG.poisson(lam, size=n)
        return discrete_to_uniform_rank_poisson(k, lam, mode="randomized", rng=RNG)
    elif dist == "gaussian":
        z = RNG.normal(0.0, 1.0, size=n)  # standard normal
        cdf = 0.5 * (1.0 + np.array([erf(zi / np.sqrt(2)) for zi in z]))
        return np.clip(cdf, 0.0, 1.0)
    else:
        raise ValueError(f"unknown dist {dist}")


def gen_synthetic_df(
        n: int,
        dist: str,
        *,
        lam: float,
        z_sigma_cm: float = 5.0,
        z_range_cm: float = 10.0,
        sigma_X_given_Q: float = 0.5,
        a0: float = 10.0,
        a1: float = 0.5,
        b0: float = 50.0,
        b1: float = 2.0,
) -> tuple[pd.DataFrame, dict]:
    Q = gen_Q_from_distribution(dist, n, lam=lam)
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
        "lam": lam
    }
    return df, truth


# ----------------------- Helpers for expectations -----------------------

def _edges_from_centers(centers: np.ndarray) -> np.ndarray:
    mid = 0.5 * (centers[1:] + centers[:-1])
    first = centers[0] - (mid[0] - centers[0])
    last = centers[-1] + (centers[-1] - mid[-1])
    return np.concatenate([[first], mid, [last]])


def expected_b_per_zbin_from_sample(df: pd.DataFrame, z_edges: np.ndarray, truth: dict) -> np.ndarray:
    z_vals = df["z_vtx"].to_numpy(np.float64)
    b_true_all = (truth["b0"] + truth["b1"] * z_vals / max(truth["z_range"], 1e-6)).clip(min=5.0)
    b_expected = []
    for i in range(len(z_edges) - 1):
        m = (z_vals >= z_edges[i]) & (z_vals <= z_edges[i+1])
        b_expected.append(np.mean(b_true_all[m]) if m.sum() > 0 else np.nan)
    return np.array(b_expected, dtype=np.float64)


def weights_from_fit_stats(col: pd.Series) -> np.ndarray:
    w = []
    for s in col:
        try:
            d = json.loads(s)
        except Exception:
            d = {}
        w.append(d.get("n_used", np.nan))
    return np.array(w, dtype=float)


# ----------------------------- Benchmark core -----------------------------

def run_one(
        dist: str,
        n: int,
        *,
        q_step=0.025,
        dq=0.05,
        z_bins=20,
        lam=50.0,
        sample_fraction=0.006,
        mem_profile: bool = False,
) -> dict:
    df, truth = gen_synthetic_df(n, dist, lam=lam)
    q_centers = np.arange(0.0, 1.0 + 1e-12, q_step)  # 0..1 inclusive

    def _do_fit():
        return fit_quantile_linear_nd(
            df,
            channel_key="channel_id",
            q_centers=q_centers,
            dq=dq,
            nuisance_axes={"z": "z_vtx"},
            n_bins_axes={"z": z_bins},
        )

    t0 = time.perf_counter()
    if mem_profile:
        try:
            from memory_profiler import memory_usage
            mem_trace, table = memory_usage((_do_fit, ), retval=True, max_iterations=1)
            peak_mem_mb = float(np.max(mem_trace)) if len(mem_trace) else np.nan
        except Exception as e:
            warnings.warn(f"memory_profiler unavailable or failed: {e}")
            table = _do_fit()
            peak_mem_mb = np.nan
    else:
        table = _do_fit()
        peak_mem_mb = np.nan
    t_fit = time.perf_counter() - t0

    # Expected b per z-bin (from sample)
    z_centers = np.sort(table["z_center"].unique())
    z_edges = _edges_from_centers(z_centers)
    b_exp = expected_b_per_zbin_from_sample(df, z_edges, truth)

    # Measured b per z-bin (weighted by window n_used)
    b_meas_w = np.full_like(b_exp, np.nan, dtype=float)
    for i, zc in enumerate(z_centers):
        g = table[table["z_center"] == zc]
        if g.empty:
            continue
        w = weights_from_fit_stats(g["fit_stats"])
        ok = np.isfinite(g["b"].to_numpy()) & (w > 0)
        if ok.sum() == 0:
            continue
        bvals = g["b"].to_numpy()[ok]
        ww = w[ok]
        b_meas_w[i] = np.average(bvals, weights=ww)

    # Informative mask
    m = np.isfinite(b_meas_w) & np.isfinite(b_exp)

    # Slope error metrics
    rms_b = float(np.sqrt(np.nanmean((b_meas_w[m] - b_exp[m]) ** 2))) if m.any() else np.nan

    # sigma_Q check (median rel err by z-bin)
    sigma_q_true = truth["sigma_X_given_Q"] / np.maximum(1e-9, b_exp)
    sigma_q_meas = table.groupby("z_center")["sigma_Q"].median().reindex(z_centers).to_numpy()
    mk = np.isfinite(sigma_q_true) & np.isfinite(sigma_q_meas)
    rel_err_sigmaQ = float(np.nanmean(np.abs(sigma_q_meas[mk] - sigma_q_true[mk]) /
                                      np.maximum(1e-9, sigma_q_true[mk]))) if mk.any() else np.nan

    # Round-trip inversion RMS (sample to limit CPU)
    k = max(1, int(round(sample_fraction * len(df))))
    idx = RNG.choice(len(df), size=min(k, len(df)), replace=False)
    evalr = QuantileEvaluator(table)
    resid = []
    for ii in idx:
        z = float(df.loc[ii, "z_vtx"])
        q_true = float(df.loc[ii, "Q"])
        x = float(df.loc[ii, "X"])
        q_hat = evalr.invert_rank(x, channel_id="ch0", z=z)
        resid.append(q_hat - q_true)
    resid = np.array(resid, dtype=float)
    rms_rt = float(np.sqrt(np.mean(np.square(resid)))) if resid.size else np.nan

    return dict(
        dist=dist, N=int(n),
        lam=float(lam),
        q_step=float(q_step), dq=float(dq), z_bins=int(z_bins),
        t_fit=float(t_fit),
        rms_b=rms_b,
        rel_err_sigmaQ=rel_err_sigmaQ,
        rms_rt=rms_rt,
        n_z_inf=int(np.sum(m)),
        peak_mem_mb=peak_mem_mb,
    )


def fit_log_slope(xs: np.ndarray, ys: np.ndarray) -> float:
    # Fit log(ys) ~ alpha * log(xs) + c ; return alpha
    m = np.isfinite(xs) & np.isfinite(ys) & (ys > 0)
    if m.sum() < 2:
        warnings.warn("Insufficient points for scaling slope fit.", RuntimeWarning)
        return np.nan
    lx = np.log(xs[m].astype(float))
    ly = np.log(ys[m].astype(float))
    A = np.column_stack([lx, np.ones_like(lx)])
    sol, _, _, _ = np.linalg.lstsq(A, ly, rcond=None)
    return float(sol[0])


def _plot_scaling(res: pd.DataFrame, dists: list[str]):
    try:
        import matplotlib.pyplot as plt
    except Exception as e:
        warnings.warn(f"--plot requested but matplotlib unavailable: {e}")
        return
    for dist in dists:
        sub = res[res["dist"] == dist].sort_values("N")
        if sub.empty:
            continue
        fig, ax = plt.subplots(figsize=(6.2, 4.2), dpi=140)
        ax.loglog(sub["N"], sub["rms_b"], marker="o", label="rms_b")
        ax.loglog(sub["N"], sub["rms_rt"], marker="s", label="rms_rt")
        ax.set_title(f"Scaling — {dist}")
        ax.set_xlabel("N events")
        ax.set_ylabel("Error")
        ax.grid(True, which="both", ls=":")
        ax.legend()
        fig.tight_layout()
        fig.savefig(f"bench_scaling_{dist}.png")
        plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--Ns", type=str, default="2000,5000,10000,20000,50000",
                    help="comma-separated N list")
    ap.add_argument("--dists", type=str, default="uniform,poisson,gaussian",
                    help="comma-separated distributions")
    ap.add_argument("--lam", type=float, default=50.0, help="Poisson mean λ")
    ap.add_argument("--q_step", type=float, default=0.025, help="q_center step")
    ap.add_argument("--dq", type=float, default=0.05, help="Δq window")
    ap.add_argument("--z_bins", type=int, default=20, help="# z bins")
    ap.add_argument("--sample_fraction", type=float, default=0.006, help="fraction for round-trip sampling")
    ap.add_argument("--plot", action="store_true", help="save log-log plots as PNGs")
    ap.add_argument("--save_csv", type=str, default="", help="path to save CSV results")
    ap.add_argument("--mem_profile", action="store_true", help="profile peak memory (if memory_profiler available)")
    ap.add_argument("--strict", action="store_true", help="raise AssertionError on scaling deviations")
    ap.add_argument("--scaling_tol", type=float, default=0.20, help="tolerance for |alpha_b + 0.5|")
    ap.add_argument("--rt_tol", type=float, default=0.10, help="tolerance for |alpha_rt - 0.0|")
    args = ap.parse_args()

    Ns = [int(s) for s in args.Ns.split(",") if s.strip()]
    dists = [s.strip() for s in args.dists.split(",") if s.strip()]

    print(f"Distributions: {', '.join(dists)}  (Poisson uses PIT, λ={args.lam})")
    print(f"q_step={args.q_step}, dq={args.dq}, z_bins={args.z_bins}, sample_fraction={args.sample_fraction}\n")

    rows = []
    for dist in dists:
        print(f"=== Benchmark: {dist} ===")
        for N in Ns:
            r = run_one(
                dist, N,
                q_step=args.q_step, dq=args.dq, z_bins=args.z_bins,
                lam=args.lam, sample_fraction=args.sample_fraction,
                mem_profile=args.mem_profile,
            )
            rows.append(r)
            print(f"N={N:7d} | t_fit={r['t_fit']:.3f}s | rms_b={r['rms_b']:.5f} "
                  f"(rms_b*√N={r['rms_b']*sqrt(N):.5f}) | σQ_rel={r['rel_err_sigmaQ']:.3f} | "
                  f"rt_rms={r['rms_rt']:.5f} (rt_rms*√N={r['rms_rt']*sqrt(N):.5f}) | "
                  f"z_inf={r['n_z_inf']} | mem={r['peak_mem_mb']:.1f}MB")

    res = pd.DataFrame(rows)

    # Scaling summary per distribution
    print("\n=== Scaling summary (expect: α_b ≈ -0.5, α_rt ≈ 0.0) ===")
    summary_rows = []
    for dist in dists:
        sub = res[res["dist"] == dist].sort_values("N")
        a_b = fit_log_slope(sub["N"].to_numpy(), sub["rms_b"].to_numpy())
        a_rt = fit_log_slope(sub["N"].to_numpy(), sub["rms_rt"].to_numpy())
        const_b = (sub["rms_b"] * np.sqrt(sub["N"])).to_numpy()
        print(f"{dist:8s} | α_b={a_b: .3f} (→ -0.5) | α_rt={a_rt: .3f} (→  0.0) "
              f"| mean(rms_b√N)={np.nanmean(const_b):.5f}")
        summary_rows.append({"dist": dist, "alpha_rms_b": a_b, "alpha_rms_rt": a_rt})
    summary = pd.DataFrame(summary_rows)

    # CSV export
    if args.save_csv:
        res.to_csv(args.save_csv, index=False)
        print(f"\nSaved CSV to: {args.save_csv}")

    # Plots
    if args.plot:
        _plot_scaling(res, dists)
        print("Saved PNG plots: bench_scaling_{dist}.png")

    # Checks (warn by default; --strict to raise)
    for dist in dists:
        a_b = float(summary[summary["dist"] == dist]["alpha_rms_b"].iloc[0])
        a_rt = float(summary[summary["dist"] == dist]["alpha_rms_rt"].iloc[0])
        ok_b  = np.isfinite(a_b)  and (abs(a_b + 0.5) <= args.scaling_tol)
        ok_rt = np.isfinite(a_rt) and (abs(a_rt - 0.0) <= args.rt_tol)
        msg = f"SCALING [{dist}]  α_b={a_b:.3f} vs -0.5 (tol {args.scaling_tol}) | α_rt={a_rt:.3f} vs 0.0 (tol {args.rt_tol})"
        if ok_b and ok_rt:
            print("PASS - " + msg)
        else:
            if args.strict:
                raise AssertionError("FAIL - " + msg)
            warnings.warn("WARN - " + msg)


if __name__ == "__main__":
    main()
