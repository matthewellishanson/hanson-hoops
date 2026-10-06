"""Freeze expanded final-training data and the future final-test contract.

Phase 3F-R0 is deliberately pre-result.  It uses only the committed historical
training curation and the spent development-holdout staging table.  It learns
deterministic preprocessing state, but it never constructs an estimator,
performs a model operation, or opens protected final-test evidence.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import socket
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from pair_fit_v2 import phase3b_curation as phase3b
from pair_fit_v2 import phase3d_model_refinement as phase3d


VERSION = "phase3f-r0.final-test-freeze.v1"
REQUIRED_BRANCH = "research/pair-fit-v2"
COMMITTED_HEAD = "5d9e123c20d486b4401932ea656897a6791083fc"
PROTECTED_SEASON = "2025-26"
DEVELOPMENT_SEASON = "2024-25"
SEASON_TYPE = "Regular Season"
MAX_HISTORY_LOOKBACK = 3
ELIGIBILITY_THRESHOLD = 150.0
RIDGE_ALPHA = 3000.0
EXPECTED_HISTORICAL_ROWS = 27001
EXPECTED_DEVELOPMENT_ROWS = 2700
EXPECTED_EXPANDED_ROWS = 29701
EXCLUDED_DEVELOPMENT_TEAMS = {
    "1610612755": "Philadelphia 76ers",
    "1610612766": "Charlotte Hornets",
}

HISTORICAL_STAGING = Path("curated/phase3b/phase3b_poss_ge_150.csv")
DEVELOPMENT_STAGING = Path("curated/phase3e-r2/holdout_staging.csv")

EXPECTED_INPUT_SHA256 = {
    "DATA_DICTIONARY.md": "484c9a618076b3291756dcf47d551e50173a4394d6e43e0a826bcbe4c4a8582b",
    "MODELSPEC.md": "fc92326279f69db3f6682e7f414d436596e92d2faec37337b337514aeb73ab54",
    "curated/phase3b/phase3b_poss_ge_150.csv": "da31ea8e01e9e0f213edee61fb4918e529883ceb77cf77f2c008da03fdf61db8",
    "curated/phase3e-r2/artifact_hashes.json": "50247fad8a51d314a6cf3933a5341ee8327fca292a06ea95b1c5816bcc3992f2",
    "curated/phase3e-r2/estimator_feature_manifest.json": "4cb3e75bc1c37a56063147b75fdc5def582ad65a704ce282afa96a7897ad4b1c",
    "curated/phase3e-r2/holdout_row_index.csv": "2ba178639cd2f1c4dcba5407a1b040bd993d7cdee31b045a33c6de0583d0304b",
    "curated/phase3e-r2/holdout_staging.csv": "2a281f379258f0f14a59395d656484fe265443217da028e7e2733ae698ffac58",
    "curated/phase3e-r2/preprocessing_state.json": "05730ce4ecd8944e236e791faecf242174272692794477e39d1523f9475d7da3",
    "curated/phase3e-r2/summary.json": "ddb877f2be0f5d6cbe8f14098c7ee3ee7201e04cbc785e93e97ce701d48ba5ba",
    "modeling/phase3d/selection_decision.json": "5ef9663dff906fc04b3a31aec56c0dce1ce9fe4e7cdcc87dbaab95762ff02ca0",
    "modeling/phase3e-r3/evaluation_policy.json": "f5d1e8852693b74d4e82ae505e9d355526a3ddaedc7fbb7ffc7282db3f48ee48",
    "PHASE3D_MODEL_REFINEMENT_REPORT.md": "8b8b08c5c6f247bb9eb91a41457b2014051b92c0ea2556ecc4bfd81ae2e155ec",
    "PHASE3E_R2_HOLDOUT_CONSTRUCTION_REPORT.md": "41468134dc963fc354af3e045ff68e2384e9f278fff68f45120c078f49b36216",
    "PHASE3E_R3_EVALUATION_POLICY.md": "47d123fd4862522665d2f8b202795a1aeb00360ff202236d49e35715fbbfa683",
    "PHASE3E_R4_DEVELOPMENT_HOLDOUT_EVALUATION_REPORT.md": "321eb2de5fe1cf6d2a41b2b24d28f6e80a148546f11ca599433a258fac472342",
    "PHASE3E_R4_PROVENANCE_WAIVER.md": "e12d48f25c6b351dc398126bd50bab2e7cad37c5fbad5b5c1ea505b08e8c4b7f",
    "PHASE3E_R4_2_CORRECTION_ONLY_RECONCILIATION_REPORT.md": "b6853fc6f27ee15e267591fa7170f84a0ecf38f09e8d1e94fb04f008b88d5b81",
}

PAYLOAD_ARTIFACTS = (
    "expanded_training_staging.csv",
    "expanded_training_row_index.csv",
    "expanded_training_estimator_matrix_unscaled.csv",
    "expanded_feature_manifest.json",
    "expanded_preprocessing_state.json",
    "population_diagnostics.json",
    "input_fingerprints.json",
    "final_test_policy.json",
)
BOOKKEEPING_ARTIFACTS = ("artifact_hashes.json", "summary.json")
EXPECTED_OUTPUT_ARTIFACTS = PAYLOAD_ARTIFACTS + BOOKKEEPING_ARTIFACTS

ROW_INDEX_COLUMNS = (
    "target_season",
    "team_id",
    "player_1_id",
    "player_2_id",
    "target_net_rating",
    "pair_possessions",
    "history_status",
    "missing_player_count",
    "player_1_history_profile_season",
    "player_2_history_profile_season",
    "player_1_history_gap",
    "player_2_history_gap",
    "player_1_history_missing",
    "player_2_history_missing",
    "endpoint_exact_250_flag",
    "phase3f_r0_source_population",
)

PROHIBITED_EXACT_FEATURES = {
    "MIN", "TOTAL_MIN", "GP", "POSS", "pair_possessions", "pair_base_minutes",
    "target_net_rating", "target_off_rating_audit", "target_def_rating_audit",
}
PROHIBITED_FEATURE_TOKENS = (
    "shot_", "player_1_", "player_2_", "weight", "usage", "reliability",
    "provenance", "history_status", "missing_player", "source_", "target_",
)

NBA_TEAM_IDS = (
    "1610612737", "1610612738", "1610612739", "1610612740", "1610612741",
    "1610612742", "1610612743", "1610612744", "1610612745", "1610612746",
    "1610612747", "1610612748", "1610612749", "1610612750", "1610612751",
    "1610612752", "1610612753", "1610612754", "1610612755", "1610612756",
    "1610612757", "1610612758", "1610612759", "1610612760", "1610612761",
    "1610612762", "1610612763", "1610612764", "1610612765", "1610612766",
)


class FreezeContractError(RuntimeError):
    """Raised when a mandatory R0 integrity condition fails."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_content_hash(value: Mapping[str, Any], field: str = "deterministic_content_sha256") -> str:
    document = dict(value)
    document.pop(field, None)
    return sha256_bytes(canonical_json_bytes(document))


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _identity_text(value: Any) -> str:
    return str(value).replace("\\", "/").replace("–", "-").lower()


