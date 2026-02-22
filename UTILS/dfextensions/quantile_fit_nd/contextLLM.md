# contextLLM.md — ND Quantile Linear Fit (quick context)

## TL;DR

We fit a **local linear inverse quantile model** per channel and nuisance grid:
[
X(q,n) \approx a(q_0,n) + b(q_0,n),\underbrace{(q - q_0)}_{\Delta q},\quad b>0
]

* Monotonic in **q** via (b \gt b_\text{min}).
* Smooth in nuisance axes (e.g., **z**, later **η**, **time**) via separable interpolation.
* **Discrete inputs** (tracks/clusters/Poisson): convert to **continuous ranks** (PIT or mid-ranks) *before* fitting.

## Key Files

* `dfextensions/quantile_fit_nd/quantile_fit_nd.py` — core fitter + evaluator
* `dfextensions/quantile_fit_nd/utils.py` — discrete→uniform helpers (PIT/mid-rank)
* `dfextensions/quantile_fit_nd/test_quantile_fit_nd.py` — unit tests + rich diagnostics
* `dfextensions/quantile_fit_nd/bench_quantile_fit_nd.py` — speed & precision benchmark, scaling plots
* `dfextensions/quantile_fit_nd/quantile_fit_nd.md` — full spec (math, API, guarantees)

## Core Assumptions & Policies

* **Δq-centered OLS** per window (|Q-q_0|\le \Delta q), default (\Delta q=0.05).
* **Monotonicity**: enforce (b \ge b_\text{min}) (configurable; “auto” heuristic or fixed).
* **Nuisance interpolation**: separable (linear now; PCHIP later); only q must be monotone.
* **Discrete inputs**:

    * Prefer **randomized PIT**: (U=F(k!-!1)+V,[F(k)-F(k!-!1)]), (V\sim\text{Unif}(0,1)).
    * Or **mid-ranks**: (U=\tfrac{F(k!-!1)+F(k)}{2}) (deterministic).
    * Helpers: `discrete_to_uniform_rank_poisson`, `discrete_to_uniform_rank_empirical`.
* **Uncertainty**: (\sigma_Q \approx \sigma_{X|Q}/|b|). Irreducible vs reducible split available downstream.

## Public API (stable)

```python
from dfextensions.quantile_fit_nd.quantile_fit_nd import fit_quantile_linear_nd, QuantileEvaluator

table = fit_quantile_linear_nd(
    df,                      # columns: channel_id, Q, X, nuisance cols (e.g. z_vtx), is_outlier (optional)
    channel_key="channel_id",
    q_centers=np.arange(0, 1.0001, 0.025),
    dq=0.05,
    nuisance_axes={"z": "z_vtx"},   # later: {"z":"z_vtx","eta":"eta","time":"timestamp"}
    n_bins_axes={"z": 20},
    mask_col="is_outlier",
    b_min_option="auto",           # or "fixed"
)

evalr = QuantileEvaluator(table)
q_hat = evalr.invert_rank(X=123.0, channel_id="ch0", z=1.2)
a, b, sigmaQ = evalr.params(channel_id="ch0", q=0.4, z=0.0)
```

### Output table (columns)

`channel_id, q_center, <axis>_center..., a, b, sigma_Q, sigma_Q_irr (optional), dX_dN (optional), db_d<axis>..., fit_stats(json), timestamp(optional)`

## Quickstart (clean run)

```bash
# 1) Unit tests with diagnostics
pytest -q -s dfextensions/quantile_fit_nd/test_quantile_fit_nd.py

# 2) Benchmark speed + precision + scaling (and plots)
python dfextensions/quantile_fit_nd/bench_quantile_fit_nd.py --plot \
  --dists uniform,poisson,gaussian --Ns 2000,5000,10000,20000,50000 --lam 50
```

* **Interpretation**: `rms_b ~ N^{-1/2}` (α≈−0.5); `rms_rt ~ const` (α≈0) because round-trip error is per-event.

## Reproducibility knobs

* RNG seed fixed in tests/bench (`RNG = np.random.default_rng(123456)`).
* Poisson rank mode: randomized PIT (default) vs mid-rank (deterministic) — switch in test/bench helpers.
* Scaling tolerances (`--scaling_tol`, `--rt_tol`) in the benchmark.

## Known Limitations

* Very edge q windows (near 0 or 1) can be data-sparse; we store fit_stats and may skip non-informative windows.
* With extremely discrete/uniform ranks (without PIT), OLS degenerate: fitter will flag `low_Q_spread`.
* Current interpolation is linear; PCHIP (shape-preserving) can be enabled later.
* Inversion uses a stable linear local model and bracketing; works inside grid, clips at edges.

## Next Steps (nice-to-have)

* Optional robust fit (`fit_mode="huber"`), once outlier flags stabilize.
* Add time as a nuisance axis or do time-sliced parallel fits + chain.
* Export ROOT trees consistently (Parquet/Arrow already supported).
* Add ML-friendly derivative grids (db/dz, db/dη) at higher resolution.

## Troubleshooting

* **ImportError in tests**: ensure `dfextensions/quantile_fit_nd/__init__.py` exists and you run from repo root.
* **.idea committed**: add `.idea/` to repo-level `.gitignore` to avoid IDE noise.
* **Poisson looks “nonsense”**: confirm PIT/mid-rank preprocessing of counts before calling `fit_*`.

---

