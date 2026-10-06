import ast
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3f_r2a_prior_profile_acquisition as phase


PROJECT = Path(__file__).resolve().parents[1]


def requests_value():
    return phase.load_frozen_requests(PROJECT)


def payload(mode, ids=(1, 2)):
    required = phase.PER100_SOURCE_FIELDS if mode == "Per100Possessions" else phase.TOTALS_SOURCE_FIELDS
    headers = list(required)
    rows = []
    for player_id in ids:
        row = []
        for header in headers:
            if header == "PLAYER_ID":
                row.append(player_id)
            elif header == "GP":
                row.append(10)
            elif header == "MIN":
                row.append(123.5)
            elif header == "TEAM_COUNT":
                row.append(1)
            else:
                row.append(1.25)
        rows.append(row)
    return {"resultSets": [{"name": phase.RESULT_SET, "headers": headers, "rowSet": rows}]}


def body(mode, ids=(1, 2)):
    return json.dumps(payload(mode, ids), separators=(",", ":")).encode()


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
    authorization = phase.initialize_authorization(PROJECT, planning)
    return planning, authorization


def test_exact_two_request_allowlist_and_order():
    items = requests_value()
    assert len(items) == 2
    assert [item["parameters"]["PerMode"] for item in items] == ["Per100Possessions", "Totals"]
    assert [item["parameters"]["Season"] for item in items] == ["2024-25", "2024-25"]
    assert all(item["endpoint"] == "leaguedashplayerstats" for item in items)
    assert all(item["parameters"]["TeamID"] == "" for item in items)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Season", "2025-26"),
        ("PerMode", "PerGame"),
        ("MeasureType", "Advanced"),
        ("TeamID", "1610612744"),
        ("Month", "1"),
    ],
)
def test_unlisted_request_rejected(field, value):
    request = deepcopy(requests_value()[0])
    request["parameters"][field] = value
    with pytest.raises(phase.AcquisitionError):
        phase.validate_request_identity(request)


def test_teamdashlineups_rejected():
    request = deepcopy(requests_value()[0])
    request["endpoint"] = "teamdashlineups"
    with pytest.raises(phase.AcquisitionError, match="allowlist"):
        phase.validate_request_identity(request)


def test_authorization_rejects_canonical_identity_drift(tmp_path):
    planning, authorization = authorize(tmp_path)
    changed = deepcopy(authorization)
    changed["authorized_requests"][0]["parameters"]["Month"] = "1"
    with pytest.raises(phase.AcquisitionError, match="does not match"):
        phase.validate_authorization(changed, PROJECT)
    assert (planning / "authorization.json").exists()


def test_authorization_is_write_once_and_identical_reuse_is_read_only(tmp_path):
    planning, first = authorize(tmp_path)
    target = planning / "authorization.json"
    before = target.read_bytes()
    second = phase.initialize_authorization(PROJECT, planning)
    assert first == second
    assert target.read_bytes() == before
    target.write_bytes(b"conflict")
    with pytest.raises(phase.AcquisitionError, match="differs"):
        phase.initialize_authorization(PROJECT, planning)


def test_session_contract_zero_retry_trust_env_and_headers():
    session = phase.create_session()
    try:
        assert session.trust_env is False
        assert session.headers["Referer"] == phase.RESEARCH_HEADERS["Referer"]
        assert session.adapters["https://"].max_retries.total == 0
        assert session.adapters["https://"].max_retries.connect == 0
        assert session.adapters["https://"].max_retries.read == 0
        assert session.adapters["https://"].max_retries.redirect == 0
    finally:
        session.close()


def test_transport_uses_timeout_and_disables_redirects(tmp_path):
    request = requests_value()[0]
    session = FakeSession([FakeResponse(body("Per100Possessions"))])
    result = phase.acquire_one(request, tmp_path / "evidence", session)
    assert result["action"] == "acquired"
    _, kwargs = session.calls[0]
    assert kwargs["timeout"] == 30
    assert kwargs["allow_redirects"] is False
    assert kwargs["params"] == request["parameters"]


