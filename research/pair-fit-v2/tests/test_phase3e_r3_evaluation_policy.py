import ast
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3e_r3_evaluation_policy as phase
from pair_fit_v2 import phase3a_population_audit as phase3a
from pair_fit_v2 import phase3e_r2_holdout as phase3e_r2


PROJECT = Path(__file__).resolve().parents[1]
SENSITIVITY_FIELDS = {
    "contains_row_level_target",
    "contains_row_level_prediction",
    "contains_target_derived_results",
    "contains_prediction_derived_results",
    "sensitivity_class",
    "may_be_written_before_stage_a_closes",
    "may_be_opened_before_stage_a_closes",
    "reveal_only_after_stage_b_computation",
    "indirectly_identifies_sensitive_generated_evidence",
}
EXPECTED_SENSITIVITY = {
    "execution_configuration.json": (False, False, False, False, "configuration_only", True, False),
    "pre_metric_integrity.json": (False, False, False, False, "pre_metric_integrity_only", True, False),
    "predictions.csv": (True, True, False, False, "row_level_evaluation", False, True),
    "overall_metrics.json": (False, False, True, True, "aggregate_evaluation", False, True),
    "missing_history_metrics.csv": (False, False, True, True, "aggregate_evaluation", False, True),
    "team_metrics.csv": (False, False, True, True, "aggregate_evaluation", False, True),
    "leave_one_team_out_metrics.csv": (False, False, True, True, "aggregate_evaluation", False, True),
    "calibration_bins.csv": (False, False, True, True, "aggregate_evaluation", False, True),
    "residual_diagnostics.json": (False, False, True, True, "aggregate_evaluation", False, True),
    "historical_stability.json": (False, False, True, True, "aggregate_evaluation", False, True),
    "evaluation_decision.json": (False, False, True, True, "aggregate_evaluation", False, True),
    "artifact_hashes.json": (False, False, False, False, "artifact_bookkeeping", False, True),
    "summary.json": (False, False, True, True, "aggregate_evaluation", False, True),
}
PROHIBITED_LEGACY_MODULES = {
    "pair_fit_v2.phase1b_contract",
    "pair_fit_v2.schema",
}
PROHIBITED_LEGACY_RELATIVE_MODULES = {"phase1b_contract", "schema"}


def _prohibited_legacy_imports(source: str) -> list[str]:
    """Return every static import that reaches a prohibited legacy module."""
    violations = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == module or alias.name.startswith(f"{module}.") for module in PROHIBITED_LEGACY_MODULES):
                    violations.append(ast.unparse(node))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            prohibited_origin = any(
                module == legacy or module.startswith(f"{legacy}.")
                for legacy in PROHIBITED_LEGACY_MODULES | PROHIBITED_LEGACY_RELATIVE_MODULES
            )
            prohibited_package_member = module in {"", "pair_fit_v2"} and any(
                alias.name in PROHIBITED_LEGACY_RELATIVE_MODULES for alias in node.names
            )
            if prohibited_origin or prohibited_package_member:
                violations.append(ast.unparse(node))
    return violations


