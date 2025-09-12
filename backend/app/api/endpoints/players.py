from fastapi import APIRouter, Query, HTTPException
from functools import lru_cache
from nba_api.stats.endpoints import playergamelog, shotchartdetail, commonplayerinfo
from nba_api.stats.static import players as static_players
from app.models.schemas import (
    PlayerProfileStats,
    GameStat,
    PlayerShotsResponse,
    ShotEvent,
)
from app.utils.seasons import format_season, current_nba_season
from app.utils.normalize import normalize_stats
from app.utils.dates import _age_at_season_start, _season_start_date
from typing import List, Optional, Literal
import pandas as pd
from datetime import datetime, date

router = APIRouter()

# Players endpoint
# Caching player data
@lru_cache(maxsize=1)
def _all_players_norm():
    # ~5k records; cache in memory
    rows = static_players.get_players()
    return [
        {
            "id": str(r["id"]),
            "name": r["full_name"],
            "first": r.get("first_name") or "",
            "last": r.get("last_name") or "",
            "is_active": bool(r.get("is_active")),
        }
        for r in rows
    ]

@router.get("/players")
def list_players(
    search: Optional[str] = Query(None, description="Substring match on full name"),
    startswith: Optional[str] = Query(None, description="Filter by first letter(s) of last name or full name"),
    active_only: bool = Query(False, description="If True, return only currently active players"),
    sort: Literal["name","last","first"] = Query("name"),
    order: Literal["asc","desc"] = Query("asc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    data = _all_players_norm()

    if active_only:
        data = [p for p in data if p["is_active"]]

    if startswith:
        s = startswith.lower()
        data = [
            p for p in data
            if p["name"].lower().startswith(s) or p["last"].lower().startswith(s)
        ]

    if search:
        q = search.lower()
        data = [p for p in data if q in p["name"].lower()]

    key_map = {"name": "name", "last": "last", "first": "first"}
    data.sort(key=lambda p: p[key_map[sort]].lower())
    if order == "desc":
        data.reverse()

    total = len(data)
    items = data[offset: offset + limit]
    return {"total": total, "items": items}

# Player Bio
def _height_to_cm_str(height_str: str | None) -> str | None:
    # HEIGHT comes like "6-8" -> inches -> cm
    if not height_str or "-" not in height_str:
        return None
    try:
        feet, inches = height_str.split("-")
        total_in = int(feet) * 12 + int(inches)
        cm = round(total_in * 2.54)
        return str(cm)
    except Exception:
        return None

@lru_cache(maxsize=512)
def _fetch_player_bio(player_id: str) -> dict | None:
    info = commonplayerinfo.CommonPlayerInfo(player_id=int(player_id)).get_data_frames()
    if not info or len(info) == 0 or info[0].empty:
        return None

    df = info[0].iloc[0]

    name = df.get("DISPLAY_FIRST_LAST") or df.get("DISPLAY_FI_LAST") or df.get("PLAYER_NAME")
    team = df.get("TEAM_NAME") or df.get("TEAM_ABBREVIATION")
    position = df.get("POSITION")
    height = df.get("HEIGHT")
    weight = df.get("WEIGHT")
    jersey = df.get("JERSEY")
    birthdate = df.get("BIRTHDATE")  # <- keep raw string from API

    headshot_url = f"https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"

    return {
        "player_id": str(player_id),
        "name": name,
        "team": team,
        "position": position,
        "height": height,
        "height_cm": _height_to_cm_str(height),
        "weight_lbs": (int(weight) if isinstance(weight, (int, float, str)) and str(weight).isdigit() else None),
        "jersey": jersey if jersey not in ("", None, "0") else None,
        "birthdate": birthdate,           # 👈 keep it so we can compute different ages on demand
        "headshot_url": headshot_url,
    }

@router.get("/player_bio")
def get_player_bio(
    player_id: str = Query(...),
    season: Optional[str] = Query(None, description="e.g. 2024 or 2024-25; if omitted, compute age as of today")
):
    data = _fetch_player_bio(player_id)
    if not data:
        raise HTTPException(status_code=404, detail="Player bio not found")

    # compute age for the requested season (or today)
    age = _age_at_season_start(data.get("birthdate"), season)

    # return the bio with the computed age; keep birthdate if you want, or drop it
    return {
        **data,
        "age": age,
        "age_as_of": (
            (_season_start_date(format_season(season)).isoformat() if season else date.today().isoformat())
            if data.get("birthdate") else None
        )
    }

# -------------------------
# Cached player shot charts
# -------------------------
@lru_cache(maxsize=256)
def _player_shots_for_season(player_id: str, season_fmt: str) -> pd.DataFrame:
    sc = shotchartdetail.ShotChartDetail(
        team_id=0,
        player_id=int(player_id),
        season_nullable=season_fmt,
        season_type_all_star="Regular Season",
        context_measure_simple="FGA",
    )
    frames = sc.get_data_frames()
    return frames[0] if frames and len(frames) > 0 else pd.DataFrame()

EARLIEST_SHOT_SEASON_START = 1996  # 1996-97

def _season_start_year(season_fmt: str) -> int:
    # "YYYY-YY" -> int(YYYY)
    return int(season_fmt.split('-')[0])

@router.get("/player_shots", response_model=PlayerShotsResponse)
def get_player_shots(player_id: str = Query(...), season: Optional[str] = Query(None)):
    season = season or current_nba_season()
    season_fmt = format_season(season)

    # Era check: no league shot locations prior to 1996–97
    has_shot_data = _season_start_year(season_fmt) >= EARLIEST_SHOT_SEASON_START
    if not has_shot_data:
        return PlayerShotsResponse(
            player_id=player_id,
            season=season_fmt,
            total=0, makes=0, attempts=0, shots=[],
            # has_shot_data=False   # uncomment if your model includes this optional field
        )

    # Pull cached player shots for this season
    shots_df = _player_shots_for_season(player_id, season_fmt)

    if shots_df.empty:
        return PlayerShotsResponse(
            player_id=player_id,
            season=season_fmt,
            total=0, makes=0, attempts=0, shots=[],
            # has_shot_data=True
        )

    # Keep only the columns we need (defensive against lib version changes)
    cols = ["LOC_X", "LOC_Y", "SHOT_MADE_FLAG", "SHOT_ZONE_BASIC", "SHOT_DISTANCE"]
    shots_df = shots_df[[c for c in cols if c in shots_df.columns]].copy()

    # Build the response list
    shots: List[ShotEvent] = [
        ShotEvent(
            x=float(r.LOC_X),
            y=float(r.LOC_Y),
            made=bool(r.SHOT_MADE_FLAG) if "SHOT_MADE_FLAG" in shots_df.columns else False,
            shot_zone=(r.SHOT_ZONE_BASIC if "SHOT_ZONE_BASIC" in shots_df.columns and pd.notna(r.SHOT_ZONE_BASIC) else None),
            shot_distance=(float(r.SHOT_DISTANCE) if "SHOT_DISTANCE" in shots_df.columns and pd.notna(r.SHOT_DISTANCE) else None),
        )
        for _, r in shots_df.iterrows()
    ]

    attempts = len(shots)
    makes = int(shots_df["SHOT_MADE_FLAG"].sum()) if "SHOT_MADE_FLAG" in shots_df.columns else 0

    return PlayerShotsResponse(
        player_id=player_id,
        season=season_fmt,
        total=attempts,
        makes=makes,
        attempts=attempts,
        shots=shots,
        # has_shot_data=True
    )

# -------------------------
# Game log series
# -------------------------
@router.get("/player_stats", response_model=list[GameStat])
def get_player_stats(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    season = season or current_nba_season()
    formatted_season = format_season(season)

    logs = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=formatted_season,
        season_type_all_star="Regular Season",
    ).get_data_frames()[0]

    if logs.empty:
        return []

    stats = logs[["GAME_DATE", "PTS"]].sort_values("GAME_DATE")
    return [
        GameStat(game_date=row["GAME_DATE"], points=int(row["PTS"]))
        for _, row in stats.iterrows()
    ]

# -------------------------
# Profile averages
# -------------------------
@router.get("/player_profile_stats", response_model=PlayerProfileStats)
@router.get("/player_profile_stats", response_model=PlayerProfileStats)
def get_player_profile_stats(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    try:
        raw_season = season
        season = season or current_nba_season()

        # Force canonical "YYYY-YY" *before* calling nba_api
        formatted_season = format_season(season).strip()
        print(f"[profile_stats] player={player_id}  raw_season={raw_season!r}  formatted={formatted_season}")

        logs = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=formatted_season,
            season_type_all_star="Regular Season"
        ).get_data_frames()[0]

        # Helpful to see which dates the API actually returned
        if not logs.empty:
            print(
                "[profile_stats] rows=", len(logs),
                " first_date=", logs["GAME_DATE"].iloc[-1] if "GAME_DATE" in logs else "n/a",
                " last_date=", logs["GAME_DATE"].iloc[0]  if "GAME_DATE" in logs else "n/a",
            )
        else:
            print("[profile_stats] EMPTY logs for", formatted_season)

        if logs.empty:
            return PlayerProfileStats(
                points=0, rebounds=0, assists=0, blocks=0, steals=0, fg_pct=0, fg3_pct=0,
                raw_points=0, raw_rebounds=0, raw_assists=0, raw_blocks=0, raw_steals=0,
                raw_fg_pct=0, raw_fg3_pct=0
            )

        averages = logs[['PTS', 'REB', 'AST', 'BLK', 'STL']].mean().fillna(0)

        fgm  = float(logs['FGM'].sum())
        fga  = float(logs['FGA'].sum())
        fg3m = float(logs['FG3M'].sum())
        fg3a = float(logs['FG3A'].sum())

        fg_pct_season  = (fgm / fga * 100.0) if fga > 0 else 0.0
        fg3_pct_season = (fg3m / fg3a * 100.0) if fg3a > 0 else 0.0

        normalized = normalize_stats({
            'PTS': averages['PTS'],
            'REB': averages['REB'],
            'AST': averages['AST'],
            'BLK': averages['BLK'],
            'STL': averages['STL'],
            'FG_PCT':  fg_pct_season,
            'FG3_PCT': fg3_pct_season,
        })

        return PlayerProfileStats(
            points=normalized['points'],
            rebounds=normalized['rebounds'],
            assists=normalized['assists'],
            blocks=normalized['blocks'],
            steals=normalized['steals'],
            fg_pct=normalized['fg_pct'],
            fg3_pct=normalized['fg3_pct'],
            raw_points=round(float(averages['PTS']), 1),
            raw_rebounds=round(float(averages['REB']), 1),
            raw_assists=round(float(averages['AST']), 1),
            raw_blocks=round(float(averages['BLK']), 1),
            raw_steals=round(float(averages['STL']), 1),
            raw_fg_pct=round(fg_pct_season, 1),
            raw_fg3_pct=round(fg3_pct_season, 1),
        )

    except Exception:
        return PlayerProfileStats(
            points=0, rebounds=0, assists=0, blocks=0, steals=0, fg_pct=0, fg3_pct=0,
            raw_points=0, raw_rebounds=0, raw_assists=0, raw_blocks=0, raw_steals=0,
            raw_fg_pct=0, raw_fg3_pct=0
        )