def test_one_attempt_enforcement_and_completed_skip(tmp_path):
    request = requests_value()[0]
    evidence = tmp_path / "evidence"
    session = FakeSession([FakeResponse(body("Per100Possessions"))])
    phase.acquire_one(request, evidence, session)
    before = {path.name: path.read_bytes() for path in phase.request_paths(evidence, request)["start"].parent.iterdir()}
    skipped = phase.acquire_one(request, evidence, FakeSession([]))
    assert skipped["action"] == "skipped_completed_verified"
    assert before == {path.name: path.read_bytes() for path in phase.request_paths(evidence, request)["start"].parent.iterdir()}


def test_started_without_outcome_stops(tmp_path):
    request = requests_value()[0]
    paths = phase.request_paths(tmp_path, request)
    phase._write_once(paths["start"], phase.serialize_json({
        "request_id": request["request_id"],
        "canonical_identity_sha256": phase.identity_sha256(request),
        "attempt_number": 1,
    }))
    assert phase.classify_request_state(tmp_path, request) == "started_without_outcome"
    with pytest.raises(phase.AcquisitionError, match="started_without_outcome"):
        phase.acquire_one(request, tmp_path, FakeSession([]))


def test_conflicting_state_refused(tmp_path):
    request = requests_value()[0]
    paths = phase.request_paths(tmp_path, request)
    phase._write_once(paths["outcome"], phase.serialize_json({"state": "completed_verified"}))
    assert phase.classify_request_state(tmp_path, request) == "conflicting_state"


def test_unexpected_record_is_conflicting(tmp_path):
    request = requests_value()[0]
    paths = phase.request_paths(tmp_path, request)
    paths["start"].parent.mkdir(parents=True)
    (paths["start"].parent / "unexpected.json").write_text("{}")
    assert phase.classify_request_state(tmp_path, request) == "conflicting_state"


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (FakeResponse(b"server error", status=503), "HTTP status 503"),
        (FakeResponse(body("Per100Possessions"), status=200, redirect=True), "redirect response prohibited"),
        (FakeResponse(b"not-json"), "invalid strict JSON"),
    ],
)
def test_http_redirect_and_invalid_json_quarantine(tmp_path, response, message):
    request = requests_value()[0]
    with pytest.raises(phase.AcquisitionError, match=message):
        phase.acquire_one(request, tmp_path, FakeSession([response]))
    assert phase.classify_request_state(tmp_path, request) == "failed_or_quarantined"
    assert phase.request_paths(tmp_path, request)["failure"].exists()


def test_timeout_quarantine_and_no_second_request(tmp_path):
    planning, _ = authorize(tmp_path)
    session = FakeSession([requests.Timeout("synthetic"), FakeResponse(body("Totals"))])
    with pytest.raises(phase.AcquisitionError, match="transport:Timeout"):
        phase.execute_authorized_acquisition(
            PROJECT,
            planning / "authorization.json",
            tmp_path / "evidence",
            planning,
            session_factory=lambda: session,
        )
    assert len(session.calls) == 1
    assert phase.classify_request_state(tmp_path / "evidence", requests_value()[0]) == "failed_or_quarantined"
    assert phase.classify_request_state(tmp_path / "evidence", requests_value()[1]) == "not_started"


def test_schema_mismatch_quarantine(tmp_path):
    request = requests_value()[0]
    bad = payload("Per100Possessions")
    index = bad["resultSets"][0]["headers"].index("FGA")
    bad["resultSets"][0]["headers"].pop(index)
    for row in bad["resultSets"][0]["rowSet"]:
        row.pop(index)
    with pytest.raises(phase.AcquisitionError, match="missing required fields"):
        phase.acquire_one(request, tmp_path, FakeSession([FakeResponse(json.dumps(bad).encode())]))
    assert phase.classify_request_state(tmp_path, request) == "failed_or_quarantined"


