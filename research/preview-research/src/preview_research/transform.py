from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .datasets import DERIVED_DATASETS, DatasetSpec
from .storage import ResearchStore
from .validation import safe_percentage, validate_dataset, validate_general


def _result_sets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(result, dict):
        return [result]
    if not isinstance(result, list):
        raise ValueError("Malformed NBA result sets")
    return result


def _slug(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def _flatten_shot_headers(headers: list[Any]) -> list[str]:
    if not headers or not all(isinstance(item, dict) for item in headers):
        raise ValueError("Shot-zone response lacks multi-level headers")
    columns_group = next((item for item in headers if item.get("name") == "columns"), None)
    category_group = next((item for item in headers if item.get("name") == "SHOT_CATEGORY"), None)
    if not columns_group or not category_group:
        raise ValueError("Shot-zone response header groups are incomplete")
    base_columns = list(columns_group.get("columnNames", []))
    skip = int(category_group.get("columnsToSkip", 0))
    span = int(category_group.get("columnSpan", 0))
    categories = list(category_group.get("columnNames", []))
    if skip <= 0 or span <= 0 or len(base_columns) < skip:
        raise ValueError("Shot-zone response header dimensions are invalid")
    flattened = [_slug(name) for name in base_columns[:skip]]
    metrics = base_columns[skip: skip + span]
    for category in categories:
        flattened.extend(f"{_slug(category)}_{_slug(metric)}" for metric in metrics)
    return flattened


def _frame_from_result_set(result_set: dict[str, Any], multi_level: bool = False) -> pd.DataFrame:
    headers = result_set.get("headers", [])
    columns = _flatten_shot_headers(headers) if multi_level else headers
    rows = result_set.get("rowSet", [])
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise ValueError("Malformed NBA table")
    if rows and len(columns) != len(rows[0]):
        raise ValueError(f"Header/row width mismatch: {len(columns)} headers and {len(rows[0])} values")
    return pd.DataFrame(rows, columns=columns)


def _drop_source_ranks(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    rank_columns = [column for column in frame.columns if str(column).endswith("_RANK")]
    return frame.drop(columns=rank_columns), rank_columns


def process_nba_payload(
    payload: dict[str, Any],
    spec: DatasetSpec,
    season: str,
    season_type: str,
    *,
    team_id: str | int | None,
    store: ResearchStore,
    raw_metadata: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    by_name = {item.get("name"): item for item in _result_sets(payload)}
    missing_sets = sorted(set(spec.result_sets) - set(by_name))
    if missing_sets:
        raise ValueError(f"Missing expected NBA result sets: {', '.join(missing_sets)}")
    pieces: list[pd.DataFrame] = []
    for name in spec.result_sets:
        piece = _frame_from_result_set(by_name[name], multi_level=spec.multi_level_headers)
        if spec.name == "player_on_off":
            piece["ON_OFF"] = "on" if "OnCourt" in name else "off"
        pieces.append(piece)
    frame = pd.concat(pieces, ignore_index=True)
    frame, excluded_ranks = _drop_source_ranks(frame)
    for identity_column in ("PLAYER_ID", "TEAM_ID", "VS_PLAYER_ID"):
        if identity_column in frame.columns:
            frame[identity_column] = frame[identity_column].astype("string")
    frame["SEASON"] = season
    frame["SEASON_TYPE"] = season_type
    frame["ROW_GRAIN"] = spec.grain
    frame["ROW_SCOPE"] = "combined" if spec.grain.startswith("combined player") else "team_specific"
    frame["SOURCE_PROVIDER"] = "nba"
    report = validate_dataset(frame, spec)
    metadata = {
        **raw_metadata,
        "status": "processed",
        "dataset": spec.name,
        "provider": "nba",
        "row_grain": spec.grain,
        "row_count": len(frame),
        "columns": list(frame.columns),
        "excluded_source_rank_columns": excluded_ranks,
        "keys": list(spec.keys),
        "benchmark_status": "not_checked",
        **report.as_dict(),
    }
    paths = store.paths(spec.name, season, season_type, team_id=team_id)
    store.write_processed(paths, frame, metadata)
    return frame, metadata


def build_shooting(
    entity: str,
    season: str,
    season_type: str,
    *,
    store: ResearchStore | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    store = store or ResearchStore()
    if entity not in {"player", "team"}:
        raise ValueError("entity must be 'player' or 'team'")
    base_name = f"{entity}_base_totals"
    advanced_name = f"{entity}_advanced"
    output_name = f"{entity}_shooting"
    base, base_meta = store.read_processed(base_name, season, season_type)
    try:
        advanced, advanced_meta = store.read_processed(advanced_name, season, season_type)
    except FileNotFoundError:
        advanced = None
        advanced_meta = None
    key = "PLAYER_ID" if entity == "player" else "TEAM_ID"
    if base[key].duplicated().any():
        raise ValueError("Cannot build shooting table from duplicate source keys")
    frame = base.copy()
    if advanced is not None:
        advanced_columns = [key] + [column for column in ("EFG_PCT", "TS_PCT") if column in advanced.columns]
        if advanced[key].duplicated().any():
            raise ValueError("Cannot build shooting table from duplicate source keys")
        frame = frame.merge(advanced[advanced_columns], on=key, how="left", validate="one_to_one", suffixes=("", "_ADV"))
    frame["CALC_FG2M"] = pd.to_numeric(frame["FGM"], errors="coerce") - pd.to_numeric(frame["FG3M"], errors="coerce")
    frame["CALC_FG2A"] = pd.to_numeric(frame["FGA"], errors="coerce") - pd.to_numeric(frame["FG3A"], errors="coerce")
    frame["CALC_FG2_PCT"] = safe_percentage(frame["CALC_FG2M"], frame["CALC_FG2A"])
    frame["CALC_FG_PCT"] = safe_percentage(frame["FGM"], frame["FGA"])
    frame["CALC_FG3_PCT"] = safe_percentage(frame["FG3M"], frame["FG3A"])
    frame["CALC_FT_PCT"] = safe_percentage(frame["FTM"], frame["FTA"])
    frame["CALC_FG3_ATTEMPT_RATE"] = safe_percentage(frame["FG3A"], frame["FGA"])
    frame["CALC_FT_RATE"] = safe_percentage(frame["FTA"], frame["FGA"])
    denominator = 2 * (
        pd.to_numeric(frame["FGA"], errors="coerce")
        + 0.44 * pd.to_numeric(frame["FTA"], errors="coerce")
    )
    frame["CALC_TS_PCT"] = (pd.to_numeric(frame["PTS"], errors="coerce") / denominator).where(denominator > 0)
    frame["CALC_EFG_PCT"] = (
        (pd.to_numeric(frame["FGM"], errors="coerce") + 0.5 * pd.to_numeric(frame["FG3M"], errors="coerce"))
        / pd.to_numeric(frame["FGA"], errors="coerce")
    ).where(pd.to_numeric(frame["FGA"], errors="coerce") > 0)
    spec = DERIVED_DATASETS[output_name]
    report = validate_general(frame, spec["keys"], required=[key, "FGA", "FG3A", "FTA", "PTS"])
    metadata = {
        "dataset": output_name,
        "season": season,
        "season_type": season_type,
        "team_id": None,
        "provider": "derived",
        "source": f"{base_name}" + (f" joined to {advanced_name}" if advanced_meta else " (advanced source unavailable; CALC_ rates only)"),
        "source_metadata": [item.get("raw_sha256") for item in (base_meta, advanced_meta) if item],
        "retrieved_at": max(filter(None, [item.get("retrieved_at") for item in (base_meta, advanced_meta) if item]), default=None),
        "status": "processed",
        "row_grain": spec["grain"],
        "keys": list(spec["keys"]),
        "units": "Counts are season totals; percentages/rates are fractions from 0 to 1; CALC_ fields are local formulas",
        "local_formulas": {
            "CALC_FG2_PCT": "(FGM - FG3M) / (FGA - FG3A)",
            "CALC_FG3_ATTEMPT_RATE": "FG3A / FGA",
            "CALC_FT_RATE": "FTA / FGA",
            "CALC_TS_PCT": "PTS / (2 * (FGA + 0.44 * FTA))",
            "CALC_EFG_PCT": "(FGM + 0.5 * FG3M) / FGA",
        },
        "benchmark_status": "not_checked",
        **report.as_dict(),
    }
    paths = store.paths(output_name, season, season_type, provider="derived")
    store.write_processed(paths, frame, metadata)
    return frame, metadata