def reject_protected_path(path: Path | str) -> None:
    if PROTECTED_SEASON in _identity_text(path):
        raise FreezeContractError(f"protected-season path rejected before access: {path}")


def reject_protected_season_label(value: Any) -> None:
    if PROTECTED_SEASON in _identity_text(value):
        raise FreezeContractError("protected-season label rejected")


def reject_protected_api_parameters(parameters: Mapping[str, Any]) -> None:
    """Reject a protected season in any future transport parameter set."""
    for key, value in parameters.items():
        if PROTECTED_SEASON in _identity_text(key) or PROTECTED_SEASON in _identity_text(value):
            raise FreezeContractError("protected-season API parameter rejected")


def reject_protected_payload_identity(payload: Mapping[str, Any]) -> None:
    """Reject protected identities before a future response body is parsed."""
    identity_keys = {
        "season", "season_id", "seasonlabel", "relative_path", "request_url",
        "request_identity", "asset_id", "cache_path", "body_path",
    }

    def visit(value: Any, identity_context: bool = False) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_is_identity = identity_context or str(key).lower() in identity_keys
                visit(child, key_is_identity)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child, identity_context)
        elif identity_context and PROTECTED_SEASON in _identity_text(value):
            raise FreezeContractError("protected-season payload identity rejected")

    visit(payload)


@contextmanager
def offline_scope():
    """Fail closed if construction code attempts any network operation."""
    original_socket = socket.socket
    original_connection = socket.create_connection
    original_lookup = socket.getaddrinfo

    def blocked(*_args: Any, **_kwargs: Any) -> None:
        raise FreezeContractError("network access is prohibited during Phase 3F-R0")

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


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    reject_protected_path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise FreezeContractError(f"invalid CSV header: {path}")
        return list(reader.fieldnames), list(reader)


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            raise FreezeContractError("nonfinite value cannot be serialized")
        return repr(float(value))
    return str(value)


