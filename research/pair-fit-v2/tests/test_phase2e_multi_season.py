from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase2e_multi_season as e
from test_phase2d_raw_season import _response

REAL_CACHE = Path(__file__).parents[1] / "cache"


@pytest.fixture(scope="module")
def expected():
    return tuple(s.expected for s in e.create_stores(REAL_CACHE))


@pytest.fixture
def stores(tmp_path, expected):
    result = tuple(e.engine.Phase2CStore(tmp_path, value, clock=lambda: "fixed", spec=spec)
                   for value, spec in zip(expected, e.SPECS))
    e.initialize(result)
    return result


def test_seven_exact_specs_and_read_only_master(tmp_path, expected):
    stores = tuple(e.engine.Phase2CStore(tmp_path, value, clock=lambda: "fixed", spec=spec)
                   for value, spec in zip(expected, e.SPECS))
    a = e.preview(stores)
    assert a == e.preview(stores)
    assert not list(tmp_path.iterdir())
    assert len(a["assets"]) == 434
    assert len({x["asset_id"] for x in a["assets"]}) == 434
    assert len({e.engine.canonical_json_hash(x["identity"]) for x in a["assets"]}) == 434
    assert [x["master_ordinal"] for x in a["assets"]] == list(range(1, 435))
    for index, spec in enumerate(e.SPECS):
        assert (spec.target_season, spec.prior_feature_season) == e.SEASON_PAIRS[index]
        assert int(spec.target_season[:4]) == int(spec.prior_feature_season[:4]) + 1
        assert spec.request_kind == f"phase2e_{spec.target_season.replace('-', '_')}_live"
        assert spec.canary_asset_count == 12
        assert (spec.maximum_first_attempts, spec.maximum_retry_attempts, spec.maximum_total_attempts) == (62, 6, 68)
        entries = a["assets"][index*62:(index+1)*62]
        assert [x["ordinal"] for x in entries] == list(range(1, 63))
        assert [x["identity"]["parameters"].get("per_mode") for x in entries[:2]] == ["Per100Possessions", "Totals"]
        assert [x["identity"]["parameters"]["team_id"] for x in entries[2:12:2]] == list(e.engine.CANARY_TEAM_IDS)
        assert all(x["cache_path"].startswith(f"phase2e/{spec.target_season}/") for x in entries)


@pytest.mark.parametrize("field", ["asset_id", "identity", "relative_path", "metadata_relative_path"])
def test_collisions_rejected_before_transport(stores, field):
    first, second = stores[0].expected["assets"][0], stores[1].expected["assets"][0]
    if field.endswith("path"):
        second["cache"][field] = first["cache"][field]
    else:
        second[field] = copy.deepcopy(first[field])
    with pytest.raises(ValueError):
        e.preview(stores)


def test_protected_and_unlisted_specs_rejected():
    with pytest.raises(ValueError):
        e.create_stores(REAL_CACHE, (replace(e.SPECS[0], target_season="2025-26", prior_feature_season="2024-25"),))
    with pytest.raises(ValueError):
        replace(e.SPECS[0], prior_feature_season="2018-19")
    with pytest.raises(ValueError):
        e.create_stores(REAL_CACHE, e.SPECS[::-1])


def test_automatic_canary_and_season_continuation_and_resume(stores):
    calls = []
    def transport(identity, timeout):
        season = identity["target_season"]
        store = next(s for s in stores if s.spec.target_season == season)
        calls.append(season)
        if len(calls) == 13:
            assert store.load()["canary_result"]["status"] == "passed"
        if len(calls) == 63:
            assert e.checkpoint_path(stores[0]).exists()
            return e.engine.TransportResult(403, b"stop", .1, {})
        return _response(store.expected, identity)
    result = e.acquire(stores, live_acquisition=True, transport=transport, sleep_fn=lambda _: None)
    assert result["completed"] == ["2020-21"]
    assert len(calls) == 63 and result["stopped_season"] == "2019-20"
    hashes = e.evidence_hashes(stores[0])
    checkpoint = e.checkpoint_path(stores[0]).read_bytes()
    again = e.acquire(stores, live_acquisition=True, transport=lambda *_: pytest.fail("repeated transport"), sleep_fn=lambda _: None)
    assert again["stopped_season"] == "2019-20"
    assert e.evidence_hashes(stores[0]) == hashes
    assert e.checkpoint_path(stores[0]).read_bytes() == checkpoint
    assert all(e.accounting(s)["attempted"] == 0 for s in stores[2:])
    assert e.analyze(stores) == e.analyze(stores)
    changed = json.loads(checkpoint)
    changed["analysis_sha256"] = "corrupt"
    e.checkpoint_path(stores[0]).write_text(json.dumps(changed))
    stopped = e.acquire(stores, live_acquisition=True, transport=lambda *_: pytest.fail("transport after corruption"))
    assert stopped["stopped_season"] == "2020-21"
    assert "checkpoint mismatch" in stopped["stop"]["detail"]


