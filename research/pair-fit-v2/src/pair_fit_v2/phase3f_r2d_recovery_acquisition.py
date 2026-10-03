"""Phase 3F-R2D exact-250 recovery acquisition and population reconciliation.

The only network-capable path is restricted to the exact eight identities frozen
in the authenticated R2C.1 corrected recovery plan.  The module performs no
rating aggregation, target reconstruction, final-test construction, feature
work, preprocessing, estimator, prediction, metric, or model serialization.
"""

from __future__ import annotations

import hashlib
import json
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


VERSION = "phase3f-r2d.exact-250-recovery-acquisition.v1"
PHASE = "Phase 3F-R2D - Indiana/Memphis Exact-250 Recovery Acquisition"
EXPECTED_HEAD = "f7f72eda75fecfeab044b6f0315f263b71af657d"
EXPECTED_BRANCH = "research/pair-fit-v2"
PLAN_PATH = Path("planning/phase3f-r2c.1/corrected_recovery_plan.json")
PLAN_BYTES = 131_714
PLAN_SHA256 = "eeb762fa61608b7920ef418175c8c26d54bd7436f7fa5bbbca9982d089330c07"
PLAN_NAMESPACE = Path("planning/phase3f-r2c.1")
PLAN_MANIFEST = {
    "artifact_hashes.json": (599, "be6abe8605a480e62d20b7c368b16039c1072804565fa4ef8ee0ba04919fa686"),
    "corrected_recovery_plan.json": (PLAN_BYTES, PLAN_SHA256),
    "summary.json": (718, "810478e5ff8d715a9044d41c34abd7f483df6c936e18cb2f97a162ea74964417"),
}
CONTRACT_PATH = Path("planning/phase3f-r2b.1/response_contract.json")
CONTRACT_FILE_SHA256 = "ecc3ecf1d547401539af8f8f640002fc3887de3dd64f1e80af1d41d62d04c49e"
CONTRACT_IDENTITY = "sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad"
TRANSPORT_PATH = Path("planning/phase3f-r2b.2.1/future_protected_transport_contract.json")
TRANSPORT_BYTES = 4_074
TRANSPORT_SHA256 = "20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234"
PUBLIC_SOURCE_PATH = Path("cache/phase3f-r2c-public-source/response.html")
PUBLIC_SOURCE_BYTES = 126_442
PUBLIC_SOURCE_SHA256 = "8a61156b746821a0341dd77be87ad97f3d9a55c40f184f9012bdc76795bebca3"
URL = "https://stats.nba.com/stats/teamdashlineups"
TIMEOUT_SECONDS = 30
MINIMUM_PACING_SECONDS = 1.0
PLANNING_NAMESPACE = Path("planning/phase3f-r2d")
EVIDENCE_NAMESPACE = Path("cache/phase3f-r2d/protected-recovery")
LEGACY_RECOVERY_NAMESPACE = Path("cache/phase3f-r2c-protected-recovery")
SOURCE_PATH = Path("src/pair_fit_v2/phase3f_r2d_recovery_acquisition.py")
CLI_PATH = Path("src/pair_fit_v2/phase3f_r2d_cli.py")
OUTPUT_FILES = (
    "recovery_authorization.json",
    "request_ledger.json",
    "response_fingerprints.json",
    "team_reconciliation.json",
    "team_dispositions.json",
    "readiness_effect.json",
    "artifact_hashes.json",
    "summary.json",
)
GIT_VISIBLE_DELIVERABLES = {
    ".gitignore": "M",
    "PHASE3F_R2D_EXACT_250_RECOVERY_ACQUISITION_POLICY.md": "??",
    "PHASE3F_R2D_EXACT_250_RECOVERY_ACQUISITION_REPORT.md": "??",
    SOURCE_PATH.as_posix(): "??",
    CLI_PATH.as_posix(): "??",
    "tests/test_phase3f_r2d_recovery_acquisition.py": "??",
}
STATE_FILES = {
    "start": "attempt-1-start.json",
    "response": "attempt-1-response.bin",
    "outcome": "attempt-1-outcome.json",
    "verification": "verification.json",
    "verified_body": "verified-response.bin",
    "quarantine": "quarantine.json",
}
EXECUTION_FILES = {
    "start": "official-invocation-start.json",
    "outcome": "official-invocation-outcome.json",
}
HISTORICAL_GIT_FILES = (
    "PHASE3F_R2B_PROTECTED_PAIR_ACQUISITION_POLICY.md",
    "PHASE3F_R2B_PROTECTED_PAIR_ACQUISITION_REPORT.md",
    "PHASE3F_R2B_1_RESPONSE_CONTRACT_POLICY.md",
    "PHASE3F_R2B_1_RESPONSE_CONTRACT_REPORT.md",
    "PHASE3F_R2B_2_PROTECTED_ACQUISITION_CONTINUATION_POLICY.md",
    "PHASE3F_R2B_2_PROTECTED_ACQUISITION_CONTINUATION_REPORT.md",
    "PHASE3F_R2B_2_1_PROCEDURAL_CLOSURE_POLICY.md",
    "PHASE3F_R2B_2_1_PROCEDURAL_CLOSURE_REPORT.md",
    "PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_POLICY.md",
    "PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_REPORT.md",
    "PHASE3F_R2C_1_RECOVERY_SPECIFICATION_CORRECTION_POLICY.md",
    "PHASE3F_R2C_1_RECOVERY_SPECIFICATION_CORRECTION_REPORT.md",
    "src/pair_fit_v2/phase3f_r2b_protected_pair_acquisition.py",
    "src/pair_fit_v2/phase3f_r2b_cli.py",
    "src/pair_fit_v2/phase3f_r2b_1_response_contract.py",
    "src/pair_fit_v2/phase3f_r2b_1_cli.py",
    "src/pair_fit_v2/phase3f_r2b_2_protected_acquisition_continuation.py",
    "src/pair_fit_v2/phase3f_r2b_2_cli.py",
    "src/pair_fit_v2/phase3f_r2b_2_1_procedural_closure.py",
    "src/pair_fit_v2/phase3f_r2b_2_1_cli.py",
    "src/pair_fit_v2/phase3f_r2c_recovery_specification.py",
    "src/pair_fit_v2/phase3f_r2c_cli.py",
    "src/pair_fit_v2/phase3f_r2c_1_recovery_specification.py",
    "src/pair_fit_v2/phase3f_r2c_1_cli.py",
    "tests/test_phase3f_r2b_protected_pair_acquisition.py",
    "tests/test_phase3f_r2b_1_response_contract.py",
    "tests/test_phase3f_r2b_2_protected_acquisition_continuation.py",
    "tests/test_phase3f_r2b_2_1_procedural_closure.py",
    "tests/test_phase3f_r2c_recovery_specification.py",
    "tests/test_phase3f_r2c_1_recovery_specification.py",
)
FULL_SEASON_SPECS = {
    ("1610612754", "Base"): {
        "team_name": "Indiana Pacers", "ordinal": 35,
        "request_id": "teamdashlineups:1610612754:base", "bytes": 65_800,
        "raw_sha256": "d0ec683e2879e8e58022114935b248f62531f88248c1e6a1374abca6def76bc3",
        "canonical_json_sha256": "0d55c4152259849055742855c5a156db935a2e12e77435a2b7b13d382ec945a5",
    },
    ("1610612754", "Advanced"): {
        "team_name": "Indiana Pacers", "ordinal": 36,
        "request_id": "teamdashlineups:1610612754:advanced", "bytes": 67_740,
        "raw_sha256": "45d6bf8a6fd7e1dcc1b47c5f3b52c278a1e0a8830a80a1a6b01d70e8e1a8faee",
        "canonical_json_sha256": "605e83bb954be19b6b52a29822c3dd6bfaf4f33e7fb5b483b61625aab1871120",
    },
    ("1610612763", "Base"): {
        "team_name": "Memphis Grizzlies", "ordinal": 53,
        "request_id": "teamdashlineups:1610612763:base", "bytes": 66_452,
        "raw_sha256": "540373cff09b3b5027144ef28a750a412408b23a01c56c7af256e309e2600b29",
        "canonical_json_sha256": "b562a30a8b188d73c6a66e5cd0851f028c0e1619245c01bb7fceb54d066eeccc",
    },
    ("1610612763", "Advanced"): {
        "team_name": "Memphis Grizzlies", "ordinal": 54,
        "request_id": "teamdashlineups:1610612763:advanced", "bytes": 68_221,
        "raw_sha256": "d7d59969325bc6731c057c7035f6629d2d28e079b6256c2fe87e83a386301fc6",
        "canonical_json_sha256": "2a7937fc2a54f855b39fa2cd92df1035c8ad9072bb2b8ab4b3ebcccccc4edfa3",
    },
}
AUTHORIZED_HISTORICAL_BODY_PATHS = {
    f"cache/phase3f-r2b.2/protected-final-target/{spec['ordinal']:02d}-"
    f"{team_id}-{measure.lower()}/verified-response.bin"
    for (team_id, measure), spec in FULL_SEASON_SPECS.items()
}


