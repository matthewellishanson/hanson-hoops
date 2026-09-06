from __future__ import annotations

import json
import inspect
import sys
from itertools import count
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2 import phase2c_raw_season as engine
from pair_fit_v2 import phase2d_raw_season as phase2d
from pair_fit_v2.phase1c_manifest import atomic_write_json, canonical_json_hash, raw_body_hash


REAL_CACHE = Path(__file__).parents[1] / "cache"


@pytest.fixture(scope="module")
def expected():
    return phase2d.build_expected_manifest(REAL_CACHE)


@pytest.fixture
def store(tmp_path, expected):
    ticks = count()
    result = engine.Phase2CStore(
        tmp_path,
        expected,
        clock=lambda: f"tick-{next(ticks):04d}",
        spec=phase2d.SPEC,
    )
    phase2d.persist_initial_plan(result)
    return result


def _columns(expected, identity):
    if identity["endpoint"] == engine.PLAYER_ENDPOINT:
        return expected["approved_player_schema_contract"]["LeagueDashPlayerStats"]["columns"]
    return expected["approved_pair_schema_contract"][identity["parameters"]["measure_type"]]


def _row(columns, values):
    return [values.get(column, 0) for column in columns]


def _payload(expected, identity):
    params = identity["parameters"]
    returned = {
        "Season": params["season"],
        "SeasonType": engine.SEASON_TYPE,
        "MeasureType": params["measure_type"],
        "LeagueID": engine.LEAGUE_ID,
    }
    if identity["endpoint"] == engine.PLAYER_ENDPOINT:
        returned["PerMode"] = params["per_mode"]
        columns = list(_columns(expected, identity))
        rows = [
            _row(columns, {
                "PLAYER_ID": player_id,
                "PLAYER_NAME": f"P{player_id}",
                "TEAM_ID": 0,
                "MIN": 2500 if params["per_mode"] == "Totals" else 48,
            })
            for player_id in (1, 2)
        ]
        return {"parameters": returned, "resultSets": [{
            "name": "LeagueDashPlayerStats", "headers": columns, "rowSet": rows,
        }]}
    returned.update({"TeamID": int(params["team_id"]), "GroupQuantity": 2})
    sets = []
    for name in ("Overall", "Lineups"):
        columns = list(_columns(expected, identity)[name]["columns"])
        values = {
            "TEAM_ID": int(params["team_id"]), "GROUP_SET": "Lineups",
            "GROUP_ID": "-1-2-", "GROUP_NAME": "P1 - P2", "GP": 1,
            "MIN": 10.5, "POSS": 20, "OFF_RATING": 110.0,
            "DEF_RATING": 100.0, "NET_RATING": 10.0,
            "E_OFF_RATING": 109.0, "E_DEF_RATING": 101.0,
            "E_NET_RATING": 8.0, "PLUS_MINUS": 2,
        }
        sets.append({"name": name, "headers": columns, "rowSet": [_row(columns, values)]})
    return {"parameters": returned, "resultSets": sets}


def _response(expected, identity):
    body = json.dumps(_payload(expected, identity), separators=(",", ":")).encode()
    return engine.TransportResult(200, body, 0.1, {})


def test_phase2d_plan_is_exact_and_isolated(expected):
    assets = expected["assets"]
    assert len(assets) == 62
    assert [x["identity"]["parameters"].get("per_mode") for x in assets[:2]] == [
        "Per100Possessions", "Totals",
    ]
    assert [x["identity"]["parameters"]["measure_type"] for x in assets[2:]] == [
        "Base", "Advanced",
    ] * 30
    assert all(x["identity"]["target_season"] == "2021-22" for x in assets)
    assert all(x["identity"]["prior_feature_season"] == "2020-21" for x in assets)
    assert {x["identity"]["parameters"]["season"] for x in assets[:2]} == {"2020-21"}
    assert {x["identity"]["parameters"]["season"] for x in assets[2:]} == {"2021-22"}
    assert all(x["cache"]["relative_path"].startswith("phase2d/raw/") for x in assets)
    assert not ({x["asset_id"] for x in assets} & {
        x["asset_id"] for x in engine.build_expected_manifest(REAL_CACHE)["assets"]
    })


