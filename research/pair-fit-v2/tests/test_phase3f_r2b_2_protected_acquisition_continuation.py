import ast
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import requests


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3f_r2b_1_response_contract as contract
from pair_fit_v2 import phase3f_r2b_2_protected_acquisition_continuation as phase


PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def frozen():
    return phase.load_continuation_requests(PROJECT)


def _row(headers, values):
    return [values.get(header, 0) for header in headers]


def payload(request, pairs=((1, 2),), *, exact_parameters=True):
    measure = request["parameters"]["MeasureType"]
    team_id = request["parameters"]["TeamID"]
    overall_headers = list(contract.SCHEMAS[measure]["Overall"])
    lineups_headers = list(contract.SCHEMAS[measure]["Lineups"])
    overall = _row(overall_headers, {
        "GROUP_SET": "Overall", "GROUP_VALUE": "2025-26", "TEAM_ID": int(team_id),
        "TEAM_ABBREVIATION": "TST", "TEAM_NAME": "Synthetic Team",
    })
    lineups = []
    for left, right in pairs:
        lineups.append(_row(lineups_headers, {
            "GROUP_SET": "Lineups", "GROUP_ID": f"-{left}-{right}-",
            "GROUP_NAME": f"{left} - {right}", "MIN": 1.0,
            "SUM_TIME_PLAYED": 60.0, "POSS": 10.0, "NET_RATING": 1.5,
        }))
    parameters = {
        "TeamID": int(team_id), "Season": "2025-26",
        "SeasonType": "Regular Season", "MeasureType": measure,
    } if exact_parameters else {"TeamID": int(team_id)}
    return {
        "resource": "teamdashlineups", "parameters": parameters,
        "resultSets": [
            {"name": "Overall", "headers": overall_headers, "rowSet": [overall]},
            {"name": "Lineups", "headers": lineups_headers, "rowSet": lineups},
        ],
    }


def body(request, pairs=((1, 2),)):
    return json.dumps(payload(request, pairs), separators=(",", ":"), allow_nan=False).encode()


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


def initialize(tmp_path, monkeypatch):
    planning = tmp_path / "p"
    monkeypatch.setattr(phase, "PLANNING_NAMESPACE", planning)
    monkeypatch.setattr(phase, "EVIDENCE_NAMESPACE", tmp_path / "official-evidence")
    document = phase.initialize_authorization(PROJECT, planning)
    return planning, document


def start_record(request):
    return {
        "version": phase.VERSION, "request_id": request["request_id"],
        "ordinal": request["ordinal"],
        "canonical_identity_sha256": phase.identity_sha256(request),
        "attempt_number": 1, "started_at": "synthetic",
    }


def atlanta_pairs():
    payload_value = json.loads((PROJECT / phase.ATLANTA_RAW_PATH).read_bytes())
    lineups = next(item for item in payload_value["resultSets"] if item["name"] == "Lineups")
    index = lineups["headers"].index("GROUP_ID")
    return tuple(tuple(map(int, row[index].strip("-").split("-"))) for row in lineups["rowSet"])


def test_exact_authorization_contract_and_original_ordinals(frozen):
    assert len(frozen) == 59
    assert [item["ordinal"] for item in frozen] == list(range(2, 61))
    assert len({item["request_id"] for item in frozen}) == 59
    assert len({item["canonical_identity_sha256"] for item in frozen}) == 59
    assert frozen[0]["request_id"] == "teamdashlineups:1610612737:advanced"
    assert all(phase.identity_sha256(item) == item["canonical_identity_sha256"] for item in frozen)
    document = phase.authorization_document(PROJECT)
    assert document["r2b1_contract_identity"] == phase.CONTRACT_IDENTITY
    assert document["atlanta_ordinal_1"]["disposition"] == "offline_revalidation_only"
    assert document["atlanta_ordinal_1"]["network_authorized"] is False
    assert document["transport_authorized_identity_count"] == 59
    assert document["network_authorized_ordinals"] == list(range(2, 61))
    assert document["transport"]["automatic_retries"] == 0
    assert document["recovery_requests_authorized"] is False
    assert document["final_test_dataset_authorized"] is False
    assert document["model_operation_authorized"] is False


