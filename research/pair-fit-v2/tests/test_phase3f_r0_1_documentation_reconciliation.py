import ast
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pair_fit_v2 import phase3f_r0_1_documentation_reconciliation as phase


PROJECT = Path(__file__).resolve().parents[1]


def _copy_file(root: Path, relative: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROJECT / relative, target)


def _isolated_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    for relative in {
        *phase.R3_EVIDENCE_SHA256,
        phase.ADDENDUM_PATH,
        phase.R0_POLICY_PATH,
        phase.R0_REPORT_PATH,
    }:
        _copy_file(root, relative)
    shutil.copytree(PROJECT / phase.R0_DIRECTORY, root / phase.R0_DIRECTORY, copy_function=shutil.copy2)
    return root


@pytest.fixture(scope="session")
def independent_builds(tmp_path_factory):
    base = tmp_path_factory.mktemp("phase3f_r0_1")
    left, right = base / "left", base / "right"
    first = phase.build(PROJECT, left, enforce_git_state=False)
    second = phase.build(PROJECT, right, enforce_git_state=False)
    return left, right, first, second


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_root_dictionary_is_historical_r3_evidence_and_addendum_is_distinct():
    assert phase.sha256_file(PROJECT / phase.ROOT_DICTIONARY_PATH) == phase.ROOT_DICTIONARY_SHA256
    assert phase.sha256_file(PROJECT / phase.ADDENDUM_PATH) == phase.ADDENDUM_SHA256
    assert (PROJECT / phase.ADDENDUM_PATH).stat().st_size == phase.ADDENDUM_BYTES
    assert phase.ROOT_DICTIONARY_PATH != phase.ADDENDUM_PATH


def test_addendum_documents_exact_original_inventory_once():
    names = phase._inventory_from_markdown(PROJECT / phase.ADDENDUM_PATH)
    assert names == phase.R0_ARTIFACT_NAMES
    block = (PROJECT / phase.ADDENDUM_PATH).read_text(encoding="utf-8").split(phase.INVENTORY_START)[1].split(phase.INVENTORY_END)[0]
    assert all(block.count(f"`{name}`") == 1 for name in names)
    assert len(names) == len(set(names)) == 10


def test_addendum_entries_match_real_original_artifacts():
    fingerprint = phase.fingerprint_r0(PROJECT)
    actual = {Path(item["relative_path"]).name: item for item in fingerprint["entries"]}
    expected = {item["name"]: item for item in phase.R0_ARTIFACTS}
    assert set(actual) == set(expected) == set(phase._inventory_from_markdown(PROJECT / phase.ADDENDUM_PATH))
    for name in expected:
        assert actual[name]["bytes"] == expected[name]["bytes"]
        assert actual[name]["sha256"] == expected[name]["sha256"]


def test_original_r0_exact_inventory_hashes_and_timestamp_fingerprint():
    fingerprint = phase.fingerprint_r0(PROJECT)
    assert fingerprint["artifact_count"] == 10
    assert len(fingerprint["entries"]) == 10
    assert all(item["mtime_ns"] > 0 for item in fingerprint["entries"])
    assert len(fingerprint["fingerprint_sha256"]) == 64


def test_r0_1_exact_inventory_and_no_original_artifact_copy(independent_builds):
    left, _, _, _ = independent_builds
    r0_1_names = {path.name for path in left.iterdir()}
    assert r0_1_names == set(phase.R01_ARTIFACTS)
    assert len(list(left.iterdir())) == 4
    assert set(phase.R0_ARTIFACT_NAMES) & r0_1_names == {"artifact_hashes.json", "summary.json"}
    assert (left / "artifact_hashes.json").read_bytes() != (PROJECT / phase.R0_DIRECTORY / "artifact_hashes.json").read_bytes()
    assert (left / "summary.json").read_bytes() != (PROJECT / phase.R0_DIRECTORY / "summary.json").read_bytes()


