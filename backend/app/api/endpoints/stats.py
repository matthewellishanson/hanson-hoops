from fastapi import APIRouter, Query
from models.schemas import PlayerProfileStats, GameStat
from nba_api.stats.endpoints import playergamelog

router = APIRouter()

@router.get("/player_stats", response_model=list[GameStat])
def get_player_stats(player_id: str = Query(...), season: str = Query(...)):
    logs = playergamelog.PlayerGameLog(player_id=player_id, season=season).get_data_frames()[0]
    stats = logs[["GAME_DATE", "PTS"]].sort_values("GAME_DATE")
    return [GameStat(game_date=row["GAME_DATE"], points=int(row["PTS"])) for _, row in stats.iterrows()]

@router.get("/player_profile_stats", response_model=PlayerProfileStats)
def get_player_profile_stats(player_id: str = Query(...), season: str = Query(...)):
    logs = playergamelog.PlayerGameLog(player_id=player_id, season=season).get_data_frames()[0]

    relevant_columns = ['PTS', 'REB', 'AST', 'BLK', 'STL', 'FG_PCT', 'FG3_PCT']
    averages = logs[relevant_columns].mean()

    return PlayerProfileStats(
        points=round(averages['PTS'], 1),
        rebounds=round(averages['REB'], 1),
        assists=round(averages['AST'], 1),
        blocks=round(averages['BLK'], 1),
        steals=round(averages['STL'], 1),
        fg_pct=round(averages['FG_PCT'] * 100, 1),
        fg3_pct=round(averages['FG3_PCT'] * 100, 1)
    )

