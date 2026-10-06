from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import pair_fit_v2.phase3f_r2d_1_response_echo_contract as module
from pair_fit_v2.phase3f_r2d_1_response_echo_contract import (
    EchoContractError,
    OUTPUT_FILES,
    build_specification,
    compare_response_echo,
    strict_json_bytes,
)


ROOT = Path(__file__).resolve().parents[1]
BODY_PATH = ROOT / module.QUARANTINED_RESPONSE
AUTHORIZATION_PATH = ROOT / module.R2D_AUTHORIZATION
R2C1_PLAN_PATH = ROOT / module.R2C1_PLAN


@pytest.fixture(scope="module")
def authorization():
    return strict_json_bytes(AUTHORIZATION_PATH.read_bytes())


@pytest.fixture(scope="module")
def r2c1_plan():
    return strict_json_bytes(R2C1_PLAN_PATH.read_bytes())


@pytest.fixture(scope="module")
def frozen_request(authorization):
    return authorization["authorized_requests"][0]


@pytest.fixture(scope="module")
def payload():
    return strict_json_bytes(BODY_PATH.read_bytes())


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    destination = tmp_path_factory.mktemp("r2d1-built") / "official-shape"
    result = build_specification(ROOT, destination)
    return destination, result


def _echo(frozen_request, **changes):
    returned = dict(frozen_request["parameters"])
    returned.update(changes)
    return returned


@pytest.mark.parametrize(
    ("sent", "echoed", "passed", "reason"),
    [
        ("2025-10-21", "2025-10-21", True, "EXACT_ISO_DATE_MATCH"),
        ("2025-10-21", "10/21/2025", True, "STRICT_DATE_NORMALIZATION_EQUIVALENT"),
        ("2026-01-31", "01/31/2026", True, "STRICT_DATE_NORMALIZATION_EQUIVALENT"),
        ("2025-10-21", "10/22/2025", False, "DATE_CALENDAR_DAY_MISMATCH"),
        ("2025-02-28", "02/29/2025", False, "DATE_INVALID_CALENDAR_VALUE"),
        ("2025-10-21", "13/21/2025", False, "DATE_INVALID_CALENDAR_VALUE"),
        ("2025-10-21", "10/1/2025", False, "ECHO_DATE_FORMAT_NOT_ALLOWED"),
        ("2025-10-21", " 10/21/2025", False, "ECHO_DATE_FORMAT_NOT_ALLOWED"),
        ("2025-10-21", "2025-10-21T00:00:00", False, "ECHO_DATE_FORMAT_NOT_ALLOWED"),
        ("2025-10-21", "2025-10-21Z", False, "ECHO_DATE_FORMAT_NOT_ALLOWED"),
        ("2025-10-21", "10-21-2025", False, "ECHO_DATE_FORMAT_NOT_ALLOWED"),
        ("2025-10-21", None, False, "DATE_NON_STRING"),
        ("2025-10-21", "", False, "ECHO_DATE_FORMAT_NOT_ALLOWED"),
        ("2025-10-21", 20251021, False, "DATE_NON_STRING"),
    ],
)
def test_strict_date_equivalence(frozen_request, sent, echoed, passed, reason):
    sent_parameters = dict(frozen_request["parameters"])
    returned = _echo(frozen_request, DateFrom=echoed)
    sent_parameters["DateFrom"] = sent
    result = compare_response_echo(sent_parameters, returned)
    field = next(item for item in result["fields"] if item["field"] == "DateFrom")
    assert field["equivalent"] is passed
    assert field["reason_code"] == reason


def test_missing_date_field_is_reported(frozen_request):
    returned = _echo(frozen_request)
    returned.pop("DateFrom")
    result = compare_response_echo(frozen_request["parameters"], returned)
    assert result["passed"] is False
    assert result["missing_expected_fields"] == ["DateFrom"]
    assert result["mismatches"][0]["reason_code"] == "MISSING_ECHOED_FIELD"


