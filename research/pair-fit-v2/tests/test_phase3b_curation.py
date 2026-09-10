import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3b_curation as phase


CACHE = Path(__file__).parents[1] / "cache"


@pytest.fixture(scope="module")
def curated(tmp_path_factory):
    output = tmp_path_factory.mktemp("phase3b")
    return output, phase.build(CACHE, output)


def _rows(output, floor):
    with (output / f"phase3b_poss_ge_{floor}.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_prerequisites_and_source_population_replay(curated):
    _, summary = curated
    assert summary["source_population_rows"] == summary["source_population_phase3a_rows"] == 46938
    assert summary["prerequisites"]["phase3a_population_audit_sha256"] == "dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f"
    assert summary["prerequisites"]["phase3a1_shot_profile_replay_sha256"] == "54743fee0db29f1847ecb46b2dae8ec07871d3a323e88d6a64fdff735c5d1b47"
    assert summary["network"] == "prohibited"


def test_thresholds_and_target_period_leakage_contract(curated):
    output, summary = curated
    assert summary["retention"] == {"poss_ge_100": {"retained_rows": 30580, "excluded_raw_rows": 16358}, "poss_ge_150": {"retained_rows": 27001, "excluded_raw_rows": 19937}}
    rows100, rows150 = _rows(output, 100), _rows(output, 150)
    assert all(float(row["pair_possessions"]) >= 100 for row in rows100)
    assert all(float(row["pair_possessions"]) >= 150 for row in rows150)
    manifest = json.loads((output / "phase3b_feature_manifest.json").read_text())
    assert "pair_possessions" not in manifest["future_estimator_features"]
    assert "target_net_rating" not in manifest["future_estimator_features"]
    assert "target-season pair pace/rating/minutes/statistics" in manifest["prohibited_predictors"]


def test_canonical_keys_stable_order_and_target_identity(curated):
    output, _ = curated
    rows = _rows(output, 100)
    keys = [(r["target_season"], int(r["team_id"]), int(r["player_1_id"]), int(r["player_2_id"])) for r in rows]
    assert keys == sorted(keys) and len(keys) == len(set(keys))
    assert all(key[2] < key[3] for key in keys)
    assert all(abs(float(r["target_net_rating"]) - (float(r["target_off_rating_audit"]) - float(r["target_def_rating_audit"]))) <= .1000001 for r in rows)


def test_history_selection_missingness_and_no_imputation(curated):
    output, _ = curated
    rows = _rows(output, 150)
    assert {r["history_status"] for r in rows} == {"complete", "one_missing", "both_missing"}
    for row in rows:
        for slot in ("1", "2"):
            season, gap = row[f"player_{slot}_history_profile_season"], row[f"player_{slot}_history_gap"]
            if row[f"player_{slot}_history_missing"] == "1":
                assert season == gap == "" and row[f"player_{slot}_age"] == ""
            else:
                assert int(season[:4]) < int(row["target_season"][:4])
                assert 1 <= int(float(gap)) <= 3
                assert row[f"player_{slot}_profile_source_per100_path"]
                assert season in row[f"player_{slot}_shot_source_path"]


def test_shot_residual_corner_and_zero_attempt_contract(curated):
    output, _ = curated
    for row in _rows(output, 100):
        for slot in ("1", "2"):
            if row[f"player_{slot}_history_missing"] == "1":
                continue
            prefix = f"player_{slot}_shot_"
            assert int(row[prefix + "classified_fga"]) + int(row[prefix + "unclassified_fga"]) == int(row[prefix + "overall_fga"])
            assert int(row[prefix + "left_corner_three_fga"]) + int(row[prefix + "right_corner_three_fga"]) >= 0
            for zone in phase.ZONE_KEYS:
                attempts = int(row[prefix + zone + "_fga"])
                assert int(row[prefix + zone + "_attempted_zone"]) == int(attempts > 0)
    manifest = json.loads((output / "phase3b_feature_manifest.json").read_text())
    assert "undefined/null" in manifest["shot_profile_raw_inputs"]["zero_attempt_efficiency"]
    assert "source Corner 3 aggregate" in manifest["prohibited_predictors"]


def test_symmetric_future_contract_and_weights(curated):
    output, _ = curated
    manifest = json.loads((output / "phase3b_feature_manifest.json").read_text())
    assert all("player_1" not in f and "player_2" not in f for f in manifest["future_estimator_features"])
    first = phase.symmetric_pair_features({"AST": 2}, {"AST": 8}, ("AST",))
    second = phase.symmetric_pair_features({"AST": 8}, {"AST": 2}, ("AST",))
    assert first == second == {"pair_mean.AST": 5.0, "pair_absolute_difference.AST": 6.0}
    assert phase.symmetric_pair_features({"AST": None}, {"AST": 8}, ("AST",))["pair_mean.AST"] is None
    assert "candidate_weight_possessions_capped_300" in manifest["weight_candidates"]
    assert all("linear_possessions" not in weight for weight in manifest["weight_candidates"])
    assert "prior shared-pair experience" in manifest["prohibited_predictors"]


def test_most_recent_strict_history_selection_never_uses_future():
    profiles = {
        "2018-19": {"7": {"PLAYER_ID": "7"}},
        "2020-21": {"7": {"PLAYER_ID": "7"}},
        "2023-24": {"7": {"PLAYER_ID": "7"}},
    }
    season, gap, _ = phase._select_history("2021-22", "7", profiles)
    assert (season, gap) == ("2020-21", 1)
    season, gap, _ = phase._select_history("2020-21", "7", profiles)
    assert (season, gap) == ("2018-19", 2)
    season, gap, _ = phase._select_history("2018-19", "7", profiles)
    assert (season, gap) == (None, None)


def test_artifact_hashes_and_summary_are_deterministic(curated):
    output, summary = curated
    replay = phase.build(CACHE, output)
    assert replay["deterministic_content_sha256"] == summary["deterministic_content_sha256"]
    for artifact in summary["artifacts"].values():
        path = output / artifact["relative_path"]
        if "sha256" in artifact:
            import hashlib
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]


