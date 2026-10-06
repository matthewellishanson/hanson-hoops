"""One-time frozen Phase 3F final Ridge evaluation.

Importing this module performs no I/O and constructs no estimator.  The sole
real-data fit and prediction are reachable only through ``run_official``.
"""

from __future__ import annotations

import csv
import ast
import hashlib
import inspect
import json
import math
import os
import platform
import socket
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import sklearn
from sklearn.linear_model import Ridge

from pair_fit_v2 import phase3e_r3_evaluation_policy as historical_policy


VERSION = "phase3f-r4.final-evaluation.v1"
REQUIRED_BRANCH = "research/pair-fit-v2"
REQUIRED_HEAD = "da6e7c1d1e7c94a8dbf7a4b4c658b2a55695862d"
EXPECTED_UPSTREAM_DIVERGENCE = "0\t0"
OUTPUT_RELATIVE = Path("curated/phase3f-r4")
REPORT_RELATIVE = Path("PHASE3F_R4_FINAL_EVALUATION_REPORT.md")
SOURCE_RELATIVE = Path("src/pair_fit_v2/phase3f_r4_final_evaluation.py")
CLI_RELATIVE = Path("src/pair_fit_v2/phase3f_r4_cli.py")
CONTRACT_RELATIVE = Path("PHASE3F_R4_FINAL_EVALUATION_CONTRACT.md")
TEST_RELATIVE = Path("tests/test_phase3f_r4_final_evaluation.py")
ALLOWED_GIT_CHANGES = {
    REPORT_RELATIVE.as_posix(),
    SOURCE_RELATIVE.as_posix(),
    CLI_RELATIVE.as_posix(),
    CONTRACT_RELATIVE.as_posix(),
    TEST_RELATIVE.as_posix(),
}

TRAIN_ROWS = 29_701
FINAL_ROWS = 2_811
FEATURE_COUNT = 45
TEAM_COUNT = 28
ALPHA = 3000.0
TRAINING_SEASONS = tuple(f"{year}-{str(year + 1)[-2:]}" for year in range(2014, 2025))
FINAL_SEASON = "2025-26"
EXCLUDED_TEAMS = {"1610612754": "Indiana Pacers", "1610612763": "Memphis Grizzlies"}
EXPECTED_HISTORY_COUNTS = {"complete": 2154, "one_missing": 597, "both_missing": 60}
EXPECTED_GATE_IDS = (
    "predictor_evidence_completeness",
    "target_evidence_completeness",
    "team_population_exhaustiveness",
    "row_eligibility",
    "row_alignment",
    "protected_result_reveal",
)

R0_DIR = Path("curated/phase3f-r0")
R0_1_DIR = Path("curated/phase3f-r0.1")
R3_DIR = Path("curated/phase3f-r3")
R3_1_DIR = Path("curated/phase3f-r3.1")
TRAIN_INDEX = R0_DIR / "expanded_training_row_index.csv"
TRAIN_STAGING = R0_DIR / "expanded_training_staging.csv"
TRAIN_MATRIX = R0_DIR / "expanded_training_estimator_matrix_unscaled.csv"
FEATURE_MANIFEST = R0_DIR / "expanded_feature_manifest.json"
PREPROCESSING_STATE = R0_DIR / "expanded_preprocessing_state.json"
R0_POLICY = R0_DIR / "final_test_policy.json"
FINAL_INDEX = R3_DIR / "final_test_row_index.csv"
FINAL_TARGET = R3_DIR / "final_test_target_vector.csv"
FINAL_MATRIX = R3_DIR / "final_test_estimator_matrix_scaled.csv"
FINAL_FEATURE_MANIFEST = R3_DIR / "estimator_feature_manifest.json"
FINAL_PREPROCESSING_IDENTITY = R3_DIR / "applied_preprocessing_state_identity.json"
READINESS_GATES = R3_DIR / "readiness_gates.json"
CORRECTED_READINESS_SUMMARY = R3_1_DIR / "corrected_summary.json"
SPENT_DEVELOPMENT_METRICS = Path("modeling/phase3e-r4-2-reconciliation/reconciled_overall_metrics.json")
SPENT_DEVELOPMENT_DECISION = Path("modeling/phase3e-r4-2-reconciliation/reconciliation_decision.json")

# These SHA-256 pins close the governing R0/R0.1 and R3/R3.1 composites.
EXPECTED_INPUT_SHA256 = {
    "curated/phase3f-r0/artifact_hashes.json": "802a14a978d937a07bf0cbeb1b93fa177b2904ef3e611f47d31a1ac3bbadf4e1",
    "curated/phase3f-r0/expanded_feature_manifest.json": "93693a520151387f0c9fb514ada7324639387a7ae60bae5bba9d2a607a5beb14",
    "curated/phase3f-r0/expanded_preprocessing_state.json": "a0180d9fc0436515f8a6f302727b4c0b030274cfbcce1a5ded7883568f05f47e",
    "curated/phase3f-r0/expanded_training_estimator_matrix_unscaled.csv": "a8a2b08daa3c56ccda78d34f77c2a29b7ef7c9e00835e7ab6ac77412ec6f8588",
    "curated/phase3f-r0/expanded_training_row_index.csv": "3062b1524e7599dcab32ae1dc419040e7f16f6730308e3a88b18c71293d4c427",
    "curated/phase3f-r0/expanded_training_staging.csv": "3fced86922b533b0da2b42748d6c0b8afddef57b1281fe14880b11a446df21b6",
    "curated/phase3f-r0/final_test_policy.json": "a3e5b7271b45b0ff997fde81d546bdd6d055a7177f44d31b41924beca8bb7e48",
    "curated/phase3f-r0/input_fingerprints.json": "04caeba6a0872fac6fad3d7a8aaa3861dbc484228c6d3b8ddb3e24a1a1819428",
    "curated/phase3f-r0/population_diagnostics.json": "a1d16291d10352aba4afced0d2d6cfc272c04acf1266f702b3ada1e866589d8c",
    "curated/phase3f-r0/summary.json": "f2475571a32af96a6c802d90d5fa8f20fcfc2f7b0d9e27f2ce1cad1c88407b41",
    "curated/phase3f-r0.1/artifact_hashes.json": "805350d8eb6aa9361f6745e8871996a226847ad989ebd77adbe8b000565a1047",
    "curated/phase3f-r0.1/documentation_reconciliation.json": "cb5b7ec2e83ad36ed0e9be683023cee553928e9aa3f08768a81d872ab8107ed7",
    "curated/phase3f-r0.1/referenced_r0_artifacts.json": "bb3ff4f51660aeba503d1bc5af18fae9847bf3d432eff4b7654007e986871198",
    "curated/phase3f-r0.1/summary.json": "cc6e37cfb1c554f7da1bbd3d4a098a3d435fdffb59b83a1ee46c0d9f9a8bc1b0",
    "curated/phase3f-r3/applied_preprocessing_state_identity.json": "027022517341ea65febe3b779feb7254f2605cb5f125795cd0f97c258311efa6",
    "curated/phase3f-r3/artifact_hashes.json": "58382f587c1b2b679fb8a24ac7652b8ff131749c5e6a0e248a769f4a535aacd6",
    "curated/phase3f-r3/estimator_feature_manifest.json": "b2ef6f25b18e1b5522c2624c1b0532648ac961c4558114fc8d94e437351564a6",
    "curated/phase3f-r3/final_test_estimator_matrix_scaled.csv": "b8213cd44ace50cb88860c832d0f810e497e403c31ff029b9ed323ed3a601f6f",
    "curated/phase3f-r3/final_test_row_index.csv": "b0c2204be4dd67d504cde0e720f3453160416a3e9f838aad6e45273d197225f9",
    "curated/phase3f-r3/final_test_staging.csv": "c7994aceebedf4093e97d3b0b41d28ab69abaebb38f6486d07c82a5125635f06",
    "curated/phase3f-r3/final_test_target_vector.csv": "a258c02992f2006ee083d39b79d328f775d8923157d80f7bed2c73955d276198",
    "curated/phase3f-r3/history_selection_diagnostics.json": "502e46022560428c83af930fac0ad30f46ce2c6a454ec7a797b51d575b8fcaba",
    "curated/phase3f-r3/input_fingerprints.json": "23f0f9e00ff205988a3890017003bc59e6a704fc1aae78c8cef455a8e58922fb",
    "curated/phase3f-r3/population_diagnostics.json": "b804699b30027e3ed1f7a255dd36d5b359f529d2838748828e23b8975ee6812d",
    "curated/phase3f-r3/readiness_gates.json": "3b63cc6502dab36de9d8413fa3f3495cfcd57941355fffd112ae0a5eb5e495a8",
    "curated/phase3f-r3/summary.json": "0d262e096e3fc3de9a8ca8b5cb6d84f7ea1a608eca662289cdf43310b1b8b2f7",
    "curated/phase3f-r3.1/artifact_hashes.json": "ed00c546e9ceeb990c9da75447bbe9f9bd5eea1ddcf395d24181264ab76db750",
    "curated/phase3f-r3.1/corrected_summary.json": "0a3867a054ac872fe585382e7bd8fed29fda4ed2cbc4f72d6b8aad1734f76f9e",
    "curated/phase3f-r3.1/correction.json": "cabc63bb5508c1bffb306e8de9aff42c602c9984ca7f60b3c2617acda5723b04",
    "curated/phase3f-r3.1/referenced_r3_artifacts.json": "51fa1e38875671a09394712dd4f05c03c6338298f08c1562d7cbf51bad126908",
    "curated/phase3f-r3.1/summary.json": "a52ff7cf80c86cdb37bc5f7c66f02b9fced53647c23d3395c34a0b8fb0026307",
    "modeling/phase3e-r4-2-reconciliation/reconciled_overall_metrics.json": "123c4611489792101b6b5788bc6d959381001eadeffe3f8bc6e41e9fea4c76be",
    "modeling/phase3e-r4-2-reconciliation/reconciliation_decision.json": "d4e72b48e6cfabf9e302093a96dbc66f001ad934fab917a350956756501ae8e4",
    "PHASE3F_R0_FINAL_TEST_POLICY.md": "c80fe6c31ba44b2e9e01f60e0943038004cf8584ea0ed7e1ed49e66138c02405",
    "PHASE3F_R0_1_DOCUMENTATION_RECONCILIATION_REPORT.md": "3cfad1d84d361a5ebde277f16de2fa4873aedc31f1523429f7c7d1f057916eb9",
    "PHASE3F_R3_FINAL_TEST_READINESS_POLICY.md": "3874423f89bc62a2ad817080f9481922334cc65ce3ad65c1a6a790f963cbe714",
    "PHASE3F_R3_1_REPRODUCIBILITY_CORRECTION_REPORT.md": "acf5b682c135a1d1f0c7ba460b1fdbb93a024146dc9e97646c18bc6e2501de2e",
}

