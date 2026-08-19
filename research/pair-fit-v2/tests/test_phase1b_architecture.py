from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2.phase1b_contract import (
    CONTRACT_VERSION,
    build_season_manifest,
    observation_key,
    possession_target_eligibility,
    raw_asset_id,
    resume_actions,
    schema_drift_report,
    season_key,
    stable_contract_id,
    stable_pair_key,
    team_season_key,
    validate_complete_season_manifest,
    validate_curated_pair_records,
)
from pair_fit_v2.player_feature_registry import (
    DEFAULT_PLAYER_FEATURE_SOURCES,
    feature_season_precedes_target,
    register_feature_source,
    validate_feature_source_registry,
)


APPROVED_SCHEMA_CONTRACT = {
    measure: {
        "Overall": {
            "name": "Overall",
            "column_count": 2,
            "columns": ["TEAM_ID", "MIN"],
        },
        "Lineups": {
            "name": "Lineups",
            "column_count": 3,
            "columns": ["GROUP_ID", "GROUP_NAME", "MIN"],
        },
    }
    for measure in ("Base", "Advanced")
}


def fake_team_ids() -> list[str]:
    return [str(1_000_000_000 + index) for index in range(1, 31)]


def mark_manifest_assets_verified(manifest):
    verified = deepcopy(manifest)
    for asset in verified["raw_assets"]:
        asset["status"] = "verified"
        asset["source_event"].update(
            {
                "acquired_at": "2026-01-01T00:00:00Z",
                "http_status": 200,
                "response_body_bytes": 100,
            }
        )
        asset["cache"].update(
            {
                "relative_path": f"cache/{asset['asset_id']}.json",
                "cache_file_bytes": 120,
                "canonical_json_hash": "abc123",
                "serialization_version": "json-indent2.v1",
            }
        )
        asset["schema_verification"].update(
            {
                "status": "accepted",
                "drift_classification": "identical",
                "fingerprints": list(
                    deepcopy(
                        APPROVED_SCHEMA_CONTRACT[
                            asset["identity"]["parameters"]["measure_type"]
                        ]
                    ).values()
                ),
            }
        )
    return verified


def validate_manifest(manifest, teams=None, **overrides):
    return validate_complete_season_manifest(
        manifest,
        expected_season="2024-25",
        expected_team_ids=teams or fake_team_ids(),
        approved_schema_contract=APPROVED_SCHEMA_CONTRACT,
        **overrides,
    )


def rehash_asset(asset):
    asset["asset_id"] = stable_contract_id("raw-asset", asset["identity"])


def curated_row(**overrides):
    row = {
        "league_id": "00",
        "target_season": "2024-25",
        "season_type": "regular-season",
        "team_id": "1610612744",
        "player_1_id": "201939",
        "player_2_id": "203110",
        "advanced_poss": 10,
        "off_rating": 110.0,
        "def_rating": 105.0,
        "net_rating": 5.0,
        "possession_rate_target_eligible": True,
        "target_eligibility_reasons": [],
        "prior_history_status": "complete",
        "base_row_present": True,
        "advanced_row_present": True,
    }
    row.update(overrides)
    return row


def test_stable_keys_make_league_season_type_team_and_unordered_pair_explicit():
    assert season_key("2024-25") == ("00", "2024-25", "regular-season")
    assert team_season_key("2024-25", "001610612744") == (
        "00",
        "2024-25",
        "regular-season",
        "1610612744",
    )
    assert stable_pair_key("203110", "201939") == ("201939", "203110")
    assert observation_key("2024-25", "1610612744", "203110", "201939") == (
        "00",
        "2024-25",
        "regular-season",
        "1610612744",
        "201939",
        "203110",
    )


def test_pair_key_rejects_same_player():
    with pytest.raises(ValueError, match="distinct"):
        stable_pair_key("201939", "201939")


def test_raw_asset_id_is_parameter_order_independent_and_measure_specific():
    common = {
        "endpoint": "TeamDashLineups",
        "season": "2024-25",
        "team_id": "1610612744",
        "measure_type": "Base",
    }
    first = raw_asset_id(**common, extra_parameters={"z": "last", "a": "first"})
    reordered = raw_asset_id(**common, extra_parameters={"a": "first", "z": "last"})
    advanced = raw_asset_id(**{**common, "measure_type": "Advanced"})

    assert first == reordered
    assert first != advanced


def test_group_quantity_is_part_of_raw_asset_identity():
    common = {
        "endpoint": "TeamDashLineups",
        "season": "2024-25",
        "team_id": "1610612744",
        "measure_type": "Base",
    }

    asset_ids = {raw_asset_id(**common, group_quantity=size) for size in (2, 3, 4, 5)}

    assert len(asset_ids) == 4


