# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow GitHub Pages, Render (self), and local dev
allowed_origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:5174",
    "https://hanson-hoops.onrender.com",
    "https://matthewellishanson.github.io",
    "https://matthewellishanson.github.io/hanson-hoops",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.github\.io$",  # allow any github.io if you want
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# ⬇️ import routers here ⬇️
from app.api.endpoints.players import router as players_router
from app.api.endpoints.teams import router as teams_router

app.include_router(players_router)
app.include_router(teams_router)

