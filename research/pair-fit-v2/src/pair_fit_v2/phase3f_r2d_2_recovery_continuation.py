"""Phase 3F-R2D.2 exact-250 recovery continuation and reconciliation.

This module can make only the seven requests frozen by the audited R2D.1
continuation plan.  Indiana Early Base is revalidated in place and is never a
network identity.  The module performs population reconciliation only: it has
no dataset-construction, feature, preprocessing, estimator, prediction,
metric, or model-serialization capability.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS
from pair_fit_v2.phase3f_r2b_1_response_contract import (
    ContractError,
    canonical_pair,
    validate_response_contract,
)
from pair_fit_v2.phase3f_r2c_1_recovery_specification import evaluate_disposition
from pair_fit_v2 import phase3f_r2d_1_response_echo_contract as echo_contract


VERSION = "phase3f-r2d.2.recovery-continuation.v1"
PHASE = "Phase 3F-R2D.2 - Exact-250 Recovery Continuation"
EXPECTED_HEAD = "31daa913bffd47bf3ba31e77aaf0f5f896b588b5"
EXPECTED_BRANCH = "research/pair-fit-v2"
URL = "https://stats.nba.com/stats/teamdashlineups"
TIMEOUT_SECONDS = 30
MINIMUM_PACING_SECONDS = 1.0
OUTPUT_ROOT = Path("cache/phase3f-r2d.2/protected-recovery-continuation")
CONTINUATION_PLAN = Path("planning/phase3f-r2d.1/continuation_plan.json")
R2C1_PLAN = Path("planning/phase3f-r2c.1/corrected_recovery_plan.json")
R2D_AUTHORIZATION = Path("planning/phase3f-r2d/recovery_authorization.json")
SOURCE_PATH = Path("src/pair_fit_v2/phase3f_r2d_2_recovery_continuation.py")
CLI_PATH = Path("src/pair_fit_v2/phase3f_r2d_2_cli.py")
QUARANTINED_BODY = echo_contract.QUARANTINED_RESPONSE

R2D1_ARTIFACTS = {
    "artifact_hashes.json": (1_082, "be4d2a9a6bbd09520d436c9e8504ea09ff68a0903b3a5672b9e2219a773e09d6"),
    "continuation_plan.json": (13_703, "904c1df531bd49e7719f6226597e0f9234576368ed9683cba87fb7c2672e20ab"),
    "quarantined_response_assessment.json": (129_140, "1b692d6b5ad522ee039b707fddffab91cb8b42d5021afc7f3438ce215cf210aa"),
    "response_echo_contract.json": (4_269, "f851f00b14b64cd92d16fe565f706d26b0467c9ac40a4d3bf99c82ba88678c73"),
    "summary.json": (851, "fa415789fc6cbe9c4d359bc9663bdffa4144f20942f442a8a66f1154e0b28883"),
}
PREPARED_FILES = frozenset({"authorization.json", "preflight.json"})
REQUEST_FILES = {
    "start": "attempt-1-start.json",
    "response": "attempt-1-response.bin",
    "verification": "verification.json",
    "outcome": "attempt-1-outcome.json",
    "quarantine": "quarantine.json",
}
FINAL_FILES = (
    "pacing.json",
    "indiana-reconciliation.json",
    "memphis-reconciliation.json",
    "team-dispositions.json",
    "summary.json",
    "artifact-hashes.json",
)
PRESERVED_NAMESPACES = (
    "planning/phase3f-r2b",
    "planning/phase3f-r2b.1",
    "planning/phase3f-r2b.2",
    "planning/phase3f-r2b.2.1",
    "cache/phase3f-r2b",
    "cache/phase3f-r2b.2",
    "planning/phase3f-r2c",
    "cache/phase3f-r2c-public-source",
    "planning/phase3f-r2c.1",
    "planning/phase3f-r2d",
    "planning/phase3f-r2d.1",
    "cache/phase3f-r2d/protected-recovery",
)


class ContinuationError(RuntimeError):
    """Fail-closed preflight, state, transport, verification, or reconciliation error."""


class ResponseVerificationError(ContinuationError):
    """A received body failed the frozen response contract."""

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
    def reject(token: str) -> None:
        raise ValueError(f"non-standard JSON constant: {token}")

    return json.loads(value.decode("utf-8", errors="strict"), parse_constant=reject)


def _read_json(path: Path) -> Any:
    return strict_json_bytes(path.read_bytes())


def _fingerprint(path: Path) -> dict[str, Any]:
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": sha256_bytes(body)}


def _write_once(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(body)
    except FileExistsError as exc:
        raise ContinuationError(f"write-once record already exists: {path}") from exc


def _git(project_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=project_root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _git_visible_inventory(project_root: Path) -> list[str]:
    prefix = "research/pair-fit-v2/"
    lines = _git(project_root, "status", "--porcelain=v1", "--untracked-files=all", "--", ".")
    output = []
    for line in lines.splitlines():
        output.append(line[3:].replace("\\", "/").removeprefix(prefix))
    return sorted(output)


def _namespace_fingerprint(project_root: Path, relative: str) -> dict[str, Any]:
    root = project_root / relative
    if not root.is_dir() or root.is_symlink():
        raise ContinuationError(f"missing or invalid preserved namespace: {relative}")
    files = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ContinuationError(f"symlink prohibited in preserved namespace: {path}")
        body = path.read_bytes()
        files.append({
            "path": path.relative_to(project_root).as_posix(),
            "bytes": len(body),
            "sha256": sha256_bytes(body),
            "mtime_ns": path.stat().st_mtime_ns,
        })
    return {
        "namespace": relative,
        "file_count": len(files),
        "byte_count": sum(item["bytes"] for item in files),
        "inventory_sha256": sha256_bytes(serialize_json(files)),
    }


def preservation_fingerprints(project_root: Path) -> list[dict[str, Any]]:
    return [_namespace_fingerprint(project_root, relative) for relative in PRESERVED_NAMESPACES]


def _assert_git_identity(project_root: Path) -> dict[str, Any]:
    branch = _git(project_root, "branch", "--show-current")
    head = _git(project_root, "rev-parse", "HEAD")
    left, right = _git(project_root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}").split()
    if branch != EXPECTED_BRANCH or head != EXPECTED_HEAD or (left, right) != ("0", "0"):
        raise ContinuationError(
            f"Git identity mismatch: branch={branch}, head={head}, divergence={left}/{right}"
        )
    if _git(project_root, "diff", "--cached", "--name-only"):
        raise ContinuationError("index must remain empty")
    return {"branch": branch, "head": head, "upstream_ahead": 0, "upstream_behind": 0}


def _assert_r2d1_artifacts(project_root: Path) -> None:
    root = project_root / "planning/phase3f-r2d.1"
    if sorted(item.name for item in root.iterdir()) != sorted(R2D1_ARTIFACTS):
        raise ContinuationError("R2D.1 artifact inventory mismatch")
    for name, (size, digest) in R2D1_ARTIFACTS.items():
        if _fingerprint(root / name) != {"bytes": size, "sha256": digest}:
            raise ContinuationError(f"R2D.1 audited artifact mismatch: {name}")
    manifest = _read_json(root / "artifact_hashes.json")
    for name, expected in manifest.get("artifacts", {}).items():
        if _fingerprint(root / name) != expected:
            raise ContinuationError(f"R2D.1 internal manifest mismatch: {name}")


def _identity_fields_from_original(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: request[key]
        for key in (
            "request_id", "canonical_request_identity_sha256", "endpoint", "team_id",
            "team_name", "window", "measure", "parameters", "future_output_namespace",
        )
    }


def load_authorized_requests(project_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load and cross-authenticate the exact audited ordinal-2-through-8 inventory."""

    _assert_r2d1_artifacts(project_root)
    continuation = _read_json(project_root / CONTINUATION_PLAN)
    corrected = _read_json(project_root / R2C1_PLAN)
    original_authorization = _read_json(project_root / R2D_AUTHORIZATION)
    remaining = continuation.get("remaining_network_identities")
    originals = original_authorization.get("authorized_requests")
    corrected_requests = corrected.get("future_recovery_identities")
    if not isinstance(remaining, list) or len(remaining) != 7:
        raise ContinuationError("continuation inventory must contain exactly seven identities")
    if not isinstance(originals, list) or len(originals) != 8:
        raise ContinuationError("original R2D identity inventory is invalid")
    if not isinstance(corrected_requests, list) or len(corrected_requests) != 8:
        raise ContinuationError("R2C.1 identity inventory is invalid")
    if any(
        _identity_fields_from_original(corrected) != _identity_fields_from_original(original)
        for corrected, original in zip(corrected_requests, originals)
    ):
        raise ContinuationError("R2C.1 and original R2D identity inventories differ")
    if continuation.get("continuation_order") != list(range(2, 9)):
        raise ContinuationError("continuation order is not exactly original ordinals 2-8")
    if continuation.get("indiana_early_base_duplicate_request_prohibited") is not True:
        raise ContinuationError("Indiana Early Base network prohibition is missing")
    if continuation.get("reused_first_evidence_member", {}).get("network_request_prohibited") is not True:
        raise ContinuationError("Indiana Early Base network prohibition changed")
    output: list[dict[str, Any]] = []
    for index, item in enumerate(remaining, start=2):
        original = originals[index - 1]
        if item.get("original_recovery_ordinal") != index:
            raise ContinuationError("original continuation ordinal mismatch")
        if _identity_fields_from_original(item) != _identity_fields_from_original(original):
            raise ContinuationError(f"continuation identity differs from original ordinal {index}")
        if _identity_fields_from_original(item) != _identity_fields_from_original(corrected_requests[index - 1]):
            raise ContinuationError(f"continuation identity differs from R2C.1 ordinal {index}")
        expected_destination = (
            OUTPUT_ROOT
            / f"{index:02d}-{item['team_id']}-{item['window']['name']}-{item['measure'].lower()}"
        ).as_posix()
        if item.get("continuation_output_namespace") != expected_destination:
            raise ContinuationError("continuation destination differs from audited R2D.1")
        if item.get("attempt_limit") != 1 or item.get("automatic_retries") != 0:
            raise ContinuationError("continuation attempt ceiling differs from audited R2D.1")
        output.append(dict(item))
    if any(item["original_recovery_ordinal"] == 1 for item in output):
        raise ContinuationError("Indiana Early Base appeared in network inventory")
    return original_authorization, output


