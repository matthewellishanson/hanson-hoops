from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from nba_api.stats.endpoints import commonallplayers, commonplayerinfo, playergamelog, shotchartdetail
from nba_api.stats.static import players as static_players

from app.models.schemas import GameStat, PlayerShotsResponse, ShotEvent
from app.services.nba_http import NBAUpstreamError, nba_call, request_timeout_seconds
from app.services.snapshots import (
    load_player_season_profile,
    load_player_shot_snapshot,
    load_player_snapshot,
)
from app.utils.dates import _age_at_season_start, _season_start_date
from app.utils.normalize import normalize_stats
from app.utils.seasons import current_nba_season, format_season

router = APIRouter()


@lru_cache(maxsize=1)
def _all_players_norm() -> list[dict]:
    try:
        season_fmt = format_season(current_nba_season())
        frames = nba_call(
            "common_all_players",
            lambda: commonallplayers.CommonAllPlayers(
                is_only_current_season=0,
                season=season_fmt,
                timeout=request_timeout_seconds(),
            ).get_data_frames(),
        )
        frame = frames[0]
        return [
            {
                "id": str(row["PERSON_ID"]),
                "name": row["DISPLAY_FIRST_LAST"],
                "first": row.get("FIRST_NAME", ""),
                "last": row.get("LAST_NAME", ""),
                "is_active": bool(row.get("ROSTERSTATUS")),
            }
            for _, row in frame.iterrows()
        ]
    except Exception as exc:
        # nba_api ships a local player index, so search remains available offline.
        print(f"[players] using packaged static list after {type(exc).__name__}")
        return [
            {
                "id": str(row["id"]),
                "name": row["full_name"],
                "first": row.get("first_name") or "",
                "last": row.get("last_name") or "",
                "is_active": bool(row.get("is_active")),
            }
            for row in static_players.get_players()
        ]


