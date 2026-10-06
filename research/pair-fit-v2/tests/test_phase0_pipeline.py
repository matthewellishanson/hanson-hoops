from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2.cache import JsonCache
from pair_fit_v2.config import Phase0Config
from pair_fit_v2.schema import canonical_pair_key, summarize_pair_feasibility, validate_pair_rows


def test_phase0_config_defaults_are_research_safe():
    config = Phase0Config()
    assert config.target_season == "2024-25"
    assert config.prior_season == "2023-24"
    assert config.season_type == "Regular Season"
    assert config.group_quantity == 2
    assert config.measure_types == ["Base", "Advanced", "Four Factors", "Usage"]
    assert config.allow_live_calls is False


def test_pair_identity_is_order_independent_and_canonicalized():
    assert canonical_pair_key("204", "101") == ("101", "204")
    assert canonical_pair_key("101", "204") == ("101", "204")
    assert canonical_pair_key("101", "101") == ("101", "101")


def test_pair_rows_are_validated_and_duplicates_flagged():
    rows = [
        {
            "GROUP_ID": "pair_1",
            "GROUP_NAME": "Player 101 - Player 204",
            "TEAM_ID": 1,
            "MIN": 100.0,
            "GP": 5,
            "PTS": 130.0,
            "ORTG": 118.0,
            "DRTG": 112.0,
        },
        {
            "GROUP_ID": "pair_1",
            "GROUP_NAME": "Player 101 - Player 204",
            "TEAM_ID": 1,
            "MIN": 100.0,
            "GP": 5,
            "PTS": 130.0,
            "ORTG": 118.0,
            "DRTG": 112.0,
        },
        {
            "GROUP_ID": "pair_bad",
            "GROUP_NAME": "Player 101",
            "TEAM_ID": 1,
            "MIN": 0.0,
            "GP": 0,
            "PTS": 0.0,
            "ORTG": None,
            "DRTG": None,
        },
    ]

    result = validate_pair_rows(rows)
    assert result["valid_rows"] == 1
    assert result["duplicate_rows"] == 1
    assert result["invalid_rows"] == 1
    assert result["unique_pairs"] == 1


def test_reference_join_summary_reports_complete_and_missing_rows():
    pair_rows = [
        {"pair_key": ("101", "204"), "MIN": 150.0, "team_id": 1},
        {"pair_key": ("101", "205"), "MIN": 80.0, "team_id": 1},
        {"pair_key": ("102", "205"), "MIN": 10.0, "team_id": 1},
    ]
    prior_features = {
        "101": {"player_id": 101, "usage_pct": 20.0},
        "204": {"player_id": 204, "usage_pct": 18.0},
        "205": {"player_id": 205, "usage_pct": 25.0},
    }

    summary = summarize_pair_feasibility(pair_rows, prior_features)
    assert summary["pair_rows"] == 3
    assert summary["complete_prior_rows"] == 2
    assert summary["missing_prior_rows"] == 1
    assert summary["complete_prior_rate"] == 0.6666666666666666


def test_cache_roundtrip_writes_json_and_reads_back(tmp_path):
    cache = JsonCache(tmp_path / "cache")
    payload = {"season": "2024-25", "rows": [{"GROUP_ID": "x"}]}
    path = cache.write("feature_fixture", payload)
    assert path.exists()
    assert cache.read("feature_fixture") == payload
    assert cache.read("does_not_exist") is None
