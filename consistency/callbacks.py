# -*- coding: utf-8 -*-
"""
consistency/callbacks.py
------------------------
Registers all Dash callbacks (server-side and clientside) on a given app.

Call register_callbacks(app, state, helpers, col_primary, col_secondary, date_col)
from build_app() after the layout is set.
"""

from __future__ import annotations

import io
from typing import Callable, Optional

import numpy as np
import pandas as pd
from dash import Dash, Input, Output, State, ctx, dcc, no_update

from .config import DEFAULT_LIM_POS, DEFAULT_LIM_NEG, DEFAULT_LIM_TRAV
from .figure import build_figure

# ── Clientside JS: middle-mouse pan ──────────────────────────────────────────
#
# Plotly's dragmode cannot be switched in time via relayout — by the time a
# mousedown handler fires, Plotly has already committed to the current gesture.
# Instead, we manually track pointer deltas and translate them into axis range
# updates, throttled via requestAnimationFrame.

_MM_PAN_JS = """
function(_figure) {
    const gd = document.getElementById('graph');
    if (!gd || gd._mmPanBound) return window.dash_clientside.no_update;
    gd._mmPanBound = true;

    let panning = false;
    let sx, sy, xr0, yr0, xLen, yLen;
    let rafId = null;

    gd.addEventListener('pointerdown', function(e) {
        if (e.button !== 1) return;
        e.preventDefault();
        e.stopPropagation();

        const xa = gd._fullLayout.xaxis;
        const ya = gd._fullLayout.yaxis;
        if (!xa || !ya) return;

        panning = true;
        sx = e.clientX;
        sy = e.clientY;
        xr0  = xa.range.map(v => xa.d2l(v));
        yr0  = ya.range.map(Number);
        xLen = xa._length;
        yLen = ya._length;

        gd.setPointerCapture(e.pointerId);
        gd.style.cursor = 'grabbing';
    });

    gd.addEventListener('pointermove', function(e) {
        if (!panning) return;
        e.preventDefault();

        const dx = e.clientX - sx;
        const dy = e.clientY - sy;

        const xa = gd._fullLayout.xaxis;
        const kx = (xr0[1] - xr0[0]) / xLen;
        const ky = (yr0[1] - yr0[0]) / yLen;

        const nx0 = xa.l2d(xr0[0] - dx * kx);
        const nx1 = xa.l2d(xr0[1] - dx * kx);
        const ny0 = yr0[0] + dy * ky;
        const ny1 = yr0[1] + dy * ky;

        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(function() {
            Plotly.relayout(gd, {
                'xaxis.range[0]': nx0,
                'xaxis.range[1]': nx1,
                'yaxis.range[0]': ny0,
                'yaxis.range[1]': ny1
            });
        });
    });

    function stopPan(e) {
        if (e.button !== 1 || !panning) return;
        panning = false;
        gd.releasePointerCapture(e.pointerId);
        gd.style.cursor = '';
        if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    }

    gd.addEventListener('pointerup',     stopPan);
    gd.addEventListener('pointercancel', stopPan);
    gd.addEventListener('lostpointercapture', function() {
        panning = false;
        gd.style.cursor = '';
    });

    gd.addEventListener('auxclick', function(e) {
        if (e.button === 1) e.preventDefault();
    });

    return window.dash_clientside.no_update;
}
"""


