from __future__ import annotations

import json
import shutil
import sys
from itertools import count
from copy import deepcopy
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pair_fit_v2.phase2c_raw_season as phase2c
from pair_fit_v2.phase1c_manifest import atomic_write_json, canonical_json_hash, raw_body_hash


REAL_CACHE = Path(__file__).parents[1] / "cache"


@pytest.fixture(scope="module")
def expected():
    return phase2c.build_expected_manifest(REAL_CACHE)


@pytest.fixture
def store(tmp_path, expected):
    ticks = count()
    result = phase2c.Phase2CStore(tmp_path, expected, clock=lambda: f"tick-{next(ticks):04d}")
    phase2c.persist_initial_plan(result)
    return result


def _columns(expected, identity):
    if identity["endpoint"] == phase2c.PLAYER_ENDPOINT:
        return expected["approved_player_schema_contract"]["LeagueDashPlayerStats"]["columns"]
    return expected["approved_pair_schema_contract"][identity["parameters"]["measure_type"]]


def _row(columns, values):
    return [values.get(column, 0) for column in columns]


def _payload(expected, identity, *, bad_schema=False, player_ids=(1, 2)):
    params = identity["parameters"]
    returned = {"Season": params["season"], "SeasonType": phase2c.SEASON_TYPE,
                "MeasureType": params["measure_type"], "LeagueID": phase2c.LEAGUE_ID}
    if identity["endpoint"] == phase2c.PLAYER_ENDPOINT:
        returned["PerMode"] = params["per_mode"]
        columns = list(_columns(expected, identity))
        if bad_schema:
            columns.append("UNAPPROVED")
        rows = [_row(columns, {"PLAYER_ID": player_id, "PLAYER_NAME": f"P{player_id}",
                               "TEAM_ID": 0, "MIN": 2500 if params["per_mode"] == "Totals" else 48})
                for player_id in player_ids]
        return {"parameters": returned, "resultSets": [{"name": "LeagueDashPlayerStats",
                                                           "headers": columns, "rowSet": rows}]}
    returned.update({"TeamID": int(params["team_id"]), "GroupQuantity": 2})
    schemas = _columns(expected, identity)
    sets = []
    for name in ("Overall", "Lineups"):
        columns = list(schemas[name]["columns"])
        if bad_schema and name == "Lineups":
            columns.append("UNAPPROVED")
        values = {"TEAM_ID": int(params["team_id"]), "GROUP_SET": "Lineups",
                  "GROUP_ID": "-1-2-", "GROUP_NAME": "P1 - P2", "GP": 1,
                  "MIN": 10.5, "POSS": 20, "OFF_RATING": 110.0,
                  "DEF_RATING": 100.0, "NET_RATING": 10.0,
                  "E_OFF_RATING": 109.0, "E_DEF_RATING": 101.0,
                  "E_NET_RATING": 8.0, "PLUS_MINUS": 2}
        sets.append({"name": name, "headers": columns, "rowSet": [_row(columns, values)]})
    return {"parameters": returned, "resultSets": sets}


def _response(expected, identity, **kwargs):
    body = json.dumps(_payload(expected, identity, **kwargs), separators=(",", ":")).encode()
    return phase2c.TransportResult(200, body, .1, {})


def _install_verified_assets(store, expected, *, count=62, persist_canary=True):
    manifest = store.load()
    for item in manifest["assets"][:count]:
        payload = _payload(expected, item["identity"])
        body = json.dumps(payload, separators=(",", ":")).encode()
        validation = phase2c.validate_response(payload, item["identity"], manifest)
        cache_path = store.cache_root / item["cache"]["relative_path"]
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(body)
        item["cache"].update({"cache_file_bytes": len(body), "raw_body_hash": raw_body_hash(body),
                              "canonical_json_hash": canonical_json_hash(payload)})
        item["source_event"] = {"provenance_format": "synthetic-test-v1", "acquired_at": "fixed",
                                "http_status": 200, "latency_seconds": 0.0,
                                "response_body_bytes": len(body), "raw_body_hash": raw_body_hash(body)}
        item["schema_verification"] = {"status": "accepted", **validation}
        atomic_write_json(store.cache_root / item["cache"]["metadata_relative_path"],
                          {"asset_id": item["asset_id"], "identity": item["identity"],
                           "source_event": item["source_event"], "cache": item["cache"],
                           "schema_verification": item["schema_verification"]})
        item["status"] = "verified"
    store.save(manifest)
    if count >= 12 and persist_canary:
        manifest = store.load()
        manifest["canary_result"] = phase2c._canary_audit(manifest, store)
        store.save(manifest)