def test_failed_r2b_and_all_pinned_inputs_preserved():
    values = phase.validate_preserved_inputs(PROJECT)
    assert values[phase.ATLANTA_RAW_PATH.as_posix()] == {
        "bytes": phase.ATLANTA_RAW_BYTES, "sha256": phase.ATLANTA_RAW_SHA256,
    }
    for name, expected in phase.R2B1_ARTIFACTS.items():
        assert values[(phase.R2B1_NAMESPACE / name).as_posix()]["sha256"] == expected
    assert not (PROJECT / "cache/phase3f-r2b/protected-final-target/1610612737-01-base/verification.json").exists()
    assert not (PROJECT / "cache/phase3f-r2b/protected-final-target/1610612737-01-base/verified-response.bin").exists()


def test_atlanta_offline_revalidation_exact_findings_and_no_copy(tmp_path, monkeypatch):
    planning, authorization = initialize(tmp_path, monkeypatch)
    # The production routine intentionally writes only to the fixed official planning
    # namespace, so exercise the pure validator and record constructor in disposable state.
    original = json.loads((PROJECT / "planning/phase3f-r2b/authorization.json").read_text())["authorized_requests"][0]
    raw = (PROJECT / phase.ATLANTA_RAW_PATH).read_bytes()
    result = phase.verify_atlanta_contract(raw, original)
    assert result["overall_header_count"] == 57
    assert result["overall_row_count"] == 1
    assert result["lineups_header_count"] == 56
    assert result["lineups_row_count"] == 200
    assert result["row_width_error_count"] == 0
    assert result["canonical_unordered_pair_count"] == 200
    assert result["duplicate_canonical_pair_count"] == 0
    assert result["malformed_group_identifier_count"] == 0
    assert result["same_player_pair_count"] == 0
    assert result["invalid_player_id_count"] == 0
    assert result["exact_250"] is False
    assert result["base_poss_absent_as_expected"] is True
    assert result["raw_sha256"] == phase.ATLANTA_RAW_SHA256
    assert result["canonical_json_sha256"] == phase.ATLANTA_CANONICAL_SHA256
    assert authorization["atlanta_ordinal_1"]["network_authorized"] is False
    assert not any(path.name.endswith("response.bin") for path in planning.iterdir())


def test_atlanta_and_ordinal_one_transport_prohibited(frozen):
    atlanta = json.loads((PROJECT / "planning/phase3f-r2b/authorization.json").read_text())["authorized_requests"][0]
    with pytest.raises(phase.ContinuationError, match="Atlanta"):
        phase.validate_request_identity(atlanta, frozen)
    changed = deepcopy(frozen[0])
    changed["ordinal"] = 1
    with pytest.raises(phase.ContinuationError, match="Atlanta|outside"):
        phase.validate_request_identity(changed, frozen)


@pytest.mark.parametrize(("location", "field", "value"), [
    ("parameters", "Season", "2024-25"),
    ("parameters", "MeasureType", "Usage"),
    ("parameters", "TeamID", "1610619999"),
    ("parameters", "DateFrom", "01/01/2026"),
    ("request", "endpoint", "leaguedashlineups"),
])
def test_identity_parameter_and_recovery_drift_rejected(frozen, location, field, value):
    changed = deepcopy(frozen[0])
    (changed if location == "request" else changed["parameters"])[field] = value
    with pytest.raises(phase.ContinuationError):
        phase.validate_request_identity(changed, frozen)


