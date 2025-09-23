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
    """Convert input to float safely."""
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default

def _norm(value, cap):
    """Normalize value to 0–100 given a ceiling (cap)."""
    v = _safe_float(value, 0.0)
    v = max(0.0, min(v, float(cap)))
    return round((v / float(cap)) * 100.0, 1)

def _norm_inv(value, cap):
    """Inverse normalize (lower is better): 0 → 100, cap → 0."""
    v = _safe_float(value, 0.0)
    v = max(0.0, min(v, float(cap)))
    return round((1.0 - (v / float(cap))) * 100.0, 1)

def _pct_to_100(v):
    """Accepts 0–1 ratios or 0–100 percentages and returns 0–100."""
    f = _safe_float(v, 0.0)
    return f * 100.0 if 0.0 <= f <= 1.0 else f

def _get(raw, *keys, default=0.0):
    """Fetch the first present key from a dict (supports TEAM_* and plain)."""
    for k in keys:
        if k in raw and raw[k] is not None:
            return raw[k]
    return default

# ---------------------------
# Normalization ceilings
# ---------------------------

PLAYER_CEIL = {
    'PTS': 50,
    'REB': 18,
    'AST': 12,
    'BLK': 4.5,
    'STL': 3.5,
    'FG_PCT': 65,
    'FG3_PCT': 45,
    'FT_PCT': 95,   # player FT% ceiling
    'TOV': 8,       # inverse scale (lower is better)
    'FTR': 70,      # FT Rate ceiling, as a percent (i.e., 70%); typical stars 20–50%
}

TEAM_CEIL = {
    'PTS': 135,
    'REB': 60,
    'AST': 40,
    'BLK': 20,
    'STL': 18,
    'FG_PCT': 60,
    'FG3_PCT': 50,
    # new ceilings used if you choose to emit extras
    'FTM': 35,     # teams ~10–25, cap at 35
    'FT_PCT': 90,  # team % ceiling
    'TOV': 20,     # inverse (lower is better)
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
        Player stats: {'PTS','REB','AST','FG_PCT',...}
        Team stats:   {'TEAM_PTS','TEAM_REB',...}
        Percentages may be ratios (0–1) or % values (0–100).

    kind : "player" | "team"
        If not provided, auto-detect by TEAM_* key presence.

    Returns
    -------
    dict :
        {
          'points','rebounds','assists','blocks','steals','fg_pct','fg3_pct',
          # optional extras (returned if present in input):
          'ftm','ft_pct','turnovers'
        }
    """
    if kind not in ("player", "team"):
        kind = "team" if any(k.startswith("TEAM_") for k in raw.keys()) else "player"

    CEIL = TEAM_CEIL if kind == "team" else PLAYER_CEIL

    pts = _safe_float(_get(raw, 'TEAM_PTS', 'PTS'))
    reb = _safe_float(_get(raw, 'TEAM_REB', 'REB'))
    ast = _safe_float(_get(raw, 'TEAM_AST', 'AST'))
    blk = _safe_float(_get(raw, 'TEAM_BLK', 'BLK'))
    stl = _safe_float(_get(raw, 'TEAM_STL', 'STL'))

    fg_pct  = _pct_to_100(_get(raw, 'TEAM_FG_PCT', 'FG_PCT'))
    fg3_pct = _pct_to_100(_get(raw, 'TEAM_FG3_PCT', 'FG3_PCT'))

    out = {
        'points':   _norm(pts, CEIL['PTS']),
        'rebounds': _norm(reb, CEIL['REB']),
        'assists':  _norm(ast, CEIL['AST']),
        'blocks':   _norm(blk, CEIL['BLK']),
        'steals':   _norm(stl, CEIL['STL']),
        'fg_pct':   _norm(fg_pct,  CEIL['FG_PCT']),
        'fg3_pct':  _norm(fg3_pct, CEIL['FG3_PCT']),
    }

    # Optional extras: only include if provided in raw
    if 'TEAM_FTM' in raw or 'FTM' in raw:
        ftm = _safe_float(_get(raw, 'TEAM_FTM', 'FTM'))
        out['ftm'] = _norm(ftm, CEIL['FTM'])
    if 'TEAM_FT_PCT' in raw or 'FT_PCT' in raw:
        ft_pct = _pct_to_100(_get(raw, 'TEAM_FT_PCT', 'FT_PCT'))
        out['ft_pct'] = _norm(ft_pct, CEIL['FT_PCT'])
    if 'TEAM_TOV' in raw or 'TOV' in raw:
        tov = _safe_float(_get(raw, 'TEAM_TOV', 'TOV'))
        out['turnovers'] = _norm_inv(tov, CEIL['TOV'])

    # Optional extras (players)
    if kind == "player":
        # FT% (0–100 or 0–1)
        if 'FT_PCT' in raw:
            from_pct = _pct_to_100(raw['FT_PCT'])
            out['ft_pct'] = _norm(from_pct, CEIL['FT_PCT'])
        # Turnovers (inverse)
        if 'TOV' in raw:
            out['turnovers'] = _norm_inv(raw['TOV'], CEIL['TOV'])
        # Free-throw rate (as %; accept 0–1 or 0–100)
        if 'FTR' in raw:
            ftr_pct = _pct_to_100(raw['FTR'])
            out['ft_rate'] = _norm(ftr_pct, CEIL['FTR'])

    return out
