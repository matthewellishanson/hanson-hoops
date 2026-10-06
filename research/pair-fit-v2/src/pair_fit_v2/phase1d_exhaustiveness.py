"""Phase 1D bounded diagnostics for TeamDashLineups population exhaustiveness.

Imports, construction, analysis, and replay are cache-only.  Network access is
possible only when ``run_authorized_diagnostics`` receives both
``live_acquisition=True`` and an explicit transport (or elects the fixed direct
transport).  Diagnostic state and payloads live outside the immutable Phase 1C
60-asset manifest.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS
from pair_fit_v2.lineup_audit import extract_result_set, result_set_rows
from pair_fit_v2.multi_team_audit import schema_fingerprint
from pair_fit_v2.phase1b_contract import (
    raw_asset_identity,
    schema_drift_report,
    stable_contract_id,
)
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
    validate_payload_structure,
)


TEAM_DASH_LINEUPS = "TeamDashLineups"
LEAGUE_DASH_LINEUPS = "LeagueDashLineups"
TEAM_DASH_LINEUPS_URL = "https://stats.nba.com/stats/teamdashlineups"
LEAGUE_DASH_LINEUPS_URL = "https://stats.nba.com/stats/leaguedashlineups"
DIAGNOSTIC_VERSION = "phase1d.endpoint-exhaustiveness.v1"
DIAGNOSTIC_ID_KIND = "phase1d-diagnostic-asset"
ROW_BOUNDARY = 250
BASE_MEASURE = "Base"
CHARLOTTE_ID = "1610612766"
PHILADELPHIA_ID = "1610612755"

LEAGUE_DASH_LINEUPS_EXTRA_PARAMETERS: dict[str, Any] = {
    "Conference": "",
    "DateFrom": "",
    "DateTo": "",
    "Division": "",
    "GameSegment": "",
    "LastNGames": "0",
    "Location": "",
    "Month": "0",
    "OpponentTeamID": "0",
    "Outcome": "",
    "PORound": "",
    "PaceAdjust": "N",
    "PerMode": "Totals",
    "Period": "0",
    "PlusMinus": "N",
    "Rank": "N",
    "SeasonSegment": "",
    "ShotClockRange": "",
    "VsConference": "",
    "VsDivision": "",
}

PAGINATION_FIELD_MARKERS = (
    "continuation",
    "hasmore",
    "is_truncated",
    "istruncated",
    "nextpage",
    "pagecount",
    "pagesize",
    "rowcount",
    "totalcount",
    "truncate",
)
PAGINATION_EXACT_FIELDS = {"limit", "offset", "page", "total"}


@dataclass(frozen=True)
class DiagnosticTransportResult:
    status_code: int
    body: bytes
    elapsed_seconds: float


class DiagnosticTransportError(RuntimeError):
    def __init__(self, category: str, detail: str):
        super().__init__(detail)
        self.category = category
        self.detail = detail


def _team_short_window_identity(team_id: str) -> dict[str, Any]:
    extra = dict(TEAM_DASH_LINEUPS_EXTRA_PARAMETERS)
    extra["LastNGames"] = "41"
    return raw_asset_identity(
        endpoint=TEAM_DASH_LINEUPS,
        season=TARGET_SEASON,
        team_id=team_id,
        measure_type=BASE_MEASURE,
        season_type=SEASON_TYPE,
        league_id=LEAGUE_ID,
        group_quantity=GROUP_QUANTITY,
        extra_parameters=extra,
    )


def _charlotte_league_identity() -> dict[str, Any]:
    return raw_asset_identity(
        endpoint=LEAGUE_DASH_LINEUPS,
        season=TARGET_SEASON,
        team_id=CHARLOTTE_ID,
        measure_type=BASE_MEASURE,
        season_type=SEASON_TYPE,
        league_id=LEAGUE_ID,
        group_quantity=GROUP_QUANTITY,
        extra_parameters=LEAGUE_DASH_LINEUPS_EXTRA_PARAMETERS,
    )


def diagnostic_asset(identity: Mapping[str, Any], sequence: int) -> dict[str, Any]:
    normalized = dict(identity)
    asset_id = stable_contract_id(DIAGNOSTIC_ID_KIND, normalized)
    safe_id = asset_id.replace(":", "_")
    relative = f"phase1d/diagnostics/{safe_id}.json"
    return {
        "sequence": sequence,
        "asset_id": asset_id,
        "identity": normalized,
        "status": "planned",
        "attempt_count": 0,
        "attempt": None,
        "cache": {
            "relative_path": relative,
            "metadata_relative_path": relative.replace(".json", ".metadata.json"),
            "error_body_relative_path": relative.replace(".json", ".error.bin"),
        },
        "comparison": None,
    }


def build_diagnostic_ledger() -> dict[str, Any]:
    assets = [
        diagnostic_asset(_team_short_window_identity(CHARLOTTE_ID), 1),
        diagnostic_asset(_team_short_window_identity(PHILADELPHIA_ID), 2),
        diagnostic_asset(_charlotte_league_identity(), 3),
    ]
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "authorization": {
            "maximum_live_requests": 3,
            "sequential_only": True,
            "stop_after_conclusive_result": True,
            "retry_authorized": False,
        },
        "assets": assets,
        "created_at": None,
        "updated_at": None,
    }


def diagnostic_ledger_path(cache_root: Path) -> Path:
    return cache_root / "phase1d" / "diagnostic_ledger.json"


def validate_diagnostic_isolation(
    ledger: Mapping[str, Any], phase1c_manifest: Mapping[str, Any]
) -> dict[str, Any]:
    diagnostic_ids = [asset["asset_id"] for asset in ledger["assets"]]
    production_ids = {asset["asset_id"] for asset in phase1c_manifest["raw_assets"]}
    diagnostic_paths = [asset["cache"]["relative_path"] for asset in ledger["assets"]]
    collisions = sorted(set(diagnostic_ids) & production_ids)
    invalid_ids = sorted(
        asset_id for asset_id in diagnostic_ids if not asset_id.startswith(f"{DIAGNOSTIC_ID_KIND}:")
    )
    invalid_paths = sorted(
        path for path in diagnostic_paths if not path.startswith("phase1d/diagnostics/")
    )
    unique = len(diagnostic_ids) == len(set(diagnostic_ids)) == 3
    result = {
        "isolated": not collisions and not invalid_ids and not invalid_paths and unique,
        "asset_id_collisions": collisions,
        "invalid_diagnostic_ids": invalid_ids,
        "invalid_diagnostic_paths": invalid_paths,
        "unique_diagnostic_asset_ids": unique,
    }
    if not result["isolated"]:
        raise ValueError(f"Diagnostic asset isolation failed: {result}")
    return result


def _validate_ledger(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    if actual.get("diagnostic_version") != DIAGNOSTIC_VERSION:
        raise ValueError("Diagnostic ledger version mismatch")
    if actual.get("authorization") != expected.get("authorization"):
        raise ValueError("Diagnostic authorization mismatch")
    actual_assets = actual.get("assets")
    expected_assets = expected.get("assets")
    if not isinstance(actual_assets, list) or len(actual_assets) != 3:
        raise ValueError("Diagnostic ledger must contain exactly three assets")
    for actual_asset, expected_asset in zip(actual_assets, expected_assets):
        for field in ("sequence", "asset_id", "identity", "cache"):
            if actual_asset.get(field) != expected_asset.get(field):
                raise ValueError(f"Diagnostic asset contract mismatch: {field}")


def load_or_create_diagnostic_ledger(cache_root: Path) -> dict[str, Any]:
    path = diagnostic_ledger_path(cache_root)
    expected = build_diagnostic_ledger()
    if path.is_file():
        actual = read_json(path)
        _validate_ledger(actual, expected)
        return actual
    now = utc_now()
    expected["created_at"] = now
    expected["updated_at"] = now
    atomic_write_json(path, expected)
    return expected


def save_diagnostic_ledger(cache_root: Path, ledger: dict[str, Any]) -> None:
    _validate_ledger(ledger, build_diagnostic_ledger())
    ledger["updated_at"] = utc_now()
    atomic_write_json(diagnostic_ledger_path(cache_root), ledger)


def _strict_pair_key(group_id: Any) -> tuple[str, str] | None:
    if not isinstance(group_id, str):
        return None
    tokens = [token for token in group_id.strip("-").split("-") if token]
    if (
        len(tokens) != 2
        or tokens[0] == tokens[1]
        or not all(token.isdecimal() and int(token) > 0 for token in tokens)
    ):
        return None
    return tuple(sorted(tokens, key=int))  # type: ignore[return-value]


def pair_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return result_set_rows(extract_result_set(dict(payload), "Lineups"))


def _pair_index(rows: list[Mapping[str, Any]]) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]], int]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    invalid = []
    duplicates = 0
    for position, row in enumerate(rows):
        key = _strict_pair_key(row.get("GROUP_ID"))
        if key is None:
            invalid.append(
                {"row_index": position, "group_id": row.get("GROUP_ID"), "group_name": row.get("GROUP_NAME")}
            )
            continue
        if key in index:
            duplicates += 1
            continue
        index[key] = dict(row)
    return index, invalid, duplicates


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _low_end(rows: list[Mapping[str, Any]], field: str, count: int = 10) -> dict[str, Any]:
    available = [row for row in rows if _numeric(row.get(field)) is not None]
    ordered = sorted(available, key=lambda row: (_numeric(row.get(field)), str(row.get("GROUP_ID"))))
    return {
        "field": field,
        "minimum": _numeric(ordered[0].get(field)) if ordered else None,
        "lowest_rows": [
            {
                "pair_ids": _strict_pair_key(row.get("GROUP_ID")),
                "group_name": row.get("GROUP_NAME"),
                "gp": row.get("GP"),
                "min": row.get("MIN"),
                field.lower(): row.get(field),
            }
            for row in ordered[:count]
        ],
    }


def _rank_maxima(rows: list[Mapping[str, Any]]) -> dict[str, float | None]:
    fields = sorted({key for row in rows for key in row if key.endswith("_RANK")})
    result = {}
    for field in fields:
        values = [_numeric(row.get(field)) for row in rows]
        numeric = [value for value in values if value is not None]
        result[field] = max(numeric) if numeric else None
    return result


def _envelope_inspection(payload: Mapping[str, Any]) -> dict[str, Any]:
    hits = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                normalized = str(key).lower().replace("-", "").replace("_", "")
                if normalized in PAGINATION_EXACT_FIELDS or any(
                    marker.replace("_", "") in normalized for marker in PAGINATION_FIELD_MARKERS
                ):
                    hits.append({"path": f"{path}.{key}", "value": child})
                if key not in {"rowSet", "headers"}:
                    visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    visit(payload, "$")
    result_sets = payload.get("resultSets", [])
    return {
        "top_level_keys": sorted(payload.keys()),
        "result_set_envelopes": [
            {"name": item.get("name"), "keys": sorted(item.keys())}
            for item in result_sets
            if isinstance(item, Mapping)
        ],
        "pagination_or_truncation_metadata": hits,
        "metadata_present": bool(hits),
    }


def analyze_boundary_payload(
    payload: Mapping[str, Any], *, measure_type: str, boundary: int = ROW_BOUNDARY
) -> dict[str, Any]:
    rows = pair_rows(payload)
    index, invalid, duplicates = _pair_index(rows)
    players = sorted({player for key in index for player in key}, key=int)
    theoretical_keys = set(combinations(players, 2))
    absent = sorted(theoretical_keys - set(index), key=lambda key: (int(key[0]), int(key[1])))
    signal = len(rows) == boundary and len(theoretical_keys) > len(index)
    result = {
        "classification": "boundary_signal_present" if signal else "no_boundary_signal",
        "boundary": boundary,
        "row_count": len(rows),
        "valid_unique_pair_count": len(index),
        "invalid_pair_row_count": len(invalid),
        "invalid_pair_rows": invalid,
        "duplicate_pair_key_count": duplicates,
        "distinct_player_count": len(players),
        "distinct_player_ids": players,
        "theoretical_unordered_pair_count": len(theoretical_keys),
        "absent_theoretical_pair_count": len(absent),
        "absent_theoretical_pair_examples": absent[:20],
        "maximum_rank_values": _rank_maxima(rows),
        "response_envelope": _envelope_inspection(payload),
        "interpretation": (
            "An exact returned-row boundary with absent theoretical combinations is a signal, not proof of omission."
            if signal
            else "No exact returned-row boundary signal was detected."
        ),
    }
    if measure_type == "Base":
        result["low_end_base_minutes"] = _low_end(rows, "MIN")
    elif measure_type == "Advanced":
        result["low_end_advanced_possessions"] = _low_end(rows, "POSS")
        result["low_end_advanced_minutes"] = _low_end(rows, "MIN")
    return result


def compare_pair_populations(
    full_season_payload: Mapping[str, Any], diagnostic_payload: Mapping[str, Any]
) -> dict[str, Any]:
    full_rows = pair_rows(full_season_payload)
    diagnostic_rows = pair_rows(diagnostic_payload)
    full_index, full_invalid, full_duplicates = _pair_index(full_rows)
    diagnostic_index, diagnostic_invalid, diagnostic_duplicates = _pair_index(diagnostic_rows)
    full_keys = set(full_index)
    diagnostic_keys = set(diagnostic_index)
    matched = sorted(full_keys & diagnostic_keys, key=lambda key: (int(key[0]), int(key[1])))
    diagnostic_only = sorted(diagnostic_keys - full_keys, key=lambda key: (int(key[0]), int(key[1])))
    full_only = sorted(full_keys - diagnostic_keys, key=lambda key: (int(key[0]), int(key[1])))
    examples = [
        {
            "pair_ids": key,
            "group_id": diagnostic_index[key].get("GROUP_ID"),
            "group_name": diagnostic_index[key].get("GROUP_NAME"),
            "gp": diagnostic_index[key].get("GP"),
            "min": diagnostic_index[key].get("MIN"),
            "structurally_valid": True,
        }
        for key in diagnostic_only
    ]
    return {
        "classification": "proven_non_exhaustive" if diagnostic_only else "not_proven_exhaustive",
        "full_season_row_count": len(full_rows),
        "diagnostic_row_count": len(diagnostic_rows),
        "matched_full_season_keys": len(matched),
        "diagnostic_only_key_count": len(diagnostic_only),
        "diagnostic_only_keys": diagnostic_only,
        "diagnostic_only_examples": examples,
        "full_season_only_key_count": len(full_only),
        "full_season_only_keys": full_only,
        "full_season_invalid_pair_rows": full_invalid,
        "diagnostic_invalid_pair_rows": diagnostic_invalid,
        "full_season_duplicate_pair_keys": full_duplicates,
        "diagnostic_duplicate_pair_keys": diagnostic_duplicates,
        "proof_basis": (
            "At least one structurally valid pair returned for a shorter same-season window is absent from the full-season pair-key set."
            if diagnostic_only
            else "No additional valid pair was found; this does not prove exhaustiveness."
        ),
    }


def _expected_query(identity: Mapping[str, Any]) -> dict[str, Any]:
    parameters = dict(identity["parameters"])
    season_type = parameters.pop("season_type")
    if season_type != "regular-season":
        raise ValueError(f"Unauthorized season type: {season_type}")
    core = {
        "LeagueID": parameters.pop("league_id"),
        "Season": parameters.pop("season"),
        "SeasonType": SEASON_TYPE,
        "TeamID": parameters.pop("team_id"),
        "GroupQuantity": parameters.pop("group_quantity"),
        "MeasureType": parameters.pop("measure_type"),
    }
    return {**parameters, **core}


def _normalized_response_value(name: str, value: Any) -> str:
    if value is None or value == "":
        return ""
    # TeamDashLineups consistently echoes the request's empty PORound sentinel
    # as numeric zero, including in the verified Phase 1C full-season assets.
    if name == "PORound" and value in {0, "0"}:
        return ""
    return str(value)


def _validate_response_parameters(payload: Mapping[str, Any], identity: Mapping[str, Any]) -> None:
    returned = payload.get("parameters")
    if not isinstance(returned, Mapping):
        raise ValueError("Response is missing request parameters")
    expected = _expected_query(identity)
    required = {"LeagueID", "Season", "SeasonType", "TeamID", "GroupQuantity", "MeasureType", "LastNGames"}
    for name in required:
        if name not in returned:
            raise ValueError(f"Response identity is missing {name}")
    mismatches = {
        name: {"expected": expected_value, "actual": returned.get(name)}
        for name, expected_value in expected.items()
        if name in returned
        and _normalized_response_value(name, expected_value)
        != _normalized_response_value(name, returned.get(name))
    }
    if mismatches:
        raise ValueError(f"Response request identity mismatch: {mismatches}")


def _validate_team_context(payload: Mapping[str, Any], team_id: str, endpoint: str) -> None:
    if endpoint == TEAM_DASH_LINEUPS:
        overall = result_set_rows(extract_result_set(dict(payload), "Overall"))
        if len(overall) != 1 or str(overall[0].get("TEAM_ID")) != team_id:
            raise ValueError("TeamDashLineups Overall team identity mismatch")
        return
    rows = pair_rows(payload)
    if not rows:
        raise ValueError("LeagueDashLineups returned no lineup rows")
    if not all("TEAM_ID" in row for row in rows):
        raise ValueError("LeagueDashLineups rows do not expose TEAM_ID for filter validation")
    returned_teams = {str(row.get("TEAM_ID")) for row in rows}
    if returned_teams != {team_id}:
        raise ValueError(f"LeagueDashLineups team filter mismatch: {sorted(returned_teams)}")


def validate_diagnostic_payload(
    payload: Mapping[str, Any],
    identity: Mapping[str, Any],
    approved_base_schema: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    _validate_response_parameters(payload, identity)
    endpoint = str(identity["endpoint"])
    team_id = str(identity["parameters"]["team_id"])
    _validate_team_context(payload, team_id, endpoint)
    if endpoint == TEAM_DASH_LINEUPS:
        structure = validate_payload_structure(payload)
        actual = {item["name"]: item for item in structure["fingerprints"]}
        for result_set_name, expected in approved_base_schema.items():
            drift = schema_drift_report(expected, actual[result_set_name])
            if not drift["accepted"]:
                raise ValueError(f"Diagnostic schema mismatch for {result_set_name}: {drift['classification']}")
        return structure
    lineups = extract_result_set(dict(payload), "Lineups")
    rows = result_set_rows(lineups)
    headers = set(lineups.get("headers", []))
    required_headers = {"TEAM_ID", "GROUP_ID", "GROUP_NAME", "GP", "MIN"}
    if not required_headers <= headers:
        raise ValueError(f"LeagueDashLineups schema missing headers: {sorted(required_headers - headers)}")
    return {
        "row_counts": {"Lineups": len(rows)},
        "fingerprints": [schema_fingerprint(lineups)],
    }


def direct_diagnostic_transport(
    identity: Mapping[str, Any], timeout_seconds: int = 30
) -> DiagnosticTransportResult:
    if timeout_seconds != 30:
        raise ValueError("Phase 1D diagnostics require the approved 30-second timeout")
    endpoint = identity.get("endpoint")
    if endpoint == TEAM_DASH_LINEUPS:
        url = TEAM_DASH_LINEUPS_URL
    elif endpoint == LEAGUE_DASH_LINEUPS:
        url = LEAGUE_DASH_LINEUPS_URL
    else:
        raise ValueError(f"Unsupported diagnostic endpoint: {endpoint}")
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    started = time.perf_counter()
    try:
        response = session.get(url, params=_expected_query(identity), timeout=timeout_seconds)
        return DiagnosticTransportResult(
            status_code=response.status_code,
            body=response.content,
            elapsed_seconds=time.perf_counter() - started,
        )
    except requests.Timeout as exc:
        raise DiagnosticTransportError("timeout", str(exc)) from exc
    except requests.exceptions.SSLError as exc:
        raise DiagnosticTransportError("tls_failure", str(exc)) from exc
    except requests.ConnectionError as exc:
        raise DiagnosticTransportError("connection_or_dns_failure", str(exc)) from exc
    except requests.RequestException as exc:
        raise DiagnosticTransportError("request_failure", str(exc)) from exc
    finally:
        session.close()


def _write_attempt_metadata(
    cache_root: Path,
    asset: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> None:
    atomic_write_json(cache_root / asset["cache"]["metadata_relative_path"], metadata)


def _failure_result(ledger: Mapping[str, Any], asset: Mapping[str, Any], category: str, detail: str) -> dict[str, Any]:
    return {
        "completed": False,
        "stopped_early": True,
        "stop_category": category,
        "stop_detail": detail,
        "attempted": sum(asset["attempt_count"] for asset in ledger["assets"]),
        "verified": sum(
            asset["status"] in {"verified", "verified_after_offline_revalidation"}
            for asset in ledger["assets"]
        ),
        "failed": sum(asset["status"] == "failed" for asset in ledger["assets"]),
        "classification": None,
        "conclusive_asset_id": None,
    }


def _verify_cached_diagnostic(
    cache_root: Path,
    asset: Mapping[str, Any],
    approved_base_schema: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload_path = cache_root / asset["cache"]["relative_path"]
    metadata_path = cache_root / asset["cache"]["metadata_relative_path"]
    if not payload_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("Verified diagnostic cache or metadata is missing")
    body = payload_path.read_bytes()
    payload = json.loads(body)
    metadata = read_json(metadata_path)
    if metadata.get("asset_id") != asset["asset_id"] or metadata.get("identity") != asset["identity"]:
        raise ValueError("Diagnostic metadata identity mismatch")
    if metadata.get("response_body_bytes") != len(body):
        raise ValueError("Diagnostic cache byte-size mismatch")
    if metadata.get("raw_body_hash") != raw_body_hash(body):
        raise ValueError("Diagnostic raw-body hash mismatch")
    if metadata.get("canonical_json_hash") != canonical_json_hash(payload):
        raise ValueError("Diagnostic canonical JSON hash mismatch")
    validation = validate_diagnostic_payload(payload, asset["identity"], approved_base_schema)
    return payload, validation


def run_authorized_diagnostics(
    cache_root: Path,
    *,
    phase1c_manifest: Mapping[str, Any],
    full_season_base_payloads: Mapping[str, Mapping[str, Any]],
    approved_base_schema: Mapping[str, Mapping[str, Any]],
    live_acquisition: bool = False,
    transport: Callable[[Mapping[str, Any], int], DiagnosticTransportResult] | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    if timeout_seconds != 30:
        raise ValueError("Phase 1D diagnostics require the approved 30-second timeout")
    if live_acquisition and transport is None:
        transport = direct_diagnostic_transport
    ledger = load_or_create_diagnostic_ledger(cache_root)
    isolation = validate_diagnostic_isolation(ledger, phase1c_manifest)

    for asset in ledger["assets"]:
        team_id = asset["identity"]["parameters"]["team_id"]
        if team_id not in full_season_base_payloads:
            raise ValueError(f"Missing full-season Base payload for {team_id}")
        if asset["status"] == "failed":
            return _failure_result(
                ledger,
                asset,
                asset.get("attempt", {}).get("error_category", "previous_failure"),
                asset.get("attempt", {}).get("error_detail", "A previous request failed"),
            )
        if asset["status"] in {"verified", "verified_after_offline_revalidation"}:
            try:
                payload, _ = _verify_cached_diagnostic(cache_root, asset, approved_base_schema)
            except Exception as exc:
                return _failure_result(ledger, asset, "cache_replay_error", str(exc))
            comparison = compare_pair_populations(full_season_base_payloads[team_id], payload)
            if json.dumps(comparison, sort_keys=True) != json.dumps(
                asset.get("comparison"), sort_keys=True
            ):
                return _failure_result(ledger, asset, "cache_comparison_mismatch", "Persisted comparison does not replay")
            if comparison["classification"] == "proven_non_exhaustive":
                return {
                    "completed": True,
                    "stopped_early": True,
                    "stop_category": "conclusive_non_exhaustiveness",
                    "attempted": sum(item["attempt_count"] for item in ledger["assets"]),
                    "verified": sum(
                        item["status"] in {"verified", "verified_after_offline_revalidation"}
                        for item in ledger["assets"]
                    ),
                    "failed": 0,
                    "classification": "proven_non_exhaustive",
                    "conclusive_asset_id": asset["asset_id"],
                    "comparison": comparison,
                    "diagnostic_isolation": isolation,
                }
            continue
        if not live_acquisition:
            return {
                "completed": False,
                "stopped_early": True,
                "stop_category": "live_request_not_enabled",
                "next_asset_id": asset["asset_id"],
                "attempted": sum(item["attempt_count"] for item in ledger["assets"]),
                "verified": sum(
                    item["status"] in {"verified", "verified_after_offline_revalidation"}
                    for item in ledger["assets"]
                ),
                "failed": 0,
                "classification": (
                    "not_proven_exhaustive"
                    if any(
                        item["status"] in {"verified", "verified_after_offline_revalidation"}
                        for item in ledger["assets"]
                    )
                    else None
                ),
                "diagnostic_isolation": isolation,
            }

        attempt_number = 1
        asset["attempt_count"] = attempt_number
        asset["attempt"] = {
            "request_kind": "phase1d_live_diagnostic",
            "attempt_number": attempt_number,
            "started_at": utc_now(),
            "timeout_seconds": timeout_seconds,
            "status": "started",
            "error_category": None,
            "error_detail": None,
        }
        save_diagnostic_ledger(cache_root, ledger)
        try:
            response = transport(asset["identity"], timeout_seconds)  # type: ignore[misc]
        except DiagnosticTransportError as exc:
            asset["status"] = "failed"
            asset["attempt"].update(status="failed", error_category=exc.category, error_detail=exc.detail)
            _write_attempt_metadata(
                cache_root,
                asset,
                {
                    "diagnostic_version": DIAGNOSTIC_VERSION,
                    "asset_id": asset["asset_id"],
                    "identity": asset["identity"],
                    "attempt": asset["attempt"],
                    "http_status": None,
                    "response_body_bytes": None,
                },
            )
            save_diagnostic_ledger(cache_root, ledger)
            return _failure_result(ledger, asset, exc.category, exc.detail)

        body_path = cache_root / asset["cache"]["relative_path"]
        metadata: dict[str, Any] = {
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "asset_id": asset["asset_id"],
            "identity": asset["identity"],
            "attempt": asset["attempt"],
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
            asset["attempt"].update(status="failed", error_category="http_error", error_detail=detail)
            metadata["attempt"] = asset["attempt"]
            metadata["error_body_relative_path"] = asset["cache"]["error_body_relative_path"]
            _write_attempt_metadata(cache_root, asset, metadata)
            save_diagnostic_ledger(cache_root, ledger)
            return _failure_result(ledger, asset, "http_error", detail)

        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            error_path = cache_root / asset["cache"]["error_body_relative_path"]
            atomic_write_bytes_new(error_path, response.body)
            asset["status"] = "failed"
            detail = f"{type(exc).__name__}: {exc}"
            asset["attempt"].update(status="failed", error_category="invalid_json", error_detail=detail)
            metadata["attempt"] = asset["attempt"]
            metadata["error_body_relative_path"] = asset["cache"]["error_body_relative_path"]
            _write_attempt_metadata(cache_root, asset, metadata)
            save_diagnostic_ledger(cache_root, ledger)
            return _failure_result(ledger, asset, "invalid_json", detail)
        if not isinstance(payload, Mapping):
            validation_error: Exception | None = ValueError("JSON response is not an object")
        else:
            validation_error = None
            try:
                validation = validate_diagnostic_payload(payload, asset["identity"], approved_base_schema)
            except Exception as exc:
                validation_error = exc
        atomic_write_bytes_new(body_path, response.body)
        metadata["canonical_json_hash"] = canonical_json_hash(payload)
        if validation_error is not None:
            asset["status"] = "failed"
            detail = f"{type(validation_error).__name__}: {validation_error}"
            asset["attempt"].update(status="failed", error_category="validation_error", error_detail=detail)
            metadata["attempt"] = asset["attempt"]
            _write_attempt_metadata(cache_root, asset, metadata)
            save_diagnostic_ledger(cache_root, ledger)
            return _failure_result(ledger, asset, "validation_error", detail)

        comparison = compare_pair_populations(full_season_base_payloads[team_id], payload)
        asset["status"] = "verified"
        asset["comparison"] = comparison
        asset["attempt"].update(status="verified", completed_at=utc_now())
        metadata.update(
            {
                "attempt": asset["attempt"],
                "validation": validation,
                "comparison": comparison,
            }
        )
        _write_attempt_metadata(cache_root, asset, metadata)
        save_diagnostic_ledger(cache_root, ledger)
        if comparison["classification"] == "proven_non_exhaustive":
            return {
                "completed": True,
                "stopped_early": True,
                "stop_category": "conclusive_non_exhaustiveness",
                "attempted": sum(item["attempt_count"] for item in ledger["assets"]),
                "verified": sum(
                    item["status"] in {"verified", "verified_after_offline_revalidation"}
                    for item in ledger["assets"]
                ),
                "failed": 0,
                "classification": "proven_non_exhaustive",
                "conclusive_asset_id": asset["asset_id"],
                "comparison": comparison,
                "diagnostic_isolation": isolation,
            }

    return {
        "completed": True,
        "stopped_early": False,
        "stop_category": None,
        "attempted": sum(item["attempt_count"] for item in ledger["assets"]),
        "verified": sum(
            item["status"] in {"verified", "verified_after_offline_revalidation"}
            for item in ledger["assets"]
        ),
        "failed": 0,
        "classification": "not_proven_exhaustive",
        "conclusive_asset_id": None,
        "diagnostic_isolation": isolation,
    }


def replay_authorized_diagnostics(
    cache_root: Path,
    *,
    phase1c_manifest: Mapping[str, Any],
    full_season_base_payloads: Mapping[str, Mapping[str, Any]],
    approved_base_schema: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Replay persisted diagnostics.  This function has no transport argument."""
    return run_authorized_diagnostics(
        cache_root,
        phase1c_manifest=phase1c_manifest,
        full_season_base_payloads=full_season_base_payloads,
        approved_base_schema=approved_base_schema,
        live_acquisition=False,
    )