def test_corrected_envelope_schema_named_selection_and_base_without_poss(frozen):
    advanced = frozen[0]
    result = phase.verify_response_bytes(body(advanced), advanced, frozen)
    assert result["observed_result_set_order"] == ["Overall", "Lineups"]
    assert result["result_set_selection"] == "exact_name"
    assert result["required_fields"] == ["POSS", "NET_RATING"]
    base = frozen[1]
    result = phase.verify_response_bytes(body(base), base, frozen)
    assert result["base_poss_absent_as_expected"] is True
    assert result["required_fields"] == ["MIN", "SUM_TIME_PLAYED"]
    assert "TEAM_ID" not in contract.BASE_LINEUPS_HEADERS


def test_missing_duplicate_unexpected_malformed_reordered_and_width_rejected(frozen):
    request = frozen[0]
    cases = []
    missing = payload(request); missing["resultSets"].pop(); cases.append(missing)
    duplicate = payload(request); duplicate["resultSets"][1]["name"] = "Overall"; cases.append(duplicate)
    unexpected = payload(request); unexpected["resultSets"][1]["name"] = "Other"; cases.append(unexpected)
    malformed = payload(request); malformed["resultSets"][1] = "Lineups"; cases.append(malformed)
    reordered = payload(request); reordered["resultSets"].reverse(); cases.append(reordered)
    width = payload(request); width["resultSets"][1]["rowSet"][0].pop(); cases.append(width)
    schema = payload(request); schema["resultSets"][1]["headers"][-1] = "OTHER"; cases.append(schema)
    for value in cases:
        with pytest.raises(phase.ResponseError):
            phase.verify_response_bytes(json.dumps(value).encode(), request, frozen)


def test_advanced_required_values_team_context_pairs_duplicates_and_zero_preserved(frozen):
    request = frozen[0]
    value = payload(request, ((20, 3),))
    poss = value["resultSets"][1]["headers"].index("POSS")
    value["resultSets"][1]["rowSet"][0][poss] = 0
    result = phase.verify_response_bytes(json.dumps(value).encode(), request, frozen)
    assert result["canonical_pair_keys"] == [["3", "20"]]
    assert result["zero_possession_advanced_row_count"] == 1

    for field, bad in (("POSS", -1), ("POSS", "inf"), ("NET_RATING", "nan")):
        invalid = payload(request)
        index = invalid["resultSets"][1]["headers"].index(field)
        invalid["resultSets"][1]["rowSet"][0][index] = bad
        with pytest.raises(phase.ResponseError):
            phase.verify_response_bytes(json.dumps(invalid).encode(), request, frozen)

    mismatch = payload(request)
    mismatch["parameters"]["MeasureType"] = "Base"
    with pytest.raises(phase.ResponseError, match="MeasureType"):
        phase.verify_response_bytes(json.dumps(mismatch).encode(), request, frozen)

    duplicate = payload(request, ((20, 3), (3, 20)))
    with pytest.raises(phase.ResponseError, match="duplicate"):
        phase.verify_response_bytes(json.dumps(duplicate).encode(), request, frozen)
    malformed = payload(request)
    group_id = malformed["resultSets"][1]["headers"].index("GROUP_ID")
    malformed["resultSets"][1]["rowSet"][0][group_id] = "bad"
    with pytest.raises(phase.ResponseError, match="malformed"):
        phase.verify_response_bytes(json.dumps(malformed).encode(), request, frozen)


def test_exact_250_is_verified_not_transport_failure(frozen):
    request = frozen[0]
    pairs = tuple((index + 1, index + 1001) for index in range(250))
    result = phase.verify_response_bytes(body(request, pairs), request, frozen)
    assert result["lineups_row_count"] == 250
    assert result["exact_250"] is True


