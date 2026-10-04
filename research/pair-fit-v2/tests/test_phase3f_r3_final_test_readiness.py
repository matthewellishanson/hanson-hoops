from __future__ import annotations

import ast
import csv
import json
import math
from pathlib import Path

import pytest

from pair_fit_v2 import phase3f_r3_final_test_readiness as r3


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def builds(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase3f-r3")
    first, second = root / "first", root / "second"
    summary = r3.build(PROJECT_ROOT, first, initial_clean_preflight_confirmed=True)
    r3.build(PROJECT_ROOT, second, initial_clean_preflight_confirmed=True)
    return first, second, summary


def test_exact_team_inclusion_exclusion_and_eligibility(builds):
    first, _, _ = builds
    rows = read_csv(first / "final_test_row_index.csv")
    teams = {row["team_id"] for row in rows}
    assert teams == set(r3.TEAM_IDS) - set(r3.EXCLUDED_TEAMS)
    assert not teams & set(r3.EXCLUDED_TEAMS)
    assert all(float(row["pair_possessions"]) >= 150 for row in rows)
    population = read_json(first / "population_diagnostics.json")
    assert all(item["retained_rows"] == 0 for item in population["excluded_teams"].values())


def test_direct_full_season_provenance_and_no_recovered_rows(builds):
    rows = read_csv(builds[0] / "final_test_staging.csv")
    assert all(row["direct_full_season_source"] == "1" for row in rows)
    assert all(row["recovered_or_window_source"] == "0" for row in rows)
    assert all("phase3f-r2d" not in row["advanced_source_path"] for row in rows)
    assert all(row["target_source_measure"] == "Advanced" for row in rows)
    assert all(row["possession_source_measure"] == "Advanced" for row in rows)


def test_unique_numeric_canonical_keys_and_alignment(builds):
    first, _, _ = builds
    staging = read_csv(first / "final_test_staging.csv")
    index = read_csv(first / "final_test_row_index.csv")
    target = read_csv(first / "final_test_target_vector.csv")
    matrix = read_csv(first / "final_test_estimator_matrix_scaled.csv")
    assert len(staging) == len(index) == len(target) == len(matrix) == 2811
    keys = [row["observation_key"] for row in index]
    assert len(keys) == len(set(keys))
    assert keys == [row["observation_key"] for row in target]
    assert all(row["player_1_id"] == str(int(row["player_1_id"])) for row in index)
    assert all(int(row["player_1_id"]) < int(row["player_2_id"]) for row in index)


def test_nearest_strict_prior_and_missing_visibility(builds):
    first, _, _ = builds
    history = read_json(first / "history_selection_diagnostics.json")
    assert history["strict_prior_failures"] == 0
    assert history["lookback_violations"] == 0
    assert history["missing_slot_count"] == 717
    assert sum(history["history_status_rows"].values()) == 2811
    assert set(history["selected_profile_seasons_all_slots"]) == set(r3.PROFILE_SEASONS)
    profiles = {season: {} for season in r3.PROFILE_SEASONS}
    profiles["2024-25"]["1"] = {"PLAYER_ID": 1}
    profiles["2023-24"]["1"] = {"PLAYER_ID": 1}
    assert r3.select_history("1", profiles)[:2] == ("2024-25", 1)
    assert r3.select_history("2", profiles) == (None, None, None)


def test_exact_feature_order_purity_finiteness_and_scaled_once(builds):
    first, _, _ = builds
    manifest = read_json(first / "estimator_feature_manifest.json")
    matrix = read_csv(first / "final_test_estimator_matrix_scaled.csv")
    assert tuple(manifest["ordered_estimator_features"]) == r3.FEATURES
    assert list(matrix[0]) == list(r3.FEATURES)
    assert all(math.isfinite(float(row[name])) for row in matrix for name in r3.FEATURES)
    prohibited = ("target", "poss", "minute", "source", "player_1", "player_2", "reliability")
    assert not [name for name in r3.FEATURES if any(token in name.lower() for token in prohibited)]
    preprocessing = read_json(first / "applied_preprocessing_state_identity.json")
    assert preprocessing["training_rows"] == 29701
    assert preprocessing["frozen_scaler_applied_count"] == 1
    assert preprocessing["final_test_statistics_learned"] is False
    assert preprocessing["double_scaling"] is False


def test_full_slot_swap_symmetry(builds):
    population = read_json(builds[0] / "population_diagnostics.json")
    integrity = population["matrix_integrity"]
    assert integrity["slot_swap_comparisons"] == 2811 * 45
    assert integrity["slot_swap_mismatches"] == 0


def test_readiness_gate_truth_table_and_unresolved_block():
    gates = [{"id": gate, "status": "passed"} for gate in r3.GATE_IDS]
    r3.require_all_gates_pass(gates)
    gates[2]["status"] = "unresolved"
    with pytest.raises(r3.ReadinessError, match="blocks"):
        r3.require_all_gates_pass(gates)
    gates[2]["status"] = "failed"
    with pytest.raises(r3.ReadinessError, match="blocks"):
        r3.require_all_gates_pass(gates)


def test_all_and_only_six_frozen_gates_pass_without_authorization(builds):
    readiness = read_json(builds[0] / "readiness_gates.json")
    assert tuple(readiness["frozen_gate_order"]) == r3.GATE_IDS
    assert len(readiness["gates"]) == 6
    assert {item["status"] for item in readiness["gates"]} == {"passed"}
    assert readiness["checkpoint_grants_execution_authorization"] is False
    assert readiness["readiness_checkpoint_read_only_audit_cleared"] is False
    assert readiness["one_time_final_model_execution_authorized"] is False


def test_write_once_restart_refusal(builds):
    first, _, _ = builds
    with pytest.raises(r3.ReadinessError, match="already exists"):
        r3.build(PROJECT_ROOT, first, initial_clean_preflight_confirmed=True)


def test_initial_preflight_confirmation_required(tmp_path):
    with pytest.raises(r3.ReadinessError, match="preflight"):
        r3.build(PROJECT_ROOT, tmp_path / "refused")


def test_two_independent_builds_are_byte_identical(builds):
    first, second, _ = builds
    assert sorted(path.name for path in first.iterdir()) == list(sorted(r3.OUTPUT_FILES))
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }


