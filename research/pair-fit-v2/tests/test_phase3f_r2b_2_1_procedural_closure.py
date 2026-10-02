import ast
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3f_r2b_2_1_procedural_closure as phase


PROJECT = Path(__file__).resolve().parents[1]


def request():
    return {
        "request_id": "teamdashlineups:1610612754:base:window-a",
        "endpoint": "teamdashlineups",
        "parameters": {
            "TeamID": "1610612754",
            "MeasureType": "Base",
            "Season": "2025-26",
            "DateFrom": "synthetic-a",
            "DateTo": "synthetic-b",
        },
    }


def future_document(tmp_path, *, source_file=None):
    normalized = phase.normalize_future_request(request(), "synthetic-future-phase", 1)
    planning = (tmp_path / "planning").resolve()
    evidence = (tmp_path / "evidence").resolve()
    source = (tmp_path / "source-evidence").resolve()
    for path in (planning, evidence, source):
        path.mkdir(parents=True, exist_ok=True)
    document = {
        "authorization_phase": "synthetic-future-phase",
        "attempt_limit_per_identity": 1,
        "authorized_inventory": [deepcopy(normalized["authorization"])],
        "requests": [normalized],
        "canonical_namespaces": {
            "planning": str(planning),
            "evidence": str(evidence),
            "source_evidence": str(source),
        },
    }
    if source_file is None:
        source_file = tmp_path / "controller.py"
        source_file.write_text("VALUE = 1\n", encoding="utf-8")
    return document, planning, evidence, source, source_file


def test_pinned_r2b_r2b1_r2b2_evidence_and_structural_state():
    values = phase.verify_inputs(PROJECT)
    assert len(values["r2b2_artifacts"]) == 14
    assert len(values["protected_response_bodies"]) == 59
    assert values["atlanta_body"] == {
        "path": phase.ATLANTA_BODY.as_posix(),
        "bytes": phase.ATLANTA_BYTES,
        "sha256": phase.ATLANTA_SHA256,
    }
    assert values["historical_pacing"]["scientific_materiality"] == "nil"
    assert values["r2b2_current_source_observation"]["historical_executing_hash_persisted"] is False
    assert values["unexpected_recovery_or_alternate_namespaces"] == []


def test_r2b2_authorization_ambiguity_detected_without_mutation():
    before = (PROJECT / phase.R2B2_PLANNING / "authorization.json").read_bytes()
    authorization = json.loads(before)
    requests = authorization["network_authorized_requests"]
    assert len(requests) == 59
    assert [item["ordinal"] for item in requests] == list(range(2, 61))
    assert all(item["currently_network_authorized"] is False for item in requests)
    assert all(
        item["may_become_eligible_only_in_later_separately_authorized_phase"] is True
        for item in requests
    )
    phase.verify_inputs(PROJECT)
    assert (PROJECT / phase.R2B2_PLANNING / "authorization.json").read_bytes() == before


def test_normalized_future_per_request_authorization_schema():
    normalized = phase.normalize_future_request(request(), "future-phase", 7)
    authorization = normalized["authorization"]
    assert tuple(authorization) == phase.PHASE_LOCAL_AUTHORIZATION_FIELDS
    assert authorization == {
        "authorization_phase": "future-phase",
        "network_authorized": True,
        "attempt_limit": 1,
        "ordinal": 7,
        "request_id": request()["request_id"],
        "canonical_request_identity": phase.request_identity(request()),
    }
    assert not set(phase.STALE_AUTHORIZATION_FIELDS) & set(normalized)


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("request_authorization", "network_authorized", False),
        ("request_authorization", "attempt_limit", 2),
        ("request_authorization", "ordinal", 2),
        ("request_authorization", "request_id", "different"),
        ("request_authorization", "canonical_request_identity", "0" * 64),
        ("top", "attempt_limit_per_identity", 2),
    ],
)
def test_top_level_per_request_disagreement_rejected(tmp_path, target, field, value):
    document, *_ = future_document(tmp_path)
    if target == "top":
        document[field] = value
    else:
        document["requests"][0]["authorization"][field] = value
    with pytest.raises(phase.ClosureError):
        phase.validate_future_authorization(document)


