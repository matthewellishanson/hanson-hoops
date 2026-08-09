from __future__ import annotations

import logging
import os
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.services.nba_http import NBAUpstreamError, configure_nba_http, log_safe_exception
from app.utils.seasons import current_nba_season, format_season

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("hanson_hoops.api")

# Configure nba_api before importing endpoint modules. nba_api shares one class-level
# requests session, so this also covers endpoint classes imported elsewhere.
configure_nba_http()

from app.api.endpoints import rookies  # noqa: E402
from app.api.endpoints.fit import router as fit_router  # noqa: E402
from app.api.endpoints.players import router as players_router  # noqa: E402
from app.api.endpoints.teams import _league_shots_for_season, router as teams_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # League-wide shot warming performs a large live request once per worker. It is
    # opt-in so Render cold starts do not compete with user-facing requests.
    if os.getenv("WARM_LEAGUE_SHOTS_ON_STARTUP", "0") == "1":
        try:
            season_fmt = format_season(current_nba_season())
            frame = _league_shots_for_season(season_fmt)
            logger.info("startup league-shot warm completed season=%s rows=%s", season_fmt, len(frame))
        except Exception as exc:
            log_safe_exception("startup_league_shots", exc)
    else:
        logger.info("startup league-shot warm disabled")

    yield
    logger.info("application shutdown")


app = FastAPI(lifespan=lifespan)

ALLOWED_ORIGINS = list(
    filter(
        None,
        [
            os.getenv("FRONTEND_ORIGIN"),
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "http://localhost:3000",
            "https://matthewellishanson.github.io",
        ],
    )
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _detail(code: str, message: str, request_id: str, retryable: bool) -> dict:
    return {
        "code": code,
        "message": message,
        "retryable": retryable,
        "request_id": request_id,
    }


def _error_headers(request: Request) -> dict[str, str]:
    request_id = _request_id(request)
    headers = {"X-Request-ID": request_id}
    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        headers.update(
            {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Vary": "Origin",
            }
        )
    return headers


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("x-request-id", "")
    request_id = supplied if _REQUEST_ID_RE.fullmatch(supplied) else uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(NBAUpstreamError)
async def nba_upstream_error(request: Request, exc: NBAUpstreamError):
    request_id = _request_id(request)
    logger.warning(
        "controlled upstream response request_id=%s route=%s operation=%s",
        request_id,
        request.url.path,
        exc.operation,
    )
    return JSONResponse(
        status_code=502,
        headers=_error_headers(request),
        content={
            "detail": _detail(
                "nba_upstream_unavailable",
                "NBA statistics are temporarily unavailable. Please try again later.",
                request_id,
                True,
            )
        },
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    request_id = _request_id(request)
    log_safe_exception(f"unexpected:{request.url.path}:request_id={request_id}", exc)
    return JSONResponse(
        status_code=500,
        headers=_error_headers(request),
        content={
            "detail": _detail(
                "internal_error",
                "The server could not complete this request.",
                request_id,
                False,
            )
        },
    )


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(players_router)
app.include_router(teams_router)
app.include_router(fit_router)
app.include_router(rookies.router)