def test_plan_has_exact_order_and_unique_assets(expected):
    assets = expected["assets"]
    assert len(assets) == 62
    assert [item["identity"]["parameters"].get("per_mode") for item in assets[:2]] == list(phase2c.PLAYER_PER_MODES)
    assert [item["identity"]["parameters"].get("team_id") for item in assets[2:12:2]] == list(phase2c.CANARY_TEAM_IDS)
    assert [item["identity"]["parameters"]["measure_type"] for item in assets[2:]] == ["Base", "Advanced"] * 30
    assert len({item["asset_id"] for item in assets}) == len({item["cache"]["relative_path"] for item in assets}) == 62


def test_season_scope_and_leakage_rejection(expected):
    identity = deepcopy(expected["assets"][0]["identity"])
    identity["parameters"]["season"] = phase2c.TARGET_SEASON
    with pytest.raises(ValueError): phase2c.validate_identity(identity, set(expected["team_directory"]))
    identity = deepcopy(expected["assets"][2]["identity"]); identity["target_season"] = "2025-26"
    with pytest.raises(ValueError): phase2c.validate_identity(identity, set(expected["team_directory"]))


def test_preview_is_read_only_and_persistence_is_create_once(tmp_path, expected):
    store = phase2c.Phase2CStore(tmp_path, expected, clock=lambda: "fixed")
    preview = phase2c.dry_run_plan(store)
    assert preview["network_calls"] == 0 and preview["side_effects"] == []
    assert not store.path.exists()
    first = phase2c.persist_initial_plan(store)
    assert first == phase2c.persist_initial_plan(store)
    phase2c.plan_path(tmp_path).write_text("conflict", encoding="utf-8")
    with pytest.raises(ValueError): phase2c.persist_initial_plan(store)


def test_unauthorized_identity_rejected_before_session(tmp_path, expected, monkeypatch):
    phase1c = REAL_CACHE / "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"
    target = tmp_path / "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"; target.parent.mkdir(parents=True)
    shutil.copyfile(phase1c, target)
    monkeypatch.setattr(phase2c.requests, "Session", lambda: pytest.fail("Session constructed"))
    identity = deepcopy(expected["assets"][2]["identity"]); identity["parameters"]["season"] = "2025-26"
    with pytest.raises(ValueError):
        phase2c.direct_transport(identity, cache_root=tmp_path, approved_identities={})


def test_nondefault_cache_reaches_real_adapter(tmp_path, expected, monkeypatch):
    phase1c = REAL_CACHE / "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"
    target = tmp_path / "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"; target.parent.mkdir(parents=True)
    shutil.copyfile(phase1c, target)
    identity = expected["assets"][2]["identity"]; aid = phase2c.asset_id(identity)
    seen = {}
    class Response:
        status_code = 200; content = b"{}"; headers = {}
    class Session:
        trust_env = True
        headers = {}
        def mount(self, prefix, adapter): seen["mounted"] = prefix
        def get(self, url, **kwargs): seen.update(url=url, kwargs=kwargs, trust_env=self.trust_env); return Response()
        def close(self): pass
    monkeypatch.setattr(phase2c.requests, "Session", Session)
    phase2c.direct_transport(identity, cache_root=tmp_path,
                             approved_identities={aid: {"identity": identity}})
    assert seen["kwargs"]["params"]["Season"] == "2022-23" and seen["trust_env"] is False


