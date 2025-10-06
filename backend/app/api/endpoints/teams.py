# backend/app/api/endpoints/teams.py
from fastapi import APIRouter, Query, HTTPException, Body
from functools import lru_cache
from typing import List, Optional, Literal
import time
import pandas as pd
import logging
import inspect
from requests.exceptions import ReadTimeout
from nba_api.stats.endpoints import (
    shotchartdetail,
    leaguedashteamstats,
    teamdashboardbygeneralsplits,
    teamgamelog,
)
from nba_api.stats.static import teams as static_teams
from ...utils.seasons import format_season, current_nba_season
from ...utils.normalize import normalize_stats

router = APIRouter()

# ---------------------------
# Helpers
# ---------------------------

def _pct100(x):
    """Accept 0–1 or 0–100 and return % in 0–100."""
    try:
        f = float(x)
        return f * 100.0 if 0.0 <= f <= 1.0 else f
    except Exception:
        return 0.0


def _minmax_inv(value: float, mn: float, mx: float) -> float:
    """
    Map value to 0..100 using (mx - v)/(mx - mn).
    Clamps safely and rounds to 1dp.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if mx <= mn:
        return 0.0
    v = min(max(v, mn), mx)
    return round(((mx - v) / (mx - mn)) * 100.0, 1)


def _invert_cap(value: float, cap: float) -> float:
    """
    Normalize where lower is better (e.g., turnovers).
    Returns 0–100 with 100 = 0 (perfect), 0 = cap (worst).
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    v = max(0.0, min(v, float(cap)))
    return round((1.0 - (v / float(cap))) * 100.0, 1)


