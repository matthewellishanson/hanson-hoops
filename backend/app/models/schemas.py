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