def test_session_and_transport_settings_zero_retry_one_attempt(tmp_path, frozen):
    session = phase.create_session()
    try:
        assert session.trust_env is False
        retry = session.adapters["https://"].max_retries
        assert (retry.total, retry.connect, retry.read, retry.redirect, retry.status) == (0, 0, 0, 0, 0)
    finally:
        session.close()
    request = frozen[0]
    fake = FakeSession([FakeResponse(body(request))])
    result = phase.acquire_one(request, frozen, tmp_path, fake)
    assert result["action"] == "acquired"
    url, kwargs = fake.calls[0]
    assert url == phase.URL
    assert kwargs["params"] == request["parameters"]
    assert kwargs["timeout"] == 30
    assert kwargs["allow_redirects"] is False
    assert phase.acquire_one(request, frozen, tmp_path, FakeSession([]))["action"] == "skipped_completed_verified"


def test_restart_states_mutation_and_write_once(tmp_path, frozen):
    request = frozen[0]
    paths = phase.request_paths(tmp_path / "started", request)
    phase._write_once(paths["start"], phase.serialize_json(start_record(request)))
    assert phase.classify_request_state(tmp_path / "started", request, frozen) == "started_without_outcome"
    with pytest.raises(phase.ContinuationError, match="write-once"):
        phase._write_once(paths["start"], b"again")

    complete = tmp_path / "complete"
    phase.acquire_one(request, frozen, complete, FakeSession([FakeResponse(body(request))]))
    phase.request_paths(complete, request)["verified_body"].write_bytes(b"changed")
    assert phase.classify_request_state(complete, request, frozen) == "conflicting_state"


@pytest.mark.parametrize("response", [
    FakeResponse(b"server", status=503),
    FakeResponse(b"redirect", status=302, redirect=True),
    FakeResponse(b"not-json"),
    requests.Timeout("synthetic"),
])
def test_failure_quarantines_and_does_not_retry(tmp_path, frozen, response):
    request = frozen[0]
    fake = FakeSession([response])
    with pytest.raises(phase.ContinuationError):
        phase.acquire_one(request, frozen, tmp_path, fake)
    assert len(fake.calls) == 1
    assert phase.classify_request_state(tmp_path, request, frozen) == "failed_or_quarantined"


def test_authorization_and_invocation_write_once(tmp_path, monkeypatch):
    planning, document = initialize(tmp_path, monkeypatch)
    assert len(document["network_authorized_requests"]) == 59
    before = (planning / "authorization.json").read_bytes()
    assert phase.initialize_authorization(PROJECT, planning) == document
    assert (planning / "authorization.json").read_bytes() == before
    record = phase.record_official_invocation(planning, planning / "authorization.json", ["python", "official"])
    assert record["invocation_number"] == 1
    assert record["r2b1_contract_identity"] == phase.CONTRACT_IDENTITY
    with pytest.raises(phase.ContinuationError, match="write-once"):
        phase.record_official_invocation(planning, planning / "authorization.json", ["again"])


def test_full_synthetic_execution_spacing_reconciliation_exact250_and_outputs(tmp_path, monkeypatch, frozen):
    planning, authorization = initialize(tmp_path, monkeypatch)
    phase.record_official_invocation(planning, planning / "authorization.json", ["python", "official"])
    atl_pairs = atlanta_pairs()
    pairs_250 = tuple((index + 1, index + 1001) for index in range(250))
    responses = []
    for request in frozen:
        team = request["parameters"]["TeamID"]
        if team == "1610612737":
            pairs = atl_pairs
        elif team == "1610612738":
            pairs = pairs_250
        else:
            pairs = ((1, 2), (2, 3))
        responses.append(FakeResponse(body(request, pairs)))
    session = FakeSession(responses)
    sleeps = []
    result = phase.execute_authorized_continuation(
        PROJECT, planning / "authorization.json", phase.EVIDENCE_NAMESPACE, planning,
        session_factory=lambda: session, sleeper=sleeps.append, monotonic=lambda: 100.0,
    )
    assert len(session.calls) == 59
    assert sleeps == [1.0] * 58
    assert result["summary"]["network_attempt_count"] == 59
    assert result["summary"]["atlanta_network_attempt_count"] == 0
    assert result["summary"]["classification"].startswith("CONDITIONAL PASS")
    teams = result["reconciliation"]["team_reconciliation"]
    assert len(teams) == 30
    assert teams[0]["base_source_namespace"].startswith("phase3f-r2b original")
    assert teams[0]["structural_disposition"] == "structurally_complete_non_250"
    assert teams[1]["structural_disposition"] == "exact_250_unresolved"
    assert result["reconciliation"]["global_reconciliation"]["advanced_zero_possession_rows"] == 0
    assert sorted(path.name for path in planning.iterdir()) == sorted(phase.FINAL_OUTPUT_FILES)
    exact = json.loads((planning / "exact_250_inventory.json").read_text())
    assert exact["teams"][0]["recovery_requires_separate_policy_and_authorization"] is True
    assert result["summary"]["recovery_request_count"] == 0
    assert result["summary"]["final_test_dataset_constructed"] is False
    replay = phase.reconcile(
        PROJECT,
        phase.EVIDENCE_NAMESPACE,
        authorization["network_authorized_requests"],
        frozen,
        phase._read_json(planning / "atlanta_offline_revalidation.json"),
    )
    assert replay == result["reconciliation"]


