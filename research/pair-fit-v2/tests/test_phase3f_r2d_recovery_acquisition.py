from __future__ import annotations

import ast
import copy
import json
import os
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2 import phase3f_r2d_recovery_acquisition as r2d
from pair_fit_v2.phase3f_r2b_1_response_contract import SCHEMAS


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.content = body
        self.status_code = status
        self.is_redirect = 300 <= status < 400
        self.is_permanent_redirect = status in {301, 308}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        self.closed = True


class Clock:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


def frozen_requests():
    return r2d.validate_frozen_requests(r2d.load_corrected_plan(PROJECT_ROOT))


def response_body(request, pairs=((101, 202, 10.0),), *, reverse_sets=False):
    measure = request["measure"]
    overall_headers = list(SCHEMAS[measure]["Overall"])
    overall = [0] * len(overall_headers)
    overall[overall_headers.index("GROUP_SET")] = "Overall"
    overall[overall_headers.index("GROUP_VALUE")] = "2025-26"
    overall[overall_headers.index("TEAM_ID")] = int(request["team_id"])
    lineup_headers = list(SCHEMAS[measure]["Lineups"])
    rows = []
    for left, right, possessions in pairs:
        row = [0] * len(lineup_headers)
        row[lineup_headers.index("GROUP_SET")] = "Lineups"
        row[lineup_headers.index("GROUP_ID")] = f"-{left}-{right}-"
        row[lineup_headers.index("GROUP_NAME")] = f"{left} - {right}"
        row[lineup_headers.index("MIN")] = 1.0
        row[lineup_headers.index("SUM_TIME_PLAYED")] = 60.0
        if measure == "Advanced":
            row[lineup_headers.index("POSS")] = possessions
            row[lineup_headers.index("NET_RATING")] = 0.0
        rows.append(row)
    result_sets = [
        {"name": "Overall", "headers": overall_headers, "rowSet": [overall]},
        {"name": "Lineups", "headers": lineup_headers, "rowSet": rows},
    ]
    if reverse_sets:
        result_sets.reverse()
    payload = {
        "resource": "teamdashlineups",
        "parameters": dict(request["parameters"]),
        "resultSets": result_sets,
    }
    return json.dumps(payload, separators=(",", ":")).encode()


def acquire_valid(tmp_path, request, frozen, pairs=((101, 202, 10.0),), *, previous=None):
    session = FakeSession([FakeResponse(response_body(request, pairs))])
    values = [10.0, 10.0, 10.2] if previous is None else [previous + 1.1, previous + 1.1, previous + 1.3]
    result = r2d.acquire_one(
        request, frozen, tmp_path, session, previous_completion=previous,
        sleeper=lambda _: None, monotonic=Clock(values),
    )
    return result, session


def fake_full(team_id, keys):
    result = {}
    for measure in ("Base", "Advanced"):
        spec = dict(r2d.FULL_SEASON_SPECS[(team_id, measure)])
        result[(team_id, measure)] = {
            **spec, "path": f"historical/{team_id}-{measure}.bin", "state": "completed_verified",
            "row_count": len(keys), "keys": set(keys), "diagnostics": {},
        }
    return result


def test_frozen_inventory_is_exactly_eight_in_required_order():
    requests_value = frozen_requests()
    assert [(item["ordinal"], item["team_id"], item["window"]["name"], item["measure"]) for item in requests_value] == [
        (1, "1610612754", "early", "Base"),
        (2, "1610612754", "early", "Advanced"),
        (3, "1610612754", "late", "Base"),
        (4, "1610612754", "late", "Advanced"),
        (5, "1610612763", "early", "Base"),
        (6, "1610612763", "early", "Advanced"),
        (7, "1610612763", "late", "Base"),
        (8, "1610612763", "late", "Advanced"),
    ]


def test_ninth_request_is_rejected():
    plan = copy.deepcopy(r2d.load_corrected_plan(PROJECT_ROOT))
    ninth = copy.deepcopy(plan["future_recovery_identities"][-1])
    ninth["ordinal"] = 9
    plan["future_recovery_identities"].append(ninth)
    with pytest.raises(r2d.RecoveryError, match="exactly eight"):
        r2d.validate_frozen_requests(plan)


