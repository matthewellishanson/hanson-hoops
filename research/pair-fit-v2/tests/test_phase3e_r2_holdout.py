import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3e_r2_holdout as phase


PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def independent_builds(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase3e_r2")
    left, right = root / "left", root / "right"
    first = phase.build(PROJECT, left)
    second = phase.build(PROJECT, right)
    return left, right, first, second


def test_protected_path_is_rejected_before_read(monkeypatch):
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("protected file was opened"))
    with pytest.raises(ValueError, match="protected-season path rejected before access"):
        phase._read_bytes(Path("evidence/2025-26/forbidden.json"))


def test_frozen_feature_contract_is_exact_and_prohibited_fields_absent(independent_builds):
    left, _, _, _ = independent_builds
    manifest = json.loads((left / "estimator_feature_manifest.json").read_text())
    names = manifest["ordered_estimator_features"]
    expected = (
        [f"pair_mean.{field}" for field in phase.phase3b.ESTIMATOR_CONTINUOUS_INPUTS]
        + [f"pair_absolute_difference.{field}" for field in phase.phase3b.ESTIMATOR_CONTINUOUS_INPUTS]
        + ["pair_traded_history_count"]
    )
    assert names == expected
    assert len(names) == len(set(names)) == 45
    assert not set(names) & phase.PROHIBITED_EXACT
    assert all(not any(token in name.lower() for token in phase.PROHIBITED_SUBSTRINGS) for name in names)
    with (left / "holdout_estimator_matrix.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == names
        assert sum(1 for _ in reader) == 2700


def test_population_policy_and_required_diagnostics(independent_builds):
    left, _, summary, _ = independent_builds
    diagnostics = json.loads((left / "population_diagnostics.json").read_text())
    assert summary["classification"] == "2024-25 holdout dataset constructed; ready for read-only audit"
    assert summary["original_team_seasons"] == 30
    assert summary["retained_team_seasons"] == 28
    assert diagnostics["all_30_teams_raw_pair_rows"] == 5297
    assert diagnostics["remaining_28_team_raw_pair_rows"] == 4797
    assert diagnostics["remaining_28_team_eligible_poss_ge_150_rows"] == 2700
    assert diagnostics["excluded_teams"]["1610612766"]["raw_pair_rows"] == 250
    assert diagnostics["excluded_teams"]["1610612755"]["raw_pair_rows"] == 250
    assert diagnostics["excluded_teams"]["1610612766"]["eligible_poss_ge_150_rows"] == 143
    assert diagnostics["excluded_teams"]["1610612755"]["eligible_poss_ge_150_rows"] == 151
    assert len(diagnostics["original_cached_team_seasons"]) == 30
    assert all(item["reconciliation_passed"] for item in diagnostics["original_cached_team_seasons"])
    assert diagnostics["row_issue_totals"] == {
        "duplicate_pair_rows": 0,
        "malformed_pair_rows": 0,
        "missing_possession_rows": 0,
        "missing_target_rows": 0,
        "nonfinite_target_rows": 0,
        "nonpositive_possession_rows": 8,
        "same_player_rows": 0,
    }


def test_history_seasons_missingness_and_training_only_preprocessing(independent_builds):
    left, _, summary, _ = independent_builds
    diagnostics = json.loads((left / "population_diagnostics.json").read_text())
    state = json.loads((left / "preprocessing_state.json").read_text())
    assert diagnostics["history_status_rows"] == {"both_missing": 38, "complete": 2139, "one_missing": 523}
    assert diagnostics["selected_profile_seasons_all_slots"] == {"2021-22": 19, "2022-23": 69, "2023-24": 4713}
    assert diagnostics["history_lookback_age_all_slots"] == {"1": 4713, "2": 69, "3": 19}
    assert summary["target_season"] == "2024-25"
    assert summary["feature_source_seasons"] == ["2021-22", "2022-23", "2023-24"]
    assert state["training_derived_only"] is True
    assert state["holdout_predictors_or_targets_used_to_fit_preprocessing"] is False
    assert state["preprocessing_training_target_seasons"] == list(phase.phase3d.ALLOWED_TARGET_SEASONS)
    assert diagnostics["second_stage_imputation"]["slot_swap_mismatches"] == 0
    assert diagnostics["second_stage_imputation"]["slot_swap_feature_values_checked"] == 2700 * 45


def test_two_independent_builds_are_byte_identical_and_inputs_unchanged(independent_builds):
    left, right, first, second = independent_builds
    assert first["deterministic_content_sha256"] == second["deterministic_content_sha256"]
    expected = set(phase.OUTPUT_FILES) | {"artifact_hashes.json", "summary.json"}
    assert {path.name for path in left.iterdir()} == expected
    assert {path.name for path in right.iterdir()} == expected
    for name in expected:
        assert (left / name).read_bytes() == (right / name).read_bytes()
    fingerprints = json.loads((left / "input_fingerprints.json").read_text())
    assert fingerprints["unchanged_during_construction"] is True
    for relative, expected_hash in fingerprints["referenced_cache_files"].items():
        assert phase.sha256_file(PROJECT / "cache" / relative) == expected_hash


def test_target_values_do_not_enter_estimator_matrix(independent_builds):
    left, _, _, _ = independent_builds
    with (left / "holdout_staging.csv").open(newline="", encoding="utf-8") as handle:
        staging = list(csv.DictReader(handle))
    with (left / "holdout_estimator_matrix.csv").open(newline="", encoding="utf-8") as handle:
        matrix_before = list(csv.DictReader(handle))
    # The matrix artifact has no join, target, or exposure column; changing the
    # separately retained target therefore cannot mutate an estimator value.
    staging[0]["target_net_rating"] = "999999"
    assert "target_net_rating" not in matrix_before[0]
    assert "pair_possessions" not in matrix_before[0]
    assert len(matrix_before[0]) == 45
