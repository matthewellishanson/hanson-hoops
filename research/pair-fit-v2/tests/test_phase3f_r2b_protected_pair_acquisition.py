import ast
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3f_r2b_protected_pair_acquisition as phase


PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def frozen():
    return phase.load_frozen_requests(PROJECT)


def payload(request, pairs=((1, 2), (2, 3)), *, field_values=None):
    measure = request["parameters"]["MeasureType"]
    field = "POSS" if measure == "Base" else "NET_RATING"
    headers = ["GROUP_ID", "TEAM_ID", field]
    values = list(field_values) if field_values is not None else ([100.0] * len(pairs))
    rows = [
        [f"-{left}-{right}-", int(request["parameters"]["TeamID"]), value]
        for (left, right), value in zip(pairs, values)
    ]
    return {"resultSets": [{"name": phase.RESULT_SET, "headers": headers, "rowSet": rows}]}


def body(request, pairs=((1, 2), (2, 3)), *, field_values=None):
    return json.dumps(payload(request, pairs, field_values=field_values), separators=(",", ":")).encode()


class FakeResponse:
    def __init__(self, content, status=200, redirect=False):
        self.content = content
        self.status_code = status
        self.is_redirect = redirect
        self.is_permanent_redirect = False


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        self.closed = True


def authorize(tmp_path):
    planning = tmp_path / "planning"
    document = phase.initialize_authorization(PROJECT, planning)
    return planning, document


def start_record(request):
    return {
        "version": phase.VERSION,
        "request_id": request["request_id"],
        "canonical_identity_sha256": phase.identity_sha256(request),
        "attempt_number": 1,
        "started_at": "synthetic",
    }


def test_exact_60_request_allowlist_teams_order_and_uniqueness(frozen):
    assert len(frozen) == 60
    observed = [
        (item["parameters"]["TeamID"], item["parameters"]["MeasureType"])
        for item in frozen
    ]
    assert observed == [(team, measure) for team in phase.TEAM_IDS for measure in phase.MEASURES]
    assert len({team for team, _ in observed}) == 30
    assert [int(team) for team in phase.TEAM_IDS] == sorted(map(int, phase.TEAM_IDS))
    assert len({item["request_id"] for item in frozen}) == 60
    assert len({phase.identity_sha256(item) for item in frozen}) == 60


@pytest.mark.parametrize(
    ("location", "field", "value"),
    [
        ("parameters", "Season", "2024-25"),
        ("request", "endpoint", "leaguedashlineups"),
        ("parameters", "TeamID", "1610619999"),
        ("parameters", "MeasureType", "Usage"),
        ("parameters", "Month", "1"),
        ("parameters", "DateFrom", "01/01/2026"),
        ("parameters", "DateTo", "04/01/2026"),
    ],
)
def test_unauthorized_and_recovery_window_request_drift_rejected(frozen, location, field, value):
    changed = deepcopy(frozen[0])
    if location == "request":
        changed[field] = value
    else:
        changed["parameters"][field] = value
    with pytest.raises(phase.AcquisitionError):
        phase.validate_request_identity(changed, frozen)


def test_authorization_exact_count_pins_and_write_once(tmp_path):
    planning, first = authorize(tmp_path)
    assert len(first["authorized_requests"]) == 60
    assert first["attempt_limit_per_identity"] == 1
    assert first["recovery_acquisition_authorized"] is False
    assert first["required_committed_head"] == phase.EXPECTED_HEAD
    before = (planning / "authorization.json").read_bytes()
    assert phase.initialize_authorization(PROJECT, planning) == first
    assert (planning / "authorization.json").read_bytes() == before
    (planning / "authorization.json").write_bytes(b"conflict")
    with pytest.raises(phase.AcquisitionError, match="differs"):
        phase.initialize_authorization(PROJECT, planning)


def test_session_zero_retries_redirect_prohibition_and_trust_env():
    session = phase.create_session()
    try:
        assert session.trust_env is False
        retry = session.adapters["https://"].max_retries
        assert (retry.total, retry.connect, retry.read, retry.redirect, retry.status) == (0, 0, 0, 0, 0)
        assert session.headers["Referer"] == phase.RESEARCH_HEADERS["Referer"]
    finally:
        session.close()


