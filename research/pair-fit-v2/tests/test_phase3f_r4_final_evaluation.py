from __future__ import annotations

import json
import ast
from pathlib import Path

import numpy as np
import pytest

from pair_fit_v2 import phase3f_r4_final_evaluation as phase


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_metric_formulas_signs_ties_and_population_dispersion():
    prediction = np.asarray([1.0, 1.0, 4.0, 8.0])
    target = np.asarray([0.0, 2.0, 4.0, 10.0])
    metrics, nulls = phase.metric_set(prediction, target)
    error = prediction - target
    assert metrics["mae"] == pytest.approx(np.mean(np.abs(error)))
    assert metrics["rmse"] == pytest.approx(np.sqrt(np.mean(error**2)))
    assert metrics["bias"] == pytest.approx(np.mean(error))
    assert metrics["prediction_std"] == pytest.approx(np.std(prediction, ddof=0))
    assert metrics["target_std"] == pytest.approx(np.std(target, ddof=0))
    assert metrics["spearman"] == pytest.approx(np.corrcoef([1.5, 1.5, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0])[0, 1])
    assert nulls == {}


def test_baseline_and_improvement_conventions():
    training_target = np.asarray([-3.0, 1.0, 8.0])
    target = np.asarray([0.0, 4.0])
    ridge = np.asarray([1.0, 5.0])
    baseline = np.full(len(target), float(np.mean(training_target)))
    ridge_metrics = phase.metric_set(ridge, target)[0]
    baseline_metrics = phase.metric_set(baseline, target)[0]
    assert baseline.tolist() == [2.0, 2.0]
    assert baseline_metrics["mae"] - ridge_metrics["mae"] == pytest.approx(1.0)
    assert baseline_metrics["rmse"] - ridge_metrics["rmse"] > 0.0


def test_weighted_metrics_and_residual_definitions():
    prediction = np.asarray([2.0, 1.0, 8.0])
    target = np.asarray([1.0, 3.0, 5.0])
    weights = np.asarray([1.0, 2.0, 3.0])
    wmae, wrmse = phase.weighted_errors(prediction, target, weights)
    error = prediction - target
    assert wmae == pytest.approx(np.sum(weights * np.abs(error)) / np.sum(weights))
    assert wrmse == pytest.approx(np.sqrt(np.sum(weights * error**2) / np.sum(weights)))
    residual = phase.residual_relationships(prediction, target, weights)
    assert residual["residual_sign_convention"] == "target minus prediction"
    assert residual["residual_mean"] == pytest.approx(np.mean(target - prediction))
    assert residual["residual_variance"] == pytest.approx(np.var(target - prediction, ddof=0))


def test_null_handling_for_constant_vectors():
    metrics, nulls = phase.metric_set([2.0, 2.0, 2.0], [1.0, 1.0, 1.0])
    assert metrics["r2"] is None
    assert metrics["spearman"] is None
    assert metrics["prediction_to_target_std_ratio"] is None
    assert set(nulls) == {"r2", "spearman", "prediction_to_target_std_ratio"}
    residual = phase.residual_relationships([2, 2, 2], [1, 2, 3], [5, 5, 5])
    assert residual["residual_vs_prediction_slope"] is None
    assert residual["residual_vs_possessions_slope"] is None
    json.dumps(residual, allow_nan=False)


def test_missing_history_grouping_and_materiality():
    records = ([{"history_status": "complete"}] * 100 +
               [{"history_status": "one_missing"}] * 100 +
               [{"history_status": "both_missing"}] * 2)
    target = np.zeros(len(records))
    prediction = np.concatenate([np.ones(100), np.full(100, 1.5), np.full(2, 0.25)])
    rows = phase.subgroup_rows(records, prediction, target)
    assert [row["history_group"] for row in rows] == ["complete", "one_missing", "both_missing"]
    assert rows[0]["adequate_for_formal_comparison"] is True
    assert rows[1]["mae_difference_from_complete"] == pytest.approx(0.5)
    assert rows[1]["material_absolute_difference"] is True
    assert rows[1]["adverse_lower_confidence_difference"] is True
    assert rows[2]["adequate_for_formal_comparison"] is False


