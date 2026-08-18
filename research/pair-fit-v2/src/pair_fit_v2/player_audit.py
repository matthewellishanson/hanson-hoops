"""Cache-only helpers for auditing LeagueDashPlayerStats and joining it to pairs."""

from __future__ import annotations

from collections import Counter, defaultdict
from math import isfinite
from statistics import mean
from typing import Any

RANKING_SUFFIX = "_RANK"

# Fields that identify a player row rather than describing performance.
IDENTITY_FIELDS = ("PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE", "GP", "MIN")


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    return numeric_value if isfinite(numeric_value) else None


def player_rows_by_id(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group player rows by their raw (unvalidated) PLAYER_ID string."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        player_id = row.get("PLAYER_ID")
        if player_id is None:
            continue
        grouped[str(player_id)].append(row)
    return grouped


def audit_stable_ids(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Quantify PLAYER_ID stability without resolving duplicates."""
    raw_rows = len(rows)
    non_null_ids = [row.get("PLAYER_ID") for row in rows if row.get("PLAYER_ID") not in (None, "")]
    malformed_ids = sum(
        1 for row in rows if row.get("PLAYER_ID") in (None, "")
    )
    id_counts = Counter(str(player_id) for player_id in non_null_ids)
    duplicate_ids = {player_id: count for player_id, count in id_counts.items() if count > 1}

    name_to_ids: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        player_id = row.get("PLAYER_ID")
        name = row.get("PLAYER_NAME")
        if player_id in (None, "") or not name:
            continue
        name_to_ids[name].add(str(player_id))
    duplicate_names_different_ids = {
        name: sorted(ids) for name, ids in name_to_ids.items() if len(ids) > 1
    }

    duplicate_id_teams: dict[str, list[dict[str, Any]]] = {}
    for player_id in duplicate_ids:
        matching_rows = [row for row in rows if str(row.get("PLAYER_ID")) == player_id]
        duplicate_id_teams[player_id] = [
            {"TEAM_ID": row.get("TEAM_ID"), "TEAM_ABBREVIATION": row.get("TEAM_ABBREVIATION")}
            for row in matching_rows
        ]

    return {
        "raw_player_rows": raw_rows,
        "non_null_player_ids": len(non_null_ids),
        "unique_player_ids": len(id_counts),
        "duplicate_player_id_count": len(duplicate_ids),
        "missing_or_malformed_player_ids": malformed_ids,
        "duplicate_player_ids": duplicate_ids,
        "duplicate_id_team_context": duplicate_id_teams,
        "duplicate_names_different_ids": duplicate_names_different_ids,
        "appears_one_row_per_player": len(duplicate_ids) == 0,
    }


def summarize_prior_feature_fields(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize non-ranking Base field missingness across observed player rows."""
    if not rows:
        return {}
    fields = [field for field in rows[0].keys() if not field.endswith(RANKING_SUFFIX)]
    summary = {}
    for field in fields:
        values = [_numeric(row.get(field)) for row in rows]
        numeric_values = [value for value in values if value is not None]
        summary[field] = {
            "missing": sum(field not in row or row.get(field) is None for row in rows),
            "zero": sum(value == 0 for value in numeric_values),
            "present_non_null": sum(field in row and row.get(field) is not None for row in rows),
        }
    return summary


def attach_prior_context(rows: list[dict[str, Any]], feature_season: str) -> list[dict[str, Any]]:
    """Attach an explicit prior-feature season field to each player row."""
    contextual_rows = []
    for row in rows:
        contextual_row = dict(row)
        contextual_row["feature_season"] = feature_season
        contextual_rows.append(contextual_row)
    return contextual_rows


def join_pairs_to_prior_players(
    pair_rows: list[dict[str, Any]],
    prior_rows_by_id: dict[str, list[dict[str, Any]]],
    target_season: str,
    feature_season: str,
) -> list[dict[str, Any]]:
    """Join each canonical pair independently to prior-player rows by stable PLAYER_ID.

    Does not use pair shared minutes/possessions/ratings/PLUS_MINUS as join keys
    or prior-player features; those remain in the pair row only for diagnostic use.
    """
    joined = []
    for row in pair_rows:
        pair_key = row.get("pair_key")
        if pair_key is None:
            continue
        player_1_id, player_2_id = pair_key
        player_1_rows = prior_rows_by_id.get(player_1_id, [])
        player_2_rows = prior_rows_by_id.get(player_2_id, [])
        joined.append(
            {
                "pair_key": pair_key,
                "player_1_id": player_1_id,
                "player_2_id": player_2_id,
                "player_1_prior_rows": player_1_rows,
                "player_2_prior_rows": player_2_rows,
                "player_1_matched": len(player_1_rows) > 0,
                "player_2_matched": len(player_2_rows) > 0,
                "target_season": target_season,
                "feature_season": feature_season,
                "shared_min": row.get("MIN"),
                "shared_poss": row.get("POSS"),
            }
        )
    return joined


def summarize_player_level_coverage(
    pair_rows: list[dict[str, Any]], prior_rows_by_id: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Report unique-player coverage across all players appearing in the pair rows."""
    unique_ids: set[str] = set()
    id_to_name: dict[str, str] = {}
    for row in pair_rows:
        pair_key = row.get("pair_key")
        if pair_key is None:
            continue
        unique_ids.update(pair_key)
        # Names must be zipped against the raw GROUP_ID token order, which matches
        # GROUP_NAME order. The canonical (sorted) pair_key order does not.
        group_id = row.get("GROUP_ID") or ""
        raw_ids = [token for token in group_id.strip("-").split("-") if token]
        # Split only on the " - " / " – " delimiter (with surrounding spaces) so
        # in-name hyphens (e.g. "Jackson-Davis") are not mistaken for the pair separator.
        group_name = row.get("GROUP_NAME") or ""
        normalized_name = group_name.replace(" – ", " - ")
        name_parts = [part.strip() for part in normalized_name.split(" - ") if part.strip()]
        for player_id, name in zip(raw_ids, name_parts):
            id_to_name.setdefault(player_id, name)

    matched_ids = {player_id for player_id in unique_ids if prior_rows_by_id.get(player_id)}
    missing_ids = unique_ids - matched_ids
    total = len(unique_ids)
    return {
        "unique_player_ids": total,
        "unique_ids_with_prior_record": len(matched_ids),
        "unique_ids_without_prior_record": len(missing_ids),
        "player_level_coverage_rate": (len(matched_ids) / total) if total else 0.0,
        "missing_player_ids": sorted(missing_ids),
        "missing_player_names": {
            player_id: id_to_name.get(player_id, "unknown") for player_id in sorted(missing_ids)
        },
    }


def summarize_pair_level_coverage(joined_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Report pair-level prior-history coverage classifications."""
    total = len(joined_rows)
    both = sum(1 for row in joined_rows if row["player_1_matched"] and row["player_2_matched"])
    only_1 = sum(1 for row in joined_rows if row["player_1_matched"] and not row["player_2_matched"])
    only_2 = sum(1 for row in joined_rows if row["player_2_matched"] and not row["player_1_matched"])
    neither = sum(1 for row in joined_rows if not row["player_1_matched"] and not row["player_2_matched"])

    missing_player_counts: Counter[str] = Counter()
    for row in joined_rows:
        if not row["player_1_matched"]:
            missing_player_counts[row["player_1_id"]] += 1
        if not row["player_2_matched"]:
            missing_player_counts[row["player_2_id"]] += 1

    return {
        "total_pair_rows": total,
        "both_players_matched": both,
        "only_player_1_matched": only_1,
        "only_player_2_matched": only_2,
        "neither_player_matched": neither,
        "complete_prior_pair_rate": (both / total) if total else 0.0,
        "one_or_more_missing_pair_rate": ((total - both) / total) if total else 0.0,
        "missing_coverage_concentration": dict(missing_player_counts),
    }


def summarize_exposure_weighted_coverage(joined_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe how 2024-25 shared-minute/possession exposure distributes across coverage groups.

    These are diagnostic, overlapping pair-row sums, not unique team totals and not features.
    """
    complete_min = 0.0
    incomplete_min = 0.0
    complete_poss = 0.0
    incomplete_poss = 0.0
    total_min = 0.0
    total_poss = 0.0

    for row in joined_rows:
        shared_min = _numeric(row.get("shared_min")) or 0.0
        shared_poss = _numeric(row.get("shared_poss")) or 0.0
        total_min += shared_min
        total_poss += shared_poss
        if row["player_1_matched"] and row["player_2_matched"]:
            complete_min += shared_min
            complete_poss += shared_poss
        else:
            incomplete_min += shared_min
            incomplete_poss += shared_poss

    return {
        "note": (
            "Pair rows overlap per player; these are summed diagnostic exposures, "
            "not estimates of unique team minutes or possessions, and are not used as features."
        ),
        "complete_prior_share_of_minutes": (complete_min / total_min) if total_min else 0.0,
        "incomplete_prior_share_of_minutes": (incomplete_min / total_min) if total_min else 0.0,
        "complete_prior_share_of_possessions": (complete_poss / total_poss) if total_poss else 0.0,
        "incomplete_prior_share_of_possessions": (incomplete_poss / total_poss) if total_poss else 0.0,
        "total_summed_minutes": total_min,
        "total_summed_possessions": total_poss,
    }
