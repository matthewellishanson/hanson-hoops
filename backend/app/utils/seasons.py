from datetime import datetime

"""Utility functions for handling NBA seasons.
"""
def format_season(year):
    """Format a given year into an NBA season string.
    Args:
        year (str or int): The year to format, must be a 4-digit string or integer.
    Returns:
        str: The formatted NBA season string in the format 'YYYY-YY'.
    """
    if isinstance(year, int):
        year = str(year)
    year = year.strip()

    if len(year) != 4 or not year.isdigit():
        raise ValueError("Year must be a 4-digit string or integer.")

    start_year = int(year)
    current_year = datetime.now().year
    if start_year < 1979 or start_year > current_year:
        raise ValueError(f"Year must be between 1979 and {current_year}.")

    # Get last two digits of next year, zero-padded (e.g., 2023 -> '24')
    end_year = str((start_year + 1) % 100).zfill(2)
    return f"{start_year}-{end_year}"
