from __future__ import annotations

import json
import shutil
import socket
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pair_fit_v2.phase2b_raw_season as phase2b
import pair_fit_v2.phase2b_cli as phase2b_cli
from pair_fit_v2.phase2b_raw_season import (
    MAX_NEW_ATTEMPTS,
    ReleaseStore,
    TransportError,
    TransportResult,
    audit_team_payloads,
    build_expected_manifest,
    pair_identity,
    release_asset_id,
    request_parameters,
    run_acquisition,
    validate_manifest,
    validate_pair_identity,
    validate_response,
    validate_season_scope,
)


REAL_CACHE = Path(__file__).parents[1] / "cache"


@pytest.fixture(scope="module")
def expected():
    return build_expected_manifest(REAL_CACHE)


@pytest.fixture
def store(tmp_path, expected):
    result = ReleaseStore(tmp_path, expected, clock=lambda: "2026-09-01T00:00:00Z")
    result.create_or_load()
    return result


def _payload(identity, expected, *, pair_id="-101-202-", poss=10, net=10.0):
    measure = identity["parameters"]["measure_type"]
    schema = expected["approved_pair_schema_contract"][measure]
    sets = []
    for name in ("Overall", "Lineups"):
        headers = list(schema[name]["columns"])
        row = [0 for _ in headers]
        if name == "Overall":
            row[headers.index("TEAM_ID")] = int(identity["parameters"]["team_id"])
        else:
            row[headers.index("GROUP_ID")] = pair_id
            row[headers.index("GROUP_NAME")] = "A. One - B. Two"
            row[headers.index("GP")] = 1
            row[headers.index("MIN")] = 5.5
            if measure == "Advanced":
                row[headers.index("POSS")] = poss
                row[headers.index("OFF_RATING")] = 110.0
                row[headers.index("DEF_RATING")] = 100.0
                row[headers.index("NET_RATING")] = net
                row[headers.index("E_OFF_RATING")] = 110.0
                row[headers.index("E_DEF_RATING")] = 100.0
                row[headers.index("E_NET_RATING")] = net
        sets.append({"name": name, "headers": headers, "rowSet": [row]})
    return {
        "parameters": {
            "Season": "2023-24",
            "SeasonType": "Regular Season",
            "MeasureType": measure,
            "TeamID": int(identity["parameters"]["team_id"]),
            "GroupQuantity": 2,
            "LeagueID": None,
        },
        "resultSets": sets,
    }


def _bypass_import_replay(monkeypatch, store=None):
    monkeypatch.setattr(
        phase2b,
        "verify_all_imports_and_dependencies",
        lambda _store: {"network_calls": 0, "imported_pair_assets_verified": 10, "player_dependencies_verified": 2},
    )
    original = phase2b.verify_release_asset

    def verify(asset, release_store, manifest):
        if asset["mode"] == "imported_reuse":
            payload = _payload(asset["identity"], release_store.expected)
            validation = validate_response(payload, asset["identity"], manifest)
            return {
                "payload": payload,
                **validation,
                "canonical_json_hash": "imported",
                "raw_body_hash": "imported",
                "cache_file_bytes": 1,
                "provenance": "fixture_import",
            }
        return original(asset, release_store, manifest)

    monkeypatch.setattr(phase2b, "verify_release_asset", verify)
    if store is not None and not (store.cache_root / "phase2b/live_allowlist.json").exists():
        phase2b.persist_initial_plan(store)


def test_deterministic_30_team_60_entry_order_and_exact_reuse_counts(expected):
    assets = expected["pair_assets"]
    assert len(assets) == 60
    assert len(expected["team_directory"]) == 30
    assert sum(a["mode"] == "imported_reuse" for a in assets) == 10
    assert sum(a["mode"] == "new_acquisition" for a in assets) == 50
    assert [(a["identity"]["parameters"]["measure_type"]) for a in assets[::2]] == ["Base"] * 30
    assert [(a["identity"]["parameters"]["measure_type"]) for a in assets[1::2]] == ["Advanced"] * 30
    assert [int(a["identity"]["parameters"]["team_id"]) for a in assets[::2]] == sorted(
        int(a["identity"]["parameters"]["team_id"]) for a in assets[::2]
    )


