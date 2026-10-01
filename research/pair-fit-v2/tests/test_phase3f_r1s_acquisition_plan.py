import ast
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3f_r1s_acquisition_plan as phase


PROJECT = Path(__file__).resolve().parents[1]


def test_exact_protected_count_team_and_measure_order():
    requests = phase.plan_document()["protected_requests"]
    assert len(requests) == 60
    assert [requests[index]["parameters"]["TeamID"] for index in range(0, 60, 2)] == list(phase.TEAM_IDS)
    assert all(
        [requests[index]["parameters"]["MeasureType"], requests[index + 1]["parameters"]["MeasureType"]]
        == ["Base", "Advanced"]
        for index in range(0, 60, 2)
    )


def test_exact_two_missing_non_protected_dependencies():
    dependencies = phase.plan_document()["missing_non_protected_dependencies"]
    assert len(dependencies) == 2
    assert [item["parameters"]["PerMode"] for item in dependencies] == ["Per100Possessions", "Totals"]
    assert all(item["status"] == "missing_not_acquired" for item in dependencies)


def test_duplicate_rejected():
    plan = phase.plan_document()
    plan["protected_requests"][-1] = deepcopy(plan["protected_requests"][0])
    with pytest.raises(phase.PlanError, match="duplicate"):
        phase.validate_plan(plan)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Season", "2024-25"),
        ("TeamID", "999"),
        ("MeasureType", "Four Factors"),
        ("PerMode", "PerGame"),
        ("DateFrom", "01/01/2026"),
    ],
)
def test_unauthorized_protected_parameter_rejected(field, value):
    plan = phase.plan_document()
    plan["protected_requests"][0]["parameters"][field] = value
    with pytest.raises(phase.PlanError, match="ordering or parameters"):
        phase.validate_plan(plan)


def test_unauthorized_endpoint_rejected():
    plan = phase.plan_document()
    plan["protected_requests"][0]["endpoint"] = "leaguedashlineups"
    with pytest.raises(phase.PlanError, match="ordering or parameters"):
        phase.validate_plan(plan)


def test_namespaces_are_separate():
    plan = phase.plan_document()
    assert len(set(plan["namespaces"].values())) == 3
    assert {item["namespace"] for item in plan["protected_requests"]} == {phase.PROTECTED_NAMESPACE}
    assert {item["namespace"] for item in plan["missing_non_protected_dependencies"]} == {phase.DEPENDENCY_NAMESPACE}


def test_no_executable_recovery_and_exact_250_is_unresolved():
    exact = phase.plan_document()["exact_250"]
    assert exact["status"] == "unresolved_warning"
    assert exact["recovery_requests"] == []
    assert exact["automatic_exclusion"] is exact["automatic_recovery"] is False


def test_restart_state_definitions_are_exact():
    states = phase.plan_document()["restart_states"]
    assert states == {
        "not_started": "eligible for its one authorized attempt",
        "completed_verified": "re-hash, verify, and skip",
        "started_without_outcome": "stop for read-only investigation",
        "failed_or_quarantined": "preserve evidence and stop",
        "conflicting_state": "refuse progress and stop",
    }


def _readiness_states(default="passed"):
    return {gate: default for gate in phase.READINESS_GATES}


def test_all_frozen_readiness_gates_audit_and_user_authorization_are_required():
    states = _readiness_states()
    assert phase.final_execution_authorized(
        states,
        readiness_checkpoint_audit_cleared=True,
        user_one_time_execution_authorized=True,
    ) is True
    assert phase.plan_document()["final_execution_boundary"]["frozen_readiness_gates"] == list(
        phase.READINESS_GATES
    )
    assert len(phase.READINESS_GATES) == 6


@pytest.mark.parametrize("blocking_state", ["failed", "unresolved"])
def test_failed_or_unresolved_readiness_gate_blocks_execution(blocking_state):
    states = _readiness_states()
    states[phase.READINESS_GATES[0]] = blocking_state
    assert phase.final_execution_authorized(
        states,
        readiness_checkpoint_audit_cleared=True,
        user_one_time_execution_authorized=True,
    ) is False


def test_audit_clearance_alone_is_insufficient():
    assert phase.final_execution_authorized(
        _readiness_states(),
        readiness_checkpoint_audit_cleared=True,
        user_one_time_execution_authorized=False,
    ) is False


