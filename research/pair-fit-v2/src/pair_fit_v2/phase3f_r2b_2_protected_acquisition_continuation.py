"""Correction-only Phase 3F-R2B.2 protected acquisition continuation.

The only network-capable path in this module is restricted to the exact
original R2B ordinals 2--60.  Atlanta Base (ordinal 1) is an immutable,
offline-only reference.  This module has no dataset construction, profile
join, preprocessing, estimator, prediction, metric, or model serialization
capability.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
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
from pair_fit_v2.phase3f_r2b_1_response_contract import (
    ATLANTA_CANONICAL_SHA256,
    ATLANTA_IDENTITY_SHA256,
    ATLANTA_RAW_BYTES,
    ATLANTA_RAW_SHA256,
    ATLANTA_REQUEST_ID,
    ContractError,
    canonical_pair,
    validate_response_contract,
)


VERSION = "phase3f-r2b.2.correction-only-continuation.v1"
PHASE = "Phase 3F-R2B.2 - Correction-Only Protected Acquisition Continuation"
EXPECTED_HEAD = "1d98c20f41fe550deafa7e68cba611d7d66bf519"
EXPECTED_BRANCH = "research/pair-fit-v2"
CONTRACT_IDENTITY = "sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad"
ORIGINAL_R2B_STATUS = "FAILED — authorized protected acquisition attempt failed"
ENDPOINT = "teamdashlineups"
URL = "https://stats.nba.com/stats/teamdashlineups"
TIMEOUT_SECONDS = 30
MINIMUM_SPACING_SECONDS = 1.0
PLANNING_NAMESPACE = Path("planning/phase3f-r2b.2")
EVIDENCE_NAMESPACE = Path("cache/phase3f-r2b.2/protected-final-target")
R2B1_NAMESPACE = Path("planning/phase3f-r2b.1")
R2B1_PLAN = R2B1_NAMESPACE / "continuation_plan.json"
ATLANTA_RAW_PATH = Path(
    "cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-response.bin"
)
ATLANTA_QUARANTINE_PATH = Path(
    "cache/phase3f-r2b/protected-final-target/1610612737-01-base/quarantine.json"
)

R2B1_ARTIFACTS = {
    "response_contract.json": "ecc3ecf1d547401539af8f8f640002fc3887de3dd64f1e80af1d41d62d04c49e",
    "continuation_plan.json": "8b30afae8e1035144153ea96d2510cc78e3b4572b03b28558edd73a0c1a56f18",
    "input_fingerprints.json": "dfc1115d139e153ee7011b1eb934355a4403b72b26579bc0e41782bc25c78267",
    "artifact_hashes.json": "3350bce351b7d64ea0d46a55d17d83024ea65c4ba008aa652a672ff25cd0d79f",
    "summary.json": "d238fa41de8a15bc75e4d831c5498bdb2664f809af8b22335174c1dbe1a291da",
}
R2B_RECORDS = {
    "planning/phase3f-r2b/authorization.json": (71656, "12249e6acca554507501e887c9afeb4f3cad0079fb40ab2738bea3d308ade856"),
    "planning/phase3f-r2b/official_invocation.json": (935, "936708826bbfaf729a1ad8c9ed7dcbbf2e8bce13b11e3e9a08403fe665b524fe"),
    "cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-start.json": (281, "90553e18945c075aa285207d01821266930d3e9fcb79b84b9386b82bf741f9c9"),
    ATLANTA_RAW_PATH.as_posix(): (ATLANTA_RAW_BYTES, ATLANTA_RAW_SHA256),
    "cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-outcome.json": (594, "c799c52fbb449c126edb669d5abcf003ae3703895f2734a7bd0d2a1c6db6d9cf"),
    ATLANTA_QUARANTINE_PATH.as_posix(): (346, "affc98a8a1cba3158764085cc5811977c31f4a088f9dda5a412b65004f97986f"),
}
STATE_FILES = {
    "start": "attempt-1-start.json",
    "response": "attempt-1-response.bin",
    "outcome": "attempt-1-outcome.json",
    "verification": "verification.json",
    "verified_body": "verified-response.bin",
    "failure": "quarantine.json",
}
FINAL_OUTPUT_FILES = (
    "authorization.json",
    "official_invocation.json",
    "atlanta_offline_revalidation.json",
    "request_inventory.json",
    "attempt_inventory.json",
    "response_verifications.json",
    "response_fingerprints.json",
    "team_reconciliation.json",
    "global_reconciliation.json",
    "exact_250_inventory.json",
    "structural_dispositions.json",
    "input_fingerprints.json",
    "summary.json",
    "artifact_hashes.json",
)


class ContinuationError(RuntimeError):
    """Authorization, immutable-input, state, transport, or response failure."""


class ResponseError(ContinuationError):
    """A received response failed transport or corrected-contract checks."""

    def __init__(self, message: str, diagnostics: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = dict(diagnostics or {})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


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


def _write_once(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise ContinuationError(f"write-once record already exists: {path}") from exc


def _git_value(project_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=project_root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _identity_document(request: Mapping[str, Any]) -> dict[str, Any]:
    return {"endpoint": request.get("endpoint"), "parameters": request.get("parameters")}


def identity_sha256(request: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(_identity_document(request)))


def _verify_file(project_root: Path, relative: str, expected_bytes: int, expected_hash: str) -> dict[str, Any]:
    observed = _fingerprint(project_root / relative)
    if observed != {"bytes": expected_bytes, "sha256": expected_hash}:
        raise ContinuationError(f"frozen input mismatch: {relative}")
    return observed


def validate_preserved_inputs(project_root: Path) -> dict[str, dict[str, Any]]:
    """Re-hash every inherited pin and prove the failed namespace is unchanged."""

    if _git_value(project_root, "rev-parse", "HEAD") != EXPECTED_HEAD:
        raise ContinuationError("committed HEAD differs from the authorized checkpoint")
    if _git_value(project_root, "branch", "--show-current") != EXPECTED_BRANCH:
        raise ContinuationError("branch differs from the authorized checkpoint")
    fingerprints: dict[str, dict[str, Any]] = {}
    for name, expected_hash in R2B1_ARTIFACTS.items():
        relative = (R2B1_NAMESPACE / name).as_posix()
        observed = _fingerprint(project_root / relative)
        if observed["sha256"] != expected_hash:
            raise ContinuationError(f"R2B.1 artifact mismatch: {relative}")
        fingerprints[relative] = observed

    r2b1_inputs = _read_json(project_root / R2B1_NAMESPACE / "input_fingerprints.json")
    for group in ("earlier_r0_r0_1_r1s_r2a_pinned_inputs", "committed_r2b_checkpoint"):
        values = r2b1_inputs.get(group)
        if not isinstance(values, Mapping):
            raise ContinuationError(f"R2B.1 input group missing: {group}")
        for relative, expected in values.items():
            observed = _fingerprint(project_root / relative)
            if observed != expected:
                raise ContinuationError(f"inherited pinned input mismatch: {relative}")
            fingerprints[relative] = observed

    expected_planning = {"authorization.json", "official_invocation.json"}
    r2b_planning = project_root / "planning/phase3f-r2b"
    if {item.name for item in r2b_planning.iterdir()} != expected_planning:
        raise ContinuationError("failed R2B planning inventory changed")
    r2b_evidence = project_root / "cache/phase3f-r2b/protected-final-target"
    entries = list(r2b_evidence.iterdir())
    if len(entries) != 1 or entries[0].name != "1610612737-01-base" or not entries[0].is_dir():
        raise ContinuationError("failed R2B evidence inventory changed")
    expected_atlanta = {
        "attempt-1-start.json", "attempt-1-response.bin", "attempt-1-outcome.json", "quarantine.json"
    }
    if {item.name for item in entries[0].iterdir()} != expected_atlanta:
        raise ContinuationError("failed Atlanta evidence inventory changed")
    for relative, (size, digest) in R2B_RECORDS.items():
        fingerprints[relative] = _verify_file(project_root, relative, size, digest)

    authorization = _read_json(project_root / "planning/phase3f-r2b/authorization.json")
    requests_value = authorization.get("authorized_requests")
    if not isinstance(requests_value, list) or len(requests_value) != 60:
        raise ContinuationError("original R2B request inventory changed")
    if [item.get("ordinal") for item in requests_value] != list(range(1, 61)):
        raise ContinuationError("original R2B ordinals changed")
    first = requests_value[0]
    if (
        first.get("request_id") != ATLANTA_REQUEST_ID
        or first.get("canonical_identity_sha256") != ATLANTA_IDENTITY_SHA256
    ):
        raise ContinuationError("original Atlanta request identity changed")
    outcome = _read_json(project_root / entries[0].relative_to(project_root) / "attempt-1-outcome.json")
    quarantine = _read_json(project_root / entries[0].relative_to(project_root) / "quarantine.json")
    if outcome.get("state") != "failed_or_quarantined" or quarantine.get("state") != "failed_or_quarantined":
        raise ContinuationError("permanent R2B failure classification changed")
    if outcome.get("automatic_retries") != 0 or outcome.get("attempt_number") != 1:
        raise ContinuationError("original Atlanta attempt linkage changed")
    return dict(sorted(fingerprints.items()))


def load_continuation_requests(project_root: Path) -> list[dict[str, Any]]:
    plan_path = project_root / R2B1_PLAN
    if _fingerprint(plan_path)["sha256"] != R2B1_ARTIFACTS["continuation_plan.json"]:
        raise ContinuationError("continuation specification differs")
    plan = _read_json(plan_path)
    values = plan.get("remaining_requests") if isinstance(plan, Mapping) else None
    if not isinstance(values, list) or len(values) != 59:
        raise ContinuationError("continuation must contain exactly 59 requests")
    requests_value = [dict(item) for item in values]
    if [item.get("ordinal") for item in requests_value] != list(range(2, 61)):
        raise ContinuationError("continuation ordinals must remain 2 through 60")
    for request in requests_value:
        if (
            request.get("request_id") == ATLANTA_REQUEST_ID
            or request.get("ordinal") == 1
            or request.get("endpoint") != ENDPOINT
            or request.get("canonical_identity_sha256") != identity_sha256(request)
        ):
            raise ContinuationError("continuation request identity differs from R2B.1")
    if len({item["request_id"] for item in requests_value}) != 59:
        raise ContinuationError("duplicate continuation request ID")
    if len({item["canonical_identity_sha256"] for item in requests_value}) != 59:
        raise ContinuationError("duplicate continuation request identity")
    return requests_value


def validate_request_identity(request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]]) -> None:
    if request.get("ordinal") == 1 or request.get("request_id") == ATLANTA_REQUEST_ID:
        raise ContinuationError("Atlanta Base transport is prohibited")
    by_ordinal = {item["ordinal"]: item for item in frozen}
    original = by_ordinal.get(request.get("ordinal"))
    if original is None or not 2 <= int(request.get("ordinal", 0)) <= 60:
        raise ContinuationError("request ordinal is outside the 2--60 authorization")
    fields = ("ordinal", "request_id", "endpoint", "parameters", "canonical_identity_sha256")
    if any(request.get(field) != original.get(field) for field in fields):
        raise ContinuationError("request differs from its frozen original identity")
    if identity_sha256(request) != request["canonical_identity_sha256"]:
        raise ContinuationError("request canonical identity hash mismatch")


def authorization_document(project_root: Path) -> dict[str, Any]:
    fingerprints = validate_preserved_inputs(project_root)
    requests_value = load_continuation_requests(project_root)
    return {
        "version": VERSION,
        "phase": PHASE,
        "required_committed_head": EXPECTED_HEAD,
        "required_branch": EXPECTED_BRANCH,
        "permanent_original_r2b_status": ORIGINAL_R2B_STATUS,
        "r2b1_contract_identity": CONTRACT_IDENTITY,
        "input_fingerprints": fingerprints,
        "atlanta_ordinal_1": {
            "ordinal": 1,
            "request_id": ATLANTA_REQUEST_ID,
            "canonical_identity_sha256": ATLANTA_IDENTITY_SHA256,
            "disposition": "offline_revalidation_only",
            "network_authorized": False,
            "original_raw_path": ATLANTA_RAW_PATH.as_posix(),
            "original_quarantine_path": ATLANTA_QUARANTINE_PATH.as_posix(),
            "raw_bytes": ATLANTA_RAW_BYTES,
            "raw_sha256": ATLANTA_RAW_SHA256,
            "canonical_json_sha256": ATLANTA_CANONICAL_SHA256,
            "attempt_number": 1,
        },
        "network_authorized_requests": requests_value,
        "network_authorized_ordinals": list(range(2, 61)),
        "request_order": [item["request_id"] for item in requests_value],
        "transport_authorized_identity_count": 59,
        "attempt_limit_per_identity": 1,
        "transport": {
            "url": URL,
            "headers": dict(RESEARCH_HEADERS),
            "trust_env": False,
            "allow_redirects": False,
            "timeout_seconds": TIMEOUT_SECONDS,
            "automatic_retries": 0,
            "minimum_seconds_between_attempts": MINIMUM_SPACING_SECONDS,
            "sequential": True,
        },
        "output_namespaces": {
            "planning": PLANNING_NAMESPACE.as_posix() + "/",
            "raw_evidence": EVIDENCE_NAMESPACE.as_posix() + "/",
        },
        "restart_rules": {
            "not_started": "eligible for its one authorized attempt",
            "completed_verified": "re-hash, revalidate, and skip without transport",
            "started_without_outcome": "stop for read-only investigation",
            "failed_or_quarantined": "preserve and stop",
            "conflicting_state": "refuse progress and stop",
            "offline_revalidated_reference": "Atlanta ordinal 1 only; never transport",
        },
        "failure_policy": "preserve start and received bytes, write outcome and quarantine, stop, never retry",
        "exact_250_policy": "verify and preserve; mark unresolved; continue only remaining full-season requests",
        "recovery_requests_authorized": False,
        "final_test_dataset_authorized": False,
        "profile_join_authorized": False,
        "preprocessing_authorized": False,
        "model_operation_authorized": False,
        "phase_stop_boundary": "acquisition and structural reconciliation only",
    }


def initialize_authorization(project_root: Path, planning_dir: Path) -> dict[str, Any]:
    planning = Path(planning_dir)
    target = planning / "authorization.json"
    document = authorization_document(Path(project_root))
    content = serialize_json(document)
    if planning.exists():
        entries = list(planning.iterdir())
        if entries:
            if len(entries) == 1 and target.exists() and _read_bytes(target) == content:
                return document
            raise ContinuationError("R2B.2 planning namespace already contains official state")
    if (Path(project_root) / EVIDENCE_NAMESPACE).exists() and any((Path(project_root) / EVIDENCE_NAMESPACE).iterdir()):
        raise ContinuationError("R2B.2 evidence namespace is not empty")
    _write_once(target, content)
    return document


def validate_authorization(document: Mapping[str, Any], project_root: Path) -> list[dict[str, Any]]:
    expected = authorization_document(project_root)
    if document != expected:
        raise ContinuationError("authorization differs from the frozen machine authorization")
    if document.get("atlanta_ordinal_1", {}).get("network_authorized") is not False:
        raise ContinuationError("Atlanta must be explicitly non-network-authorized")
    requests_value = list(document.get("network_authorized_requests", []))
    if len(requests_value) != 59 or [item["ordinal"] for item in requests_value] != list(range(2, 61)):
        raise ContinuationError("authorization must contain exactly original ordinals 2--60")
    frozen = load_continuation_requests(project_root)
    for request in requests_value:
        validate_request_identity(request, frozen)
    return requests_value


def _request_slug(request: Mapping[str, Any]) -> str:
    return f"{int(request['ordinal']):02d}-{request['parameters']['TeamID']}-{request['parameters']['MeasureType'].lower()}"


def request_paths(evidence_root: Path, request: Mapping[str, Any]) -> dict[str, Path]:
    base = Path(evidence_root) / _request_slug(request)
    return {name: base / filename for name, filename in STATE_FILES.items()}


def _named_result(payload: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    result_sets = payload.get("resultSets")
    matches = [item for item in result_sets if isinstance(item, Mapping) and item.get("name") == name]
    if len(matches) != 1:
        raise ResponseError(f"missing or duplicate named result set: {name}")
    return matches[0]


def _normalize_parameter(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def verify_response_bytes(body: bytes, request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    validate_request_identity(request, frozen)
    try:
        diagnostics = validate_response_contract(body, request)
        payload = strict_json_bytes(body)
    except (ContractError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ResponseError(f"corrected response contract failed: {exc}") from exc
    if payload.get("resource") not in (None, ENDPOINT):
        raise ResponseError("response endpoint context mismatch")
    returned = payload.get("parameters")
    if returned is not None:
        if not isinstance(returned, Mapping):
            raise ResponseError("returned parameters are malformed")
        for key in ("TeamID", "Season", "SeasonType", "MeasureType"):
            if key in returned and _normalize_parameter(returned[key]) != _normalize_parameter(request["parameters"][key]):
                raise ResponseError(f"returned parameter mismatch: {key}")
    lineups = _named_result(payload, "Lineups")
    headers = lineups["headers"]
    rows = [dict(zip(headers, row)) for row in lineups["rowSet"]]
    keys = [canonical_pair(row["GROUP_ID"]) for row in rows]
    measure = request["parameters"]["MeasureType"]
    zero_possession = sum(float(row["POSS"]) == 0 for row in rows) if measure == "Advanced" else 0
    required_fields = ["MIN", "SUM_TIME_PLAYED"] if measure == "Base" else ["POSS", "NET_RATING"]
    return {
        "version": VERSION,
        "request_id": request["request_id"],
        "ordinal": request["ordinal"],
        "team_id": request["parameters"]["TeamID"],
        "measure": measure,
        "endpoint": request["endpoint"],
        "season": request["parameters"]["Season"],
        "season_type": request["parameters"]["SeasonType"],
        "canonical_identity_sha256": identity_sha256(request),
        "raw_bytes": len(body),
        "raw_sha256": sha256_bytes(body),
        "canonical_json_sha256": sha256_bytes(canonical_json_bytes(payload)),
        "overall_header_count": diagnostics["overall_header_count"],
        "overall_row_count": diagnostics["overall_row_count"],
        "lineups_header_count": diagnostics["lineups_header_count"],
        "lineups_row_count": diagnostics["lineups_row_count"],
        "row_width_error_count": diagnostics["row_width_error_count"],
        "canonical_pair_count": len(keys),
        "canonical_pair_keys": [list(key) for key in keys],
        "duplicate_canonical_pair_count": diagnostics["duplicate_canonical_pair_count"],
        "malformed_group_id_count": diagnostics["malformed_group_identifier_count"],
        "same_player_pair_count": diagnostics["same_player_pair_count"],
        "invalid_player_id_count": diagnostics["invalid_player_id_count"],
        "required_fields": required_fields,
        "invalid_required_field_count": 0,
        "zero_possession_advanced_row_count": zero_possession,
        "exact_250": diagnostics["exact_250"],
        "result_set_selection": "exact_name",
        "observed_result_set_order": diagnostics["observed_result_set_order"],
        "team_context": diagnostics["team_context"],
        "base_poss_absent_as_expected": diagnostics["base_poss_absent_as_expected"],
        "verified": True,
    }


def offline_revalidate_atlanta(
    project_root: Path,
    authorization: Mapping[str, Any],
    planning_dir: Path | None = None,
) -> dict[str, Any]:
    record_path = Path(planning_dir or (project_root / PLANNING_NAMESPACE)) / "atlanta_offline_revalidation.json"
    if record_path.exists():
        existing = _read_json(record_path)
        body = _read_bytes(project_root / ATLANTA_RAW_PATH)
        request = _read_json(project_root / "planning/phase3f-r2b/authorization.json")["authorized_requests"][0]
        expected = _atlanta_record(project_root, body, request, authorization)
        if existing != expected:
            raise ContinuationError("existing Atlanta offline revalidation record conflicts")
        return existing
    body = _read_bytes(project_root / ATLANTA_RAW_PATH)
    request = _read_json(project_root / "planning/phase3f-r2b/authorization.json")["authorized_requests"][0]
    record = _atlanta_record(project_root, body, request, authorization)
    _write_once(record_path, serialize_json(record))
    return record


def _atlanta_record(project_root: Path, body: bytes, request: Mapping[str, Any], authorization: Mapping[str, Any]) -> dict[str, Any]:
    if len(body) != ATLANTA_RAW_BYTES or sha256_bytes(body) != ATLANTA_RAW_SHA256:
        raise ContinuationError("Atlanta raw identity differs")
    if request.get("ordinal") != 1 or request.get("request_id") != ATLANTA_REQUEST_ID:
        raise ContinuationError("Atlanta original attempt linkage differs")
    if identity_sha256(request) != ATLANTA_IDENTITY_SHA256:
        raise ContinuationError("Atlanta canonical request identity differs")
    try:
        validation = verify_atlanta_contract(body, request)
    except ResponseError as exc:
        raise ContinuationError(f"Atlanta offline revalidation blocked: {exc}") from exc
    if validation["canonical_json_sha256"] != ATLANTA_CANONICAL_SHA256:
        raise ContinuationError("Atlanta canonical JSON identity differs")
    quarantine = _fingerprint(project_root / ATLANTA_QUARANTINE_PATH)
    return {
        "version": VERSION,
        "state": "offline_revalidated_reference",
        "network_authorized": False,
        "network_attempt_occurred": False,
        "original_r2b_path": ATLANTA_RAW_PATH.as_posix(),
        "original_quarantine_path": ATLANTA_QUARANTINE_PATH.as_posix(),
        "original_quarantine_identity": quarantine,
        "request_id": ATLANTA_REQUEST_ID,
        "ordinal": 1,
        "attempt_number": 1,
        "canonical_identity_sha256": ATLANTA_IDENTITY_SHA256,
        "raw_bytes": len(body),
        "raw_sha256": sha256_bytes(body),
        "canonical_json_sha256": validation["canonical_json_sha256"],
        "r2b1_contract_identity": CONTRACT_IDENTITY,
        "authorization_sha256": sha256_bytes(serialize_json(authorization)),
        "structural_validation": validation,
    }


def verify_atlanta_contract(body: bytes, request: Mapping[str, Any]) -> dict[str, Any]:
    try:
        diagnostics = validate_response_contract(body, request)
        payload = strict_json_bytes(body)
    except (ContractError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResponseError(str(exc)) from exc
    returned = payload.get("parameters")
    if isinstance(returned, Mapping):
        for key in ("TeamID", "Season", "SeasonType", "MeasureType"):
            if key in returned and _normalize_parameter(returned[key]) != _normalize_parameter(request["parameters"][key]):
                raise ResponseError(f"returned parameter mismatch: {key}")
    return {
        **diagnostics,
        "raw_bytes": len(body),
        "raw_sha256": sha256_bytes(body),
        "canonical_json_sha256": sha256_bytes(canonical_json_bytes(payload)),
    }


def _record_matches(record: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    return (
        record.get("request_id") == request.get("request_id")
        and record.get("ordinal") == request.get("ordinal")
        and record.get("canonical_identity_sha256") == identity_sha256(request)
        and record.get("attempt_number") == 1
    )


def classify_request_state(evidence_root: Path, request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]]) -> str:
    paths = request_paths(evidence_root, request)
    directory = paths["start"].parent
    if not directory.exists():
        return "not_started"
    if not directory.is_dir():
        return "conflicting_state"
    if any(not item.is_file() or item.name not in STATE_FILES.values() for item in directory.iterdir()):
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
    if not isinstance(start, Mapping) or not _record_matches(start, request):
        return "conflicting_state"
    if "outcome" not in present:
        return "started_without_outcome"
    try:
        outcome = _read_json(paths["outcome"])
    except Exception:
        return "conflicting_state"
    if not isinstance(outcome, Mapping) or not _record_matches(outcome, request):
        return "conflicting_state"
    if outcome.get("state") == "failed_or_quarantined":
        allowed = {"start", "outcome", "failure"} | ({"response"} if "response" in present else set())
        return "failed_or_quarantined" if present == allowed else "conflicting_state"
    if outcome.get("state") != "completed_verified":
        return "conflicting_state"
    if present != {"start", "response", "outcome", "verification", "verified_body"}:
        return "conflicting_state"
    try:
        body = _read_bytes(paths["response"])
        promoted = _read_bytes(paths["verified_body"])
        verification = _read_json(paths["verification"])
        actual = verify_response_bytes(body, request, frozen)
    except Exception:
        return "conflicting_state"
    if body != promoted or verification != actual:
        return "conflicting_state"
    checks = {
        "http_status": 200,
        "redirected": False,
        "automatic_retries": 0,
        "raw_sha256": actual["raw_sha256"],
        "canonical_json_sha256": actual["canonical_json_sha256"],
    }
    return "completed_verified" if all(outcome.get(k) == v for k, v in checks.items()) else "conflicting_state"


def create_session() -> requests.Session:
    retry = Retry(total=0, connect=0, read=0, redirect=0, status=0)
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _write_failure(paths: Mapping[str, Path], request: Mapping[str, Any], reason: str, diagnostics: Mapping[str, Any] | None = None) -> None:
    _write_once(paths["failure"], serialize_json({
        "version": VERSION,
        "request_id": request["request_id"],
        "ordinal": request["ordinal"],
        "canonical_identity_sha256": identity_sha256(request),
        "attempt_number": 1,
        "state": "failed_or_quarantined",
        "reason": reason,
        "diagnostics": dict(diagnostics or {}),
    }))


def acquire_one(request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]], evidence_root: Path, session: requests.Session, *, clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    validate_request_identity(request, frozen)
    state = classify_request_state(evidence_root, request, frozen)
    if state == "completed_verified":
        return {"request_id": request["request_id"], "action": "skipped_completed_verified"}
    if state != "not_started":
        raise ContinuationError(f"request state blocks transport: {state}")
    paths = request_paths(evidence_root, request)
    started = {
        "version": VERSION,
        "request_id": request["request_id"],
        "ordinal": request["ordinal"],
        "canonical_identity_sha256": identity_sha256(request),
        "attempt_number": 1,
        "started_at": utc_now(),
    }
    _write_once(paths["start"], serialize_json(started))
    response: requests.Response | None = None
    began = clock()
    try:
        response = session.get(URL, params=dict(request["parameters"]), timeout=TIMEOUT_SECONDS, allow_redirects=False)
        body = response.content
        _write_once(paths["response"], body)
        redirected = bool(response.is_redirect or response.is_permanent_redirect or 300 <= response.status_code < 400)
        if redirected:
            raise ResponseError("redirect response prohibited")
        if response.status_code != 200:
            raise ResponseError(f"HTTP status {response.status_code}")
        verification = verify_response_bytes(body, request, frozen)
        _write_once(paths["verification"], serialize_json(verification))
        _write_once(paths["verified_body"], body)
        outcome = {
            "version": VERSION,
            "request_id": request["request_id"],
            "ordinal": request["ordinal"],
            "canonical_identity_sha256": identity_sha256(request),
            "attempt_number": 1,
            "completed_at": utc_now(),
            "state": "completed_verified",
            "http_status": 200,
            "redirected": False,
            "automatic_retries": 0,
            "elapsed_seconds": clock() - began,
            "row_count": verification["lineups_row_count"],
            "byte_count": len(body),
            "raw_sha256": verification["raw_sha256"],
            "canonical_json_sha256": verification["canonical_json_sha256"],
            "disposition": "exact_250_unresolved" if verification["exact_250"] else "completed_verified",
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        return {"request_id": request["request_id"], "action": "acquired", "outcome": outcome}
    except requests.RequestException as exc:
        reason = f"transport:{type(exc).__name__}"
        outcome = {
            "version": VERSION, "request_id": request["request_id"], "ordinal": request["ordinal"],
            "canonical_identity_sha256": identity_sha256(request), "attempt_number": 1,
            "completed_at": utc_now(), "state": "failed_or_quarantined", "http_status": None,
            "redirected": False, "automatic_retries": 0, "elapsed_seconds": clock() - began,
            "failure": reason,
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        _write_failure(paths, request, reason)
        raise ContinuationError(reason) from exc
    except ResponseError as exc:
        body = b"" if response is None else response.content
        redirected = False if response is None else bool(response.is_redirect or response.is_permanent_redirect or 300 <= response.status_code < 400)
        outcome = {
            "version": VERSION, "request_id": request["request_id"], "ordinal": request["ordinal"],
            "canonical_identity_sha256": identity_sha256(request), "attempt_number": 1,
            "completed_at": utc_now(), "state": "failed_or_quarantined",
            "http_status": None if response is None else response.status_code, "redirected": redirected,
            "automatic_retries": 0, "elapsed_seconds": clock() - began, "byte_count": len(body),
            "raw_sha256": sha256_bytes(body) if response is not None else None, "failure": str(exc),
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        _write_failure(paths, request, str(exc), exc.diagnostics)
        raise ContinuationError(str(exc)) from exc


def _verified_data(evidence_root: Path, request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], set[tuple[str, str]]]:
    if classify_request_state(evidence_root, request, frozen) != "completed_verified":
        raise ContinuationError(f"request is not completed_verified: {request['request_id']}")
    verification = _read_json(request_paths(evidence_root, request)["verification"])
    return verification, {tuple(item) for item in verification["canonical_pair_keys"]}


def _atlanta_data(project_root: Path, offline: Mapping[str, Any]) -> tuple[dict[str, Any], set[tuple[str, str]]]:
    body = _read_bytes(project_root / ATLANTA_RAW_PATH)
    payload = strict_json_bytes(body)
    result = _named_result(payload, "Lineups")
    rows = [dict(zip(result["headers"], row)) for row in result["rowSet"]]
    keys = {canonical_pair(row["GROUP_ID"]) for row in rows}
    verification = {
        "request_id": ATLANTA_REQUEST_ID, "ordinal": 1, "team_id": "1610612737", "measure": "Base",
        "lineups_row_count": len(rows), "canonical_pair_count": len(keys), "canonical_pair_keys": [list(k) for k in sorted(keys, key=lambda x: (int(x[0]), int(x[1])))],
        "duplicate_canonical_pair_count": 0, "malformed_group_id_count": 0, "same_player_pair_count": 0,
        "invalid_player_id_count": 0, "invalid_required_field_count": 0, "zero_possession_advanced_row_count": 0,
        "exact_250": False, "raw_bytes": offline["raw_bytes"], "raw_sha256": offline["raw_sha256"],
        "canonical_json_sha256": offline["canonical_json_sha256"], "verified": True,
    }
    return verification, keys


def reconcile(project_root: Path, evidence_root: Path, requests_value: Sequence[Mapping[str, Any]], frozen: Sequence[Mapping[str, Any]], offline: Mapping[str, Any]) -> dict[str, Any]:
    by_team: dict[str, dict[str, Mapping[str, Any]]] = {}
    for request in requests_value:
        by_team.setdefault(request["parameters"]["TeamID"], {})[request["parameters"]["MeasureType"]] = request
    atlanta_base, atlanta_keys = _atlanta_data(project_root, offline)
    responses: list[dict[str, Any]] = [atlanta_base]
    teams = []
    for team_id in sorted(by_team, key=int):
        advanced_request = by_team[team_id].get("Advanced")
        if advanced_request is None:
            raise ContinuationError(f"missing Advanced request for {team_id}")
        advanced, advanced_keys = _verified_data(evidence_root, advanced_request, frozen)
        responses.append(advanced)
        if team_id == "1610612737":
            base, base_keys, base_namespace = atlanta_base, atlanta_keys, "phase3f-r2b original offline reference"
        else:
            base_request = by_team[team_id].get("Base")
            if base_request is None:
                raise ContinuationError(f"missing Base request for {team_id}")
            base, base_keys = _verified_data(evidence_root, base_request, frozen)
            responses.append(base)
            base_namespace = "phase3f-r2b.2"
        base_only = base_keys - advanced_keys
        advanced_only = advanced_keys - base_keys
        mismatch = bool(base_only or advanced_only or base["lineups_row_count"] != advanced["lineups_row_count"])
        invalid_pair = any(item.get(field, 0) for item in (base, advanced) for field in ("duplicate_canonical_pair_count", "malformed_group_id_count", "same_player_pair_count", "invalid_player_id_count"))
        invalid_field = any(item.get("invalid_required_field_count", 0) for item in (base, advanced))
        exact_250 = bool(base["exact_250"] or advanced["exact_250"])
        issues = (["base_advanced_mismatch"] if mismatch else []) + (["invalid_pair_identity"] if invalid_pair else []) + (["invalid_required_field"] if invalid_field else []) + (["exact_250_unresolved"] if exact_250 else [])
        if mismatch:
            disposition = "base_advanced_mismatch"
        elif invalid_pair:
            disposition = "invalid_pair_identity"
        elif invalid_field:
            disposition = "invalid_required_field"
        elif exact_250:
            disposition = "exact_250_unresolved"
        else:
            disposition = "structurally_complete_non_250"
        triggers = [{"request_id": item["request_id"], "ordinal": item["ordinal"], "measure": item["measure"], "raw_sha256": item["raw_sha256"], "canonical_json_sha256": item["canonical_json_sha256"]} for item in (base, advanced) if item["exact_250"]]
        teams.append({
            "team_id": team_id, "base_source_namespace": base_namespace, "advanced_source_namespace": "phase3f-r2b.2",
            "base_request_id": base["request_id"], "advanced_request_id": advanced["request_id"],
            "base_row_count": base["lineups_row_count"], "advanced_row_count": advanced["lineups_row_count"],
            "base_canonical_pair_count": len(base_keys), "advanced_canonical_pair_count": len(advanced_keys),
            "intersection_count": len(base_keys & advanced_keys),
            "base_only_keys": [list(k) for k in sorted(base_only, key=lambda x: (int(x[0]), int(x[1])))],
            "advanced_only_keys": [list(k) for k in sorted(advanced_only, key=lambda x: (int(x[0]), int(x[1])))],
            "duplicate_count": base.get("duplicate_canonical_pair_count", 0) + advanced.get("duplicate_canonical_pair_count", 0),
            "malformed_key_count": base.get("malformed_group_id_count", 0) + advanced.get("malformed_group_id_count", 0),
            "invalid_field_count": base.get("invalid_required_field_count", 0) + advanced.get("invalid_required_field_count", 0),
            "zero_possession_advanced_rows": advanced["zero_possession_advanced_row_count"],
            "base_exact_250": base["exact_250"], "advanced_exact_250": advanced["exact_250"],
            "exact_250_triggering_identities": triggers, "structural_issues": issues,
            "structural_disposition": disposition,
        })
    if len(teams) != 30:
        raise ContinuationError("reconciliation did not produce exactly 30 teams")
    counts = Counter(item["structural_disposition"] for item in teams)
    unresolved = [item for item in teams if item["structural_disposition"] != "structurally_complete_non_250"]
    classification = (
        "PASS — correction-only protected acquisition completed and structurally reconciled"
        if not unresolved else
        "CONDITIONAL PASS — acquisition complete; unresolved team evidence requires a separate checkpoint"
    )
    global_record = {
        "version": VERSION, "classification": classification, "total_original_protected_identities": 60,
        "offline_revalidated_identities": 1, "new_completed_verified_requests": 59,
        "total_available_base_responses": 30, "total_available_advanced_responses": 30,
        "total_raw_base_rows": sum(item["base_row_count"] for item in teams),
        "total_raw_advanced_rows": sum(item["advanced_row_count"] for item in teams),
        "unique_team_canonical_pair_population": sum(item["intersection_count"] for item in teams),
        "structurally_complete_non_250_teams": counts["structurally_complete_non_250"],
        "exact_250_unresolved_teams": [item["team_id"] for item in teams if item["base_exact_250"] or item["advanced_exact_250"]],
        "base_advanced_mismatch_teams": [item["team_id"] for item in teams if "base_advanced_mismatch" in item["structural_issues"]],
        "invalid_pair_teams": [item["team_id"] for item in teams if "invalid_pair_identity" in item["structural_issues"]],
        "invalid_field_teams": [item["team_id"] for item in teams if "invalid_required_field" in item["structural_issues"]],
        "advanced_zero_possession_rows": sum(item["zero_possession_advanced_rows"] for item in teams),
        "duplicate_count": sum(item["duplicate_count"] for item in teams),
        "malformed_count": sum(item["malformed_key_count"] for item in teams),
        "failed_or_quarantined_continuation_identities": 0,
        "final_test_readiness_gates": "all six pending", "final_test_dataset_constructed": False,
        "profile_join_occurred": False, "preprocessing_occurred": False, "model_operation_occurred": False,
    }
    return {"response_verifications": sorted(responses, key=lambda x: x["ordinal"]), "team_reconciliation": teams, "global_reconciliation": global_record}


def attempt_inventory(evidence_root: Path, requests_value: Sequence[Mapping[str, Any]], frozen: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for request in requests_value:
        paths = request_paths(evidence_root, request)
        state = classify_request_state(evidence_root, request, frozen)
        item: dict[str, Any] = {"ordinal": request["ordinal"], "request_id": request["request_id"], "team_id": request["parameters"]["TeamID"], "measure": request["parameters"]["MeasureType"], "state": state}
        item["records"] = {name: {"path": path.relative_to(evidence_root).as_posix(), **_fingerprint(path)} for name, path in paths.items() if path.exists()}
        if paths["start"].exists():
            item["started_at"] = _read_json(paths["start"]).get("started_at")
        if paths["outcome"].exists():
            outcome = _read_json(paths["outcome"])
            for field in ("attempt_number", "completed_at", "http_status", "redirected", "automatic_retries", "elapsed_seconds", "row_count", "byte_count", "raw_sha256", "canonical_json_sha256", "disposition"):
                item[field] = outcome.get(field)
        output.append(item)
    return output


def record_official_invocation(planning_dir: Path, authorization_path: Path, argv: Sequence[str] | None = None) -> dict[str, Any]:
    body = _read_bytes(authorization_path)
    record = {
        "version": VERSION, "invocation_number": 1, "recorded_at": utc_now(),
        "python_executable": sys.executable, "working_directory": os.getcwd(),
        "command_argv": list(sys.argv if argv is None else argv), "pythonpath": os.environ.get("PYTHONPATH", ""),
        "authorization_path": str(authorization_path), "authorization_sha256": sha256_bytes(body),
        "r2b1_contract_identity": CONTRACT_IDENTITY,
    }
    _write_once(Path(planning_dir) / "official_invocation.json", serialize_json(record))
    return record


def _write_final_outputs(planning_dir: Path, authorization: Mapping[str, Any], offline: Mapping[str, Any], inventory: Sequence[Mapping[str, Any]], reconciliation: Mapping[str, Any]) -> dict[str, Any]:
    planning = Path(planning_dir)
    requests_value = authorization["network_authorized_requests"]
    verifications = reconciliation["response_verifications"]
    fingerprints = [{k: item[k] for k in ("ordinal", "request_id", "raw_bytes", "raw_sha256", "canonical_json_sha256")} for item in verifications]
    teams = reconciliation["team_reconciliation"]
    exact = [{"team_id": item["team_id"], "structural_disposition": item["structural_disposition"], "triggering_identities": item["exact_250_triggering_identities"], "recovery_requires_separate_policy_and_authorization": True} for item in teams if item["exact_250_triggering_identities"]]
    summary = {
        "version": VERSION, "classification": reconciliation["global_reconciliation"]["classification"],
        "authorization_sha256": sha256_bytes(serialize_json(authorization)), "r2b1_contract_identity": CONTRACT_IDENTITY,
        "permanent_original_r2b_status": ORIGINAL_R2B_STATUS, "atlanta_offline_revalidated": True,
        "atlanta_network_attempt_count": 0, "official_invocation_count": 1, "network_attempt_count": 59,
        "completed_verified_request_count": 59, "recovery_request_count": 0,
        "final_test_dataset_constructed": False, "profile_join_occurred": False,
        "preprocessing_occurred": False, "estimator_or_prediction_or_metric_occurred": False,
        "model_artifact_created": False,
    }
    values = {
        "request_inventory.json": requests_value,
        "attempt_inventory.json": list(inventory),
        "response_verifications.json": verifications,
        "response_fingerprints.json": fingerprints,
        "team_reconciliation.json": teams,
        "global_reconciliation.json": reconciliation["global_reconciliation"],
        "exact_250_inventory.json": {"version": VERSION, "teams": exact},
        "structural_dispositions.json": {"version": VERSION, "by_team": [{"team_id": item["team_id"], "disposition": item["structural_disposition"], "issues": item["structural_issues"]} for item in teams]},
        "input_fingerprints.json": authorization["input_fingerprints"],
        "summary.json": summary,
    }
    for name, value in values.items():
        _write_once(planning / name, serialize_json(value))
    manifest_names = [name for name in FINAL_OUTPUT_FILES if name != "artifact_hashes.json"]
    manifest = {"version": VERSION, "artifact_inventory": list(FINAL_OUTPUT_FILES), "sha256": {name: _fingerprint(planning / name)["sha256"] for name in manifest_names}, "note": "artifact_hashes.json excludes itself to avoid a circular hash"}
    _write_once(planning / "artifact_hashes.json", serialize_json(manifest))
    return summary


def execute_authorized_continuation(project_root: Path, authorization_path: Path, evidence_root: Path, planning_dir: Path, *, session_factory: Callable[[], requests.Session] = create_session, sleeper: Callable[[float], None] = time.sleep, monotonic: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    root = Path(project_root)
    authorization_body = _read_bytes(Path(authorization_path))
    authorization = strict_json_bytes(authorization_body)
    requests_value = validate_authorization(authorization, root)
    frozen = load_continuation_requests(root)
    offline = offline_revalidate_atlanta(root, authorization, Path(planning_dir))
    states = [classify_request_state(Path(evidence_root), request, frozen) for request in requests_value]
    blockers = [state for state in states if state not in {"not_started", "completed_verified"}]
    if blockers:
        raise ContinuationError(f"pre-transport state blocks continuation: {blockers}")
    session = session_factory()
    attempts = []
    previous_finished: float | None = None
    try:
        for request, initial_state in zip(requests_value, states):
            if _read_bytes(Path(authorization_path)) != authorization_body:
                raise ContinuationError("machine authorization changed during execution")
            validate_request_identity(request, frozen)
            if initial_state == "completed_verified":
                attempts.append({"request_id": request["request_id"], "action": "skipped_completed_verified"})
                continue
            if previous_finished is not None:
                remaining = MINIMUM_SPACING_SECONDS - (monotonic() - previous_finished)
                if remaining > 0:
                    sleeper(remaining)
            attempts.append(acquire_one(request, frozen, Path(evidence_root), session, clock=monotonic))
            previous_finished = monotonic()
    finally:
        session.close()
    reconciliation = reconcile(root, Path(evidence_root), requests_value, frozen, offline)
    inventory = attempt_inventory(Path(evidence_root), requests_value, frozen)
    summary = _write_final_outputs(Path(planning_dir), authorization, offline, inventory, reconciliation)
    return {"summary": summary, "attempts": attempts, "reconciliation": reconciliation}
