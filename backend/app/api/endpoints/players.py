from fastapi import APIRouter
from app.models.schemas import Player
from nba_api.stats.endpoints import commonallplayers

router = APIRouter()

@router.get("/players", response_model=list[Player])
def get_players():
    players = commonallplayers.CommonAllPlayers(is_only_current_season=1).get_data_frames()[0]
    active = players[players["ROSTERSTATUS"] == 1]
    return [Player(id=str(row["PERSON_ID"]), name=row["DISPLAY_FIRST_LAST"]) for _, row in active.iterrows()]
