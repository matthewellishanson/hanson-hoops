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
    Uses Oct 1 as the season turnover (preseason/training camp).
    """
    today = date.today()
    year = today.year
    # if before Oct, we’re still in the prior season’s label start year
    start_year = year - 1 if today.month < 10 else year
    end = str((start_year + 1) % 100).zfill(2)
    return f"{start_year}-{end}"