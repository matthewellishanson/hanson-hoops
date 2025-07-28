from fastapi import APIRouter
from models.schemas import Player
from nba_api.stats.endpoints import commonallplayers

router = APIRouter()

import threading
import time

_cached_players = None
_cache_timestamp = 0
_cache_lock = threading.Lock()
_CACHE_TTL = 60 * 60  # 1 hour

def get_cached_players():
    global _cached_players, _cache_timestamp
    with _cache_lock:
        now = time.time()
        if _cached_players is None or now - _cache_timestamp > _CACHE_TTL:
            players = commonallplayers.CommonAllPlayers(is_only_current_season=1).get_data_frames()[0]
            active = players[players["ROSTERSTATUS"] == 1]
            _cached_players = [Player(id=str(row["PERSON_ID"]), name=row["DISPLAY_FIRST_LAST"]) for _, row in active.iterrows()]
            _cache_timestamp = now
        return _cached_players

@router.get("/players", response_model=list[Player])
def get_players():
    return get_cached_players()
