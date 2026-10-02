"""Offline-only Phase 3F-R2B.1 response-contract specification builder.

This module reads historical TeamDashLineups evidence and the one preserved
Phase 3F-R2B Atlanta Base response.  It has no transport, final-test, feature,
preprocessing, estimator, prediction, metric, or model-serialization capability.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


VERSION = "phase3f-r2b.1.response-contract.v1"
CLASSIFICATION = (
    "PASS — Phase 3F-R2B.1 corrected response contract frozen; "
    "ready for read-only audit"
)
EXPECTED_HEAD = "dd740e39cce03a3ab0f52f5be1067c47bb510db5"
EXPECTED_AUTHORIZATION_SHA256 = (
    "12249e6acca554507501e887c9afeb4f3cad0079fb40ab2738bea3d308ade856"
)
ATLANTA_REQUEST_ID = "teamdashlineups:1610612737:base"
ATLANTA_IDENTITY_SHA256 = (
    "9809de72e3a017b700ce2059a77b9ba31128cb467f2e9fde516119f6230bf64b"
)
ATLANTA_RAW_BYTES = 51_905
ATLANTA_RAW_SHA256 = "e2134b18de903b79b1bcce8d628cf041ae18a50ccab00018d3b29b7daa63aff0"
ATLANTA_CANONICAL_SHA256 = (
    "bac19c1df5f1a25de0e558c62410457917bb25ffb9130833e346444ae8c30f8d"
)
ATLANTA_SLUG = "1610612737-01-base"
R2B_PLANNING = Path("planning/phase3f-r2b")
R2B_EVIDENCE = Path("cache/phase3f-r2b/protected-final-target")
HISTORICAL_MANIFEST = Path(
    "cache/phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"
)
HISTORICAL_MANIFEST_SHA256 = (
    "5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c"
)
OUTPUT_FILES = (
    "response_contract.json",
    "continuation_plan.json",
    "input_fingerprints.json",
    "summary.json",
    "artifact_hashes.json",
)

R2B_COMMITTED_HASHES = {
    "PHASE3F_R2B_PROTECTED_PAIR_ACQUISITION_POLICY.md":
        "013dceee4e7f2aa103179daebf042bd07280cdb1a9a6eb707e8a80c0c770f3a5",
    "PHASE3F_R2B_PROTECTED_PAIR_ACQUISITION_REPORT.md":
        "074adb84e538d0036a398ec3d5b888029ecd65d0f60b49255838813db981a3f6",
    "src/pair_fit_v2/phase3f_r2b_protected_pair_acquisition.py":
        "f39da68f790db55edd31eb16875d6c856042e7bcd8d8cd8d3c67b93b93b9917d",
    "src/pair_fit_v2/phase3f_r2b_cli.py":
        "b53708945de80dc7ae2294e4ce6e6ceb8f8999503bb183e182debab5481405f4",
    "tests/test_phase3f_r2b_protected_pair_acquisition.py":
        "91eb5774027d331e3d8b145631a4de24195636e37334e572ef2fd14c728c0ff4",
}

R2B_RECORDS = {
    "planning/phase3f-r2b/authorization.json": (
        71_656,
        EXPECTED_AUTHORIZATION_SHA256,
    ),
    "planning/phase3f-r2b/official_invocation.json": (
        935,
        "936708826bbfaf729a1ad8c9ed7dcbbf2e8bce13b11e3e9a08403fe665b524fe",
    ),
    f"cache/phase3f-r2b/protected-final-target/{ATLANTA_SLUG}/attempt-1-start.json": (
        281,
        "90553e18945c075aa285207d01821266930d3e9fcb79b84b9386b82bf741f9c9",
    ),
    f"cache/phase3f-r2b/protected-final-target/{ATLANTA_SLUG}/attempt-1-response.bin": (
        ATLANTA_RAW_BYTES,
        ATLANTA_RAW_SHA256,
    ),
    f"cache/phase3f-r2b/protected-final-target/{ATLANTA_SLUG}/attempt-1-outcome.json": (
        594,
        "c799c52fbb449c126edb669d5abcf003ae3703895f2734a7bd0d2a1c6db6d9cf",
    ),
    f"cache/phase3f-r2b/protected-final-target/{ATLANTA_SLUG}/quarantine.json": (
        346,
        "affc98a8a1cba3158764085cc5811977c31f4a088f9dda5a412b65004f97986f",
    ),
}

BASE_OVERALL_HEADERS = (
    "GROUP_SET", "GROUP_VALUE", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME",
    "GP", "W", "L", "W_PCT", "MIN", "FGM", "FGA", "FG_PCT", "FG3M",
    "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB",
    "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS",
    "GP_RANK", "W_RANK", "L_RANK", "W_PCT_RANK", "MIN_RANK", "FGM_RANK",
    "FGA_RANK", "FG_PCT_RANK", "FG3M_RANK", "FG3A_RANK", "FG3_PCT_RANK",
    "FTM_RANK", "FTA_RANK", "FT_PCT_RANK", "OREB_RANK", "DREB_RANK",
    "REB_RANK", "AST_RANK", "TOV_RANK", "STL_RANK", "BLK_RANK",
    "BLKA_RANK", "PF_RANK", "PFD_RANK", "PTS_RANK", "PLUS_MINUS_RANK",
)
BASE_LINEUPS_HEADERS = (
    "GROUP_SET", "GROUP_ID", "GROUP_NAME", "GP", "W", "L", "W_PCT", "MIN",
    "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA",
    "FT_PCT", "OREB", "DREB", "REB", "AST", "TOV", "STL", "BLK", "BLKA",
    "PF", "PFD", "PTS", "PLUS_MINUS", "GP_RANK", "W_RANK", "L_RANK",
    "W_PCT_RANK", "MIN_RANK", "FGM_RANK", "FGA_RANK", "FG_PCT_RANK",
    "FG3M_RANK", "FG3A_RANK", "FG3_PCT_RANK", "FTM_RANK", "FTA_RANK",
    "FT_PCT_RANK", "OREB_RANK", "DREB_RANK", "REB_RANK", "AST_RANK",
    "TOV_RANK", "STL_RANK", "BLK_RANK", "BLKA_RANK", "PF_RANK", "PFD_RANK",
    "PTS_RANK", "PLUS_MINUS_RANK", "SUM_TIME_PLAYED",
)
ADVANCED_OVERALL_HEADERS = (
    "GROUP_SET", "GROUP_VALUE", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME",
    "GP", "W", "L", "W_PCT", "MIN", "E_OFF_RATING", "OFF_RATING",
    "E_DEF_RATING", "DEF_RATING", "E_NET_RATING", "NET_RATING", "AST_PCT",
    "AST_TO", "AST_RATIO", "OREB_PCT", "DREB_PCT", "REB_PCT", "TM_TOV_PCT",
    "EFG_PCT", "TS_PCT", "E_PACE", "PACE", "PACE_PER40", "POSS", "PIE",
    "GP_RANK", "W_RANK", "L_RANK", "W_PCT_RANK", "MIN_RANK",
    "OFF_RATING_RANK", "DEF_RATING_RANK", "NET_RATING_RANK", "AST_PCT_RANK",
    "AST_TO_RANK", "AST_RATIO_RANK", "OREB_PCT_RANK", "DREB_PCT_RANK",
    "REB_PCT_RANK", "TM_TOV_PCT_RANK", "EFG_PCT_RANK", "TS_PCT_RANK",
    "PACE_RANK", "PIE_RANK",
)
ADVANCED_LINEUPS_HEADERS = (
    "GROUP_SET", "GROUP_ID", "GROUP_NAME", "GP", "W", "L", "W_PCT", "MIN",
    "E_OFF_RATING", "OFF_RATING", "E_DEF_RATING", "DEF_RATING", "E_NET_RATING",
    "NET_RATING", "AST_PCT", "AST_TO", "AST_RATIO", "OREB_PCT", "DREB_PCT",
    "REB_PCT", "TM_TOV_PCT", "EFG_PCT", "TS_PCT", "E_PACE", "PACE",
    "PACE_PER40", "POSS", "PIE", "GP_RANK", "W_RANK", "L_RANK",
    "W_PCT_RANK", "MIN_RANK", "OFF_RATING_RANK", "DEF_RATING_RANK",
    "NET_RATING_RANK", "AST_PCT_RANK", "AST_TO_RANK", "AST_RATIO_RANK",
    "OREB_PCT_RANK", "DREB_PCT_RANK", "REB_PCT_RANK", "TM_TOV_PCT_RANK",
    "EFG_PCT_RANK", "TS_PCT_RANK", "PACE_RANK", "PIE_RANK", "SUM_TIME_PLAYED",
)
SCHEMAS = {
    "Base": {"Overall": BASE_OVERALL_HEADERS, "Lineups": BASE_LINEUPS_HEADERS},
    "Advanced": {
        "Overall": ADVANCED_OVERALL_HEADERS,
        "Lineups": ADVANCED_LINEUPS_HEADERS,
    },
}
PAIR_PATTERN = re.compile(r"^-([1-9][0-9]*)-([1-9][0-9]*)-$")


class ContractError(RuntimeError):
    """Raised when a frozen input or response violates the correction contract."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def historical_canonical_json_bytes(value: Any) -> bytes:
    """Reproduce the earlier Phase 1C canonical-hash serialization exactly."""

    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_json_bytes(value: bytes) -> Any:
    def reject_constant(token: str) -> None:
        raise ValueError(f"non-standard JSON constant: {token}")

    return json.loads(value.decode("utf-8", errors="strict"), parse_constant=reject_constant)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _read_json(path: Path) -> Any:
    return strict_json_bytes(_read_bytes(path))


