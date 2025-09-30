from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

# existing CORSMiddleware — keep it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # (you can lock to your GH pages origin later)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# guarantee the header on ALL responses
@app.middleware("http")
async def add_cors_header_everywhere(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        # ensure even error responses include CORS
        response = JSONResponse({"detail": "internal error"}, status_code=500)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Vary"] = "Origin"
    return response

# Set custom headers for nba_api requests to avoid 403 errors
try:
    from nba_api.stats.library.http import NBAStatsHTTP
    # Update the default headers used by nba_api
    NBAStatsHTTP._DEFAULT_HEADERS.update({
        "User-Agent": (
            # any modern UA; keep it realistic
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nba.com",
        "Referer": "https://www.nba.com/",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
        "Connection": "keep-alive",
    })
except Exception as e:
    print("[startup] failed to set NBAStatsHTTP headers:", e)


# ⬇️ import routers here ⬇️
from app.api.endpoints.players import router as players_router
from app.api.endpoints.teams import router as teams_router

app.include_router(players_router)
app.include_router(teams_router)

@app.get("/cors-test")
def cors_test():
    return {"ok": True}

