"""
Phase 0D: Direct pair-lineup acquisition via requests.Session.

This module preserves the successful direct HTTP pattern from Phase 0C
as reusable research-only code.

It does NOT use the nba_api wrapper; instead it constructs explicit
endpoint URLs with normalized parameters and canonical headers.
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import sys

import requests


# Canonical headers based on Phase 0C success
RESEARCH_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nba.com/',
}


def create_research_session() -> requests.Session:
    """Create a requests.Session with research baseline headers."""
    session = requests.Session()
    session.headers.update(RESEARCH_HEADERS)
    return session


def fetch_team_dash_lineups(
    team_id: str,
    season: str = '2024-25',
    season_type: str = 'Regular Season',
    group_quantity: str = '2',
    measure_type: str = 'Base',
    timeout: int = 30,
) -> Tuple[bool, dict, float, Optional[str]]:
    """
    Fetch TeamDashLineups via direct requests.Session.
    
    Args:
        team_id: NBA team ID (e.g., '1610612744' for Warriors)
        season: Season year (e.g., '2024-25')
        season_type: 'Regular Season', 'Playoffs', etc.
        group_quantity: Number of players in lineup group (e.g., '2' for pairs)
        measure_type: 'Base', 'Advanced', 'Four Factors', 'Usage'
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (success: bool, payload: dict, elapsed_time: float, error_msg: Optional[str])
    """
    url = (
        f"https://stats.nba.com/stats/teamdashlineups"
        f"?DateFrom="
        f"&DateTo="
        f"&GameID="
        f"&GameSegment="
        f"&GroupQuantity={group_quantity}"
        f"&LastNGames=0"
        f"&LeagueID="
        f"&Location="
        f"&MeasureType={measure_type}"
        f"&Month=0"
        f"&OpponentTeamID=0"
        f"&Outcome="
        f"&PORound="
        f"&PaceAdjust=N"
        f"&PerMode=Totals"
        f"&Period=0"
        f"&PlusMinus=N"
        f"&Rank=N"
        f"&Season={season}"
        f"&SeasonSegment="
        f"&SeasonType={season_type.replace(' ', '+')}"
        f"&ShotClockRange="
        f"&TeamID={team_id}"
        f"&VsConference="
        f"&VsDivision="
    )
    
    session = create_research_session()
    start = time.time()
    
    try:
        response = session.get(url, timeout=timeout)
        elapsed = time.time() - start
        
        if response.status_code != 200:
            return False, {}, elapsed, f"HTTP {response.status_code}"
        
        try:
            payload = response.json()
            return True, payload, elapsed, None
        except json.JSONDecodeError as e:
            return False, {}, elapsed, f"JSON decode error: {str(e)[:100]}"
    
    except requests.Timeout as e:
        elapsed = time.time() - start
        return False, {}, elapsed, f"Request timeout after {elapsed:.1f}s"
    except requests.RequestException as e:
        elapsed = time.time() - start
        return False, {}, elapsed, f"{type(e).__name__}: {str(e)[:100]}"


def fetch_league_dash_lineups(
    team_id: str,
    season: str = '2024-25',
    season_type: str = 'Regular Season',
    group_quantity: str = '2',
    measure_type: str = 'Base',
    timeout: int = 30,
) -> Tuple[bool, dict, float, Optional[str]]:
    """
    Fetch LeagueDashLineups via direct requests.Session, filtered to one team.
    
    Returns:
        Tuple of (success: bool, payload: dict, elapsed_time: float, error_msg: Optional[str])
    """
    url = (
        f"https://stats.nba.com/stats/leaguedashlineups"
        f"?Conference="
        f"&DateFrom="
        f"&DateTo="
        f"&Division="
        f"&GameSegment="
        f"&GroupQuantity={group_quantity}"
        f"&LastNGames=0"
        f"&LeagueID="
        f"&Location="
        f"&MeasureType={measure_type}"
        f"&Month=0"
        f"&OpponentTeamID=0"
        f"&Outcome="
        f"&PORound="
        f"&PaceAdjust=N"
        f"&PerMode=Totals"
        f"&Period=0"
        f"&PlusMinus=N"
        f"&Rank=N"
        f"&Season={season}"
        f"&SeasonSegment="
        f"&SeasonType={season_type.replace(' ', '+')}"
        f"&ShotClockRange="
        f"&TeamID={team_id}"
        f"&VsConference="
        f"&VsDivision="
    )
    
    session = create_research_session()
    start = time.time()
    
    try:
        response = session.get(url, timeout=timeout)
        elapsed = time.time() - start
        
        if response.status_code != 200:
            return False, {}, elapsed, f"HTTP {response.status_code}"
        
        try:
            payload = response.json()
            return True, payload, elapsed, None
        except json.JSONDecodeError as e:
            return False, {}, elapsed, f"JSON decode error: {str(e)[:100]}"
    
    except requests.Timeout as e:
        elapsed = time.time() - start
        return False, {}, elapsed, f"Request timeout after {elapsed:.1f}s"
    except requests.RequestException as e:
        elapsed = time.time() - start
        return False, {}, elapsed, f"{type(e).__name__}: {str(e)[:100]}"


def team_dash_lineups_cache_name(team_id: str, season: str, measure_type: str) -> str:
    """Return a stable, measure-specific cache name for TeamDashLineups payloads."""
    measure_slug = measure_type.strip().lower().replace(" ", "_")
    return f"team_dash_lineups_{team_id}_{season}_{measure_slug}.json"


def load_or_fetch_team_dash_lineups(
    team_id: str,
    season: str = '2024-25',
    season_type: str = 'Regular Season',
    group_quantity: str = '2',
    measure_type: str = 'Base',
    timeout: int = 30,
    cache_dir: Optional[Path] = None,
) -> Tuple[bool, dict, float, Optional[str], bool]:
    """Return a cached payload when available; otherwise perform one direct request."""
    cache_dir = cache_dir or Path('research/pair-fit-v2/cache/live_responses')
    cache_file = cache_dir / team_dash_lineups_cache_name(team_id, season, measure_type)
    cached = load_cached_response(cache_file)
    if cached is not None:
        return True, cached, 0.0, None, True

    success, payload, elapsed, error = fetch_team_dash_lineups(
        team_id=team_id,
        season=season,
        season_type=season_type,
        group_quantity=group_quantity,
        measure_type=measure_type,
        timeout=timeout,
    )
    if success:
        cache_response(payload, cache_file.name, cache_dir)
    return success, payload, elapsed, error, False


def cache_response(
    payload: dict,
    cache_name: str,
    cache_dir: Optional[Path] = None,
) -> Tuple[Path, str]:
    """
    Cache a successful response payload.
    
    Args:
        payload: The JSON payload to cache
        cache_name: Filename (e.g., 'team_dash_lineups_warriors_2024-25_base.json')
        cache_dir: Cache directory (default: research/pair-fit-v2/cache/live_responses)
    
    Returns:
        Tuple of (cache_file_path, content_hash)
    """
    if cache_dir is None:
        cache_dir = Path('research/pair-fit-v2/cache/live_responses')
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / cache_name
    
    with open(cache_file, 'w') as f:
        json.dump(payload, f, indent=2)
    
    content_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()[:16]
    
    return cache_file, content_hash


def load_cached_response(cache_file: Path) -> Optional[dict]:
    """Load a cached response from disk."""
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'r') as f:
            return json.load(f)
    except Exception:
        return None
