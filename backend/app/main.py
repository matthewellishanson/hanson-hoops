from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
import requests

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

# --- BEGIN robust nba_api HTTP patch (version-agnostic) ---

try:
    from nba_api.stats.library.http import NBAStatsHTTP
except Exception as e:
    NBAStatsHTTP = None
    print("[startup] nba_api import failed:", e)

def _build_retrying_session() -> requests.Session:
    s = requests.Session()

    # Retry/backoff
    retry = Retry(
        total=6,
        connect=3,
        read=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD", "OPTIONS"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    # Browser-ish headers that NBA expects
    s.headers.update({
        "User-Agent": os.getenv("NBA_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                                  "Chrome/124.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.nba.com",
        "Referer": "https://www.nba.com/stats/",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    })

    # Optional proxy (set in Render as env var NBA_STATS_PROXY, e.g. http://user:pass@host:port)
    proxy = os.getenv("NBA_STATS_PROXY")
    if proxy:
        s.proxies.update({"http": proxy, "https": proxy})

    return s

def _patch_nba_api():
    if NBAStatsHTTP is None:
        return

    # Increase default timeouts where possible
    for attr in ("_DEFAULT_TIMEOUT", "timeout", "DEFAULT_TIMEOUT"):
        if hasattr(NBAStatsHTTP, attr):
            try:
                setattr(NBAStatsHTTP, attr, 60)  # 60s read timeout
                print(f"[startup] set NBAStatsHTTP.{attr}=60")
            except Exception as e:
                print(f"[startup] failed to set {attr}:", e)

    # Some versions keep a class- or module-level Session; some build per instance.
    # We patch both paths:

    # 1) If a class/session attribute exists, replace it.
    for cand in ("_SESSION", "SESSION", "session"):
        if hasattr(NBAStatsHTTP, cand):
            try:
                setattr(NBAStatsHTTP, cand, _build_retrying_session())
                print(f"[startup] replaced NBAStatsHTTP.{cand} with retrying Session")
                break
            except Exception as e:
                print(f"[startup] failed to replace {cand}:", e)

    # 2) Wrap __init__ to force a retrying session on each instance (covers per-instance sessions)
    orig_init = getattr(NBAStatsHTTP, "__init__", None)

    def patched_init(self, *args, **kwargs):
        if orig_init:
            orig_init(self, *args, **kwargs)
        # set any likely session attributes on the instance
        sess = _build_retrying_session()
        applied = False
        for cand in ("session", "_session", "SESSION"):
            if hasattr(self, cand) or cand in ("session", "_session"):
                try:
                    setattr(self, cand, sess)
                    applied = True
                    # don’t break; try to set multiple names if they exist
                except Exception:
                    pass
        if not applied:
            # As a fallback, stash it; later calls may look it up
            setattr(self, "__retry_session__", sess)

    try:
        setattr(NBAStatsHTTP, "__init__", patched_init)
        print("[startup] wrapped NBAStatsHTTP.__init__ for retrying Session")
    except Exception as e:
        print("[startup] failed to wrap NBAStatsHTTP.__init__:", e)

_patch_nba_api()
# --- END robust nba_api HTTP patch ---

# ⬇️ import routers here ⬇️
from app.api.endpoints.players import router as players_router
from app.api.endpoints.teams import router as teams_router

app.include_router(players_router)
app.include_router(teams_router)

@app.get("/cors-test")
def cors_test():
    return {"ok": True}

