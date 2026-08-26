"""Cache-only Phase 1F target-semantics and preliminary reliability audit.

This module has no transport function and performs no network I/O.  It accepts
already-validated NBA Stats payloads, or loads the immutable Phase 1C--1E
caches through their existing replay contracts.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pair_fit_v2.lineup_audit import extract_result_set, result_set_rows
from pair_fit_v2.phase1c_manifest import read_json, verify_asset_cache
from pair_fit_v2.phase1d_exhaustiveness import CHARLOTTE_ID, _strict_pair_key
from pair_fit_v2.phase1e_cli import load_phase1e_context
from pair_fit_v2.phase1e_recovery import replay_phase1e_recovery


PHASE1F_VERSION = "phase1f.target-semantics.v1"
STANDARD_FIELDS = ("OFF_RATING", "DEF_RATING", "NET_RATING")
ESTIMATED_FIELDS = ("E_OFF_RATING", "E_DEF_RATING", "E_NET_RATING")
ALL_RATING_FIELDS = STANDARD_FIELDS + ESTIMATED_FIELDS
THRESHOLDS = (1, 5, 10, 25, 50, 100, 200, 300)
TOTAL_POSSESSION_BANDS = (
    (0, 9),
    (10, 24),
    (25, 49),
    (50, 99),
    (100, 199),
    (200, 499),
    (500, 999),
    (1000, None),
)
MIN_WINDOW_POSSESSION_BANDS = (
    (0, 4),
    (5, 9),
    (10, 24),
    (25, 49),
    (50, 99),
    (100, 199),
    (200, 299),
    (300, None),
)


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _lineup_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return result_set_rows(extract_result_set(dict(payload), "Lineups"))


def _pair_index(payload: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _lineup_rows(payload):
        key = _strict_pair_key(row.get("GROUP_ID"))
        if key is None:
            continue
        if key in result:
            raise ValueError(f"Duplicate canonical pair key: {key}")
        result[key] = row
    return result


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _distribution(values: Sequence[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "minimum": min(values) if values else None,
        "q1": _percentile(values, 0.25),
        "median": _percentile(values, 0.5),
        "q3": _percentile(values, 0.75),
        "p90": _percentile(values, 0.9),
        "p95": _percentile(values, 0.95),
        "p99": _percentile(values, 0.99),
        "maximum": max(values) if values else None,
        "total": sum(values),
    }


def _error_metrics(errors: Sequence[float]) -> dict[str, Any]:
    absolute = [abs(value) for value in errors]
    count = len(absolute)
    return {
        "comparable_rows": count,
        "mean_absolute_error": statistics.mean(absolute) if absolute else None,
        "median_absolute_error": statistics.median(absolute) if absolute else None,
        "maximum_absolute_error": max(absolute) if absolute else None,
        "within_0_1_count": sum(value <= 0.1 + 1e-12 for value in absolute),
        "within_0_1_pct": 100 * sum(value <= 0.1 + 1e-12 for value in absolute) / count if count else None,
        "within_0_2_count": sum(value <= 0.2 + 1e-12 for value in absolute),
        "within_0_2_pct": 100 * sum(value <= 0.2 + 1e-12 for value in absolute) / count if count else None,
        "within_0_5_count": sum(value <= 0.5 + 1e-12 for value in absolute),
        "within_0_5_pct": 100 * sum(value <= 0.5 + 1e-12 for value in absolute) / count if count else None,
        "over_0_2_count": sum(value > 0.2 + 1e-12 for value in absolute),
    }


def field_availability(
    payloads: Iterable[Mapping[str, Any]], fields: Sequence[str] = ALL_RATING_FIELDS
) -> dict[str, Any]:
    rows = [row for payload in payloads for row in _lineup_rows(payload)]
    result: dict[str, Any] = {"row_count": len(rows), "fields": {}}
    for field in fields:
        numeric = [_numeric(row.get(field)) for row in rows]
        result["fields"][field] = {
            "numeric": sum(value is not None for value in numeric),
            "missing_or_nonnumeric": sum(value is None for value in numeric),
        }
    return result


def rating_identity_audit(
    payloads: Iterable[Mapping[str, Any]], *, estimated: bool = False
) -> dict[str, Any]:
    off, defense, net = ESTIMATED_FIELDS if estimated else STANDARD_FIELDS
    details = []
    for payload in payloads:
        for row in _lineup_rows(payload):
            values = [_numeric(row.get(field)) for field in (off, defense, net)]
            if any(value is None for value in values):
                continue
            difference = values[2] - (values[0] - values[1])  # type: ignore[operator]
            details.append(
                {
                    "pair_ids": _strict_pair_key(row.get("GROUP_ID")),
                    "difference": difference,
                    "absolute_difference": abs(difference),
                }
            )
    errors = [item["difference"] for item in details]
    return {"fields": [off, defense, net], "metrics": _error_metrics(errors), "details": details}


def published_rounding_interval(value: float, decimals: int = 1) -> tuple[float, float]:
    half_unit = 0.5 * 10 ** (-decimals)
    return value - half_unit, value + half_unit


def weighted_rounding_interval(
    weighted_values: Sequence[tuple[float, float]], decimals: int = 1
) -> tuple[float, float] | None:
    positive = [(weight, value) for weight, value in weighted_values if weight > 0]
    total = sum(weight for weight, _ in positive)
    if total <= 0:
        return None
    intervals = [(weight, published_rounding_interval(value, decimals)) for weight, value in positive]
    return (
        sum(weight * interval[0] for weight, interval in intervals) / total,
        sum(weight * interval[1] for weight, interval in intervals) / total,
    )


def intervals_overlap(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return max(first[0], second[0]) <= min(first[1], second[1]) + 1e-12


def rounding_feasibility_classification(
    *,
    field: str,
    aggregate_interval: tuple[float, float],
    full_season_interval: tuple[float, float],
) -> str:
    if intervals_overlap(aggregate_interval, full_season_interval):
        return "explainable_by_published_rounding"
    if field == "OFF_RATING":
        return "not_explainable_by_published_rounding"
    return "indeterminate_due_to_missing_denominator_or_precision"


def recomposition_audit(
    full_payload: Mapping[str, Any],
    early_payload: Mapping[str, Any],
    late_payload: Mapping[str, Any],
    *,
    fields: Sequence[str],
) -> dict[str, Any]:
    full = _pair_index(full_payload)
    early = _pair_index(early_payload)
    late = _pair_index(late_payload)
    by_field: dict[str, Any] = {}
    for field in fields:
        details = []
        for key in sorted(full, key=lambda item: (int(item[0]), int(item[1]))):
            official = _numeric(full[key].get(field))
            early_row = early.get(key)
            late_row = late.get(key)
            early_poss = _numeric(early_row.get("POSS")) if early_row else 0.0
            late_poss = _numeric(late_row.get("POSS")) if late_row else 0.0
            early_rate = _numeric(early_row.get(field)) if early_row else None
            late_rate = _numeric(late_row.get(field)) if late_row else None
            weighted = [
                (poss, rate)
                for poss, rate in ((early_poss, early_rate), (late_poss, late_rate))
                if poss is not None and poss > 0 and rate is not None
            ]
            total_poss = sum(poss for poss, _ in weighted)
            if official is None or total_poss <= 0:
                continue
            recomposed = sum(poss * rate for poss, rate in weighted) / total_poss
            error = recomposed - official
            aggregate_interval = weighted_rounding_interval(weighted)
            full_interval = published_rounding_interval(official)
            rounding_classification = None
            if aggregate_interval is not None:
                rounding_classification = rounding_feasibility_classification(
                    field=field,
                    aggregate_interval=aggregate_interval,
                    full_season_interval=full_interval,
                )
            details.append(
                {
                    "pair_ids": key,
                    "group_name": full[key].get("GROUP_NAME"),
                    "early_possessions": early_poss or 0.0,
                    "late_possessions": late_poss or 0.0,
                    "total_possessions": total_poss,
                    "minimum_window_possessions": min(early_poss or 0.0, late_poss or 0.0),
                    "early_rate": early_rate,
                    "late_rate": late_rate,
                    "recomposed_rate": recomposed,
                    "full_season_rate": official,
                    "signed_error": error,
                    "absolute_error": abs(error),
                    "aggregate_rounding_interval": aggregate_interval,
                    "full_season_rounding_interval": full_interval,
                    "rounding_classification": rounding_classification,
                }
            )
        errors = [item["signed_error"] for item in details]
        discrepancies = [item for item in details if item["absolute_error"] > 0.2 + 1e-12]
        by_field[field] = {
            "metrics": _error_metrics(errors),
            "details": details,
            "discrepancies_over_0_2": discrepancies,
            "rounding_classification_counts": _counts(
                item["rounding_classification"] for item in discrepancies
            ),
            "errors_by_total_possessions": error_band_summary(details, TOTAL_POSSESSION_BANDS, "total_possessions"),
            "errors_by_minimum_window_possessions": error_band_summary(
                details, MIN_WINDOW_POSSESSION_BANDS, "minimum_window_possessions"
            ),
        }
    return by_field


def _counts(values: Iterable[Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value)
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))


def _band_label(lower: int, upper: int | None) -> str:
    return f"{lower}+" if upper is None else f"{lower}-{upper}"


def error_band_summary(
    details: Sequence[Mapping[str, Any]],
    bands: Sequence[tuple[int, int | None]],
    value_field: str,
) -> list[dict[str, Any]]:
    result = []
    for lower, upper in bands:
        selected = [
            item
            for item in details
            if _numeric(item.get(value_field)) is not None
            and _numeric(item.get(value_field)) >= lower  # type: ignore[operator]
            and (upper is None or _numeric(item.get(value_field)) <= upper)  # type: ignore[operator]
        ]
        metrics = _error_metrics([float(item["signed_error"]) for item in selected])
        result.append({"band": _band_label(lower, upper), **metrics})
    return result


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _pearson(first: Sequence[float], second: Sequence[float]) -> float | None:
    if len(first) < 2 or len(first) != len(second):
        return None
    mean_first, mean_second = _mean(first), _mean(second)
    centered_first = [value - mean_first for value in first]
    centered_second = [value - mean_second for value in second]
    denominator = math.sqrt(
        sum(value * value for value in centered_first)
        * sum(value * value for value in centered_second)
    )
    if denominator <= 0:
        return None
    return sum(a * b for a, b in zip(centered_first, centered_second)) / denominator


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_rank = (index + 1 + end) / 2
        for position in range(index, end):
            ranks[ordered[position][0]] = average_rank
        index = end
    return ranks


def _spearman(first: Sequence[float], second: Sequence[float]) -> float | None:
    return _pearson(_average_ranks(first), _average_ranks(second))


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def stability_audit(
    early_payload: Mapping[str, Any],
    late_payload: Mapping[str, Any],
    *,
    thresholds: Sequence[int] = THRESHOLDS,
    fields: Sequence[str] = ALL_RATING_FIELDS,
) -> dict[str, Any]:
    early = _pair_index(early_payload)
    late = _pair_index(late_payload)
    both = sorted(set(early) & set(late), key=lambda item: (int(item[0]), int(item[1])))
    rows = []
    for threshold in thresholds:
        qualifying = [
            key
            for key in both
            if (_numeric(early[key].get("POSS")) or -1) >= threshold
            and (_numeric(late[key].get("POSS")) or -1) >= threshold
        ]
        for field in fields:
            comparable = [
                (
                    _numeric(early[key].get(field)),
                    _numeric(late[key].get(field)),
                )
                for key in qualifying
            ]
            comparable = [(a, b) for a, b in comparable if a is not None and b is not None]
            first = [a for a, _ in comparable]
            second = [b for _, b in comparable]
            differences = [b - a for a, b in comparable]
            count = len(comparable)
            rows.append(
                {
                    "threshold_possessions_per_window": threshold,
                    "field": field,
                    "qualifying_pair_count": count,
                    "share_of_both_window_pairs": count / len(both) if both else None,
                    "pearson_correlation": _pearson(first, second),
                    "spearman_correlation": _spearman(first, second),
                    "mean_absolute_difference": statistics.mean(abs(value) for value in differences) if differences else None,
                    "root_mean_square_difference": math.sqrt(statistics.mean(value * value for value in differences)) if differences else None,
                    "median_absolute_difference": statistics.median(abs(value) for value in differences) if differences else None,
                    "sign_agreement": (
                        sum(_sign(a) == _sign(b) for a, b in comparable) / count
                        if count and "NET_RATING" in field
                        else None
                    ),
                    "early_variance": statistics.pvariance(first) if count >= 2 else None,
                    "late_variance": statistics.pvariance(second) if count >= 2 else None,
                    "correlation_undefined_reason": (
                        "fewer_than_two_rows"
                        if count < 2
                        else "zero_variance"
                        if _pearson(first, second) is None
                        else None
                    ),
                    "sample_too_small_to_interpret_responsibly": count < 10,
                }
            )
    return {"both_window_pair_count": len(both), "rows": rows}


def league_exposure_audit(
    advanced_payloads: Mapping[str, Mapping[str, Any]],
    *,
    thresholds: Sequence[int] = THRESHOLDS,
) -> dict[str, Any]:
    rows = [
        {**row, "_TEAM_ID": team_id}
        for team_id, payload in advanced_payloads.items()
        for row in _lineup_rows(payload)
    ]
    valid_poss = [_numeric(row.get("POSS")) for row in rows]
    possessions = [value for value in valid_poss if value is not None]
    total_possessions = sum(possessions)
    threshold_rows = []
    for threshold in thresholds:
        retained = [row for row in rows if (_numeric(row.get("POSS")) or -1) >= threshold]
        retained_possessions = sum(_numeric(row.get("POSS")) or 0 for row in retained)
        nets = [_numeric(row.get("NET_RATING")) for row in retained]
        numeric_nets = [value for value in nets if value is not None]
        threshold_rows.append(
            {
                "threshold_possessions": threshold,
                "rows_retained": len(retained),
                "rows_excluded": len(rows) - len(retained),
                "rows_retained_share": len(retained) / len(rows) if rows else None,
                "rows_excluded_share": (len(rows) - len(retained)) / len(rows) if rows else None,
                "possessions_retained": retained_possessions,
                "possession_share_retained": retained_possessions / total_possessions if total_possessions else None,
                "net_rating_variance": statistics.pvariance(numeric_nets) if len(numeric_nets) >= 2 else None,
                "absolute_net_at_least_50_count": sum(abs(value) >= 50 for value in numeric_nets),
                "absolute_net_at_least_50_share": sum(abs(value) >= 50 for value in numeric_nets) / len(numeric_nets) if numeric_nets else None,
            }
        )
    band_rows = []
    for lower, upper in TOTAL_POSSESSION_BANDS:
        selected = [
            row
            for row in rows
            if (_numeric(row.get("POSS")) is not None)
            and _numeric(row.get("POSS")) >= lower  # type: ignore[operator]
            and (upper is None or _numeric(row.get("POSS")) <= upper)  # type: ignore[operator]
        ]
        nets = [_numeric(row.get("NET_RATING")) for row in selected]
        numeric_nets = [value for value in nets if value is not None]
        band_rows.append(
            {
                "band": _band_label(lower, upper),
                "row_count": len(selected),
                "possession_total": sum(_numeric(row.get("POSS")) or 0 for row in selected),
                "net_rating_variance": statistics.pvariance(numeric_nets) if len(numeric_nets) >= 2 else None,
                "absolute_net_at_least_25_count": sum(abs(value) >= 25 for value in numeric_nets),
                "absolute_net_at_least_50_count": sum(abs(value) >= 50 for value in numeric_nets),
                "absolute_net_at_least_100_count": sum(abs(value) >= 100 for value in numeric_nets),
                "absolute_net_at_least_50_share": sum(abs(value) >= 50 for value in numeric_nets) / len(numeric_nets) if numeric_nets else None,
            }
        )
    team_counts = {
        team_id: len(_lineup_rows(payload)) for team_id, payload in sorted(advanced_payloads.items())
    }
    return {
        "row_count": len(rows),
        "possession_distribution": _distribution(possessions),
        "zero_or_negative_possession_rows": sum(value is not None and value <= 0 for value in valid_poss),
        "missing_or_nonnumeric_possession_rows": sum(value is None for value in valid_poss),
        "thresholds": threshold_rows,
        "bands": band_rows,
        "team_row_counts": team_counts,
    }


def omission_sensitivity(
    full_payload: Mapping[str, Any],
    recovered_only_pairs: Sequence[Mapping[str, Any]],
    union_pairs: Sequence[Mapping[str, Any]],
    *,
    thresholds: Sequence[int] = THRESHOLDS,
) -> list[dict[str, Any]]:
    full = _pair_index(full_payload)
    result = []
    for threshold in thresholds:
        omitted = [
            row
            for row in recovered_only_pairs
            if (_numeric(row.get("advanced_possessions")) or -1) >= threshold
        ]
        union = [
            row
            for row in union_pairs
            if (_numeric(row.get("advanced_possessions")) or -1) >= threshold
        ]
        full_count = sum((_numeric(row.get("POSS")) or -1) >= threshold for row in full.values())
        omitted_possessions = sum(_numeric(row.get("advanced_possessions")) or 0 for row in omitted)
        union_possessions = sum(_numeric(row.get("advanced_possessions")) or 0 for row in union)
        result.append(
            {
                "threshold_possessions": threshold,
                "known_recovered_only_pairs_retained": len(omitted),
                "known_omitted_possessions_retained": omitted_possessions,
                "known_omitted_exposure_share": omitted_possessions / union_possessions if union_possessions else 0.0,
                "full_season_rows_retained": full_count,
                "observed_union_rows_retained": len(union),
                "full_season_contains_all_currently_observed_qualifying_pairs": not omitted,
                "bounded_statement": (
                    "no known omission survives this threshold"
                    if not omitted
                    else "at least one known omission survives this threshold"
                ),
            }
        )
    return result


def opponent_points_diagnostic(
    full_base_payload: Mapping[str, Any], full_advanced_payload: Mapping[str, Any]
) -> dict[str, Any]:
    base = _pair_index(full_base_payload)
    advanced = _pair_index(full_advanced_payload)
    off_errors, defense_errors = [], []
    for key in sorted(set(base) & set(advanced)):
        points = _numeric(base[key].get("PTS"))
        plus_minus = _numeric(base[key].get("PLUS_MINUS"))
        possessions = _numeric(advanced[key].get("POSS"))
        off = _numeric(advanced[key].get("OFF_RATING"))
        defense = _numeric(advanced[key].get("DEF_RATING"))
        if None in (points, plus_minus, possessions) or possessions <= 0:  # type: ignore[operator]
            continue
        opponent_points = points - plus_minus  # type: ignore[operator]
        if off is not None:
            off_errors.append(100 * points / possessions - off)  # type: ignore[operator]
        if defense is not None:
            defense_errors.append(100 * opponent_points / possessions - defense)
    advanced_headers = list(extract_result_set(dict(full_advanced_payload), "Lineups").get("headers", []))
    opponent_possession_fields = [
        field for field in advanced_headers if "POSS" in str(field).upper() and field != "POSS"
    ]
    return {
        "opponent_points_derivation": "Base PTS - Base PLUS_MINUS",
        "offense_from_points_and_returned_possessions": _error_metrics(off_errors),
        "defense_from_opponent_points_and_returned_team_possessions": _error_metrics(defense_errors),
        "advanced_possession_fields": [field for field in advanced_headers if "POSS" in str(field).upper()],
        "separate_opponent_possession_fields": opponent_possession_fields,
        "opponent_possession_denominator_available": bool(opponent_possession_fields),
    }


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze_cached_phase1f(cache_root: Path) -> dict[str, Any]:
    """Run the complete Phase 1F analysis from immutable local caches only."""
    phase1c_manifest = cache_root / "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"
    phase1d_ledger_path = cache_root / "phase1d/diagnostic_ledger.json"
    phase1e_ledger_path = cache_root / "phase1e/recovery_ledger.json"
    protected_paths = (phase1c_manifest, phase1d_ledger_path, phase1e_ledger_path)
    hashes_before = {str(path.relative_to(cache_root)): _file_hash(path) for path in protected_paths}
    context = load_phase1e_context(cache_root)
    replay = replay_phase1e_recovery(
        cache_root,
        phase1c_manifest=context["phase1c"]["manifest"],
        phase1d_ledger=context["phase1d_ledger"],
        full_season_payloads=context["full_payloads"],
        approved_schemas=context["schemas"],
    )
    hashes_after = {str(path.relative_to(cache_root)): _file_hash(path) for path in protected_paths}
    if hashes_before != hashes_after:
        raise ValueError("Immutable Phase 1C--1E artifact changed during cache-only replay")
    baseline = context["phase1c"]["baseline"]
    charlotte = replay["team_audits"].get(CHARLOTTE_ID)
    totals = baseline["totals"]
    if (
        baseline["asset_count"] != 60
        or baseline["status_counts"] != {"verified": 60}
        or totals["base_raw_pair_rows"] != 5297
        or totals["advanced_raw_pair_rows"] != 5297
        or totals["matched_pairs"] != 5297
        or totals["base_only_pairs"] != 0
        or totals["advanced_only_pairs"] != 0
        or baseline["target_eligibility"]["ineligible"] != 8
    ):
        raise ValueError("Phase 1C baseline mismatch")
    if context["phase1d_replay"]["classification"] != "proven_non_exhaustive":
        raise ValueError("Phase 1D baseline mismatch")
    if charlotte is None:
        raise ValueError("Phase 1E baseline mismatch")
    early_reconciliation = charlotte["window_reconciliation"]["early"]
    late_reconciliation = charlotte["window_reconciliation"]["late"]
    phase1e_rate_errors = charlotte["aggregation"]["rate_recomposition"]
    if (
        early_reconciliation["base_rows"] != 163
        or early_reconciliation["advanced_rows"] != 163
        or late_reconciliation["base_rows"] != 177
        or late_reconciliation["advanced_rows"] != 177
        or charlotte["union"]["unique_recovered_pair_keys"] != 257
        or charlotte["union"]["full_season_keys_found_in_union"] != 250
        or charlotte["recovered_only"]["count"] != 7
        or charlotte["recovered_only"]["advanced_possessions_distribution"]["total"] != 23
        or any(
            row["recovered_only_rows_retained"]
            for row in charlotte["threshold_sensitivity"]
            if row["threshold_possessions"] >= 10
        )
        or not charlotte["aggregation"]["additive_totals_reproduced"]
        or phase1e_rate_errors["OFF_RATING"]["maximum_absolute_error"] > 0.1 + 1e-12
        or len(phase1e_rate_errors["DEF_RATING"]["discrepancies_over_0_2"]) != 9
        or len(phase1e_rate_errors["NET_RATING"]["discrepancies_over_0_2"]) != 10
    ):
        raise ValueError("Phase 1E evidence mismatch")
    ledger = read_json(phase1e_ledger_path)
    window_payloads: dict[str, dict[str, Mapping[str, Any]]] = {"early": {}, "late": {}}
    for asset in ledger["assets"]:
        if asset["identity"]["parameters"]["team_id"] != CHARLOTTE_ID or asset["status"] != "verified":
            continue
        window_payloads[asset["window"]][asset["measure"]] = read_json(
            cache_root / asset["cache"]["relative_path"]
        )
    full_charlotte = context["full_payloads"][CHARLOTTE_ID]
    full_payloads_by_team: dict[str, dict[str, Mapping[str, Any]]] = {}
    for asset in context["phase1c"]["manifest"]["raw_assets"]:
        verified = verify_asset_cache(asset, cache_root, context["schemas"])
        parameters = asset["identity"]["parameters"]
        full_payloads_by_team.setdefault(parameters["team_id"], {})[
            parameters["measure_type"]
        ] = verified["payload"]
    if len(full_payloads_by_team) != 30 or any(len(measures) != 2 for measures in full_payloads_by_team.values()):
        raise ValueError("Phase 1C all-team payload replay mismatch")
    full_advanced_by_team = {
        team_id: measures["Advanced"] for team_id, measures in full_payloads_by_team.items()
    }
    standard_recomposition = recomposition_audit(
        full_charlotte["Advanced"],
        window_payloads["early"]["Advanced"],
        window_payloads["late"]["Advanced"],
        fields=STANDARD_FIELDS,
    )
    estimated_recomposition = recomposition_audit(
        full_charlotte["Advanced"],
        window_payloads["early"]["Advanced"],
        window_payloads["late"]["Advanced"],
        fields=ESTIMATED_FIELDS,
    )
    union_pairs = list(charlotte["recovered_only"]["pairs"])
    # Reconstruct the full union exposure records from the Phase 1E threshold source.
    early_adv = _pair_index(window_payloads["early"]["Advanced"])
    late_adv = _pair_index(window_payloads["late"]["Advanced"])
    recovered_only_keys = {tuple(row["pair_ids"]) for row in charlotte["recovered_only"]["pairs"]}
    union_pairs = []
    for key in sorted(set(early_adv) | set(late_adv), key=lambda item: (int(item[0]), int(item[1]))):
        possessions = sum(
            _numeric(index[key].get("POSS")) or 0
            for index in (early_adv, late_adv)
            if key in index
        )
        union_pairs.append({"pair_ids": key, "advanced_possessions": possessions})
    recovered_only = [row for row in union_pairs if tuple(row["pair_ids"]) in recovered_only_keys]
    result = {
        "phase1f_version": PHASE1F_VERSION,
        "immutable_replay": {
            "hashes_before": hashes_before,
            "hashes_after": hashes_after,
            "unchanged": hashes_before == hashes_after,
            "phase1c": {
                "asset_count": baseline["asset_count"],
                "status_counts": baseline["status_counts"],
                "totals": baseline["totals"],
                "target_eligibility": baseline["target_eligibility"],
                "schemas": context["schemas"],
            },
            "phase1d": {
                "classification": context["phase1d_replay"]["classification"],
                "diagnostic_only_keys": context["phase1d_replay"]["comparison"]["diagnostic_only_keys"],
            },
            "phase1e": {
                "classification": replay["classification"],
                "window_reconciliation": charlotte["window_reconciliation"],
                "union": charlotte["union"],
                "recovered_only": charlotte["recovered_only"],
                "aggregation": charlotte["aggregation"],
                "request_identities": [
                    {
                        "asset_id": asset["asset_id"],
                        "identity": asset["identity"],
                        "status": asset["status"],
                        "attempt_count": asset["attempt_count"],
                    }
                    for asset in ledger["assets"]
                ],
            },
        },
        "availability": {
            "charlotte_full": field_availability([full_charlotte["Advanced"]]),
            "charlotte_early": field_availability([window_payloads["early"]["Advanced"]]),
            "charlotte_late": field_availability([window_payloads["late"]["Advanced"]]),
            "phase1c_all_teams": field_availability(full_advanced_by_team.values()),
        },
        "full_season_identity": {
            "standard": rating_identity_audit(full_advanced_by_team.values()),
            "estimated": rating_identity_audit(full_advanced_by_team.values(), estimated=True),
        },
        "standard_recomposition": standard_recomposition,
        "estimated_recomposition": estimated_recomposition,
        "denominator_diagnostic": opponent_points_diagnostic(
            full_charlotte["Base"], full_charlotte["Advanced"]
        ),
        "stability": stability_audit(
            window_payloads["early"]["Advanced"], window_payloads["late"]["Advanced"]
        ),
        "league_exposure": league_exposure_audit(full_advanced_by_team),
        "omission_sensitivity": omission_sensitivity(
            full_charlotte["Advanced"], recovered_only, union_pairs
        ),
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
    result["summary_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return result
