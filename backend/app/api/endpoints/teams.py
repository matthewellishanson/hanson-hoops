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
@router.get("/team_profile_stats")
def get_team_profile_stats(
    team_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    """
    Returns normalized (0–100) team profile stats + raw per-game numbers,
    and an 'opponent' view (normalized as 'lower is better' -> higher score when allowing less).
    Uses TeamDashboardByGeneralSplits to avoid fragile kwarg names on LeagueDashTeamStats.
    """
    try:
        season = season or current_nba_season()
        season_fmt = format_season(season)

        # Pull per-game dashboards (team + opponent)
        dash = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
            team_id=int(team_id),
            season=season_fmt,
            season_type_all_star="Regular Season",
            per_mode_detailed="PerGame",
        ).get_data_frames()

        team_df = dash[0] if len(dash) > 0 else pd.DataFrame()
        opp_df  = dash[1] if len(dash) > 1 else pd.DataFrame()

        if team_df.empty:
            print("[team_profile_stats] Team dashboard empty for", team_id, season_fmt)
            raise ValueError("empty team dashboard")

        # ---- TEAM (per game) ----
        t = team_df.iloc[0]
        # Some frames use pct in 0..1; others already in percent. Detect & scale once.
        def pct_to_100(v):
            try:
                f = float(v)
                return f * 100.0 if 0.0 <= f <= 1.0 else f
            except Exception:
                return 0.0

        team_pts = float(t.get("PTS", 0))
        team_reb = float(t.get("REB", 0))
        team_ast = float(t.get("AST", 0))
        team_blk = float(t.get("BLK", 0))
        team_stl = float(t.get("STL", 0))
        team_fg_pct  = pct_to_100(t.get("FG_PCT", 0))
        team_fg3_pct = pct_to_100(t.get("FG3_PCT", 0))

        norm_team = normalize_stats({
            "PTS": team_pts, "REB": team_reb, "AST": team_ast, "BLK": team_blk, "STL": team_stl,
            "FG_PCT": team_fg_pct, "FG3_PCT": team_fg3_pct,
        })

        # ---- OPPONENT (per game, invert so 'better defense' -> higher score) ----
        # Prefer OPP_* columns if present on team_df; otherwise, read plain columns from opp_df.
        if any(col.startswith("OPP_") for col in team_df.columns):
            raw_opp_pts = float(t.get("OPP_PTS", 0))
            raw_opp_fg  = pct_to_100(t.get("OPP_FG_PCT", 0))
            raw_opp_3p  = pct_to_100(t.get("OPP_FG3_PCT", 0))
        elif not opp_df.empty:
            o = opp_df.iloc[0]
            raw_opp_pts = float(o.get("PTS", 0))
            raw_opp_fg  = pct_to_100(o.get("FG_PCT", 0))
            raw_opp_3p  = pct_to_100(o.get("FG3_PCT", 0))
        else:
            raw_opp_pts = raw_opp_fg = raw_opp_3p = 0.0

        # Invert opponent numbers (lower allowed -> higher score)
        OPP_CEIL = {"PTS": 130.0, "FG_PCT": 60.0, "FG3_PCT": 45.0}
        def inv(v, cap):
            v = max(0.0, min(float(v or 0.0), cap))
            return round((1.0 - (v / cap)) * 100.0, 1)

        return {
            # normalized (team)
            "points":   norm_team["points"],
            "rebounds": norm_team["rebounds"],
            "assists":  norm_team["assists"],
            "blocks":   norm_team["blocks"],
            "steals":   norm_team["steals"],
            "fg_pct":   norm_team["fg_pct"],
            "fg3_pct":  norm_team["fg3_pct"],

            # raw (team)
            "raw_points": round(team_pts, 1),
            "raw_rebounds": round(team_reb, 1),
            "raw_assists": round(team_ast, 1),
            "raw_blocks": round(team_blk, 1),
            "raw_steals": round(team_stl, 1),
            "raw_fg_pct": round(team_fg_pct, 1),
            "raw_fg3_pct": round(team_fg3_pct, 1),

            # normalized (opponent — inverted)
            "opp_points": inv(raw_opp_pts, OPP_CEIL["PTS"]),
            "opp_fg_pct": inv(raw_opp_fg,  OPP_CEIL["FG_PCT"]),
            "opp_fg3_pct":inv(raw_opp_3p,  OPP_CEIL["FG3_PCT"]),

            # raw (opponent)
            "raw_opp_points": round(raw_opp_pts, 1),
            "raw_opp_fg_pct": round(raw_opp_fg, 1),
            "raw_opp_fg3_pct": round(raw_opp_3p, 1),
        }

    except Exception as e:
        print(f"[team_profile_stats] error: {e}")
        return {
            "points":0,"rebounds":0,"assists":0,"blocks":0,"steals":0,"fg_pct":0,"fg3_pct":0,
            "raw_points":0,"raw_rebounds":0,"raw_assists":0,"raw_blocks":0,"raw_steals":0,"raw_fg_pct":0,"raw_fg3_pct":0,
            "opp_points":0,"opp_fg_pct":0,"opp_fg3_pct":0,
            "raw_opp_points":0,"raw_opp_fg_pct":0,"raw_opp_fg3_pct":0,
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
        return {"season": season_fmt, "team_id": team_id, "shots_for": [], "shots_against": []}

    # columns we’ll keep if present
    cols = [
        "LOC_X","LOC_Y","SHOT_MADE_FLAG","TEAM_ID",
        "SHOT_ZONE_BASIC","SHOT_DISTANCE","HTM","VTM"
    ]
    df = df[[c for c in cols if c in df.columns]].copy()

    # --- figure out the team’s tri-code (abbr) from its id ---
    teams_data = static_teams.get_teams()
    team_row = next((t for t in teams_data if int(t["id"]) == int(team_id)), None)
    team_abbr = (team_row or {}).get("abbreviation")
    if not team_abbr:
        # fail soft: fall back to only 'shots_for'
        shots_for_df = df[df["TEAM_ID"] == int(team_id)] if "TEAM_ID" in df.columns else pd.DataFrame()
        def to_events(frame: pd.DataFrame):
            if frame.empty: return []
            return [
                {
                    "x": float(r["LOC_X"]), "y": float(r["LOC_Y"]),
                    "made": bool(r["SHOT_MADE_FLAG"]),
                    "shot_zone": (r["SHOT_ZONE_BASIC"] if pd.notna(r.get("SHOT_ZONE_BASIC")) else None),
                    "shot_distance": (float(r["SHOT_DISTANCE"]) if pd.notna(r.get("SHOT_DISTANCE")) else None),
                }
                for _, r in frame.iterrows()
            ]
        return {
            "season": season_fmt, "team_id": team_id,
            "shots_for": to_events(shots_for_df), "shots_against": []
        }

    # --- build boolean mask: games involving this team (by HTM/VTM) ---
    has_htm = "HTM" in df.columns
    has_vtm = "VTM" in df.columns
    if has_htm and has_vtm:
        # normalize case just in case
        df["HTM"] = df["HTM"].astype(str).str.upper()
        df["VTM"] = df["VTM"].astype(str).str.upper()
        involves_team = (df["HTM"] == team_abbr) | (df["VTM"] == team_abbr)
        df_team_games = df[involves_team].copy()
    else:
        # if HTM/VTM missing somehow, fall back to whole df (less accurate)
        df_team_games = df

    # shots by this team vs by opponent
    shots_for_df = df_team_games[df_team_games["TEAM_ID"] == int(team_id)] if "TEAM_ID" in df_team_games.columns else pd.DataFrame()
    shots_against_df = df_team_games[df_team_games["TEAM_ID"] != int(team_id)] if "TEAM_ID" in df_team_games.columns else pd.DataFrame()

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

    return {
        "season": season_fmt,
        "team_id": team_id,
        "shots_for": to_events(shots_for_df),
        "shots_against": to_events(shots_against_df),
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

