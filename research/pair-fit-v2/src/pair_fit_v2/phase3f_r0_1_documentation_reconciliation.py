"""Build the append-only Phase 3F-R0.1 documentation reconciliation."""

from __future__ import annotations

import hashlib
import json
import math
import re
import socket
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping


VERSION = "phase3f-r0.1.documentation-reconciliation.v1"
PHASE_IDENTIFIER = "phase3f-r0.1"
RECONCILIATION_TYPE = "documentation_location_only"
REQUIRED_BRANCH = "research/pair-fit-v2"
REQUIRED_HEAD = "5d9e123c20d486b4401932ea656897a6791083fc"
REQUIRED_UPSTREAM = "origin/research/pair-fit-v2"
PROTECTED_SEASON = "2025-26"
ROOT_DICTIONARY_PATH = "DATA_DICTIONARY.md"
ROOT_DICTIONARY_SHA256 = "484c9a618076b3291756dcf47d551e50173a4394d6e43e0a826bcbe4c4a8582b"
ADDENDUM_PATH = "PHASE3F_R0_DATA_DICTIONARY_ADDENDUM.md"
ADDENDUM_BYTES = 7502
ADDENDUM_SHA256 = "f73bbf36568a86050339abfd304cd3726dab0bf63964e7f76e8271256b60db6a"
R0_POLICY_PATH = "PHASE3F_R0_FINAL_TEST_POLICY.md"
R0_POLICY_SHA256 = "c80fe6c31ba44b2e9e01f60e0943038004cf8584ea0ed7e1ed49e66138c02405"
R0_REPORT_PATH = "PHASE3F_R0_FINAL_TEST_FREEZE_REPORT.md"
R0_REPORT_SHA256 = "1a0cddef616e1be19e3b764264de5b4390fae61e7b9a926e9c92bc7e40168755"
R0_DIRECTORY = "curated/phase3f-r0"

R0_ARTIFACTS: tuple[dict[str, Any], ...] = (
    {
        "name": "expanded_training_staging.csv", "bytes": 62406352,
        "sha256": "3fced86922b533b0da2b42748d6c0b8afddef57b1281fe14880b11a446df21b6",
        "role": "expanded-training research and audit staging; not direct estimator input",
        "sensitivity_classification": "restricted_expanded_training_row_evidence",
    },
    {
        "name": "expanded_training_row_index.csv", "bytes": 2969425,
        "sha256": "3062b1524e7599dcab32ae1dc419040e7f16f6730308e3a88b18c71293d4c427",
        "role": "deterministic observation identity, ordering, alignment, target, history, and provenance",
        "sensitivity_classification": "restricted_expanded_training_row_evidence",
    },
    {
        "name": "expanded_training_estimator_matrix_unscaled.csv", "bytes": 14934011,
        "sha256": "a8a2b08daa3c56ccda78d34f77c2a29b7ef7c9e00835e7ab6ac77412ec6f8588",
        "role": "unscaled 29701-by-45 frozen estimator-feature matrix",
        "sensitivity_classification": "restricted_estimator_input",
    },
    {
        "name": "expanded_feature_manifest.json", "bytes": 1924,
        "sha256": "93693a520151387f0c9fb514ada7324639387a7ae60bae5bba9d2a607a5beb14",
        "role": "exact ordered 45-feature contract",
        "sensitivity_classification": "configuration_metadata",
    },
    {
        "name": "expanded_preprocessing_state.json", "bytes": 13011,
        "sha256": "a0180d9fc0436515f8a6f302727b4c0b030274cfbcce1a5ded7883568f05f47e",
        "role": "expanded-training-only medians, fills, scaler state, and scaling safeguards",
        "sensitivity_classification": "restricted_learned_preprocessing_state",
    },
    {
        "name": "population_diagnostics.json", "bytes": 1446,
        "sha256": "a1d16291d10352aba4afced0d2d6cfc272c04acf1266f702b3ada1e866589d8c",
        "role": "population, provenance, exclusion, history, symmetry, and safety diagnostics",
        "sensitivity_classification": "aggregate_research_metadata",
    },
    {
        "name": "input_fingerprints.json", "bytes": 6175,
        "sha256": "04caeba6a0872fac6fad3d7a8aaa3861dbc484228c6d3b8ddb3e24a1a1819428",
        "role": "permitted R0 input fingerprints and nonmutation assertions",
        "sensitivity_classification": "integrity_metadata",
    },
    {
        "name": "final_test_policy.json", "bytes": 13107,
        "sha256": "a3e5b7271b45b0ff997fde81d546bdd6d055a7177f44d31b41924beca8bb7e48",
        "role": "machine-readable frozen future final-test contract",
        "sensitivity_classification": "protected_policy_metadata",
    },
    {
        "name": "artifact_hashes.json", "bytes": 2338,
        "sha256": "802a14a978d937a07bf0cbeb1b93fa177b2904ef3e611f47d31a1ac3bbadf4e1",
        "role": "nonrecursive R0 payload hash manifest",
        "sensitivity_classification": "integrity_metadata",
    },
    {
        "name": "summary.json", "bytes": 1328,
        "sha256": "f2475571a32af96a6c802d90d5fa8f20fcfc2f7b0d9e27f2ce1cad1c88407b41",
        "role": "deterministic R0 construction summary and negative safety assertions",
        "sensitivity_classification": "aggregate_summary_metadata",
    },
)
R0_ARTIFACT_NAMES = tuple(item["name"] for item in R0_ARTIFACTS)

