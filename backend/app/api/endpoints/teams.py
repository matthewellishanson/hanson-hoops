from fastapi import APIRouter, Query, HTTPException, Body
from functools import lru_cache
from typing import List, Optional, Literal
import time
import pandas as pd
import logging
from requests.exceptions import ReadTimeout
from nba_api.stats.endpoints import shotchartdetail, leaguedashteamstats, teamdashboardbygeneralsplits, teamgamelog
from nba_api.stats.static import teams as static_teams
from ...utils.seasons import format_season, current_nba_season
from ...utils.normalize import normalize_stats


router = APIRouter()

# opponent normalization

# ---------------------------
def _pct100(x):
    try:
        f = float(x)
        return f * 100.0 if 0.0 <= f <= 1.0 else f
    except Exception:
        return 0.0

@lru_cache(maxsize=16)
def _opp_baselines(season_fmt: str) -> dict:
    """
    Per-season league min/max for opponent metrics.
    Returns {} on failure (so we can fall back).
    """
    try:
        df = _ldt_compat(
            season=season_fmt,
            season_type="Regular Season",
            per_mode="PerGame",
            measure="Opponent",
        )
        if df is None or df.empty:
            return {}

        # Ensure 0..100 units for pcts
        opp_pts = pd.to_numeric(df.get("OPP_PTS"), errors="coerce").fillna(0.0)
        opp_fg  = pd.to_numeric(df.get("OPP_FG_PCT"), errors="coerce").fillna(0.0)
        opp_3p  = pd.to_numeric(df.get("OPP_FG3_PCT"), errors="coerce").fillna(0.0)
        if opp_fg.max() <= 1.0:  opp_fg  = opp_fg  * 100.0
        if opp_3p.max() <= 1.0:  opp_3p  = opp_3p  * 100.0

        return {
            "PTS":     (float(opp_pts.min()), float(opp_pts.max())),
            "FG_PCT":  (float(opp_fg.min()),  float(opp_fg.max())),
            "FG3_PCT": (float(opp_3p.min()),  float(opp_3p.max())),
        }
    except Exception:
        return {}

def _minmax_inv(value: float, mn: float, mx: float) -> float:
    """
    score = (max - value) / (max - min) * 100, clamped and rounded.
    Lower allowed -> higher score.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if mx <= mn:
        return 0.0
    v = min(max(v, mn), mx)
    return round(((mx - v) / (mx - mn)) * 100.0, 1)
# -------------------------
# Compatibility shim for nba_api
# -------------------------

def _ldt_compat(*, season: str, season_type: str = "Regular Season",
                per_mode: str = "PerGame", measure: str = "Base") -> pd.DataFrame:
    """
    Compatibility wrapper for LeagueDashTeamStats parameter name change.
    Tries 'measure_type_detailed_def' first, falls back to 'measure_type_detailed'.
    """
    try:
        df = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            season_type_all_star=season_type,
            per_mode_detailed=per_mode,
            measure_type_detailed_def=measure,
        ).get_data_frames()[0]
        return df
    except TypeError:
        # Older nba_api versions expect 'measure_type_detailed'
        df = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            season_type_all_star=season_type,
            per_mode_detailed=per_mode,
            measure_type_detailed=measure,
        ).get_data_frames()[0]
        return df


# -------------------------
# Teams endpoint
# -------------------------
@lru_cache(maxsize=1)
def _all_teams_norm():
    # Get all NBA teams from static data
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

# -------------------------
# Team Bio
# -------------------------
@lru_cache(maxsize=512)
def _fetch_team_bio(team_id: str) -> dict | None:
    """Fetch basic team information from static data"""
    teams_data = static_teams.get_teams()
    team = next((t for t in teams_data if str(t["id"]) == str(team_id)), None)
    
    if not team:
        return None
    
    # Construct logo URL (NBA.com format)
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
    
    # For now, return basic team info
    # TODO: Add season-specific data like record, standing, coach, arena
    return {
        **data,
        "record": None,  # TODO: implement
        "standing": None,  # TODO: implement
        "coach": None,  # TODO: implement
        "arena": None,  # TODO: implement
    }

# -------------------------
# Team Profile Stats
# -------------------------
# --- helper: pull opponent table + compute season baselines ---
@lru_cache(maxsize=16)
def _opp_baselines(season_fmt: str) -> dict:
    """
    Return per-season min/max for opponent metrics (used to scale defense).
    Output:
      {
        'PTS': (min_pts, max_pts),
        'FG_PCT': (min_fg, max_fg),
        'FG3_PCT': (min_3p, max_3p),
      }
    Values are in *percent units* for pct metrics (0–100).
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

        # Ensure % columns are in 0..100 (nba_api may return 0..1)
        def pct100(s):
            s = pd.to_numeric(s, errors="coerce")
            s = s.fillna(0.0)
            # If max <= 1, it’s ratios → convert
            return (s * 100.0) if s.max() <= 1.0 else s

        opp_pts  = pd.to_numeric(df_opp.get("OPP_PTS"), errors="coerce").fillna(0.0)
        opp_fg   = pct100(df_opp.get("OPP_FG_PCT"))
        opp_fg3  = pct100(df_opp.get("OPP_FG3_PCT"))

        return {
            "PTS":     (float(opp_pts.min()), float(opp_pts.max())),
            "FG_PCT":  (float(opp_fg.min()),  float(opp_fg.max())),
            "FG3_PCT": (float(opp_fg3.min()), float(opp_fg3.max())),
        }
    except Exception:
        # signal fallback by returning {}
        return {}


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

