# -*- coding: utf-8 -*-
"""
consistency/indicators.py
-------------------------
Signal-quality indicators for the primary time series:
  - locking_indicator : detects repeated-value ("frozen sensor") runs.
  - color_labels      : classifies each point into a display category.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import _MAX_NAN_LOCKING


def locking_indicator(values: np.ndarray, max_nan: int = _MAX_NAN_LOCKING) -> np.ndarray:
    """
    For each position, return the length of the "locked" run it belongs to.

    A locked run is a sequence of points that contains at most 2 distinct
    non-NaN values (which may alternate), with up to `max_nan` consecutive
    NaNs allowed internally. Operates on positional (0-based) indices only.

    Returns an int32 array; isolated points get value 1.
    """
    n = len(values)
    result = np.ones(n, dtype=np.int32)

    i = 0
    while i < n:
        if pd.isna(values[i]):
            i += 1
            continue

        anchors: list = [values[i]]   # at most 2 distinct values
        nan_count  = 0
        last_valid = i
        j = i + 1

        while j < n:
            v = values[j]
            if pd.isna(v):
                nan_count += 1
                if nan_count > max_nan:
                    break
                j += 1
            elif v in anchors:
                nan_count  = 0
                last_valid = j
                j += 1
            elif len(anchors) < 2:
                anchors.append(v)
                nan_count  = 0
                last_valid = j
                j += 1
            else:
                break

        run_end    = last_valid + 1
        run_length = run_end - i
        result[i:run_end] = run_length
        i = run_end if run_end > i else i + 1

    return result


def color_labels(
    df: pd.DataFrame,
    col: str,
    lim_pos: float,
    lim_neg: float,
    lim_trav: int,
) -> np.ndarray:
    """
    Classify each point into one of four indicator categories.
    Priority (highest first): Pos. Variation > Neg. Variation > Locking > Normal.
    """
    series = df[col].astype(float)

    # Use the last valid value to compute the real jump across NaN gaps
    last_valid = series.ffill().shift(1)
    diff = (series - last_valid).to_numpy()

    values = series.to_numpy()
    trav   = locking_indicator(values)

    return np.where(
        diff > lim_pos,  "Pos. Variation",
        np.where(
            diff < -lim_neg, "Neg. Variation",
            np.where(
                trav > lim_trav, "Locking", "Normal"
            )
        )
    )
