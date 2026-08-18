"""Cache-only helpers for validating and joining TeamDashLineups measures."""

from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import mean
from typing import Any

from pair_fit_v2.schema import canonical_pair_key


def extract_result_set(payload: dict[str, Any], name: str) -> dict[str, Any]:
    """Return exactly one named result set or raise a clear validation error."""
    result_sets = payload.get("resultSets")
    if not isinstance(result_sets, list):
        raise ValueError("Payload is missing a resultSets list")

    matches = [item for item in result_sets if item.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"Expected one result set named {name!r}, found {len(matches)}")
    return matches[0]


def result_set_rows(result_set: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a NBA result set to validated row dictionaries."""
    headers = result_set.get("headers")
    raw_rows = result_set.get("rowSet")
    if not isinstance(headers, list) or not all(isinstance(header, str) for header in headers):
        raise ValueError("Result set has invalid headers")
    if not isinstance(raw_rows, list):
        raise ValueError("Result set has invalid rowSet")
    if len(set(headers)) != len(headers):
        raise ValueError("Result set has duplicate headers")

    rows = []
    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, list) or len(raw_row) != len(headers):
            raise ValueError(f"Row {index} does not match header count")
        rows.append(dict(zip(headers, raw_row)))
    return rows


def parse_pair_group_id(group_id: Any) -> tuple[str, str] | None:
    """Parse a Phase 0D TeamDashLineups two-player GROUP_ID into a canonical key."""
    if not isinstance(group_id, str):
        return None
    player_ids = [token for token in group_id.strip("-").split("-") if token]
    if len(player_ids) != 2 or player_ids[0] == player_ids[1]:
        return None
    return canonical_pair_key(player_ids[0], player_ids[1])


def attach_pair_context(
    rows: list[dict[str, Any]], season: str, team_id: str
) -> list[dict[str, Any]]:
    """Attach request context and a canonical pair key without relying on row order."""
    contextual_rows = []
    for row in rows:
        contextual_row = dict(row)
        contextual_row["season"] = season
        contextual_row["team_id"] = str(team_id)
        contextual_row["pair_key"] = parse_pair_group_id(row.get("GROUP_ID"))
        contextual_rows.append(contextual_row)
    return contextual_rows


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    return numeric_value if isfinite(numeric_value) else None


def _field_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [_numeric(row.get(field)) for row in rows]
    numeric_values = [value for value in values if value is not None]
    return {
        "present": any(field in row for row in rows),
        "missing": sum(value is None for value in values),
        "nonnumeric": sum(field in row and value is None for row, value in zip(rows, values)),
        "zero": sum(value == 0 for value in numeric_values),
        "negative": sum(value < 0 for value in numeric_values),
        "min": min(numeric_values) if numeric_values else None,
        "max": max(numeric_values) if numeric_values else None,
        "mean": mean(numeric_values) if numeric_values else None,
    }


def summarize_pair_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Quantify pair identity and shared-sample structural checks."""
    parsed = [row for row in rows if row.get("pair_key") is not None]
    pair_counts = Counter(row["pair_key"] for row in parsed)
    return {
        "raw_pair_rows": len(rows),
        "two_player_rows": len(parsed),
        "same_player_or_malformed_rows": len(rows) - len(parsed),
        "duplicate_canonical_pairs": sum(count - 1 for count in pair_counts.values() if count > 1),
        "zero_game_rows": sum(_numeric(row.get("GP")) == 0 for row in rows),
        "zero_minute_rows": sum(_numeric(row.get("MIN")) == 0 for row in rows),
        "unique_valid_canonical_pairs": len(pair_counts),
    }


def summarize_advanced_targets(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Assess observed Advanced target and reliability fields without filtering rows."""
    fields = [
        "OFF_RATING", "DEF_RATING", "NET_RATING", "E_OFF_RATING", "E_DEF_RATING",
        "E_NET_RATING", "POSS", "PACE", "MIN",
    ]
    summary = {field: _field_summary(rows, field) for field in fields}
    summary["zero_or_missing_possessions"] = sum(
        (_numeric(row.get("POSS")) is None) or (_numeric(row.get("POSS")) == 0)
        for row in rows
    )

    def rating_differences(net_field: str, offense_field: str, defense_field: str) -> dict[str, Any]:
        differences = []
        unavailable = 0
        for row in rows:
            net = _numeric(row.get(net_field))
            offense = _numeric(row.get(offense_field))
            defense = _numeric(row.get(defense_field))
            if net is None or offense is None or defense is None:
                unavailable += 1
                continue
            differences.append(net - (offense - defense))
        return {
            "comparable_rows": len(differences),
            "unavailable_rows": unavailable,
            "min_difference": min(differences) if differences else None,
            "max_difference": max(differences) if differences else None,
            "max_absolute_difference": max((abs(value) for value in differences), default=None),
            "rounding_consistent": bool(differences) and max(abs(value) for value in differences) <= 0.2,
        }

    summary["net_rating_consistency"] = rating_differences(
        "NET_RATING", "OFF_RATING", "DEF_RATING"
    )
    summary["estimated_net_rating_consistency"] = rating_differences(
        "E_NET_RATING", "E_OFF_RATING", "E_DEF_RATING"
    )
    return summary


def join_pair_measures(
    base_rows: list[dict[str, Any]], advanced_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Join measures on season, team ID, and canonical player pair, retaining all keys."""
    def keyed(rows: list[dict[str, Any]]) -> tuple[dict[tuple[str, str, tuple[str, str]], dict[str, Any]], int]:
        index: dict[tuple[str, str, tuple[str, str]], dict[str, Any]] = {}
        duplicates = 0
        for row in rows:
            pair_key = row.get("pair_key")
            if pair_key is None:
                continue
            key = (str(row["season"]), str(row["team_id"]), pair_key)
            if key in index:
                duplicates += 1
            else:
                index[key] = row
        return index, duplicates

    base_index, base_duplicates = keyed(base_rows)
    advanced_index, advanced_duplicates = keyed(advanced_rows)
    base_keys = set(base_index)
    advanced_keys = set(advanced_index)
    matched_keys = base_keys & advanced_keys
    base_only_keys = base_keys - advanced_keys
    advanced_only_keys = advanced_keys - base_keys
    return {
        "base_unique_pairs": len(base_keys),
        "advanced_unique_pairs": len(advanced_keys),
        "matched_pairs": len(matched_keys),
        "base_only_pairs": len(base_only_keys),
        "advanced_only_pairs": len(advanced_only_keys),
        "base_match_rate": len(matched_keys) / len(base_keys) if base_keys else 0.0,
        "advanced_match_rate": len(matched_keys) / len(advanced_keys) if advanced_keys else 0.0,
        "base_duplicate_key_violations": base_duplicates,
        "advanced_duplicate_key_violations": advanced_duplicates,
        "one_to_one": base_duplicates == 0 and advanced_duplicates == 0,
        "base_only_keys": sorted(base_only_keys),
        "advanced_only_keys": sorted(advanced_only_keys),
    }