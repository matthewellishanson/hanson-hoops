from fastapi import APIRouter, Query, HTTPException
from functools import lru_cache
from nba_api.stats.endpoints import shotchartdetail, teamgamelog, teamdashboardbygeneralsplits
from nba_api.stats.static import teams as static_teams
from ...utils.seasons import format_season, current_nba_season
from ...utils.normalize import normalize_stats
from typing import List, Optional, Literal
import pandas as pd

router = APIRouter()

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
    try:
        season = season or current_nba_season()
        formatted_season = format_season(season)
        
        # Get team dashboard stats
        dashboard = teamdashboardbygeneralsplits.TeamDashboardByGeneralSplits(
            team_id=team_id,
            season=formatted_season,
            season_type_all_star="Regular Season"
        ).get_data_frames()
        
        if not dashboard or len(dashboard) == 0 or dashboard[0].empty:
            # Return empty stats if no data
            return {
                "points": 0, "rebounds": 0, "assists": 0, "blocks": 0, "steals": 0,
                "fg_pct": 0, "fg3_pct": 0,
                "raw_points": 0, "raw_rebounds": 0, "raw_assists": 0, 
                "raw_blocks": 0, "raw_steals": 0, "raw_fg_pct": 0, "raw_fg3_pct": 0,
                "opp_points": 0, "opp_fg_pct": 0, "opp_fg3_pct": 0,
                "raw_opp_points": 0, "raw_opp_fg_pct": 0, "raw_opp_fg3_pct": 0,
            }
        
        # Get team stats (first dataframe)
        team_stats = dashboard[0].iloc[0]
        
        # Get opponent stats (second dataframe if available)
        opp_stats = dashboard[1].iloc[0] if len(dashboard) > 1 and not dashboard[1].empty else None
        
        # Team stats
        team_pts = float(team_stats.get("PTS", 0))
        team_reb = float(team_stats.get("REB", 0))
        team_ast = float(team_stats.get("AST", 0))
        team_blk = float(team_stats.get("BLK", 0))
        team_stl = float(team_stats.get("STL", 0))
        
        # Shooting percentages
        team_fgm = float(team_stats.get("FGM", 0))
        team_fga = float(team_stats.get("FGA", 0))
        team_fg3m = float(team_stats.get("FG3M", 0))
        team_fg3a = float(team_stats.get("FG3A", 0))
        
        team_fg_pct = (team_fgm / team_fga * 100.0) if team_fga > 0 else 0.0
        team_fg3_pct = (team_fg3m / team_fg3a * 100.0) if team_fg3a > 0 else 0.0
        
        # Opponent stats (if available)
        opp_pts = float(opp_stats.get("PTS", 0)) if opp_stats else 0
        opp_fgm = float(opp_stats.get("FGM", 0)) if opp_stats else 0
        opp_fga = float(opp_stats.get("FGA", 0)) if opp_stats else 0
        opp_fg3m = float(opp_stats.get("FG3M", 0)) if opp_stats else 0
        opp_fg3a = float(opp_stats.get("FG3A", 0)) if opp_stats else 0
        
        opp_fg_pct = (opp_fgm / opp_fga * 100.0) if opp_fga > 0 else 0.0
        opp_fg3_pct = (opp_fg3m / opp_fg3a * 100.0) if opp_fg3a > 0 else 0.0
        
        # Normalize team stats
        normalized = normalize_stats({
            'PTS': team_pts,
            'REB': team_reb,
            'AST': team_ast,
            'BLK': team_blk,
            'STL': team_stl,
            'FG_PCT': team_fg_pct,
            'FG3_PCT': team_fg3_pct,
        })
        
        # Normalize opponent stats (using same normalization)
        opp_normalized = normalize_stats({
            'PTS': opp_pts,
            'FG_PCT': opp_fg_pct,
            'FG3_PCT': opp_fg3_pct,
        })
        
        return {
            # Team stats (normalized 0-100)
            "points": normalized['points'],
            "rebounds": normalized['rebounds'],
            "assists": normalized['assists'],
            "blocks": normalized['blocks'],
            "steals": normalized['steals'],
            "fg_pct": normalized['fg_pct'],
            "fg3_pct": normalized['fg3_pct'],
            
            # Team stats (raw values)
            "raw_points": round(team_pts, 1),
            "raw_rebounds": round(team_reb, 1),
            "raw_assists": round(team_ast, 1),
            "raw_blocks": round(team_blk, 1),
            "raw_steals": round(team_stl, 1),
            "raw_fg_pct": round(team_fg_pct, 1),
            "raw_fg3_pct": round(team_fg3_pct, 1),
            
            # Opponent stats (normalized 0-100)
            "opp_points": opp_normalized['points'],
            "opp_fg_pct": opp_normalized['fg_pct'],
            "opp_fg3_pct": opp_normalized['fg3_pct'],
            
            # Opponent stats (raw values)
            "raw_opp_points": round(opp_pts, 1),
            "raw_opp_fg_pct": round(opp_fg_pct, 1),
            "raw_opp_fg3_pct": round(opp_fg3_pct, 1),
        }
        
    except Exception as e:
        print(f"Error fetching team profile stats: {e}")
        # Return empty stats on error
        return {
            "points": 0, "rebounds": 0, "assists": 0, "blocks": 0, "steals": 0,
            "fg_pct": 0, "fg3_pct": 0,
            "raw_points": 0, "raw_rebounds": 0, "raw_assists": 0, 
            "raw_blocks": 0, "raw_steals": 0, "raw_fg_pct": 0, "raw_fg3_pct": 0,
            "opp_points": 0, "opp_fg_pct": 0, "opp_fg3_pct": 0,
            "raw_opp_points": 0, "raw_opp_fg_pct": 0, "raw_opp_fg3_pct": 0,
        }

# -------------------------
# Cached league shots
# -------------------------
@lru_cache(maxsize=8)
def _league_shots_for_season(season_fmt: str) -> pd.DataFrame:
    sc = shotchartdetail.ShotChartDetail(
        team_id=0,
        player_id=0,
        season_nullable=season_fmt,
        season_type_all_star="Regular Season",
        context_measure_simple="FGA",
    )
    frames = sc.get_data_frames()
    return frames[0] if frames and len(frames) > 0 else pd.DataFrame()

# -------------------------
# Team shots
# -------------------------
@router.get("/team_shots")
def team_shots(team_id: int = Query(...), season: str = Query(...)):
    season_fmt = format_season(season)
    df = _league_shots_for_season(season_fmt)

    if df.empty:
        return {"season": season_fmt, "team_id": team_id, "shots_for": [], "shots_against": []}

    cols = ["LOC_X","LOC_Y","SHOT_MADE_FLAG","TEAM_ID","OPPONENT_TEAM_ID","SHOT_ZONE_BASIC","SHOT_DISTANCE"]
    df = df[[c for c in cols if c in df.columns]].copy()

    shots_for_df = df[df["TEAM_ID"] == team_id] if "TEAM_ID" in df.columns else pd.DataFrame()
    shots_against_df = df[df["OPPONENT_TEAM_ID"] == team_id] if "OPPONENT_TEAM_ID" in df.columns else pd.DataFrame()

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