def register_callbacks(
    app: Dash,
    state: dict,
    n_fn: Callable[[], int],
    sec_df_fn: Callable[[], pd.DataFrame],
    secondary_fn: Callable[[pd.DataFrame], Optional[pd.DataFrame]],
    col_primary: str,
    col_secondary: Optional[str],
    date_col: str,
) -> None:
    """
    Attach all callbacks to `app`.

    Parameters
    ----------
    app           : The Dash application instance.
    state         : Shared mutable dict with keys 'df', 'section', 'pending', 'uirev'.
    n_fn          : Returns the total number of sections for the current df.
    sec_df_fn     : Returns the current section slice of the primary df.
    secondary_fn  : Returns the cropped secondary df for a given primary slice.
    col_primary   : Primary value column name.
    col_secondary : Secondary value column name (or None).
    date_col      : Datetime column name.
    """

    # ── Middle-mouse pan (clientside, no server round-trip) ───────────────
    app.clientside_callback(
        _MM_PAN_JS,
        Output("graph", "className"),   # harmless dummy output
        Input("graph",  "figure"),      # fires after every figure render
        prevent_initial_call=True,
    )

    # ── Enable Delete button only when points are selected ────────────────
    @app.callback(
        Output("btn-delete", "disabled"),
        Input("graph", "selectedData"),
    )
    def _toggle_delete(selected_data: dict) -> bool:
        return not (selected_data and selected_data.get("points"))

    # ── Main figure/navigation/deletion callback ──────────────────────────
    @app.callback(
        Output("graph",       "figure"),
        Output("btn-prev",    "disabled"),
        Output("btn-next",    "disabled"),
        Output("lbl-section", "children"),
        Output("modal",       "is_open"),
        Output("modal-body",  "children"),
        inputs=[
            Input("btn-prev",    "n_clicks"),
            Input("btn-next",    "n_clicks"),
            Input("btn-apply",   "n_clicks"),
            Input("btn-reset",   "n_clicks"),
            Input("btn-delete",  "n_clicks"),
            Input("btn-confirm", "n_clicks"),
            Input("btn-cancel",  "n_clicks"),
        ],
        state=[
            State("graph",    "selectedData"),
            State("lim-pos",  "value"),
            State("lim-neg",  "value"),
            State("lim-trav", "value"),
        ],
        prevent_initial_call=False,
    )
    def _update(
        _prev, _nxt, _apply, _reset, _delete, _confirm, _cancel,
        selected_data, lim_pos, lim_neg, lim_trav,
    ):
        """
        Zoom rule via uirevision:
        - Navigation / explicit reset  → increment uirev → Plotly resets zoom.
        - Deletion / apply indicators  → keep uirev      → zoom preserved.
        """
        triggered = ctx.triggered_id
        lim_pos  = lim_pos  if lim_pos  is not None else DEFAULT_LIM_POS
        lim_neg  = lim_neg  if lim_neg  is not None else DEFAULT_LIM_NEG
        lim_trav = lim_trav if lim_trav is not None else DEFAULT_LIM_TRAV

        modal_open = False
        modal_body = no_update
        reset_zoom = False  # only set True for navigation and explicit reset

        if triggered == "btn-next":
            if state["section"] < n_fn() - 1:
                state["section"] += 1
            state["pending"] = []
            reset_zoom = True

        elif triggered == "btn-prev":
            if state["section"] > 0:
                state["section"] -= 1
            state["pending"] = []
            reset_zoom = True

        elif triggered == "btn-reset":
            reset_zoom = True

        elif triggered == "btn-delete":
            pts     = (selected_data or {}).get("points", [])
            indices = [int(p["customdata"][0]) for p in pts if "customdata" in p]
            valid   = [i for i in indices if i in state["df"].index]
            state["pending"] = valid
            if valid:
                return (
                    no_update, no_update, no_update, no_update,
                    True, f"Delete {len(valid)} selected point(s)?",
                )

        elif triggered == "btn-confirm":
            if state["pending"]:
                valid = [i for i in state["pending"] if i in state["df"].index]
                state["df"].loc[valid, col_primary] = np.nan
                state["pending"] = []
            # reset_zoom stays False — preserve zoom after deletion

        elif triggered == "btn-cancel":
            state["pending"] = []
            # reset_zoom stays False — nothing changed

        # btn-apply and initial render: reset_zoom stays False

        if reset_zoom:
            state["uirev"] += 1

        df_sec = sec_df_fn()
        df_ref = secondary_fn(df_sec)

        fig = build_figure(
            df_sec, df_ref, col_primary, col_secondary,
            lim_pos, lim_neg, lim_trav,
            uirevision=state["uirev"],
            date_col=date_col,
        )

        prev_dis  = state["section"] == 0
        next_dis  = state["section"] >= n_fn() - 1
        sec_label = f'Section {state["section"] + 1} / {n_fn()}'

        return fig, prev_dis, next_dis, sec_label, modal_open, modal_body

    # ── Export / download ─────────────────────────────────────────────────
    @app.callback(
        Output("download",    "data"),
        Output("save-status", "children"),
        Input("btn-save",     "n_clicks"),
        State("save-format",  "value"),
        prevent_initial_call=True,
    )
    def _save(_, fmt: str):
        df_out = state["df"].copy()
        fname  = f"consistent_series.{fmt}"

        if fmt == "csv":
            return dcc.send_string(df_out.to_csv(index=False), fname), f"✓ {fname}"

        if fmt == "xlsx":
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                df_out.to_excel(w, index=False)
            return dcc.send_bytes(buf.getvalue(), fname), f"✓ {fname}"

        if fmt == "parquet":
            buf = io.BytesIO()
            df_out.to_parquet(buf, index=False)
            return dcc.send_bytes(buf.getvalue(), fname), f"✓ {fname}"

        return no_update, "Unknown format."
