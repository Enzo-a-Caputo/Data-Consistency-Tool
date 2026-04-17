# -*- coding: utf-8 -*-
"""
consistency/layout.py
---------------------
Dash HTML layout factories.

- build_shell(): top-level navbar + URL router placeholder.
- build_consistency_layout(): content for the consistency page.
"""

from __future__ import annotations

from dash import dcc, html
import dash_bootstrap_components as dbc

from .config import DEFAULT_LIM_POS, DEFAULT_LIM_NEG, DEFAULT_LIM_TRAV


def build_shell() -> dbc.Container:
    """Root layout: navbar + Location + page-content slot."""
    return dbc.Container(fluid=True, className="p-0", children=[
        dcc.Location(id="url", refresh=False),
        dbc.Navbar(
            dbc.Container([
                dbc.NavbarBrand("Data Consistency Tool", className="fw-semibold text-white"),
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink("Consistency", href="/",        active="exact",
                                            className="text-white")),
                    dbc.NavItem(dbc.NavLink("Filling",     href="/filling", active="exact",
                                            className="text-white")),
                ], className="ms-auto", navbar=True),
            ], fluid=True),
            color="primary", dark=True, className="mb-2",
        ),
        html.Div(id="page-content"),
    ])


def build_consistency_layout() -> dbc.Container:
    """Return the consistency page layout tree."""
    _num = {"type": "number", "debounce": True}

    return dbc.Container(fluid=True, children=[

        # ── Indicator controls ────────────────────────────────────────────
        dbc.Card(dbc.CardBody(dbc.Row([
            dbc.Col([
                html.Label("Positive variation (threshold)",
                           className="small fw-semibold"),
                dbc.Input(id="lim-pos", value=DEFAULT_LIM_POS,
                          step=0.01, **_num),
            ], width=3),
            dbc.Col([
                html.Label("Negative variation (threshold)",
                           className="small fw-semibold"),
                dbc.Input(id="lim-neg", value=DEFAULT_LIM_NEG,
                          step=0.01, **_num),
            ], width=3),
            dbc.Col([
                html.Label("Locking (number of points)",
                           className="small fw-semibold"),
                dbc.Input(id="lim-trav", value=DEFAULT_LIM_TRAV,
                          step=1, **_num),
            ], width=3),
            dbc.Col(
                dbc.Button("Apply indicators", id="btn-apply",
                           color="secondary", className="w-100 mt-3"),
                width=3,
            ),
        ])), className="mb-2"),

        # ── Action bar ───────────────────────────────────────────────────
        dbc.Row([
            dbc.Col(dbc.ButtonGroup([
                dbc.Button("◀ Previous", id="btn-prev",
                           color="outline-secondary", disabled=True),
                dbc.Button("Section — / —", id="lbl-section", disabled=True,
                           color="light",
                           style={"cursor": "default", "minWidth": "150px",
                                  "pointerEvents": "none"}),
                dbc.Button("Next ▶", id="btn-next",
                           color="outline-secondary"),
            ]), width="auto"),
            dbc.Col(
                dbc.Button("Delete selected", id="btn-delete",
                           color="danger", disabled=True, n_clicks=0),
                width="auto",
            ),
            dbc.Col(
                dbc.Button("↺ Reset zoom", id="btn-reset",
                           color="outline-secondary", n_clicks=0),
                width="auto",
            ),
        ], className="mb-1 g-2", align="center"),

        # ── Main chart ───────────────────────────────────────────────────
        dcc.Graph(
            id="graph",
            config={
                "modeBarButtonsToAdd":    ["lasso2d", "select2d"],
                "modeBarButtonsToRemove": ["toImage"],
                "scrollZoom":             True,
                "displayModeBar":         True,
            },
            style={"height": "68vh"},
        ),

        # ── Deletion confirmation modal ───────────────────────────────────
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Confirm deletion")),
            dbc.ModalBody(id="modal-body", children=""),
            dbc.ModalFooter([
                dbc.Button("Delete", id="btn-confirm",
                           color="danger", n_clicks=0),
                dbc.Button("Cancel", id="btn-cancel",
                           color="secondary", n_clicks=0, className="ms-2"),
            ]),
        ], id="modal", is_open=False),

        # ── Export ───────────────────────────────────────────────────────
        dbc.Card(dbc.CardBody(dbc.Row([
            dbc.Col(
                html.Span("Export consistent series:", className="fw-semibold"),
                width="auto",
            ),
            dbc.Col(dbc.RadioItems(
                id="save-format",
                options=[
                    {"label": " CSV",     "value": "csv"},
                    {"label": " Excel",   "value": "xlsx"},
                    {"label": " Parquet", "value": "parquet"},
                ],
                value="csv",
                inline=True,
            )),
            dbc.Col(
                dbc.Button("Save", id="btn-save", color="success"),
                width="auto",
            ),
            dbc.Col(
                html.Span(id="save-status", className="text-muted small"),
                width="auto",
            ),
        ], align="center")), className="mt-3"),

        dcc.Download(id="download"),
    ])