def test_resume_within_season_environment_pause_consumes_no_attempt(stores):
    calls = []
    def transport(identity, timeout):
        calls.append(identity)
        return _response(stores[0].expected, identity)
    def interrupted_sleep(_):
        raise KeyboardInterrupt("environment pause before next attempt")
    with pytest.raises(KeyboardInterrupt):
        e.acquire(stores, live_acquisition=True, transport=transport, sleep_fn=interrupted_sleep)
    assert len(calls) == 1
    assert e.accounting(stores[0])["attempted"] == 1
    result = e.acquire(stores, live_acquisition=True, transport=lambda *_: e.engine.TransportResult(403, b"stop", .1, {}), sleep_fn=lambda _: None)
    assert result["accounting"]["next_asset"]["ordinal"] == 2
    assert len(stores[0].load()["assets"][0]["attempt_history"]) == 1


def test_retry_budget_not_borrowed(stores):
    calls, waits = [], []
    def transport(identity, timeout):
        calls.append(identity)
        if len(calls) <= 12:
            if len(calls) % 2:
                return e.engine.TransportResult(503, b"retry", .1, {"Retry-After": "45"})
            return _response(stores[0].expected, identity)
        return e.engine.TransportResult(503, b"exhausted", .1, {})
    result = e.acquire(stores, live_acquisition=True, transport=transport, sleep_fn=waits.append)
    assert len(calls) == 13 and waits.count(45.0) == 6
    assert result["accounting"]["retried"] == 6
    assert result["accounting"]["remaining"]["retries"] == 0
    assert all(e.accounting(s)["remaining"]["retries"] == 6 for s in stores[1:])


def test_schema_quarantine_stops_all_later_seasons(stores):
    def transport(identity, timeout):
        response = _response(stores[0].expected, identity)
        payload = json.loads(response.body)
        result = payload["resultSets"][0]
        result["headers"].append("CHANGED")
        for row in result["rowSet"]:
            row.append(0)
        return e.engine.TransportResult(200, json.dumps(payload).encode(), .1, {})
    result = e.acquire(stores, live_acquisition=True, transport=transport, sleep_fn=lambda _: None)
    assert result["stop"]["stop_category"] == "schema_quarantine"
    assert result["accounting"]["quarantined"] == 1
    assert result["accounting"]["attempted"] == 1
    assert all(e.accounting(s)["attempted"] == 0 for s in stores[1:])
    assert stores[0].load()["assets"][0]["attempt_history"][0]["request_kind"] == e.SPECS[0].request_kind


def test_summary_deterministic_preserves_observations():
    analyses = {season: {"combined": {"matched_observation_keys": 3}, "prior_history": {"combined": {}}, "asset_ledger": []}
                for season in ("2019-20", "2020-21")}
    pairs = {season: [("1", "2"), ("1", "2"), ("2", "3")] for season in analyses}
    result = e.summarize(analyses, pairs)
    assert result == e.summarize(dict(reversed(list(analyses.items()))), pairs)
    assert result["total_pair_season_team_observations"] == 6
    assert result["unique_players"] == 3 and result["unique_unordered_pairs"] == 2
    assert len(result["pairs_in_multiple_seasons"]) == 2
    assert all(x["pandemic_era"] for x in result["seasons"].values())