@pytest.mark.parametrize("team_count, expected", [(1, 0), (2, 1), (3.0, 1), (None, None), ("bad", None), (1.5, None), (0, None), (-1, None)])
def test_traded_history_indicator_is_known_only(team_count, expected):
    assert phase.traded_history_indicator(team_count) == expected


@pytest.mark.parametrize("left,right,expected", [(0, 0, 0), (0, 1, 1), (1, 1, 2), (None, 0, None), (1, None, None)])
def test_pair_traded_history_count(left, right, expected):
    assert phase.pair_traded_history_count(left, right) == expected


def _shot_profile(**changes):
    value = {
        "shot_restricted_area_fga": 0, "shot_non_restricted_paint_fga": 0,
        "shot_mid_range_fga": 0, "shot_left_corner_three_fga": 0,
        "shot_right_corner_three_fga": 0, "shot_above_the_break_three_fga": 0,
        "shot_backcourt_fga": 0, "shot_unclassified_fga": 0,
        "shot_overall_fga": 10,
    }
    value.update(changes)
    return value


def test_shot_distribution_l1_special_feature_contract():
    identical = _shot_profile(shot_restricted_area_fga=10)
    partial = _shot_profile(shot_restricted_area_fga=5, shot_mid_range_fga=5)
    disjoint = _shot_profile(shot_mid_range_fga=10)
    residual = _shot_profile(shot_unclassified_fga=10)
    assert phase.shot_distribution_l1_distance_overall_fga(identical, identical) == 0
    assert phase.shot_distribution_l1_distance_overall_fga(identical, partial) == 1
    assert phase.shot_distribution_l1_distance_overall_fga(identical, disjoint) == 2
    assert phase.shot_distribution_l1_distance_overall_fga(identical, residual) == 2
    assert phase.shot_distribution_l1_distance_overall_fga(identical, {}) is None
    assert phase.shot_distribution_l1_distance_overall_fga(identical, _shot_profile(shot_overall_fga=0)) is None


def test_manifest_partition_and_redundancy_correction():
    manifest = phase.feature_manifest()
    predictors = set(manifest["future_estimator_features"])
    assert len(predictors) == 52
    removed = {"pair_mean.GP", "pair_absolute_difference.GP", "pair_mean.TOTAL_MIN", "pair_absolute_difference.TOTAL_MIN", "pair_combined_overall_fga", "pair_any_traded_history", "pair_mean.shot_overall_three_point_location_share_overall", "pair_mean.shot_classified_attempt_coverage"}
    assert not predictors & removed
    assert phase.validate_feature_manifest(manifest)["valid"]
    bad = json.loads(json.dumps(manifest))
    bad["authoritative_categories"]["identifiers"].append("unknown_column")
    with pytest.raises(ValueError, match="unknown referenced"):
        phase.validate_feature_manifest(bad)
    bad = json.loads(json.dumps(manifest))
    bad["authoritative_categories"]["reliability_metadata"].append("pair_mean.AST")
    with pytest.raises(ValueError, match="multiple categories"):
        phase.validate_feature_manifest(bad)