def test_stale_inherited_authorization_fields_rejected(tmp_path):
    document, *_ = future_document(tmp_path)
    document["requests"][0]["currently_network_authorized"] = False
    with pytest.raises(phase.ClosureError, match="inherited"):
        phase.validate_future_authorization(document)


def test_exact_namespace_binding_and_alternate_roots_refused(tmp_path):
    document, planning, evidence, source, _ = future_document(tmp_path)
    observed = phase.validate_namespace_binding(
        document, planning_dir=planning, evidence_dir=evidence, source_evidence=source
    )
    assert observed == document["canonical_namespaces"]
    alternate_planning = (tmp_path / "alternate-planning").resolve()
    alternate_planning.mkdir()
    with pytest.raises(phase.ClosureError, match="differs"):
        phase.validate_namespace_binding(
            document,
            planning_dir=alternate_planning,
            evidence_dir=evidence,
            source_evidence=source,
        )
    alternate_evidence = (tmp_path / "alternate-evidence").resolve()
    alternate_evidence.mkdir()
    with pytest.raises(phase.ClosureError, match="differs"):
        phase.validate_namespace_binding(
            document,
            planning_dir=planning,
            evidence_dir=alternate_evidence,
            source_evidence=source,
        )


def test_relative_and_path_normalization_aliases_refused(tmp_path):
    with pytest.raises(phase.ClosureError, match="absolute"):
        phase.canonical_namespace_path(Path("relative/planning"))
    aliased = tmp_path.resolve() / "planning" / ".." / "planning"
    with pytest.raises(phase.ClosureError, match="normalization"):
        phase.canonical_namespace_path(aliased)


def test_source_hash_pinning_mismatch_and_future_invocation_inventory(tmp_path):
    document, planning, evidence, source, controller = future_document(tmp_path)
    inventory = phase.fingerprint_source_inventory([controller])
    assert phase.validate_source_inventory(inventory) == inventory
    record = phase.future_invocation_record(
        document,
        planning_dir=planning,
        evidence_dir=evidence,
        source_evidence=source,
        source_inventory=inventory,
        command=["python", "future_cli.py", "acquire"],
        python_executable="python",
        working_directory=str(tmp_path),
        pythonpath=str(tmp_path / "src"),
    )
    assert record["verified_source_inventory"] == inventory
    assert record["command"][-1] == "acquire"
    assert record["verified_canonical_namespaces"] == document["canonical_namespaces"]
    controller.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(phase.ClosureError, match="source identity mismatch"):
        phase.validate_source_inventory(inventory)


def test_monotonic_gap_sleep_remainder_and_persisted_fields():
    values = iter([10.25, 11.0])
    sleeps = []
    pacing = phase.enforce_monotonic_pacing(
        10.0,
        1.0,
        monotonic=lambda: next(values),
        sleeper=sleeps.append,
        utc_start="2026-01-01T00:00:01Z",
    )
    assert sleeps == [0.75]
    assert pacing["calculated_pre_attempt_gap_seconds"] == 0.25
    assert pacing["requested_sleep_duration_seconds"] == 0.75
    assert pacing["observed_post_sleep_monotonic_gap_seconds"] == 1.0
    assert pacing["enforcement_clock"] == "process_monotonic"
    assert pacing["utc_role"] == "audit_context_only"
    complete = phase.complete_timing_record(
        pacing, utc_completion="2026-01-01T00:00:02Z", monotonic_completion=11.5
    )
    assert tuple(complete) == phase.PACING_FIELDS
    assert complete["process_monotonic_completion"] == 11.5
    assert complete["utc_completion"] == "2026-01-01T00:00:02Z"


