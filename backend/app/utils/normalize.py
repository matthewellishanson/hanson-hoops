import math

def _norm(value, cap):
    """
    Normalize a raw stat to 0..100 against a chosen cap.
    - Handles None / NaN
    - Clamps to [0, cap] so outliers don't exceed 100
    """
    if value is None:
        return 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(v) or math.isinf(v):
        return 0.0
    v = max(0.0, min(v, float(cap)))
    return round((v / float(cap)) * 100.0, 1)


def normalize_stats(raw: dict) -> dict:
    """
    Expected raw keys for the current radar:
      - counting:  'PTS', 'REB', 'AST', 'BLK', 'STL'
      - percents:  'FG_PCT', 'FG3_PCT' (already in percent units, e.g. 47.3)
    Return keys:
      - 'points', 'rebounds', 'assists', 'blocks', 'steals', 'fg_pct', 'fg3_pct'
    """

    # Chosen ceilings:
    # - Counting stats target “elite but realistic modern” ceilings (avoids Wilt skew but leaves headroom)
    # - Percentages use realistic maxes so they don’t dwarf counting legs
    CEIL = {
        # counting (per game)
        'PTS': 50,     # 35–37 elite, 50 = “super ceiling”
        'REB': 18,     # 12–14 elite, 18 as ceiling
        'AST': 12,     # 8–10 elite, 12 as ceiling
        'BLK': 4.5,    # 3+ elite, 4.5 ceiling
        'STL': 3.5,    # 2+ elite, 3.5 ceiling

        # percentages (already in % units)
        'FG_PCT': 65,  # elite FG% ceiling ~70 for bigs; 65 balances the chart visually
        'FG3_PCT': 45, # elite 3P% ceiling ~45
        # when I add FT:
        # 'FT_PCT': 90,
    }

    return {
        'points':  _norm(raw.get('PTS'), CEIL['PTS']),
        'rebounds': _norm(raw.get('REB'), CEIL['REB']),
        'assists':  _norm(raw.get('AST'), CEIL['AST']),
        'blocks':   _norm(raw.get('BLK'), CEIL['BLK']),
        'steals':   _norm(raw.get('STL'), CEIL['STL']),
        'fg_pct':   _norm(raw.get('FG_PCT'),  CEIL['FG_PCT']),
        'fg3_pct':  _norm(raw.get('FG3_PCT'), CEIL['FG3_PCT']),
    }