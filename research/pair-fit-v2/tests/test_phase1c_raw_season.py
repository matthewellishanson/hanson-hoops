from __future__ import annotations

import importlib
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2.phase1b_contract import validate_complete_season_manifest
from pair_fit_v2.phase1c_acquisition import (
    AcquisitionTransportError,
    TransportResult,
    _request_parameters,
    run_manifest_acquisition,
)
from pair_fit_v2.phase1c_manifest import (
    ENDPOINT,
    GROUP_QUANTITY,
    LEAGUE_ID,
    PILOT_TEAM_IDS,
    REQUIRED_PAIR_MEASURES,
    SEASON_TYPE,
    TARGET_SEASON,
    TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
    ManifestStore,
    atomic_write_json,
    build_operational_manifest,
    canonical_json_hash,
    extend_live_request_authorization,
    reconcile_pilot_assets,
)
from pair_fit_v2.phase1c_validation import (
    audit_exact_row_boundaries,
    validate_raw_season,
)


BASE_SCHEMA = {
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
ADVANCED_SCHEMA = {
    "Overall": {
        "name": "Overall",
        "column_count": 2,
        "columns": ["TEAM_ID", "MIN"],
    },
    "Lineups": {
        "name": "Lineups",
        "column_count": 7,
        "columns": [
            "GROUP_ID",
            "GROUP_NAME",
            "MIN",
            "POSS",
            "OFF_RATING",
            "DEF_RATING",
            "NET_RATING",
        ],
    },
}
APPROVED_SCHEMAS = {"Base": BASE_SCHEMA, "Advanced": ADVANCED_SCHEMA}


def full_teams():
    teams = [
        {
            "team_id": team_id,
            "team_name": f"Pilot {team_id}",
            "team_slug": f"pilot-{team_id}",
        }
        for team_id in sorted(PILOT_TEAM_IDS, key=int)
    ]
    teams.extend(
        {
            "team_id": str(2000000000 + index),
            "team_name": f"Team {index}",
            "team_slug": f"team-{index}",
        }
        for index in range(1, 27)
    )
    return teams


def payload_for(team_id, measure, *, poss=20, extra_lineups_column=None):
    if measure == "Base":
        lineups_headers = list(BASE_SCHEMA["Lineups"]["columns"])
        lineup_row = ["-101-202-", "A - B", 10.5]
    else:
        lineups_headers = list(ADVANCED_SCHEMA["Lineups"]["columns"])
        lineup_row = ["-101-202-", "A - B", 10.0, poss, 110.0, 105.0, 5.0]
    if extra_lineups_column:
        lineups_headers.append(extra_lineups_column)
        lineup_row.append("unexpected")
    return {
        "resultSets": [
            {
                "name": "Overall",
                "headers": ["TEAM_ID", "MIN"],
                "rowSet": [[int(team_id), 10.5]],
            },
            {
                "name": "Lineups",
                "headers": lineups_headers,
                "rowSet": [lineup_row],
            },
        ]
    }


def response_for_identity(identity, **payload_options):
    parameters = identity["parameters"]
    body = json.dumps(
        payload_for(
            parameters["team_id"], parameters["measure_type"], **payload_options
        )
    ).encode("utf-8")
    return TransportResult(status_code=200, body=body, elapsed_seconds=0.25)


def make_store(tmp_path, teams=None):
    teams = teams or full_teams()
    expected = build_operational_manifest(teams, APPROVED_SCHEMAS)
    store = ManifestStore(
        tmp_path,
        expected,
        clock=lambda: "2026-08-18T00:00:00Z",
    )
    return store


def write_pilot_fixtures(cache_root):
    live = cache_root / "live_responses"
    live.mkdir(parents=True, exist_ok=True)
    for team_id in sorted(PILOT_TEAM_IDS, key=int):
        for measure in REQUIRED_PAIR_MEASURES:
            stem = f"team_dash_lineups_{team_id}_{TARGET_SEASON}_{measure.lower()}"
            payload = payload_for(team_id, measure)
            payload_path = live / f"{stem}.json"
            payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            metadata = {
                "endpoint": ENDPOINT,
                "team_id": team_id,
                "season": TARGET_SEASON,
                "season_type": SEASON_TYPE,
                "group_quantity": GROUP_QUANTITY,
                "measure_type": measure,
                "content_hash": canonical_json_hash(payload)[:16],
                "payload_size_bytes": payload_path.stat().st_size,
                "fetch_time_seconds": 1.0,
            }
            (live / f"{stem}_metadata.json").write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )


