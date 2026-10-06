from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2 import direct_fetch
from pair_fit_v2.lineup_audit import (
    attach_pair_context,
    extract_result_set,
    join_pair_measures,
    parse_pair_group_id,
    result_set_rows,
    summarize_advanced_targets,
)


ADVANCED_HEADERS = [
    "GROUP_ID", "GROUP_NAME", "GP", "MIN", "E_OFF_RATING", "OFF_RATING",
    "E_DEF_RATING", "DEF_RATING", "E_NET_RATING", "NET_RATING", "POSS", "PACE",
]


def advanced_row(group_id: str = "-201939-203110-", **overrides):
    row = {
        "GROUP_ID": group_id,
        "GROUP_NAME": "S. Curry - D. Green",
        "GP": 60,
        "MIN": 1419.0,
        "E_OFF_RATING": 118.0,
        "OFF_RATING": 118.2,
        "E_DEF_RATING": 110.8,
        "DEF_RATING": 110.9,
        "E_NET_RATING": 7.1,
        "NET_RATING": 7.3,
        "POSS": 3046,
        "PACE": 102.79,
    }
    row.update(overrides)
    return row


def contextual(rows):
    return attach_pair_context(rows, "2024-25", "1610612744")


def test_advanced_request_uses_observed_bounded_parameters(monkeypatch):
    requested = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"resultSets": []}

    class Session:
        @staticmethod
        def get(url, timeout):
            requested["url"] = url
            requested["timeout"] = timeout
            return Response()

    monkeypatch.setattr(direct_fetch, "create_research_session", lambda: Session())
    success, _, _, error = direct_fetch.fetch_team_dash_lineups(
        "1610612744", measure_type="Advanced", timeout=30
    )

    assert success and error is None
    assert "TeamID=1610612744" in requested["url"]
    assert "Season=2024-25" in requested["url"]
    assert "SeasonType=Regular+Season" in requested["url"]
    assert "GroupQuantity=2" in requested["url"]
    assert "MeasureType=Advanced" in requested["url"]
    assert requested["timeout"] == 30


def test_advanced_cache_name_cannot_collide_with_base():
    assert direct_fetch.team_dash_lineups_cache_name("1610612744", "2024-25", "Base") == (
        "team_dash_lineups_1610612744_2024-25_base.json"
    )
    assert direct_fetch.team_dash_lineups_cache_name("1610612744", "2024-25", "Advanced") == (
        "team_dash_lineups_1610612744_2024-25_advanced.json"
    )


def test_cache_hit_avoids_live_request(tmp_path, monkeypatch):
    cache_name = direct_fetch.team_dash_lineups_cache_name("1610612744", "2024-25", "Advanced")
    direct_fetch.cache_response({"resultSets": []}, cache_name, tmp_path)
    monkeypatch.setattr(
        direct_fetch,
        "fetch_team_dash_lineups",
        lambda **_: pytest.fail("cache hit must not make a live request"),
    )

    success, payload, elapsed, error, from_cache = direct_fetch.load_or_fetch_team_dash_lineups(
        "1610612744", measure_type="Advanced", cache_dir=tmp_path
    )

    assert (success, payload, elapsed, error, from_cache) == (True, {"resultSets": []}, 0.0, None, True)


def test_result_set_validation_rejects_missing_or_malformed_data():
    with pytest.raises(ValueError, match="resultSets"):
        extract_result_set({}, "Lineups")
    with pytest.raises(ValueError, match="Lineups"):
        extract_result_set({"resultSets": []}, "Lineups")
    with pytest.raises(ValueError, match="header count"):
        result_set_rows({"headers": ["GROUP_ID", "MIN"], "rowSet": [["-1-2-"]]})


def test_actual_observed_advanced_pair_token_structure_is_parsed_canonically():
    assert parse_pair_group_id("-201939-203110-") == ("201939", "203110")
    assert parse_pair_group_id("-203110-201939-") == ("201939", "203110")
    assert parse_pair_group_id("-201939-201939-") is None
    assert parse_pair_group_id("malformed") is None


def test_result_set_rows_creates_validated_table():
    row = advanced_row()
    result_set = {"headers": ADVANCED_HEADERS, "rowSet": [[row[field] for field in ADVANCED_HEADERS]]}
    assert result_set_rows(result_set) == [row]


def test_canonical_join_reports_one_to_one_and_unmatched_pairs():
    base = contextual([advanced_row(), advanced_row("-203110-1626171-")])
    advanced = contextual([advanced_row(), advanced_row("-203110-1629008-")])
    summary = join_pair_measures(base, advanced)

    assert summary["base_unique_pairs"] == 2
    assert summary["advanced_unique_pairs"] == 2
    assert summary["matched_pairs"] == 1
    assert summary["base_only_pairs"] == 1
    assert summary["advanced_only_pairs"] == 1
    assert summary["base_match_rate"] == 0.5
    assert summary["advanced_match_rate"] == 0.5
    assert summary["one_to_one"] is True


def test_canonical_join_reports_duplicate_key_violations():
    duplicated = contextual([advanced_row(), advanced_row("-203110-201939-")])
    summary = join_pair_measures(duplicated, contextual([advanced_row()]))

    assert summary["base_duplicate_key_violations"] == 1
    assert summary["one_to_one"] is False


def test_target_summary_detects_zero_or_missing_possessions_and_missing_ratings():
    rows = contextual([
        advanced_row(POSS=0),
        advanced_row("-203110-1626171-", POSS=None, OFF_RATING=None, NET_RATING="bad"),
    ])
    summary = summarize_advanced_targets(rows)

    assert summary["zero_or_missing_possessions"] == 2
    assert summary["POSS"]["zero"] == 1
    assert summary["POSS"]["missing"] == 1
    assert summary["OFF_RATING"]["missing"] == 1
    assert summary["NET_RATING"]["nonnumeric"] == 1


def test_net_rating_consistency_allows_observed_rounding_behavior():
    summary = summarize_advanced_targets(contextual([advanced_row(NET_RATING=7.2)]))

    assert summary["net_rating_consistency"]["max_absolute_difference"] == pytest.approx(0.1)
    assert summary["net_rating_consistency"]["rounding_consistent"] is True
    assert summary["estimated_net_rating_consistency"]["max_absolute_difference"] == pytest.approx(0.1)
    assert summary["estimated_net_rating_consistency"]["rounding_consistent"] is True


def test_cumulative_plus_minus_is_not_substituted_for_rate_target():
    row = advanced_row(PLUS_MINUS=239)
    summary = summarize_advanced_targets(contextual([row]))

    assert row["PLUS_MINUS"] == 239
    assert summary["NET_RATING"]["present"] is True
    assert summary["NET_RATING"]["mean"] == 7.3