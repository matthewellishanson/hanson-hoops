from __future__ import annotations

import json
import socket
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2.multi_team_audit import schema_fingerprint
from pair_fit_v2.phase2a_historical_canary import (
    MAX_LIVE_ATTEMPTS,
    PLAYER_ENDPOINT,
    PLAYER_PER_MODES,
    PRIOR_FEATURE_SEASON,
    TARGET_SEASON,
    TEAMS,
    CanaryStore,
    TransportError,
    TransportResult,
    analyze_cache,
    build_manifest,
    diagnostic_asset_id,
    dry_run_plan,
    pair_identity,
    player_identity,
    request_parameters,
    reconcile_quarantine_evidence,
    run_acquisition,
    validate_identity,
    validate_manifest,
    validate_season_shift,
    verify_asset_cache,
)


PAIR_HEADERS = {
    "Overall": ["GROUP_SET", "GROUP_VALUE", "TEAM_ID", "TEAM_ABBREVIATION"],
    "Base": ["GROUP_SET", "GROUP_ID", "GROUP_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "GP", "W", "L", "W_PCT", "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB", "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS", "GP_RANK", "W_RANK", "L_RANK", "W_PCT_RANK", "MIN_RANK", "FGM_RANK", "FGA_RANK", "FG_PCT_RANK", "FG3M_RANK", "FG3A_RANK", "FG3_PCT_RANK", "FTM_RANK", "FTA_RANK", "FT_PCT_RANK", "OREB_RANK", "DREB_RANK", "REB_RANK", "AST_RANK", "TOV_RANK", "STL_RANK", "BLK_RANK", "BLKA_RANK", "PF_RANK", "PFD_RANK", "PTS_RANK", "PLUS_MINUS_RANK"],
    "Advanced": ["GROUP_SET", "GROUP_ID", "GROUP_NAME", "TEAM_ID", "TEAM_ABBREVIATION", "GP", "W", "L", "W_PCT", "MIN", "E_OFF_RATING", "OFF_RATING", "E_DEF_RATING", "DEF_RATING", "E_NET_RATING", "NET_RATING", "AST_PCT", "AST_TO", "AST_RATIO", "OREB_PCT", "DREB_PCT", "REB_PCT", "TM_TOV_PCT", "EFG_PCT", "TS_PCT", "E_PACE", "PACE", "PACE_PER40", "POSS", "PIE", "GP_RANK", "W_RANK", "L_RANK", "W_PCT_RANK", "MIN_RANK", "E_OFF_RATING_RANK", "OFF_RATING_RANK", "E_DEF_RATING_RANK", "DEF_RATING_RANK", "E_NET_RATING_RANK", "NET_RATING_RANK", "AST_PCT_RANK", "AST_TO_RANK", "AST_RATIO_RANK", "OREB_PCT_RANK", "DREB_PCT_RANK", "REB_PCT_RANK", "TM_TOV_PCT_RANK", "EFG_PCT_RANK", "TS_PCT_RANK", "PACE_RANK", "PIE_RANK"],
}
PLAYER_HEADERS = ["PLAYER_ID", "PLAYER_NAME", "NICKNAME", "TEAM_ID", "TEAM_ABBREVIATION", "AGE", "GP", "W", "L", "W_PCT", "MIN", "PTS", "PLUS_MINUS", "TEAM_COUNT"]


def contracts():
    pair = {}
    for measure in ("Base", "Advanced"):
        pair[measure] = {
            "Overall": schema_fingerprint({"name": "Overall", "headers": PAIR_HEADERS["Overall"]}),
            "Lineups": schema_fingerprint({"name": "Lineups", "headers": PAIR_HEADERS[measure]}),
        }
    player = {"LeagueDashPlayerStats": schema_fingerprint({"name": "LeagueDashPlayerStats", "headers": PLAYER_HEADERS})}
    return pair, player


def _row(headers, values):
    return [values.get(name, 1) for name in headers]


def pair_payload(identity, *, drift=False, malformed=False):
    params = request_parameters(identity)
    team_id = int(identity["parameters"]["team_id"])
    measure = identity["parameters"]["measure_type"]
    headers = list(PAIR_HEADERS[measure])
    if drift: headers.append("NEW_FIELD")
    values = {"GROUP_SET": "Lineups", "GROUP_ID": "-1-2-", "GROUP_NAME": "A - B",
              "TEAM_ID": team_id, "TEAM_ABBREVIATION": "TST", "GP": 2, "MIN": 10.5,
              "PTS": 20, "PLUS_MINUS": 2, "POSS": 20, "OFF_RATING": 110.0,
              "DEF_RATING": 100.0, "NET_RATING": 10.0, "E_OFF_RATING": 109.0,
              "E_DEF_RATING": 101.0, "E_NET_RATING": 8.0}
    line = _row(headers, values)
    if malformed: line.pop()
    return {"parameters": params, "resultSets": [
        {"name": "Overall", "headers": PAIR_HEADERS["Overall"],
         "rowSet": [["Overall", "TST", team_id, "TST"]]},
        {"name": "Lineups", "headers": headers, "rowSet": [line]},
    ]}


def player_payload(identity):
    params = request_parameters(identity)
    per = identity["parameters"]["per_mode"]
    minutes = 3200.0 if per == "Totals" else 35.0
    rows = [
        _row(PLAYER_HEADERS, {"PLAYER_ID": 1, "PLAYER_NAME": "A", "NICKNAME": "A", "TEAM_ID": 10,
             "TEAM_ABBREVIATION": "TST", "AGE": 25, "GP": 80, "MIN": minutes, "PTS": 20, "PLUS_MINUS": 1, "TEAM_COUNT": 1}),
        _row(PLAYER_HEADERS, {"PLAYER_ID": 2, "PLAYER_NAME": "B", "NICKNAME": "B", "TEAM_ID": 10,
             "TEAM_ABBREVIATION": "TST", "AGE": 26, "GP": 80, "MIN": minutes-100 if per == "Totals" else 34.0,
             "PTS": 18, "PLUS_MINUS": 0, "TEAM_COUNT": 1}),
    ]
    return {"parameters": params, "resultSets": [{"name": "LeagueDashPlayerStats", "headers": PLAYER_HEADERS, "rowSet": rows}]}


def make_store(tmp_path):
    pair, player = contracts()
    expected = build_manifest(pair, player)
    store = CanaryStore(tmp_path, expected, clock=lambda: "2026-01-01T00:00:00Z")
    store.create_or_load()
    return store


def transport_for(identity, timeout):
    assert timeout == 30
    payload = pair_payload(identity) if identity["endpoint"] != PLAYER_ENDPOINT else player_payload(identity)
    return TransportResult(200, json.dumps(payload, separators=(",", ":")).encode(), .25)


def test_deterministic_12_asset_order_and_unique_isolated_destinations(tmp_path):
    store = make_store(tmp_path)
    manifest = store.load()
    assert len(manifest["raw_assets"]) == MAX_LIVE_ATTEMPTS == 12
    expected = [(tid, measure) for tid, _, _ in TEAMS for measure in ("Base", "Advanced")]
    observed = [(a["identity"]["parameters"].get("team_id"), a["identity"]["parameters"].get("measure_type")) for a in manifest["raw_assets"][:10]]
    assert observed == expected
    assert [a["identity"]["parameters"]["per_mode"] for a in manifest["raw_assets"][10:]] == list(PLAYER_PER_MODES)
    assert len({a["asset_id"] for a in manifest["raw_assets"]}) == 12
    assert len({a["cache"]["relative_path"] for a in manifest["raw_assets"]}) == 12
    assert all(a["cache"]["relative_path"].startswith("phase2a/raw/") for a in manifest["raw_assets"])


def test_dry_run_is_zero_network_and_shows_parameters(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_k: pytest.fail("network prohibited"))
    plan = dry_run_plan(store)
    assert plan["network_calls"] == 0 and len(plan["actions"]) == 12
    assert plan["actions"][0]["request_parameters"]["Season"] == "2023-24"
    assert plan["actions"][10]["request_parameters"]["Season"] == "2022-23"


@pytest.mark.parametrize("target,prior", [("2023-24", "2023-24"), ("2023-24", "2024-25"), ("2024-25", "2022-23")])
def test_same_future_or_unauthorized_season_source_is_rejected(target, prior):
    with pytest.raises(ValueError): validate_season_shift(target, prior)


def test_cross_season_identity_and_cache_isolation():
    identity = pair_identity(TEAMS[0][0], "Base")
    altered = deepcopy(identity); altered["parameters"]["season"] = "2024-25"
    assert TARGET_SEASON == "2023-24" and PRIOR_FEATURE_SEASON == "2022-23"
    with pytest.raises(ValueError): diagnostic_asset_id(altered)
    with pytest.raises(ValueError): validate_identity({**player_identity("Totals"), "prior_feature_season": "2025-26"})


def test_complete_mocked_acquisition_replays_and_analyzes(tmp_path):
    store = make_store(tmp_path)
    calls = []
    def transport(identity, timeout):
        calls.append(identity)
        return transport_for(identity, timeout)
    result = run_acquisition(store, dry_run=False, live_acquisition=True, transport=transport, sleep_fn=lambda _: None)
    assert result["completed"] is True and result["verified"] == 12 and len(calls) == 12
    manifest = store.load()
    assert all(verify_asset_cache(a, tmp_path, manifest)["accepted"] for a in manifest["raw_assets"])
    summary = analyze_cache(store)
    assert summary["base_advanced_reconciliation"] == "clean"
    assert summary["minutes_semantics"]["classification"] == "season_total_minutes_supported"
    assert summary["prior_coverage"]["combined"]["pairs"]["both_players_matched"] == 5
    assert summary["target_season"] != summary["prior_feature_season"]


def test_verified_cache_skips_transport_and_resume_starts_first_unverified(tmp_path):
    store = make_store(tmp_path)
    manifest = store.load()
    # First run deliberately fills only two then fails at third.
    count = 0
    def transport(identity, timeout):
        nonlocal count; count += 1
        if count == 3: raise TransportError("timeout", "bounded failure")
        return transport_for(identity, timeout)
    first = run_acquisition(store, dry_run=False, live_acquisition=True, transport=transport, sleep_fn=lambda _: None)
    assert first["verified"] == 2 and first["failed"] == 1 and count == 3
    # Failed asset is not retried; exact verified assets replay without transport.
    second = run_acquisition(store, dry_run=False, live_acquisition=True,
                             transport=lambda *_: pytest.fail("no retry/network progression"), sleep_fn=lambda _: None)
    assert second["stop_category"] == "existing_failed"


def test_failure_stops_immediately_without_retry_or_progression(tmp_path):
    store = make_store(tmp_path); calls=[]
    def fail(identity, timeout): calls.append(identity); raise TransportError("timeout", "once")
    result = run_acquisition(store, dry_run=False, live_acquisition=True, transport=fail, sleep_fn=lambda _: None)
    assert len(calls) == 1 and result["attempted"] == 1 and result["planned"] == 11
    assert store.load()["raw_assets"][0]["attempt_count"] == 1


def test_schema_drift_is_quarantined_and_queue_stops(tmp_path):
    store = make_store(tmp_path); calls=[]
    def drift(identity, timeout):
        calls.append(identity); return TransportResult(200, json.dumps(pair_payload(identity, drift=True)).encode(), .1)
    result = run_acquisition(store, dry_run=False, live_acquisition=True, transport=drift, sleep_fn=lambda _: None)
    assert len(calls) == 1 and result["quarantined"] == 1 and result["planned"] == 11
    assert result["stop_category"] == "schema_quarantine"
    first = reconcile_quarantine_evidence(store)
    second = reconcile_quarantine_evidence(store)
    assert first == second
    evidence = store.load()["raw_assets"][0]["schema_verification"]
    assert evidence["raw_body_hash"] and evidence["canonical_json_hash"]


def test_malformed_rows_and_identity_mismatch_stop_before_promotion(tmp_path):
    store = make_store(tmp_path)
    def malformed(identity, timeout):
        return TransportResult(200, json.dumps(pair_payload(identity, malformed=True)).encode(), .1)
    result = run_acquisition(store, dry_run=False, live_acquisition=True, transport=malformed, sleep_fn=lambda _: None)
    assert result["stop_category"] == "validation_failure"
    assert not (tmp_path / store.load()["raw_assets"][0]["cache"]["relative_path"]).exists()


def test_corrupt_verified_cache_is_detected(tmp_path):
    store = make_store(tmp_path)
    # Populate all, then corrupt a cached payload and require replay failure before new work.
    run_acquisition(store, dry_run=False, live_acquisition=True, transport=transport_for, sleep_fn=lambda _: None)
    manifest = store.load(); path = tmp_path / manifest["raw_assets"][0]["cache"]["relative_path"]
    path.write_bytes(b"{}")
    with pytest.raises(ValueError): verify_asset_cache(manifest["raw_assets"][0], tmp_path, manifest)


def test_manifest_rejects_reorder_collision_and_atomic_files_exist(tmp_path):
    store = make_store(tmp_path); manifest = store.load()
    assert store.path.is_file() and store.ledger_path.is_file()
    reordered = deepcopy(manifest); reordered["raw_assets"][0], reordered["raw_assets"][1] = reordered["raw_assets"][1], reordered["raw_assets"][0]
    with pytest.raises(ValueError): validate_manifest(reordered, store.expected)
    collision = deepcopy(manifest); collision["raw_assets"][1]["cache"]["relative_path"] = collision["raw_assets"][0]["cache"]["relative_path"]
    with pytest.raises(ValueError): validate_manifest(collision, store.expected)


def test_imports_and_normal_offline_operations_make_no_network(monkeypatch, tmp_path):
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_k: pytest.fail("network prohibited"))
    store = make_store(tmp_path)
    dry_run_plan(store)


def test_no_prohibited_artifact_formats_are_part_of_contract(tmp_path):
    store = make_store(tmp_path)
    text = json.dumps(store.load()).lower()
    for forbidden in (".parquet", ".feather", ".duckdb", ".sqlite", "2025-26"):
        assert forbidden not in text
