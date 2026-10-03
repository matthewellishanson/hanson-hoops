from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3f_r2c_1_recovery_specification as r2c1


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def operational_record(**changes):
    record = {
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
        "early_base_pair_row_count": 249,
        "early_advanced_pair_row_count": 249,
        "late_base_pair_row_count": 249,
        "late_advanced_pair_row_count": 249,
        "recovered_only_count": 0,
        "full_season_only_count": 0,
        "duplicate_count": 0,
        "malformed_pair_count": 0,
        "same_player_count": 0,
        "base_only_count": 0,
        "advanced_only_count": 0,
    }
    record.update(changes)
    return record


def trigger_documents():
    return [
        json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))
        for path in (
            r2c1.R2B2_EXACT_250_PATH,
            r2c1.R2B2_REQUESTS_PATH,
            r2c1.R2B2_FINGERPRINTS_PATH,
            r2c1.R2B2_ATTEMPTS_PATH,
        )
    ]


def test_schema_is_exact_machine_readable_and_has_no_defaults():
    assert r2c1.DISPOSITION_SCHEMA["additional_properties"] is False
    assert r2c1.DISPOSITION_SCHEMA["required"] == list(r2c1.DISPOSITION_FIELDS)
    assert set(r2c1.DISPOSITION_SCHEMA["properties"]) == set(r2c1.DISPOSITION_FIELDS)
    assert all("default" not in value for value in r2c1.DISPOSITION_SCHEMA["properties"].values())


@pytest.mark.parametrize(
    "record",
    [
        {},
        {
            "full_season_evidence_authenticated": True,
            "all_four_recovery_responses_present": True,
            "all_four_recovery_responses_authenticated": True,
            "all_four_recovery_responses_structurally_valid": True,
        },
        {"recovered_only_count": 1},
    ],
)
def test_sparse_records_never_receive_favorable_defaults(record):
    decision = r2c1.evaluate_disposition(record)
    assert decision.disposition == "recovery_unresolved"
    assert decision.reason_codes


def test_missing_recovered_key_validity_is_unresolved():
    record = operational_record()
    del record["recovered_only_keys_validated"]
    decision = r2c1.evaluate_disposition(record)
    assert decision.disposition == "recovery_unresolved"
    assert decision.reason_codes == ("missing_field:recovered_only_keys_validated",)


@pytest.mark.parametrize("missing", r2c1.DISPOSITION_FIELDS)
def test_missing_each_required_field_is_unresolved(missing):
    record = operational_record()
    del record[missing]
    decision = r2c1.evaluate_disposition(record)
    assert decision.disposition == "recovery_unresolved"
    assert decision.reason_codes == (f"missing_field:{missing}",)


def test_unexpected_field_and_malformed_nested_provenance_are_unresolved():
    extra = operational_record(provenance={"source": "synthetic"})
    assert r2c1.evaluate_disposition(extra).reason_codes == ("unexpected_field:provenance",)
    nested = operational_record(full_season_evidence_authenticated={"value": True})
    assert r2c1.evaluate_disposition(nested).reason_codes == (
        "invalid_boolean_type:full_season_evidence_authenticated",
    )


@pytest.mark.parametrize("field", r2c1.COUNT_FIELDS)
@pytest.mark.parametrize("value", [True, False])
def test_boolean_is_rejected_as_every_count_field(field, value):
    record = operational_record()
    record[field] = value
    decision = r2c1.evaluate_disposition(record)
    assert decision.disposition == "recovery_unresolved"
    assert decision.reason_codes == (f"invalid_count_type:{field}",)


@pytest.mark.parametrize(
    "value,code",
    [
        (1.0, "invalid_count_type:recovered_only_count"),
        (0.0, "invalid_count_type:recovered_only_count"),
        (float("nan"), "invalid_count_type:recovered_only_count"),
        (float("inf"), "invalid_count_type:recovered_only_count"),
        (float("-inf"), "invalid_count_type:recovered_only_count"),
        (-1, "negative_count:recovered_only_count"),
        ("1", "invalid_count_type:recovered_only_count"),
        (None, "invalid_count_type:recovered_only_count"),
        ([], "invalid_count_type:recovered_only_count"),
        ({}, "invalid_count_type:recovered_only_count"),
    ],
)
def test_malformed_counts_are_unresolved_without_coercion(value, code):
    decision = r2c1.evaluate_disposition(operational_record(recovered_only_count=value))
    assert decision.disposition == "recovery_unresolved"
    assert decision.reason_codes == (code,)


