# backend/app/utils/percentiles.py
from functools import lru_cache
import pandas as pd
import inspect

from nba_api.stats.endpoints import leaguedashplayerstats, leaguedashteamstats
from app.services.nba_http import nba_call, request_timeout_seconds

# -------- helpers --------

def _pct_series(s: pd.Series) -> pd.Series:
    """Compute percentiles (0–100) for a numeric series; NaNs -> 0."""
    s_num = pd.to_numeric(s, errors="coerce")
    pct = s_num.rank(pct=True).fillna(0.0) * 100.0
    return pct

def _invert_0_100(s: pd.Series) -> pd.Series:
    """Invert 0–100 scale (lower-is-better stats)."""
    return 100.0 - s

# -------- players --------

@lru_cache(maxsize=16)
def league_players_table(season_fmt: str) -> pd.DataFrame:
    """League-wide per-player per-game base table for a season."""
    # Build kwargs compatibly across nba_api versions
    base_kwargs = dict(
        season=season_fmt,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
        measure_type_detailed_def="Base",
    )
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
        "percentiles_league_players",
        lambda: leaguedashplayerstats.LeagueDashPlayerStats(**base_kwargs).get_data_frames()[0],
    )
    # Defensive: ensure the columns we care about exist
    return df

@lru_cache(maxsize=16)
def player_percentile_table(season_fmt: str) -> pd.DataFrame:
    """Return a dataframe indexed by PLAYER_ID with percentile columns 0–100."""
    df = league_players_table(season_fmt).copy()
    if df is None or df.empty:
        return pd.DataFrame()

    # Make a clean index
    if "PLAYER_ID" not in df.columns:
        return pd.DataFrame()
    df["PLAYER_ID"] = pd.to_numeric(df["PLAYER_ID"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["PLAYER_ID"]).copy()

    # Columns we want for your radar:
    cols = {
        "PTS": "pts_pct",
        "REB": "reb_pct",
        "AST": "ast_pct",
        "BLK": "blk_pct",
        "STL": "stl_pct",
        "FG_PCT": "fg_pct_pct",     # yes, a bit tautological
        "FG3_PCT": "fg3_pct_pct",
        "TOV": "tov_pct",           # lower-better → invert
        # extras you may show in hovers:
        "FT_PCT": "ft_pct_pct",
        # “free-throw rate” isn’t native here; you compute from logs in your endpoint,
        # so if you want FTR percentile too, you can add it in the endpoint (see notes).
    }

    out = pd.DataFrame(index=df["PLAYER_ID"].astype(int))

    for src, dst in cols.items():
        if src in df.columns:
            pct = _pct_series(df[src])
            if src == "TOV":
                pct = _invert_0_100(pct)
            out[dst] = pct
        else:
            out[dst] = 0.0

    return out

def player_row_percentiles(player_id: int, season_fmt: str) -> dict:
    """Return a dict of percentiles for one player_id."""
    tbl = player_percentile_table(season_fmt)
    if tbl is None or tbl.empty or player_id not in tbl.index:
        return {}
    row = tbl.loc[int(player_id)].to_dict()
    # coerce to float with 1 decimal like your normalize
    return {k: round(float(v), 1) for k, v in row.items()}

# -------- teams --------

@lru_cache(maxsize=16)
def league_teams_table(season_fmt: str, measure: str = "Base") -> pd.DataFrame:
    base_kwargs = dict(
        season=season_fmt,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )
    try:
        sig = inspect.signature(leaguedashteamstats.LeagueDashTeamStats.__init__)
        params = sig.parameters
    except Exception:
        params = {}

    if "measure_type_detailed_def" in params:
        base_kwargs["measure_type_detailed_def"] = measure
    elif "measure_type_detailed" in params:
        base_kwargs["measure_type_detailed"] = measure

    if "league_id_nullable" in params:
        base_kwargs["league_id_nullable"] = "00"
    elif "league_id" in params:
        base_kwargs["league_id"] = "00"
    if "timeout" in params:
        base_kwargs["timeout"] = request_timeout_seconds()

    df = nba_call(
        f"percentiles_league_teams:{measure}",
        lambda: leaguedashteamstats.LeagueDashTeamStats(**base_kwargs).get_data_frames()[0],
    )
    return df

@lru_cache(maxsize=16)
def team_percentile_table(season_fmt: str) -> pd.DataFrame:
    """Percentiles for TEAM Base metrics (0–100), indexed by TEAM_ID."""
    df = league_teams_table(season_fmt, "Base").copy()
    if df is None or df.empty:
        return pd.DataFrame()
    df["TEAM_ID"] = pd.to_numeric(df["TEAM_ID"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["TEAM_ID"]).copy()

    cols = {
        "PTS": "pts_pct",
        "REB": "reb_pct",
        "AST": "ast_pct",
        "BLK": "blk_pct",
        "STL": "stl_pct",
        "FG_PCT": "fg_pct_pct",
        "FG3_PCT": "fg3_pct_pct",
        "TOV": "tov_pct",   # invert
        # optional extras:
        "FTM": "ftm_pct",
        "FT_PCT": "ft_pct_pct",
    }

    out = pd.DataFrame(index=df["TEAM_ID"].astype(int))
    for src, dst in cols.items():
        if src in df.columns:
            pct = _pct_series(df[src])
            if src == "TOV":
                pct = _invert_0_100(pct)
            out[dst] = pct
        else:
            out[dst] = 0.0

    return out

def team_row_percentiles(team_id: int, season_fmt: str) -> dict:
    tbl = team_percentile_table(season_fmt)
    if tbl is None or tbl.empty or team_id not in tbl.index:
        return {}
    row = tbl.loc[int(team_id)].to_dict()
    return {k: round(float(v), 1) for k, v in row.items()}

# ---------- Opponent percentiles ----------
@lru_cache(maxsize=16)
def team_opponent_percentile_table(season_fmt: str) -> pd.DataFrame:
    """
    Percentiles for OPP_* metrics where *lower is better*. We invert the percentile
    so that 100 = best defense (lowest allowed), 0 = worst (highest allowed).
    """
    df = league_teams_table(season_fmt, "Opponent").copy()
    if df is None or df.empty: return pd.DataFrame()

    # nba_api uses columns like OPP_PTS, OPP_FG_PCT, OPP_FG3_PCT, OPP_AST, OPP_REB, OPP_FTM, OPP_FT_PCT
    df["TEAM_ID"] = pd.to_numeric(df["TEAM_ID"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["TEAM_ID"]).copy()

    # Map opponent columns → output columns (defense legs)
    cols = {
        "OPP_PTS": "opp_points_pct",
        "OPP_FG_PCT": "opp_fg_pct_pct",
        "OPP_FG3_PCT": "opp_fg3_pct_pct",
        "OPP_AST": "opp_ast_pct",
        "OPP_REB": "opp_reb_pct",
        "OPP_FTM": "opp_ftm_pct",
        "OPP_FT_PCT": "opp_ft_pct_pct",
    }

    out = pd.DataFrame(index=df["TEAM_ID"].astype(int))
    for src, dst in cols.items():
        if src in df.columns:
            # If % is in 0–1, convert to 0–100 first so ranking is consistent. Rank doesn’t care, but good hygiene.
            series = pd.to_numeric(df[src], errors="coerce").fillna(0.0)
            if series.max() <= 1.0:
                series = series * 100.0
            pct = _pct_series(series)
            # Invert because lower OPP_* means better defense.
            out[dst] = _invert_0_100(pct)
        else:
            out[dst] = 0.0

    return out

def team_row_opponent_percentiles(team_id: int, season_fmt: str) -> dict:
    tbl = team_opponent_percentile_table(season_fmt)
    if tbl is None or tbl.empty or team_id not in tbl.index: return {}
    row = tbl.loc[int(team_id)].to_dict()
    return {k: round(float(v), 1) for k, v in row.items()}
