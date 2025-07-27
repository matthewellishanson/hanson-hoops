from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.endpoints import players, stats

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(stats.router)

@app.get("/")
def read_root():
    return {"message": "NBA Data API is running!"}