def test_default_acquisition_uses_nondefault_store_from_unrelated_cwd(
    store, expected, tmp_path, monkeypatch
):
    source = REAL_CACHE / "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"
    target = store.cache_root / "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"
    target.parent.mkdir(parents=True)
    shutil.copyfile(source, target)
    unrelated = tmp_path / "unrelated-working-directory"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    seen = []

    class Response:
        status_code = 403
        content = b"controlled nondefault-cache response"
        headers = {}

    class Session:
        def __init__(self):
            self.trust_env = True
            self.headers = {}

        def mount(self, prefix, adapter):
            assert prefix == "https://"

        def get(self, url, **kwargs):
            seen.append((url, kwargs, self.trust_env))
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(phase2c.requests, "Session", Session)
    result = phase2c.run_acquisition(
        store, live_acquisition=True, transport=None, sleep_fn=lambda _: None
    )
    assert result["stop_category"] == "nonretryable_http"
    assert len(seen) == 1 and seen[0][1]["params"]["Season"] == "2021-22"
    assert seen[0][2] is False
    assert (store.cache_root / store.load()["assets"][0]["attempt_history"][0]["preserved_response_path"]).exists()


def test_schema_quarantine_stops_without_advancing(store, expected):
    def transport(identity, timeout): return _response(expected, identity, bad_schema=True)
    result = phase2c.run_acquisition(store, live_acquisition=True, transport=transport, sleep_fn=lambda _: None)
    assert result["stop_category"] == "schema_quarantine" and result["attempts"] == 1
    manifest = store.load()
    assert manifest["assets"][1]["status"] == "planned"
    evidence = manifest["assets"][0]["attempt_history"][0]
    assert evidence["preserved_response_bytes"] > 0
    assert (store.cache_root / evidence["preserved_response_path"]).exists()


def test_http_503_body_survives_successful_retry(store, expected):
    calls = 0

    def transport(identity, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            return phase2c.TransportResult(503, b"temporary upstream failure", .1, {})
        if calls == 2:
            return _response(expected, identity)
        return phase2c.TransportResult(403, b"controlled stop", .1, {})

    result = phase2c.run_acquisition(
        store, live_acquisition=True, transport=transport, sleep_fn=lambda _: None
    )
    assert result["stop_category"] == "nonretryable_http"
    first = store.load()["assets"][0]
    failed_attempt, successful_attempt = first["attempt_history"]
    failure_path = store.cache_root / failed_attempt["preserved_response_path"]
    verified_path = store.cache_root / first["cache"]["relative_path"]
    assert failure_path.read_bytes() == b"temporary upstream failure"
    assert verified_path.exists() and verified_path.read_bytes() != failure_path.read_bytes()
    assert failed_attempt["preserved_response_bytes"] == len(b"temporary upstream failure")
    assert failed_attempt["preserved_response_raw_sha256"] == raw_body_hash(b"temporary upstream failure")
    assert successful_attempt["status"] == "verified"


def test_retryable_failure_retries_same_identity_and_preserves_history(store, expected):
    calls = []
    waits = []
    def transport(identity, timeout):
        calls.append(identity)
        if len(calls) == 1: raise phase2c.TransportError("timeout", "synthetic")
        return _response(expected, identity)
    result = phase2c.run_acquisition(store, live_acquisition=True, transport=transport, sleep_fn=waits.append)
    # Later assets succeed too; the relevant assertion is the first identity twice.
    assert calls[0] == calls[1]
    first = store.load()["assets"][0]
    assert first["attempt_count"] == 2 and [x["status"] for x in first["attempt_history"]] == ["retryable", "verified"]
    assert result["retry_attempts"] == 1
    assert waits[0] == 30.0


def test_phase2c_attempt_uses_configured_request_kind(store):
    result = phase2c.run_acquisition(
        store,
        live_acquisition=True,
        transport=lambda i, t: phase2c.TransportResult(403, b"controlled", .1, {}),
        sleep_fn=lambda _: None,
    )
    assert result["attempts"] == 1
    event = store.load()["assets"][0]["attempt_history"][0]
    assert event["request_kind"] == "phase2c_live"


@pytest.mark.parametrize("status", [401, 403, 429, 302])
def test_nonretryable_http_stops_once(store, status):
    result = phase2c.run_acquisition(
        store, live_acquisition=True,
        transport=lambda i, t: phase2c.TransportResult(status, b"blocked", .1, {}),
        sleep_fn=lambda _: None,
    )
    assert result["attempts"] == 1 and result["stop_category"] == "nonretryable_http"
    event = store.load()["assets"][0]["attempt_history"][0]
    assert (store.cache_root / event["preserved_response_path"]).read_bytes() == b"blocked"
    assert event["preserved_response_raw_sha256"] == raw_body_hash(b"blocked")


def test_invalid_json_body_is_preserved(store):
    body = b"not-json"
    result = phase2c.run_acquisition(
        store,
        live_acquisition=True,
        transport=lambda i, t: phase2c.TransportResult(200, body, .1, {}),
        sleep_fn=lambda _: None,
    )
    assert result["stop_category"] == "invalid_json"
    event = store.load()["assets"][0]["attempt_history"][0]
    assert (store.cache_root / event["preserved_response_path"]).read_bytes() == body
    assert event["preserved_response_bytes"] == len(body)


def test_preexisting_failure_evidence_stops_before_attempt_or_transport(
    store, monkeypatch
):
    item = store.load()["assets"][0]
    path = phase2c._failure_evidence_path(store, item, 1)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"preexisting evidence")
    monkeypatch.setattr(
        phase2c,
        "direct_transport",
        lambda *_args, **_kwargs: pytest.fail("transport selected or invoked"),
    )
    monkeypatch.setattr(
        phase2c.requests,
        "Session",
        lambda: pytest.fail("HTTP session constructed"),
    )
    result = phase2c.run_acquisition(
        store,
        live_acquisition=True,
        transport=None,
        sleep_fn=lambda _: None,
    )
    assert result["stop_category"] == "failure_evidence_preflight_collision"
    assert path.read_bytes() == b"preexisting evidence"
    manifest = store.load()
    assert manifest["assets"][0]["status"] == "planned"
    assert manifest["assets"][0]["attempt_count"] == 0
    assert manifest["assets"][0]["attempt_history"] == []
    assert manifest["assets"][1]["status"] == "planned"
    stop = manifest["integrity_stop"]
    assert stop["asset_id"] == item["asset_id"]
    assert stop["attempt_number"] == 1
    assert stop["conflicting_path"] == phase2c._relative_evidence_path(store, path)

    restarted = phase2c.Phase2CStore(
        store.cache_root, store.expected, clock=lambda: "restart"
    )
    restarted_result = phase2c.run_acquisition(
        restarted, live_acquisition=True, transport=None, sleep_fn=lambda _: None
    )
    assert restarted_result["stop_category"] == "persisted_integrity_stop"
    assert path.read_bytes() == b"preexisting evidence"


