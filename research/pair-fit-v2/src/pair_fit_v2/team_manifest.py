"""Phase 1A: pilot team manifest and sequential cache-aware acquisition.

Extends the Phase 0 direct_fetch module rather than duplicating it. No new
prior-player request is made here; player-stat data is loaded from the
existing Phase 0F cache only.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pair_fit_v2.direct_fetch import (
    load_or_fetch_team_dash_lineups,
    team_dash_lineups_cache_name,
    load_cached_response,
)

TARGET_SEASON = "2024-25"
SEASON_TYPE = "Regular Season"
GROUP_QUANTITY = "2"
MEASURE_TYPES = ("Base", "Advanced")

# Warriors are the Phase 0 cache-only team; the three others are the new Phase 1A pilot teams.
# Team ID / name / abbreviation validated against the cached 2024-25 LeagueStandingsV3 response.
PILOT_TEAMS = (
    {"team_id": "1610612744", "team_name": "Golden State Warriors", "team_abbreviation": "GSW", "source": "phase_0_cache_only"},
    {"team_id": "1610612738", "team_name": "Boston Celtics", "team_abbreviation": "BOS", "source": "phase_1a_new"},
    {"team_id": "1610612764", "team_name": "Washington Wizards", "team_abbreviation": "WAS", "source": "phase_1a_new"},
    {"team_id": "1610612751", "team_name": "Brooklyn Nets", "team_abbreviation": "BKN", "source": "phase_1a_new"},
)

# The three new teams only, in the required sequential request order.
NEW_PILOT_TEAMS = tuple(team for team in PILOT_TEAMS if team["source"] == "phase_1a_new")

MAX_NEW_LIVE_REQUESTS = 6


def build_acquisition_plan() -> list[dict[str, str]]:
    """Return the bounded, ordered list of new-team requests (max 6: 3 teams x 2 measures)."""
    plan = []
    for team in NEW_PILOT_TEAMS:
        for measure_type in MEASURE_TYPES:
            plan.append(
                {
                    "team_id": team["team_id"],
                    "team_name": team["team_name"],
                    "team_abbreviation": team["team_abbreviation"],
                    "measure_type": measure_type,
                    "season": TARGET_SEASON,
                }
            )
    assert len(plan) <= MAX_NEW_LIVE_REQUESTS
    return plan


def build_manifest(cache_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return one manifest row per team/measure describing request/cache status.

    Contains no credentials or proxy details; only non-sensitive request identity.
    """
    cache_dir = cache_dir or Path("research/pair-fit-v2/cache/live_responses")
    manifest = []
    for team in PILOT_TEAMS:
        for measure_type in MEASURE_TYPES:
            cache_name = team_dash_lineups_cache_name(team["team_id"], TARGET_SEASON, measure_type)
            cached = load_cached_response(cache_dir / cache_name)
            manifest.append(
                {
                    "target_season": TARGET_SEASON,
                    "team_id": team["team_id"],
                    "team_name": team["team_name"],
                    "team_abbreviation": team["team_abbreviation"],
                    "measure_type": measure_type,
                    "source": team["source"],
                    "cache_filename": cache_name,
                    "cache_status": "cached" if cached is not None else "missing",
                }
            )
    return manifest


def run_acquisition_plan(
    cache_dir: Path | None = None,
    timeout: int = 30,
    pacing_seconds: float = 1.0,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    """Run the bounded, sequential, cache-aware acquisition plan.

    Stops the remaining queue on the first live-request failure. A cache hit
    never counts against pacing and never issues a live request. Safe to
    call repeatedly: already-cached steps are skipped, so a partially
    completed run resumes from the first missing/failed request.
    """
    cache_dir = cache_dir or Path("research/pair-fit-v2/cache/live_responses")
    plan = build_acquisition_plan()
    results = []
    stopped_early = False

    for step in plan:
        cache_name = team_dash_lineups_cache_name(step["team_id"], step["season"], step["measure_type"])
        already_cached = load_cached_response(cache_dir / cache_name) is not None

        success, payload, elapsed, error, from_cache = load_or_fetch_team_dash_lineups(
            team_id=step["team_id"],
            season=step["season"],
            season_type=SEASON_TYPE,
            group_quantity=GROUP_QUANTITY,
            measure_type=step["measure_type"],
            timeout=timeout,
            cache_dir=cache_dir,
        )

        results.append(
            {
                **step,
                "cache_filename": cache_name,
                "success": success,
                "from_cache": from_cache,
                "elapsed_seconds": elapsed,
                "error_category": error,
                "row_count": len(payload.get("resultSets", [])) if success else 0,
            }
        )

        if not success:
            stopped_early = True
            break

        if not already_cached and not from_cache:
            # Only a genuine new live request incurs conservative pacing.
            sleep_fn(pacing_seconds)

    return {
        "plan_length": len(plan),
        "results": results,
        "stopped_early": stopped_early,
        "completed_count": sum(1 for r in results if r["success"]),
    }


def first_missing_step(cache_dir: Path | None = None) -> dict[str, str] | None:
    """Return the first plan step without a valid cache entry, or None if all are cached."""
    cache_dir = cache_dir or Path("research/pair-fit-v2/cache/live_responses")
    for step in build_acquisition_plan():
        cache_name = team_dash_lineups_cache_name(step["team_id"], step["season"], step["measure_type"])
        if load_cached_response(cache_dir / cache_name) is None:
            return step
    return None
