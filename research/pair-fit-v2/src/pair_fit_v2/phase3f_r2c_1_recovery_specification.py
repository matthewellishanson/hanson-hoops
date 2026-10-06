"""Offline Phase 3F-R2C.1 correction-only recovery specification.

This module authenticates existing opaque evidence and emits a corrected,
write-once planning bundle.  It has no acquisition or model capability.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any


VERSION = "phase3f-r2c.1.recovery-specification-correction.v1"
CLASSIFICATION = (
    "PASS — Phase 3F-R2C.1 correction-only recovery specification hardened; "
    "ready for read-only audit"
)
EXPECTED_BRANCH = "research/pair-fit-v2"
EXPECTED_HEAD = "d233b71749104dcc494fbc979a4c83e86e1054ff"

OUTPUT_NAMESPACE = Path("planning/phase3f-r2c.1")
OUTPUT_FILES = (
    "corrected_recovery_plan.json",
    "artifact_hashes.json",
    "summary.json",
)
ORIGINAL_R2C_PLAN_PATH = Path("planning/phase3f-r2c/recovery_plan.json")
ORIGINAL_R2C_PLAN_BYTES = 121_619
ORIGINAL_R2C_PLAN_SHA256 = "79276836678e163d3ff45e03040aba95a412c590a6928f027765ea33bbc71daf"
ORIGINAL_R2C_PLANNING = {
    "artifact_hashes.json": (602, "25bac05220a8d7c1645b235a98b8800a28d7d6df821a0a9c1a9cbe2721d4fd76"),
    "recovery_plan.json": (121_619, ORIGINAL_R2C_PLAN_SHA256),
    "summary.json": (705, "d2c77126e161f695a92c1e679a216f007f4eedb35b2e3ab766d7c396625e2980"),
}
ORIGINAL_R2C_GIT_VISIBLE = {
    "PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_POLICY.md": (
        8_135, "5eedfc058ff616d928364082e574688cf77c6b6a3c916df02ded5c3527ac9fc3"
    ),
    "PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_REPORT.md": (
        10_173, "f36126191f0b4f8d0472460c2e661cca6efe58aaab911e2d0b86b41b9f5ec801"
    ),
    "src/pair_fit_v2/phase3f_r2c_recovery_specification.py": (
        35_653, "285a9ce240f9c232667c6c7e48bd1df3df38dfdba19e9350ddeb0efef6fe2174"
    ),
    "src/pair_fit_v2/phase3f_r2c_cli.py": (
        1_107, "abf1131635343f6b3178cae57ebe790b75d74922c314b14f8af268f6ac0106c8"
    ),
    "tests/test_phase3f_r2c_recovery_specification.py": (
        14_859, "bbb132a88a8cc3f16b31da2cba35365b9f99f47bc92f8659e558a7d738e732d5"
    ),
}

PUBLIC_SOURCE_NAMESPACE = Path("cache/phase3f-r2c-public-source")
PUBLIC_URL = "https://pr.nba.com/2025-26-nba-regular-season-schedule/"
PUBLIC_FILES = {
    "attempt-1-outcome.json": (397, "f04a957870bc603571deac07ed9a4ab7bdd6f1a771941671ae9a2d3bf928f3c9"),
    "attempt-1-start.json": (224, "ddaab6e0b05903fd886e9b2f3ceace22d177dc2d439bd43964b418f732c1f204"),
    "authorization-request.json": (435, "434f051b5bd91897b2dd0206a9cff2d8ca711da4d097e95533fae9d91d613327"),
    "response.html": (126_442, "8a61156b746821a0341dd77be87ad97f3d9a55c40f184f9012bdc76795bebca3"),
    "verified-source-summary.json": (1_080, "348718fa280bba090e132651c4c6905a3685a97e998b1ed0f7aca9fff8110bb3"),
}
PUBLIC_BODY_BYTES = 126_442
PUBLIC_BODY_SHA256 = "8a61156b746821a0341dd77be87ad97f3d9a55c40f184f9012bdc76795bebca3"
SEASON_START = date(2025, 10, 21)
SEASON_END = date(2026, 4, 12)
WINDOWS = (
    {"name": "early", "DateFrom": "2025-10-21", "DateTo": "2026-01-31"},
    {"name": "late", "DateFrom": "2026-02-01", "DateTo": "2026-04-12"},
)

R2B1_CONTRACT_PATH = Path("planning/phase3f-r2b.1/response_contract.json")
R2B1_CONTRACT_FILE_SHA256 = "ecc3ecf1d547401539af8f8f640002fc3887de3dd64f1e80af1d41d62d04c49e"
R2B1_CONTRACT_IDENTITY = "sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad"
R2B21_TRANSPORT_PATH_TEXT = "planning/phase3f-r2b.2.1/future_protected_transport_contract.json"
R2B21_TRANSPORT_PATH = Path(R2B21_TRANSPORT_PATH_TEXT)
R2B21_TRANSPORT_SHA256 = "20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234"
R2B2_EXACT_250_PATH = Path("planning/phase3f-r2b.2/exact_250_inventory.json")
R2B2_REQUESTS_PATH = Path("planning/phase3f-r2b.2/request_inventory.json")
R2B2_FINGERPRINTS_PATH = Path("planning/phase3f-r2b.2/response_fingerprints.json")
R2B2_ATTEMPTS_PATH = Path("planning/phase3f-r2b.2/attempt_inventory.json")
FUTURE_PROTECTED_NAMESPACE = Path("cache/phase3f-r2c-protected-recovery")
PRESERVED_NAMESPACES = (
    Path("planning/phase3f-r2b"),
    Path("planning/phase3f-r2b.1"),
    Path("planning/phase3f-r2b.2"),
    Path("planning/phase3f-r2b.2.1"),
    Path("cache/phase3f-r2b"),
    Path("cache/phase3f-r2b.2"),
    PUBLIC_SOURCE_NAMESPACE,
    Path("planning/phase3f-r2c"),
)

ESTABLISHED_PARAMETER_DEFAULTS = {
    "DateFrom": "", "DateTo": "", "GameID": "", "GameSegment": "",
    "GroupQuantity": "2", "LastNGames": "0", "LeagueID": "00",
    "Location": "", "Month": "0", "OpponentTeamID": "0", "Outcome": "",
    "PORound": "", "PaceAdjust": "N", "PerMode": "Totals", "Period": "0",
    "PlusMinus": "N", "Rank": "N", "Season": "2025-26",
    "SeasonSegment": "", "SeasonType": "Regular Season", "ShotClockRange": "",
    "VsConference": "", "VsDivision": "",
}
TRIGGERS = (
    {
        "ordinal": 35, "request_id": "teamdashlineups:1610612754:base",
        "team_id": "1610612754", "team_name": "Indiana Pacers", "measure": "Base",
        "bytes": 65_800,
        "raw_sha256": "d0ec683e2879e8e58022114935b248f62531f88248c1e6a1374abca6def76bc3",
        "canonical_json_sha256": "0d55c4152259849055742855c5a156db935a2e12e77435a2b7b13d382ec945a5",
        "verification_state": "completed_verified", "row_count": 250,
    },
    {
        "ordinal": 36, "request_id": "teamdashlineups:1610612754:advanced",
        "team_id": "1610612754", "team_name": "Indiana Pacers", "measure": "Advanced",
        "bytes": 67_740,
        "raw_sha256": "45d6bf8a6fd7e1dcc1b47c5f3b52c278a1e0a8830a80a1a6b01d70e8e1a8faee",
        "canonical_json_sha256": "605e83bb954be19b6b52a29822c3dd6bfaf4f33e7fb5b483b61625aab1871120",
        "verification_state": "completed_verified", "row_count": 250,
    },
    {
        "ordinal": 53, "request_id": "teamdashlineups:1610612763:base",
        "team_id": "1610612763", "team_name": "Memphis Grizzlies", "measure": "Base",
        "bytes": 66_452,
        "raw_sha256": "540373cff09b3b5027144ef28a750a412408b23a01c56c7af256e309e2600b29",
        "canonical_json_sha256": "b562a30a8b188d73c6a66e5cd0851f028c0e1619245c01bb7fceb54d066eeccc",
        "verification_state": "completed_verified", "row_count": 250,
    },
    {
        "ordinal": 54, "request_id": "teamdashlineups:1610612763:advanced",
        "team_id": "1610612763", "team_name": "Memphis Grizzlies", "measure": "Advanced",
        "bytes": 68_221,
        "raw_sha256": "d7d59969325bc6731c057c7035f6629d2d28e079b6256c2fe87e83a386301fc6",
        "canonical_json_sha256": "2a7937fc2a54f855b39fa2cd92df1035c8ad9072bb2b8ab4b3ebcccccc4edfa3",
        "verification_state": "completed_verified", "row_count": 250,
    },
)

BOOLEAN_FIELDS = (
    "full_season_evidence_authenticated",
    "all_four_recovery_responses_present",
    "all_four_recovery_responses_authenticated",
    "all_four_recovery_responses_structurally_valid",
    "complete_complementary_date_coverage",
    "every_individual_window_below_250",
    "early_base_advanced_keys_equal",
    "late_base_advanced_keys_equal",
    "window_union_equals_full_season_keys",
    "recovered_only_keys_validated",
    "conflicting_state",
    "failed_or_quarantined",
)
COUNT_FIELDS = (
    "early_base_pair_row_count",
    "early_advanced_pair_row_count",
    "late_base_pair_row_count",
    "late_advanced_pair_row_count",
    "recovered_only_count",
    "full_season_only_count",
    "duplicate_count",
    "malformed_pair_count",
    "same_player_count",
    "base_only_count",
    "advanced_only_count",
)
DISPOSITION_FIELDS = BOOLEAN_FIELDS + COUNT_FIELDS
DISPOSITION_SCHEMA = {
    "schema_id": "phase3f-r2c.1.team-disposition-input.v1",
    "additional_properties": False,
    "required": list(DISPOSITION_FIELDS),
    "properties": {
        **{name: {"type": "boolean", "python_exact_type": "bool"} for name in BOOLEAN_FIELDS},
        **{
            name: {
                "type": "integer", "minimum": 0, "python_exact_type": "int",
                "coercion": False, "booleans_rejected": True,
            }
            for name in COUNT_FIELDS
        },
    },
}


class CorrectionError(RuntimeError):
    """Raised when authenticated inputs or write-once boundaries fail."""


@dataclass(frozen=True)
class DispositionDecision:
    disposition: str
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"disposition": self.disposition, "reason_codes": list(self.reason_codes)}


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> Any:
    def reject(token: str) -> None:
        raise ValueError(f"non-finite JSON token: {token}")

    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise CorrectionError(f"invalid JSON input: {path}") from exc


def _write_once(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(body)
    except FileExistsError as exc:
        raise CorrectionError(f"refusing to overwrite artifact: {path}") from exc


def _require_absent_namespace(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise CorrectionError(f"R2C.1 namespace already exists, is partial, or conflicts: {path}")


def _file_fingerprint(project_root: Path, relative_path: Path) -> dict[str, Any]:
    path = project_root / relative_path
    if not path.is_file() or path.is_symlink():
        raise CorrectionError(f"missing or non-regular preserved file: {relative_path.as_posix()}")
    stat = path.stat()
    return {
        "path": relative_path.as_posix(),
        "bytes": stat.st_size,
        "sha256": sha256_bytes(path.read_bytes()),
        "mtime_ns": stat.st_mtime_ns,
    }


def fingerprint_namespace(project_root: Path, relative_root: Path) -> dict[str, Any]:
    root = project_root / relative_root
    if not root.is_dir() or root.is_symlink():
        raise CorrectionError(f"missing or invalid preserved namespace: {relative_root.as_posix()}")
    paths = sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix())
    files = [_file_fingerprint(project_root, item.relative_to(project_root)) for item in paths]
    return {
        "namespace": relative_root.as_posix(),
        "file_count": len(files),
        "byte_count": sum(item["bytes"] for item in files),
        "inventory_sha256": sha256_bytes(canonical_json(files)),
        "files": files,
    }


def _authenticate_exact_files(
    project_root: Path, namespace: Path, expected: Mapping[str, tuple[int, str]]
) -> dict[str, Any]:
    root = project_root / namespace
    if not root.is_dir() or root.is_symlink():
        raise CorrectionError(f"missing authenticated namespace: {namespace.as_posix()}")
    entries = list(root.iterdir())
    if any(not item.is_file() or item.is_symlink() for item in entries):
        raise CorrectionError(f"namespace contains a non-file or symlink: {namespace.as_posix()}")
    observed_names = sorted(item.name for item in entries)
    if observed_names != sorted(expected):
        raise CorrectionError(f"namespace inventory mismatch: {namespace.as_posix()}")
    result = fingerprint_namespace(project_root, namespace)
    for entry in result["files"]:
        name = Path(entry["path"]).name
        expected_bytes, expected_hash = expected[name]
        if entry["bytes"] != expected_bytes or entry["sha256"] != expected_hash:
            raise CorrectionError(f"authenticated file mismatch: {entry['path']}")
    return result


def evaluate_disposition(record: Any) -> DispositionDecision:
    """Validate and classify without coercion, defaults, or caller-visible exceptions."""

    try:
        if not isinstance(record, Mapping):
            return DispositionDecision("recovery_unresolved", ("record_not_mapping",))

        reasons: list[str] = []
        keys = set(record.keys())
        for field in DISPOSITION_FIELDS:
            if field not in keys:
                reasons.append(f"missing_field:{field}")
        unexpected = sorted(
            (key if isinstance(key, str) else f"<{type(key).__name__}>")
            for key in keys
            if not isinstance(key, str) or key not in DISPOSITION_FIELDS
        )
        for label in unexpected:
            reasons.append(f"unexpected_field:{label}")
        if reasons:
            return DispositionDecision("recovery_unresolved", tuple(reasons))

        for field in BOOLEAN_FIELDS:
            if type(record[field]) is not bool:
                reasons.append(f"invalid_boolean_type:{field}")
        for field in COUNT_FIELDS:
            value = record[field]
            if type(value) is not int:
                reasons.append(f"invalid_count_type:{field}")
            elif value < 0:
                reasons.append(f"negative_count:{field}")
        if reasons:
            return DispositionDecision("recovery_unresolved", tuple(reasons))

        below_250 = all(record[field] < 250 for field in COUNT_FIELDS[:4])
        if record["every_individual_window_below_250"] is not below_250:
            reasons.append("contradiction:window_threshold_indicator")
        if not below_250:
            reasons.append("window_response_not_below_250")
        if record["recovered_only_count"] > 0 and not record["recovered_only_keys_validated"]:
            reasons.append("contradiction:recovered_count_without_validated_keys")
        if record["window_union_equals_full_season_keys"] and (
            record["recovered_only_count"] != 0 or record["full_season_only_count"] != 0
        ):
            reasons.append("contradiction:union_equality_with_set_difference")
        if record["early_base_advanced_keys_equal"] and record["late_base_advanced_keys_equal"] and (
            record["base_only_count"] != 0 or record["advanced_only_count"] != 0
        ):
            reasons.append("contradiction:base_advanced_equality_with_difference")
        if record["conflicting_state"]:
            reasons.append("evidence_conflicting")
        if record["failed_or_quarantined"]:
            reasons.append("evidence_failed_or_quarantined")
        if reasons:
            return DispositionDecision("recovery_unresolved", tuple(reasons))

        if record["recovered_only_count"] > 0:
            required_true = (
                "full_season_evidence_authenticated",
                "all_four_recovery_responses_present",
                "all_four_recovery_responses_authenticated",
                "all_four_recovery_responses_structurally_valid",
                "early_base_advanced_keys_equal",
                "late_base_advanced_keys_equal",
                "recovered_only_keys_validated",
            )
            for field in required_true:
                if not record[field]:
                    reasons.append(f"required_true_for_proven_non_exhaustive:{field}")
            for field in (
                "duplicate_count", "malformed_pair_count", "same_player_count",
                "base_only_count", "advanced_only_count",
            ):
                if record[field] != 0:
                    reasons.append(f"required_zero_for_valid_recovered_keys:{field}")
            if not reasons:
                return DispositionDecision(
                    "proven_non_exhaustive", ("validated_recovered_only_keys_present",)
                )
            return DispositionDecision("recovery_unresolved", tuple(reasons))

        operational_true = (
            "full_season_evidence_authenticated",
            "all_four_recovery_responses_present",
            "all_four_recovery_responses_authenticated",
            "all_four_recovery_responses_structurally_valid",
            "complete_complementary_date_coverage",
            "every_individual_window_below_250",
            "early_base_advanced_keys_equal",
            "late_base_advanced_keys_equal",
            "window_union_equals_full_season_keys",
            "recovered_only_keys_validated",
        )
        for field in operational_true:
            if not record[field]:
                reasons.append(f"required_true_for_operational_resolution:{field}")
        for field in COUNT_FIELDS[4:]:
            if record[field] != 0:
                reasons.append(f"required_zero_for_operational_resolution:{field}")
        if reasons:
            return DispositionDecision("recovery_unresolved", tuple(reasons))
        return DispositionDecision(
            "operationally_resolved_no_observed_omission",
            ("all_operational_resolution_conditions_satisfied",),
        )
    except Exception:
        return DispositionDecision("recovery_unresolved", ("invalid_record_processing_failure",))


def classify_disposition(record: Any) -> str:
    return evaluate_disposition(record).disposition


def validate_transport_contract(project_root: Path, binding: Any) -> dict[str, str]:
    if not isinstance(binding, Mapping):
        raise CorrectionError("transport binding must be an object")
    if set(binding) != {"path", "sha256"}:
        raise CorrectionError("transport binding requires the exact path and sha256 fields")
    path_value = binding["path"]
    digest = binding["sha256"]
    if type(path_value) is not str:
        raise CorrectionError("transport path must be a string")
    pure = PurePosixPath(path_value)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise CorrectionError("transport path must be an exact normalized repository-relative path")
    if path_value != R2B21_TRANSPORT_PATH_TEXT:
        raise CorrectionError("transport contract path mismatch")
    if type(digest) is not str or digest != R2B21_TRANSPORT_SHA256:
        raise CorrectionError("transport contract hash mismatch")
    path = project_root / R2B21_TRANSPORT_PATH
    if not path.is_file() or path.is_symlink():
        raise CorrectionError("transport contract file is missing")
    if sha256_bytes(path.read_bytes()) != R2B21_TRANSPORT_SHA256:
        raise CorrectionError("transport contract recomputed hash mismatch")
    return {"path": path_value, "sha256": digest}


def _exact_item(items: Any, field: str, value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(items, list):
        raise CorrectionError(f"{label} must be a list")
    matches = [item for item in items if isinstance(item, Mapping) and item.get(field) == value]
    if len(matches) != 1:
        raise CorrectionError(f"expected one {label} for {field}={value}")
    return matches[0]


def validate_trigger_documents(
    exact: Any, requests_value: Any, fingerprints: Any, attempts: Any
) -> list[dict[str, Any]]:
    if not isinstance(exact, Mapping) or not exact.get("teams"):
        raise CorrectionError("exact-250 inventory is malformed")
    teams = exact.get("teams")
    if not isinstance(teams, list) or [item.get("team_id") for item in teams if isinstance(item, Mapping)] != [
        "1610612754", "1610612763"
    ]:
        raise CorrectionError("exact-250 team inventory mismatch")

    authenticated: list[dict[str, Any]] = []
    for expected in TRIGGERS:
        team = _exact_item(teams, "team_id", expected["team_id"], "exact-250 team")
        if team.get("structural_disposition") != "exact_250_unresolved":
            raise CorrectionError("trigger team is not exact_250_unresolved")
        trigger = _exact_item(
            team.get("triggering_identities"), "request_id", expected["request_id"], "trigger identity"
        )
        request = _exact_item(requests_value, "request_id", expected["request_id"], "request identity")
        fingerprint = _exact_item(
            fingerprints, "request_id", expected["request_id"], "response fingerprint"
        )
        attempt = _exact_item(attempts, "request_id", expected["request_id"], "attempt metadata")

        trigger_expected = {
            "canonical_json_sha256": expected["canonical_json_sha256"],
            "measure": expected["measure"],
            "ordinal": expected["ordinal"],
            "raw_sha256": expected["raw_sha256"],
            "request_id": expected["request_id"],
        }
        if dict(trigger) != trigger_expected:
            raise CorrectionError(f"trigger identity mismatch: {expected['request_id']}")
        parameters = request.get("parameters")
        expected_parameters = {
            **ESTABLISHED_PARAMETER_DEFAULTS,
            "TeamID": expected["team_id"],
            "MeasureType": expected["measure"],
        }
        if request.get("ordinal") != expected["ordinal"] or parameters != expected_parameters:
            raise CorrectionError(f"trigger request metadata mismatch: {expected['request_id']}")
        fingerprint_expected = {
            "canonical_json_sha256": expected["canonical_json_sha256"],
            "ordinal": expected["ordinal"],
            "raw_bytes": expected["bytes"],
            "raw_sha256": expected["raw_sha256"],
            "request_id": expected["request_id"],
        }
        if dict(fingerprint) != fingerprint_expected:
            raise CorrectionError(f"trigger response fingerprint mismatch: {expected['request_id']}")
        attempt_fields = {
            "ordinal": expected["ordinal"], "request_id": expected["request_id"],
            "team_id": expected["team_id"], "measure": expected["measure"],
            "byte_count": expected["bytes"], "raw_sha256": expected["raw_sha256"],
            "canonical_json_sha256": expected["canonical_json_sha256"],
            "state": expected["verification_state"], "row_count": expected["row_count"],
        }
        for field, value in attempt_fields.items():
            if attempt.get(field) != value or type(attempt.get(field)) is not type(value):
                raise CorrectionError(f"trigger attempt mismatch: {expected['request_id']}:{field}")
        authenticated.append(dict(expected))
    return authenticated


def load_and_validate_triggers(project_root: Path) -> tuple[list[dict[str, Any]], list[Mapping[str, Any]]]:
    requests_value = _read_json(project_root / R2B2_REQUESTS_PATH)
    authenticated = validate_trigger_documents(
        _read_json(project_root / R2B2_EXACT_250_PATH),
        requests_value,
        _read_json(project_root / R2B2_FINGERPRINTS_PATH),
        _read_json(project_root / R2B2_ATTEMPTS_PATH),
    )
    selected = [
        _exact_item(requests_value, "request_id", trigger["request_id"], "request identity")
        for trigger in authenticated
    ]
    return authenticated, selected


def prove_window_coverage() -> dict[str, Any]:
    early_start = date.fromisoformat(WINDOWS[0]["DateFrom"])
    early_end = date.fromisoformat(WINDOWS[0]["DateTo"])
    late_start = date.fromisoformat(WINDOWS[1]["DateFrom"])
    late_end = date.fromisoformat(WINDOWS[1]["DateTo"])
    proof = {
        "both_within_verified_interval": (
            SEASON_START <= early_start <= early_end <= SEASON_END
            and SEASON_START <= late_start <= late_end <= SEASON_END
        ),
        "nonoverlapping": early_end < late_start,
        "contiguous": early_end + timedelta(days=1) == late_start,
        "complete_coverage": (
            early_start == SEASON_START
            and late_end == SEASON_END
            and early_end + timedelta(days=1) == late_start
        ),
        "verified_interval_day_count": (SEASON_END - SEASON_START).days + 1,
        "window_union_day_count": (
            (early_end - early_start).days + 1 + (late_end - late_start).days + 1
        ),
    }
    if not all(proof.values()):
        raise CorrectionError("complementary-window coverage proof failed")
    return proof


def build_recovery_identities(full_season_requests: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    source = {item["request_id"]: item for item in full_season_requests}
    output: list[dict[str, Any]] = []
    for team_id, team_name in (("1610612754", "Indiana Pacers"), ("1610612763", "Memphis Grizzlies")):
        team_triggers = [item for item in TRIGGERS if item["team_id"] == team_id]
        trigger_by_measure = {item["measure"]: item for item in team_triggers}
        for window in WINDOWS:
            for measure in ("Base", "Advanced"):
                ordinal = len(output) + 1
                full = source[trigger_by_measure[measure]["request_id"]]
                parameters = dict(full["parameters"])
                parameters.update(DateFrom=window["DateFrom"], DateTo=window["DateTo"])
                identity = {
                    "ordinal": ordinal,
                    "request_id": (
                        f"teamdashlineups:{team_id}:2025-26:regular-season:"
                        f"{window['DateFrom']}:{window['DateTo']}:{measure.lower()}"
                    ),
                    "team_id": team_id,
                    "team_name": team_name,
                    "endpoint": "teamdashlineups",
                    "endpoint_identity": "TeamDashLineups",
                    "season": "2025-26",
                    "season_type": "Regular Season",
                    "window": dict(window),
                    "measure": measure,
                    "parameters": parameters,
                    "triggering_full_season_identities": {
                        key: {
                            field: value
                            for field, value in trigger_by_measure[key].items()
                            if field in {
                                "ordinal", "request_id", "bytes", "raw_sha256",
                                "canonical_json_sha256",
                            }
                        }
                        for key in ("Base", "Advanced")
                    },
                    "corrected_response_contract_identity": R2B1_CONTRACT_IDENTITY,
                    "future_protected_transport_contract": {
                        "path": R2B21_TRANSPORT_PATH_TEXT,
                        "sha256": R2B21_TRANSPORT_SHA256,
                    },
                    "future_output_namespace": (
                        FUTURE_PROTECTED_NAMESPACE
                        / f"{ordinal:02d}-{team_id}-{window['name']}-{measure.lower()}"
                    ).as_posix(),
                    "specification_status": "frozen_not_authorized",
                }
                identity["canonical_request_identity_sha256"] = sha256_bytes(canonical_json(identity))
                output.append(identity)
    validate_recovery_inventory(output)
    return output


def validate_recovery_inventory(identities: Any) -> None:
    if not isinstance(identities, list) or len(identities) != 8:
        raise CorrectionError("recovery inventory must contain exactly eight identities")
    expected_teams = ["1610612754"] * 4 + ["1610612763"] * 4
    expected_windows = ["early", "early", "late", "late"] * 2
    expected_measures = ["Base", "Advanced", "Base", "Advanced"] * 2
    for index, identity in enumerate(identities, start=1):
        if not isinstance(identity, Mapping):
            raise CorrectionError("recovery identity must be an object")
        team_id = expected_teams[index - 1]
        window = next(item for item in WINDOWS if item["name"] == expected_windows[index - 1])
        measure = expected_measures[index - 1]
        expected_id = (
            f"teamdashlineups:{team_id}:2025-26:regular-season:"
            f"{window['DateFrom']}:{window['DateTo']}:{measure.lower()}"
        )
        expected_namespace = (
            FUTURE_PROTECTED_NAMESPACE
            / f"{index:02d}-{team_id}-{window['name']}-{measure.lower()}"
        ).as_posix()
        exact_values = {
            "ordinal": index, "team_id": team_id, "window": window, "measure": measure,
            "request_id": expected_id, "future_output_namespace": expected_namespace,
            "endpoint": "teamdashlineups", "endpoint_identity": "TeamDashLineups",
            "season": "2025-26", "season_type": "Regular Season",
            "corrected_response_contract_identity": R2B1_CONTRACT_IDENTITY,
            "specification_status": "frozen_not_authorized",
        }
        for field, expected in exact_values.items():
            if identity.get(field) != expected:
                raise CorrectionError(f"recovery identity mismatch: {index}:{field}")
        validate_transport_binding = identity.get("future_protected_transport_contract")
        if validate_transport_binding != {
            "path": R2B21_TRANSPORT_PATH_TEXT, "sha256": R2B21_TRANSPORT_SHA256
        }:
            raise CorrectionError("recovery transport binding mismatch")
        hashed = dict(identity)
        recorded_hash = hashed.pop("canonical_request_identity_sha256", None)
        if recorded_hash != sha256_bytes(canonical_json(hashed)):
            raise CorrectionError("recovery identity canonical hash mismatch")


def authenticate_public_source(project_root: Path) -> dict[str, Any]:
    fingerprint = _authenticate_exact_files(project_root, PUBLIC_SOURCE_NAMESPACE, PUBLIC_FILES)
    root = project_root / PUBLIC_SOURCE_NAMESPACE
    authorization = _read_json(root / "authorization-request.json")
    start = _read_json(root / "attempt-1-start.json")
    outcome = _read_json(root / "attempt-1-outcome.json")
    summary = _read_json(root / "verified-source-summary.json")
    if authorization.get("url") != PUBLIC_URL or authorization.get("authorized_attempts") != 1:
        raise CorrectionError("public authorization linkage mismatch")
    if start.get("url") != PUBLIC_URL or start.get("attempt_number") != 1:
        raise CorrectionError("public start linkage mismatch")
    if outcome.get("state") != "completed_verified" or outcome.get("attempt_number") != 1:
        raise CorrectionError("public outcome is not completed_verified")
    exact_summary = {
        "official_url": PUBLIC_URL,
        "season_start": SEASON_START.isoformat(),
        "season_end": SEASON_END.isoformat(),
        "byte_count": PUBLIC_BODY_BYTES,
        "raw_sha256": PUBLIC_BODY_SHA256,
        "request_count": 1,
        "protected_request_count": 0,
        "recovery_request_count": 0,
    }
    for field, value in exact_summary.items():
        if summary.get(field) != value or type(summary.get(field)) is not type(value):
            raise CorrectionError(f"public summary mismatch: {field}")
    if outcome.get("byte_count") != PUBLIC_BODY_BYTES or outcome.get("raw_sha256") != PUBLIC_BODY_SHA256:
        raise CorrectionError("public outcome fingerprint mismatch")
    return {
        "namespace": PUBLIC_SOURCE_NAMESPACE.as_posix(),
        "reuse_only_no_request": True,
        "url": PUBLIC_URL,
        "body_bytes": PUBLIC_BODY_BYTES,
        "raw_sha256": PUBLIC_BODY_SHA256,
        "season_start": SEASON_START.isoformat(),
        "season_end": SEASON_END.isoformat(),
        "fingerprint": fingerprint,
    }


def authenticate_original_and_historical(project_root: Path) -> dict[str, Any]:
    git_visible = []
    for text, (expected_bytes, expected_hash) in ORIGINAL_R2C_GIT_VISIBLE.items():
        fingerprint = _file_fingerprint(project_root, Path(text))
        if fingerprint["bytes"] != expected_bytes or fingerprint["sha256"] != expected_hash:
            raise CorrectionError(f"original R2C Git-visible file changed: {text}")
        git_visible.append(fingerprint)
    planning = _authenticate_exact_files(project_root, Path("planning/phase3f-r2c"), ORIGINAL_R2C_PLANNING)
    original_plan = _read_json(project_root / ORIGINAL_R2C_PLAN_PATH)
    expected_historical = original_plan.get("historical_preservation_before_state")
    if not isinstance(expected_historical, list):
        raise CorrectionError("authenticated original R2C plan lacks historical fingerprints")
    current_historical = [fingerprint_namespace(project_root, path) for path in PRESERVED_NAMESPACES[:6]]
    if current_historical != expected_historical:
        raise CorrectionError("R2B historical evidence changed after original R2C")
    return {
        "original_r2c_git_visible": git_visible,
        "original_r2c_planning": planning,
        "r2b_historical_namespaces": current_historical,
        "original_plan": original_plan,
    }


def _validate_response_contract(project_root: Path) -> dict[str, str]:
    path = project_root / R2B1_CONTRACT_PATH
    if not path.is_file() or sha256_bytes(path.read_bytes()) != R2B1_CONTRACT_FILE_SHA256:
        raise CorrectionError("R2B.1 response-contract file fingerprint mismatch")
    contract = _read_json(path)
    if contract.get("correction_contract_identity") != R2B1_CONTRACT_IDENTITY:
        raise CorrectionError("R2B.1 response-contract identity mismatch")
    return {"path": R2B1_CONTRACT_PATH.as_posix(), "identity": R2B1_CONTRACT_IDENTITY}


def build_artifacts(project_root: Path, output_dir: Path) -> dict[str, bytes]:
    project_root = Path(project_root)
    output_dir = Path(output_dir)
    _require_absent_namespace(output_dir)
    if (project_root / FUTURE_PROTECTED_NAMESPACE).exists():
        raise CorrectionError("recovery evidence namespace exists; correction must remain request-free")

    preserved = authenticate_original_and_historical(project_root)
    public = authenticate_public_source(project_root)
    response_contract = _validate_response_contract(project_root)
    transport_contract = validate_transport_contract(
        project_root, {"path": R2B21_TRANSPORT_PATH_TEXT, "sha256": R2B21_TRANSPORT_SHA256}
    )
    triggers, requests_value = load_and_validate_triggers(project_root)
    identities = build_recovery_identities(requests_value)
    original_identities = preserved["original_plan"].get("future_recovery_identities")
    if original_identities != identities:
        raise CorrectionError("original R2C request identities do not match independent R2C.1 validation")

    preservation = {
        "original_r2c_git_visible": preserved["original_r2c_git_visible"],
        "original_r2c_planning": preserved["original_r2c_planning"],
        "public_source": public["fingerprint"],
        "r2b_historical_namespaces": preserved["r2b_historical_namespaces"],
    }
    plan = {
        "version": VERSION,
        "classification": CLASSIFICATION,
        "correction_scope": {
            "original_r2c_audit_status": "failed",
            "failure_classification": "FAIL — R2C recovery specification is not defensible",
            "r2c_1_status": "correction checkpoint awaiting audit",
            "supersedes_original_r2c_for_future_recovery_authorization": True,
            "original_r2c_preserved_as_failed_historical_evidence": True,
            "neither_r2c_nor_r2c_1_authorizes_acquisition": True,
            "recovery_request_count": 0,
        },
        "original_r2c_plan_reference": {
            "path": ORIGINAL_R2C_PLAN_PATH.as_posix(),
            "bytes": ORIGINAL_R2C_PLAN_BYTES,
            "sha256": ORIGINAL_R2C_PLAN_SHA256,
        },
        "public_season_boundary_source": {key: value for key, value in public.items() if key != "fingerprint"},
        "verified_regular_season": {
            "season": "2025-26", "season_type": "Regular Season",
            "start": SEASON_START.isoformat(), "end": SEASON_END.isoformat(),
        },
        "complementary_windows": {
            "windows": [dict(item) for item in WINDOWS], "coverage_proof": prove_window_coverage()
        },
        "future_recovery_identities": identities,
        "authenticated_exact_250_triggers": triggers,
        "governing_contracts": {
            "r2b1_response_contract": response_contract,
            "r2b21_future_protected_transport_contract": transport_contract,
        },
        "disposition_input_contract": DISPOSITION_SCHEMA,
        "disposition_outputs": {
            "proven_non_exhaustive": {
                "rule": "one or more explicitly validated recovered-only keys under authenticated evidence proves the full-season response incomplete",
                "applied_during_r2c_1": False,
            },
            "operationally_resolved_no_observed_omission": {
                "rule": "all explicit operational conditions are present, valid, and satisfied",
                "limitation": "not proof of universal or mathematical exhaustiveness",
            },
            "recovery_unresolved": {
                "rule": "every missing, malformed, contradictory, failed, quarantined, conflicting, or otherwise unresolved record",
            },
        },
        "deterministic_unresolved_reason_code_families": [
            "record_not_mapping", "missing_field:<field>", "unexpected_field:<field>",
            "invalid_boolean_type:<field>", "invalid_count_type:<field>",
            "negative_count:<field>", "contradiction:<condition>",
            "window_response_not_below_250",
            "evidence_conflicting", "evidence_failed_or_quarantined",
            "required_true_for_proven_non_exhaustive:<field>",
            "required_zero_for_valid_recovered_keys:<field>",
            "required_true_for_operational_resolution:<field>",
            "required_zero_for_operational_resolution:<field>",
            "invalid_record_processing_failure",
        ],
        "population_reconciliation": {
            "scope": "population-only",
            "canonical_pair_identity": "exactly two distinct positive player IDs in numeric order",
            "rating_aggregation": False,
            "target_reconstruction": False,
            "rating_values_affect_retention": False,
            "preserve_zero_possession_rows": True,
        },
        "future_transport_restrictions_preserved": {
            "separate_explicit_acquisition_authorization_required": True,
            "phase_local_authorization_consistency": True,
            "exact_namespace_binding": True,
            "executing_source_pinning": True,
            "attempt_limit_per_identity": 1,
            "automatic_retries": 0,
            "redirects_allowed": False,
            "trust_env": False,
            "timeout_seconds": 30,
            "sequential_ordinal_order": True,
            "minimum_monotonic_completion_to_next_start_seconds": 1.0,
            "immutable_start_and_outcome_records": True,
            "verification_before_promotion": True,
            "quarantine_and_immediate_stop_on_failure": True,
            "restart_safe_refusal_states": [
                "incomplete", "conflicting", "failed", "quarantined"
            ],
        },
        "historical_preservation_before_state": preservation,
        "explicit_zero_operations": {
            "network_requests": 0, "protected_requests": 0, "recovery_requests": 0,
            "final_test_rows": 0, "estimator_operations": 0,
        },
    }
    summary = {
        "version": VERSION,
        "classification": CLASSIFICATION,
        "network_requests": 0,
        "public_source_reuse_only": True,
        "public_source_requests": 0,
        "protected_requests": 0,
        "recovery_requests": 0,
        "final_test_rows": 0,
        "estimator_operations": 0,
        "original_r2c_audit_status": "failed",
        "r2c_1_status": "correction checkpoint awaiting audit",
        "team_status": {
            "Indiana Pacers": "exact_250_unresolved",
            "Memphis Grizzlies": "exact_250_unresolved",
        },
        "final_test_readiness": "blocked on recovery and later audited gates",
        "acquisition_authorized": False,
    }
    plan_body = canonical_json(plan)
    summary_body = canonical_json(summary)
    manifest = {
        "version": VERSION,
        "rule": "nonrecursive SHA-256 over corrected_recovery_plan.json and summary.json; manifest excludes itself",
        "artifact_inventory": list(OUTPUT_FILES),
        "artifacts": {
            "corrected_recovery_plan.json": {
                "bytes": len(plan_body), "sha256": sha256_bytes(plan_body)
            },
            "summary.json": {"bytes": len(summary_body), "sha256": sha256_bytes(summary_body)},
        },
    }
    artifacts = {
        "corrected_recovery_plan.json": plan_body,
        "artifact_hashes.json": canonical_json(manifest),
        "summary.json": summary_body,
    }
    if tuple(artifacts) != OUTPUT_FILES:
        raise CorrectionError("generated inventory mismatch")
    for body in artifacts.values():
        json.loads(body.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    return artifacts


def write_specification(project_root: Path, output_dir: Path) -> dict[str, Any]:
    artifacts = build_artifacts(project_root, output_dir)
    _require_absent_namespace(Path(output_dir))
    for name, body in artifacts.items():
        _write_once(Path(output_dir) / name, body)
    return {
        "classification": CLASSIFICATION,
        "artifacts": {
            name: {"bytes": len(body), "sha256": sha256_bytes(body)}
            for name, body in artifacts.items()
        },
    }
