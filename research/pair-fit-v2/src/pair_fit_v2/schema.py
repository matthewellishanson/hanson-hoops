from __future__ import annotations

from typing import Any


def canonical_pair_key(player_a: Any, player_b: Any) -> tuple[Any, Any]:
    """Return an unordered pair key that prevents A+B and B+A from splitting one record."""
    left, right = sorted((str(player_a), str(player_b)))
    return (left, right)


def validate_pair_rows(rows: list[dict[str, Any]]) -> dict[str, int | list[str]]:
    """Basic validation for pair-level rows. This is intentionally conservative."""
    valid_rows = 0
    duplicate_rows = 0
    invalid_rows = 0
    unique_pairs: set[tuple[str, str]] = set()

    seen = set()
    for row in rows:
        pair_key = canonical_pair_key(row.get("PLAYER_ID_A", 0), row.get("PLAYER_ID_B", 0))
        if row.get("GROUP_ID") in seen:
            duplicate_rows += 1
            continue
        if row.get("MIN", 0) <= 0 or row.get("GP", 0) <= 0:
            invalid_rows += 1
            continue
        if row.get("ORTG") is None or row.get("DRTG") is None:
            invalid_rows += 1
            continue
        seen.add(row.get("GROUP_ID"))
        unique_pairs.add(pair_key)
        valid_rows += 1

    return {
        "valid_rows": valid_rows,
        "duplicate_rows": duplicate_rows,
        "invalid_rows": invalid_rows,
        "unique_pairs": len(unique_pairs),
    }


def summarize_pair_feasibility(pair_rows: list[dict[str, Any]], prior_features: dict[str, dict[str, Any]]) -> dict[str, float | int]:
    """Summarize how many pair rows have complete prior-player coverage."""
    complete_prior_rows = 0
    missing_prior_rows = 0

    for row in pair_rows:
        pair_key = row.get("pair_key")
        if not pair_key:
            continue
        left, right = pair_key
        lhs_ok = left in prior_features and prior_features[left].get("player_id") is not None
        rhs_ok = right in prior_features and prior_features[right].get("player_id") is not None
        if lhs_ok and rhs_ok:
            complete_prior_rows += 1
        else:
            missing_prior_rows += 1

    total = len(pair_rows)
    rate = (complete_prior_rows / total) if total else 0.0
    return {
        "pair_rows": total,
        "complete_prior_rows": complete_prior_rows,
        "missing_prior_rows": missing_prior_rows,
        "complete_prior_rate": rate,
    }
