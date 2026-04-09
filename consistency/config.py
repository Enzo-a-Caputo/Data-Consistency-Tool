# -*- coding: utf-8 -*-
"""
consistency/config.py
---------------------
Application-wide constants and default parameter values.
"""

DEFAULT_SECTION_SIZE: int = 20_000
DEFAULT_LIM_POS: float    = 0.7
DEFAULT_LIM_NEG: float    = 0.3
DEFAULT_LIM_TRAV: int     = 150
_MAX_NAN_LOCKING: int     = 72    # consecutive NaNs tolerated inside a locking run