def test_before_after_r0_fingerprints_and_timestamps_are_identical(independent_builds):
    left, _, _, _ = independent_builds
    reconciliation = _load(left / "documentation_reconciliation.json")
    before = reconciliation["r0_directory_fingerprint_before"]
    after = reconciliation["r0_directory_fingerprint_after"]
    assert reconciliation["r0_directory_fingerprints_equal"] is True
    assert before == after == phase.fingerprint_r0(PROJECT)
    assert [item["mtime_ns"] for item in before["entries"]] == [item["mtime_ns"] for item in after["entries"]]


def test_r3_source_evidence_is_unchanged_and_hash_pinned(independent_builds):
    left, _, _, _ = independent_builds
    assert phase.validate_r3_evidence(PROJECT) == phase.R3_EVIDENCE_SHA256
    reconciliation = _load(left / "documentation_reconciliation.json")
    assert reconciliation["r3_evidence_changed"] is False
    assert reconciliation["r3_evidence_hashes"] == phase.R3_EVIDENCE_SHA256


def test_composite_policy_report_addendum_and_machine_inventories_reconcile(independent_builds):
    left, _, _, _ = independent_builds
    for relative in (phase.ADDENDUM_PATH, phase.R0_POLICY_PATH, phase.R0_REPORT_PATH):
        assert phase._inventory_from_markdown(PROJECT / relative) == phase.R0_ARTIFACT_NAMES
    referenced = _load(left / "referenced_r0_artifacts.json")
    assert [Path(item["relative_path"]).name for item in referenced["artifacts"]] == list(phase.R0_ARTIFACT_NAMES)
    assert _load(left / "artifact_hashes.json")["artifact_inventory"] == list(phase.R01_ARTIFACTS)
    assert _load(left / "summary.json")["artifact_inventory"] == list(phase.R01_ARTIFACTS)


def test_changed_root_dictionary_refuses(tmp_path):
    root = _isolated_project(tmp_path)
    (root / phase.ROOT_DICTIONARY_PATH).write_bytes((root / phase.ROOT_DICTIONARY_PATH).read_bytes() + b"\n")
    with pytest.raises(phase.ReconciliationError, match="hash mismatch"):
        phase.build(root, root / "out", enforce_git_state=False)
    assert not (root / "out").exists()


def test_changed_addendum_refuses(tmp_path):
    root = _isolated_project(tmp_path)
    (root / phase.ADDENDUM_PATH).write_bytes((root / phase.ADDENDUM_PATH).read_bytes() + b"\n")
    with pytest.raises(phase.ReconciliationError, match="hash mismatch"):
        phase.build(root, root / "out", enforce_git_state=False)
    assert not (root / "out").exists()


def test_changed_original_r0_artifact_refuses(tmp_path):
    root = _isolated_project(tmp_path)
    path = root / phase.R0_DIRECTORY / "summary.json"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(phase.ReconciliationError, match="original R0 artifact mismatch"):
        phase.build(root, root / "out", enforce_git_state=False)
    assert not (root / "out").exists()


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_missing_or_extra_original_r0_artifact_refuses(tmp_path, mutation):
    root = _isolated_project(tmp_path)
    directory = root / phase.R0_DIRECTORY
    if mutation == "missing":
        (directory / "summary.json").unlink()
    else:
        (directory / "unexpected.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(phase.ReconciliationError, match="inventory mismatch"):
        phase.build(root, root / "out", enforce_git_state=False)
    assert not (root / "out").exists()


@pytest.mark.parametrize("partial", [False, True])
def test_existing_or_partial_r0_1_refuses_without_mutation(tmp_path, partial):
    root = _isolated_project(tmp_path)
    output = root / "out"
    output.mkdir()
    if partial:
        (output / "partial.json").write_text("{\"preserve\":true}\n", encoding="utf-8")
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    with pytest.raises(phase.ReconciliationError, match="restart refusal"):
        phase.build(root, output, enforce_git_state=False)
    assert {path.name: path.read_bytes() for path in output.iterdir()} == before


def test_protected_synthetic_identities_reject_before_access(monkeypatch):
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("protected path was opened"))
    with pytest.raises(phase.ReconciliationError, match="path"):
        phase.read_bytes(Path("evidence/2025-26/body.json"))
    with pytest.raises(phase.ReconciliationError, match="label"):
        phase.reject_protected_label("2025-26")
    with pytest.raises(phase.ReconciliationError, match="request identity"):
        phase.reject_protected_request_identity({"Season": "2025-26"})
    with pytest.raises(phase.ReconciliationError, match="payload identity"):
        phase.reject_protected_payload_identity({"request_identity": {"season": "2025-26"}})