def test_unique_release_ids_and_phase2b_cache_paths(expected):
    ids = [a["release_asset_id"] for a in expected["pair_assets"]]
    paths = [a["cache"]["relative_path"] for a in expected["pair_assets"] if a["cache"]]
    assert len(ids) == len(set(ids)) == 60
    assert len(paths) == len(set(paths)) == 50
    assert all(path.startswith("phase2b/raw/") for path in paths)


def test_fixed_season_mapping_and_future_same_season_rejection(expected):
    validate_season_scope("2023-24", "2022-23")
    with pytest.raises(ValueError):
        validate_season_scope("2023-24", "2023-24")
    identity = deepcopy(expected["pair_assets"][0]["identity"])
    identity["parameters"]["season"] = "2025-26"
    with pytest.raises(ValueError):
        validate_pair_identity(identity, set(expected["team_directory"]))


def test_live_allowlist_rejects_canary_refetch_player_and_out_of_season(expected):
    team_ids = set(expected["team_directory"])
    canary = next(a for a in expected["pair_assets"] if a["mode"] == "imported_reuse")
    assert canary["mode"] == "imported_reuse"
    identity = deepcopy(canary["identity"])
    identity["endpoint"] = "LeagueDashPlayerStats"
    with pytest.raises(ValueError):
        validate_pair_identity(identity, team_ids)
    identity = deepcopy(canary["identity"])
    identity["parameters"]["team_id"] = "999"
    with pytest.raises(ValueError):
        validate_pair_identity(identity, team_ids)


def test_request_parameters_are_exact_full_season_contract(expected):
    identity = expected["pair_assets"][0]["identity"]
    params = request_parameters(identity, set(expected["team_directory"]))
    assert params["Season"] == "2023-24" and params["LastNGames"] == "0"
    assert params["DateFrom"] == params["DateTo"] == ""
    assert params["GroupQuantity"] == "2" and params["MeasureType"] == "Base"
    assert "season" not in params and "team_id" not in params


def test_imports_retain_source_provenance_and_have_no_attempts(expected):
    for asset in (a for a in expected["pair_assets"] if a["mode"] == "imported_reuse"):
        assert asset["attempt_count"] == 0 and asset["attempt_history"] == []
        assert asset["source_reference"]["source_asset_id"].startswith("phase2a-raw-asset:")
        assert asset["source_reference"]["raw_body_hash"]
        assert asset["source_reference"]["canonical_json_hash"]


def test_manifest_rejects_imported_provenance_mutation(expected):
    changed = deepcopy(expected)
    imported = next(a for a in changed["pair_assets"] if a["mode"] == "imported_reuse")
    imported["source_reference"]["raw_body_hash"] = "changed"
    with pytest.raises(ValueError):
        validate_manifest(changed, expected)


def test_dry_run_has_zero_network_and_correct_actions(store, monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_k: pytest.fail("network prohibited"))
    _bypass_import_replay(monkeypatch, store)
    plan = phase2b.dry_run_plan(store)
    assert plan["network_calls"] == 0 and plan["pair_entries"] == 60
    assert plan["initial_imported_reuses"] == 10
    assert plan["planned_or_remaining_acquisitions"] == 50
    assert plan["player_dependencies"] == 2


def test_dry_run_persists_exact_50_identity_allowlist(store, monkeypatch):
    _bypass_import_replay(monkeypatch, store)
    result = phase2b.persist_dry_run(store)
    allowlist = json.loads((store.cache_root / result["live_allowlist_path"]).read_text())
    assert result["live_allowlist_count"] == 50
    assert len(allowlist["authorized_assets"]) == 50
    assert all(
        item["identity"]["parameters"]["team_id"] not in phase2b.CANARY_TEAM_IDS
        for item in allowlist["authorized_assets"]
    )


def test_exact_schema_enforcement_and_drift_rejection(expected):
    identity = expected["pair_assets"][0]["identity"]
    good = _payload(identity, expected)
    assert validate_response(good, identity, expected)["drift_classification"] == "identical"
    bad = deepcopy(good)
    bad["resultSets"][1]["headers"].append("UNREVIEWED")
    bad["resultSets"][1]["rowSet"][0].append(0)
    result = validate_response(bad, identity, expected)
    assert result["accepted"] is False


