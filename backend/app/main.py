from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.endpoints import players, teams

app = FastAPI()

# ✅ For development, allow everything
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev: allow any origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(players.router)
app.include_router(teams.router)
