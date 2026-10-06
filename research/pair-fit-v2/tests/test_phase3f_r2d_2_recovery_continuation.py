from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2 import phase3f_r2d_2_recovery_continuation as r2d2
from pair_fit_v2.phase3f_r2b_1_response_contract import SCHEMAS
from pair_fit_v2.phase3f_r2c_1_recovery_specification import evaluate_disposition
from pair_fit_v2.phase3f_r2d_1_response_echo_contract import compare_response_echo


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.content = body
        self.status_code = status
        self.is_redirect = 300 <= status < 400
        self.is_permanent_redirect = status in {301, 308}
        self.history = []


class FakeSession:
    def __init__(self, values):
        self.values = list(values)
        self.calls = []
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.values.pop(0)
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


def requests_value():
    return r2d2.load_authorized_requests(PROJECT_ROOT)[1]


def response_body(request, pairs=((101, 202, 10.0),), *, parameters=None):
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
            row[lineup_headers.index("OFF_RATING")] = 100.0
            row[lineup_headers.index("DEF_RATING")] = 99.0
            row[lineup_headers.index("NET_RATING")] = 1.0
        rows.append(row)
    payload = {
        "resource": "teamdashlineups",
        "parameters": dict(request["parameters"]) if parameters is None else parameters,
        "resultSets": [
            {"name": "Overall", "headers": overall_headers, "rowSet": [overall]},
            {"name": "Lineups", "headers": lineup_headers, "rowSet": rows},
        ],
    }
    return json.dumps(payload, separators=(",", ":")).encode()


def disposition_record(**changes):
    value = {
        "full_season_evidence_authenticated": True,
        "all_four_recovery_responses_present": True,
        "all_four_recovery_responses_authenticated": True,
        "all_four_recovery_responses_structurally_valid": True,
        "complete_complementary_date_coverage": True,
        "every_individual_window_below_250": True,
        "early_base_advanced_keys_equal": True,
        "late_base_advanced_keys_equal": True,
        "window_union_equals_full_season_keys": True,
        "recovered_only_keys_validated": True,
        "conflicting_state": False,
        "failed_or_quarantined": False,
        "early_base_pair_row_count": 2,
        "early_advanced_pair_row_count": 2,
        "late_base_pair_row_count": 2,
        "late_advanced_pair_row_count": 2,
        "recovered_only_count": 0,
        "full_season_only_count": 0,
        "duplicate_count": 0,
        "malformed_pair_count": 0,
        "same_player_count": 0,
        "base_only_count": 0,
        "advanced_only_count": 0,
    }
    value.update(changes)
    return value


def verification(team, window, measure, keys, possessions=None):
    return {
        "team_id": team,
        "window": window,
        "measure": measure,
        "canonical_pair_keys": [list(item) for item in keys],
        "lineups_row_count": len(keys),
        "zero_possession_pair_keys": [],
        "possession_by_pair_key": possessions or {},
        "duplicate_count": 0,
        "malformed_pair_count": 0,
        "same_player_count": 0,
    }


def test_preflight_inputs_and_exact_seven_identity_allowlist_authenticate():
    original, requests = r2d2.load_authorized_requests(PROJECT_ROOT)
    assert len(original["authorized_requests"]) == 8
    assert [item["original_recovery_ordinal"] for item in requests] == list(range(2, 9))
    assert all(item["original_recovery_ordinal"] != 1 for item in requests)
    assert [item["canonical_request_identity_sha256"] for item in requests] == [
        "50994123ad43fe755078b138d579aee5a736c8e6c859cc4a9be63ef7f5664b42",
        "2aecf73ce3f86f50411ef7a761d2e3c5fc8e5985c4e18b791e1f75f093c991f9",
        "5339d2d00e17b56f6b8bfeded94c9983c008eb1034a31e2223f8ef6f5abfa6bd",
        "ef0f4fca5a19fd86183514b42323454b822dac7186b503f9516d99fbdea781aa",
        "c98989c66082563fbbf0caad68674c8e03dea43b3f3497eeeab8002de6cc00dc",
        "4e09d72c863e3db4b88e0540cec6b980800244b9d764a9ac25bea3ed4916e0e0",
        "be9e74c47bd223dd526148543e29c4580240cee75d7d87396c4e46c774989a02",
    ]


def test_namespace_lineage_fields_remain_distinct_and_exact():
    for request in requests_value():
        ordinal = request["original_recovery_ordinal"]
        assert request["future_output_namespace"].startswith("cache/phase3f-r2c-protected-recovery/")
        assert request["continuation_output_namespace"].startswith(r2d2.OUTPUT_ROOT.as_posix() + "/")
        assert request["future_output_namespace"] != request["continuation_output_namespace"]
        assert Path(request["continuation_output_namespace"]).name.startswith(f"{ordinal:02d}-")