R01_PAYLOAD_ARTIFACTS = (
    "documentation_reconciliation.json",
    "referenced_r0_artifacts.json",
)
R01_BOOKKEEPING_ARTIFACTS = ("artifact_hashes.json", "summary.json")
R01_ARTIFACTS = R01_PAYLOAD_ARTIFACTS + R01_BOOKKEEPING_ARTIFACTS

PERMITTED_GIT_VISIBLE_PATHS = frozenset(
    {
        "PHASE3F_R0_DATA_DICTIONARY_ADDENDUM.md",
        "PHASE3F_R0_FINAL_TEST_FREEZE_REPORT.md",
        "PHASE3F_R0_FINAL_TEST_POLICY.md",
        "PHASE3F_R0_1_DOCUMENTATION_RECONCILIATION_REPORT.md",
        "src/pair_fit_v2/phase3f_r0_cli.py",
        "src/pair_fit_v2/phase3f_r0_final_test_freeze.py",
        "src/pair_fit_v2/phase3f_r0_1_cli.py",
        "src/pair_fit_v2/phase3f_r0_1_documentation_reconciliation.py",
        "tests/test_phase3f_r0_final_test_freeze.py",
        "tests/test_phase3f_r0_1_documentation_reconciliation.py",
    }
)

R3_EVIDENCE_SHA256 = {
    "MODELSPEC.md": "fc92326279f69db3f6682e7f414d436596e92d2faec37337b337514aeb73ab54",
    "DATA_DICTIONARY.md": ROOT_DICTIONARY_SHA256,
    "PHASE3E_R3_EVALUATION_POLICY.md": "47d123fd4862522665d2f8b202795a1aeb00360ff202236d49e35715fbbfa683",
    "src/pair_fit_v2/phase3e_r3_evaluation_policy.py": "2c857b4511826751fbedbec808b8555d78c4d86ccc3bad31c14ce9ca28fe1158",
    "tests/test_phase3e_r3_evaluation_policy.py": "d5755341be5cd9ccc60e454a9dcf11d03813da715c05d7c4ba6878f477ee229c",
    "modeling/phase3e-r3/evaluation_policy.json": "f5d1e8852693b74d4e82ae505e9d355526a3ddaedc7fbb7ffc7282db3f48ee48",
}

INVENTORY_START = "<!-- PHASE3F_R0_ARTIFACT_INVENTORY_START -->"
INVENTORY_END = "<!-- PHASE3F_R0_ARTIFACT_INVENTORY_END -->"


