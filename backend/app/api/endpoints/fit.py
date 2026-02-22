from __future__ import annotations

from functools import lru_cache

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.feature_engineering.axes import compute_axes
from app.feature_engineering.fetch_stats import player_pool
from app.feature_engineering.normalize import METRIC_COLUMNS, body_based_percentiles
from app.feature_engineering.pair_features import build_pair_features
from app.feature_engineering.scoring import score_pair
from app.utils.cache import cache
from app.utils.seasons import current_nba_season, format_season

router = APIRouter(prefix="/fit", tags=["Projected Fit"])


def _to_row_dict(r: pd.Series) -> dict:
    # Convert a pandas row into JSON-safe primitives used by downstream scoring.
    d = r.to_dict()
    for k, v in list(d.items()):
        if isinstance(v, (int, float)):
            d[k] = float(v)
    d["PLAYER_ID"] = int(r["PLAYER_ID"])
    d["PLAYER_NAME"] = str(r["PLAYER_NAME"])
    d["TEAM_ABBREVIATION"] = str(r.get("TEAM_ABBREVIATION", ""))
    return d


@lru_cache(maxsize=8)
def _feature_table(season_fmt: str, min_minutes: int) -> pd.DataFrame:
    # Core pipeline:
    # 1) pull filtered player stats, 2) body-based percentiles, 3) style axes.
    # Cached by season + minute threshold to avoid recomputing on every request.
    raw = player_pool(season_fmt, min_minutes=min_minutes)
    if raw.empty:
        return pd.DataFrame()
    pcts = body_based_percentiles(raw, metric_cols=METRIC_COLUMNS, k_neighbors=40, shrinkage_floor=25)
    feats = pd.concat([raw.reset_index(drop=True), pcts.reset_index(drop=True)], axis=1)
    feats = compute_axes(feats)
    return feats


def _pair_payload(
    df: pd.DataFrame,
    player_a: int,
    player_b: int,
    emphasis: dict[str, float],
    primary_handler: str,
) -> dict:
    # Build one complete pair response object used by /pair and /top routes.
    row_a = df[df["PLAYER_ID"] == player_a]
    row_b = df[df["PLAYER_ID"] == player_b]
    if row_a.empty or row_b.empty:
        raise HTTPException(status_code=404, detail="Player not found in current fit pool/minutes filter.")

    a = _to_row_dict(row_a.iloc[0])
    b = _to_row_dict(row_b.iloc[0])
    pfeat = build_pair_features(a, b, primary_handler=primary_handler)
    scored = score_pair(a, b, pfeat, emphasis=emphasis)

    return {
        "player_a": {
            "player_id": a["PLAYER_ID"],
            "name": a["PLAYER_NAME"],
            "team": a["TEAM_ABBREVIATION"],
            "minutes": round(float(a.get("MIN", 0.0)), 1),
            "axes": {
                "creation_load": round(float(a.get("AXIS_CREATION_LOAD", 0.0)), 1),
                "scoring_pressure": round(float(a.get("AXIS_SCORING_PRESSURE", 0.0)), 1),
                "spacing_gravity": round(float(a.get("AXIS_SPACING_GRAVITY", 0.0)), 1),
                "ball_security": round(float(a.get("AXIS_BALL_SECURITY", 0.0)), 1),
                "disruption": round(float(a.get("AXIS_DISRUPTION", 0.0)), 1),
                "rim_protection": round(float(a.get("AXIS_RIM_PROTECTION", 0.0)), 1),
                "rebounding": round(float(a.get("AXIS_REBOUNDING", 0.0)), 1),
                "discipline": round(float(a.get("AXIS_DISCIPLINE", 0.0)), 1),
            },
        },
        "player_b": {
            "player_id": b["PLAYER_ID"],
            "name": b["PLAYER_NAME"],
            "team": b["TEAM_ABBREVIATION"],
            "minutes": round(float(b.get("MIN", 0.0)), 1),
            "axes": {
                "creation_load": round(float(b.get("AXIS_CREATION_LOAD", 0.0)), 1),
                "scoring_pressure": round(float(b.get("AXIS_SCORING_PRESSURE", 0.0)), 1),
                "spacing_gravity": round(float(b.get("AXIS_SPACING_GRAVITY", 0.0)), 1),
                "ball_security": round(float(b.get("AXIS_BALL_SECURITY", 0.0)), 1),
                "disruption": round(float(b.get("AXIS_DISRUPTION", 0.0)), 1),
                "rim_protection": round(float(b.get("AXIS_RIM_PROTECTION", 0.0)), 1),
                "rebounding": round(float(b.get("AXIS_REBOUNDING", 0.0)), 1),
                "discipline": round(float(b.get("AXIS_DISCIPLINE", 0.0)), 1),
            },
        },
        "pair_components": pfeat,
        **scored,
    }