def test_player_id_validation_duplicate_and_nonpositive():
    request = requests_value()[0]
    with pytest.raises(phase.ResponseValidationError, match="duplicate") as duplicate:
        phase.verify_response_bytes(body("Per100Possessions", (1, 1)), request)
    assert duplicate.value.diagnostics["player_ids"]["duplicate_count"] == 1
    with pytest.raises(phase.ResponseValidationError, match="malformed") as malformed:
        phase.verify_response_bytes(body("Per100Possessions", (0, 2)), request)
    assert malformed.value.diagnostics["player_ids"]["malformed_or_nonpositive_count"] == 1


def test_hash_verification_detects_mutation(tmp_path):
    request = requests_value()[0]
    evidence = tmp_path / "evidence"
    phase.acquire_one(request, evidence, FakeSession([FakeResponse(body("Per100Possessions"))]))
    phase.request_paths(evidence, request)["verified_body"].write_bytes(b"changed")
    assert phase.classify_request_state(evidence, request) == "conflicting_state"


def test_minimum_spacing_and_deterministic_reconciliation(tmp_path):
    planning, _ = authorize(tmp_path)
    session = FakeSession([
        FakeResponse(body("Per100Possessions", (1, 2))),
        FakeResponse(body("Totals", (2, 3))),
    ])
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
    assert sleeps == [1.0]
    reconciliation = result["reconciliation"]
    ids = reconciliation["player_id_reconciliation"]
    assert ids["per100_unique_player_count"] == 2
    assert ids["totals_unique_player_count"] == 2
    assert ids["intersection_count"] == 1
    assert ids["per100_only_ids"] == ["1"]
    assert ids["totals_only_ids"] == ["3"]
    assert reconciliation["total_min_reliability"]["finite_nonnegative_for_all_totals_rows"] is True
    assert reconciliation["frozen_no_shot_inputs"]["feature_count"] == 45
    assert result["summary"]["classification"].startswith("PASS")


def test_all_states_scanned_before_transport(tmp_path):
    planning, _ = authorize(tmp_path)
    second = requests_value()[1]
    paths = phase.request_paths(tmp_path / "evidence", second)
    phase._write_once(paths["start"], phase.serialize_json({
        "request_id": second["request_id"],
        "canonical_identity_sha256": phase.identity_sha256(second),
        "attempt_number": 1,
    }))
    session = FakeSession([FakeResponse(body("Per100Possessions"))])
    with pytest.raises(phase.AcquisitionError, match="blocks phase"):
        phase.execute_authorized_acquisition(
            PROJECT,
            planning / "authorization.json",
            tmp_path / "evidence",
            planning,
            session_factory=lambda: session,
        )
    assert session.calls == []


def test_protected_path_rejected_before_filesystem_access(monkeypatch):
    monkeypatch.setattr(Path, "exists", lambda self: pytest.fail("filesystem accessed"))
    with pytest.raises(phase.AcquisitionError, match="protected-season path"):
        phase.classify_request_state(Path("cache/2025-26"), requests_value()[0])


def test_input_fingerprints_cover_r0_r01_and_r1s():
    values = phase.fingerprint_inputs(PROJECT)
    assert len(values) == len(phase.COMMITTED_INPUTS) + len(phase.GENERATED_INPUT_HASHES)
    assert values[phase.R1S_PLAN.as_posix()]["sha256"] == phase.R1S_PLAN_SHA256
    assert all(item["kind"] in {"committed", "generated"} for item in values.values())


def test_source_has_no_model_or_final_test_construction_capability():
    sources = [
        PROJECT / "src/pair_fit_v2/phase3f_r2a_prior_profile_acquisition.py",
        PROJECT / "src/pair_fit_v2/phase3f_r2a_cli.py",
    ]
    forbidden_imports = {"sklearn", "numpy", "pandas", "joblib", "pickle"}
    forbidden_calls = {"fit", "fit_transform", "predict", "score", "dump"}
    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8"))
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


def test_official_invocation_record_is_write_once(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "src")
    record = phase.record_official_invocation(tmp_path, ["python", "-m", "pair_fit_v2.phase3f_r2a_cli"])
    assert record["pythonpath"] == "src"
    with pytest.raises(phase.AcquisitionError, match="write-once"):
        phase.record_official_invocation(tmp_path, ["again"])
