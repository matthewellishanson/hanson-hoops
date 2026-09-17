import csv
import json
import math
import socket
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3e_r4_2_reconciliation as phase


PROJECT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("display_case", "payload", "expected_xy", "expected_path", "expected_original"),
    [
        (" M .gitignore", b" M .gitignore\0", " M", ".gitignore", None),
        ("M  tracked-file.md", b"M  tracked-file.md\0", "M ", "tracked-file.md", None),
        (
            "MM both-staged-and-modified.txt",
            b"MM both-staged-and-modified.txt\0",
            "MM",
            "both-staged-and-modified.txt",
            None,
        ),
        ("?? new-file.py", b"?? new-file.py\0", "??", "new-file.py", None),
        ("A  added-file.py", b"A  added-file.py\0", "A ", "added-file.py", None),
        (" D deleted-file.py", b" D deleted-file.py\0", " D", "deleted-file.py", None),
        (
            "R  old-name.py -> new-name.py",
            b"R  new-name.py\0old-name.py\0",
            "R ",
            "new-name.py",
            "old-name.py",
        ),
    ],
)
def test_porcelain_v1_z_regression_cases(
    display_case, payload, expected_xy, expected_path, expected_original
):
    assert display_case
    assert phase.parse_porcelain_v1_z(payload) == [
        {"xy": expected_xy, "path": expected_path, "original_path": expected_original}
    ]


def test_porcelain_parser_preserves_leading_punctuation_and_path_spaces():
    records = phase.parse_porcelain_v1_z(b" M .gitignore\0??  leading-space.py\0")
    assert records[0]["path"] == ".gitignore"
    assert records[1]["path"] == " leading-space.py"
    source = (PROJECT / "src/pair_fit_v2/phase3e_r4_2_reconciliation.py").read_text(
        encoding="utf-8"
    )
    body = source[source.index("def parse_porcelain_v1_z") : source.index("def verify_git_state")]
    assert ".strip(" not in body
    assert ".lstrip(" not in body


@pytest.mark.parametrize(
    "payload",
    [
        b" M .gitignore",
        b"M tracked-file.md\0",
        b"  impossible.txt\0",
        b"R  new-name.py\0",
        b"Z  unknown.txt\0",
    ],
)
def test_porcelain_parser_rejects_malformed_records(payload):
    with pytest.raises(phase.ReconciliationFailure, match="malformed"):
        phase.parse_porcelain_v1_z(payload)


def test_failed_r4_1_attempt_is_hash_and_timestamp_pinned():
    evidence = phase.verify_failed_r4_1(PROJECT)
    assert evidence["classification"] == phase.FAILED_R4_1_CLASSIFICATION
    assert evidence["runtime_inventory"]["fingerprint_sha256"] == phase.FAILED_R4_1_NAMESPACE_FINGERPRINT
    assert evidence["ledger_sha256"] == phase.FAILED_R4_1_LEDGER_SHA256
    assert evidence["runtime_inventory"]["file_count"] == 1
    assert len(evidence["ledger_events"]) == 2
    assert evidence["source_prediction_opened_or_processed"] is False
    assert evidence["model_fit_count"] == evidence["prediction_call_count"] == 0


def test_prior_wrapper_failure_is_disclosed_without_becoming_an_execution_event():
    failure = phase.PRE_EXECUTION_WRAPPER_FAILURE
    assert failure["occurred"] is True
    assert failure["module_imported"] is False
    assert failure["reconciliation_function_began"] is False
    assert failure["runtime_directory_created"] is False
    assert failure["event_ledger_created"] is False
    assert failure["model_loaded_or_fitted"] is False
    assert failure["prediction_generated"] is False
    assert failure["protected_season_evidence_accessed"] is False


