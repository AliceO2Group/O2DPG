"""
# export O2DPG=~/alicesw/O2DPG/
import sys, os; sys.path.insert(1, os.environ.get("O2DPG", "") + "/UTILS/dfextensions")

"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from collections import OrderedDict

def df_draw_scatter(
        df,
        expr,
        selection=None,          # str (pandas query), bool mask, or callable(df)->mask
        color=None,              # None | column name
        marker=None,             # None | column name for size
        cmap="tab10",
        jitter=False,
        show=True                # if False, don't plt.show(); always return (fig, ax)
):
    # --- parse "y:x"
    try:
        y_col, x_col = expr.split(":")
    except ValueError:
        raise ValueError("expr must be 'y:x'")

    # --- selection: str | mask | callable
    if selection is None:
        df_plot = df
    elif isinstance(selection, str):
        # engine='python' allows .str.contains() etc.
        df_plot = df.query(selection, engine="python")
    elif callable(selection):
        df_plot = df[selection(df)]
    else:
        # assume boolean mask-like
        df_plot = df[selection]

    # --- numeric x/y with NA filtering
    x = pd.to_numeric(df_plot[x_col], errors="coerce")
    y = pd.to_numeric(df_plot[y_col], errors="coerce")
    valid = x.notna() & y.notna()
    df_plot, x, y = df_plot[valid], x[valid], y[valid]

    # --- optional jitter (useful when values are quantized)
    if jitter:
        x = x + np.random.uniform(-0.1, 0.1, len(x))
        y = y + np.random.uniform(-2e-4, 2e-4, len(y))

    # --- color handling
    if color:
        col_data = df_plot[color]
        if col_data.dtype == "object":
            cats = pd.Categorical(col_data)
            c_vals = cats.codes  # -1 for NaN; handle below
            # build a discrete colormap large enough
            base = plt.get_cmap(cmap)
            n = max(cats.categories.size, 1)
            c_map = ListedColormap([base(i % base.N) for i in range(n)])
            # replace -1 with 0 to plot (will map to first color)
            c_plot = np.where(c_vals < 0, 0, c_vals)
            colorbar_mode = "categorical"
            categories = list(cats.categories)
        else:
            c_plot = pd.to_numeric(col_data, errors="coerce").fillna(method="pad")
            c_map = plt.get_cmap(cmap)
            colorbar_mode = "continuous"
            categories = None
    else:
        c_plot = "tab:blue"
        c_map = None
        colorbar_mode = None
        categories = None

    # --- marker size
    if marker:
        m_data = pd.to_numeric(df_plot[marker], errors="coerce")
        m_min, m_max = m_data.min(), m_data.max()
        # safe normalize
        denom = (m_max - m_min) if (m_max > m_min) else 1.0
        sizes = 100 + (m_data - m_min) / denom * 300
    else:
        sizes = 150

    # --- plotting
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(
        x, y,
        c=c_plot,
        s=sizes,
        cmap=c_map,
        alpha=0.7,
        linewidths=0.5,   # avoids edgecolor warning
        edgecolors="k"
    )

    ax.set_xlim(x.min() - 0.5, x.max() + 0.5)
    pad_y = max(1e-4, 0.02 * (y.max() - y.min()))
    ax.set_ylim(y.min() - pad_y, y.max() + pad_y)

    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title(f"Scatter: {y_col} vs {x_col}")
    ax.grid(True, alpha=0.3)

    # --- colorbar for continuous / categorical labels
    if color and colorbar_mode:
        cbar = plt.colorbar(scatter, ax=ax)
        if colorbar_mode == "categorical" and categories is not None:
            cbar.set_ticks(np.arange(len(categories)))
            cbar.set_ticklabels(categories)
        cbar.set_label(color)

    if show:
        plt.show()

    return fig, ax


def df_draw_scatter_categorical(
        df: pd.DataFrame,
        expr: str,
        selection: str = None,          # pandas query string ONLY (engine="python")
        color: str = None,              # categorical column -> COLORS
        marker_style: str = None,       # categorical column -> MARKER SHAPES
        marker_size=None,               # None | "" | number | column name
        jitter: bool = False,
        # category controls
        top_k_color: int = None,        # keep top-K colors, rest -> other_label_color
        other_label_color: str = "Other",
        order_color: list = None,       # explicit order for color legend
        top_k_marker: int = None,       # keep top-K marker cats, rest -> other_label_marker
        other_label_marker: str = "Other",
        order_marker: list = None,      # explicit order for marker legend
        # palettes / markers
        palette: list = None,           # list of color specs; defaults to repeating tab20
        markers: list = None,           # list of marker styles; defaults to common shapes
        # legends & layout
        legend_outside: bool = True,    # put legends outside plot and reserve margin
        legend_cols_color: int = 1,
        legend_cols_marker: int = 1,
        show: bool = False,
):
    """
    Scatter plot with categorical COLOR and MARKER SHAPE; flexible size control. Returns (fig, ax).

    Parameters
    ----------
    expr : str
        ROOT-like "y:x" expression, e.g. "sigma:pTmin".
    selection : str, optional
        pandas query string evaluated with engine="python".
        Example: "productionId.str.contains(r'(?:LHC25b8a|LHC24)', regex=True, na=False)".
    color : str, optional
        Categorical column used for colors (legend #1).
    marker_style : str, optional
        Categorical column used for marker shapes (legend #2).
    marker_size : None | "" | number | str, optional
        - None or ""  → constant default size (150 pt^2).
        - number      → fixed size (pt^2) for all points.
        - str (column):
            * numeric → min–max normalize to [100, 400] pt^2
            * non-numeric → map categories to sizes (150, 220, 290, …)
    jitter : bool, default False
        Add small uniform jitter to x and y.
    top_k_color, other_label_color, order_color :
        control color categories (reduce tail to 'Other', set order).
    top_k_marker, other_label_marker, order_marker :
        control marker-shape categories.
    palette : list, optional
        Colors to cycle through; defaults to repeating 'tab20'.
    markers : list, optional
        Marker shapes; defaults to ["o","s","^","D","P","X","v","<",">","h","H","*","p"].
    legend_outside : bool, default True
        Reserve right margin and place legends outside so they aren’t clipped.
    legend_cols_color, legend_cols_marker : int
        Number of columns for each legend block.
    show : bool, default True
        If True, plt.show() is called. Function always returns (fig, ax).

    Raises
    ------
    ValueError / TypeError on malformed expr or failed selection.
    """
    # --- parse "y:x"
    try:
        y_col, x_col = expr.split(":")
    except Exception as e:
        raise ValueError("expr must be in 'y:x' format, e.g. 'sigma:pTmin'") from e

    # --- selection via pandas query
    if selection is None:
        df_plot = df
    else:
        if not isinstance(selection, str):
            raise TypeError("selection must be a pandas query string (str).")
        try:
            df_plot = df.query(selection, engine="python")
        except Exception as e:
            raise ValueError(f"selection query failed: {selection}\n{e}") from e

    # --- numeric x/y with NA filtering
    x = pd.to_numeric(df_plot[x_col], errors="coerce")
    y = pd.to_numeric(df_plot[y_col], errors="coerce")
    valid = x.notna() & y.notna()
    df_plot, x, y = df_plot[valid], x[valid], y[valid]

    if jitter:
        x = x + np.random.uniform(-0.1, 0.1, len(x))
        y = y + np.random.uniform(-2e-4, 2e-4, len(y))

    # --- marker size handling
    DEFAULT_SIZE = 150.0  # pt^2
    if marker_size is None or (isinstance(marker_size, str) and marker_size == ""):
        sizes = np.full(len(df_plot), DEFAULT_SIZE, dtype=float)
    elif isinstance(marker_size, (int, float)):
        sizes = np.full(len(df_plot), float(marker_size), dtype=float)
    elif isinstance(marker_size, str):
        ms = df_plot[marker_size]
        if pd.api.types.is_numeric_dtype(ms):
            m = pd.to_numeric(ms, errors="coerce")
            mmin, mmax = m.min(), m.max()
            denom = (mmax - mmin) if (mmax > mmin) else 1.0
            sizes = 100.0 + (m - mmin) / denom * 300.0
            sizes = sizes.fillna(DEFAULT_SIZE).to_numpy(dtype=float)
        else:
            # categorical → cycle sizes
            cats = ms.astype("string").fillna("NA").value_counts().index.tolist()
            base_sizes = [150, 220, 290, 360, 430, 500]
            size_map = {cat: base_sizes[i % len(base_sizes)] for i, cat in enumerate(cats)}
            sizes = ms.astype("string").map(size_map).fillna(DEFAULT_SIZE).to_numpy(dtype=float)
    else:
        raise ValueError("marker_size must be None, '', a number, or a column name (str).")

    # --- categorical series (color & marker_style)
    if color is None:
        color_series = pd.Series(["All"] * len(df_plot), index=df_plot.index, dtype="string")
    else:
        color_series = df_plot[color].astype("string").fillna(other_label_color)

    if marker_style is None:
        marker_series = pd.Series(["All"] * len(df_plot), index=df_plot.index, dtype="string")
    else:
        marker_series = df_plot[marker_style].astype("string").fillna(other_label_marker)

    # reduce categories (top-K)
    if top_k_color is not None:
        keep = set(color_series.value_counts().head(top_k_color).index)
        color_series = color_series.where(color_series.isin(keep), other_label_color)

    if top_k_marker is not None:
        keep = set(marker_series.value_counts().head(top_k_marker).index)
        marker_series = marker_series.where(marker_series.isin(keep), other_label_marker)

    # final ordering
    def order_categories(series, explicit_order):
        counts = series.value_counts()
        by_freq = list(counts.index)
        if explicit_order:
            seen, ordered = set(), []
            for c in explicit_order:
                if c in counts.index and c not in seen:
                    ordered.append(c); seen.add(c)
            for c in by_freq:
                if c not in seen:
                    ordered.append(c); seen.add(c)
            return ordered
        return by_freq

    color_cats  = order_categories(color_series,  order_color)
    marker_cats = order_categories(marker_series, order_marker)

    # palettes / marker shapes
    if palette is None:
        base = list(plt.get_cmap("tab20").colors)
        repeats = (len(color_cats) + len(base) - 1) // len(base)
        palette = (base * max(1, repeats))[:len(color_cats)]
    else:
        repeats = (len(color_cats) + len(palette) - 1) // len(palette)
        palette = (list(palette) * max(1, repeats))[:len(color_cats)]

    if markers is None:
        markers = ["o", "s", "^", "D", "P", "X", "v", "<", ">", "h", "H", "*", "p"]
    else:
        markers = list(markers)

    color_map  = OrderedDict((cat, palette[i])                    for i, cat in enumerate(color_cats))
    marker_map = OrderedDict((cat, markers[i % len(markers)])     for i, cat in enumerate(marker_cats))

    # --- plot
    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=False)
    if legend_outside:
        fig.subplots_adjust(right=0.78)  # reserve space for legends on the right

    # robust bool masks (no pd.NA)
    color_vals  = color_series.astype("string")
    marker_vals = marker_series.astype("string")

    for mcat in marker_cats:
        m_mask = (marker_vals == mcat).fillna(False).to_numpy(dtype=bool)
        for ccat in color_cats:
            c_mask = (color_vals == ccat).fillna(False).to_numpy(dtype=bool)
            mc_mask = np.logical_and(m_mask, c_mask)
            if not np.any(mc_mask):
                continue
            ax.scatter(
                x.values[mc_mask], y.values[mc_mask],
                c=[color_map[ccat]],
                marker=marker_map[mcat],
                s=sizes[mc_mask],
                alpha=0.75,
                edgecolors="k",
                linewidths=0.5,
            )

    # axes & limits
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title(f"Scatter (categorical): {y_col} vs {x_col}")
    ax.grid(True, alpha=0.3)

    if len(x):
        ax.set_xlim(x.min() - 0.5, x.max() + 0.5)
    if len(y):
        pad_y = max(1e-4, 0.02 * (y.max() - y.min()))
        ax.set_ylim(y.min() - pad_y, y.max() + pad_y)

    # legends
    color_handles = [
        plt.Line2D([0], [0], marker="o", color="none",
                   markerfacecolor=color_map[c], markeredgecolor="k",
                   markersize=8, linewidth=0) for c in color_cats
    ]
    color_legend = ax.legend(
        color_handles, list(color_cats),
        title=color if color else "",
        ncol=legend_cols_color,
        loc="center left" if legend_outside else "best",
        bbox_to_anchor=(1.0, 0.5) if legend_outside else None,
        frameon=True,
    )
    ax.add_artist(color_legend)

    marker_handles = [
        plt.Line2D([0], [0], marker=marker_map[m], color="none",
                   markerfacecolor="lightgray", markeredgecolor="k",
                   markersize=8, linewidth=0) for m in marker_cats
    ]
    marker_legend = ax.legend(
        marker_handles, list(marker_cats),
        title=marker_style if marker_style else "",
        ncol=legend_cols_marker,
        loc="center left" if legend_outside else "best",
        bbox_to_anchor=(1.0, 0.15) if legend_outside else None,
        frameon=True,
    )
    ax.add_artist(marker_legend)

    if show:
        plt.show()

    return fig, ax

def drawExample():
    df=df = pd.read_csv("D0_resolution.csv")
    df.rename(columns={"production ID": "productionId"}, inplace=True)

    #
    fig, ax = df_draw_scatter(
        df,
        "sigma:pTmin",
        selection=lambda d: d["productionId"].str.contains(r"(LHC25b8a|LHC24)", regex=True, na=False),
        color="productionId",
        marker="centmin",
        show=True
    )
    #
    fig, ax = df_draw_scatter_categorical(
        df, "sigma:pTmin",
        selection="productionId.str.contains(r'(?:LHC25b8a|LHC24|LHC25a5)', regex=True, na=False)",
        color="productionId",
        marker_style="centmin",
        marker_size=100,    # pt²
    )
    fig.savefig("out.png", dpi=200, bbox_inches="tight")

    fig, ax = df_draw_scatter_categorical(
        df, "sigma:pTmin",
        selection="productionId.str.contains(r'(?:LHC24|LHC25a5)', regex=True, na=False)",
        color="productionId",
        marker_style="centmin",
        marker_size=100,    # pt²
    )
    fig.savefig("resol_LHC24_LHC25a5.png", dpi=200, bbox_inches="tight")

    fig, ax = df_draw_scatter_categorical(
        df, "sigma:pTmin",
        selection="productionId.str.contains(r'(?:LHC25b8a|LHC24)', regex=True, na=False)",
        color="productionId",
        marker_style="centmin",
        marker_size=100,    # pt²
    )
    fig.savefig("resol_LHC24_LHC25b8a.png", dpi=150, bbox_inches="tight")