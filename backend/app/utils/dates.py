from datetime import datetime, date

def _parse_birthdate_iso(birthdate_str: str | None) -> date | None:
    """NBA API birthdate example: '1984-12-30T00:00:00' (sometimes with 'Z')."""
    if not birthdate_str:
        return None
    try:
        return datetime.fromisoformat(birthdate_str.replace("Z", "")).date()
    except Exception:
        return None

def _season_start_date(season_fmt: str) -> date:
    """
    Convert 'YYYY-YY' -> season start date.
    We’ll use Oct 1 as a stable anchor (preseason/early regular season window).
    Adjust if you want Sep 1 instead; you used Sep logic on the frontend already.
    """
    start_year = int(season_fmt.split("-")[0])
    return date(start_year, 10, 1)  # Oct 1 of the start year

def _age_on(born: date, asof: date) -> int:
    """Age in whole years at a given reference date."""
    return asof.year - born.year - ((asof.month, asof.day) < (born.month, born.day))

def _age_at_season_start(birthdate_str: str | None, season: str | None) -> int | None:
    """
    If season provided -> age as of season start.
    If season omitted -> age as of *today* (keeps old behavior).
    """
    born = _parse_birthdate_iso(birthdate_str)
    if not born:
        return None
    if season:
        # format_season lets you pass “2024” or “2024-25”
        from .seasons import format_season
        season_fmt = format_season(season)
        asof = _season_start_date(season_fmt)
    else:
        asof = date.today()
    return _age_on(born, asof)