def test_user_authorization_alone_is_insufficient():
    assert phase.final_execution_authorized(
        _readiness_states(),
        readiness_checkpoint_audit_cleared=False,
        user_one_time_execution_authorized=True,
    ) is False


def test_acquisition_completion_alone_is_insufficient():
    separation = phase.plan_document()["stage_separation"]
    assert separation["acquisition"] == (
        "acquisition completion does not authorize final-test construction"
    )
    assert separation["acquisition_completion"] == (
        "no model execution is authorized merely because evidence acquisition completed"
    )
    assert phase.final_execution_authorized(
        _readiness_states("unresolved"),
        readiness_checkpoint_audit_cleared=False,
        user_one_time_execution_authorized=False,
    ) is False


def test_policy_and_plan_represent_the_same_three_execution_conditions():
    policy = (PROJECT / "PHASE3F_R1S_SIMPLIFIED_ACQUISITION_POLICY.md").read_text(
        encoding="utf-8"
    )
    assert "every frozen Phase 3F final-test readiness gate passes" in policy
    assert "the completed readiness checkpoint receives read-only audit clearance" in policy
    assert "the user separately authorizes the one-time final model execution" in policy
    boundary = phase.plan_document()["final_execution_boundary"]
    assert boundary["required_conditions"] == list(
        phase.FINAL_EXECUTION_REQUIRED_CONDITIONS
    )
    assert boundary["authorization_rule"] == "all three required conditions must be true"


def test_deterministic_serialization():
    assert phase.serialize_json(phase.plan_document()) == phase.serialize_json(phase.plan_document())


def test_two_builds_are_byte_identical(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    assert phase.build(PROJECT, left) == phase.build(PROJECT, right)
    assert {item.name for item in left.iterdir()} == set(phase.OUTPUT_FILES)
    for name in phase.OUTPUT_FILES:
        assert (left / name).read_bytes() == (right / name).read_bytes()


def test_write_once_namespace_refusal(tmp_path):
    output = tmp_path / "plan"
    phase.build(PROJECT, output)
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(phase.PlanError, match="write-once"):
        phase.build(PROJECT, output)
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}


def test_partial_namespace_refusal_preserves_existing_bytes(tmp_path):
    output = tmp_path / "partial"
    output.mkdir()
    marker = output / "acquisition_plan.json"
    marker.write_bytes(b"partial correction evidence")
    with pytest.raises(phase.PlanError, match="write-once"):
        phase.build(PROJECT, output)
    assert list(output.iterdir()) == [marker]
    assert marker.read_bytes() == b"partial correction evidence"


def test_generated_hash_inventory(tmp_path):
    output = tmp_path / "plan"
    summary = phase.build(PROJECT, output)
    hashes = json.loads((output / "artifact_hashes.json").read_text(encoding="utf-8"))
    assert summary["protected_request_count"] == 60
    assert hashes["artifact_inventory"] == list(phase.OUTPUT_FILES)
    assert set(hashes["sha256"]) == {"acquisition_plan.json", "summary.json"}
    for name, expected in hashes["sha256"].items():
        assert phase.sha256_bytes((output / name).read_bytes()) == expected


def test_no_network_or_model_capability_imports_or_calls():
    sources = [
        PROJECT / "src/pair_fit_v2/phase3f_r1s_acquisition_plan.py",
        PROJECT / "src/pair_fit_v2/phase3f_r1s_cli.py",
    ]
    forbidden_imports = {"requests", "httpx", "urllib", "socket", "aiohttp", "sklearn", "numpy", "pandas", "joblib", "pickle"}
    forbidden_calls = {"fit", "fit_transform", "predict", "score", "request", "post", "urlopen"}
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


def test_real_protected_cache_path_rejected_before_read(monkeypatch):
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("forbidden path was opened"))
    candidate = PROJECT / "cache" / "2025-26" / "response.json"
    with pytest.raises(phase.PlanError, match="protected or cache"):
        phase.validate_planning_input_path(PROJECT, candidate)


def test_source_pins_and_scope_validate():
    plan = phase.plan_document()
    phase.validate_plan(plan)
    assert len(plan["source_pins"]) == 14
    assert plan["scope"]["network_requests_authorized"] is False
    assert plan["scope"]["protected_evidence_access_authorized"] is False
    assert plan["scope"]["model_execution_authorized"] is False
