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


def _local_fit_delta_q(Qw: np.ndarray, Xw: np.ndarray, q0: float) -> Tuple[float, float, float, int, Dict[str, Any]]:
    """
    Stable 2-parameter OLS in the Δq-centered model:
        X = a + b * (Q - q0)
    Returns:
      a, b, sigma_X|Q (RMS of residuals), n_used, stats(dict)
    Rejects windows with insufficient Q spread to estimate slope reliably.
    """
    Qw = np.asarray(Qw, dtype=np.float64)
    Xw = np.asarray(Xw, dtype=np.float64)
    m = np.isfinite(Qw) & np.isfinite(Xw)
    Qw, Xw = Qw[m], Xw[m]
    n = Qw.size
    if n < 3:
        return np.nan, np.nan, np.nan, int(n), {"ok": False, "reason": "n<3"}

    dq = Qw - q0
    # Degeneracy checks for discrete/plateau windows (typical in Poisson-CDF ranks)
    # Require at least 3 unique Q values and a minimal span in Q.
    uq = np.unique(np.round(Qw, 6))  # rounding collapses near-duplicates
    span_q = float(np.max(Qw) - np.min(Qw)) if n else 0.0
    if uq.size < 3 or span_q < 1e-3:
        return np.nan, np.nan, np.nan, int(n), {
            "ok": False, "reason": "low_Q_spread", "n_unique_q": int(uq.size), "span_q": span_q
        }

    # Design matrix for OLS: [1, (Q - q0)]
    A = np.column_stack([np.ones(n, dtype=np.float64), dq])
    # Least squares solution (stable even when dq mean ≠ 0)
    sol, resid, rank, svals = np.linalg.lstsq(A, Xw, rcond=None)
    a, b = float(sol[0]), float(sol[1])

    # Residual RMS as sigma_X|Q
    if n > 2:
        if resid.size > 0:
            rss = float(resid[0])
        else:
            # fallback if lstsq doesn't return resid (e.g., rank-deficient weird cases)
            rss = float(np.sum((Xw - (a + b * dq)) ** 2))
        sigmaX = float(np.sqrt(max(rss, 0.0) / (n - 2)))
    else:
        sigmaX = np.nan

    stats = {
        "ok": True,
        "rms": sigmaX,
        "n_used": int(n),
        "n_unique_q": int(uq.size),
        "span_q": span_q,
    }
    return a, b, sigmaX, int(n), stats


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
    Degree-1, Δq-centered model: X = a + b*(Q - q_center).

    Monotonicity:
      - Enforce floor b>=b_min ONLY for valid fits with non-positive b.
      - Degenerate windows (low Q spread / too few unique Q) remain NaN (no flooring).

    sigma_Q = sigma_X|Q / |b|

    Returns a flat DataFrame with coefficients and diagnostics.
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
                        "fit_stats": json.dumps({"n_used": n_keep, "ok": False, "reason": "cell_n<6", "masked_frac": float(masked_frac)})
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

                # window-local b_min (compute BEFORE branching)
                if b_min_option == "auto":
                    if n_win > 1:
                        sigmaX_win = float(np.std(X_all[in_win]))
                    else:
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
                            "n_used": n_win, "ok": False, "reason": "win_n<6",
                            "masked_frac": float(masked_frac), "b_min": float(bmin)
                        })
                    }
                else:
                    a, b, sigX, n_used, stats = _local_fit_delta_q(Q_all[in_win], X_all[in_win], q0)

                    # If fit is NOT ok (e.g. low_Q_spread), keep NaNs (do NOT floor here)
                    if not bool(stats.get("ok", True)):
                        row = {
                            "channel_id": ch_val,
                            "q_center": float(q0),
                            "a": np.nan, "b": np.nan, "sigma_Q": np.nan,
                            "sigma_Q_irr": np.nan, "dX_dN": np.nan,
                            "fit_stats": json.dumps({
                                **stats, "ok": False, "n_used": int(n_used),
                                "masked_frac": float(masked_frac), "b_min": float(bmin)
                            })
                        }
                    else:
                        # Valid fit: enforce b floor only if b<=0 (monotonicity)
                        clipped = False
                        if not np.isfinite(b) or b <= 0.0:
                            b = max(bmin, 1e-9)
                            clipped = True

                        sigma_Q = _sigma_Q_from_sigmaX(b, sigX)
                        fit_stats = {
                            **stats,
                            "n_used": int(n_used),
                            "ok": True,
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
        Invert amplitude -> rank using a monotone, piecewise-blended segment model:
          For q in [q_k, q_{k+1}], define
            X_blend(q) = (1-t)*(a_k + b_k*(q - q_k)) + t*(a_{k+1} + b_{k+1}*(q - q_{k+1})),
            t = (q - q_k) / (q_{k+1} - q_k).
        With b_k>0, X_blend is monotone increasing => solve X_blend(q)=X via bisection.
        Returns q in [0,1] or NaN if no information is available.
        """
        item = self.store.get(channel_id)
        if item is None:
            return np.nan

        qc = self.q_centers
        if qc.size < 2:
            return np.nan

        # Interpolate nuisance -> vectors over q-centers
        a_vec = self._interp_nuisance_vector(item["A"], coords)
        b_vec = self._interp_nuisance_vector(item["B"], coords)

        # Fill NaNs across q using linear interpolation on valid centers
        valid = np.isfinite(a_vec) & np.isfinite(b_vec) & (b_vec > 0.0)
        if valid.sum() < 2:
            return np.nan

        def _fill1d(xc, y):
            v = np.isfinite(y)
            if v.sum() == 0:
                return y
            if v.sum() == 1:
                # only one point: flat fill
                y2 = np.full_like(y, y[v][0])
                return y2
            y2 = np.array(y, dtype=np.float64, copy=True)
            y2[~v] = np.interp(xc[~v], xc[v], y[v])
            return y2

        a_f = _fill1d(qc, a_vec)
        b_f = _fill1d(qc, b_vec)
        # enforce positive floor to keep monotonicity
        b_f = np.where(np.isfinite(b_f) & (b_f > 0.0), b_f, 1e-9)

        # Fast helpers for segment evaluation
        def X_blend(q: float) -> float:
            # find segment
            if q <= qc[0]:
                k = 0
            elif q >= qc[-1]:
                k = qc.size - 2
            else:
                k = int(np.clip(np.searchsorted(qc, q) - 1, 0, qc.size - 2))
            qk, qk1 = qc[k], qc[k + 1]
            t = (q - qk) / (qk1 - qk) if qk1 > qk else 0.0
            ak, bk = a_f[k], b_f[k]
            ak1, bk1 = a_f[k + 1], b_f[k + 1]
            xk = ak + bk * (q - qk)
            xk1 = ak1 + bk1 * (q - qk1)
            return float((1.0 - t) * xk + t * xk1)

        # Bracket on [0,1]
        f0 = X_blend(0.0) - X
        f1 = X_blend(1.0) - X
        if not np.isfinite(f0) or not np.isfinite(f1):
            return np.nan

        # If not bracketed, clamp to nearest end (rare with our synthetic noise)
        if f0 == 0.0:
            return 0.0
        if f1 == 0.0:
            return 1.0
        if f0 > 0.0 and f1 > 0.0:
            return 0.0
        if f0 < 0.0 and f1 < 0.0:
            return 1.0

        # Bisection
        lo, hi = 0.0, 1.0
        flo, fhi = f0, f1
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            fm = X_blend(mid) - X
            if not np.isfinite(fm):
                break
            # root in [lo, mid] ?
            if (flo <= 0.0 and fm >= 0.0) or (flo >= 0.0 and fm <= 0.0):
                hi, fhi = mid, fm
            else:
                lo, flo = mid, fm
            if abs(hi - lo) < 1e-6:
                break
        return float(0.5 * (lo + hi))



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