def test_team_grouping_and_no_refit_leave_one_team_out():
    records = [
        {"team_id": "2"}, {"team_id": "1"}, {"team_id": "2"}, {"team_id": "1"},
    ]
    prediction = np.asarray([1.0, 2.0, 4.0, 8.0])
    target = np.asarray([0.0, 2.0, 2.0, 4.0])
    possessions = np.asarray([10.0, 20.0, 30.0, 40.0])
    teams, leave = phase.team_rows(records, prediction, target, possessions)
    assert [row["team_id"] for row in teams] == ["1", "2"]
    assert teams[0]["summed_possessions"] == 60.0
    assert [row["removed_team_id"] for row in leave] == ["1", "2"]
    assert all(row["remaining_rows"] == 2 for row in leave)


def test_calibration_order_and_2811_bin_assignment():
    count = 2811
    records = [{"team_id": "1", "player_1_id": str(i + 1), "player_2_id": str(i + 10_000)} for i in range(count)]
    prediction = np.arange(count, dtype=np.float64)
    target = prediction + 2.0
    rows = phase.calibration_rows(records, prediction, target)
    assert [row["bin"] for row in rows] == list(range(1, 11))
    assert [row["row_count"] for row in rows] == [282, 281, 281, 281, 281, 281, 281, 281, 281, 281]
    assert rows[0]["tail"] == "lower" and rows[-1]["tail"] == "upper"
    assert all(row["calibration_difference"] == pytest.approx(2.0) for row in rows)


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
def test_frozen_classification_boundaries(integrity, mae, rmse, expected):
    policy = json.loads((PROJECT_ROOT / phase.R0_POLICY).read_text(encoding="utf-8"))
    assert phase.classify_final(policy, integrity, mae, rmse) == expected


def test_deterministic_serialization_and_exact_schemas():
    document = {"z": 2.5, "a": [True, None]}
    assert phase.serialize_json(document) == phase.serialize_json(document)
    assert phase.serialize_json(document).endswith(b"\n")
    row = {name: index for index, name in enumerate(phase.PREDICTION_COLUMNS)}
    body = phase.serialize_csv([row], phase.PREDICTION_COLUMNS)
    assert body.splitlines()[0].decode() == ",".join(phase.PREDICTION_COLUMNS)
    assert phase.PREDICTION_COLUMNS == (
        "row_position", "target_season", "team_id", "player_1_id", "player_2_id",
        "observation_key", "target_net_rating", "ridge_prediction", "baseline_prediction",
        "pair_possessions", "history_status", "endpoint_exact_250_flag",
    )


def test_write_once_refusal(tmp_path):
    path = tmp_path / "artifact.json"
    phase.write_once(path, b"first\n")
    with pytest.raises(FileExistsError):
        phase.write_once(path, b"second\n")
    assert path.read_bytes() == b"first\n"


def test_manifest_rules_and_official_inventory():
    assert phase.OFFICIAL_ARTIFACTS[-2:] == ("artifact_hashes.json", "summary.json")
    assert "execution_events.jsonl" in phase.PAYLOAD_ARTIFACTS
    assert "predictions.csv" in phase.PAYLOAD_ARTIFACTS
    assert len(phase.OFFICIAL_ARTIFACTS) == len(set(phase.OFFICIAL_ARTIFACTS)) == 14


def test_static_single_model_path_and_prohibited_capabilities_absent():
    source = (PROJECT_ROOT / phase.SOURCE_RELATIVE).read_text(encoding="utf-8")
    tree = ast.parse(source)
    fit_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "fit"]
    predict_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "predict"]
    assert len(fit_calls) == 1
    assert len(predict_calls) == 1
    assert source.count("Ridge(alpha=") == 1
    imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    for prohibited in ("joblib", "pickle", "requests", "urllib", "httpx", "nba_api"):
        assert not any(prohibited in line for line in imports)


def test_no_alternate_estimator_path_and_import_is_inert():
    source = (PROJECT_ROOT / phase.SOURCE_RELATIVE).read_text(encoding="utf-8")
    assert "RandomForest" not in source
    assert "HistGradientBoosting" not in source
    assert "ElasticNet" not in source
    assert "model_selection" not in source
    assert callable(phase.run_official)