def test_date_rule_is_limited_to_two_date_fields(frozen_request):
    returned = _echo(frozen_request, Season="10/21/2025")
    result = compare_response_echo(frozen_request["parameters"], returned)
    season = next(item for item in result["fields"] if item["field"] == "Season")
    assert season["comparison_rule"] == "exact_string_identity"
    assert season["reason_code"] == "EXACT_STRING_MISMATCH"


@pytest.mark.parametrize(
    ("echoed", "passed"),
    [(0, True), ("0", False), (0.0, False), (False, False), (None, False), (1, False), (-0.0, False)],
)
def test_poround_sentinel_is_exact_and_type_strict(frozen_request, echoed, passed):
    result = compare_response_echo(
        frozen_request["parameters"], _echo(frozen_request, PORound=echoed)
    )
    field = next(item for item in result["fields"] if item["field"] == "PORound")
    assert field["equivalent"] is passed
    assert field["reason_code"] == (
        "POROUND_EMPTY_TO_INTEGER_ZERO_EQUIVALENT" if passed else "POROUND_NOT_EQUIVALENT"
    )


def test_poround_missing_fails(frozen_request):
    returned = _echo(frozen_request)
    returned.pop("PORound")
    result = compare_response_echo(frozen_request["parameters"], returned)
    assert "PORound" in result["missing_expected_fields"]


def test_poround_rule_cannot_apply_to_another_field(frozen_request):
    result = compare_response_echo(
        frozen_request["parameters"], _echo(frozen_request, Location=0)
    )
    field = next(item for item in result["fields"] if item["field"] == "Location")
    assert field["comparison_rule"] == "exact_empty_string_or_empty_string_to_json_null"
    assert field["equivalent"] is False


def test_quarantined_response_collects_all_fields_and_three_nonliteral_equivalences(frozen_request, payload):
    result = compare_response_echo(frozen_request["parameters"], payload["parameters"])
    assert result["passed"] is True
    assert result["mismatch_count"] == 0
    assert result["compared_field_order"] == list(module.EXPECTED_FIELD_ORDER)
    fields = {item["field"]: item for item in result["fields"]}
    assert fields["DateFrom"]["reason_code"] == "STRICT_DATE_NORMALIZATION_EQUIVALENT"
    assert fields["DateTo"]["reason_code"] == "STRICT_DATE_NORMALIZATION_EQUIVALENT"
    assert fields["PORound"]["reason_code"] == "POROUND_EMPTY_TO_INTEGER_ZERO_EQUIVALENT"
    assert result["extra_returned_fields"] == [{
        "field": "ISTRound",
        "echoed_raw_value": None,
        "comparison_rule": "allowlisted_istround_exact_json_null_only",
        "permitted": True,
        "reason_code": "PERMITTED_ISTROUND_NULL_EXTRA",
    }]


def test_comparator_reports_every_mismatch_in_deterministic_order(frozen_request, payload):
    returned = dict(payload["parameters"])
    returned.update({
        "DateFrom": "10/22/2025", "DateTo": "02/01/2026", "TeamID": 1,
        "Season": "2024-25", "MeasureType": "Advanced", "Unexpected": None,
    })
    result = compare_response_echo(frozen_request["parameters"], returned)
    assert result["passed"] is False
    assert [item["field"] for item in result["mismatches"]] == [
        "DateFrom", "DateTo", "MeasureType", "Season", "TeamID", "Unexpected",
    ]
    assert result["full_mismatch_collection"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [("TeamID", 1610612763), ("Season", "2024-25"), ("MeasureType", "Advanced"), ("DateTo", "02/01/2026")],
)
def test_identity_alterations_fail(frozen_request, payload, field, value):
    returned = dict(payload["parameters"])
    returned[field] = value
    result = compare_response_echo(frozen_request["parameters"], returned)
    assert result["passed"] is False
    assert [item["field"] for item in result["mismatches"]] == [field]