def test_schema_drift_identical_schema_is_accepted_even_without_row_counts():
    fingerprint = {"name": "Lineups", "column_count": 3, "columns": ["A", "B", "C"]}

    report = schema_drift_report(fingerprint, dict(fingerprint))

    assert report["classification"] == "identical"
    assert report["accepted"] is True
    assert report["action"] == "accept"


@pytest.mark.parametrize(
    ("actual", "classification"),
    [
        ({"name": "Lineups", "column_count": 3, "columns": ["A", "C", "B"]}, "reordered"),
        ({"name": "Lineups", "column_count": 4, "columns": ["A", "B", "C", "D"]}, "additive"),
        ({"name": "Lineups", "column_count": 2, "columns": ["A", "B"]}, "subtractive"),
        ({"name": "Other", "column_count": 3, "columns": ["A", "B", "C"]}, "result_set_name_changed"),
    ],
)
def test_every_schema_change_is_quarantined_for_review(actual, classification):
    expected = {"name": "Lineups", "column_count": 3, "columns": ["A", "B", "C"]}

    report = schema_drift_report(expected, actual)

    assert report["classification"] == classification
    assert report["accepted"] is False
    assert report["action"] == "quarantine_for_review"


def test_design_manifest_has_sixty_unique_assets_for_thirty_teams():
    manifest = build_season_manifest(season="2024-25", team_ids=fake_team_ids())

    assert manifest["contract_version"] == CONTRACT_VERSION
    assert manifest["expected_team_count"] == 30
    assert len(manifest["raw_assets"]) == 60
    assert len({asset["asset_id"] for asset in manifest["raw_assets"]}) == 60
    assert {asset["status"] for asset in manifest["raw_assets"]} == {"planned"}


def test_manifest_identity_and_asset_order_canonicalize_unordered_inputs():
    canonical = build_season_manifest(
        season="2024-25", team_ids=["1", "2", "10"], measures=["Base", "Advanced"]
    )
    reordered = build_season_manifest(
        season="2024-25", team_ids=["10", "1", "2"], measures=["Advanced", "Base"]
    )

    assert reordered["manifest_id"] == canonical["manifest_id"]
    assert reordered["logical_identity"] == canonical["logical_identity"]
    assert reordered["logical_identity"]["team_ids"] == ["1", "2", "10"]
    assert reordered["logical_identity"]["measures"] == ["Base", "Advanced"]
    assert [asset["identity"] for asset in reordered["raw_assets"]] == [
        asset["identity"] for asset in canonical["raw_assets"]
    ]


def test_complete_season_gate_requires_verified_assets_provenance_and_schemas():
    teams = fake_team_ids()
    planned = build_season_manifest(season="2024-25", team_ids=teams)
    planned_result = validate_manifest(planned, teams)

    verified = mark_manifest_assets_verified(planned)
    verified_result = validate_manifest(verified, teams)

    assert planned_result["valid"] is False
    assert planned_result["checks"]["all_assets_verified"] is False
    assert planned_result["checks"]["all_assets_have_provenance"] is False
    assert verified_result["valid"] is True
    assert verified_result["expected_asset_count"] == 60
    assert verified_result["actual_asset_count"] == 60


def test_complete_season_gate_reports_missing_team_measure_asset():
    teams = fake_team_ids()
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=teams)
    )
    removed = manifest["raw_assets"].pop()

    result = validate_manifest(manifest, teams)

    assert result["valid"] is False
    assert result["actual_asset_count"] == 59
    assert result["missing_team_measure_pairs"] == [
        (
            removed["identity"]["parameters"]["team_id"],
            removed["identity"]["parameters"]["measure_type"],
        )
    ]


@pytest.mark.parametrize(
    ("field", "wrong_value", "expected_path"),
    [
        ("season", "2023-24", "identity.parameters.season"),
        ("league_id", "01", "identity.parameters.league_id"),
        ("season_type", "playoffs", "identity.parameters.season_type"),
        ("endpoint", "WrongEndpoint", "identity.endpoint"),
        ("group_quantity", "5", "identity.parameters.group_quantity"),
        ("team_id", "9999999999", "identity.parameters.team_id"),
        ("measure_type", "WrongMeasure", "identity.parameters.measure_type"),
    ],
)
def test_complete_season_gate_rejects_asset_identity_that_disagrees_with_manifest(
    field, wrong_value, expected_path
):
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=fake_team_ids())
    )
    asset = manifest["raw_assets"][0]
    if field == "endpoint":
        asset["identity"]["endpoint"] = wrong_value
    else:
        asset["identity"]["parameters"][field] = wrong_value
    rehash_asset(asset)

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["asset_id_mismatches"] == []
    assert expected_path in {
        mismatch["field"]
        for item in result["asset_identity_mismatches"]
        for mismatch in item["mismatched_fields"]
    }


