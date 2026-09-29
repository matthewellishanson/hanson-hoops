import ast
import csv
import json
import math
import socket
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3f_r0_final_test_freeze as phase


PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def independent_builds(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase3f_r0")
    left, right = root / "left", root / "right"
    first = phase.build(PROJECT, left)
    second = phase.build(PROJECT, right)
    return left, right, first, second


def _read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def test_protected_season_paths_parameters_labels_and_payloads_fail_before_access(monkeypatch):
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("protected path was opened"))
    with pytest.raises(phase.FreezeContractError, match="protected-season path"):
        phase.read_bytes(Path("evidence/2025-26/final.json"))
    with pytest.raises(phase.FreezeContractError, match="label"):
        phase.reject_protected_season_label("2025-26")
    with pytest.raises(phase.FreezeContractError, match="API parameter"):
        phase.reject_protected_api_parameters({"Season": "2025-26", "MeasureType": "Advanced"})
    with pytest.raises(phase.FreezeContractError, match="payload identity"):
        phase.reject_protected_payload_identity({"request_identity": {"season": "2025-26"}})


def test_offline_scope_blocks_network():
    with phase.offline_scope():
        with pytest.raises(phase.FreezeContractError, match="network access"):
            socket.getaddrinfo("example.com", 443)


def test_exact_population_provenance_exclusions_keys_and_eligibility(independent_builds):
    left, _, summary, _ = independent_builds
    diagnostics = json.loads((left / "population_diagnostics.json").read_text(encoding="utf-8"))
    _, rows = _read_csv(left / "expanded_training_row_index.csv")
    assert summary["expanded_training_rows"] == len(rows) == 29701
    assert diagnostics["provenance_split"] == {
        "phase3b_historical": 27001,
        "phase3e_r2_development": 2700,
    }
    development = [row for row in rows if row["phase3f_r0_source_population"] == "phase3e_r2_development"]
    assert len(development) == 2700
    assert len({row["team_id"] for row in development}) == 28
    assert not ({"1610612755", "1610612766"} & {row["team_id"] for row in development})
    keys = [tuple(row[name] for name in ("target_season", "team_id", "player_1_id", "player_2_id")) for row in rows]
    assert len(keys) == len(set(keys))
    assert all(int(row["player_1_id"]) < int(row["player_2_id"]) for row in rows)
    assert all(float(row["pair_possessions"]) >= 150 for row in rows)
    assert all(math.isfinite(float(row["target_net_rating"])) for row in rows)


def test_strict_prior_history_three_season_boundary_and_counts(independent_builds):
    left, _, _, _ = independent_builds
    diagnostics = json.loads((left / "population_diagnostics.json").read_text(encoding="utf-8"))["history"]
    assert diagnostics["strict_prior_and_three_season_boundary_failures"] == 0
    assert diagnostics["history_status_rows"] == {
        "complete": 22886,
        "one_missing": 6229,
        "both_missing": 586,
    }
    assert diagnostics["history_lookback_age_all_slots"] == {"1": 51242, "2": 592, "3": 167}
    _, rows = _read_csv(left / "expanded_training_row_index.csv")
    development = [row for row in rows if row["target_season"] == "2024-25"]
    selected = Counter(
        row[f"player_{slot}_history_profile_season"]
        for row in development for slot in (1, 2)
        if row[f"player_{slot}_history_profile_season"]
    )
    assert selected == Counter({"2023-24": 4713, "2022-23": 69, "2021-22": 19})
    assert all(row[f"player_{slot}_history_profile_season"] != "2024-25" for row in development for slot in (1, 2))