def complete_gate(manifest):
    return validate_complete_season_manifest(
        manifest,
        expected_season=TARGET_SEASON,
        expected_team_ids=manifest["logical_identity"]["team_ids"],
        required_measures=REQUIRED_PAIR_MEASURES,
        expected_endpoint=ENDPOINT,
        expected_season_type=SEASON_TYPE,
        expected_league_id=LEAGUE_ID,
        expected_group_quantity=GROUP_QUANTITY,
        expected_extra_parameters=TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
        approved_schema_contract=APPROVED_SCHEMAS,
    )


def test_deterministic_manifest_persistence_and_reload(tmp_path):
    store = make_store(tmp_path)
    manifest = store.create_or_load()
    reloaded = store.load()
    independently_built = build_operational_manifest(full_teams(), APPROVED_SCHEMAS)

    assert manifest == reloaded
    assert manifest["manifest_id"] == independently_built["manifest_id"]
    assert [asset["asset_id"] for asset in manifest["raw_assets"]] == [
        asset["asset_id"] for asset in independently_built["raw_assets"]
    ]


def test_atomic_manifest_write_uses_replace_and_leaves_no_temporary_file(
    tmp_path, monkeypatch
):
    destination = tmp_path / "manifest.json"
    calls = []
    real_replace = os.replace

    def recording_replace(source, target):
        calls.append((Path(source), Path(target)))
        return real_replace(source, target)

    monkeypatch.setattr(os, "replace", recording_replace)
    atomic_write_json(destination, {"value": 1})

    assert json.loads(destination.read_text(encoding="utf-8")) == {"value": 1}
    assert calls and calls[0][1] == destination
    assert not list(tmp_path.glob("*.tmp"))


def test_import_and_default_runner_cannot_access_network(tmp_path, monkeypatch):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    store.create_or_load()
    called = False

    def forbidden_transport(*_):
        nonlocal called
        called = True
        raise AssertionError("network transport must not run")

    result = run_manifest_acquisition(store, transport=forbidden_transport)
    assert result["dry_run"] is True
    assert called is False
    module = importlib.import_module("pair_fit_v2.phase1c_cli")
    assert hasattr(module, "main")


def test_live_request_parameters_exactly_match_authorized_contract(tmp_path):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    identity = store.expected_manifest["raw_assets"][0]["identity"]

    parameters = _request_parameters(identity)

    assert parameters["LeagueID"] == "00"
    assert parameters["Season"] == "2024-25"
    assert parameters["SeasonType"] == "Regular Season"
    assert parameters["TeamID"] == "1"
    assert parameters["GroupQuantity"] == "2"
    assert parameters["MeasureType"] == "Base"
    assert "season_type" not in parameters
    assert set(parameters) == {
        *TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
        "LeagueID",
        "Season",
        "SeasonType",
        "TeamID",
        "GroupQuantity",
        "MeasureType",
    }


def test_reconciliation_finds_exactly_eight_existing_and_fifty_two_missing(tmp_path):
    write_pilot_fixtures(tmp_path)
    store = make_store(tmp_path)
    manifest = store.create_or_load()

    result = reconcile_pilot_assets(manifest, store)
    gate = complete_gate(manifest)

    assert result == {
        "verified_existing": 8,
        "planned_missing": 52,
        "unique_asset_ids": 60,
    }
    assert gate["valid"] is False
    assert len(gate["unverified_asset_ids"]) == 52
    assert all(
        asset["source_event"].get("unknown_fields")
        for asset in manifest["raw_assets"]
        if asset["status"] == "verified"
    )


def test_dry_run_skips_verified_and_reports_first_missing_without_transport(
    tmp_path,
):
    write_pilot_fixtures(tmp_path)
    store = make_store(tmp_path)
    manifest = store.create_or_load()
    reconcile_pilot_assets(manifest, store)

    result = run_manifest_acquisition(
        store,
        dry_run=True,
        transport=lambda *_: pytest.fail("dry-run must not use transport"),
    )

    assert result["attempted"] == 0
    assert result["skipped"] == 8
    assert sum(action["action"] == "acquire" for action in result["actions"]) == 52
    first_missing = next(
        action for action in result["actions"] if action["action"] == "acquire"
    )
    expected_first = next(
        asset
        for asset in manifest["raw_assets"]
        if asset["status"] == "planned"
    )
    assert first_missing["asset_id"] == expected_first["asset_id"]


