from fastapi import APIRouter, Query
from functools import lru_cache
from nba_api.stats.endpoints import playergamelog, shotchartdetail
from models.schemas import (
    PlayerProfileStats,
    GameStat,
    PlayerShotsResponse,
    ShotEvent,
)
from utils.seasons import format_season, current_nba_season
from utils.normalize import normalize_stats
from typing import List, Optional
import pandas as pd


router = APIRouter()


# =========================
# Team and Player Shot Maps (with caching)
# =========================
# ---- cache league-wide shots per season (expensive) ----
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

# ---- cache player shots per (player, season) ----
@lru_cache(maxsize=256)
def _player_shots_for_season(player_id: str, season_fmt: str) -> pd.DataFrame:
    sc = shotchartdetail.ShotChartDetail(
        team_id=0,
        player_id=int(player_id),
        season_nullable=season_fmt,
        season_type_all_star="Regular Season",
        context_measure_simple="FGA",
    )
    frames = sc.get_data_frames()
    return frames[0] if frames and len(frames) > 0 else pd.DataFrame()

@router.get("/player_shots", response_model=PlayerShotsResponse)
def get_player_shots(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    season = season or current_nba_season()
    season_fmt = format_season(season)

    shots_df = _player_shots_for_season(player_id, season_fmt)

    if shots_df.empty:
        return PlayerShotsResponse(
            player_id=player_id, season=season_fmt,
            total=0, makes=0, attempts=0, shots=[]
        )

    cols = ["LOC_X", "LOC_Y", "SHOT_MADE_FLAG", "SHOT_ZONE_BASIC", "SHOT_DISTANCE"]
    shots_df = shots_df[[c for c in cols if c in shots_df.columns]].copy()

    shots: List[ShotEvent] = [
        ShotEvent(
            x=float(r.LOC_X),
            y=float(r.LOC_Y),
            made=bool(r.SHOT_MADE_FLAG),
            shot_zone=(r.SHOT_ZONE_BASIC if pd.notna(r.SHOT_ZONE_BASIC) else None),
            shot_distance=(float(r.SHOT_DISTANCE) if pd.notna(r.SHOT_DISTANCE) else None),
        )
        for _, r in shots_df.iterrows()
    ]

    attempts = len(shots)
    makes = int(shots_df["SHOT_MADE_FLAG"].sum()) if "SHOT_MADE_FLAG" in shots_df.columns else 0

    return PlayerShotsResponse(
        player_id=player_id,
        season=season_fmt,
        total=attempts,
        makes=makes,
        attempts=attempts,
        shots=shots
    )

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


# =========================
# Simple per-game points series
# =========================
@router.get("/player_stats", response_model=list[GameStat])
def get_player_stats(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    """
    Returns points per game timeseries for Plotly line chart (example).
    """
    season = season or current_nba_season()
    formatted_season = format_season(season)

    logs = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=formatted_season,
        season_type_all_star="Regular Season",
    ).get_data_frames()[0]

    if logs.empty:
        return []

    stats = logs[["GAME_DATE", "PTS"]].sort_values("GAME_DATE")
    return [
        GameStat(game_date=row["GAME_DATE"], points=int(row["PTS"]))
        for _, row in stats.iterrows()
    ]


# =========================
# Profile averages (normalized + raw)
# =========================
@router.get("/player_profile_stats", response_model=PlayerProfileStats)
def get_player_profile_stats(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    """
    Returns normalized (0–100) values for radar chart + raw averages for tooltips.
    Normalization happens in utils.normalize.normalize_stats.
    """
    try:
        season = season or current_nba_season()
        formatted_season = format_season(season)
        print(f"DEBUG: player_profile_stats -> player_id={player_id}, season={season}, formatted={formatted_season}")

        logs = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=formatted_season,
            season_type_all_star="Regular Season"
        ).get_data_frames()[0]

        print(f"DEBUG: logs shape={logs.shape}")
        if logs.empty:
            print("DEBUG: No games found")
            # Return zeros across the board
            return PlayerProfileStats(
                points=0, rebounds=0, assists=0, blocks=0, steals=0, fg_pct=0, fg3_pct=0,
                raw_points=0, raw_rebounds=0, raw_assists=0, raw_blocks=0, raw_steals=0, raw_fg_pct=0, raw_fg3_pct=0
            )

        relevant = ['PTS', 'REB', 'AST', 'BLK', 'STL', 'FGM', 'FGA', 'FG3M', 'FG3A']
        averages = logs[['PTS', 'REB', 'AST', 'BLK', 'STL']].mean().fillna(0)

        fgm  = float(logs['FGM'].sum())
        fga  = float(logs['FGA'].sum())
        fg3m = float(logs['FG3M'].sum())
        fg3a = float(logs['FG3A'].sum())

        # season (totals-based) shooting percentages
        fg_pct_season  = (fgm / fga * 100.0)  if fga  > 0 else 0.0
        fg3_pct_season = (fg3m / fg3a * 100.0) if fg3a > 0 else 0.0

        # pass *percent values* to your normalizer
        normalized = normalize_stats({
            'PTS': averages['PTS'],
            'REB': averages['REB'],
            'AST': averages['AST'],
            'BLK': averages['BLK'],
            'STL': averages['STL'],
            'FG_PCT':  fg_pct_season,
            'FG3_PCT': fg3_pct_season,
        })

        return PlayerProfileStats(
            # normalized for radar (0–100 scale)
            points=normalized['points'],
            rebounds=normalized['rebounds'],
            assists=normalized['assists'],
            blocks=normalized['blocks'],
            steals=normalized['steals'],
            fg_pct=normalized['fg_pct'],
            fg3_pct=normalized['fg3_pct'],

            # raw values for tooltips/labels (official method)
            raw_points=round(float(averages['PTS']), 1),
            raw_rebounds=round(float(averages['REB']), 1),
            raw_assists=round(float(averages['AST']), 1),
            raw_blocks=round(float(averages['BLK']), 1),
            raw_steals=round(float(averages['STL']), 1),
            raw_fg_pct=round(fg_pct_season, 1),
            raw_fg3_pct=round(fg3_pct_season, 1),
        )

    except Exception as e:
        print(f"ERROR in player_profile_stats: {e}")
        return PlayerProfileStats(
            points=0, rebounds=0, assists=0, blocks=0, steals=0, fg_pct=0, fg3_pct=0,
            raw_points=0, raw_rebounds=0, raw_assists=0, raw_blocks=0, raw_steals=0, raw_fg_pct=0, raw_fg3_pct=0
        )
