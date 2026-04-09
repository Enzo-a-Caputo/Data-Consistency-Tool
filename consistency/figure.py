# -*- coding: utf-8 -*-
"""
consistency/figure.py
---------------------
Plotly figure construction for the consistency tool.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .indicators import color_labels

# Color palette for the four point categories
PALETTE: dict[str, str] = {
    "Normal":         "#1f77b4",  # blue
    "Locking":        "#2ca02c",  # green
    "Pos. Variation": "#e377c2",  # pink
    "Neg. Variation": "#FFD700",  # yellow
}


def filter_secondary(
    df_primary: pd.DataFrame,
    df_secondary: pd.DataFrame,
    date_col: str = "Date",
) -> pd.DataFrame:
    """
    Crop df_secondary to the date range of df_primary.
    UTC coercion prevents comparison errors when the two series have
    divergent or missing timezone info.
    """
    t_prim = pd.to_datetime(df_primary[date_col], utc=True)
    t_sec  = pd.to_datetime(df_secondary[date_col], utc=True)
    mask   = (t_sec >= t_prim.min()) & (t_sec <= t_prim.max())
    return df_secondary.loc[mask].copy()


def build_figure(
    df_section: pd.DataFrame,
    df_secondary: Optional[pd.DataFrame],
    col_primary: str,
    col_secondary: Optional[str],
    lim_pos: float,
    lim_neg: float,
    lim_trav: int,
    uirevision: object,
    date_col: str = "Date",
) -> go.Figure:
    """
    Build the Plotly figure for one section of the primary series.

    - Primary series: one Scattergl trace per category (WebGL performance).
      customdata carries the global df index for reliable point identification.
    - NaN values (deleted points) are filtered out before sending to the browser.
    - Secondary series (e.g. rainfall): orange Scattergl on a right axis.
    - uirevision: increment to reset zoom, keep constant to preserve it.
    """
    labels   = color_labels(df_section, col_primary, lim_pos, lim_neg, lim_trav)
    orig_idx = df_section.index.to_numpy()
    dates    = df_section[date_col].to_numpy()
    values   = df_section[col_primary].to_numpy(dtype=float)

    # Drop NaN rows — deleted points must not appear as selectable ghosts
    valid    = ~np.isnan(values)
    labels   = labels[valid]
    orig_idx = orig_idx[valid]
    dates    = dates[valid]
    values   = values[valid]

    fig = go.Figure()

    for cat, color in PALETTE.items():
        mask = labels == cat
        if not mask.any():
            continue
        cdata = [[int(i)] for i in orig_idx[mask]]
        fig.add_trace(go.Scattergl(
            x           = dates[mask],
            y           = values[mask],
            mode        = "markers",
            name        = cat,
            marker      = dict(color=color, size=4, opacity=0.85),
            customdata  = cdata,
            legendgroup = cat,
            selected    = dict(marker=dict(color="red", size=7, opacity=1.0)),
            unselected  = dict(marker=dict(opacity=0.85)),
        ))

    has_sec = (
        df_secondary is not None
        and not df_secondary.empty
        and col_secondary is not None
        and col_secondary in df_secondary.columns
    )

    layout: dict = dict(
        uirevision    = uirevision,
        dragmode      = "select",
        margin        = dict(t=30, b=40, l=60, r=60),
        legend        = dict(orientation="h", yanchor="bottom", y=1.01,
                             xanchor="left", x=0),
        xaxis         = dict(type="date", title="Date"),
        yaxis         = dict(title=col_primary),
        hovermode     = "x",
        spikedistance = -1,
    )

    if has_sec:
        fig.add_trace(go.Scattergl(
            x          = df_secondary[date_col],
            y          = df_secondary[col_secondary],
            mode       = "markers",
            name       = col_secondary,
            marker     = dict(color="orange", size=4, opacity=0.7),
            yaxis      = "y2",
            selected   = dict(marker=dict(opacity=0.7)),
            unselected = dict(marker=dict(opacity=0.7)),
        ))
        layout["yaxis2"] = dict(
            overlaying = "y",
            side       = "right",
            title      = col_secondary,
            showgrid   = False,
        )

    fig.update_layout(**layout)
    return fig
