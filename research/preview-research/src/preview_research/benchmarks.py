from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from .storage import ResearchStore, write_json


def record_benchmark(
    dataset: str,
    season: str,
    season_type: str,
    *,
    column: str,
    entity_column: str,
    entity: str,
    expected: float,
    tolerance: float,
    source: str,
    source_url: str,
    team_id: str | int | None = None,
    provider: str = "nba",
    store: ResearchStore | None = None,
) -> dict:
    store = store or ResearchStore()
    frame, metadata = store.read_processed(dataset, season, season_type, team_id=team_id, provider=provider)
    for required in (column, entity_column):
        if required not in frame.columns:
            raise KeyError(required)
    match = frame[frame[entity_column].astype("string").str.casefold().eq(str(entity).casefold())]
    if len(match) != 1:
        raise ValueError(f"Benchmark entity matched {len(match)} rows; expected exactly one")
    actual = float(pd.to_numeric(match.iloc[0][column], errors="raise"))
    passed = abs(actual - expected) <= tolerance
    check = {
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "column": column,
        "entity_column": entity_column,
        "entity": entity,
        "expected": expected,
        "actual": actual,
        "tolerance": tolerance,
        "source": source,
        "source_url": source_url,
        "passed": passed,
    }
    metadata.setdefault("benchmark_checks", []).append(check)
    metadata["benchmark_status"] = "benchmark_checked" if all(item["passed"] for item in metadata["benchmark_checks"]) else "benchmark_failed"
    paths = store.paths(dataset, season, season_type, team_id=team_id, provider=provider)
    write_json(paths.processed_metadata, metadata)
    if not passed:
        raise ValueError(json.dumps(check, sort_keys=True))
    return check

