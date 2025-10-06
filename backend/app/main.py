# backend/app/main.py
import os

_proxy = os.environ.get("PROXY_URL")
if _proxy:
    # Force-populate all the variants requests honors
    os.environ["HTTP_PROXY"]  = _proxy
    os.environ["HTTPS_PROXY"] = _proxy
    os.environ["http_proxy"]  = _proxy
    os.environ["https_proxy"] = _proxy
    # (Optional) do not proxy Render's own domain and localhost
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,.onrender.com")
# --- end proxy bootstrap ---


from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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

    # Optional proxies: accept NBA_STATS_PROXY, PROXY_URL, or the standard *_PROXY envs
    proxy = (
        os.getenv("NBA_STATS_PROXY")
        or os.getenv("PROXY_URL")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
    )
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

@app.get("/_debug/outbound_ip")
def outbound_ip():
    # requests respects HTTPS_PROXY/HTTP_PROXY in env automatically
    r = requests.get("https://httpbin.org/ip", timeout=20)
    return r.json()

@app.get("/_debug/whoami")
def whoami():
    # Plain request (no proxies)
    try:
        plain = requests.get("https://httpbin.org/ip", timeout=10).json()
    except Exception as e:
        plain = {"error": str(e)}

    # With proxies pulled from env (what requests will honor)
    proxies = {
        "http":  os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
    }
    try:
        via_proxy = requests.get("https://httpbin.org/ip", timeout=20, proxies=proxies).json()
    except Exception as e:
        via_proxy = {"error": str(e)}

    return {
        "env": {
            "HTTP_PROXY":  os.environ.get("HTTP_PROXY"),
            "HTTPS_PROXY": os.environ.get("HTTPS_PROXY"),
            "NO_PROXY":    os.environ.get("NO_PROXY"),
        },
        "plain_ip": plain,
        "proxy_ip": via_proxy,
    }


@app.get("/_debug/ping_nba_raw")
def ping_nba_raw():
    """
    Call stats.nba.com WITHOUT nba_api to test headers+proxy directly.
    """
    headers = {
        # real-world headers that Cloudflare accepts for stats.nba.com
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com",
        "Connection": "keep-alive",
    }
    proxies = {
        "http":  os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
    }
    try:
        r = requests.get(
            "https://stats.nba.com/stats/commonplayerinfo",
            params={"PlayerID": "2544", "LeagueID": ""},
            headers=headers,
            proxies=proxies,
            timeout=25,
        )
        return {"ok": True, "status": r.status_code, "length": len(r.content)}
    except Exception as e:
        return {"ok": False, "error": str(e)}