def test_every_formula_uses_frozen_signs_and_population_conventions():
    metrics, nulls = phase.metric_set([1.0, 3.0, 5.0], [2.0, 2.0, 8.0])
    assert metrics["mae"] == pytest.approx(5 / 3)
    assert metrics["rmse"] == pytest.approx(math.sqrt(11 / 3))
    assert metrics["bias"] == pytest.approx(-1.0)
    assert metrics["prediction_std"] == pytest.approx(np.std([1.0, 3.0, 5.0], ddof=0))
    assert metrics["target_std"] == pytest.approx(np.std([2.0, 2.0, 8.0], ddof=0))
    assert nulls == {}

    weighted = phase.weighted_errors(
        np.asarray([1.0, 3.0]), np.asarray([2.0, 1.0]), np.asarray([1.0, 3.0])
    )
    assert weighted[0] == pytest.approx(7 / 4)
    assert weighted[1] == pytest.approx(math.sqrt(13 / 4))

    residual = phase.residual_relationships([1.0, 2.0, 3.0], [2.0, 2.0, 4.0], [1, 2, 4])
    assert residual["residual_sign_convention"] == "target minus prediction"
    assert residual["residual_mean"] == pytest.approx(2 / 3)


def test_tied_spearman_uses_average_ranks_and_nulls_are_explicit():
    tied, _ = phase.metric_set([1.0, 1.0, 3.0, 4.0], [1.0, 2.0, 2.0, 4.0])
    expected = np.corrcoef([1.5, 1.5, 3.0, 4.0], [1.0, 2.5, 2.5, 4.0])[0, 1]
    assert tied["spearman"] == pytest.approx(expected)
    constant, reasons = phase.metric_set([2.0, 2.0, 2.0], [1.0, 2.0, 3.0])
    assert constant["spearman"] is None
    assert reasons["spearman"] == "left vector variance is zero"


def test_missing_history_flags_are_independent_of_adequacy():
    records = (
        [{"history_status": "complete"}] * 100
        + [{"history_status": "one_missing"}] * 100
        + [{"history_status": "both_missing"}] * 2
    )
    target = np.zeros(202)
    values = np.concatenate((np.zeros(100), np.ones(100), np.full(2, 3.0)))
    rows = phase.subgroup_rows(records, values, target)
    both = rows[2]
    assert both["adequate_for_formal_comparison"] is False
    assert both["descriptive_only"] is True
    assert both["material_absolute_difference"] is True
    assert both["adverse_lower_confidence_difference"] is True


@pytest.mark.parametrize(
    ("mae", "rmse", "expected"),
    [
        (0.0, 1.0, "VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE"),
        (-0.1, 1.0, "VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE"),
        (0.099999, 1.0, "VALID DEVELOPMENT-HOLDOUT MIXED RESULT"),
        (0.1, -0.00001, "VALID DEVELOPMENT-HOLDOUT MIXED RESULT"),
        (0.1, 0.0, "VALID DEVELOPMENT-HOLDOUT PASS"),
    ],
)
def test_classification_boundaries(mae, rmse, expected):
    assert phase.classify_scientific(mae, rmse) == expected


def test_source_hash_rejection(tmp_path):
    source = tmp_path / "source.csv"
    source.write_bytes(b"changed")
    with pytest.raises(phase.ReconciliationFailure, match="persisted prediction hash mismatch"):
        phase.require_sha256(source, phase.PREDICTION_SHA256, "persisted prediction")


def test_original_namespace_mutation_rejection():
    before = {"fingerprint_sha256": "a", "files": []}
    after = {"fingerprint_sha256": "b", "files": []}
    with pytest.raises(phase.ReconciliationFailure, match="original namespace changed"):
        phase.require_unchanged(before, after, "original namespace")


def test_restart_refusal(tmp_path):
    output = tmp_path / phase.OUTPUT_DIR
    output.mkdir(parents=True)
    with pytest.raises(phase.ReconciliationFailure, match="already exists"):
        phase.verify_restart_safe(tmp_path)


def test_static_model_prohibitions():
    result = phase.static_prohibition_audit(PROJECT)
    assert result["passed"] is True
    assert result["forbidden_imports"] == []
    assert result["forbidden_calls"] == []
    for relative in result["paths"]:
        source = (PROJECT / relative).read_text(encoding="utf-8")
        assert "from sklearn" not in source
        assert "import sklearn" not in source
        assert ".fit(" not in source
        assert ".predict(" not in source
        assert ".fit_predict(" not in source


