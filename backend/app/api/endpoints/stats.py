from fastapi import APIRouter, Query
from typing import Optional
from functools import lru_cache

import pandas as pd
from nba_api.stats.endpoints import playergamelog, shotchartdetail

from models.schemas import (
    PlayerProfileStats,
    GameStat,
    PlayerShotsResponse,
    ShotEvent,
)

from utils.seasons import format_season, current_nba_season
from utils.normalize import normalize_stats

router = APIRouter()


# =========================
# Shot Map (with caching)
# =========================
@lru_cache(maxsize=256)
def _fetch_player_shots_cached(player_id: str, season_fmt: str):
    """
    Cached low-level call to nba_api for shot chart data.
    season_fmt must be 'YYYY-YY' (already formatted).
    """
    sc = shotchartdetail.ShotChartDetail(
        team_id=0,
        player_id=player_id,
        season_type_all_star="Regular Season",
        season_nullable=season_fmt,        # expects 'YYYY-YY'
        context_measure_simple="FGA"       # return all attempts
    )
    return sc.get_data_frames()


@router.get("/player_shots", response_model=PlayerShotsResponse)
def get_player_shots(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    """
    Returns all shot attempts for a player in a season (made/missed + xy).
    season may be 'YYYY' or 'YYYY-YY'; if omitted we use current season.
    """
    season = season or current_nba_season()
    season_fmt = format_season(season)

    frames = _fetch_player_shots_cached(player_id, season_fmt)
    shots_df: pd.DataFrame = frames[0] if len(frames) > 0 else pd.DataFrame()

    if shots_df.empty:
        return PlayerShotsResponse(
            player_id=player_id, season=season_fmt, total=0, makes=0, attempts=0, shots=[]
        )

    cols = ["LOC_X", "LOC_Y", "SHOT_MADE_FLAG", "SHOT_ZONE_BASIC", "SHOT_DISTANCE"]
    shots_df = shots_df[cols].copy()

    shots = [
        ShotEvent(
            x=float(row.LOC_X),
            y=float(row.LOC_Y),
            made=bool(row.SHOT_MADE_FLAG),
            shot_zone=(row.SHOT_ZONE_BASIC if pd.notna(row.SHOT_ZONE_BASIC) else None),
            shot_distance=(float(row.SHOT_DISTANCE) if pd.notna(row.SHOT_DISTANCE) else None),
        )
        for _, row in shots_df.iterrows()
    ]

    attempts = len(shots)
    makes = int(shots_df["SHOT_MADE_FLAG"].sum())

    return PlayerShotsResponse(
        player_id=player_id,
        season=season_fmt,
        total=attempts,
        makes=makes,
        attempts=attempts,
        shots=shots
    )


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