def _dotted_reference(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_reference(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def _prohibited_legacy_canonicalizer_references(source: str) -> list[str]:
    """Return executable attribute references to either legacy canonicalizer."""
    prohibited_suffixes = {
        "phase1b_contract.stable_pair_key",
        "schema.canonical_pair",
        "schema.canonical_pair_key",
    }
    violations = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            reference = _dotted_reference(node)
            if reference and any(reference == suffix or reference.endswith(f".{suffix}") for suffix in prohibited_suffixes):
                violations.append(reference)
    return violations


def test_policy_is_deterministic_and_self_hashing():
    first = phase.policy_document()
    second = phase.policy_document()
    assert first == second
    assert phase.serialize_policy(first) == phase.serialize_policy(second)
    assert first["deterministic_content_sha256"] == phase.canonical_content_hash(first)
    assert phase.serialize_policy(first).endswith(b"\n")
    # Strict JSON serialization rejects nonfinite numeric values.  The word
    # "NaN" may still appear legitimately in a human-readable gate label.
    json.dumps(first, allow_nan=False)


@pytest.mark.parametrize(
    ("stage_a", "stage_b", "mae_improvement", "rmse_improvement", "expected"),
    [
        (True, True, 0.10, 0.0, "VALID DEVELOPMENT-HOLDOUT PASS"),
        (True, True, 0.1000001, 0.01, "VALID DEVELOPMENT-HOLDOUT PASS"),
        (True, True, 0.0999999, 1.0, "VALID DEVELOPMENT-HOLDOUT MIXED RESULT"),
        (True, True, 0.10, -0.000001, "VALID DEVELOPMENT-HOLDOUT MIXED RESULT"),
        (True, True, 0.000001, -1.0, "VALID DEVELOPMENT-HOLDOUT MIXED RESULT"),
        (True, True, 0.0, 1.0, "VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE"),
        (True, True, -0.000001, 1.0, "VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE"),
        (False, True, 1.0, 1.0, "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"),
        (True, False, 1.0, 1.0, "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"),
        (True, True, math.nan, 1.0, "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"),
        (True, True, math.inf, 1.0, "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"),
        (True, True, -math.inf, 1.0, "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"),
        (True, True, 1.0, math.nan, "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"),
        (True, True, 1.0, math.inf, "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"),
        (True, True, 1.0, -math.inf, "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"),
    ],
)
def test_classification_boundaries(stage_a, stage_b, mae_improvement, rmse_improvement, expected):
    assert phase.classify_evaluation(stage_a, stage_b, mae_improvement, rmse_improvement) == expected


def test_policy_agrees_with_phase3d_and_phase3e_r2_without_parsing_holdout_rows(monkeypatch):
    loaded = []
    original = phase._load_json

    def guarded_load(path):
        assert path.suffix == ".json"
        assert path.name not in {"holdout_row_index.csv", "holdout_staging.csv", "holdout_estimator_matrix.csv"}
        loaded.append(path.name)
        return original(path)

    monkeypatch.setattr(phase, "_load_json", guarded_load)
    policy = phase.policy_document()
    phase.validate_against_frozen_contracts(PROJECT, policy)
    assert "selection_decision.json" in loaded
    assert "preprocessing_state.json" in loaded
    assert "population_diagnostics.json" in loaded


def test_all_129_r2_cache_fingerprints_and_phase1_manifest_hash_remain_unchanged():
    document = json.loads((PROJECT / "curated/phase3e-r2/input_fingerprints.json").read_text(encoding="utf-8"))
    fingerprints = document["referenced_cache_files"]
    assert document["referenced_cache_file_count"] == len(fingerprints) == 129
    assert all(phase.sha256_file(PROJECT / "cache" / relative) == expected for relative, expected in fingerprints.items())
    assert phase.sha256_file(PROJECT / "cache" / phase3e_r2.PHASE1C_MANIFEST) == phase3e_r2.PHASE1C_MANIFEST_SHA256


@pytest.mark.parametrize(
    "source",
    [
        # Direct symbol imports.
        "from pair_fit_v2.phase1b_contract import stable_pair_key",
        "from pair_fit_v2.phase1b_contract import stable_pair_key as legacy_key",
        "from pair_fit_v2.schema import canonical_pair",
        "from pair_fit_v2.schema import canonical_pair as legacy_key",
        # Fully qualified module imports.
        "import pair_fit_v2.phase1b_contract",
        "import pair_fit_v2.phase1b_contract as legacy",
        "import pair_fit_v2.schema",
        "import pair_fit_v2.schema as legacy",
        # Package-level module imports.
        "from pair_fit_v2 import phase1b_contract",
        "from pair_fit_v2 import phase1b_contract as legacy",
        "from pair_fit_v2 import schema",
        "from pair_fit_v2 import schema as legacy",
        # Relative direct imports.
        "from .phase1b_contract import stable_pair_key",
        "from .phase1b_contract import stable_pair_key as legacy_key",
        "from .schema import canonical_pair",
        "from .schema import canonical_pair as legacy_key",
        # Relative package-level module imports.
        "from . import phase1b_contract",
        "from . import phase1b_contract as legacy",
        "from . import schema",
        "from . import schema as legacy",
        # Equivalent double-dot forms.
        "from ..phase1b_contract import stable_pair_key",
        "from ..phase1b_contract import stable_pair_key as legacy_key",
        "from ..schema import canonical_pair",
        "from ..schema import canonical_pair as legacy_key",
        "from .. import phase1b_contract",
        "from .. import phase1b_contract as legacy",
        "from .. import schema",
        "from .. import schema as legacy",
        # Wildcard, submodule, and multiple-name forms.
        "from pair_fit_v2.schema import canonical_pair_key",
        "from pair_fit_v2.phase1b_contract import *",
        "from pair_fit_v2.schema import *",
        "import pair_fit_v2.schema.future_helper as legacy",
        "from pair_fit_v2 import config, phase1b_contract as legacy",
        "from . import config, schema as legacy",
        "import pair_fit_v2.config, pair_fit_v2.schema as legacy",
        "from ..pair_fit_v2 import schema as legacy_schema",
        "from ..pair_fit_v2.phase1b_contract import stable_pair_key as legacy_key",
    ],
)
def test_legacy_import_guard_rejects_every_prohibited_static_form(source):
    assert _prohibited_legacy_imports(source) == [ast.unparse(ast.parse(source).body[0])]


@pytest.mark.parametrize(
    "source",
    [
        "from pair_fit_v2 import config",
        "from pair_fit_v2.config import SOME_CONSTANT",
        "import pair_fit_v2.config",
        "from . import config",
        "from .config import SOME_CONSTANT",
        "from .. import config",
        "from ..pair_fit_v2 import config",
        "legacy_name = 'pair_fit_v2.schema'",
    ],
)
def test_legacy_import_guard_allows_nonlegacy_imports_and_plain_strings(source):
    assert _prohibited_legacy_imports(source) == []


@pytest.mark.parametrize(
    "source",
    [
        "pair_fit_v2.phase1b_contract.stable_pair_key('9', '10')",
        "phase1b_contract.stable_pair_key('9', '10')",
        "pair_fit_v2.schema.canonical_pair('9', '10')",
        "schema.canonical_pair_key('9', '10')",
    ],
)
def test_legacy_reference_guard_rejects_executable_canonicalizer_references(source):
    assert _prohibited_legacy_canonicalizer_references(source)


def test_legacy_reference_guard_ignores_policy_string_literals():
    source = "legacy_reference = 'pair_fit_v2.phase1b_contract.stable_pair_key'"
    assert _prohibited_legacy_canonicalizer_references(source) == []


def test_active_model_pair_keys_are_numeric_and_all_phase3_imports_are_guarded():
    assert phase3a.canonical_pair("9", "10") == ("9", "10")
    assert phase3a.canonical_pair("10", "9") == ("9", "10")
    synthetic = {
        "resultSets": [{"name": "Lineups", "headers": ["GROUP_ID"], "rowSet": [["-10-9-"]]}],
    }
    index, diagnostics = phase3e_r2._pair_index(synthetic)
    assert list(index) == [("9", "10")]
    assert diagnostics["canonical_unique_pair_keys"] == 1

    namespaces = phase.policy_document()["pair_key_namespaces"]
    assert namespaces["active_phase3b_plus_model_key"]["ordering"] == (
        "numeric normalized positive player IDs with player_1_id < player_2_id"
    )
    assert namespaces["future_r4_enforcement"]["legacy_imports_prohibited"] == [
        "pair_fit_v2.phase1b_contract.stable_pair_key",
        "pair_fit_v2.schema.canonical_pair_key",
    ]
    for path in (PROJECT / "src/pair_fit_v2").glob("phase3*.py"):
        source = path.read_text(encoding="utf-8")
        import_violations = _prohibited_legacy_imports(source)
        reference_violations = _prohibited_legacy_canonicalizer_references(source)
        assert import_violations == [], f"{path}: {import_violations}"
        assert reference_violations == [], f"{path}: {reference_violations}"


def test_two_independent_policy_builds_are_byte_identical(tmp_path):
    left = tmp_path / "left" / "evaluation_policy.json"
    right = tmp_path / "right" / "evaluation_policy.json"
    phase.build(PROJECT, left)
    phase.build(PROJECT, right)
    assert left.read_bytes() == right.read_bytes()
    assert json.loads(left.read_text(encoding="utf-8")) == phase.policy_document()


def test_population_estimator_metrics_and_diagnostics_are_complete():
    policy = phase.policy_document()
    assert policy["evaluation_population"] == {
        "target_season": "2024-25",
        "season_type": "Regular Season",
        "retained_teams": 28,
        "excluded_teams": {"1610612766": "Charlotte Hornets", "1610612755": "Philadelphia 76ers"},
        "eligible_rows": 2700,
        "eligibility": "directly returned full-season POSS >= 150",
        "target": "directly returned full-season pair NET_RATING",
        "window_aggregated_or_reconstructed_targets": False,
    }
    assert policy["estimator"]["features"] == phase.FEATURES
    assert len(policy["estimator"]["features"]) == 45
    assert policy["estimator"]["alpha"] == 3000.0
    assert policy["estimator"]["calibrator"] is None
    assert policy["decision_gates"]["mae_improvement_minimum"] == 0.10
    assert policy["decision_gates"]["rmse_improvement_minimum"] == 0.0
    assert policy["missing_history_diagnostics"]["expected_phase3e_r2_counts"] == {
        "complete": 2139,
        "one_missing": 523,
        "both_missing": 38,
    }
    assert policy["calibration_and_tail_diagnostics"]["bin_assignment"] == "with zero-based sorted index j and n=2700, bin = 1 + floor(j * 10 / n)"
    stages = policy["evaluation_stages"]
    assert stages["stage_a_pre_metric_integrity"]["gates"] == phase.STAGE_A_PRE_METRIC_GATES
    assert stages["stage_b_post_computation_completeness"]["checks"] == phase.STAGE_B_POST_COMPUTATION_CHECKS
    assert stages["future_execution_sequence"] == phase.FUTURE_EXECUTION_SEQUENCE
    assert {gate["id"] for gate in phase.STAGE_A_PRE_METRIC_GATES} >= {
        "finite_estimator_matrix", "finite_target_vector", "finite_prediction_vector",
        "single_authorized_prediction_vector", "transformation_compatibility",
    }
    assert set(policy["classifications"]) >= {
        "VALID DEVELOPMENT-HOLDOUT PASS",
        "VALID DEVELOPMENT-HOLDOUT MIXED RESULT",
        "VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE",
        "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE",
    }


def test_generated_policy_location_is_git_ignored_and_module_cannot_run_models():
    ignore = (PROJECT / ".gitignore").read_text(encoding="utf-8")
    assert "/modeling/phase3e-r3/" in ignore
    assert "/modeling/phase3e-r4/" in ignore
    source = Path(phase.__file__).read_text(encoding="utf-8")
    for prohibited_import in ("sklearn", "numpy", "pandas", "joblib", "pickle"):
        assert f"import {prohibited_import}" not in source
        assert f"from {prohibited_import}" not in source
    assert "holdout_row_index.csv\").open" not in source
    assert "holdout_staging.csv\").open" not in source


def test_exact_r4_output_inventory_schemas_and_mutation_allowlist():
    contract = phase.policy_document()["runtime_output_contract"]
    assert contract["runtime_output_directory"] == "modeling/phase3e-r4/"
    assert contract["runtime_artifact_order"] == phase.R4_RUNTIME_ARTIFACTS
    assert contract["generated_artifact_count"] == 13
    assert list(contract["artifacts"]) == phase.R4_RUNTIME_ARTIFACTS
    for artifact in contract["artifacts"].values():
        assert ("columns" in artifact) != ("top_level_keys" in artifact)
        assert {"purpose", "rows", "ordering"} | SENSITIVITY_FIELDS <= artifact.keys()
        assert "contains_target_values" not in artifact
        assert "contains_predictions" not in artifact
    execution = contract["artifacts"]["execution_configuration.json"]
    assert execution["nested_keys"]["policy_identity"] == [
        "relative_path", "deterministic_content_sha256", "serialized_byte_sha256",
    ]
    pre_metric = contract["artifacts"]["pre_metric_integrity.json"]
    assert pre_metric["nested_keys"]["stage_a_gate_result_entry"] == ["gate_id", "passed", "evidence"]
    assert pre_metric["forbidden_content"] == [
        "performance metrics", "target summaries", "prediction-performance comparisons",
    ]
    assert contract["artifacts"]["predictions.csv"]["rows"] == 2700
    assert contract["artifacts"]["predictions.csv"]["columns"] == [
        "row_position", "target_season", "team_id", "player_1_id", "player_2_id",
        "target_net_rating", "ridge_prediction", "baseline_prediction", "pair_possessions",
        "history_status", "endpoint_exact_250_flag",
    ]
    assert contract["artifacts"]["missing_history_metrics.csv"]["rows"] == 3
    assert contract["artifacts"]["team_metrics.csv"]["rows"] == 28
    assert contract["artifacts"]["leave_one_team_out_metrics.csv"]["rows"] == 28
    assert contract["artifacts"]["calibration_bins.csv"]["rows"] == 10
    assert contract["artifacts"]["overall_metrics.json"]["nested_keys"]["exact_250_diagnostic"] == [
        "applicable", "row_count", "mae", "rmse", "bias", "not_applicable_reason",
    ]
    assert "residual_variance" in contract["artifacts"]["residual_diagnostics.json"]["top_level_keys"]
    for name, expected in EXPECTED_SENSITIVITY.items():
        artifact = contract["artifacts"][name]
        actual = (
            artifact["contains_row_level_target"],
            artifact["contains_row_level_prediction"],
            artifact["contains_target_derived_results"],
            artifact["contains_prediction_derived_results"],
            artifact["sensitivity_class"],
            artifact["may_be_opened_before_stage_a_closes"],
            artifact["reveal_only_after_stage_b_computation"],
        )
        assert actual == expected
        assert artifact["may_be_written_before_stage_a_closes"] is expected[5]
        assert artifact["sensitivity_class"] in phase.SENSITIVITY_CLASSES
    hashes_artifact = contract["artifacts"]["artifact_hashes.json"]
    assert hashes_artifact["indirectly_identifies_sensitive_generated_evidence"] is True
    assert contract["sensitivity_contract"]["allowed_classes"] == phase.SENSITIVITY_CLASSES
    access = contract["stage_access_policy"]
    assert access["before_stage_a_closes_writable_or_revealable_final_artifacts"] == [
        "execution_configuration.json", "pre_metric_integrity.json",
    ]
    assert "in memory" in access["prediction_failure_safe_mechanism"]
    assert access["stage_a_failure_persistence"] == ["execution_configuration.json", "pre_metric_integrity.json"]
    hashes = contract["artifacts"]["artifact_hashes.json"]
    assert hashes["payload_artifacts"] == phase.R4_RUNTIME_ARTIFACTS[:11]
    assert hashes["excluded_from_own_byte_manifest"] == ["artifact_hashes.json", "summary.json"]
    assert contract["human_report"]["relative_path"] == "PHASE3E_R4_DEVELOPMENT_HOLDOUT_EVALUATION_REPORT.md"
    allowlist = contract["runtime_mutation_allowlist"]
    assert allowlist["ignored_runtime_artifacts"] == [f"modeling/phase3e-r4/{name}" for name in phase.R4_RUNTIME_ARTIFACTS]
    assert not (PROJECT / "modeling" / "phase3e-r4").exists()


def test_markdown_matches_stage_ids_output_inventory_and_edge_cases():
    text = (PROJECT / "PHASE3E_R3_EVALUATION_POLICY.md").read_text(encoding="utf-8")
    for item in phase.STAGE_A_PRE_METRIC_GATES + phase.STAGE_B_POST_COMPUTATION_CHECKS:
        assert f"`{item['id']}`" in text
    for name in phase.R4_RUNTIME_ARTIFACTS:
        assert f"`{name}`" in text
    for phrase in (
        "NaN, positive infinity, or negative infinity",
        "full-sample MAE - leave-one-team-out MAE > 0",
        "prediction variance is zero",
        "possessions variance is zero",
        "If residual variance is zero",
        "Do not emit NaN or infinity",
        "legacy Phase 1B raw-acquisition",
        "memory-only buffering",
        "contains_target_derived_results",
    ):
        assert phrase in text
    assert "contains_target_values" not in text
    assert "contains_predictions" not in text
    for name, expected in EXPECTED_SENSITIVITY.items():
        values = [str(value).lower() if isinstance(value, bool) else f"`{value}`" for value in expected]
        assert f"| `{name}` | {' | '.join(values)} |" in text
