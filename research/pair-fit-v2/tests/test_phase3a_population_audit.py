from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3a_population_audit as audit


CACHE = Path(__file__).parents[1] / "cache"
EXPECTED_PHASE3A_HASH = "dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f"


@pytest.fixture(scope="module")
def summary():
    return audit.analyze(CACHE)


def test_immutable_anchors_and_population(summary):
    assert summary["immutable_evidence"]["phase1f_analysis"] == audit.PHASE1_ANCHORS["phase1f_analysis"]
    assert summary["immutable_evidence"]["phase2e_analysis"] == audit.PHASE2E_HASH
    assert summary["population"]["rows"] == 46938
    assert summary["population"]["positive_possession_rows"] == 46786
    assert summary["population"]["zero_possession_rows"] == 152
    assert summary["feature_inventory"]["profile_rows"] == 5219


def _lineup_payload(*group_ids):
    return {
        "resultSets": [
            {"name": "Lineups", "headers": ["GROUP_ID"], "rowSet": [[group_id] for group_id in group_ids]}
        ]
    }


def test_duplicate_base_keys_are_rejected_before_indexing():
    with pytest.raises(ValueError, match="duplicate Base observation keys") as exc:
        audit._reconciled_pair_indexes(
            _lineup_payload("-10-20-", "-20-10-"), _lineup_payload("-10-20-"), "2023-24", "1"
        )
    assert "('2023-24', '1', '10', '20')" in str(exc.value)


def test_duplicate_advanced_keys_are_rejected_before_indexing():
    with pytest.raises(ValueError, match="duplicate Advanced observation keys") as exc:
        audit._reconciled_pair_indexes(
            _lineup_payload("-10-20-"), _lineup_payload("-10-20-", "-20-10-"), "2023-24", "1"
        )
    assert "('2023-24', '1', '10', '20')" in str(exc.value)


def test_clean_pair_indexes_reconcile_without_collapsing_rows():
    base, advanced = audit._reconciled_pair_indexes(
        _lineup_payload("-10-20-", "-10-30-"),
        _lineup_payload("-20-10-", "-30-10-"),
        "2023-24",
        "1",
    )
    assert len(base) == len(advanced) == 2
    assert set(base) == set(advanced) == {("10", "20"), ("10", "30")}


def test_unmatched_base_and_advanced_keys_are_rejected():
    with pytest.raises(ValueError, match="Base/Advanced pair reconciliation failure") as exc:
        audit._reconciled_pair_indexes(
            _lineup_payload("-10-20-"), _lineup_payload("-10-30-"), "2023-24", "1"
        )
    assert "base_only=[('10', '20')]" in str(exc.value)
    assert "advanced_only=[('10', '30')]" in str(exc.value)


