from datetime import datetime

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