def test_offline_indiana_revalidation_passes_without_copy_or_network():
    record, request = r2d2.offline_revalidate_indiana(PROJECT_ROOT)
    assert request["ordinal"] == 1
    assert record["offline_revalidation"] == "passed"
    assert record["network_request_prohibited"] is True
    assert record["network_attempt_count"] == 0
    assert record["body_copied_moved_rewritten_or_promoted"] is False
    assert record["body_reference"] == {
        "path": r2d2.QUARANTINED_BODY.as_posix(),
        "bytes": 58235,
        "raw_sha256": "9726387a7e3f3f6cae9656cf74d1d4194a0e1f4593bc5bb15b016bae9a072593",
        "canonical_json_sha256": "09f5970be9c4a9fdc2ece0cdeeeeef0bc04b8afb2c84f257781e0a81e44f7213",
    }


def test_corrected_echo_contract_accepts_only_frozen_special_representations():
    request = requests_value()[0]
    returned = dict(request["parameters"])
    returned["DateFrom"] = "10/21/2025"
    returned["DateTo"] = "01/31/2026"
    returned["PORound"] = 0
    returned["ISTRound"] = None
    result = compare_response_echo(request["parameters"], returned)
    assert result["passed"] is True
    returned["PORound"] = "0"
    assert compare_response_echo(request["parameters"], returned)["passed"] is False


def test_response_verification_uses_echo_schema_pair_and_numeric_checks():
    request = requests_value()[0]
    body = response_body(request, pairs=((202, 101, 0.0),))
    result = r2d2.verify_response_bytes(body, request)
    assert result["canonical_pair_keys"] == [["101", "202"]]
    assert result["zero_possession_pair_keys"] == [["101", "202"]]
    assert result["observed_result_set_order"] == ["Overall", "Lineups"]
    payload = json.loads(body)
    poss_index = payload["resultSets"][1]["headers"].index("POSS")
    payload["resultSets"][1]["rowSet"][0][poss_index] = "bad"
    with pytest.raises(r2d2.ResponseVerificationError, match="numeric and finite"):
        r2d2.verify_response_bytes(json.dumps(payload).encode(), request)


def test_indiana_ordinal_one_is_rejected_by_network_function(tmp_path):
    request = dict(requests_value()[0])
    request["original_recovery_ordinal"] = 1
    with pytest.raises(r2d2.ContinuationError, match="prohibited"):
        r2d2.acquire_one(request, tmp_path, FakeSession([]), previous_completion=None)


def test_successful_attempt_is_one_call_no_retry_redirect_or_timeout(tmp_path):
    request = requests_value()[0]
    session = FakeSession([FakeResponse(response_body(request))])
    outcome = r2d2.acquire_one(
        request, tmp_path, session, previous_completion=None,
        sleeper=lambda _: None, monotonic=Clock([10.0, 10.0, 10.2]),
    )
    assert outcome["state"] == "completed_verified"
    assert outcome["automatic_retries"] == 0
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == r2d2.URL
    assert kwargs["timeout"] == 30
    assert kwargs["allow_redirects"] is False
    assert kwargs["params"] == request["parameters"]
    assert r2d2.classify_request_state(tmp_path, request) == "completed_verified"


def test_transport_failure_is_quarantined_once_and_never_retried(tmp_path):
    request = requests_value()[0]
    session = FakeSession([requests.Timeout("timeout")])
    with pytest.raises(r2d2.ContinuationError, match="transport:Timeout"):
        r2d2.acquire_one(
            request, tmp_path, session, previous_completion=None,
            sleeper=lambda _: None, monotonic=Clock([1.0, 1.0, 1.1]),
        )
    assert len(session.calls) == 1
    assert r2d2.classify_request_state(tmp_path, request) == "failed_or_quarantined"
    with pytest.raises(r2d2.ContinuationError, match="not_started"):
        r2d2.acquire_one(
            request, tmp_path, session, previous_completion=None,
            sleeper=lambda _: None, monotonic=Clock([2.0, 2.0]),
        )


def test_monotonic_pacing_is_enforced_and_persisted(tmp_path):
    request = requests_value()[0]
    session = FakeSession([FakeResponse(response_body(request))])
    sleeps = []
    outcome = r2d2.acquire_one(
        request, tmp_path, session, previous_completion=9.0,
        sleeper=sleeps.append, monotonic=Clock([9.1, 10.0, 10.2]),
    )
    start = json.loads(r2d2.request_paths(tmp_path, request)["start"].read_text())
    assert sleeps == pytest.approx([0.9])
    assert start["observed_post_sleep_monotonic_gap_seconds"] == pytest.approx(1.0)
    assert outcome["process_monotonic_completion"] == pytest.approx(10.2)


