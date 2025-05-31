from pydantic import BaseModel

class Player(BaseModel):
    id: str
    name: str

class GameStat(BaseModel):
    game_date: str
    points: int