def test_verified_assets_are_replayed_and_skipped(tmp_path):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    store.create_or_load()
    first = run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=lambda identity, _: response_for_identity(identity),
        sleep_fn=lambda _: None,
    )
    assert first["successful"] == 2

    second = run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=lambda *_: pytest.fail("verified asset must be skipped"),
        sleep_fn=lambda _: None,
    )
    assert second["attempted"] == 0
    assert second["skipped"] == 2


def test_failure_persists_and_stops_immediately_without_retry(tmp_path):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    store.create_or_load()
    calls = 0

    def failing_transport(*_):
        nonlocal calls
        calls += 1
        raise AcquisitionTransportError("timeout", "timed out")

    result = run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=failing_transport,
        sleep_fn=lambda _: None,
    )
    persisted = store.load()

    assert calls == 1
    assert result["stopped_early"] is True
    assert persisted["raw_assets"][0]["status"] == "failed"
    assert persisted["raw_assets"][1]["status"] == "planned"
    assert persisted["raw_assets"][0]["attempt_count"] == 1

    no_retry = run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=lambda *_: pytest.fail("failed asset must not auto-retry"),
        sleep_fn=lambda _: None,
    )
    assert no_retry["stop_category"] == "failed_asset_retry_not_authorized"


def test_explicit_retry_authorization_resumes_failed_asset(tmp_path):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    store.create_or_load()
    run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=lambda *_: (_ for _ in ()).throw(
            AcquisitionTransportError("connection_or_dns_failure", "offline")
        ),
        sleep_fn=lambda _: None,
    )

    resumed = run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        retry_failed=True,
        transport=lambda identity, _: response_for_identity(identity),
        sleep_fn=lambda _: None,
    )

    manifest = store.load()
    assert resumed["stopped_early"] is False
    assert [asset["status"] for asset in manifest["raw_assets"]] == [
        "verified",
        "verified",
    ]
    assert manifest["raw_assets"][0]["attempt_count"] == 2


def test_schema_quarantine_preserves_cache_and_stops_queue(tmp_path):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    manifest = store.create_or_load()

    result = run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=lambda identity, _: response_for_identity(
            identity, extra_lineups_column="UNEXPECTED"
        ),
        sleep_fn=lambda _: None,
    )
    persisted = store.load()
    first = persisted["raw_assets"][0]

    assert result["stop_category"] == "schema_quarantine"
    assert first["status"] == "quarantined"
    assert (tmp_path / first["cache"]["relative_path"]).is_file()
    assert persisted["raw_assets"][1]["status"] == "planned"
    assert complete_gate(persisted)["valid"] is False


def test_cache_replay_failure_prevents_advancement(tmp_path, monkeypatch):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    store.create_or_load()
    monkeypatch.setattr(
        "pair_fit_v2.phase1c_acquisition.verify_asset_cache",
        lambda *_: (_ for _ in ()).throw(ValueError("replay mismatch")),
    )

    result = run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=lambda identity, _: response_for_identity(identity),
        sleep_fn=lambda _: None,
    )
    manifest = store.load()

    assert result["stop_category"] == "cache_replay_failure"
    assert manifest["raw_assets"][0]["status"] == "failed"
    assert manifest["raw_assets"][1]["status"] == "planned"


def test_manifest_is_persisted_at_each_live_asset_stage(tmp_path, monkeypatch):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    store.create_or_load()
    save_count = 0
    real_save = store.save

    def counting_save(manifest):
        nonlocal save_count
        save_count += 1
        real_save(manifest)

    monkeypatch.setattr(store, "save", counting_save)
    run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=lambda identity, _: response_for_identity(identity),
        sleep_fn=lambda _: None,
    )

    # attempt-start save plus acquired and verified transitions for each of 2 assets
    assert save_count >= 6


def test_complete_sixty_asset_mocked_success_and_cache_only_replay(tmp_path):
    write_pilot_fixtures(tmp_path)
    store = make_store(tmp_path)
    manifest = store.create_or_load()
    reconcile_pilot_assets(manifest, store)

    acquisition = run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=lambda identity, _: response_for_identity(identity),
        sleep_fn=lambda _: None,
    )
    first_replay = validate_raw_season(store)
    second_replay = validate_raw_season(store)

    assert acquisition["attempted"] == 52
    assert acquisition["successful"] == 52
    assert acquisition["skipped"] == 8
    assert acquisition["verified"] == 60
    assert first_replay["manifest_gate"]["valid"] is True
    assert first_replay["clean_release"] is True
    assert first_replay["totals"] == {
        "base_raw_pair_rows": 30,
        "advanced_raw_pair_rows": 30,
        "full_outer_union_count": 30,
        "matched_pairs": 30,
        "base_only_pairs": 0,
        "advanced_only_pairs": 0,
    }
    assert first_replay == second_replay


