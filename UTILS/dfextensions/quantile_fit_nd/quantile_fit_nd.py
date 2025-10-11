# dfextension/quantile_fit_nd/quantile_fit_nd.py
# v3.1 — ND quantile linear fitting (Δq-centered), separable interpolation, evaluator, and I/O.
# Dependencies: numpy, pandas (optional: pyarrow, fastparquet, scipy for PCHIP)
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Sequence, Any
import json
import warnings

import numpy as np
import pandas as pd


# ----------------------------- Utilities ---------------------------------

def _ensure_array(x) -> np.ndarray:
    return np.asarray(x, dtype=np.float64)


def _bin_edges_from_centers(centers: np.ndarray) -> np.ndarray:
    """Create edges from sorted centers (extrapolate half-steps at ends)."""
    c = _ensure_array(centers)
    mid = 0.5 * (c[1:] + c[:-1])
    first = c[0] - (mid[0] - c[0])
    last = c[-1] + (c[-1] - mid[-1])
    return np.concatenate([[first], mid, [last]])


def _build_uniform_centers(values: np.ndarray, n_bins: int) -> np.ndarray:
    vmin, vmax = np.nanmin(values), np.nanmax(values)
    if vmin == vmax:
        # degenerate: single bin at that value
        return np.array([vmin], dtype=np.float64)
    return np.linspace(vmin, vmax, n_bins, dtype=np.float64)


