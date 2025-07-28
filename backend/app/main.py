from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.endpoints import players, stats

app = FastAPI()

# ✅ CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for dev (restrict in prod)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include routers
app.include_router(players.router)
app.include_router(stats.router)