def test_each_identity_is_byte_for_byte_equal_to_r2c1_and_hashes_itself():
    raw = r2d.load_corrected_plan(PROJECT_ROOT)["future_recovery_identities"]
    frozen = frozen_requests()
    assert frozen == raw
    assert all(item["canonical_request_identity_sha256"] == r2d.identity_sha256(item) for item in frozen)


def test_frozen_inputs_and_historical_namespaces_authenticate_without_network():
    result = r2d.authenticate_frozen_inputs(PROJECT_ROOT)
    assert len(result["requests"]) == 8
    assert len(result["preservation_fingerprints"]) == 9
    assert result["contracts"]["response_contract"]["identity"] == r2d.CONTRACT_IDENTITY


def test_only_four_authorized_full_season_bodies_parse_and_authenticate():
    result = r2d.authenticate_full_season_bodies(PROJECT_ROOT)
    assert set(result) == set(r2d.FULL_SEASON_SPECS)
    assert all(item["row_count"] == 250 for item in result.values())
    assert all(len(item["keys"]) == 250 for item in result.values())
    assert {item["raw_sha256"] for item in result.values()} == {
        item["raw_sha256"] for item in r2d.FULL_SEASON_SPECS.values()
    }


def test_authorization_pins_source_cli_namespaces_and_prohibitions():
    authorization = r2d.build_authorization(PROJECT_ROOT)
    assert authorization["implementation_source"]["sha256"] == r2d._fingerprint(PROJECT_ROOT / r2d.SOURCE_PATH)["sha256"]
    assert authorization["cli_source"]["sha256"] == r2d._fingerprint(PROJECT_ROOT / r2d.CLI_PATH)["sha256"]
    assert authorization["authorized_request_count"] == 8
    assert authorization["output_namespaces"] == {
        "protected_recovery": str((PROJECT_ROOT / r2d.EVIDENCE_NAMESPACE).resolve()),
        "reconciliation": str((PROJECT_ROOT / r2d.PLANNING_NAMESPACE).resolve()),
    }
    assert authorization["scope"] == {
        "population_reconciliation_only": True,
        "rating_aggregation_authorized": False,
        "target_reconstruction_authorized": False,
        "final_test_construction_authorized": False,
        "prior_profile_join_authorized": False,
        "preprocessing_authorized": False,
        "estimator_or_prediction_authorized": False,
    }


def test_source_and_cli_hash_binding_fail_closed(monkeypatch):
    authorization = r2d.build_authorization(PROJECT_ROOT)
    authorization["implementation_source"]["sha256"] = "0" * 64
    monkeypatch.setenv("PYTHONPATH", "src")
    monkeypatch.chdir(PROJECT_ROOT)
    with pytest.raises(r2d.RecoveryError, match="executing hash"):
        r2d.validate_authorization(
            authorization, PROJECT_ROOT,
            PROJECT_ROOT / r2d.EVIDENCE_NAMESPACE, PROJECT_ROOT / r2d.PLANNING_NAMESPACE,
        )


def test_exact_namespace_binding_rejects_alias(monkeypatch):
    authorization = r2d.build_authorization(PROJECT_ROOT)
    monkeypatch.setenv("PYTHONPATH", "src")
    monkeypatch.chdir(PROJECT_ROOT)
    with pytest.raises(r2d.RecoveryError, match="namespace"):
        r2d.validate_authorization(
            authorization, PROJECT_ROOT, PROJECT_ROOT / "cache/other", PROJECT_ROOT / r2d.PLANNING_NAMESPACE
        )


def test_session_has_zero_retries_trust_env_false_and_research_headers():
    session = r2d.create_session()
    try:
        assert session.trust_env is False
        assert session.get_adapter("https://").max_retries.total == 0
        assert session.get_adapter("https://").max_retries.redirect == 0
        for key, value in r2d.RESEARCH_HEADERS.items():
            assert session.headers[key] == value
    finally:
        session.close()


def test_successful_attempt_is_one_request_no_redirect_timeout_30(tmp_path):
    frozen = frozen_requests()
    result, session = acquire_valid(tmp_path, frozen[0], frozen)
    assert result["action"] == "acquired"
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == r2d.URL
    assert kwargs["timeout"] == 30
    assert kwargs["allow_redirects"] is False
    assert kwargs["params"] == frozen[0]["parameters"]
    assert r2d.classify_request_state(tmp_path, frozen[0], frozen) == "completed_verified"