def test_immutable_anchor_verification_rejects_copied_or_altered_evidence(tmp_path, monkeypatch):
    assert audit._verify_phase1f_anchor(CACHE) == audit.PHASE1_ANCHORS["phase1f_analysis"]
    monkeypatch.setattr(audit, "_phase1f_replay_hash", lambda cache_root: "0" * 64)
    with pytest.raises(ValueError, match="Phase 1F analysis anchor mismatch"):
        audit._verify_phase1f_anchor(CACHE)

    phase2e_path = CACHE / "phase2e" / "final-combined-audit.json"
    assert audit._verify_phase2e_summary(phase2e_path) == audit.PHASE2E_HASH
    altered = json.loads(phase2e_path.read_text(encoding="utf-8-sig"))
    altered["primary_classification"] = "altered while copied digest remains unchanged"
    altered_path = tmp_path / "altered-phase2e-summary.json"
    altered_path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="Phase 2E final analysis anchor mismatch"):
        audit._verify_phase2e_summary(altered_path)

    copied_only_path = tmp_path / "copied-only-phase2e-summary.json"
    copied_only_path.write_text(
        json.dumps({"deterministic_analysis_sha256": audit.PHASE2E_HASH}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Phase 2E final analysis anchor mismatch"):
        audit._verify_phase2e_summary(copied_only_path)


def test_row_grain_canonical_keys_and_zero_preservation(summary):
    ledger = summary["row_evidence_ledger"]
    keys = [(r["season"], r["team_id"], *r["pair"]) for r in ledger]
    assert len(keys) == len(set(keys)) == 46938
    assert all(int(r["pair"][0]) < int(r["pair"][1]) for r in ledger)
    assert sum(r["possessions"] == 0 for r in ledger) == 152
    with pytest.raises(ValueError):
        audit.canonical_pair("12", "12")
    with pytest.raises(ValueError):
        audit.canonical_pair("01", "2")


def test_target_identity_and_exposure_thresholds(summary):
    assert summary["target"]["numeric_missing"] == 0
    assert summary["target"]["standard_identity_failures"] == 0
    assert summary["exposure_thresholds"]["100"]["retained_rows"] == 30580
    assert summary["exposure_thresholds"]["100"]["retained_summed_possession_share"] > .97
    assert summary["exposure_thresholds"]["1000"]["retained_rows"] < summary["exposure_thresholds"]["100"]["retained_rows"]


def test_weighting_and_effective_sample_size(summary):
    weights = summary["weighting"]
    assert weights["equal"]["effective_sample_size"] == weights["equal"]["eligible_rows"]
    assert weights["linear_possessions"]["effective_sample_size"] < weights["sqrt_possessions"]["effective_sample_size"]
    assert weights["linear_possessions"]["top_10pct_weight_share"] > weights["equal"]["top_10pct_weight_share"]


def test_missing_history_lookback_and_no_future_history(summary):
    history = summary["missing_history"]
    strict = history["strict_previous_season"]
    assert strict["statuses"] == {"both_missing": 1928, "complete": 30773, "one_missing": 14237}
    assert history["lookbacks"]["5"]["remaining_missing_rows"] < history["lookbacks"]["2"]["remaining_missing_rows"]
    assert set(history["lookbacks"]["1"]["history_gap_distribution"]) == {1}


def test_safe_derivations_and_symmetric_transformations():
    profile = {"FGM": 4, "FGA": 10, "FG3M": 1, "FG3A": 4, "FTA": 2}
    assert audit.derived_shooting_features(profile)["two_point_accuracy"] == .5
    assert audit.derived_shooting_features({"FGM": 0, "FGA": 0, "FG3M": 0, "FG3A": 0})["three_point_accuracy"] is None
    assert audit.symmetric_pair_transform({"AST": 4}, {"AST": 10}, "AST") == {"sum": 14.0, "mean": 7.0, "minimum": 4.0, "maximum": 10.0, "absolute_difference": 6.0}
    assert audit.symmetric_pair_transform({"AST": None}, {"AST": 10}, "AST")["sum"] is None


def test_cross_season_and_endpoint_flags(summary):
    stability = summary["adjacent_season_stability"]
    assert stability["all_repeated_pairs"]["poss_ge_100_each"]["matched_adjacent_observations"] > 0
    flags = [x for x in summary["endpoint_flags"] if x["exact_250"]]
    assert {(x["season"], x["team_id"], x["team_name"]) for x in flags} == {
        ("2020-21", "1610612745", "Houston Rockets"),
        ("2023-24", "1610612761", "Toronto Raptors"),
        ("2023-24", "1610612763", "Memphis Grizzlies"),
        ("2023-24", "1610612765", "Detroit Pistons"),
    }

    report = (Path(__file__).parents[1] / "PHASE3A_POPULATION_POLICY_AUDIT.md").read_text(encoding="utf-8")
    assert f"Across {summary['feature_inventory']['profile_rows']:,} acquired profile rows" in report
    for flag in flags:
        short_name = flag["team_name"].removesuffix(" Rockets").removesuffix(" Raptors").removesuffix(" Grizzlies").removesuffix(" Pistons")
        assert f"{short_name} (`{flag['team_id']}`)" in report


def test_determinism_and_network_prohibition(summary, monkeypatch):
    assert summary["deterministic_analysis_sha256"] == EXPECTED_PHASE3A_HASH
    assert audit.analyze(CACHE)["deterministic_analysis_sha256"] == summary["deterministic_analysis_sha256"]
    with audit.network_prohibited():
        with pytest.raises(RuntimeError):
            socket.socket().connect(("example.com", 443))
        with pytest.raises(RuntimeError):
            socket.socket().connect_ex(("example.com", 443))
        with pytest.raises(RuntimeError):
            socket.create_connection(("example.com", 443))
