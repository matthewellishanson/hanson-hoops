# backend/app/api/endpoints/players.py
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
from app.utils.percentiles import player_row_percentiles
from app.utils.dates import _age_at_season_start, _season_start_date
from app.utils.player_percentiles import player_stat_percentile
from typing import List, Optional, Literal
import pandas as pd
from datetime import datetime, date
import time
import traceback
from requests.exceptions import RequestException, ReadTimeout

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

def _fetch_player_bio(player_id: str, retries: int = 5, backoff: float = 1.5) -> dict | None:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            info = commonplayerinfo.CommonPlayerInfo(
                player_id=int(player_id),
                timeout=60,  # <— per-call timeout, in addition to the global one
            ).get_data_frames()

            if not info or len(info) == 0 or info[0].empty:
                last_err = RuntimeError("empty CommonPlayerInfo")
                raise last_err

            df = info[0].iloc[0]
            name = df.get("DISPLAY_FIRST_LAST") or df.get("DISPLAY_FI_LAST") or df.get("PLAYER_NAME")
            team = df.get("TEAM_NAME") or df.get("TEAM_ABBREVIATION")
            position = df.get("POSITION")
            height = df.get("HEIGHT")
            weight = df.get("WEIGHT")
            jersey = df.get("JERSEY")
            birthdate = df.get("BIRTHDATE")
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
                "birthdate": birthdate,
                "headshot_url": headshot_url,
            }

        except (ReadTimeout, RequestException, RuntimeError) as e:
            last_err = e
            sleep = backoff * attempt
            print(f"[player_bio] attempt {attempt}/{retries} failed ({e}); sleeping {sleep:.1f}s")
            time.sleep(sleep)
        except Exception as e:
            last_err = e
            sleep = backoff * attempt
            print(f"[player_bio] unexpected error attempt {attempt}/{retries}: {repr(e)}; sleeping {sleep:.1f}s")
            time.sleep(sleep)

    print(f"[player_bio] giving up for player_id={player_id}: {repr(last_err)}")
    traceback.print_exc()
    return None