class RecoveryError(RuntimeError):
    """Fail-closed authorization, state, transport, or reconciliation error."""


class ResponseError(RecoveryError):
    """A received response failed transport or structural authentication."""

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
        raise RecoveryError(f"write-once record already exists: {path}") from exc


def _git(project_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=project_root, check=check, capture_output=True, text=True
    )


def identity_sha256(request: Mapping[str, Any]) -> str:
    # R2C.1 deliberately bound the complete frozen identity, not merely the
    # endpoint/parameter transport tuple.  Phase-local authorization fields are
    # excluded because they did not exist in the corrected plan.
    value = {
        key: item
        for key, item in request.items()
        if key not in {
            "canonical_request_identity_sha256", "authorization_phase",
            "network_authorized", "attempt_limit", "r2d_output_namespace",
        }
    }
    return sha256_bytes(serialize_json(value))


def _plan_style_namespace_fingerprint(
    project_root: Path, relative_root: Path, expected: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = project_root / relative_root
    if not root.is_dir() or root.is_symlink():
        raise RecoveryError(f"missing or invalid preserved namespace: {relative_root.as_posix()}")
    expected_files = {
        item["path"]: item for item in (expected or {}).get("files", [])
    }
    files = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda p: p.as_posix()):
        if path.is_symlink():
            raise RecoveryError(f"symlink prohibited in preserved namespace: {path}")
        stat = path.stat()
        relative = path.relative_to(project_root).as_posix()
        expected_file = expected_files.get(relative)
        if path.suffix == ".bin" and relative not in AUTHORIZED_HISTORICAL_BODY_PATHS:
            # The phase must not open any other historical protected body.  Its
            # frozen content hash is carried forward only after exact path,
            # regular-file, byte-count, and nanosecond-mtime authentication.
            if expected_file is None:
                raise RecoveryError(f"unexpected protected response body: {relative}")
            digest = expected_file["sha256"]
        else:
            digest = sha256_bytes(path.read_bytes())
        files.append({
            "path": relative, "bytes": stat.st_size,
            "sha256": digest, "mtime_ns": stat.st_mtime_ns,
        })
    pretty = serialize_json(files)
    return {
        "namespace": relative_root.as_posix(), "file_count": len(files),
        "byte_count": sum(item["bytes"] for item in files),
        "inventory_sha256": sha256_bytes(pretty), "files": files,
    }


def _compact_namespace(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in ("namespace", "file_count", "byte_count", "inventory_sha256")}


def _assert_regular_file(path: Path, expected: Mapping[str, Any], label: str) -> None:
    if not path.is_file() or path.is_symlink() or _fingerprint(path) != dict(expected):
        raise RecoveryError(f"{label} fingerprint mismatch: {path}")


def load_corrected_plan(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan_path = root / PLAN_PATH
    _assert_regular_file(plan_path, {"bytes": PLAN_BYTES, "sha256": PLAN_SHA256}, "corrected plan")
    namespace = root / PLAN_NAMESPACE
    if sorted(item.name for item in namespace.iterdir()) != sorted(PLAN_MANIFEST):
        raise RecoveryError("R2C.1 planning namespace inventory mismatch")
    for name, (size, digest) in PLAN_MANIFEST.items():
        _assert_regular_file(namespace / name, {"bytes": size, "sha256": digest}, "R2C.1 artifact")
    manifest = _read_json(namespace / "artifact_hashes.json")
    if manifest.get("artifact_inventory") != [
        "corrected_recovery_plan.json", "artifact_hashes.json", "summary.json"
    ] or manifest.get("rule") != (
        "nonrecursive SHA-256 over corrected_recovery_plan.json and summary.json; manifest excludes itself"
    ):
        raise RecoveryError("R2C.1 manifest rule or inventory mismatch")
    plan = _read_json(plan_path)
    if not isinstance(plan, dict):
        raise RecoveryError("corrected plan is not a mapping")
    return plan


def validate_frozen_requests(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = plan.get("future_recovery_identities")
    if not isinstance(raw, list) or len(raw) != 8:
        raise RecoveryError("corrected plan must contain exactly eight recovery identities")
    requests_value = [dict(item) for item in raw]
    expected_order = [
        (1, "1610612754", "early", "Base"),
        (2, "1610612754", "early", "Advanced"),
        (3, "1610612754", "late", "Base"),
        (4, "1610612754", "late", "Advanced"),
        (5, "1610612763", "early", "Base"),
        (6, "1610612763", "early", "Advanced"),
        (7, "1610612763", "late", "Base"),
        (8, "1610612763", "late", "Advanced"),
    ]
    if [(item.get("ordinal"), item.get("team_id"), item.get("window", {}).get("name"), item.get("measure")) for item in requests_value] != expected_order:
        raise RecoveryError("exact eight recovery order differs from R2C.1")
    for item in requests_value:
        parameters = item.get("parameters")
        if not isinstance(parameters, dict):
            raise RecoveryError("recovery parameters missing")
        window = item["window"]
        required = {
            "TeamID": item["team_id"], "MeasureType": item["measure"],
            "Season": "2025-26", "SeasonType": "Regular Season", "GroupQuantity": "2",
            "PerMode": "Totals", "DateFrom": window["DateFrom"], "DateTo": window["DateTo"],
        }
        if any(parameters.get(key) != value for key, value in required.items()):
            raise RecoveryError("recovery request science differs from R2C.1")
        if item.get("endpoint") != "teamdashlineups":
            raise RecoveryError("recovery endpoint differs from R2C.1")
        if item.get("canonical_request_identity_sha256") != identity_sha256(item):
            raise RecoveryError("recovery canonical identity differs from R2C.1")
        if item.get("corrected_response_contract_identity") != CONTRACT_IDENTITY:
            raise RecoveryError("recovery response-contract identity differs")
        if item.get("specification_status") != "frozen_not_authorized":
            raise RecoveryError("R2C.1 identity status differs")
    if len({item["request_id"] for item in requests_value}) != 8:
        raise RecoveryError("duplicate recovery request ID")
    return requests_value


def validate_request_identity(request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]]) -> None:
    by_ordinal = {item["ordinal"]: item for item in frozen}
    original = by_ordinal.get(request.get("ordinal"))
    fields = (
        "ordinal", "request_id", "endpoint", "parameters",
        "canonical_request_identity_sha256", "team_id", "team_name", "measure", "window",
    )
    if original is None or any(request.get(field) != original.get(field) for field in fields):
        raise RecoveryError("request differs from exact R2C.1 allowlist")
    if identity_sha256(request) != request["canonical_request_identity_sha256"]:
        raise RecoveryError("request identity hash mismatch")


