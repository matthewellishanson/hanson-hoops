from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.nba_http import configure_nba_http
from nba_api.stats.endpoints import LeagueDashLineups, LeagueDashPlayerStats

RESEARCH_ROOT = REPO_ROOT / "research" / "pair-fit-v2"
CACHE_ROOT = RESEARCH_ROOT / "cache"
CACHE_ROOT.mkdir(parents=True, exist_ok=True)


def _measure_filename(measure_type: str) -> str:
    return measure_type.lower().replace(" ", "_")


def _cache_path(name: str) -> Path:
    return CACHE_ROOT / f"{name}.json"


def _safe_json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def parse_group_players(group_name: str | None) -> list[str]:
    if not group_name:
        return []
    normalized = group_name.replace(" - ", "-").replace("–", "-")
    candidates = [part.strip() for part in normalized.split("-") if part.strip()]
    return candidates


def format_pair_key(player_ids: list[str]) -> tuple[str, str]:
    ordered = sorted(str(pid).strip() for pid in player_ids if str(pid).strip())
    if len(ordered) != 2:
        raise ValueError(f"Expected exactly 2 player IDs, got {ordered!r}")
    return (ordered[0], ordered[1])


def summarize_lineup_df(df: pd.DataFrame) -> dict[str, Any]:
    rows = len(df)
    group_null = int(df["GROUP_ID"].isna().sum()) if "GROUP_ID" in df.columns else 0
    group_name_null = int(df["GROUP_NAME"].isna().sum()) if "GROUP_NAME" in df.columns else 0
    duplicate_group_ids = int(df.duplicated(subset=["GROUP_ID"]).sum()) if "GROUP_ID" in df.columns else 0
    hours = df.get("MIN")
    zero_minute_rows = int(hours.isna().sum() + (hours == 0).sum()) if hours is not None else 0
    valid_target_rows = 0
    if {"MIN", "ORTG", "DRTG"}.issubset(set(df.columns)):
        not_duplicate = ~df.duplicated(subset=["GROUP_ID"]) if "GROUP_ID" in df.columns else pd.Series([True] * len(df))
        valid_target_rows = int(
            (
                not_duplicate
                & df["MIN"].notna()
                & (df["MIN"] > 0)
                & df["ORTG"].notna()
                & df["DRTG"].notna()
            ).sum()
        )
    pair_issues = 0
    if "GROUP_NAME" in df.columns:
        pair_issues = sum(1 for v in df["GROUP_NAME"].dropna().tolist() if len(parse_group_players(v)) != 2)
    return {
        "row_count": rows,
        "group_id_null": group_null,
        "group_name_null": group_name_null,
        "duplicate_group_ids": duplicate_group_ids,
        "zero_minute_rows": zero_minute_rows,
        "valid_target_rows": valid_target_rows,
        "malformed_pair_names": pair_issues,
        "columns": df.columns.tolist(),
    }


def fetch_lineup_measure(
    measure_type: str,
    season: str = "2024-25",
    season_type: str = "Regular Season",
    group_quantity: str = "2",
    force_live: bool = False,
) -> dict[str, Any]:
    cache_file = _cache_path(f"lineup_{_measure_filename(measure_type)}_{season.replace('-', '_')}")
    if not force_live:
        cached = _read_json(cache_file)
        if cached is not None:
            return {**cached, "source": "cache"}

    try:
        configure_nba_http()
        endpoint = LeagueDashLineups(
            group_quantity=group_quantity,
            measure_type_detailed_defense=measure_type,
            season=season,
            season_type_all_star=season_type,
            timeout=30,
            get_request=True,
        )
        frame = endpoint.get_data_frames()[0]
        summary = summarize_lineup_df(frame)
        payload = {
            "source": "live",
            "measure_type": measure_type,
            "season": season,
            "season_type": season_type,
            "group_quantity": group_quantity,
            "summary": summary,
            "records": frame.to_dict(orient="records"),
            "columns": frame.columns.tolist(),
            "attempts": 1,
        }
        _safe_json_dump(cache_file, payload)
        return payload
    except Exception as exc:  # pragma: no cover - network-bound failure path
        failure = {
            "source": "failure",
            "measure_type": measure_type,
            "season": season,
            "season_type": season_type,
            "group_quantity": group_quantity,
            "attempts": 1,
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }
        _safe_json_dump(cache_file, failure)
        return failure


def fetch_prior_player_stats(
    season: str = "2023-24",
    force_live: bool = False,
) -> dict[str, Any]:
    cache_file = _cache_path(f"player_stats_{season.replace('-', '_')}")
    if not force_live:
        cached = _read_json(cache_file)
        if cached is not None:
            return {**cached, "source": "cache"}

    try:
        configure_nba_http()
        endpoint = LeagueDashPlayerStats(
            season=season,
            season_type_all_star="Regular Season",
            timeout=30,
            get_request=True,
        )
        frame = endpoint.get_data_frames()[0]
        payload = {
            "source": "live",
            "season": season,
            "row_count": len(frame),
            "columns": frame.columns.tolist(),
            "records": frame.to_dict(orient="records"),
            "attempts": 1,
        }
        _safe_json_dump(cache_file, payload)
        return payload
    except Exception as exc:  # pragma: no cover - network-bound failure path
        failure = {
            "source": "failure",
            "season": season,
            "attempts": 1,
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }
        _safe_json_dump(cache_file, failure)
        return failure


def run_live_audit(force_live: bool = True) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for measure in ["Base", "Advanced", "Four Factors", "Usage"]:
        results[measure] = fetch_lineup_measure(measure, force_live=force_live)
    results["prior_player_stats"] = fetch_prior_player_stats(force_live=force_live)
    return results


def run_cached_audit() -> dict[str, Any]:
    return run_live_audit(force_live=False)
