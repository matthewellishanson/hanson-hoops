from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # keep '*' until we confirm it works
    allow_credentials=False,   # must be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⬇️ import routers here ⬇️
from app.api.endpoints.players import router as players_router
from app.api.endpoints.teams import router as teams_router

app.include_router(players_router)
app.include_router(teams_router)

@app.get("/cors-test")
def cors_test():
    return {"ok": True}

