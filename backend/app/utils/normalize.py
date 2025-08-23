def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)

def _window_to_100(value: float, lo: float, hi: float) -> float:
    """Map [lo, hi] -> [0, 100], clamp outside."""
    if hi <= lo:
        return 0.0
    t = (value - lo) / (hi - lo)
    return round(_clamp01(t) * 100.0, 1)

def normalize_stats(raw):
    """
    raw is a dict with keys:
      'PTS','REB','AST','BLK','STL','FG_PCT','FG3_PCT','FT_PCT'  (percentages in 0–100)
    Returns values on 0–100 for the radar, tuned for visual balance.
    """

    # Use realistic per-game ceilings (cross-season but not absurdly high)
    # These are “good modern NBA” anchors; tweak as you like.
    CEIL = {
        'PTS': 70,   # elite ~35–37
        'REB': 22.0,   # elite ~13–15
        'AST': 16.5,   # elite ~10–12
        'BLK': 8.0,    # elite ~3–3.5
        'STL': 6.0,    # elite ~2–2.5
    }

    # Percentage windows mapped to 0–100 (typical starter-to-elite range)
    # Values below lo → 0; above hi → 100 (clamped)
    # These keep % legs from dwarfing counting stats.
    WIN = {
        'FG_PCT':  (40.0, 65.0),  # 40–65%
        'FG3_PCT': (28.0, 45.0),  # 28–45%
        'FT_PCT':  (65.0, 92.0),  # 65–92%
    }

    pts  = round(min(raw['PTS'] / CEIL['PTS'] * 100.0, 100.0), 1)
    reb  = round(min(raw['REB'] / CEIL['REB'] * 100.0, 100.0), 1)
    ast  = round(min(raw['AST'] / CEIL['AST'] * 100.0, 100.0), 1)
    blk  = round(min(raw['BLK'] / CEIL['BLK'] * 100.0, 100.0), 1)
    stl  = round(min(raw['STL'] / CEIL['STL'] * 100.0, 100.0), 1)

    fg   = _window_to_100(raw['FG_PCT'],  *WIN['FG_PCT'])
    fg3  = _window_to_100(raw['FG3_PCT'], *WIN['FG3_PCT'])
    # Optional (if/when you add FT% to the radar):
    ft   = _window_to_100(raw.get('FT_PCT', 0.0), *WIN['FT_PCT'])

    return {
        'points':  pts,
        'rebounds': reb,
        'assists': ast,
        'blocks':  blk,
        'steals':  stl,
        'fg_pct':  fg,
        'fg3_pct': fg3,
        'ft_pct':  ft,   # harmless if you don't use it yet
    }