def test_transport_timeout_redirect_setting_and_completed_skip(tmp_path, frozen):
    request = frozen[0]
    evidence = tmp_path / "evidence"
    session = FakeSession([FakeResponse(body(request))])
    result = phase.acquire_one(request, frozen, evidence, session)
    assert result["action"] == "acquired"
    url, kwargs = session.calls[0]
    assert url == phase.URL
    assert kwargs["timeout"] == 30
    assert kwargs["allow_redirects"] is False
    assert kwargs["params"] == request["parameters"]
    before = {item.name: item.read_bytes() for item in phase.request_paths(evidence, request)["start"].parent.iterdir()}
    assert phase.acquire_one(request, frozen, evidence, FakeSession([]))["action"] == "skipped_completed_verified"
    assert before == {item.name: item.read_bytes() for item in phase.request_paths(evidence, request)["start"].parent.iterdir()}


def test_restart_started_failed_and_conflicting_states_stop(tmp_path, frozen):
    request = frozen[0]
    started_root = tmp_path / "started"
    paths = phase.request_paths(started_root, request)
    phase._write_once(paths["start"], phase.serialize_json(start_record(request)))
    assert phase.classify_request_state(started_root, request, frozen) == "started_without_outcome"
    with pytest.raises(phase.AcquisitionError, match="started_without_outcome"):
        phase.acquire_one(request, frozen, started_root, FakeSession([]))

    failed_root = tmp_path / "failed"
    paths = phase.request_paths(failed_root, request)
    phase._write_once(paths["start"], phase.serialize_json(start_record(request)))
    failed = {
        **start_record(request),
        "state": "failed_or_quarantined",
        "http_status": None,
    }
    phase._write_once(paths["outcome"], phase.serialize_json(failed))
    phase._write_once(paths["failure"], phase.serialize_json({"reason": "synthetic"}))
    assert phase.classify_request_state(failed_root, request, frozen) == "failed_or_quarantined"

    conflict_root = tmp_path / "conflict"
    paths = phase.request_paths(conflict_root, request)
    phase._write_once(paths["outcome"], b"{}")
    assert phase.classify_request_state(conflict_root, request, frozen) == "conflicting_state"


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse(b"error", status=503), "HTTP status 503"),
        (FakeResponse(b"redirect", status=302, redirect=True), "redirect response prohibited"),
        (FakeResponse(b"not-json"), "invalid strict JSON"),
        (FakeResponse(json.dumps({"resultSets": []}).encode()), "one Lineups"),
    ],
)
def test_http_redirect_json_and_result_set_failure_quarantine(tmp_path, frozen, response, message):
    request = frozen[0]
    with pytest.raises(phase.AcquisitionError, match=message):
        phase.acquire_one(request, frozen, tmp_path, FakeSession([response]))
    assert phase.classify_request_state(tmp_path, request, frozen) == "failed_or_quarantined"


def test_timeout_stops_before_next_identity(tmp_path, frozen):
    planning, _ = authorize(tmp_path)
    session = FakeSession([requests.Timeout("synthetic"), FakeResponse(body(frozen[1]))])
    with pytest.raises(phase.AcquisitionError, match="transport:Timeout"):
        phase.execute_authorized_acquisition(
            PROJECT,
            planning / "authorization.json",
            tmp_path / "evidence",
            planning,
            session_factory=lambda: session,
        )
    assert len(session.calls) == 1
    assert phase.classify_request_state(tmp_path / "evidence", frozen[0], frozen) == "failed_or_quarantined"
    assert phase.classify_request_state(tmp_path / "evidence", frozen[1], frozen) == "not_started"


def test_row_width_mismatch_is_quarantined(tmp_path, frozen):
    request = frozen[0]
    malformed = payload(request)
    malformed["resultSets"][0]["rowSet"][0].pop()
    response = FakeResponse(json.dumps(malformed).encode())
    with pytest.raises(phase.AcquisitionError, match="row width"):
        phase.acquire_one(request, frozen, tmp_path, FakeSession([response]))
    assert phase.classify_request_state(tmp_path, request, frozen) == "failed_or_quarantined"


