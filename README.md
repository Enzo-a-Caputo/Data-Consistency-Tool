# Data Consistency Tool

An interactive web-based tool for detecting and correcting inconsistencies in hydrometeorological time-series data. Built with [Dash](https://dash.plotly.com/) and [Plotly](https://plotly.com/python/), it provides a visual interface to identify anomalies, manually remove erroneous readings, and export the cleaned dataset.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **Automatic anomaly detection** — classifies each data point as Normal, Locking, Positive Variation, or Negative Variation
- **Interactive visualization** — color-coded scatter plot with lasso/box selection
- **Section-based navigation** — handles large datasets by rendering up to 20 000 points at a time
- **Secondary reference series** — overlay a read-only reference signal (e.g., rainfall) on a second y-axis
- **Point deletion** — select and remove erroneous readings with a confirmation step
- **Adjustable thresholds** — tune detection sensitivity without restarting
- **Export** — save the cleaned data as CSV, Excel, or Parquet

---

## Installation

```bash
pip install pandas numpy plotly dash dash-bootstrap-components openpyxl
```

Then clone or copy the `consistency/` package into your project.

---

## Quick Start

```python
import pandas as pd
from consistency import run_app

# Load primary time-series (e.g., water level)
df_level = pd.read_excel("Nivel.xlsx", names=["Date", "Level"])
df_level["Date"] = pd.to_datetime(df_level["Date"])

# Optional: load a reference series (e.g., rainfall)
df_rain = pd.read_excel("rainfall.xlsx")
df_rain["Increment"] = df_rain["Counter"].diff()

# Launch the interactive tool
run_app(
    df_level,
    df_secondary=df_rain,
    col_primary="Level",
    col_secondary="Increment",
    date_col="Date",
    port=8054,
)
```

A browser window opens automatically at `http://localhost:8054`.

---

## API Reference

### `run_app`

```python
consistency.run_app(
    df_primary,
    df_secondary=None,
    col_primary="Level",
    col_secondary=None,
    port=8054,
    section_size=20000,
    date_col="Date",
)
```

Builds the application and starts the development server. This call is **blocking** — interrupt the kernel or process to stop the server.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `df_primary` | `pd.DataFrame` | — | DataFrame containing the series to be inspected and edited. Must include `date_col` and `col_primary` columns. |
| `df_secondary` | `pd.DataFrame` \| `None` | `None` | Read-only reference DataFrame displayed alongside the primary series. Not modified by the tool. |
| `col_primary` | `str` | `"Level"` | Column name of the primary time-series values. |
| `col_secondary` | `str` \| `None` | `None` | Column name in `df_secondary` to display on the secondary y-axis. |
| `port` | `int` | `8054` | Port for the local development server. |
| `section_size` | `int` | `20000` | Maximum number of points rendered per section. |
| `date_col` | `str` | `"Date"` | Datetime column name (must exist in both DataFrames if secondary is provided). |

---

### `build_app`

```python
app = consistency.build_app(
    df_primary,
    df_secondary=None,
    col_primary="Level",
    col_secondary=None,
    section_size=20000,
    date_col="Date",
)
```

Same parameters as `run_app` (without `port`). Returns a configured `Dash` application instance without starting the server, useful for deploying with a custom WSGI server or embedding in a larger Dash app.

---

## Anomaly Categories

The tool classifies each data point into one of four categories based on configurable thresholds:

| Category | Color | Condition |
|---|---|---|
| **Normal** | Blue | No anomaly detected |
| **Pos. Variation** | Pink | Point-to-point increase exceeds `lim_pos` |
| **Neg. Variation** | Yellow | Point-to-point decrease exceeds `lim_neg` |
| **Locking** | Green | Sensor reads the same (or alternating) value for more than `lim_trav` consecutive points |

Default thresholds are:

| Threshold | Default | Description |
|---|---|---|
| `lim_pos` | `0.7` | Positive variation limit |
| `lim_neg` | `0.3` | Negative variation limit |
| `lim_trav` | `150` | Minimum locked-run length |

All thresholds can be adjusted at runtime via the **Control Panel** and re-applied without reloading.

---

## UI Walkthrough

<img width="1888" height="922" alt="image" src="https://github.com/user-attachments/assets/81a5903d-bb2b-4006-bd69-817ed57637b1" />


**Workflow:**

1. **Inspect** — Navigate between sections using Prev / Next
2. **Select** — Use lasso or box select to highlight suspicious points
3. **Delete** — Click "Delete selected" and confirm in the modal dialog
4. **Tune** — Adjust thresholds and click "Apply indicators" to re-classify
5. **Export** — Choose a format and click "Save" to download the cleaned data

**Navigation tips:**

- Middle-mouse button: pan the graph without changing the drag tool
- Scroll wheel: zoom in/out
- "Reset zoom": fits the entire section in view and resets pan

---

## Internal Modules

| Module | Responsibility |
|---|---|
| `config.py` | Default thresholds and constants |
| `indicators.py` | Anomaly detection algorithms (`locking_indicator`, `color_labels`) |
| `figure.py` | Plotly figure construction (`build_figure`, `filter_secondary`) |
| `layout.py` | Dash HTML/Bootstrap component tree (`build_layout`) |
| `callbacks.py` | Interactive event handlers (`register_callbacks`) |
| `app.py` | Application factory (`build_app`, `run_app`) |

---

## License

MIT © 2026 Enzo Augusto Caputo