def test_postcheck_failure_evidence_race_preserves_returned_body_and_stops(
    store, monkeypatch
):
    item = store.load()["assets"][0]
    normal_path = phase2c._failure_evidence_path(store, item, 1)
    original_conflict = b"racing writer evidence"
    returned_body = b"retryable response that must survive"
    returned_sha = raw_body_hash(returned_body)
    original_atomic_write = phase2c.atomic_write_bytes_new
    calls = []

    def racing_atomic_write(path, body):
        if path == normal_path and not normal_path.exists():
            normal_path.parent.mkdir(parents=True, exist_ok=True)
            normal_path.write_bytes(original_conflict)
        return original_atomic_write(path, body)

    def transport(identity, timeout):
        calls.append(identity)
        return phase2c.TransportResult(503, returned_body, .1, {})

    monkeypatch.setattr(phase2c, "atomic_write_bytes_new", racing_atomic_write)
    result = phase2c.run_acquisition(
        store, live_acquisition=True, transport=transport, sleep_fn=lambda _: None
    )

    assert result["stop_category"] == "failure_evidence_postcheck_collision"
    assert len(calls) == 1
    assert normal_path.read_bytes() == original_conflict
    manifest = store.load()
    first = manifest["assets"][0]
    event = first["attempt_history"][0]
    collision_path = store.cache_root / event["preserved_response_path"]
    expected_collision_path = phase2c._failure_evidence_collision_path(
        store, item, 1, returned_sha
    )
    assert collision_path == expected_collision_path
    assert collision_path.read_bytes() == returned_body
    assert event["preserved_response_bytes"] == len(returned_body)
    assert event["preserved_response_raw_sha256"] == returned_sha
    assert event["error_category"] == "failure_evidence_postcheck_collision"
    assert first["attempt_count"] == 1 and first["status"] == "failed"
    assert manifest["assets"][1]["status"] == "planned"
    assert manifest["integrity_stop"]["preserved_response_path"] == event["preserved_response_path"]