def test_summary_uses_declared_inventory_independent_of_report_timing(monkeypatch):
    complete = r3.verify_repository_state(PROJECT_ROOT, True)
    real_git = r3._git
    status = real_git(PROJECT_ROOT, "status", "--porcelain=v1", "--untracked-files=all")
    before_report = "\n".join(
        line for line in status.splitlines()
        if "PHASE3F_R3_FINAL_TEST_READINESS_REPORT.md" not in line
    )

    def git_before_report(project_root, *args):
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return before_report
        return real_git(project_root, *args)

    monkeypatch.setattr(r3, "_git", git_before_report)
    incomplete = r3.verify_repository_state(PROJECT_ROOT, True)
    assert incomplete == complete
    assert incomplete["construction_time_changes"] == list(
        r3.EXPECTED_R3_GIT_VISIBLE_DELIVERABLES
    )


def test_final_git_visible_inventory_is_exact():
    r3.validate_final_git_visible_inventory(PROJECT_ROOT)


def test_fresh_build_matches_authoritative_corrected_composite(builds):
    fresh = builds[0]
    original = PROJECT_ROOT / "curated/phase3f-r3"
    correction = PROJECT_ROOT / "curated/phase3f-r3.1"
    for name in r3.OUTPUT_FILES[:-1]:
        assert (fresh / name).read_bytes() == (original / name).read_bytes()
    assert (fresh / "summary.json").read_bytes() == (
        correction / "corrected_summary.json"
    ).read_bytes()


def test_r3_1_manifest_and_reference_inventory_are_exact():
    correction = PROJECT_ROOT / "curated/phase3f-r3.1"
    assert sorted(path.name for path in correction.iterdir()) == sorted(r3.R3_1_OUTPUT_FILES)
    manifest = read_json(correction / "artifact_hashes.json")
    assert tuple(manifest["artifact_inventory"]) == r3.R3_1_OUTPUT_FILES
    assert tuple(manifest["payload_artifacts"]) == r3.R3_1_OUTPUT_FILES[:3]
    for name, record in manifest["artifacts"].items():
        assert r3.sha256_file(correction / name) == record["sha256"]
    references = read_json(correction / "referenced_r3_artifacts.json")
    assert len(references["artifacts"]) == 11
    assert all(item["disposition"] == "referenced_not_copied" for item in references["artifacts"])
    assert {Path(item["path"]).name for item in references["artifacts"]} == set(
        r3.OUTPUT_FILES[:-1]
    )


def test_nonrecursive_manifest_exact_inventory(builds):
    first, _, _ = builds
    manifest = read_json(first / "artifact_hashes.json")
    assert tuple(manifest["payload_artifacts"]) == r3.PAYLOAD_FILES
    assert manifest["excluded_from_own_manifest"] == ["artifact_hashes.json", "summary.json"]
    assert set(manifest["artifacts"]) == set(r3.PAYLOAD_FILES)
    for name, record in manifest["artifacts"].items():
        assert r3.sha256_file(first / name) == record["sha256"]


def test_static_capability_boundary():
    source_path = PROJECT_ROOT / "src/pair_fit_v2/phase3f_r3_final_test_readiness.py"
    cli_path = PROJECT_ROOT / "src/pair_fit_v2/phase3f_r3_cli.py"
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in (source_path, cli_path)]
    imports = set()
    called_attributes = set()
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                called_attributes.add(node.func.attr)
    assert not imports & {"requests", "urllib", "httpx", "socket", "sklearn", "joblib", "pickle"}
    assert not called_attributes & {"fit", "predict", "fit_predict", "dump"}


def test_summary_records_zero_prohibited_operations(builds):
    summary = builds[2]
    assert summary["network_operations"] == 0
    assert summary["estimator_operations"] == 0
    assert summary["prediction_operations"] == 0
    assert summary["metric_operations"] == 0
    assert summary["model_serialization_operations"] == 0


def test_protected_and_training_fingerprints_unchanged(builds):
    fingerprints = read_json(builds[0] / "input_fingerprints.json")
    assert fingerprints["protected_evidence_before"] == fingerprints["protected_evidence_after"]
    assert fingerprints["expanded_training_before"] == fingerprints["expanded_training_after"]