@pytest.mark.parametrize("record", [None, [], "bad", 1, 1.0, True])
def test_malformed_containers_never_raise(record):
    assert r2c1.evaluate_disposition(record) == r2c1.DispositionDecision(
        "recovery_unresolved", ("record_not_mapping",)
    )
    assert r2c1.classify_disposition(record) == "recovery_unresolved"


def test_recovered_count_validity_contradiction_is_unresolved():
    record = operational_record(
        recovered_only_count=1,
        recovered_only_keys_validated=False,
        window_union_equals_full_season_keys=False,
    )
    decision = r2c1.evaluate_disposition(record)
    assert decision.disposition == "recovery_unresolved"
    assert "contradiction:recovered_count_without_validated_keys" in decision.reason_codes


@pytest.mark.parametrize("flag", ["conflicting_state", "failed_or_quarantined"])
def test_affirmative_looking_record_with_conflict_or_failure_is_unresolved(flag):
    decision = r2c1.evaluate_disposition(operational_record(**{flag: True}))
    assert decision.disposition == "recovery_unresolved"


def test_operational_record_with_250_row_window_is_unresolved():
    record = operational_record(
        early_base_pair_row_count=250,
        every_individual_window_below_250=False,
    )
    assert r2c1.classify_disposition(record) == "recovery_unresolved"


def test_positive_recovered_count_cannot_override_250_row_window():
    record = operational_record(
        recovered_only_count=1,
        window_union_equals_full_season_keys=False,
        early_base_pair_row_count=250,
        every_individual_window_below_250=False,
    )
    decision = r2c1.evaluate_disposition(record)
    assert decision.disposition == "recovery_unresolved"
    assert "window_response_not_below_250" in decision.reason_codes


def test_operational_record_with_full_season_only_keys_is_unresolved():
    record = operational_record(
        full_season_only_count=1,
        window_union_equals_full_season_keys=False,
    )
    assert r2c1.classify_disposition(record) == "recovery_unresolved"


def test_operational_record_with_base_advanced_mismatch_is_unresolved():
    record = operational_record(early_base_advanced_keys_equal=False, base_only_count=1)
    assert r2c1.classify_disposition(record) == "recovery_unresolved"


def test_valid_examples_for_all_three_dispositions():
    operational = r2c1.evaluate_disposition(operational_record())
    assert operational.disposition == "operationally_resolved_no_observed_omission"
    assert operational.reason_codes == ("all_operational_resolution_conditions_satisfied",)

    proven = r2c1.evaluate_disposition(
        operational_record(recovered_only_count=1, window_union_equals_full_season_keys=False)
    )
    assert proven.disposition == "proven_non_exhaustive"
    assert proven.reason_codes == ("validated_recovered_only_keys_present",)

    unresolved = r2c1.evaluate_disposition(
        operational_record(full_season_evidence_authenticated=False)
    )
    assert unresolved.disposition == "recovery_unresolved"
    assert unresolved.reason_codes == (
        "required_true_for_operational_resolution:full_season_evidence_authenticated",
    )


def transport_project(tmp_path):
    target = tmp_path / r2c1.R2B21_TRANSPORT_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes((PROJECT_ROOT / r2c1.R2B21_TRANSPORT_PATH).read_bytes())
    return tmp_path


def valid_transport_binding():
    return {"path": r2c1.R2B21_TRANSPORT_PATH_TEXT, "sha256": r2c1.R2B21_TRANSPORT_SHA256}


def test_exact_transport_path_and_hash_are_authenticated(tmp_path):
    assert r2c1.validate_transport_contract(transport_project(tmp_path), valid_transport_binding()) == valid_transport_binding()