@router.get("/team_profile_stats")
def get_team_profile_stats(
    team_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    """
    Returns normalized team profile (0–100) + raw per-game numbers.
    - Team legs use your normalize_stats(kind='team') caps.
    - Opponent legs use dynamic per-season league min/max (defense → higher=better).
    """
    try:
        season = season or current_nba_season()
        season_fmt = format_season(season)

        dash = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
            team_id=int(team_id),
            season=season_fmt,
            season_type_all_star="Regular Season",
            per_mode_detailed="PerGame",
        ).get_data_frames()

        team_df = dash[0] if len(dash) > 0 else pd.DataFrame()
        opp_df  = dash[1] if len(dash) > 1 else pd.DataFrame()
        if team_df.empty:
            raise ValueError("empty team dashboard")

        # --- TEAM (per-game) ---
        t = team_df.iloc[0]
        def pct100(x):
            try:
                f = float(x)
                return f * 100.0 if 0.0 <= f <= 1.0 else f
            except Exception:
                return 0.0

        team_pts = float(t.get("PTS", 0))
        team_reb = float(t.get("REB", 0))
        team_ast = float(t.get("AST", 0))
        team_blk = float(t.get("BLK", 0))
        team_stl = float(t.get("STL", 0))
        team_fg  = pct100(t.get("FG_PCT", 0))
        team_3p  = pct100(t.get("FG3_PCT", 0))

        norm_team = normalize_stats({
            "TEAM_PTS": team_pts,
            "TEAM_REB": team_reb,
            "TEAM_AST": team_ast,
            "TEAM_BLK": team_blk,
            "TEAM_STL": team_stl,
            "TEAM_FG_PCT":  team_fg,
            "TEAM_FG3_PCT": team_3p,
        }, kind="team")

        # --- OPPONENT raw (prefer OPP_* on team_df, else opp_df) ---
        # --- OPPONENT raw (prefer OPP_* on team_df, else opp_df) ---
        if any(c.startswith("OPP_") for c in team_df.columns):
            raw_opp_pts = float(t.get("OPP_PTS", 0))
            raw_opp_fg  = _pct100(t.get("OPP_FG_PCT", 0))
            raw_opp_3p  = _pct100(t.get("OPP_FG3_PCT", 0))
        elif not opp_df.empty:
            o = opp_df.iloc[0]
            raw_opp_pts = float(o.get("PTS", 0))
            raw_opp_fg  = _pct100(o.get("FG_PCT", 0))
            raw_opp_3p  = _pct100(o.get("FG3_PCT", 0))
        else:
            raw_opp_pts = raw_opp_fg = raw_opp_3p = 0.0

        # --- Opponent normalization: dynamic min/max per season ---
        baselines = _opp_baselines(season_fmt)
        if baselines:
            opp_points = _minmax_inv(raw_opp_pts, *baselines["PTS"])
            opp_fg_pct = _minmax_inv(raw_opp_fg,  *baselines["FG_PCT"])
            opp_fg3_pct= _minmax_inv(raw_opp_3p,  *baselines["FG3_PCT"])
            scale_hint = "dynamic"
        else:
            # fallback to fixed caps if baselines unavailable
            OPP_CAP = {"PTS": 130.0, "FG_PCT": 60.0, "FG3_PCT": 45.0}
            def inv_cap(v, cap):
                v = max(0.0, min(float(v or 0.0), cap))
                return round((1.0 - (v / cap)) * 100.0, 1)
            opp_points = inv_cap(raw_opp_pts, OPP_CAP["PTS"])
            opp_fg_pct = inv_cap(raw_opp_fg,  OPP_CAP["FG_PCT"])
            opp_fg3_pct= inv_cap(raw_opp_3p,  OPP_CAP["FG3_PCT"])
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

            "raw_points": round(team_pts, 1),
            "raw_rebounds": round(team_reb, 1),
            "raw_assists": round(team_ast, 1),
            "raw_blocks": round(team_blk, 1),
            "raw_steals": round(team_stl, 1),
            "raw_fg_pct": round(team_fg, 1),
            "raw_fg3_pct": round(team_3p, 1),

            # opponent (normalized with dynamic per-season scale) + raw
            "opp_points": opp_points,
            "opp_fg_pct": opp_fg_pct,
            "opp_fg3_pct": opp_fg3_pct,

            "raw_opp_points": round(raw_opp_pts, 1),
            "raw_opp_fg_pct": round(raw_opp_fg, 1),
            "raw_opp_fg3_pct": round(raw_opp_3p, 1),

            # optional metadata for debugging / transparency
            "opponent_scale": scale_hint,
            "season": season_fmt,
        }

    except Exception as e:
        print(f"[team_profile_stats] error: {e}")
        return {
            "points":0,"rebounds":0,"assists":0,"blocks":0,"steals":0,"fg_pct":0,"fg3_pct":0,
            "raw_points":0,"raw_rebounds":0,"raw_assists":0,"raw_blocks":0,"raw_steals":0,"raw_fg_pct":0,"raw_fg3_pct":0,
            "opp_points":0,"opp_fg_pct":0,"opp_fg3_pct":0,
            "raw_opp_points":0,"raw_opp_fg_pct":0,"raw_opp_fg3_pct":0,
            "opponent_scale":"error"
        }