def test_preview_is_read_only_and_paths_are_release_scoped(tmp_path, expected):
    store = engine.Phase2CStore(
        tmp_path, expected, clock=lambda: "fixed", spec=phase2d.SPEC
    )
    preview = phase2d.dry_run_plan(store)
    assert preview["network_calls"] == 0 and preview["side_effects"] == []
    assert not store.path.exists()
    assert phase2d.manifest_path(tmp_path) == tmp_path / "phase2d/manifest.json"
    assert phase2d.ledger_path(tmp_path) == tmp_path / "phase2d/attempt_ledger.json"
    assert engine._failure_evidence_path(store, expected["assets"][0], 1).is_relative_to(
        tmp_path / "phase2d/failure_evidence"
    )


def test_exact_prior_relationship_and_scope_are_enforced(expected):
    with pytest.raises(ValueError, match="immediately preceding"):
        engine.HistoricalSeasonSpec(
            **{**phase2d.SPEC.__dict__, "prior_feature_season": "2019-20"}
        )
    identity = json.loads(json.dumps(expected["assets"][0]["identity"]))
    identity["prior_feature_season"] = "2021-22"
    with pytest.raises(ValueError):
        engine.validate_identity(identity, set(expected["team_directory"]), phase2d.SPEC)


def test_phase2c_default_configuration_remains_byte_compatible():
    store = engine.create_store(REAL_CACHE)
    analysis = engine.analyze_release(store)
    assert engine._sha256_file(store.path) == engine.PHASE2C_HASHES["manifest"]
    assert engine._sha256_file(store.ledger_path) == engine.PHASE2C_HASHES["ledger"]
    assert analysis["deterministic_analysis_sha256"] == engine.PHASE2C_HASHES["analysis"]
    assert analysis["combined"]["matched_observation_keys"] == 4805


def test_phase2d_configured_engine_completes_synthetic_release(store, expected):
    calls = []

    def transport(identity, timeout):
        calls.append(identity)
        return _response(expected, identity)

    result = phase2d.run_acquisition(
        store, live_acquisition=True, transport=transport, sleep_fn=lambda _: None
    )
    assert result["completed"] and len(calls) == 62
    first = phase2d.analyze_release(store)
    second = phase2d.analyze_release(store)
    assert first == second
    assert first["target_season"] == "2021-22"
    assert first["prior_feature_season"] == "2020-21"
    assert first["combined"]["matched_observation_keys"] == 30
    assert first["canary"]["certification"]["status"] == "certified"
    assert first["primary_classification"] == phase2d.SPEC.supported_classification


def test_phase2d_attempt_uses_configured_request_kind(store):
    result = phase2d.run_acquisition(
        store,
        live_acquisition=True,
        transport=lambda i, t: engine.TransportResult(403, b"controlled", .1, {}),
        sleep_fn=lambda _: None,
    )
    assert result["attempts"] == 1
    event = store.load()["assets"][0]["attempt_history"][0]
    assert event["request_kind"] == "phase2d_live"


def test_shared_runner_has_no_hardcoded_phase2c_request_kind():
    assert "phase2c_live" not in inspect.getsource(engine.run_acquisition)


def test_request_kind_is_required_and_validated_before_transport(monkeypatch):
    reached = []
    monkeypatch.setattr(engine, "direct_transport", lambda *_a, **_k: reached.append(True))
    values = dict(phase2d.SPEC.__dict__)
    values["request_kind"] = "Phase2D"
    with pytest.raises(ValueError, match="request_kind"):
        engine.HistoricalSeasonSpec(**values)
    values.pop("request_kind")
    with pytest.raises(TypeError):
        engine.HistoricalSeasonSpec(**values)
    assert reached == []


def test_phase2d_unauthorized_identity_stops_before_session(tmp_path, expected, monkeypatch):
    monkeypatch.setattr(
        engine.requests, "Session", lambda: pytest.fail("Session constructed")
    )
    identity = json.loads(json.dumps(expected["assets"][0]["identity"]))
    identity["parameters"]["season"] = "2025-26"
    with pytest.raises(ValueError):
        engine.direct_transport(
            identity, cache_root=tmp_path, approved_identities={}, spec=phase2d.SPEC
        )
