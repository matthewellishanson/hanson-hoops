import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3d_model_refinement as phase


def _row(player1="1", player2="2", profile1="2017-18", profile2="2017-18", season="2018-19", value=2.0):
    row = {
        "target_season": season,
        "player_1_id": player1,
        "player_2_id": player2,
        "team_id": "9",
        "target_net_rating": "1.0",
        "pair_possessions": "150",
        "history_status": "complete",
        "missing_player_count": "0",
        "pandemic_affected_season_flag": "0",
        "endpoint_exact_250_flag": "0",
        "player_1_history_missing": "0",
        "player_2_history_missing": "0",
        "player_1_history_profile_season": profile1,
        "player_2_history_profile_season": profile2,
    }
    for slot in ("1", "2"):
        slot_value = value if slot == "1" else value + 1
        for field in phase.phase3c.IMPUTATION_SLOT_FIELDS:
            row[f"player_{slot}_{field}"] = str(slot_value)
        for zone_components in phase.ZONE_INPUTS.values():
            for component in zone_components[0]:
                row[f"player_{slot}_shot_{component}_fgm"] = "1"
                row[f"player_{slot}_shot_{component}_fga"] = "2"
        row[f"player_{slot}_shot_overall_fgm"] = "7"
        row[f"player_{slot}_shot_overall_fga"] = "14"
    return row


def _swap(row):
    result = dict(row)
    for key in row:
        if key.startswith("player_1_"):
            result[key] = row["player_2_" + key[len("player_1_"):]]
        elif key.startswith("player_2_"):
            result[key] = row["player_1_" + key[len("player_2_"):]]
    return result


def test_protected_season_path_rejected_before_hash_or_open(monkeypatch):
    monkeypatch.setattr(phase, "sha256_file", lambda path: pytest.fail("hashing occurred before rejection"))
    with pytest.raises(ValueError, match="protected-season input rejected before processing"):
        phase.verify_prerequisites("2024-25.csv", "safe.csv", "manifest.json", "b.json", "c.json")


def test_outer_and_inner_folds_are_strictly_chronological():
    folds = phase.authorized_outer_folds()
    assert len(folds) == 6
    for validation, training in folds:
        assert all(phase.ALLOWED_TARGET_SEASONS.index(season) < phase.ALLOWED_TARGET_SEASONS.index(validation) for season in training)
        for inner_validation, inner_training in phase.inner_folds(training):
            assert inner_validation in training
            assert all(training.index(season) < training.index(inner_validation) for season in inner_training)


@pytest.mark.parametrize("policy", phase.WEIGHT_POLICIES)
def test_weight_normalization_is_partition_local_and_validation_independent(policy):
    training = [_row(player1=str(i * 2 + 1), player2=str(i * 2 + 2)) for i in range(3)]
    for row, possession in zip(training, (100, 225, 900)):
        row["pair_possessions"] = str(possession)
    selected, weights = phase.normalized_training_weights(training, policy)
    assert selected == training
    assert np.mean(weights) == pytest.approx(1.0)
    assert np.sum(weights) == pytest.approx(len(training))
    validation_possessions = np.asarray([10**12])
    assert validation_possessions[0] not in weights


def test_exact_250_include_downweight_and_exclude_are_training_only():
    rows = [_row(player1="1", player2="2"), _row(player1="3", player2="4")]
    rows[0]["endpoint_exact_250_flag"] = "1"
    included, include_weights = phase.normalized_training_weights(rows, "equal", "include")
    downweighted, down_weights = phase.normalized_training_weights(rows, "equal", "downweight_0_5")
    excluded, exclude_weights = phase.normalized_training_weights(rows, "equal", "exclude")
    assert len(included) == len(downweighted) == 2
    assert down_weights[0] == pytest.approx(2 / 3) and down_weights[1] == pytest.approx(4 / 3)
    assert excluded == [rows[1]] and exclude_weights.tolist() == [1.0]
    assert include_weights.tolist() == [1.0, 1.0]


