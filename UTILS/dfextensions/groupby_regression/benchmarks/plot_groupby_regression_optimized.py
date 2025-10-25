#!/usr/bin/env python3
"""
plot_groupby_regression_optimized.py
Config-driven plotting for the optimized GroupBy benchmark.

Reads:
  benchmarks/bench_out/benchmark_summary.csv

Writes (defaults, can be changed with CLI):
  benchmarks/bench_out/throughput_by_engine.png
  benchmarks/bench_out/speedup_v4_over_v2.png
  benchmarks/bench_out/scaling_groups.png
  benchmarks/bench_out/scaling_rows_per_group.png
  benchmarks/bench_out/scaling_n_jobs.png
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, List
from pathlib import Path
import argparse

import pandas as pd
import matplotlib.pyplot as plt


# ------------------------------- Plot Config API -------------------------------

PlotKind = Literal["bar", "line", "speedup_v4_over_v2"]

# Colorblind-friendly palette (Wong 2011)
COLORS = ['#0173B2', '#DE8F05', '#029E73', '#CC78BC', '#CA9161']

@dataclass
class PlotConfig:
    """Configuration for a single plot."""
    # Subset of rows to consider (pandas .query() string)
    query: str
    # Output
    filename: str
    title: str
    # Semantics
    kind: PlotKind                       # "bar" | "line" | "speedup_v4_over_v2"
    x_axis: str                          # e.g., "scenario_id" | "n_groups" | "rows_per_group" | "n_jobs"
    y_axis: str = "groups_per_s"         # metric to plot
    legend: str = "engine"               # which column defines the series (legend)
    log_y: bool = False
    # Line-plot specifics
    agg: Literal["median", "mean", "max"] = "median"
    min_points: int = 3                  # require at least N distinct x values


# ----------------------------- Default configurations --------------------------

PLOT_CONFIGS: List[PlotConfig] = [
    # 1) Throughput summary by engine (grouped bar)
    PlotConfig(
        query="engine in ['v2','v3','v4']",
        filename="throughput_by_engine.png",
        title="Throughput by Engine (higher is better)",
        kind="bar",
        x_axis="scenario_id",
        log_y=True,
    ),
    # 2) Speedup bar: v4 over v2 per scenario
    PlotConfig(
        query="engine in ['v2','v4']",
        filename="speedup_v4_over_v2.png",
        title="Speedup of Numba v4 over v2 (higher is better)",
        kind="speedup_v4_over_v2",
        x_axis="scenario_id",
    ),
    # 3) Scaling vs n_groups (line)
    PlotConfig(
        query="engine in ['v2','v3','v4']",
        filename="scaling_groups.png",
        title="Scaling vs n_groups",
        kind="line",
        x_axis="n_groups",
        log_y=True,
    ),
    # 4) Scaling vs rows_per_group (line)
    PlotConfig(
        query="engine in ['v2','v3','v4']",
        filename="scaling_rows_per_group.png",
        title="Scaling vs rows_per_group",
        kind="line",
        x_axis="rows_per_group",
        log_y=True,
    ),
    # 5) Scaling vs n_jobs (line)
    PlotConfig(
        query="engine in ['v2','v3','v4']",
        filename="scaling_n_jobs.png",
        title="Scaling vs n_jobs",
        kind="line",
        x_axis="n_jobs",
        log_y=True,
    ),
]


# ------------------------------- Helper functions ------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Plot optimized GroupBy benchmark results (config-driven).")
    p.add_argument("--csv", type=str,
                   default=str(Path(__file__).resolve().parent / "bench_out" / "benchmark_summary.csv"),
                   help="Path to benchmark_summary.csv")
    p.add_argument("--outdir", type=str,
                   default=str(Path(__file__).resolve().parent / "bench_out"),
                   help="Output directory for plots")
    p.add_argument("--fmt", choices=["png", "svg"], default="png", help="Image format")
    p.add_argument("--dpi", type=int, default=140, help="DPI for PNG")
    p.add_argument("--only", nargs="*", default=[],
                   help="Optional list of output filenames to generate (filters PLOT_CONFIGS)")
    return p.parse_args()


def _safe_category_order(series: pd.Series) -> list:
    """Stable order for categorical x (e.g., scenario_id)."""
    if pd.api.types.is_categorical_dtype(series):
        return list(series.cat.categories)
    # preserve first-seen order
    seen, order = set(), []
    for v in series:
        if v not in seen:
            seen.add(v)
            order.append(v)
    return order


def render_bar(df: pd.DataFrame, cfg: PlotConfig, outdir: Path, fmt: str, dpi: int):
    """Render grouped bar chart."""
    try:
        d = df.query(cfg.query).copy()
        if d.empty:
            print(f"[skip] {cfg.filename}: no data after query '{cfg.query}'")
            return None

        # Use median aggregation instead of "first"
        pv = d.pivot_table(index=cfg.x_axis, columns=cfg.legend,
                           values=cfg.y_axis, aggfunc="median")

        scenarios = list(pv.index.astype(str))
        engines = list(pv.columns.astype(str))

        n_sc = len(scenarios)
        n_eng = len(engines)
        if n_sc == 0 or n_eng == 0:
            print(f"[skip] {cfg.filename}: empty pivot table")
            return None

        width = 0.22
        xs = list(range(n_sc))

        fig, ax = plt.subplots(figsize=(max(9, n_sc * 0.6), 5.5))
        for j, eng in enumerate(engines):
            xj = [x + (j - (n_eng-1)/2)*width for x in xs]
            ax.bar(xj, pv[eng].values, width=width,
                   color=COLORS[j % len(COLORS)], label=eng)

        ax.set_xticks(xs)
        ax.set_xticklabels(scenarios, rotation=30, ha="right")
        ax.set_ylabel(cfg.y_axis.replace("_", " "))
        ax.set_title(cfg.title)
        if cfg.log_y:
            ax.set_yscale("log")
        ax.grid(axis="y", alpha=0.2)
        ax.legend()

        out = outdir / cfg.filename
        if fmt == "png":
            fig.savefig(out, dpi=dpi, bbox_inches="tight")
        else:
            fig.savefig(out, bbox_inches="tight")
        plt.close(fig)
        return out

    except Exception as e:
        print(f"[error] {cfg.filename}: {e}")
        return None


def render_speedup(df: pd.DataFrame, cfg: PlotConfig, outdir: Path, fmt: str, dpi: int):
    """Render speedup comparison (v4 / v2)."""
    try:
        d = df.query(cfg.query).copy()
        if d.empty:
            print(f"[skip] {cfg.filename}: no data after query '{cfg.query}'")
            return None

        X = cfg.x_axis

        base = d[d[cfg.legend] == "v2"][[X, cfg.y_axis]].rename(columns={cfg.y_axis: "v2"})
        v4   = d[d[cfg.legend] == "v4"][[X, cfg.y_axis]].rename(columns={cfg.y_axis: "v4"})
        m = base.merge(v4, on=X, how="inner")

        if m.empty:
            print(f"[skip] {cfg.filename}: no matching v2/v4 data")
            return None

        m["speedup"] = m["v4"] / m["v2"]

        scenarios = list(m[X].astype(str).values)
        vals = m["speedup"].values

        fig, ax = plt.subplots(figsize=(max(9, len(scenarios) * 0.6), 5.0))
        ax.bar(range(len(scenarios)), vals, color=COLORS[0])
        ax.set_xticks(range(len(scenarios)))
        ax.set_xticklabels(scenarios, rotation=30, ha="right")
        ax.set_ylabel("speedup (v4 ÷ v2)")
        ax.set_title(cfg.title)
        ax.grid(axis="y", alpha=0.2)

        # Label bars with speedup value
        for i, v in enumerate(vals):
            if v > 5:
                ax.text(i, v, f"{v:.0f}×", ha="center", va="bottom", fontsize=9)

        out = outdir / cfg.filename
        if fmt == "png":
            fig.savefig(out, dpi=dpi, bbox_inches="tight")
        else:
            fig.savefig(out, bbox_inches="tight")
        plt.close(fig)
        return out

    except Exception as e:
        print(f"[error] {cfg.filename}: {e}")
        return None


def render_line(df: pd.DataFrame, cfg: PlotConfig, outdir: Path, fmt: str, dpi: int):
    """Render line plot (scaling analysis)."""
    try:
        d = df.query(cfg.query).copy()
        if d.empty:
            print(f"[skip] {cfg.filename}: no data after query '{cfg.query}'")
            return None

        X = cfg.x_axis
        Y = cfg.y_axis
        L = cfg.legend

        # Aggregate by (legend, X) with selected reducer
        reducer = {"median": "median", "mean": "mean", "max": "max"}[cfg.agg]
        g = d.groupby([L, X], as_index=False)[Y].agg(reducer)

        # Filter out too-short series
        counts = g.groupby(L)[X].nunique()
        keep = set(counts[counts >= cfg.min_points].index)
        g = g[g[L].isin(keep)]

        if g.empty:
            print(f"[skip] {cfg.filename}: insufficient data points (need {cfg.min_points})")
            return None

        # Order X
        try:
            x_sorted = sorted(g[X].unique())
        except Exception:
            x_sorted = _safe_category_order(g[X])

        fig, ax = plt.subplots(figsize=(max(9, len(x_sorted) * 0.6), 5.5))
        for idx, (key, part) in enumerate(g.groupby(L)):
            # align to sorted X
            part = part.set_index(X).reindex(x_sorted)
            ax.plot(x_sorted, part[Y].values, marker="o",
                    color=COLORS[idx % len(COLORS)], label=str(key))

        ax.set_xlabel(X.replace("_", " "))
        ax.set_ylabel(Y.replace("_", " "))
        ax.set_title(cfg.title)
        if cfg.log_y:
            ax.set_yscale("log")
        ax.grid(True, alpha=0.25)
        ax.legend(title=L)

        out = outdir / cfg.filename
        if fmt == "png":
            fig.savefig(out, dpi=dpi, bbox_inches="tight")
        else:
            fig.savefig(out, bbox_inches="tight")
        plt.close(fig)
        return out

    except Exception as e:
        print(f"[error] {cfg.filename}: {e}")
        return None


# ------------------------------------- Main ------------------------------------

def main():
    args = parse_args()
    csv_path = Path(args.csv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        print(f"[error] CSV not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)

    if df.empty:
        print("[error] CSV is empty")
        return

    print(f"Loaded {len(df)} rows from {csv_path}")

    generated = []
    for cfg in PLOT_CONFIGS:
        if args.only and cfg.filename not in args.only:
            continue

        if cfg.kind == "bar":
            out = render_bar(df, cfg, outdir, args.fmt, args.dpi)
        elif cfg.kind == "line":
            out = render_line(df, cfg, outdir, args.fmt, args.dpi)
        elif cfg.kind == "speedup_v4_over_v2":
            out = render_speedup(df, cfg, outdir, args.fmt, args.dpi)
        else:
            out = None

        if out:
            print(f"[wrote] {out}")
            generated.append(out)

    if generated:
        print(f"\nGenerated {len(generated)} plot(s)")
    else:
        print("\n[warning] No plots generated")


if __name__ == "__main__":
    main()