def _historical_git_fingerprints(project_root: Path) -> list[dict[str, Any]]:
    output = []
    for relative in HISTORICAL_GIT_FILES:
        path = project_root / relative
        if not path.is_file() or path.is_symlink():
            raise RecoveryError(f"historical Git-visible file missing: {relative}")
        if _git(project_root, "diff", "--quiet", "HEAD", "--", relative, check=False).returncode != 0:
            raise RecoveryError(f"historical Git-visible file modified: {relative}")
        fp = _fingerprint(path)
        output.append({"path": relative, **fp})
    return output


def git_visible_worktree_inventory(project_root: Path) -> dict[str, str]:
    prefix = "research/pair-fit-v2/"
    result = _git(project_root, "status", "--porcelain=v1", "--untracked-files=all", "--", ".")
    output: dict[str, str] = {}
    for line in result.stdout.splitlines():
        raw_path = line[3:].replace("\\", "/")
        relative = raw_path.removeprefix(prefix)
        output[relative] = line[:2].strip()
    return output


def authenticate_frozen_inputs(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if _git(root, "rev-parse", "HEAD").stdout.strip() != EXPECTED_HEAD:
        raise RecoveryError("HEAD differs from required starting checkpoint")
    if _git(root, "branch", "--show-current").stdout.strip() != EXPECTED_BRANCH:
        raise RecoveryError("branch differs from required branch")
    upstream = _git(root, "rev-list", "--left-right", "--count", "@{upstream}...HEAD").stdout.split()
    if upstream != ["0", "0"]:
        raise RecoveryError("upstream ahead/behind is not 0/0")
    plan = load_corrected_plan(root)
    requests_value = validate_frozen_requests(plan)

    contract_path = root / CONTRACT_PATH
    if _fingerprint(contract_path)["sha256"] != CONTRACT_FILE_SHA256:
        raise RecoveryError("R2B.1 response-contract file mismatch")
    if _read_json(contract_path).get("correction_contract_identity") != CONTRACT_IDENTITY:
        raise RecoveryError("R2B.1 response-contract internal identity mismatch")
    _assert_regular_file(
        root / TRANSPORT_PATH,
        {"bytes": TRANSPORT_BYTES, "sha256": TRANSPORT_SHA256},
        "future protected transport contract",
    )
    _assert_regular_file(
        root / PUBLIC_SOURCE_PATH,
        {"bytes": PUBLIC_SOURCE_BYTES, "sha256": PUBLIC_SOURCE_SHA256},
        "public season source",
    )
    public = plan.get("public_season_boundary_source", {})
    if (
        public.get("url") != "https://pr.nba.com/2025-26-nba-regular-season-schedule/"
        or public.get("season_start") != "2025-10-21"
        or public.get("season_end") != "2026-04-12"
        or public.get("reuse_only_no_request") is not True
    ):
        raise RecoveryError("public season-boundary evidence differs")
    summary = _read_json(root / PLAN_NAMESPACE / "summary.json")
    if summary.get("team_status") != {
        "Indiana Pacers": "exact_250_unresolved", "Memphis Grizzlies": "exact_250_unresolved"
    } or summary.get("original_r2c_audit_status") != "failed":
        raise RecoveryError("R2C.1 unresolved team state differs")
    if (root / LEGACY_RECOVERY_NAMESPACE).exists():
        raise RecoveryError("a prior recovery-request namespace exists")

    preservation = plan.get("historical_preservation_before_state")
    if not isinstance(preservation, dict):
        raise RecoveryError("R2C.1 historical preservation record missing")
    expected_namespaces = list(preservation.get("r2b_historical_namespaces", [])) + [
        preservation.get("original_r2c_planning"), preservation.get("public_source")
    ]
    before = []
    for expected in expected_namespaces:
        if not isinstance(expected, dict):
            raise RecoveryError("historical namespace fingerprint missing")
        relative = Path(expected["namespace"])
        observed = _plan_style_namespace_fingerprint(root, relative, expected)
        if observed != expected:
            raise RecoveryError(f"historical namespace changed: {relative.as_posix()}")
        before.append(_compact_namespace(observed))
    before.append(_compact_namespace(_plan_style_namespace_fingerprint(root, PLAN_NAMESPACE)))
    return {
        "plan": plan,
        "requests": requests_value,
        "historical_git_visible": _historical_git_fingerprints(root),
        "preservation_fingerprints": before,
        "contracts": {
            "response_contract": {"path": CONTRACT_PATH.as_posix(), "identity": CONTRACT_IDENTITY},
            "transport_contract": {
                "path": TRANSPORT_PATH.as_posix(), "bytes": TRANSPORT_BYTES,
                "sha256": TRANSPORT_SHA256,
            },
        },
    }


def _python_identity(executable: Path) -> dict[str, Any]:
    path = executable.resolve()
    value = {"path": str(path), "version": sys.version, "implementation": sys.implementation.name}
    if path.is_file():
        value.update(_fingerprint(path))
    return value


def official_argv(project_root: Path) -> list[str]:
    root = Path(project_root).resolve()
    return [
        str(Path(sys.executable).resolve()), "-m", "pair_fit_v2.phase3f_r2d_cli", "run",
        "--project-root", ".", "--authorization", PLANNING_NAMESPACE.joinpath("recovery_authorization.json").as_posix(),
        "--evidence-root", EVIDENCE_NAMESPACE.as_posix(), "--planning-dir", PLANNING_NAMESPACE.as_posix(),
    ]


def build_authorization(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    authenticated = authenticate_frozen_inputs(root)
    source_fp = _fingerprint(root / SOURCE_PATH)
    cli_fp = _fingerprint(root / CLI_PATH)
    worktree = git_visible_worktree_inventory(root)
    if worktree != GIT_VISIBLE_DELIVERABLES:
        raise RecoveryError(f"Git-visible worktree inventory differs from the exact R2D allowlist: {worktree}")
    requests_value = authenticated["requests"]
    return {
        "version": VERSION, "phase": PHASE, "created_at_utc": utc_now(),
        "required_starting_head": EXPECTED_HEAD, "branch": EXPECTED_BRANCH,
        "upstream_ahead": 0, "upstream_behind": 0,
        "corrected_plan": {"path": PLAN_PATH.as_posix(), "bytes": PLAN_BYTES, "sha256": PLAN_SHA256},
        "response_contract_identity": CONTRACT_IDENTITY,
        "transport_contract": authenticated["contracts"]["transport_contract"],
        "authorized_requests": [
            {
                **item, "authorization_phase": "Phase 3F-R2D", "network_authorized": True,
                "attempt_limit": 1,
                "r2d_output_namespace": (EVIDENCE_NAMESPACE / request_slug(item)).as_posix(),
            }
            for item in requests_value
        ],
        "authorized_request_count": 8,
        "ordered_request_ids": [item["request_id"] for item in requests_value],
        "output_namespaces": {
            "protected_recovery": str((root / EVIDENCE_NAMESPACE).resolve()),
            "reconciliation": str((root / PLANNING_NAMESPACE).resolve()),
        },
        "implementation_source": {"path": SOURCE_PATH.as_posix(), **source_fp},
        "cli_source": {"path": CLI_PATH.as_posix(), **cli_fp},
        "python_executable": _python_identity(Path(sys.executable)),
        "working_directory": str(root), "required_pythonpath": "src",
        "official_command_argv": official_argv(root),
        "transport": {
            "url": URL, "timeout_seconds": TIMEOUT_SECONDS, "allow_redirects": False,
            "trust_env": False, "automatic_retries": 0, "proxy_substitution": False,
            "fallback_endpoint": False, "sequential": True,
            "minimum_monotonic_completion_to_next_start_seconds": MINIMUM_PACING_SECONDS,
            "headers": dict(RESEARCH_HEADERS),
        },
        "restart_rules": {
            "not_started": "eligible for its one authorized attempt",
            "completed_verified": "rehash, revalidate, and skip",
            "started_without_outcome": "stop for audit",
            "failed_or_quarantined": "preserve and stop",
            "conflicting_state": "refuse progress",
        },
        "scope": {
            "population_reconciliation_only": True, "rating_aggregation_authorized": False,
            "target_reconstruction_authorized": False, "final_test_construction_authorized": False,
            "prior_profile_join_authorized": False, "preprocessing_authorized": False,
            "estimator_or_prediction_authorized": False,
        },
        "full_season_trigger_references": [dict(value) for value in FULL_SEASON_SPECS.values()],
        "historical_git_visible_fingerprints": authenticated["historical_git_visible"],
        "historical_namespace_fingerprints_before": authenticated["preservation_fingerprints"],
        "git_visible_worktree_inventory": worktree,
        "import_canary_required_count": 1, "official_invocation_limit": 1,
    }


def initialize_authorization(project_root: Path, planning_dir: Path, evidence_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    planning = Path(planning_dir).resolve()
    evidence = Path(evidence_root).resolve()
    expected_planning = (root / PLANNING_NAMESPACE).resolve()
    expected_evidence = (root / EVIDENCE_NAMESPACE).resolve()
    if planning != expected_planning or evidence != expected_evidence:
        raise RecoveryError("authorization output namespaces are not the exact R2D paths")
    if planning.exists() or planning.is_symlink() or evidence.exists() or evidence.is_symlink():
        raise RecoveryError("R2D output namespace exists, is partial, or conflicts")
    authorization = build_authorization(root)
    _write_once(planning / "recovery_authorization.json", serialize_json(authorization))
    return authorization


def validate_authorization(
    authorization: Mapping[str, Any], project_root: Path, evidence_root: Path, planning_dir: Path,
) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    evidence = Path(evidence_root).resolve()
    planning = Path(planning_dir).resolve()
    if evidence != (root / EVIDENCE_NAMESPACE).resolve() or planning != (root / PLANNING_NAMESPACE).resolve():
        raise RecoveryError("invocation namespace differs from pinned R2D namespace")
    if authorization.get("required_starting_head") != EXPECTED_HEAD or authorization.get("branch") != EXPECTED_BRANCH:
        raise RecoveryError("authorization Git identity mismatch")
    authenticated = authenticate_frozen_inputs(root)
    frozen = authenticated["requests"]
    requests_value = authorization.get("authorized_requests")
    if not isinstance(requests_value, list) or len(requests_value) != 8:
        raise RecoveryError("authorization does not contain exactly eight requests")
    for authorized, original in zip(requests_value, frozen):
        validate_request_identity(authorized, frozen)
        if authorized.get("network_authorized") is not True or authorized.get("attempt_limit") != 1:
            raise RecoveryError("phase-local request authorization mismatch")
        if authorized.get("r2d_output_namespace") != (EVIDENCE_NAMESPACE / request_slug(original)).as_posix():
            raise RecoveryError("per-request namespace binding mismatch")
    if authorization.get("ordered_request_ids") != [item["request_id"] for item in frozen]:
        raise RecoveryError("authorization order differs from R2C.1")
    for key, relative in (("implementation_source", SOURCE_PATH), ("cli_source", CLI_PATH)):
        expected = authorization.get(key)
        if not isinstance(expected, dict) or expected.get("path") != relative.as_posix():
            raise RecoveryError(f"{key} path binding mismatch")
        if _fingerprint(root / relative) != {"bytes": expected.get("bytes"), "sha256": expected.get("sha256")}:
            raise RecoveryError(f"{key} executing hash differs from authorization")
    if authorization.get("python_executable") != _python_identity(Path(sys.executable)):
        raise RecoveryError("Python executable identity differs from authorization")
    if authorization.get("working_directory") != str(root) or Path.cwd().resolve() != root:
        raise RecoveryError("working directory differs from authorization")
    if os.environ.get("PYTHONPATH") != authorization.get("required_pythonpath") or os.environ.get("PYTHONPATH") != "src":
        raise RecoveryError("PYTHONPATH differs from authorization")
    if official_argv(root) != authorization.get("official_command_argv"):
        raise RecoveryError("official command differs from authorization")
    if authorization.get("output_namespaces") != {
        "protected_recovery": str(evidence), "reconciliation": str(planning)
    }:
        raise RecoveryError("authorization namespace identity mismatch")
    expected_transport = {
        "url": URL, "timeout_seconds": TIMEOUT_SECONDS, "allow_redirects": False,
        "trust_env": False, "automatic_retries": 0, "proxy_substitution": False,
        "fallback_endpoint": False, "sequential": True,
        "minimum_monotonic_completion_to_next_start_seconds": MINIMUM_PACING_SECONDS,
        "headers": dict(RESEARCH_HEADERS),
    }
    if authorization.get("transport") != expected_transport:
        raise RecoveryError("transport settings differ from frozen authorization")
    if authorization.get("scope", {}).get("population_reconciliation_only") is not True or any(
        authorization.get("scope", {}).get(field) is not False
        for field in (
            "rating_aggregation_authorized", "target_reconstruction_authorized",
            "final_test_construction_authorized", "prior_profile_join_authorized",
            "preprocessing_authorized", "estimator_or_prediction_authorized",
        )
    ):
        raise RecoveryError("authorization scope is broader than population reconciliation")
    current_worktree = git_visible_worktree_inventory(root)
    if (
        authorization.get("git_visible_worktree_inventory") != GIT_VISIBLE_DELIVERABLES
        or current_worktree != GIT_VISIBLE_DELIVERABLES
    ):
        raise RecoveryError("Git-visible worktree inventory changed or contains unrelated work")
    return [dict(item) for item in requests_value]


def request_slug(request: Mapping[str, Any]) -> str:
    return (
        f"{int(request['ordinal']):02d}-{request['team_id']}-"
        f"{request['window']['name']}-{request['measure'].lower()}"
    )


def request_paths(evidence_root: Path, request: Mapping[str, Any]) -> dict[str, Path]:
    base = Path(evidence_root) / request_slug(request)
    return {name: base / filename for name, filename in STATE_FILES.items()}


def _record_matches(record: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    return (
        record.get("request_id") == request.get("request_id")
        and record.get("ordinal") == request.get("ordinal")
        and record.get("canonical_request_identity_sha256") == identity_sha256(request)
        and record.get("attempt_number") == 1
    )


def _named_lineups(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    result_sets = payload.get("resultSets")
    if not isinstance(result_sets, list):
        raise ResponseError("resultSets missing")
    matches = [item for item in result_sets if isinstance(item, dict) and item.get("name") == "Lineups"]
    if len(matches) != 1:
        raise ResponseError("missing or duplicate Lineups result set")
    return matches[0]


def _normalize(value: Any) -> str:
    return "" if value is None else str(value)


def verify_response_bytes(
    body: bytes, request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validate_request_identity(request, frozen)
    try:
        diagnostics = validate_response_contract(body, request)
        payload = strict_json_bytes(body)
    except (ContractError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ResponseError(f"corrected R2B.1 response contract failed: {exc}") from exc
    returned = payload.get("parameters")
    if returned is not None:
        if not isinstance(returned, dict):
            raise ResponseError("returned parameters malformed")
        for key, expected in request["parameters"].items():
            if key in returned and _normalize(returned[key]) != _normalize(expected):
                raise ResponseError(f"returned parameter mismatch: {key}")
    lineups = _named_lineups(payload)
    headers = lineups["headers"]
    rows = [dict(zip(headers, row)) for row in lineups["rowSet"]]
    keys = [canonical_pair(row["GROUP_ID"]) for row in rows]
    sorted_keys = sorted(keys, key=lambda pair: (int(pair[0]), int(pair[1])))
    possession_by_key: dict[str, float] = {}
    zero_keys: list[list[str]] = []
    if request["measure"] == "Advanced":
        for key, row in zip(keys, rows):
            value = float(row["POSS"])
            possession_by_key[f"{key[0]}-{key[1]}"] = value
            if value == 0:
                zero_keys.append(list(key))
    return {
        "version": VERSION, "request_id": request["request_id"], "ordinal": request["ordinal"],
        "team_id": request["team_id"], "team_name": request["team_name"],
        "window": request["window"]["name"], "measure": request["measure"],
        "canonical_request_identity_sha256": identity_sha256(request),
        "raw_bytes": len(body), "raw_sha256": sha256_bytes(body),
        "canonical_json_sha256": sha256_bytes(canonical_json_bytes(payload)),
        "overall_row_count": diagnostics["overall_row_count"],
        "lineups_row_count": diagnostics["lineups_row_count"],
        "canonical_pair_count": len(keys), "canonical_pair_keys": [list(item) for item in sorted_keys],
        "duplicate_count": diagnostics["duplicate_canonical_pair_count"],
        "malformed_pair_count": diagnostics["malformed_group_identifier_count"],
        "same_player_count": diagnostics["same_player_pair_count"],
        "invalid_player_id_count": diagnostics["invalid_player_id_count"],
        "row_width_error_count": diagnostics["row_width_error_count"],
        "observed_result_set_order": diagnostics["observed_result_set_order"],
        "possession_by_pair_key": possession_by_key,
        "zero_possession_pair_keys": sorted(zero_keys, key=lambda pair: (int(pair[0]), int(pair[1]))),
        "exact_250": diagnostics["exact_250"], "authenticated": True,
        "structurally_valid": True,
    }


def classify_request_state(
    evidence_root: Path, request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]],
) -> str:
    paths = request_paths(evidence_root, request)
    directory = paths["start"].parent
    if not directory.exists():
        return "not_started"
    if not directory.is_dir() or directory.is_symlink():
        return "conflicting_state"
    if any(not item.is_file() or item.is_symlink() or item.name not in STATE_FILES.values() for item in directory.iterdir()):
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
    if not isinstance(start, dict) or not _record_matches(start, request):
        return "conflicting_state"
    if "outcome" not in present:
        return "started_without_outcome"
    try:
        outcome = _read_json(paths["outcome"])
    except Exception:
        return "conflicting_state"
    if not isinstance(outcome, dict) or not _record_matches(outcome, request):
        return "conflicting_state"
    if outcome.get("state") == "failed_or_quarantined":
        allowed = {"start", "outcome", "quarantine"} | ({"response"} if "response" in present else set())
        return "failed_or_quarantined" if present == allowed else "conflicting_state"
    if outcome.get("state") != "completed_verified" or present != {
        "start", "response", "outcome", "verification", "verified_body"
    }:
        return "conflicting_state"
    try:
        body = paths["response"].read_bytes()
        verification = _read_json(paths["verification"])
        actual = verify_response_bytes(body, request, frozen)
        if paths["verified_body"].read_bytes() != body or verification != actual:
            return "conflicting_state"
    except Exception:
        return "conflicting_state"
    expected = {
        "http_status": 200, "redirect_count": 0, "automatic_retries": 0,
        "raw_sha256": actual["raw_sha256"],
        "canonical_json_sha256": actual["canonical_json_sha256"],
        "row_count": actual["lineups_row_count"], "byte_count": actual["raw_bytes"],
    }
    if not all(outcome.get(key) == value for key, value in expected.items()):
        return "conflicting_state"
    start_gap = start.get("observed_post_sleep_monotonic_gap_seconds")
    previous = start.get("previous_monotonic_completion")
    if previous is not None and (not isinstance(start_gap, (int, float)) or start_gap < MINIMUM_PACING_SECONDS):
        return "conflicting_state"
    return "completed_verified"


def create_session() -> requests.Session:
    retry = Retry(total=0, connect=0, read=0, redirect=0, status=0)
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _write_quarantine(
    paths: Mapping[str, Path], request: Mapping[str, Any], reason: str,
    diagnostics: Mapping[str, Any] | None = None,
) -> None:
    _write_once(paths["quarantine"], serialize_json({
        "version": VERSION, "request_id": request["request_id"], "ordinal": request["ordinal"],
        "canonical_request_identity_sha256": identity_sha256(request), "attempt_number": 1,
        "state": "failed_or_quarantined", "reason": reason,
        "diagnostics": dict(diagnostics or {}),
    }))


def acquire_one(
    request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]], evidence_root: Path,
    session: requests.Session, *, previous_completion: float | None,
    sleeper: Callable[[float], None] = time.sleep, monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    validate_request_identity(request, frozen)
    state = classify_request_state(evidence_root, request, frozen)
    if state == "completed_verified":
        return {"action": "skipped_completed_verified", "request_id": request["request_id"]}
    if state != "not_started":
        raise RecoveryError(f"request state blocks transport: {state}")
    before_sleep = monotonic()
    pre_gap = None if previous_completion is None else before_sleep - previous_completion
    requested_sleep = 0.0
    if previous_completion is not None and pre_gap < MINIMUM_PACING_SECONDS:
        requested_sleep = MINIMUM_PACING_SECONDS - pre_gap
        sleeper(requested_sleep)
    started_mono = monotonic()
    observed_gap = None if previous_completion is None else started_mono - previous_completion
    if observed_gap is not None and observed_gap < MINIMUM_PACING_SECONDS:
        raise RecoveryError("persisted monotonic pacing interval below 1.000000 seconds")
    paths = request_paths(evidence_root, request)
    start = {
        "version": VERSION, "request_id": request["request_id"], "ordinal": request["ordinal"],
        "canonical_request_identity_sha256": identity_sha256(request), "attempt_number": 1,
        "utc_start": utc_now(), "process_monotonic_start": started_mono,
        "previous_monotonic_completion": previous_completion,
        "required_minimum_gap_seconds": MINIMUM_PACING_SECONDS,
        "calculated_pre_attempt_gap_seconds": pre_gap,
        "requested_sleep_duration_seconds": requested_sleep,
        "observed_post_sleep_monotonic_gap_seconds": observed_gap,
        "pacing_disposition": "first_request_not_applicable" if previous_completion is None else "satisfied",
        "enforcement_clock": "time.monotonic", "utc_role": "audit_context_only",
    }
    _write_once(paths["start"], serialize_json(start))
    response: requests.Response | None = None
    try:
        response = session.get(
            URL, params=dict(request["parameters"]), timeout=TIMEOUT_SECONDS, allow_redirects=False
        )
        body = response.content
        _write_once(paths["response"], body)
        redirected = bool(
            response.is_redirect or response.is_permanent_redirect or 300 <= response.status_code < 400
        )
        if redirected:
            raise ResponseError("redirect response prohibited")
        if response.status_code != 200:
            raise ResponseError(f"HTTP status {response.status_code}")
        verification = verify_response_bytes(body, request, frozen)
        _write_once(paths["verification"], serialize_json(verification))
        _write_once(paths["verified_body"], body)
        completed_mono = monotonic()
        outcome = {
            "version": VERSION, "request_id": request["request_id"], "ordinal": request["ordinal"],
            "canonical_request_identity_sha256": identity_sha256(request), "attempt_number": 1,
            "utc_completion": utc_now(), "process_monotonic_completion": completed_mono,
            "state": "completed_verified", "http_status": 200, "redirect_count": 0,
            "automatic_retries": 0, "failure_reason": None,
            "row_count": verification["lineups_row_count"], "byte_count": len(body),
            "raw_sha256": verification["raw_sha256"],
            "canonical_json_sha256": verification["canonical_json_sha256"],
            "response_disposition": "completed_verified",
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        return {"action": "acquired", "request_id": request["request_id"], "outcome": outcome}
    except requests.RequestException as exc:
        reason = f"transport:{type(exc).__name__}"
        completed_mono = monotonic()
        outcome = {
            "version": VERSION, "request_id": request["request_id"], "ordinal": request["ordinal"],
            "canonical_request_identity_sha256": identity_sha256(request), "attempt_number": 1,
            "utc_completion": utc_now(), "process_monotonic_completion": completed_mono,
            "state": "failed_or_quarantined", "http_status": None, "redirect_count": 0,
            "automatic_retries": 0, "failure_reason": reason,
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        _write_quarantine(paths, request, reason)
        raise RecoveryError(reason) from exc
    except ResponseError as exc:
        body = b"" if response is None else response.content
        redirected = False if response is None else bool(
            response.is_redirect or response.is_permanent_redirect or 300 <= response.status_code < 400
        )
        completed_mono = monotonic()
        outcome = {
            "version": VERSION, "request_id": request["request_id"], "ordinal": request["ordinal"],
            "canonical_request_identity_sha256": identity_sha256(request), "attempt_number": 1,
            "utc_completion": utc_now(), "process_monotonic_completion": completed_mono,
            "state": "failed_or_quarantined", "http_status": None if response is None else response.status_code,
            "redirect_count": 1 if redirected else 0, "automatic_retries": 0,
            "failure_reason": str(exc), "byte_count": len(body),
            "raw_sha256": None if response is None else sha256_bytes(body),
        }
        _write_once(paths["outcome"], serialize_json(outcome))
        _write_quarantine(paths, request, str(exc), exc.diagnostics)
        raise RecoveryError(str(exc)) from exc


def _recovery_data(
    evidence_root: Path, request: Mapping[str, Any], frozen: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], set[tuple[str, str]]]:
    if classify_request_state(evidence_root, request, frozen) != "completed_verified":
        raise RecoveryError(f"recovery response not completed_verified: {request['request_id']}")
    verification = _read_json(request_paths(evidence_root, request)["verification"])
    return verification, {tuple(item) for item in verification["canonical_pair_keys"]}


def _full_season_path(spec: Mapping[str, Any]) -> Path:
    return Path(
        f"cache/phase3f-r2b.2/protected-final-target/{int(spec['ordinal']):02d}-"
        f"{spec['request_id'].split(':')[1]}-{spec['request_id'].split(':')[-1]}/verified-response.bin"
    )


def authenticate_full_season_bodies(project_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    root = Path(project_root).resolve()
    inventory = _read_json(root / "planning/phase3f-r2b.2/request_inventory.json")
    by_ordinal = {item["ordinal"]: item for item in inventory}
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for key, frozen_spec in FULL_SEASON_SPECS.items():
        spec = dict(frozen_spec)
        request = by_ordinal.get(spec["ordinal"])
        if not isinstance(request, dict) or request.get("request_id") != spec["request_id"]:
            raise RecoveryError("full-season request inventory linkage mismatch")
        directory = root / _full_season_path(spec).parent
        body_path = root / _full_season_path(spec)
        outcome = _read_json(directory / "attempt-1-outcome.json")
        verification_record = _read_json(directory / "verification.json")
        expected_fp = {"bytes": spec["bytes"], "sha256": spec["raw_sha256"]}
        _assert_regular_file(body_path, expected_fp, "full-season verified body")
        if (
            outcome.get("state") != "completed_verified" or outcome.get("attempt_number") != 1
            or outcome.get("row_count") != 250 or outcome.get("raw_sha256") != spec["raw_sha256"]
            or outcome.get("canonical_json_sha256") != spec["canonical_json_sha256"]
            or verification_record.get("canonical_json_sha256") != spec["canonical_json_sha256"]
        ):
            raise RecoveryError("full-season metadata authentication mismatch")
        body = body_path.read_bytes()
        try:
            diagnostics = validate_response_contract(body, request)
            payload = strict_json_bytes(body)
        except (ContractError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise RecoveryError(f"full-season corrected-contract failure: {exc}") from exc
        canonical = sha256_bytes(canonical_json_bytes(payload))
        if canonical != spec["canonical_json_sha256"] or diagnostics["lineups_row_count"] != 250:
            raise RecoveryError("full-season body canonical identity mismatch")
        lineups = _named_lineups(payload)
        rows = [dict(zip(lineups["headers"], row)) for row in lineups["rowSet"]]
        keys = [canonical_pair(row["GROUP_ID"]) for row in rows]
        output[key] = {
            **spec, "path": _full_season_path(spec).as_posix(), "state": "completed_verified",
            "row_count": len(rows), "keys": set(keys), "diagnostics": diagnostics,
        }
    return output


def _pair_list(values: set[tuple[str, str]]) -> list[list[str]]:
    return [list(value) for value in sorted(values, key=lambda pair: (int(pair[0]), int(pair[1])))]


def reconcile_populations(
    project_root: Path, evidence_root: Path, requests_value: Sequence[Mapping[str, Any]],
    frozen: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    states = [classify_request_state(evidence_root, item, frozen) for item in requests_value]
    if states != ["completed_verified"] * 8:
        raise RecoveryError(f"all eight responses must verify before reconciliation: {states}")
    full = authenticate_full_season_bodies(project_root)
    recovery: dict[tuple[str, str, str], tuple[dict[str, Any], set[tuple[str, str]]]] = {}
    for request in requests_value:
        recovery[(request["team_id"], request["window"]["name"], request["measure"])] = _recovery_data(
            evidence_root, request, frozen
        )
    teams = []
    dispositions = []
    for team_id, team_name in (("1610612754", "Indiana Pacers"), ("1610612763", "Memphis Grizzlies")):
        window_data: dict[str, Any] = {}
        aggregate_base_only: set[tuple[str, str]] = set()
        aggregate_advanced_only: set[tuple[str, str]] = set()
        window_union: set[tuple[str, str]] = set()
        zero_rows = []
        for window in ("early", "late"):
            base_v, base_keys = recovery[(team_id, window, "Base")]
            advanced_v, advanced_keys = recovery[(team_id, window, "Advanced")]
            base_only = base_keys - advanced_keys
            advanced_only = advanced_keys - base_keys
            aggregate_base_only |= base_only
            aggregate_advanced_only |= advanced_only
            window_union |= base_keys | advanced_keys
            zero_rows.extend({"window": window, "key": key} for key in advanced_v["zero_possession_pair_keys"])
            window_data[window] = {
                "base_count": base_v["lineups_row_count"],
                "advanced_count": advanced_v["lineups_row_count"],
                "base_advanced_keys_equal": not base_only and not advanced_only,
                "base_only_keys": _pair_list(base_only), "advanced_only_keys": _pair_list(advanced_only),
                "zero_possession_pair_keys": advanced_v["zero_possession_pair_keys"],
            }
        full_base = full[(team_id, "Base")]
        full_advanced = full[(team_id, "Advanced")]
        full_base_only = full_base["keys"] - full_advanced["keys"]
        full_advanced_only = full_advanced["keys"] - full_base["keys"]
        aggregate_base_only |= full_base_only
        aggregate_advanced_only |= full_advanced_only
        full_keys = full_base["keys"] | full_advanced["keys"]
        recovered_only = window_union - full_keys
        full_only = full_keys - window_union
        exposure = []
        for key in sorted(recovered_only, key=lambda pair: (int(pair[0]), int(pair[1]))):
            text = f"{key[0]}-{key[1]}"
            early_v = recovery[(team_id, "early", "Advanced")][0]
            late_v = recovery[(team_id, "late", "Advanced")][0]
            early_poss = float(early_v["possession_by_pair_key"].get(text, 0.0))
            late_poss = float(late_v["possession_by_pair_key"].get(text, 0.0))
            total = early_poss + late_poss
            exposure.append({
                "canonical_pair_key": list(key), "early_possessions": early_poss,
                "late_possessions": late_poss, "summed_possessions": total,
                "meets_poss_ge_150": total >= 150.0,
            })
        verifications = [recovery[(team_id, w, m)][0] for w in ("early", "late") for m in ("Base", "Advanced")]
        duplicate_count = sum(item["duplicate_count"] for item in verifications)
        malformed_count = sum(item["malformed_pair_count"] for item in verifications)
        same_player_count = sum(item["same_player_count"] for item in verifications)
        record = {
            "full_season_evidence_authenticated": True,
            "all_four_recovery_responses_present": True,
            "all_four_recovery_responses_authenticated": True,
            "all_four_recovery_responses_structurally_valid": True,
            "complete_complementary_date_coverage": True,
            "every_individual_window_below_250": all(item["lineups_row_count"] < 250 for item in verifications),
            "early_base_advanced_keys_equal": window_data["early"]["base_advanced_keys_equal"],
            "late_base_advanced_keys_equal": window_data["late"]["base_advanced_keys_equal"],
            "window_union_equals_full_season_keys": not recovered_only and not full_only,
            "recovered_only_keys_validated": not (
                duplicate_count or malformed_count or same_player_count or aggregate_base_only or aggregate_advanced_only
            ),
            "conflicting_state": False, "failed_or_quarantined": False,
            "early_base_pair_row_count": window_data["early"]["base_count"],
            "early_advanced_pair_row_count": window_data["early"]["advanced_count"],
            "late_base_pair_row_count": window_data["late"]["base_count"],
            "late_advanced_pair_row_count": window_data["late"]["advanced_count"],
            "recovered_only_count": len(recovered_only), "full_season_only_count": len(full_only),
            "duplicate_count": duplicate_count, "malformed_pair_count": malformed_count,
            "same_player_count": same_player_count,
            "base_only_count": len(aggregate_base_only),
            "advanced_only_count": len(aggregate_advanced_only),
        }
        decision = evaluate_disposition(record)
        reconciliation = {
            "team_id": team_id, "team_name": team_name,
            "full_season": {
                "base_count": len(full_base["keys"]), "advanced_count": len(full_advanced["keys"]),
                "base_advanced_keys_equal": not full_base_only and not full_advanced_only,
                "base_path": full_base["path"], "advanced_path": full_advanced["path"],
                "base_raw_sha256": full_base["raw_sha256"],
                "advanced_raw_sha256": full_advanced["raw_sha256"],
            },
            "windows": window_data, "window_union_count": len(window_union),
            "overlap_count": len(window_union & full_keys),
            "recovered_only_keys": _pair_list(recovered_only),
            "full_season_only_keys": _pair_list(full_only),
            "full_season_base_only_keys": _pair_list(full_base_only),
            "full_season_advanced_only_keys": _pair_list(full_advanced_only),
            "duplicate_count": duplicate_count, "malformed_count": malformed_count,
            "same_player_count": same_player_count,
            "base_only_count": len(aggregate_base_only),
            "advanced_only_count": len(aggregate_advanced_only),
            "zero_possession_rows": zero_rows,
            "every_individual_window_below_250": record["every_individual_window_below_250"],
            "exposure_diagnostics": exposure,
            "rating_aggregation_performed": False, "target_reconstruction_performed": False,
        }
        teams.append(reconciliation)
        dispositions.append({
            "team_id": team_id, "team_name": team_name, "schema_record": record,
            **decision.as_dict(),
        })
    return {"full_season": full, "team_reconciliation": teams, "team_dispositions": dispositions}


def _attempt_ledger(
    evidence_root: Path, requests_value: Sequence[Mapping[str, Any]], frozen: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output = []
    for request in requests_value:
        paths = request_paths(evidence_root, request)
        state = classify_request_state(evidence_root, request, frozen)
        item: dict[str, Any] = {
            "ordinal": request["ordinal"], "request_id": request["request_id"],
            "team_id": request["team_id"], "team_name": request["team_name"],
            "window": request["window"]["name"], "measure": request["measure"], "state": state,
            "records": {
                name: {"path": path.relative_to(evidence_root).as_posix(), **_fingerprint(path)}
                for name, path in paths.items() if path.exists()
            },
        }
        if paths["start"].exists():
            start = _read_json(paths["start"])
            item["start"] = {key: start.get(key) for key in (
                "utc_start", "process_monotonic_start", "previous_monotonic_completion",
                "required_minimum_gap_seconds", "calculated_pre_attempt_gap_seconds",
                "requested_sleep_duration_seconds", "observed_post_sleep_monotonic_gap_seconds",
                "pacing_disposition", "enforcement_clock", "utc_role",
            )}
        if paths["outcome"].exists():
            outcome = _read_json(paths["outcome"])
            item["outcome"] = {key: outcome.get(key) for key in (
                "attempt_number", "utc_completion", "process_monotonic_completion", "state",
                "http_status", "redirect_count", "automatic_retries", "failure_reason",
                "row_count", "byte_count", "raw_sha256", "canonical_json_sha256",
                "response_disposition",
            )}
        output.append(item)
    return output


def _preservation_after(project_root: Path, authorization: Mapping[str, Any]) -> list[dict[str, Any]]:
    authenticated = authenticate_frozen_inputs(project_root)
    output = authenticated["preservation_fingerprints"]
    if output != authorization["historical_namespace_fingerprints_before"]:
        raise RecoveryError("historical namespace changed during R2D")
    if authenticated["historical_git_visible"] != authorization["historical_git_visible_fingerprints"]:
        raise RecoveryError("historical Git-visible fingerprints changed during R2D")
    return output


def _write_final_artifacts(
    project_root: Path, planning_dir: Path, evidence_root: Path, authorization: Mapping[str, Any],
    requests_value: Sequence[Mapping[str, Any]], frozen: Sequence[Mapping[str, Any]],
    reconciliation: Mapping[str, Any],
) -> dict[str, Any]:
    planning = Path(planning_dir)
    ledger = _attempt_ledger(evidence_root, requests_value, frozen)
    verifications = [_read_json(request_paths(evidence_root, item)["verification"]) for item in requests_value]
    response_fingerprints = [{
        key: value[key] for key in (
            "ordinal", "request_id", "team_id", "team_name", "window", "measure",
            "lineups_row_count", "raw_bytes", "raw_sha256", "canonical_json_sha256",
            "exact_250", "zero_possession_pair_keys",
        )
    } for value in verifications]
    dispositions = reconciliation["team_dispositions"]
    unresolved = [item["team_name"] for item in dispositions if item["disposition"] == "recovery_unresolved"]
    classification = (
        "CONDITIONAL PASS — recovery acquisition complete but one or both teams remain unresolved"
        if unresolved else
        "PASS — Phase 3F-R2D exact-250 recovery acquisition and reconciliation complete; ready for read-only audit"
    )
    preservation_after = _preservation_after(project_root, authorization)
    readiness = {
        "version": VERSION,
        "scope": "Indiana/Memphis exact-250 evidence status only",
        "team_status": {item["team_name"]: item["disposition"] for item in dispositions},
        "blocked_teams": unresolved,
        "final_test_pipeline_ready": False,
        "final_test_population_constructed": False,
        "execution_authorized": False,
        "next_gate": "separate read-only Phase 3F-R2D audit",
    }
    summary = {
        "version": VERSION, "classification": classification,
        "authorization_sha256": _fingerprint(planning / "recovery_authorization.json")["sha256"],
        "import_canary_count": 1, "official_invocation_count": 1,
        "authorized_request_count": 8, "network_attempt_count": 8,
        "completed_verified_count": 8, "quarantine_count": 0,
        "team_dispositions": readiness["team_status"],
        "historical_namespace_fingerprints_before": authorization["historical_namespace_fingerprints_before"],
        "historical_namespace_fingerprints_after": preservation_after,
        "unauthorized_request_count": 0, "rating_aggregation_count": 0,
        "target_reconstruction_count": 0, "final_test_rows": 0,
        "estimator_prediction_metric_or_serialization_operations": 0,
        "next_step": "separate read-only audit only",
    }
    values = {
        "request_ledger.json": {
            "version": VERSION, "request_count": 8, "requests": ledger,
            "execution_records": {
                name: {"path": path.relative_to(evidence_root).as_posix(), **_fingerprint(path)}
                for name, path in execution_paths(evidence_root).items() if path.exists()
            },
        },
        "response_fingerprints.json": response_fingerprints,
        "team_reconciliation.json": reconciliation["team_reconciliation"],
        "team_dispositions.json": dispositions,
        "readiness_effect.json": readiness,
        "summary.json": summary,
    }
    for name, value in values.items():
        _write_once(planning / name, serialize_json(value))
    manifest_names = [name for name in OUTPUT_FILES if name != "artifact_hashes.json"]
    manifest = {
        "version": VERSION, "artifact_inventory": list(OUTPUT_FILES),
        "rule": "nonrecursive SHA-256 over the other seven listed artifacts; artifact_hashes.json excludes itself",
        "artifacts": {name: _fingerprint(planning / name) for name in manifest_names},
    }
    _write_once(planning / "artifact_hashes.json", serialize_json(manifest))
    return summary


def execution_paths(evidence_root: Path) -> dict[str, Path]:
    base = Path(evidence_root) / "execution"
    return {name: base / filename for name, filename in EXECUTION_FILES.items()}


def _invocation_start(
    evidence_root: Path, authorization_path: Path, authorization: Mapping[str, Any],
) -> dict[str, Any]:
    record = {
        "version": VERSION, "invocation_number": 1, "start_time_utc": utc_now(),
        "command_argv": authorization["official_command_argv"],
        "process_sys_argv": list(sys.argv),
        "working_directory": os.getcwd(), "python_executable": _python_identity(Path(sys.executable)),
        "pythonpath": os.environ.get("PYTHONPATH"), "authorization_path": str(authorization_path),
        "authorization_sha256": _fingerprint(authorization_path)["sha256"],
        "implementation_source": authorization["implementation_source"],
        "cli_source": authorization["cli_source"],
    }
    _write_once(execution_paths(evidence_root)["start"], serialize_json(record))
    return record


def _invocation_outcome(
    evidence_root: Path, *, exit_code: int, stdout: str, stderr: str,
) -> dict[str, Any]:
    record = {
        "version": VERSION, "invocation_number": 1, "end_time_utc": utc_now(),
        "exit_code": exit_code, "stdout": stdout, "stderr": stderr,
    }
    _write_once(execution_paths(evidence_root)["outcome"], serialize_json(record))
    return record


def execute_authorized_recovery(
    project_root: Path, authorization_path: Path, evidence_root: Path, planning_dir: Path,
    *, session_factory: Callable[[], requests.Session] = create_session,
    sleeper: Callable[[float], None] = time.sleep, monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    authorization_path = Path(authorization_path).resolve()
    evidence = Path(evidence_root).resolve()
    planning = Path(planning_dir).resolve()
    if execution_paths(evidence)["start"].exists() or execution_paths(evidence)["outcome"].exists():
        raise RecoveryError("official invocation already launched; a second launch is prohibited")
    authorization_body = authorization_path.read_bytes()
    authorization = strict_json_bytes(authorization_body)
    _invocation_start(evidence, authorization_path, authorization)
    success_stdout = ""
    try:
        requests_value = validate_authorization(authorization, root, evidence, planning)
        frozen = validate_frozen_requests(load_corrected_plan(root))
        states = [classify_request_state(evidence, item, frozen) for item in requests_value]
        blockers = [state for state in states if state not in {"not_started", "completed_verified"}]
        if blockers:
            raise RecoveryError(f"pre-transport restart state blocks execution: {blockers}")
        session = session_factory()
        attempts = []
        previous_completion: float | None = None
        try:
            for request, initial_state in zip(requests_value, states):
                if authorization_path.read_bytes() != authorization_body:
                    raise RecoveryError("authorization changed during execution")
                validate_request_identity(request, frozen)
                if initial_state == "completed_verified":
                    attempts.append({"action": "skipped_completed_verified", "request_id": request["request_id"]})
                    previous_completion = _read_json(request_paths(evidence, request)["outcome"])[
                        "process_monotonic_completion"
                    ]
                    continue
                result = acquire_one(
                    request, frozen, evidence, session, previous_completion=previous_completion,
                    sleeper=sleeper, monotonic=monotonic,
                )
                attempts.append(result)
                previous_completion = result["outcome"]["process_monotonic_completion"]
        finally:
            session.close()
        if len([item for item in attempts if item["action"] == "acquired"]) != 8:
            raise RecoveryError("official launch did not make exactly eight first attempts")
        reconciliation = reconcile_populations(root, evidence, requests_value, frozen)
        dispositions = {item["team_name"]: item["disposition"] for item in reconciliation["team_dispositions"]}
        unresolved = any(value == "recovery_unresolved" for value in dispositions.values())
        success_stdout = (
            "CONDITIONAL PASS — recovery acquisition complete but one or both teams remain unresolved"
            if unresolved else
            "PASS — Phase 3F-R2D exact-250 recovery acquisition and reconciliation complete; ready for read-only audit"
        )
        summary = _write_final_artifacts(
            root, planning, evidence, authorization, requests_value, frozen, reconciliation
        )
        _invocation_outcome(evidence, exit_code=0, stdout=success_stdout + "\n", stderr="")
        return {"summary": summary, "attempts": attempts, "stdout": success_stdout}
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        if not execution_paths(evidence)["outcome"].exists():
            _invocation_outcome(evidence, exit_code=1, stdout="", stderr=message + "\n")
        raise


def verify_completed_checkpoint(
    project_root: Path, authorization_path: Path, evidence_root: Path, planning_dir: Path,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    authorization = _read_json(Path(authorization_path).resolve())
    requests_value = validate_authorization(
        authorization, root, Path(evidence_root).resolve(), Path(planning_dir).resolve()
    )
    frozen = validate_frozen_requests(load_corrected_plan(root))
    states = [classify_request_state(Path(evidence_root).resolve(), item, frozen) for item in requests_value]
    if states != ["completed_verified"] * 8:
        raise RecoveryError(f"checkpoint is not fully completed: {states}")
    planning = Path(planning_dir).resolve()
    if sorted(item.name for item in planning.iterdir()) != sorted(OUTPUT_FILES):
        raise RecoveryError("generated planning inventory mismatch")
    manifest = _read_json(planning / "artifact_hashes.json")
    if manifest.get("artifact_inventory") != list(OUTPUT_FILES):
        raise RecoveryError("generated manifest inventory mismatch")
    for name, expected in manifest.get("artifacts", {}).items():
        if _fingerprint(planning / name) != expected:
            raise RecoveryError(f"generated artifact hash mismatch: {name}")
    reconciliation = reconcile_populations(root, Path(evidence_root).resolve(), requests_value, frozen)
    recorded = _read_json(planning / "team_dispositions.json")
    if reconciliation["team_dispositions"] != recorded:
        raise RecoveryError("independent disposition replay mismatch")
    invocation = _read_json(execution_paths(Path(evidence_root).resolve())["outcome"])
    if invocation.get("invocation_number") != 1 or invocation.get("exit_code") != 0:
        raise RecoveryError("official invocation outcome is not successful")
    _preservation_after(root, authorization)
    return {
        "verified": True, "request_count": 8,
        "team_dispositions": {item["team_name"]: item["disposition"] for item in recorded},
        "network_requests": 0,
    }


def cache_only_replay(
    project_root: Path, authorization_path: Path, evidence_root: Path, planning_dir: Path,
) -> dict[str, Any]:
    """Read-only deterministic replay; never creates records or performs transport."""

    return verify_completed_checkpoint(project_root, authorization_path, evidence_root, planning_dir)
