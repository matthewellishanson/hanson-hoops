"""Bounded Phase 3F-R2B protected pair acquisition and structural reconciliation.

This module can issue only the 60 TeamDashLineups identities stored in the
audited Phase 3F-R1S plan.  It deliberately has no final-test construction,
profile join, preprocessing, estimator, prediction, metric, or serialization
capability.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
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


VERSION = "phase3f-r2b.protected-pair-acquisition.v1"
EXPECTED_HEAD = "8d8f7f5fc6de31b81506091dff00b3e617e13232"
ENDPOINT = "teamdashlineups"
RESULT_SET = "Lineups"
URL = "https://stats.nba.com/stats/teamdashlineups"
AUTHORIZED_SEASON = "2025-26"
AUTHORIZED_SEASON_TYPE = "Regular Season"
TEAM_IDS = tuple(str(value) for value in range(1610612737, 1610612767))
MEASURES = ("Base", "Advanced")
R1S_PLAN = Path("planning/phase3f-r1s/acquisition_plan.json")
R1S_PLAN_BYTES = 64_477
R1S_PLAN_SHA256 = "fd0db91ad876df39d13829ac7e11b920a24e5b394c9f025115a7db46010056c4"
R1S_ARTIFACT_HASHES_SHA256 = "7f3ddbc31665797b0c0acb24c49b9c47c2ddd0b31d92a1c98e8b39921e2ac347"
R1S_SUMMARY_SHA256 = "81f16d12563aa36d1770f172dea1c090e1ed37da5d4c15744f132a9f1352f19b"
EVIDENCE_NAMESPACE = Path("cache/phase3f-r2b/protected-final-target")
PLANNING_NAMESPACE = Path("planning/phase3f-r2b")
MINIMUM_SPACING_SECONDS = 1.0
TIMEOUT_SECONDS = 30

R0_R01_INPUT_HASHES = {
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
}

R0_R01_R1S_COMMITTED_INPUT_HASHES = {
    "PHASE3F_R0_DATA_DICTIONARY_ADDENDUM.md": "f73bbf36568a86050339abfd304cd3726dab0bf63964e7f76e8271256b60db6a",
    "PHASE3F_R0_FINAL_TEST_FREEZE_REPORT.md": "1a0cddef616e1be19e3b764264de5b4390fae61e7b9a926e9c92bc7e40168755",
    "PHASE3F_R0_FINAL_TEST_POLICY.md": "c80fe6c31ba44b2e9e01f60e0943038004cf8584ea0ed7e1ed49e66138c02405",
    "PHASE3F_R0_1_DOCUMENTATION_RECONCILIATION_REPORT.md": "3cfad1d84d361a5ebde277f16de2fa4873aedc31f1523429f7c7d1f057916eb9",
    "PHASE3F_R1S_SIMPLIFIED_ACQUISITION_POLICY.md": "e56377df5e1f8dfc66a2ec5ae71ee6e119add920a7299870f86f3b5eef1bfcc3",
    "PHASE3F_R1S_SIMPLIFIED_ACQUISITION_REPORT.md": "79c40a1754dc5ec9e6b2f0bb2ce91609af7c7c7ad0563df69a43005c8be1ed99",
    "src/pair_fit_v2/phase3f_r0_cli.py": "2b757a85576c3e398e029b95e89457a2e6a2bc1c09be51ef0451fc11da1ce12d",
    "src/pair_fit_v2/phase3f_r0_final_test_freeze.py": "2820c58cbf04748dab9650552d6f4b55db43308a566619447ca048b75ae05357",
    "src/pair_fit_v2/phase3f_r0_1_cli.py": "6d3e05ceab1f7d93eb8cf0e957e16c33808ae3143070777be3e77578eed5160a",
    "src/pair_fit_v2/phase3f_r0_1_documentation_reconciliation.py": "1da2cdf24e2da5d563e131fbf9d0f5eedc8f4ce77ab260ce8a227327a610657b",
    "src/pair_fit_v2/phase3f_r1s_acquisition_plan.py": "e496847bb75cc052f418965d12d20a46d2d139fb3cb9405e9e6b6020c636c92c",
    "src/pair_fit_v2/phase3f_r1s_cli.py": "cd3bb5609dc06e0df6d36e7ac9995f82b43a639a134349c8f6c2e0f45d463d7f",
    "tests/test_phase3f_r0_final_test_freeze.py": "a785513d323dc0edd0e14d70b4c0b776ded811d7a6d33264c6548de55521d480",
    "tests/test_phase3f_r0_1_documentation_reconciliation.py": "6303818ff5296f90491e917243e70712529d27be3c830106cd3b28ae54da834c",
    "tests/test_phase3f_r1s_acquisition_plan.py": "29cccd3bc5d805b5bfdff6b8fe91c251f72e1e57981b764c4af0063d97def767",
}

R1S_INPUT_HASHES = {
    "planning/phase3f-r1s/acquisition_plan.json": R1S_PLAN_SHA256,
    "planning/phase3f-r1s/artifact_hashes.json": R1S_ARTIFACT_HASHES_SHA256,
    "planning/phase3f-r1s/summary.json": R1S_SUMMARY_SHA256,
}

R2A_COMMITTED_INPUT_HASHES = {
    "PHASE3F_R2A_PRIOR_PROFILE_ACQUISITION_POLICY.md": "b0cbb3d0c3067a5392a3816f1719a806ece3dda7cd45acc7b608660ffbd2e7da",
    "PHASE3F_R2A_PRIOR_PROFILE_ACQUISITION_REPORT.md": "ae95f1c0077bbd9c02e1ae110705cec34ccb2b88bd51820627f58bab98bf22ff",
    "src/pair_fit_v2/phase3f_r2a_cli.py": "2b833759740adf84784b535bacf8399e37abcf01b506e673dba3270f34060f0f",
    "src/pair_fit_v2/phase3f_r2a_prior_profile_acquisition.py": "f46fe35cbbd2a40764b0875ea0ac3222b034756d2c2da5d2194809fc78dd5034",
    "tests/test_phase3f_r2a_prior_profile_acquisition.py": "61caf540fa5dce73251804964ed48ae7f128b6b077cb777cf75c6983b199e3e0",
}

R2A_GENERATED_INPUT_HASHES = {
    "planning/phase3f-r2a/authorization.json": "474d6debd597469cccfa2c950536529f4b9c0f9c274be23acf63fbb28c236ab6",
    "planning/phase3f-r2a/reconciliation.json": "b0450dd143a8fb78b824bc14f6b447cf077864660c40cc4777fc55def93604e9",
    "planning/phase3f-r2a/summary.json": "6602ade04750c75353af472b8bc29167dc883fd6c7037a7dedba9c5b25d41ee9",
    "planning/phase3f-r2a/artifact_hashes.json": "81263f9f909c3c2e390099e9a6aaba56711b572039ac69eff91e199b25d72413",
    "cache/phase3f-r2a/non-protected-prior-profiles/01-per100possessions/attempt-1-response.bin": "047d8c16703647425c2fa23678667595a6b7843b213e7e0c5794562bd96fc9ff",
    "cache/phase3f-r2a/non-protected-prior-profiles/02-totals/attempt-1-response.bin": "3bd21076a2fde4b75ce70023f4c07cc633d811cfe08fce65a1c75bb653dfccd5",
}

R2A_RESPONSE_IDENTITIES = {
    "cache/phase3f-r2a/non-protected-prior-profiles/01-per100possessions/attempt-1-response.bin": {
        "bytes": 175_793,
        "rows": 569,
        "raw_sha256": "047d8c16703647425c2fa23678667595a6b7843b213e7e0c5794562bd96fc9ff",
        "canonical_json_sha256": "3651e4096775d485562bf181e4c89b74064c5dca3cde623de25581b31ed316a1",
    },
    "cache/phase3f-r2a/non-protected-prior-profiles/02-totals/attempt-1-response.bin": {
        "bytes": 173_315,
        "rows": 569,
        "raw_sha256": "3bd21076a2fde4b75ce70023f4c07cc633d811cfe08fce65a1c75bb653dfccd5",
        "canonical_json_sha256": "69d1ae9b2f388c95bab72a35703b438cf8cb7bbd05d33189137ab8a414edf7df",
    },
}

PINNED_INPUT_HASHES = {
    **R0_R01_INPUT_HASHES,
    **R0_R01_R1S_COMMITTED_INPUT_HASHES,
    **R1S_INPUT_HASHES,
    **R2A_COMMITTED_INPUT_HASHES,
    **R2A_GENERATED_INPUT_HASHES,
}

STATE_FILES = {
    "start": "attempt-1-start.json",
    "response": "attempt-1-response.bin",
    "outcome": "attempt-1-outcome.json",
    "verified_body": "verified-response.bin",
    "verification": "verification.json",
    "failure": "quarantine.json",
}

OUTPUT_FILES = (
    "authorization.json",
    "official_invocation.json",
    "request_inventory.json",
    "attempt_inventory.json",
    "response_verifications.json",
    "team_reconciliation.json",
    "global_reconciliation.json",
    "exact_250_unresolved.json",
    "structural_dispositions.json",
    "input_fingerprints.json",
    "summary.json",
    "artifact_hashes.json",
)

PAIR_PATTERN = re.compile(r"^-([1-9][0-9]*)-([1-9][0-9]*)-$")


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


def _read_bytes(path: Path | str) -> bytes:
    return Path(path).read_bytes()


def _read_json(path: Path | str) -> Any:
    return strict_json_bytes(_read_bytes(path))


def _write_once(path: Path | str, content: bytes) -> None:
    target = Path(path)
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


def fingerprint_inputs(project_root: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for relative, expected_hash in sorted(PINNED_INPUT_HASHES.items()):
        body = _read_bytes(Path(project_root) / relative)
        actual_hash = sha256_bytes(body)
        if actual_hash != expected_hash:
            raise AcquisitionError(f"pinned input fingerprint mismatch: {relative}")
        output[relative] = {"bytes": len(body), "sha256": actual_hash}
    for relative, expected in R2A_RESPONSE_IDENTITIES.items():
        body = _read_bytes(Path(project_root) / relative)
        payload = strict_json_bytes(body)
        result_sets = payload.get("resultSets") if isinstance(payload, Mapping) else None
        if not isinstance(result_sets, list) or len(result_sets) != 1:
            raise AcquisitionError(f"R2A result-set identity mismatch: {relative}")
        row_set = result_sets[0].get("rowSet") if isinstance(result_sets[0], Mapping) else None
        observed = {
            "bytes": len(body),
            "rows": len(row_set) if isinstance(row_set, list) else None,
            "raw_sha256": sha256_bytes(body),
            "canonical_json_sha256": sha256_bytes(canonical_json_bytes(payload)),
        }
        if observed != expected:
            raise AcquisitionError(f"R2A response identity mismatch: {relative}")
    return output


def load_frozen_requests(project_root: Path) -> list[dict[str, Any]]:
    plan_path = Path(project_root) / R1S_PLAN
    body = _read_bytes(plan_path)
    if len(body) != R1S_PLAN_BYTES or sha256_bytes(body) != R1S_PLAN_SHA256:
        raise AcquisitionError("audited R1S acquisition plan identity mismatch")
    plan = strict_json_bytes(body)
    requests_value = plan.get("protected_requests") if isinstance(plan, Mapping) else None
    if not isinstance(requests_value, list) or len(requests_value) != 60:
        raise AcquisitionError("R1S plan does not contain exactly 60 protected requests")
    requests_copy = [dict(item) for item in requests_value]
    expected_order = [(team_id, measure) for team_id in TEAM_IDS for measure in MEASURES]
    observed_order = []
    for item in requests_copy:
        parameters = item.get("parameters")
        if not isinstance(parameters, Mapping):
            raise AcquisitionError("frozen request has no parameter dictionary")
        team_id = parameters.get("TeamID")
        measure = parameters.get("MeasureType")
        observed_order.append((team_id, measure))
        if (
            item.get("endpoint") != ENDPOINT
            or item.get("protected") is not True
            or parameters.get("Season") != AUTHORIZED_SEASON
            or parameters.get("SeasonType") != AUTHORIZED_SEASON_TYPE
            or parameters.get("GroupQuantity") != "2"
            or parameters.get("DateFrom") != ""
            or parameters.get("DateTo") != ""
            or item.get("request_id") != f"{ENDPOINT}:{team_id}:{str(measure).lower()}"
        ):
            raise AcquisitionError("frozen protected request structure mismatch")
    if observed_order != expected_order:
        raise AcquisitionError("frozen protected request order mismatch")
    if len({team_id for team_id, _ in observed_order}) != 30:
        raise AcquisitionError("frozen protected request team count mismatch")
    if Counter(measure for _, measure in observed_order) != Counter({"Base": 30, "Advanced": 30}):
        raise AcquisitionError("frozen protected request measure count mismatch")
    if len({item.get("request_id") for item in requests_copy}) != 60:
        raise AcquisitionError("duplicate frozen request ID")
    if len({identity_sha256(item) for item in requests_copy}) != 60:
        raise AcquisitionError("duplicate frozen endpoint/parameter identity")
    return requests_copy


def validate_request_identity(
    request: Mapping[str, Any], frozen_requests: Sequence[Mapping[str, Any]]
) -> None:
    by_id = {item.get("request_id"): item for item in frozen_requests}
    request_id = request.get("request_id")
    frozen = by_id.get(request_id)
    if frozen is None:
        raise AcquisitionError("request is not present in the frozen 60-item allowlist")
    if _identity_document(request) != _identity_document(frozen):
        raise AcquisitionError("request endpoint or parameters differ from the frozen R1S identity")
    if identity_sha256(request) != identity_sha256(frozen):
        raise AcquisitionError("request canonical identity differs from the frozen R1S identity")


def authorization_document(project_root: Path) -> dict[str, Any]:
    frozen = load_frozen_requests(project_root)
    authorized = []
    for ordinal, item in enumerate(frozen, 1):
        parameters = dict(item["parameters"])
        authorized.append(
            {
                "ordinal": ordinal,
                "request_id": item["request_id"],
                "team_id": parameters["TeamID"],
                "measure": parameters["MeasureType"],
                "endpoint": item["endpoint"],
                "parameters": parameters,
                "canonical_identity_sha256": identity_sha256(item),
            }
        )
    return {
        "version": VERSION,
        "checkpoint": "Phase 3F-R2B - Protected 2025-26 Pair-Evidence Acquisition and Structural Reconciliation",
        "required_committed_head": EXPECTED_HEAD,
        "source_r1s_plan": {
            "path": R1S_PLAN.as_posix(),
            "bytes": R1S_PLAN_BYTES,
            "sha256": R1S_PLAN_SHA256,
        },
        "r2a_committed_checkpoint": {
            "commit": EXPECTED_HEAD,
            "committed_file_count": 6,
            "files": [
                ".gitignore",
                *R2A_COMMITTED_INPUT_HASHES.keys(),
            ],
        },
        "input_fingerprints": fingerprint_inputs(project_root),
        "authorized_requests": authorized,
        "request_order": [item["request_id"] for item in authorized],
        "output_namespaces": {
            "raw_evidence": EVIDENCE_NAMESPACE.as_posix() + "/",
            "planning": PLANNING_NAMESPACE.as_posix() + "/",
        },
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
        "failure_policy": "preserve start and any bytes, write outcome and quarantine, stop immediately, never retry",
        "quarantine_policy": "failed bytes and diagnostics remain in the request identity directory and are never promoted",
        "restart_rules": {
            "not_started": "eligible for its one authorized attempt",
            "completed_verified": "re-hash, verify, and skip",
            "started_without_outcome": "stop for read-only investigation",
            "failed_or_quarantined": "preserve and stop",
            "conflicting_state": "refuse progress and stop",
        },
        "exact_250_policy": "preserve, mark unresolved, continue remaining full-season allowlist; no recovery request authorized",
        "phase_stop_boundary": "protected acquisition and structural population reconciliation only",
        "recovery_acquisition_authorized": False,
        "final_test_construction_authorized": False,
        "predictor_join_authorized": False,
        "model_operation_authorized": False,
    }


def initialize_authorization(project_root: Path, planning_dir: Path) -> dict[str, Any]:
    target = Path(planning_dir) / "authorization.json"
    document = authorization_document(project_root)
    content = serialize_json(document)
    if target.exists():
        if _read_bytes(target) != content:
            raise AcquisitionError("existing authorization differs from frozen authorization")
        return document
    _write_once(target, content)
    return document


def validate_authorization(
    document: Mapping[str, Any], project_root: Path, expected: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    expected_document = dict(expected) if expected is not None else authorization_document(project_root)
    if document != expected_document:
        raise AcquisitionError("authorization record does not match the audited frozen identities")
    authorized = list(document.get("authorized_requests", []))
    if len(authorized) != 60:
        raise AcquisitionError("authorization does not contain exactly 60 requests")
    frozen = load_frozen_requests(project_root)
    for request in authorized:
        validate_request_identity(request, frozen)
    return authorized


def _request_slug(request: Mapping[str, Any]) -> str:
    measure_ordinal = "01-base" if request["parameters"]["MeasureType"] == "Base" else "02-advanced"
    return f"{request['parameters']['TeamID']}-{measure_ordinal}"


def request_paths(evidence_root: Path, request: Mapping[str, Any]) -> dict[str, Path]:
    base = Path(evidence_root) / _request_slug(request)
    return {name: base / filename for name, filename in STATE_FILES.items()}


def parse_canonical_pair(group_id: Any) -> tuple[tuple[str, str] | None, str]:
    if not isinstance(group_id, str):
        return None, "missing_or_malformed_player_ids"
    match = PAIR_PATTERN.fullmatch(group_id)
    if match is None:
        return None, "missing_or_malformed_player_ids"
    left, right = match.groups()
    if left == right:
        return None, "same_player_pair"
    ordered = tuple(sorted((left, right), key=int))
    return ordered, "valid"


def _numeric_status(value: Any) -> tuple[float | None, str]:
    if value is None:
        return None, "missing"
    if isinstance(value, bool):
        return None, "nonnumeric"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, "nonnumeric"
    if not math.isfinite(number):
        return None, "nonfinite"
    return number, "valid"


def _field_diagnostics(rows: Sequence[Mapping[str, Any]], headers: Sequence[str], field: str, *, negative_invalid: bool) -> dict[str, Any]:
    counts = Counter({"missing": 0, "nonnumeric": 0, "nonfinite": 0, "negative": 0, "zero": 0, "valid": 0})
    invalid_rows = 0
    for row in rows:
        number, status = _numeric_status(row.get(field))
        if status != "valid":
            counts[status] += 1
            invalid_rows += 1
            continue
        if number == 0:
            counts["zero"] += 1
        if number is not None and number < 0:
            counts["negative"] += 1
            if negative_invalid:
                invalid_rows += 1
                continue
        counts["valid"] += 1
    return {
        "field": field,
        "header_present": field in headers,
        "missing_count": counts["missing"],
        "nonnumeric_count": counts["nonnumeric"],
        "nonfinite_count": counts["nonfinite"],
        "negative_count": counts["negative"],
        "zero_count": counts["zero"],
        "valid_count": counts["valid"],
        "invalid_row_count": invalid_rows,
    }


def verify_response_bytes(body: bytes, request: Mapping[str, Any], frozen_requests: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    validate_request_identity(request, frozen_requests)
    try:
        payload = strict_json_bytes(body)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ResponseValidationError(f"invalid strict JSON: {exc}") from exc
    if not isinstance(payload, Mapping) or not isinstance(payload.get("resultSets"), list):
        raise ResponseValidationError("response lacks a resultSets list")
    result_sets = payload["resultSets"]
    matches = [item for item in result_sets if isinstance(item, Mapping) and item.get("name") == RESULT_SET]
    if len(result_sets) != 1 or len(matches) != 1:
        raise ResponseValidationError("expected exactly one Lineups result set")
    result = matches[0]
    headers, raw_rows = result.get("headers"), result.get("rowSet")
    if (
        not isinstance(headers, list)
        or not all(isinstance(item, str) for item in headers)
        or len(headers) != len(set(headers))
        or not isinstance(raw_rows, list)
    ):
        raise ResponseValidationError("malformed Lineups headers or rows")
    width_mismatches = [index for index, row in enumerate(raw_rows) if not isinstance(row, list) or len(row) != len(headers)]
    if width_mismatches:
        raise ResponseValidationError("Lineups row width mismatch", {"row_width_mismatch_indices": width_mismatches})
    rows = [dict(zip(headers, row)) for row in raw_rows]
    valid_keys: list[tuple[str, str]] = []
    malformed_pairs = 0
    same_player_pairs = 0
    missing_or_malformed_ids = 0
    for row in rows:
        key, status = parse_canonical_pair(row.get("GROUP_ID"))
        if status == "valid" and key is not None:
            valid_keys.append(key)
        elif status == "same_player_pair":
            same_player_pairs += 1
        else:
            malformed_pairs += 1
            missing_or_malformed_ids += 1
    pair_counts = Counter(valid_keys)
    duplicate_count = sum(count - 1 for count in pair_counts.values() if count > 1)
    requested_team = request["parameters"]["TeamID"]
    team_id_mismatches = sum(str(row.get("TEAM_ID")) != requested_team for row in rows)
    measure = request["parameters"]["MeasureType"]
    required_field = "POSS" if measure == "Base" else "NET_RATING"
    field = _field_diagnostics(rows, headers, required_field, negative_invalid=measure == "Base")
    return {
        "version": VERSION,
        "request_id": request["request_id"],
        "team_id": requested_team,
        "measure": measure,
        "season": request["parameters"]["Season"],
        "season_type": request["parameters"]["SeasonType"],
        "endpoint": request["endpoint"],
        "canonical_identity_sha256": identity_sha256(request),
        "expected_result_set_name": RESULT_SET,
        "observed_result_set_name": result.get("name"),
        "response_byte_count": len(body),
        "raw_sha256": sha256_bytes(body),
        "canonical_json_sha256": sha256_bytes(canonical_json_bytes(payload)),
        "header_count": len(headers),
        "header_names": headers,
        "row_count": len(rows),
        "row_width_consistent": True,
        "pair_identity": {
            "canonical_order": "numeric ascending player IDs",
            "valid_pair_row_count": len(valid_keys),
            "unique_canonical_pair_count": len(pair_counts),
            "malformed_pair_count": malformed_pairs,
            "same_player_pair_count": same_player_pairs,
            "missing_or_malformed_player_id_count": missing_or_malformed_ids,
            "duplicate_canonical_pair_count": duplicate_count,
        },
        "requested_team_id_mismatch_count": team_id_mismatches,
        "required_field": field,
        "zero_possession_row_count": field["zero_count"] if measure == "Base" else 0,
        "exact_250": len(rows) == 250,
        "verified": True,
    }


def _record_identity_matches(record: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    return (
        record.get("request_id") == request.get("request_id")
        and record.get("canonical_identity_sha256") == identity_sha256(request)
        and record.get("attempt_number") == 1
    )


def classify_request_state(
    evidence_root: Path, request: Mapping[str, Any], frozen_requests: Sequence[Mapping[str, Any]]
) -> str:
    paths = request_paths(evidence_root, request)
    base = paths["start"].parent
    if not base.exists():
        return "not_started"
    if not base.is_dir():
        return "conflicting_state"
    expected_names = set(STATE_FILES.values())
    if any(item.name not in expected_names or not item.is_file() for item in base.iterdir()):
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
    if not isinstance(start, Mapping) or not _record_identity_matches(start, request):
        return "conflicting_state"
    if "outcome" not in present:
        return "started_without_outcome"
    try:
        outcome = _read_json(paths["outcome"])
    except Exception:
        return "conflicting_state"
    if not isinstance(outcome, Mapping) or not _record_identity_matches(outcome, request):
        return "conflicting_state"
    if outcome.get("state") == "completed_verified":
        if present != {"start", "response", "outcome", "verified_body", "verification"}:
            return "conflicting_state"
        try:
            response = _read_bytes(paths["response"])
            promoted = _read_bytes(paths["verified_body"])
            verification = _read_json(paths["verification"])
            actual = verify_response_bytes(response, request, frozen_requests)
        except Exception:
            return "conflicting_state"
        if response != promoted or verification != actual:
            return "conflicting_state"
        if (
            outcome.get("http_status") != 200
            or outcome.get("redirected") is not False
            or outcome.get("automatic_retries") != 0
            or outcome.get("raw_sha256") != actual["raw_sha256"]
            or outcome.get("canonical_json_sha256") != actual["canonical_json_sha256"]
        ):
            return "conflicting_state"
        return "completed_verified"
    if outcome.get("state") == "failed_or_quarantined":
        allowed = {"start", "outcome", "failure"} | ({"response"} if "response" in present else set())
        if present == allowed:
            return "failed_or_quarantined"
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
                "attempt_number": 1,
                "state": "failed_or_quarantined",
                "reason": reason,
                "diagnostics": dict(diagnostics or {}),
            }
        ),
    )


def acquire_one(
    request: Mapping[str, Any],
    frozen_requests: Sequence[Mapping[str, Any]],
    evidence_root: Path,
    session: requests.Session,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    validate_request_identity(request, frozen_requests)
    state = classify_request_state(evidence_root, request, frozen_requests)
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
        if redirected:
            raise ResponseValidationError("redirect response prohibited")
        if response.status_code != 200:
            raise ResponseValidationError(f"HTTP status {response.status_code}")
        verification = verify_response_bytes(body, request, frozen_requests)
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
            "byte_count": verification["response_byte_count"],
            "row_count": verification["row_count"],
            "raw_sha256": verification["raw_sha256"],
            "canonical_json_sha256": verification["canonical_json_sha256"],
            "disposition": "exact_250_unresolved" if verification["exact_250"] else "completed_verified",
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


def _verified_request_data(
    evidence_root: Path, request: Mapping[str, Any], frozen_requests: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], set[tuple[str, str]]]:
    if classify_request_state(evidence_root, request, frozen_requests) != "completed_verified":
        raise AcquisitionError(f"request is not completed_verified: {request['request_id']}")
    paths = request_paths(evidence_root, request)
    verification = _read_json(paths["verification"])
    payload = strict_json_bytes(_read_bytes(paths["verified_body"]))
    result = payload["resultSets"][0]
    rows = [dict(zip(result["headers"], row)) for row in result["rowSet"]]
    keys = {
        key
        for row in rows
        for key, status in [parse_canonical_pair(row.get("GROUP_ID"))]
        if status == "valid" and key is not None
    }
    return verification, keys


def _pair_lists(keys: set[tuple[str, str]]) -> list[list[str]]:
    return [list(key) for key in sorted(keys, key=lambda item: (int(item[0]), int(item[1])))]


def reconcile(
    evidence_root: Path,
    requests_value: Sequence[Mapping[str, Any]],
    frozen_requests: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if len(requests_value) != 60:
        raise AcquisitionError("reconciliation requires exactly 60 authorized requests")
    response_verifications = []
    team_records = []
    for team_index, team_id in enumerate(TEAM_IDS):
        base_request = requests_value[team_index * 2]
        advanced_request = requests_value[team_index * 2 + 1]
        base, base_keys = _verified_request_data(evidence_root, base_request, frozen_requests)
        advanced, advanced_keys = _verified_request_data(evidence_root, advanced_request, frozen_requests)
        response_verifications.extend((base, advanced))
        base_only = base_keys - advanced_keys
        advanced_only = advanced_keys - base_keys
        row_count_mismatch = base["row_count"] != advanced["row_count"]
        key_set_mismatch = bool(base_only or advanced_only)
        pair_invalid = any(
            verification["pair_identity"][field] > 0
            for verification in (base, advanced)
            for field in (
                "malformed_pair_count", "same_player_pair_count",
                "missing_or_malformed_player_id_count", "duplicate_canonical_pair_count",
            )
        )
        required_invalid = (
            base["required_field"]["invalid_row_count"] > 0
            or advanced["required_field"]["invalid_row_count"] > 0
            or base["requested_team_id_mismatch_count"] > 0
            or advanced["requested_team_id_mismatch_count"] > 0
        )
        exact_250 = base["exact_250"] or advanced["exact_250"]
        issues = []
        if row_count_mismatch or key_set_mismatch:
            issues.append("base_advanced_mismatch")
        if pair_invalid:
            issues.append("invalid_pair_identity")
        if required_invalid:
            issues.append("invalid_required_field")
        if exact_250:
            issues.append("exact_250_unresolved")
        if base["row_count"] == 0 or advanced["row_count"] == 0:
            issues.append("acquisition_incomplete")
        if "acquisition_incomplete" in issues:
            disposition = "acquisition_incomplete"
        elif "base_advanced_mismatch" in issues:
            disposition = "base_advanced_mismatch"
        elif "invalid_pair_identity" in issues:
            disposition = "invalid_pair_identity"
        elif "invalid_required_field" in issues:
            disposition = "invalid_required_field"
        elif exact_250:
            disposition = "exact_250_unresolved"
        else:
            disposition = "structurally_complete_non_250"
        exact_triggers = [
            {
                "request_id": verification["request_id"],
                "measure": verification["measure"],
                "raw_sha256": verification["raw_sha256"],
                "canonical_json_sha256": verification["canonical_json_sha256"],
            }
            for verification in (base, advanced)
            if verification["exact_250"]
        ]
        team_records.append(
            {
                "team_id": team_id,
                "base_request_id": base["request_id"],
                "advanced_request_id": advanced["request_id"],
                "base_row_count": base["row_count"],
                "advanced_row_count": advanced["row_count"],
                "base_canonical_pair_count": len(base_keys),
                "advanced_canonical_pair_count": len(advanced_keys),
                "intersection_count": len(base_keys & advanced_keys),
                "base_only_keys": _pair_lists(base_only),
                "advanced_only_keys": _pair_lists(advanced_only),
                "base_duplicate_keys": base["pair_identity"]["duplicate_canonical_pair_count"],
                "advanced_duplicate_keys": advanced["pair_identity"]["duplicate_canonical_pair_count"],
                "base_malformed_keys": base["pair_identity"]["malformed_pair_count"],
                "advanced_malformed_keys": advanced["pair_identity"]["malformed_pair_count"],
                "base_same_player_pairs": base["pair_identity"]["same_player_pair_count"],
                "advanced_same_player_pairs": advanced["pair_identity"]["same_player_pair_count"],
                "zero_possession_base_rows": base["zero_possession_row_count"],
                "base_invalid_possession_rows": base["required_field"]["invalid_row_count"],
                "advanced_invalid_target_rows": advanced["required_field"]["invalid_row_count"],
                "base_exact_250": base["exact_250"],
                "advanced_exact_250": advanced["exact_250"],
                "exact_250_triggering_responses": exact_triggers,
                "structural_issues": issues,
                "structural_disposition": disposition,
            }
        )
    disposition_counts = Counter(item["structural_disposition"] for item in team_records)
    exact_teams = [item["team_id"] for item in team_records if item["base_exact_250"] or item["advanced_exact_250"]]
    mismatch_teams = [item["team_id"] for item in team_records if "base_advanced_mismatch" in item["structural_issues"]]
    invalid_pair_teams = [item["team_id"] for item in team_records if "invalid_pair_identity" in item["structural_issues"]]
    invalid_field_teams = [item["team_id"] for item in team_records if "invalid_required_field" in item["structural_issues"]]
    all_completed = len(response_verifications) == 60
    unresolved = [item["team_id"] for item in team_records if item["structural_disposition"] != "structurally_complete_non_250"]
    if all_completed and not unresolved:
        classification = "PASS - all 60 protected responses acquired and structurally reconciled"
    elif all_completed:
        classification = "CONDITIONAL PASS - acquisition complete; unresolved team evidence requires a separate checkpoint"
    else:
        classification = "BLOCKED - protected acquisition or reconciliation incomplete"
    global_record = {
        "version": VERSION,
        "classification": classification,
        "total_teams_acquired": len(team_records),
        "total_base_responses": 30,
        "total_advanced_responses": 30,
        "total_raw_base_rows": sum(item["base_row_count"] for item in team_records),
        "total_raw_advanced_rows": sum(item["advanced_row_count"] for item in team_records),
        "unique_team_pair_observation_count": sum(item["intersection_count"] for item in team_records),
        "unique_team_pair_union_count": sum(
            item["base_canonical_pair_count"] + len(item["advanced_only_keys"]) for item in team_records
        ),
        "structurally_complete_non_250_team_count": disposition_counts["structurally_complete_non_250"],
        "exact_250_unresolved_team_count": len(exact_teams),
        "exact_250_unresolved_team_ids": exact_teams,
        "base_advanced_mismatch_team_count": len(mismatch_teams),
        "base_advanced_mismatch_team_ids": mismatch_teams,
        "invalid_pair_team_count": len(invalid_pair_teams),
        "invalid_pair_team_ids": invalid_pair_teams,
        "invalid_required_field_team_count": len(invalid_field_teams),
        "invalid_required_field_team_ids": invalid_field_teams,
        "zero_possession_base_rows": sum(item["zero_possession_base_rows"] for item in team_records),
        "duplicate_canonical_pair_rows": sum(
            item["base_duplicate_keys"] + item["advanced_duplicate_keys"] for item in team_records
        ),
        "malformed_pair_rows": sum(
            item["base_malformed_keys"] + item["advanced_malformed_keys"] for item in team_records
        ),
        "acquisition_failures_or_quarantines": 0,
        "all_60_authorized_requests_completed_verified": all_completed,
        "structural_disposition_counts": dict(sorted(disposition_counts.items())),
        "final_execution_readiness_gates": "pending",
        "final_test_constructed": False,
        "predictor_profiles_joined": False,
        "model_operation_occurred": False,
    }
    return {
        "response_verifications": response_verifications,
        "team_reconciliation": team_records,
        "global_reconciliation": global_record,
    }


def attempt_record_inventory(
    evidence_root: Path,
    requests_value: Sequence[Mapping[str, Any]],
    frozen_requests: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    inventory = []
    for request in requests_value:
        paths = request_paths(evidence_root, request)
        state = classify_request_state(evidence_root, request, frozen_requests)
        item: dict[str, Any] = {
            "request_id": request["request_id"],
            "team_id": request["parameters"]["TeamID"],
            "measure": request["parameters"]["MeasureType"],
            "state": state,
        }
        records = {}
        for name, path in paths.items():
            if path.exists():
                content = _read_bytes(path)
                records[name] = {
                    "relative_path": f"{_request_slug(request)}/{path.name}",
                    "bytes": len(content),
                    "sha256": sha256_bytes(content),
                }
        item["records"] = records
        if paths["start"].exists():
            item["started_at"] = _read_json(paths["start"]).get("started_at")
        if paths["outcome"].exists():
            outcome = _read_json(paths["outcome"])
            for field in (
                "attempt_number", "completed_at", "http_status", "redirected",
                "automatic_retries", "elapsed_seconds", "row_count", "byte_count",
                "raw_sha256", "canonical_json_sha256", "disposition",
            ):
                item[field] = outcome.get(field)
        inventory.append(item)
    return inventory


def record_official_invocation(
    planning_dir: Path, authorization_path: Path, argv: Sequence[str] | None = None
) -> dict[str, Any]:
    authorization_body = _read_bytes(authorization_path)
    record = {
        "version": VERSION,
        "invocation_number": 1,
        "recorded_at": utc_now(),
        "python_executable": sys.executable,
        "working_directory": os.getcwd(),
        "command_argv": list(sys.argv if argv is None else argv),
        "pythonpath": os.environ.get("PYTHONPATH", ""),
        "authorization_path": str(authorization_path),
        "authorization_sha256": sha256_bytes(authorization_body),
    }
    _write_once(Path(planning_dir) / "official_invocation.json", serialize_json(record))
    return record


def _write_outputs(
    planning_dir: Path,
    authorization: Mapping[str, Any],
    attempt_inventory: Sequence[Mapping[str, Any]],
    reconciliation: Mapping[str, Any],
) -> dict[str, Any]:
    output = Path(planning_dir)
    request_inventory = [
        {
            "ordinal": item["ordinal"],
            "request_id": item["request_id"],
            "team_id": item["team_id"],
            "measure": item["measure"],
            "endpoint": item["endpoint"],
            "parameters": item["parameters"],
            "canonical_identity_sha256": item["canonical_identity_sha256"],
        }
        for item in authorization["authorized_requests"]
    ]
    team_records = reconciliation["team_reconciliation"]
    exact_records = [
        {
            "team_id": item["team_id"],
            "structural_disposition": item["structural_disposition"],
            "triggering_responses": item["exact_250_triggering_responses"],
            "later_checkpoint_requirements": {
                "affected_team": item["team_id"],
                "triggering_full_season_hashes": item["exact_250_triggering_responses"],
                "exact_complementary_2025_26_date_windows": "must be separately frozen",
                "recovery_request_count": 4,
                "measures": ["Base", "Advanced"],
                "separate_approval_required": True,
            },
        }
        for item in team_records
        if item["exact_250_triggering_responses"]
    ]
    dispositions = {
        "version": VERSION,
        "by_team": [
            {
                "team_id": item["team_id"],
                "structural_disposition": item["structural_disposition"],
                "structural_issues": item["structural_issues"],
            }
            for item in team_records
        ],
    }
    summary = {
        "version": VERSION,
        "classification": reconciliation["global_reconciliation"]["classification"],
        "authorization_sha256": sha256_bytes(serialize_json(authorization)),
        "authorized_request_count": 60,
        "official_invocation_count": 1,
        "completed_verified_request_count": sum(item["state"] == "completed_verified" for item in attempt_inventory),
        "global_structural_counts": reconciliation["global_reconciliation"],
        "recovery_request_count": 0,
        "final_test_table_constructed": False,
        "predictor_profiles_joined": False,
        "imputation_or_scaling_occurred": False,
        "estimator_loaded_or_fit": False,
        "predictions_or_metrics_created": False,
        "model_artifact_created": False,
    }
    values = {
        "request_inventory.json": request_inventory,
        "attempt_inventory.json": list(attempt_inventory),
        "response_verifications.json": reconciliation["response_verifications"],
        "team_reconciliation.json": team_records,
        "global_reconciliation.json": reconciliation["global_reconciliation"],
        "exact_250_unresolved.json": {"version": VERSION, "teams": exact_records},
        "structural_dispositions.json": dispositions,
        "input_fingerprints.json": authorization["input_fingerprints"],
        "summary.json": summary,
    }
    serialized = {name: serialize_json(value) for name, value in values.items()}
    for name, content in serialized.items():
        _write_once(output / name, content)
    manifest_paths = ["authorization.json", "official_invocation.json", *serialized.keys()]
    manifest = {
        "version": VERSION,
        "artifact_inventory": [*manifest_paths, "artifact_hashes.json"],
        "sha256": {name: sha256_bytes(_read_bytes(output / name)) for name in manifest_paths},
        "note": "artifact_hashes.json excludes itself to avoid a circular hash",
    }
    _write_once(output / "artifact_hashes.json", serialize_json(manifest))
    return summary


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
    expected_authorization = authorization_document(project_root)
    authorization = _read_json(authorization_path)
    authorized = validate_authorization(authorization, project_root, expected_authorization)
    frozen = load_frozen_requests(project_root)
    states = [classify_request_state(evidence_root, request, frozen) for request in authorized]
    blockers = [state for state in states if state not in {"not_started", "completed_verified"}]
    if blockers:
        raise AcquisitionError(f"pre-transport state blocks phase: {blockers}")
    attempts = []
    last_attempt_finished: float | None = None
    session = session_factory()
    try:
        for request, initial_state in zip(authorized, states):
            current_authorization = _read_json(authorization_path)
            validate_authorization(current_authorization, project_root, expected_authorization)
            validate_request_identity(request, frozen)
            if initial_state == "completed_verified":
                attempts.append({"request_id": request["request_id"], "action": "skipped_completed_verified"})
                continue
            if last_attempt_finished is not None:
                elapsed = monotonic() - last_attempt_finished
                if elapsed < MINIMUM_SPACING_SECONDS:
                    sleeper(MINIMUM_SPACING_SECONDS - elapsed)
            result = acquire_one(request, frozen, evidence_root, session, clock=monotonic)
            attempts.append(result)
            last_attempt_finished = monotonic()
    finally:
        session.close()
    reconciliation = reconcile(evidence_root, authorized, frozen)
    inventory = attempt_record_inventory(evidence_root, authorized, frozen)
    summary = _write_outputs(planning_dir, authorization, inventory, reconciliation)
    return {"summary": summary, "reconciliation": reconciliation, "attempts": attempts}