def test_numeric_pair_canonicalization_reversal_malformed_same_and_duplicates(frozen):
    assert phase.parse_canonical_pair("-20-3-") == (("3", "20"), "valid")
    assert phase.parse_canonical_pair("-3-20-") == (("3", "20"), "valid")
    assert phase.parse_canonical_pair("-3-3-")[1] == "same_player_pair"
    assert phase.parse_canonical_pair("-03-20-")[1] == "missing_or_malformed_player_ids"
    assert phase.parse_canonical_pair(None)[1] == "missing_or_malformed_player_ids"
    request = frozen[0]
    verification = phase.verify_response_bytes(body(request, ((20, 3), (3, 20))), request, frozen)
    assert verification["pair_identity"]["unique_canonical_pair_count"] == 1
    assert verification["pair_identity"]["duplicate_canonical_pair_count"] == 1


def test_pair_and_required_field_defects_are_visible_not_transport_failures(frozen):
    base = frozen[0]
    value = payload(base, ((1, 1), (2, 3)), field_values=(0, -1))
    value["resultSets"][0]["rowSet"].append(["bad", int(base["parameters"]["TeamID"]), "x"])
    verification = phase.verify_response_bytes(json.dumps(value).encode(), base, frozen)
    assert verification["pair_identity"]["same_player_pair_count"] == 1
    assert verification["pair_identity"]["malformed_pair_count"] == 1
    assert verification["required_field"]["zero_count"] == 1
    assert verification["required_field"]["negative_count"] == 1
    assert verification["required_field"]["nonnumeric_count"] == 1
    assert verification["zero_possession_row_count"] == 1

    advanced = frozen[1]
    invalid = phase.verify_response_bytes(body(advanced, ((1, 2),), field_values=("inf",)), advanced, frozen)
    assert invalid["required_field"]["nonfinite_count"] == 1
    negative = phase.verify_response_bytes(body(advanced, ((1, 2),), field_values=(-20.5,)), advanced, frozen)
    assert negative["required_field"]["invalid_row_count"] == 0


def test_missing_required_field_is_recorded(frozen):
    request = frozen[0]
    value = payload(request)
    value["resultSets"][0]["headers"].pop()
    for row in value["resultSets"][0]["rowSet"]:
        row.pop()
    verification = phase.verify_response_bytes(json.dumps(value).encode(), request, frozen)
    assert verification["required_field"]["header_present"] is False
    assert verification["required_field"]["missing_count"] == 2


def test_full_execution_spacing_reconciliation_outputs_and_exact_250(tmp_path, frozen):
    planning, authorization = authorize(tmp_path)
    phase.record_official_invocation(planning, planning / "authorization.json", ["python", "official"])
    pairs_250 = tuple((index + 1, index + 1001) for index in range(250))
    responses = []
    for request in frozen:
        pairs = pairs_250 if request["parameters"]["TeamID"] == phase.TEAM_IDS[0] else ((1, 2), (2, 3))
        responses.append(FakeResponse(body(request, pairs)))
    session = FakeSession(responses)
    sleeps = []
    result = phase.execute_authorized_acquisition(
        PROJECT,
        planning / "authorization.json",
        tmp_path / "evidence",
        planning,
        session_factory=lambda: session,
        sleeper=sleeps.append,
        monotonic=lambda: 100.0,
    )
    assert len(session.calls) == 60
    assert sleeps == [1.0] * 59
    assert result["summary"]["completed_verified_request_count"] == 60
    assert result["summary"]["classification"].startswith("CONDITIONAL PASS")
    teams = result["reconciliation"]["team_reconciliation"]
    assert teams[0]["structural_disposition"] == "exact_250_unresolved"
    assert teams[1]["structural_disposition"] == "structurally_complete_non_250"
    assert result["reconciliation"] == phase.reconcile(tmp_path / "evidence", authorization["authorized_requests"], frozen)
    assert (planning / "artifact_hashes.json").exists()
    assert (planning / "exact_250_unresolved.json").exists()
    exact = phase._read_json(planning / "exact_250_unresolved.json")
    assert exact["teams"][0]["later_checkpoint_requirements"]["recovery_request_count"] == 4
    assert result["summary"]["recovery_request_count"] == 0