def test_row_width_and_empty_result_fail(expected):
    identity = expected["pair_assets"][0]["identity"]
    bad_width = _payload(identity, expected)
    bad_width["resultSets"][1]["rowSet"][0].pop()
    with pytest.raises(ValueError):
        validate_response(bad_width, identity, expected)
    empty = _payload(identity, expected)
    empty["resultSets"][1]["rowSet"] = []
    with pytest.raises(ValueError):
        validate_response(empty, identity, expected)


def test_full_outer_reconciliation_and_positive_target_gate(expected):
    base_id = next(a["identity"] for a in expected["pair_assets"] if a["identity"]["parameters"]["measure_type"] == "Base")
    adv_id = next(a["identity"] for a in expected["pair_assets"] if a["identity"]["parameters"]["measure_type"] == "Advanced" and a["identity"]["parameters"]["team_id"] == base_id["parameters"]["team_id"])
    clean = audit_team_payloads(base_id["parameters"]["team_id"], _payload(base_id, expected), _payload(adv_id, expected))
    assert clean["clean_release_gate"] is True and clean["reconciliation"]["matched_pairs"] == 1
    bad = audit_team_payloads(base_id["parameters"]["team_id"], _payload(base_id, expected), _payload(adv_id, expected, net=9.0))
    assert bad["clean_release_gate"] is False


def test_zero_possession_is_preserved_not_a_team_stop(expected):
    base_id = expected["pair_assets"][0]["identity"]
    adv_id = expected["pair_assets"][1]["identity"]
    audit = audit_team_payloads(base_id["parameters"]["team_id"], _payload(base_id, expected), _payload(adv_id, expected, poss=0))
    assert audit["clean_release_gate"] is True


def test_first_failure_stops_without_retry_or_progression(store, monkeypatch):
    _bypass_import_replay(monkeypatch, store)
    calls = []

    def failed(identity, _timeout):
        calls.append(identity)
        raise TransportError("timeout", "fixture timeout")

    result = run_acquisition(store, live_acquisition=True, transport=failed, sleep_fn=lambda _: None)
    assert result["new_attempts"] == 1 and result["failed"] == 1
    assert result["unattempted"] == 49 and len(calls) == 1
    result2 = run_acquisition(
        store,
        live_acquisition=True,
        transport=lambda *_: pytest.fail("no retry"),
        sleep_fn=lambda _: None,
    )
    assert result2["new_attempts"] == 1 and result2["stop_category"] == "existing_failed"


def test_successful_team_is_cached_replayed_then_next_team_can_continue(store, monkeypatch):
    _bypass_import_replay(monkeypatch, store)
    calls = []

    def transport(identity, _timeout):
        calls.append((identity["parameters"]["team_id"], identity["parameters"]["measure_type"]))
        if len(calls) == 3:
            raise TransportError("timeout", "bounded stop")
        return TransportResult(200, json.dumps(_payload(identity, store.expected)).encode(), 0.01)

    result = run_acquisition(store, live_acquisition=True, transport=transport, sleep_fn=lambda _: None)
    assert calls[:2] == [("1610612737", "Base"), ("1610612737", "Advanced")]
    assert result["new_verified"] == 2 and result["new_attempts"] == 3


def test_schema_quarantine_stops_and_preserves_body(store, monkeypatch):
    _bypass_import_replay(monkeypatch, store)

    def transport(identity, _timeout):
        payload = _payload(identity, store.expected)
        payload["resultSets"][1]["headers"].append("NEW")
        payload["resultSets"][1]["rowSet"][0].append(0)
        return TransportResult(200, json.dumps(payload).encode(), 0.01)

    result = run_acquisition(store, live_acquisition=True, transport=transport, sleep_fn=lambda _: None)
    assert result["quarantined"] == 1 and result["new_attempts"] == 1
    assert list((store.cache_root / "phase2b/quarantine").glob("*.body"))


def test_attempt_budget_is_cumulative_and_fixed(expected):
    assert expected["authorization"] == {"maximum_new_live_attempts": MAX_NEW_ATTEMPTS, "retries": 0}
    assert MAX_NEW_ATTEMPTS == 50


