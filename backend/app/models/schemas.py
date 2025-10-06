# backend/app/models/schemas.py
from pydantic import BaseModel
from typing import List, Optional

class PlayerProfileStats(BaseModel):
    # normalized (0–100)
    points: float
    rebounds: float
    assists: float
    blocks: float
    steals: float
    fg_pct: float
    fg3_pct: float

    # raw
    raw_points: Optional[float] = None
    raw_rebounds: Optional[float] = None
    raw_assists: Optional[float] = None
    raw_blocks: Optional[float] = None
    raw_steals: Optional[float] = None
    raw_fg_pct: Optional[float] = None
    raw_fg3_pct: Optional[float] = None



class GameStat(BaseModel):
    game_date: str
    points: int

class Player(BaseModel):
    id: str
    name: str

class ShotEvent(BaseModel):
    x: float
    y: float
    made: bool
    shot_zone: Optional[str] = None
    shot_distance: Optional[float] = None

class PlayerShotsResponse(BaseModel):
    player_id: str
    season: str
    total: int
    makes: int
    attempts: int
    shots: List[ShotEvent]

class PlayerBio(BaseModel):
    id: str
    name: str
    team: str | None = None
    jersey: str | None = None
    position: str | None = None
    height: str | None = None          # e.g. "6-8"
    height_cm: float | None = None
    weight_lbs: float | None = None
    age: float | None = None
    headshot_url: str | None = None
    # Placeholders for future sources (not in nba_api)
    contract_years: int | None = None
    salary_usd: int | None = None