def _fingerprint(path: Path) -> dict[str, Any]:
    body = _read_bytes(path)
    return {"bytes": len(body), "sha256": sha256_bytes(body)}


def _positive_id(value: Any, label: str) -> str:
    if isinstance(value, bool):
        raise ContractError(f"{label} is not a positive numeric ID")
    text = str(value)
    if not re.fullmatch(r"[1-9][0-9]*", text):
        raise ContractError(f"{label} is not a positive numeric ID")
    return text


def canonical_pair(group_id: Any) -> tuple[str, str]:
    if not isinstance(group_id, str):
        raise ContractError("malformed group identifier")
    match = PAIR_PATTERN.fullmatch(group_id)
    if match is None:
        raise ContractError("malformed group identifier")
    left, right = match.groups()
    if left == right:
        raise ContractError("same-player pair")
    return tuple(sorted((left, right), key=int))


def _finite_number(value: Any, label: str, *, nonnegative: bool) -> float:
    if value is None or isinstance(value, bool):
        raise ContractError(f"{label} must be numeric and finite")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{label} must be numeric and finite") from exc
    if not math.isfinite(number):
        raise ContractError(f"{label} must be numeric and finite")
    if nonnegative and number < 0:
        raise ContractError(f"{label} must be nonnegative")
    return number


