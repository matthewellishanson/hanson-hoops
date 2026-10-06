import ast
import csv
import io
import json
import math
import socket
import sys
from pathlib import Path

import numpy as np
import pytest
from sklearn.linear_model import Ridge

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3e_r4_evaluation as phase


PROJECT = Path(__file__).resolve().parents[1]


def test_metric_formulas_and_signed_bias_use_synthetic_values_only():
    metrics, nulls = phase.metric_set([1.0, 3.0, 5.0], [2.0, 2.0, 8.0])
    assert metrics["mae"] == pytest.approx(5 / 3)
    assert metrics["rmse"] == pytest.approx(math.sqrt(11 / 3))
    assert metrics["bias"] == pytest.approx(-1.0)
    assert metrics["prediction_std"] == pytest.approx(np.std([1.0, 3.0, 5.0], ddof=0))
    assert metrics["target_std"] == pytest.approx(np.std([2.0, 2.0, 8.0], ddof=0))
    assert nulls == {}


def test_tied_spearman_uses_average_ranks():
    metrics, _ = phase.metric_set([1.0, 1.0, 3.0, 4.0], [4.0, 2.0, 2.0, 1.0])
    expected = np.corrcoef([1.5, 1.5, 3.0, 4.0], [4.0, 2.5, 2.5, 1.0])[0, 1]
    assert metrics["spearman"] == pytest.approx(expected)


@pytest.mark.parametrize(
    ("mae", "rmse", "expected"),
    [
        (0.10, 0.0, "VALID DEVELOPMENT-HOLDOUT PASS"),
        (0.099999, 1.0, "VALID DEVELOPMENT-HOLDOUT MIXED RESULT"),
        (0.10, -0.000001, "VALID DEVELOPMENT-HOLDOUT MIXED RESULT"),
        (0.0, 1.0, "VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE"),
        (-0.1, 1.0, "VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE"),
    ],
)
def test_frozen_classification_boundaries(mae, rmse, expected):
    assert phase.classify(True, True, mae, rmse) == expected


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, "bad", None])
def test_nonfinite_target_predictor_and_prediction_rejected(bad):
    with pytest.raises(phase.ContractFailure):
        phase.metric_set([0.0, bad], [0.0, 1.0])
    with pytest.raises(phase.ContractFailure):
        phase.metric_set([0.0, 1.0], [0.0, bad])


def test_residual_zero_variance_has_null_correlations_but_defined_slopes():
    result = phase.residual_relationships([1.0, 2.0, 3.0], [2.0, 3.0, 4.0], [10.0, 20.0, 30.0])
    assert result["residual_variance"] == 0.0
    assert result["residual_vs_prediction_pearson"] is None
    assert result["residual_vs_possessions_pearson"] is None
    assert result["residual_vs_prediction_slope"] == pytest.approx(0.0)
    assert result["residual_vs_possessions_slope"] == pytest.approx(0.0)
    assert set(result["null_reasons"]) == {
        "residual_vs_prediction_pearson", "residual_vs_possessions_pearson"
    }


def test_zero_predictor_variance_emits_json_null_and_reason():
    result = phase.residual_relationships([2.0, 2.0, 2.0], [1.0, 2.0, 4.0], [10.0, 20.0, 40.0])
    assert result["residual_vs_prediction_pearson"] is None
    assert result["residual_vs_prediction_slope"] is None
    assert "prediction variance is zero" in result["null_reasons"]["residual_vs_prediction_slope"]
    json.dumps(result, allow_nan=False)


def test_deterministic_json_and_csv_serialization_and_schema():
    document = {"z": 1.5, "a": {"b": True}}
    assert phase.serialize_json(document) == phase.serialize_json(document)
    assert phase.serialize_json(document).endswith(b"\n")
    rows = [{"i": 1, "x": 1.25, "ok": True, "missing": None}]
    payload = phase.serialize_csv(rows, ["i", "x", "ok", "missing"])
    assert payload == b"i,x,ok,missing\n1,1.25,true,\n"
    with pytest.raises(phase.ContractFailure):
        phase.serialize_csv([{"i": 1}], ["i", "x"])


def test_numeric_canonical_keys_reject_lexicographic_or_excluded_inputs():
    row = {"target_season": "synthetic", "team_id": "20", "player_1_id": "9", "player_2_id": "10"}
    assert phase.numeric_observation_key(row) == ("synthetic", "20", "9", "10")
    reversed_row = row | {"player_1_id": "10", "player_2_id": "9"}
    with pytest.raises(phase.ContractFailure, match="numeric canonical"):
        phase.numeric_observation_key(reversed_row)
    excluded = row | {"team_id": "1610612755"}
    assert phase.numeric_observation_key(excluded)[1] in phase.EXCLUDED_TEAMS


