from __future__ import annotations

from functools import lru_cache
from numbers import Real

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.feature_engineering.axes import compute_axes
from app.feature_engineering.fetch_stats import player_pool
from app.feature_engineering.normalize import METRIC_COLUMNS, body_based_percentiles
from app.feature_engineering.pair_features import build_pair_features
from app.feature_engineering.scoring import score_pair
from app.services.nba_http import NBAUpstreamError
from app.services.snapshots import comparison_coverage
from app.utils.cache import cache
from app.utils.seasons import current_nba_season, format_season

router = APIRouter(prefix="/fit", tags=["Projected Fit"])


def _require_fit_coverage(*seasons: str) -> None:
    entries = {
        item.get("season"): item
        for item in comparison_coverage().get("seasons", [])
        if isinstance(item, dict)
    }
    unavailable = [season for season in seasons if season in entries and not entries[season].get("fit")]
    if unavailable:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "fit_data_unavailable",
                "message": f"Projected-fit inputs are unavailable for {', '.join(unavailable)}.",
                "retryable": False,
            },
        )


def _to_row_dict(r: pd.Series) -> dict:
    # Convert a pandas row into JSON-safe primitives used by downstream scoring.
    d = r.to_dict()
    for k, v in list(d.items()):
        if isinstance(v, Real):
            d[k] = None if pd.isna(v) else float(v)
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
        raise NBAUpstreamError("fit_player_pool_empty")
    data_source = raw.attrs.get("data_source", "live")
    pcts = body_based_percentiles(raw, metric_cols=METRIC_COLUMNS, k_neighbors=40, shrinkage_floor=25)
    feats = pd.concat([raw.reset_index(drop=True), pcts.reset_index(drop=True)], axis=1)
    feats = compute_axes(feats)
    feats.attrs["data_source"] = data_source
    return feats


def _pair_payload(
    df_a: pd.DataFrame,
    player_a: int,
    player_b: int,
    emphasis: dict[str, float],
    primary_handler: str,
    df_b: pd.DataFrame | None = None,
    season_a: str | None = None,
    season_b: str | None = None,
) -> dict:
    # Build one complete pair response object used by /pair and /top routes.
    df_b = df_a if df_b is None else df_b
    row_a = df_a[df_a["PLAYER_ID"] == player_a]
    row_b = df_b[df_b["PLAYER_ID"] == player_b]
    if row_a.empty:
        suffix = f" for {season_a}" if season_a else ""
        raise HTTPException(status_code=404, detail=f"Player A not found in fit pool/minutes filter{suffix}.")
    if row_b.empty:
        suffix = f" for {season_b}" if season_b else ""
        raise HTTPException(status_code=404, detail=f"Player B not found in fit pool/minutes filter{suffix}.")

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
            "season": season_a,
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
            "season": season_b,
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
    _require_fit_coverage(season_fmt)
    df = _feature_table(season_fmt, min_minutes=min_minutes)

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
        "data_source": df.attrs.get("data_source", "live"),
        "model_version": "fit-v1.0.0",
    }


@router.get("/pair/{player_a}/{player_b}")
def fit_pair(
    player_a: int,
    player_b: int,
    season: str | None = Query(None),
    season_a: str | None = Query(None),
    season_b: str | None = Query(None),
    min_minutes: int = Query(300, ge=0),
    offense: float = Query(1.0, ge=0.5, le=1.8),
    defense: float = Query(1.0, ge=0.5, le=1.8),
    spacers: float = Query(1.0, ge=0.5, le=1.8),
    rebounding: float = Query(1.0, ge=0.5, le=1.8),
    primary_handler: str = Query("auto", pattern="^(auto|a|b)$"),
):
    fallback_season = season or current_nba_season()
    season_a_fmt = format_season(season_a or fallback_season)
    season_b_fmt = format_season(season_b or fallback_season)
    _require_fit_coverage(season_a_fmt, season_b_fmt)
    if player_a == player_b and season_a_fmt == season_b_fmt:
        raise HTTPException(status_code=400, detail="Choose two different player-seasons.")

    df_a = _feature_table(season_a_fmt, min_minutes=min_minutes)
    df_b = df_a if season_b_fmt == season_a_fmt else _feature_table(season_b_fmt, min_minutes=min_minutes)

    emphasis = {
        "offense": float(offense),
        "defense": float(defense),
        "spacers": float(spacers),
        "rebounding": float(rebounding),
    }

    key = (
        "fit_pair",
        "fit-v1.0.0",
        season_a_fmt,
        season_b_fmt,
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
    payload = cache.get_or_set(
        key,
        lambda: _pair_payload(
            df_a,
            int(player_a),
            int(player_b),
            emphasis,
            primary_handler,
            df_b=df_b,
            season_a=season_a_fmt,
            season_b=season_b_fmt,
        ),
    )
    return {
        "season": season_a_fmt if season_a_fmt == season_b_fmt else None,
        "season_a": season_a_fmt,
        "season_b": season_b_fmt,
        "data_source": (
            df_a.attrs.get("data_source", "live")
            if df_a is df_b
            else {
                "player_a": df_a.attrs.get("data_source", "live"),
                "player_b": df_b.attrs.get("data_source", "live"),
            }
        ),
        "data_source_a": df_a.attrs.get("data_source", "live"),
        "data_source_b": df_b.attrs.get("data_source", "live"),
        "model_version": "fit-v1.0.0",
        **payload,
    }


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
    _require_fit_coverage(season_fmt)
    df = _feature_table(season_fmt, min_minutes=min_minutes)
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
        "data_source": df.attrs.get("data_source", "live"),
        "model_version": "fit-v1.0.0",
    }
