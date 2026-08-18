from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2 import direct_fetch
from pair_fit_v2.lineup_audit import attach_pair_context
from pair_fit_v2.player_audit import (
    audit_stable_ids,
    attach_prior_context,
    join_pairs_to_prior_players,
    player_rows_by_id,
    summarize_exposure_weighted_coverage,
    summarize_pair_level_coverage,
    summarize_player_level_coverage,
    summarize_prior_feature_fields,
)


def player_row(player_id="203110", name="D. Green", team_id=1610612744, team_abbr="GSW", **overrides):
    row = {
        "PLAYER_ID": player_id,
        "PLAYER_NAME": name,
        "TEAM_ID": team_id,
        "TEAM_ABBREVIATION": team_abbr,
        "AGE": 33.0,
        "GP": 76,
        "MIN": 30.1,
        "FG_PCT": 0.5,
        "FG3_PCT": 0.39,
        "FT_PCT": 0.7,
        "TEAM_COUNT": 1,
    }
    row.update(overrides)
    return row


def pair_row(group_id="-201939-203110-", group_name="S. Curry - D. Green", **overrides):
    row = {"GROUP_ID": group_id, "GROUP_NAME": group_name, "MIN": 1419.0, "POSS": 3046}
    row.update(overrides)
    return attach_pair_context([row], "2024-25", "1610612744")[0]


def test_league_dash_player_stats_url_uses_normalized_parameters(monkeypatch):
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
    success, _, _, error = direct_fetch.fetch_league_dash_player_stats(
        season="2023-24", season_type="Regular Season", measure_type="Base",
        per_mode="Per100Possessions", league_id="00", timeout=30,
    )

    assert success and error is None
    assert "leaguedashplayerstats" in requested["url"]
    assert "Season=2023-24" in requested["url"]
    assert "SeasonType=Regular+Season" in requested["url"]
    assert "MeasureType=Base" in requested["url"]
    assert "PerMode=Per100Possessions" in requested["url"]
    assert "LeagueID=00" in requested["url"]
    assert requested["timeout"] == 30


def test_cache_name_identifies_endpoint_season_measure_and_per_mode_without_collision():
    player_cache = direct_fetch.league_dash_player_stats_cache_name("2023-24", "Base", "Per100Possessions")
    lineup_cache = direct_fetch.team_dash_lineups_cache_name("1610612744", "2024-25", "Base")

    assert player_cache == "league_dash_player_stats_2023-24_base_per100possessions.json"
    assert player_cache != lineup_cache


def test_player_stats_cache_hit_avoids_live_request(tmp_path, monkeypatch):
    cache_name = direct_fetch.league_dash_player_stats_cache_name("2023-24", "Base", "Per100Possessions")
    direct_fetch.cache_response({"resultSets": []}, cache_name, tmp_path)
    monkeypatch.setattr(
        direct_fetch,
        "fetch_league_dash_player_stats",
        lambda **_: pytest.fail("cache hit must not make a live request"),
    )

    success, payload, elapsed, error, from_cache = direct_fetch.load_or_fetch_league_dash_player_stats(
        cache_dir=tmp_path
    )

    assert (success, payload, elapsed, error, from_cache) == (True, {"resultSets": []}, 0.0, None, True)


def test_stable_id_audit_detects_no_duplicates_for_unique_ids():
    rows = [player_row("1", "Player One"), player_row("2", "Player Two")]
    audit = audit_stable_ids(rows)

    assert audit["raw_player_rows"] == 2
    assert audit["unique_player_ids"] == 2
    assert audit["duplicate_player_id_count"] == 0
    assert audit["appears_one_row_per_player"] is True


def test_stable_id_audit_reports_duplicate_ids_without_resolving_them():
    rows = [
        player_row("1", "Player One", team_abbr="TM1"),
        player_row("1", "Player One", team_abbr="TM2"),
    ]
    audit = audit_stable_ids(rows)

    assert audit["duplicate_player_id_count"] == 1
    assert audit["duplicate_player_ids"] == {"1": 2}
    assert audit["appears_one_row_per_player"] is False
    # No silent first/last-row resolution: both rows' team context is preserved.
    assert len(audit["duplicate_id_team_context"]["1"]) == 2


def test_stable_id_audit_flags_missing_and_malformed_ids():
    rows = [player_row("1"), {"PLAYER_ID": None, "PLAYER_NAME": "Unknown"}, {"PLAYER_ID": "", "PLAYER_NAME": "Blank"}]
    audit = audit_stable_ids(rows)

    assert audit["missing_or_malformed_player_ids"] == 2
    assert audit["non_null_player_ids"] == 1


def test_stable_id_audit_reports_duplicate_names_with_different_ids():
    rows = [player_row("1", "Jordan Smith"), player_row("2", "Jordan Smith")]
    audit = audit_stable_ids(rows)

    assert audit["duplicate_names_different_ids"] == {"Jordan Smith": ["1", "2"]}


def test_stable_id_audit_treats_gp_above_82_as_a_valid_traded_player_row():
    # A traded player's combined GP can exceed 82 if the two teams played a
    # different number of games at the trade date; this is not a validation failure.
    rows = [player_row("1627741", "Buddy Hield", team_abbr="PHI", GP=84, TEAM_COUNT=2)]
    audit = audit_stable_ids(rows)

    assert audit["raw_player_rows"] == 1
    assert audit["unique_player_ids"] == 1
    assert audit["duplicate_player_id_count"] == 0
    assert audit["missing_or_malformed_player_ids"] == 0
    assert audit["appears_one_row_per_player"] is True