def test_row_misalignment_is_detectable_by_numeric_key():
    left = {"target_season": "synthetic", "team_id": "20", "player_1_id": "9", "player_2_id": "10"}
    right = left | {"player_2_id": "11"}
    assert phase.numeric_observation_key(left) != phase.numeric_observation_key(right)


def test_stage_b_completeness_rejects_missing_artifact():
    with pytest.raises(phase.ContractFailure, match="required artifact missing"):
        phase._validate_stage_b_in_memory(
            {}, {"runtime_output_contract": {"artifacts": {}}}
        )


def test_network_and_protected_season_are_blocked():
    with pytest.raises(phase.ContractFailure, match="protected-season"):
        phase.reject_protected_identity(Path("cache/2025-26/outcome.json"))
    with phase.offline_scope():
        with pytest.raises(phase.ContractFailure, match="network access prohibited"):
            socket.create_connection(("127.0.0.1", 9))
        with pytest.raises(phase.ContractFailure, match="network access prohibited"):
            socket.getaddrinfo("localhost", 80)


def test_alternate_estimator_and_prediction_contract_is_static_and_narrow():
    source = Path(phase.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    sklearn_imports = [ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) and "sklearn" in ast.unparse(node)]
    assert sklearn_imports == ["import sklearn", "from sklearn.linear_model import Ridge"]
    assert source.count("estimator.fit(") == 1
    assert source.count("estimator.predict(") == 1
    assert "HistGradientBoosting" not in source
    assert "joblib" not in source and "pickle" not in source


