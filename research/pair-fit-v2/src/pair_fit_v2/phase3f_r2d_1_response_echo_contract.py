"""Offline-only Phase 3F-R2D.1 response-echo correction specification.

This module has no network, recovery-execution, reconciliation, dataset, or
model capability.  It authenticates the failed R2D checkpoint, applies one
field-specific response-echo comparator to the single quarantined response,
and writes a deterministic continuation specification.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from pair_fit_v2.phase3f_r2b_1_response_contract import (
    ContractError,
    validate_response_contract,
)


VERSION = "phase3f-r2d.1.response-echo-correction.v1"
PHASE = "Phase 3F-R2D.1 - Response-Echo Contract Correction"
CLASSIFICATION = (
    "PASS \u2014 Phase 3F-R2D.1 response-echo correction and continuation "
    "specification frozen; ready for read-only audit"
)
EXPECTED_HEAD = "f7f72eda75fecfeab044b6f0315f263b71af657d"
EXPECTED_BRANCH = "research/pair-fit-v2"

R2C1_PLAN = Path("planning/phase3f-r2c.1/corrected_recovery_plan.json")
R2C1_PLAN_BYTES = 131_714
R2C1_PLAN_SHA256 = "eeb762fa61608b7920ef418175c8c26d54bd7436f7fa5bbbca9982d089330c07"
R2B1_CONTRACT_IDENTITY = (
    "sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad"
)
TRANSPORT_CONTRACT = Path(
    "planning/phase3f-r2b.2.1/future_protected_transport_contract.json"
)
TRANSPORT_CONTRACT_BYTES = 4_074
TRANSPORT_CONTRACT_SHA256 = (
    "20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234"
)

R2D_AUTHORIZATION = Path("planning/phase3f-r2d/recovery_authorization.json")
R2D_AUTHORIZATION_BYTES = 35_696
R2D_AUTHORIZATION_SHA256 = (
    "5bbf18388958f8dcdc9cd61062391a3a4c47f9e357ff463e4270802bf6e1eb3e"
)
R2D_EVIDENCE_ROOT = Path("cache/phase3f-r2d/protected-recovery")
QUARANTINED_RESPONSE = R2D_EVIDENCE_ROOT / (
    "01-1610612754-early-base/attempt-1-response.bin"
)
QUARANTINED_RESPONSE_BYTES = 58_235
QUARANTINED_RESPONSE_SHA256 = (
    "9726387a7e3f3f6cae9656cf74d1d4194a0e1f4593bc5bb15b016bae9a072593"
)
QUARANTINED_RESPONSE_CANONICAL_SHA256 = (
    "09f5970be9c4a9fdc2ece0cdeeeeef0bc04b8afb2c84f257781e0a81e44f7213"
)
QUARANTINED_RESPONSE_MTIME_UTC = "2026-10-03T05:36:49.6738827Z"
QUARANTINED_RESPONSE_MTIME_NS = 1_791_005_809_673_882_700

OUTPUT_NAMESPACE = Path("planning/phase3f-r2d.1")
FUTURE_CONTINUATION_NAMESPACE = Path(
    "cache/phase3f-r2d.2/protected-recovery-continuation"
)
OUTPUT_FILES = (
    "response_echo_contract.json",
    "continuation_plan.json",
    "quarantined_response_assessment.json",
    "artifact_hashes.json",
    "summary.json",
)

FIRST_REQUEST_ID = (
    "teamdashlineups:1610612754:2025-26:regular-season:"
    "2025-10-21:2026-01-31:base"
)
FIRST_IDENTITY_SHA256 = (
    "8b30d755aa4c8f16002fb637d6cbdac2e2fff495a5c177013c08ed9655a67f78"
)
EXPECTED_FIELD_ORDER = (
    "DateFrom", "DateTo", "GameID", "GameSegment", "GroupQuantity",
    "LastNGames", "LeagueID", "Location", "MeasureType", "Month",
    "OpponentTeamID", "Outcome", "PORound", "PaceAdjust", "PerMode",
    "Period", "PlusMinus", "Rank", "Season", "SeasonSegment",
    "SeasonType", "ShotClockRange", "TeamID", "VsConference", "VsDivision",
)
DATE_FIELDS = frozenset({"DateFrom", "DateTo"})
NUMERIC_ECHO_FIELDS = frozenset({
    "GroupQuantity", "LastNGames", "Month", "OpponentTeamID", "Period", "TeamID",
})
EMPTY_NULL_FIELDS = frozenset({
    "GameID", "GameSegment", "Location", "Outcome", "SeasonSegment",
    "ShotClockRange", "VsConference", "VsDivision",
})
EXACT_STRING_FIELDS = frozenset({
    "LeagueID", "MeasureType", "PaceAdjust", "PerMode", "PlusMinus", "Rank",
    "Season", "SeasonType",
})
PERMITTED_EXTRA_FIELDS = {"ISTRound": None}
ISO_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
US_DATE_PATTERN = re.compile(r"^[0-9]{2}/[0-9]{2}/[0-9]{4}$")
DECIMAL_INTEGER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")

R2D_PINNED_FILES: dict[str, tuple[int, str]] = {
    "PHASE3F_R2D_EXACT_250_RECOVERY_ACQUISITION_POLICY.md": (
        8_674, "a10a7a36cf06d56ad01601409c8dc2c29413cfa4d4a2d2ee62f0bbb1a59a0ebe",
    ),
    "PHASE3F_R2D_EXACT_250_RECOVERY_ACQUISITION_REPORT.md": (
        12_507, "e68657e6911483f0377c2b1c7832ba67d3fce5b36e83db30be1acb1ba96eabfe",
    ),
    "src/pair_fit_v2/phase3f_r2d_recovery_acquisition.py": (
        68_430, "c5858fd5c9ca28cda4a60251cb1d77f1dba6a1433cb698a429f93e9f2994e901",
    ),
    "src/pair_fit_v2/phase3f_r2d_cli.py": (
        1_907, "019174917199ffa56bc50cb4365894c4cd47c4a3c0f4d767dc070fb829d3a187",
    ),
    "tests/test_phase3f_r2d_recovery_acquisition.py": (
        25_115, "21bb461df27339384aea103d0e6ee5055441c2e2270c3d84477fc4f70015e6bc",
    ),
    "cache/phase3f-r2d/protected-recovery/01-1610612754-early-base/attempt-1-start.json": (
        748, "9f81e72bb1a101e88775143e3b50be00a533dcef2fc9da91801651fd192c28e1",
    ),
    "cache/phase3f-r2d/protected-recovery/01-1610612754-early-base/attempt-1-response.bin": (
        QUARANTINED_RESPONSE_BYTES, QUARANTINED_RESPONSE_SHA256,
    ),
    "cache/phase3f-r2d/protected-recovery/01-1610612754-early-base/attempt-1-outcome.json": (
        678, "f9fad8a8dc790ceec0f89d32cad299d322f98c2bd458dddacbd2e8a2b0de79b4",
    ),
    "cache/phase3f-r2d/protected-recovery/01-1610612754-early-base/quarantine.json": (
        417, "81abba7da00f63d2b8eeabb225b604c7d6672881fc3b30d3014d0b571e250199",
    ),
    "cache/phase3f-r2d/protected-recovery/execution/official-invocation-start.json": (
        1_955, "59a3adc11f6f2b63fd70005c90fef7879d146b8f24f2519ea0c431a2d9ee3b4b",
    ),
    "cache/phase3f-r2d/protected-recovery/execution/official-invocation-outcome.json": (
        244, "54b1aab08150e9da465616e3d6313502efdf59f54be56372eac45320cb4675aa",
    ),
}
R2D_EVIDENCE_INVENTORY = frozenset(
    path for path in R2D_PINNED_FILES if path.startswith(R2D_EVIDENCE_ROOT.as_posix())
)


class EchoContractError(RuntimeError):
    """Raised when frozen inputs or offline output rules are violated."""


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_json_bytes(value: bytes) -> Any:
    def reject_constant(token: str) -> None:
        raise ValueError(f"non-standard JSON constant: {token}")

    return json.loads(
        value.decode("utf-8", errors="strict"), parse_constant=reject_constant
    )


def _read_json(path: Path) -> Any:
    return strict_json_bytes(path.read_bytes())


def _fingerprint(path: Path) -> dict[str, Any]:
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": sha256_bytes(body)}


def _assert_fingerprint(path: Path, size: int, digest: str, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise EchoContractError(f"{label} is missing or not a regular file: {path}")
    actual = _fingerprint(path)
    if actual != {"bytes": size, "sha256": digest}:
        raise EchoContractError(f"{label} fingerprint mismatch: {path}")
    return {"path": path.as_posix(), **actual}


def _git(project_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=project_root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _date_value(value: Any, *, sent: bool) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return None, "DATE_NON_STRING"
    pattern = ISO_DATE_PATTERN if sent else None
    if sent and pattern.fullmatch(value) is None:
        return None, "SENT_DATE_NOT_EXACT_ISO"
    if not sent and ISO_DATE_PATTERN.fullmatch(value):
        format_string = "%Y-%m-%d"
    elif not sent and US_DATE_PATTERN.fullmatch(value):
        format_string = "%m/%d/%Y"
    elif sent:
        format_string = "%Y-%m-%d"
    else:
        return None, "ECHO_DATE_FORMAT_NOT_ALLOWED"
    try:
        parsed = datetime.strptime(value, format_string).date()
    except ValueError:
        return None, "DATE_INVALID_CALENDAR_VALUE"
    return parsed.isoformat(), None


def _base_comparison(field: str, sent: Any, echoed: Any) -> dict[str, Any]:
    return {
        "field": field,
        "sent_raw_value": sent,
        "echoed_raw_value": echoed,
        "comparison_rule": None,
        "normalized_sent_value": None,
        "normalized_echoed_value": None,
        "equivalent": False,
        "reason_code": None,
        "mismatch_reason": None,
    }


def _finish(entry: dict[str, Any], equivalent: bool, reason: str) -> dict[str, Any]:
    entry["equivalent"] = equivalent
    entry["reason_code"] = reason
    entry["mismatch_reason"] = None if equivalent else reason
    return entry


def _compare_date(field: str, sent: Any, echoed: Any) -> dict[str, Any]:
    entry = _base_comparison(field, sent, echoed)
    entry["comparison_rule"] = "strict_iso_request_and_iso_or_us_echo_same_calendar_date"
    sent_normalized, sent_error = _date_value(sent, sent=True)
    echo_normalized, echo_error = _date_value(echoed, sent=False)
    entry["normalized_sent_value"] = sent_normalized
    entry["normalized_echoed_value"] = echo_normalized
    if sent_error:
        return _finish(entry, False, sent_error)
    if echo_error:
        return _finish(entry, False, echo_error)
    if sent_normalized != echo_normalized:
        return _finish(entry, False, "DATE_CALENDAR_DAY_MISMATCH")
    reason = "EXACT_ISO_DATE_MATCH" if sent == echoed else "STRICT_DATE_NORMALIZATION_EQUIVALENT"
    return _finish(entry, True, reason)


def _valid_poround_exact(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value >= 0
    return isinstance(value, str) and (
        value == "" or DECIMAL_INTEGER_PATTERN.fullmatch(value) is not None
    )


def _compare_poround(field: str, sent: Any, echoed: Any) -> dict[str, Any]:
    entry = _base_comparison(field, sent, echoed)
    entry["comparison_rule"] = "poround_exact_or_empty_string_to_integer_zero"
    if type(sent) is type(echoed) and sent == echoed and _valid_poround_exact(sent):
        return _finish(entry, True, "POROUND_EXACT_FROZEN_VALUE_MATCH")
    if sent == "" and type(echoed) is int and echoed == 0:
        entry["normalized_sent_value"] = ""
        entry["normalized_echoed_value"] = ""
        return _finish(entry, True, "POROUND_EMPTY_TO_INTEGER_ZERO_EQUIVALENT")
    return _finish(entry, False, "POROUND_NOT_EQUIVALENT")


def _compare_numeric(field: str, sent: Any, echoed: Any) -> dict[str, Any]:
    entry = _base_comparison(field, sent, echoed)
    entry["comparison_rule"] = "exact_frozen_decimal_string_or_json_integer_echo"
    if not isinstance(sent, str) or DECIMAL_INTEGER_PATTERN.fullmatch(sent) is None:
        return _finish(entry, False, "SENT_NUMERIC_VALUE_NOT_FROZEN_DECIMAL_STRING")
    entry["normalized_sent_value"] = sent
    if isinstance(echoed, str) and echoed == sent:
        entry["normalized_echoed_value"] = echoed
        return _finish(entry, True, "EXACT_STRING_MATCH")
    if type(echoed) is int and echoed >= 0 and str(echoed) == sent:
        entry["normalized_echoed_value"] = str(echoed)
        return _finish(entry, True, "NUMERIC_STRING_TO_INTEGER_EQUIVALENT")
    return _finish(entry, False, "NUMERIC_ECHO_NOT_EQUIVALENT")


def _compare_empty_null(field: str, sent: Any, echoed: Any) -> dict[str, Any]:
    entry = _base_comparison(field, sent, echoed)
    entry["comparison_rule"] = "exact_empty_string_or_empty_string_to_json_null"
    if sent != "":
        return _finish(entry, False, "SENT_EMPTY_FILTER_NOT_EMPTY_STRING")
    entry["normalized_sent_value"] = ""
    if echoed == "" and isinstance(echoed, str):
        entry["normalized_echoed_value"] = ""
        return _finish(entry, True, "EXACT_EMPTY_STRING_MATCH")
    if echoed is None:
        entry["normalized_echoed_value"] = ""
        return _finish(entry, True, "EMPTY_STRING_TO_JSON_NULL_EQUIVALENT")
    return _finish(entry, False, "EMPTY_FILTER_ECHO_NOT_EQUIVALENT")


def _compare_exact_string(field: str, sent: Any, echoed: Any) -> dict[str, Any]:
    entry = _base_comparison(field, sent, echoed)
    entry["comparison_rule"] = "exact_string_identity"
    if isinstance(sent, str) and isinstance(echoed, str) and sent == echoed:
        return _finish(entry, True, "EXACT_STRING_MATCH")
    return _finish(entry, False, "EXACT_STRING_MISMATCH")


def compare_response_echo(
    sent_parameters: Mapping[str, Any], returned_parameters: Any
) -> dict[str, Any]:
    """Compare every frozen field and every returned extra without short-circuiting."""

    if not isinstance(sent_parameters, Mapping):
        raise EchoContractError("sent parameters must be a mapping")
    returned = returned_parameters if isinstance(returned_parameters, Mapping) else {}
    comparisons: list[dict[str, Any]] = []
    missing: list[str] = []
    for field in EXPECTED_FIELD_ORDER:
        sent = sent_parameters.get(field)
        if field not in sent_parameters:
            entry = _base_comparison(field, None, None)
            entry["comparison_rule"] = "required_frozen_request_field"
            comparisons.append(_finish(entry, False, "MISSING_SENT_FIELD"))
            continue
        if field not in returned:
            missing.append(field)
            entry = _base_comparison(field, sent, None)
            entry["comparison_rule"] = "required_returned_field"
            comparisons.append(_finish(entry, False, "MISSING_ECHOED_FIELD"))
            continue
        echoed = returned[field]
        if field in DATE_FIELDS:
            entry = _compare_date(field, sent, echoed)
        elif field == "PORound":
            entry = _compare_poround(field, sent, echoed)
        elif field in NUMERIC_ECHO_FIELDS:
            entry = _compare_numeric(field, sent, echoed)
        elif field in EMPTY_NULL_FIELDS:
            entry = _compare_empty_null(field, sent, echoed)
        elif field in EXACT_STRING_FIELDS:
            entry = _compare_exact_string(field, sent, echoed)
        else:  # pragma: no cover - frozen partition assertion below makes this unreachable
            entry = _base_comparison(field, sent, echoed)
            entry["comparison_rule"] = "unclassified_field"
            entry = _finish(entry, False, "UNCLASSIFIED_EXPECTED_FIELD")
        comparisons.append(entry)

    extras: list[dict[str, Any]] = []
    if isinstance(returned_parameters, Mapping):
        for field in sorted(set(returned) - set(EXPECTED_FIELD_ORDER)):
            value = returned[field]
            permitted = field in PERMITTED_EXTRA_FIELDS and value is None
            extras.append({
                "field": field,
                "echoed_raw_value": value,
                "comparison_rule": "allowlisted_istround_exact_json_null_only",
                "permitted": permitted,
                "reason_code": (
                    "PERMITTED_ISTROUND_NULL_EXTRA"
                    if permitted else "UNEXPECTED_OR_INVALID_EXTRA_FIELD"
                ),
            })
    malformed = not isinstance(returned_parameters, Mapping)
    mismatches = [entry for entry in comparisons if not entry["equivalent"]]
    mismatches.extend(entry for entry in extras if not entry["permitted"])
    if malformed:
        mismatches.append({
            "field": None,
            "reason_code": "RETURNED_PARAMETERS_NOT_OBJECT",
            "mismatch_reason": "RETURNED_PARAMETERS_NOT_OBJECT",
        })
    return {
        "contract_version": VERSION,
        "passed": not mismatches,
        "compared_field_order": list(EXPECTED_FIELD_ORDER),
        "fields": comparisons,
        "missing_expected_fields": missing,
        "extra_returned_fields": extras,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "full_mismatch_collection": True,
    }


def verify_initial_response_echo(
    sent_parameters: Mapping[str, Any], returned_parameters: Any
) -> dict[str, Any]:
    """Initial verification entry point; delegates to the sole comparator."""

    return compare_response_echo(sent_parameters, returned_parameters)


def verify_replay_response_echo(
    sent_parameters: Mapping[str, Any], returned_parameters: Any
) -> dict[str, Any]:
    """Replay/restart entry point; delegates to the sole comparator."""

    return compare_response_echo(sent_parameters, returned_parameters)


def _identity_sha256(request: Mapping[str, Any]) -> str:
    value = {
        key: item for key, item in request.items()
        if key not in {
            "canonical_request_identity_sha256", "authorization_phase",
            "network_authorized", "attempt_limit", "r2d_output_namespace",
        }
    }
    return sha256_bytes(serialize_json(value))


def _assert_record(record: Mapping[str, Any], request: Mapping[str, Any], label: str) -> None:
    expected = {
        "request_id": request["request_id"],
        "ordinal": 1,
        "canonical_request_identity_sha256": FIRST_IDENTITY_SHA256,
        "attempt_number": 1,
    }
    if any(record.get(key) != value for key, value in expected.items()):
        raise EchoContractError(f"{label} request identity mismatch")


def _authenticate_r2d(project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    authorization_path = project_root / R2D_AUTHORIZATION
    authorization_fp = _assert_fingerprint(
        authorization_path, R2D_AUTHORIZATION_BYTES, R2D_AUTHORIZATION_SHA256,
        "original R2D authorization",
    )
    authorization = _read_json(authorization_path)
    if authorization.get("required_starting_head") != EXPECTED_HEAD:
        raise EchoContractError("original R2D required HEAD changed")
    requests_value = authorization.get("authorized_requests")
    if not isinstance(requests_value, list) or len(requests_value) != 8:
        raise EchoContractError("original R2D authorization no longer has eight requests")
    request = requests_value[0]
    if (
        request.get("request_id") != FIRST_REQUEST_ID
        or request.get("ordinal") != 1
        or request.get("canonical_request_identity_sha256") != FIRST_IDENTITY_SHA256
        or _identity_sha256(request) != FIRST_IDENTITY_SHA256
    ):
        raise EchoContractError("original R2D request 1 identity mismatch")

    observed_files = {
        path.relative_to(project_root).as_posix()
        for path in (project_root / R2D_EVIDENCE_ROOT).rglob("*") if path.is_file()
    }
    if observed_files != R2D_EVIDENCE_INVENTORY:
        raise EchoContractError("original R2D evidence inventory changed")
    pinned = []
    for relative, (size, digest) in R2D_PINNED_FILES.items():
        entry = _assert_fingerprint(project_root / relative, size, digest, "pinned R2D file")
        entry["path"] = relative
        pinned.append(entry)

    start = _read_json(project_root / R2D_EVIDENCE_ROOT / "01-1610612754-early-base/attempt-1-start.json")
    outcome = _read_json(project_root / R2D_EVIDENCE_ROOT / "01-1610612754-early-base/attempt-1-outcome.json")
    quarantine = _read_json(project_root / R2D_EVIDENCE_ROOT / "01-1610612754-early-base/quarantine.json")
    invocation_start = _read_json(project_root / R2D_EVIDENCE_ROOT / "execution/official-invocation-start.json")
    invocation_outcome = _read_json(project_root / R2D_EVIDENCE_ROOT / "execution/official-invocation-outcome.json")
    for label, record in (("start", start), ("outcome", outcome), ("quarantine", quarantine)):
        _assert_record(record, request, label)
    if outcome.get("state") != "failed_or_quarantined" or quarantine.get("state") != "failed_or_quarantined":
        raise EchoContractError("original R2D failed/quarantined state changed")
    if outcome.get("http_status") != 200 or outcome.get("automatic_retries") != 0:
        raise EchoContractError("original R2D outcome transport facts changed")
    if outcome.get("failure_reason") != "returned parameter mismatch: DateFrom":
        raise EchoContractError("original R2D failure reason changed")
    if invocation_start.get("invocation_number") != 1 or invocation_outcome.get("invocation_number") != 1:
        raise EchoContractError("original R2D invocation count changed")
    if invocation_outcome.get("exit_code") != 1:
        raise EchoContractError("original R2D failure outcome changed")
    for later in requests_value[1:]:
        slug = (
            f"{later['ordinal']:02d}-{later['team_id']}-"
            f"{later['window']['name']}-{later['measure'].lower()}"
        )
        if (project_root / R2D_EVIDENCE_ROOT / slug).exists():
            raise EchoContractError(f"R2D request {later['ordinal']} unexpectedly has evidence")
    prohibited_r2d_outputs = {
        "request_ledger.json", "response_fingerprints.json", "team_reconciliation.json",
        "team_dispositions.json", "readiness_effect.json", "artifact_hashes.json", "summary.json",
    }
    planning_inventory = {path.name for path in (project_root / "planning/phase3f-r2d").iterdir()}
    if planning_inventory != {"recovery_authorization.json"} or planning_inventory & prohibited_r2d_outputs:
        raise EchoContractError("failed R2D planning namespace changed")
    return authorization, {
        "authorization": {"path": R2D_AUTHORIZATION.as_posix(), **authorization_fp},
        "pinned_r2d_files": sorted(pinned, key=lambda item: item["path"]),
        "attempt_count": 1,
        "requests_2_through_8_evidence_absent": True,
        "reconciliation_and_readiness_artifacts_absent": True,
        "original_state": "failed_or_quarantined",
    }


def _namespace_fingerprint(project_root: Path, expected: Mapping[str, Any]) -> dict[str, Any]:
    relative_text = str(expected["namespace"])
    relative_root = Path(relative_text)
    root = project_root / relative_root
    if not root.is_dir() or root.is_symlink():
        raise EchoContractError(f"historical namespace missing: {relative_root.as_posix()}")
    files = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise EchoContractError(f"historical symlink prohibited: {path}")
        body = path.read_bytes()  # Opaque hashing only; protected bodies are not parsed.
        files.append({
            "path": path.relative_to(project_root).as_posix(),
            "bytes": len(body),
            "sha256": sha256_bytes(body),
            "mtime_ns": path.stat().st_mtime_ns,
        })
    inventory = {
        "namespace": relative_text,
        "file_count": len(files),
        "byte_count": sum(item["bytes"] for item in files),
        "inventory_sha256": sha256_bytes(serialize_json(files)),
        "files": files,
    }
    compact = {
        key: inventory[key]
        for key in ("namespace", "file_count", "byte_count", "inventory_sha256")
    }
    if compact != dict(expected):
        raise EchoContractError(f"historical namespace fingerprint changed: {relative_root}")
    return inventory


def _authenticate_governing_and_historical(
    project_root: Path, authorization: Mapping[str, Any]
) -> dict[str, Any]:
    _assert_fingerprint(
        project_root / R2C1_PLAN, R2C1_PLAN_BYTES, R2C1_PLAN_SHA256, "R2C.1 plan"
    )
    _assert_fingerprint(
        project_root / TRANSPORT_CONTRACT,
        TRANSPORT_CONTRACT_BYTES,
        TRANSPORT_CONTRACT_SHA256,
        "R2B.2.1 transport contract",
    )
    if authorization.get("response_contract_identity") != R2B1_CONTRACT_IDENTITY:
        raise EchoContractError("R2B.1 contract identity changed")
    namespaces = [
        _namespace_fingerprint(project_root, expected)
        for expected in authorization["historical_namespace_fingerprints_before"]
    ]
    git_files = []
    for expected in authorization["historical_git_visible_fingerprints"]:
        relative = expected["path"]
        actual = _assert_fingerprint(
            project_root / relative, expected["bytes"], expected["sha256"],
            "historical Git-visible file",
        )
        actual["path"] = relative
        git_files.append(actual)
    return {
        "r2c_1_plan": {
            "path": R2C1_PLAN.as_posix(), "bytes": R2C1_PLAN_BYTES,
            "sha256": R2C1_PLAN_SHA256,
        },
        "r2b_1_response_contract_identity": R2B1_CONTRACT_IDENTITY,
        "r2b_2_1_transport_contract": {
            "path": TRANSPORT_CONTRACT.as_posix(), "bytes": TRANSPORT_CONTRACT_BYTES,
            "sha256": TRANSPORT_CONTRACT_SHA256,
        },
        "historical_namespaces": namespaces,
        "historical_git_visible_files": git_files,
        "all_fingerprints_match_original_r2d_authorization": True,
    }


def _validate_structural(body: bytes, request: Mapping[str, Any]) -> dict[str, Any]:
    try:
        diagnostics = validate_response_contract(body, request)
    except ContractError as exc:
        raise EchoContractError(f"quarantined response structural validation failed: {exc}") from exc
    required = {
        "observed_result_set_order": ["Overall", "Lineups"],
        "overall_header_count": 57,
        "overall_row_count": 1,
        "lineups_header_count": 56,
        "lineups_row_count": 227,
        "canonical_unordered_pair_count": 227,
        "duplicate_canonical_pair_count": 0,
        "malformed_group_identifier_count": 0,
        "same_player_pair_count": 0,
        "invalid_player_id_count": 0,
        "row_width_error_count": 0,
    }
    if any(diagnostics.get(key) != value for key, value in required.items()):
        raise EchoContractError("quarantined response structural properties differ")
    return {key: diagnostics[key] for key in required} | {
        "strict_json_valid": True,
        "structurally_valid": True,
    }


def _response_contract_document() -> dict[str, Any]:
    return {
        "version": VERSION,
        "phase": PHASE,
        "scope": "TeamDashLineups response-echo comparison only",
        "authoritative_comparator": "compare_response_echo",
        "applicability": [
            "initial_response_verification", "offline_revalidation",
            "future_response_verification", "completed_state_replay",
            "restart_classification", "final_evidence_reconciliation",
        ],
        "full_mismatch_collection": True,
        "field_order": list(EXPECTED_FIELD_ORDER),
        "field_rules": {
            "DateFrom": "strict ISO request; exact ISO or MM/DD/YYYY echo; identical calendar day",
            "DateTo": "strict ISO request; exact ISO or MM/DD/YYYY echo; identical calendar day",
            "PORound": "exact valid frozen value or sent empty string to echoed JSON integer zero only",
            "numeric_echo_fields": {
                "fields": sorted(NUMERIC_ECHO_FIELDS),
                "rule": "exact frozen decimal string or same nonnegative JSON integer",
            },
            "empty_null_fields": {
                "fields": sorted(EMPTY_NULL_FIELDS),
                "rule": "sent empty string; echoed exact empty string or JSON null",
            },
            "exact_string_fields": {
                "fields": sorted(EXACT_STRING_FIELDS),
                "rule": "exact type-and-value string identity",
            },
        },
        "date_formats": {"sent": ["%Y-%m-%d"], "echoed": ["%Y-%m-%d", "%m/%d/%Y"]},
        "poround_rejections": ["string zero substitution", "null", "false", "float zero", "negative float zero", "nonzero integer", "missing", "array", "object", "whitespace"],
        "permitted_extra_fields": {
            "ISTRound": {
                "only_value": None,
                "basis": (
                    "legacy R2D compared expected keys only and therefore accepted this observed extra; "
                    "R2D.1 narrows that behavior to this field and exact JSON null"
                ),
            }
        },
        "unexpected_field_policy": "reject every non-allowlisted extra field",
        "missing_field_policy": "reject every missing expected field",
        "reason_codes": [
            "EXACT_ISO_DATE_MATCH", "STRICT_DATE_NORMALIZATION_EQUIVALENT",
            "DATE_NON_STRING", "SENT_DATE_NOT_EXACT_ISO", "ECHO_DATE_FORMAT_NOT_ALLOWED",
            "DATE_INVALID_CALENDAR_VALUE", "DATE_CALENDAR_DAY_MISMATCH",
            "POROUND_EXACT_FROZEN_VALUE_MATCH", "POROUND_EMPTY_TO_INTEGER_ZERO_EQUIVALENT",
            "POROUND_NOT_EQUIVALENT", "EXACT_STRING_MATCH",
            "NUMERIC_STRING_TO_INTEGER_EQUIVALENT", "NUMERIC_ECHO_NOT_EQUIVALENT",
            "SENT_NUMERIC_VALUE_NOT_FROZEN_DECIMAL_STRING",
            "EMPTY_STRING_TO_JSON_NULL_EQUIVALENT", "EXACT_EMPTY_STRING_MATCH",
            "EMPTY_FILTER_ECHO_NOT_EQUIVALENT", "SENT_EMPTY_FILTER_NOT_EMPTY_STRING",
            "EXACT_STRING_MISMATCH",
            "MISSING_SENT_FIELD", "MISSING_ECHOED_FIELD",
            "PERMITTED_ISTROUND_NULL_EXTRA", "UNEXPECTED_OR_INVALID_EXTRA_FIELD",
            "RETURNED_PARAMETERS_NOT_OBJECT", "UNCLASSIFIED_EXPECTED_FIELD",
        ],
        "historical_basis": {
            "date_behavior": "pinned R2D response and immutable R2D report",
            "poround_behavior": "Phase 1D endpoint convention and pinned R2D response",
            "numeric_null_and_exact_behavior": "legacy R2D _normalize comparison",
            "extra_field_behavior": "legacy R2D expected-field-only loop, narrowed here",
        },
        "prohibited": ["fuzzy matching", "general empty-to-zero normalization", "date parsing for non-date fields", "arbitrary extra fields", "legacy R2D comparator fallback"],
    }


def _continuation_plan(
    requests_value: Sequence[Mapping[str, Any]], response_reference: Mapping[str, Any]
) -> dict[str, Any]:
    remaining = []
    for network_ordinal, request in enumerate(requests_value[1:], start=1):
        remaining.append({
            "original_recovery_ordinal": request["ordinal"],
            "continuation_network_ordinal": network_ordinal,
            "request_id": request["request_id"],
            "canonical_request_identity_sha256": request["canonical_request_identity_sha256"],
            "endpoint": request["endpoint"],
            "team_id": request["team_id"],
            "team_name": request["team_name"],
            "window": request["window"],
            "measure": request["measure"],
            "parameters": request["parameters"],
            "future_output_namespace": request["future_output_namespace"],
            "continuation_output_namespace": (
                FUTURE_CONTINUATION_NAMESPACE
                / f"{request['ordinal']:02d}-{request['team_id']}-{request['window']['name']}-{request['measure'].lower()}"
            ).as_posix(),
            "attempt_limit": 1,
            "automatic_retries": 0,
            "present_authority": False,
        })
    if [item["original_recovery_ordinal"] for item in remaining] != list(range(2, 9)):
        raise EchoContractError("continuation ordinals are not exactly original R2C.1 ordinals 2-8")
    return {
        "version": VERSION,
        "phase": PHASE,
        "present_authority": "none",
        "original_failed_r2d": {
            "classification": "FAIL \u2014 authorized recovery acquisition or reconciliation failed",
            "state": "failed_or_quarantined",
            "request_id": FIRST_REQUEST_ID,
            "canonical_request_identity_sha256": FIRST_IDENTITY_SHA256,
            "quarantine_unchanged": True,
        },
        "reused_first_evidence_member": {
            **response_reference,
            "original_recovery_ordinal": 1,
            "network_request_prohibited": True,
            "counts_as_verified_only_after_separately_authorized_offline_revalidation": True,
            "copy_or_overwrite_prohibited": True,
            "continuation_verification_namespace": (
                FUTURE_CONTINUATION_NAMESPACE / "01-1610612754-early-base"
            ).as_posix(),
        },
        "offline_revalidation_prerequisite": {
            "separate_audited_committed_checkpoint_required": True,
            "separate_explicit_user_authorization_required": True,
            "reauthenticate_original_authorization_attempt_outcome_quarantine_and_body": True,
            "authoritative_comparator": "compare_response_echo",
            "failure_action": "stop_before_network_activity",
            "success_record_location": "new continuation namespace only",
            "original_r2d_verification_record_prohibited": True,
        },
        "continuation_output_namespace": FUTURE_CONTINUATION_NAMESPACE.as_posix(),
        "future_network_attempt_limit": 7,
        "automatic_retry_limit": 0,
        "remaining_network_identities": remaining,
        "continuation_order": [item["original_recovery_ordinal"] for item in remaining],
        "indiana_early_base_duplicate_request_prohibited": True,
        "stop_conditions": [
            "offline revalidation fails", "original evidence authentication fails",
            "corrected echo comparison fails", "structural validation fails",
            "any remaining identity transport or verification fails",
        ],
        "replay_consistency": {
            "same_comparator_required_for_all_verification_and_replay_paths": True,
            "literal_date_comparison_fallback_prohibited": True,
            "failed_r2d_comparator_import_or_call_prohibited": True,
        },
    }


def _assess_quarantined_response(
    project_root: Path,
    authorization: Mapping[str, Any],
    r2d_evidence: Mapping[str, Any],
    historical: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = authorization["authorized_requests"][0]
    response_path = project_root / QUARANTINED_RESPONSE
    body = response_path.read_bytes()
    payload = strict_json_bytes(body)
    canonical_digest = sha256_bytes(canonical_json_bytes(payload))
    if canonical_digest != QUARANTINED_RESPONSE_CANONICAL_SHA256:
        raise EchoContractError("quarantined response canonical hash mismatch")
    echo = verify_initial_response_echo(request["parameters"], payload.get("parameters"))
    structural = _validate_structural(body, request)
    eligible = echo["passed"] and structural["structurally_valid"]
    finding = (
        "eligible_for_future_offline_revalidation_under_corrected_echo_contract"
        if eligible else "not_eligible_for_future_reuse"
    )
    response_reference = {
        "path": QUARANTINED_RESPONSE.as_posix(),
        "bytes": len(body),
        "raw_sha256": sha256_bytes(body),
        "canonical_json_sha256": canonical_digest,
        "last_write_time_utc": QUARANTINED_RESPONSE_MTIME_UTC,
    }
    if response_path.stat().st_mtime_ns != QUARANTINED_RESPONSE_MTIME_NS:
        raise EchoContractError("quarantined response timestamp changed")
    assessment = {
        "version": VERSION,
        "phase": PHASE,
        "finding": finding,
        "eligible_for_future_reuse": eligible,
        "request": {
            "ordinal": 1,
            "request_id": request["request_id"],
            "canonical_request_identity_sha256": request["canonical_request_identity_sha256"],
            "team_id": request["team_id"],
            "team_name": request["team_name"],
            "window": request["window"],
            "measure": request["measure"],
            "parameters": request["parameters"],
        },
        "quarantined_response": response_reference,
        "original_evidence_authentication": r2d_evidence,
        "governing_and_historical_preservation": historical,
        "response_echo_comparison": echo,
        "all_representation_differences": [
            entry for entry in echo["fields"]
            if entry["sent_raw_value"] != entry["echoed_raw_value"]
        ] + echo["extra_returned_fields"],
        "all_unpermitted_mismatches": echo["mismatches"],
        "structural_validation": structural,
        "original_r2d_classification": "FAIL \u2014 authorized recovery acquisition or reconciliation failed",
        "original_r2d_state_unchanged": "failed_or_quarantined",
        "indiana_disposition": "recovery_unresolved",
        "memphis_disposition": "recovery_unresolved",
        "promotion_occurred": False,
        "completed_verification_created_in_r2d": False,
        "body_copied": False,
        "population_reconciliation_performed": False,
        "finding_scope": "eligibility for separately authorized future offline revalidation only",
    }
    return assessment, response_reference


def _validate_static_contract_partition() -> None:
    partition = DATE_FIELDS | NUMERIC_ECHO_FIELDS | EMPTY_NULL_FIELDS | EXACT_STRING_FIELDS | {"PORound"}
    if partition != set(EXPECTED_FIELD_ORDER):
        raise EchoContractError("frozen response-echo field partition is incomplete or overlapping")
    groups = [DATE_FIELDS, NUMERIC_ECHO_FIELDS, EMPTY_NULL_FIELDS, EXACT_STRING_FIELDS, {"PORound"}]
    for index, left in enumerate(groups):
        if any(set(left) & set(right) for right in groups[index + 1:]):
            raise EchoContractError("frozen response-echo field rules overlap")


def build_specification(project_root: Path, output_dir: Path) -> dict[str, Any]:
    """Authenticate, build in memory, then write the exact five artifacts once."""

    root = Path(project_root).resolve()
    destination = Path(output_dir)
    if not destination.is_absolute():
        destination = (root / destination).resolve()
    if destination.exists():
        raise EchoContractError(f"write-once namespace already exists: {destination}")
    _validate_static_contract_partition()
    if _git(root, "branch", "--show-current") != EXPECTED_BRANCH:
        raise EchoContractError("branch differs from required R2D.1 branch")
    if _git(root, "rev-parse", "HEAD") != EXPECTED_HEAD:
        raise EchoContractError("committed HEAD differs from required R2D.1 checkpoint")
    ahead, behind = _git(root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}").split()
    if (ahead, behind) != ("0", "0"):
        raise EchoContractError("upstream ahead/behind differs from 0/0")
    if _git(root, "diff", "--cached", "--name-only"):
        raise EchoContractError("index must be empty")
    if (root / FUTURE_CONTINUATION_NAMESPACE).exists():
        raise EchoContractError("future continuation namespace must be absent")

    authorization, r2d_evidence = _authenticate_r2d(root)
    historical = _authenticate_governing_and_historical(root, authorization)
    assessment, response_reference = _assess_quarantined_response(
        root, authorization, r2d_evidence, historical
    )
    if not assessment["eligible_for_future_reuse"]:
        raise EchoContractError("quarantined response is not eligible for future reuse")
    contract = _response_contract_document()
    continuation = _continuation_plan(authorization["authorized_requests"], response_reference)
    summary = {
        "version": VERSION,
        "classification": CLASSIFICATION,
        "network_requests_during_r2d_1": 0,
        "protected_requests": 0,
        "recovery_requests": 0,
        "response_promotions": 0,
        "original_r2d_classification": "FAIL \u2014 authorized recovery acquisition or reconciliation failed",
        "original_r2d_state": "failed_or_quarantined",
        "original_r2d_state_unchanged": True,
        "indiana": "recovery_unresolved",
        "memphis": "recovery_unresolved",
        "future_continuation_network_identities": 7,
        "future_continuation_authorized_now": False,
        "final_test_rows": 0,
        "estimator_operations": 0,
        "population_reconciliation_operations": 0,
        "dataset_operations": 0,
        "r2d_1_status": "awaiting_read_only_audit",
    }
    documents = {
        "response_echo_contract.json": contract,
        "continuation_plan.json": continuation,
        "quarantined_response_assessment.json": assessment,
        "summary.json": summary,
    }
    serialized = {name: serialize_json(value) for name, value in documents.items()}
    manifest = {
        "version": VERSION,
        "hash_algorithm": "SHA-256 over exact artifact bytes",
        "rule": (
            "nonrecursive SHA-256 over response_echo_contract.json, continuation_plan.json, "
            "quarantined_response_assessment.json, and summary.json; manifest excludes itself"
        ),
        "artifact_inventory": list(OUTPUT_FILES),
        "artifacts": {
            name: {"bytes": len(body), "sha256": sha256_bytes(body)}
            for name, body in sorted(serialized.items())
        },
    }
    serialized["artifact_hashes.json"] = serialize_json(manifest)
    if set(serialized) != set(OUTPUT_FILES):
        raise EchoContractError("generated artifact inventory differs from exact contract")
    for body in serialized.values():
        strict_json_bytes(body)

    destination.mkdir(parents=True, exist_ok=False)
    for name in OUTPUT_FILES:
        with (destination / name).open("xb") as stream:
            stream.write(serialized[name])
    return {
        "classification": CLASSIFICATION,
        "output_dir": str(destination),
        "artifact_inventory": list(OUTPUT_FILES),
        "artifacts": {
            name: {"bytes": len(serialized[name]), "sha256": sha256_bytes(serialized[name])}
            for name in OUTPUT_FILES
        },
        "eligibility_finding": assessment["finding"],
        "network_requests": 0,
    }
