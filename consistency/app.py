# -*- coding: utf-8 -*-
"""
consistency/app.py
------------------
Top-level factory that wires together layout, state, and callbacks.
"""

from __future__ import annotations

import threading
import webbrowser
from typing import Optional

import pandas as pd
from dash import Dash
import dash_bootstrap_components as dbc

from .config import DEFAULT_SECTION_SIZE
from .figure import filter_secondary
from .layout import build_layout
from .callbacks import register_callbacks


def _load_section(df: pd.DataFrame, section: int, section_size: int) -> pd.DataFrame:
    start = section * section_size
    end   = min(start + section_size, len(df))
    return df.iloc[start:end].copy()


def _n_sections(df: pd.DataFrame, section_size: int) -> int:
    if len(df) == 0:
        return 1
    return max(1, (len(df) + section_size - 1) // section_size)


def build_app(
    df_primary: pd.DataFrame,
    df_secondary: Optional[pd.DataFrame] = None,
    col_primary: str = "Level",
    col_secondary: Optional[str] = None,
    section_size: int = DEFAULT_SECTION_SIZE,
    date_col: str = "Date",
) -> Dash:
    """
    Build and return the consistency Dash app.

    Parameters
    ----------
    df_primary   : DataFrame with `date_col` and `col_primary` columns.
    df_secondary : Read-only reference DataFrame (e.g. rainfall). Not edited.
    col_primary  : Column of the series to be edited.
    col_secondary: Column of the reference series.
    section_size : Maximum points rendered per display section.
    date_col     : Datetime column name (must match in both DataFrames).
    """
    state: dict = {
        "df":      df_primary.reset_index(drop=True).copy(),
        "section": 0,
        "pending": [],
        "uirev":   1,   # must start at a truthy value — Plotly.js treats 0 as
                        # "uirevision not set" and always resets zoom/pan
    }
    _df_ref = df_secondary.copy() if df_secondary is not None else None

    def _n() -> int:
        return _n_sections(state["df"], section_size)

    def _sec_df() -> pd.DataFrame:
        return _load_section(state["df"], state["section"], section_size)

    def _secondary(df_prim: pd.DataFrame) -> Optional[pd.DataFrame]:
        if _df_ref is None:
            return None
        return filter_secondary(df_prim, _df_ref, date_col=date_col)

    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True,
    )
    app.layout = build_layout()

    register_callbacks(
        app, state,
        n_fn          = _n,
        sec_df_fn     = _sec_df,
        secondary_fn  = _secondary,
        col_primary   = col_primary,
        col_secondary = col_secondary,
        date_col      = date_col,
    )

    return app


def run_app(
    df_primary: pd.DataFrame,
    df_secondary: Optional[pd.DataFrame] = None,
    col_primary: str = "Level",
    col_secondary: Optional[str] = None,
    port: int = 8054,
    section_size: int = DEFAULT_SECTION_SIZE,
    date_col: str = "Date",
) -> None:
    """
    Build and start the consistency server.
    Opens the browser automatically after 1.5 s.
    Blocking — interrupt the kernel to stop.
    """
    app = build_app(
        df_primary, df_secondary,
        col_primary, col_secondary,
        section_size, date_col,
    )
    threading.Timer(
        1.5, lambda: webbrowser.open_new(f"http://127.0.0.1:{port}/")
    ).start()
    app.run(debug=False, use_reloader=False, port=port)