def _team_pg_from_gamelog(team_id: int, season_fmt: str) -> dict:
    """
    Compute per-game from TeamGameLog by rolling up game totals.
    Returns floats (not rounded) so caller can round as desired.

    Keys returned:
      PTS, REB, AST, STL, BLK, FG_PCT, FG3_PCT, FTM, FT_PCT, TOV
      OPP_PTS (if present), OPP_FG_PCT/OPP_FG3_PCT (if we can compute)
    """
    try:
        gl_kwargs = dict(
            team_id=team_id,
            season=season_fmt,
            season_type_all_star="Regular Season",
        )
        try:
            sig = inspect.signature(teamgamelog.TeamGameLog.__init__)
        except (TypeError, ValueError):
            sig = None
        if sig is not None:
            params = sig.parameters
            if "league_id_nullable" in params:
                gl_kwargs["league_id_nullable"] = "00"
            elif "league_id" in params:
                gl_kwargs["league_id"] = "00"

        gl = teamgamelog.TeamGameLog(**gl_kwargs).get_data_frames()[0]
        if "TEAM_ID" in gl.columns:
            gl = gl[gl["TEAM_ID"] == int(team_id)].copy()

        df = gl.copy()

        # means of game totals
        out = {
            "PTS": float(df["PTS"].astype(float).mean()),
            "REB": float(df["REB"].astype(float).mean()),
            "AST": float(df["AST"].astype(float).mean()),
            "STL": float(df["STL"].astype(float).mean()),
            "BLK": float(df["BLK"].astype(float).mean()),
            "FTM": float(df["FTM"].astype(float).mean()) if "FTM" in df.columns else 0.0,
            "TOV": float(df["TOV"].astype(float).mean()) if "TOV" in df.columns else 0.0,
        }

        # Percentages from totals (BRef-style)
        fgm = float(df.get("FGM", 0).astype(float).sum()) if "FGM" in df.columns else None
        fga = float(df.get("FGA", 0).astype(float).sum()) if "FGA" in df.columns else None
        fg3m = float(df.get("FG3M", 0).astype(float).sum()) if "FG3M" in df.columns else None
        fg3a = float(df.get("FG3A", 0).astype(float).sum()) if "FG3A" in df.columns else None
        ftm_tot = float(df.get("FTM", 0).astype(float).sum()) if "FTM" in df.columns else None
        fta_tot = float(df.get("FTA", 0).astype(float).sum()) if "FTA" in df.columns else None

        if fgm is not None and fga and fga > 0:
            out["FG_PCT"] = (fgm / fga) * 100.0
        elif "FG_PCT" in df.columns:
            out["FG_PCT"] = float(df["FG_PCT"].astype(float).mean()) * (100.0 if df["FG_PCT"].max() <= 1.0 else 1.0)
        else:
            out["FG_PCT"] = 0.0

        if fg3m is not None and fg3a and fg3a > 0:
            out["FG3_PCT"] = (fg3m / fg3a) * 100.0
        elif "FG3_PCT" in df.columns:
            out["FG3_PCT"] = float(df["FG3_PCT"].astype(float).mean()) * (100.0 if df["FG3_PCT"].max() <= 1.0 else 1.0)
        else:
            out["FG3_PCT"] = 0.0

        if ftm_tot is not None and fta_tot and fta_tot > 0:
            out["FT_PCT"] = (ftm_tot / fta_tot) * 100.0
        elif "FT_PCT" in df.columns:
            out["FT_PCT"] = float(df["FT_PCT"].astype(float).mean()) * (100.0 if df["FT_PCT"].max() <= 1.0 else 1.0)
        else:
            out["FT_PCT"] = 0.0

        # Opponent optional
        if "OPP_PTS" in df.columns:
            out["OPP_PTS"] = float(df["OPP_PTS"].astype(float).mean())

        opp_fgm = float(df.get("OPP_FGM", 0).astype(float).sum()) if "OPP_FGM" in df.columns else None
        opp_fga = float(df.get("OPP_FGA", 0).astype(float).sum()) if "OPP_FGA" in df.columns else None
        opp_fg3m = float(df.get("OPP_FG3M", 0).astype(float).sum()) if "OPP_FG3M" in df.columns else None
        opp_fg3a = float(df.get("OPP_FG3A", 0).astype(float).sum()) if "OPP_FG3A" in df.columns else None

        if opp_fgm is not None and opp_fga and opp_fga > 0:
            out["OPP_FG_PCT"] = (opp_fgm / opp_fga) * 100.0
        if opp_fg3m is not None and opp_fg3a and opp_fg3a > 0:
            out["OPP_FG3_PCT"] = (opp_fg3m / opp_fg3a) * 100.0

        return out
    except Exception:
        return {}

# ---------------------------
# Compatibility shim for nba_api
# ---------------------------
def _ldt_compat(*, season: str, season_type: str = "Regular Season",
                per_mode: str = "PerGame", measure: str = "Base") -> pd.DataFrame:
    """
    LeagueDashTeamStats wrapper that detects the correct kwargs by introspection.
    Filters to NBA (TEAM_ID startswith 161061).
    """
    base_kwargs = dict(
        season=season,
        season_type_all_star=season_type,
        per_mode_detailed=per_mode,
    )
    try:
        sig = inspect.signature(leaguedashteamstats.LeagueDashTeamStats.__init__)
        params = sig.parameters
    except Exception:
        params = {}

    if "measure_type_detailed_def" in params:
        measure_kw = {"measure_type_detailed_def": measure}
    elif "measure_type_detailed" in params:
        measure_kw = {"measure_type_detailed": measure}
    else:
        measure_kw = {}

    if "league_id_nullable" in params:
        league_kw = {"league_id_nullable": "00"}
    elif "league_id" in params:
        league_kw = {"league_id": "00"}
    else:
        league_kw = {}

    df = leaguedashteamstats.LeagueDashTeamStats(
        **base_kwargs, **measure_kw, **league_kw
    ).get_data_frames()[0]

    if "TEAM_ID" in df.columns:
        df = df[df["TEAM_ID"].astype(str).str.startswith("161061")].copy()

    return df

