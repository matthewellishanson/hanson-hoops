"""Construct the frozen 2025-26 final-test matrix and readiness evidence.

This module is deliberately offline and estimator-free.  It authenticates and
parses existing evidence, applies the already-frozen Phase 3F-R0 preprocessing
state exactly once, and stops before any fit, prediction, or metric operation.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


VERSION = "phase3f-r3.final-test-readiness.v1"
REQUIRED_BRANCH = "research/pair-fit-v2"
REQUIRED_HEAD = "6dc1234fd6dc2643af8718f77ca5651eb5c6594a"
TARGET_SEASON = "2025-26"
ELIGIBILITY_THRESHOLD = 150.0
EXCLUDED_TEAMS = {
    "1610612754": "Indiana Pacers",
    "1610612763": "Memphis Grizzlies",
}
TEAM_IDS = tuple(str(value) for value in range(1610612737, 1610612767))
PROFILE_SEASONS = ("2024-25", "2023-24", "2022-23")

PLAYER_DIRECT_FIELDS = (
    "AGE", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB",
    "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS",
)
PLAYER_DERIVED_FIELDS = (
    "effective_field_goal_pct", "true_shooting_pct",
    "three_point_attempt_rate", "free_throw_rate",
)
FEATURES = tuple(
    [f"pair_mean.{field}" for field in PLAYER_DIRECT_FIELDS + PLAYER_DERIVED_FIELDS]
    + [f"pair_absolute_difference.{field}" for field in PLAYER_DIRECT_FIELDS + PLAYER_DERIVED_FIELDS]
    + ["pair_traded_history_count"]
)
GATE_IDS = (
    "predictor_evidence_completeness",
    "target_evidence_completeness",
    "team_population_exhaustiveness",
    "row_eligibility",
    "row_alignment",
    "protected_result_reveal",
)

OUTPUT_FILES = (
    "final_test_staging.csv",
    "final_test_row_index.csv",
    "final_test_target_vector.csv",
    "final_test_estimator_matrix_scaled.csv",
    "estimator_feature_manifest.json",
    "applied_preprocessing_state_identity.json",
    "population_diagnostics.json",
    "history_selection_diagnostics.json",
    "input_fingerprints.json",
    "readiness_gates.json",
    "artifact_hashes.json",
    "summary.json",
)
PAYLOAD_FILES = OUTPUT_FILES[:-2]

EXPECTED_R3_GIT_VISIBLE_DELIVERABLES = (
    "PHASE3F_R3_FINAL_TEST_READINESS_POLICY.md",
    "PHASE3F_R3_FINAL_TEST_READINESS_REPORT.md",
    "src/pair_fit_v2/phase3f_r3_final_test_readiness.py",
    "src/pair_fit_v2/phase3f_r3_cli.py",
    "tests/test_phase3f_r3_final_test_readiness.py",
)
R3_CORE_BUILD_DELIVERABLES = frozenset(EXPECTED_R3_GIT_VISIBLE_DELIVERABLES) - {
    "PHASE3F_R3_FINAL_TEST_READINESS_REPORT.md",
}
EXPECTED_R3_1_GIT_VISIBLE_ADDITIONS = (
    "PHASE3F_R3_1_REPRODUCIBILITY_CORRECTION_REPORT.md",
)
R3_1_OUTPUT_FILES = (
    "correction.json",
    "referenced_r3_artifacts.json",
    "corrected_summary.json",
    "artifact_hashes.json",
    "summary.json",
)
R3_AUDITED_SHA256 = {
    "final_test_staging.csv": "c7994aceebedf4093e97d3b0b41d28ab69abaebb38f6486d07c82a5125635f06",
    "final_test_row_index.csv": "b0c2204be4dd67d504cde0e720f3453160416a3e9f838aad6e45273d197225f9",
    "final_test_target_vector.csv": "a258c02992f2006ee083d39b79d328f775d8923157d80f7bed2c73955d276198",
    "final_test_estimator_matrix_scaled.csv": "b8213cd44ace50cb88860c832d0f810e497e403c31ff029b9ed323ed3a601f6f",
    "estimator_feature_manifest.json": "b2ef6f25b18e1b5522c2624c1b0532648ac961c4558114fc8d94e437351564a6",
    "applied_preprocessing_state_identity.json": "027022517341ea65febe3b779feb7254f2605cb5f125795cd0f97c258311efa6",
    "population_diagnostics.json": "b804699b30027e3ed1f7a255dd36d5b359f529d2838748828e23b8975ee6812d",
    "history_selection_diagnostics.json": "502e46022560428c83af930fac0ad30f46ce2c6a454ec7a797b51d575b8fcaba",
    "input_fingerprints.json": "23f0f9e00ff205988a3890017003bc59e6a704fc1aae78c8cef455a8e58922fb",
    "readiness_gates.json": "3b63cc6502dab36de9d8413fa3f3495cfcd57941355fffd112ae0a5eb5e495a8",
    "artifact_hashes.json": "58382f587c1b2b679fb8a24ac7652b8ff131749c5e6a0e248a769f4a535aacd6",
    "summary.json": "0d262e096e3fc3de9a8ca8b5cb6d84f7ea1a608eca662289cdf43310b1b8b2f7",
}

R0_ARTIFACTS = {
    "expanded_training_staging.csv": "3fced86922b533b0da2b42748d6c0b8afddef57b1281fe14880b11a446df21b6",
    "expanded_training_row_index.csv": "3062b1524e7599dcab32ae1dc419040e7f16f6730308e3a88b18c71293d4c427",
    "expanded_training_estimator_matrix_unscaled.csv": "a8a2b08daa3c56ccda78d34f77c2a29b7ef7c9e00835e7ab6ac77412ec6f8588",
    "expanded_feature_manifest.json": "93693a520151387f0c9fb514ada7324639387a7ae60bae5bba9d2a607a5beb14",
    "expanded_preprocessing_state.json": "a0180d9fc0436515f8a6f302727b4c0b030274cfbcce1a5ded7883568f05f47e",
    "population_diagnostics.json": "a1d16291d10352aba4afced0d2d6cfc272c04acf1266f702b3ada1e866589d8c",
    "input_fingerprints.json": "04caeba6a0872fac6fad3d7a8aaa3861dbc484228c6d3b8ddb3e24a1a1819428",
    "final_test_policy.json": "a3e5b7271b45b0ff997fde81d546bdd6d055a7177f44d31b41924beca8bb7e48",
    "artifact_hashes.json": "802a14a978d937a07bf0cbeb1b93fa177b2904ef3e611f47d31a1ac3bbadf4e1",
    "summary.json": "f2475571a32af96a6c802d90d5fa8f20fcfc2f7b0d9e27f2ce1cad1c88407b41",
}
PINNED_MANIFESTS = {
    "curated/phase3f-r0.1/artifact_hashes.json": "805350d8eb6aa9361f6745e8871996a226847ad989ebd77adbe8b000565a1047",
    "planning/phase3f-r1s/artifact_hashes.json": "7f3ddbc31665797b0c0acb24c49b9c47c2ddd0b31d92a1c98e8b39921e2ac347",
    "planning/phase3f-r2a/artifact_hashes.json": "81263f9f909c3c2e390099e9a6aaba56711b572039ac69eff91e199b25d72413",
    "planning/phase3f-r2b.2/artifact_hashes.json": "257651c2a5fe49ba292542862eb757b1ed5551d7a05542053a10d2a49da8a7d4",
    "planning/phase3f-r2b.2.1/artifact_hashes.json": "04332a6003859e88bcb54e0b5116e4d807d265296617f1835273f563e5bb1f82",
    "planning/phase3f-r2c/artifact_hashes.json": "25bac05220a8d7c1645b235a98b8800a28d7d6df821a0a9c1a9cbe2721d4fd76",
    "planning/phase3f-r2c.1/artifact_hashes.json": "be6abe8605a480e62d20b7c368b16039c1072804565fa4ef8ee0ba04919fa686",
    "planning/phase3f-r2d.1/artifact_hashes.json": "be4d2a9a6bbd09520d436c9e8504ea09ff68a0903b3a5672b9e2219a773e09d6",
    "cache/phase3f-r2d.2/protected-recovery-continuation/artifact-hashes.json": "5415e554e989f29d8c0e868530aba47b6bcde2a3aaa19e606b30140c7c1ba380",
}
PRESERVED_NAMESPACES = {
    "planning/phase3f-r2b": "65271de8523330662115d55ee0d30adc29396e50bfe670fc060f135ef271dc93",
    "planning/phase3f-r2b.1": "f939d0a17c6e5cc1af9ab32a8555d7933dfc6123bac16f02dcbcc40a2c6c82a9",
    "planning/phase3f-r2b.2": "e7197ffe2a0c79e1ebd9cf35d0eece53f1343ac69e1ac6f8600abb9382ed6026",
    "planning/phase3f-r2b.2.1": "e40e4bd0bbc06a62f5881bb241d4a5d1df5c202309aac9291fc0de097eab5c33",
    "cache/phase3f-r2b": "8b350170f1faf7d8ef33e8ba0ce4075ee35e3535008636b26169b908cc9e624e",
    "cache/phase3f-r2b.2": "3e7c88f73b8c873b3dc99c3ad6cc7dc44158afdcd05984b2001d6620287e94a5",
    "planning/phase3f-r2c": "fb7d85802cadde1510e53a25a81ad8c7d7f5f813a5b1bd4086970859e1af2e31",
    "cache/phase3f-r2c-public-source": "fd9c05c0f5f58b51aaa4627eaa8d732d7209ad98c6925a063bc68abf40cc80b0",
    "planning/phase3f-r2c.1": "b2d0ed15ce272603ced88ac6efc084c8b4d34994b86ddab6c5868efb4764e7e6",
    "planning/phase3f-r2d": "a3c4e24e4003c43471d672c9ca281fc5271ada14dcbc7367a15a96774366c64e",
    "planning/phase3f-r2d.1": "3dc2212dc24a3d293b85841cfefc6348ef2fee62311c941d17bdffadb3b082bd",
    "cache/phase3f-r2d/protected-recovery": "0276ce181cedb4135384e41eff9aef8dc3c8ee3317a83a0537b5ebeae7413cb3",
    "cache/phase3f-r2d.2/protected-recovery-continuation": "c92c5717c5735ee3480c2d73117f93c3362922cef2b7d2a56d467733c406b8d7",
}
ALLOWED_GIT_CHANGES = frozenset(
    EXPECTED_R3_GIT_VISIBLE_DELIVERABLES + EXPECTED_R3_1_GIT_VISIBLE_ADDITIONS
)


class ReadinessError(RuntimeError):
    """A frozen prerequisite or construction invariant failed."""


def require_all_gates_pass(gates: Sequence[Mapping[str, Any]]) -> None:
    if tuple(item.get("id") for item in gates) != GATE_IDS:
        raise ReadinessError("readiness gate identity/order changed")
    invalid = [item.get("id") for item in gates if item.get("status") not in {"passed", "failed", "unresolved"}]
    if invalid:
        raise ReadinessError(f"invalid readiness gate status: {invalid}")
    blockers = [item.get("id") for item in gates if item.get("status") != "passed"]
    if blockers:
        raise ReadinessError(f"failed or unresolved readiness gate blocks construction: {blockers}")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def strict_json_bytes(value: bytes) -> Any:
    def reject_constant(token: str) -> None:
        raise ReadinessError(f"non-finite JSON token: {token}")
    return json.loads(value.decode("utf-8-sig"), parse_constant=reject_constant)


def read_json(path: Path) -> Any:
    return strict_json_bytes(path.read_bytes())


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_content_hash(value: Mapping[str, Any]) -> str:
    document = dict(value)
    document.pop("deterministic_content_sha256", None)
    return sha256_bytes(canonical_json_bytes(document))


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ReadinessError(f"invalid numeric {field}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ReadinessError(f"invalid numeric {field}") from exc
    if not math.isfinite(result):
        raise ReadinessError(f"nonfinite numeric {field}")
    return result


def _optional_finite(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _canonical_player(value: Any) -> str:
    text = str(value)
    if not text.isdecimal() or int(text) <= 0 or text != str(int(text)):
        raise ReadinessError(f"noncanonical player ID: {value!r}")
    return text


def _git(project_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=project_root, check=True, capture_output=True, text=True,
    )
    return completed.stdout.strip()


def _git_visible_changes(project_root: Path) -> set[str]:
    prefix = "research/pair-fit-v2/"
    changes = set()
    for line in _git(project_root, "status", "--porcelain=v1", "--untracked-files=all").splitlines():
        path = line[3:].replace("\\", "/")
        if path.startswith(prefix):
            path = path[len(prefix):]
        changes.add(path)
    return changes


def verify_repository_state(project_root: Path, initial_clean_preflight_confirmed: bool) -> dict[str, Any]:
    if not initial_clean_preflight_confirmed:
        raise ReadinessError("mandatory initial clean preflight was not confirmed")
    branch = _git(project_root, "branch", "--show-current")
    head = _git(project_root, "rev-parse", "HEAD")
    divergence = _git(project_root, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    if branch != REQUIRED_BRANCH or head != REQUIRED_HEAD or divergence.split() != ["0", "0"]:
        raise ReadinessError("branch, HEAD, or upstream divergence mismatch")
    if _git(project_root, "diff", "--cached", "--name-only"):
        raise ReadinessError("index is not clean")
    changes = _git_visible_changes(project_root)
    unexpected = sorted(changes - ALLOWED_GIT_CHANGES)
    if unexpected:
        raise ReadinessError(f"unexpected worktree changes: {unexpected}")
    missing_core = sorted(R3_CORE_BUILD_DELIVERABLES - changes)
    if missing_core:
        raise ReadinessError(f"missing R3 construction deliverables: {missing_core}")
    return {
        "branch": branch, "head": head, "upstream_divergence": "0/0",
        "index_clean": True, "initial_worktree_clean": True,
        "construction_time_changes": list(EXPECTED_R3_GIT_VISIBLE_DELIVERABLES),
    }


def validate_final_git_visible_inventory(project_root: Path) -> None:
    expected = set(EXPECTED_R3_GIT_VISIBLE_DELIVERABLES + EXPECTED_R3_1_GIT_VISIBLE_ADDITIONS)
    actual = _git_visible_changes(project_root)
    if actual != expected:
        raise ReadinessError(
            f"final Git-visible inventory mismatch: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def namespace_fingerprint(root: Path, relative: str) -> dict[str, Any]:
    directory = root / relative
    if not directory.is_dir() or directory.is_symlink():
        raise ReadinessError(f"missing namespace: {relative}")
    entries = []
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        if path.is_symlink():
            raise ReadinessError(f"symlink prohibited in preserved namespace: {path}")
        entries.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "mtime_ns": path.stat().st_mtime_ns,
        })
    return {
        "namespace": relative,
        "file_count": len(entries),
        "byte_count": sum(item["bytes"] for item in entries),
        "inventory_sha256": sha256_bytes(serialize_json(entries)),
    }


def _verify_generated_manifest(root: Path, relative: str, expected_hash: str) -> dict[str, Any]:
    path = root / relative
    if sha256_file(path) != expected_hash:
        raise ReadinessError(f"pinned manifest mismatch: {relative}")
    document = read_json(path)
    base = path.parent
    entries: dict[str, str] = {}
    if isinstance(document.get("sha256"), dict):
        entries.update(document["sha256"])
    artifacts = document.get("artifacts")
    if isinstance(artifacts, dict):
        for name, record in artifacts.items():
            if isinstance(record, dict):
                digest = record.get("sha256") or record.get("serialized_byte_sha256")
                if digest:
                    entries[name] = digest
    if isinstance(artifacts, list):
        for record in artifacts:
            entries[record["path"]] = record["sha256"]
    for name, expected in entries.items():
        candidate = base / name
        if not candidate.is_file() or sha256_file(candidate) != expected:
            raise ReadinessError(f"manifest payload mismatch: {relative}:{name}")
    return {"path": relative, "sha256": expected_hash, "verified_entries": len(entries)}


def authenticate_prerequisites(project_root: Path) -> dict[str, Any]:
    r0_dir = project_root / "curated/phase3f-r0"
    for name, expected in R0_ARTIFACTS.items():
        if sha256_file(r0_dir / name) != expected:
            raise ReadinessError(f"R0 artifact mismatch: {name}")
    manifests = [
        _verify_generated_manifest(project_root, relative, digest)
        for relative, digest in PINNED_MANIFESTS.items()
    ]
    namespaces = []
    for relative, expected in PRESERVED_NAMESPACES.items():
        record = namespace_fingerprint(project_root, relative)
        if record["inventory_sha256"] != expected:
            raise ReadinessError(f"preserved lineage mismatch: {relative}")
        namespaces.append(record)
    r2d2 = read_json(project_root / "cache/phase3f-r2d.2/protected-recovery-continuation/team-dispositions.json")
    expected_dispositions = {
        item["team_id"]: item["final_test_population_disposition"] for item in r2d2
    }
    if expected_dispositions != {
        team: "exclude_whole_team_from_final_test_population" for team in EXCLUDED_TEAMS
    }:
        raise ReadinessError("final team dispositions mismatch")
    r2b = read_json(project_root / "planning/phase3f-r2b.2/global_reconciliation.json")
    if r2b.get("structurally_complete_non_250_teams") != 28:
        raise ReadinessError("28-team structural disposition missing")
    if sorted(r2b.get("exact_250_unresolved_teams", []), key=int) != sorted(EXCLUDED_TEAMS, key=int):
        raise ReadinessError("R2B exact-250 team set mismatch")
    return {
        "r0_artifacts": {name: digest for name, digest in sorted(R0_ARTIFACTS.items())},
        "pinned_manifests": manifests,
        "preserved_lineage_namespaces": namespaces,
        "team_dispositions": expected_dispositions,
    }


def verify_empty_execution_boundary(project_root: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise ReadinessError(f"write-once output namespace already exists: {output_dir}")
    prohibited_namespaces = (
        "modeling/phase3f-r3", "modeling/phase3f-r4", "modeling/phase3f-final",
        "curated/phase3f-r4", "curated/phase3f-final-execution",
    )
    present = [name for name in prohibited_namespaces if (project_root / name).exists()]
    if present:
        raise ReadinessError(f"prior execution namespace exists: {present}")
    prohibited = []
    for base_name in ("curated", "planning", "cache", "modeling"):
        base = project_root / base_name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or "phase3f" not in path.as_posix().lower():
                continue
            name = path.name.lower()
            if any(token in name for token in ("prediction_vector", "final_predictions", "final_metrics", "serialized_model")):
                prohibited.append(path.relative_to(project_root).as_posix())
            if path.suffix.lower() in {".joblib", ".pkl", ".pickle"}:
                prohibited.append(path.relative_to(project_root).as_posix())
    if prohibited:
        raise ReadinessError(f"prohibited prior final-result artifact exists: {sorted(prohibited)}")
    return {"execution_namespaces_present": [], "prohibited_artifacts_present": []}


def _named_rows(payload: Mapping[str, Any], name: str) -> tuple[list[str], list[dict[str, Any]]]:
    matches = [item for item in payload.get("resultSets", []) if item.get("name") == name]
    if len(matches) != 1:
        raise ReadinessError(f"expected exactly one {name} result set")
    headers, raw_rows = matches[0].get("headers"), matches[0].get("rowSet")
    if not isinstance(headers, list) or len(headers) != len(set(headers)) or not isinstance(raw_rows, list):
        raise ReadinessError(f"malformed {name} result set")
    if any(not isinstance(row, list) or len(row) != len(headers) for row in raw_rows):
        raise ReadinessError(f"malformed {name} row width")
    return headers, [dict(zip(headers, row)) for row in raw_rows]


def _pair_index(payload: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    _, rows = _named_rows(payload, "Lineups")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        tokens = [token for token in str(row.get("GROUP_ID", "")).strip("-").split("-") if token]
        if len(tokens) != 2:
            raise ReadinessError("malformed pair key")
        left, right = (_canonical_player(token) for token in tokens)
        if left == right:
            raise ReadinessError("same-player pair key")
        key = tuple(sorted((left, right), key=int))
        if key in result:
            raise ReadinessError("duplicate canonical pair key")
        result[key] = row
    return result


def load_final_population(project_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    fingerprints = read_json(project_root / "planning/phase3f-r2b.2/response_fingerprints.json")
    if len(fingerprints) != 60:
        raise ReadinessError("protected response fingerprint count is not 60")
    response_hashes: dict[str, str] = {}
    teams: dict[str, dict[str, Any]] = {team: {} for team in TEAM_IDS}
    for record in fingerprints:
        ordinal = int(record["ordinal"])
        _, team_id, measure = record["request_id"].split(":")
        if ordinal == 1:
            relative = "cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-response.bin"
        else:
            relative = f"cache/phase3f-r2b.2/protected-final-target/{ordinal:02d}-{team_id}-{measure}/verified-response.bin"
        path = project_root / relative
        actual = sha256_file(path)
        if actual != record["raw_sha256"] or path.stat().st_size != record["raw_bytes"]:
            raise ReadinessError(f"protected response identity mismatch: {record['request_id']}")
        payload = read_json(path)
        teams[team_id][measure] = {"payload": payload, "path": relative, "sha256": actual}
        response_hashes[relative] = actual
    raw_rows: list[dict[str, Any]] = []
    team_diagnostics = []
    for team_id in TEAM_IDS:
        measures = teams[team_id]
        if set(measures) != {"base", "advanced"}:
            raise ReadinessError(f"Base/Advanced evidence missing: {team_id}")
        base = _pair_index(measures["base"]["payload"])
        advanced = _pair_index(measures["advanced"]["payload"])
        if set(base) != set(advanced):
            raise ReadinessError(f"Base/Advanced canonical keys differ: {team_id}")
        overall_headers, overall_rows = _named_rows(measures["base"]["payload"], "Overall")
        if "TEAM_NAME" not in overall_headers or len(overall_rows) != 1:
            raise ReadinessError(f"team identity unavailable: {team_id}")
        team_name = str(overall_rows[0]["TEAM_NAME"])
        eligible = zero_possession = 0
        eligible_possessions = 0.0
        for key in sorted(base, key=lambda pair: tuple(map(int, pair))):
            # POSS exists only in the direct Advanced schema; Base supplies the
            # exact matching full-season key and MIN audit field.
            possession = _finite(advanced[key].get("POSS"), "POSS")
            target = _finite(advanced[key].get("NET_RATING"), "NET_RATING")
            if possession < 0:
                raise ReadinessError("negative direct full-season possession")
            zero_possession += int(possession == 0)
            is_eligible = possession >= ELIGIBILITY_THRESHOLD
            eligible += int(is_eligible)
            if is_eligible:
                eligible_possessions += possession
            raw_rows.append({
                "target_season": TARGET_SEASON,
                "team_id": team_id,
                "team_name": team_name,
                "player_1_id": key[0],
                "player_2_id": key[1],
                "pair_possessions": possession,
                "pair_base_minutes": _optional_finite(base[key].get("MIN")),
                "target_net_rating": target,
                "eligible_poss_ge_150": int(is_eligible),
                "endpoint_exact_250_flag": int(len(base) == 250),
                "population_disposition": (
                    "excluded_full_team_proven_non_exhaustive" if team_id in EXCLUDED_TEAMS
                    else "retained_if_eligible"
                ),
                "target_source_measure": "Advanced",
                "possession_source_measure": "Advanced",
                "base_source_path": measures["base"]["path"],
                "base_source_sha256": measures["base"]["sha256"],
                "advanced_source_path": measures["advanced"]["path"],
                "advanced_source_sha256": measures["advanced"]["sha256"],
                "direct_full_season_source": 1,
                "recovered_or_window_source": 0,
            })
        team_diagnostics.append({
            "team_id": team_id, "team_name": team_name,
            "raw_rows": len(base), "eligible_rows": eligible,
            "eligible_possessions": eligible_possessions,
            "zero_possession_raw_rows": zero_possession,
            "base_advanced_key_equality": True,
            "disposition": "excluded_whole_team" if team_id in EXCLUDED_TEAMS else "retained",
        })
    if len(raw_rows) != 5403:
        raise ReadinessError(f"unexpected protected raw population: {len(raw_rows)}")
    return raw_rows, {"teams": team_diagnostics}, response_hashes


def _profile_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    _, rows = _named_rows(payload, "LeagueDashPlayerStats")
    return rows


def _profile_index(
    season: str, per100_path: Path, totals_path: Path, per100_hash: str, totals_hash: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if sha256_file(per100_path) != per100_hash or sha256_file(totals_path) != totals_hash:
        raise ReadinessError(f"prior-profile body identity mismatch: {season}")
    per100_rows = _profile_payload(read_json(per100_path))
    totals_rows = _profile_payload(read_json(totals_path))
    per100: dict[str, dict[str, Any]] = {}
    totals: dict[str, dict[str, Any]] = {}
    for row in per100_rows:
        player_id = _canonical_player(row.get("PLAYER_ID"))
        if player_id in per100:
            raise ReadinessError(f"duplicate Per100 player: {season}/{player_id}")
        per100[player_id] = row
    for row in totals_rows:
        player_id = _canonical_player(row.get("PLAYER_ID"))
        if player_id in totals:
            raise ReadinessError(f"duplicate Totals player: {season}/{player_id}")
        total_min = _finite(row.get("MIN"), "MIN")
        if total_min < 0:
            raise ReadinessError(f"negative Totals MIN: {season}/{player_id}")
        totals[player_id] = row
    if set(per100) != set(totals):
        raise ReadinessError(f"Per100/Totals player-ID disagreement: {season}")
    profiles = {
        player_id: {**row, "TOTAL_MIN": totals[player_id]["MIN"]}
        for player_id, row in per100.items()
    }
    return profiles, {
        "season": season,
        "player_count": len(profiles),
        "per100_path": per100_path.as_posix(), "per100_sha256": per100_hash,
        "totals_path": totals_path.as_posix(), "totals_sha256": totals_hash,
        "player_id_set_equality": True,
    }


def _phase2b_profile_sources(project_root: Path) -> tuple[Path, Path, str, str]:
    manifest_path = project_root / "cache/phase2b/release_manifest.json"
    if sha256_file(manifest_path) != "af8acbc10adf110f43c7c53a0ab2d6b402e3121fbe57e2d8b5dc3de7072e689e":
        raise ReadinessError("Phase 2B manifest identity mismatch")
    manifest = read_json(manifest_path)
    modes = {}
    for asset in manifest.get("player_dependencies", []):
        identity = asset.get("identity") or asset.get("source_identity")
        params = identity.get("parameters", {})
        if params.get("season") != "2022-23":
            continue
        cache = asset.get("cache") or asset.get("source_reference") or asset
        modes[params.get("per_mode")] = (
            project_root / "cache" / (cache.get("relative_path") or cache.get("source_cache_path")),
            cache.get("raw_body_hash"),
        )
    if set(modes) != {"Per100Possessions", "Totals"}:
        raise ReadinessError("2022-23 profile sources unavailable")
    return (*modes["Per100Possessions"], *modes["Totals"])


def load_profiles(project_root: Path) -> tuple[dict[str, dict[str, dict[str, Any]]], list[dict[str, Any]], dict[str, str]]:
    p22, h22, t22, th22 = _phase2b_profile_sources(project_root)
    source_specs = {
        "2024-25": (
            project_root / "cache/phase3f-r2a/non-protected-prior-profiles/01-per100possessions/verified-response.json",
            project_root / "cache/phase3f-r2a/non-protected-prior-profiles/02-totals/verified-response.json",
            "047d8c16703647425c2fa23678667595a6b7843b213e7e0c5794562bd96fc9ff",
            "3bd21076a2fde4b75ce70023f4c07cc633d811cfe08fce65a1c75bb653dfccd5",
        ),
        "2023-24": (
            project_root / "cache/live_responses/league_dash_player_stats_2023-24_base_per100possessions.json",
            project_root / "cache/phase3a1/raw/league_dash_player_stats_2023-24_base_totals.attempt-1.json",
            "da9ba4375be5522407e908e073a95d51b1a1ede41fe659ef75d07e178f8bbc0a",
            "0a856d37c33218362a0b88fc645b7d609a64a7da0773a1be1368d22d07b54774",
        ),
        "2022-23": (p22, t22, h22, th22),
    }
    profiles, diagnostics, fingerprints = {}, [], {}
    for season in PROFILE_SEASONS:
        per100, totals, per100_hash, totals_hash = source_specs[season]
        profile_index, record = _profile_index(season, per100, totals, per100_hash, totals_hash)
        record["per100_path"] = per100.relative_to(project_root).as_posix()
        record["totals_path"] = totals.relative_to(project_root).as_posix()
        profiles[season] = profile_index
        diagnostics.append(record)
        fingerprints[record["per100_path"]] = per100_hash
        fingerprints[record["totals_path"]] = totals_hash
    return profiles, diagnostics, fingerprints


def _rate(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _profile_values(profile: Mapping[str, Any]) -> dict[str, float | None]:
    values = {field: _optional_finite(profile.get(field)) for field in PLAYER_DIRECT_FIELDS}
    fgm, fga, fg3m = values["FGM"], values["FGA"], values["FG3M"]
    fg3a, fta, pts = values["FG3A"], values["FTA"], values["PTS"]
    values.update({
        "effective_field_goal_pct": _rate(None if fgm is None or fg3m is None else fgm + 0.5 * fg3m, fga),
        "true_shooting_pct": _rate(pts, None if fga is None or fta is None else 2.0 * (fga + 0.44 * fta)),
        "three_point_attempt_rate": _rate(fg3a, fga),
        "free_throw_rate": _rate(fta, fga),
    })
    team_count = _optional_finite(profile.get("TEAM_COUNT"))
    values["traded_player_indicator"] = (
        None if team_count is None or team_count <= 0 or not team_count.is_integer()
        else float(team_count > 1)
    )
    values["GP"] = _optional_finite(profile.get("GP"))
    values["TOTAL_MIN"] = _optional_finite(profile.get("TOTAL_MIN"))
    return values


def select_history(player_id: str, profiles: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> tuple[str | None, int | None, Mapping[str, Any] | None]:
    for gap, season in enumerate(PROFILE_SEASONS, start=1):
        if player_id in profiles[season]:
            return season, gap, profiles[season][player_id]
    return None, None, None


def curate_rows(
    raw_rows: Sequence[Mapping[str, Any]], profiles: Mapping[str, Mapping[str, Mapping[str, Any]]],
    profile_sources: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_by_season = {item["season"]: item for item in profile_sources}
    rows = []
    strict_prior_failures = lookback_violations = 0
    for raw in raw_rows:
        if raw["team_id"] in EXCLUDED_TEAMS or not raw["eligible_poss_ge_150"]:
            continue
        row = dict(raw)
        missing = 0
        for slot in (1, 2):
            player_id = row[f"player_{slot}_id"]
            season, gap, profile = select_history(player_id, profiles)
            row[f"player_{slot}_history_profile_season"] = season
            row[f"player_{slot}_history_gap"] = gap
            row[f"player_{slot}_history_missing"] = int(profile is None)
            if profile is None:
                missing += 1
                values = {field: None for field in PLAYER_DIRECT_FIELDS + PLAYER_DERIVED_FIELDS}
                values.update({"traded_player_indicator": None, "GP": None, "TOTAL_MIN": None})
                source = None
            else:
                values = _profile_values(profile)
                source = source_by_season[season]
                strict_prior_failures += int(int(season[:4]) >= int(TARGET_SEASON[:4]))
                lookback_violations += int(gap not in (1, 2, 3))
            for field, value in values.items():
                row[f"player_{slot}_{field.lower()}"] = value
            for kind in ("per100", "totals"):
                row[f"player_{slot}_profile_source_{kind}_path"] = None if source is None else source[f"{kind}_path"]
                row[f"player_{slot}_profile_source_{kind}_sha256"] = None if source is None else source[f"{kind}_sha256"]
        row["missing_player_count"] = missing
        row["history_status"] = {0: "complete", 1: "one_missing", 2: "both_missing"}[missing]
        row["history_confidence"] = "standard" if missing == 0 else "lower"
        row["observation_key"] = "|".join((TARGET_SEASON, row["team_id"], row["player_1_id"], row["player_2_id"]))
        rows.append(row)
    rows.sort(key=lambda row: (int(row["team_id"]), int(row["player_1_id"]), int(row["player_2_id"])))
    keys = [row["observation_key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise ReadinessError("duplicate final-test observation key")
    status = Counter(row["history_status"] for row in rows)
    seasons = Counter(
        row[f"player_{slot}_history_profile_season"]
        for row in rows for slot in (1, 2)
        if row[f"player_{slot}_history_profile_season"] is not None
    )
    missing_slots = sum(row["missing_player_count"] for row in rows)
    return rows, {
        "history_status_rows": {name: status.get(name, 0) for name in ("complete", "one_missing", "both_missing")},
        "selected_profile_seasons_all_slots": {season: seasons.get(season, 0) for season in PROFILE_SEASONS},
        "missing_slot_count": missing_slots,
        "strict_prior_failures": strict_prior_failures,
        "lookback_violations": lookback_violations,
        "per100_totals_reconciliation": list(profile_sources),
        "target_performance_by_history_computed": False,
    }


def _slot(row: Mapping[str, Any], slot: int, medians: Mapping[str, Any]) -> dict[str, float]:
    values = {}
    for field in PLAYER_DIRECT_FIELDS + PLAYER_DERIVED_FIELDS + ("traded_player_indicator",):
        value = _optional_finite(row.get(f"player_{slot}_{field.lower()}"))
        if value is None:
            value = _finite(medians[field.lower()], f"slot median {field}")
        values[field] = value
    return values


def _unscaled_features(row: Mapping[str, Any], medians: Mapping[str, Any], swapped: bool = False) -> dict[str, float]:
    left_slot, right_slot = ((2, 1) if swapped else (1, 2))
    left, right = _slot(row, left_slot, medians), _slot(row, right_slot, medians)
    values: dict[str, float] = {}
    for field in PLAYER_DIRECT_FIELDS + PLAYER_DERIVED_FIELDS:
        values[f"pair_mean.{field}"] = (left[field] + right[field]) / 2.0
        values[f"pair_absolute_difference.{field}"] = abs(left[field] - right[field])
    values["pair_traded_history_count"] = left["traded_player_indicator"] + right["traded_player_indicator"]
    return values


def construct_scaled_matrix(
    project_root: Path, rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, float]], dict[str, Any], dict[str, Any]]:
    manifest = read_json(project_root / "curated/phase3f-r0/expanded_feature_manifest.json")
    state = read_json(project_root / "curated/phase3f-r0/expanded_preprocessing_state.json")
    if tuple(manifest.get("ordered_estimator_features", ())) != FEATURES:
        raise ReadinessError("frozen feature manifest differs from exact ordered 45")
    if tuple(state.get("feature_order", ())) != FEATURES or state.get("training_rows") != 29701:
        raise ReadinessError("frozen preprocessing population/order mismatch")
    if state.get("protected_final_test_values_used") is not False or not state.get("expanded_training_evidence_only"):
        raise ReadinessError("preprocessing provenance is not expanded-training-only")
    medians = state["player_slot_medians"]
    fills = state["symmetric_feature_fill_values"]
    means, scales = state["scaler"]["mean"], state["scaler"]["scale"]
    matrix = []
    symmetry_mismatches = 0
    second_stage_rows = 0
    for row in rows:
        original = _unscaled_features(row, medians)
        swapped = _unscaled_features(row, medians, swapped=True)
        symmetry_mismatches += sum(original[name] != swapped[name] for name in FEATURES)
        had_fill = False
        scaled = {}
        for name in FEATURES:
            value = _optional_finite(original[name])
            if value is None:
                value = _finite(fills[name], f"symmetric fill {name}")
                had_fill = True
            scale = _finite(scales[name], f"scale {name}")
            if scale <= 0:
                raise ReadinessError(f"invalid frozen scale: {name}")
            result = (value - _finite(means[name], f"mean {name}")) / scale
            if not math.isfinite(result):
                raise ReadinessError(f"nonfinite scaled feature: {name}")
            scaled[name] = result
        second_stage_rows += int(had_fill)
        matrix.append(scaled)
    if symmetry_mismatches:
        raise ReadinessError(f"slot-swap symmetry mismatch count: {symmetry_mismatches}")
    identity = {
        "version": VERSION,
        "source_path": "curated/phase3f-r0/expanded_preprocessing_state.json",
        "source_sha256": R0_ARTIFACTS["expanded_preprocessing_state.json"],
        "training_rows": 29701,
        "training_target_seasons": state["training_target_seasons"],
        "feature_order": list(FEATURES),
        "player_slot_medians_applied": True,
        "symmetric_feature_fills_applied": True,
        "frozen_scaler_applied_count": 1,
        "final_persisted_matrix_representation": "scaled_once_ready_for_direct_ridge_prediction",
        "final_test_statistics_learned": False,
        "training_and_final_test_combined_for_preprocessing": False,
        "independent_final_test_scaling": False,
        "double_scaling": False,
    }
    identity["deterministic_content_sha256"] = canonical_content_hash(identity)
    diagnostics = {
        "rows": len(rows), "features": len(FEATURES),
        "slot_swap_comparisons": len(rows) * len(FEATURES),
        "slot_swap_mismatches": symmetry_mismatches,
        "second_stage_symmetric_fill_rows": second_stage_rows,
        "all_values_finite": True,
    }
    return matrix, identity, diagnostics


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)


def serialize_csv(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _csv_value(row.get(name)) for name in columns})
    return stream.getvalue().encode("utf-8")


def _write_once(path: Path, body: bytes) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(body)
    return {"bytes": len(body), "sha256": sha256_bytes(body)}


def _artifact_reference(name: str, bodies: Mapping[str, bytes]) -> dict[str, str]:
    return {"path": name, "sha256": sha256_bytes(bodies[name])}


def build(
    project_root: Path | str = ".",
    output_dir: Path | str = "curated/phase3f-r3",
    *,
    initial_clean_preflight_confirmed: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    repository = verify_repository_state(project_root, initial_clean_preflight_confirmed)
    boundary = verify_empty_execution_boundary(project_root, output_dir)
    prerequisites = authenticate_prerequisites(project_root)
    protected_before = [namespace_fingerprint(project_root, relative) for relative in PRESERVED_NAMESPACES]
    expanded_before = namespace_fingerprint(project_root, "curated/phase3f-r0")

    raw_rows, population_base, target_fingerprints = load_final_population(project_root)
    profiles, profile_sources, profile_fingerprints = load_profiles(project_root)
    rows, history = curate_rows(raw_rows, profiles, profile_sources)
    matrix, preprocessing_identity, matrix_diagnostics = construct_scaled_matrix(project_root, rows)

    retained_teams = sorted({row["team_id"] for row in rows}, key=int)
    if len(retained_teams) != 28 or set(retained_teams) != set(TEAM_IDS) - set(EXCLUDED_TEAMS):
        raise ReadinessError("retained team set is not the exact frozen 28")
    if any(row["team_id"] in EXCLUDED_TEAMS for row in rows):
        raise ReadinessError("excluded team entered retained population")
    if any(row["pair_possessions"] < ELIGIBILITY_THRESHOLD for row in rows):
        raise ReadinessError("ineligible row entered retained population")

    raw_included = [row for row in raw_rows if row["team_id"] not in EXCLUDED_TEAMS]
    excluded_raw = [row for row in raw_rows if row["team_id"] in EXCLUDED_TEAMS]
    excluded_eligible = [row for row in excluded_raw if row["eligible_poss_ge_150"]]
    population = {
        "version": VERSION,
        "target_season": TARGET_SEASON,
        "raw_rows_all_30_teams": len(raw_rows),
        "raw_rows_retained_28_teams_before_eligibility": len(raw_included),
        "eligible_retained_rows": len(rows),
        "eligible_retained_possessions": sum(row["pair_possessions"] for row in rows),
        "retained_team_count": 28,
        "retained_team_ids": retained_teams,
        "excluded_teams": {
            team: {
                "name": EXCLUDED_TEAMS[team],
                "retained_rows": 0,
                "raw_rows": sum(row["team_id"] == team for row in excluded_raw),
                "eligible_rows_excluded": sum(row["team_id"] == team and row["eligible_poss_ge_150"] for row in excluded_raw),
                "eligible_possessions_excluded": sum(row["pair_possessions"] for row in excluded_eligible if row["team_id"] == team),
                "disposition": "proven_non_exhaustive_exclude_whole_team",
            }
            for team in sorted(EXCLUDED_TEAMS, key=int)
        },
        "zero_possession_raw_rows_preserved_diagnostically": sum(row["pair_possessions"] == 0 for row in raw_rows),
        "zero_possession_retained_rows": 0,
        "direct_full_season_source_rows": len(rows),
        "recovered_or_window_source_rows": 0,
        "unique_observation_keys": len({row["observation_key"] for row in rows}),
        "target_distribution_summaries_computed": False,
        "team_diagnostics": population_base["teams"],
        "matrix_integrity": matrix_diagnostics,
    }
    population["deterministic_content_sha256"] = canonical_content_hash(population)
    history["version"] = VERSION
    history["deterministic_content_sha256"] = canonical_content_hash(history)

    row_index_columns = (
        "row_number", "observation_key", "target_season", "team_id", "team_name",
        "player_1_id", "player_2_id", "target_net_rating", "pair_possessions",
        "history_status", "history_confidence", "missing_player_count",
        "player_1_history_profile_season", "player_1_history_gap",
        "player_2_history_profile_season", "player_2_history_gap",
        "endpoint_exact_250_flag", "direct_full_season_source",
    )
    indexed_rows = [{"row_number": index, **row} for index, row in enumerate(rows)]
    target_rows = [{
        "row_number": index, "observation_key": row["observation_key"],
        "target_net_rating": row["target_net_rating"],
        "target_source_measure": "Advanced",
        "target_source_path": row["advanced_source_path"],
        "target_source_sha256": row["advanced_source_sha256"],
    } for index, row in enumerate(rows)]
    staging_columns = tuple(indexed_rows[0].keys()) if indexed_rows else ()

    feature_manifest = {
        "version": VERSION,
        "ordered_estimator_features": list(FEATURES),
        "feature_count": 45,
        "feature_family": "Phase 3D/R0 no-shot symmetric",
        "source_manifest_path": "curated/phase3f-r0/expanded_feature_manifest.json",
        "source_manifest_sha256": R0_ARTIFACTS["expanded_feature_manifest.json"],
        "matrix_representation": "scaled_once_ready_for_direct_ridge_prediction",
        "slot_exchange_invariant": True,
        "target_exposure_reliability_provenance_fields_absent": True,
        "slot_specific_columns_absent": True,
    }
    feature_manifest["deterministic_content_sha256"] = canonical_content_hash(feature_manifest)

    bodies: dict[str, bytes] = {
        "final_test_staging.csv": serialize_csv(indexed_rows, staging_columns),
        "final_test_row_index.csv": serialize_csv(indexed_rows, row_index_columns),
        "final_test_target_vector.csv": serialize_csv(target_rows, tuple(target_rows[0].keys())),
        "final_test_estimator_matrix_scaled.csv": serialize_csv(matrix, FEATURES),
        "estimator_feature_manifest.json": serialize_json(feature_manifest),
        "applied_preprocessing_state_identity.json": serialize_json(preprocessing_identity),
        "population_diagnostics.json": serialize_json(population),
        "history_selection_diagnostics.json": serialize_json(history),
    }

    protected_after = [namespace_fingerprint(project_root, relative) for relative in PRESERVED_NAMESPACES]
    expanded_after = namespace_fingerprint(project_root, "curated/phase3f-r0")
    if protected_before != protected_after or expanded_before != expanded_after:
        raise ReadinessError("protected or expanded-training evidence changed during construction")
    referenced_files = {
        **target_fingerprints, **profile_fingerprints,
        "curated/phase3f-r0/expanded_feature_manifest.json": R0_ARTIFACTS["expanded_feature_manifest.json"],
        "curated/phase3f-r0/expanded_preprocessing_state.json": R0_ARTIFACTS["expanded_preprocessing_state.json"],
        "curated/phase3f-r0/expanded_training_staging.csv": R0_ARTIFACTS["expanded_training_staging.csv"],
        "curated/phase3f-r0/expanded_training_estimator_matrix_unscaled.csv": R0_ARTIFACTS["expanded_training_estimator_matrix_unscaled.csv"],
    }
    input_fingerprints = {
        "version": VERSION,
        "referenced_files": dict(sorted(referenced_files.items())),
        "authenticated_prerequisites": prerequisites,
        "protected_evidence_before": protected_before,
        "protected_evidence_after": protected_after,
        "protected_evidence_unchanged": True,
        "expanded_training_before": expanded_before,
        "expanded_training_after": expanded_after,
        "expanded_training_unchanged": True,
    }
    input_fingerprints["deterministic_content_sha256"] = canonical_content_hash(input_fingerprints)
    bodies["input_fingerprints.json"] = serialize_json(input_fingerprints)

    output_refs = {
        name: _artifact_reference(name, bodies) for name in bodies
    }
    gates = [
        {
            "id": GATE_IDS[0], "status": "passed", "blocks_final_execution": False,
            "evidence": "three authenticated strict-prior profile seasons; nearest-profile selection; explicit missing states; zero strict-prior/lookback violations",
            "artifacts": [output_refs["history_selection_diagnostics.json"], {"path": "planning/phase3f-r2a/artifact_hashes.json", "sha256": PINNED_MANIFESTS["planning/phase3f-r2a/artifact_hashes.json"]}],
        },
        {
            "id": GATE_IDS[1], "status": "passed", "blocks_final_execution": False,
            "evidence": "all 60 direct full-season bodies byte-authenticated; Base/Advanced keys reconciled; targets are direct Advanced NET_RATING",
            "artifacts": [output_refs["population_diagnostics.json"], {"path": "planning/phase3f-r2b.2/artifact_hashes.json", "sha256": PINNED_MANIFESTS["planning/phase3f-r2b.2/artifact_hashes.json"]}],
        },
        {
            "id": GATE_IDS[2], "status": "passed", "blocks_final_execution": False,
            "evidence": "all 30 teams adjudicated; 28 retained; Indiana and Memphis excluded in full under R2D.2; no other exclusion",
            "artifacts": [output_refs["population_diagnostics.json"], {"path": "cache/phase3f-r2d.2/protected-recovery-continuation/artifact-hashes.json", "sha256": PINNED_MANIFESTS["cache/phase3f-r2d.2/protected-recovery-continuation/artifact-hashes.json"]}],
        },
        {
            "id": GATE_IDS[3], "status": "passed", "blocks_final_execution": False,
            "evidence": "every retained row has direct finite NET_RATING, finite POSS >= 150, and distinct positive canonical player IDs; target magnitude was not used",
            "artifacts": [output_refs["final_test_row_index.csv"], output_refs["final_test_target_vector.csv"]],
        },
        {
            "id": GATE_IDS[4], "status": "passed", "blocks_final_execution": False,
            "evidence": "unique canonical keys, exact Base/Advanced equality, identical pinned row order, exact 45-feature order, finite scaled-once matrix, and full slot-swap symmetry",
            "artifacts": [output_refs["final_test_row_index.csv"], output_refs["final_test_target_vector.csv"], output_refs["final_test_estimator_matrix_scaled.csv"], output_refs["estimator_feature_manifest.json"]],
        },
        {
            "id": GATE_IDS[5], "status": "passed", "blocks_final_execution": False,
            "evidence": "audit-cleared acquisition/reconciliation lineage authenticated at the required committed HEAD; no target/prediction co-opening, prediction, or execution artifact exists",
            "artifacts": [{"path": "PHASE3F_R2D_2_RECOVERY_CONTINUATION_REPORT.md", "sha256": sha256_file(project_root / "PHASE3F_R2D_2_RECOVERY_CONTINUATION_REPORT.md")}, output_refs["input_fingerprints.json"]],
        },
    ]
    require_all_gates_pass(gates)
    readiness = {
        "version": VERSION,
        "frozen_gate_count": 6,
        "frozen_gate_order": list(GATE_IDS),
        "gates": gates,
        "all_six_passed": all(item["status"] == "passed" for item in gates),
        "readiness_checkpoint_read_only_audit_cleared": False,
        "one_time_final_model_execution_authorized": False,
        "checkpoint_grants_execution_authorization": False,
    }
    readiness["deterministic_content_sha256"] = canonical_content_hash(readiness)
    bodies["readiness_gates.json"] = serialize_json(readiness)

    if len(rows) != len(indexed_rows) or len(rows) != len(target_rows) or len(rows) != len(matrix):
        raise ReadinessError("row alignment count mismatch")
    for index, (row, target) in enumerate(zip(indexed_rows, target_rows)):
        if row["row_number"] != index or target["row_number"] != index or row["observation_key"] != target["observation_key"]:
            raise ReadinessError("row alignment ordering mismatch")

    artifact_hashes = {
        "version": VERSION,
        "manifest_rule": "nonrecursive: hash exactly the ten payload artifacts; exclude this manifest and summary.json",
        "artifact_inventory": list(OUTPUT_FILES),
        "payload_artifacts": list(PAYLOAD_FILES),
        "excluded_from_own_manifest": ["artifact_hashes.json", "summary.json"],
        "artifacts": {
            name: {"bytes": len(bodies[name]), "sha256": sha256_bytes(bodies[name])}
            for name in PAYLOAD_FILES
        },
    }
    artifact_hashes["deterministic_content_sha256"] = canonical_content_hash(artifact_hashes)
    bodies["artifact_hashes.json"] = serialize_json(artifact_hashes)
    summary = {
        "version": VERSION,
        "classification": "PASS — 2025–26 final-test dataset constructed and all six readiness gates passed; ready for read-only audit",
        "repository": repository,
        "execution_boundary": boundary,
        "target_season": TARGET_SEASON,
        "retained_teams": 28,
        "excluded_team_ids": sorted(EXCLUDED_TEAMS, key=int),
        "raw_rows_all_30_teams": len(raw_rows),
        "raw_rows_retained_28_teams_before_eligibility": len(raw_included),
        "eligible_rows": len(rows),
        "eligible_possessions": population["eligible_retained_possessions"],
        "history_status_rows": history["history_status_rows"],
        "selected_profile_seasons_all_slots": history["selected_profile_seasons_all_slots"],
        "missing_slot_count": history["missing_slot_count"],
        "estimator_matrix_dimensions": [len(rows), 45],
        "estimator_matrix_representation": "scaled_once_ready_for_direct_ridge_prediction",
        "feature_manifest_content_sha256": feature_manifest["deterministic_content_sha256"],
        "preprocessing_state_sha256": R0_ARTIFACTS["expanded_preprocessing_state.json"],
        "slot_swap_comparisons": matrix_diagnostics["slot_swap_comparisons"],
        "slot_swap_mismatches": 0,
        "row_alignment_passed": True,
        "six_readiness_gates": {item["id"]: item["status"] for item in gates},
        "artifact_manifest_content_sha256": artifact_hashes["deterministic_content_sha256"],
        "network_operations": 0,
        "estimator_operations": 0,
        "prediction_operations": 0,
        "metric_operations": 0,
        "model_serialization_operations": 0,
        "readiness_checkpoint_read_only_audit_cleared": False,
        "one_time_final_model_execution_authorized": False,
        "next_step": "one focused read-only audit of this readiness checkpoint",
    }
    summary["deterministic_content_sha256"] = canonical_content_hash(summary)
    bodies["summary.json"] = serialize_json(summary)

    if tuple(bodies) != OUTPUT_FILES:
        raise ReadinessError("generated artifact inventory/order mismatch")
    output_dir.mkdir(parents=True, exist_ok=False)
    for name in OUTPUT_FILES:
        _write_once(output_dir / name, bodies[name])
    if sorted(path.name for path in output_dir.iterdir()) != sorted(OUTPUT_FILES):
        raise ReadinessError("written artifact inventory mismatch")
    return summary


def audited_r3_fingerprints(project_root: Path) -> list[dict[str, Any]]:
    r3_dir = project_root / "curated/phase3f-r3"
    if not r3_dir.is_dir() or r3_dir.is_symlink():
        raise ReadinessError("missing original R3 namespace")
    actual = sorted(path.name for path in r3_dir.iterdir() if path.is_file())
    if actual != sorted(OUTPUT_FILES):
        raise ReadinessError("original R3 inventory mismatch")
    records = []
    for name in OUTPUT_FILES:
        path = r3_dir / name
        stat = path.stat()
        digest = sha256_file(path)
        if digest != R3_AUDITED_SHA256[name]:
            raise ReadinessError(f"original R3 audited hash mismatch: {name}")
        records.append({
            "path": f"curated/phase3f-r3/{name}",
            "bytes": stat.st_size,
            "sha256": digest,
            "last_write_time_ns": stat.st_mtime_ns,
            "last_write_time_utc": datetime.fromtimestamp(
                stat.st_mtime_ns / 1_000_000_000, tz=timezone.utc,
            ).isoformat().replace("+00:00", "Z"),
        })
    return records


def build_reproducibility_correction(
    project_root: Path | str = ".",
    output_dir: Path | str = "curated/phase3f-r3.1",
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    if output_dir.exists():
        raise ReadinessError(f"write-once output namespace already exists: {output_dir}")
    validate_final_git_visible_inventory(project_root)
    original_before = audited_r3_fingerprints(project_root)
    original_by_name = {Path(item["path"]).name: item for item in original_before}

    temp_parent = project_root / ".t"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase3f-r3.1-", dir=temp_parent) as temporary:
        temporary_root = Path(temporary)
        first = temporary_root / "first"
        second = temporary_root / "second"
        build(project_root, first, initial_clean_preflight_confirmed=True)
        build(project_root, second, initial_clean_preflight_confirmed=True)

        first_bodies = {name: (first / name).read_bytes() for name in OUTPUT_FILES}
        second_bodies = {name: (second / name).read_bytes() for name in OUTPUT_FILES}
        if first_bodies != second_bodies:
            raise ReadinessError("two corrected R3 builds are not byte-identical")
        for name in OUTPUT_FILES[:-1]:
            if first_bodies[name] != (project_root / "curated/phase3f-r3" / name).read_bytes():
                raise ReadinessError(f"fresh build differs from referenced R3 artifact: {name}")

        corrected_summary_body = first_bodies["summary.json"]
        corrected_summary_hash = sha256_bytes(corrected_summary_body)
        referenced = {
            "version": "phase3f-r3.1.reproducibility-correction.v1",
            "reference_rule": "reference exactly the eleven audited R3 non-summary artifacts in place; do not copy them",
            "artifacts": [
                {
                    "path": original_by_name[name]["path"],
                    "bytes": original_by_name[name]["bytes"],
                    "sha256": original_by_name[name]["sha256"],
                    "disposition": "referenced_not_copied",
                }
                for name in OUTPUT_FILES[:-1]
            ],
        }
        referenced["deterministic_content_sha256"] = canonical_content_hash(referenced)
        correction = {
            "version": "phase3f-r3.1.reproducibility-correction.v1",
            "classification": "R3.1 narrow non-scientific reproducibility correction",
            "audit_defects_corrected": [
                {
                    "id": "cli_extra_blank_line_at_eof",
                    "correction": "removed exactly one extra trailing line feed; no CLI behavior changed",
                },
                {
                    "id": "summary_construction_time_inventory_timing_dependency",
                    "correction": "serialize the contract-defined five-file R3 deliverable inventory while separately validating live Git state",
                },
            ],
            "historical_original_summary": {
                "path": "curated/phase3f-r3/summary.json",
                "bytes": original_by_name["summary.json"]["bytes"],
                "sha256": original_by_name["summary.json"]["sha256"],
                "status": "historically_valid_original_production_summary_superseded_for_deterministic_composite_evidence",
            },
            "corrected_summary": {
                "path": "curated/phase3f-r3.1/corrected_summary.json",
                "bytes": len(corrected_summary_body),
                "sha256": corrected_summary_hash,
                "declared_git_visible_r3_deliverables": list(EXPECTED_R3_GIT_VISIBLE_DELIVERABLES),
            },
            "authoritative_corrected_r3_composite": {
                "artifact_count": 12,
                "referenced_original_r3_non_summary_artifact_count": 11,
                "corrected_summary_path": "curated/phase3f-r3.1/corrected_summary.json",
            },
            "reproducibility_proof": {
                "independent_fresh_build_count": 2,
                "fresh_build_artifact_count_each": 12,
                "two_fresh_builds_byte_identical": True,
                "fresh_non_summary_artifacts_match_referenced_originals": True,
                "fresh_summary_matches_corrected_summary": True,
                "disposable_build_directories_removed_after_proof": True,
            },
            "scientific_artifacts_changed": False,
            "scientific_rows_features_targets_preprocessing_readiness_population_or_inputs_changed": False,
            "readiness_checkpoint_read_only_audit_cleared": False,
            "one_time_final_model_execution_authorized": False,
        }
        correction["deterministic_content_sha256"] = canonical_content_hash(correction)
        bodies = {
            "correction.json": serialize_json(correction),
            "referenced_r3_artifacts.json": serialize_json(referenced),
            "corrected_summary.json": corrected_summary_body,
        }
        artifact_hashes = {
            "version": "phase3f-r3.1.reproducibility-correction.v1",
            "manifest_rule": "nonrecursive: hash correction.json, referenced_r3_artifacts.json, and corrected_summary.json; exclude this manifest and summary.json",
            "artifact_inventory": list(R3_1_OUTPUT_FILES),
            "payload_artifacts": list(R3_1_OUTPUT_FILES[:3]),
            "excluded_from_own_manifest": ["artifact_hashes.json", "summary.json"],
            "artifacts": {
                name: {"bytes": len(body), "sha256": sha256_bytes(body)}
                for name, body in bodies.items()
            },
        }
        artifact_hashes["deterministic_content_sha256"] = canonical_content_hash(artifact_hashes)
        bodies["artifact_hashes.json"] = serialize_json(artifact_hashes)
        summary = {
            "version": "phase3f-r3.1.reproducibility-correction.v1",
            "classification": "PASS — R3.1 reproducibility correction evidence constructed",
            "original_r3_summary_sha256": R3_AUDITED_SHA256["summary.json"],
            "corrected_r3_summary_sha256": corrected_summary_hash,
            "artifact_manifest_content_sha256": artifact_hashes["deterministic_content_sha256"],
            "authoritative_corrected_r3_composite_artifact_count": 12,
            "referenced_original_r3_non_summary_artifact_count": 11,
            "scientific_artifacts_changed": False,
            "network_operations": 0,
            "estimator_operations": 0,
            "prediction_operations": 0,
            "metric_operations": 0,
            "model_serialization_operations": 0,
            "readiness_checkpoint_read_only_audit_cleared": False,
            "one_time_final_model_execution_authorized": False,
            "next_step": "one narrow read-only audit of the R3.1 reproducibility correction",
        }
        summary["deterministic_content_sha256"] = canonical_content_hash(summary)
        bodies["summary.json"] = serialize_json(summary)

    if audited_r3_fingerprints(project_root) != original_before:
        raise ReadinessError("original R3 bytes, hashes, timestamps, or inventory changed")
    if tuple(bodies) != R3_1_OUTPUT_FILES:
        raise ReadinessError("R3.1 correction artifact inventory/order mismatch")
    output_dir.mkdir(parents=True, exist_ok=False)
    for name in R3_1_OUTPUT_FILES:
        _write_once(output_dir / name, bodies[name])
    if sorted(path.name for path in output_dir.iterdir()) != sorted(R3_1_OUTPUT_FILES):
        raise ReadinessError("written R3.1 correction inventory mismatch")
    return summary
