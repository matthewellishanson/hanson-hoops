def normalize_stats(raw):
    max_values = {
    # basic
    'PTS': 130, 'REB': 60, 'OREB': 30, 'DREB': 50, 'AST': 40, 'BLK': 15, 'STL': 20,
    'FG_PCT': 65, 'FG3_PCT': 45, 'FT_PCT': 90,
    # advanced
    'OFF_RTG': 130, 'DEF_RTG': 130, 'PTS_100': 130,
    'AST_TO': 3.5, 'EFG_PCT': 65, 'FTA_RATE': 0.6,
    'EXP_FG_PCT': 60, 'EXP_3P_PCT': 45,
    }
    return {
        'points': round((raw['PTS'] / max_values['PTS']) * 100, 1),
        'rebounds': round((raw['REB'] / max_values['REB']) * 100, 1),
        'assists': round((raw['AST'] / max_values['AST']) * 100, 1),
        'blocks': round((raw['BLK'] / max_values['BLK']) * 100, 1),
        'steals': round((raw['STL'] / max_values['STL']) * 100, 1),
        'fg_pct': round((raw['FG_PCT'] / max_values['FG_PCT']) * 100, 1),
        'fg3_pct': round((raw['FG3_PCT'] / max_values['FG3_PCT']) * 100, 1),
    }