def test_insufficient_post_sleep_monotonic_gap_refused():
    values = iter([20.25, 20.9])
    with pytest.raises(phase.ClosureError, match="remains below"):
        phase.enforce_monotonic_pacing(
            20.0,
            1.0,
            monotonic=lambda: next(values),
            sleeper=lambda _: None,
            utc_start="audit-only",
        )


def test_historical_pacing_limitation_exact_wording_and_values():
    values = phase.verify_inputs(PROJECT)["historical_pacing"]
    assert values["utc_completion_to_next_start"] == {
        "count": 58,
        "minimum_seconds": 0.986753,
        "maximum_seconds": 1.011286,
        "average_seconds": 1.002996,
        "below_one_second_count": 3,
    }
    assert values["utc_start_to_next_start_minimum_seconds"] == 1.248367
    assert values["utc_completion_to_next_completion_minimum_seconds"] == 1.247101
    assert values["genuine_spacing_violation_established"] is False
    assert values["exact_completion_to_start_compliance"] == "strongly supported but not proved"


def test_indiana_memphis_remain_unresolved_with_no_recovery_identity():
    values = phase._procedural_closure(phase.verify_inputs(PROJECT))
    teams = values["unresolved_teams"]
    assert [item["team_id"] for item in teams] == ["1610612754", "1610612763"]
    assert all(item["base"]["rows"] == item["advanced"]["rows"] == 250 for item in teams)
    assert all(item["base_advanced_key_equality"] is True for item in teams)
    assert all(item["disposition"] == "exact_250_unresolved" for item in teams)
    assert values["phase_boundary"]["recovery_request_identities_created"] == 0
    assert values["phase_boundary"]["network_authorization_count"] == 0


def test_future_recovery_boundary_has_no_dates_or_request_identities():
    contract = phase._future_contract()
    frozen = contract["possible_future_recovery_specification_must_freeze"]
    assert "exact season-boundary dates" in frozen
    assert "Base and Advanced request identities for each window" in frozen
    assert contract["not_selected_or_created_here"] == {
        "recovery_dates": True,
        "recovery_request_identities": True,
        "recovery_authorization": True,
        "final_test_population": True,
    }


def test_deterministic_build_and_write_once_refusal(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    result = phase.build_procedural_closure(PROJECT, first)
    assert result["classification"] == phase.CLASSIFICATION
    phase.build_procedural_closure(PROJECT, second)
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }
    assert sorted(path.name for path in first.iterdir()) == sorted(phase.OUTPUT_FILES)
    with pytest.raises(phase.ClosureError, match="already exists"):
        phase.build_procedural_closure(PROJECT, first)
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(phase.ClosureError, match="already exists"):
        phase.build_procedural_closure(PROJECT, partial)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(phase.ClosureError, match="already exists"):
        phase.build_procedural_closure(PROJECT, empty)


def test_generated_json_is_finite_and_hash_manifest_is_correct(tmp_path):
    output = tmp_path / "closure"
    phase.build_procedural_closure(PROJECT, output)
    for path in output.iterdir():
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        assert value is not None
    manifest = json.loads((output / "artifact_hashes.json").read_text(encoding="utf-8"))
    assert set(manifest["sha256"]) == set(phase.OUTPUT_FILES) - {"artifact_hashes.json"}
    for name, digest in manifest["sha256"].items():
        assert phase.sha256_bytes((output / name).read_bytes()) == digest


def test_zero_network_final_test_and_model_capability():
    sources = [
        PROJECT / "src/pair_fit_v2/phase3f_r2b_2_1_procedural_closure.py",
        PROJECT / "src/pair_fit_v2/phase3f_r2b_2_1_cli.py",
    ]
    forbidden_imports = {
        "requests", "urllib", "httpx", "aiohttp", "socket", "pandas", "numpy",
        "sklearn", "joblib", "pickle",
    }
    forbidden_calls = {
        "post", "request", "urlopen", "fit", "fit_transform", "predict",
        "score", "to_csv", "to_parquet", "dump",
    }
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
        text = source.read_text(encoding="utf-8").lower()
        assert "https://" not in text
        assert "http://" not in text