def serialize_csv(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> bytes:
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: _csv_value(row.get(column)) for column in columns})
    return buffer.getvalue().encode("utf-8")


def _fingerprint_inputs(project_root: Path) -> dict[str, dict[str, Any]]:
    fingerprints: dict[str, dict[str, Any]] = {}
    for relative, expected in sorted(EXPECTED_INPUT_SHA256.items()):
        path = project_root / relative
        actual = sha256_file(path)
        if actual != expected:
            raise FreezeContractError(
                f"committed prerequisite changed: {relative}; expected={expected}; actual={actual}"
            )
        fingerprints[relative] = {
            "serialized_byte_sha256": actual,
            "bytes": path.stat().st_size,
        }
    return fingerprints


def _season_start(value: str) -> int:
    try:
        first, second = value.split("-")
        start = int(first)
        if int(second) != (start + 1) % 100:
            raise ValueError
        return start
    except (AttributeError, TypeError, ValueError):
        raise FreezeContractError(f"invalid season label: {value!r}") from None


def observation_key(row: Mapping[str, Any]) -> tuple[int, int, int, int]:
    return (
        _season_start(str(row["target_season"])),
        int(row["team_id"]),
        int(row["player_1_id"]),
        int(row["player_2_id"]),
    )


def _finite_number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise FreezeContractError(f"non-numeric {name}") from None
    if not math.isfinite(result):
        raise FreezeContractError(f"nonfinite {name}")
    return result


def validate_history(row: Mapping[str, Any]) -> None:
    target_start = _season_start(str(row["target_season"]))
    for slot in (1, 2):
        missing = str(row[f"player_{slot}_history_missing"])
        profile = str(row.get(f"player_{slot}_history_profile_season", ""))
        gap = str(row.get(f"player_{slot}_history_gap", ""))
        if missing == "1":
            if profile or gap:
                raise FreezeContractError("missing-history slot contains a selected profile")
            continue
        if missing != "0" or not profile or not gap:
            raise FreezeContractError("history slot has an invalid missing/profile contract")
        calculated_gap = target_start - _season_start(profile)
        if calculated_gap != int(float(gap)) or calculated_gap not in range(1, MAX_HISTORY_LOOKBACK + 1):
            raise FreezeContractError("strict prior-history lookback contract failed")


def _swap_player_slots(row: Mapping[str, Any]) -> dict[str, Any]:
    swapped = dict(row)
    for key in row:
        if key.startswith("player_1_"):
            swapped[key] = row.get("player_2_" + key[len("player_1_"):])
        elif key.startswith("player_2_"):
            swapped[key] = row.get("player_1_" + key[len("player_2_"):])
    return swapped