def test_threshold_coverage_keeps_history_and_eligibility_separate():
    joined = [
        {"player_1_matched": True, "player_2_matched": True, "shared_poss": 100, "shared_min": 50},
        {"player_1_matched": True, "player_2_matched": False, "shared_poss": 5, "shared_min": 2},
        {"player_1_matched": False, "player_2_matched": False, "shared_poss": 0, "shared_min": 0.1},
    ]
    detail = phase2b._coverage_detail(joined)
    thresholds = phase2b._threshold_coverage(joined)
    assert detail["categories"]["complete"]["count"] == 1
    assert detail["categories"]["both_missing"]["target_ineligible"] == 1
    assert next(row for row in thresholds if row["possessions_at_least"] == 5)["rows"] == 2


def test_import_and_normal_offline_operations_have_no_network(monkeypatch, expected):
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_k: pytest.fail("network prohibited"))
    assert release_asset_id(expected["pair_assets"][0]["identity"])
    assert pair_identity("1610612737", "Base", set(expected["team_directory"]))


def test_direct_transport_builds_team_id_allowlist_without_tuple_mismatch(monkeypatch, expected):
    observed = {}

    class Response:
        status_code = 200
        content = b"{}"

    class Session:
        trust_env = True

        def __init__(self):
            self.headers = self

        def update(self, values):
            observed["headers"] = values

        def get(self, url, *, params, timeout):
            observed.update({"url": url, "params": params, "timeout": timeout, "trust_env": self.trust_env})
            return Response()

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr(phase2b.requests, "Session", Session)
    identity = expected["pair_assets"][0]["identity"]
    approved = {
        phase2b.release_asset_id(identity): {
            "release_asset_id": phase2b.release_asset_id(identity),
            "identity": identity,
        }
    }
    result = phase2b.direct_transport(
        identity, cache_root=REAL_CACHE, approved_identities=approved
    )
    assert result.status_code == 200
    assert observed["params"]["TeamID"] == "1610612737"
    assert observed["timeout"] == 30 and observed["trust_env"] is False and observed["closed"] is True


def test_default_acquisition_transport_uses_nondefault_store_cache_root(tmp_path, monkeypatch):
    selected_cache = (tmp_path / "selected_nondefault_cache").resolve()
    shutil.copytree(REAL_CACHE.resolve(), selected_cache)
    shutil.rmtree(selected_cache / "phase2b")
    unrelated_cwd = tmp_path / "unrelated_working_directory"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)
    assert not (unrelated_cwd / "research/pair-fit-v2/cache").exists()

    selected_store = phase2b.create_store(
        selected_cache,
        clock=lambda: "2026-09-01T00:00:00Z",
    )
    selected_store.create_or_load()
    phase2b.persist_initial_plan(selected_store)
    observed = {"session_constructions": 0, "gets": 0}

    class Response:
        status_code = 503
        content = b"offline fixture response"

    class Session:
        trust_env = True

        def __init__(self):
            observed["session_constructions"] += 1
            self.headers = self

        def update(self, _values):
            pass

        def get(self, _url, *, params, timeout):
            observed["gets"] += 1
            observed["team_id"] = params["TeamID"]
            observed["timeout"] = timeout
            observed["trust_env"] = self.trust_env
            return Response()

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr(phase2b.requests, "Session", Session)
    result = run_acquisition(
        selected_store,
        live_acquisition=True,
        transport=None,
        sleep_fn=lambda _seconds: pytest.fail("first failed response must stop the queue"),
    )
    assert result["stop_category"] == "non_200_http"
    assert result["new_attempts"] == 1
    assert observed == {
        "session_constructions": 1,
        "gets": 1,
        "team_id": "1610612737",
        "timeout": 30,
        "trust_env": False,
        "closed": True,
    }
    assert (selected_cache / "phase2b/release_manifest.json").exists()