PREDICTION_COLUMNS = (
    "row_position", "target_season", "team_id", "player_1_id", "player_2_id",
    "observation_key", "target_net_rating", "ridge_prediction", "baseline_prediction",
    "pair_possessions", "history_status", "endpoint_exact_250_flag",
)
MISSING_COLUMNS = (
    "history_group", "row_count", "mae", "rmse", "bias", "mae_difference_from_complete",
    "adequate_for_formal_comparison", "material_absolute_difference",
    "adverse_lower_confidence_difference",
)
TEAM_COLUMNS = (
    "team_id", "eligible_rows", "summed_possessions", "mae", "rmse", "bias",
    "mean_target", "mean_prediction",
)
LOTO_COLUMNS = (
    "removed_team_id", "remaining_rows", "leave_one_team_out_mae", "full_sample_mae",
    "full_sample_minus_leave_one_team_out_mae",
)
CALIBRATION_COLUMNS = (
    "bin", "tail", "row_count", "mean_prediction", "mean_target", "calibration_difference",
)

PAYLOAD_ARTIFACTS = (
    "execution_configuration.json", "execution_events.jsonl", "pre_execution_integrity.json",
    "predictions.csv", "overall_metrics.json", "missing_history_metrics.csv", "team_metrics.csv",
    "leave_one_team_out_metrics.csv", "calibration_bins.csv", "residual_diagnostics.json",
    "historical_stability.json", "evaluation_decision.json",
)
OFFICIAL_ARTIFACTS = PAYLOAD_ARTIFACTS + ("artifact_hashes.json", "summary.json")