def test_output_schemas_and_deterministic_serialization():
    row = {column: index for index, column in enumerate(phase.TEAM_COLUMNS)}
    first = phase.serialize_csv([row], phase.TEAM_COLUMNS)
    second = phase.serialize_csv([row], phase.TEAM_COLUMNS)
    assert first == second
    assert first.endswith(b"\n")
    document = {"z": 1, "a": {"x": None}}
    assert phase.serialize_json(document) == phase.serialize_json(document)
    assert phase.serialize_json(document).endswith(b"\n")
    bad = dict(row)
    bad["unexpected"] = 1
    with pytest.raises(phase.ReconciliationFailure, match="schema"):
        phase.serialize_csv([bad], phase.TEAM_COLUMNS)


def test_event_ledger_ordering_and_fixed_schema(tmp_path):
    moments = iter(["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"])
    ledger = phase.EventLedger(tmp_path / "events.jsonl", clock=lambda: next(moments))
    ledger.add("start", "passed")
    ledger.add("finish", "passed", path="x", sha256="a" * 64, detail="done")
    ledger.close()
    result = phase.validate_event_ledger(tmp_path / "events.jsonl")
    assert result["event_count"] == 2
    assert result["first_event"]["event_number"] == 1
    assert result["last_event"]["event_number"] == 2


def test_stage_b_mismatch_failure():
    with pytest.raises(phase.ReconciliationFailure, match="numerical artifact mismatch"):
        phase._assert_close({"mae": 1.0}, {"mae": 1.1})


def test_network_and_protected_season_blocking():
    with pytest.raises(phase.ReconciliationFailure, match="protected-season"):
        phase.reject_protected_identity("evidence/2025-26/final.csv")
    with phase.offline_scope():
        with pytest.raises(phase.ReconciliationFailure, match="network access"):
            socket.getaddrinfo("example.com", 443)


def test_team_leave_one_out_and_calibration_ordering():
    records = [
        {"team_id": "2", "player_1_id": "1", "player_2_id": "3"},
        {"team_id": "1", "player_1_id": "2", "player_2_id": "4"},
    ] * 1350
    values = np.linspace(-2, 2, 2700)
    target = values + 1
    possessions = np.ones(2700)
    teams, leave = phase.team_rows(records, values, target, possessions)
    assert [row["team_id"] for row in teams] == ["1", "2"]
    assert [row["removed_team_id"] for row in leave] == ["1", "2"]
    assert all(row["full_sample_minus_leave_one_team_out_mae"] == pytest.approx(0.0) for row in leave)
    bins = phase.calibration_rows(records, values, target)
    assert len(bins) == 10
    assert all(row["row_count"] == 270 for row in bins)
    assert bins[0]["tail"] == "lower" and bins[-1]["tail"] == "upper"


def test_pinned_persisted_prediction_audit_without_model_code():
    before = phase.inventory_namespace(PROJECT)
    report = phase.report_identity(PROJECT)
    evidence, rows, vectors = phase.verify_source_evidence(PROJECT, before, report)
    assert evidence["prediction_source"]["serialized_byte_sha256"] == phase.PREDICTION_SHA256
    assert len(rows) == 2700
    assert vectors["values"].shape == (2700,)
    assert evidence["stage_a_source"]["stage_a_pass"] is True
    assert evidence["prohibition_verification"]["model_artifact_present"] is False


def test_recomputed_pinned_stage_b_matches_surviving_numerical_artifacts():
    before = phase.inventory_namespace(PROJECT)
    evidence, rows, vectors = phase.verify_source_evidence(
        PROJECT, before, phase.report_identity(PROJECT)
    )
    assert evidence["verification_status"].startswith("passed")
    artifacts = phase.compute_stage_b(rows, vectors)
    phase.compare_original_numerical_artifacts(PROJECT, artifacts)
    missing = artifacts["reconciled_missing_history_metrics.csv"]
    assert [row["row_count"] for row in missing] == [2139, 523, 38]
    assert missing[2]["descriptive_only"] is True
    assert artifacts["reconciliation_decision.json"]["reconciled_scientific_classification"] == "VALID DEVELOPMENT-HOLDOUT PASS"

