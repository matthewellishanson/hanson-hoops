"""Phase 1A: multi-team schema comparison and combined-key validation.

Extends the Phase 0 lineup_audit / player_audit modules; does not duplicate them.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def schema_fingerprint(result_set: dict[str, Any]) -> dict[str, Any]:
    """Return a stable fingerprint of a result set's structure.

    Contains only the result-set name, column count, and ordered column names.
    Deliberately excludes row count: row count is dataset metadata, not schema,
    and two result sets with identical schema commonly have different row counts.
    """
    headers = result_set.get("headers", [])
    return {
        "name": result_set.get("name"),
        "column_count": len(headers),
        "columns": list(headers),
    }


def compare_schema_fingerprints(fingerprints: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compare named schema fingerprints (e.g. one per team) for a single measure/result-set.

    Reports exact matches, column-order differences, and missing/additional columns
    without silently coercing any difference away.
    """
    teams = list(fingerprints.keys())
    if not teams:
        return {"teams": [], "all_identical": True, "differences": {}}

    reference_team = teams[0]
    reference_columns = fingerprints[reference_team]["columns"]
    reference_set = set(reference_columns)

    differences = {}
    for team in teams[1:]:
        columns = fingerprints[team]["columns"]
        column_set = set(columns)
        missing = sorted(reference_set - column_set)
        additional = sorted(column_set - reference_set)
        same_columns_different_order = (
            column_set == reference_set and columns != reference_columns
        )
        if columns != reference_columns or missing or additional:
            differences[team] = {
                "missing_relative_to_reference": missing,
                "additional_relative_to_reference": additional,
                "same_columns_different_order": same_columns_different_order,
            }

    return {
        "reference_team": reference_team,
        "teams": teams,
        "all_identical": len(differences) == 0,
        "differences": differences,
    }


def combine_pair_tables(team_rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Combine per-team pair rows into one table, tagging each row's source team.

    Does not deduplicate across teams: the same player or pair on different
    teams is a distinct team-context observation.
    """
    combined = []
    for team_id, rows in team_rows.items():
        for row in rows:
            combined_row = dict(row)
            combined_row["source_team_id"] = team_id
            combined.append(combined_row)
    return combined


def validate_combined_observation_keys(combined_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate the four-team combined canonical observation key.

    Canonical key: (season, team_id, canonical player 1 ID, canonical player 2 ID).
    """
    key_counts: Counter[tuple[str, str, str, str]] = Counter()
    player_to_teams: dict[str, set[str]] = defaultdict(set)
    pair_to_teams: dict[tuple[str, str], set[str]] = defaultdict(set)

    for row in combined_rows:
        pair_key = row.get("pair_key")
        if pair_key is None:
            continue
        season = str(row.get("season"))
        team_id = str(row.get("team_id"))
        observation_key = (season, team_id, pair_key[0], pair_key[1])
        key_counts[observation_key] += 1
        player_to_teams[pair_key[0]].add(team_id)
        player_to_teams[pair_key[1]].add(team_id)
        pair_to_teams[pair_key].add(team_id)

    duplicate_keys = {key: count for key, count in key_counts.items() if count > 1}
    cross_team_players = {player: sorted(teams) for player, teams in player_to_teams.items() if len(teams) > 1}
    cross_team_pairs = {pair: sorted(teams) for pair, teams in pair_to_teams.items() if len(teams) > 1}

    return {
        "combined_row_count": len(combined_rows),
        "unique_observation_keys": len(key_counts),
        "duplicate_observation_key_count": len(duplicate_keys),
        "duplicate_observation_keys": duplicate_keys,
        "cross_team_player_count": len(cross_team_players),
        "cross_team_players": cross_team_players,
        "cross_team_pair_count": len(cross_team_pairs),
        "cross_team_pairs": {f"{pair[0]}-{pair[1]}": teams for pair, teams in cross_team_pairs.items()},
    }


def possession_distribution(rows: list[dict[str, Any]], field: str = "POSS") -> dict[str, Any]:
    """Descriptive exposure distribution for a numeric field, plus sparse-sample bucket counts.

    No threshold is applied or recommended; this is descriptive only.
    """
    values = sorted(
        float(row[field]) for row in rows if isinstance(row.get(field), (int, float)) and not isinstance(row.get(field), bool)
    )
    if not values:
        return {"count": 0}

    def percentile(data: list[float], fraction: float) -> float:
        if len(data) == 1:
            return data[0]
        index = fraction * (len(data) - 1)
        lower = int(index)
        upper = min(lower + 1, len(data) - 1)
        weight = index - lower
        return data[lower] * (1 - weight) + data[upper] * weight

    return {
        "count": len(values),
        "minimum": values[0],
        "p25": percentile(values, 0.25),
        "median": percentile(values, 0.5),
        "p75": percentile(values, 0.75),
        "maximum": values[-1],
        "below_10": sum(value < 10 for value in values),
        "below_25": sum(value < 25 for value in values),
        "below_50": sum(value < 50 for value in values),
        "below_100": sum(value < 100 for value in values),
        "below_200": sum(value < 200 for value in values),
    }