def test_all_seven_automatic_coordinator_boundaries(stores, monkeypatch):
    calls = []
    def run(store, **kwargs):
        calls.append(("acquire", store.spec.target_season))
        return {"completed": True}
    def certify(store, **kwargs):
        calls.append(("certify", store.spec.target_season))
    monkeypatch.setattr(e.engine, "run_acquisition", run)
    monkeypatch.setattr(e, "certify", certify)
    result = e.acquire(stores, live_acquisition=True, sleep_fn=lambda _: None)
    assert result["completed"] == [s.target_season for s in e.SPECS]
    assert calls == [(op, s.target_season) for s in e.SPECS for op in ("acquire", "certify")]


def test_uncertain_transport_stops_before_next_asset(stores):
    def interrupted(*_):
        raise KeyboardInterrupt("transport outcome unknown")
    with pytest.raises(KeyboardInterrupt):
        e.acquire(stores, live_acquisition=True, transport=interrupted)
    result = e.acquire(stores, live_acquisition=True, transport=lambda *_: pytest.fail("uncertain attempt repeated"))
    assert result["stop"]["stop_category"] == "uncertain_interrupted_attempt"
    assert e.accounting(stores[0])["attempted"] == 1
    assert all(e.accounting(s)["attempted"] == 0 for s in stores[1:])


@pytest.fixture
def interrupted_cleveland(stores, monkeypatch):
    calls = []
    def transport(identity, timeout):
        calls.append(identity)
        if len(calls) == 16:
            raise KeyboardInterrupt("unknown transport outcome")
        return _response(stores[0].expected, identity)
    with pytest.raises(KeyboardInterrupt):
        e.acquire(stores, live_acquisition=True, transport=transport, sleep_fn=lambda _: None)
    assert stores[0].load()["assets"][15]["asset_id"] == e.RECOVERY_ASSET
    monkeypatch.setattr(e, "RECOVERY_ANCHOR", {k: e.evidence_hashes(stores[0])[k] for k in ("manifest", "ledger")})
    return stores


@pytest.mark.parametrize("status", [200, 403, 503])
def test_exact_recovery_preserves_attempt_and_budget(interrupted_cleveland, status):
    stores = interrupted_cleveland
    original = stores[0].load()
    original_bytes = stores[0].path.read_bytes()
    e.prepare_recovery(stores)
    assert (e.recovery_path(stores[0]) / "2020-21/manifest.json").read_bytes() == original_bytes
    assert e.prepare_recovery(stores)["recovery"] == "already_prepared_or_consumed"
    calls, waits = [], []
    def transport(identity, timeout):
        calls.append(identity)
        assert identity == original["assets"][15]["identity"]
        return _response(stores[0].expected, identity) if status == 200 else e.engine.TransportResult(status, b"failure", .1, {})
    def sleep(seconds):
        waits.append(seconds)
        if seconds == 1:
            raise KeyboardInterrupt("pause before asset 17")
    if status == 200:
        with pytest.raises(KeyboardInterrupt):
            e.acquire(stores, live_acquisition=True, transport=transport, sleep_fn=sleep)
    else:
        result = e.acquire(stores, live_acquisition=True, transport=transport, sleep_fn=sleep)
        assert not result["completed"]
    current = stores[0].load()
    assert len(calls) == 1 and waits[0] >= 30
    assert current["assets"][:15] == original["assets"][:15]
    asset = current["assets"][15]
    assert asset["attempt_history"][0] == original["assets"][15]["attempt_history"][0]
    assert asset["attempt_history"][1]["attempt_number"] == 2
    assert asset["status"] == ("verified" if status == 200 else "failed")
    assert e.accounting(stores[0])["remaining"] == {"first_attempts":46,"retries":5,"total_attempts":51}
    assert all(e.accounting(s)["attempted"] == 0 for s in stores[1:])
    e.audit_recovery(stores[0])
    if status != 200:
        e.prepare_recovery(stores)
        e.acquire(stores, live_acquisition=True, transport=lambda *_: pytest.fail("third attempt"))


def test_recovery_rejects_changed_anchor(interrupted_cleveland):
    stores = interrupted_cleveland
    stores[0].path.write_bytes(stores[0].path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="anchor"):
        e.prepare_recovery(stores)
    assert not e.recovery_path(stores[0]).exists()
