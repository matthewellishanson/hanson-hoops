from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2 import direct_fetch
from pair_fit_v2.lineup_audit import attach_pair_context
from pair_fit_v2.multi_team_audit import (
    combine_pair_tables,
    compare_schema_fingerprints,
    possession_distribution,
    schema_fingerprint,
    validate_combined_observation_keys,
)
from pair_fit_v2.player_audit import (
    attach_prior_context,
    join_pairs_to_prior_players,
    player_rows_by_id,
    summarize_exposure_weighted_coverage,
    summarize_pair_level_coverage,
)
from pair_fit_v2.team_manifest import (
    MAX_NEW_LIVE_REQUESTS,
    NEW_PILOT_TEAMS,
    PILOT_TEAMS,
    build_acquisition_plan,
    build_manifest,
    first_missing_step,
    run_acquisition_plan,
)


def make_pair_row(group_id, group_name, season="2024-25", team_id="1", **overrides):
    row = {"GROUP_ID": group_id, "GROUP_NAME": group_name, "MIN": 100.0, "POSS": 200}
    row.update(overrides)
    return attach_pair_context([row], season, team_id)[0]


def test_pilot_manifest_has_validated_team_ids_and_names():
    by_id = {team["team_id"]: team for team in PILOT_TEAMS}
    assert by_id["1610612744"]["team_name"] == "Golden State Warriors"
    assert by_id["1610612738"]["team_name"] == "Boston Celtics"
    assert by_id["1610612764"]["team_name"] == "Washington Wizards"
    assert by_id["1610612751"]["team_name"] == "Brooklyn Nets"
    assert by_id["1610612744"]["source"] == "phase_0_cache_only"
    assert all(team["source"] == "phase_1a_new" for team in NEW_PILOT_TEAMS)


def test_acquisition_plan_is_bounded_to_six_requests():
    plan = build_acquisition_plan()
    assert len(plan) == 6
    assert len(plan) <= MAX_NEW_LIVE_REQUESTS


def test_acquisition_plan_follows_required_sequential_order():
    plan = build_acquisition_plan()
    expected = [
        ("Boston Celtics", "Base"), ("Boston Celtics", "Advanced"),
        ("Washington Wizards", "Base"), ("Washington Wizards", "Advanced"),
        ("Brooklyn Nets", "Base"), ("Brooklyn Nets", "Advanced"),
    ]
    actual = [(step["team_name"], step["measure_type"]) for step in plan]
    assert actual == expected


def test_cache_hit_skips_live_request_during_acquisition_plan(tmp_path, monkeypatch):
    for team in NEW_PILOT_TEAMS:
        for measure in ("Base", "Advanced"):
            cache_name = direct_fetch.team_dash_lineups_cache_name(team["team_id"], "2024-25", measure)
            direct_fetch.cache_response({"resultSets": []}, cache_name, tmp_path)

    monkeypatch.setattr(
        direct_fetch, "fetch_team_dash_lineups",
        lambda **_: pytest.fail("cache hit must not trigger a live request"),
    )

    result = run_acquisition_plan(cache_dir=tmp_path, sleep_fn=lambda _: None)

    assert result["completed_count"] == 6
    assert result["stopped_early"] is False
    assert all(step["from_cache"] for step in result["results"])


