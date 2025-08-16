from fastapi import APIRouter, Query
from models.schemas import Player, PlayerBio
from nba_api.stats.endpoints import commonallplayers, commonplayerinfo
from datetime import datetime, date 


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

def _parse_height_to_cm(height_str: str | None) -> float | None:
    # NBA returns "6-8" etc
    if not height_str or "-" not in height_str:
        return None
    try:
        ft, inch = height_str.split("-")
        inches_total = int(ft) * 12 + int(inch)
        return round(inches_total * 2.54, 1)
    except Exception:
        return None

def _compute_age(birthdate_str: str | None) -> float | None:
    # birthdate like "12/30/1984"
    if not birthdate_str:
        return None
    try:
        b = datetime.strptime(birthdate_str, "%m/%d/%Y").date()
        today = date.today()
        # years with one decimal (approx)
        days = (today - b).days
        return round(days / 365.2425, 1)
    except Exception:
        return None

@router.get("/player_bio", response_model=PlayerBio)
def get_player_bio(player_id: str = Query(...)):
    info = commonplayerinfo.CommonPlayerInfo(player_id=player_id).get_data_frames()[0]
    row = info.iloc[0].to_dict()

    name = row.get("DISPLAY_FIRST_LAST")
    team = row.get("TEAM_NAME") or None
    jersey = row.get("JERSEY") or None
    position = row.get("POSITION") or None
    height = row.get("HEIGHT") or None              # "6-8"
    weight = row.get("WEIGHT") or None              # string like "250"
    birthdate = row.get("BIRTHDATE") or None        # "12/30/1984"

    height_cm = _parse_height_to_cm(height)
    try:
        weight_lbs = float(weight) if weight else None
    except Exception:
        weight_lbs = None

    age = _compute_age(birthdate)

    # NBA CDN headshots: common pattern
    headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"

    return PlayerBio(
        id=str(player_id),
        name=name,
        team=team,
        jersey=jersey,
        position=position,
        height=height,
        height_cm=height_cm,
        weight_lbs=weight_lbs,
        age=age,
        headshot_url=headshot_url,
        contract_years=None,    # not in nba_api; fill later if you add another source
        salary_usd=None,
    )
