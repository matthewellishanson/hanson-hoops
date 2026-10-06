"""Phase 1E bounded two-window pair-population recovery diagnostics.

The module is research-only. Imports, analysis, and replay are offline. Live
access requires the explicit ``live_acquisition`` flag and uses one sequential
direct ``requests.Session`` call per uncached authorized asset, with no retry.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS
from pair_fit_v2.lineup_audit import extract_result_set, result_set_rows
from pair_fit_v2.phase1b_contract import raw_asset_identity, stable_contract_id
from pair_fit_v2.phase1c_manifest import (
    GROUP_QUANTITY,
    LEAGUE_ID,
    SEASON_TYPE,
    TARGET_SEASON,
    TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
    atomic_write_bytes_new,
    atomic_write_json,
    canonical_json_hash,
    raw_body_hash,
    read_json,
    utc_now,
)
from pair_fit_v2.phase1d_exhaustiveness import (
    CHARLOTTE_ID,
    PHILADELPHIA_ID,
    TEAM_DASH_LINEUPS,
    TEAM_DASH_LINEUPS_URL,
    _expected_query,
    _strict_pair_key,
    validate_diagnostic_payload,
)


PHASE1E_VERSION = "phase1e.window-recovery.v1"
PHASE1E_ASSET_KIND = "phase1e-diagnostic-asset"
MEASURES = ("Base", "Advanced")
TEAM_SEQUENCE = (
    (CHARLOTTE_ID, "Charlotte Hornets"),
    (PHILADELPHIA_ID, "Philadelphia 76ers"),
)
WINDOWS = (
    {
        "window": "early",
        "start_iso": "2024-10-22",
        "end_iso": "2025-01-31",
        "date_from": "10/22/2024",
        "date_to": "01/31/2025",
    },
    {
        "window": "late",
        "start_iso": "2025-02-01",
        "end_iso": "2025-04-13",
        "date_from": "02/01/2025",
        "date_to": "04/13/2025",
    },
)
PHASE1D_PROVING_KEYS = {
    ("203901", "1630163"),
    ("1629006", "1631111"),
    ("1630163", "1630585"),
}
THRESHOLDS = (1, 5, 10, 25, 50, 100)
RATE_FIELDS = ("OFF_RATING", "DEF_RATING", "NET_RATING")

# Totals/counts returned under PerMode=Totals. Percentages, rates, pace, and
# ranks are intentionally excluded. Advanced MIN remains audit-only.
BASE_ADDITIVE_FIELDS = (
    "GP",
    "W",
    "L",
    "MIN",
    "FGM",
    "FGA",
    "FG3M",
    "FG3A",
    "FTM",
    "FTA",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "TOV",
    "STL",
    "BLK",
    "BLKA",
    "PF",
    "PFD",
    "PTS",
    "PLUS_MINUS",
    "SUM_TIME_PLAYED",
)


@dataclass(frozen=True)
class WindowTransportResult:
    status_code: int
    body: bytes
    elapsed_seconds: float


class WindowTransportError(RuntimeError):
    def __init__(self, category: str, detail: str):
        super().__init__(detail)
        self.category = category
        self.detail = detail


def validate_window_contract() -> dict[str, Any]:
    parsed = []
    for window in WINDOWS:
        start_iso = date.fromisoformat(window["start_iso"])
        end_iso = date.fromisoformat(window["end_iso"])
        request_start = datetime.strptime(window["date_from"], "%m/%d/%Y").date()
        request_end = datetime.strptime(window["date_to"], "%m/%d/%Y").date()
        if start_iso != request_start or end_iso != request_end or start_iso > end_iso:
            raise ValueError(f"Ambiguous window representation: {window}")
        parsed.append((start_iso, end_iso))
    if parsed[0][1] + timedelta(days=1) != parsed[1][0]:
        raise ValueError("Phase 1E windows are not contiguous and non-overlapping")
    if parsed[0][0] != date(2024, 10, 22) or parsed[1][1] != date(2025, 4, 13):
        raise ValueError("Phase 1E windows do not cover the authorized season bounds")
    return {
        "valid": True,
        "inclusive": True,
        "non_overlapping": True,
        "contiguous": True,
        "request_format": "MM/DD/YYYY",
        "windows": deepcopy(WINDOWS),
    }


def window_identity(team_id: str, measure: str, window: Mapping[str, str]) -> dict[str, Any]:
    if measure not in MEASURES:
        raise ValueError(f"Unauthorized measure: {measure}")
    validate_window_contract()
    extra = dict(TEAM_DASH_LINEUPS_EXTRA_PARAMETERS)
    extra.update(
        {
            "DateFrom": window["date_from"],
            "DateTo": window["date_to"],
            "LastNGames": "0",
        }
    )
    return raw_asset_identity(
        endpoint=TEAM_DASH_LINEUPS,
        season=TARGET_SEASON,
        team_id=team_id,
        measure_type=measure,
        season_type=SEASON_TYPE,
        league_id=LEAGUE_ID,
        group_quantity=GROUP_QUANTITY,
        extra_parameters=extra,
    )


def build_phase1e_ledger() -> dict[str, Any]:
    assets = []
    sequence = 0
    for team_id, team_name in TEAM_SEQUENCE:
        for window in WINDOWS:
            for measure in MEASURES:
                sequence += 1
                identity = window_identity(team_id, measure, window)
                asset_id = stable_contract_id(PHASE1E_ASSET_KIND, identity)
                safe = asset_id.replace(":", "_")
                relative = f"phase1e/windows/{safe}.json"
                assets.append(
                    {
                        "sequence": sequence,
                        "team_name": team_name,
                        "window": window["window"],
                        "window_start": window["start_iso"],
                        "window_end": window["end_iso"],
                        "measure": measure,
                        "asset_id": asset_id,
                        "identity": identity,
                        "status": "planned",
                        "attempt_count": 0,
                        "attempt": None,
                        "cache": {
                            "relative_path": relative,
                            "metadata_relative_path": relative.replace(".json", ".metadata.json"),
                            "error_body_relative_path": relative.replace(".json", ".error.bin"),
                        },
                    }
                )
    return {
        "phase1e_version": PHASE1E_VERSION,
        "window_contract": validate_window_contract(),
        "authorization": {
            "maximum_live_requests": 8,
            "no_retry": True,
            "sequential_only": True,
            "charlotte_continuation_gate_required": True,
        },
        "assets": assets,
        "team_audits": {},
        "created_at": None,
        "updated_at": None,
    }


def phase1e_ledger_path(cache_root: Path) -> Path:
    return cache_root / "phase1e" / "recovery_ledger.json"


def validate_phase1e_isolation(
    ledger: Mapping[str, Any],
    phase1c_manifest: Mapping[str, Any],
    phase1d_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    ids = [asset["asset_id"] for asset in ledger["assets"]]
    protected_ids = {
        asset["asset_id"]
        for source in (phase1c_manifest, phase1d_ledger)
        for asset in source.get("raw_assets", source.get("assets", []))
    }
    paths = [asset["cache"]["relative_path"] for asset in ledger["assets"]]
    collisions = sorted(set(ids) & protected_ids)
    valid = (
        len(ids) == len(set(ids)) == 8
        and not collisions
        and all(value.startswith(f"{PHASE1E_ASSET_KIND}:") for value in ids)
        and all(path.startswith("phase1e/windows/") for path in paths)
    )
    result = {
        "isolated": valid,
        "asset_count": len(ids),
        "asset_id_collisions": collisions,
        "unique_ids": len(ids) == len(set(ids)),
    }
    if not valid:
        raise ValueError(f"Phase 1E isolation failure: {result}")
    return result


def _validate_ledger(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    if actual.get("phase1e_version") != PHASE1E_VERSION:
        raise ValueError("Phase 1E ledger version mismatch")
    if json.dumps(actual.get("window_contract"), sort_keys=True) != json.dumps(
        expected.get("window_contract"), sort_keys=True
    ):
        raise ValueError("Phase 1E window contract mismatch")
    if actual.get("authorization") != expected.get("authorization"):
        raise ValueError("Phase 1E authorization mismatch")
    actual_assets = actual.get("assets")
    expected_assets = expected["assets"]
    if not isinstance(actual_assets, list) or len(actual_assets) != 8:
        raise ValueError("Phase 1E ledger must contain eight assets")
    for actual_asset, expected_asset in zip(actual_assets, expected_assets):
        for field in (
            "sequence",
            "team_name",
            "window",
            "window_start",
            "window_end",
            "measure",
            "asset_id",
            "identity",
            "cache",
        ):
            if actual_asset.get(field) != expected_asset.get(field):
                raise ValueError(f"Phase 1E ledger asset mismatch: {field}")


def load_or_create_phase1e_ledger(cache_root: Path) -> dict[str, Any]:
    path = phase1e_ledger_path(cache_root)
    expected = build_phase1e_ledger()
    if path.is_file():
        actual = read_json(path)
        _validate_ledger(actual, expected)
        return actual
    now = utc_now()
    expected["created_at"] = now
    expected["updated_at"] = now
    atomic_write_json(path, expected)
    return expected


def save_phase1e_ledger(cache_root: Path, ledger: dict[str, Any]) -> None:
    _validate_ledger(ledger, build_phase1e_ledger())
    ledger["updated_at"] = utc_now()
    atomic_write_json(phase1e_ledger_path(cache_root), ledger)


def _parse_response_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            continue
    return None


def validate_window_payload(
    payload: Mapping[str, Any],
    identity: Mapping[str, Any],
    approved_schema: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    parameters = payload.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ValueError("Response lacks a parameters identity envelope")
    expected = _expected_query(identity)
    for field in ("DateFrom", "DateTo"):
        returned_date = _parse_response_date(parameters.get(field))
        requested_date = _parse_response_date(expected[field])
        if returned_date is None or returned_date != requested_date:
            raise ValueError(
                f"Ambiguous or ignored {field}: expected={expected[field]!r}, actual={parameters.get(field)!r}"
            )
    # The server may echo an equivalent date in ISO form. Semantic equality was
    # established above; align only those two echo fields for the shared strict
    # identity validator while preserving the requested identity in provenance.
    echo_aligned_identity = deepcopy(identity)
    echo_aligned_identity["parameters"]["DateFrom"] = parameters["DateFrom"]
    echo_aligned_identity["parameters"]["DateTo"] = parameters["DateTo"]
    validation = validate_diagnostic_payload(
        payload, echo_aligned_identity, approved_schema
    )
    row_count = validation["row_counts"].get("Lineups")
    if row_count == 250:
        raise ValueError("Child-window response hit the prohibited exact-250 boundary")
    return validation


def direct_window_transport(
    identity: Mapping[str, Any], timeout_seconds: int = 30
) -> WindowTransportResult:
    if timeout_seconds != 30:
        raise ValueError("Phase 1E requires the approved 30-second timeout")
    if identity.get("endpoint") != TEAM_DASH_LINEUPS:
        raise ValueError("Phase 1E supports only TeamDashLineups")
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    started = time.perf_counter()
    try:
        response = session.get(
            TEAM_DASH_LINEUPS_URL,
            params=_expected_query(identity),
            timeout=timeout_seconds,
        )
        return WindowTransportResult(
            status_code=response.status_code,
            body=response.content,
            elapsed_seconds=time.perf_counter() - started,
        )
    except requests.Timeout as exc:
        raise WindowTransportError("timeout", str(exc)) from exc
    except requests.exceptions.SSLError as exc:
        raise WindowTransportError("tls_failure", str(exc)) from exc
    except requests.ConnectionError as exc:
        raise WindowTransportError("connection_or_dns_failure", str(exc)) from exc
    except requests.RequestException as exc:
        raise WindowTransportError("request_failure", str(exc)) from exc
    finally:
        session.close()


def _pair_index(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = result_set_rows(extract_result_set(dict(payload), "Lineups"))
    index: dict[tuple[str, str], dict[str, Any]] = {}
    malformed = []
    same_player = []
    duplicates = []
    for position, row in enumerate(rows):
        group_id = row.get("GROUP_ID")
        tokens = (
            [token for token in group_id.strip("-").split("-") if token]
            if isinstance(group_id, str)
            else []
        )
        if len(tokens) == 2 and tokens[0] == tokens[1]:
            same_player.append({"row_index": position, "group_id": group_id})
            continue
        key = _strict_pair_key(group_id)
        if key is None:
            malformed.append({"row_index": position, "group_id": group_id})
            continue
        if key in index:
            duplicates.append({"row_index": position, "pair_ids": key})
            continue
        index[key] = dict(row)
    return {
        "rows": rows,
        "index": index,
        "malformed": malformed,
        "same_player": same_player,
        "duplicates": duplicates,
    }


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def reconcile_window_measures(
    base_payload: Mapping[str, Any], advanced_payload: Mapping[str, Any]
) -> dict[str, Any]:
    base = _pair_index(base_payload)
    advanced = _pair_index(advanced_payload)
    base_keys = set(base["index"])
    advanced_keys = set(advanced["index"])
    advanced_rows = advanced["rows"]
    poss_values = [_numeric(row.get("POSS")) for row in advanced_rows]
    invalid_poss = [
        {
            "pair_ids": _strict_pair_key(row.get("GROUP_ID")),
            "poss": row.get("POSS"),
        }
        for row, poss in zip(advanced_rows, poss_values)
        if poss is None or poss <= 0
    ]
    return {
        "base_rows": len(base["rows"]),
        "advanced_rows": len(advanced_rows),
        "matched_keys": len(base_keys & advanced_keys),
        "base_only_keys": sorted(base_keys - advanced_keys, key=_key_sort),
        "advanced_only_keys": sorted(advanced_keys - base_keys, key=_key_sort),
        "base_malformed_identifiers": base["malformed"],
        "advanced_malformed_identifiers": advanced["malformed"],
        "base_same_player_identifiers": base["same_player"],
        "advanced_same_player_identifiers": advanced["same_player"],
        "base_duplicate_keys": base["duplicates"],
        "advanced_duplicate_keys": advanced["duplicates"],
        "zero_possessions": sum(poss == 0 for poss in poss_values),
        "negative_possessions": sum(poss is not None and poss < 0 for poss in poss_values),
        "missing_or_nonnumeric_possessions": sum(poss is None for poss in poss_values),
        "possession_ineligible_rows": invalid_poss,
        "target_eligible_rows": sum(poss is not None and poss > 0 for poss in poss_values),
        "full_outer_union_count": len(base_keys | advanced_keys),
    }


def _key_sort(key: tuple[str, str]) -> tuple[int, int]:
    return (int(key[0]), int(key[1]))


def _sum_field(rows: list[Mapping[str, Any]], field: str) -> float | None:
    values = [_numeric(row.get(field)) for row in rows]
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def _window_indexes(
    payloads: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> dict[str, dict[str, dict[tuple[str, str], dict[str, Any]]]]:
    return {
        window: {
            measure: _pair_index(payload)["index"]
            for measure, payload in measures.items()
        }
        for window, measures in payloads.items()
    }


def _error_summary(errors: list[dict[str, Any]]) -> dict[str, Any]:
    absolute = [abs(item["error"]) for item in errors]
    return {
        "comparable_rows": len(absolute),
        "mean_absolute_error": statistics.mean(absolute) if absolute else None,
        "median_absolute_error": statistics.median(absolute) if absolute else None,
        "maximum_absolute_error": max(absolute) if absolute else None,
        "within_0_1_count": sum(value <= 0.1 + 1e-12 for value in absolute),
        "within_0_1_pct": 100 * sum(value <= 0.1 + 1e-12 for value in absolute) / len(absolute) if absolute else None,
        "within_0_2_count": sum(value <= 0.2 + 1e-12 for value in absolute),
        "within_0_2_pct": 100 * sum(value <= 0.2 + 1e-12 for value in absolute) / len(absolute) if absolute else None,
        "discrepancies_over_0_2": [item for item in errors if abs(item["error"]) > 0.2 + 1e-12],
    }


def audit_additive_reconstruction(
    full_base_payload: Mapping[str, Any],
    full_advanced_payload: Mapping[str, Any],
    window_payloads: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    full_base = _pair_index(full_base_payload)["index"]
    full_advanced = _pair_index(full_advanced_payload)["index"]
    windows = _window_indexes(window_payloads)
    full_keys = set(full_base) | set(full_advanced)
    field_discrepancies = []
    comparable_by_field: Counter[str] = Counter()
    for key in sorted(full_keys, key=_key_sort):
        for field in BASE_ADDITIVE_FIELDS:
            official = _numeric(full_base.get(key, {}).get(field))
            rows = [windows[name]["Base"][key] for name in ("early", "late") if key in windows[name]["Base"]]
            reconstructed = _sum_field(rows, field) if rows else None
            if official is None or reconstructed is None:
                continue
            comparable_by_field[field] += 1
            tolerance = 0.000002 if field == "MIN" else 0.000001
            if abs(reconstructed - official) > tolerance:
                field_discrepancies.append(
                    {
                        "pair_ids": key,
                        "field": field,
                        "official": official,
                        "reconstructed": reconstructed,
                        "difference": reconstructed - official,
                    }
                )
        official_poss = _numeric(full_advanced.get(key, {}).get("POSS"))
        advanced_rows = [
            windows[name]["Advanced"][key]
            for name in ("early", "late")
            if key in windows[name]["Advanced"]
        ]
        reconstructed_poss = _sum_field(advanced_rows, "POSS") if advanced_rows else None
        if official_poss is not None and reconstructed_poss is not None:
            comparable_by_field["POSS"] += 1
            if abs(reconstructed_poss - official_poss) > 0.000001:
                field_discrepancies.append(
                    {
                        "pair_ids": key,
                        "field": "POSS",
                        "official": official_poss,
                        "reconstructed": reconstructed_poss,
                        "difference": reconstructed_poss - official_poss,
                    }
                )

    rate_summaries = {}
    all_rate_errors = []
    for field in RATE_FIELDS:
        errors = []
        for key in sorted(set(full_advanced), key=_key_sort):
            official = _numeric(full_advanced[key].get(field))
            weighted = []
            for name in ("early", "late"):
                row = windows[name]["Advanced"].get(key)
                if row is None:
                    continue
                poss = _numeric(row.get("POSS"))
                rate = _numeric(row.get(field))
                if poss is not None and poss > 0 and rate is not None:
                    weighted.append((poss, rate))
            total_poss = sum(poss for poss, _ in weighted)
            if official is None or total_poss <= 0:
                continue
            recomposed = sum(poss * rate for poss, rate in weighted) / total_poss
            item = {
                "pair_ids": key,
                "field": field,
                "official": official,
                "recomposed": recomposed,
                "error": recomposed - official,
                "window_possessions": total_poss,
            }
            errors.append(item)
            all_rate_errors.append(item)
        rate_summaries[field] = _error_summary(errors)

    derived_errors = {field: [] for field in RATE_FIELDS}
    for key in sorted(set(full_base) & set(full_advanced), key=_key_sort):
        points = _numeric(full_base[key].get("PTS"))
        plus_minus = _numeric(full_base[key].get("PLUS_MINUS"))
        poss = _numeric(full_advanced[key].get("POSS"))
        if points is None or plus_minus is None or poss is None or poss <= 0:
            continue
        derived = {
            "OFF_RATING": 100 * points / poss,
            "DEF_RATING": 100 * (points - plus_minus) / poss,
            "NET_RATING": 100 * plus_minus / poss,
        }
        for field, value in derived.items():
            official = _numeric(full_advanced[key].get(field))
            if official is not None:
                derived_errors[field].append(
                    {
                        "pair_ids": key,
                        "field": field,
                        "official": official,
                        "derived": value,
                        "error": value - official,
                    }
                )
    derived_summaries = {field: _error_summary(errors) for field, errors in derived_errors.items()}
    derived_max = max(
        (
            summary["maximum_absolute_error"]
            for summary in derived_summaries.values()
            if summary["maximum_absolute_error"] is not None
        ),
        default=None,
    )
    if derived_max is None:
        derived_classification = "unresolved"
    elif derived_max <= 0.2 + 1e-12:
        derived_classification = "validated"
    elif all(
        summary["within_0_2_pct"] is not None and summary["within_0_2_pct"] >= 95
        for summary in derived_summaries.values()
    ):
        derived_classification = "approximate"
    else:
        derived_classification = "unsupported"

    rate_max = max(
        (
            summary["maximum_absolute_error"]
            for summary in rate_summaries.values()
            if summary["maximum_absolute_error"] is not None
        ),
        default=None,
    )
    return {
        "base_additive_fields": list(BASE_ADDITIVE_FIELDS),
        "advanced_additive_fields": ["POSS"],
        "comparable_by_field": dict(sorted(comparable_by_field.items())),
        "additive_discrepancy_count": len(field_discrepancies),
        "additive_discrepancies": field_discrepancies,
        "additive_totals_reproduced": not field_discrepancies,
        "rate_recomposition": rate_summaries,
        "rate_recomposition_max_absolute_error": rate_max,
        "rate_recomposition_within_0_2_every_row": rate_max is not None and rate_max <= 0.2 + 1e-12,
        "base_points_plus_minus_derived_ratings": {
            "classification": derived_classification,
            "summaries": derived_summaries,
        },
        "zero_possession_rows_preserved_and_excluded_only_from_rate_arithmetic": True,
    }


def _quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"minimum": None, "q1": None, "median": None, "q3": None, "maximum": None, "total": 0}
    ordered = sorted(values)
    quartiles = statistics.quantiles(ordered, n=4, method="inclusive") if len(ordered) > 1 else [ordered[0]] * 3
    return {
        "minimum": ordered[0],
        "q1": quartiles[0],
        "median": statistics.median(ordered),
        "q3": quartiles[2],
        "maximum": ordered[-1],
        "total": sum(ordered),
    }


def _aggregate_pair(
    key: tuple[str, str],
    windows: Mapping[str, Mapping[str, Mapping[tuple[str, str], Mapping[str, Any]]]],
    ratings_validated: bool,
) -> dict[str, Any]:
    base_rows = [windows[name]["Base"][key] for name in ("early", "late") if key in windows[name]["Base"]]
    advanced_rows = [
        windows[name]["Advanced"][key]
        for name in ("early", "late")
        if key in windows[name]["Advanced"]
    ]
    name = next((row.get("GROUP_NAME") for row in base_rows + advanced_rows if row.get("GROUP_NAME")), None)
    poss = _sum_field(advanced_rows, "POSS")
    ratings = None
    if ratings_validated and poss is not None and poss > 0:
        ratings = {}
        for field in RATE_FIELDS:
            weighted = [
                (_numeric(row.get("POSS")), _numeric(row.get(field))) for row in advanced_rows
            ]
            usable = [(p, r) for p, r in weighted if p is not None and p > 0 and r is not None]
            ratings[field] = sum(p * r for p, r in usable) / sum(p for p, _ in usable) if usable else None
    return {
        "pair_ids": key,
        "group_name": name,
        "windows_present": [
            name
            for name in ("early", "late")
            if key in windows[name]["Base"] or key in windows[name]["Advanced"]
        ],
        "games": _sum_field(base_rows, "GP"),
        "base_minutes": _sum_field(base_rows, "MIN"),
        "advanced_possessions": poss,
        "reconstructed_ratings": ratings,
    }


def threshold_sensitivity(
    recovered: list[dict[str, Any]],
    recovered_only: list[dict[str, Any]],
    full_advanced_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    full_index = _pair_index(full_advanced_payload)["index"]
    result = []
    for threshold in THRESHOLDS:
        recovered_retained = [row for row in recovered if (_numeric(row.get("advanced_possessions")) or -1) >= threshold]
        omitted_retained = [row for row in recovered_only if (_numeric(row.get("advanced_possessions")) or -1) >= threshold]
        full_retained = [row for row in full_index.values() if (_numeric(row.get("POSS")) or -1) >= threshold]
        recovered_poss = sum(_numeric(row.get("advanced_possessions")) or 0 for row in recovered_retained)
        omitted_poss = sum(_numeric(row.get("advanced_possessions")) or 0 for row in omitted_retained)
        result.append(
            {
                "threshold_possessions": threshold,
                "recovered_union_rows_retained": len(recovered_retained),
                "recovered_only_rows_retained": len(omitted_retained),
                "full_season_rows_retained": len(full_retained),
                "known_omission_remains_model_eligible": bool(omitted_retained),
                "omitted_possession_share_of_retained_union": omitted_poss / recovered_poss if recovered_poss else 0.0,
                "recovered_union_possessions": recovered_poss,
                "recovered_only_possessions": omitted_poss,
            }
        )
    return result


def audit_team_recovery(
    team_id: str,
    full_base_payload: Mapping[str, Any],
    full_advanced_payload: Mapping[str, Any],
    window_payloads: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    reconciliations = {
        window: reconcile_window_measures(measures["Base"], measures["Advanced"])
        for window, measures in window_payloads.items()
    }
    indexes = _window_indexes(window_payloads)
    early_keys = set(indexes["early"]["Base"]) | set(indexes["early"]["Advanced"])
    late_keys = set(indexes["late"]["Base"]) | set(indexes["late"]["Advanced"])
    union_keys = early_keys | late_keys
    full_base_keys = set(_pair_index(full_base_payload)["index"])
    full_advanced_keys = set(_pair_index(full_advanced_payload)["index"])
    full_keys = full_base_keys | full_advanced_keys
    aggregation = audit_additive_reconstruction(
        full_base_payload, full_advanced_payload, window_payloads
    )
    ratings_validated = aggregation["rate_recomposition_within_0_2_every_row"]
    recovered_rows = [
        _aggregate_pair(key, indexes, ratings_validated)
        for key in sorted(union_keys, key=_key_sort)
    ]
    recovered_only_keys = union_keys - full_keys
    recovered_only = [row for row in recovered_rows if tuple(row["pair_ids"]) in recovered_only_keys]
    structural = all(
        not reconciliation["base_only_keys"]
        and not reconciliation["advanced_only_keys"]
        and not reconciliation["base_malformed_identifiers"]
        and not reconciliation["advanced_malformed_identifiers"]
        and not reconciliation["base_same_player_identifiers"]
        and not reconciliation["advanced_same_player_identifiers"]
        and not reconciliation["base_duplicate_keys"]
        and not reconciliation["advanced_duplicate_keys"]
        for reconciliation in reconciliations.values()
    )
    proving_present = sorted(PHASE1D_PROVING_KEYS & union_keys, key=_key_sort)
    child_below_boundary = all(
        reconciliation["base_rows"] < 250 and reconciliation["advanced_rows"] < 250
        for reconciliation in reconciliations.values()
    )
    gate_checks = {
        "all_four_responses_validated": True,
        "both_child_windows_below_250": child_below_boundary,
        "union_contains_every_full_season_key": not (full_keys - union_keys),
        "union_includes_phase1d_proving_keys": (
            team_id != CHARLOTTE_ID or set(proving_present) == PHASE1D_PROVING_KEYS
        ),
        "base_advanced_reconciliation_structurally_sound": structural,
        "additive_totals_and_possessions_reproduce_full_season": aggregation[
            "additive_totals_reproduced"
        ],
        "rate_recomposition_within_0_2_every_positive_possession_row": ratings_validated,
    }
    continuation_passed = all(gate_checks.values())
    minutes = [_numeric(row["base_minutes"]) for row in recovered_only]
    possessions = [_numeric(row["advanced_possessions"]) for row in recovered_only]
    return {
        "team_id": team_id,
        "window_reconciliation": reconciliations,
        "union": {
            "unique_recovered_pair_keys": len(union_keys),
            "full_season_unique_keys": len(full_keys),
            "full_season_keys_found_in_union": len(full_keys & union_keys),
            "full_season_only_keys": sorted(full_keys - union_keys, key=_key_sort),
            "window_union_only_keys": sorted(union_keys - full_keys, key=_key_sort),
            "early_only_pairs": len(early_keys - late_keys),
            "late_only_pairs": len(late_keys - early_keys),
            "both_window_pairs": len(early_keys & late_keys),
            "phase1d_proving_keys_present": proving_present,
            "increase_above_full_season_response": len(union_keys) - len(full_keys),
        },
        "aggregation": aggregation,
        "recovered_only": {
            "count": len(recovered_only),
            "pairs": recovered_only,
            "base_minutes_distribution": _quantiles([value for value in minutes if value is not None]),
            "advanced_possessions_distribution": _quantiles(
                [value for value in possessions if value is not None]
            ),
        },
        "threshold_sensitivity": threshold_sensitivity(
            recovered_rows, recovered_only, full_advanced_payload
        ),
        "continuation_gate": {
            "checks": gate_checks,
            "passed": continuation_passed,
        },
    }


def _write_metadata(cache_root: Path, asset: Mapping[str, Any], metadata: Mapping[str, Any]) -> None:
    atomic_write_json(cache_root / asset["cache"]["metadata_relative_path"], metadata)


def _verify_cached_asset(
    cache_root: Path,
    asset: Mapping[str, Any],
    approved_schemas: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload_path = cache_root / asset["cache"]["relative_path"]
    metadata_path = cache_root / asset["cache"]["metadata_relative_path"]
    if not payload_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("Phase 1E cache payload or metadata is missing")
    body = payload_path.read_bytes()
    payload = json.loads(body)
    metadata = read_json(metadata_path)
    if metadata.get("asset_id") != asset["asset_id"] or metadata.get("identity") != asset["identity"]:
        raise ValueError("Phase 1E cached identity mismatch")
    if metadata.get("response_body_bytes") != len(body):
        raise ValueError("Phase 1E cached byte count mismatch")
    if metadata.get("raw_body_hash") != raw_body_hash(body):
        raise ValueError("Phase 1E cached raw-body hash mismatch")
    if metadata.get("canonical_json_hash") != canonical_json_hash(payload):
        raise ValueError("Phase 1E cached canonical JSON hash mismatch")
    validation = validate_window_payload(
        payload, asset["identity"], approved_schemas[asset["measure"]]
    )
    return payload, validation


def _stop_result(
    ledger: Mapping[str, Any], category: str, detail: str, *, classification: str = "window recovery not demonstrated"
) -> dict[str, Any]:
    return {
        "completed": False,
        "stopped_early": True,
        "stop_category": category,
        "stop_detail": detail,
        "attempted": sum(asset["attempt_count"] for asset in ledger["assets"]),
        "verified": sum(asset["status"] == "verified" for asset in ledger["assets"]),
        "failed": sum(asset["status"] == "failed" for asset in ledger["assets"]),
        "classification": classification,
        "team_audits": ledger.get("team_audits", {}),
    }


def run_phase1e_recovery(
    cache_root: Path,
    *,
    phase1c_manifest: Mapping[str, Any],
    phase1d_ledger: Mapping[str, Any],
    full_season_payloads: Mapping[str, Mapping[str, Mapping[str, Any]]],
    approved_schemas: Mapping[str, Mapping[str, Mapping[str, Any]]],
    live_acquisition: bool = False,
    transport: Callable[[Mapping[str, Any], int], WindowTransportResult] | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    if timeout_seconds != 30:
        raise ValueError("Phase 1E requires the approved 30-second timeout")
    validate_window_contract()
    if live_acquisition and transport is None:
        transport = direct_window_transport
    ledger = load_or_create_phase1e_ledger(cache_root)
    isolation = validate_phase1e_isolation(ledger, phase1c_manifest, phase1d_ledger)
    payloads: dict[str, dict[str, dict[str, Any]]] = {
        team_id: {"early": {}, "late": {}} for team_id, _ in TEAM_SEQUENCE
    }

    for asset in ledger["assets"]:
        team_id = asset["identity"]["parameters"]["team_id"]
        if asset["status"] == "failed":
            attempt = asset.get("attempt") or {}
            return _stop_result(
                ledger,
                attempt.get("error_category", "previous_failure"),
                attempt.get("error_detail", "A previous Phase 1E asset failed"),
            )
        payload_path = cache_root / asset["cache"]["relative_path"]
        metadata_path = cache_root / asset["cache"]["metadata_relative_path"]
        if asset["status"] == "verified" or (
            asset["status"] == "planned" and payload_path.is_file() and metadata_path.is_file()
        ):
            try:
                payload, validation = _verify_cached_asset(
                    cache_root, asset, approved_schemas
                )
            except Exception as exc:
                return _stop_result(ledger, "cache_replay_error", str(exc))
            if asset["status"] == "planned":
                asset["status"] = "verified"
                asset["cache_reconciled_without_transport"] = True
                asset["validation"] = validation
                if live_acquisition:
                    save_phase1e_ledger(cache_root, ledger)
            payloads[team_id][asset["window"]][asset["measure"]] = payload
        elif not live_acquisition:
            return {
                **_stop_result(
                    ledger,
                    "live_request_not_enabled",
                    f"Next uncached asset: {asset['asset_id']}",
                ),
                "next_asset_id": asset["asset_id"],
                "diagnostic_isolation": isolation,
            }
        else:
            if asset["attempt_count"] != 0:
                return _stop_result(
                    ledger, "retry_not_authorized", f"Asset already consumed an attempt: {asset['asset_id']}"
                )
            asset["attempt_count"] = 1
            asset["attempt"] = {
                "request_kind": "phase1e_live_window",
                "attempt_number": 1,
                "started_at": utc_now(),
                "timeout_seconds": timeout_seconds,
                "status": "started",
                "error_category": None,
                "error_detail": None,
            }
            save_phase1e_ledger(cache_root, ledger)
            try:
                response = transport(asset["identity"], timeout_seconds)  # type: ignore[misc]
            except WindowTransportError as exc:
                asset["status"] = "failed"
                asset["attempt"].update(
                    status="failed", error_category=exc.category, error_detail=exc.detail
                )
                _write_metadata(
                    cache_root,
                    asset,
                    {
                        "phase1e_version": PHASE1E_VERSION,
                        "asset_id": asset["asset_id"],
                        "identity": asset["identity"],
                        "attempt": asset["attempt"],
                        "http_status": None,
                        "validation_classification": "transport_failure",
                    },
                )
                save_phase1e_ledger(cache_root, ledger)
                return _stop_result(ledger, exc.category, exc.detail)
            metadata: dict[str, Any] = {
                "phase1e_version": PHASE1E_VERSION,
                "asset_id": asset["asset_id"],
                "identity": asset["identity"],
                "attempt": asset["attempt"],
                "acquisition_timestamp": asset["attempt"]["started_at"],
                "http_status": response.status_code,
                "latency_seconds": response.elapsed_seconds,
                "response_body_bytes": len(response.body),
                "raw_body_hash": raw_body_hash(response.body),
            }
            if response.status_code != 200:
                error_path = cache_root / asset["cache"]["error_body_relative_path"]
                atomic_write_bytes_new(error_path, response.body)
                asset["status"] = "failed"
                detail = f"HTTP {response.status_code}"
                asset["attempt"].update(
                    status="failed", error_category="http_error", error_detail=detail
                )
                metadata.update(
                    attempt=asset["attempt"],
                    validation_classification="http_failure",
                    error_body_relative_path=asset["cache"]["error_body_relative_path"],
                )
                _write_metadata(cache_root, asset, metadata)
                save_phase1e_ledger(cache_root, ledger)
                return _stop_result(ledger, "http_error", detail)
            try:
                payload = json.loads(response.body)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                error_path = cache_root / asset["cache"]["error_body_relative_path"]
                atomic_write_bytes_new(error_path, response.body)
                asset["status"] = "failed"
                detail = f"{type(exc).__name__}: {exc}"
                asset["attempt"].update(
                    status="failed", error_category="invalid_json", error_detail=detail
                )
                metadata.update(
                    attempt=asset["attempt"],
                    validation_classification="invalid_json",
                    error_body_relative_path=asset["cache"]["error_body_relative_path"],
                )
                _write_metadata(cache_root, asset, metadata)
                save_phase1e_ledger(cache_root, ledger)
                return _stop_result(ledger, "invalid_json", detail)
            payload_path = cache_root / asset["cache"]["relative_path"]
            atomic_write_bytes_new(payload_path, response.body)
            metadata["canonical_json_hash"] = canonical_json_hash(payload)
            try:
                validation = validate_window_payload(
                    payload, asset["identity"], approved_schemas[asset["measure"]]
                )
            except Exception as exc:
                asset["status"] = "failed"
                detail = f"{type(exc).__name__}: {exc}"
                asset["attempt"].update(
                    status="failed", error_category="validation_error", error_detail=detail
                )
                metadata.update(
                    attempt=asset["attempt"],
                    validation_classification="rejected",
                    validation_error=detail,
                )
                _write_metadata(cache_root, asset, metadata)
                save_phase1e_ledger(cache_root, ledger)
                return _stop_result(ledger, "validation_error", detail)
            asset["status"] = "verified"
            asset["attempt"].update(status="verified", completed_at=utc_now())
            asset["validation"] = validation
            metadata.update(
                attempt=asset["attempt"],
                validation_classification="verified",
                schemas=validation["fingerprints"],
                row_counts=validation["row_counts"],
            )
            _write_metadata(cache_root, asset, metadata)
            save_phase1e_ledger(cache_root, ledger)
            payloads[team_id][asset["window"]][asset["measure"]] = payload

        # Audit Charlotte immediately after its fourth asset, before Philadelphia.
        if asset["sequence"] == 4:
            charlotte = audit_team_recovery(
                CHARLOTTE_ID,
                full_season_payloads[CHARLOTTE_ID]["Base"],
                full_season_payloads[CHARLOTTE_ID]["Advanced"],
                payloads[CHARLOTTE_ID],
            )
            ledger["team_audits"][CHARLOTTE_ID] = charlotte
            if live_acquisition:
                save_phase1e_ledger(cache_root, ledger)
            if not charlotte["continuation_gate"]["passed"]:
                return _stop_result(
                    ledger,
                    "charlotte_continuation_gate_failed",
                    "Charlotte did not satisfy every continuation condition",
                    classification=(
                        "window recovery demonstrated; target recomposition unresolved"
                        if charlotte["union"]["increase_above_full_season_response"] > 0
                        else "window recovery not demonstrated"
                    ),
                )

        if asset["sequence"] == 8:
            philadelphia = audit_team_recovery(
                PHILADELPHIA_ID,
                full_season_payloads[PHILADELPHIA_ID]["Base"],
                full_season_payloads[PHILADELPHIA_ID]["Advanced"],
                payloads[PHILADELPHIA_ID],
            )
            ledger["team_audits"][PHILADELPHIA_ID] = philadelphia
            if live_acquisition:
                save_phase1e_ledger(cache_root, ledger)

    charlotte = ledger["team_audits"].get(CHARLOTTE_ID)
    philadelphia = ledger["team_audits"].get(PHILADELPHIA_ID)
    if charlotte and charlotte["continuation_gate"]["passed"]:
        if philadelphia and philadelphia["continuation_gate"]["passed"]:
            classification = "window recovery and target recomposition demonstrated for both affected team-seasons"
        else:
            classification = "window recovery and target recomposition demonstrated for Charlotte only"
    elif charlotte and charlotte["union"]["increase_above_full_season_response"] > 0:
        classification = "window recovery demonstrated; target recomposition unresolved"
    else:
        classification = "window recovery not demonstrated"
    return {
        "completed": True,
        "stopped_early": False,
        "stop_category": None,
        "attempted": sum(asset["attempt_count"] for asset in ledger["assets"]),
        "verified": sum(asset["status"] == "verified" for asset in ledger["assets"]),
        "failed": sum(asset["status"] == "failed" for asset in ledger["assets"]),
        "classification": classification,
        "team_audits": ledger["team_audits"],
        "diagnostic_isolation": isolation,
    }


def replay_phase1e_recovery(
    cache_root: Path,
    *,
    phase1c_manifest: Mapping[str, Any],
    phase1d_ledger: Mapping[str, Any],
    full_season_payloads: Mapping[str, Mapping[str, Mapping[str, Any]]],
    approved_schemas: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Replay Phase 1E with no transport surface."""
    return run_phase1e_recovery(
        cache_root,
        phase1c_manifest=phase1c_manifest,
        phase1d_ledger=phase1d_ledger,
        full_season_payloads=full_season_payloads,
        approved_schemas=approved_schemas,
        live_acquisition=False,
    )
