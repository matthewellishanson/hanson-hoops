# models/schemas.py
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