def test_complete_season_gate_rejects_self_consistent_wrong_request_contract():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(
            season="2023-24",
            team_ids=fake_team_ids(),
            endpoint="WrongEndpoint",
            group_quantity=5,
        )
    )

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["checks"]["manifest_id_matches_logical_identity"] is True
    assert result["checks"]["asset_ids_unique_and_reproducible"] is True
    assert result["checks"]["manifest_identity_matches_expected_contract"] is False
    assert {
        mismatch["field"] for mismatch in result["manifest_identity_mismatches"]
    } >= {
        "logical_identity.season",
        "logical_identity.endpoint",
        "logical_identity.group_quantity",
    }


def test_complete_season_gate_rejects_tampered_manifest_id():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=fake_team_ids())
    )
    manifest["manifest_id"] = "season-manifest:tampered"

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["checks"]["manifest_id_matches_logical_identity"] is False
    assert result["manifest_id_mismatch"]["stored"] == "season-manifest:tampered"


def test_complete_season_gate_rejects_tampered_asset_id_independently():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=fake_team_ids())
    )
    asset = manifest["raw_assets"][0]
    asset["asset_id"] = "raw-asset:tampered"

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["asset_identity_mismatches"] == []
    assert result["asset_id_mismatches"] == [
        {
            "index": 0,
            "stored_asset_id": "raw-asset:tampered",
            "recomputed_from_embedded_identity": stable_contract_id(
                "raw-asset", asset["identity"]
            ),
        }
    ]


def test_complete_season_gate_rejects_incomplete_manifest_identity():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=fake_team_ids())
    )
    manifest["logical_identity"].pop("extra_parameters")
    manifest["manifest_id"] = stable_contract_id(
        "season-manifest", manifest["logical_identity"]
    )

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["checks"]["manifest_identity_complete_and_normalized"] is False
    assert "missing_logical_identity_fields:extra_parameters" in result[
        "manifest_identity_errors"
    ]


def test_complete_season_gate_governs_extra_request_parameters():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(
            season="2024-25",
            team_ids=fake_team_ids(),
            extra_parameters={"pace_adjust": "N"},
        )
    )
    assert validate_manifest(
        manifest, expected_extra_parameters={"pace_adjust": "N"}
    )["valid"] is True
    asset = manifest["raw_assets"][0]
    asset["identity"]["parameters"]["pace_adjust"] = "Y"
    rehash_asset(asset)

    result = validate_manifest(
        manifest, expected_extra_parameters={"pace_adjust": "N"}
    )

    assert result["valid"] is False
    assert result["asset_id_mismatches"] == []
    assert result["asset_identity_mismatches"][0]["mismatched_fields"] == [
        {
            "field": "identity.parameters.pace_adjust",
            "expected": "N",
            "actual": "Y",
            "problem": "value_mismatch",
        }
    ]


def test_complete_season_gate_rejects_missing_schema_fingerprints():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=fake_team_ids())
    )
    asset = manifest["raw_assets"][0]
    asset["schema_verification"]["fingerprints"] = []

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["missing_schema_fingerprint_asset_ids"] == [asset["asset_id"]]


def test_complete_season_gate_rejects_missing_required_result_set():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=fake_team_ids())
    )
    asset = manifest["raw_assets"][0]
    asset["schema_verification"]["fingerprints"].pop()

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["missing_required_result_sets"] == [
        {"asset_id": asset["asset_id"], "result_sets": ["Lineups"]}
    ]


def test_complete_season_gate_rejects_duplicate_result_set_fingerprints():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=fake_team_ids())
    )
    asset = manifest["raw_assets"][0]
    asset["schema_verification"]["fingerprints"].append(
        deepcopy(asset["schema_verification"]["fingerprints"][1])
    )

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["duplicate_result_set_fingerprints"] == [
        {"asset_id": asset["asset_id"], "result_sets": ["Lineups"]}
    ]


def test_complete_season_gate_rejects_malformed_fingerprint():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=fake_team_ids())
    )
    asset = manifest["raw_assets"][0]
    asset["schema_verification"]["fingerprints"][1]["column_count"] = 99

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["malformed_schema_fingerprints"][0]["asset_id"] == asset["asset_id"]
    assert "column_count_mismatch" in result["malformed_schema_fingerprints"][0]["errors"]