def test_monotonic_pacing_is_persisted_at_or_above_one_second(tmp_path):
    frozen = frozen_requests()
    session = FakeSession([FakeResponse(response_body(frozen[0])), FakeResponse(response_body(frozen[1]))])
    sleeps = []
    first = r2d.acquire_one(
        frozen[0], frozen, tmp_path, session, previous_completion=None,
        sleeper=sleeps.append, monotonic=Clock([1.0, 1.0, 1.2]),
    )
    second = r2d.acquire_one(
        frozen[1], frozen, tmp_path, session,
        previous_completion=first["outcome"]["process_monotonic_completion"],
        sleeper=sleeps.append, monotonic=Clock([1.3, 2.2, 2.4]),
    )
    start = r2d._read_json(r2d.request_paths(tmp_path, frozen[1])["start"])
    assert sleeps == pytest.approx([0.9])
    assert start["observed_post_sleep_monotonic_gap_seconds"] == pytest.approx(1.0)
    assert second["outcome"]["state"] == "completed_verified"


def test_pacing_failure_stops_before_attempt_or_transport(tmp_path):
    frozen = frozen_requests()
    session = FakeSession([FakeResponse(response_body(frozen[0]))])
    with pytest.raises(r2d.RecoveryError, match="pacing"):
        r2d.acquire_one(
            frozen[0], frozen, tmp_path, session, previous_completion=1.0,
            sleeper=lambda _: None, monotonic=Clock([1.1, 1.2]),
        )
    assert session.calls == []
    assert r2d.classify_request_state(tmp_path, frozen[0], frozen) == "not_started"


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirect_is_quarantined_and_never_followed(tmp_path, status):
    frozen = frozen_requests()
    session = FakeSession([FakeResponse(b"redirect", status)])
    with pytest.raises(r2d.RecoveryError, match="redirect"):
        r2d.acquire_one(
            frozen[0], frozen, tmp_path, session, previous_completion=None,
            sleeper=lambda _: None, monotonic=Clock([1.0, 1.0, 1.1]),
        )
    assert session.calls[0][1]["allow_redirects"] is False
    assert r2d.classify_request_state(tmp_path, frozen[0], frozen) == "failed_or_quarantined"


def test_timeout_is_single_attempt_quarantined_and_no_retry(tmp_path):
    frozen = frozen_requests()
    session = FakeSession([requests.Timeout("synthetic")])
    with pytest.raises(r2d.RecoveryError, match="Timeout"):
        r2d.acquire_one(
            frozen[0], frozen, tmp_path, session, previous_completion=None,
            sleeper=lambda _: None, monotonic=Clock([1.0, 1.0, 1.2]),
        )
    assert len(session.calls) == 1
    assert r2d.classify_request_state(tmp_path, frozen[0], frozen) == "failed_or_quarantined"


def test_failure_means_caller_cannot_start_next_when_fail_stop_loop_breaks(tmp_path):
    frozen = frozen_requests()
    session = FakeSession([FakeResponse(b"bad", 500), FakeResponse(response_body(frozen[1]))])
    attempted = []
    with pytest.raises(r2d.RecoveryError):
        for request in frozen[:2]:
            attempted.append(request["ordinal"])
            r2d.acquire_one(
                request, frozen, tmp_path, session, previous_completion=None,
                sleeper=lambda _: None, monotonic=Clock([1.0, 1.0, 1.2]),
            )
    assert attempted == [1]
    assert len(session.calls) == 1


def test_all_five_restart_states(tmp_path):
    frozen = frozen_requests()
    assert r2d.classify_request_state(tmp_path, frozen[0], frozen) == "not_started"
    paths = r2d.request_paths(tmp_path, frozen[0])
    start = {
        "request_id": frozen[0]["request_id"], "ordinal": 1,
        "canonical_request_identity_sha256": r2d.identity_sha256(frozen[0]), "attempt_number": 1,
    }
    r2d._write_once(paths["start"], r2d.serialize_json(start))
    assert r2d.classify_request_state(tmp_path, frozen[0], frozen) == "started_without_outcome"
    paths["outcome"].write_bytes(b"{}")
    assert r2d.classify_request_state(tmp_path, frozen[0], frozen) == "conflicting_state"

    completed = tmp_path / "completed"
    acquire_valid(completed, frozen[1], frozen)
    assert r2d.classify_request_state(completed, frozen[1], frozen) == "completed_verified"
    failed = tmp_path / "failed"
    session = FakeSession([requests.Timeout()])
    with pytest.raises(r2d.RecoveryError):
        r2d.acquire_one(
            frozen[2], frozen, failed, session, previous_completion=None,
            sleeper=lambda _: None, monotonic=Clock([1.0, 1.0, 1.1]),
        )
    assert r2d.classify_request_state(failed, frozen[2], frozen) == "failed_or_quarantined"


