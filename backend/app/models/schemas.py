# app/models/schemas.py

from pydantic import BaseModel

class PlayerProfileStats(BaseModel):
    points: float
    rebounds: float
    assists: float
    blocks: float
    steals: float
    fg_pct: float
    fg3_pct: float
    
    raw_points: float
    raw_rebounds: float
    raw_assists: float
    raw_blocks: float
    raw_steals: float
    raw_fg_pct: float
    raw_fg3_pct: float


class GameStat(BaseModel):
    game_date: str
    points: int

class Player(BaseModel):
    id: str
    name: str