def test_exact_ordered_feature_contract_matrix_purity_and_symmetry(independent_builds):
    left, _, _, _ = independent_builds
    manifest = json.loads((left / "expanded_feature_manifest.json").read_text(encoding="utf-8"))
    expected = (
        [f"pair_mean.{field}" for field in phase.phase3b.ESTIMATOR_CONTINUOUS_INPUTS]
        + [f"pair_absolute_difference.{field}" for field in phase.phase3b.ESTIMATOR_CONTINUOUS_INPUTS]
        + ["pair_traded_history_count"]
    )
    assert manifest["ordered_estimator_features"] == expected
    assert len(expected) == len(set(expected)) == 45
    columns, rows = _read_csv(left / "expanded_training_estimator_matrix_unscaled.csv")
    assert columns == expected and len(rows) == 29701
    assert all(not any(token in name.lower() for token in phase.PROHIBITED_FEATURE_TOKENS) for name in columns)
    assert not set(columns) & phase.PROHIBITED_EXACT_FEATURES
    assert all(math.isfinite(float(value)) for row in rows for value in row.values())
    diagnostics = json.loads((left / "population_diagnostics.json").read_text(encoding="utf-8"))["preprocessing"]
    assert diagnostics["slot_swap_rows_checked"] == 29701
    assert diagnostics["slot_swap_feature_values_checked"] == 29701 * 45
    assert diagnostics["slot_swap_mismatches"] == 0


def test_expanded_training_only_preprocessing_and_no_double_scaling(independent_builds):
    left, _, _, _ = independent_builds
    state = json.loads((left / "expanded_preprocessing_state.json").read_text(encoding="utf-8"))
    manifest = json.loads((left / "expanded_feature_manifest.json").read_text(encoding="utf-8"))
    assert state["training_rows"] == 29701
    assert state["training_target_seasons"] == list(phase.phase3d.ALLOWED_TARGET_SEASONS) + ["2024-25"]
    assert "2025-26" not in state["training_target_seasons"]
    assert state["expanded_training_evidence_only"] is True
    assert state["protected_final_test_values_used"] is False
    assert state["persisted_matrix_representation"] == "unscaled_after_both_imputation_stages"
    assert manifest["matrix_representation"].startswith("unscaled_")
    assert state["double_scaling_prohibited"] is True
    assert state["independent_final_test_scaling_prohibited"] is True
    assert state["scaler"]["ddof"] == 0
    assert state["feature_order"] == manifest["ordered_estimator_features"]
    assert set(state["scaler"]["mean"]) == set(state["feature_order"])
    assert all(value > 0 and math.isfinite(value) for value in state["scaler"]["scale"].values())


def test_two_builds_are_byte_identical_and_inventory_is_consistent(independent_builds):
    left, right, first, second = independent_builds
    expected = set(phase.EXPECTED_OUTPUT_ARTIFACTS)
    assert first == second
    assert {path.name for path in left.iterdir()} == expected
    assert {path.name for path in right.iterdir()} == expected
    for name in expected:
        assert (left / name).read_bytes() == (right / name).read_bytes()
    hashes = json.loads((left / "artifact_hashes.json").read_text(encoding="utf-8"))
    policy = json.loads((left / "final_test_policy.json").read_text(encoding="utf-8"))
    assert hashes["artifact_inventory"] == list(phase.EXPECTED_OUTPUT_ARTIFACTS)
    assert policy["r0_artifact_inventory"] == list(phase.EXPECTED_OUTPUT_ARTIFACTS)
    assert set(hashes["artifacts"]) == set(phase.PAYLOAD_ARTIFACTS)
    for name, identity in hashes["artifacts"].items():
        assert phase.sha256_file(left / name) == identity["serialized_byte_sha256"]


def test_source_evidence_is_hash_pinned_and_unchanged(independent_builds):
    left, _, _, _ = independent_builds
    evidence = json.loads((left / "input_fingerprints.json").read_text(encoding="utf-8"))
    assert evidence["unchanged_during_construction"] is True
    assert evidence["inputs_before"] == evidence["inputs_after"]
    assert evidence["network_access"] is False
    assert evidence["protected_final_test_evidence_accessed"] is False
    assert set(evidence["inputs_before"]) == set(phase.EXPECTED_INPUT_SHA256)


