from fastapi import APIRouter, Query
from models.schemas import PlayerProfileStats, GameStat, PlayerShotsResponse, ShotEvent
from nba_api.stats.endpoints import playergamelog, shotchartdetail
from functools import lru_cache
from utils.seasons import format_season, current_nba_season
from utils.normalize import normalize_stats
import pandas as pd
from typing import Optional

router = APIRouter()

@lru_cache(maxsize=256)
def _fetch_player_shots_cached(player_id: str, season: str):
    # season_type_all_star: "Regular Season" or "Playoffs"
    sc = shotchartdetail.ShotChartDetail(
        team_id=0,
        player_id=player_id,
        season_type_all_star="Regular Season",
        season_nullable=season,        # expects 'YYYY-YY'
        context_measure_simple="FGA"   # return all attempts
    )
    return sc.get_data_frames()

@router.get("/player_shots", response_model=PlayerShotsResponse)
def get_player_shots(player_id: str = Query(...), season: str = Query(...)):
    season_fmt = format_season(season)

    # pull and shape
    frames = _fetch_player_shots_cached(player_id, season_fmt)
    # data frames order: 0: shot detail, 1: league average
    shots_df: pd.DataFrame = frames[0] if len(frames) > 0 else pd.DataFrame()

    if shots_df.empty:
        return PlayerShotsResponse(
            player_id=player_id, season=season_fmt, total=0, makes=0, attempts=0, shots=[]
        )

    # columns of interest
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


@router.get("/player_stats", response_model=list[GameStat])
def get_player_stats(player_id: str = Query(...), season: str = Query(...)):
    # Format season here
    formatted_season = format_season(season)
    # Fetch player game logs for the specified season
    logs = playergamelog.PlayerGameLog(player_id=player_id, season=formatted_season).get_data_frames()[0]
    stats = logs[["GAME_DATE", "PTS"]].sort_values("GAME_DATE")
    # Convert to list of GameStat objects
    return [
        GameStat(game_date=row["GAME_DATE"], points=int(row["PTS"])) 
        for _, row in stats.iterrows()
    ]

# Player Profile Stats

@router.get("/player_profile_stats", response_model=PlayerProfileStats)
def get_player_profile_stats(player_id: str = Query(...), season: str = Query(...)):
    try:
        formatted_season = format_season(season)
        print(f"DEBUG: Formatted season -> {formatted_season}")

        print(f"DEBUG: Calling PlayerGameLog for player_id={player_id}")
        logs = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=formatted_season,
            season_type_all_star="Regular Season"
        ).get_data_frames()[0]
        print(f"DEBUG: Successfully retrieved logs")

        print(f"DEBUG: DataFrame shape={logs.shape}")
        if logs.empty:
            print("DEBUG: No games found")
            return PlayerProfileStats(points=0, rebounds=0, assists=0, blocks=0, steals=0, fg_pct=0, fg3_pct=0)

        relevant_columns = ['PTS', 'REB', 'AST', 'BLK', 'STL', 'FG_PCT', 'FG3_PCT']
        averages = logs[relevant_columns].mean().fillna(0)
        print("DEBUG: Averages calculated ->", averages.to_dict())
        
        # Averages calculated...
        print("DEBUG: Normalizing stats")
        # Normalize the stats
        print("DEBUG: Raw averages ->", averages.to_dict())
        # Normalized values
        normalized = normalize_stats({
            'PTS': averages['PTS'],
            'REB': averages['REB'],
            'AST': averages['AST'],
            'BLK': averages['BLK'],
            'STL': averages['STL'],
            'FG_PCT': averages['FG_PCT'] * 100,
            'FG3_PCT': averages['FG3_PCT'] * 100
        })

        return PlayerProfileStats(
            points=normalized['points'],
            rebounds=normalized['rebounds'],
            assists=normalized['assists'],
            blocks=normalized['blocks'],
            steals=normalized['steals'],
            fg_pct=normalized['fg_pct'],
            fg3_pct=normalized['fg3_pct'],

            raw_points=round(averages['PTS'], 1),
            raw_rebounds=round(averages['REB'], 1),
            raw_assists=round(averages['AST'], 1),
            raw_blocks=round(averages['BLK'], 1),
            raw_steals=round(averages['STL'], 1),
            raw_fg_pct=round(averages['FG_PCT'] * 100, 1),
            raw_fg3_pct=round(averages['FG3_PCT'] * 100, 1)
        )

    except Exception as e:
        print(f"ERROR in player_profile_stats: {e}")
        return PlayerProfileStats(points=0, rebounds=0, assists=0, blocks=0, steals=0, fg_pct=0, fg3_pct=0)



# @router.get("/team_profile_stats")
# def get_team_profile_stats(team_id: str = Query(...), season: str = Query(...)):
#     formatted_season = format_season(season)
    
#     logs = teamgamelog.TeamGameLog(team_id=team_id, season=formatted_season).get_data_frames()[0]
    
#     # For now, just return the first few games so we can confirm it works
#     return logs.head().to_dict(orient="records")