# backend/app/utils/normalize.py
#
# Utility functions to normalize basketball stats (player or team)
# into a consistent 0–100 scale for radar chart visualization.
#
# Why normalize?
#   - Raw values (e.g. 115 team PPG vs. 28 player PPG) live on very different scales.
#   - Radar charts need a common 0–100 axis to compare categories fairly.
#   - We pick realistic “elite ceilings” for both player and team stats so charts
#     reflect relative strength without one stat dwarfing the others.

import math


# ---------------------------
# Low-level helpers
# ---------------------------

def _safe_float(x, default=0.0):
    """
    Convert input to float safely.
    - Returns `default` for None, NaN, Inf, or non-numeric values.
    - Ensures downstream math never breaks.
    """
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def _norm(value, cap):
    """
    Normalize a raw value to 0–100 given a ceiling (`cap`).
    - Values are clamped into [0, cap].
    - Example: value=25, cap=50 -> 50.0 (% of ceiling).
    """
    v = _safe_float(value, 0.0)
    v = max(0.0, min(v, float(cap)))  # clamp
    return round((v / float(cap)) * 100.0, 1)


def _pct_to_100(v):
    """
    Normalize percentage inputs.
    - Handles both 0–1 ratios and 0–100 percentages.
    - Example: 0.456 -> 45.6, 45.6 -> 45.6
    """
    f = _safe_float(v, 0.0)
    return f * 100.0 if 0.0 <= f <= 1.0 else f


def _get(raw, *keys, default=0.0):
    """
    Fetch the first present key from a dict.
    - Allows fallback to multiple naming conventions (e.g. 'PTS' vs 'TEAM_PTS').
    - Returns `default` if nothing is found.
    """
    for k in keys:
        if k in raw and raw[k] is not None:
            return raw[k]
    return default


# ---------------------------
# Normalization ceilings
# ---------------------------

# Player per-game stat ceilings (elite but realistic modern levels)
PLAYER_CEIL = {
    'PTS': 50,    # ~35–37 elite, 50 = extreme outlier ceiling
    'REB': 18,    # 12–14 elite rebounder
    'AST': 12,    # 8–10 elite playmaker
    'BLK': 4.5,   # 3+ elite rim protector
    'STL': 3.5,   # 2+ elite defender
    'FG_PCT': 65, # % ceiling (big men efficiency)
    'FG3_PCT': 45 # elite three-point %
}

# Team per-game stat ceilings (full NBA game context)
TEAM_CEIL = {
    'PTS': 135,   # top offenses ~120–125, cap at 135
    'REB': 60,    # teams average ~40–50
    'AST': 40,    # ~25–30 common, 40 rare but possible
    'BLK': 20,    # typical ~4–7, cap high for safety
    'STL': 18,    # typical ~6–9, cap high for safety
    'FG_PCT': 60, # realistic max efficiency
    'FG3_PCT': 50 # elite shooting cap
}


# ---------------------------
# Main entrypoint
# ---------------------------

def normalize_stats(raw: dict, kind: str = "player") -> dict:
    """
    Normalize stats for radar charts.

    Parameters
    ----------
    raw : dict
        Input dictionary with either:
          - Player stats: {'PTS', 'REB', 'AST', 'FG_PCT', ...}
          - Team stats:   {'TEAM_PTS', 'TEAM_REB', ...}
        Percentages may be ratios (0–1) or % values (0–100).
    kind : str, optional
        "player" | "team"
        If not provided, will auto-detect by presence of TEAM_* keys.

    Returns
    -------
    dict : normalized values (0–100 scale)
        {
            'points', 'rebounds', 'assists',
            'blocks', 'steals', 'fg_pct', 'fg3_pct'
        }
    """

    # Auto-detect kind if user didn't specify
    if kind not in ("player", "team"):
        kind = "team" if any(k.startswith("TEAM_") for k in raw.keys()) else "player"

    CEIL = TEAM_CEIL if kind == "team" else PLAYER_CEIL

    # Grab raw values (supports both TEAM_* and plain keys)
    pts = _safe_float(_get(raw, 'TEAM_PTS', 'PTS'))
    reb = _safe_float(_get(raw, 'TEAM_REB', 'REB'))
    ast = _safe_float(_get(raw, 'TEAM_AST', 'AST'))
    blk = _safe_float(_get(raw, 'TEAM_BLK', 'BLK'))
    stl = _safe_float(_get(raw, 'TEAM_STL', 'STL'))

    fg_pct  = _pct_to_100(_get(raw, 'TEAM_FG_PCT', 'FG_PCT'))
    fg3_pct = _pct_to_100(_get(raw, 'TEAM_FG3_PCT', 'FG3_PCT'))

    # Return normalized dict (all 0–100)
    return {
        'points':   _norm(pts, CEIL['PTS']),
        'rebounds': _norm(reb, CEIL['REB']),
        'assists':  _norm(ast, CEIL['AST']),
        'blocks':   _norm(blk, CEIL['BLK']),
        'steals':   _norm(stl, CEIL['STL']),
        'fg_pct':   _norm(fg_pct,  CEIL['FG_PCT']),
        'fg3_pct':  _norm(fg3_pct, CEIL['FG3_PCT']),
    }