@router.get("/players")
def list_players(
    search: Optional[str] = Query(None),
    startswith: Optional[str] = Query(None),
    active_only: bool = Query(False),
    sort: Literal["name", "last", "first"] = Query("name"),
    order: Literal["asc", "desc"] = Query("asc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    data = _all_players_norm()
    if active_only:
        data = [player for player in data if player["is_active"]]
    if startswith:
        prefix = startswith.lower()
        data = [
            player
            for player in data
            if player["name"].lower().startswith(prefix) or player["last"].lower().startswith(prefix)
        ]
    if search:
        query = search.lower()
        data = [player for player in data if query in player["name"].lower()]
    data.sort(key=lambda player: player[sort].lower(), reverse=order == "desc")
    return {"total": len(data), "items": data[offset : offset + limit]}


def _height_to_cm_str(height_str: str | None) -> str | None:
    if not height_str or "-" not in height_str:
        return None
    try:
        feet, inches = height_str.split("-", 1)
        return str(round((int(feet) * 12 + int(inches)) * 2.54))
    except (TypeError, ValueError):
        return None


def _fetch_player_bio_uncached(
    player_id: str,
    retries: int = 1,
    backoff: float = 0.6,
    request_timeout: float | None = None,
) -> dict:
    # retries/backoff remain in the signature for controlled tests and emergency tuning;
    # one attempt is the default because the shared HTTP session already retries statuses.
    del backoff
    timeout = request_timeout or request_timeout_seconds()
    last_error: NBAUpstreamError | None = None
    for _ in range(max(1, retries)):
        try:
            frames = nba_call(
                "common_player_info",
                lambda: commonplayerinfo.CommonPlayerInfo(
                    player_id=int(player_id), timeout=timeout
                ).get_data_frames(),
            )
            if not frames or frames[0].empty:
                raise NBAUpstreamError("common_player_info_empty")
            row = frames[0].iloc[0]
            height = row.get("HEIGHT")
            weight = row.get("WEIGHT")
            return {
                "player_id": str(player_id),
                "name": row.get("DISPLAY_FIRST_LAST") or row.get("DISPLAY_FI_LAST") or row.get("PLAYER_NAME"),
                "team": row.get("TEAM_NAME") or row.get("TEAM_ABBREVIATION"),
                "position": row.get("POSITION"),
                "height": height,
                "height_cm": _height_to_cm_str(height),
                "weight_lbs": int(weight) if str(weight).isdigit() else None,
                "jersey": row.get("JERSEY") if row.get("JERSEY") not in ("", None, "0") else None,
                "birthdate": row.get("BIRTHDATE"),
                "headshot_url": f"https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png",
            }
        except NBAUpstreamError as exc:
            last_error = exc
    raise last_error or NBAUpstreamError("common_player_info")


_BIO_CACHE: dict[tuple[str, str], dict] = {}


def _fetch_player_bio(player_id: str, season_fmt: str) -> dict:
    cache_key = (player_id, season_fmt)
    if cache_key in _BIO_CACHE:
        return _BIO_CACHE[cache_key]
    snapshot = load_player_snapshot(player_id)
    season_profile, metadata = load_player_season_profile(player_id, season_fmt)
    if season_profile:
        supplemental = snapshot.get("bio", {}) if isinstance(snapshot, dict) else {}
        data = {
            "player_id": str(player_id),
            "name": season_profile.get("name") or supplemental.get("name"),
            "team": season_profile.get("team"),
            "position": season_profile.get("position"),
            "height": season_profile.get("height") or supplemental.get("height"),
            "height_cm": season_profile.get("height_cm") or supplemental.get("height_cm"),
            "weight_lbs": season_profile.get("weight_lbs") or supplemental.get("weight_lbs"),
            "jersey": season_profile.get("jersey"),
            "birthdate": supplemental.get("birthdate"),
            "headshot_url": supplemental.get("headshot_url") or (
                f"https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"
            ),
            "data_source": "packaged_snapshot",
            "snapshot_generated_at": metadata.get("generated_at"),
        }
    elif snapshot and isinstance(snapshot.get("bio"), dict):
        data = {
            **snapshot["bio"],
            "data_source": "packaged_snapshot",
            "snapshot_generated_at": snapshot.get("generated_at"),
        }
    else:
        data = {**_fetch_player_bio_uncached(player_id), "data_source": "live"}
    _BIO_CACHE[cache_key] = data
    return data


@router.get("/player_bio")
def get_player_bio(player_id: str = Query(...), season: Optional[str] = Query(None)):
    season_fmt = format_season(season or current_nba_season())
    data = _fetch_player_bio(player_id, season_fmt)
    age = _age_at_season_start(data.get("birthdate"), season)
    return {
        **data,
        "age": age,
        "age_as_of": (
            _season_start_date(season_fmt).isoformat() if season else date.today().isoformat()
        )
        if data.get("birthdate")
        else None,
    }


@lru_cache(maxsize=256)
def _player_shots_for_season(player_id: str, season_fmt: str) -> pd.DataFrame:
    frames = nba_call(
        "player_shot_chart",
        lambda: shotchartdetail.ShotChartDetail(
            team_id=0,
            player_id=int(player_id),
            season_nullable=season_fmt,
            season_type_all_star="Regular Season",
            context_measure_simple="FGA",
            timeout=request_timeout_seconds(),
        ).get_data_frames(),
    )
    return frames[0] if frames else pd.DataFrame()


EARLIEST_SHOT_SEASON_START = 1996


@router.get("/player_shots", response_model=PlayerShotsResponse)
def get_player_shots(player_id: str = Query(...), season: Optional[str] = Query(None)):
    season_fmt = format_season(season or current_nba_season())
    if int(season_fmt.split("-", 1)[0]) < EARLIEST_SHOT_SEASON_START:
        return PlayerShotsResponse(
            player_id=player_id,
            season=season_fmt,
            total=0,
            makes=0,
            attempts=0,
            shots=[],
            data_source="not_available_for_era",
        )

    frame, metadata = load_player_shot_snapshot(player_id, season_fmt)
    data_source = "packaged_snapshot" if frame is not None else "live"
    if frame is None:
        frame = _player_shots_for_season(player_id, season_fmt)
    if frame.empty:
        return PlayerShotsResponse(
            player_id=player_id,
            season=season_fmt,
            total=0,
            makes=0,
            attempts=0,
            shots=[],
            data_source=data_source,
            snapshot_generated_at=(metadata.get("generated_at") if metadata else None),
        )

    columns = [
        "LOC_X", "LOC_Y", "SHOT_MADE_FLAG", "SHOT_TYPE", "SHOT_ZONE_BASIC", "SHOT_DISTANCE"
    ]
    frame = frame[[column for column in columns if column in frame.columns]].copy()
    if "LOC_X" not in frame.columns or "LOC_Y" not in frame.columns:
        raise NBAUpstreamError("player_shot_chart_schema")
    shots = [
        ShotEvent(
            x=float(row.LOC_X),
            y=float(row.LOC_Y),
            made=bool(row.SHOT_MADE_FLAG) if "SHOT_MADE_FLAG" in frame.columns else False,
            shot_type=row.SHOT_TYPE
            if "SHOT_TYPE" in frame.columns and pd.notna(row.SHOT_TYPE)
            else None,
            shot_zone=row.SHOT_ZONE_BASIC
            if "SHOT_ZONE_BASIC" in frame.columns and pd.notna(row.SHOT_ZONE_BASIC)
            else None,
            shot_distance=float(row.SHOT_DISTANCE)
            if "SHOT_DISTANCE" in frame.columns and pd.notna(row.SHOT_DISTANCE)
            else None,
        )
        for _, row in frame.iterrows()
    ]
    makes = sum(1 for shot in shots if shot.made)
    return PlayerShotsResponse(
        player_id=player_id,
        season=season_fmt,
        total=len(shots),
        makes=makes,
        attempts=len(shots),
        shots=shots,
        data_source=data_source,
        snapshot_generated_at=(metadata.get("generated_at") if metadata else None),
    )


@router.get("/player_stats", response_model=list[GameStat])
def get_player_stats(player_id: str = Query(...), season: Optional[str] = Query(None)):
    season_fmt = format_season(season or current_nba_season())
    frames = nba_call(
        "player_game_log",
        lambda: playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season_fmt,
            season_type_all_star="Regular Season",
            timeout=request_timeout_seconds(),
        ).get_data_frames(),
    )
    logs = frames[0] if frames else pd.DataFrame()
    if logs.empty:
        return []
    stats = logs[["GAME_DATE", "PTS"]].sort_values("GAME_DATE")
    return [GameStat(game_date=row["GAME_DATE"], points=int(row["PTS"])) for _, row in stats.iterrows()]


def _profile_payload_from_logs(logs: pd.DataFrame, requested_scale: str, season_fmt: str) -> dict:
    required = {"PTS", "REB", "AST", "BLK", "STL", "TOV"}
    if not required.issubset(logs.columns):
        raise NBAUpstreamError("player_profile_schema")
    averages = logs[list(required)].mean().fillna(0)
    totals = {
        column: float(logs[column].sum()) if column in logs.columns else 0.0
        for column in ("FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA")
    }
    fg_pct = totals["FGM"] / totals["FGA"] * 100.0 if totals["FGA"] else 0.0
    fg3_pct = totals["FG3M"] / totals["FG3A"] * 100.0 if totals["FG3A"] else 0.0
    ft_pct = totals["FTM"] / totals["FTA"] * 100.0 if totals["FTA"] else 0.0
    ft_rate = totals["FTA"] / totals["FGA"] * 100.0 if totals["FGA"] else 0.0
    normalized = normalize_stats(
        {
            "PTS": averages["PTS"],
            "REB": averages["REB"],
            "AST": averages["AST"],
            "BLK": averages["BLK"],
            "STL": averages["STL"],
            "FG_PCT": fg_pct,
            "FG3_PCT": fg3_pct,
            "TOV": averages["TOV"],
        },
        kind="player",
    )
    # All existing radar legs use caps. Keep that contract explicit instead of
    # making another league request only for the two free-throw legs.
    normalized["ft_pct"] = round((max(50.0, min(90.0, ft_pct)) - 50.0) / 40.0 * 100.0, 1)
    normalized["ft_rate"] = round(max(0.0, min(60.0, ft_rate)) / 60.0 * 100.0, 1)
    return {
        **{key: float(normalized[key]) for key in (
            "points", "rebounds", "assists", "blocks", "steals", "fg_pct", "fg3_pct",
            "ft_rate", "ft_pct", "turnovers",
        )},
        "raw_points": round(float(averages["PTS"]), 1),
        "raw_rebounds": round(float(averages["REB"]), 1),
        "raw_assists": round(float(averages["AST"]), 1),
        "raw_blocks": round(float(averages["BLK"]), 1),
        "raw_steals": round(float(averages["STL"]), 1),
        "raw_fg_pct": round(fg_pct, 1),
        "raw_fg3_pct": round(fg3_pct, 1),
        "raw_ft_rate": round(ft_rate, 1),
        "raw_ft_pct": round(ft_pct, 1),
        "raw_tov": round(float(averages["TOV"]), 1),
        "scale": requested_scale,
        "scale_used": "cap",
        "season": season_fmt,
        "data_source": "live",
    }


@router.get("/player_profile_stats")
def get_player_profile_stats(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
    scale: Literal["percentile", "cap"] = Query("percentile"),
):
    season_fmt = format_season(season or current_nba_season()).strip()
    snapshot = load_player_snapshot(player_id)
    cached = (snapshot or {}).get("profiles", {}).get(season_fmt)
    if isinstance(cached, dict):
        return {
            **cached,
            "scale": scale,
            "season": season_fmt,
            "data_source": "packaged_snapshot",
            "snapshot_generated_at": snapshot.get("generated_at"),
        }

    season_profile, metadata = load_player_season_profile(player_id, season_fmt)
    if season_profile:
        profile_keys = {
            "points", "rebounds", "assists", "blocks", "steals", "fg_pct", "fg3_pct",
            "ft_rate", "ft_pct", "turnovers", "raw_points", "raw_rebounds", "raw_assists",
            "raw_blocks", "raw_steals", "raw_fg_pct", "raw_fg3_pct", "raw_ft_rate",
            "raw_ft_pct", "raw_tov", "scale_used",
        }
        return {
            **{key: season_profile.get(key) for key in profile_keys},
            "scale": scale,
            "season": season_fmt,
            "data_source": "packaged_snapshot",
            "snapshot_generated_at": metadata.get("generated_at"),
        }

    frames = nba_call(
        "player_profile_game_log",
        lambda: playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season_fmt,
            season_type_all_star="Regular Season",
            timeout=request_timeout_seconds(),
        ).get_data_frames(),
    )
    logs = frames[0] if frames else pd.DataFrame()
    if logs.empty:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "player_season_not_found",
                "message": "No regular-season games were found for this player and season.",
                "retryable": False,
            },
        )
    return _profile_payload_from_logs(logs, scale, season_fmt)


@router.get("/_debug/ping_nba")
def ping_nba():
    frames = nba_call(
        "debug_common_player_info",
        lambda: commonplayerinfo.CommonPlayerInfo(
            player_id=2544, timeout=request_timeout_seconds()
        ).get_data_frames(),
    )
    return {"ok": bool(frames and not frames[0].empty), "note": "NBA request completed"}