def test_direct_transport_rejects_unauthorized_identity_before_session(monkeypatch, expected):
    identity = deepcopy(expected["pair_assets"][0]["identity"])
    identity["parameters"]["measure_type"] = "Four Factors"
    monkeypatch.setattr(
        phase2b.requests,
        "Session",
        lambda: pytest.fail("unauthorized identity must fail before session construction"),
    )
    with pytest.raises(ValueError, match="Unauthorized Phase 2B pair request identity"):
        phase2b.direct_transport(
            identity,
            cache_root=REAL_CACHE,
            approved_identities={},
        )


def test_persisted_analysis_failure_stops_after_restart_before_transport(store, monkeypatch):
    _bypass_import_replay(monkeypatch, store)
    manifest = store.load()
    affected = [
        asset
        for asset in manifest["pair_assets"]
        if asset["identity"]["parameters"]["team_id"] == "1610612739"
    ]
    following = [
        asset
        for asset in manifest["pair_assets"]
        if asset["identity"]["parameters"]["team_id"] == "1610612740"
    ]
    assert [asset["identity"]["parameters"]["measure_type"] for asset in affected] == [
        "Base",
        "Advanced",
    ]
    for asset in affected:
        asset["status"] = "verified"
    assert all(asset["status"] == "planned" for asset in following)
    manifest["release_analysis_failure"] = {
        "team_id": "1610612739",
        "category": "fixture_analysis_stop",
    }
    store.save(manifest)
    restarted = ReleaseStore(
        store.cache_root,
        store.expected,
        clock=lambda: "2026-09-01T00:01:00Z",
    )
    reloaded = restarted.load()
    assert all(asset["status"] == "verified" for asset in reloaded["pair_assets"][4:6])
    assert all(asset["status"] == "planned" for asset in reloaded["pair_assets"][6:8])
    monkeypatch.setattr(
        phase2b,
        "verify_all_imports_and_dependencies",
        lambda _store: pytest.fail("persisted stop must occur before prerequisite replay"),
    )
    monkeypatch.setattr(
        phase2b.requests,
        "Session",
        lambda: pytest.fail("persisted stop must occur before HTTP setup"),
    )
    result = run_acquisition(
        restarted,
        live_acquisition=True,
        transport=None,
    )
    assert result["stop_category"] == "persisted_release_analysis_failure"
    assert result["persisted_analysis_failure"]["category"] == "fixture_analysis_stop"
    after = restarted.load()
    assert all(asset["attempt_count"] == 0 for asset in after["pair_assets"][6:8])
    assert all(asset["status"] == "planned" for asset in after["pair_assets"][6:8])


def test_persisted_allowlist_tamper_stops_before_transport(store, monkeypatch):
    _bypass_import_replay(monkeypatch, store)
    path = store.cache_root / "phase2b/live_allowlist.json"
    payload = json.loads(path.read_text())
    payload["authorized_assets"][0]["identity"]["parameters"]["team_id"] = "1610612738"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="allowlist identities"):
        run_acquisition(
            store,
            live_acquisition=True,
            transport=lambda *_: pytest.fail("invalid allowlist must prevent transport"),
        )


