from datetime import datetime, date

"""Utility functions for handling NBA seasons.
"""
def format_season(year_or_season):
    """
    Converts '2023' -> '2023-24'
    Passes through if already formatted like '2023-24'
    """
    s = str(year_or_season).strip()
    if "-" in s:
        return s
    if len(s) == 4 and s.isdigit():
        return f"{s}-{str((int(s)+1) % 100).zfill(2)}"
    raise ValueError("Invalid season format")

def current_nba_season() -> str:
    """
    Returns the current NBA season label like '2024-25'.
    Uses Sept 9 as the season turnover (preseason/training camp).
    """
    # Treat Sep (9) and later as new season start
    today = date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}-{str((start + 1) % 100).zfill(2)}"