def test_ambiguous_and_partial_restart_states_are_refused(tmp_path):
    request = requests_value()[0]
    paths = r2d2.request_paths(tmp_path, request)
    paths["start"].parent.mkdir(parents=True)
    paths["start"].write_text("{}", encoding="utf-8")
    assert r2d2.classify_request_state(tmp_path, request) == "conflicting_state"
    with pytest.raises(r2d2.ContinuationError, match="not_started"):
        r2d2.acquire_one(
            request, tmp_path, FakeSession([]), previous_completion=None,
            monotonic=Clock([1.0, 1.0]),
        )


def test_session_has_research_headers_trust_env_false_and_zero_retries():
    session = r2d2.create_session()
    try:
        assert session.trust_env is False
        assert session.get_adapter("https://").max_retries.total == 0
        assert session.get_adapter("https://").max_retries.redirect == 0
        for key, value in r2d2.RESEARCH_HEADERS.items():
            assert session.headers[key] == value
    finally:
        session.close()


def test_both_frozen_disposition_branches_and_final_population_actions():
    non_exhaustive = evaluate_disposition(disposition_record(
        recovered_only_count=1,
        window_union_equals_full_season_keys=False,
    ))
    assert non_exhaustive.disposition == "proven_non_exhaustive"
    assert r2d2.final_population_disposition(non_exhaustive.disposition) == (
        "exclude_whole_team_from_final_test_population"
    )
    operational = evaluate_disposition(disposition_record())
    assert operational.disposition == "operationally_resolved_no_observed_omission"
    assert r2d2.final_population_disposition(operational.disposition) == (
        "include_direct_full_season_population_when_final_test_is_later_built"
    )


def test_base_advanced_reconciliation_and_exposure_counts(monkeypatch, tmp_path):
    requests = requests_value()
    ind = "1610612754"
    mem = "1610612763"
    a, b, c = ("1", "2"), ("1", "3"), ("2", "3")
    d, e = ("4", "5"), ("4", "6")
    ordinal_one = verification(ind, "early", "Base", [a, b])
    data = {
        (ind, "early", "Advanced"): verification(ind, "early", "Advanced", [a, b], {"1-2": 20.0, "1-3": 30.0}),
        (ind, "late", "Base"): verification(ind, "late", "Base", [b, c]),
        (ind, "late", "Advanced"): verification(ind, "late", "Advanced", [b, c], {"1-3": 40.0, "2-3": 160.0}),
        (mem, "early", "Base"): verification(mem, "early", "Base", [d]),
        (mem, "early", "Advanced"): verification(mem, "early", "Advanced", [d], {"4-5": 10.0}),
        (mem, "late", "Base"): verification(mem, "late", "Base", [e]),
        (mem, "late", "Advanced"): verification(mem, "late", "Advanced", [e], {"4-6": 20.0}),
    }
    for request in requests:
        value = data[(request["team_id"], request["window"]["name"], request["measure"])]
        path = r2d2.request_paths(tmp_path, request)["verification"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r2d2.serialize_json(value))
    monkeypatch.setattr(r2d2, "classify_request_state", lambda *_: "completed_verified")
    monkeypatch.setattr(r2d2, "authenticate_full_season_bodies", lambda _: {
        (ind, "Base"): {"keys": {a, b}, "path": "i-base"},
        (ind, "Advanced"): {"keys": {a, b}, "path": "i-advanced"},
        (mem, "Base"): {"keys": {d, e}, "path": "m-base"},
        (mem, "Advanced"): {"keys": {d, e}, "path": "m-advanced"},
    })
    teams = r2d2.reconcile_teams(PROJECT_ROOT, tmp_path, ordinal_one, requests)
    assert teams[0]["recovered_only_keys"] == [["2", "3"]]
    assert teams[0]["recovered_only_summed_possessions"] == 160.0
    assert teams[0]["recovered_only_pairs_potentially_meeting_poss_ge_150"] == 1
    assert teams[0]["final_test_population_disposition"] == "exclude_whole_team_from_final_test_population"
    assert teams[1]["recovered_only_count"] == 0
    assert teams[1]["final_test_population_disposition"].startswith("include_direct_full_season")


def test_invalid_base_advanced_evidence_stays_unresolved():
    decision = evaluate_disposition(disposition_record(
        early_base_advanced_keys_equal=False,
        base_only_count=1,
        window_union_equals_full_season_keys=False,
        full_season_only_count=1,
    ))
    assert decision.disposition == "recovery_unresolved"
    assert r2d2.final_population_disposition(decision.disposition) == (
        "unresolved_block_final_test_readiness"
    )


def test_failure_before_model_safeguard_has_no_model_or_dataset_capability():
    tree = ast.parse((PROJECT_ROOT / r2d2.SOURCE_PATH).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not ({"sklearn", "pandas", "numpy", "joblib", "pickle"} & imported)
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not ({"fit", "predict", "transform", "fit_transform", "to_parquet", "to_csv"} & calls)
