"""Bounded Phase 3F-R2A acquisition of two non-protected player profiles.

The module deliberately has no pair construction, preprocessing, estimator,
prediction, metric, or model-artifact capability.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS


VERSION = "phase3f-r2a.prior-profile-acquisition.v1"
EXPECTED_HEAD = "200a60036d095bf6a90483f3cdcfa3dd86f86f7c"
ENDPOINT = "leaguedashplayerstats"
RESULT_SET = "LeagueDashPlayerStats"
URL = "https://stats.nba.com/stats/leaguedashplayerstats"
AUTHORIZED_SEASON = "2024-25"
PROHIBITED_SEASON = "2025-26"
R1S_PLAN = Path("planning/phase3f-r1s/acquisition_plan.json")
R1S_PLAN_BYTES = 64_477
R1S_PLAN_SHA256 = "fd0db91ad876df39d13829ac7e11b920a24e5b394c9f025115a7db46010056c4"
R1S_ARTIFACT_HASHES_SHA256 = "7f3ddbc31665797b0c0acb24c49b9c47c2ddd0b31d92a1c98e8b39921e2ac347"
R1S_SUMMARY_SHA256 = "81f16d12563aa36d1770f172dea1c090e1ed37da5d4c15744f132a9f1352f19b"
EVIDENCE_NAMESPACE = Path("cache/phase3f-r2a/non-protected-prior-profiles")
PLANNING_NAMESPACE = Path("planning/phase3f-r2a")
MINIMUM_SPACING_SECONDS = 1.0
TIMEOUT_SECONDS = 30

PLAYER_PARAMETERS = {
    "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
    "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "",
    "GameSegment": "", "Height": "", "LastNGames": "0", "LeagueID": "00",
    "Location": "", "MeasureType": "Base", "Month": "0", "OpponentTeamID": "0",
    "Outcome": "", "PORound": "", "PaceAdjust": "N", "Period": "0",
    "PlayerExperience": "", "PlayerPosition": "", "PlusMinus": "N", "Rank": "N",
    "Season": AUTHORIZED_SEASON, "SeasonSegment": "", "SeasonType": "Regular Season",
    "ShotClockRange": "", "StarterBench": "", "TeamID": "", "TwoWay": "",
    "VsConference": "", "VsDivision": "", "Weight": "",
}

PER100_SOURCE_FIELDS = (
    "PLAYER_ID", "AGE", "GP", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
    "OREB", "DREB", "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS",
    "PLUS_MINUS", "TEAM_COUNT",
)
TOTALS_SOURCE_FIELDS = ("PLAYER_ID", "MIN")
ESTIMATOR_DIRECT_FIELDS = (
    "AGE", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB", "AST",
    "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS",
)
DERIVED_FIELDS = (
    "effective_field_goal_pct", "true_shooting_pct", "three_point_attempt_rate",
    "free_throw_rate",
)
EXPECTED_45_FEATURES = tuple(
    [f"pair_mean.{name}" for name in ESTIMATOR_DIRECT_FIELDS + DERIVED_FIELDS]
    + [f"pair_absolute_difference.{name}" for name in ESTIMATOR_DIRECT_FIELDS + DERIVED_FIELDS]
    + ["pair_traded_history_count"]
)

COMMITTED_INPUTS = (
    "PHASE3F_R0_DATA_DICTIONARY_ADDENDUM.md",
    "PHASE3F_R0_FINAL_TEST_FREEZE_REPORT.md",
    "PHASE3F_R0_FINAL_TEST_POLICY.md",
    "PHASE3F_R0_1_DOCUMENTATION_RECONCILIATION_REPORT.md",
    "PHASE3F_R1S_SIMPLIFIED_ACQUISITION_POLICY.md",
    "PHASE3F_R1S_SIMPLIFIED_ACQUISITION_REPORT.md",
    "src/pair_fit_v2/phase3f_r0_cli.py",
    "src/pair_fit_v2/phase3f_r0_final_test_freeze.py",
    "src/pair_fit_v2/phase3f_r0_1_cli.py",
    "src/pair_fit_v2/phase3f_r0_1_documentation_reconciliation.py",
    "src/pair_fit_v2/phase3f_r1s_acquisition_plan.py",
    "src/pair_fit_v2/phase3f_r1s_cli.py",
    "tests/test_phase3f_r0_final_test_freeze.py",
    "tests/test_phase3f_r0_1_documentation_reconciliation.py",
    "tests/test_phase3f_r1s_acquisition_plan.py",
)

GENERATED_INPUT_HASHES = {
    "curated/phase3f-r0/artifact_hashes.json": "802a14a978d937a07bf0cbeb1b93fa177b2904ef3e611f47d31a1ac3bbadf4e1",
    "curated/phase3f-r0/expanded_feature_manifest.json": "93693a520151387f0c9fb514ada7324639387a7ae60bae5bba9d2a607a5beb14",
    "curated/phase3f-r0/expanded_preprocessing_state.json": "a0180d9fc0436515f8a6f302727b4c0b030274cfbcce1a5ded7883568f05f47e",
    "curated/phase3f-r0/expanded_training_estimator_matrix_unscaled.csv": "a8a2b08daa3c56ccda78d34f77c2a29b7ef7c9e00835e7ab6ac77412ec6f8588",
    "curated/phase3f-r0/expanded_training_row_index.csv": "3062b1524e7599dcab32ae1dc419040e7f16f6730308e3a88b18c71293d4c427",
    "curated/phase3f-r0/expanded_training_staging.csv": "3fced86922b533b0da2b42748d6c0b8afddef57b1281fe14880b11a446df21b6",
    "curated/phase3f-r0/final_test_policy.json": "a3e5b7271b45b0ff997fde81d546bdd6d055a7177f44d31b41924beca8bb7e48",
    "curated/phase3f-r0/input_fingerprints.json": "04caeba6a0872fac6fad3d7a8aaa3861dbc484228c6d3b8ddb3e24a1a1819428",
    "curated/phase3f-r0/population_diagnostics.json": "a1d16291d10352aba4afced0d2d6cfc272c04acf1266f702b3ada1e866589d8c",
    "curated/phase3f-r0/summary.json": "f2475571a32af96a6c802d90d5fa8f20fcfc2f7b0d9e27f2ce1cad1c88407b41",
    "curated/phase3f-r0.1/artifact_hashes.json": "805350d8eb6aa9361f6745e8871996a226847ad989ebd77adbe8b000565a1047",
    "curated/phase3f-r0.1/documentation_reconciliation.json": "cb5b7ec2e83ad36ed0e9be683023cee553928e9aa3f08768a81d872ab8107ed7",
    "curated/phase3f-r0.1/referenced_r0_artifacts.json": "bb3ff4f51660aeba503d1bc5af18fae9847bf3d432eff4b7654007e986871198",
    "curated/phase3f-r0.1/summary.json": "cc6e37cfb1c554f7da1bbd3d4a098a3d435fdffb59b83a1ee46c0d9f9a8bc1b0",
    "planning/phase3f-r1s/acquisition_plan.json": R1S_PLAN_SHA256,
    "planning/phase3f-r1s/artifact_hashes.json": R1S_ARTIFACT_HASHES_SHA256,
    "planning/phase3f-r1s/summary.json": R1S_SUMMARY_SHA256,
}

STATE_FILES = {
    "start": "attempt-1-start.json",
    "response": "attempt-1-response.bin",
    "outcome": "attempt-1-outcome.json",
    "verified_body": "verified-response.json",
    "verification": "verification.json",
    "failure": "quarantine.json",
}


class AcquisitionError(RuntimeError):
    """Raised for authorization, state, transport, or evidence failure."""


class ResponseValidationError(AcquisitionError):
    """Raised when response bytes cannot be promoted to verified evidence."""

    def __init__(self, message: str, diagnostics: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = dict(diagnostics or {})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_json_bytes(value: bytes) -> Any:
    def reject_constant(token: str) -> None:
        raise ValueError(f"non-standard JSON constant: {token}")

    return json.loads(value.decode("utf-8", errors="strict"), parse_constant=reject_constant)


def _safe_lexical_path(path: Path | str) -> Path:
    """Reject protected or out-of-scope path text before any filesystem call."""
    text = str(path).replace("\\", "/")
    lowered = text.lower()
    if PROHIBITED_SEASON in lowered:
        raise AcquisitionError("protected-season path rejected before filesystem access")
    if "teamdashlineups" in lowered or "protected-final-target" in lowered:
        raise AcquisitionError("protected TeamDashLineups path rejected before filesystem access")
    return Path(path)


def _read_bytes(path: Path | str) -> bytes:
    return _safe_lexical_path(path).read_bytes()


def _read_json(path: Path | str) -> Any:
    return strict_json_bytes(_read_bytes(path))


def _write_once(path: Path | str, content: bytes) -> None:
    target = _safe_lexical_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise AcquisitionError(f"write-once record already exists: {target}") from exc


def _identity_document(request: Mapping[str, Any]) -> dict[str, Any]:
    return {"endpoint": request.get("endpoint"), "parameters": request.get("parameters")}


def identity_sha256(request: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(_identity_document(request)))


def validate_request_identity(request: Mapping[str, Any]) -> None:
    parameters = request.get("parameters")
    if request.get("endpoint") != ENDPOINT or not isinstance(parameters, Mapping):
        raise AcquisitionError("request is outside the exact LeagueDashPlayerStats allowlist")
    encoded = canonical_json_bytes(_identity_document(request)).decode("utf-8")
    if PROHIBITED_SEASON in encoded:
        raise AcquisitionError("protected season request rejected")
    if parameters.get("Season") != AUTHORIZED_SEASON:
        raise AcquisitionError("unauthorized season")
    if parameters.get("SeasonType") != "Regular Season":
        raise AcquisitionError("unauthorized season type")
    if parameters.get("MeasureType") != "Base":
        raise AcquisitionError("unauthorized measure")
    if parameters.get("PerMode") not in {"Per100Possessions", "Totals"}:
        raise AcquisitionError("unauthorized per mode")
    if parameters.get("LeagueID") != "00" or parameters.get("TeamID") != "":
        raise AcquisitionError("request must be league-wide and not team-specific")
    expected = {**PLAYER_PARAMETERS, "PerMode": parameters.get("PerMode")}
    if dict(parameters) != expected:
        raise AcquisitionError("request parameter dictionary differs from the frozen R1S identity")


def load_frozen_requests(project_root: Path) -> list[dict[str, Any]]:
    plan_path = _safe_lexical_path(Path(project_root) / R1S_PLAN)
    body = _read_bytes(plan_path)
    if len(body) != R1S_PLAN_BYTES or sha256_bytes(body) != R1S_PLAN_SHA256:
        raise AcquisitionError("audited R1S acquisition plan identity mismatch")
    plan = strict_json_bytes(body)
    requests_value = plan.get("missing_non_protected_dependencies") if isinstance(plan, Mapping) else None
    if not isinstance(requests_value, list) or len(requests_value) != 2:
        raise AcquisitionError("R1S does not contain exactly two non-protected dependencies")
    requests_copy = [dict(item) for item in requests_value]
    if [item.get("parameters", {}).get("PerMode") for item in requests_copy] != [
        "Per100Possessions", "Totals"
    ]:
        raise AcquisitionError("frozen dependency order mismatch")
    for item in requests_copy:
        validate_request_identity(item)
        if item.get("protected") is not False or item.get("status") != "missing_not_acquired":
            raise AcquisitionError("frozen dependency classification mismatch")
    if len({identity_sha256(item) for item in requests_copy}) != 2:
        raise AcquisitionError("duplicate frozen dependency identity")
    return requests_copy


def fingerprint_inputs(project_root: Path) -> dict[str, dict[str, Any]]:
    root = Path(project_root)
    output: dict[str, dict[str, Any]] = {}
    for relative in COMMITTED_INPUTS:
        body = _read_bytes(root / relative)
        output[relative] = {"bytes": len(body), "sha256": sha256_bytes(body), "kind": "committed"}
    for relative, expected in GENERATED_INPUT_HASHES.items():
        body = _read_bytes(root / relative)
        actual = sha256_bytes(body)
        if actual != expected:
            raise AcquisitionError(f"generated input fingerprint mismatch: {relative}")
        output[relative] = {"bytes": len(body), "sha256": actual, "kind": "generated"}
    return dict(sorted(output.items()))


def authorization_document(project_root: Path) -> dict[str, Any]:
    requests_value = load_frozen_requests(project_root)
    authorized = []
    for ordinal, item in enumerate(requests_value, 1):
        authorized.append(
            {
                "ordinal": ordinal,
                "request_id": item["request_id"],
                "endpoint": item["endpoint"],
                "parameters": item["parameters"],
                "canonical_identity_sha256": identity_sha256(item),
            }
        )
    return {
        "version": VERSION,
        "checkpoint": "Phase 3F-R2A — 2024–25 Prior-Profile Dependency Acquisition",
        "required_committed_head": EXPECTED_HEAD,
        "source_r1s_plan": {
            "path": R1S_PLAN.as_posix(),
            "bytes": R1S_PLAN_BYTES,
            "sha256": R1S_PLAN_SHA256,
        },
        "input_fingerprints": fingerprint_inputs(project_root),
        "authorized_requests": authorized,
        "request_order": [item["request_id"] for item in authorized],
        "output_namespace": EVIDENCE_NAMESPACE.as_posix() + "/",
        "attempt_limit_per_identity": 1,
        "transport": {
            "sequential": True,
            "headers": dict(RESEARCH_HEADERS),
            "trust_env": False,
            "allow_redirects": False,
            "timeout_seconds": TIMEOUT_SECONDS,
            "automatic_retries": 0,
            "minimum_seconds_between_attempts": MINIMUM_SPACING_SECONDS,
        },
        "failure_rule": "preserve evidence, quarantine, stop phase, do not attempt next request",
        "restart_states": [
            "not_started", "completed_verified", "started_without_outcome",
            "failed_or_quarantined", "conflicting_state",
        ],
        "prohibited_protected_season": PROHIBITED_SEASON,
        "phase_stop_boundary": "acquisition, independent verification, reconciliation, and reporting only",
        "final_test_construction_authorized": False,
        "model_operation_authorized": False,
    }


def initialize_authorization(project_root: Path, planning_dir: Path) -> dict[str, Any]:
    target = _safe_lexical_path(Path(planning_dir) / "authorization.json")
    document = authorization_document(project_root)
    content = serialize_json(document)
    if target.exists():
        if _read_bytes(target) != content:
            raise AcquisitionError("existing authorization differs from frozen authorization")
        return document
    _write_once(target, content)
    return document


def validate_authorization(document: Mapping[str, Any], project_root: Path) -> list[dict[str, Any]]:
    expected = authorization_document(project_root)
    if document != expected:
        raise AcquisitionError("authorization record does not match the frozen R1S identities")
    return list(document["authorized_requests"])


def _request_slug(request: Mapping[str, Any]) -> str:
    mode = request["parameters"]["PerMode"]
    return "01-per100possessions" if mode == "Per100Possessions" else "02-totals"


def request_paths(evidence_root: Path, request: Mapping[str, Any]) -> dict[str, Path]:
    base = _safe_lexical_path(Path(evidence_root) / _request_slug(request))
    return {name: base / filename for name, filename in STATE_FILES.items()}


def _strict_player_id(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("PLAYER_ID is not a string or integer")
    text = str(value)
    if not text.isdecimal() or int(text) <= 0 or str(int(text)) != text:
        raise ValueError("PLAYER_ID is not a positive canonical decimal")
    return text


def _finite_nonnegative(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number >= 0


def verify_response_bytes(body: bytes, request: Mapping[str, Any]) -> dict[str, Any]:
    validate_request_identity(request)
    try:
        payload = strict_json_bytes(body)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ResponseValidationError(f"invalid strict JSON: {exc}") from exc
    if not isinstance(payload, Mapping) or not isinstance(payload.get("resultSets"), list):
        raise ResponseValidationError("response lacks a resultSets list")
    result_sets = payload["resultSets"]
    matches = [item for item in result_sets if isinstance(item, Mapping) and item.get("name") == RESULT_SET]
    if len(result_sets) != 1 or len(matches) != 1:
        raise ResponseValidationError("expected exactly one LeagueDashPlayerStats result set")
    result = matches[0]
    headers, raw_rows = result.get("headers"), result.get("rowSet")
    if (
        not isinstance(headers, list)
        or not all(isinstance(item, str) for item in headers)
        or len(headers) != len(set(headers))
        or not isinstance(raw_rows, list)
    ):
        raise ResponseValidationError("malformed LeagueDashPlayerStats headers or rows")
    if any(not isinstance(row, list) or len(row) != len(headers) for row in raw_rows):
        raise ResponseValidationError("LeagueDashPlayerStats row width mismatch")
    rows = [dict(zip(headers, row)) for row in raw_rows]
    required = PER100_SOURCE_FIELDS if request["parameters"]["PerMode"] == "Per100Possessions" else TOTALS_SOURCE_FIELDS
    missing = sorted(set(required) - set(headers))
    valid_ids: list[str] = []
    malformed = 0
    for row in rows:
        try:
            valid_ids.append(_strict_player_id(row.get("PLAYER_ID")))
        except ValueError:
            malformed += 1
    duplicate_count = sum(count - 1 for count in Counter(valid_ids).values() if count > 1)
    reliability_field = "GP" if request["parameters"]["PerMode"] == "Per100Possessions" else "MIN"
    invalid_reliability = (
        len(rows)
        if reliability_field not in headers
        else sum(not _finite_nonnegative(row.get(reliability_field)) for row in rows)
    )
    diagnostics = {
        "endpoint": request["endpoint"],
        "request_id": request.get("request_id"),
        "canonical_identity_sha256": identity_sha256(request),
        "result_set_name": RESULT_SET,
        "column_names": headers,
        "column_count": len(headers),
        "row_count": len(rows),
        "byte_count": len(body),
        "raw_sha256": sha256_bytes(body),
        "canonical_json_sha256": sha256_bytes(canonical_json_bytes(payload)),
        "player_ids": {
            "unique_count": len(set(valid_ids)),
            "duplicate_count": duplicate_count,
            "malformed_or_nonpositive_count": malformed,
        },
        "required_fields": {
            "required": list(required),
            "missing": missing,
            "all_present": not missing,
        },
        "reliability": {
            "field": reliability_field,
            "present": reliability_field in headers,
            "finite_nonnegative_count": len(rows) - invalid_reliability,
            "invalid_count": invalid_reliability,
        },
    }
    errors = []
    if not rows:
        errors.append("empty player result set")
    if missing:
        errors.append(f"missing required fields: {missing}")
    if malformed:
        errors.append(f"malformed/nonpositive player IDs: {malformed}")
    if duplicate_count:
        errors.append(f"duplicate player IDs: {duplicate_count}")
    if invalid_reliability:
        errors.append(f"invalid {reliability_field} reliability values: {invalid_reliability}")
    if errors:
        raise ResponseValidationError("; ".join(errors), diagnostics)
    diagnostics["verified"] = True
    return diagnostics


def _record_identity_matches(record: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    return (
        record.get("request_id") == request.get("request_id")
        and record.get("canonical_identity_sha256") == identity_sha256(request)
    )


def classify_request_state(evidence_root: Path, request: Mapping[str, Any]) -> str:
    paths = request_paths(evidence_root, request)
    base = paths["start"].parent
    if not base.exists():
        return "not_started"
    expected_names = set(STATE_FILES.values())
    if any(item.name not in expected_names for item in base.iterdir()):
        return "conflicting_state"
    present = {name for name, path in paths.items() if path.exists()}
    if not present:
        return "not_started"
    if "start" not in present:
        return "conflicting_state"
    try:
        start = _read_json(paths["start"])
    except Exception:
        return "conflicting_state"
    if not isinstance(start, Mapping) or not _record_identity_matches(start, request) or start.get("attempt_number") != 1:
        return "conflicting_state"
    if "outcome" not in present:
        return "started_without_outcome"
    try:
        outcome = _read_json(paths["outcome"])
    except Exception:
        return "conflicting_state"
    if not isinstance(outcome, Mapping) or not _record_identity_matches(outcome, request):
        return "conflicting_state"
    state = outcome.get("state")
    if state == "completed_verified":
        expected = {"start", "response", "outcome", "verified_body", "verification"}
        if present != expected:
            return "conflicting_state"
        try:
            response = _read_bytes(paths["response"])
            promoted = _read_bytes(paths["verified_body"])
            verification = _read_json(paths["verification"])
            actual = verify_response_bytes(response, request)
        except Exception:
            return "conflicting_state"
        if response != promoted or verification != actual:
            return "conflicting_state"
        if (
            outcome.get("http_status") != 200
            or outcome.get("redirected") is not False
            or outcome.get("raw_sha256") != actual["raw_sha256"]
            or outcome.get("canonical_json_sha256") != actual["canonical_json_sha256"]
        ):
            return "conflicting_state"
        return "completed_verified"
    if state == "failed_or_quarantined":
        if "failure" in present and "verified_body" not in present and "verification" not in present:
            return "failed_or_quarantined"
        return "conflicting_state"
    return "conflicting_state"


def create_session() -> requests.Session:
    retry = Retry(total=0, connect=0, read=0, redirect=0, status=0)
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _write_failure(
    paths: Mapping[str, Path], request: Mapping[str, Any], reason: str,
    diagnostics: Mapping[str, Any] | None = None,
) -> None:
    _write_once(
        paths["failure"],
        serialize_json(
            {
                "version": VERSION,
                "request_id": request["request_id"],
                "canonical_identity_sha256": identity_sha256(request),
                "state": "failed_or_quarantined",
                "reason": reason,
                "diagnostics": dict(diagnostics or {}),
            }
        ),
    )


def acquire_one(
    request: Mapping[str, Any],
    evidence_root: Path,
    session: requests.Session,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    validate_request_identity(request)
    state = classify_request_state(evidence_root, request)
    if state == "completed_verified":
        return {"request_id": request["request_id"], "action": "skipped_completed_verified"}
    if state != "not_started":
        raise AcquisitionError(f"request state blocks transport: {state}")
    paths = request_paths(evidence_root, request)
    started = {
        "version": VERSION,
        "request_id": request["request_id"],
        "canonical_identity_sha256": identity_sha256(request),
        "attempt_number": 1,
        "started_at": utc_now(),
    }
    _write_once(paths["start"], serialize_json(started))
    response = None
    transport_started = clock()
    try:
        response = session.get(
            URL,
            params=dict(request["parameters"]),
            timeout=TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        body = response.content
        _write_once(paths["response"], body)
        redirected = bool(response.is_redirect or response.is_permanent_redirect or 300 <= response.status_code < 400)
        if response.status_code != 200:
            raise ResponseValidationError(f"HTTP status {response.status_code}")
        if redirected:
            raise ResponseValidationError("redirect response prohibited")
        verification = verify_response_bytes(body, request)
        _write_once(paths["verified_body"], body)
        _write_once(paths["verification"], serialize_json(verification))
        outcome = {
            "version": VERSION,
            "request_id": request["request_id"],
            "canonical_identity_sha256": identity_sha256(request),
            "attempt_number": 1,
            "completed_at": utc_now(),
            "state": "completed_verified",
            "http_status": response.status_code,
            "redirected": redirected,
            "automatic_retries": 0,
            "elapsed_seconds": clock() - transport_started,
            "byte_count": verification["byte_count"],
            "row_count": verification["row_count"],
            "raw_sha256": verification["raw_sha256"],
            "canonical_json_sha256": verification["canonical_json_sha256"],
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        return {"request_id": request["request_id"], "action": "acquired", "outcome": outcome}
    except requests.RequestException as exc:
        outcome = {
            "version": VERSION,
            "request_id": request["request_id"],
            "canonical_identity_sha256": identity_sha256(request),
            "attempt_number": 1,
            "completed_at": utc_now(),
            "state": "failed_or_quarantined",
            "http_status": None,
            "redirected": False,
            "automatic_retries": 0,
            "elapsed_seconds": clock() - transport_started,
            "failure": f"transport:{type(exc).__name__}",
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        _write_failure(paths, request, outcome["failure"])
        raise AcquisitionError(outcome["failure"]) from exc
    except ResponseValidationError as exc:
        body = b"" if response is None else response.content
        status = None if response is None else response.status_code
        redirected = False if response is None else bool(
            response.is_redirect or response.is_permanent_redirect or 300 <= response.status_code < 400
        )
        outcome = {
            "version": VERSION,
            "request_id": request["request_id"],
            "canonical_identity_sha256": identity_sha256(request),
            "attempt_number": 1,
            "completed_at": utc_now(),
            "state": "failed_or_quarantined",
            "http_status": status,
            "redirected": redirected,
            "automatic_retries": 0,
            "elapsed_seconds": clock() - transport_started,
            "byte_count": len(body),
            "raw_sha256": sha256_bytes(body) if response is not None else None,
            "failure": str(exc),
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        _write_failure(paths, request, str(exc), exc.diagnostics)
        raise AcquisitionError(str(exc)) from exc


def _verified_request_data(evidence_root: Path, request: Mapping[str, Any]) -> tuple[dict[str, Any], set[str]]:
    if classify_request_state(evidence_root, request) != "completed_verified":
        raise AcquisitionError(f"request is not completed_verified: {request['request_id']}")
    paths = request_paths(evidence_root, request)
    verification = _read_json(paths["verification"])
    payload = strict_json_bytes(_read_bytes(paths["verified_body"]))
    result = payload["resultSets"][0]
    headers = result["headers"]
    rows = [dict(zip(headers, row)) for row in result["rowSet"]]
    ids = {_strict_player_id(row["PLAYER_ID"]) for row in rows}
    return verification, ids


def reconcile(project_root: Path, evidence_root: Path, requests_value: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(requests_value) != 2:
        raise AcquisitionError("reconciliation requires exactly two authorized requests")
    per100_verification, per100_ids = _verified_request_data(evidence_root, requests_value[0])
    totals_verification, totals_ids = _verified_request_data(evidence_root, requests_value[1])
    feature_manifest = _read_json(Path(project_root) / "curated/phase3f-r0/expanded_feature_manifest.json")
    frozen_features = feature_manifest.get("ordered_estimator_features")
    feature_contract_ok = frozen_features == list(EXPECTED_45_FEATURES)
    per100_fields_ok = per100_verification["required_fields"]["all_present"]
    min_ok = (
        totals_verification["required_fields"]["all_present"]
        and totals_verification["reliability"]["field"] == "MIN"
        and totals_verification["reliability"]["invalid_count"] == 0
    )
    per100_only = sorted(per100_ids - totals_ids, key=int)
    totals_only = sorted(totals_ids - per100_ids, key=int)
    material_discrepancies = []
    if not feature_contract_ok or not per100_fields_ok or not min_ok:
        material_discrepancies.append("schema_or_frozen_feature_contract_failure")
    # A side-only ID is reported but is not automatically material: league-wide
    # PerMode populations can differ without implying a malformed identity.
    disposition = "verified" if not material_discrepancies else "blocked"
    return {
        "version": VERSION,
        "authorization_identity": R1S_PLAN_SHA256,
        "request_inventory": [
            {
                "ordinal": index + 1,
                "request_id": request["request_id"],
                "canonical_identity_sha256": identity_sha256(request),
            }
            for index, request in enumerate(requests_value)
        ],
        "verified_responses": [per100_verification, totals_verification],
        "player_id_reconciliation": {
            "per100_unique_player_count": len(per100_ids),
            "totals_unique_player_count": len(totals_ids),
            "intersection_count": len(per100_ids & totals_ids),
            "per100_only_ids": per100_only,
            "totals_only_ids": totals_only,
            "per100_duplicate_ids": per100_verification["player_ids"]["duplicate_count"],
            "totals_duplicate_ids": totals_verification["player_ids"]["duplicate_count"],
            "per100_malformed_or_nonpositive_ids": per100_verification["player_ids"]["malformed_or_nonpositive_count"],
            "totals_malformed_or_nonpositive_ids": totals_verification["player_ids"]["malformed_or_nonpositive_count"],
            "id_set_equality_observed": per100_ids == totals_ids,
            "side_only_ids_are_not_automatically_material": True,
        },
        "total_min_reliability": {
            "source_field": "MIN",
            "materialized_field": "TOTAL_MIN",
            "finite_nonnegative_for_all_totals_rows": min_ok,
            "is_reliability_metadata_not_estimator_input": True,
        },
        "frozen_no_shot_inputs": {
            "feature_count": len(frozen_features) if isinstance(frozen_features, list) else None,
            "exact_order_matches_frozen_45": feature_contract_ok,
            "per100_direct_source_fields": list(ESTIMATOR_DIRECT_FIELDS),
            "derived_fields": {
                "effective_field_goal_pct": "(FGM + 0.5 * FG3M) / FGA",
                "true_shooting_pct": "PTS / (2 * (FGA + 0.44 * FTA))",
                "three_point_attempt_rate": "FG3A / FGA",
                "free_throw_rate": "FTA / FGA",
                "pair_traded_history_count": "known-only sum of TEAM_COUNT > 1 indicators",
            },
            "all_source_fields_available_or_derivable": per100_fields_ok and feature_contract_ok,
        },
        "material_discrepancies": material_discrepancies,
        "prior_profile_dependency_disposition": disposition,
        "protected_season_accessed": False,
        "final_test_constructed": False,
        "model_operation_occurred": False,
    }


def write_reconciliation_outputs(
    planning_dir: Path,
    authorization: Mapping[str, Any],
    reconciliation: Mapping[str, Any],
    attempt_inventory: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    output = _safe_lexical_path(planning_dir)
    reconciliation_bytes = serialize_json(reconciliation)
    summary = {
        "version": VERSION,
        "classification": (
            "PASS — Phase 3F-R2A prior-profile dependencies acquired and verified"
            if reconciliation["prior_profile_dependency_disposition"] == "verified"
            else "BLOCKED — dependency evidence is incomplete or inconsistent"
        ),
        "authorization_sha256": sha256_bytes(serialize_json(authorization)),
        "authorized_request_count": 2,
        "attempt_inventory": list(attempt_inventory),
        "verified_response_count": 2,
        "prior_profile_dependency_disposition": reconciliation["prior_profile_dependency_disposition"],
        "protected_season_accessed": False,
        "final_test_constructed": False,
        "model_operation_occurred": False,
    }
    summary_bytes = serialize_json(summary)
    manifest = {
        "version": VERSION,
        "artifact_inventory": ["authorization.json", "reconciliation.json", "summary.json", "artifact_hashes.json"],
        "sha256": {
            "authorization.json": sha256_bytes(serialize_json(authorization)),
            "reconciliation.json": sha256_bytes(reconciliation_bytes),
            "summary.json": sha256_bytes(summary_bytes),
        },
        "note": "artifact_hashes.json excludes itself to avoid a circular hash",
    }
    _write_once(output / "reconciliation.json", reconciliation_bytes)
    _write_once(output / "summary.json", summary_bytes)
    _write_once(output / "artifact_hashes.json", serialize_json(manifest))
    return summary


def attempt_record_inventory(
    evidence_root: Path, requests_value: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Describe immutable attempt records without depending on this run's actions."""
    inventory = []
    for request in requests_value:
        paths = request_paths(evidence_root, request)
        state = classify_request_state(evidence_root, request)
        item: dict[str, Any] = {"request_id": request["request_id"], "state": state}
        records = {}
        for name in ("start", "response", "outcome", "verified_body", "verification", "failure"):
            path = paths[name]
            if path.exists():
                content = _read_bytes(path)
                records[name] = {
                    "relative_path": f"{_request_slug(request)}/{path.name}",
                    "bytes": len(content),
                    "sha256": sha256_bytes(content),
                }
        item["records"] = records
        if "outcome" in records:
            outcome = _read_json(paths["outcome"])
            item["attempt_number"] = outcome.get("attempt_number")
            item["http_status"] = outcome.get("http_status")
            item["redirected"] = outcome.get("redirected")
            item["automatic_retries"] = outcome.get("automatic_retries")
        inventory.append(item)
    return inventory


