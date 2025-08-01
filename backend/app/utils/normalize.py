def normalize_stats(raw_stats):
    max_values = {
        'PTS': 50,
        'REB': 20,
        'AST': 20,
        'BLK': 10,
        'STL': 10,
        'FG_PCT': 90,
        'FG3_PCT': 80
    }
    
    normalized = {
        'points': round((raw_stats['PTS'] / max_values['PTS']) * 100, 1),
        'rebounds': round((raw_stats['REB'] / max_values['REB']) * 100, 1),
        'assists': round((raw_stats['AST'] / max_values['AST']) * 100, 1),
        'blocks': round((raw_stats['BLK'] / max_values['BLK']) * 100, 1),
        'steals': round((raw_stats['STL'] / max_values['STL']) * 100, 1),
        'fg_pct': round((raw_stats['FG_PCT'] / max_values['FG_PCT']) * 100, 1),
        'fg3_pct': round((raw_stats['FG3_PCT'] / max_values['FG3_PCT']) * 100, 1)
    }

    return normalized
