from fastapi import APIRouter, Query, HTTPException
from functools import lru_cache
from nba_api.stats.endpoints import playergamelog, shotchartdetail, commonplayerinfo
from nba_api.stats.static import players as static_players
from models.schemas import (
    PlayerProfileStats,
    GameStat,
    PlayerShotsResponse,
    ShotEvent,
)
from utils.seasons import format_season, current_nba_season
from utils.normalize import normalize_stats
from typing import List, Optional, Literal
import pandas as pd
from datetime import datetime, date

router = APIRouter()

# Players endpoint
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

def _calc_age(birthdate_str: str | None) -> int | None:
    # birthdate format: "1984-12-30T00:00:00"
    if not birthdate_str:
        return None
    try:
        d = datetime.fromisoformat(birthdate_str.replace("Z", "")).date()
        today = date.today()
        return today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    except Exception:
        return None

@lru_cache(maxsize=512)
def _fetch_player_bio(player_id: str) -> dict | None:
    info = commonplayerinfo.CommonPlayerInfo(player_id=int(player_id)).get_data_frames()
    if not info or len(info) == 0 or info[0].empty:
        return None

    df = info[0].iloc[0]

    # Some columns vary by library version; use .get with defaults
    name = df.get("DISPLAY_FIRST_LAST") or df.get("DISPLAY_FI_LAST") or df.get("PLAYER_NAME")
    team = df.get("TEAM_NAME") or df.get("TEAM_ABBREVIATION")
    position = df.get("POSITION")
    height = df.get("HEIGHT")              # e.g. "6-9"
    weight = df.get("WEIGHT")              # string like "250"
    jersey = df.get("JERSEY")
    birthdate = df.get("BIRTHDATE")
    age = _calc_age(birthdate)

    # Headshot CDN (works for most current players)
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
        "age": age,
        "headshot_url": headshot_url,
    }

@router.get("/player_bio")
def get_player_bio(player_id: str = Query(...)):
    data = _fetch_player_bio(player_id)
    if not data:
        raise HTTPException(status_code=404, detail="Player bio not found")
    return data

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

@router.get("/player_shots", response_model=PlayerShotsResponse)
def get_player_shots(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    season = season or current_nba_season()
    season_fmt = format_season(season)

    shots_df = _player_shots_for_season(player_id, season_fmt)

    if shots_df.empty:
        return PlayerShotsResponse(
            player_id=player_id, season=season_fmt,
            total=0, makes=0, attempts=0, shots=[]
        )

    cols = ["LOC_X", "LOC_Y", "SHOT_MADE_FLAG", "SHOT_ZONE_BASIC", "SHOT_DISTANCE"]
    shots_df = shots_df[[c for c in cols if c in shots_df.columns]].copy()

    shots: List[ShotEvent] = [
        ShotEvent(
            x=float(r.LOC_X),
            y=float(r.LOC_Y),
            made=bool(r.SHOT_MADE_FLAG),
            shot_zone=(r.SHOT_ZONE_BASIC if pd.notna(r.SHOT_ZONE_BASIC) else None),
            shot_distance=(float(r.SHOT_DISTANCE) if pd.notna(r.SHOT_DISTANCE) else None),
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
        shots=shots
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
def get_player_profile_stats(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
):
    try:
        season = season or current_nba_season()
        formatted_season = format_season(season)

        logs = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=formatted_season,
            season_type_all_star="Regular Season"
        ).get_data_frames()[0]

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
