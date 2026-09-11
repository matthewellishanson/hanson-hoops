import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3c_baseline_modeling as phase


ROOT = Path(__file__).parents[1]


def _row(player1="1", player2="2", profile1="2017-18", profile2="2017-18", season="2018-19", value=2.0):
    row = {"target_season": season, "player_1_id": player1, "player_2_id": player2,
           "team_id": "9", "target_net_rating": "1.0", "pair_possessions": "150",
           "history_status": "complete", "pandemic_affected_season_flag": "0", "endpoint_exact_250_flag": "0",
           "player_1_history_profile_season": profile1, "player_2_history_profile_season": profile2}
    for slot in ("1", "2"):
        for field in phase.IMPUTATION_SLOT_FIELDS:
            row[f"player_{slot}_{field}"] = str(value if slot == "1" else value + 1)
    return row


def _swap(row):
    result = dict(row)
    for key in list(row):
        if key.startswith("player_1_"):
            result[key] = row["player_2_" + key[len("player_1_"):]]
        elif key.startswith("player_2_"):
            result[key] = row["player_1_" + key[len("player_2_"):]]
    return result


def test_phase3b_exact_inputs_and_no_network_contract():
    curated = ROOT / "curated" / "phase3b"
    assert phase.sha256_file(curated / "phase3b_poss_ge_150.csv") == phase.PRIMARY_SHA256
    assert phase.sha256_file(curated / "phase3b_feature_manifest.json") == phase.MANIFEST_SHA256
    summary = json.loads((curated / "phase3b_curation_summary.json").read_text())
    assert summary["deterministic_content_sha256"] == phase.SUMMARY_CONTENT_SHA256
    assert phase.HGB_CONFIG["random_state"] == 314159


def test_authorized_target_season_enforcement_and_outer_boundaries():
    with pytest.raises(ValueError, match="unauthorized"):
        phase.validate_target_seasons([{"target_season": "2024-25"}])
    folds = phase.authorized_outer_folds()
    assert [fold[0] for fold in folds] == list(phase.ALLOWED_TARGET_SEASONS[4:])
    assert folds[0][1] == phase.ALLOWED_TARGET_SEASONS[:4]
    assert folds[-1][1] == phase.ALLOWED_TARGET_SEASONS[:9]
    assert phase.inner_folds(folds[1][1]) == (("2017-18", phase.ALLOWED_TARGET_SEASONS[:3]), ("2018-19", phase.ALLOWED_TARGET_SEASONS[:4]))


def test_unique_profile_medians_are_not_pair_frequency_weighted_and_slots_share_values():
    common = _row(player1="11", player2="12", value=1)
    frequent = [_row(player1="11", player2=str(100 + index), value=1) for index in range(20)]
    rare = _row(player1="22", player2="23", value=9)
    for slot in ("1", "2"):
        rare[f"player_{slot}_age"] = "9"
        common[f"player_{slot}_age"] = "1"
        for row in frequent:
            row[f"player_{slot}_age"] = "1"
    medians, profiles = phase.fit_slot_imputer([common, *frequent, rare])
    assert profiles == 24
    assert medians["age"] == 1.0  # 20 repeated pair appearances do not enter the profile sample.
    missing = _row(profile1="", profile2="", value=4)
    missing["player_1_age"] = missing["player_2_age"] = ""
    left, right = phase.impute_slots(missing, medians)
    assert left["age"] == right["age"] == medians["age"]


def test_training_only_imputation_scaling_and_transform_order_leakage_sentinel():
    train = [_row(player1="1", player2="2", value=1), _row(player1="3", player2="4", value=3)]
    valid_low = [_row(player1="5", player2="6", value=5)]
    valid_extreme = [_row(player1="5", player2="6", value=10**9)]
    features = phase.feature_lists()[0]
    _, low_x, low_medians, _, scaler_low, _ = phase.fit_preprocessor(train, valid_low, features, scale=True)
    _, extreme_x, extreme_medians, _, scaler_extreme, _ = phase.fit_preprocessor(train, valid_extreme, features, scale=True)
    assert low_medians == extreme_medians
    assert np.array_equal(scaler_low.mean_, scaler_extreme.mean_)
    assert not np.array_equal(low_x, extreme_x)


def test_player_swap_symmetry_predictor_allowlist_and_shot_ablation():
    row = _row(value=2)
    medians, _ = phase.fit_slot_imputer([row])
    enabled, no_shot, shot = phase.feature_lists()
    assert len(enabled) == 52 and len(no_shot) == 45 and len(shot) == 7
    assert set(enabled) - set(no_shot) == set(shot)
    assert phase.transform_row(row, medians, enabled) == phase.transform_row(_swap(row), medians, enabled)
    assert all("player_" not in item and "target_" not in item and "possessions" not in item for item in enabled)


def test_metrics_calibration_and_audit_prediction_shape_are_deterministic():
    metrics = phase.metric_values([0, 2], [1, 1])
    assert metrics["mae"] == 1 and metrics["rmse"] == 1 and metrics["mean_signed_error_bias"] == 0
    rows = [phase._prediction_record(_row(player1=str(i * 2 + 1), player2=str(i * 2 + 2)), i, "ridge_shot_enabled", "2018-19") for i in range(3)]
    assert list(rows[0]) == ["target_season", "team_id", "player_1_id", "player_2_id", "actual_target", "prediction", "model_variant", "outer_fold", "history_status", "pandemic_flag", "exact_250_flag"]
    calibration = phase.calibration_rows(rows, bins=10)
    assert len(calibration) == 3 and all(item["used_bins"] == 3 for item in calibration)


def test_hgb_configuration_and_identical_ablation_hyperparameters():
    assert phase.HGB_CONFIG == {"learning_rate": .05, "max_iter": 200, "max_leaf_nodes": 15,
                                "min_samples_leaf": 50, "l2_regularization": 5.0,
                                "early_stopping": False, "random_state": 314159}
    assert tuple(phase.VARIANTS) == ("training_mean_baseline", "ridge_shot_enabled", "ridge_no_shot", "hist_gradient_boosting_shot_enabled", "hist_gradient_boosting_no_shot")


def test_artifact_manifest_scope_and_summary_hash_policy_are_non_circular():
    output = ROOT / "modeling" / "phase3c"
    manifest = json.loads((output / "artifact_hashes.json").read_text())
    scope = phase.validate_artifact_manifest_scope(manifest)
    assert scope["covered_byte_artifacts"] == 8
    assert set(scope["explicitly_excluded_outputs"]) == {"artifact_hashes.json", "summary.json"}
    assert set(phase.EXPECTED_OUTPUT_ARTIFACTS) == set(manifest["artifacts"]) | set(scope["explicitly_excluded_outputs"])
    summary = json.loads((output / "summary.json").read_text())
    assert phase.canonical_content_hash(summary) == summary["deterministic_content_sha256"]
    assert phase.sha256_file(output / "summary.json") == "e10e233a435a38d13d66c65bb77a9a325b0f03bee26d77edf87741f173990d55"