def test_base_advanced_equality_and_mismatch_disposition(tmp_path, frozen):
    evidence = tmp_path / "evidence"
    for request in frozen:
        pairs = ((1, 2), (2, 3))
        if request["parameters"]["TeamID"] == phase.TEAM_IDS[0] and request["parameters"]["MeasureType"] == "Advanced":
            pairs = ((1, 2),)
        phase.acquire_one(request, frozen, evidence, FakeSession([FakeResponse(body(request, pairs))]))
    result = phase.reconcile(evidence, frozen, frozen)
    first = result["team_reconciliation"][0]
    second = result["team_reconciliation"][1]
    assert first["structural_disposition"] == "base_advanced_mismatch"
    assert first["base_only_keys"] == [["2", "3"]]
    assert second["structural_disposition"] == "structurally_complete_non_250"


def test_all_states_scanned_before_transport(tmp_path, frozen):
    planning, _ = authorize(tmp_path)
    blocked = frozen[-1]
    paths = phase.request_paths(tmp_path / "evidence", blocked)
    phase._write_once(paths["start"], phase.serialize_json(start_record(blocked)))
    session = FakeSession([FakeResponse(body(frozen[0]))])
    with pytest.raises(phase.AcquisitionError, match="blocks phase"):
        phase.execute_authorized_acquisition(
            PROJECT,
            planning / "authorization.json",
            tmp_path / "evidence",
            planning,
            session_factory=lambda: session,
        )
    assert session.calls == []


def test_hash_mutation_detection_and_write_once_destination(tmp_path, frozen):
    request = frozen[0]
    phase.acquire_one(request, frozen, tmp_path, FakeSession([FakeResponse(body(request))]))
    paths = phase.request_paths(tmp_path, request)
    with pytest.raises(phase.AcquisitionError, match="write-once"):
        phase._write_once(paths["start"], b"again")
    paths["verified_body"].write_bytes(b"changed")
    assert phase.classify_request_state(tmp_path, request, frozen) == "conflicting_state"


def test_official_invocation_is_write_once_and_pins_authorization(tmp_path):
    planning, _ = authorize(tmp_path)
    auth = planning / "authorization.json"
    record = phase.record_official_invocation(planning, auth, ["python", "official"])
    assert record["invocation_number"] == 1
    assert record["authorization_sha256"] == phase.sha256_bytes(auth.read_bytes())
    with pytest.raises(phase.AcquisitionError, match="write-once"):
        phase.record_official_invocation(planning, auth, ["again"])


def test_pinned_inputs_include_r0_r01_r1s_and_r2a():
    values = phase.fingerprint_inputs(PROJECT)
    assert set(values) == set(phase.PINNED_INPUT_HASHES)
    assert values[phase.R1S_PLAN.as_posix()]["sha256"] == phase.R1S_PLAN_SHA256
    assert all(value["bytes"] > 0 for value in values.values())


def test_source_has_no_model_evaluation_serialization_or_recovery_transport_capability():
    sources = [
        PROJECT / "src/pair_fit_v2/phase3f_r2b_protected_pair_acquisition.py",
        PROJECT / "src/pair_fit_v2/phase3f_r2b_cli.py",
    ]
    forbidden_imports = {"sklearn", "numpy", "pandas", "joblib", "pickle"}
    forbidden_calls = {"fit", "fit_transform", "predict", "score", "dump"}
    for source in sources:
        text = source.read_text(encoding="utf-8")
        tree = ast.parse(text)
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names
        }
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not imports & forbidden_imports
        assert not calls & forbidden_calls
        assert "leaguedashlineups" not in text.lower()
        assert "four factors" not in text.lower()
    assert phase.URL.endswith("/teamdashlineups")
