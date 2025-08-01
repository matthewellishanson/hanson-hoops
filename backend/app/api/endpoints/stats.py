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

        # 🎯 Normalization max values (reasonable NBA ranges)
        max_values = {
            'PTS': 50,     # 50 PPG max
            'REB': 20,     # 20 RPG max
            'AST': 20,     # 20 APG max
            'BLK': 10,      # 10 BPG max
            'STL': 10,      # 10 SPG max
            'FG_PCT': 90,  # 90% max FG%
            'FG3_PCT': 80  # 80% max 3P%
        }

        # Normalize to 0–100 scale
        normalized_stats = {
            'points': round((averages['PTS'] / max_values['PTS']) * 100, 1),
            'rebounds': round((averages['REB'] / max_values['REB']) * 100, 1),
            'assists': round((averages['AST'] / max_values['AST']) * 100, 1),
            'blocks': round((averages['BLK'] / max_values['BLK']) * 100, 1),
            'steals': round((averages['STL'] / max_values['STL']) * 100, 1),
            'fg_pct': round((averages['FG_PCT'] * 100 / max_values['FG_PCT']) * 100, 1),  # FG% in % then normalized
            'fg3_pct': round((averages['FG3_PCT'] * 100 / max_values['FG3_PCT']) * 100, 1) # 3P% normalized
        }

        print("DEBUG: Normalized stats ->", normalized_stats)

        return PlayerProfileStats(**normalized_stats)

    except Exception as e:
        print(f"ERROR in player_profile_stats: {e}")
        return PlayerProfileStats(points=0, rebounds=0, assists=0, blocks=0, steals=0, fg_pct=0, fg3_pct=0)



# @router.get("/team_profile_stats")
# def get_team_profile_stats(team_id: str = Query(...), season: str = Query(...)):
#     formatted_season = format_season(season)
    
#     logs = teamgamelog.TeamGameLog(team_id=team_id, season=formatted_season).get_data_frames()[0]
    
#     # For now, just return the first few games so we can confirm it works
#     return logs.head().to_dict(orient="records")