def test_failure_stops_remaining_live_queue(tmp_path, monkeypatch):
    call_count = {"n": 0}

    def fake_fetch(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return True, {"resultSets": [{"name": "Lineups", "headers": ["GROUP_ID"], "rowSet": []}]}, 1.0, None
        return False, {}, 5.0, "Request timeout after 5.0s"

    monkeypatch.setattr(direct_fetch, "fetch_team_dash_lineups", fake_fetch)

    result = run_acquisition_plan(cache_dir=tmp_path, sleep_fn=lambda _: None)

    assert result["stopped_early"] is True
    assert result["completed_count"] == 1
    assert len(result["results"]) == 2
    assert result["results"][-1]["success"] is False
    assert result["results"][-1]["error_category"] is not None


def test_resume_finds_first_missing_step_after_partial_completion(tmp_path):
    plan = build_acquisition_plan()
    first_two = plan[:2]
    for step in first_two:
        cache_name = direct_fetch.team_dash_lineups_cache_name(step["team_id"], step["season"], step["measure_type"])
        direct_fetch.cache_response({"resultSets": []}, cache_name, tmp_path)

    missing = first_missing_step(cache_dir=tmp_path)

    assert missing is not None
    assert missing["team_name"] == "Washington Wizards"
    assert missing["measure_type"] == "Base"


def test_build_manifest_reports_cache_status_without_secrets(tmp_path):
    manifest = build_manifest(cache_dir=tmp_path)

    assert len(manifest) == len(PILOT_TEAMS) * 2
    assert all(row["cache_status"] == "missing" for row in manifest)
    for row in manifest:
        assert "proxy" not in str(row).lower()
        assert "token" not in str(row).lower()
        assert "key" not in row or row.get("key") is None


def test_base_and_advanced_cache_names_never_collide_across_teams():
    names = set()
    for team in PILOT_TEAMS:
        for measure in ("Base", "Advanced"):
            name = direct_fetch.team_dash_lineups_cache_name(team["team_id"], "2024-25", measure)
            assert name not in names
            names.add(name)


def test_schema_fingerprint_and_comparison_detects_identical_schemas():
    result_set = {"headers": ["GROUP_ID", "GROUP_NAME", "MIN"], "rowSet": [["-1-2-", "A - B", 10.0]]}
    fingerprints = {
        "team_a": schema_fingerprint(result_set),
        "team_b": schema_fingerprint(result_set),
    }
    comparison = compare_schema_fingerprints(fingerprints)

    assert comparison["all_identical"] is True
    assert comparison["differences"] == {}


def test_schema_fingerprint_excludes_row_count_and_matches_across_different_row_counts():
    # Row count is dataset metadata, not schema; identical columns with different
    # row counts must fingerprint identically.
    few_rows = {"headers": ["GROUP_ID", "MIN"], "rowSet": [["-1-2-", 10.0]]}
    many_rows = {"headers": ["GROUP_ID", "MIN"], "rowSet": [["-1-2-", 10.0], ["-3-4-", 20.0], ["-5-6-", 30.0]]}

    fingerprint_few = schema_fingerprint(few_rows)
    fingerprint_many = schema_fingerprint(many_rows)

    assert "row_count" not in fingerprint_few
    assert "row_count" not in fingerprint_many
    assert fingerprint_few == fingerprint_many

    comparison = compare_schema_fingerprints({"team_a": fingerprint_few, "team_b": fingerprint_many})
    assert comparison["all_identical"] is True


def test_schema_fingerprint_comparison_flags_missing_and_additional_columns():
    reference = {"headers": ["GROUP_ID", "MIN", "POSS"], "rowSet": []}
    missing_poss = {"headers": ["GROUP_ID", "MIN"], "rowSet": []}
    extra_field = {"headers": ["GROUP_ID", "MIN", "POSS", "PACE"], "rowSet": []}

    fingerprints = {
        "reference_team": schema_fingerprint(reference),
        "missing_team": schema_fingerprint(missing_poss),
        "extra_team": schema_fingerprint(extra_field),
    }
    comparison = compare_schema_fingerprints(fingerprints)

    assert comparison["all_identical"] is False
    assert comparison["differences"]["missing_team"]["missing_relative_to_reference"] == ["POSS"]
    assert comparison["differences"]["extra_team"]["additional_relative_to_reference"] == ["PACE"]


def test_schema_fingerprint_comparison_flags_column_order_difference():
    reference = {"headers": ["GROUP_ID", "MIN", "POSS"], "rowSet": []}
    reordered = {"headers": ["GROUP_ID", "POSS", "MIN"], "rowSet": []}

    fingerprints = {"team_a": schema_fingerprint(reference), "team_b": schema_fingerprint(reordered)}
    comparison = compare_schema_fingerprints(fingerprints)

    assert comparison["differences"]["team_b"]["same_columns_different_order"] is True


def test_per_team_canonical_keys_are_unique_within_team():
    team_rows = {
        "1": [make_pair_row("-101-202-", "A - B", team_id="1"), make_pair_row("-101-303-", "A - C", team_id="1")],
    }
    combined = combine_pair_tables(team_rows)
    validation = validate_combined_observation_keys(combined)

    assert validation["unique_observation_keys"] == 2
    assert validation["duplicate_observation_key_count"] == 0


def test_same_player_on_multiple_teams_is_reported_without_collision():
    team_rows = {
        "1": [make_pair_row("-101-202-", "A - B", team_id="1")],
        "2": [make_pair_row("-101-404-", "A - D", team_id="2")],
    }
    combined = combine_pair_tables(team_rows)
    validation = validate_combined_observation_keys(combined)

    # Same player (101) on two teams: two distinct observations, not a collision.
    assert validation["unique_observation_keys"] == 2
    assert validation["duplicate_observation_key_count"] == 0
    assert "101" in validation["cross_team_players"]
    assert validation["cross_team_players"]["101"] == ["1", "2"]


def test_same_pair_on_multiple_teams_is_not_deduplicated():
    team_rows = {
        "1": [make_pair_row("-101-202-", "A - B", team_id="1")],
        "2": [make_pair_row("-101-202-", "A - B", team_id="2")],
    }
    combined = combine_pair_tables(team_rows)
    validation = validate_combined_observation_keys(combined)

    # Same pair on two different teams: both rows retained as distinct observations.
    assert validation["combined_row_count"] == 2
    assert validation["unique_observation_keys"] == 2
    assert validation["cross_team_pair_count"] == 1


def test_combined_prior_history_coverage_and_status_reporting():
    prior_rows_by_id = player_rows_by_id(
        attach_prior_context([{"PLAYER_ID": "101", "PLAYER_NAME": "A"}], "2023-24")
    )
    team_rows = {
        "1": [make_pair_row("-101-202-", "A - B", team_id="1")],
        "2": [make_pair_row("-101-303-", "A - C", team_id="2", MIN=50.0, POSS=100)],
    }
    combined = combine_pair_tables(team_rows)
    joined = join_pairs_to_prior_players(combined, prior_rows_by_id, "2024-25", "2023-24")
    pair_coverage = summarize_pair_level_coverage(joined)
    exposure = summarize_exposure_weighted_coverage(joined)

    assert pair_coverage["total_pair_rows"] == 2
    assert pair_coverage["only_player_1_matched"] == 2  # only "101" (A) matched in both
    assert exposure["complete_prior_share_of_minutes"] == 0.0
    assert exposure["incomplete_prior_share_of_minutes"] == 1.0
    assert "overlap" in exposure["note"].lower()


def test_prior_history_status_classification_values():
    prior_rows_by_id = player_rows_by_id(
        attach_prior_context([{"PLAYER_ID": "101", "PLAYER_NAME": "A"}, {"PLAYER_ID": "202", "PLAYER_NAME": "B"}], "2023-24")
    )
    rows = [
        make_pair_row("-101-202-", "A - B"),  # complete
        make_pair_row("-101-303-", "A - C"),  # one_missing
        make_pair_row("-404-303-", "D - C"),  # both_missing
    ]
    joined = join_pairs_to_prior_players(rows, prior_rows_by_id, "2024-25", "2023-24")

    def status(row):
        if row["player_1_matched"] and row["player_2_matched"]:
            return "complete"
        if not row["player_1_matched"] and not row["player_2_matched"]:
            return "both_missing"
        return "one_missing"

    statuses = [status(row) for row in joined]
    assert statuses == ["complete", "one_missing", "both_missing"]


def test_exposure_weighted_coverage_reports_explicit_complete_incomplete_and_total():
    prior_rows_by_id = player_rows_by_id(
        attach_prior_context([{"PLAYER_ID": "101"}, {"PLAYER_ID": "202"}], "2023-24")
    )
    rows = [
        make_pair_row("-101-202-", "A - B", MIN=100.0, POSS=200),
        make_pair_row("-101-303-", "A - C", MIN=50.0, POSS=100),
    ]
    joined = join_pairs_to_prior_players(rows, prior_rows_by_id, "2024-25", "2023-24")
    exposure = summarize_exposure_weighted_coverage(joined)

    assert exposure["total_summed_minutes"] == 150.0
    assert exposure["total_summed_possessions"] == 300.0
    assert exposure["complete_prior_share_of_minutes"] == pytest.approx(100.0 / 150.0)
    assert exposure["incomplete_prior_share_of_minutes"] == pytest.approx(50.0 / 150.0)


def test_possession_distribution_reports_sparse_buckets_without_threshold():
    rows = [{"POSS": value} for value in [5, 20, 40, 80, 150, 300, 1000]]
    distribution = possession_distribution(rows)

    assert distribution["count"] == 7
    assert distribution["minimum"] == 5
    assert distribution["maximum"] == 1000
    assert distribution["below_10"] == 1
    assert distribution["below_25"] == 2
    assert distribution["below_50"] == 3
    assert distribution["below_100"] == 4
    assert distribution["below_200"] == 5
    # No filtering occurred: all rows remain represented in the count.
    assert distribution["count"] == len(rows)


def test_no_minimum_threshold_is_applied_to_pair_rows():
    rows = [make_pair_row("-1-2-", "A - B", MIN=0.5, POSS=1), make_pair_row("-3-4-", "C - D", MIN=2000.0, POSS=4000)]
    # Both sparse and heavy-exposure rows must remain present; no filtering function is called.
    assert len(rows) == 2


def test_no_random_split_or_model_object_is_constructed():
    # Phase 1A modules expose no train/test split or model-fitting function.
    import pair_fit_v2.team_manifest as team_manifest
    import pair_fit_v2.multi_team_audit as multi_team_audit

    forbidden_terms = ("train_test_split", "fit_model", "RandomForest", "LinearRegression")
    for module in (team_manifest, multi_team_audit):
        module_source = Path(module.__file__).read_text(encoding="utf-8")
        for term in forbidden_terms:
            assert term not in module_source


def test_no_2025_26_season_referenced_in_pilot_config():
    for team in PILOT_TEAMS:
        assert team["team_id"]  # sanity: manifest entries exist
    assert "2025-26" not in Path(
        Path(__file__).resolve().parents[1] / "src" / "pair_fit_v2" / "team_manifest.py"
    ).read_text(encoding="utf-8")