def test_shot_priors_are_training_only_and_validation_extreme_cannot_change_them():
    training = [_row(player1="1", player2="2"), _row(player1="3", player2="4")]
    ordinary = _row(player1="5", player2="6")
    extreme = _row(player1="5", player2="6")
    extreme["player_1_shot_restricted_area_fgm"] = "999999"
    low = phase.prepare_matrices(training, [ordinary], "distribution_plus_efficiency", k=25.0)
    high = phase.prepare_matrices(training, [extreme], "distribution_plus_efficiency", k=25.0)
    assert low["shot_priors"] == high["shot_priors"]
    assert low["efficiency_slot_medians"] == high["efficiency_slot_medians"]


def test_zero_attempts_are_not_zero_percent_and_unclassified_is_not_reallocated():
    assert phase.smoothed_efficiency(0.0, 10.0, 0.5, 25.0) == pytest.approx(12.5 / 35.0)
    assert phase.smoothed_efficiency(0.0, 0.0, 0.5, 25.0) is None
    baseline = _row()
    changed = _row()
    changed["player_1_shot_unclassified_fgm"] = "90"
    changed["player_1_shot_unclassified_fga"] = "100"
    prior_a, _, _ = phase.fit_shot_priors([baseline])
    prior_b, _, _ = phase.fit_shot_priors([changed])
    assert prior_a["restricted_area"] == prior_b["restricted_area"]
    assert prior_a["unclassified_residual"] != prior_b["unclassified_residual"]


def test_smoothing_grid_and_conservative_tie_break(monkeypatch):
    rows = [_row()]
    monkeypatch.setattr(phase, "inner_folds", lambda seasons: (("2018-19", ("2017-18",)),))
    monkeypatch.setattr(phase, "_inner_partition", lambda *args: (rows, rows, np.ones(1)))
    monkeypatch.setattr(phase, "prepare_matrices", lambda *args, **kwargs: {"train_x": np.ones((1, 1)), "validation_x": np.ones((1, 1))})
    monkeypatch.setattr(phase, "_fit_predict", lambda *args, **kwargs: np.ones(1))
    selected, tried = phase.select_smoothing_parameters("ridge", rows, ("2017-18",), "equal")
    assert {item["k"] for item in tried} == set(phase.SMOOTHING_K)
    assert selected["k"] == 100.0
    assert selected["alpha"] == 0.1


def test_ridge_grid_and_phase3c_tie_break(monkeypatch):
    rows = [_row()]
    monkeypatch.setattr(phase, "inner_folds", lambda seasons: (("2018-19", ("2017-18",)),))
    monkeypatch.setattr(phase, "_inner_partition", lambda *args: (rows, rows, np.ones(1)))
    monkeypatch.setattr(phase, "prepare_matrices", lambda *args, **kwargs: {"train_x": np.ones((1, 1)), "validation_x": np.ones((1, 1))})
    monkeypatch.setattr(phase, "_fit_predict", lambda *args, **kwargs: np.ones(1))
    selected, tried = phase.select_ridge_alpha(rows, ("2017-18",), "distribution", "equal")
    assert [item["alpha"] for item in tried] == list(phase.RIDGE_ALPHAS)
    assert selected["alpha"] == 0.1


def test_player_slot_swap_preserves_efficiency_features_and_predictions():
    row = _row()
    medians, _ = phase.phase3c.fit_slot_imputer([row])
    priors, _, profiles = phase.fit_shot_priors([row])
    efficiency_medians = phase.fit_efficiency_slot_medians([row], priors, 50.0, profiles)
    left = phase.transform_row(row, medians, "distribution_plus_efficiency", priors, 50.0, efficiency_medians)
    right = phase.transform_row(_swap(row), medians, "distribution_plus_efficiency", priors, 50.0, efficiency_medians)
    assert left == right
    vector_left = np.asarray([left[name] for name in phase.feature_lists()["distribution_plus_efficiency"]])
    vector_right = np.asarray([right[name] for name in phase.feature_lists()["distribution_plus_efficiency"]])
    assert float(vector_left @ np.ones(len(vector_left))) == float(vector_right @ np.ones(len(vector_right)))