def test_complete_season_gate_rejects_unaccepted_schema_classification():
    manifest = mark_manifest_assets_verified(
        build_season_manifest(season="2024-25", team_ids=fake_team_ids())
    )
    asset = manifest["raw_assets"][0]
    fingerprint = asset["schema_verification"]["fingerprints"][1]
    fingerprint["columns"].append("EXTRA")
    fingerprint["column_count"] += 1

    result = validate_manifest(manifest)

    assert result["valid"] is False
    assert result["unaccepted_schema_fingerprints"] == [
        {
            "asset_id": asset["asset_id"],
            "measure_type": "Base",
            "result_set": "Lineups",
            "classification": "additive",
        }
    ]


def test_resume_actions_skip_only_fully_verified_assets():
    manifest = build_season_manifest(season="2024-25", team_ids=["1"])
    first, second = manifest["raw_assets"]
    first["status"] = "verified"
    first["cache"].update(
        {"canonical_json_hash": "abc", "serialization_version": "json-v1"}
    )
    first["schema_verification"]["status"] = "accepted"
    second["status"] = "quarantined"

    actions = resume_actions(manifest)

    assert [item["action"] for item in actions] == [
        "skip_verified",
        "manual_schema_review",
    ]


def test_zero_possessions_with_numeric_ratings_are_retained_but_ineligible():
    eligibility = possession_target_eligibility(
        poss=0, off_rating=0.0, def_rating=0.0, net_rating=0.0
    )

    assert eligibility == {
        "eligible": False,
        "reasons": ["nonpositive_possessions"],
    }


def test_curated_contract_preserves_ineligible_row_and_prior_history_status():
    row = curated_row(
        advanced_poss=0,
        off_rating=0.0,
        def_rating=0.0,
        net_rating=0.0,
        possession_rate_target_eligible=False,
        target_eligibility_reasons=["nonpositive_possessions"],
        prior_history_status="one_missing",
    )

    result = validate_curated_pair_records([row], expected_source_union_count=1)

    assert result["valid"] is True
    assert result["row_count"] == 1


def test_curated_contract_detects_dropped_rows_invalid_status_and_eligibility_mismatch():
    row = curated_row(
        prior_history_status="unknown",
        possession_rate_target_eligible=False,
    )

    result = validate_curated_pair_records([row], expected_source_union_count=2)

    assert result["valid"] is False
    assert result["checks"]["all_source_union_rows_preserved"] is False
    assert result["checks"]["all_prior_history_statuses_valid"] is False
    assert result["checks"]["all_target_eligibility_values_reproducible"] is False


def test_curated_contract_requires_canonical_storage_order_and_source_presence():
    row = curated_row(player_1_id="203110", player_2_id="201939")
    row.pop("base_row_present")

    result = validate_curated_pair_records([row], expected_source_union_count=1)

    assert result["valid"] is False
    assert result["invalid_key_row_indexes"] == [0]
    assert result["source_presence_mismatch_row_indexes"] == [0]


def test_default_player_feature_registry_is_valid():
    assert validate_feature_source_registry(DEFAULT_PLAYER_FEATURE_SOURCES) == {
        "valid": True,
        "source_errors": {},
    }


def test_registry_accepts_later_heliocentrism_source_without_mutating_default():
    heliocentrism_source = {
        "source_id": "future_heliocentrism_source",
        "source_version": "design-placeholder-v1",
        "status": "proposed",
        "entity_grain": "player_season",
        "source_kind": "unresolved",
        "source_locator": {"status": "not_selected"},
        "aggregation_contract": "must be defined before activation",
        "join_key_fields": ["feature_season", "player_id"],
        "availability_rule": "strictly_before_target_season",
        "feature_families": ["heliocentrism", "role_style"],
        "field_contract": {
            "identity_fields": ["player_id"],
            "candidate_fields": [],
            "metric_definitions_required_before_activation": True,
        },
        "notes": "No source or formula selected in Phase 1B.",
    }

    updated = register_feature_source(
        DEFAULT_PLAYER_FEATURE_SOURCES, heliocentrism_source
    )

    assert "future_heliocentrism_source" in updated
    assert "future_heliocentrism_source" not in DEFAULT_PLAYER_FEATURE_SOURCES
    assert validate_feature_source_registry(updated)["valid"] is True


def test_feature_source_registry_and_temporal_rule_reject_leakage():
    leaking_source = {
        **next(iter(DEFAULT_PLAYER_FEATURE_SOURCES.values())),
        "source_id": "leaking_source",
        "availability_rule": "target_season_allowed",
    }

    with pytest.raises(ValueError, match="target_season_leakage"):
        register_feature_source(DEFAULT_PLAYER_FEATURE_SOURCES, leaking_source)
    assert feature_season_precedes_target("2023-24", "2024-25") is True
    assert feature_season_precedes_target("2024-25", "2024-25") is False