def test_partial_or_unknown_record_is_conflicting(tmp_path):
    frozen = frozen_requests()
    directory = r2d.request_paths(tmp_path, frozen[0])["start"].parent
    directory.mkdir(parents=True)
    (directory / "unknown.txt").write_text("x", encoding="utf-8")
    assert r2d.classify_request_state(tmp_path, frozen[0], frozen) == "conflicting_state"


def test_overall_then_lineups_order_and_measure_schemas():
    frozen = frozen_requests()
    for request in (frozen[0], frozen[1]):
        result = r2d.verify_response_bytes(response_body(request), request, frozen)
        assert result["observed_result_set_order"] == ["Overall", "Lineups"]
        assert result["structurally_valid"] is True
    with pytest.raises(r2d.ResponseError, match="contract"):
        r2d.verify_response_bytes(response_body(frozen[0], reverse_sets=True), frozen[0], frozen)


@pytest.mark.parametrize(
    "pairs,pattern",
    [
        (((101, 202, 1.0), (202, 101, 2.0)), "duplicate"),
        (((101, 101, 1.0),), "same-player"),
        (((0, 202, 1.0),), "malformed"),
    ],
)
def test_malformed_duplicate_and_same_player_pairs_are_rejected(pairs, pattern):
    frozen = frozen_requests()
    with pytest.raises(r2d.ResponseError, match="contract"):
        r2d.verify_response_bytes(response_body(frozen[1], pairs), frozen[1], frozen)


def test_numeric_pair_order_and_zero_possession_are_preserved():
    frozen = frozen_requests()
    result = r2d.verify_response_bytes(
        response_body(frozen[1], ((20, 3, 0.0),)), frozen[1], frozen
    )
    assert result["canonical_pair_keys"] == [["3", "20"]]
    assert result["zero_possession_pair_keys"] == [["3", "20"]]
    assert result["possession_by_pair_key"] == {"3-20": 0.0}


def test_window_at_exactly_250_is_valid_response_but_unresolved_disposition():
    frozen = frozen_requests()
    pairs = tuple((index + 1, index + 1001, 1.0) for index in range(250))
    result = r2d.verify_response_bytes(response_body(frozen[1], pairs), frozen[1], frozen)
    assert result["exact_250"] is True
    record = {
        "full_season_evidence_authenticated": True,
        "all_four_recovery_responses_present": True,
        "all_four_recovery_responses_authenticated": True,
        "all_four_recovery_responses_structurally_valid": True,
        "complete_complementary_date_coverage": True,
        "every_individual_window_below_250": False,
        "early_base_advanced_keys_equal": True, "late_base_advanced_keys_equal": True,
        "window_union_equals_full_season_keys": True, "recovered_only_keys_validated": True,
        "conflicting_state": False, "failed_or_quarantined": False,
        "early_base_pair_row_count": 250, "early_advanced_pair_row_count": 250,
        "late_base_pair_row_count": 1, "late_advanced_pair_row_count": 1,
        "recovered_only_count": 0, "full_season_only_count": 0,
        "duplicate_count": 0, "malformed_pair_count": 0, "same_player_count": 0,
        "base_only_count": 0, "advanced_only_count": 0,
    }
    assert r2d.evaluate_disposition(record).disposition == "recovery_unresolved"


def prepare_eight(evidence_root, per_request_pairs=None):
    frozen = frozen_requests()
    per_request_pairs = per_request_pairs or {item["ordinal"]: ((101, 202, 10.0),) for item in frozen}
    previous = None
    for request in frozen:
        result, _ = acquire_valid(
            evidence_root, request, frozen, per_request_pairs[request["ordinal"]], previous=previous
        )
        previous = result["outcome"]["process_monotonic_completion"]
    return frozen


