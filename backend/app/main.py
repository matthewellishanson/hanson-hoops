# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # ← easiest way to prove CORS is your blocker
    allow_credentials=False,      # keep False if you use "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⬇️ import routers here ⬇️
from app.api.endpoints.players import router as players_router
from app.api.endpoints.teams import router as teams_router

app.include_router(players_router)
app.include_router(teams_router)