@pytest.mark.parametrize(
    "mutation",
    [
        "altered_path",
        "altered_hash",
        "missing_path",
        "path_traversal",
        "absolute_path",
        "case_altered_path",
    ],
)
def test_transport_binding_rejects_every_path_or_hash_substitution(tmp_path, mutation):
    root = transport_project(tmp_path)
    binding = valid_transport_binding()
    if mutation == "altered_path":
        binding["path"] = "planning/alternate/future_protected_transport_contract.json"
    elif mutation == "altered_hash":
        binding["sha256"] = "0" * 64
    elif mutation == "missing_path":
        del binding["path"]
    elif mutation == "path_traversal":
        binding["path"] = "planning/phase3f-r2b.2.1/../phase3f-r2b.2.1/future_protected_transport_contract.json"
    elif mutation == "absolute_path":
        binding["path"] = str((root / r2c1.R2B21_TRANSPORT_PATH).resolve())
    else:
        binding["path"] = "Planning/phase3f-r2b.2.1/future_protected_transport_contract.json"
    with pytest.raises(r2c1.CorrectionError):
        r2c1.validate_transport_contract(root, binding)


def test_missing_transport_file_is_rejected(tmp_path):
    with pytest.raises(r2c1.CorrectionError, match="missing"):
        r2c1.validate_transport_contract(tmp_path, valid_transport_binding())


def test_transport_file_with_recomputed_hash_mismatch_is_rejected(tmp_path):
    target = tmp_path / r2c1.R2B21_TRANSPORT_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(b"changed")
    with pytest.raises(r2c1.CorrectionError, match="recomputed"):
        r2c1.validate_transport_contract(tmp_path, valid_transport_binding())


def test_trigger_metadata_authenticates_bytes_hashes_state_and_250_rows():
    result = r2c1.validate_trigger_documents(*trigger_documents())
    assert result == [dict(item) for item in r2c1.TRIGGERS]


@pytest.mark.parametrize("mutation", ["altered_bytes", "missing_bytes", "wrong_type"])
def test_trigger_bytes_are_mandatory_and_exact_even_when_hashes_are_unchanged(mutation):
    documents = copy.deepcopy(trigger_documents())
    fingerprint = next(item for item in documents[2] if item["ordinal"] == 35)
    if mutation == "altered_bytes":
        fingerprint["raw_bytes"] = 1
    elif mutation == "missing_bytes":
        del fingerprint["raw_bytes"]
    else:
        fingerprint["raw_bytes"] = "65800"
    with pytest.raises(r2c1.CorrectionError, match="fingerprint"):
        r2c1.validate_trigger_documents(*documents)


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "failed"),
        ("row_count", 249),
        ("team_id", "1610612755"),
        ("measure", "Base"),
        ("byte_count", 1),
    ],
)
def test_trigger_attempt_metadata_is_exact(field, value):
    documents = copy.deepcopy(trigger_documents())
    attempt = next(item for item in documents[3] if item["ordinal"] == 36)
    attempt[field] = value
    with pytest.raises(r2c1.CorrectionError, match="attempt"):
        r2c1.validate_trigger_documents(*documents)


def test_public_source_is_reused_by_exact_inventory_linkage_bytes_and_hash():
    source = r2c1.authenticate_public_source(PROJECT_ROOT)
    assert source["reuse_only_no_request"] is True
    assert source["body_bytes"] == 126_442
    assert source["raw_sha256"] == r2c1.PUBLIC_BODY_SHA256
    assert source["season_start"] == "2025-10-21"
    assert source["season_end"] == "2026-04-12"


def test_original_r2c_and_all_historical_namespaces_are_authenticated_opaquely():
    result = r2c1.authenticate_original_and_historical(PROJECT_ROOT)
    assert len(result["original_r2c_git_visible"]) == 5
    assert result["original_r2c_planning"]["file_count"] == 3
    assert [item["file_count"] for item in result["r2b_historical_namespaces"]] == [2, 5, 14, 5, 4, 295]