def _assign_bin_indices(values: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """Return integer indices mapping each value to nearest center (safe, inclusive edges)."""
    edges = _bin_edges_from_centers(centers)
    idx = np.searchsorted(edges, values, side="right") - 1
    idx = np.clip(idx, 0, len(centers) - 1)
    return idx.astype(np.int32)


def _linear_interp_1d(xc: np.ndarray, yc: np.ndarray, x: float) -> float:
    """Piecewise-linear interpolation clamped to endpoints. yc may contain NaNs -> nearest good."""
    xc = _ensure_array(xc)
    yc = _ensure_array(yc)
    good = np.isfinite(yc)
    if good.sum() == 0:
        return np.nan
    xcg, ycg = xc[good], yc[good]
    if x <= xcg[0]:
        return float(ycg[0])
    if x >= xcg[-1]:
        return float(ycg[-1])
    j = np.searchsorted(xcg, x)
    x0, x1 = xcg[j-1], xcg[j]
    y0, y1 = ycg[j-1], ycg[j]
    t = (x - x0) / max(x1 - x0, 1e-12)
    return float((1 - t) * y0 + t * y1)


def _local_fit_delta_q(Q: np.ndarray, X: np.ndarray, q0: float) -> Tuple[float, float, float, int, Dict[str, float]]:
    """
    OLS for X = a + b*(Q - q0). Returns (a, b, sigma_X_given_Q, n_used, stats).
    """
    n = Q.size
    stats = {}
    if n < 6:
        return np.nan, np.nan, np.nan, n, {"n_used": n, "ok": False}
    dq = Q - q0
    dq0 = dq.mean()
    x0 = X.mean()
    dq_c = dq - dq0
    x_c = X - x0
    sxx = float(np.dot(dq_c, dq_c))
    if sxx <= 0:
        return np.nan, np.nan, np.nan, n, {"n_used": n, "ok": False}
    b = float(np.dot(dq_c, x_c) / sxx)
    a = x0 - b * dq0
    res = X - (a + b * (Q - q0))
    sig = float(np.sqrt(np.mean(res * res)))
    stats = {"n_used": n, "rms": float(np.sqrt(np.mean(res**2))), "ok": True}
    return a, b, sig, n, stats


def _sigma_Q_from_sigmaX(b: float, sigma_X_given_Q: float) -> float:
    if not np.isfinite(b) or b == 0:
        return np.nan
    return float(abs(sigma_X_given_Q) / abs(b))


def _auto_b_min(sigma_X: float, dq: float, c: float = 0.25) -> float:
    # heuristic to avoid explosive Q when amplitude scatter is large vs window
    return float(max(1e-12, c * sigma_X / max(2.0 * dq, 1e-12)))


# ------------------------------ Fit API ----------------------------------

def fit_quantile_linear_nd(
        df: pd.DataFrame,
        *,
        channel_key: str = "channel_id",
        q_centers: np.ndarray = np.linspace(0.0, 1.0, 11),
        dq: float = 0.05,
        nuisance_axes: Dict[str, str] = None,     # e.g. {"z": "z_vtx", "eta": "eta"}
        n_bins_axes: Dict[str, int] = None,       # e.g. {"z": 10}
        mask_col: Optional[str] = "is_outlier",
        b_min_option: str = "auto",               # "auto" or "fixed"
        b_min_value: float = 1e-6,
        fit_mode: str = "ols",
        kappa_w: float = 1.3,
        timestamp: Optional[Any] = None,
) -> pd.DataFrame:
    """
    Fit local linear inverse-CDF per channel, per (q_center, nuisance bins).
    Returns a flat DataFrame (calibration table) with coefficients and diagnostics.

    Columns expected in df:
      - channel_key, Q, X, and nuisance columns per nuisance_axes dict.
      - mask_col (optional): True rows are excluded.

    Notes:
      - Degree-1 only, Δq-centered model: X = a + b*(Q - q_center).
      - b>0 enforced via floor (auto/fixed).
      - sigma_Q = sigma_X|Q / |b|
      - sigma_Q_irr left NaN unless a multiplicity model is provided downstream.
    """
    if nuisance_axes is None:
        nuisance_axes = {}
    if n_bins_axes is None:
        n_bins_axes = {ax: 10 for ax in nuisance_axes}

    df = df.copy()

    # Ensure a boolean keep-mask exists
    if mask_col is None or mask_col not in df.columns:
        df["_mask_keep"] = True
        mask_col_use = "_mask_keep"
    else:
        mask_col_use = mask_col

    # ------------------------ build nuisance binning ------------------------
    axis_to_centers: Dict[str, np.ndarray] = {}
    axis_to_idxcol: Dict[str, str] = {}
    for ax, col in nuisance_axes.items():
        centers = _build_uniform_centers(df[col].to_numpy(np.float64), int(n_bins_axes.get(ax, 10)))
        axis_to_centers[ax] = centers
        idxcol = f"__bin_{ax}"
        df[idxcol] = _assign_bin_indices(df[col].to_numpy(np.float64), centers)
        axis_to_idxcol[ax] = idxcol

    bin_cols = [axis_to_idxcol[a] for a in nuisance_axes]
    out_rows: list[dict] = []

    # --------------------------- iterate channels --------------------------
    for ch_val, df_ch in df.groupby(channel_key, sort=False, dropna=False):
        # iterate bins of nuisance axes
        if bin_cols:
            if len(bin_cols) == 1:
                gb = df_ch.groupby(bin_cols[0], sort=False, dropna=False)  # avoid FutureWarning
            else:
                gb = df_ch.groupby(bin_cols, sort=False, dropna=False)
        else:
            df_ch = df_ch.copy()
            df_ch["__bin_dummy__"] = 0
            gb = df_ch.groupby(["__bin_dummy__"], sort=False, dropna=False)

        for bin_key, df_cell in gb:
            if not isinstance(bin_key, tuple):
                bin_key = (bin_key,)

            # select non-outliers
            keep = (df_cell[mask_col_use] == False) if mask_col_use in df_cell.columns else np.ones(len(df_cell), dtype=bool)
            n_keep = int(keep.sum())
            masked_frac = 1.0 - float(keep.mean())

            X_all = df_cell.loc[keep, "X"].to_numpy(np.float64)
            Q_all = df_cell.loc[keep, "Q"].to_numpy(np.float64)

            # If too few points overall, emit NaNs for all q-centers in this cell
            if n_keep < 6:
                for q0 in q_centers:
                    row = {
                        "channel_id": ch_val,
                        "q_center": float(q0),
                        "a": np.nan, "b": np.nan, "sigma_Q": np.nan,
                        "sigma_Q_irr": np.nan, "dX_dN": np.nan,
                        "fit_stats": json.dumps({"n_used": n_keep, "ok": False, "masked_frac": float(masked_frac)})
                    }
                    for ax_i, ax in enumerate(nuisance_axes):
                        row[f"{ax}_center"] = float(axis_to_centers[ax][bin_key[ax_i]])
                    if timestamp is not None:
                        row["timestamp"] = timestamp
                    out_rows.append(row)
                continue

            # -------------------- per-q_center sliding window --------------------
            for q0 in q_centers:
                in_win = (Q_all >= q0 - dq) & (Q_all <= q0 + dq)
                n_win = int(in_win.sum())

                # window-local auto b_min (compute BEFORE branching to avoid NameError)
                if b_min_option == "auto":
                    if n_win > 1:
                        sigmaX_win = float(np.std(X_all[in_win]))
                    else:
                        # fallback to overall scatter in this cell
                        sigmaX_win = float(np.std(X_all)) if X_all.size > 1 else 0.0
                    bmin = _auto_b_min(sigmaX_win, dq)
                else:
                    bmin = float(b_min_value)

                if n_win < 6:
                    row = {
                        "channel_id": ch_val,
                        "q_center": float(q0),
                        "a": np.nan, "b": np.nan, "sigma_Q": np.nan,
                        "sigma_Q_irr": np.nan, "dX_dN": np.nan,
                        "fit_stats": json.dumps({
                            "n_used": n_win, "ok": False,
                            "masked_frac": float(masked_frac),
                            "b_min": float(bmin)
                        })
                    }
                else:
                    a, b, sigX, n_used, stats = _local_fit_delta_q(Q_all[in_win], X_all[in_win], q0)

                    # monotonicity floor
                    if not np.isfinite(b) or b <= 0.0:
                        b = bmin
                        clipped = True
                    else:
                        clipped = False

                    sigma_Q = _sigma_Q_from_sigmaX(b, sigX)
                    fit_stats = {
                        "n_used": int(n_used),
                        "ok": bool(stats.get("ok", True)),
                        "rms": float(stats.get("rms", np.nan)),
                        "masked_frac": float(masked_frac),
                        "clipped": bool(clipped),
                        "b_min": float(bmin),
                    }
                    row = {
                        "channel_id": ch_val,
                        "q_center": float(q0),
                        "a": float(a), "b": float(b), "sigma_Q": float(sigma_Q),
                        "sigma_Q_irr": np.nan, "dX_dN": np.nan,
                        "fit_stats": json.dumps(fit_stats)
                    }

                # write nuisance centers and optional timestamp
                for ax_i, ax in enumerate(nuisance_axes):
                    row[f"{ax}_center"] = float(axis_to_centers[ax][bin_key[ax_i]])
                if timestamp is not None:
                    row["timestamp"] = timestamp
                out_rows.append(row)

    table = pd.DataFrame(out_rows)

    # ------------------------------ metadata ------------------------------
    table.attrs.update({
        "model": "X = a + b*(Q - q_center)",
        "dq": float(dq),
        "b_min_option": b_min_option,
        "b_min_value": float(b_min_value),
        "fit_mode": fit_mode,
        "kappa_w": float(kappa_w),
        "axes": ["q"] + list(nuisance_axes.keys()),
        "channel_key": channel_key,
    })

    # --------- finite-difference derivatives along nuisance axes ----------
    for ax in nuisance_axes:
        der_col = f"db_d{ax}"
        table[der_col] = np.nan
        for (ch, q0), g in table.groupby(["channel_id", "q_center"], sort=False):
            centers = np.unique(g[f"{ax}_center"].to_numpy(np.float64))
            if centers.size < 2:
                continue
            gg = g.sort_values(f"{ax}_center")
            bvals = gg["b"].to_numpy(np.float64)
            xc = gg[f"{ax}_center"].to_numpy(np.float64)
            d = np.full_like(bvals, np.nan)
            if bvals.size >= 2:
                d[0] = (bvals[1] - bvals[0]) / max(xc[1] - xc[0], 1e-12)
                d[-1] = (bvals[-1] - bvals[-2]) / max(xc[-1] - xc[-2], 1e-12)
            if bvals.size >= 3:
                for i in range(1, bvals.size - 1):
                    d[i] = (bvals[i+1] - bvals[i-1]) / max(xc[i+1] - xc[i-1], 1e-12)
            table.loc[gg.index, der_col] = d

    return table


# --------------------------- Evaluator API -------------------------------

@dataclass
class QuantileEvaluator:
    table: pd.DataFrame

    def __post_init__(self):
        self._build_index()

    def _build_index(self):
        t = self.table
        if "channel_id" not in t.columns or "q_center" not in t.columns:
            raise ValueError("Calibration table missing 'channel_id' or 'q_center'.")
        # detect nuisance axes from columns ending with _center, but EXCLUDE q_center
        self.axes = []
        for c in t.columns:
                if c.endswith("_center") and c != "q_center":
                    self.axes.append(c[:-7])  # strip '_center'
        self.q_centers = np.sort(t["q_center"].unique())
        # map channel -> nested dicts of arrays over (q, axis1, axis2, ...)
        self.store: Dict[Any, Dict[str, Any]] = {}
        for ch, gch in t.groupby("channel_id", sort=False):
            # build sorted grids per axis
            axis_centers = {ax: np.sort(gch[f"{ax}_center"].unique()) for ax in self.axes}
            # allocate arrays
            shape = (len(self.q_centers),) + tuple(len(axis_centers[ax]) for ax in self.axes)
            A = np.full(shape, np.nan, dtype=np.float64)
            B = np.full(shape, np.nan, dtype=np.float64)
            SQ = np.full(shape, np.nan, dtype=np.float64)
            # fill
            for _, row in gch.iterrows():
                qi = int(np.where(self.q_centers == row["q_center"])[0][0])
                idx = [qi]
                for ax in self.axes:
                    ci = int(np.where(axis_centers[ax] == row[f"{ax}_center"])[0][0])
                    idx.append(ci)
                idx = tuple(idx)
                A[idx] = row["a"]
                B[idx] = row["b"]
                SQ[idx] = row["sigma_Q"]
            self.store[ch] = {"A": A, "B": B, "SQ": SQ, "axes": axis_centers}

    def _interp_nuisance_vector(self, arr: np.ndarray, coords: Dict[str, float]) -> np.ndarray:
        """Reduce arr over nuisance axes via chained 1D linear interpolation; returns vector over q."""
        out = arr
        for ax_i, ax in enumerate(self.axes, start=1):
            centers = self.store_axis_centers(ax)
            # move this axis to last
            out = np.moveaxis(out, ax_i, -1)
            shp = out.shape[:-1]
            reduced = np.empty(shp, dtype=np.float64)
            for idx in np.ndindex(shp):
                yc = out[idx]
                reduced[idx] = _linear_interp_1d(centers, yc, coords.get(ax, float(centers[len(centers)//2])))
            out = reduced
        # out shape -> (len(q_centers),)
        return out

    def store_axis_centers(self, ax: str) -> np.ndarray:
        # assumes all channels share same set; take from first channel
        for ch in self.store:
            return self.store[ch]["axes"][ax]
        return np.array([], dtype=np.float64)

    def params(self, *, channel_id: Any, q: float, **coords) -> Tuple[float, float, float]:
        item = self.store.get(channel_id)
        if item is None:
            return np.nan, np.nan, np.nan
        a_vec = self._interp_nuisance_vector(item["A"], coords)  # vector over q-centers
        b_vec = self._interp_nuisance_vector(item["B"], coords)
        s_vec = self._interp_nuisance_vector(item["SQ"], coords)
        # interpolate across q-centers
        a = _linear_interp_1d(self.q_centers, a_vec, q)
        b = _linear_interp_1d(self.q_centers, b_vec, q)
        s = _linear_interp_1d(self.q_centers, s_vec, q)
        # monotonicity safeguard (clip b)
        if not np.isfinite(b) or b <= 0.0:
            # try minimal positive value to avoid NaN
            b = 1e-9
        return float(a), float(b), float(s)

    def invert_rank(self, X: float, *, channel_id: Any, **coords) -> float:
        """
        Invert amplitude -> rank using the Δq-centered grid with robust fixed-point iteration.

        Steps:
          - Build candidate Q̂(q0) = q0 + (X - a(q0)) / b(q0) over all q-centers (at given nuisances).
          - Choose the self-consistent candidate (min |Q̂ - q0|) as the initial guess.
          - Run damped fixed-point iteration: q <- q + λ * (X - a(q)) / b(q), with λ in (0,1].
          - Clamp to [0,1]; stop when |Δq| < tol or max_iter reached.

        Returns:
          q in [0,1], or NaN if unavailable.
        """
        item = self.store.get(channel_id)
        if item is None:
            return np.nan

        a_vec = self._interp_nuisance_vector(item["A"], coords)  # shape (n_q,)
        b_vec = self._interp_nuisance_vector(item["B"], coords)  # shape (n_q,)
        qc = self.q_centers

        # Candidate ranks from all centers
        b_safe = np.where(np.isfinite(b_vec) & (b_vec > 0.0), b_vec, np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            q_candidates = qc + (X - a_vec) / b_safe

        dif = np.abs(q_candidates - qc)
        if not np.any(np.isfinite(dif)):
            return np.nan
        j0 = int(np.nanargmin(dif))
        q = float(np.clip(q_candidates[j0], 0.0, 1.0))

        # Damped fixed-point
        max_iter = 10
        tol = 1e-6
        lam = 0.8  # damping
        for _ in range(max_iter):
            a = _linear_interp_1d(qc, a_vec, q)
            b = _linear_interp_1d(qc, b_vec, q)
            if not np.isfinite(a) or not np.isfinite(b) or b <= 0.0:
                break
            step = (X - a) / b
            if not np.isfinite(step):
                break
            q_new = float(np.clip(q + lam * step, 0.0, 1.0))
            if abs(q_new - q) < tol:
                q = q_new
                break
            q = q_new

        return q


# ------------------------------ I/O helpers ------------------------------

def save_table(df: pd.DataFrame, path: str, fmt: str = "parquet") -> None:
    fmt = fmt.lower()
    if fmt == "parquet":
        df.to_parquet(path, index=False)
    elif fmt == "arrow":
        import pyarrow as pa, pyarrow.ipc as ipc  # noqa
        table = pa.Table.from_pandas(df, preserve_index=False)
        with ipc.new_file(path, table.schema) as writer:
            writer.write(table)
    elif fmt == "root":
        try:
            import uproot  # noqa
        except Exception as e:
            raise RuntimeError("ROOT export requires 'uproot' or PyROOT.") from e
        # minimal ROOT writer via uproot (one-shot)
        with uproot.recreate(path) as f:
            f["quantile_fit_nd"] = df
    else:
        raise ValueError(f"Unsupported fmt='{fmt}'")


def load_table(path: str, fmt: Optional[str] = None) -> pd.DataFrame:
    if fmt is None:
        if path.endswith(".parquet"):
            fmt = "parquet"
        elif path.endswith(".arrow") or path.endswith(".feather"):
            fmt = "arrow"
        elif path.endswith(".root"):
            fmt = "root"
        else:
            fmt = "parquet"
    fmt = fmt.lower()
    if fmt == "parquet":
        return pd.read_parquet(path)
    elif fmt == "arrow":
        import pyarrow as pa, pyarrow.ipc as ipc  # noqa
        with ipc.open_file(path) as reader:
            t = reader.read_all()
        return t.to_pandas()
    elif fmt == "root":
        import uproot  # noqa
        with uproot.open(path) as f:
            # first TTree
            keys = [k for k in f.keys() if k.endswith(";1")]
            if not keys:
                raise RuntimeError("No TTrees found in ROOT file")
            return f[keys[0]].arrays(library="pd")
    else:
        raise ValueError(f"Unsupported fmt='{fmt}'")
