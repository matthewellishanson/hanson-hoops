"""Build the offline Phase 3F-R1S acquisition plan.

This module describes and validates a future acquisition.  It contains no
transport, response-reading, reconciliation execution, or model capability.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


VERSION = "phase3f-r1s.simplified-acquisition-plan.v1"
CHECKPOINT = "Phase 3F-R1S — Simplified Final-Test Acquisition Plan"
COMMITTED_HEAD = "20469c320886b6ea306fe3e5d17cbc3db23c6824"
PROTECTED_SEASON = "2025-26"
SEASON_TYPE = "Regular Season"
PROTECTED_NAMESPACE = "raw/phase3f-r1s/protected-final-target/"
DEPENDENCY_NAMESPACE = "raw/phase3f-r1s/prior-profile-dependencies/"
PLANNING_NAMESPACE = "planning/phase3f-r1s/"
OUTPUT_FILES = ("acquisition_plan.json", "artifact_hashes.json", "summary.json")

TEAM_IDS = tuple(str(value) for value in range(1610612737, 1610612767))
MEASURES = ("Base", "Advanced")
READINESS_GATES = (
    "predictor_evidence_completeness",
    "target_evidence_completeness",
    "team_population_exhaustiveness",
    "row_eligibility",
    "row_alignment",
    "protected_result_reveal",
)
FINAL_EXECUTION_REQUIRED_CONDITIONS = (
    "all_frozen_phase3f_final_test_readiness_gates_pass",
    "completed_readiness_checkpoint_has_read_only_audit_clearance",
    "user_separately_authorizes_one_time_final_model_execution",
)

FINAL_EXECUTION_BOUNDARY = {
    "frozen_readiness_gate_count": 6,
    "frozen_readiness_gates": list(READINESS_GATES),
    "required_conditions": list(FINAL_EXECUTION_REQUIRED_CONDITIONS),
    "authorization_rule": "all three required conditions must be true",
    "failed_or_unresolved_gate": "blocks final execution",
}

STAGE_SEPARATION = {
    "planning": "R1S planning does not authorize acquisition",
    "acquisition": "acquisition completion does not authorize final-test construction",
    "reconciliation": "does not authorize fitting or prediction",
    "readiness": "readiness assessment does not itself authorize execution",
    "failed_or_unresolved_readiness": "any failed or unresolved readiness gate blocks execution",
    "final_execution": "remains a later, separate phase",
    "excluded_team_seasons": "no result from an unresolved or excluded team-season may silently enter the final test",
    "acquisition_completion": "no model execution is authorized merely because evidence acquisition completed",
    "protected_opening": "2025-26 may be opened only by the later bounded acquisition checkpoint",
}

TEAM_PARAMETERS = {
    "DateFrom": "",
    "DateTo": "",
    "GameID": "",
    "GameSegment": "",
    "GroupQuantity": "2",
    "LastNGames": "0",
    "LeagueID": "00",
    "Location": "",
    "Month": "0",
    "OpponentTeamID": "0",
    "Outcome": "",
    "PORound": "",
    "PaceAdjust": "N",
    "PerMode": "Totals",
    "Period": "0",
    "PlusMinus": "N",
    "Rank": "N",
    "Season": PROTECTED_SEASON,
    "SeasonSegment": "",
    "SeasonType": SEASON_TYPE,
    "ShotClockRange": "",
    "VsConference": "",
    "VsDivision": "",
}

PLAYER_PARAMETERS = {
    "College": "",
    "Conference": "",
    "Country": "",
    "DateFrom": "",
    "DateTo": "",
    "Division": "",
    "DraftPick": "",
    "DraftYear": "",
    "GameScope": "",
    "GameSegment": "",
    "Height": "",
    "LastNGames": "0",
    "LeagueID": "00",
    "Location": "",
    "MeasureType": "Base",
    "Month": "0",
    "OpponentTeamID": "0",
    "Outcome": "",
    "PORound": "",
    "PaceAdjust": "N",
    "Period": "0",
    "PlayerExperience": "",
    "PlayerPosition": "",
    "PlusMinus": "N",
    "Rank": "N",
    "Season": "2024-25",
    "SeasonSegment": "",
    "SeasonType": SEASON_TYPE,
    "ShotClockRange": "",
    "StarterBench": "",
    "TeamID": "",
    "TwoWay": "",
    "VsConference": "",
    "VsDivision": "",
    "Weight": "",
}

RESEARCH_HEADERS = {
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nba.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

SOURCE_PINS = {
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


class PlanError(RuntimeError):
    """Raised when the compact planning contract is violated."""


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _protected_requests() -> list[dict[str, Any]]:
    requests = []
    for team_id in TEAM_IDS:
        for measure in MEASURES:
            parameters = {**TEAM_PARAMETERS, "MeasureType": measure, "TeamID": team_id}
            requests.append(
                {
                    "request_id": f"teamdashlineups:{team_id}:{measure.lower()}",
                    "endpoint": "teamdashlineups",
                    "namespace": PROTECTED_NAMESPACE,
                    "parameters": parameters,
                    "protected": True,
                }
            )
    return requests


def _dependencies() -> list[dict[str, Any]]:
    return [
        {
            "request_id": f"leaguedashplayerstats:2024-25:base:{per_mode.lower()}",
            "endpoint": "leaguedashplayerstats",
            "namespace": DEPENDENCY_NAMESPACE,
            "parameters": {**PLAYER_PARAMETERS, "PerMode": per_mode},
            "protected": False,
            "status": "missing_not_acquired",
        }
        for per_mode in ("Per100Possessions", "Totals")
    ]


def plan_document() -> dict[str, Any]:
    """Return the deterministic, data-free R1S planning document."""
    return {
        "version": VERSION,
        "checkpoint": CHECKPOINT,
        "committed_head": COMMITTED_HEAD,
        "scope": {
            "planning_only": True,
            "network_requests_authorized": False,
            "protected_evidence_access_authorized": False,
            "holdout_construction_authorized": False,
            "model_execution_authorized": False,
        },
        "source_pins": deepcopy(SOURCE_PINS),
        "namespaces": {
            "planning": PLANNING_NAMESPACE,
            "future_protected_responses": PROTECTED_NAMESPACE,
            "future_non_protected_dependencies": DEPENDENCY_NAMESPACE,
        },
        "protected_requests": _protected_requests(),
        "missing_non_protected_dependencies": _dependencies(),
        "transport_rules": {
            "request_order": "sequential",
            "minimum_seconds_between_attempts": 1,
            "timeout_seconds": 30,
            "allow_redirects": False,
            "trust_env": False,
            "automatic_retries": 0,
            "authorized_attempts_per_request_identity": 1,
            "headers": deepcopy(RESEARCH_HEADERS),
            "promotion": "verify before promotion",
            "failure": "quarantine and stop",
            "implemented_here": False,
        },
        "future_records": {
            "write_policy": "append-only/write-once during acquisition",
            "records": {
                "authorization": ["request_id", "endpoint", "parameters", "authorized_checkpoint"],
                "attempt_start": ["request_id", "attempted_at", "attempt_number"],
                "attempt_outcome": ["request_id", "completed_at", "http_status", "byte_length", "state"],
                "verified_raw_response_body": ["request_id", "raw_sha256", "canonical_json_sha256", "state"],
                "quarantine_when_applicable": ["request_id", "raw_sha256", "canonical_json_sha256", "state", "reason"],
            },
            "hash_meaning": "SHA-256 checks mutation and byte identity; it does not authenticate an author or authorization.",
        },
        "restart_states": {
            "not_started": "eligible for its one authorized attempt",
            "completed_verified": "re-hash, verify, and skip",
            "started_without_outcome": "stop for read-only investigation",
            "failed_or_quarantined": "preserve evidence and stop",
            "conflicting_state": "refuse progress and stop",
        },
        "population_reconciliation": {
            "pair_key": "numeric canonical unordered player IDs within team and season",
            "base_advanced_key_equality_required": True,
            "zero_possession_rows_visible": True,
            "eligibility": "direct full-season POSS >= 150",
            "target": "direct full-season Advanced NET_RATING",
            "approximate_window_rating_aggregation": False,
            "selective_omitted_pair_removal": False,
            "proved_non_exhaustive_team": "exclude the whole team unless definition-supported direct recovery exists",
        },
        "exact_250": {
            "status": "unresolved_warning",
            "meaning": "investigate; exactly 250 rows is not proof of incompleteness",
            "automatic_exclusion": False,
            "automatic_recovery": False,
            "recovery_requests": [],
            "later_authorization_must_identify": [
                "affected team",
                "triggering full-season response hash",
                "exact complementary date windows",
                "four Base/Advanced request identities",
                "approving checkpoint",
            ],
        },
        "stage_separation": deepcopy(STAGE_SEPARATION),
        "final_execution_boundary": deepcopy(FINAL_EXECUTION_BOUNDARY),
        "threat_model": {
            "protects_against": [
                "accidental request drift",
                "an agent using an unapproved endpoint, season, team, measure, or parameter",
                "accidental duplicate requests",
                "accidental retries",
                "partial or contradictory acquisition state",
                "corrupted or changed response bytes",
                "silent omission of required requests",
                "mixing protected acquisition with model execution",
                "accidental access to protected evidence before authorization",
            ],
            "out_of_scope": [
                "a malicious repository owner",
                "a caller who can arbitrarily rewrite source code and all evidence files",
                "a compromised operating system",
                "forged evidence created by an actor with unrestricted local write and execution access",
            ],
            "authority_boundary": "Git review, audit, and the future committed checkpoint are the practical authority boundary.",
            "hash_limit": "SHA-256 hashes are mutation and identity checks; they are not proof of who created or authorized the bytes.",
        },
        "control_purposes": {
            "scientific_validity": "freeze the population, direct target, eligibility, and reconciliation rules",
            "operational_safety": "bound later attempts and stop on ambiguous or failed state",
            "reproducibility": "pin identities, ordering, source hashes, and deterministic serialization",
            "adversarial_security": "out of scope",
        },
    }


def _identity_key(request: Mapping[str, Any]) -> bytes:
    return serialize_json(
        {"endpoint": request.get("endpoint"), "parameters": request.get("parameters")}
    )


def final_execution_authorized(
    readiness_gate_states: Mapping[str, str],
    *,
    readiness_checkpoint_audit_cleared: bool,
    user_one_time_execution_authorized: bool,
) -> bool:
    """Assess the frozen three-condition boundary without executing a model."""
    if set(readiness_gate_states) != set(READINESS_GATES):
        raise PlanError("readiness gate identities drift")
    allowed_states = {"passed", "failed", "unresolved"}
    if any(state not in allowed_states for state in readiness_gate_states.values()):
        raise PlanError("invalid readiness gate state")
    return (
        all(readiness_gate_states[gate] == "passed" for gate in READINESS_GATES)
        and readiness_checkpoint_audit_cleared is True
        and user_one_time_execution_authorized is True
    )


def validate_plan(plan: Mapping[str, Any]) -> None:
    """Validate objective R1S planning facts and reject drift."""
    if plan.get("version") != VERSION or plan.get("committed_head") != COMMITTED_HEAD:
        raise PlanError("checkpoint identity drift")
    if plan.get("source_pins") != SOURCE_PINS:
        raise PlanError("R0/R0.1 source pins drift")
    namespaces = plan.get("namespaces")
    if namespaces != {
        "planning": PLANNING_NAMESPACE,
        "future_protected_responses": PROTECTED_NAMESPACE,
        "future_non_protected_dependencies": DEPENDENCY_NAMESPACE,
    } or len(set(namespaces.values())) != 3:
        raise PlanError("namespace separation failure")

    protected = plan.get("protected_requests")
    if not isinstance(protected, list) or len(protected) != 60:
        raise PlanError("exactly 60 protected requests are required")
    if len({_identity_key(item) for item in protected}) != 60:
        raise PlanError("duplicate protected request identity")
    expected = _protected_requests()
    if protected != expected:
        raise PlanError("protected request ordering or parameters drift")

    dependencies = plan.get("missing_non_protected_dependencies")
    if dependencies != _dependencies() or len(dependencies) != 2:
        raise PlanError("exactly two frozen non-protected dependencies are required")
    if any(item["namespace"] == PROTECTED_NAMESPACE for item in dependencies):
        raise PlanError("dependency/protected namespace collision")

    transport = plan.get("transport_rules", {})
    required_transport = {
        "request_order": "sequential",
        "minimum_seconds_between_attempts": 1,
        "timeout_seconds": 30,
        "allow_redirects": False,
        "trust_env": False,
        "automatic_retries": 0,
        "authorized_attempts_per_request_identity": 1,
        "headers": RESEARCH_HEADERS,
        "promotion": "verify before promotion",
        "failure": "quarantine and stop",
        "implemented_here": False,
    }
    if transport != required_transport:
        raise PlanError("transport rule drift")

    recovery = plan.get("exact_250", {})
    if (
        recovery.get("status") != "unresolved_warning"
        or recovery.get("recovery_requests") != []
        or recovery.get("automatic_exclusion") is not False
        or recovery.get("automatic_recovery") is not False
    ):
        raise PlanError("exact-250 must remain unresolved and non-executable")

    required_states = {
        "not_started",
        "completed_verified",
        "started_without_outcome",
        "failed_or_quarantined",
        "conflicting_state",
    }
    if set(plan.get("restart_states", {})) != required_states:
        raise PlanError("restart-state definitions drift")
    scope = plan.get("scope", {})
    if scope != {
        "planning_only": True,
        "network_requests_authorized": False,
        "protected_evidence_access_authorized": False,
        "holdout_construction_authorized": False,
        "model_execution_authorized": False,
    }:
        raise PlanError("stage scope drift")
    if plan.get("stage_separation") != STAGE_SEPARATION:
        raise PlanError("stage-separation boundary drift")
    if plan.get("final_execution_boundary") != FINAL_EXECUTION_BOUNDARY:
        raise PlanError("final-execution readiness boundary drift")


def validate_planning_input_path(project_root: Path, candidate: Path) -> str:
    """Reject cache/raw/protected paths before any read is attempted."""
    root = Path(project_root)
    path = Path(candidate)
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise PlanError("planning input must be inside the project") from exc
    lowered_parts = {part.lower() for part in Path(relative).parts}
    if "cache" in lowered_parts or "raw" in lowered_parts or PROTECTED_SEASON in relative:
        raise PlanError("protected or cache paths are forbidden planning inputs")
    if relative not in SOURCE_PINS:
        raise PlanError("unapproved planning input")
    return relative


def _verified_source_pins(project_root: Path) -> dict[str, str]:
    verified = {}
    for relative, expected_hash in sorted(SOURCE_PINS.items()):
        path = Path(project_root) / relative
        validate_planning_input_path(Path(project_root), path)
        actual_hash = sha256_bytes(path.read_bytes())
        if actual_hash != expected_hash:
            raise PlanError(f"pinned source changed: {relative}")
        verified[relative] = actual_hash
    return verified


def build(project_root: Path, output_dir: Path) -> dict[str, Any]:
    """Write one new deterministic three-file planning namespace."""
    destination = Path(output_dir)
    if destination.exists():
        raise PlanError(f"write-once planning namespace already exists: {destination}")
    verified = _verified_source_pins(Path(project_root))
    plan = plan_document()
    plan["source_pins"] = verified
    validate_plan(plan)
    plan_bytes = serialize_json(plan)
    summary = {
        "version": VERSION,
        "status": "planning_complete_ready_for_read_only_audit",
        "protected_request_count": 60,
        "missing_non_protected_dependency_count": 2,
        "generated_artifact_count": 3,
        "network_requests_made": 0,
        "protected_evidence_files_opened": 0,
        "recovery_request_count": 0,
        "source_pin_count": len(verified),
        "frozen_readiness_gate_count": len(READINESS_GATES),
        "final_execution_required_condition_count": len(FINAL_EXECUTION_REQUIRED_CONDITIONS),
    }
    summary_bytes = serialize_json(summary)
    hashes = {
        "version": VERSION,
        "artifact_inventory": list(OUTPUT_FILES),
        "sha256": {
            "acquisition_plan.json": sha256_bytes(plan_bytes),
            "summary.json": sha256_bytes(summary_bytes),
        },
        "note": "artifact_hashes.json excludes itself to avoid a circular hash",
    }
    destination.mkdir(parents=False, exist_ok=False)
    for name, content in (
        ("acquisition_plan.json", plan_bytes),
        ("summary.json", summary_bytes),
        ("artifact_hashes.json", serialize_json(hashes)),
    ):
        with (destination / name).open("xb") as handle:
            handle.write(content)
    return summary