@router.get("/player/{player_id}")
def fit_player(
    player_id: int,
    season: str | None = Query(None),
    min_minutes: int = Query(300, ge=0),
):
    # Single-player endpoint returns the normalized axis profile used by pair logic.
    season_fmt = format_season(season or current_nba_season())
    df = _feature_table(season_fmt, min_minutes=min_minutes)
    if df.empty:
        raise HTTPException(status_code=502, detail="No player pool available for fit model.")

    row = df[df["PLAYER_ID"] == int(player_id)]
    if row.empty:
        raise HTTPException(status_code=404, detail="Player not found in fit pool/minutes filter.")

    a = _to_row_dict(row.iloc[0])
    return {
        "season": season_fmt,
        "player_id": a["PLAYER_ID"],
        "name": a["PLAYER_NAME"],
        "team": a["TEAM_ABBREVIATION"],
        "minutes": round(float(a.get("MIN", 0.0)), 1),
        "games": round(float(a.get("GP", 0.0)), 1),
        "axes": {
            "creation_load": round(float(a.get("AXIS_CREATION_LOAD", 0.0)), 1),
            "scoring_pressure": round(float(a.get("AXIS_SCORING_PRESSURE", 0.0)), 1),
            "spacing_gravity": round(float(a.get("AXIS_SPACING_GRAVITY", 0.0)), 1),
            "ball_security": round(float(a.get("AXIS_BALL_SECURITY", 0.0)), 1),
            "disruption": round(float(a.get("AXIS_DISRUPTION", 0.0)), 1),
            "rim_protection": round(float(a.get("AXIS_RIM_PROTECTION", 0.0)), 1),
            "rebounding": round(float(a.get("AXIS_REBOUNDING", 0.0)), 1),
            "discipline": round(float(a.get("AXIS_DISCIPLINE", 0.0)), 1),
        },
        "model_note": "Projected fit uses style complementarity, not observed on-court synergy.",
    }


@router.get("/pair/{player_a}/{player_b}")
def fit_pair(
    player_a: int,
    player_b: int,
    season: str | None = Query(None),
    min_minutes: int = Query(300, ge=0),
    offense: float = Query(1.0, ge=0.5, le=1.8),
    defense: float = Query(1.0, ge=0.5, le=1.8),
    spacers: float = Query(1.0, ge=0.5, le=1.8),
    rebounding: float = Query(1.0, ge=0.5, le=1.8),
    primary_handler: str = Query("auto", pattern="^(auto|a|b)$"),
):
    if player_a == player_b:
        raise HTTPException(status_code=400, detail="Choose two different players.")

    season_fmt = format_season(season or current_nba_season())
    df = _feature_table(season_fmt, min_minutes=min_minutes)
    if df.empty:
        raise HTTPException(status_code=502, detail="No player pool available for fit model.")

    emphasis = {
        "offense": float(offense),
        "defense": float(defense),
        "spacers": float(spacers),
        "rebounding": float(rebounding),
    }

    key = (
        "fit_pair",
        season_fmt,
        int(min_minutes),
        int(player_a),
        int(player_b),
        round(offense, 2),
        round(defense, 2),
        round(spacers, 2),
        round(rebounding, 2),
        primary_handler,
    )
    # Cache pair results because this route can be hit repeatedly when users move sliders.
    return cache.get_or_set(key, lambda: _pair_payload(df, int(player_a), int(player_b), emphasis, primary_handler))


@router.get("/player/{player_id}/top")
def fit_top_partners(
    player_id: int,
    n: int = Query(50, ge=1, le=100),
    season: str | None = Query(None),
    min_minutes: int = Query(300, ge=0),
    offense: float = Query(1.0, ge=0.5, le=1.8),
    defense: float = Query(1.0, ge=0.5, le=1.8),
    spacers: float = Query(1.0, ge=0.5, le=1.8),
    rebounding: float = Query(1.0, ge=0.5, le=1.8),
):
    # Brute-force over eligible players, then return the top N projected partners.
    season_fmt = format_season(season or current_nba_season())
    df = _feature_table(season_fmt, min_minutes=min_minutes)
    if df.empty:
        raise HTTPException(status_code=502, detail="No player pool available for fit model.")
    if int(player_id) not in set(df["PLAYER_ID"].astype(int).tolist()):
        raise HTTPException(status_code=404, detail="Player not found in fit pool/minutes filter.")

    emphasis = {
        "offense": float(offense),
        "defense": float(defense),
        "spacers": float(spacers),
        "rebounding": float(rebounding),
    }

    partners = []
    for pid in df["PLAYER_ID"].astype(int).tolist():
        if pid == int(player_id):
            continue
        payload = _pair_payload(df, int(player_id), pid, emphasis, primary_handler="auto")
        partners.append(
            {
                "partner_id": payload["player_b"]["player_id"],
                "partner_name": payload["player_b"]["name"],
                "partner_team": payload["player_b"]["team"],
                "fit_score": payload["fit_score"],
                "confidence": payload["confidence"],
                "top_positive_driver": payload["drivers_positive"][0]["component"] if payload["drivers_positive"] else None,
                "top_risk": payload["risks"][0] if payload["risks"] else None,
            }
        )
    partners.sort(key=lambda x: x["fit_score"], reverse=True)
    return {
        "season": season_fmt,
        "player_id": int(player_id),
        "count": min(n, len(partners)),
        "items": partners[:n],
        "model_note": "Projected fit uses style complementarity, not observed on-court synergy.",
    }