def test_response_contract_identity_and_transport_path_are_in_corrected_plan(tmp_path):
    artifacts = r2c1.build_artifacts(PROJECT_ROOT, tmp_path / "absent")
    plan = json.loads(artifacts["corrected_recovery_plan.json"])
    contracts = plan["governing_contracts"]
    assert contracts["r2b1_response_contract"]["identity"] == r2c1.R2B1_CONTRACT_IDENTITY
    assert contracts["r2b21_future_protected_transport_contract"] == valid_transport_binding()


def test_plan_preserves_exact_eight_science_and_request_identities(tmp_path):
    plan = json.loads(r2c1.build_artifacts(PROJECT_ROOT, tmp_path / "absent")["corrected_recovery_plan.json"])
    assert plan["correction_scope"]["original_r2c_audit_status"] == "failed"
    assert plan["correction_scope"]["supersedes_original_r2c_for_future_recovery_authorization"] is True
    assert plan["correction_scope"]["neither_r2c_nor_r2c_1_authorizes_acquisition"] is True
    assert len(plan["future_recovery_identities"]) == 8
    assert plan["population_reconciliation"]["scope"] == "population-only"
    assert plan["population_reconciliation"]["rating_aggregation"] is False
    assert plan["population_reconciliation"]["target_reconstruction"] is False


def test_summary_has_exact_zero_operation_and_blocked_readiness_accounting(tmp_path):
    summary = json.loads(r2c1.build_artifacts(PROJECT_ROOT, tmp_path / "absent")["summary.json"])
    assert summary["network_requests"] == 0
    assert summary["public_source_reuse_only"] is True
    assert summary["protected_requests"] == summary["recovery_requests"] == 0
    assert summary["final_test_rows"] == summary["estimator_operations"] == 0
    assert summary["original_r2c_audit_status"] == "failed"
    assert set(summary["team_status"].values()) == {"exact_250_unresolved"}
    assert summary["final_test_readiness"] == "blocked on recovery and later audited gates"


