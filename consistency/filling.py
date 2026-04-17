# -*- coding: utf-8 -*-
"""
consistency/filling.py
----------------------
Filling page: layout, gap-filling methods, and Dash callbacks.

Shares `state["df"]` with the consistency page so gaps produced by deleting
spurious points are immediately visible here without restarting the app.

Fill strategy
-------------
When the user specifies an expected time step (e.g. 15 min), the callback
first *reindexes* the series to the full regular date grid — adding NaN rows
for every timestamp that is absent — then applies the chosen interpolation
method.  This means the fill covers both:
  - existing rows whose value was deleted (NaN in col_primary), and
  - timestamps that were never in the DataFrame (structural gaps).
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update
import dash_bootstrap_components as dbc


# ── Filling methods ──────────────────────────────────────────────────────────
#
# Each method receives the full (values, dates) arrays after reindexing and
# returns a new array with NaN positions imputed.  Non-NaN positions must be
# returned unchanged so the caller only replaces the originally-missing slots.

def _fill_linear(values: np.ndarray, dates: np.ndarray) -> np.ndarray:
    """Time-based linear interpolation via pandas."""
    s = pd.Series(values, index=pd.to_datetime(dates))
    return s.interpolate(method="time", limit_direction="both").to_numpy()


def _fill_knn(values: np.ndarray, dates: np.ndarray, k: int = 5) -> np.ndarray:
    """
    Temporal KNN: each NaN is replaced by the weighted mean of its k nearest
    observed neighbours in time.  No external dependency required.
    """
    out       = values.copy()
    nan_mask  = np.isnan(values)
    valid_idx = np.where(~nan_mask)[0]
    if valid_idx.size == 0:
        return out

    t       = pd.to_datetime(dates).astype("int64").to_numpy().astype(float)
    t_valid = t[valid_idx]
    v_valid = values[valid_idx]
    kk      = min(k, v_valid.size)

    for i in np.where(nan_mask)[0]:
        dists = np.abs(t_valid - t[i])
        if v_valid.size <= kk:
            out[i] = v_valid.mean()
        else:
            nn     = np.argpartition(dists, kk)[:kk]
            out[i] = v_valid[nn].mean()
    return out


def _fill_ffill(values: np.ndarray, dates: np.ndarray) -> np.ndarray:
    """Forward fill followed by backward fill for leading gaps."""
    return pd.Series(values).ffill().bfill().to_numpy()


FILLING_METHODS: dict[str, Callable[[np.ndarray, np.ndarray], np.ndarray]] = {
    "linear": _fill_linear,
    "knn":    _fill_knn,
    "ffill":  _fill_ffill,
}

METHOD_LABELS: dict[str, str] = {
    "linear": "Linear interpolation (time)",
    "knn":    "KNN temporal (k=5)",
    "ffill":  "Forward / backward fill",
}

STEP_UNITS: list[dict] = [
    {"label": "seconds", "value": "s"},
    {"label": "minutes", "value": "min"},
    {"label": "hours",   "value": "h"},
    {"label": "days",    "value": "D"},
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_freq(step_value, step_unit) -> Optional[str]:
    """Return a pandas freq string like '15min' or '1D', or None if invalid."""
    try:
        v = int(step_value)
        if v <= 0 or step_unit not in {o["value"] for o in STEP_UNITS}:
            return None
        return f"{v}{step_unit}"
    except (TypeError, ValueError):
        return None


def _reindex_to_grid(
    df: pd.DataFrame,
    col_primary: str,
    date_col: str,
    freq: str,
) -> pd.DataFrame:
    """
    Reindex `df` to a regular date grid at `freq`.
    Missing timestamps get NaN in col_primary; all other columns are forward-
    filled from the nearest preceding row so the date column stays consistent.
    Returns a fresh DataFrame with a clean RangeIndex.
    """
    dts      = pd.to_datetime(df[date_col])
    grid     = pd.date_range(start=dts.min(), end=dts.max(), freq=freq)
    df_work  = df.set_index(dts)[[col_primary]]
    df_work  = df_work.reindex(grid)
    df_work.index.name = date_col
    return df_work.reset_index()


def _gap_stats(
    df: pd.DataFrame,
    col_primary: str,
    date_col: str,
    freq: Optional[str],
) -> dict:
    """Return a dict of gap statistics for the metrics card."""
    total    = len(df)
    n_nan    = int(df[col_primary].isna().sum())
    n_obs    = total - n_nan
    stats    = dict(total=total, n_nan=n_nan, n_obs=n_obs,
                    n_expected=None, n_missing_ts=None, n_total_to_fill=None)

    if freq:
        try:
            dts          = pd.to_datetime(df[date_col])
            grid         = pd.date_range(dts.min(), dts.max(), freq=freq)
            n_exp        = len(grid)
            # Count grid timestamps that have no matching row in df.
            # This mirrors exactly what _reindex_to_grid will create as NaN rows.
            existing_set = set(dts)
            n_missing_ts = sum(1 for t in grid if t not in existing_set)
            stats.update(
                n_expected      = n_exp,
                n_missing_ts    = n_missing_ts,
                n_total_to_fill = n_nan + n_missing_ts,
            )
        except Exception:
            pass
    return stats


# ── Layout ───────────────────────────────────────────────────────────────────

def build_filling_layout() -> dbc.Container:
    """Return the filling page layout tree."""
    return dbc.Container(fluid=True, children=[

        dbc.Row([
            # ── Missing-data metrics ─────────────────────────────────────
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Missing data summary", className="mb-2"),
                html.Div(id="fill-metrics", className="small"),
            ])), width=4),

            # ── Method + time step controls ──────────────────────────────
            dbc.Col(dbc.Card(dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("Expected time step",
                                   className="small fw-semibold"),
                        dbc.InputGroup([
                            dbc.Input(id="fill-step-value", type="number",
                                      value=15, min=1, step=1, debounce=True),
                            dbc.Select(id="fill-step-unit",
                                       options=STEP_UNITS, value="min"),
                        ]),
                    ], width=5),
                    dbc.Col([
                        html.Label("Filling method",
                                   className="small fw-semibold"),
                        dcc.Dropdown(
                            id="fill-method",
                            options=[{"label": v, "value": k}
                                     for k, v in METHOD_LABELS.items()],
                            value=None,
                            placeholder="Select a method to preview…",
                            clearable=True,
                        ),
                    ], width=7),
                ], className="g-2"),

                dbc.Row([
                    dbc.Col(
                        dbc.Button("Confirm fill", id="fill-btn-confirm",
                                   color="success", disabled=True,
                                   className="w-100 mt-2", n_clicks=0),
                    ),
                ]),

                html.Div(id="fill-status", className="text-muted small mt-2"),
            ])), width=8),
        ], className="mb-2 g-2"),

        # ── Section navigation ────────────────────────────────────────────
        dbc.Row([
            dbc.Col(dbc.ButtonGroup([
                dbc.Button("◀ Previous", id="fill-btn-prev",
                           color="outline-secondary", disabled=True),
                dbc.Button("Section — / —", id="fill-lbl-section",
                           disabled=True, color="light",
                           style={"cursor": "default", "minWidth": "150px",
                                  "pointerEvents": "none"}),
                dbc.Button("Next ▶", id="fill-btn-next",
                           color="outline-secondary"),
            ]), width="auto"),
        ], className="mb-1 g-2", align="center"),

        dcc.Graph(
            id="fill-graph",
            config={"scrollZoom": True, "displayModeBar": True},
            style={"height": "68vh"},
        ),
    ])


# ── Callbacks ────────────────────────────────────────────────────────────────

def register_filling_callbacks(
    app: Dash,
    state: dict,
    col_primary: str,
    date_col: str,
    section_size: int = 20_000,
) -> None:
    """Attach the filling-page callbacks to `app`."""

    def _n_fill(df: pd.DataFrame) -> int:
        n = len(df)
        if n == 0:
            return 1
        return max(1, (n + section_size - 1) // section_size)

    def _slice(df: pd.DataFrame, section: int) -> pd.DataFrame:
        start = section * section_size
        return df.iloc[start: start + section_size]

    # ── Missing-data metrics ─────────────────────────────────────────────
    @app.callback(
        Output("fill-metrics", "children"),
        Input("url",              "pathname"),
        Input("fill-btn-confirm", "n_clicks"),
        Input("fill-step-value",  "value"),
        Input("fill-step-unit",   "value"),
    )
    def _metrics(_path, _click, step_value, step_unit):
        df   = state["df"]
        freq = _build_freq(step_value, step_unit)
        st   = _gap_stats(df, col_primary, date_col, freq)

        items = [
            html.Li(f"Observed points: {st['n_obs']:,}"),
            html.Li(f"NaN values (existing rows): {st['n_nan']:,}"),
        ]

        if st["n_expected"] is not None:
            items += [
                html.Li(f"Expected on {freq} grid: {st['n_expected']:,}"),
                html.Li(f"Missing timestamps: {st['n_missing_ts']:,}"),
                html.Li(
                    html.Strong(f"Total to fill: {st['n_total_to_fill']:,}"),
                    className="mt-1",
                ),
            ]

        return html.Ul(items, className="mb-0 ps-3")

    # ── Preview + confirm + navigation + figure ──────────────────────────
    @app.callback(
        Output("fill-graph",        "figure"),
        Output("fill-btn-confirm",  "disabled"),
        Output("fill-status",       "children"),
        Output("fill-btn-prev",     "disabled"),
        Output("fill-btn-next",     "disabled"),
        Output("fill-lbl-section",  "children"),
        Input("fill-method",        "value"),
        Input("fill-btn-confirm",   "n_clicks"),
        Input("fill-btn-prev",      "n_clicks"),
        Input("fill-btn-next",      "n_clicks"),
        Input("url",                "pathname"),
        Input("fill-step-value",    "value"),
        Input("fill-step-unit",     "value"),
        prevent_initial_call=False,
    )
    def _update(method, _confirm_clicks, _prev, _next,
                pathname, step_value, step_unit):
        if pathname != "/filling":
            return no_update, no_update, no_update, no_update, no_update, no_update

        triggered = ctx.triggered_id
        freq      = _build_freq(step_value, step_unit)
        df        = state["df"]
        status    = ""
        disable_confirm = True
        preview_full    = None   # filled values for entire grid (NaN positions only)

        # ── Navigation ────────────────────────────────────────────────────
        if triggered == "fill-btn-next":
            # Tentative n_sections based on current df or grid
            state["fill_section"] += 1
            state["fill_uirev"]   += 1
        elif triggered == "fill-btn-prev":
            state["fill_section"] = max(0, state["fill_section"] - 1)
            state["fill_uirev"]  += 1

        # ── Build the full reindexed grid ─────────────────────────────────
        if freq:
            df_grid = _reindex_to_grid(df, col_primary, date_col, freq)
        else:
            df_grid = df[[date_col, col_primary]].copy().reset_index(drop=True)

        n_sec = _n_fill(df_grid)
        # Clamp section index in case the grid shrank (e.g. after confirm)
        state["fill_section"] = min(state["fill_section"], n_sec - 1)
        sec = state["fill_section"]

        all_dates  = df_grid[date_col].to_numpy()
        all_values = df_grid[col_primary].to_numpy(dtype=float)
        all_nan    = np.isnan(all_values)

        # ── Confirm: fill full grid and store ─────────────────────────────
        if triggered == "fill-btn-confirm" \
                and method in FILLING_METHODS and all_nan.any():
            n_to_fill = int(all_nan.sum())
            filled    = FILLING_METHODS[method](all_values, all_dates)
            df_grid[col_primary] = np.where(all_nan, filled, all_values)
            state["df"]          = df_grid.reset_index(drop=True)
            state["section"]     = 0
            state["pending"]     = []
            state["fill_uirev"] += 1
            # Refresh arrays from updated state
            df_grid    = state["df"][[date_col, col_primary]].copy()
            all_dates  = df_grid[date_col].to_numpy()
            all_values = df_grid[col_primary].to_numpy(dtype=float)
            all_nan    = np.isnan(all_values)
            n_sec      = _n_fill(df_grid)
            sec        = state["fill_section"]
            status     = (
                f"✓ {METHOD_LABELS[method]} applied — "
                f"{n_to_fill:,} point(s) filled."
            )

        # ── Preview: compute on full grid, display on section ─────────────
        elif method in FILLING_METHODS and all_nan.any():
            preview_full    = FILLING_METHODS[method](all_values, all_dates)
            disable_confirm = False
            freq_info = f" on {freq} grid" if freq else ""
            status = (
                f"Preview: {METHOD_LABELS[method]}{freq_info} — "
                f"{int(all_nan.sum()):,} point(s) to fill. "
                f"Click Confirm to apply."
            )
        elif method in FILLING_METHODS and not all_nan.any():
            status = "No missing points to fill."
        elif not freq:
            status = "Set the expected time step to detect structural gaps."

        # ── Slice section for display ─────────────────────────────────────
        start       = sec * section_size
        sl          = slice(start, start + section_size)
        sec_dates   = all_dates[sl]
        sec_values  = all_values[sl]
        sec_nan     = all_nan[sl]
        obs_mask    = ~sec_nan

        # ── Build figure ──────────────────────────────────────────────────
        fig = go.Figure()

        fig.add_trace(go.Scattergl(
            x     = sec_dates[obs_mask],
            y     = sec_values[obs_mask],
            mode  = "markers",
            name  = "Observed",
            marker=dict(color="#1f77b4", size=4, opacity=0.85),
        ))

        if preview_full is not None and sec_nan.any():
            sec_preview = preview_full[sl]
            fig.add_trace(go.Scattergl(
                x     = sec_dates[sec_nan],
                y     = sec_preview[sec_nan],
                mode  = "markers",
                name  = "To be filled",
                marker=dict(
                    color  = "#ff7f0e",
                    size   = 7,
                    symbol = "x",
                    opacity= 0.95,
                    line   = dict(color="#d62728", width=1),
                ),
            ))

        fig.update_layout(
            uirevision = state["fill_uirev"],
            margin     = dict(t=30, b=40, l=60, r=20),
            legend     = dict(orientation="h", yanchor="bottom", y=1.01,
                              xanchor="left", x=0),
            xaxis      = dict(type="date", title="Date"),
            yaxis      = dict(title=col_primary),
            hovermode  = "x",
        )

        prev_dis  = sec == 0
        next_dis  = sec >= n_sec - 1
        sec_label = f"Section {sec + 1} / {n_sec}"

        return fig, disable_confirm, status, prev_dis, next_dis, sec_label