class ReconciliationError(RuntimeError):
    """Raised when an append-only reconciliation invariant fails."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def canonical_content_hash(value: Mapping[str, Any]) -> str:
    document = dict(value)
    document.pop("deterministic_content_sha256", None)
    return sha256_bytes(canonical_json_bytes(document))


def _identity_text(value: Any) -> str:
    return str(value).replace("\\", "/").lower()


def reject_protected_path(path: Path | str) -> None:
    if PROTECTED_SEASON in _identity_text(path):
        raise ReconciliationError(f"protected-season path rejected before access: {path}")


def reject_protected_label(value: Any) -> None:
    if PROTECTED_SEASON in _identity_text(value):
        raise ReconciliationError("protected-season label rejected")


def reject_protected_request_identity(parameters: Mapping[str, Any]) -> None:
    for key, value in parameters.items():
        if PROTECTED_SEASON in _identity_text(key) or PROTECTED_SEASON in _identity_text(value):
            raise ReconciliationError("protected-season request identity rejected")


def reject_protected_payload_identity(payload: Mapping[str, Any]) -> None:
    identity_keys = {
        "season", "season_id", "seasonlabel", "relative_path", "request_url",
        "request_identity", "asset_id", "cache_path", "body_path",
    }

    def visit(value: Any, identity_context: bool = False) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                visit(child, identity_context or str(key).lower() in identity_keys)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child, identity_context)
        elif identity_context and PROTECTED_SEASON in _identity_text(value):
            raise ReconciliationError("protected-season payload identity rejected")

    visit(payload)


@contextmanager
def offline_scope():
    original_socket = socket.socket
    original_connection = socket.create_connection
    original_lookup = socket.getaddrinfo

    def blocked(*_args: Any, **_kwargs: Any) -> None:
        raise ReconciliationError("network access is prohibited during Phase 3F-R0.1")

    socket.socket = blocked  # type: ignore[assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    socket.getaddrinfo = blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_connection  # type: ignore[assignment]
        socket.getaddrinfo = original_lookup  # type: ignore[assignment]


def read_bytes(path: Path) -> bytes:
    reject_protected_path(path)
    return path.read_bytes()


def sha256_file(path: Path) -> str:
    return sha256_bytes(read_bytes(path))


def _require_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise ReconciliationError(f"required file missing: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise ReconciliationError(f"byte hash mismatch for {path}: expected {expected}, got {actual}")


def _inventory_from_markdown(path: Path) -> tuple[str, ...]:
    text = read_bytes(path).decode("utf-8")
    if text.count(INVENTORY_START) != 1 or text.count(INVENTORY_END) != 1:
        raise ReconciliationError(f"authoritative inventory markers invalid: {path}")
    block = text.split(INVENTORY_START, 1)[1].split(INVENTORY_END, 1)[0]
    names = tuple(re.findall(r"(?:^|\n)(?:\|\s*|\s*\d+\.\s*)`([^`]+)`", block))
    if names != R0_ARTIFACT_NAMES or any(block.count(f"`{name}`") != 1 for name in R0_ARTIFACT_NAMES):
        raise ReconciliationError(f"authoritative R0 inventory mismatch: {path}")
    return names


def validate_documentation(project_root: Path) -> dict[str, dict[str, Any]]:
    documents = {
        ROOT_DICTIONARY_PATH: ROOT_DICTIONARY_SHA256,
        ADDENDUM_PATH: ADDENDUM_SHA256,
        R0_POLICY_PATH: R0_POLICY_SHA256,
        R0_REPORT_PATH: R0_REPORT_SHA256,
    }
    for relative, expected in documents.items():
        _require_hash(project_root / relative, expected)
    addendum = project_root / ADDENDUM_PATH
    if addendum.stat().st_size != ADDENDUM_BYTES:
        raise ReconciliationError("addendum byte count mismatch")
    for relative in (ADDENDUM_PATH, R0_POLICY_PATH, R0_REPORT_PATH):
        _inventory_from_markdown(project_root / relative)
    addendum_text = read_bytes(addendum).decode("utf-8")
    required_phrases = (
        "supplements the committed root", "does not replace, modify, supersede, or reinterpret",
        "waived only as to documentation location", "No data, schema, leakage, provenance, determinism, safety",
        "references and reconciliation metadata only", "must not be committed",
    )
    if any(phrase not in addendum_text for phrase in required_phrases):
        raise ReconciliationError("addendum documentation contract incomplete")
    return {
        relative: {
            "relative_path": relative,
            "bytes": (project_root / relative).stat().st_size,
            "sha256": sha256_file(project_root / relative),
        }
        for relative in documents
    }


def validate_r3_evidence(project_root: Path) -> dict[str, str]:
    for relative, expected in R3_EVIDENCE_SHA256.items():
        _require_hash(project_root / relative, expected)
    return dict(R3_EVIDENCE_SHA256)


def validate_git_state(project_root: Path) -> None:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=project_root, check=False, capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode != 0:
            raise ReconciliationError(f"Git preflight failed: {' '.join(args)}: {result.stderr.strip()}")
        return result.stdout.strip()

    if git("branch", "--show-current") != REQUIRED_BRANCH:
        raise ReconciliationError("unexpected branch")
    if git("rev-parse", "HEAD") != REQUIRED_HEAD:
        raise ReconciliationError("unexpected committed HEAD")
    if git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}") != REQUIRED_UPSTREAM:
        raise ReconciliationError("unexpected upstream")
    if git("rev-list", "--left-right", "--count", "HEAD...@{upstream}") != "0\t0":
        raise ReconciliationError("HEAD and upstream differ")
    lines = git("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    if any(not line.startswith("?? ") for line in lines):
        raise ReconciliationError("tracked or staged working-tree change is prohibited")
    repository_root = Path(git("rev-parse", "--show-toplevel")).resolve()
    try:
        project_prefix = project_root.relative_to(repository_root).as_posix().rstrip("/") + "/"
    except ValueError as exc:
        raise ReconciliationError("project root is outside the Git repository") from exc
    repository_visible = {line[3:].replace("\\", "/") for line in lines}
    if any(not path.startswith(project_prefix) for path in repository_visible):
        raise ReconciliationError("Git-visible change exists outside the Phase 3F project")
    visible = {path[len(project_prefix):] for path in repository_visible}
    if visible != PERMITTED_GIT_VISIBLE_PATHS:
        raise ReconciliationError(
            f"Git-visible path mismatch: missing={sorted(PERMITTED_GIT_VISIBLE_PATHS - visible)}, "
            f"extra={sorted(visible - PERMITTED_GIT_VISIBLE_PATHS)}"
        )


def fingerprint_r0(project_root: Path) -> dict[str, Any]:
    directory = project_root / R0_DIRECTORY
    reject_protected_path(directory)
    if not directory.is_dir():
        raise ReconciliationError("original R0 directory missing")
    actual_names = tuple(sorted(path.name for path in directory.iterdir() if path.is_file()))
    expected_names = tuple(sorted(R0_ARTIFACT_NAMES))
    if actual_names != expected_names or len(list(directory.iterdir())) != len(R0_ARTIFACT_NAMES):
        raise ReconciliationError("original R0 inventory mismatch")
    expected_by_name = {item["name"]: item for item in R0_ARTIFACTS}
    entries = []
    for name in actual_names:
        path = directory / name
        stat = path.stat()
        expected = expected_by_name[name]
        actual_hash = sha256_file(path)
        if stat.st_size != expected["bytes"] or actual_hash != expected["sha256"]:
            raise ReconciliationError(f"original R0 artifact mismatch: {name}")
        entries.append(
            {
                "relative_path": f"{R0_DIRECTORY}/{name}",
                "bytes": stat.st_size,
                "sha256": actual_hash,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    fingerprint = {"artifact_count": len(entries), "entries": entries}
    fingerprint["fingerprint_sha256"] = sha256_bytes(canonical_json_bytes(fingerprint))
    return fingerprint


def referenced_r0_document(fingerprint: Mapping[str, Any]) -> dict[str, Any]:
    observed = {Path(entry["relative_path"]).name: entry for entry in fingerprint["entries"]}
    artifacts = []
    for expected in R0_ARTIFACTS:
        entry = observed[expected["name"]]
        artifacts.append(
            {
                "relative_path": entry["relative_path"],
                "bytes": entry["bytes"],
                "sha256": entry["sha256"],
                "role": expected["role"],
                "sensitivity_classification": expected["sensitivity_classification"],
                "remains_in_original_namespace": True,
                "reference_mode": "referenced_not_copied",
            }
        )
    document = {
        "version": VERSION,
        "phase_identifier": PHASE_IDENTIFIER,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    document["deterministic_content_sha256"] = canonical_content_hash(document)
    return document


def _write_once(path: Path, data: bytes) -> dict[str, Any]:
    if path.exists():
        raise ReconciliationError(f"write-once refusal: path already exists: {path}")
    path.write_bytes(data)
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def build(
    project_root: Path | str = ".",
    output_dir: Path | str = "curated/phase3f-r0.1",
    *,
    enforce_git_state: bool = True,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    reject_protected_path(project_root)
    reject_protected_path(output_dir)
    if output_dir.exists():
        raise ReconciliationError(f"write-once restart refusal: R0.1 namespace exists: {output_dir}")

    with offline_scope():
        if enforce_git_state:
            validate_git_state(project_root)
        documentation = validate_documentation(project_root)
        r3_evidence = validate_r3_evidence(project_root)
        before = fingerprint_r0(project_root)
        referenced = referenced_r0_document(before)

        output_dir.mkdir(parents=True, exist_ok=False)
        referenced_info = _write_once(
            output_dir / "referenced_r0_artifacts.json", serialize_json(referenced)
        )
        after_reference_write = fingerprint_r0(project_root)
        if after_reference_write != before:
            raise ReconciliationError("original R0 changed during R0.1 construction")

        reconciliation = {
            "version": VERSION,
            "phase_identifier": PHASE_IDENTIFIER,
            "reconciliation_type": RECONCILIATION_TYPE,
            "committed_head": REQUIRED_HEAD,
            "branch": REQUIRED_BRANCH,
            "root_dictionary": documentation[ROOT_DICTIONARY_PATH],
            "data_dictionary_addendum": documentation[ADDENDUM_PATH],
            "r0_human_contracts": {
                "policy": documentation[R0_POLICY_PATH],
                "report": documentation[R0_REPORT_PATH],
            },
            "conflict_reason": (
                "the root dictionary is byte-pinned Phase 3E-R3 evidence while the original R0 instruction "
                "also required continued mutation of that same file"
            ),
            "location_only_waiver": (
                "the R0 inventory is documented in the versioned Phase 3F addendum instead of mutating "
                "the historical root dictionary"
            ),
            "r3_evidence_hashes": r3_evidence,
            "r3_evidence_changed": False,
            "r0_generated_evidence_changed": False,
            "scientific_settings_changed": False,
            "protected_final_test_evidence_accessed": False,
            "estimator_constructed": False,
            "estimator_trained": False,
            "prediction_generated": False,
            "metric_generated": False,
            "network_access": False,
            "r0_directory_fingerprint_before": before,
            "r0_directory_fingerprint_after": after_reference_write,
            "r0_directory_fingerprints_equal": before == after_reference_write,
        }
        reconciliation["deterministic_content_sha256"] = canonical_content_hash(reconciliation)
        reconciliation_info = _write_once(
            output_dir / "documentation_reconciliation.json", serialize_json(reconciliation)
        )

        artifact_hashes = {
            "version": VERSION,
            "manifest_rule": "nonrecursive: hash exactly the two payload JSON files; exclude this manifest and summary.json",
            "artifact_inventory": list(R01_ARTIFACTS),
            "payload_artifacts": list(R01_PAYLOAD_ARTIFACTS),
            "excluded_from_own_manifest": list(R01_BOOKKEEPING_ARTIFACTS),
            "artifacts": {
                "documentation_reconciliation.json": reconciliation_info,
                "referenced_r0_artifacts.json": referenced_info,
            },
        }
        artifact_hashes["deterministic_content_sha256"] = canonical_content_hash(artifact_hashes)
        manifest_info = _write_once(output_dir / "artifact_hashes.json", serialize_json(artifact_hashes))

        summary = {
            "version": VERSION,
            "original_r0_status": "BLOCKED — documentation-contract conflict",
            "r0_1_status": "documentation reconciliation completed",
            "composite_checkpoint_status": "Phase 3F-R0 final-test pipeline frozen; ready for read-only audit",
            "original_r0_artifact_count": 10,
            "r0_1_artifact_count": 4,
            "expanded_training_rows": 29701,
            "historical_rows": 27001,
            "spent_development_rows": 2700,
            "feature_count": 45,
            "scientific_contract_unchanged": True,
            "root_dictionary_preserved": True,
            "protected_final_test_evidence_accessed": False,
            "estimator_constructed": False,
            "estimator_trained": False,
            "prediction_generated": False,
            "metric_generated": False,
            "network_access": False,
            "commit_performed": False,
            "push_performed": False,
            "artifact_inventory": list(R01_ARTIFACTS),
            "artifact_manifest_sha256": manifest_info["sha256"],
            "r0_directory_fingerprint_sha256": before["fingerprint_sha256"],
        }
        summary["deterministic_content_sha256"] = canonical_content_hash(summary)
        _write_once(output_dir / "summary.json", serialize_json(summary))

        final_fingerprint = fingerprint_r0(project_root)
        if final_fingerprint != before:
            raise ReconciliationError("original R0 changed during final R0.1 writes")
        actual_inventory = tuple(sorted(path.name for path in output_dir.iterdir()))
        if actual_inventory != tuple(sorted(R01_ARTIFACTS)) or len(list(output_dir.iterdir())) != 4:
            raise ReconciliationError("R0.1 generated inventory mismatch")
        for value in summary.values():
            if isinstance(value, float) and not math.isfinite(value):
                raise ReconciliationError("nonfinite summary value")
        return summary
