from fastapi import APIRouter, Query
from functools import lru_cache
from nba_api.stats.endpoints import shotchartdetail
from utils.seasons import format_season
from typing import List
import pandas as pd

router = APIRouter()

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