def revalidate_stopped_identity_normalization(
    cache_root: Path,
    *,
    phase1c_manifest: Mapping[str, Any],
    full_season_base_payloads: Mapping[str, Mapping[str, Any]],
    approved_base_schema: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Offline-only correction for the PORound empty-to-zero response echo.

    The function accepts only the first stopped validation-error asset, requires
    that later requests remain untouched, validates the already-cached immutable
    response, and preserves the original failed attempt record.  It has no
    transport argument and cannot advance the authorized request sequence.
    """
    ledger = load_or_create_diagnostic_ledger(cache_root)
    validate_diagnostic_isolation(ledger, phase1c_manifest)
    first, *later = ledger["assets"]
    if first.get("status") != "failed" or first.get("attempt_count") != 1:
        raise ValueError("Offline revalidation requires one stopped first diagnostic")
    attempt = first.get("attempt") or {}
    if attempt.get("error_category") != "validation_error" or "PORound" not in str(
        attempt.get("error_detail")
    ):
        raise ValueError("Stopped diagnostic is not the approved PORound normalization case")
    if any(asset.get("status") != "planned" or asset.get("attempt_count") != 0 for asset in later):
        raise ValueError("Offline revalidation refuses a ledger that advanced after Request 1")
    payload, validation = _verify_cached_diagnostic(cache_root, first, approved_base_schema)
    team_id = first["identity"]["parameters"]["team_id"]
    comparison = compare_pair_populations(full_season_base_payloads[team_id], payload)
    correction = {
        "performed_at": utc_now(),
        "kind": "offline_identity_normalization_correction",
        "no_live_request": True,
        "did_not_advance_sequence": True,
        "original_attempt_status_preserved": attempt.get("status"),
        "original_error_category": attempt.get("error_category"),
        "normalization": "PORound request empty sentinel is equivalent to response numeric zero",
        "validation": validation,
        "comparison": comparison,
    }
    first["status"] = "verified_after_offline_revalidation"
    first["comparison"] = comparison
    first["offline_revalidation"] = correction
    metadata_path = cache_root / first["cache"]["metadata_relative_path"]
    metadata = read_json(metadata_path)
    metadata["offline_revalidation"] = correction
    atomic_write_json(metadata_path, metadata)
    save_diagnostic_ledger(cache_root, ledger)
    return {
        "classification": comparison["classification"],
        "asset_id": first["asset_id"],
        "attempt_count": 1,
        "additional_live_requests": 0,
        "later_requests_untouched": True,
        "original_attempt": attempt,
        "comparison": comparison,
    }