def test_unexpected_extra_and_altered_istround_fail(frozen_request, payload):
    unexpected = dict(payload["parameters"], arbitrary=None)
    assert compare_response_echo(frozen_request["parameters"], unexpected)["passed"] is False
    altered = dict(payload["parameters"])
    altered["ISTRound"] = 0
    result = compare_response_echo(frozen_request["parameters"], altered)
    assert result["passed"] is False
    assert result["extra_returned_fields"][0]["reason_code"] == "UNEXPECTED_OR_INVALID_EXTRA_FIELD"


def test_initial_and_replay_entry_points_delegate_to_only_comparator(monkeypatch):
    sentinel = {"passed": True}
    calls = []

    def fake(sent, returned):
        calls.append((sent, returned))
        return sentinel

    monkeypatch.setattr(module, "compare_response_echo", fake)
    assert module.verify_initial_response_echo({"a": 1}, {"a": 1}) is sentinel
    assert module.verify_replay_response_echo({"b": 2}, {"b": 2}) is sentinel
    assert len(calls) == 2


def test_failed_r2d_comparator_is_neither_imported_nor_called():
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "from pair_fit_v2.phase3f_r2d_recovery_acquisition import" not in source
    assert "_normalize(" not in source
    assert "verify_response_bytes(" not in source


def test_exact_quarantined_fingerprint_and_structure(frozen_request, payload):
    body = BODY_PATH.read_bytes()
    assert len(body) == module.QUARANTINED_RESPONSE_BYTES
    assert module.sha256_bytes(body) == module.QUARANTINED_RESPONSE_SHA256
    assert module.sha256_bytes(module.canonical_json_bytes(payload)) == module.QUARANTINED_RESPONSE_CANONICAL_SHA256
    structural = module._validate_structural(body, frozen_request)
    assert structural == {
        "observed_result_set_order": ["Overall", "Lineups"],
        "overall_header_count": 57,
        "overall_row_count": 1,
        "lineups_header_count": 56,
        "lineups_row_count": 227,
        "canonical_unordered_pair_count": 227,
        "duplicate_canonical_pair_count": 0,
        "malformed_group_identifier_count": 0,
        "same_player_pair_count": 0,
        "invalid_player_id_count": 0,
        "row_width_error_count": 0,
        "strict_json_valid": True,
        "structurally_valid": True,
    }


def test_build_has_exact_inventory_and_offline_only_assessment(built):
    destination, result = built
    assert sorted(path.name for path in destination.iterdir()) == sorted(OUTPUT_FILES)
    assert result["network_requests"] == 0
    assessment = strict_json_bytes((destination / "quarantined_response_assessment.json").read_bytes())
    assert assessment["finding"] == "eligible_for_future_offline_revalidation_under_corrected_echo_contract"
    assert assessment["original_r2d_state_unchanged"] == "failed_or_quarantined"
    assert assessment["promotion_occurred"] is False
    assert assessment["completed_verification_created_in_r2d"] is False
    assert assessment["body_copied"] is False
    assert assessment["population_reconciliation_performed"] is False
    assert assessment["all_unpermitted_mismatches"] == []
    assert assessment["quarantined_response"] == {
        "path": module.QUARANTINED_RESPONSE.as_posix(),
        "bytes": 58235,
        "raw_sha256": module.QUARANTINED_RESPONSE_SHA256,
        "canonical_json_sha256": module.QUARANTINED_RESPONSE_CANONICAL_SHA256,
        "last_write_time_utc": module.QUARANTINED_RESPONSE_MTIME_UTC,
    }
    assert not (ROOT / module.R2D_EVIDENCE_ROOT / "01-1610612754-early-base/verification.json").exists()
    assert not (ROOT / module.R2D_EVIDENCE_ROOT / "01-1610612754-early-base/verified-response.bin").exists()