@pytest.mark.parametrize(
    ("integrity", "mae", "rmse", "expected"),
    [
        (False, 1.0, 1.0, "INVALID"),
        (True, float("nan"), 1.0, "INVALID"),
        (True, 0.10, 0.0, "FINAL SCIENTIFIC PASS"),
        (True, 0.099999, 1.0, "FINAL MIXED RESULT"),
        (True, 0.10, -0.000001, "FINAL MIXED RESULT"),
        (True, 0.0, 1.0, "FINAL SCIENTIFIC FAILURE"),
        (True, -0.000001, 1.0, "FINAL SCIENTIFIC FAILURE"),
    ],
)
def test_future_final_classification_boundaries(integrity, mae, rmse, expected):
    assert phase.final_classification(integrity, mae, rmse) == expected


def test_policy_freezes_acquisition_population_execution_metrics_and_post_result_rules(independent_builds):
    left, _, _, _ = independent_builds
    policy = json.loads((left / "final_test_policy.json").read_text(encoding="utf-8"))
    assert policy["scientific_record"] == {
        "original_r4": "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE",
        "r4_1": "CORRECTION-ONLY RECONCILIATION FAILED — PRE-EVIDENCE GIT-STATUS PARSING FAILURE",
        "r4_2": "VALID DEVELOPMENT-HOLDOUT PASS",
        "development_evidence_status": "spent; admitted to final training and never again untouched evaluation evidence",
        "prediction_compression_policy": "report later in product language; no post-hoc calibrator",
    }
    assert policy["frozen_model"]["alpha"] == 3000.0
    assert policy["frozen_model"]["estimator"] == "sklearn.linear_model.Ridge"
    assert policy["future_acquisition"]["execute_during_r0"] is False
    assert policy["future_acquisition"]["transport"] == {
        "trust_env": False,
        "allow_redirects": False,
        "timeout_seconds": 30,
        "request_order": "sequential",
        "minimum_seconds_between_attempts": 1,
        "automatic_retries": 0,
    }
    assert len(policy["population_readiness_gates"]) == 7
    assert set(policy["execution"]) == {"stage_a", "stage_b", "stage_c"}
    assert len(policy["metrics"]["primary"]) == 6
    assert policy["metrics"]["diagnostics_override_classification"] is False
    assert policy["classification"]["rationale"]["derived_from_protected_results"] is False
    assert policy["post_final_test"]["quiet_retuning_and_same-target_reevaluation"] == "prohibited"


def test_r0_source_has_no_model_operation_estimator_construction_or_network_client():
    paths = [
        PROJECT / "src/pair_fit_v2/phase3f_r0_final_test_freeze.py",
        PROJECT / "src/pair_fit_v2/phase3f_r0_cli.py",
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert ".fit(" not in source
        assert ".predict(" not in source
        assert "from sklearn" not in source and "import sklearn" not in source
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
            and (node.func.id if isinstance(node.func, ast.Name) else node.func.attr)
            in {"Ridge", "HistGradientBoostingRegressor"}
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and any(alias.name.split(".")[0] in {"requests", "httpx", "urllib", "http"} for alias in node.names)
            for node in ast.walk(tree)
        )


def test_git_ignore_and_prohibited_artifact_absence(independent_builds):
    left, _, _, _ = independent_builds
    result = subprocess.run(
        ["git", "check-ignore", "-q", "curated/phase3f-r0/ignore-probe"],
        cwd=PROJECT,
        check=False,
    )
    assert result.returncode == 0
    prohibited_suffixes = {".joblib", ".pkl", ".pickle", ".parquet", ".feather", ".duckdb"}
    assert not [path for path in left.iterdir() if path.suffix.lower() in prohibited_suffixes]
    assert not [path for path in left.iterdir() if "model" in path.name.lower()]
