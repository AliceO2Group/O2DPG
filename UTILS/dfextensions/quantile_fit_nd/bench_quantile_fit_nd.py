# dfextension/quantile_fit_nd/bench_quantile_fit_nd.py
# Simple timing benchmark across N points, distributions, and grid sizes.
import time
import numpy as np
import pandas as pd

from dfextensions.quantile_fit_nd.quantile_fit_nd import fit_quantile_linear_nd

RNG = np.random.default_rng(1234)


def gen_data(n: int, dist: str = "uniform", sigma_X: float = 0.5):
    if dist == "uniform":
        Q = RNG.uniform(0, 1, size=n)
    elif dist == "poisson":
        lam = 20.0
        m = RNG.poisson(lam, size=n)
        from math import erf
        z = (m + 0.5 - lam) / np.sqrt(max(lam, 1e-6))
        Q = 0.5 * (1.0 + np.array([erf(zi / np.sqrt(2)) for zi in z]))
        Q = np.clip(Q, 0, 1)
    elif dist == "gaussian":
        g = RNG.normal(0.0, 1.0, size=n)
        from math import erf
        Q = 0.5 * (1.0 + np.array([erf(gi / np.sqrt(2)) for gi in g]))
        Q = np.clip(Q, 0, 1)
    else:
        raise ValueError

    z = np.clip(RNG.normal(0.0, 5.0, size=n), -10, 10)
    a = 10.0 + 0.5 * z
    b = (50.0 + 2.0 * z / 10.0).clip(min=5.0)
    X = a + b * Q + RNG.normal(0.0, sigma_X, size=n)
    df = pd.DataFrame({"channel_id": "bench", "Q": Q, "X": X, "z_vtx": z, "is_outlier": False})
    return df


def run_one(n, dist, q_bins=11, z_bins=10):
    df = gen_data(n, dist=dist)
    t0 = time.perf_counter()
    table = fit_quantile_linear_nd(
        df,
        channel_key="channel_id",
        q_centers=np.linspace(0, 1, q_bins),
        dq=0.05,
        nuisance_axes={"z": "z_vtx"},
        n_bins_axes={"z": z_bins},
        mask_col="is_outlier",
        b_min_option="auto",
        fit_mode="ols",
        kappa_w=1.3,
    )
    dt = time.perf_counter() - t0
    return dt, len(table)


def main():
    Ns = [5_000, 50_000, 200_000]
    dists = ["uniform", "poisson", "gaussian"]
    print("N, dist, q_bins, z_bins, secs, rows")
    for n in Ns:
        for dist in dists:
            dt, rows = run_one(n, dist, q_bins=11, z_bins=10)
            print(f"{n:>8}, {dist:>8}, {11:>2}, {10:>2}, {dt:7.3f}, {rows:>6}")


if __name__ == "__main__":
    main()
