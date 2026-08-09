from __future__ import annotations

import logging
import os
import re
import traceback
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("hanson_hoops.nba")

T = TypeVar("T")

DEFAULT_HEADERS = {
    "User-Agent": os.getenv(
        "NBA_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
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

PROXY_ENV_NAMES = (
    "NBA_RUNTIME_PROXY",
    "PROXY_URL",
    "NBA_STATS_PROXY",
)

_URL_CREDENTIALS = re.compile(r"(?P<scheme>https?://)[^\s/@]+(?::[^\s/@]*)?@", re.IGNORECASE)


class NBAUpstreamError(RuntimeError):
    """A safe, expected failure while reading stats.nba.com."""

    def __init__(self, operation: str):
        super().__init__("NBA statistics provider is temporarily unavailable.")
        self.operation = operation


def request_timeout_seconds() -> float:
    try:
        value = float(os.getenv("NBA_REQUEST_TIMEOUT_SECONDS", "8"))
    except ValueError:
        value = 8.0
    return max(1.0, min(value, 30.0))


def _selected_proxy() -> tuple[str | None, str | None]:
    for name in PROXY_ENV_NAMES:
        value = os.getenv(name)
        if value:
            return name, value
    return None, None


def _redact(value: object) -> str:
    text = str(value)
    return _URL_CREDENTIALS.sub(r"\g<scheme>***:***@", text)


def _safe_proxy_label(name: str, value: str) -> str:
    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme or "unknown"
        host = parsed.hostname or "unknown"
        return f"{name} ({scheme}://{host}; credentials redacted)"
    except Exception:
        return f"{name} (value redacted)"


def _safe_stack(exc: BaseException) -> str:
    frames = traceback.extract_tb(exc.__traceback__)
    return " <- ".join(f"{frame.name}:{frame.lineno}" for frame in frames[-8:])


def log_safe_exception(operation: str, exc: BaseException) -> None:
    logger.error(
        "NBA request failed operation=%s type=%s message=%s stack=%s",
        operation,
        type(exc).__name__,
        _redact(exc),
        _safe_stack(exc),
    )


def nba_call(operation: str, call: Callable[[], T]) -> T:
    try:
        return call()
    except NBAUpstreamError:
        raise
    except Exception as exc:
        log_safe_exception(operation, exc)
        raise NBAUpstreamError(operation) from None


def configure_nba_http() -> requests.Session | None:
    """Install the requests session actually used by nba_api 1.10.x."""
    try:
        from nba_api.stats.library.http import NBAStatsHTTP
    except Exception as exc:  # pragma: no cover - import failure is a deployment fault
        logger.error("nba_api import failed type=%s message=%s", type(exc).__name__, _redact(exc))
        return None

    retry = Retry(
        total=1,
        connect=1,
        read=0,
        status=1,
        backoff_factor=0.25,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(("GET", "HEAD", "OPTIONS")),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20))
    session.mount("http://", HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20))
    session.headers.update(DEFAULT_HEADERS)

    proxy_name, proxy_value = _selected_proxy()
    trust_env = os.getenv("NBA_TRUST_ENV_PROXY", "0") == "1"
    session.trust_env = trust_env
    if proxy_name and proxy_value:
        session.proxies.update({"http": proxy_value, "https": proxy_value})
        logger.info("NBA proxy configured from %s", _safe_proxy_label(proxy_name, proxy_value))
    elif trust_env:
        logger.info("NBA proxy mode uses inherited environment variables (values redacted)")
    else:
        logger.info("NBA proxy disabled; inherited HTTP proxy variables ignored")

    # nba_api 1.10.x resolves this class attribute in NBAHTTP.get_session().
    # Assigning an instance attribute does not affect that classmethod.
    NBAStatsHTTP._session = session
    NBAStatsHTTP.headers = {**getattr(NBAStatsHTTP, "headers", {}), **DEFAULT_HEADERS}
    return session

