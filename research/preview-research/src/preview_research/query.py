from __future__ import annotations

import hashlib
import json
import operator
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .config import DEFAULT_SEASON_TYPE
from .datasets import DERIVED_DATASETS
from .storage import ResearchStore


@dataclass
class QueryResult:
    frame: pd.DataFrame
    dataset: str
    seasons: tuple[str, ...]
    season_type: str
    metadata: list[dict[str, Any]] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    description: str = ""


def _default_provider(dataset: str) -> str:
    return "derived" if dataset in DERIVED_DATASETS else "nba"


def load_dataset(
    dataset: str,
    seasons: Iterable[str],
    *,
    season_type: str = DEFAULT_SEASON_TYPE,
    team_id: str | int | None = None,
    provider: str | None = None,
    store: ResearchStore | None = None,
) -> QueryResult:
    """Load only saved tables. This function has no network path."""
    store = store or ResearchStore()
    provider = provider or _default_provider(dataset)
    season_list = tuple(seasons)
    if not season_list:
        raise ValueError("At least one explicit season is required")
    frames: list[pd.DataFrame] = []
    metadata: list[dict[str, Any]] = []
    for season in season_list:
        frame, item = store.read_processed(
            dataset, season, season_type, team_id=team_id, provider=provider
        )
        frames.append(frame)
        metadata.append(item)
    combined = pd.concat(frames, ignore_index=True, sort=False)
    return QueryResult(combined, dataset, season_list, season_type, metadata)


_CONDITION = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(<=|>=|==|!=|<|>)\s*"
    r"(-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*$"
)
_OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


def apply_numeric_conditions(frame: pd.DataFrame, conditions: Iterable[str]) -> pd.DataFrame:
    selected = frame
    for condition in conditions:
        match = _CONDITION.fullmatch(condition)
        if not match:
            raise ValueError(f"Invalid numeric condition {condition!r}; example: MIN>=500")
        column, symbol, raw_value = match.groups()
        if column not in selected.columns:
            raise KeyError(f"Unknown condition column: {column}")
        values = pd.to_numeric(selected[column], errors="coerce")
        selected = selected.loc[_OPERATORS[symbol](values, float(raw_value))]
    return selected


def filter_rows(
    result: QueryResult,
    *,
    conditions: Iterable[str] = (),
    player: str | None = None,
    team: str | None = None,
    sort_by: str | None = None,
    descending: bool = False,
    limit: int | None = None,
    columns: Iterable[str] | None = None,
) -> QueryResult:
    frame = result.frame.copy()
    applied = list(result.filters)
    conditions = list(conditions)
    if conditions:
        frame = apply_numeric_conditions(frame, conditions)
        applied.extend(conditions)
    if player:
        player_columns = [column for column in ("PLAYER_ID", "PLAYER_NAME", "VS_PLAYER_ID", "VS_PLAYER_NAME") if column in frame.columns]
        if not player_columns:
            raise KeyError("Dataset has no player identifier")
        mask = pd.Series(False, index=frame.index)
        for column in player_columns:
            mask |= frame[column].astype("string").str.casefold().eq(str(player).casefold())
        frame = frame.loc[mask]
        applied.append(f"player={player}")
    if team:
        team_columns = [column for column in ("TEAM_ID", "TEAM_NAME", "TEAM_ABBREVIATION") if column in frame.columns]
        if not team_columns:
            raise KeyError("Dataset has no team identifier")
        mask = pd.Series(False, index=frame.index)
        for column in team_columns:
            mask |= frame[column].astype("string").str.casefold().eq(str(team).casefold())
        frame = frame.loc[mask]
        applied.append(f"team={team}")
    if sort_by:
        if sort_by not in frame.columns:
            raise KeyError(f"Unknown sort column: {sort_by}")
        frame = frame.sort_values(sort_by, ascending=not descending, na_position="last", kind="stable")
        applied.append(f"sort={sort_by}:{'desc' if descending else 'asc'}")
    if limit is not None:
        if limit < 0:
            raise ValueError("limit must be nonnegative")
        frame = frame.head(limit)
        applied.append(f"limit={limit}")
    if columns:
        requested = list(columns)
        missing = sorted(set(requested) - set(frame.columns))
        if missing:
            raise KeyError(f"Unknown selected columns: {', '.join(missing)}")
        frame = frame[requested]
        applied.append(f"columns={','.join(requested)}")
    return QueryResult(
        frame.reset_index(drop=True), result.dataset, result.seasons,
        result.season_type, result.metadata, applied, result.description,
    )


def join_compatible(
    left: QueryResult,
    right: QueryResult,
    *,
    keys: Iterable[str] | None = None,
    how: str = "inner",
    suffixes: tuple[str, str] = ("_LEFT", "_RIGHT"),
) -> QueryResult:
    if left.seasons != right.seasons or left.season_type != right.season_type:
        raise ValueError("Joins require identical explicit season and season-type selections")
    if keys is None:
        if "VS_PLAYER_ID" in left.frame.columns and "VS_PLAYER_ID" in right.frame.columns:
            candidates = ("VS_PLAYER_ID", "TEAM_ID", "SEASON", "SEASON_TYPE", "ON_OFF")
        elif "PLAYER_ID" in left.frame.columns and "PLAYER_ID" in right.frame.columns:
            # LeagueDashPlayerStats is combined player-season grain. TEAM_ID can
            # display a current/final team and must never be treated as stint identity.
            candidates = ("PLAYER_ID", "SEASON", "SEASON_TYPE")
        else:
            candidates = ("TEAM_ID", "SEASON", "SEASON_TYPE")
        keys = [column for column in candidates if column in left.frame.columns and column in right.frame.columns]
    keys = list(keys)
    if not keys:
        raise ValueError("No compatible stable join keys; pass explicit keys")
    for label, frame in (("left", left.frame), ("right", right.frame)):
        missing = sorted(set(keys) - set(frame.columns))
        if missing:
            raise KeyError(f"{label} table lacks join keys: {', '.join(missing)}")
        if frame.duplicated(keys).any():
            raise ValueError(f"{label} table is not unique at join grain {keys}")
    joined = left.frame.merge(right.frame, on=keys, how=how, validate="one_to_one", suffixes=suffixes)
    return QueryResult(
        joined,
        f"{left.dataset}+{right.dataset}",
        left.seasons,
        left.season_type,
        left.metadata + right.metadata,
        left.filters + right.filters + [f"join_keys={','.join(keys)}", f"join_how={how}"],
        "One-to-one compatible table join",
    )