def test_initial_plan_is_create_once_and_preview_is_read_only(store, monkeypatch, capsys):
    _bypass_import_replay(monkeypatch, store)
    plan_path = store.cache_root / "phase2b/dry_run.json"
    allowlist_path = store.cache_root / "phase2b/live_allowlist.json"
    before = (plan_path.read_bytes(), allowlist_path.read_bytes())
    monkeypatch.setattr(phase2b_cli, "create_store", lambda _root: store)
    assert phase2b_cli.main(["--cache-root", str(store.cache_root), "--dry-run"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"]["command_semantics"] == "read_only_preview"
    assert output["dry_run"]["side_effects"] == []
    assert before == (plan_path.read_bytes(), allowlist_path.read_bytes())
    with pytest.raises(SystemExit, match="cannot be combined"):
        phase2b_cli.main(["--cache-root", str(store.cache_root), "--dry-run", "--initialize"])
    persisted = phase2b.persist_initial_plan(store)
    assert persisted["evidence_action"] == "validated_existing"
    assert persisted["side_effects"] == []
    assert before == (plan_path.read_bytes(), allowlist_path.read_bytes())


@pytest.mark.parametrize("pair_id", ["-abc-202-", "-0101-202-", "-0-202-", "-101-101-"])
def test_strict_pair_ids_reject_previously_parseable_or_invalid_values(expected, pair_id):
    identity = expected["pair_assets"][0]["identity"]
    with pytest.raises(ValueError, match="stable player IDs"):
        validate_response(_payload(identity, expected, pair_id=pair_id), identity, expected)


def test_prior_player_boundary_rejects_duplicate_invalid_and_same_season(expected):
    identity = expected["player_dependencies"][0]["source_identity"]
    assert phase2b.strict_player_source_audit(
        [{"PLAYER_ID": 101}, {"PLAYER_ID": "202"}], identity
    )["player_ids"] == ["101", "202"]
    with pytest.raises(ValueError, match="invalid or duplicate"):
        phase2b.strict_player_source_audit(
            [{"PLAYER_ID": "101"}, {"PLAYER_ID": 101}], identity
        )
    with pytest.raises(ValueError, match="invalid or duplicate"):
        phase2b.strict_player_source_audit([{"PLAYER_ID": "01"}], identity)
    same_season = deepcopy(identity)
    same_season["prior_feature_season"] = "2023-24"
    same_season["parameters"]["season"] = "2023-24"
    with pytest.raises(ValueError, match="only target 2023-24 and prior 2022-23"):
        phase2b.strict_player_source_audit([{"PLAYER_ID": 101}], same_season)


def test_synthetic_completed_season_analysis_is_deterministic_and_offline(store, monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_k: pytest.fail("network prohibited"))
    monkeypatch.setattr(phase2b.requests, "Session", lambda: pytest.fail("network prohibited"))
    manifest = store.load()
    for asset in manifest["pair_assets"]:
        if asset["mode"] == "new_acquisition":
            asset["status"] = "verified"
    store.save(manifest)
    monkeypatch.setattr(
        phase2b,
        "verify_all_imports_and_dependencies",
        lambda _store: {
            "network_calls": 0,
            "imported_pair_assets_verified": 10,
            "player_dependencies_verified": 2,
        },
    )

    def verify_pair(asset, release_store, current_manifest):
        payload = _payload(asset["identity"], release_store.expected)
        validation = validate_response(payload, asset["identity"], current_manifest)
        return {
            "payload": payload,
            **validation,
            "raw_body_hash": "fixture-raw",
            "canonical_json_hash": "fixture-canonical",
            "cache_file_bytes": 1,
            "provenance": "isolated_fixture",
        }

    monkeypatch.setattr(phase2b, "verify_release_asset", verify_pair)
    source_manifest = {
        "raw_assets": [{} for _ in range(10)]
        + [
            {"identity": dependency["source_identity"]}
            for dependency in store.expected["player_dependencies"]
        ]
    }
    source_pairs = {
        "total_pair_rows": 5,
        "both_players_matched": 5,
        "only_player_1_matched": 0,
        "only_player_2_matched": 0,
        "neither_player_matched": 0,
    }
    source_analysis = {
        "deterministic_analysis_sha256": "fixture-phase2a",
        "teams": {
            team_id: {"reconciliation": {"matched_pairs": 1}}
            for team_id in phase2b.CANARY_TEAM_IDS
        },
        "prior_coverage": {"combined": {"pairs": source_pairs}},
    }
    monkeypatch.setattr(
        phase2b,
        "_phase2a_context",
        lambda _root: (object(), source_manifest, source_analysis),
    )
    player_payload = {
        "resultSets": [
            {
                "name": "LeagueDashPlayerStats",
                "headers": ["PLAYER_ID", "PLAYER_NAME"],
                "rowSet": [[101, "A. One"], [202, "B. Two"]],
            }
        ]
    }
    monkeypatch.setattr(
        phase2b,
        "verify_phase2a_asset_cache",
        lambda *_a, **_k: {"payload": deepcopy(player_payload)},
    )
    first = phase2b.analyze_release(store)
    second = phase2b.analyze_release(store)
    assert first["request_set"]["pair_entries"] == 60
    assert first["combined"]["matched_observation_keys"] == 30
    assert first["canary_reproduction"]["exact"] is True
    assert first["primary_classification"].startswith("2023-24 raw release supported")
    assert first["deterministic_analysis_sha256"] == second["deterministic_analysis_sha256"]