def assemble_expanded_population(project_root: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    historical_columns, historical = read_csv(project_root / HISTORICAL_STAGING)
    development_columns, development = read_csv(project_root / DEVELOPMENT_STAGING)
    if len(historical) != EXPECTED_HISTORICAL_ROWS or len(development) != EXPECTED_DEVELOPMENT_ROWS:
        raise FreezeContractError("expected 27,001 + 2,700 provenance split was not reproduced")
    if {row["target_season"] for row in historical} != set(phase3d.ALLOWED_TARGET_SEASONS):
        raise FreezeContractError("historical target-season population changed")
    if {row["target_season"] for row in development} != {DEVELOPMENT_SEASON}:
        raise FreezeContractError("development staging season mismatch")
    development_teams = {row["team_id"] for row in development}
    if len(development_teams) != 28 or development_teams & set(EXCLUDED_DEVELOPMENT_TEAMS):
        raise FreezeContractError("development team exclusions or retained-team count changed")

    rows: list[dict[str, str]] = []
    for source, source_rows in (("phase3b_historical", historical), ("phase3e_r2_development", development)):
        for original in source_rows:
            row = dict(original)
            row["phase3f_r0_source_population"] = source
            if int(row["player_1_id"]) >= int(row["player_2_id"]):
                raise FreezeContractError("numeric canonical player order failed")
            if _finite_number(row["pair_possessions"], "pair_possessions") < ELIGIBILITY_THRESHOLD:
                raise FreezeContractError("ineligible row entered expanded training")
            _finite_number(row["target_net_rating"], "target_net_rating")
            validate_history(row)
            rows.append(row)
    rows.sort(key=observation_key)
    keys = [observation_key(row) for row in rows]
    if len(rows) != EXPECTED_EXPANDED_ROWS or len(keys) != len(set(keys)):
        raise FreezeContractError("expanded row count or observation-key uniqueness failed")

    columns = list(historical_columns)
    for column in development_columns:
        if column not in columns:
            columns.append(column)
    columns.append("phase3f_r0_source_population")
    return rows, {
        "staging_columns": columns,
        "historical_rows": len(historical),
        "development_rows": len(development),
        "expanded_rows": len(rows),
        "development_retained_teams": len(development_teams),
    }


def _feature_contract() -> tuple[dict[str, Any], tuple[str, ...]]:
    source_manifest = phase3b.feature_manifest()
    names = tuple(phase3d.feature_lists(source_manifest)["no_shot"])
    expected = tuple(
        [f"pair_mean.{field}" for field in phase3b.ESTIMATOR_CONTINUOUS_INPUTS]
        + [f"pair_absolute_difference.{field}" for field in phase3b.ESTIMATOR_CONTINUOUS_INPUTS]
        + ["pair_traded_history_count"]
    )
    if names != expected or len(names) != len(set(names)) or len(names) != 45:
        raise FreezeContractError("frozen ordered 45-feature contract changed")
    violations = [
        name for name in names
        if name in PROHIBITED_EXACT_FEATURES
        or any(token in name.lower() for token in PROHIBITED_FEATURE_TOKENS)
    ]
    if violations:
        raise FreezeContractError(f"prohibited estimator feature(s): {violations}")
    return source_manifest, names


def construct_unscaled_matrix(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    source_manifest, names = _feature_contract()
    slot_medians, unique_profiles = phase3d.phase3c.fit_slot_imputer(rows)
    transformed = [phase3d.transform_row(row, slot_medians, "no_shot", manifest=source_manifest) for row in rows]
    matrix = np.asarray(
        [[np.nan if item[name] is None else item[name] for name in names] for item in transformed],
        dtype=float,
    )
    second_stage = ~np.isfinite(matrix).all(axis=1)
    symmetric_medians: dict[str, float] = {}
    for index, name in enumerate(names):
        finite = matrix[np.isfinite(matrix[:, index]), index]
        if not len(finite):
            raise FreezeContractError(f"no finite expanded-training value for feature: {name}")
        median = float(np.median(finite))
        symmetric_medians[name] = median
        matrix[~np.isfinite(matrix[:, index]), index] = median
    if matrix.shape != (EXPECTED_EXPANDED_ROWS, 45) or not np.isfinite(matrix).all():
        raise FreezeContractError("expanded estimator matrix shape/finiteness failed")

    swap_mismatches = 0
    for row, original in zip(rows, transformed):
        swapped = phase3d.transform_row(_swap_player_slots(row), slot_medians, "no_shot", manifest=source_manifest)
        if original != swapped:
            swap_mismatches += 1
    if swap_mismatches:
        raise FreezeContractError("player-slot exchange changed frozen symmetric features")

    means = np.mean(matrix, axis=0)
    variances = np.var(matrix, axis=0, ddof=0)
    scales = np.sqrt(variances)
    scales[scales == 0.0] = 1.0
    if not np.isfinite(means).all() or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise FreezeContractError("expanded scaler state is invalid")

    state = {
        "version": VERSION,
        "training_target_seasons": list(phase3d.ALLOWED_TARGET_SEASONS) + [DEVELOPMENT_SEASON],
        "training_rows": len(rows),
        "unique_training_player_season_profiles": unique_profiles,
        "feature_order": list(names),
        "player_slot_medians": slot_medians,
        "symmetric_feature_fill_values": symmetric_medians,
        "scaler": {
            "definition": "columnwise population mean and standard deviation matching StandardScaler defaults",
            "ddof": 0,
            "mean": dict(zip(names, map(float, means))),
            "variance": dict(zip(names, map(float, variances))),
            "scale": dict(zip(names, map(float, scales))),
            "zero_variance_scale_policy": "use 1.0",
        },
        "persisted_matrix_representation": "unscaled_after_both_imputation_stages",
        "future_scaling_rule": "apply this one frozen scaler exactly once before the sole final model operation",
        "independent_final_test_scaling_prohibited": True,
        "double_scaling_prohibited": True,
        "expanded_training_evidence_only": True,
        "protected_final_test_values_used": False,
    }
    diagnostics = {
        "second_stage_symmetric_imputation_rows": int(second_stage.sum()),
        "second_stage_by_history": dict(sorted(Counter(
            str(row["history_status"]) for row, required in zip(rows, second_stage) if required
        ).items())),
        "slot_swap_rows_checked": len(rows),
        "slot_swap_feature_values_checked": len(rows) * len(names),
        "slot_swap_mismatches": swap_mismatches,
    }
    return matrix, state, diagnostics


def _history_diagnostics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    status = Counter(str(row["history_status"]) for row in rows)
    selected = Counter()
    gaps = Counter()
    boundary_failures = 0
    for row in rows:
        try:
            validate_history(row)
        except FreezeContractError:
            boundary_failures += 1
        for slot in (1, 2):
            profile = str(row.get(f"player_{slot}_history_profile_season", ""))
            gap = str(row.get(f"player_{slot}_history_gap", ""))
            if profile:
                selected[profile] += 1
            if gap:
                gaps[str(int(float(gap)))] += 1
    return {
        "history_status_rows": {name: status.get(name, 0) for name in ("complete", "one_missing", "both_missing")},
        "selected_profile_seasons_all_slots": dict(sorted(selected.items(), key=lambda item: _season_start(item[0]))),
        "history_lookback_age_all_slots": dict(sorted(gaps.items(), key=lambda item: int(item[0]))),
        "strict_prior_and_three_season_boundary_failures": boundary_failures,
    }


def final_classification(integrity_passed: bool, mae_improvement: float, rmse_improvement: float) -> str:
    if not integrity_passed or not math.isfinite(mae_improvement) or not math.isfinite(rmse_improvement):
        return "INVALID"
    if mae_improvement >= 0.10 and rmse_improvement >= 0.0:
        return "FINAL SCIENTIFIC PASS"
    if mae_improvement <= 0.0:
        return "FINAL SCIENTIFIC FAILURE"
    return "FINAL MIXED RESULT"


def final_test_policy_document(feature_names: Sequence[str]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "policy_kind": "pre-result final-training and final-test freeze",
        "r0_artifact_inventory": list(EXPECTED_OUTPUT_ARTIFACTS),
        "protected_final_test": {
            "season": PROTECTED_SEASON,
            "season_type": SEASON_TYPE,
            "evidence_accessed_during_r0": False,
            "acquisition_executed_during_r0": False,
            "population_constructed_during_r0": False,
        },
        "scientific_record": {
            "original_r4": "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE",
            "r4_1": "CORRECTION-ONLY RECONCILIATION FAILED — PRE-EVIDENCE GIT-STATUS PARSING FAILURE",
            "r4_2": "VALID DEVELOPMENT-HOLDOUT PASS",
            "development_evidence_status": "spent; admitted to final training and never again untouched evaluation evidence",
            "prediction_compression_policy": "report later in product language; no post-hoc calibrator",
        },
        "frozen_model": {
            "estimator": "sklearn.linear_model.Ridge",
            "alpha": RIDGE_ALPHA,
            "target": "direct full-season pair NET_RATING",
            "eligibility": "direct full-season pair POSS >= 150",
            "training_weights": "equal",
            "feature_count": 45,
            "ordered_features": list(feature_names),
            "shot_features": "excluded",
            "exact_250_policy": "normally included unless team-season non-exhaustiveness is proven",
            "history": "nearest strictly prior profile within maximum three-season lookback",
            "history_confidence": {"complete": "standard", "one_missing": "lower", "both_missing": "lower"},
            "calibrator": None,
            "pair_order": "numeric canonical ascending player IDs",
            "symmetric_under_player_slot_exchange": True,
            "prohibited": [
                "HGB", "alternate alpha", "ensemble", "fallback estimator", "target-derived feature",
                "exposure estimator feature", "previous shared-pair-history feature", "post-hoc calibration",
            ],
        },
        "final_test_population": {
            "season": PROTECTED_SEASON,
            "season_type": SEASON_TYPE,
            "target": "directly returned full-season pair NET_RATING",
            "eligibility": "directly returned full-season POSS >= 150",
            "observation_key": ["target_season", "team_id", "player_1_id", "player_2_id"],
            "pair_identity": "numeric canonical unordered pair within team and season",
            "history_priority": [DEVELOPMENT_SEASON, "2023-24", "2022-23"],
            "history_lookback": 3,
            "same-season_complete_player_profile_prohibited": True,
            "previous_shared_pair_feature_prohibited": True,
            "reconstructed_or_approximately_aggregated_target_prohibited": True,
            "non_exhaustive_team_policy": "exclude the full team-season unless a definition-supported direct recovery source exists",
            "exact_250_policy": "flag and investigate; do not automatically exclude",
            "excluded_team_disclosure": ["raw_rows", "eligible_rows", "eligible_possession_cost"],
            "population_decisions_may_use_target_magnitude_or_model_error": False,
            "post_reveal_model_or_threshold_change_prohibited": True,
        },
        "population_readiness_gates": {
            "predictor_evidence_completeness": "all permitted prior-profile assets verified, schema-approved, uniquely keyed, and history selection resolved or explicitly missing",
            "target_evidence_completeness": "all authorized direct full-season Base and Advanced bodies verified and reconciled; no reconstructed rating",
            "team_population_exhaustiveness": "all 30 team-seasons adjudicated; capped responses investigated; every proven non-exhaustive team fully excluded or directly recovered",
            "row_eligibility": "finite direct POSS and NET_RATING, POSS >= 150, valid distinct numeric IDs, no target-dependent inclusion",
            "row_alignment": "unique canonical observation keys, Base/Advanced alignment, exact row order pinned, and 45 finite ordered features",
            "protected_result_reveal": "acquisition and reconciliation audit passes before target/prediction co-opening or prediction generation is authorized",
            "ready_definition": "all six gates pass with immutable evidence, exclusion ledger, fingerprints, and empty execution namespace",
        },
        "future_acquisition": {
            "execute_during_r0": False,
            "authorized_hosts": ["stats.nba.com"],
            "authorized_endpoints": [
                {
                    "endpoint": "teamdashlineups",
                    "season": PROTECTED_SEASON,
                    "season_type": SEASON_TYPE,
                    "group_quantity": 2,
                    "per_mode": "Totals",
                    "measures": ["Base", "Advanced"],
                    "team_ids": list(NBA_TEAM_IDS),
                    "date_windows": "blank full season; bounded windows only after a capped-response investigation authorization",
                },
                {
                    "endpoint": "leaguedashplayerstats",
                    "season": DEVELOPMENT_SEASON,
                    "season_type": SEASON_TYPE,
                    "measure": "Base",
                    "per_modes": ["Per100Possessions", "Totals"],
                    "team_scope": "league",
                    "date_windows": "blank",
                },
            ],
            "headers": "the established accepted NBA Stats browser-origin header set pinned in the authorization package",
            "transport": {
                "trust_env": False,
                "allow_redirects": False,
                "timeout_seconds": 30,
                "request_order": "sequential",
                "minimum_seconds_between_attempts": 1,
                "automatic_retries": 0,
            },
            "durability": {
                "authorization_records": "immutable and written before transport",
                "started_outcome_body_records": "immutable per attempt",
                "failure": "quarantine body/metadata and stop; do not parse or substitute",
                "restart": "refuse if any authorized identity has an ambiguous or completed prior attempt; require reconciliation",
            },
            "scope": "no opportunistic request and no identity outside the authorized package",
            "endpoint_behavior_assumption": "none; later acquisition must verify behavior independently",
            "prediction_authorization": "forbidden until acquisition and reconciliation finish and pass read-only audit",
        },
        "execution": {
            "stage_a": {
                "name": "evidence and implementation integrity",
                "gates": [
                    "verify committed source and policy hashes",
                    "verify expanded-training artifacts and preprocessing hashes",
                    "verify authorized final-test cache fingerprints",
                    "verify final-test completeness and exclusions",
                    "verify row identity, uniqueness, alignment, numeric pair order, feature order, and finiteness",
                    "verify protected targets contributed to neither preprocessing nor model training",
                    "verify exact frozen estimator configuration",
                    "verify empty execution namespace",
                    "verify network prohibition during model execution",
                    "verify no alternate estimator, alpha, calibrator, or prediction path",
                ],
                "failure": "INVALID; stop before any model operation and preserve immutable failure evidence",
            },
            "stage_b": {
                "name": "exactly one final model operation",
                "operations": [
                    "scale the frozen unscaled expanded matrix exactly once with the pinned preprocessing state",
                    "construct and train exactly one Ridge estimator with alpha 3000.0 and equal row weights",
                    "generate exactly one final-test prediction vector",
                    "derive one full-precision unweighted expanded-training target mean and assign one constant baseline vector",
                    "persist predictions only after every pre-result integrity gate passes",
                ],
                "prohibited": "second training run, second prediction run, alternate path, network, or recovery-by-rerun",
                "failure": "INVALID; quarantine partial outputs, preserve events, and do not retry without a new audited authorization",
            },
            "stage_c": {
                "name": "final metrics and classification",
                "operations": "calculate every frozen metric/diagnostic, classify mechanically, and preserve favorable or unfavorable results",
                "failure": "INVALID if a mandatory metric or integrity check fails; preserve all partial results without tuning, calibration, retraining, or rerun",
            },
        },
        "baseline": {
            "definition": "unweighted mean target across all and only the expanded final-training rows",
            "application": "one full-precision constant for every eligible final-test row",
            "protected_target_access": False,
            "r0_numeric_value_exposed": False,
            "future_derivation": "deterministic and hash-pinned before target/prediction reveal",
        },
        "metrics": {
            "primary": [
                "Ridge MAE", "baseline MAE", "baseline-minus-Ridge MAE improvement",
                "Ridge RMSE", "baseline RMSE", "baseline-minus-Ridge RMSE improvement",
            ],
            "diagnostics": [
                "R2", "Spearman correlation", "prediction-minus-target bias", "prediction SD", "target SD",
                "prediction/target SD ratio", "possession-weighted Ridge and baseline MAE/RMSE",
                "complete/one-missing/both-missing counts and errors", "team counts/MAE/RMSE/bias/exposure",
                "leave-one-team-out descriptive diagnostics without retraining", "exact-250 subgroup if applicable",
                "deterministic ten-bin calibration", "lower/upper target-minus-prediction differences",
                "residual relationships with predictions and possessions",
                "comparison with historical chronological validation and spent development results",
            ],
            "diagnostics_override_classification": False,
        },
        "classification": {
            "invalid": "any mandatory integrity stage fails or either required improvement is nonfinite",
            "final_scientific_pass": "MAE improvement >= 0.10 and RMSE improvement >= 0.0",
            "final_scientific_failure": "MAE improvement <= 0.0",
            "final_mixed_result": "all other finite cases",
            "rationale": {
                "mae_0_10": "project-established materiality band, not a universal law",
                "rmse_nonnegative": "protects against worsening large misses",
                "derived_from_protected_results": False,
                "diagnostic_override": False,
            },
        },
        "post_final_test": {
            "pass": "permits consideration of production packaging; does not authorize deployment",
            "mixed": "requires a user decision about usefulness and more cautious product claims",
            "failure": "prohibits presenting the current model as final-test validated",
            "redesign": "converts the opened final-test season to development evidence and requires a later untouched final test for an equivalent claim",
            "quiet_retuning_and_same-target_reevaluation": "prohibited",
        },
    }


def _write_once(path: Path, data: bytes) -> dict[str, Any]:
    if path.exists():
        raise FreezeContractError(f"restart-safe refusal: output already exists: {path}")
    path.write_bytes(data)
    return {"bytes": len(data), "serialized_byte_sha256": sha256_bytes(data)}


def build(project_root: Path | str = ".", output_dir: Path | str = "curated/phase3f-r0") -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    reject_protected_path(project_root)
    reject_protected_path(output_dir)
    if output_dir.exists():
        raise FreezeContractError(f"restart-safe refusal: output directory exists: {output_dir}")

    with offline_scope():
        inputs_before = _fingerprint_inputs(project_root)
        rows, population = assemble_expanded_population(project_root)
        matrix, preprocessing, matrix_diagnostics = construct_unscaled_matrix(rows)
        source_manifest, feature_names = _feature_contract()
        history = _history_diagnostics(rows)
        if history["strict_prior_and_three_season_boundary_failures"]:
            raise FreezeContractError("history boundary verification failed")
        inputs_after = _fingerprint_inputs(project_root)
        if inputs_before != inputs_after:
            raise FreezeContractError("source evidence changed during construction")

        output_dir.mkdir(parents=True, exist_ok=False)
        staging_columns = population.pop("staging_columns")
        index_rows = [{column: row.get(column, "") for column in ROW_INDEX_COLUMNS} for row in rows]
        matrix_rows = [dict(zip(feature_names, map(float, values))) for values in matrix]
        feature_manifest = {
            "version": VERSION,
            "ordered_estimator_features": list(feature_names),
            "feature_count": len(feature_names),
            "feature_family": "Phase 3D/R2 no-shot symmetric",
            "source_feature_manifest_version": source_manifest.get("version"),
            "matrix_representation": "unscaled_after_player-slot_and_symmetric-feature_imputation",
            "slot_exchange_invariant": True,
            "prohibited_fields_absent": True,
            "target_exposure_reliability_provenance_fields_separate": True,
        }
        population_diagnostics = {
            "version": VERSION,
            **population,
            "provenance_split": {
                "phase3b_historical": EXPECTED_HISTORICAL_ROWS,
                "phase3e_r2_development": EXPECTED_DEVELOPMENT_ROWS,
            },
            "development_exclusions": {
                team: {"name": name, "expanded_training_rows": 0}
                for team, name in sorted(EXCLUDED_DEVELOPMENT_TEAMS.items())
            },
            "unique_observation_keys": len(rows),
            "duplicate_observation_keys": 0,
            "history": history,
            "preprocessing": matrix_diagnostics,
            "target_magnitude_used_for_population_or_preprocessing": False,
        }
        input_fingerprints = {
            "version": VERSION,
            "inputs_before": inputs_before,
            "inputs_after": inputs_after,
            "unchanged_during_construction": True,
            "network_access": False,
            "protected_final_test_evidence_accessed": False,
        }
        policy = final_test_policy_document(feature_names)

        payload_bytes = {
            "expanded_training_staging.csv": serialize_csv(rows, staging_columns),
            "expanded_training_row_index.csv": serialize_csv(index_rows, ROW_INDEX_COLUMNS),
            "expanded_training_estimator_matrix_unscaled.csv": serialize_csv(matrix_rows, feature_names),
            "expanded_feature_manifest.json": serialize_json(feature_manifest),
            "expanded_preprocessing_state.json": serialize_json(preprocessing),
            "population_diagnostics.json": serialize_json(population_diagnostics),
            "input_fingerprints.json": serialize_json(input_fingerprints),
            "final_test_policy.json": serialize_json(policy),
        }
        written: dict[str, dict[str, Any]] = {}
        for name in PAYLOAD_ARTIFACTS:
            written[name] = _write_once(output_dir / name, payload_bytes[name])

        artifact_hashes = {
            "version": VERSION,
            "artifact_inventory": list(EXPECTED_OUTPUT_ARTIFACTS),
            "covered_payload_artifacts": list(PAYLOAD_ARTIFACTS),
            "excluded_from_own_manifest": list(BOOKKEEPING_ARTIFACTS),
            "artifacts": {name: written[name] for name in PAYLOAD_ARTIFACTS},
        }
        artifact_hashes["deterministic_content_sha256"] = canonical_content_hash(artifact_hashes)
        manifest_info = _write_once(output_dir / "artifact_hashes.json", serialize_json(artifact_hashes))
        summary = {
            "version": VERSION,
            "classification": "Phase 3F-R0 final-test pipeline frozen; ready for read-only audit",
            "committed_head_at_start": COMMITTED_HEAD,
            "required_branch": REQUIRED_BRANCH,
            "expanded_training_rows": EXPECTED_EXPANDED_ROWS,
            "historical_rows": EXPECTED_HISTORICAL_ROWS,
            "development_rows": EXPECTED_DEVELOPMENT_ROWS,
            "feature_count": 45,
            "matrix_representation": "unscaled",
            "artifact_inventory": list(EXPECTED_OUTPUT_ARTIFACTS),
            "artifact_manifest_serialized_byte_sha256": manifest_info["serialized_byte_sha256"],
            "artifact_manifest_content_sha256": artifact_hashes["deterministic_content_sha256"],
            "network_access": False,
            "protected_final_test_evidence_accessed": False,
            "estimator_constructed": False,
            "model_trained": False,
            "prediction_generated": False,
            "production_model_serialized": False,
        }
        summary["deterministic_content_sha256"] = canonical_content_hash(summary)
        _write_once(output_dir / "summary.json", serialize_json(summary))
        actual_inventory = tuple(sorted(path.name for path in output_dir.iterdir()))
        if actual_inventory != tuple(sorted(EXPECTED_OUTPUT_ARTIFACTS)):
            raise FreezeContractError("generated artifact inventory mismatch")
        return summary