def test_postcheck_race_reuses_identical_content_addressed_evidence(
    store, monkeypatch
):
    item = store.load()["assets"][0]
    normal_path = phase2c._failure_evidence_path(store, item, 1)
    normal_body = b"racing writer evidence"
    returned_body = b"returned response already preserved"
    returned_sha = raw_body_hash(returned_body)
    collision_path = phase2c._failure_evidence_collision_path(
        store, item, 1, returned_sha
    )
    collision_path.parent.mkdir(parents=True, exist_ok=True)
    collision_path.write_bytes(returned_body)
    original_atomic_write = phase2c.atomic_write_bytes_new
    calls = []

    def racing_atomic_write(path, body):
        if path == normal_path and not normal_path.exists():
            normal_path.write_bytes(normal_body)
        return original_atomic_write(path, body)

    def transport(identity, timeout):
        calls.append(identity)
        return phase2c.TransportResult(503, returned_body, .1, {})

    monkeypatch.setattr(phase2c, "atomic_write_bytes_new", racing_atomic_write)
    result = phase2c.run_acquisition(
        store, live_acquisition=True, transport=transport, sleep_fn=lambda _: None
    )

    assert result["stop_category"] == "failure_evidence_postcheck_collision"
    assert len(calls) == 1
    assert normal_path.read_bytes() == normal_body
    assert collision_path.read_bytes() == returned_body
    manifest = store.load()
    event = manifest["assets"][0]["attempt_history"][0]
    assert event["preserved_response_path"] == phase2c._relative_evidence_path(
        store, collision_path
    )
    assert event["preserved_response_bytes"] == len(returned_body)
    assert event["preserved_response_raw_sha256"] == returned_sha
    assert manifest["assets"][1]["status"] == "planned"


def test_content_addressed_contradiction_is_terminal_without_overwrite(
    store, monkeypatch
):
    item = store.load()["assets"][0]
    normal_path = phase2c._failure_evidence_path(store, item, 1)
    normal_body = b"racing writer evidence"
    returned_body = b"returned response that cannot be stored"
    returned_sha = raw_body_hash(returned_body)
    contradictory_body = b"bytes contradicting the content-addressed name"
    contradictory_sha = raw_body_hash(contradictory_body)
    collision_path = phase2c._failure_evidence_collision_path(
        store, item, 1, returned_sha
    )
    collision_path.parent.mkdir(parents=True, exist_ok=True)
    collision_path.write_bytes(contradictory_body)
    original_atomic_write = phase2c.atomic_write_bytes_new
    calls = []

    def racing_atomic_write(path, body):
        if path == normal_path and not normal_path.exists():
            normal_path.write_bytes(normal_body)
        return original_atomic_write(path, body)

    def transport(identity, timeout):
        calls.append(identity)
        return phase2c.TransportResult(503, returned_body, .1, {})

    monkeypatch.setattr(phase2c, "atomic_write_bytes_new", racing_atomic_write)
    result = phase2c.run_acquisition(
        store, live_acquisition=True, transport=transport, sleep_fn=lambda _: None
    )

    assert result["stop_category"] == "failure_evidence_content_address_mismatch"
    assert len(calls) == 1
    assert normal_path.read_bytes() == normal_body
    assert collision_path.read_bytes() == contradictory_body
    assert sorted(path.name for path in collision_path.parent.iterdir()) == sorted([
        normal_path.name,
        collision_path.name,
    ])
    manifest = store.load()
    first = manifest["assets"][0]
    event = first["attempt_history"][0]
    intended_path = phase2c._relative_evidence_path(store, collision_path)
    assert event["evidence_persistence_status"] == "content_addressed_contradiction"
    assert event["returned_body_expected_sha256"] == returned_sha
    assert event["returned_body_bytes"] == len(returned_body)
    assert event["intended_preserved_response_path"] == intended_path
    assert event["conflicting_file_actual_sha256"] == contradictory_sha
    assert "preserved_response_path" not in event
    assert "could not be persisted" in event["error_detail"]
    assert first["attempt_count"] == 1 and first["status"] == "failed"
    assert manifest["assets"][1]["status"] == "planned"
    stop = manifest["integrity_stop"]
    assert stop["returned_body_expected_sha256"] == returned_sha
    assert stop["returned_body_bytes"] == len(returned_body)
    assert stop["intended_preserved_response_path"] == intended_path
    assert stop["conflicting_file_actual_sha256"] == contradictory_sha
    assert "preserved_response_path" not in stop
    assert "could not be persisted" in stop["detail"]

    restarted = phase2c.Phase2CStore(
        store.cache_root, store.expected, clock=lambda: "restart"
    )
    restarted_result = phase2c.run_acquisition(
        restarted,
        live_acquisition=True,
        transport=lambda *_: pytest.fail("transport after terminal stop"),
        sleep_fn=lambda _: None,
    )
    assert restarted_result["stop_category"] == "persisted_integrity_stop"