def test_base_advanced_mismatch_disposition(tmp_path, frozen):
    evidence = tmp_path / "e"
    atl_pairs = atlanta_pairs()
    for request in frozen:
        team = request["parameters"]["TeamID"]
        if team == "1610612737":
            pairs = atl_pairs
        elif team == "1610612738" and request["parameters"]["MeasureType"] == "Base":
            pairs = ((1, 2), (2, 3))
        else:
            pairs = ((1, 2),)
        phase.acquire_one(request, frozen, evidence, FakeSession([FakeResponse(body(request, pairs))]))
    offline = {
        "raw_bytes": phase.ATLANTA_RAW_BYTES,
        "raw_sha256": phase.ATLANTA_RAW_SHA256,
        "canonical_json_sha256": phase.ATLANTA_CANONICAL_SHA256,
    }
    result = phase.reconcile(PROJECT, evidence, frozen, frozen, offline)
    boston = result["team_reconciliation"][1]
    assert boston["structural_disposition"] == "base_advanced_mismatch"
    assert boston["base_only_keys"] == [["2", "3"]]
    assert boston["advanced_only_keys"] == []


def test_stop_on_first_failure_before_next_request(tmp_path, monkeypatch, frozen):
    planning, _ = initialize(tmp_path, monkeypatch)
    fake = FakeSession([requests.Timeout("synthetic"), FakeResponse(body(frozen[1]))])
    with pytest.raises(phase.ContinuationError, match="transport:Timeout"):
        phase.execute_authorized_continuation(
            PROJECT, planning / "authorization.json", phase.EVIDENCE_NAMESPACE, planning,
            session_factory=lambda: fake,
        )
    assert len(fake.calls) == 1
    assert phase.classify_request_state(phase.EVIDENCE_NAMESPACE, frozen[0], frozen) == "failed_or_quarantined"
    assert phase.classify_request_state(phase.EVIDENCE_NAMESPACE, frozen[1], frozen) == "not_started"


def test_no_positional_result_selection_or_model_dataset_capability():
    sources = [
        PROJECT / "src/pair_fit_v2/phase3f_r2b_2_protected_acquisition_continuation.py",
        PROJECT / "src/pair_fit_v2/phase3f_r2b_2_cli.py",
    ]
    forbidden_imports = {"pandas", "numpy", "sklearn", "joblib", "pickle"}
    forbidden_calls = {"fit", "fit_transform", "predict", "score", "dump", "to_csv", "to_parquet"}
    for source in sources:
        text = source.read_text(encoding="utf-8")
        tree = ast.parse(text)
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names
        }
        calls = {
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not imports & forbidden_imports
        assert not calls & forbidden_calls
        assert 'payload["resultSets"][0]' not in text