def test_incomplete_and_quarantined_manifests_fail_release(tmp_path):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    incomplete = store.create_or_load()
    assert complete_gate(incomplete)["valid"] is False
    quarantined = deepcopy(incomplete)
    quarantined["raw_assets"][0]["status"] = "quarantined"
    assert complete_gate(quarantined)["valid"] is False


def test_manifest_load_retains_hardened_identity_checks(tmp_path):
    store = make_store(tmp_path)
    store.create_or_load()
    tampered = json.loads(store.path.read_text(encoding="utf-8"))
    tampered["raw_assets"][0]["identity"]["parameters"]["season"] = "2023-24"
    store.path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match="Asset identity mismatch"):
        store.load()


def test_single_asset_guard_and_audited_one_request_extension(tmp_path):
    store = make_store(
        tmp_path,
        teams=[{"team_id": "1", "team_name": "One", "team_slug": "one"}],
    )
    manifest = store.create_or_load()
    base_asset_id = manifest["raw_assets"][0]["asset_id"]
    advanced_asset_id = manifest["raw_assets"][1]["asset_id"]
    calls = 0

    def transport(identity, _):
        nonlocal calls
        calls += 1
        return response_for_identity(identity)

    result = run_manifest_acquisition(
        store,
        dry_run=False,
        live_acquisition=True,
        transport=transport,
        sleep_fn=lambda _: None,
        authorized_asset_id=base_asset_id,
        max_live_attempts_this_run=1,
    )

    assert calls == 1
    assert result["attempted"] == 1
    assert result["stop_category"] == "asset_not_authorized_for_run"
    assert store.load()["raw_assets"][1]["status"] == "planned"

    extended = extend_live_request_authorization(
        store,
        asset_id=advanced_asset_id,
        authorization_note="constructed one-request continuation",
    )
    assert extended["authorization"]["maximum_new_live_requests"] == 53
    assert extended["authorization"]["extensions"] == [
        {
            "asset_id": advanced_asset_id,
            "additional_live_attempts": 1,
            "authorized_at": "2026-08-18T00:00:00Z",
            "note": "constructed one-request continuation",
        }
    ]
    with pytest.raises(ValueError, match="already recorded"):
        extend_live_request_authorization(
            store,
            asset_id=advanced_asset_id,
            authorization_note="must not duplicate",
        )


def test_exact_250_rows_are_review_signal_not_truncation_classification():
    player_ids = [str(index) for index in range(1, 25)]
    pairs = [
        (left, right)
        for index, left in enumerate(player_ids)
        for right in player_ids[index + 1 :]
    ][:250]
    rows = [
        {
            "pair_key": pair,
            "GROUP_NAME": f"{pair[0]} - {pair[1]}",
            "MIN": float(index + 1),
            "MIN_RANK": index + 1,
        }
        for index, pair in enumerate(pairs)
    ]
    payload = {
        "resource": "teamdashlineups",
        "resultSets": [
            {"name": "Overall", "headers": [], "rowSet": []},
            {"name": "Lineups", "headers": [], "rowSet": []},
        ],
    }
    result = audit_exact_row_boundaries(
        {"1": {"Base": rows}, "2": {"Base": rows[:249]}},
        {"1": {"Base": payload}, "2": {"Base": payload}},
        {"1": {"team_name": "Boundary"}, "2": {"team_name": "Nearby"}},
    )
    finding = result["findings"][0]

    assert result["exact_boundary_asset_count"] == 1
    assert finding["distinct_player_ids"] == 24
    assert finding["theoretical_unordered_pairs"] == 276
    assert finding["returned_canonical_pair_count"] == 250
    assert finding["absent_theoretical_pairs"] == 26
    assert finding["rank_fields"]["fields_reaching_boundary"] == ["MIN_RANK"]
    assert finding["review_signal"] is True
    assert finding["automatically_classified_as_truncated"] is False
    assert finding["response_envelope"][
        "pagination_limit_or_truncation_markers"
    ] == []
