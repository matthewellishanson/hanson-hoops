# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ⬇️ import your routers; adjust paths to match your repo
from app.api.endpoints.players import router as players_router
from app.api.endpoints.teams import router as teams_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players_router)
app.include_router(teams_router)

