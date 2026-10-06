import json
from copy import deepcopy
from pathlib import Path

import pytest

from pair_fit_v2 import phase3e_r1_philadelphia as phase
from pair_fit_v2.phase3a_population_audit import network_prohibited


ROOT = Path(__file__).resolve().parents[1]
REAL_CACHE = ROOT / "cache"


def test_policy_and_authorization_are_fixed_and_bounded(tmp_path):
    policy = phase.verify_policy(ROOT)
    authorization, record = phase.ensure_authorization(tmp_path, ROOT)
    assert policy["serialized_byte_sha256"] == phase.POLICY_SHA256
    assert len(authorization["assets"]) == 4
    assert [asset["measure"] for asset in authorization["assets"]] == ["Base", "Advanced", "Base", "Advanced"]
    assert {asset["identity"]["parameters"]["team_id"] for asset in authorization["assets"]} == {"1610612755"}
    assert authorization["transport"] == {
        "sequential": True,
        "timeout_seconds": 30,
        "minimum_seconds_between_transport_attempts": 1.0,
        "automatic_retries": 0,
        "trust_env": False,
        "allow_redirects": False,
    }
    before = (tmp_path / record["relative_path"]).read_bytes()
    phase.ensure_authorization(tmp_path, ROOT)
    assert (tmp_path / record["relative_path"]).read_bytes() == before


def test_protected_path_rejected_before_access(tmp_path):
    with pytest.raises(ValueError, match="protected-season path rejected before access"):
        phase._read_bytes(tmp_path / "2025-26" / "anything.json")


def test_exact_250_window_is_warning_not_automatic_validation_failure(monkeypatch):
    asset = phase.authorized_assets()[0]
    called = {}
    payload = {"parameters": {"DateFrom": "10/22/2024", "DateTo": "01/31/2025"}}

    def accepted(value, identity, schema):
        called["identity"] = identity
        return {"row_counts": {"Lineups": 250}}

    monkeypatch.setattr(phase, "validate_diagnostic_payload", accepted)
    result = phase.validate_payload(payload, asset["identity"], {})
    assert result["row_counts"]["Lineups"] == 250
    assert called["identity"]["parameters"]["team_id"] == "1610612755"


def test_direct_transport_enforces_headers_no_proxy_no_retry_and_no_redirect(monkeypatch):
    calls = {}

    class Response:
        status_code = 200
        content = b"{}"

    class Session:
        def __init__(self):
            self.trust_env = True
            self.headers = {}

        def mount(self, prefix, adapter):
            calls["mount"] = (prefix, adapter.max_retries.total)

        def get(self, url, **kwargs):
            calls["trust_env"] = self.trust_env
            calls["headers"] = dict(self.headers)
            calls["url"] = url
            calls["kwargs"] = kwargs
            return Response()

        def close(self):
            calls["closed"] = True

    monkeypatch.setattr(phase.requests, "Session", Session)
    result = phase.direct_transport(phase.authorized_assets()[0]["identity"])
    assert result.status_code == 200
    assert calls["trust_env"] is False
    assert calls["headers"] == phase.RESEARCH_HEADERS
    assert calls["mount"] == ("https://", 0)
    assert calls["url"] == phase.TEAM_DASH_LINEUPS_URL
    assert calls["kwargs"]["timeout"] == 30
    assert calls["kwargs"]["allow_redirects"] is False
    assert calls["closed"] is True


def test_failed_body_is_quarantined_and_no_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(phase, "verify_policy", lambda root: {"relative_path": "policy", "serialized_byte_sha256": "x", "byte_count": 1, "fixed_before_philadelphia_response_access": True})
    monkeypatch.setattr(phase, "load_context", lambda root: {"schemas": {"Base": {}, "Advanced": {}}, "legacy": {asset["source_phase1e_asset_id"]: {**asset, "asset_id": asset["source_phase1e_asset_id"], "identity": asset["identity"], "status": "planned", "attempt_count": 0, "cache": asset["legacy_paths"]} for asset in phase.authorized_assets()}, "full": {}})
    calls = []

    def transport(identity, timeout):
        calls.append((deepcopy(identity), timeout))
        return phase.TransportResult(503, b"upstream unavailable", 0.1)

    result = phase.acquire(tmp_path, tmp_path, live=True, transport=transport, sleeper=lambda seconds: None)
    assert result["primary_classification"] == phase.PRIMARY_CLASSIFICATIONS[2]
    assert len(calls) == 1
    asset = phase.authorized_assets()[0]
    paths = phase._path_map(tmp_path, asset)
    assert paths["quarantine_body"].read_bytes() == b"upstream unavailable"
    with pytest.raises(FileExistsError):
        phase._write_json_new(paths["started"], {})