def test_write_once_dual_build_exact_inventory_and_finite_json(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    r2c1.write_specification(PROJECT_ROOT, left)
    r2c1.write_specification(PROJECT_ROOT, right)
    left_bytes = {path.name: path.read_bytes() for path in left.iterdir()}
    right_bytes = {path.name: path.read_bytes() for path in right.iterdir()}
    assert left_bytes == right_bytes
    assert set(left_bytes) == set(r2c1.OUTPUT_FILES)
    for raw in left_bytes.values():
        assert json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    with pytest.raises(r2c1.CorrectionError, match="already exists"):
        r2c1.write_specification(PROJECT_ROOT, left)
    partial = tmp_path / "partial"
    partial.mkdir()
    with pytest.raises(r2c1.CorrectionError, match="partial"):
        r2c1.write_specification(PROJECT_ROOT, partial)


def test_manifest_hashes_exact_payload_bytes(tmp_path):
    artifacts = r2c1.build_artifacts(PROJECT_ROOT, tmp_path / "absent")
    manifest = json.loads(artifacts["artifact_hashes.json"])
    assert manifest["artifact_inventory"] == list(r2c1.OUTPUT_FILES)
    for name, expected in manifest["artifacts"].items():
        raw = artifacts[name]
        assert expected == {"bytes": len(raw), "sha256": r2c1.sha256_bytes(raw)}


def test_historical_r2b1_metadata_current_equivalent_without_body_parsing():
    summary = json.loads((PROJECT_ROOT / "planning/phase3f-r2b.1/summary.json").read_text(encoding="utf-8"))
    continuation = json.loads((PROJECT_ROOT / "planning/phase3f-r2b.1/continuation_plan.json").read_text(encoding="utf-8"))
    assert summary["original_r2b_status"].startswith("FAILED")
    assert summary["atlanta_remains_quarantined"] is True
    assert continuation["atlanta_base"]["network_eligible"] is False
    assert continuation["remaining_request_count"] == 59
    assert continuation["contains_executable_network_authorization"] is False


def test_historical_r2b2_metadata_current_equivalent_without_body_parsing():
    authorization = json.loads((PROJECT_ROOT / "planning/phase3f-r2b.2/authorization.json").read_text(encoding="utf-8"))
    attempts = json.loads((PROJECT_ROOT / r2c1.R2B2_ATTEMPTS_PATH).read_text(encoding="utf-8"))
    exact = json.loads((PROJECT_ROOT / r2c1.R2B2_EXACT_250_PATH).read_text(encoding="utf-8"))
    requests = authorization["network_authorized_requests"]
    assert len(requests) == 59
    assert [item["ordinal"] for item in requests] == list(range(2, 61))
    assert all(item["currently_network_authorized"] is False for item in requests)
    assert len(attempts) == 59
    assert [item["team_id"] for item in exact["teams"]] == ["1610612754", "1610612763"]
    assert all(item["structural_disposition"] == "exact_250_unresolved" for item in exact["teams"])


def test_historical_r2b21_metadata_current_equivalent_without_body_parsing():
    closure = json.loads((PROJECT_ROOT / "planning/phase3f-r2b.2.1/procedural_closure.json").read_text(encoding="utf-8"))
    summary = json.loads((PROJECT_ROOT / "planning/phase3f-r2b.2.1/summary.json").read_text(encoding="utf-8"))
    assert [item["team_id"] for item in closure["unresolved_teams"]] == ["1610612754", "1610612763"]
    assert closure["phase_boundary"]["recovery_request_identities_created"] == 0
    assert closure["phase_boundary"]["network_authorization_count"] == 0
    assert summary["network_requests"] == 0


def test_current_git_visible_allowlist_and_ignore_behavior():
    expected = {
        ".gitignore",
        "PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_POLICY.md",
        "PHASE3F_R2C_EXACT_250_RECOVERY_SPECIFICATION_REPORT.md",
        "PHASE3F_R2C_1_RECOVERY_SPECIFICATION_CORRECTION_POLICY.md",
        "PHASE3F_R2C_1_RECOVERY_SPECIFICATION_CORRECTION_REPORT.md",
        "src/pair_fit_v2/phase3f_r2c_recovery_specification.py",
        "src/pair_fit_v2/phase3f_r2c_cli.py",
        "src/pair_fit_v2/phase3f_r2c_1_recovery_specification.py",
        "src/pair_fit_v2/phase3f_r2c_1_cli.py",
        "tests/test_phase3f_r2c_recovery_specification.py",
        "tests/test_phase3f_r2c_1_recovery_specification.py",
    }
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    observed = {line[3:].replace("\\", "/").removeprefix("research/pair-fit-v2/") for line in result.stdout.splitlines()}
    assert observed == expected
    for probe in ("planning/phase3f-r2c/x", "planning/phase3f-r2c.1/x"):
        ignored = subprocess.run(["git", "check-ignore", "-q", probe], cwd=PROJECT_ROOT, check=False)
        assert ignored.returncode == 0


def test_static_scope_has_no_network_protected_parser_model_or_dataset_capability():
    sources = [
        PROJECT_ROOT / "src/pair_fit_v2/phase3f_r2c_1_recovery_specification.py",
        PROJECT_ROOT / "src/pair_fit_v2/phase3f_r2c_1_cli.py",
    ]
    forbidden_imports = {
        "requests", "urllib", "httpx", "aiohttp", "socket", "sklearn", "numpy",
        "pandas", "joblib", "pickle", "sqlite3", "duckdb",
    }
    forbidden_calls = {
        "post", "request", "fit", "fit_predict", "predict", "score",
        "dump", "to_csv", "to_parquet",
    }
    for source in sources:
        text = source.read_text(encoding="utf-8")
        tree = ast.parse(text)
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names
        }
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not imports & forbidden_imports
        assert not calls & forbidden_calls
        assert "pair_fit_v2.phase3f_r2c_recovery_specification" not in imported_modules
        assert "resultSets" not in text
        assert "HMAC" not in text and "credential" not in text.lower()
