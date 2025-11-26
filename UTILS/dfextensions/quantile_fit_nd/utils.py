# dfextensions/quantile_fit_nd/utils.py
import numpy as np
from typing import Optional

def discrete_to_uniform_rank_poisson(
        k: np.ndarray,
        lam: float,
        mode: str = "randomized",
        rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """
    Map Poisson counts k ~ Poisson(lam) to U ~ Uniform(0,1).

    mode="randomized" (preferred, exact PIT):
        U = F(k-1) + V * (F(k) - F(k-1)),  V ~ Unif(0,1)
    mode="midrank" (deterministic):
        U = 0.5 * (F(k-1) + F(k))

    Returns U in [0,1].
    """
    k = np.asarray(k, dtype=np.int64)
    if rng is None:
        rng = np.random.default_rng()

    k_max = int(np.max(k)) if k.size else 0
    pmf = np.empty(k_max + 1, dtype=np.float64)
    pmf[0] = np.exp(-lam)
    for j in range(k_max):
        pmf[j + 1] = pmf[j] * lam / (j + 1)

    cdf = np.cumsum(pmf)
    cdf = np.clip(cdf, 0.0, 1.0)

    Fk   = cdf[k]
    Fkm1 = np.where(k > 0, cdf[k - 1], 0.0)

    if mode == "randomized":
        u = rng.random(size=k.size)
        U = Fkm1 + u * (Fk - Fkm1)
    elif mode == "midrank":
        U = 0.5 * (Fkm1 + Fk)
    else:
        raise ValueError(f"unknown mode {mode!r}")

    return np.clip(U, 0.0, 1.0)


def discrete_to_uniform_rank_empirical(
        x: np.ndarray,
        mode: str = "randomized",
        rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """
    Generic discrete -> Uniform(0,1) using the empirical CDF of x.

    For unique value v with mass p_v and cumulative F(v):
      randomized: U ~ Uniform(F(v-), F(v))
      midrank:    U = 0.5 * (F(v-) + F(v))
    """
    x = np.asarray(x)
    n = x.size
    if rng is None:
        rng = np.random.default_rng()
    if n == 0:
        return np.array([], dtype=np.float64)

    uniq, inv = np.unique(x, return_inverse=True)
    counts = np.bincount(inv, minlength=uniq.size)
    cum = np.cumsum(counts)
    F_curr = cum / float(n)
    F_prev = (cum - counts) / float(n)

    if mode == "randomized":
        u = rng.random(size=n)
        U = F_prev[inv] + u * (F_curr[inv] - F_prev[inv])
    elif mode == "midrank":
        U = 0.5 * (F_prev[inv] + F_curr[inv])
    else:
        raise ValueError(f"unknown mode {mode!r}")

    return np.clip(U, 0.0, 1.0)