def test_uncertain_started_attempt_blocks_repeat(tmp_path, monkeypatch):
    monkeypatch.setattr(phase, "verify_policy", lambda root: {"relative_path": "policy", "serialized_byte_sha256": "x", "byte_count": 1, "fixed_before_philadelphia_response_access": True})
    context = {"schemas": {"Base": {}, "Advanced": {}}, "legacy": {asset["source_phase1e_asset_id"]: {**asset, "asset_id": asset["source_phase1e_asset_id"], "identity": asset["identity"], "status": "planned", "attempt_count": 0, "cache": asset["legacy_paths"]} for asset in phase.authorized_assets()}, "full": {}}
    monkeypatch.setattr(phase, "load_context", lambda root: context)
    asset = phase.authorized_assets()[0]
    paths = phase._path_map(tmp_path, asset)
    phase.ensure_authorization(tmp_path, tmp_path)
    phase._write_json_new(paths["started"], {"identity": asset["identity"]})
    calls = []
    result = phase.acquire(tmp_path, tmp_path, live=True, transport=lambda *args: calls.append(args))
    assert result["primary_classification"] == phase.PRIMARY_CLASSIFICATIONS[2]
    assert "Incomplete prior attempt" in result["classification_detail"]
    assert calls == []


def test_real_context_reads_only_philadelphia_full_season_and_planned_windows():
    context = phase.load_context(REAL_CACHE)
    assert set(context["full"]) == {"Base", "Advanced"}
    assert {item["replay"]["row_counts"]["Lineups"] for item in context["full"].values()} == {250}
    assert len(context["legacy"]) == 4
    assert all(asset["status"] == "planned" and asset["attempt_count"] == 0 for asset in context["legacy"].values())


def test_real_cache_replay_is_deterministic_network_free_and_nonmutating():
    protected = [
        REAL_CACHE / phase.PHASE1C_MANIFEST,
        REAL_CACHE / phase.PHASE1E_LEDGER,
    ]
    before = {path: path.read_bytes() for path in protected}
    with network_prohibited():
        first = phase.acquire(REAL_CACHE, ROOT, live=False)
        second = phase.acquire(REAL_CACHE, ROOT, live=False)
    assert first == second
    assert first["primary_classification"] == phase.PRIMARY_CLASSIFICATIONS[0]
    assert first["population_reconciliation"]["window_union_key_count"] == 271
    assert first["population_reconciliation"]["recovered_only_key_count"] == 21
    assert first["population_reconciliation"]["recovered_only_pairs_potentially_meeting_poss_150"] == 0
    assert {path: path.read_bytes() for path in protected} == before
    assert json.loads((ROOT / "modeling/phase3e-r1/philadelphia_evidence.json").read_text()) == first


def test_sequential_fixture_replay_waits_between_each_transport_attempt(tmp_path, monkeypatch):
    real_context = phase.load_context(REAL_CACHE)
    bodies = {
        asset["source_phase1e_asset_id"]: (
            REAL_CACHE / asset["paths"]["verified_body"]
        ).read_bytes()
        for asset in phase.authorized_assets()
    }
    monkeypatch.setattr(phase, "load_context", lambda root: real_context)
    calls = []
    sleeps = []

    def transport(identity, timeout):
        asset = next(item for item in phase.authorized_assets() if item["identity"] == identity)
        calls.append((asset["window"], asset["measure"], timeout))
        return phase.TransportResult(200, bodies[asset["source_phase1e_asset_id"]], 0.1)

    result = phase.acquire(
        tmp_path,
        ROOT,
        live=True,
        transport=transport,
        sleeper=sleeps.append,
    )
    assert calls == [
        ("early", "Base", 30),
        ("early", "Advanced", 30),
        ("late", "Base", 30),
        ("late", "Advanced", 30),
    ]
    assert sleeps == [1.0, 1.0, 1.0]
    assert result["primary_classification"] == phase.PRIMARY_CLASSIFICATIONS[0]


def test_result_writer_is_immutable_and_deterministic(tmp_path):
    result = {"completed": False, "primary_classification": phase.PRIMARY_CLASSIFICATIONS[2]}
    first = phase.write_result(tmp_path, result)
    before = first.read_bytes()
    assert phase.write_result(tmp_path, result).read_bytes() == before
    with pytest.raises(FileExistsError):
        phase.write_result(tmp_path, {**result, "changed": True})
