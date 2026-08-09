# app/utils/player_percentiles.py
from functools import lru_cache
import pandas as pd
import inspect
from nba_api.stats.endpoints import leaguedashplayerstats
from app.services.nba_http import nba_call, request_timeout_seconds

def _pct100(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0.0)
    return (s * 100.0) if s.max() <= 1.0 else s

@lru_cache(maxsize=8)
def _player_base_table(season_fmt: str) -> pd.DataFrame:
    """
    LeagueDashPlayerStats (Base, PerGame) for a season.
    """
    base_kwargs = dict(
        season=season_fmt,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
        measure_type_detailed_def="Base",
    )
    # Introspect for league_id(_nullable) differences
    try:
        sig = inspect.signature(leaguedashplayerstats.LeagueDashPlayerStats.__init__)
        params = sig.parameters
    except Exception:
        params = {}
    if "league_id_nullable" in params:
        base_kwargs["league_id_nullable"] = "00"
    elif "league_id" in params:
        base_kwargs["league_id"] = "00"
    if "timeout" in params:
        base_kwargs["timeout"] = request_timeout_seconds()

    df = nba_call(
        "player_percentile_table",
        lambda: leaguedashplayerstats.LeagueDashPlayerStats(**base_kwargs).get_data_frames()[0],
    )
    if df is None or df.empty:
        return pd.DataFrame()

    # normalize % columns to 0–100 and compute FTR% = (FTA/FGA)*100
    df = df.copy()
    if "FT_PCT" in df.columns:
        df["FT_PCT"] = _pct100(df["FT_PCT"])
    if "FGA" in df.columns and "FTA" in df.columns:
        fga = pd.to_numeric(df["FGA"], errors="coerce").fillna(0.0)
        fta = pd.to_numeric(df["FTA"], errors="coerce").fillna(0.0)
        with pd.option_context("mode.use_inf_as_na", True):
            df["FTR_PCT"] = (fta / fga).replace([float("inf")], 0.0) * 100.0
        df["FTR_PCT"] = df["FTR_PCT"].fillna(0.0).clip(lower=0.0)
    else:
        df["FTR_PCT"] = 0.0
    return df

def player_stat_percentile(season_fmt: str, stat: str, value: float) -> float:
    """
    Percentile rank (0–100) of `value` among players for `stat` in `season_fmt`.
    stat: "FT_PCT" or "FTR_PCT"
    """
    try:
        df = _player_base_table(season_fmt)
        if df.empty or stat not in df.columns:
            raise ValueError("no table/column")
        s = pd.to_numeric(df[stat], errors="coerce").dropna()
        if s.empty:
            raise ValueError("empty series")
        v = float(value or 0.0)
        pct = float((s <= v).mean() * 100.0)  # inclusive percentile
        return round(max(0.0, min(100.0, pct)), 1)
    except Exception:
        # sensible caps fallback if league call fails
        if stat == "FT_PCT":
            # map 50–90% -> 0–100
            v = max(50.0, min(90.0, float(value or 0.0)))
            return round(((v - 50.0) / (90.0 - 50.0)) * 100.0, 1)
        if stat == "FTR_PCT":
            # map 0–60% -> 0–100
            v = max(0.0, min(60.0, float(value or 0.0)))
            return round((v / 60.0) * 100.0, 1)
        return 0.0