# -------------------------
# Cached league shots
# -------------------------
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
    # Last resort: empty df (prevents 500 → keeps CORS headers)
    return pd.DataFrame()

@lru_cache(maxsize=8)
def _league_shots_for_season(season_fmt: str) -> pd.DataFrame:
    return _fetch_league_shots(season_fmt)

# -------------------------
# Team shots
# -------------------------
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

    # keep columns we need (add SHOT_TYPE so we can compute 3P%)
    cols = [
        "LOC_X","LOC_Y","SHOT_MADE_FLAG","TEAM_ID",
        "SHOT_ZONE_BASIC","SHOT_DISTANCE","SHOT_TYPE","HTM","VTM"
    ]
    df = df[[c for c in cols if c in df.columns]].copy()

    # --- lookup team abbreviation ---
    teams_data = static_teams.get_teams()
    team_row = next((t for t in teams_data if int(t["id"]) == int(team_id)), None)
    team_abbr = (team_row or {}).get("abbreviation")

    # filter to games that involve this team using HTM/VTM (if present)
    if "HTM" in df.columns and "VTM" in df.columns and team_abbr:
        df["HTM"] = df["HTM"].astype(str).str.upper()
        df["VTM"] = df["VTM"].astype(str).str.upper()
        involves = (df["HTM"] == team_abbr) | (df["VTM"] == team_abbr)
        df = df[involves].copy()

    # split
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

        # detect threes via SHOT_TYPE if available (e.g., "3PT Field Goal")
        if "SHOT_TYPE" in frame.columns:
            threes = frame[frame["SHOT_TYPE"].astype(str).str.startswith("3PT", na=False)]
        else:
            # crude fallback: treat >= 23 ft as a 3 (NBA arc ~23'9" above break)
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



# debug only
@router.get("/_debug/leaguedashteamstats")
def debug_leaguedashteamstats(
    season: str = Query(..., description="e.g. 2023-24"),
    season_type: str = Query("Regular Season"),
):
    # Call exactly the two tables we use, return shapes/columns + a few IDs
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

@router.get("/debug/team_shots_columns")
def debug_team_shots_columns(season: str = Query(...)):
    season_fmt = format_season(season)
    df = _league_shots_for_season(season_fmt)
    cols = list(df.columns) if not df.empty else []
    sample = df.head(3).to_dict(orient="records") if not df.empty else []
    return {
        "season": season_fmt,
        "empty": df.empty,
        "cols": cols,
        "has_TEAM_ID": "TEAM_ID" in cols,
        "has_OPPONENT_TEAM_ID": "OPPONENT_TEAM_ID" in cols,
        "sample": sample,
    }