def test_reconciliation_operational_and_no_rating_or_target_work(tmp_path, monkeypatch):
    frozen = prepare_eight(tmp_path)
    keys = {("101", "202")}
    full = {**fake_full("1610612754", keys), **fake_full("1610612763", keys)}
    monkeypatch.setattr(r2d, "authenticate_full_season_bodies", lambda _: full)
    result = r2d.reconcile_populations(PROJECT_ROOT, tmp_path, frozen, frozen)
    assert {item["disposition"] for item in result["team_dispositions"]} == {
        "operationally_resolved_no_observed_omission"
    }
    assert all(item["rating_aggregation_performed"] is False for item in result["team_reconciliation"])
    assert all(item["target_reconstruction_performed"] is False for item in result["team_reconciliation"])


def test_recovered_only_proves_non_exhaustive_and_exposure_is_diagnostic_only(tmp_path, monkeypatch):
    pairs = {ordinal: ((101, 202, 75.0), (303, 404, 75.0)) for ordinal in range(1, 9)}
    frozen = prepare_eight(tmp_path, pairs)
    full_keys = {("101", "202")}
    full = {**fake_full("1610612754", full_keys), **fake_full("1610612763", full_keys)}
    monkeypatch.setattr(r2d, "authenticate_full_season_bodies", lambda _: full)
    result = r2d.reconcile_populations(PROJECT_ROOT, tmp_path, frozen, frozen)
    for disposition, reconciliation in zip(result["team_dispositions"], result["team_reconciliation"]):
        assert disposition["disposition"] == "proven_non_exhaustive"
        assert reconciliation["recovered_only_keys"] == [["303", "404"]]
        diagnostic = reconciliation["exposure_diagnostics"][0]
        assert diagnostic["summed_possessions"] == 150.0
        assert diagnostic["meets_poss_ge_150"] is True


def test_full_season_only_and_base_advanced_mismatch_are_unresolved(tmp_path, monkeypatch):
    pairs = {ordinal: ((101, 202, 10.0),) for ordinal in range(1, 9)}
    pairs[2] = ((101, 202, 10.0), (303, 404, 1.0))
    frozen = prepare_eight(tmp_path, pairs)
    full_keys = {("101", "202"), ("505", "606")}
    full = {**fake_full("1610612754", full_keys), **fake_full("1610612763", full_keys)}
    monkeypatch.setattr(r2d, "authenticate_full_season_bodies", lambda _: full)
    result = r2d.reconcile_populations(PROJECT_ROOT, tmp_path, frozen, frozen)
    assert all(item["disposition"] == "recovery_unresolved" for item in result["team_dispositions"])
    assert result["team_dispositions"][0]["schema_record"]["advanced_only_count"] == 1
    assert all(item["schema_record"]["full_season_only_count"] == 1 for item in result["team_dispositions"])


def test_failure_closed_schema_uses_exact_r2c1_classifier():
    decision = r2d.evaluate_disposition({"recovered_only_count": 1})
    assert decision.disposition == "recovery_unresolved"
    assert "missing_field:full_season_evidence_authenticated" in decision.reason_codes


def test_completed_state_is_deterministic_cache_only_and_makes_no_request(tmp_path):
    frozen = frozen_requests()
    acquire_valid(tmp_path, frozen[0], frozen)
    session = FakeSession([AssertionError("transport must not occur")])
    result = r2d.acquire_one(
        frozen[0], frozen, tmp_path, session, previous_completion=None,
        sleeper=lambda _: None, monotonic=Clock([]),
    )
    assert result["action"] == "skipped_completed_verified"
    assert session.calls == []


def minimal_authorization():
    return {
        "implementation_source": {"path": r2d.SOURCE_PATH.as_posix(), "bytes": 1, "sha256": "x"},
        "cli_source": {"path": r2d.CLI_PATH.as_posix(), "bytes": 1, "sha256": "y"},
        "official_command_argv": ["synthetic"],
        "historical_namespace_fingerprints_before": [],
        "historical_git_visible_fingerprints": [],
    }