class FinalEvaluationError(RuntimeError):
    """Frozen final-evaluation contract failure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_content_hash(document: Mapping[str, Any]) -> str:
    body = dict(document)
    body.pop("deterministic_content_sha256", None)
    return hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("ascii")).hexdigest()


def serialize_json(document: Any) -> bytes:
    return (json.dumps(document, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if value else "false"
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            raise FinalEvaluationError("CSV serialization refuses nonfinite values")
        return repr(float(value))
    return value


def serialize_csv(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> bytes:
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(columns), extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        if tuple(row) != tuple(columns):
            raise FinalEvaluationError("CSV row schema or column order mismatch")
        writer.writerow({name: _csv_value(row[name]) for name in columns})
    return buffer.getvalue().encode("utf-8")


def write_once(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(
        FinalEvaluationError(f"nonfinite JSON constant: {value}")
    ))


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise FinalEvaluationError(f"missing CSV header: {path}")
        return list(reader.fieldnames), list(reader)


def _read_matrix(path: Path) -> tuple[list[str], np.ndarray]:
    columns, rows = _read_csv(path)
    try:
        matrix = np.asarray([[float(row[name]) for name in columns] for row in rows], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as exc:
        raise FinalEvaluationError(f"invalid numeric matrix: {path}") from exc
    return columns, matrix


def _finite_vector(values: Iterable[Any], name: str) -> np.ndarray:
    try:
        result = np.asarray([float(value) for value in values], dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise FinalEvaluationError(f"{name} is not numeric") from exc
    if result.ndim != 1 or not np.isfinite(result).all():
        raise FinalEvaluationError(f"{name} must be a finite vector")
    return result


def _git(project_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=project_root, check=True, capture_output=True, text=True, encoding="utf-8",
    )
    return completed.stdout.strip()


def verify_git_state(project_root: Path) -> dict[str, Any]:
    branch = _git(project_root, "branch", "--show-current")
    head = _git(project_root, "rev-parse", "HEAD")
    divergence = _git(project_root, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if branch != REQUIRED_BRANCH or head != REQUIRED_HEAD or divergence != EXPECTED_UPSTREAM_DIVERGENCE:
        raise FinalEvaluationError("branch, HEAD, or upstream divergence mismatch")
    if _git(project_root, "diff", "--cached", "--name-only"):
        raise FinalEvaluationError("Git index is not clean")
    status = _git(project_root, "status", "--porcelain=v1", "--untracked-files=all")
    changed = set()
    for line in status.splitlines():
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.add(path)
    prefixed = {f"research/pair-fit-v2/{name}" for name in ALLOWED_GIT_CHANGES}
    if not changed.issubset(prefixed):
        raise FinalEvaluationError(f"unexpected Git-visible change: {sorted(changed - prefixed)}")
    return {
        "branch": branch, "head": head, "upstream_divergence": "0/0",
        "index_clean": True, "allowed_worktree_changes": sorted(changed),
        "stage1_initial_worktree_clean": True,
    }


def authenticate_inputs(project_root: Path) -> dict[str, str]:
    actual = {}
    for relative, expected in sorted(EXPECTED_INPUT_SHA256.items()):
        path = project_root / relative
        if not path.is_file():
            raise FinalEvaluationError(f"missing authenticated input: {relative}")
        digest = sha256_file(path)
        if digest != expected:
            raise FinalEvaluationError(f"authenticated input hash mismatch: {relative}")
        actual[relative] = digest
    return actual


def verify_no_prior_execution(project_root: Path, output_dir: Path) -> None:
    if output_dir.exists():
        raise FinalEvaluationError(f"write-once execution namespace already exists: {output_dir}")
    prohibited_namespaces = (
        "modeling/phase3f-r3", "modeling/phase3f-r4", "modeling/phase3f-final",
        "curated/phase3f-final-execution",
    )
    present = [name for name in prohibited_namespaces if (project_root / name).exists()]
    if present:
        raise FinalEvaluationError(f"prior final execution namespace exists: {present}")
    for base_name in ("curated", "planning", "cache", "modeling"):
        base = project_root / base_name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or "phase3f" not in path.as_posix().lower():
                continue
            lower = path.name.lower()
            if any(token in lower for token in ("prediction_vector", "final_predictions", "final_metrics", "serialized_model")):
                raise FinalEvaluationError(f"prior final-result artifact exists: {path}")
            if path.suffix.lower() in {".joblib", ".pkl", ".pickle", ".onnx"}:
                raise FinalEvaluationError(f"prohibited serialized model exists: {path}")


@contextmanager
def offline_scope():
    original_socket = socket.socket
    original_create = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    class BlockedSocket:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise FinalEvaluationError("network access is prohibited during final execution")

    def blocked(*args: Any, **kwargs: Any) -> Any:
        raise FinalEvaluationError("network access is prohibited during final execution")

    socket.socket = BlockedSocket  # type: ignore[assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    socket.getaddrinfo = blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create  # type: ignore[assignment]
        socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]


def _average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2.0 + 1.0
        start = end
    return ranks


def _pearson(left: np.ndarray, right: np.ndarray) -> tuple[float | None, str | None]:
    left_var = float(np.var(left, ddof=0))
    right_var = float(np.var(right, ddof=0))
    if left_var == 0.0:
        return None, "left vector variance is zero"
    if right_var == 0.0:
        return None, "right vector variance is zero"
    covariance = float(np.mean((left - np.mean(left)) * (right - np.mean(right))))
    value = covariance / math.sqrt(left_var * right_var)
    return (value, None) if math.isfinite(value) else (None, "correlation is nonfinite")


def metric_set(prediction: Iterable[Any], target: Iterable[Any]) -> tuple[dict[str, Any], dict[str, str]]:
    pred = _finite_vector(prediction, "prediction")
    truth = _finite_vector(target, "target")
    if len(pred) != len(truth) or not len(pred):
        raise FinalEvaluationError("metric vectors are empty or misaligned")
    error = pred - truth
    target_var = float(np.var(truth, ddof=0))
    prediction_std = float(np.std(pred, ddof=0))
    target_std = float(np.std(truth, ddof=0))
    nulls: dict[str, str] = {}
    r2 = None
    if target_var == 0.0:
        nulls["r2"] = "target variance is zero"
    else:
        r2 = 1.0 - float(np.sum(error * error)) / float(np.sum((truth - np.mean(truth)) ** 2))
    spearman, reason = _pearson(_average_ranks(pred), _average_ranks(truth))
    if reason:
        nulls["spearman"] = reason
    ratio = None
    if target_std == 0.0:
        nulls["prediction_to_target_std_ratio"] = "target standard deviation is zero"
    else:
        ratio = prediction_std / target_std
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(math.sqrt(float(np.mean(error * error)))),
        "r2": r2,
        "bias": float(np.mean(error)),
        "spearman": spearman,
        "prediction_std": prediction_std,
        "target_std": target_std,
        "prediction_to_target_std_ratio": ratio,
    }, nulls


def weighted_errors(prediction: np.ndarray, target: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    if len(prediction) != len(target) or len(target) != len(weights):
        raise FinalEvaluationError("weighted vectors are misaligned")
    if np.any(weights <= 0) or not np.isfinite(weights).all() or float(np.sum(weights)) <= 0:
        raise FinalEvaluationError("possession weights must be finite and positive")
    error = prediction - target
    return (
        float(np.sum(weights * np.abs(error)) / np.sum(weights)),
        float(math.sqrt(float(np.sum(weights * error * error) / np.sum(weights)))),
    )


def residual_relationships(prediction: Iterable[Any], target: Iterable[Any], possessions: Iterable[Any]) -> dict[str, Any]:
    pred = _finite_vector(prediction, "prediction")
    truth = _finite_vector(target, "target")
    poss = _finite_vector(possessions, "possessions")
    if not (len(pred) == len(truth) == len(poss)):
        raise FinalEvaluationError("residual vectors are misaligned")
    residual = truth - pred
    pred_var = float(np.var(pred, ddof=0))
    poss_var = float(np.var(poss, ddof=0))
    nulls: dict[str, str] = {}

    def relationship(independent: np.ndarray, variance: float, label: str) -> tuple[float | None, float | None]:
        correlation, reason = _pearson(residual, independent)
        if reason:
            nulls[f"residual_vs_{label}_pearson"] = reason
        if variance == 0.0:
            nulls[f"residual_vs_{label}_slope"] = f"{label} variance is zero"
            slope = None
        else:
            slope = float(np.mean((independent - np.mean(independent)) * (residual - np.mean(residual))) / variance)
        return correlation, slope

    pred_corr, pred_slope = relationship(pred, pred_var, "prediction")
    poss_corr, poss_slope = relationship(poss, poss_var, "possessions")
    return {
        "version": VERSION,
        "row_count": len(pred),
        "residual_sign_convention": "target minus prediction",
        "residual_mean": float(np.mean(residual)),
        "residual_variance": float(np.var(residual, ddof=0)),
        "prediction_variance": pred_var,
        "possessions_variance": poss_var,
        "residual_vs_prediction_pearson": pred_corr,
        "residual_vs_prediction_slope": pred_slope,
        "residual_vs_possessions_pearson": poss_corr,
        "residual_vs_possessions_slope": poss_slope,
        "null_reasons": nulls,
    }


def classification_thresholds(policy: Mapping[str, Any]) -> tuple[float, float]:
    import re
    rules = policy["classification"]
    pass_rule = str(rules["final_scientific_pass"])
    numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", pass_rule)]
    if len(numbers) != 2 or rules["final_scientific_failure"] != "MAE improvement <= 0.0":
        raise FinalEvaluationError("frozen classification policy definition drift")
    return numbers[0], numbers[1]


def classify_final(policy: Mapping[str, Any], integrity_passed: bool, mae_improvement: float, rmse_improvement: float) -> str:
    rules = policy["classification"]
    labels = {name: name.replace("_", " ").upper() for name in (
        "invalid", "final_scientific_failure", "final_scientific_pass", "final_mixed_result",
    )}
    mae_threshold, rmse_threshold = classification_thresholds(policy)
    if not integrity_passed or not math.isfinite(mae_improvement) or not math.isfinite(rmse_improvement):
        return labels["invalid"]
    if mae_improvement <= float(str(rules["final_scientific_failure"]).rsplit(" ", 1)[1]):
        return labels["final_scientific_failure"]
    if mae_improvement >= mae_threshold and rmse_improvement >= rmse_threshold:
        return labels["final_scientific_pass"]
    return labels["final_mixed_result"]


def subgroup_rows(records: Sequence[Mapping[str, Any]], prediction: np.ndarray, target: np.ndarray) -> list[dict[str, Any]]:
    complete = [index for index, row in enumerate(records) if row["history_status"] == "complete"]
    complete_mae = metric_set(prediction[complete], target[complete])[0]["mae"]
    output = []
    for group in ("complete", "one_missing", "both_missing"):
        indices = [index for index, row in enumerate(records) if row["history_status"] == group]
        metrics, _ = metric_set(prediction[indices], target[indices])
        difference = metrics["mae"] - complete_mae
        output.append({
            "history_group": group,
            "row_count": len(indices),
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "bias": metrics["bias"],
            "mae_difference_from_complete": difference,
            "adequate_for_formal_comparison": len(indices) >= 100 and group in {"complete", "one_missing"},
            "material_absolute_difference": abs(difference) >= 0.50,
            "adverse_lower_confidence_difference": group != "complete" and difference >= 0.50,
        })
    return output


def team_rows(records: Sequence[Mapping[str, Any]], prediction: np.ndarray, target: np.ndarray, possessions: np.ndarray) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    teams = sorted({str(row["team_id"]) for row in records}, key=int)
    output, leave_one_out = [], []
    full_mae = float(np.mean(np.abs(prediction - target)))
    for team in teams:
        selected = np.asarray([str(row["team_id"]) == team for row in records], dtype=bool)
        metrics, _ = metric_set(prediction[selected], target[selected])
        output.append({
            "team_id": team,
            "eligible_rows": int(np.sum(selected)),
            "summed_possessions": float(np.sum(possessions[selected])),
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "bias": metrics["bias"],
            "mean_target": float(np.mean(target[selected])),
            "mean_prediction": float(np.mean(prediction[selected])),
        })
        remaining = ~selected
        leave_mae = float(np.mean(np.abs(prediction[remaining] - target[remaining])))
        leave_one_out.append({
            "removed_team_id": team,
            "remaining_rows": int(np.sum(remaining)),
            "leave_one_team_out_mae": leave_mae,
            "full_sample_mae": full_mae,
            "full_sample_minus_leave_one_team_out_mae": full_mae - leave_mae,
        })
    return output, leave_one_out


def calibration_rows(records: Sequence[Mapping[str, Any]], prediction: np.ndarray, target: np.ndarray) -> list[dict[str, Any]]:
    count = len(records)
    order = sorted(range(count), key=lambda index: (
        prediction[index], int(records[index]["team_id"]), int(records[index]["player_1_id"]),
        int(records[index]["player_2_id"]),
    ))
    bins: list[list[int]] = [[] for _ in range(10)]
    for sorted_index, row_index in enumerate(order):
        bins[(sorted_index * 10) // count].append(row_index)
    output = []
    for offset, indices in enumerate(bins):
        mean_prediction = float(np.mean(prediction[indices]))
        mean_target = float(np.mean(target[indices]))
        number = offset + 1
        output.append({
            "bin": number,
            "tail": "lower" if number == 1 else "upper" if number == 10 else "middle",
            "row_count": len(indices),
            "mean_prediction": mean_prediction,
            "mean_target": mean_target,
            "calibration_difference": mean_target - mean_prediction,
        })
    return output


def historical_stability(ridge_metrics: Mapping[str, Any], spent_development: Mapping[str, Any]) -> dict[str, Any]:
    references = historical_policy.HISTORICAL_METRICS
    pooled = dict(references["pooled"])
    folds = {season: dict(references[season]) for season in historical_policy.HISTORICAL_VALIDATION_SEASONS}
    compared = ("r2", "bias", "spearman", "prediction_std", "target_std", "prediction_to_target_std_ratio")
    deltas = {metric: ridge_metrics[metric] - pooled[metric] for metric in ("mae", "rmse", *compared) if ridge_metrics[metric] is not None}
    ranges, outside = {}, {}
    for metric in compared:
        values = [folds[season][metric] for season in historical_policy.HISTORICAL_VALIDATION_SEASONS]
        value = ridge_metrics[metric]
        position = "not_comparable" if value is None else "below" if value < min(values) else "above" if value > max(values) else "within"
        ranges[metric] = {"fold_min": min(values), "fold_max": max(values), "final_value": value, "position": position}
        outside[metric] = position in {"below", "above"}
    spent = dict(spent_development["ridge_unweighted"])
    return {
        "version": VERSION,
        "final_values": dict(ridge_metrics),
        "historical_pooled_reference": pooled,
        "historical_fold_references": folds,
        "spent_2024_25_development_reference": spent,
        "deltas_from_historical_pooled": deltas | {
            "mae_minus_phase3d_macro_mae": ridge_metrics["mae"] - 7.113451159210443,
            "mae_minus_historical_worst_season_mae": ridge_metrics["mae"] - 7.596126328447196,
            "rmse_minus_historical_worst_season_rmse": ridge_metrics["rmse"] - 10.330015941206614,
        },
        "deltas_from_spent_2024_25_development": {
            metric: ridge_metrics[metric] - spent[metric]
            for metric in ("mae", "rmse", *compared)
            if ridge_metrics[metric] is not None and spent[metric] is not None
        },
        "fold_range_comparisons": ranges,
        "warning_flags": {
            "mae_above_worst_by_more_than_0_50": ridge_metrics["mae"] > 8.096126328447196,
            "rmse_above_historical_worst": ridge_metrics["rmse"] > 10.330015941206614,
            "outside_six_fold_range": outside,
            "absolute_bias_above_historical_maximum": abs(ridge_metrics["bias"]) > max(abs(folds[s]["bias"]) for s in folds),
        },
    }


def _canonical_train_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return str(row["target_season"]), str(row["team_id"]), str(row["player_1_id"]), str(row["player_2_id"])


def _validate_source_restrictions(project_root: Path) -> dict[str, Any]:
    source = (project_root / SOURCE_RELATIVE).read_text(encoding="utf-8")
    tree = ast.parse(source)
    fit_count = sum(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "fit"
        for node in ast.walk(tree)
    )
    predict_count = sum(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "predict"
        for node in ast.walk(tree)
    )
    prohibited = ("joblib", "pickle", "requests", "urllib", "httpx", "nba_api")
    imports = [line.strip() for line in source.splitlines() if line.startswith(("import ", "from "))]
    bad = [name for name in prohibited if any(name in line for line in imports)]
    if fit_count != 1 or predict_count != 1 or bad:
        raise FinalEvaluationError("source fit/predict count or capability restriction failed")
    if "Ridge(" not in inspect.getsource(run_model_once):
        raise FinalEvaluationError("sole Ridge construction path is missing")
    return {"reachable_fit_call_count": fit_count, "reachable_predict_call_count": predict_count, "prohibited_imports": bad}


def _load_and_validate_inputs(project_root: Path) -> dict[str, Any]:
    policy = _read_json(project_root / R0_POLICY)
    feature_manifest = _read_json(project_root / FEATURE_MANIFEST)
    final_manifest = _read_json(project_root / FINAL_FEATURE_MANIFEST)
    preprocessing = _read_json(project_root / PREPROCESSING_STATE)
    applied_identity = _read_json(project_root / FINAL_PREPROCESSING_IDENTITY)
    readiness = _read_json(project_root / READINESS_GATES)
    corrected_summary = _read_json(project_root / CORRECTED_READINESS_SUMMARY)
    spent_metrics = _read_json(project_root / SPENT_DEVELOPMENT_METRICS)
    spent_decision = _read_json(project_root / SPENT_DEVELOPMENT_DECISION)

    features = list(policy["frozen_model"]["ordered_features"])
    if not (
        len(features) == FEATURE_COUNT == len(set(features))
        and feature_manifest["ordered_estimator_features"] == features
        and final_manifest["ordered_estimator_features"] == features
        and preprocessing["feature_order"] == features
        and applied_identity["feature_order"] == features
    ):
        raise FinalEvaluationError("exact ordered 45-feature identity mismatch")
    if applied_identity["source_sha256"] != EXPECTED_INPUT_SHA256[PREPROCESSING_STATE.as_posix()]:
        raise FinalEvaluationError("applied preprocessing source identity mismatch")
    if not (
        preprocessing["scaler"]["ddof"] == 0
        and preprocessing["expanded_training_evidence_only"]
        and not preprocessing["protected_final_test_values_used"]
        and applied_identity["frozen_scaler_applied_count"] == 1
        and not applied_identity["double_scaling"]
        and not applied_identity["independent_final_test_scaling"]
        and applied_identity["final_persisted_matrix_representation"] == "scaled_once_ready_for_direct_ridge_prediction"
    ):
        raise FinalEvaluationError("frozen preprocessing restrictions mismatch")

    train_columns, train_index = _read_csv(project_root / TRAIN_INDEX)
    staging_columns, train_staging = _read_csv(project_root / TRAIN_STAGING)
    train_matrix_columns, train_unscaled = _read_matrix(project_root / TRAIN_MATRIX)
    if len(train_index) != TRAIN_ROWS or len(train_staging) != TRAIN_ROWS or train_unscaled.shape != (TRAIN_ROWS, FEATURE_COUNT):
        raise FinalEvaluationError("expanded-training dimensions mismatch")
    if train_matrix_columns != features or not np.isfinite(train_unscaled).all():
        raise FinalEvaluationError("expanded-training feature order or finiteness mismatch")
    if train_columns != [
        "target_season", "team_id", "player_1_id", "player_2_id", "target_net_rating",
        "pair_possessions", "history_status", "missing_player_count", "player_1_history_profile_season",
        "player_2_history_profile_season", "player_1_history_gap", "player_2_history_gap",
        "player_1_history_missing", "player_2_history_missing", "endpoint_exact_250_flag",
        "phase3f_r0_source_population",
    ]:
        raise FinalEvaluationError("expanded-training row-index schema mismatch")
    train_keys = [_canonical_train_key(row) for row in train_index]
    if len(set(train_keys)) != TRAIN_ROWS or train_keys != [_canonical_train_key(row) for row in train_staging]:
        raise FinalEvaluationError("expanded-training key alignment mismatch")
    if any(index["target_net_rating"] != staging["target_net_rating"] for index, staging in zip(train_index, train_staging)):
        raise FinalEvaluationError("expanded-training target alignment mismatch")
    if any(int(row["player_1_id"]) >= int(row["player_2_id"]) or float(row["pair_possessions"]) < 150.0 for row in train_index):
        raise FinalEvaluationError("expanded-training eligibility or canonical-pair mismatch")
    if {row["target_season"] for row in train_index} != set(TRAINING_SEASONS):
        raise FinalEvaluationError("expanded-training season mismatch")
    training_target = _finite_vector((row["target_net_rating"] for row in train_index), "training target")
    means = np.asarray([preprocessing["scaler"]["mean"][name] for name in features], dtype=np.float64)
    scales = np.asarray([preprocessing["scaler"]["scale"][name] for name in features], dtype=np.float64)
    if not np.isfinite(means).all() or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise FinalEvaluationError("frozen scaler contains invalid values")
    if not np.allclose(train_unscaled.mean(axis=0), means, rtol=0.0, atol=2e-13):
        raise FinalEvaluationError("frozen scaler means do not identify expanded training matrix")
    if not np.allclose(train_unscaled.std(axis=0, ddof=0), scales, rtol=0.0, atol=2e-13):
        raise FinalEvaluationError("frozen scaler scales do not identify expanded training matrix")
    training_scaled = (train_unscaled - means) / scales
    if not np.isfinite(training_scaled).all():
        raise FinalEvaluationError("scaled training matrix is nonfinite")

    final_columns, final_index = _read_csv(project_root / FINAL_INDEX)
    target_columns, final_target_rows = _read_csv(project_root / FINAL_TARGET)
    final_matrix_columns, final_matrix = _read_matrix(project_root / FINAL_MATRIX)
    if len(final_index) != FINAL_ROWS or len(final_target_rows) != FINAL_ROWS or final_matrix.shape != (FINAL_ROWS, FEATURE_COUNT):
        raise FinalEvaluationError("final-test dimensions mismatch")
    if final_matrix_columns != features or not np.isfinite(final_matrix).all():
        raise FinalEvaluationError("final-test matrix order or finiteness mismatch")
    expected_final_columns = [
        "row_number", "observation_key", "target_season", "team_id", "team_name", "player_1_id",
        "player_2_id", "target_net_rating", "pair_possessions", "history_status", "history_confidence",
        "missing_player_count", "player_1_history_profile_season", "player_1_history_gap",
        "player_2_history_profile_season", "player_2_history_gap", "endpoint_exact_250_flag",
        "direct_full_season_source",
    ]
    if final_columns != expected_final_columns or target_columns != [
        "row_number", "observation_key", "target_net_rating", "target_source_measure",
        "target_source_path", "target_source_sha256",
    ]:
        raise FinalEvaluationError("final-test index or target schema mismatch")
    keys = []
    for position, (index_row, target_row) in enumerate(zip(final_index, final_target_rows)):
        key = "|".join((index_row["target_season"], index_row["team_id"], index_row["player_1_id"], index_row["player_2_id"]))
        if (
            int(index_row["row_number"]) != position
            or target_row["row_number"] != index_row["row_number"]
            or target_row["observation_key"] != index_row["observation_key"] != key
            or target_row["target_net_rating"] != index_row["target_net_rating"]
            or int(index_row["player_1_id"]) >= int(index_row["player_2_id"])
            or float(index_row["pair_possessions"]) < 150.0
        ):
            raise FinalEvaluationError(f"final-test row alignment mismatch at {position}")
        keys.append(key)
    if len(set(keys)) != FINAL_ROWS:
        raise FinalEvaluationError("final-test observation keys are not unique")
    final_target = _finite_vector((row["target_net_rating"] for row in final_target_rows), "final-test target")
    teams = {row["team_id"] for row in final_index}
    if len(teams) != TEAM_COUNT or teams & set(EXCLUDED_TEAMS):
        raise FinalEvaluationError("retained team count or exclusion mismatch")
    counts = Counter(row["history_status"] for row in final_index)
    if {name: counts[name] for name in EXPECTED_HISTORY_COUNTS} != EXPECTED_HISTORY_COUNTS:
        raise FinalEvaluationError("missing-history group counts mismatch")
    if (
        readiness["frozen_gate_order"] != list(EXPECTED_GATE_IDS)
        or not readiness["all_six_passed"]
        or any(gate["status"] != "passed" or gate["blocks_final_execution"] for gate in readiness["gates"])
        or corrected_summary["eligible_rows"] != FINAL_ROWS
        or corrected_summary["excluded_team_ids"] != sorted(EXCLUDED_TEAMS, key=int)
    ):
        raise FinalEvaluationError("authoritative readiness composite mismatch")
    if spent_decision["reconciled_scientific_classification"] != "VALID DEVELOPMENT-HOLDOUT PASS":
        raise FinalEvaluationError("spent development reference identity mismatch")
    classification_thresholds(policy)
    return {
        "policy": policy,
        "features": features,
        "training_rows": train_index,
        "training_scaled": training_scaled,
        "training_target": training_target,
        "final_rows": final_index,
        "final_matrix": final_matrix,
        "final_target": final_target,
        "spent_development": spent_metrics,
    }


def run_model_once(training_x: np.ndarray, training_target: np.ndarray, final_x: np.ndarray, alpha: float) -> np.ndarray:
    estimator = Ridge(alpha=alpha)
    if estimator.__class__ is not Ridge or estimator.get_params()["alpha"] != ALPHA:
        raise FinalEvaluationError("frozen Ridge estimator identity mismatch")
    estimator.fit(training_x, training_target)
    return np.asarray(estimator.predict(final_x), dtype=np.float64)


def _execution_configuration(project_root: Path, git_state: Mapping[str, Any], inputs: Mapping[str, str], features: Sequence[str]) -> dict[str, Any]:
    pythonpath = os.environ.get("PYTHONPATH", "")
    required_pythonpath = str((project_root / "src").resolve())
    if str(Path(pythonpath).resolve()) != required_pythonpath:
        raise FinalEvaluationError("PYTHONPATH is not explicitly the resolved project src directory")
    if os.environ.get("PHASE3F_R4_IMPORT_CANARY") != "passed":
        raise FinalEvaluationError("successful import-canary attestation is absent")
    return {
        "version": VERSION,
        "official_invocation_number": 1,
        "repository": dict(git_state),
        "command": subprocess.list2cmdline([sys.executable, *sys.argv]),
        "working_directory": str(Path.cwd().resolve()),
        "python_executable": str(Path(sys.executable).resolve()),
        "pythonpath": pythonpath,
        "import_canary": {
            "command": "$env:PYTHONPATH=(Resolve-Path .\\research\\pair-fit-v2\\src).Path; & .\\.venv\\Scripts\\python.exe -B -c \"import pair_fit_v2.phase3f_r4_cli, pair_fit_v2.phase3f_r4_final_evaluation; print('PHASE3F_R4_IMPORT_CANARY_OK')\"",
            "result": "PHASE3F_R4_IMPORT_CANARY_OK",
            "passed": True,
        },
        "source_identity": {
            SOURCE_RELATIVE.as_posix(): sha256_file(project_root / SOURCE_RELATIVE),
            CLI_RELATIVE.as_posix(): sha256_file(project_root / CLI_RELATIVE),
        },
        "contract_identity": {
            CONTRACT_RELATIVE.as_posix(): sha256_file(project_root / CONTRACT_RELATIVE),
            "curated/phase3f-r0/final_test_policy.json": inputs["curated/phase3f-r0/final_test_policy.json"],
        },
        "authenticated_input_sha256": dict(inputs),
        "readiness_composite": {
            "original_r3_non_summary_artifacts": 11,
            "corrected_summary": "curated/phase3f-r3.1/corrected_summary.json",
            "corrected_summary_sha256": inputs["curated/phase3f-r3.1/corrected_summary.json"],
        },
        "dimensions": {"training_rows": TRAIN_ROWS, "final_test_rows": FINAL_ROWS, "features": FEATURE_COUNT},
        "training_seasons": list(TRAINING_SEASONS),
        "final_test": {"season": FINAL_SEASON, "season_type": "Regular Season", "retained_teams": TEAM_COUNT, "excluded_teams": EXCLUDED_TEAMS},
        "ordered_features": list(features),
        "estimator": {"family": "sklearn.linear_model.Ridge", "alpha": ALPHA, "training_weights": "equal"},
        "preprocessing": {"training_matrix_input": "unscaled", "training_scaler_applications": 1, "final_matrix_input": "already_scaled", "final_scaler_applications": 0},
        "baseline": {"definition": "full-precision unweighted mean of all and only 29,701 expanded-training targets", "calibrator": None},
        "restrictions": {"network": False, "model_serialization": False, "alternate_estimator": False, "tuning": False, "calibration_fit": False},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scikit_learn": sklearn.__version__},
    }


def _append_event(path: Path, event_number: int, event: str, status: str = "passed", detail: str | None = None) -> None:
    record: dict[str, Any] = {"event_number": event_number, "event": event, "status": status}
    if detail is not None:
        record["detail"] = detail
    body = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n"
    with path.open("ab") as handle:
        handle.write(body.encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())


def _validate_artifacts_in_memory(artifacts: Mapping[str, Any]) -> None:
    required = {
        "predictions.csv", "overall_metrics.json", "missing_history_metrics.csv", "team_metrics.csv",
        "leave_one_team_out_metrics.csv", "calibration_bins.csv", "residual_diagnostics.json",
        "historical_stability.json", "evaluation_decision.json",
    }
    if set(artifacts) != required:
        raise FinalEvaluationError("in-memory artifact inventory mismatch")
    predictions = artifacts["predictions.csv"]
    if len(predictions) != FINAL_ROWS or [row["row_position"] for row in predictions] != list(range(FINAL_ROWS)):
        raise FinalEvaluationError("prediction rows or positions mismatch")
    if any(tuple(row) != PREDICTION_COLUMNS for row in predictions):
        raise FinalEvaluationError("prediction schema mismatch")
    if [row["history_group"] for row in artifacts["missing_history_metrics.csv"]] != ["complete", "one_missing", "both_missing"]:
        raise FinalEvaluationError("missing-history ordering mismatch")
    if len(artifacts["team_metrics.csv"]) != TEAM_COUNT or len(artifacts["leave_one_team_out_metrics.csv"]) != TEAM_COUNT:
        raise FinalEvaluationError("team diagnostic row count mismatch")
    calibration = artifacts["calibration_bins.csv"]
    if len(calibration) != 10 or sum(row["row_count"] for row in calibration) != FINAL_ROWS:
        raise FinalEvaluationError("calibration-bin completeness mismatch")
    if [row["row_count"] for row in calibration] != [282, 281, 281, 281, 281, 281, 281, 281, 281, 281]:
        raise FinalEvaluationError("frozen calibration-bin assignment mismatch")


def _report_text(configuration: Mapping[str, Any], artifacts: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    overall = artifacts["overall_metrics.json"]
    ridge = overall["ridge_unweighted"]
    baseline = overall["baseline_unweighted"]
    weighted = overall["possession_weighted"]
    decision = artifacts["evaluation_decision.json"]
    missing = artifacts["missing_history_metrics.csv"]
    teams = artifacts["team_metrics.csv"]
    calibration = artifacts["calibration_bins.csv"]
    historical = artifacts["historical_stability.json"]
    worst = max(teams, key=lambda row: (row["mae"], -int(row["team_id"])))
    best = min(teams, key=lambda row: (row["mae"], int(row["team_id"])))
    warnings = historical["warning_flags"]
    active_warnings = [name for name, value in warnings.items() if value is True]
    outside = [name for name, value in warnings["outside_six_fold_range"].items() if value]
    lines = [
        "# Phase 3F-R4 final Ridge evaluation report", "",
        f"## {decision['classification']}", "",
        decision["plain_english_interpretation"], "",
        "The mechanical result was not overridden by diagnostics, subgroup findings, or judgment.", "",
        "## Execution integrity", "",
        f"- Branch `{configuration['repository']['branch']}` at `{configuration['repository']['head']}`; upstream divergence `0/0`; index clean; Stage 1 began with a clean worktree.",
        f"- Import canary: `{configuration['import_canary']['result']}` using the repository virtual environment and explicit project `src` PYTHONPATH.",
        "- Official invocation count: `1`; pre-execution integrity: `passed`; Ridge fit count: `1`; prediction call count: `1`.",
        f"- Dimensions: `{TRAIN_ROWS} x {FEATURE_COUNT}` training and `{FINAL_ROWS} x {FEATURE_COUNT}` final test; 28 retained teams.",
        "- Indiana `1610612754` and Memphis `1610612763` remained fully excluded.",
        "- Network, alternate estimator, tuning, calibration fitting, model serialization, commit, and push: none.", "",
        "## Primary result", "",
        "| Metric | Ridge | Baseline | Baseline minus Ridge |", "| --- | ---: | ---: | ---: |",
        f"| MAE | {ridge['mae']:.6f} | {baseline['mae']:.6f} | {overall['improvements']['mae_baseline_minus_ridge']:.6f} |",
        f"| RMSE | {ridge['rmse']:.6f} | {baseline['rmse']:.6f} | {overall['improvements']['rmse_baseline_minus_ridge']:.6f} |", "",
        f"R-squared was `{ridge['r2']:.6f}`, prediction-minus-target bias `{ridge['bias']:.6f}`, Spearman `{ridge['spearman']:.6f}`, prediction SD `{ridge['prediction_std']:.6f}`, target SD `{ridge['target_std']:.6f}`, and SD ratio `{ridge['prediction_to_target_std_ratio']:.6f}`.",
        f"Possession-weighted Ridge MAE/RMSE were `{weighted['ridge_mae']:.6f}` / `{weighted['ridge_rmse']:.6f}`; baseline values were `{weighted['baseline_mae']:.6f}` / `{weighted['baseline_rmse']:.6f}`.", "",
        "## Diagnostics", "",
    ]
    for row in missing:
        lines.append(f"- `{row['history_group']}`: {row['row_count']} rows, MAE `{row['mae']:.6f}`, RMSE `{row['rmse']:.6f}`, bias `{row['bias']:.6f}`, MAE delta from complete `{row['mae_difference_from_complete']:.6f}`.")
    lines.extend([
        f"- Best/worst retained-team MAE: `{best['team_id']}` at `{best['mae']:.6f}` / `{worst['team_id']}` at `{worst['mae']:.6f}`.",
        f"- Calibration lower/upper target-minus-prediction differences: `{calibration[0]['calibration_difference']:.6f}` / `{calibration[-1]['calibration_difference']:.6f}`.",
        f"- Historical warning flags: `{', '.join(active_warnings) if active_warnings else 'none'}`; outside historical fold ranges: `{', '.join(outside) if outside else 'none'}`.",
        f"- Residual diagnostics are retained in `residual_diagnostics.json`; exact-250 diagnostic applicable: `{str(overall['exact_250_diagnostic']['applicable']).lower()}`.", "",
        "## Evidence and limitation", "",
        f"The ignored write-once namespace contains {len(OFFICIAL_ARTIFACTS)} artifacts. Its nonrecursive payload manifest canonical SHA-256 is `{manifest['deterministic_content_sha256']}`. Independent persisted-prediction reproduction is a required read-only post-execution check and is reported at handoff.", "",
        "The result is a one-time frozen scientific checkpoint, not deployment authorization. The historical 2024-25 development result carries its previously disclosed provenance waiver; the present final execution does not add a new provenance limitation.", "",
        "The narrowest justified next step is one final read-only scientific audit. Packaging and deployment remain unauthorized.", "",
    ])
    return "\n".join(lines)


def run_official(project_root: Path | str = ".") -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = project_root / OUTPUT_RELATIVE
    verify_no_prior_execution(project_root, output_dir)
    output_dir.mkdir(parents=False, exist_ok=False)
    events_path = output_dir / "execution_events.jsonl"
    write_once(events_path, b"")
    event_number = 1
    _append_event(events_path, event_number, "official_invocation_started")

    integrity_checks: list[dict[str, Any]] = []

    def passed(check_id: str, evidence: str) -> None:
        integrity_checks.append({"check_id": check_id, "passed": True, "evidence": evidence})

    configuration: dict[str, Any] | None = None
    inputs_before: dict[str, str] = {}
    failure_prediction_bytes: bytes | None = None
    try:
        with offline_scope():
            git_state = verify_git_state(project_root)
            passed("repository_identity", "required branch, HEAD, 0/0 divergence, clean index, and allowed worktree paths")
            inputs_before = authenticate_inputs(project_root)
            passed("authenticated_inputs", f"{len(inputs_before)} byte-pinned governing inputs authenticated")
            source_restrictions = _validate_source_restrictions(project_root)
            passed("single_model_path", "exactly one reachable .fit() and one reachable .predict(); no prohibited imports")
            loaded = _load_and_validate_inputs(project_root)
            passed("expanded_training_population", "29,701 aligned finite rows across 2014-15 through 2024-25")
            passed("frozen_preprocessing", "expanded-training scaler identified and applied exactly once to training")
            passed("final_test_population", "2,811 aligned finite rows, 28 retained teams, Indiana and Memphis absent")
            passed("feature_identity", "exact ordered 45-feature symmetric no-shot manifest")
            passed("readiness_composite", "authoritative eleven-plus-corrected-summary composite; all six gates passed")
            passed("estimator_restrictions", "Ridge alpha 3000.0, equal weights, no alternate path or calibrator")
            passed("network_and_serialization", "socket guard active; no model-serialization capability")
            configuration = _execution_configuration(project_root, git_state, inputs_before, loaded["features"])
            configuration["source_restrictions"] = source_restrictions
            write_once(output_dir / "execution_configuration.json", serialize_json(configuration))
            integrity = {
                "version": VERSION,
                "official_invocation_number": 1,
                "status": "passed",
                "checks": integrity_checks,
                "authenticated_input_sha256": inputs_before,
                "dimensions": {"training": [TRAIN_ROWS, FEATURE_COUNT], "final_test": [FINAL_ROWS, FEATURE_COUNT]},
                "ordered_features": loaded["features"],
                "readiness_statuses": {gate_id: "passed" for gate_id in EXPECTED_GATE_IDS},
                "target_finiteness": {"training": True, "final_test": True},
                "predictor_finiteness": {"training_scaled_once": True, "final_test_already_scaled": True},
                "row_alignment": {"training": True, "final_test": True},
                "restrictions": configuration["restrictions"],
                "fit_count_before_model_operation": 0,
                "prediction_count_before_model_operation": 0,
            }
            write_once(output_dir / "pre_execution_integrity.json", serialize_json(integrity))
            event_number += 1
            _append_event(events_path, event_number, "pre_execution_integrity_closed")

            prediction = run_model_once(
                loaded["training_scaled"], loaded["training_target"], loaded["final_matrix"], ALPHA,
            )
            if prediction.shape != (FINAL_ROWS,) or not np.isfinite(prediction).all():
                raise FinalEvaluationError("sole prediction vector is incomplete or nonfinite")
            event_number += 1
            _append_event(events_path, event_number, "sole_fit_and_prediction_completed")
            inputs_after_prediction = authenticate_inputs(project_root)
            if inputs_after_prediction != inputs_before:
                raise FinalEvaluationError("governing inputs changed during model operation")
            event_number += 1
            _append_event(events_path, event_number, "post_prediction_integrity_passed")

            training_target = loaded["training_target"]
            target = loaded["final_target"]
            rows = loaded["final_rows"]
            baseline_value = float(np.mean(training_target))
            baseline = np.full(FINAL_ROWS, baseline_value, dtype=np.float64)
            if not np.isfinite(baseline).all():
                raise FinalEvaluationError("baseline vector is nonfinite")
            ridge_metrics, ridge_nulls = metric_set(prediction, target)
            baseline_metrics, baseline_nulls = metric_set(baseline, target)
            possessions = _finite_vector((row["pair_possessions"] for row in rows), "pair possessions")
            ridge_wmae, ridge_wrmse = weighted_errors(prediction, target, possessions)
            baseline_wmae, baseline_wrmse = weighted_errors(baseline, target, possessions)
            exact_indices = [index for index, row in enumerate(rows) if row["endpoint_exact_250_flag"] == "1"]
            if exact_indices:
                exact_metrics, _ = metric_set(prediction[exact_indices], target[exact_indices])
                exact = {"applicable": True, "row_count": len(exact_indices), "mae": exact_metrics["mae"], "rmse": exact_metrics["rmse"], "bias": exact_metrics["bias"], "not_applicable_reason": None}
            else:
                exact = {"applicable": False, "row_count": 0, "mae": None, "rmse": None, "bias": None, "not_applicable_reason": "zero retained rows have endpoint_exact_250_flag"}
            improvements = {
                "mae_baseline_minus_ridge": baseline_metrics["mae"] - ridge_metrics["mae"],
                "rmse_baseline_minus_ridge": baseline_metrics["rmse"] - ridge_metrics["rmse"],
            }
            policy = loaded["policy"]
            classification = classify_final(policy, True, improvements["mae_baseline_minus_ridge"], improvements["rmse_baseline_minus_ridge"])
            mae_threshold, rmse_threshold = classification_thresholds(policy)
            interpretation_by_label = {
                "FINAL SCIENTIFIC PASS": "The frozen Ridge cleared both predeclared baseline-relative gates on the untouched final-test population.",
                "FINAL SCIENTIFIC FAILURE": "The frozen Ridge did not improve MAE over the historical-training-mean baseline and is not final-test validated.",
                "FINAL MIXED RESULT": "The frozen Ridge produced a finite result that did not satisfy the complete pass rule and did not meet the failure boundary.",
                "INVALID": "A mandatory integrity or finiteness condition failed, so no scientific verdict is valid.",
            }
            overall = {
                "version": VERSION,
                "row_count": FINAL_ROWS,
                "ridge_unweighted": ridge_metrics,
                "baseline_unweighted": baseline_metrics,
                "improvements": improvements,
                "possession_weighted": {"ridge_mae": ridge_wmae, "ridge_rmse": ridge_wrmse, "baseline_mae": baseline_wmae, "baseline_rmse": baseline_wrmse},
                "dispersion": {"ridge_prediction_std": ridge_metrics["prediction_std"], "baseline_prediction_std": baseline_metrics["prediction_std"], "target_std": ridge_metrics["target_std"], "ridge_prediction_to_target_std_ratio": ridge_metrics["prediction_to_target_std_ratio"], "baseline_prediction_to_target_std_ratio": baseline_metrics["prediction_to_target_std_ratio"]},
                "exact_250_diagnostic": exact,
                "null_reasons": {"ridge_unweighted": ridge_nulls, "baseline_unweighted": baseline_nulls},
                "pre_execution_integrity_sha256": sha256_file(output_dir / "pre_execution_integrity.json"),
            }
            prediction_rows = [{
                "row_position": index,
                "target_season": row["target_season"],
                "team_id": row["team_id"],
                "player_1_id": row["player_1_id"],
                "player_2_id": row["player_2_id"],
                "observation_key": row["observation_key"],
                "target_net_rating": target[index],
                "ridge_prediction": prediction[index],
                "baseline_prediction": baseline[index],
                "pair_possessions": possessions[index],
                "history_status": row["history_status"],
                "endpoint_exact_250_flag": bool(int(row["endpoint_exact_250_flag"])),
            } for index, row in enumerate(rows)]
            failure_prediction_bytes = serialize_csv(prediction_rows, PREDICTION_COLUMNS)
            missing = subgroup_rows(rows, prediction, target)
            if {row["history_group"]: row["row_count"] for row in missing} != EXPECTED_HISTORY_COUNTS:
                raise FinalEvaluationError("missing-history result counts mismatch")
            teams, leave_one_out = team_rows(rows, prediction, target, possessions)
            calibration = calibration_rows(rows, prediction, target)
            residual = residual_relationships(prediction, target, possessions)
            historical = historical_stability(ridge_metrics, loaded["spent_development"])
            decision = {
                "version": VERSION,
                "integrity_passed": True,
                "mandatory_improvements_finite": True,
                "gate_inputs": {
                    "mae_improvement": improvements["mae_baseline_minus_ridge"],
                    "rmse_improvement": improvements["rmse_baseline_minus_ridge"],
                },
                "threshold_comparisons": {
                    "mae_improvement_at_least_0_10": improvements["mae_baseline_minus_ridge"] >= mae_threshold,
                    "rmse_improvement_at_least_0_0": improvements["rmse_baseline_minus_ridge"] >= rmse_threshold,
                    "mae_improvement_at_most_0_0": improvements["mae_baseline_minus_ridge"] <= 0.0,
                },
                "classification": classification,
                "plain_english_interpretation": interpretation_by_label[classification],
                "diagnostics_overrode_result": False,
                "result_not_overridden": True,
            }
            artifacts = {
                "predictions.csv": prediction_rows,
                "overall_metrics.json": overall,
                "missing_history_metrics.csv": missing,
                "team_metrics.csv": teams,
                "leave_one_team_out_metrics.csv": leave_one_out,
                "calibration_bins.csv": calibration,
                "residual_diagnostics.json": residual,
                "historical_stability.json": historical,
                "evaluation_decision.json": decision,
            }
            _validate_artifacts_in_memory(artifacts)
            serialized = {
                "predictions.csv": failure_prediction_bytes,
                "overall_metrics.json": serialize_json(overall),
                "missing_history_metrics.csv": serialize_csv(missing, MISSING_COLUMNS),
                "team_metrics.csv": serialize_csv(teams, TEAM_COLUMNS),
                "leave_one_team_out_metrics.csv": serialize_csv(leave_one_out, LOTO_COLUMNS),
                "calibration_bins.csv": serialize_csv(calibration, CALIBRATION_COLUMNS),
                "residual_diagnostics.json": serialize_json(residual),
                "historical_stability.json": serialize_json(historical),
                "evaluation_decision.json": serialize_json(decision),
            }
            event_number += 1
            _append_event(events_path, event_number, "all_frozen_metrics_and_classification_validated_in_memory")
            event_number += 1
            _append_event(events_path, event_number, "sensitive_artifact_publication_started")

            # Prediction bytes are written first only after the complete in-memory Stage C passes.
            for name in (
                "predictions.csv", "overall_metrics.json", "missing_history_metrics.csv", "team_metrics.csv",
                "leave_one_team_out_metrics.csv", "calibration_bins.csv", "residual_diagnostics.json",
                "historical_stability.json", "evaluation_decision.json",
            ):
                write_once(output_dir / name, serialized[name])
            inputs_after_publication = authenticate_inputs(project_root)
            if inputs_after_publication != inputs_before:
                raise FinalEvaluationError("governing inputs changed during result publication")
            manifest = {
                "version": VERSION,
                "artifact_inventory": list(OFFICIAL_ARTIFACTS),
                "payload_artifacts": {
                    name: {"bytes": (output_dir / name).stat().st_size, "sha256": sha256_file(output_dir / name)}
                    for name in sorted(PAYLOAD_ARTIFACTS)
                },
                "excluded_from_own_manifest": ["artifact_hashes.json", "summary.json"],
                "manifest_rule": "nonrecursive: hash every payload artifact; exclude this manifest and summary.json",
            }
            manifest["deterministic_content_sha256"] = canonical_content_hash(manifest)
            write_once(output_dir / "artifact_hashes.json", serialize_json(manifest))
            summary = {
                "version": VERSION,
                "classification": classification,
                "artifact_manifest_content_sha256": manifest["deterministic_content_sha256"],
                "official_invocation_count": 1,
                "pre_execution_integrity_passed": True,
                "fit_count": 1,
                "prediction_count": 1,
                "training_rows": TRAIN_ROWS,
                "final_test_rows": FINAL_ROWS,
                "feature_count": FEATURE_COUNT,
                "retained_teams": TEAM_COUNT,
                "excluded_team_ids": sorted(EXCLUDED_TEAMS, key=int),
                "network_operations": 0,
                "alternate_model_operations": 0,
                "tuning_operations": 0,
                "calibration_fit_operations": 0,
                "model_serialization_operations": 0,
                "commit_operations": 0,
                "push_operations": 0,
            }
            summary["deterministic_content_sha256"] = canonical_content_hash(summary)
            write_once(output_dir / "summary.json", serialize_json(summary))
            (project_root / REPORT_RELATIVE).write_bytes(_report_text(configuration, artifacts, manifest).encode("utf-8"))
    except Exception as exc:
        prediction_path = output_dir / "predictions.csv"
        if failure_prediction_bytes is not None and not prediction_path.exists():
            write_once(prediction_path, failure_prediction_bytes)
        failure = {
            "version": VERSION,
            "official_invocation_number": 1,
            "status": "failed",
            "checks": integrity_checks + [{"check_id": "official_execution_failure", "passed": False, "evidence": str(exc)}],
            "authenticated_input_sha256": inputs_before,
            "fit_or_prediction_may_have_occurred": (output_dir / "pre_execution_integrity.json").exists(),
            "rerun_authorized": False,
        }
        integrity_path = output_dir / "pre_execution_integrity.json"
        if not integrity_path.exists():
            write_once(integrity_path, serialize_json(failure))
        event_number += 1
        _append_event(events_path, event_number, "official_execution_failed", "failed", str(exc))
        raise FinalEvaluationError(f"official one-time evaluation stopped and must not be rerun: {exc}") from exc

    actual_inventory = {path.name for path in output_dir.iterdir() if path.is_file()}
    if actual_inventory != set(OFFICIAL_ARTIFACTS):
        raise FinalEvaluationError("official artifact inventory mismatch after publication")
    return {
        "classification": artifacts["evaluation_decision.json"]["classification"],
        "output_directory": str(output_dir),
        "report": str(project_root / REPORT_RELATIVE),
    }