def test_offline_scope_prohibits_network():
    with phase.offline_scope():
        with pytest.raises(phase.ReconciliationError, match="network access"):
            socket.getaddrinfo("example.com", 443)


def test_source_has_no_estimator_import_construction_or_model_operation():
    paths = [
        PROJECT / "src/pair_fit_v2/phase3f_r0_1_documentation_reconciliation.py",
        PROJECT / "src/pair_fit_v2/phase3f_r0_1_cli.py",
    ]
    prohibited_calls = {"fit", "predict", "fit_predict", "Ridge", "HistGradientBoostingRegressor"}
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert "sklearn" not in source
        assert not any(
            isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id in prohibited_calls)
                or (isinstance(node.func, ast.Attribute) and node.func.attr in prohibited_calls)
            )
            for node in ast.walk(tree)
        )


def test_no_prediction_metric_model_training_row_target_or_feature_artifact(independent_builds):
    left, _, _, _ = independent_builds
    forbidden_tokens = ("prediction", "metric", "model", "training", "target", "feature")
    assert all(not any(token in path.name.lower() for token in forbidden_tokens) for path in left.iterdir())
    assert all(path.suffix == ".json" for path in left.iterdir())


def test_two_builds_are_byte_identical(independent_builds):
    left, right, first, second = independent_builds
    assert first == second
    for name in phase.R01_ARTIFACTS:
        assert (left / name).read_bytes() == (right / name).read_bytes()


def test_two_payload_nonrecursive_hash_manifest(independent_builds):
    left, _, _, _ = independent_builds
    manifest = _load(left / "artifact_hashes.json")
    assert manifest["payload_artifacts"] == list(phase.R01_PAYLOAD_ARTIFACTS)
    assert manifest["excluded_from_own_manifest"] == list(phase.R01_BOOKKEEPING_ARTIFACTS)
    assert set(manifest["artifacts"]) == set(phase.R01_PAYLOAD_ARTIFACTS)
    for name, identity in manifest["artifacts"].items():
        assert identity == {
            "bytes": (left / name).stat().st_size,
            "sha256": phase.sha256_file(left / name),
        }


def test_summary_preserves_scientific_contract_and_negative_assertions(independent_builds):
    left, _, _, _ = independent_builds
    summary = _load(left / "summary.json")
    assert summary["original_r0_status"] == "BLOCKED — documentation-contract conflict"
    assert summary["r0_1_status"] == "documentation reconciliation completed"
    assert summary["composite_checkpoint_status"] == "Phase 3F-R0 final-test pipeline frozen; ready for read-only audit"
    assert (summary["expanded_training_rows"], summary["historical_rows"], summary["spent_development_rows"]) == (29701, 27001, 2700)
    assert summary["feature_count"] == 45
    assert summary["scientific_contract_unchanged"] is True
    for key in (
        "protected_final_test_evidence_accessed", "estimator_constructed", "estimator_trained",
        "prediction_generated", "metric_generated", "network_access", "commit_performed", "push_performed",
    ):
        assert summary[key] is False


def test_git_visible_allowlist_and_ignore_behavior():
    phase.validate_git_state(PROJECT)
    result = subprocess.run(
        ["git", "check-ignore", "-q", "curated/phase3f-r0.1/ignore-probe"],
        cwd=PROJECT,
        check=False,
    )
    assert result.returncode == 0


def test_prohibited_artifact_scan(independent_builds):
    left, _, _, _ = independent_builds
    prohibited_suffixes = {".csv", ".joblib", ".pkl", ".pickle", ".parquet", ".feather", ".db", ".sqlite"}
    assert not [path for path in left.rglob("*") if path.is_file() and path.suffix.lower() in prohibited_suffixes]
    assert {path.name for path in left.iterdir()} == set(phase.R01_ARTIFACTS)