def test_interrupted_and_persisted_stops_prevent_transport(store):
    manifest = store.load(); manifest["assets"][0]["status"] = "attempting"
    manifest["assets"][0]["attempt_history"] = [{"attempt_number": 1}]; manifest["assets"][0]["attempt_count"] = 1
    store.save(manifest)
    assert phase2c.run_acquisition(store, live_acquisition=True,
                                   transport=lambda *_: pytest.fail("transport"))["stop_category"] == "uncertain_interrupted_attempt"
    manifest = store.load(); manifest["assets"][0]["status"] = "planned"
    manifest["integrity_stop"] = {"category": "synthetic"}; store.save(manifest)
    restarted = phase2c.Phase2CStore(store.cache_root, store.expected, clock=lambda: "later")
    assert phase2c.run_acquisition(restarted, live_acquisition=True,
                                   transport=lambda *_: pytest.fail("transport"))["stop_category"] == "persisted_integrity_stop"


def test_restart_recreates_player_source_gate_before_transport(store, expected):
    _install_verified_assets(store, expected, count=2, persist_canary=False)
    restarted = phase2c.Phase2CStore(store.cache_root, store.expected, clock=lambda: "restart")
    reached = []

    def transport(identity, timeout):
        reached.append(True)
        assert restarted.load()["player_source_gate"]["status"] == "passed"
        return phase2c.TransportResult(403, b"controlled stop", .1, {})

    result = phase2c.run_acquisition(
        restarted, live_acquisition=True, transport=transport, sleep_fn=lambda _: None
    )
    assert reached == [True] and result["stop_category"] == "nonretryable_http"


def test_restart_recreates_completed_team_gate_before_transport(store, expected):
    _install_verified_assets(store, expected, count=4, persist_canary=False)
    restarted = phase2c.Phase2CStore(store.cache_root, store.expected, clock=lambda: "restart")

    def transport(identity, timeout):
        gates = restarted.load()["team_gate_results"]
        assert gates[phase2c.CANARY_TEAM_IDS[0]]["status"] == "passed"
        return phase2c.TransportResult(403, b"controlled stop", .1, {})

    result = phase2c.run_acquisition(
        restarted, live_acquisition=True, transport=transport, sleep_fn=lambda _: None
    )
    assert result["stop_category"] == "nonretryable_http"


def test_restart_recreates_canary_gate_before_transport(store, expected):
    _install_verified_assets(store, expected, count=12, persist_canary=False)
    restarted = phase2c.Phase2CStore(store.cache_root, store.expected, clock=lambda: "restart")

    def transport(identity, timeout):
        manifest = restarted.load()
        assert manifest["canary_result"]["status"] == "passed"
        assert len(manifest["team_gate_results"]) == 5
        return phase2c.TransportResult(403, b"controlled stop", .1, {})

    result = phase2c.run_acquisition(
        restarted, live_acquisition=True, transport=transport, sleep_fn=lambda _: None
    )
    assert result["stop_category"] == "nonretryable_http"