@router.get("/player_bio")
def get_player_bio(
    player_id: str = Query(...),
    season: Optional[str] = Query(None, description="e.g. 2024 or 2024-25; if omitted, compute age as of today")
):
    data = _fetch_player_bio(player_id)
    if not data:
        # Tell the frontend it's an upstream problem, not a CORS/route issue
        raise HTTPException(status_code=502, detail="NBA upstream unavailable")

    age = _age_at_season_start(data.get("birthdate"), season)
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
@router.get("/player_profile_stats")  # keep response_model off unless updated
def get_player_profile_stats(
    player_id: str = Query(...),
    season: Optional[str] = Query(None),
    scale: str = Query("percentile", description="percentile | cap")
):
    try:
        raw_season = season
        season = season or current_nba_season()
        formatted_season = format_season(season).strip()
        print(f"[profile_stats] player={player_id}  raw_season={raw_season!r}  formatted={formatted_season}")

        logs = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=formatted_season,
            season_type_all_star="Regular Season"
        ).get_data_frames()[0]

        if logs.empty:
            return {
                "points":0,"rebounds":0,"assists":0,"blocks":0,"steals":0,"fg_pct":0,"fg3_pct":0,
                "ft_rate":0,"ft_pct":0,"turnovers":0,
                "raw_points":0,"raw_rebounds":0,"raw_assists":0,"raw_blocks":0,"raw_steals":0,
                "raw_fg_pct":0,"raw_fg3_pct":0,"raw_ft_rate":0,"raw_ft_pct":0,"raw_tov":0,
                "scale": scale, "season": formatted_season
            }

        # ---- Per-game means (counting stats) ----
        avgs = logs[['PTS','REB','AST','BLK','STL','TOV']].mean().fillna(0)
        tov_pg = float(avgs['TOV']) if 'TOV' in avgs else 0.0

        # ---- Totals -> season percentages ----
        fgm  = float(logs['FGM'].sum()) if 'FGM' in logs.columns else 0.0
        fga  = float(logs['FGA'].sum()) if 'FGA' in logs.columns else 0.0
        fg3m = float(logs['FG3M'].sum()) if 'FG3M' in logs.columns else 0.0
        fg3a = float(logs['FG3A'].sum()) if 'FG3A' in logs.columns else 0.0
        ftm  = float(logs['FTM'].sum()) if 'FTM' in logs.columns else 0.0
        fta  = float(logs['FTA'].sum()) if 'FTA' in logs.columns else 0.0

        fg_pct_season  = (fgm / fga * 100.0) if fga > 0 else 0.0
        fg3_pct_season = (fg3m / fg3a * 100.0) if fg3a > 0 else 0.0
        ft_pct_season  = (ftm / fta * 100.0) if fta > 0 else 0.0
        ftr_ratio      = (fta / fga) if fga > 0 else 0.0   # FTA/FGA
        ftr_percent    = ftr_ratio * 100.0                 # show as %

        # ---- Normalize the classic legs with your existing utility ----
        normalized = normalize_stats({
            'PTS': avgs['PTS'],
            'REB': avgs['REB'],
            'AST': avgs['AST'],
            'BLK': avgs['BLK'],
            'STL': avgs['STL'],
            'FG_PCT':   fg_pct_season,   # already 0–100
            'FG3_PCT':  fg3_pct_season,  # already 0–100
            'TOV':      tov_pg,          # your normalize may invert; if not, you can invert yourself
            # (we'll supply FT legs separately so charts won’t flatten)
        }, kind="player")

        # ---- NEW: FT legs via league percentiles (fallback to caps) ----
        if scale == "percentile":
            ft_pct_norm  = player_stat_percentile(formatted_season, "FT_PCT",  ft_pct_season)
            ft_rate_norm = player_stat_percentile(formatted_season, "FTR_PCT", ftr_percent)
            scale_used = "percentile"
        else:
            # cap mode: FT%: 50–90% -> 0–100; FTR%: 0–60% -> 0–100
            v_ft  = max(50.0, min(90.0, ft_pct_season))
            v_ftr = max(0.0, min(60.0, ftr_percent))
            ft_pct_norm  = round(((v_ft - 50.0) / 40.0) * 100.0, 1)
            ft_rate_norm = round((v_ftr / 60.0) * 100.0, 1)
            scale_used = "cap"

        # If your normalize() didn’t invert turnovers, you can do it here instead:
        tov_norm = float(normalized.get('turnovers', 0.0))

        return {
            "points":   float(normalized['points']),
            "rebounds": float(normalized['rebounds']),
            "assists":  float(normalized['assists']),
            "blocks":   float(normalized['blocks']),
            "steals":   float(normalized['steals']),
            "fg_pct":   float(normalized['fg_pct']),
            "fg3_pct":  float(normalized['fg3_pct']),
            "ft_rate":  float(ft_rate_norm),    # ✅ fixed
            "ft_pct":   float(ft_pct_norm),     # ✅ fixed
            "turnovers": float(tov_norm),

            # raw hover values
            "raw_points": round(float(avgs['PTS']), 1),
            "raw_rebounds": round(float(avgs['REB']), 1),
            "raw_assists": round(float(avgs['AST']), 1),
            "raw_blocks": round(float(avgs['BLK']), 1),
            "raw_steals": round(float(avgs['STL']), 1),
            "raw_fg_pct": round(fg_pct_season, 1),
            "raw_fg3_pct": round(fg3_pct_season, 1),
            "raw_ft_rate": round(ftr_percent, 1),
            "raw_ft_pct":  round(ft_pct_season, 1),
            "raw_tov":     round(tov_pg, 1),

            "scale": scale,
            "scale_used": scale_used,
            "season": formatted_season,
        }

    except Exception as e:
        print("[player_profile_stats] error:", e)
        return {
            "points":0,"rebounds":0,"assists":0,"blocks":0,"steals":0,"fg_pct":0,"fg3_pct":0,
            "ft_rate":0,"ft_pct":0,"turnovers":0,
            "raw_points":0,"raw_rebounds":0,"raw_assists":0,"raw_blocks":0,"raw_steals":0,
            "raw_fg_pct":0,"raw_fg3_pct":0,"raw_ft_rate":0,"raw_ft_pct":0,"raw_tov":0,
            "scale": scale, "scale_used": "error", "season": formatted_season
        }




# -------------------------
# Debugging endpoint
# -------------------------
@router.get("/_debug/ping_nba")
def ping_nba():
    try:
        test = commonplayerinfo.CommonPlayerInfo(player_id=2544).get_data_frames()
        ok = bool(test and len(test) > 0 and not test[0].empty)
        return {"ok": ok, "note": "CommonPlayerInfo(LeBron) fetched"}
    except Exception as e:
        print("[_debug/ping_nba]", repr(e))
        traceback.print_exc()
        return {"ok": False, "error": str(e)}