def test_legacy_import_guard_and_prediction_persistence_order():
    source = Path(phase.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [ast.unparse(node) for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not any("phase1b_contract" in item or "pair_fit_v2.schema" in item for item in imports)
    integrity_write = source.index('_write_bytes(output_dir / "pre_metric_integrity.json"')
    stage_b_start = source.index("# Stage B begins only")
    predictions_write = source.index("for name in PAYLOAD_ARTIFACTS[2:]", stage_b_start)
    assert integrity_write < predictions_write
    assert "temporary" not in source.lower() or "temporary or final predictions file" in source


def test_stage_a_failure_output_policy_has_only_two_artifacts():
    assert phase.OFFICIAL_ARTIFACTS[:2] == (
        "execution_configuration.json", "pre_metric_integrity.json"
    )
    source = Path(phase.__file__).read_text(encoding="utf-8")
    catch_start = source.index("except Exception as exc:")
    stage_b_start = source.index("# Stage B begins only")
    failure_block = source[catch_start:stage_b_start]
    assert "predictions.csv" not in failure_block
    assert "overall_metrics.json" not in failure_block


def test_official_preflight_accepts_only_the_three_authorized_project_changes(monkeypatch, tmp_path):
    repository = tmp_path / "repository"
    project = repository / "research" / "pair-fit-v2"
    project.mkdir(parents=True)
    responses = {
        ("branch", "--show-current"): phase.EXPECTED_BRANCH,
        ("rev-parse", "HEAD"): phase.EXPECTED_HEAD,
        ("rev-parse", "@{upstream}"): phase.EXPECTED_HEAD,
        ("rev-parse", "--show-toplevel"): str(repository),
        ("status", "--porcelain=v1", "--untracked-files=all"): "\n".join(
            f"?? research/pair-fit-v2/{path}" for path in sorted(phase.ALLOWED_PRE_RUN_CHANGES)
        ),
    }
    monkeypatch.setattr(phase, "_git", lambda _root, *args: responses[args])
    phase.verify_official_start(project)


def test_no_real_holdout_outcomes_appear_in_synthetic_test_module():
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    official_calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith("run_official_evaluation")
    ]
    assert official_calls == []


def test_missing_history_materiality_is_independent_of_adequacy():
    records = [
        {"history_status": "complete"},
        {"history_status": "complete"},
        {"history_status": "one_missing"},
        {"history_status": "both_missing"},
    ]
    rows = phase._subgroup_rows(
        records,
        np.asarray([0.0, 0.0, 1.0, 2.0]),
        np.asarray([0.0, 0.0, 0.0, 0.0]),
    )
    both = next(row for row in rows if row["history_group"] == "both_missing")
    assert both["adequate_for_formal_comparison"] is False
    assert both["material_absolute_difference"] is True
    assert both["adverse_lower_confidence_difference"] is True


def test_official_output_inventory_schemas_hashes_and_invalid_reconciliation():
    output = PROJECT / phase.OUTPUT_DIR
    assert sorted(path.name for path in output.iterdir()) == sorted(phase.OFFICIAL_ARTIFACTS)
    assert len(list(output.iterdir())) == 13
    policy = json.loads((PROJECT / phase.POLICY_PATH).read_text(encoding="utf-8"))
    contract = policy["runtime_output_contract"]["artifacts"]
    for name in phase.OFFICIAL_ARTIFACTS:
        path = output / name
        spec = contract[name]
        if path.suffix == ".json":
            document = json.loads(path.read_text(encoding="utf-8"))
            assert set(document) == set(spec["top_level_keys"])
            json.dumps(document, allow_nan=False)
        else:
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            assert reader.fieldnames == spec["columns"]
            assert len(rows) == spec["rows"]
    manifest = json.loads((output / "artifact_hashes.json").read_text(encoding="utf-8"))
    assert set(manifest["payload_artifacts"]) == set(phase.PAYLOAD_ARTIFACTS)
    assert manifest["excluded_from_own_byte_manifest"] == ["artifact_hashes.json", "summary.json"]
    assert manifest["deterministic_content_sha256"] == phase.canonical_content_hash(manifest)
    for name, entry in manifest["payload_artifacts"].items():
        assert set(entry) == {"relative_path", "serialized_byte_sha256"}
        assert entry["relative_path"] == name
        assert entry["serialized_byte_sha256"] == phase.sha256_file(output / name)
    decision = json.loads((output / "evaluation_decision.json").read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    report = (PROJECT / phase.REPORT_PATH).read_text(encoding="utf-8")
    expected = "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"
    assert decision["classification"] == summary["final_classification"] == expected
    assert expected in report
    assert decision["stage_a_pass"] is True
    assert decision["stage_b_pass"] is False
    failed = [row["gate_id"] for row in decision["gate_outcomes"] if not row["passed"]]
    assert failed == ["required_metrics_diagnostics_complete"]


def test_official_predictions_reconcile_without_refitting_or_regenerating():
    output = PROJECT / phase.OUTPUT_DIR
    with (output / "predictions.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    overall = json.loads((output / "overall_metrics.json").read_text(encoding="utf-8"))
    target = np.asarray([float(row["target_net_rating"]) for row in rows])
    ridge = np.asarray([float(row["ridge_prediction"]) for row in rows])
    baseline = np.asarray([float(row["baseline_prediction"]) for row in rows])
    assert len(rows) == 2700
    assert np.isfinite(np.concatenate((target, ridge, baseline))).all()
    ridge_mae = float(np.mean(np.abs(ridge - target)))
    baseline_mae = float(np.mean(np.abs(baseline - target)))
    ridge_rmse = float(np.sqrt(np.mean((ridge - target) ** 2)))
    baseline_rmse = float(np.sqrt(np.mean((baseline - target) ** 2)))
    assert ridge_mae == overall["ridge_unweighted"]["mae"]
    assert baseline_mae == overall["baseline_unweighted"]["mae"]
    assert ridge_rmse == overall["ridge_unweighted"]["rmse"]
    assert baseline_rmse == overall["baseline_unweighted"]["rmse"]
    assert baseline_mae - ridge_mae == overall["improvements"]["mae_baseline_minus_ridge"]
    assert baseline_rmse - ridge_rmse == overall["improvements"]["rmse_baseline_minus_ridge"]


def test_official_order_alignment_exclusions_and_subgroup_flags():
    output = PROJECT / phase.OUTPUT_DIR
    with (output / "predictions.csv").open(encoding="utf-8", newline="") as handle:
        predictions = list(csv.DictReader(handle))
    assert [int(row["row_position"]) for row in predictions] == list(range(2700))
    keys = [phase.numeric_observation_key(row) for row in predictions]
    assert len(set(keys)) == 2700
    assert not ({row["team_id"] for row in predictions} & phase.EXCLUDED_TEAMS)
    with (output / "missing_history_metrics.csv").open(encoding="utf-8", newline="") as handle:
        groups = list(csv.DictReader(handle))
    both = groups[2]
    assert both["history_group"] == "both_missing"
    assert both["adequate_for_formal_comparison"] == "false"
    assert both["material_absolute_difference"] == "true"
    assert both["adverse_lower_confidence_difference"] == "true"