def _request_for_contract(request: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(request)
    value["ordinal"] = request.get("ordinal", request.get("original_recovery_ordinal"))
    return value


def _named_lineups(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    result_sets = payload.get("resultSets")
    if not isinstance(result_sets, list):
        raise ResponseVerificationError("resultSets missing")
    if [item.get("name") for item in result_sets if isinstance(item, dict)] != ["Overall", "Lineups"]:
        raise ResponseVerificationError("response envelope must be ordered Overall, then Lineups")
    return result_sets[1]


def verify_response_bytes(body: bytes, request: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the corrected echo contract and all structural/pair/value checks."""

    contract_request = _request_for_contract(request)
    try:
        payload = strict_json_bytes(body)
        structural = validate_response_contract(body, contract_request)
    except (ContractError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ResponseVerificationError(f"structural response contract failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ResponseVerificationError("response JSON must be an object")
    echo = echo_contract.verify_initial_response_echo(
        request["parameters"], payload.get("parameters")
    )
    if not echo["passed"]:
        raise ResponseVerificationError("corrected response-echo contract failed", echo)
    lineups = _named_lineups(payload)
    headers = lineups.get("headers")
    row_set = lineups.get("rowSet")
    if not isinstance(headers, list) or not isinstance(row_set, list):
        raise ResponseVerificationError("Lineups schema or rows malformed")
    rows = [dict(zip(headers, row)) for row in row_set]
    keys = [canonical_pair(row["GROUP_ID"]) for row in rows]
    if len(set(keys)) != len(keys):
        raise ResponseVerificationError("duplicate canonical pair key")
    possessions: dict[str, float] = {}
    zero_possessions: list[list[str]] = []
    if request["measure"] == "Advanced":
        for key, row in zip(keys, rows):
            for field in ("POSS", "OFF_RATING", "DEF_RATING", "NET_RATING"):
                value = row.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    raise ResponseVerificationError(f"required Advanced numeric field invalid: {field}")
            possession = float(row["POSS"])
            if possession < 0:
                raise ResponseVerificationError("negative possession value")
            text = f"{key[0]}-{key[1]}"
            possessions[text] = possession
            if possession == 0:
                zero_possessions.append(list(key))
    ordered = sorted(keys, key=lambda pair: (int(pair[0]), int(pair[1])))
    return {
        "version": VERSION,
        "original_recovery_ordinal": contract_request["ordinal"],
        "request_id": request["request_id"],
        "canonical_request_identity_sha256": request["canonical_request_identity_sha256"],
        "team_id": request["team_id"],
        "team_name": request["team_name"],
        "window": request["window"]["name"],
        "measure": request["measure"],
        "bytes": len(body),
        "raw_sha256": sha256_bytes(body),
        "canonical_json_sha256": sha256_bytes(canonical_json_bytes(payload)),
        "overall_row_count": structural["overall_row_count"],
        "lineups_row_count": structural["lineups_row_count"],
        "canonical_pair_count": len(keys),
        "canonical_pair_keys": [list(item) for item in ordered],
        "duplicate_count": structural["duplicate_canonical_pair_count"],
        "malformed_pair_count": structural["malformed_group_identifier_count"],
        "same_player_count": structural["same_player_pair_count"],
        "invalid_player_id_count": structural["invalid_player_id_count"],
        "row_width_error_count": structural["row_width_error_count"],
        "observed_result_set_order": structural["observed_result_set_order"],
        "possession_by_pair_key": possessions,
        "zero_possession_pair_keys": sorted(
            zero_possessions, key=lambda pair: (int(pair[0]), int(pair[1]))
        ),
        "response_echo_comparison": echo,
        "structurally_valid": True,
        "authenticated": True,
    }


def offline_revalidate_indiana(project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Revalidate ordinal 1 in place without copying, moving, or promoting its body."""

    authorization, original = echo_contract._authenticate_r2d(project_root)
    historical = echo_contract._authenticate_governing_and_historical(project_root, authorization)
    assessment, reference = echo_contract._assess_quarantined_response(
        project_root, authorization, original, historical
    )
    if not assessment.get("eligible_for_future_reuse"):
        raise ContinuationError("Indiana Early Base failed corrected offline revalidation")
    request = authorization["authorized_requests"][0]
    body = (project_root / QUARANTINED_BODY).read_bytes()
    verification = verify_response_bytes(body, request)
    if (
        len(body) != echo_contract.QUARANTINED_RESPONSE_BYTES
        or verification["raw_sha256"] != echo_contract.QUARANTINED_RESPONSE_SHA256
        or verification["canonical_json_sha256"] != echo_contract.QUARANTINED_RESPONSE_CANONICAL_SHA256
    ):
        raise ContinuationError("Indiana Early Base frozen body identity changed")
    record = {
        **verification,
        "network_request_prohibited": True,
        "network_attempt_count": 0,
        "body_reference": {
            "path": QUARANTINED_BODY.as_posix(),
            "bytes": len(body),
            "raw_sha256": verification["raw_sha256"],
            "canonical_json_sha256": verification["canonical_json_sha256"],
        },
        "body_copied_moved_rewritten_or_promoted": False,
        "original_r2d_state_preserved": "failed_or_quarantined",
        "offline_revalidation": "passed",
    }
    return record, request


def create_session() -> requests.Session:
    retry = Retry(total=0, connect=0, read=0, redirect=0, status=0)
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def request_slug(request: Mapping[str, Any]) -> str:
    return (
        f"{int(request['original_recovery_ordinal']):02d}-{request['team_id']}-"
        f"{request['window']['name']}-{request['measure'].lower()}"
    )


def request_paths(output_root: Path, request: Mapping[str, Any]) -> dict[str, Path]:
    directory = Path(output_root) / request_slug(request)
    return {key: directory / value for key, value in REQUEST_FILES.items()}


def _record_matches(record: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    return (
        record.get("original_recovery_ordinal") == request.get("original_recovery_ordinal")
        and record.get("request_id") == request.get("request_id")
        and record.get("canonical_request_identity_sha256")
        == request.get("canonical_request_identity_sha256")
        and record.get("attempt_number") == 1
    )


def classify_request_state(output_root: Path, request: Mapping[str, Any]) -> str:
    paths = request_paths(output_root, request)
    directory = paths["start"].parent
    if not directory.exists():
        return "not_started"
    if not directory.is_dir() or directory.is_symlink():
        return "conflicting_state"
    names = {item.name for item in directory.iterdir() if item.is_file()}
    if any(not item.is_file() or item.is_symlink() for item in directory.iterdir()):
        return "conflicting_state"
    if not names.issubset(set(REQUEST_FILES.values())):
        return "conflicting_state"
    present = {key for key, path in paths.items() if path.exists()}
    if "start" not in present:
        return "conflicting_state"
    try:
        start = _read_json(paths["start"])
        if not isinstance(start, dict) or not _record_matches(start, request):
            return "conflicting_state"
    except Exception:
        return "conflicting_state"
    if "outcome" not in present:
        return "started_without_outcome"
    try:
        outcome = _read_json(paths["outcome"])
        if not isinstance(outcome, dict) or not _record_matches(outcome, request):
            return "conflicting_state"
    except Exception:
        return "conflicting_state"
    if outcome.get("state") == "failed_or_quarantined":
        allowed = {"start", "outcome", "quarantine"} | ({"response"} if "response" in present else set())
        return "failed_or_quarantined" if present == allowed else "conflicting_state"
    if outcome.get("state") != "completed_verified" or present != {"start", "response", "verification", "outcome"}:
        return "conflicting_state"
    try:
        verification = verify_response_bytes(paths["response"].read_bytes(), request)
        if _read_json(paths["verification"]) != verification:
            return "conflicting_state"
    except Exception:
        return "conflicting_state"
    if any(outcome.get(key) != value for key, value in {
        "http_status": 200,
        "redirect_count": 0,
        "automatic_retries": 0,
        "byte_count": verification["bytes"],
        "raw_sha256": verification["raw_sha256"],
        "canonical_json_sha256": verification["canonical_json_sha256"],
        "row_count": verification["lineups_row_count"],
    }.items()):
        return "conflicting_state"
    gap = start.get("observed_post_sleep_monotonic_gap_seconds")
    if start.get("previous_monotonic_completion") is not None and (
        isinstance(gap, bool) or not isinstance(gap, (int, float)) or gap < MINIMUM_PACING_SECONDS
    ):
        return "conflicting_state"
    return "completed_verified"


def _attempt_identity(request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "original_recovery_ordinal": request["original_recovery_ordinal"],
        "continuation_network_ordinal": request["continuation_network_ordinal"],
        "request_id": request["request_id"],
        "canonical_request_identity_sha256": request["canonical_request_identity_sha256"],
        "attempt_number": 1,
    }


def acquire_one(
    request: Mapping[str, Any], output_root: Path, session: requests.Session,
    *, previous_completion: float | None,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    if request.get("original_recovery_ordinal") == 1:
        raise ContinuationError("Indiana Early Base network request is prohibited")
    if classify_request_state(output_root, request) != "not_started":
        raise ContinuationError("request is not in an unambiguous not_started state")
    before_sleep = monotonic()
    pre_gap = None if previous_completion is None else before_sleep - previous_completion
    sleep_seconds = 0.0
    if previous_completion is not None and pre_gap < MINIMUM_PACING_SECONDS:
        sleep_seconds = MINIMUM_PACING_SECONDS - pre_gap
        sleeper(sleep_seconds)
    started = monotonic()
    observed_gap = None if previous_completion is None else started - previous_completion
    if observed_gap is not None and observed_gap < MINIMUM_PACING_SECONDS:
        raise ContinuationError("persisted monotonic pacing interval is below one full second")
    paths = request_paths(output_root, request)
    identity = _attempt_identity(request)
    _write_once(paths["start"], serialize_json({
        **identity,
        "utc_start": utc_now(),
        "process_monotonic_start": started,
        "previous_monotonic_completion": previous_completion,
        "calculated_pre_attempt_gap_seconds": pre_gap,
        "requested_sleep_duration_seconds": sleep_seconds,
        "observed_post_sleep_monotonic_gap_seconds": observed_gap,
        "required_minimum_gap_seconds": MINIMUM_PACING_SECONDS,
        "enforcement_clock": "time.monotonic",
        "utc_role": "descriptive_only",
    }))
    response: requests.Response | None = None
    try:
        response = session.get(
            URL,
            params=dict(request["parameters"]),
            timeout=TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        body = response.content
        _write_once(paths["response"], body)
        redirected = bool(
            response.is_redirect
            or response.is_permanent_redirect
            or 300 <= response.status_code < 400
            or getattr(response, "history", [])
        )
        if redirected:
            raise ResponseVerificationError("redirect response prohibited")
        if response.status_code != 200:
            raise ResponseVerificationError(f"HTTP status {response.status_code}")
        verification = verify_response_bytes(body, request)
        _write_once(paths["verification"], serialize_json(verification))
        completed = monotonic()
        outcome = {
            **identity,
            "utc_completion": utc_now(),
            "process_monotonic_completion": completed,
            "state": "completed_verified",
            "http_status": 200,
            "redirect_count": 0,
            "automatic_retries": 0,
            "failure_reason": None,
            "byte_count": len(body),
            "row_count": verification["lineups_row_count"],
            "raw_sha256": verification["raw_sha256"],
            "canonical_json_sha256": verification["canonical_json_sha256"],
            "response_disposition": "completed_verified",
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        return outcome
    except requests.RequestException as exc:
        reason = f"transport:{type(exc).__name__}"
        outcome = {
            **identity,
            "utc_completion": utc_now(),
            "process_monotonic_completion": monotonic(),
            "state": "failed_or_quarantined",
            "http_status": None,
            "redirect_count": 0,
            "automatic_retries": 0,
            "failure_reason": reason,
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        _write_once(paths["quarantine"], serialize_json({**identity, "state": "failed_or_quarantined", "reason": reason, "diagnostics": {}}))
        raise ContinuationError(reason) from exc
    except ResponseVerificationError as exc:
        redirected = False if response is None else bool(
            response.is_redirect or response.is_permanent_redirect or 300 <= response.status_code < 400
        )
        body = b"" if response is None else response.content
        outcome = {
            **identity,
            "utc_completion": utc_now(),
            "process_monotonic_completion": monotonic(),
            "state": "failed_or_quarantined",
            "http_status": None if response is None else response.status_code,
            "redirect_count": 1 if redirected else 0,
            "automatic_retries": 0,
            "failure_reason": str(exc),
            "byte_count": len(body),
            "raw_sha256": None if response is None else sha256_bytes(body),
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        _write_once(paths["quarantine"], serialize_json({
            **identity,
            "state": "failed_or_quarantined",
            "reason": str(exc),
            "diagnostics": exc.diagnostics,
        }))
        raise ContinuationError(str(exc)) from exc


def _full_season_path(trigger: Mapping[str, Any]) -> Path:
    return Path(
        "cache/phase3f-r2b.2/protected-final-target"
    ) / f"{int(trigger['ordinal']):02d}-{trigger['team_id']}-{trigger['measure'].lower()}" / "verified-response.bin"


def authenticate_full_season_bodies(project_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    plan = _read_json(project_root / R2C1_PLAN)
    triggers = plan.get("authenticated_exact_250_triggers")
    if not isinstance(triggers, list) or len(triggers) != 4:
        raise ContinuationError("four authenticated full-season triggers are required")
    inventory = _read_json(project_root / "planning/phase3f-r2b.2/request_inventory.json")
    by_ordinal = {item["ordinal"]: item for item in inventory}
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for trigger in triggers:
        request = by_ordinal.get(trigger["ordinal"])
        if not isinstance(request, dict) or request.get("request_id") != trigger["request_id"]:
            raise ContinuationError("full-season request inventory linkage mismatch")
        body_path = project_root / _full_season_path(trigger)
        if _fingerprint(body_path) != {"bytes": trigger["bytes"], "sha256": trigger["raw_sha256"]}:
            raise ContinuationError("full-season body fingerprint mismatch")
        directory = body_path.parent
        outcome = _read_json(directory / "attempt-1-outcome.json")
        verification = _read_json(directory / "verification.json")
        if (
            outcome.get("state") != "completed_verified"
            or outcome.get("row_count") != 250
            or outcome.get("raw_sha256") != trigger["raw_sha256"]
            or outcome.get("canonical_json_sha256") != trigger["canonical_json_sha256"]
            or verification.get("canonical_json_sha256") != trigger["canonical_json_sha256"]
        ):
            raise ContinuationError("full-season verification metadata mismatch")
        body = body_path.read_bytes()
        try:
            structural = validate_response_contract(body, request)
            payload = strict_json_bytes(body)
        except (ContractError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ContinuationError(f"full-season response validation failed: {exc}") from exc
        if sha256_bytes(canonical_json_bytes(payload)) != trigger["canonical_json_sha256"]:
            raise ContinuationError("full-season canonical JSON hash mismatch")
        lineups = _named_lineups(payload)
        rows = [dict(zip(lineups["headers"], row)) for row in lineups["rowSet"]]
        keys = [canonical_pair(row["GROUP_ID"]) for row in rows]
        if len(keys) != 250 or len(set(keys)) != 250:
            raise ContinuationError("full-season pair population is not 250 unique canonical keys")
        output[(trigger["team_id"], trigger["measure"])] = {
            **trigger,
            "path": _full_season_path(trigger).as_posix(),
            "keys": set(keys),
            "structural": structural,
        }
    return output


def _pairs(values: set[tuple[str, str]]) -> list[list[str]]:
    return [list(item) for item in sorted(values, key=lambda pair: (int(pair[0]), int(pair[1])))]


def _verification_keys(value: Mapping[str, Any]) -> set[tuple[str, str]]:
    return {tuple(item) for item in value["canonical_pair_keys"]}


def final_population_disposition(evidence_classification: str) -> str:
    """Map only the three frozen R2C.1 evidence classifications to readiness action."""

    if evidence_classification == "proven_non_exhaustive":
        return "exclude_whole_team_from_final_test_population"
    if evidence_classification == "operationally_resolved_no_observed_omission":
        return "include_direct_full_season_population_when_final_test_is_later_built"
    if evidence_classification == "recovery_unresolved":
        return "unresolved_block_final_test_readiness"
    raise ContinuationError("unknown frozen evidence classification")


def reconcile_teams(
    project_root: Path,
    output_root: Path,
    ordinal_one: Mapping[str, Any],
    requests_value: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Compare complementary-window pair populations with direct full-season keys."""

    if any(classify_request_state(output_root, request) != "completed_verified" for request in requests_value):
        raise ContinuationError("all seven continuation requests must be completed_verified")
    full = authenticate_full_season_bodies(project_root)
    verifications: dict[tuple[str, str, str], dict[str, Any]] = {
        (ordinal_one["team_id"], ordinal_one["window"], ordinal_one["measure"]): dict(ordinal_one)
    }
    for request in requests_value:
        verification = _read_json(request_paths(output_root, request)["verification"])
        verifications[(request["team_id"], request["window"]["name"], request["measure"])] = verification
    results = []
    for team_id, team_name in (("1610612754", "Indiana Pacers"), ("1610612763", "Memphis Grizzlies")):
        windows: dict[str, Any] = {}
        union: set[tuple[str, str]] = set()
        base_only_all: set[tuple[str, str]] = set()
        advanced_only_all: set[tuple[str, str]] = set()
        team_verifications = []
        for window in ("early", "late"):
            base = verifications[(team_id, window, "Base")]
            advanced = verifications[(team_id, window, "Advanced")]
            team_verifications.extend((base, advanced))
            base_keys = _verification_keys(base)
            advanced_keys = _verification_keys(advanced)
            base_only = base_keys - advanced_keys
            advanced_only = advanced_keys - base_keys
            base_only_all |= base_only
            advanced_only_all |= advanced_only
            union |= base_keys | advanced_keys
            windows[window] = {
                "base_count": len(base_keys),
                "advanced_count": len(advanced_keys),
                "base_advanced_keys_equal": not base_only and not advanced_only,
                "base_only_keys": _pairs(base_only),
                "advanced_only_keys": _pairs(advanced_only),
                "zero_possession_pair_keys": advanced["zero_possession_pair_keys"],
            }
        full_base = full[(team_id, "Base")]
        full_advanced = full[(team_id, "Advanced")]
        full_base_only = full_base["keys"] - full_advanced["keys"]
        full_advanced_only = full_advanced["keys"] - full_base["keys"]
        base_only_all |= full_base_only
        advanced_only_all |= full_advanced_only
        full_keys = full_base["keys"] | full_advanced["keys"]
        found = full_keys & union
        full_only = full_keys - union
        recovered_only = union - full_keys
        exposure = []
        for pair in sorted(recovered_only, key=lambda value: (int(value[0]), int(value[1]))):
            text = f"{pair[0]}-{pair[1]}"
            early = float(verifications[(team_id, "early", "Advanced")]["possession_by_pair_key"].get(text, 0.0))
            late = float(verifications[(team_id, "late", "Advanced")]["possession_by_pair_key"].get(text, 0.0))
            exposure.append({
                "canonical_pair_key": list(pair),
                "early_possessions": early,
                "late_possessions": late,
                "summed_possessions": early + late,
                "potentially_meets_poss_ge_150": early + late >= 150.0,
            })
        duplicate_count = sum(item["duplicate_count"] for item in team_verifications)
        malformed_count = sum(item["malformed_pair_count"] for item in team_verifications)
        same_player_count = sum(item["same_player_count"] for item in team_verifications)
        record = {
            "full_season_evidence_authenticated": True,
            "all_four_recovery_responses_present": True,
            "all_four_recovery_responses_authenticated": True,
            "all_four_recovery_responses_structurally_valid": True,
            "complete_complementary_date_coverage": True,
            "every_individual_window_below_250": all(item["lineups_row_count"] < 250 for item in team_verifications),
            "early_base_advanced_keys_equal": windows["early"]["base_advanced_keys_equal"],
            "late_base_advanced_keys_equal": windows["late"]["base_advanced_keys_equal"],
            "window_union_equals_full_season_keys": not recovered_only and not full_only,
            "recovered_only_keys_validated": not (
                duplicate_count or malformed_count or same_player_count or base_only_all or advanced_only_all
            ),
            "conflicting_state": False,
            "failed_or_quarantined": False,
            "early_base_pair_row_count": windows["early"]["base_count"],
            "early_advanced_pair_row_count": windows["early"]["advanced_count"],
            "late_base_pair_row_count": windows["late"]["base_count"],
            "late_advanced_pair_row_count": windows["late"]["advanced_count"],
            "recovered_only_count": len(recovered_only),
            "full_season_only_count": len(full_only),
            "duplicate_count": duplicate_count,
            "malformed_pair_count": malformed_count,
            "same_player_count": same_player_count,
            "base_only_count": len(base_only_all),
            "advanced_only_count": len(advanced_only_all),
        }
        decision = evaluate_disposition(record)
        final_disposition = final_population_disposition(decision.disposition)
        results.append({
            "version": VERSION,
            "team_id": team_id,
            "team_name": team_name,
            "full_season_key_count": len(full_keys),
            "full_season_base_count": len(full_base["keys"]),
            "full_season_advanced_count": len(full_advanced["keys"]),
            "full_season_base_advanced_keys_equal": not full_base_only and not full_advanced_only,
            "early_window_count": len(_verification_keys(verifications[(team_id, "early", "Base")])),
            "late_window_count": len(_verification_keys(verifications[(team_id, "late", "Base")])),
            "window_union_count": len(union),
            "full_season_keys_found_in_union_count": len(found),
            "full_season_only_count": len(full_only),
            "full_season_only_keys": _pairs(full_only),
            "recovered_only_count": len(recovered_only),
            "recovered_only_keys": _pairs(recovered_only),
            "malformed_count": malformed_count,
            "duplicate_count": duplicate_count,
            "same_player_count": same_player_count,
            "base_only_count": len(base_only_all),
            "advanced_only_count": len(advanced_only_all),
            "windows": windows,
            "recovered_only_exposure": exposure,
            "recovered_only_summed_possessions": sum(item["summed_possessions"] for item in exposure),
            "recovered_only_pairs_potentially_meeting_poss_ge_150": sum(
                item["potentially_meets_poss_ge_150"] for item in exposure
            ),
            "disposition_input": record,
            "evidence_classification": decision.disposition,
            "disposition_reason_codes": list(decision.reason_codes),
            "final_test_population_disposition": final_disposition,
            "directly_proved": (
                "direct full-season response is non-exhaustive"
                if decision.disposition == "proven_non_exhaustive"
                else "no omission observed under the frozen complementary-window design"
            ),
            "global_population_exhaustiveness_proved": False,
            "rating_aggregation_performed": False,
            "target_reconstruction_performed": False,
        })
    return results


def _source_binding(project_root: Path) -> dict[str, Any]:
    return {
        "implementation": {"path": SOURCE_PATH.as_posix(), **_fingerprint(project_root / SOURCE_PATH)},
        "cli": {"path": CLI_PATH.as_posix(), **_fingerprint(project_root / CLI_PATH)},
    }


def prepare_checkpoint(project_root: Path, output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    """Create the write-once authorization and ordinal-1 verification before transport."""

    root = Path(project_root).resolve()
    destination = Path(output_root)
    if not destination.is_absolute():
        destination = (root / destination).resolve()
    if destination != (root / OUTPUT_ROOT).resolve():
        raise ContinuationError("output root differs from the audited R2D.2 destination")
    if destination.exists() or destination.is_symlink():
        raise ContinuationError("R2D.2 write-once namespace already exists")
    git = _assert_git_identity(root)
    original, requests_value = load_authorized_requests(root)
    preservation = preservation_fingerprints(root)
    ordinal_one, first_request = offline_revalidate_indiana(root)
    if first_request.get("ordinal") != 1 or any(
        item["original_recovery_ordinal"] == 1 for item in requests_value
    ):
        raise ContinuationError("ordinal-1 network prohibition failed")
    visible = _git_visible_inventory(root)
    authorization = {
        "version": VERSION,
        "phase": PHASE,
        "created_at_utc": utc_now(),
        "git": git,
        "required_initial_clean_worktree_and_index": True,
        "git_visible_checkpoint_files": visible,
        "source_binding": _source_binding(root),
        "network_authorized_identity_count": 7,
        "network_attempt_limit_per_identity": 1,
        "automatic_retry_limit": 0,
        "indiana_early_base_network_prohibited": True,
        "authorized_requests": requests_value,
        "ordered_original_recovery_ordinals": list(range(2, 9)),
        "output_root": OUTPUT_ROOT.as_posix(),
        "transport": {
            "url": URL,
            "headers": dict(RESEARCH_HEADERS),
            "trust_env": False,
            "allow_redirects": False,
            "timeout_seconds": TIMEOUT_SECONDS,
            "automatic_retries": 0,
            "sequential": True,
            "minimum_monotonic_completion_to_next_start_seconds": MINIMUM_PACING_SECONDS,
        },
        "preserved_namespace_fingerprints_before": preservation,
        "original_r2d_state": "failed_or_quarantined",
        "original_r2d_authorization_sha256": _fingerprint(root / R2D_AUTHORIZATION)["sha256"],
        "r2d1_continuation_plan_sha256": _fingerprint(root / CONTINUATION_PLAN)["sha256"],
        "scope": {
            "population_reconciliation": True,
            "final_test_construction": False,
            "player_profile_join": False,
            "preprocessing": False,
            "estimator": False,
            "prediction": False,
            "metric": False,
            "model_serialization": False,
        },
    }
    preflight = {
        "version": VERSION,
        "status": "passed",
        "completed_before_network": True,
        "git": git,
        "r2d1_artifacts_audited_identity_match": True,
        "original_r2d_permanently_failed_and_quarantined": True,
        "indiana_and_memphis_initially_unresolved": True,
        "prior_r2d2_namespace_absent": True,
        "seven_continuation_identities_exact": True,
        "indiana_early_base_absent_from_network_inventory": True,
        "indiana_early_base_network_prohibited": True,
        "offline_indiana_revalidation": "passed",
        "offline_body_reference": ordinal_one["body_reference"],
        "preserved_namespace_fingerprints_before": preservation,
    }
    _write_once(destination / "authorization.json", serialize_json(authorization))
    _write_once(destination / "preflight.json", serialize_json(preflight))
    _write_once(destination / "01-1610612754-early-base" / "offline-verification.json", serialize_json(ordinal_one))
    return {"authorization": authorization, "preflight": preflight, "ordinal_one": ordinal_one}


def _validate_authorization(project_root: Path, output_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    authorization = _read_json(output_root / "authorization.json")
    _assert_git_identity(project_root)
    _, current = load_authorized_requests(project_root)
    if authorization.get("authorized_requests") != current:
        raise ContinuationError("authorized seven-request inventory changed")
    if authorization.get("source_binding") != _source_binding(project_root):
        raise ContinuationError("executing source or CLI differs from authorization")
    if authorization.get("git_visible_checkpoint_files") != _git_visible_inventory(project_root):
        raise ContinuationError("Git-visible checkpoint inventory changed")
    expected_transport = {
        "url": URL,
        "headers": dict(RESEARCH_HEADERS),
        "trust_env": False,
        "allow_redirects": False,
        "timeout_seconds": TIMEOUT_SECONDS,
        "automatic_retries": 0,
        "sequential": True,
        "minimum_monotonic_completion_to_next_start_seconds": MINIMUM_PACING_SECONDS,
    }
    if authorization.get("transport") != expected_transport:
        raise ContinuationError("transport authorization changed")
    if preservation_fingerprints(project_root) != authorization.get("preserved_namespace_fingerprints_before"):
        raise ContinuationError("preserved evidence changed before acquisition")
    ordinal_one, _ = offline_revalidate_indiana(project_root)
    if _read_json(output_root / "01-1610612754-early-base/offline-verification.json") != ordinal_one:
        raise ContinuationError("ordinal-1 continuation verification record differs from replay")
    return authorization, current


def _execution_paths(output_root: Path) -> dict[str, Path]:
    return {
        "start": output_root / "execution/official-invocation-start.json",
        "outcome": output_root / "execution/official-invocation-outcome.json",
    }


def _write_invocation_outcome(output_root: Path, exit_code: int, message: str) -> None:
    _write_once(_execution_paths(output_root)["outcome"], serialize_json({
        "version": VERSION,
        "official_invocation_number": 1,
        "utc_completion": utc_now(),
        "exit_code": exit_code,
        "message": message,
    }))


def _write_manifest(output_root: Path) -> dict[str, Any]:
    files = []
    manifest_path = output_root / "artifact-hashes.json"
    for path in sorted((item for item in output_root.rglob("*") if item.is_file() and item != manifest_path), key=lambda item: item.as_posix()):
        files.append({"path": path.relative_to(output_root).as_posix(), **_fingerprint(path)})
    manifest = {
        "version": VERSION,
        "rule": "recursive SHA-256 over every file in the R2D.2 namespace except artifact-hashes.json itself",
        "artifact_count_excluding_manifest": len(files),
        "artifacts": files,
    }
    _write_once(manifest_path, serialize_json(manifest))
    return manifest


def execute_authorized_continuation(
    project_root: Path,
    output_root: Path = OUTPUT_ROOT,
    *,
    session_factory: Callable[[], requests.Session] = create_session,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Make exactly seven sequential attempts, then reconcile and stop."""

    root = Path(project_root).resolve()
    destination = Path(output_root)
    if not destination.is_absolute():
        destination = (root / destination).resolve()
    if destination != (root / OUTPUT_ROOT).resolve():
        raise ContinuationError("output root differs from audited R2D.2 destination")
    execution = _execution_paths(destination)
    if execution["start"].exists() or execution["outcome"].exists():
        raise ContinuationError("official continuation invocation already exists")
    _write_once(execution["start"], serialize_json({
        "version": VERSION,
        "official_invocation_number": 1,
        "utc_start": utc_now(),
        "command_argv": list(sys.argv),
        "working_directory": os.getcwd(),
        "python_executable": str(Path(sys.executable).resolve()),
    }))
    try:
        authorization, requests_value = _validate_authorization(root, destination)
        states = [classify_request_state(destination, request) for request in requests_value]
        if states != ["not_started"] * 7:
            raise ContinuationError(f"restart-safe state refusal: {states}")
        session = session_factory()
        outcomes = []
        previous_completion: float | None = None
        try:
            for request in requests_value:
                outcome = acquire_one(
                    request,
                    destination,
                    session,
                    previous_completion=previous_completion,
                    sleeper=sleeper,
                    monotonic=monotonic,
                )
                outcomes.append(outcome)
                previous_completion = outcome["process_monotonic_completion"]
        finally:
            session.close()
        if len(outcomes) != 7:
            raise ContinuationError("official invocation did not make exactly seven attempts")
        ordinal_one = _read_json(destination / "01-1610612754-early-base/offline-verification.json")
        teams = reconcile_teams(root, destination, ordinal_one, requests_value)
        gaps = [
            _read_json(request_paths(destination, request)["start"])["observed_post_sleep_monotonic_gap_seconds"]
            for request in requests_value[1:]
        ]
        pacing = {
            "version": VERSION,
            "governing_clock": "time.monotonic",
            "utc_role": "descriptive_only",
            "inter_attempt_gap_count": len(gaps),
            "inter_attempt_gaps_seconds": gaps,
            "minimum_inter_attempt_gap_seconds": min(gaps),
            "required_minimum_seconds": MINIMUM_PACING_SECONDS,
            "passed": min(gaps) >= MINIMUM_PACING_SECONDS,
        }
        dispositions = [{
            key: team[key]
            for key in (
                "team_id", "team_name", "evidence_classification",
                "disposition_reason_codes", "final_test_population_disposition",
                "directly_proved", "global_population_exhaustiveness_proved",
            )
        } for team in teams]
        unresolved = [item["team_name"] for item in dispositions if item["evidence_classification"] == "recovery_unresolved"]
        classification = (
            "CONDITIONAL PASS — acquisition complete but a team remains unresolved"
            if unresolved
            else "PASS — recovery continuation complete; Indiana and Memphis dispositions assigned; ready for read-only audit"
        )
        preservation_after = preservation_fingerprints(root)
        if preservation_after != authorization["preserved_namespace_fingerprints_before"]:
            raise ContinuationError("preserved evidence changed during continuation")
        _write_once(destination / "pacing.json", serialize_json(pacing))
        _write_once(destination / "indiana-reconciliation.json", serialize_json(teams[0]))
        _write_once(destination / "memphis-reconciliation.json", serialize_json(teams[1]))
        _write_once(destination / "team-dispositions.json", serialize_json(dispositions))
        summary = {
            "version": VERSION,
            "classification": classification,
            "official_invocation_count": 1,
            "authorized_network_identity_count": 7,
            "network_attempt_count": 7,
            "completed_verified_count": 7,
            "retry_count": 0,
            "redirect_count": 0,
            "failure_count": 0,
            "quarantine_count": 0,
            "offline_indiana_revalidation": "passed",
            "pacing_minimum_seconds": pacing["minimum_inter_attempt_gap_seconds"],
            "team_dispositions": {
                item["team_name"]: item["final_test_population_disposition"] for item in dispositions
            },
            "unresolved_teams": unresolved,
            "preserved_namespace_fingerprints_before": authorization["preserved_namespace_fingerprints_before"],
            "preserved_namespace_fingerprints_after": preservation_after,
            "unauthorized_request_count": 0,
            "final_test_rows_constructed": 0,
            "player_profile_join_operations": 0,
            "preprocessing_operations": 0,
            "estimator_operations": 0,
            "prediction_operations": 0,
            "model_metric_operations": 0,
            "model_serialization_operations": 0,
            "next_step": "one focused read-only audit",
        }
        _write_once(destination / "summary.json", serialize_json(summary))
        _write_invocation_outcome(destination, 0, classification)
        _write_manifest(destination)
        return {"summary": summary, "outcomes": outcomes, "teams": teams}
    except Exception as exc:
        if not execution["outcome"].exists():
            try:
                _write_invocation_outcome(destination, 1, f"{type(exc).__name__}: {exc}")
            except Exception:
                pass
        raise


def cache_only_replay(project_root: Path, output_root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    """Deterministically revalidate the completed checkpoint without transport or writes."""

    root = Path(project_root).resolve()
    destination = Path(output_root)
    if not destination.is_absolute():
        destination = (root / destination).resolve()
    authorization, requests_value = _validate_authorization(root, destination)
    if [classify_request_state(destination, request) for request in requests_value] != ["completed_verified"] * 7:
        raise ContinuationError("cache-only replay found incomplete request state")
    ordinal_one, _ = offline_revalidate_indiana(root)
    if _read_json(destination / "01-1610612754-early-base/offline-verification.json") != ordinal_one:
        raise ContinuationError("offline Indiana replay differs")
    teams = reconcile_teams(root, destination, ordinal_one, requests_value)
    for name, team in zip(("indiana-reconciliation.json", "memphis-reconciliation.json"), teams):
        if _read_json(destination / name) != team:
            raise ContinuationError(f"deterministic reconciliation replay differs: {name}")
    recorded_dispositions = _read_json(destination / "team-dispositions.json")
    if [item["final_test_population_disposition"] for item in recorded_dispositions] != [
        item["final_test_population_disposition"] for item in teams
    ]:
        raise ContinuationError("recorded team dispositions differ from replay")
    manifest = _read_json(destination / "artifact-hashes.json")
    for item in manifest.get("artifacts", []):
        if _fingerprint(destination / item["path"]) != {"bytes": item["bytes"], "sha256": item["sha256"]}:
            raise ContinuationError(f"artifact hash mismatch: {item['path']}")
    if preservation_fingerprints(root) != authorization["preserved_namespace_fingerprints_before"]:
        raise ContinuationError("preserved evidence changed at replay")
    outcome = _read_json(_execution_paths(destination)["outcome"])
    if outcome.get("official_invocation_number") != 1 or outcome.get("exit_code") != 0:
        raise ContinuationError("official invocation outcome is not successful")
    return {
        "verified": True,
        "network_requests": 0,
        "official_invocation_count": 1,
        "team_dispositions": {
            item["team_name"]: item["final_test_population_disposition"] for item in recorded_dispositions
        },
    }