def _request_identity(request: Mapping[str, Any]) -> str:
    value = {"endpoint": request.get("endpoint"), "parameters": request.get("parameters")}
    return sha256_bytes(canonical_json_bytes(value))


def validate_response_contract(
    body: bytes,
    request: Mapping[str, Any],
    *,
    enforce_established_order: bool = True,
) -> dict[str, Any]:
    """Validate one response offline and return row-free structural diagnostics."""

    parameters = request.get("parameters")
    if request.get("endpoint") != "teamdashlineups" or not isinstance(parameters, Mapping):
        raise ContractError("invalid authorized request identity")
    measure = parameters.get("MeasureType")
    if measure not in SCHEMAS:
        raise ContractError("unsupported measure type")
    requested_team = _positive_id(parameters.get("TeamID"), "request TeamID")
    try:
        payload = strict_json_bytes(body)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ContractError(f"invalid strict JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ContractError("response must be a JSON object")
    if payload.get("resource") not in (None, "teamdashlineups"):
        raise ContractError("unexpected response resource")
    result_sets = payload.get("resultSets")
    if not isinstance(result_sets, list) or len(result_sets) != 2:
        raise ContractError("response must contain exactly Overall and Lineups")

    names: list[str] = []
    selected: dict[str, Mapping[str, Any]] = {}
    for result in result_sets:
        if not isinstance(result, Mapping):
            raise ContractError("malformed result-set object")
        name = result.get("name")
        if not isinstance(name, str):
            raise ContractError("result-set name must be a string")
        if name in selected:
            raise ContractError("duplicate result-set name")
        names.append(name)
        selected[name] = result
    if set(names) != {"Overall", "Lineups"}:
        missing = sorted({"Overall", "Lineups"} - set(names))
        unexpected = sorted(set(names) - {"Overall", "Lineups"})
        raise ContractError(f"result-set membership mismatch: missing={missing}, unexpected={unexpected}")
    if enforce_established_order and names != ["Overall", "Lineups"]:
        raise ContractError("result-set order must be Overall then Lineups")

    rows_by_name: dict[str, list[dict[str, Any]]] = {}
    headers_by_name: dict[str, list[str]] = {}
    for name in ("Overall", "Lineups"):
        result = selected[name]
        headers = result.get("headers")
        raw_rows = result.get("rowSet")
        if (
            not isinstance(headers, list)
            or not all(isinstance(item, str) for item in headers)
            or len(headers) != len(set(headers))
            or not isinstance(raw_rows, list)
        ):
            raise ContractError(f"malformed {name} headers or rows")
        expected_headers = list(SCHEMAS[measure][name])
        if headers != expected_headers:
            raise ContractError(f"{measure} {name} schema differs from the exact frozen schema")
        rows: list[dict[str, Any]] = []
        for index, raw_row in enumerate(raw_rows):
            if not isinstance(raw_row, list) or len(raw_row) != len(headers):
                raise ContractError(f"{name} row-width mismatch at index {index}")
            rows.append(dict(zip(headers, raw_row)))
        rows_by_name[name] = rows
        headers_by_name[name] = headers

    overall_rows = rows_by_name["Overall"]
    if len(overall_rows) != 1:
        raise ContractError("Overall must contain exactly one team-context row")
    overall = overall_rows[0]
    if overall.get("GROUP_SET") != "Overall":
        raise ContractError("Overall team-context GROUP_SET mismatch")
    if "Season" in parameters and str(overall.get("GROUP_VALUE")) != str(parameters["Season"]):
        raise ContractError("Overall team-context season mismatch")

    team_sources = {"authorized_request": requested_team}
    returned_parameters = payload.get("parameters")
    if returned_parameters is not None:
        if not isinstance(returned_parameters, Mapping) or "TeamID" not in returned_parameters:
            raise ContractError("returned parameters lack a valid TeamID")
        team_sources["returned_parameters"] = _positive_id(
            returned_parameters["TeamID"], "returned-parameter TeamID"
        )
    team_sources["overall_row"] = _positive_id(overall.get("TEAM_ID"), "Overall TEAM_ID")
    if len(set(team_sources.values())) != 1:
        raise ContractError("team identity mismatch across response context")

    lineup_rows = rows_by_name["Lineups"]
    pair_keys: list[tuple[str, str]] = []
    for row in lineup_rows:
        pair_keys.append(canonical_pair(row.get("GROUP_ID")))
        if measure == "Base":
            _finite_number(row.get("MIN"), "Base MIN", nonnegative=True)
            _finite_number(
                row.get("SUM_TIME_PLAYED"), "Base SUM_TIME_PLAYED", nonnegative=True
            )
        else:
            _finite_number(row.get("POSS"), "Advanced POSS", nonnegative=True)
            _finite_number(row.get("NET_RATING"), "Advanced NET_RATING", nonnegative=False)
    duplicate_pairs = sum(value - 1 for value in Counter(pair_keys).values() if value > 1)
    if duplicate_pairs:
        raise ContractError("duplicate canonical unordered pair")

    return {
        "strict_json_valid": True,
        "request_id": request.get("request_id"),
        "canonical_request_identity_sha256": _request_identity(request),
        "measure": measure,
        "observed_result_set_order": names,
        "overall_header_count": len(headers_by_name["Overall"]),
        "overall_row_count": len(overall_rows),
        "lineups_header_count": len(headers_by_name["Lineups"]),
        "lineups_row_count": len(lineup_rows),
        "row_width_error_count": 0,
        "unique_result_set_names": True,
        "canonical_unordered_pair_count": len(pair_keys),
        "duplicate_canonical_pair_count": 0,
        "malformed_group_identifier_count": 0,
        "same_player_pair_count": 0,
        "invalid_player_id_count": 0,
        "exact_250": len(lineup_rows) == 250,
        "team_context": team_sources,
        "lineup_team_id_required": False,
        "base_poss_absent_as_expected": (
            measure == "Base" and "POSS" not in headers_by_name["Lineups"]
        ),
        "compatible": True,
    }


def _git_head(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _verify_exact_file(path: Path, expected_bytes: int, expected_sha256: str) -> dict[str, Any]:
    observed = _fingerprint(path)
    if observed != {"bytes": expected_bytes, "sha256": expected_sha256}:
        raise ContractError(f"frozen input mismatch: {path.as_posix()}")
    return observed


def _validate_preserved_r2b(project_root: Path) -> dict[str, Any]:
    planning = project_root / R2B_PLANNING
    evidence = project_root / R2B_EVIDENCE
    if sorted(item.name for item in planning.iterdir()) != [
        "authorization.json", "official_invocation.json"
    ]:
        raise ContractError("failed R2B planning namespace changed")
    evidence_entries = list(evidence.iterdir())
    if len(evidence_entries) != 1 or evidence_entries[0].name != ATLANTA_SLUG:
        raise ContractError("additional or missing protected request identity")
    atlanta_dir = evidence_entries[0]
    if not atlanta_dir.is_dir() or sorted(item.name for item in atlanta_dir.iterdir()) != [
        "attempt-1-outcome.json",
        "attempt-1-response.bin",
        "attempt-1-start.json",
        "quarantine.json",
    ]:
        raise ContractError("failed Atlanta record inventory changed")

    records = {}
    for relative, (expected_bytes, expected_hash) in R2B_RECORDS.items():
        observed = _verify_exact_file(project_root / relative, expected_bytes, expected_hash)
        records[relative] = observed

    authorization = _read_json(planning / "authorization.json")
    invocation = _read_json(planning / "official_invocation.json")
    start = _read_json(atlanta_dir / "attempt-1-start.json")
    outcome = _read_json(atlanta_dir / "attempt-1-outcome.json")
    quarantine = _read_json(atlanta_dir / "quarantine.json")
    requests = authorization.get("authorized_requests")
    if not isinstance(requests, list) or len(requests) != 60:
        raise ContractError("R2B authorization request inventory changed")
    if [item.get("ordinal") for item in requests] != list(range(1, 61)):
        raise ContractError("R2B authorization ordinals changed")
    if requests[0].get("request_id") != ATLANTA_REQUEST_ID:
        raise ContractError("Atlanta request identity changed")
    if requests[0].get("canonical_identity_sha256") != ATLANTA_IDENTITY_SHA256:
        raise ContractError("Atlanta canonical request identity changed")
    if invocation.get("invocation_number") != 1:
        raise ContractError("official invocation count changed")
    if invocation.get("authorization_sha256") != EXPECTED_AUTHORIZATION_SHA256:
        raise ContractError("official invocation authorization link changed")
    for record in (start, outcome, quarantine):
        if record.get("request_id") != ATLANTA_REQUEST_ID or record.get("attempt_number") != 1:
            raise ContractError("Atlanta attempt record identity changed")
    if outcome.get("state") != "failed_or_quarantined" or quarantine.get("state") != "failed_or_quarantined":
        raise ContractError("original R2B failure classification changed")
    if outcome.get("automatic_retries") != 0:
        raise ContractError("original R2B retry count changed")
    if (atlanta_dir / "verified-response.bin").exists() or (atlanta_dir / "verification.json").exists():
        raise ContractError("Atlanta response was promoted or verified in the failed namespace")

    expected_inputs = authorization.get("input_fingerprints")
    if not isinstance(expected_inputs, Mapping):
        raise ContractError("R2B pinned input inventory missing")
    pinned_inputs = {}
    for relative, expected in sorted(expected_inputs.items()):
        observed = _fingerprint(project_root / relative)
        if observed != expected:
            raise ContractError(f"earlier pinned input changed: {relative}")
        pinned_inputs[relative] = observed

    response = _read_bytes(atlanta_dir / "attempt-1-response.bin")
    payload = strict_json_bytes(response)
    if sha256_bytes(canonical_json_bytes(payload)) != ATLANTA_CANONICAL_SHA256:
        raise ContractError("Atlanta canonical JSON hash changed")
    compatibility = validate_response_contract(response, requests[0])
    if compatibility["canonical_request_identity_sha256"] != ATLANTA_IDENTITY_SHA256:
        raise ContractError("Atlanta request identity calculation changed")
    return {
        "authorization": authorization,
        "authorized_requests": requests,
        "record_fingerprints": records,
        "pinned_inputs": pinned_inputs,
        "atlanta_compatibility": compatibility,
    }


def _validate_committed_r2b(project_root: Path) -> dict[str, Any]:
    output = {}
    for relative, expected_hash in sorted(R2B_COMMITTED_HASHES.items()):
        observed = _fingerprint(project_root / relative)
        if observed["sha256"] != expected_hash:
            raise ContractError(f"committed R2B checkpoint changed: {relative}")
        output[relative] = observed
    return output


def _historical_request(asset: Mapping[str, Any]) -> dict[str, Any]:
    parameters = asset["identity"]["parameters"]
    return {
        "request_id": asset["asset_id"],
        "endpoint": "teamdashlineups",
        "parameters": {
            "TeamID": parameters["team_id"],
            "MeasureType": parameters["measure_type"],
            "Season": parameters["season"],
        },
    }


def _validate_historical_2024_25(project_root: Path) -> dict[str, Any]:
    manifest_path = project_root / HISTORICAL_MANIFEST
    manifest_fp = _fingerprint(manifest_path)
    if manifest_fp["sha256"] != HISTORICAL_MANIFEST_SHA256:
        raise ContractError("historical 2024-25 manifest changed")
    manifest = _read_json(manifest_path)
    assets = manifest.get("raw_assets")
    if not isinstance(assets, list) or len(assets) != 60:
        raise ContractError("historical manifest does not contain 60 responses")
    if any(asset.get("status") != "verified" for asset in assets):
        raise ContractError("historical response is not verified")

    response_fingerprints = []
    measure_counts = Counter()
    order_counts = Counter()
    row_width_error_count = 0
    for asset in assets:
        relative = asset["cache"]["relative_path"]
        path = project_root / "cache" / relative
        body = _read_bytes(path)
        expected_bytes = asset["cache"]["cache_file_bytes"]
        if len(body) != expected_bytes:
            raise ContractError(f"historical response byte count changed: {relative}")
        payload = strict_json_bytes(body)
        if sha256_bytes(historical_canonical_json_bytes(payload)) != asset["cache"]["canonical_json_hash"]:
            raise ContractError(f"historical response canonical hash changed: {relative}")
        diagnostic = validate_response_contract(body, _historical_request(asset))
        measure_counts[diagnostic["measure"]] += 1
        order_counts[tuple(diagnostic["observed_result_set_order"])] += 1
        row_width_error_count += diagnostic["row_width_error_count"]
        response_fingerprints.append(
            {
                "path": f"cache/{relative}",
                "bytes": len(body),
                "sha256": sha256_bytes(body),
                "canonical_json_sha256": asset["cache"]["canonical_json_hash"],
                "measure": diagnostic["measure"],
            }
        )
    response_fingerprints.sort(key=lambda item: item["path"])
    if measure_counts != Counter({"Base": 30, "Advanced": 30}):
        raise ContractError("historical Base/Advanced response counts changed")
    if order_counts != Counter({("Overall", "Lineups"): 60}):
        raise ContractError("historical result-set ordering is not stable")
    return {
        "manifest": manifest_fp,
        "response_count": 60,
        "measure_counts": dict(sorted(measure_counts.items())),
        "result_set_order_counts": {"Overall,Lineups": 60},
        "row_width_error_count": row_width_error_count,
        "responses": response_fingerprints,
        "response_inventory_sha256": sha256_bytes(canonical_json_bytes(response_fingerprints)),
    }


def _schema_record(measure: str, name: str) -> dict[str, Any]:
    headers = list(SCHEMAS[measure][name])
    required = ["GROUP_SET"]
    if name == "Overall":
        required += ["GROUP_VALUE", "TEAM_ID"]
    elif measure == "Base":
        required += ["GROUP_ID", "MIN", "SUM_TIME_PLAYED"]
    else:
        required += ["GROUP_ID", "POSS", "NET_RATING"]
    return {
        "headers": headers,
        "ordered_header_sha256": sha256_bytes(canonical_json_bytes(headers)),
        "column_count": len(headers),
        "required_fields": required,
        "schema_rule": "exact ordered equality",
        "row_width_rule": "every row width equals the exact header count",
    }


def _response_contract(atlanta: Mapping[str, Any]) -> dict[str, Any]:
    core = {
        "version": VERSION,
        "phase": "Phase 3F-R2B.1 — Protected Response-Contract Correction Specification",
        "classification": CLASSIFICATION,
        "permanent_historical_status": {
            "original_r2b": "FAILED — authorized protected acquisition attempt failed",
            "quarantine_historically_correct_under_then_frozen_implementation": True,
            "r2b_1_rewrites_or_repairs_failed_execution": False,
            "atlanta_base_is_permanently_attempted": True,
            "atlanta_base_future_network_attempt_allowed": False,
            "future_offline_revalidation_of_original_bytes_may_be_separately_authorized": True,
            "remaining_identity_ordinals": {"first": 2, "last": 60, "count": 59},
        },
        "evidence_basis": {
            "verified_2024_25_full_season_responses_compared": 60,
            "base_responses": 30,
            "advanced_responses": 30,
            "all_observed_result_set_orders": ["Overall", "Lineups"],
            "all_four_ordered_schemas_identical_within_measure_and_set": True,
            "atlanta_base_matches_historical_base_schemas_exactly": True,
            "schema_decision": "exact ordered header equality",
            "ordering_decision": "require Overall then Lineups",
            "decision_reason": (
                "all 60 verified 2024-25 responses and the preserved Atlanta Base response "
                "use the same order; exact schemas were stable across all 30 responses per measure"
            ),
        },
        "corrections": {
            "response_envelope": {
                "exact_unique_names": ["Overall", "Lineups"],
                "exact_order": ["Overall", "Lineups"],
                "reject_missing_duplicate_or_unexpected_names": True,
                "reject_malformed_result_set_objects": True,
                "unique_string_headers_required": True,
                "row_width_equality_required_for_both_sets": True,
                "overall_row_count": 1,
            },
            "named_selection": {
                "select_overall_by_exact_name": True,
                "select_lineups_by_exact_name": True,
                "positional_selection_prohibited": True,
                "pair_rows_source": "uniquely named Lineups result set only",
            },
            "measure_specific_field_ownership": {
                "Base": {
                    "canonical_pair_identity": "GROUP_ID",
                    "exposure_time_fields": ["MIN", "SUM_TIME_PLAYED"],
                    "POSS_owned": False,
                    "NET_RATING_target_owned": False,
                    "absence_of_POSS_is_valid": True,
                },
                "Advanced": {
                    "canonical_pair_identity": "GROUP_ID",
                    "eligibility_field": "POSS",
                    "target_field": "NET_RATING",
                    "POSS_validation": "numeric, finite, nonnegative",
                    "NET_RATING_validation": "numeric and finite",
                },
            },
            "team_identity_location": {
                "sources": [
                    "authorized request parameters TeamID",
                    "returned response parameters TeamID when parameters are present",
                    "singleton Overall row TEAM_ID",
                ],
                "all_available_sources_must_agree": True,
                "lineups_row_TEAM_ID_required": False,
                "infer_from_player_names": False,
                "inject_into_raw_lineup_rows": False,
                "later_team_provenance_source": "validated response context only",
            },
        },
        "schemas": {
            measure: {name: _schema_record(measure, name) for name in ("Overall", "Lineups")}
            for measure in ("Base", "Advanced")
        },
        "pair_contract": {
            "source_set": "Lineups selected by exact name",
            "group_identifier_pattern": "^-([1-9][0-9]*)-([1-9][0-9]*)-$",
            "canonical_key": "two positive numeric player IDs ordered by numeric value",
            "malformed_same_player_and_duplicate_pairs_rejected": True,
        },
        "atlanta_offline_compatibility": dict(atlanta),
        "future_reconciliation_contract": {
            "select_both_measure_lineups_by_name": True,
            "team_context_source": "validated envelope identity",
            "canonical_unordered_pair_key": "numeric player-ID ordering",
            "base_and_advanced_pair_key_sets_must_match": True,
            "zero_exposure_rows_remain_visible": True,
            "eligibility_source": "Advanced POSS >= 150",
            "target_source": "Advanced NET_RATING",
            "exact_250_disposition": "unresolved; neither automatically complete nor incomplete",
            "approximate_rating_reconstruction": False,
            "selective_pair_deletion": False,
            "demonstrated_non_exhaustiveness_policy": "whole-team exclusion without direct recovery",
            "constructs_final_test_population": False,
        },
        "authorization_boundaries": {
            "network_request_authorized": False,
            "recovery_window_authorized": False,
            "final_test_construction_authorized": False,
            "prior_profile_join_authorized": False,
            "preprocessing_authorized": False,
            "model_operation_authorized": False,
        },
    }
    contract_digest = sha256_bytes(canonical_json_bytes(core))
    return {**core, "correction_contract_identity": f"sha256:{contract_digest}"}


def _continuation_plan(
    contract_identity: str,
    requests: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    remaining = []
    for request in requests[1:]:
        remaining.append(
            {
                "ordinal": request["ordinal"],
                "request_id": request["request_id"],
                "canonical_identity_sha256": request["canonical_identity_sha256"],
                "endpoint": request["endpoint"],
                "parameters": request["parameters"],
                "currently_network_authorized": False,
                "may_become_eligible_only_in_later_separately_authorized_phase": True,
            }
        )
    return {
        "version": VERSION,
        "plan_kind": "non-executable correction-only continuation specification",
        "correction_contract_identity": contract_identity,
        "contains_executable_network_authorization": False,
        "original_namespace_immutable": R2B_EVIDENCE.as_posix() + "/",
        "future_namespace_must_be_new": True,
        "atlanta_base": {
            "ordinal": 1,
            "request_id": ATLANTA_REQUEST_ID,
            "canonical_identity_sha256": ATLANTA_IDENTITY_SHA256,
            "attempt_number": 1,
            "original_raw_path": (
                f"{R2B_EVIDENCE.as_posix()}/{ATLANTA_SLUG}/attempt-1-response.bin"
            ),
            "raw_sha256": ATLANTA_RAW_SHA256,
            "canonical_json_sha256": ATLANTA_CANONICAL_SHA256,
            "original_quarantine_path": (
                f"{R2B_EVIDENCE.as_posix()}/{ATLANTA_SLUG}/quarantine.json"
            ),
            "correction_contract_identity": contract_identity,
            "future_disposition_method": "offline revalidation of original bytes only",
            "network_eligible": False,
            "second_attempt_allowed": False,
        },
        "remaining_requests": remaining,
        "remaining_request_count": len(remaining),
        "remaining_ordinal_range": [2, 60],
        "rules": {
            "preserve_original_request_id_ordinal_and_exact_parameters": True,
            "attempt_limit_per_remaining_identity": 1,
            "automatic_retries": 0,
            "manual_retries": 0,
            "fail_stop": True,
            "future_transport_failure_stops_continuation": True,
            "recovery_windows_authorized": False,
            "final_test_construction_authorized": False,
            "modeling_authorized": False,
        },
    }


def _input_fingerprints(
    preserved: Mapping[str, Any],
    committed: Mapping[str, Any],
    historical: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "version": VERSION,
        "required_committed_head": EXPECTED_HEAD,
        "earlier_r0_r0_1_r1s_r2a_pinned_inputs": preserved["pinned_inputs"],
        "earlier_pinned_input_count": len(preserved["pinned_inputs"]),
        "committed_r2b_checkpoint": committed,
        "failed_r2b_records": preserved["record_fingerprints"],
        "historical_2024_25_manifest": historical["manifest"],
        "historical_2024_25_response_count": historical["response_count"],
        "historical_2024_25_response_inventory_sha256": historical[
            "response_inventory_sha256"
        ],
        "historical_2024_25_responses": historical["responses"],
        "atlanta_response": {
            "bytes": ATLANTA_RAW_BYTES,
            "raw_sha256": ATLANTA_RAW_SHA256,
            "canonical_json_sha256": ATLANTA_CANONICAL_SHA256,
        },
    }


def _summary(contract: Mapping[str, Any], historical: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "phase": "Phase 3F-R2B.1",
        "classification": CLASSIFICATION,
        "correction_contract_identity": contract["correction_contract_identity"],
        "specification_only": True,
        "original_r2b_status": "FAILED — authorized protected acquisition attempt failed",
        "failed_namespace_unchanged": True,
        "atlanta_offline_compatible": True,
        "atlanta_remains_quarantined": True,
        "atlanta_network_reacquisition_allowed": False,
        "remaining_future_candidate_count": 59,
        "historical_responses_compared": historical["response_count"],
        "historical_schema_mismatch_count": 0,
        "generated_file_inventory": list(OUTPUT_FILES),
        "network_requests": 0,
        "additional_2025_26_responses_opened": 0,
        "final_test_rows_constructed": 0,
        "model_operations": 0,
        "ready_for": "read-only audit only",
    }


def build_specification(project_root: Path, output_dir: Path) -> dict[str, Any]:
    """Build the five deterministic, write-once specification artifacts."""

    root = Path(project_root).resolve()
    destination = Path(output_dir)
    if not destination.is_absolute():
        destination = (root / destination).resolve()
    if destination.exists():
        raise ContractError(f"write-once specification namespace already exists: {destination}")
    if _git_head(root) != EXPECTED_HEAD:
        raise ContractError("committed HEAD differs from the required R2B checkpoint")

    committed = _validate_committed_r2b(root)
    preserved = _validate_preserved_r2b(root)
    historical = _validate_historical_2024_25(root)
    contract = _response_contract(preserved["atlanta_compatibility"])
    continuation = _continuation_plan(
        contract["correction_contract_identity"], preserved["authorized_requests"]
    )
    inputs = _input_fingerprints(preserved, committed, historical)
    summary = _summary(contract, historical)
    documents = {
        "response_contract.json": contract,
        "continuation_plan.json": continuation,
        "input_fingerprints.json": inputs,
        "summary.json": summary,
    }
    serialized = {name: serialize_json(value) for name, value in documents.items()}
    artifact_hashes = {
        "version": VERSION,
        "hash_algorithm": "SHA-256 over exact artifact bytes",
        "artifacts": {
            name: {"bytes": len(body), "sha256": sha256_bytes(body)}
            for name, body in sorted(serialized.items())
        },
    }
    serialized["artifact_hashes.json"] = serialize_json(artifact_hashes)

    destination.mkdir(parents=True, exist_ok=False)
    for name in OUTPUT_FILES:
        with (destination / name).open("xb") as handle:
            handle.write(serialized[name])
    return {
        "classification": CLASSIFICATION,
        "correction_contract_identity": contract["correction_contract_identity"],
        "output_dir": str(destination),
        "artifacts": {
            name: {"bytes": len(serialized[name]), "sha256": sha256_bytes(serialized[name])}
            for name in OUTPUT_FILES
        },
    }