def record_official_invocation(planning_dir: Path, argv: Sequence[str] | None = None) -> dict[str, Any]:
    record = {
        "version": VERSION,
        "python_executable": sys.executable,
        "working_directory": os.getcwd(),
        "command_argv": list(sys.argv if argv is None else argv),
        "pythonpath": os.environ.get("PYTHONPATH", ""),
    }
    _write_once(Path(planning_dir) / "official_invocation.json", serialize_json(record))
    return record


def execute_authorized_acquisition(
    project_root: Path,
    authorization_path: Path,
    evidence_root: Path,
    planning_dir: Path,
    *,
    session_factory: Callable[[], requests.Session] = create_session,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    authorization = _read_json(authorization_path)
    authorized = validate_authorization(authorization, project_root)
    states = [classify_request_state(evidence_root, request) for request in authorized]
    blockers = [state for state in states if state not in {"not_started", "completed_verified"}]
    if blockers:
        raise AcquisitionError(f"pre-transport state blocks phase: {blockers}")
    attempts = []
    last_attempt_finished: float | None = None
    session = session_factory()
    try:
        for request, initial_state in zip(authorized, states):
            if initial_state == "completed_verified":
                attempts.append({"request_id": request["request_id"], "action": "skipped_completed_verified"})
                continue
            if last_attempt_finished is not None:
                elapsed = monotonic() - last_attempt_finished
                if elapsed < MINIMUM_SPACING_SECONDS:
                    sleeper(MINIMUM_SPACING_SECONDS - elapsed)
            result = acquire_one(request, evidence_root, session, clock=monotonic)
            attempts.append(result)
            last_attempt_finished = monotonic()
    finally:
        session.close()
    reconciliation = reconcile(project_root, evidence_root, authorized)
    inventory = attempt_record_inventory(evidence_root, authorized)
    summary = write_reconciliation_outputs(planning_dir, authorization, reconciliation, inventory)
    return {"summary": summary, "reconciliation": reconciliation}