# ---------------------------
# Teams endpoint
# ---------------------------
@lru_cache(maxsize=1)
def _all_teams_norm():
    rows = static_teams.get_teams()
    return [
        {
            "id": str(r["id"]),
            "name": r["full_name"],
            "tri_code": r.get("abbreviation"),
            "city": r.get("city"),
            "conference": r.get("conference"),
            "division": r.get("division"),
        }
        for r in rows
    ]


@router.get("/teams")
def list_teams(
    search: Optional[str] = Query(None, description="Substring match on team name"),
    sort: Literal["name", "city", "conference", "division"] = Query("name"),
    order: Literal["asc", "desc"] = Query("asc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    data = _all_teams_norm()

    if search:
        q = search.lower()
        data = [t for t in data if q in t["name"].lower() or q in t["city"].lower()]

    key_map = {"name": "name", "city": "city", "conference": "conference", "division": "division"}
    data.sort(key=lambda t: t[key_map[sort]].lower())
    if order == "desc":
        data.reverse()

    total = len(data)
    items = data[offset: offset + limit]
    return {"total": total, "items": items}

# ---------------------------
# Team Bio
# ---------------------------
@lru_cache(maxsize=512)
def _fetch_team_bio(team_id: str) -> dict | None:
    teams_data = static_teams.get_teams()
    team = next((t for t in teams_data if str(t["id"]) == str(team_id)), None)
    if not team:
        return None
    logo_url = f"https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"
    return {
        "team_id": str(team_id),
        "name": team["full_name"],
        "city": team.get("city"),
        "abbreviation": team.get("abbreviation"),
        "conference": team.get("conference"),
        "division": team.get("division"),
        "logo_url": logo_url,
    }

@router.get("/team_bio")
def get_team_bio(
    team_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    data = _fetch_team_bio(team_id)
    if not data:
        raise HTTPException(status_code=404, detail="Team not found")
    return {
        **data,
        "record": None,
        "standing": None,
        "coach": None,
        "arena": None,
    }

# ---------------------------
# Opponent baselines for defense normalization
# ---------------------------
@lru_cache(maxsize=16)
def _opp_baselines(season_fmt: str) -> dict:
    """
    Per-season min/max for opponent metrics (defense legs). % columns in 0–100.
    """
    try:
        df_opp = _ldt_compat(
            season=season_fmt,
            season_type="Regular Season",
            per_mode="PerGame",
            measure="Opponent"
        )
        if df_opp is None or df_opp.empty:
            raise ValueError("opp table empty")

        def pctcol(series):
            s = pd.to_numeric(series, errors="coerce").fillna(0.0)
            return (s * 100.0) if s.max() <= 1.0 else s

        out = {}
        # PTS + shooting %
        out["PTS"]     = (float(df_opp["OPP_PTS"].min()),     float(df_opp["OPP_PTS"].max()))
        out["FG_PCT"]  = (float(pctcol(df_opp["OPP_FG_PCT"]).min()),  float(pctcol(df_opp["OPP_FG_PCT"]).max()))
        out["FG3_PCT"] = (float(pctcol(df_opp["OPP_FG3_PCT"]).min()), float(pctcol(df_opp["OPP_FG3_PCT"]).max()))
        # New: AST, REB, FTM, FT%
        if "OPP_AST" in df_opp.columns:
            out["AST"] = (float(df_opp["OPP_AST"].min()), float(df_opp["OPP_AST"].max()))
        if "OPP_REB" in df_opp.columns:
            out["REB"] = (float(df_opp["OPP_REB"].min()), float(df_opp["OPP_REB"].max()))
        if "OPP_FTM" in df_opp.columns:
            out["FTM"] = (float(df_opp["OPP_FTM"].min()), float(df_opp["OPP_FTM"].max()))
        # FT% may be named OPP_FT_PCT or OPP_FT_PCT (already); handle generically
        ft_pct_col = "OPP_FT_PCT" if "OPP_FT_PCT" in df_opp.columns else None
        if ft_pct_col:
            ft_pct = pctcol(df_opp[ft_pct_col])
            out["FT_PCT"] = (float(ft_pct.min()), float(ft_pct.max()))

        return out
    except Exception:
        return {}

# ---------------------------
# Team Profile Stats
# ---------------------------
@router.get("/team_profile_stats")
def get_team_profile_stats(
    team_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    """
    Returns normalized team profile (0–100) + raw per-game numbers.
    - Team legs use normalize_stats(kind='team') caps (+ inverted turnovers).
    - Opponent legs use dynamic per-season league min/max (defense → higher=better).
    """
    try:
        season = season or current_nba_season()
        season_fmt = format_season(season)

        # --- TEAM (Base table) ---
        df_team = _ldt_compat(
            season=season_fmt,
            season_type="Regular Season",
            per_mode="PerGame",
            measure="Base",
        )
        row_team = df_team.loc[df_team["TEAM_ID"] == int(team_id)]
        if row_team.empty:
            raise ValueError(f"TEAM_ID {team_id} not found in Base table")
        t = row_team.iloc[0]

        # --- OPPONENT (Opponent table) ---
        df_opp = _ldt_compat(
            season=season_fmt,
            season_type="Regular Season",
            per_mode="PerGame",
            measure="Opponent",
        )
        row_opp = df_opp.loc[df_opp["TEAM_ID"] == int(team_id)]
        if row_opp.empty:
            raise ValueError(f"TEAM_ID {team_id} not found in Opponent table")
        o = row_opp.iloc[0]

        # --- TEAM raw per-game (gamelog preferred for percentages) ---
        pg = _team_pg_from_gamelog(int(team_id), season_fmt)

        if pg:
            team_pts = float(pg.get("PTS", 0.0))
            team_reb = float(pg.get("REB", 0.0))
            team_ast = float(pg.get("AST", 0.0))
            team_blk = float(pg.get("BLK", 0.0))
            team_stl = float(pg.get("STL", 0.0))
            team_tov = float(pg.get("TOV", 0.0))
            team_ftm = float(pg.get("FTM", 0.0))
            team_fg  = float(pg.get("FG_PCT", 0.0))   # 0–100
            team_3p  = float(pg.get("FG3_PCT", 0.0))  # 0–100
            team_ft  = float(pg.get("FT_PCT", 0.0))   # 0–100
        else:
            team_pts = float(t.get("PTS", 0))
            team_reb = float(t.get("REB", 0))
            team_ast = float(t.get("AST", 0))
            team_blk = float(t.get("BLK", 0))
            team_stl = float(t.get("STL", 0))
            team_tov = float(t.get("TOV", 0)) if "TOV" in t else 0.0
            team_ftm = float(t.get("FTM", 0)) if "FTM" in t else 0.0
            team_fg  = _pct100(t.get("FG_PCT", 0))
            team_3p  = _pct100(t.get("FG3_PCT", 0))
            team_ft  = _pct100(t.get("FT_PCT", 0)) if "FT_PCT" in t else 0.0

        # Normalize the team legs using your utility (adds classic legs)
        norm_team = normalize_stats({
            "TEAM_PTS": team_pts,
            "TEAM_REB": team_reb,
            "TEAM_AST": team_ast,
            "TEAM_BLK": team_blk,
            "TEAM_STL": team_stl,
            "TEAM_FG_PCT":  team_fg,
            "TEAM_FG3_PCT": team_3p,
            # extras (normalize.py may ignore; we handle turnovers below)
            "TEAM_FTM": team_ftm,
            "TEAM_FT_PCT": team_ft,
            "TEAM_TOV": team_tov,
        }, kind="team")

        # Add turnovers as an inverted 0–100 (lower is better)
        # and pass through FTM/FT% if your normalize.py supports them later.
        TEAM_CAPS = {"TOV": 20.0}  # sensible ceiling
        norm_tov = _invert_cap(team_tov, TEAM_CAPS["TOV"])

        # --- OPPONENT raw (from Opponent table) ---
        raw_opp_pts = float(o.get("PTS", 0))
        raw_opp_fg  = _pct100(o.get("FG_PCT", 0))
        raw_opp_3p  = _pct100(o.get("FG3_PCT", 0))
        raw_opp_ast = float(o.get("AST", 0)) if "AST" in o else 0.0
        raw_opp_reb = float(o.get("REB", 0)) if "REB" in o else 0.0
        raw_opp_ftm = float(o.get("FTM", 0)) if "FTM" in o else 0.0
        raw_opp_ft  = _pct100(o.get("FT_PCT", 0)) if "FT_PCT" in o else 0.0

        # --- Opponent normalization: dynamic per-season min/max ---
        baselines = _opp_baselines(season_fmt)
        if baselines:
            opp_points = _minmax_inv(raw_opp_pts, *baselines["PTS"])
            opp_fg_pct = _minmax_inv(raw_opp_fg,  *baselines["FG_PCT"])
            opp_fg3_pct= _minmax_inv(raw_opp_3p,  *baselines["FG3_PCT"])
            # new legs if we have baselines
            opp_ast = _minmax_inv(raw_opp_ast, *baselines["AST"]) if "AST" in baselines else 0.0
            opp_reb = _minmax_inv(raw_opp_reb, *baselines["REB"]) if "REB" in baselines else 0.0
            opp_ftm = _minmax_inv(raw_opp_ftm, *baselines["FTM"]) if "FTM" in baselines else 0.0
            opp_ft_pct = _minmax_inv(raw_opp_ft, *baselines["FT_PCT"]) if "FT_PCT" in baselines else 0.0
            scale_hint = "dynamic"
        else:
            # fixed caps fallback
            OPP_CAP = {"PTS": 130.0, "FG_PCT": 60.0, "FG3_PCT": 45.0, "AST": 35.0, "REB": 60.0, "FTM": 35.0, "FT_PCT": 90.0}
            def inv_cap(v, cap):
                v = max(0.0, min(float(v or 0.0), cap))
                return round((1.0 - (v / cap)) * 100.0, 1)
            opp_points = inv_cap(raw_opp_pts, OPP_CAP["PTS"])
            opp_fg_pct = inv_cap(raw_opp_fg,  OPP_CAP["FG_PCT"])
            opp_fg3_pct= inv_cap(raw_opp_3p,  OPP_CAP["FG3_PCT"])
            opp_ast    = inv_cap(raw_opp_ast, OPP_CAP["AST"])
            opp_reb    = inv_cap(raw_opp_reb, OPP_CAP["REB"])
            opp_ftm    = inv_cap(raw_opp_ftm, OPP_CAP["FTM"])
            opp_ft_pct = inv_cap(raw_opp_ft,  OPP_CAP["FT_PCT"])
            scale_hint = "cap"

        return {
            # team (normalized + raw)
            "points":   norm_team["points"],
            "rebounds": norm_team["rebounds"],
            "assists":  norm_team["assists"],
            "blocks":   norm_team["blocks"],
            "steals":   norm_team["steals"],
            "fg_pct":   norm_team["fg_pct"],
            "fg3_pct":  norm_team["fg3_pct"],
            "turnovers": norm_tov,  # NEW (0–100, lower is better)

            "raw_points": round(team_pts, 1),
            "raw_rebounds": round(team_reb, 1),
            "raw_assists": round(team_ast, 1),
            "raw_blocks": round(team_blk, 1),
            "raw_steals": round(team_stl, 1),
            "raw_fg_pct": round(team_fg, 1),
            "raw_fg3_pct": round(team_3p, 1),
            "raw_tov": round(team_tov, 1),  # NEW

            # opponent (normalized + raw)
            "opp_points": opp_points,
            "opp_fg_pct": opp_fg_pct,
            "opp_fg3_pct": opp_fg3_pct,
            "opp_ast": opp_ast,       # NEW
            "opp_reb": opp_reb,       # NEW
            "opp_ftm": opp_ftm,       # NEW
            "opp_ft_pct": opp_ft_pct, # NEW

            "raw_opp_points": round(raw_opp_pts, 1),
            "raw_opp_fg_pct": round(raw_opp_fg, 1),
            "raw_opp_fg3_pct": round(raw_opp_3p, 1),
            "raw_opp_ast": round(raw_opp_ast, 1),     # NEW
            "raw_opp_reb": round(raw_opp_reb, 1),     # NEW
            "raw_opp_ftm": round(raw_opp_ftm, 1),     # NEW
            "raw_opp_ft_pct": round(raw_opp_ft, 1),   # NEW

            "opponent_scale": scale_hint,
            "season": season_fmt,
        }

    except Exception as e:
        print(f"[team_profile_stats] error: {e}")
        return {
            "points":0,"rebounds":0,"assists":0,"blocks":0,"steals":0,"fg_pct":0,"fg3_pct":0,"turnovers":0,
            "raw_points":0,"raw_rebounds":0,"raw_assists":0,"raw_blocks":0,"raw_steals":0,"raw_fg_pct":0,"raw_fg3_pct":0,"raw_tov":0,
            "opp_points":0,"opp_fg_pct":0,"opp_fg3_pct":0,"opp_ast":0,"opp_reb":0,"opp_ftm":0,"opp_ft_pct":0,
            "raw_opp_points":0,"raw_opp_fg_pct":0,"raw_opp_fg3_pct":0,"raw_opp_ast":0,"raw_opp_reb":0,"raw_opp_ftm":0,"raw_opp_ft_pct":0,
            "opponent_scale":"error"
        }

# ---------------------------
# Cached league shots
# ---------------------------
def _fetch_league_shots(season_fmt: str, retries=2, backoff=1.5) -> pd.DataFrame:
    last_err = None
    for attempt in range(retries + 1):
        try:
            sc = shotchartdetail.ShotChartDetail(
                team_id=0,
                player_id=0,
                season_nullable=season_fmt,
                season_type_all_star="Regular Season",
                context_measure_simple="FGA",
            )
            frames = sc.get_data_frames()
            return frames[0] if frames and len(frames) > 0 else pd.DataFrame()
        except ReadTimeout as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
            else:
                break
        except Exception as e:
            last_err = e
            break
    return pd.DataFrame()

@lru_cache(maxsize=8)
def _league_shots_for_season(season_fmt: str) -> pd.DataFrame:
    return _fetch_league_shots(season_fmt)

# ---------------------------
# Team shots
# ---------------------------
@router.get("/team_shots")
def team_shots(team_id: int = Query(...), season: str = Query(...)):
    season_fmt = format_season(season)
    df = _league_shots_for_season(season_fmt)

    if df.empty:
        return {
            "season": season_fmt, "team_id": team_id,
            "shots_for": [], "shots_against": [],
            "summary_for": {"fg_pct": 0.0, "fgm": 0, "fga": 0, "fg3_pct": 0.0, "fg3m": 0, "fg3a": 0},
            "summary_against": {"fg_pct": 0.0, "fgm": 0, "fga": 0, "fg3_pct": 0.0, "fg3m": 0, "fg3a": 0},
        }

    cols = [
        "LOC_X","LOC_Y","SHOT_MADE_FLAG","TEAM_ID",
        "SHOT_ZONE_BASIC","SHOT_DISTANCE","SHOT_TYPE","HTM","VTM"
    ]
    df = df[[c for c in cols if c in df.columns]].copy()

    teams_data = static_teams.get_teams()
    team_row = next((t for t in teams_data if int(t["id"]) == int(team_id)), None)
    team_abbr = (team_row or {}).get("abbreviation")

    if "HTM" in df.columns and "VTM" in df.columns and team_abbr:
        df["HTM"] = df["HTM"].astype(str).str.upper()
        df["VTM"] = df["VTM"].astype(str).str.upper()
        involves = (df["HTM"] == team_abbr) | (df["VTM"] == team_abbr)
        df = df[involves].copy()

    shots_for_df = df[df["TEAM_ID"] == int(team_id)] if "TEAM_ID" in df.columns else pd.DataFrame()
    shots_against_df = df[df["TEAM_ID"] != int(team_id)] if "TEAM_ID" in df.columns else pd.DataFrame()

    def to_events(frame: pd.DataFrame) -> List[dict]:
        if frame.empty: return []
        return [
            {
                "x": float(r["LOC_X"]),
                "y": float(r["LOC_Y"]),
                "made": bool(r["SHOT_MADE_FLAG"]),
                "shot_zone": (r["SHOT_ZONE_BASIC"] if pd.notna(r.get("SHOT_ZONE_BASIC")) else None),
                "shot_distance": (float(r["SHOT_DISTANCE"]) if pd.notna(r.get("SHOT_DISTANCE")) else None),
            }
            for _, r in frame.iterrows()
        ]

    def summarize(frame: pd.DataFrame) -> dict:
        if frame.empty:
            return {"fg_pct": 0.0, "fgm": 0, "fga": 0, "fg3_pct": 0.0, "fg3m": 0, "fg3a": 0}
        fga = int(len(frame))
        fgm = int(frame["SHOT_MADE_FLAG"].fillna(0).astype(int).sum())
        fg_pct = round((fgm / fga) * 100.0, 1) if fga else 0.0

        if "SHOT_TYPE" in frame.columns:
            threes = frame[frame["SHOT_TYPE"].astype(str).str.startswith("3PT", na=False)]
        else:
            threes = frame[frame.get("SHOT_DISTANCE", pd.Series(dtype=float)) >= 23]

        fg3a = int(len(threes))
        fg3m = int(threes["SHOT_MADE_FLAG"].fillna(0).astype(int).sum()) if fg3a else 0
        fg3_pct = round((fg3m / fg3a) * 100.0, 1) if fg3a else 0.0

        return {"fg_pct": fg_pct, "fgm": fgm, "fga": fga, "fg3_pct": fg3_pct, "fg3m": fg3m, "fg3a": fg3a}

    return {
        "season": season_fmt,
        "team_id": team_id,
        "shots_for": to_events(shots_for_df),
        "shots_against": to_events(shots_against_df),
        "summary_for": summarize(shots_for_df),
        "summary_against": summarize(shots_against_df),
    }

# ---------------------------
# Debug helpers
# ---------------------------

@router.get("/_debug/team_gamelog")
def debug_team_gamelog(team_id: int = Query(...), season: str = Query(...)):
    season_fmt = format_season(season)
    try:
        gl_kwargs = dict(
            team_id=team_id,
            season=season_fmt,
            season_type_all_star="Regular Season",
        )
        try:
            sig = inspect.signature(teamgamelog.TeamGameLog.__init__)
        except (TypeError, ValueError):
            sig = None
        if sig is not None:
            params = sig.parameters
            if "league_id_nullable" in params:
                gl_kwargs["league_id_nullable"] = "00"
            elif "league_id" in params:
                gl_kwargs["league_id"] = "00"

        gl = teamgamelog.TeamGameLog(**gl_kwargs).get_data_frames()[0]
    except Exception as e:
        return {"season": season_fmt, "team_id": team_id, "error": str(e)}

    if gl is None or gl.empty:
        return {"season": season_fmt, "team_id": team_id, "empty": True}

    df = gl.copy()
    head = df.head(3).to_dict(orient="records")

    def safe_sum(col):
        return float(df.get(col, 0).astype(float).sum()) if col in df.columns else 0.0

    fgm, fga = safe_sum("FGM"), safe_sum("FGA")
    fg3m, fg3a = safe_sum("FG3M"), safe_sum("FG3A")
    opp_fgm, opp_fga = safe_sum("OPP_FGM"), safe_sum("OPP_FGA")
    opp_fg3m, opp_fg3a = safe_sum("OPP_FG3M"), safe_sum("OPP_FG3A")
    ftm_tot, fta_tot = safe_sum("FTM"), safe_sum("FTA")

    pg = {
        "PTS": float(df.get("PTS", 0).astype(float).mean()) if "PTS" in df.columns else 0.0,
        "REB": float(df.get("REB", 0).astype(float).mean()) if "REB" in df.columns else 0.0,
        "AST": float(df.get("AST", 0).astype(float).mean()) if "AST" in df.columns else 0.0,
        "STL": float(df.get("STL", 0).astype(float).mean()) if "STL" in df.columns else 0.0,
        "BLK": float(df.get("BLK", 0).astype(float).mean()) if "BLK" in df.columns else 0.0,
        "TOV": float(df.get("TOV", 0).astype(float).mean()) if "TOV" in df.columns else 0.0,
        "FTM": float(df.get("FTM", 0).astype(float).mean()) if "FTM" in df.columns else 0.0,
        "FG_PCT": (fgm / fga * 100.0) if fga > 0 else None,
        "FG3_PCT": (fg3m / fg3a * 100.0) if fg3a > 0 else None,
        "FT_PCT": (ftm_tot / fta_tot * 100.0) if fta_tot > 0 else None,
    }

    if "OPP_PTS" in df.columns:
        pg["OPP_PTS"] = float(df["OPP_PTS"].astype(float).mean())
    if opp_fga > 0:
        pg["OPP_FG_PCT"] = (opp_fgm / opp_fga) * 100.0
    if opp_fg3a > 0:
        pg["OPP_FG3_PCT"] = (opp_fg3m / opp_fg3a) * 100.0

    return {
        "season": season_fmt,
        "team_id": team_id,
        "columns": list(df.columns),
        "games": int(len(df)),
        "head": head,
        "totals": {
            "FGM": fgm, "FGA": fga, "FG3M": fg3m, "FG3A": fg3a,
            "FTM": ftm_tot, "FTA": fta_tot,
            "OPP_FGM": opp_fgm, "OPP_FGA": opp_fga, "OPP_FG3M": opp_fg3m, "OPP_FG3A": opp_fg3a
        },
        "per_game_calc": pg
    }

@router.get("/_debug/leaguedashteamstats")
def debug_leaguedashteamstats(
    season: str = Query(..., description="e.g. 2023-24"),
    season_type: str = Query("Regular Season"),
):
    try:
        df_team = _ldt_compat(season=season, season_type=season_type, per_mode="PerGame", measure="Base")
    except Exception as e:
        df_team = pd.DataFrame()
        team_err = str(e)
    else:
        team_err = None

    try:
        df_opp  = _ldt_compat(season=season, season_type=season_type, per_mode="PerGame", measure="Opponent")
    except Exception as e:
        df_opp = pd.DataFrame()
        opp_err = str(e)
    else:
        opp_err = None

    def brief(df: pd.DataFrame):
        return {
            "rows": 0 if df is None else int(len(df)),
            "cols": [] if df is None or df.empty else list(df.columns),
            "sample_team_ids": [] if df is None or df.empty or "TEAM_ID" not in df.columns else list(map(int, df["TEAM_ID"].head(8))),
            "head": [] if df is None or df.empty else df.head(3).to_dict(orient="records"),
        }

    return {
        "season": season,
        "season_type": season_type,
        "base": brief(df_team),
        "opponent": brief(df_opp),
        "errors": {"base": team_err, "opponent": opp_err},
    }
