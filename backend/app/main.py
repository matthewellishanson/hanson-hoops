# backend/app/main.py
import os
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = FastAPI()

# ---- CORS (set exact origins) ----
ALLOWED_ORIGINS = list(filter(None, [
    os.getenv("FRONTEND_ORIGIN"),          # set this in Render for prod, e.g. https://hanson-hoops.onrender.com
    "http://localhost:5173",               # Vite dev
    "http://localhost:3000",
    "https://matthewellishanson.github.io" # if you use GH Pages
]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],   # fallback to * while testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

# ---- OPTIONAL PROXY (only if you actually use one) ----
# If you don’t use a proxy, you can delete this whole block.
_PROXY = os.getenv("PROXY_URL") or os.getenv("NBA_STATS_PROXY")
if _PROXY:
    os.environ["HTTP_PROXY"]  = _PROXY
    os.environ["HTTPS_PROXY"] = _PROXY
    os.environ["http_proxy"]  = _PROXY
    os.environ["https_proxy"] = _PROXY
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,.onrender.com")
    print(f"[startup] proxy enabled via PROXY_URL={_PROXY}")

# ---- nba_api reliability patch (keep this) ----
try:
    from nba_api.stats.library.http import NBAStatsHTTP
except Exception as e:
    NBAStatsHTTP = None
    print("[startup] nba_api import failed:", e)

# Default headers expected by stats.nba.com/Cloudflare
DEFAULT_HEADERS = {
    "User-Agent": os.getenv(
        "NBA_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/stats/",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

def _build_retrying_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=6, connect=3, read=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD", "OPTIONS"],
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(DEFAULT_HEADERS)
    # If a proxy is set via env, requests will honor it automatically.
    return s

def _patch_nba_api():
    if NBAStatsHTTP is None:
        return
    # Raise default timeout where possible
    for attr in ("_DEFAULT_TIMEOUT", "timeout", "DEFAULT_TIMEOUT"):
        if hasattr(NBAStatsHTTP, attr):
            try:
                setattr(NBAStatsHTTP, attr, 60)
                print(f"[startup] set NBAStatsHTTP.{attr}=60")
            except Exception as e:
                print(f"[startup] failed to set {attr}: {e}")

    # Update class default headers if available
    try:
        if hasattr(NBAStatsHTTP, "_DEFAULT_HEADERS"):
            NBAStatsHTTP._DEFAULT_HEADERS.update(DEFAULT_HEADERS)  # type: ignore[attr-defined]
    except Exception as e:
        print("[startup] failed to set NBAStatsHTTP headers:", e)

    # Replace any shared session
    for cand in ("_SESSION", "SESSION", "session"):
        if hasattr(NBAStatsHTTP, cand):
            try:
                setattr(NBAStatsHTTP, cand, _build_retrying_session())
                print(f"[startup] replaced NBAStatsHTTP.{cand} with retrying Session")
                break
            except Exception as e:
                print(f"[startup] failed to replace {cand}: {e}")

    # Ensure per-instance sessions use retries too
    orig_init = getattr(NBAStatsHTTP, "__init__", None)
    def patched_init(self, *args, **kwargs):
        if orig_init:
            orig_init(self, *args, **kwargs)
        sess = _build_retrying_session()
        for cand in ("session", "_session", "SESSION"):
            try:
                setattr(self, cand, sess)
            except Exception:
                pass
        setattr(self, "__retry_session__", sess)
    try:
        setattr(NBAStatsHTTP, "__init__", patched_init)
        print("[startup] wrapped NBAStatsHTTP.__init__")
    except Exception as e:
        print("[startup] failed to wrap __init__:", e)

_patch_nba_api()

# ---- Routers ----
from app.api.endpoints.players import router as players_router
from app.api.endpoints.teams import router as teams_router
app.include_router(players_router)
app.include_router(teams_router)