def test_restart_gate_disagreement_stops_before_session(store, expected, monkeypatch):
    _install_verified_assets(store, expected, count=2, persist_canary=False)
    manifest = store.load()
    manifest["player_source_gate"] = {"status": "passed", "deterministic_sha256": "stale"}
    store.save(manifest)
    monkeypatch.setattr(phase2c.requests, "Session", lambda: pytest.fail("session constructed"))
    result = phase2c.run_acquisition(
        phase2c.Phase2CStore(store.cache_root, store.expected, clock=lambda: "restart"),
        live_acquisition=True,
        transport=None,
    )
    assert result["stop_category"] == "player_source_gate_mismatch"
    assert store.load()["integrity_stop"]["category"] == "player_source_gate_mismatch"


def test_player_ids_are_strict_and_unique():
    assert phase2c.strict_player_source_audit([{"PLAYER_ID": 1}])["unique_ids"] == 1
    assert phase2c.strict_player_source_audit([{"PLAYER_ID": "01"}])["invalid_ids"]
    assert phase2c.strict_player_source_audit([{"PLAYER_ID": 1}, {"PLAYER_ID": 1}])["duplicate_ids"]


def test_canary_automatically_continues(store, expected):
    calls = []
    def transport(identity, timeout): calls.append(identity); return _response(expected, identity)
    result = phase2c.run_acquisition(store, live_acquisition=True, transport=transport, sleep_fn=lambda _: None)
    assert result["completed"] and len(calls) == 62
    assert store.load()["canary_result"]["status"] == "passed"


def test_synthetic_complete_analysis_is_deterministic_and_network_free(store, expected, monkeypatch):
    _install_verified_assets(store, expected)
    monkeypatch.setattr(requests, "Session", lambda: pytest.fail("network prohibited"))
    first = phase2c.analyze_release(store); second = phase2c.analyze_release(store)
    assert first["deterministic_analysis_sha256"] == second["deterministic_analysis_sha256"]
    assert first["combined"]["matched_observation_keys"] == 30
    assert first["player_sources"]["exact_id_set_match"]
    assert first["player_sources"]["totals_min_semantics"]["classification"] == "consistent_with_season_total_minutes"
    assert first["canary"]["certification"]["status"] == "certified"
    assert first["release_gates"]["canary_passed"]


@pytest.mark.parametrize(
    ("mutation", "mismatch"),
    [
        ("missing", "missing_persisted_canary"),
        ("team", "teams"),
        ("coverage", "coverage"),
        ("hash", "deterministic_sha256"),
    ],
)
def test_analysis_rejects_stale_or_missing_canary(store, expected, mutation, mismatch):
    _install_verified_assets(store, expected)
    manifest = store.load()
    if mutation == "missing":
        manifest["canary_result"] = None
    elif mutation == "team":
        team_id = phase2c.CANARY_TEAM_IDS[0]
        manifest["canary_result"]["teams"][team_id]["matched"] += 1
    elif mutation == "coverage":
        manifest["canary_result"]["coverage"]["total_pairs"] += 1
    else:
        manifest["canary_result"]["deterministic_sha256"] = "altered"
    store.save(manifest)
    analysis = phase2c.analyze_release(store)
    assert not analysis["release_gates"]["canary_passed"]
    assert mismatch in analysis["canary"]["certification"]["mismatch_fields"]
    assert analysis["primary_classification"] == "2022-23 raw request set complete; release audit unresolved"


def test_attempt_budget_validation_rejects_more_than_two(store):
    manifest = store.load(); item = manifest["assets"][0]
    item["attempt_history"] = [{"attempt_number": n} for n in (1, 2, 3)]; item["attempt_count"] = 3
    with pytest.raises(ValueError): phase2c.validate_manifest(manifest, store.expected)


def test_global_retry_budget_validation_rejects_seventh_retry(store):
    manifest = store.load()
    for item in manifest["assets"][:7]:
        item["attempt_history"] = [{"attempt_number": 1}, {"attempt_number": 2}]
        item["attempt_count"] = 2
    with pytest.raises(ValueError, match="cumulative attempt budget"):
        phase2c.validate_manifest(manifest, store.expected)


def test_phase2b_prerequisite_hashes_are_exact(expected):
    assert expected["phase2b_prerequisite"]["hashes"] == phase2c.PHASE2B_HASHES
