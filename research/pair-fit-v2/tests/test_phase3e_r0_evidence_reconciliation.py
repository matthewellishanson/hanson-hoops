import hashlib
import json
from pathlib import Path

import pytest

from pair_fit_v2.phase3a_population_audit import network_prohibited
from pair_fit_v2 import phase3e_r0_evidence_reconciliation as phase


ROOT = Path(__file__).resolve().parents[1]
REAL_CACHE = ROOT / "cache"


def test_rejects_final_test_path_before_access(tmp_path):
    forbidden = tmp_path / "2025-26" / "evidence.json"
    with pytest.raises(ValueError, match="protected-season path rejected before access"):
        phase._read_json(forbidden)


def test_fixed_player_totals_hash_and_cache_only_reconciliation():
    assert phase.PLAYER_TOTALS_RAW_SHA256 == (
        "0a856d37c33218362a0b88fc645b7d609a64a7da0773a1be1368d22d07b54774"
    )
    with network_prohibited():
        result = phase.verify_player_totals_dependency(REAL_CACHE)
    assert result["raw_body_sha256"] == phase.PLAYER_TOTALS_RAW_SHA256
    assert result["byte_count"] == 173_713
    assert result["schema_column_count"] == 69
    assert result["unique_player_ids"] == 572
    assert result["duplicate_player_ids"] == 0
    assert result["per100_reconciliation"]["totals_only_ids"] == []
    assert result["per100_reconciliation"]["per100_only_ids"] == []
    assert result["season_total_minutes"]["reliability_metadata_contract_satisfied"] is True
    assert result["path_convention_action"].startswith("none")


def test_charlotte_union_and_reconstruction_blocker_replay_cache_only():
    with network_prohibited():
        result = phase.analyze_charlotte_and_windows(REAL_CACHE)
    population = result["population_reconciliation"]
    assert population["window_union_keys"] == 257
    assert population["full_season_keys"] == 250
    assert population["full_season_keys_in_union"] == 250
    assert population["full_season_only_keys"] == []
    assert population["recovered_only_keys"] == [
        ["203901", "1630163"],
        ["1629006", "1631111"],
        ["1629684", "1641733"],
        ["1630163", "1630585"],
        ["1630163", "1631197"],
        ["1630208", "1631109"],
        ["1630544", "1631197"],
    ]
    reconstruction = result["reconstruction_analysis"]
    assert reconstruction["additive_discrepancy_count"] == 0
    assert reconstruction["rate_recomposition_using_team_possessions"]["OFF_RATING"]["discrepancies_over_0_2_count"] == 0
    assert reconstruction["rate_recomposition_using_team_possessions"]["DEF_RATING"]["discrepancies_over_0_2_count"] == 9
    assert reconstruction["rate_recomposition_using_team_possessions"]["NET_RATING"]["discrepancies_over_0_2_count"] == 10
    assert "opponent possessions" in reconstruction["missing_definition_fields"][0]


def test_no_noncapped_validation_package_exists_in_cached_ledgers():
    with network_prohibited():
        inventory = phase.analyze_charlotte_and_windows(REAL_CACHE)["all_cached_partition_inventory"]
    assert inventory["full_season_team_count"] == 30
    assert inventory["full_season_below_250_team_count"] == 28
    assert inventory["full_season_exact_250_team_ids"] == ["1610612755", "1610612766"]
    assert len(inventory["phase1e_verified_assets"]) == 4
    assert {asset["team_id"] for asset in inventory["phase1e_verified_assets"]} == {"1610612766"}
    assert len(inventory["phase1e_planned_not_cached"]) == 4
    assert inventory["noncapped_validation_package_present"] is False


def test_summary_and_serialization_are_deterministic(tmp_path):
    with network_prohibited():
        first = phase.build_summary(REAL_CACHE)
        second = phase.build_summary(REAL_CACHE)
    assert first == second
    assert phase.canonical_content_hash(first) == first["deterministic_content_sha256"]
    one = phase.write_summary(tmp_path / "one", first)
    two = phase.write_summary(tmp_path / "two", second)
    assert one.read_bytes() == two.read_bytes()
    assert hashlib.sha256(one.read_bytes()).hexdigest() == hashlib.sha256(two.read_bytes()).hexdigest()
    assert json.loads(one.read_text(encoding="utf-8")) == first
    assert first["evidence_classification"]["cache_only_reconstruction_validation_feasible"] is False

