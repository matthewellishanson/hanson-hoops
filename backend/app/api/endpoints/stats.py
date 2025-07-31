from fastapi import APIRouter, Query
from models.schemas import PlayerProfileStats, GameStat
from nba_api.stats.endpoints import playergamelog
from utils.seasons import format_season

router = APIRouter()

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
    formatted_season = format_season(season)
    logs = playergamelog.PlayerGameLog(player_id=player_id, season=formatted_season).get_data_frames()[0]

    if logs.empty:
        return PlayerProfileStats(
            points=0, rebounds=0, assists=0,
            blocks=0, steals=0, fg_pct=0, fg3_pct=0
        )

    
    # Calculate averages for relevant stats
    relevant_columns = ['PTS', 'REB', 'AST', 'BLK', 'STL', 'FG_PCT', 'FG3_PCT']
    averages = logs[relevant_columns].mean().fillna(0)

    return PlayerProfileStats(
        points=round(averages['PTS'], 1),
        rebounds=round(averages['REB'], 1),
        assists=round(averages['AST'], 1),
        blocks=round(averages['BLK'], 1),
        steals=round(averages['STL'], 1),
        fg_pct=round(averages['FG_PCT'] * 100, 1),
        fg3_pct=round(averages['FG3_PCT'] * 100, 1)
    )


# @router.get("/team_profile_stats")
# def get_team_profile_stats(team_id: str = Query(...), season: str = Query(...)):
#     formatted_season = format_season(season)
    
#     logs = teamgamelog.TeamGameLog(team_id=team_id, season=formatted_season).get_data_frames()[0]
    
#     # For now, just return the first few games so we can confirm it works
#     return logs.head().to_dict(orient="records")