def test_continuation_freezes_only_original_ordinals_two_through_eight(
    built, authorization, r2c1_plan
):
    destination, _ = built
    plan = strict_json_bytes((destination / "continuation_plan.json").read_bytes())
    remaining = plan["remaining_network_identities"]
    authorized_remaining = authorization["authorized_requests"][1:]
    r2c1_remaining = r2c1_plan["future_recovery_identities"][1:]
    assert plan["future_network_attempt_limit"] == 7
    assert plan["automatic_retry_limit"] == 0
    assert plan["continuation_order"] == list(range(2, 9))
    assert [item["original_recovery_ordinal"] for item in remaining] == list(range(2, 9))
    assert [item["continuation_network_ordinal"] for item in remaining] == list(range(1, 8))
    assert [item["request_id"] for item in remaining] == [
        item["request_id"] for item in authorized_remaining
    ] == [item["request_id"] for item in r2c1_remaining]
    assert [item["canonical_request_identity_sha256"] for item in remaining] == [
        item["canonical_request_identity_sha256"] for item in authorized_remaining
    ] == [item["canonical_request_identity_sha256"] for item in r2c1_remaining]
    assert len({item["request_id"] for item in remaining}) == 7
    assert all(item["request_id"] != module.FIRST_REQUEST_ID for item in remaining)
    assert plan["indiana_early_base_duplicate_request_prohibited"] is True
    assert plan["reused_first_evidence_member"]["network_request_prohibited"] is True
    assert plan["present_authority"] == "none"


def test_lineage_and_continuation_namespaces_are_exact_distinct_and_nonfallback(
    built, r2c1_plan
):
    destination, _ = built
    plan = strict_json_bytes((destination / "continuation_plan.json").read_bytes())
    remaining = plan["remaining_network_identities"]
    r2c1_remaining = r2c1_plan["future_recovery_identities"][1:]
    expected_lineage = [item["future_output_namespace"] for item in r2c1_remaining]
    expected_continuation = [
        (
            module.FUTURE_CONTINUATION_NAMESPACE
            / f"{item['ordinal']:02d}-{item['team_id']}-{item['window']['name']}-{item['measure'].lower()}"
        ).as_posix()
        for item in r2c1_remaining
    ]
    assert [item["future_output_namespace"] for item in remaining] == expected_lineage
    assert [item["continuation_output_namespace"] for item in remaining] == expected_continuation
    assert all(
        item["future_output_namespace"] != item["continuation_output_namespace"]
        for item in remaining
    )
    assert plan["continuation_output_namespace"] == module.FUTURE_CONTINUATION_NAMESPACE.as_posix()
    assert "future_output_namespace" not in plan

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if isinstance(child, str) and child.startswith(
                    module.FUTURE_CONTINUATION_NAMESPACE.as_posix()
                ):
                    assert "continuation" in key
                if isinstance(child, str) and child.startswith(
                    "cache/phase3f-r2c-protected-recovery/"
                ):
                    assert key == "future_output_namespace"
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(plan)


def test_policy_report_plan_and_tests_use_same_namespace_contract(built):
    destination, _ = built
    expected_continuation_root = "cache/phase3f-r2d.2/protected-recovery-continuation"
    assert expected_continuation_root == module.FUTURE_CONTINUATION_NAMESPACE.as_posix()
    plan_text = (destination / "continuation_plan.json").read_text(encoding="utf-8")
    policy_text = (ROOT / "PHASE3F_R2D_1_RESPONSE_ECHO_CORRECTION_POLICY.md").read_text(
        encoding="utf-8"
    )
    report_text = (ROOT / "PHASE3F_R2D_1_RESPONSE_ECHO_CORRECTION_REPORT.md").read_text(
        encoding="utf-8"
    )
    test_text = Path(__file__).read_text(encoding="utf-8")
    for text in (plan_text, policy_text, report_text, test_text):
        assert "future_output_namespace" in text
        assert "continuation_output_namespace" in text
        assert expected_continuation_root in text


