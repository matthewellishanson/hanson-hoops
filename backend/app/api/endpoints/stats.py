from fastapi import APIRouter, Query
from app.models.schemas import GameStat
from nba_api.stats.endpoints import playergamelog

router = APIRouter()

@router.get("/player_stats", response_model=list[GameStat])
def get_player_stats(player_id: str = Query(...), season: str = Query(...)):
    logs = playergamelog.PlayerGameLog(player_id=player_id, season=season).get_data_frames()[0]
    stats = logs[["GAME_DATE", "PTS"]].sort_values("GAME_DATE")
    return [GameStat(game_date=row["GAME_DATE"], points=int(row["PTS"])) for _, row in stats.iterrows()]