def test_join_uses_canonical_pair_key_independently_for_both_players():
    prior_rows_by_id = player_rows_by_id(
        attach_prior_context([player_row("201939", "S. Curry"), player_row("203110", "D. Green")], "2023-24")
    )
    joined = join_pairs_to_prior_players([pair_row()], prior_rows_by_id, "2024-25", "2023-24")

    assert len(joined) == 1
    row = joined[0]
    assert row["pair_key"] == ("201939", "203110")
    assert row["player_1_matched"] and row["player_2_matched"]
    assert row["target_season"] == "2024-25"
    assert row["feature_season"] == "2023-24"


def test_join_does_not_use_name_based_fallback():
    # Prior table keyed only by PLAYER_ID; a name-only row must not match.
    prior_rows_by_id = {"999999": [player_row("999999", "S. Curry")]}
    joined = join_pairs_to_prior_players([pair_row()], prior_rows_by_id, "2024-25", "2023-24")

    assert joined[0]["player_1_matched"] is False
    assert joined[0]["player_2_matched"] is False


def test_pair_level_coverage_classifies_both_one_or_neither_matched():
    prior_rows_by_id = player_rows_by_id(
        attach_prior_context([player_row("201939", "S. Curry")], "2023-24")
    )
    rows = [
        pair_row("-201939-203110-", "S. Curry - D. Green"),  # only player 1 (203110 missing)
        pair_row("-1-2-", "A - B"),  # neither matched
    ]
    joined = join_pairs_to_prior_players(rows, prior_rows_by_id, "2024-25", "2023-24")
    coverage = summarize_pair_level_coverage(joined)

    assert coverage["total_pair_rows"] == 2
    assert coverage["both_players_matched"] == 0
    assert coverage["only_player_1_matched"] == 1
    assert coverage["neither_player_matched"] == 1
    assert coverage["complete_prior_pair_rate"] == 0.0


def test_player_level_coverage_reports_missing_ids_and_correct_names():
    prior_rows_by_id = player_rows_by_id(
        attach_prior_context([player_row("201939", "S. Curry")], "2023-24")
    )
    rows = [pair_row("-201939-203110-", "S. Curry - D. Green")]
    coverage = summarize_player_level_coverage(rows, prior_rows_by_id)

    assert coverage["unique_player_ids"] == 2
    assert coverage["unique_ids_with_prior_record"] == 1
    assert coverage["missing_player_ids"] == ["203110"]
    assert coverage["missing_player_names"]["203110"] == "D. Green"


def test_player_level_coverage_uses_raw_group_id_order_for_hyphenated_names():
    # "Jackson-Davis" must not be split as if it were the pair separator.
    prior_rows_by_id = {}
    rows = [pair_row("-1631218-1642050-", "T. Jackson-Davis - J. Rowe")]
    coverage = summarize_player_level_coverage(rows, prior_rows_by_id)

    assert coverage["missing_player_names"]["1631218"] == "T. Jackson-Davis"
    assert coverage["missing_player_names"]["1642050"] == "J. Rowe"


def test_player_level_coverage_does_not_swap_names_when_canonical_order_reverses_raw_order():
    # Regression: canonical_pair_key sorts "1642366" before "203110" lexicographically,
    # reversing the raw GROUP_ID order. Names must still attach to their own stable ID.
    prior_rows_by_id = {}
    rows = [pair_row("-203110-1642366-", "D. Green - Q. Post")]
    coverage = summarize_player_level_coverage(rows, prior_rows_by_id)

    assert coverage["missing_player_names"]["203110"] == "D. Green"
    assert coverage["missing_player_names"]["1642366"] == "Q. Post"


def test_exposure_weighted_coverage_reports_overlapping_diagnostic_shares():
    prior_rows_by_id = player_rows_by_id(
        attach_prior_context([player_row("201939", "S. Curry"), player_row("203110", "D. Green")], "2023-24")
    )
    rows = [
        pair_row("-201939-203110-", "S. Curry - D. Green", MIN=100.0, POSS=200.0),
        pair_row("-201939-999999-", "S. Curry - Unknown", MIN=50.0, POSS=100.0),
    ]
    joined = join_pairs_to_prior_players(rows, prior_rows_by_id, "2024-25", "2023-24")
    exposure = summarize_exposure_weighted_coverage(joined)

    assert exposure["complete_prior_share_of_minutes"] == pytest.approx(100.0 / 150.0)
    assert exposure["incomplete_prior_share_of_minutes"] == pytest.approx(50.0 / 150.0)
    assert exposure["complete_prior_share_of_possessions"] == pytest.approx(200.0 / 300.0)
    assert "overlap" in exposure["note"].lower()
    assert "not" in exposure["note"].lower()


def test_missing_player_record_distinguished_from_missing_feature_value():
    prior_rows_by_id = player_rows_by_id(
        attach_prior_context([player_row("201939", "S. Curry", FG3_PCT=0.0)], "2023-24")
    )
    matched_rows = prior_rows_by_id["201939"]
    missingness = summarize_prior_feature_fields(matched_rows)

    # A present record with a valid zero observation is not "missing".
    assert missingness["FG3_PCT"]["missing"] == 0
    assert missingness["FG3_PCT"]["zero"] == 1
    assert missingness["FG3_PCT"]["present_non_null"] == 1


def test_no_target_season_player_features_used_in_join():
    # Prior rows are explicitly tagged 2023-24; join must not read target-season fields.
    prior_rows_by_id = player_rows_by_id(
        attach_prior_context([player_row("201939", "S. Curry")], "2023-24")
    )
    joined = join_pairs_to_prior_players([pair_row()], prior_rows_by_id, "2024-25", "2023-24")

    assert joined[0]["feature_season"] == "2023-24"
    assert joined[0]["target_season"] == "2024-25"
    assert joined[0]["feature_season"] != joined[0]["target_season"]
    for prior_row in joined[0]["player_1_prior_rows"]:
        assert prior_row["feature_season"] == "2023-24"