def test_summary_has_zero_operations_and_unresolved_dispositions(built):
    destination, _ = built
    summary = strict_json_bytes((destination / "summary.json").read_bytes())
    for key in (
        "network_requests_during_r2d_1", "protected_requests", "recovery_requests",
        "response_promotions", "final_test_rows", "estimator_operations",
        "population_reconciliation_operations", "dataset_operations",
    ):
        assert summary[key] == 0
    assert summary["indiana"] == "recovery_unresolved"
    assert summary["memphis"] == "recovery_unresolved"
    assert summary["future_continuation_network_identities"] == 7
    assert summary["future_continuation_authorized_now"] is False


def test_manifest_rule_is_nonrecursive_and_excludes_itself(built):
    destination, _ = built
    manifest = strict_json_bytes((destination / "artifact_hashes.json").read_bytes())
    assert "nonrecursive" in manifest["rule"]
    assert set(manifest["artifacts"]) == set(OUTPUT_FILES) - {"artifact_hashes.json"}
    for name, expected in manifest["artifacts"].items():
        assert module._fingerprint(destination / name) == expected


def test_write_once_rejects_existing_empty_or_partial_namespace(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(EchoContractError, match="already exists"):
        build_specification(ROOT, empty)
    partial = tmp_path / "partial"
    partial.mkdir()
    (partial / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(EchoContractError, match="already exists"):
        build_specification(ROOT, partial)


def test_two_disposable_builds_are_byte_identical_and_no_body_is_copied(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    build_specification(ROOT, left)
    build_specification(ROOT, right)
    assert {name: (left / name).read_bytes() for name in OUTPUT_FILES} == {
        name: (right / name).read_bytes() for name in OUTPUT_FILES
    }
    assert not list(left.rglob("*.bin"))
    assert not list(right.rglob("*.bin"))


def test_continuation_is_not_built_when_offline_assessment_fails(monkeypatch, tmp_path):
    original = module._assess_quarantined_response

    def ineligible(*args, **kwargs):
        assessment, reference = original(*args, **kwargs)
        assessment["eligible_for_future_reuse"] = False
        assessment["finding"] = "not_eligible_for_future_reuse"
        return assessment, reference

    monkeypatch.setattr(module, "_assess_quarantined_response", ineligible)
    with pytest.raises(EchoContractError, match="not eligible"):
        build_specification(ROOT, tmp_path / "blocked")
    assert not (tmp_path / "blocked").exists()


def test_namespace_ignore_and_scope_prohibitions():
    result = subprocess.run(
        [
            "git", "check-ignore", "-q",
            (module.OUTPUT_NAMESPACE / "response_echo_contract.json").as_posix(),
        ],
        # Git only applies a directory-only pattern to a path below that directory.
        cwd=ROOT, check=False,
    )
    assert result.returncode == 0
    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    for prohibited in (
        "import requests", "from requests", "urllib.request", "socket.",
        "session.get", "session.post", "fit(", "predict(", "joblib", "pickle",
    ):
        assert prohibited not in source


def test_historical_and_original_r2d_fingerprints_remain_exact(built):
    destination, _ = built
    assessment = strict_json_bytes((destination / "quarantined_response_assessment.json").read_bytes())
    history = assessment["governing_and_historical_preservation"]
    assert history["all_fingerprints_match_original_r2d_authorization"] is True
    assert len(history["historical_namespaces"]) == 9
    assert len(history["historical_git_visible_files"]) == 30
    original = assessment["original_evidence_authentication"]
    assert original["attempt_count"] == 1
    assert original["requests_2_through_8_evidence_absent"] is True
    assert original["reconciliation_and_readiness_artifacts_absent"] is True
    assert original["original_state"] == "failed_or_quarantined"


def test_generated_outputs_are_valid_strict_json_without_nan_or_infinity(built):
    destination, _ = built
    for name in OUTPUT_FILES:
        body = (destination / name).read_bytes()
        strict_json_bytes(body)
        assert b"NaN" not in body
        assert b"Infinity" not in body