def compare_entity(
    result: QueryResult,
    entity: str,
    *,
    metrics: Iterable[str],
    id_column: str | None = None,
) -> QueryResult:
    if id_column is None:
        id_column = "PLAYER_ID" if "PLAYER_ID" in result.frame.columns else "TEAM_ID"
    metrics = list(metrics)
    required = [id_column, "SEASON", *metrics]
    missing = sorted(set(required) - set(result.frame.columns))
    if missing:
        raise KeyError(f"Comparison columns unavailable: {', '.join(missing)}")
    name_columns = [column for column in ("PLAYER_NAME", "TEAM_NAME", "TEAM_ABBREVIATION") if column in result.frame.columns]
    matched = result.frame[result.frame[id_column].astype("string").str.casefold().eq(str(entity).casefold())]
    if matched.empty:
        for name_column in name_columns:
            matched = result.frame[result.frame[name_column].astype("string").str.casefold().eq(str(entity).casefold())]
            if not matched.empty:
                break
    selected = matched[[id_column, *name_columns, "SEASON", "SEASON_TYPE", *metrics]].copy()
    selected = selected.sort_values("SEASON", kind="stable")
    return QueryResult(
        selected.reset_index(drop=True), result.dataset, result.seasons,
        result.season_type, result.metadata, result.filters + [f"entity={entity}", f"metrics={','.join(metrics)}"],
        "Same entity across explicitly selected seasons",
    )


def year_over_year(
    result: QueryResult,
    metric: str,
    *,
    id_column: str | None = None,
) -> QueryResult:
    if metric not in result.frame.columns:
        raise KeyError(metric)
    if id_column is None:
        id_column = "PLAYER_ID" if "PLAYER_ID" in result.frame.columns else "TEAM_ID"
    required = {id_column, "SEASON", metric}
    if not required <= set(result.frame.columns):
        raise KeyError(f"Year-over-year calculation requires {sorted(required)}")
    if result.frame.duplicated([id_column, "SEASON"]).any():
        raise ValueError("Year-over-year input must be unique by entity and season")
    frame = result.frame.copy()
    season_order = {season: index for index, season in enumerate(result.seasons)}
    frame["_season_order"] = frame["SEASON"].map(season_order)
    frame = frame.sort_values([id_column, "_season_order"], kind="stable")
    numeric = pd.to_numeric(frame[metric], errors="coerce")
    frame[f"CHANGE_{metric}"] = numeric.groupby(frame[id_column], sort=False).diff()
    frame = frame.drop(columns="_season_order")
    return QueryResult(
        frame.reset_index(drop=True), result.dataset, result.seasons,
        result.season_type, result.metadata, result.filters + [f"yoy_metric={metric}"],
        f"Year-over-year arithmetic change in {metric}",
    )


def _reject_nonfinite_export(frame: pd.DataFrame) -> None:
    numeric = frame.select_dtypes(include="number")
    if numeric.empty:
        return
    values = numeric.to_numpy(dtype=float, na_value=np.nan)
    if np.isinf(values).any():
        raise ValueError("Export rejected because one or more chart values are infinite")


def export_result(result: QueryResult, path: str | Path, *, notes: str = "") -> tuple[Path, Path]:
    _reject_nonfinite_export(result.frame)
    csv_path = Path(path)
    if not csv_path.is_absolute():
        csv_path = ResearchStore().exports_root / csv_path
    if csv_path.suffix.lower() != ".csv":
        csv_path = csv_path.with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    result.frame.to_csv(csv_path, index=False, lineterminator="\n")
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    note_path = csv_path.with_suffix(".notes.md")
    sources = []
    for item in result.metadata:
        sources.append({
            "source": item.get("source"),
            "provider": item.get("provider"),
            "retrieved_at": item.get("retrieved_at"),
            "raw_sha256": item.get("raw_sha256"),
            "validation_status": item.get("validation_status"),
            "benchmark_status": item.get("benchmark_status", "not_checked"),
            "row_grain": item.get("row_grain"),
        })
    lines = [
        f"# Export note: {csv_path.name}",
        "",
        f"- Exported at (UTC): {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        f"- Dataset: `{result.dataset}`",
        f"- Seasons: `{', '.join(result.seasons)}`",
        f"- Season type: `{result.season_type}`",
        f"- Rows: `{len(result.frame)}`",
        f"- CSV SHA-256: `{digest}`",
        f"- Filters: `{'; '.join(result.filters) if result.filters else 'none'}`",
        "- Percentage convention: fraction from 0 to 1 unless the source metadata explicitly says otherwise.",
        "- Missing values are preserved. Infinite numeric values are rejected.",
        "- `CALC_` columns are local calculations; other statistics retain their named source definition.",
        "",
        "## Sources and validation",
        "",
        "```json",
        json.dumps(sources, indent=2, sort_keys=True),
        "```",
    ]
    if result.description:
        lines.extend(["", f"Description: {result.description}"])
    if notes:
        lines.extend(["", "## Writer note", "", notes])
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, note_path
