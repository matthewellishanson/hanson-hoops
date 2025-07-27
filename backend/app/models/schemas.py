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

class GameStat(BaseModel):
    game_date: str
    points: int

class Player(BaseModel):
    id: str
    name: str