def test_synthetic_official_flow_is_sequential_exact_eight_and_writes_manifest(tmp_path, monkeypatch):
    frozen = frozen_requests()
    planning = tmp_path / "planning"
    evidence = tmp_path / "evidence"
    planning.mkdir()
    authorization_path = planning / "recovery_authorization.json"
    authorization_path.write_bytes(r2d.serialize_json(minimal_authorization()))
    session = FakeSession([FakeResponse(response_body(item)) for item in frozen])
    monkeypatch.setattr(r2d, "validate_authorization", lambda *args: frozen)
    monkeypatch.setattr(r2d, "load_corrected_plan", lambda *_: {})
    monkeypatch.setattr(r2d, "validate_frozen_requests", lambda *_: frozen)
    full = {
        **fake_full("1610612754", {("101", "202")}),
        **fake_full("1610612763", {("101", "202")}),
    }
    monkeypatch.setattr(r2d, "authenticate_full_season_bodies", lambda _: full)
    monkeypatch.setattr(r2d, "_preservation_after", lambda *_: [])
    clock_values = []
    for index in range(8):
        base = index * 2.0
        clock_values.extend([base, base, base + 0.1])
    result = r2d.execute_authorized_recovery(
        PROJECT_ROOT, authorization_path, evidence, planning,
        session_factory=lambda: session, sleeper=lambda _: None, monotonic=Clock(clock_values),
    )
    assert len(session.calls) == 8
    assert [call[1]["params"] for call in session.calls] == [item["parameters"] for item in frozen]
    assert result["summary"]["network_attempt_count"] == 8
    assert sorted(item.name for item in planning.iterdir()) == sorted(r2d.OUTPUT_FILES)
    manifest = r2d._read_json(planning / "artifact_hashes.json")
    assert manifest["artifact_inventory"] == list(r2d.OUTPUT_FILES)
    assert "artifact_hashes.json" not in manifest["artifacts"]
    invocation = r2d._read_json(r2d.execution_paths(evidence)["outcome"])
    assert invocation["exit_code"] == 0


def test_synthetic_official_failure_stops_after_one_and_records_failure(tmp_path, monkeypatch):
    frozen = frozen_requests()
    planning = tmp_path / "planning"
    evidence = tmp_path / "evidence"
    planning.mkdir()
    authorization_path = planning / "recovery_authorization.json"
    authorization_path.write_bytes(r2d.serialize_json(minimal_authorization()))
    session = FakeSession([FakeResponse(b"failure", 500), FakeResponse(response_body(frozen[1]))])
    monkeypatch.setattr(r2d, "validate_authorization", lambda *args: frozen)
    monkeypatch.setattr(r2d, "load_corrected_plan", lambda *_: {})
    monkeypatch.setattr(r2d, "validate_frozen_requests", lambda *_: frozen)
    with pytest.raises(r2d.RecoveryError, match="HTTP status"):
        r2d.execute_authorized_recovery(
            PROJECT_ROOT, authorization_path, evidence, planning,
            session_factory=lambda: session, sleeper=lambda _: None,
            monotonic=Clock([0.0, 0.0, 0.1]),
        )
    assert len(session.calls) == 1
    assert r2d.classify_request_state(evidence, frozen[0], frozen) == "failed_or_quarantined"
    assert r2d.classify_request_state(evidence, frozen[1], frozen) == "not_started"
    invocation = r2d._read_json(r2d.execution_paths(evidence)["outcome"])
    assert invocation["exit_code"] == 1
    assert "HTTP status 500" in invocation["stderr"]


def test_output_inventory_and_nonrecursive_manifest_contract_are_exact():
    assert r2d.OUTPUT_FILES == (
        "recovery_authorization.json", "request_ledger.json", "response_fingerprints.json",
        "team_reconciliation.json", "team_dispositions.json", "readiness_effect.json",
        "artifact_hashes.json", "summary.json",
    )
    source = (PROJECT_ROOT / r2d.SOURCE_PATH).read_text(encoding="utf-8")
    assert "artifact_hashes.json excludes itself" in source


def test_module_has_no_model_dataset_or_rating_aggregation_capability():
    source_path = PROJECT_ROOT / r2d.SOURCE_PATH
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = {"pandas", "numpy", "sklearn", "joblib", "pickle", "torch", "tensorflow"}
    assert imported.isdisjoint(forbidden)
    assert not any(name.startswith("fit_") or name.startswith("predict_") for name in dir(r2d))


def test_historical_paths_are_not_written_by_source_ast():
    source = (PROJECT_ROOT / r2d.SOURCE_PATH).read_text(encoding="utf-8")
    tree = ast.parse(source)
    write_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_write_once":
            write_calls.append(ast.unparse(node.args[0]))
    assert write_calls
    assert all("phase3f-r2b" not in call and "phase3f-r2c" not in call for call in write_calls)