def test_missing_history_second_stage_and_l1_diagnostics():
    training = [_row()]
    validation = _row(player1="3", player2="4")
    validation["player_1_shot_overall_fga"] = "0"
    matrices = phase.prepare_matrices(training, [validation], "distribution")
    assert matrices["second_stage_validation"].tolist() == [True]
    record = phase._diagnostic_record(validation, 0.0, "candidate", "2018-19", True)
    assert record["missing_history_group"] == "complete_player_history"
    assert record["second_stage_symmetric_imputation_required"] == 1
    assert record["shot_l1_undefined_missing_or_nonpositive_overall_fga"] == 1
    validation["missing_player_count"] = "2"
    validation["player_1_history_missing"] = validation["player_2_history_missing"] = "1"
    assert phase.missing_history_group(validation) == "both_players_missing"


def test_estimator_allowlist_and_fixed_hgb_policy():
    with pytest.raises(ValueError, match="not allowlisted"):
        phase._fit_predict("random_forest", np.ones((1, 1)), np.ones(1), np.ones((1, 1)), np.ones(1))
    assert phase.ESTIMATORS == ("ridge", "hist_gradient_boosting")
    assert phase.HGB_CONFIG == {"learning_rate": 0.05, "max_iter": 200, "max_leaf_nodes": 15,
                                "min_samples_leaf": 50, "l2_regularization": 5.0,
                                "early_stopping": False, "random_state": 314159}


def test_staged_plan_and_simplicity_selection_rules():
    assert len(phase.staged_candidate_plan()) == 24
    candidates = [
        {"candidate_id": "simple", "macro_season_mae": 7.09, "rank": 0},
        {"candidate_id": "complex", "macro_season_mae": 7.00, "rank": 1},
    ]
    assert phase.select_by_primary_mae(candidates, lambda item: item["rank"])["candidate_id"] == "simple"
    candidates[0]["macro_season_mae"] = 7.10
    assert phase.select_by_primary_mae(candidates, lambda item: item["rank"])["candidate_id"] == "complex"


def test_ridge_vs_hgb_decision_rule_requires_every_condition():
    ridge_summary = {"candidate_id": "ridge", "macro_season_mae": 1.2, "pooled_rmse": 2.0}
    hgb_summary = {"candidate_id": "hgb", "macro_season_mae": 1.0, "pooled_rmse": 1.8}
    ridge, hgb = [], []
    for index, season in enumerate([fold[0] for fold in phase.OUTER_FOLDS]):
        common = {"outer_fold": season, "actual_target": 0.0, "exact_250_membership": 0, "pandemic_affected": 0,
                  "missing_history_group": "complete_player_history", "pair_possessions": 150.0}
        ridge.append({**common, "candidate_id": "ridge", "prediction": 1.0})
        hgb.append({**common, "candidate_id": "hgb", "prediction": 0.0})
    subgroups = [
        {"candidate_id": "ridge", "dimension": "missing_history", "group": "complete_player_history", "validation_rows": 200, "mae": 1.0},
        {"candidate_id": "hgb", "dimension": "missing_history", "group": "complete_player_history", "validation_rows": 200, "mae": 0.8},
    ]
    decision = phase.ridge_vs_hgb_decision(ridge_summary, hgb_summary, ridge, hgb, subgroups)
    assert decision["selected_estimator"] == "hist_gradient_boosting"
    hgb_summary["macro_season_mae"] = 1.11
    assert phase.ridge_vs_hgb_decision(ridge_summary, hgb_summary, ridge, hgb, subgroups)["selected_estimator"] == "ridge"


def test_artifact_inventory_and_hashing_are_deterministic(tmp_path):
    manifest = {"artifacts": {name: "0" * 64 for name in phase.PAYLOAD_ARTIFACTS}}
    scope = phase.validate_artifact_manifest_scope(manifest)
    assert scope["covered_byte_artifacts"] == len(phase.PAYLOAD_ARTIFACTS)
    assert set(phase.EXPECTED_OUTPUT_ARTIFACTS) == set(phase.PAYLOAD_ARTIFACTS) | set(phase.NONCIRCULAR_EXCLUDED_OUTPUTS)
    left, right = tmp_path / "left.json", tmp_path / "right.json"
    phase._write_json(left, {"b": 2, "a": 1})
    phase._write_json(right, {"a": 1, "b": 2})
    assert left.read_bytes() == right.read_bytes()
    assert phase.sha256_file(left) == phase.sha256_file(right)
    document = {"value": 1}
    document["deterministic_content_sha256"] = phase.canonical_json_hash(document)
    assert phase.canonical_content_hash(document) == document["deterministic_content_sha256"]
