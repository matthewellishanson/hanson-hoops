"""Frozen one-time Phase 3E-R4 development-holdout evaluation.

The official entry point is restart-safe and fail-closed.  Metric helpers are
pure so they can be exercised with synthetic fixtures before the one official
Ridge fit and prediction vector are generated.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import socket
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from unittest.mock import patch

import numpy as np
import sklearn
from sklearn.linear_model import Ridge

from pair_fit_v2 import phase3b_curation as phase3b
from pair_fit_v2 import phase3d_model_refinement as phase3d
from pair_fit_v2 import phase3e_r3_evaluation_policy as phase3r3


VERSION = "phase3e-r4.development-holdout-evaluation.v1"
EXPECTED_BRANCH = "research/pair-fit-v2"
EXPECTED_HEAD = "91635b517d3f63a318cae2ea6f65f324b9463b44"
POLICY_CONTENT_SHA256 = "6e0eff4b38c520ed5bd0c26100b2ddb4b911d6d3c9bb92fd7f016416b6211ad4"
POLICY_BYTES_SHA256 = "f5d1e8852693b74d4e82ae505e9d355526a3ddaedc7fbb7ffc7282db3f48ee48"
POLICY_PATH = Path("modeling/phase3e-r3/evaluation_policy.json")
TRAINING_PATH = Path("curated/phase3b/phase3b_poss_ge_150.csv")
R2_DIR = Path("curated/phase3e-r2")
OUTPUT_DIR = Path("modeling/phase3e-r4")
REPORT_PATH = Path("PHASE3E_R4_DEVELOPMENT_HOLDOUT_EVALUATION_REPORT.md")
PROTECTED_SEASON = "2025-26"
EXCLUDED_TEAMS = {"1610612755", "1610612766"}
EXPECTED_HISTORY_COUNTS = {"complete": 2139, "one_missing": 523, "both_missing": 38}
OFFICIAL_ARTIFACTS = tuple(phase3r3.R4_RUNTIME_ARTIFACTS)
PAYLOAD_ARTIFACTS = OFFICIAL_ARTIFACTS[:11]
ALLOWED_PRE_RUN_CHANGES = {
    "src/pair_fit_v2/phase3e_r4_evaluation.py",
    "src/pair_fit_v2/phase3e_r4_cli.py",
    "tests/test_phase3e_r4_evaluation.py",
}


class ContractFailure(RuntimeError):
    """A frozen R4 implementation or evidence contract failed."""


def sha256_file(path: Path) -> str:
    reject_protected_identity(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_content_hash(document: Mapping[str, Any]) -> str:
    value = dict(document)
    value.pop("deterministic_content_sha256", None)
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def serialize_json(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(document, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if not math.isfinite(value):
            raise ContractFailure("nonfinite CSV output prohibited")
        return repr(value)
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return str(value)


def serialize_csv(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> bytes:
    import io

    handle = io.StringIO(newline="")
    writer = csv.DictWriter(
        handle, fieldnames=list(columns), lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    for row in rows:
        if set(row) != set(columns):
            raise ContractFailure("CSV row schema mismatch")
        writer.writerow({column: _csv_value(row[column]) for column in columns})
    return handle.getvalue().encode("utf-8")


def reject_protected_identity(value: Any) -> None:
    if PROTECTED_SEASON in str(value).replace("\\", "/").lower():
        raise ContractFailure(f"protected-season identity rejected before access: {value}")


@contextmanager
def offline_scope():
    """Block socket-level access for the entire official evidence window."""

    def reject(*_args, **_kwargs):
        raise ContractFailure("Phase 3E-R4 network access prohibited")

    with (
        patch.object(socket.socket, "connect", reject),
        patch.object(socket.socket, "connect_ex", reject),
        patch.object(socket, "create_connection", reject),
        patch.object(socket, "getaddrinfo", reject),
    ):
        yield


def _read_json(path: Path) -> dict[str, Any]:
    reject_protected_identity(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    reject_protected_identity(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ContractFailure(f"missing CSV header: {path}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ContractFailure(f"duplicate CSV columns: {path}")
        return list(reader.fieldnames), list(reader)


def _git(project_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=project_root, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


def verify_official_start(project_root: Path) -> None:
    if _git(project_root, "branch", "--show-current") != EXPECTED_BRANCH:
        raise ContractFailure("required branch mismatch")
    if _git(project_root, "rev-parse", "HEAD") != EXPECTED_HEAD:
        raise ContractFailure("required HEAD mismatch")
    upstream = _git(project_root, "rev-parse", "@{upstream}")
    if upstream != EXPECTED_HEAD:
        raise ContractFailure("required upstream commit mismatch")
    changed = set()
    repository_root = Path(_git(project_root, "rev-parse", "--show-toplevel")).resolve()
    project_prefix = project_root.relative_to(repository_root).as_posix().rstrip("/") + "/"
    for line in _git(project_root, "status", "--porcelain=v1", "--untracked-files=all").splitlines():
        if not line:
            continue
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if path.startswith(project_prefix):
            path = path[len(project_prefix):]
        changed.add(path)
    unexpected = changed - ALLOWED_PRE_RUN_CHANGES
    if unexpected:
        raise ContractFailure(f"unexpected pre-run working-tree changes: {sorted(unexpected)}")
    if (project_root / OUTPUT_DIR).exists():
        raise ContractFailure("prior Phase 3E-R4 output directory exists; refusing overwrite")
    if (project_root / REPORT_PATH).exists():
        raise ContractFailure("prior Phase 3E-R4 report exists; refusing overwrite")


def _all_pinned_inputs(policy: Mapping[str, Any]) -> list[dict[str, str]]:
    inputs = policy["input_artifacts"]
    records: dict[str, str] = {}
    for entry in inputs["reviewed_source_evidence"].values():
        records[entry["relative_path"]] = entry["serialized_byte_sha256"]
    training = inputs["phase3b_training_population"]
    records[training["relative_path"]] = training["serialized_byte_sha256"]
    for group in ("phase3d", "phase3e_r2"):
        for entry in inputs[group].values():
            records[entry["relative_path"]] = entry["serialized_byte_sha256"]
    return [
        {"relative_path": relative, "serialized_byte_sha256": records[relative]}
        for relative in sorted(records)
    ]


def verify_pinned_inputs(project_root: Path, policy: Mapping[str, Any]) -> dict[str, str]:
    actual: dict[str, str] = {}
    for entry in _all_pinned_inputs(policy):
        relative = entry["relative_path"]
        digest = sha256_file(project_root / relative)
        if digest != entry["serialized_byte_sha256"]:
            raise ContractFailure(f"pinned input hash mismatch: {relative}")
        actual[relative] = digest
    return actual


def cache_fingerprints(project_root: Path) -> dict[str, str]:
    document = _read_json(project_root / R2_DIR / "input_fingerprints.json")
    expected = document["referenced_cache_files"]
    if document["referenced_cache_file_count"] != len(expected) or len(expected) != 129:
        raise ContractFailure("R2 cache fingerprint inventory is not exactly 129 files")
    actual = {
        relative: sha256_file(project_root / "cache" / relative)
        for relative in sorted(expected)
    }
    if actual != dict(sorted(expected.items())):
        raise ContractFailure("R2 cache fingerprint mismatch")
    return actual


def load_and_validate_policy(project_root: Path) -> dict[str, Any]:
    path = project_root / POLICY_PATH
    if sha256_file(path) != POLICY_BYTES_SHA256:
        raise ContractFailure("serialized R3 policy hash mismatch")
    policy = _read_json(path)
    if canonical_content_hash(policy) != POLICY_CONTENT_SHA256:
        raise ContractFailure("canonical-content R3 policy hash mismatch")
    if policy.get("deterministic_content_sha256") != POLICY_CONTENT_SHA256:
        raise ContractFailure("recorded R3 policy content hash mismatch")
    if policy["estimator"]["features"] != phase3r3.FEATURES:
        raise ContractFailure("R3 feature order mismatch")
    if policy["runtime_output_contract"]["runtime_artifact_order"] != list(OFFICIAL_ARTIFACTS):
        raise ContractFailure("R3 runtime inventory mismatch")
    return policy


def execution_configuration(policy: Mapping[str, Any]) -> dict[str, Any]:
    preprocessing = policy["input_artifacts"]["phase3e_r2"]["preprocessing_state.json"]
    return {
        "version": VERSION,
        "policy_identity": {
            "relative_path": str(POLICY_PATH).replace("\\", "/"),
            "deterministic_content_sha256": POLICY_CONTENT_SHA256,
            "serialized_byte_sha256": POLICY_BYTES_SHA256,
        },
        "input_artifacts": _all_pinned_inputs(policy),
        "estimator": {
            "family": "sklearn.linear_model.Ridge",
            "constructor_parameters": {"alpha": 3000.0},
        },
        "training_seasons": list(phase3r3.TRAINING_SEASONS),
        "training_rows": 27001,
        "training_weight_policy": "equal",
        "preprocessing_state_identity": {
            "relative_path": preprocessing["relative_path"],
            "serialized_byte_sha256": preprocessing["serialized_byte_sha256"],
            "deterministic_content_sha256": "a14e8b8afe12be0bdaea9b1dee05c446a7c9bc7d00d41a2d62180891e5a7cfee",
        },
        "feature_order": list(phase3r3.FEATURES),
        "baseline": {
            "definition": "equal-row mean target over all 27,001 frozen historical training rows",
            "target_column": "target_net_rating",
            "training_population_relative_path": str(TRAINING_PATH).replace("\\", "/"),
            "training_population_serialized_byte_sha256": phase3r3.PHASE3B_TRAINING_HASH,
            "training_rows": 27001,
            "training_seasons": list(phase3r3.TRAINING_SEASONS),
            "weight_policy": "equal",
        },
        "environment_versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "prohibited_operation_confirmations": {
            "network_accessed": False,
            "final_test_season_accessed": False,
            "alternate_estimator_or_prediction_generated": False,
            "calibrator_or_prediction_transform_applied": False,
        },
    }


def validate_schema(document: Mapping[str, Any], required_keys: Sequence[str], name: str) -> None:
    if set(document) != set(required_keys):
        raise ContractFailure(f"{name} top-level schema mismatch")


def _finite_vector(values: Iterable[Any], name: str) -> np.ndarray:
    try:
        vector = np.asarray(list(values), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ContractFailure(f"{name} is not numeric") from exc
    if vector.ndim != 1 or not np.isfinite(vector).all():
        raise ContractFailure(f"{name} contains missing or nonfinite values")
    return vector


def numeric_observation_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    season = str(row["target_season"])
    reject_protected_identity(season)
    ids = [str(row[name]) for name in ("team_id", "player_1_id", "player_2_id")]
    if any(not value.isdecimal() or int(value) <= 0 or str(int(value)) != value for value in ids):
        raise ContractFailure("noncanonical numeric observation-key ID")
    if int(ids[1]) >= int(ids[2]):
        raise ContractFailure("player IDs are not in numeric canonical order")
    return season, *ids


def reconstruct_training_matrix(
    training_rows: Sequence[Mapping[str, Any]], preprocessing: Mapping[str, Any]
) -> np.ndarray:
    names = list(preprocessing["feature_order"])
    if names != list(phase3r3.FEATURES) or len(names) != 45 or len(set(names)) != 45:
        raise ContractFailure("frozen preprocessing feature order mismatch")
    manifest = phase3b.feature_manifest()
    medians = preprocessing["player_slot_medians"]
    symmetric = preprocessing["symmetric_feature_medians"]
    means = preprocessing["scaler_mean"]
    scales = preprocessing["scaler_scale"]
    raw = []
    for row in training_rows:
        transformed = phase3d.transform_row(row, medians, "no_shot", manifest=manifest)
        raw.append([
            symmetric[name]
            if transformed[name] is None or not math.isfinite(float(transformed[name]))
            else float(transformed[name])
            for name in names
        ])
    matrix = np.asarray(raw, dtype=np.float64)
    mean_vector = np.asarray([means[name] for name in names], dtype=np.float64)
    scale_vector = np.asarray([scales[name] for name in names], dtype=np.float64)
    if matrix.shape != (27001, 45) or not np.isfinite(matrix).all():
        raise ContractFailure("training estimator matrix shape or finiteness mismatch")
    if not np.isfinite(mean_vector).all() or not np.isfinite(scale_vector).all() or np.any(scale_vector <= 0):
        raise ContractFailure("frozen scaler state is invalid")
    return (matrix - mean_vector) / scale_vector


def _average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    index = 0
    while index < len(values):
        end = index + 1
        while end < len(values) and values[order[end]] == values[order[index]]:
            end += 1
        ranks[order[index:end]] = (index + end - 1) / 2.0 + 1.0
        index = end
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
    if not math.isfinite(value):
        return None, "correlation is nonfinite"
    return value, None


def metric_set(prediction: Iterable[Any], target: Iterable[Any]) -> tuple[dict[str, Any], dict[str, str]]:
    pred = _finite_vector(prediction, "prediction")
    truth = _finite_vector(target, "target")
    if len(pred) != len(truth) or not len(pred):
        raise ContractFailure("metric vectors are empty or misaligned")
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
    result = {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(math.sqrt(float(np.mean(error * error)))),
        "r2": r2,
        "bias": float(np.mean(error)),
        "spearman": spearman,
        "prediction_std": prediction_std,
        "target_std": target_std,
        "prediction_to_target_std_ratio": ratio,
    }
    return result, nulls


def weighted_errors(prediction: np.ndarray, target: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    if np.any(weights <= 0) or not np.isfinite(weights).all() or float(np.sum(weights)) <= 0:
        raise ContractFailure("possession weights must be finite and positive")
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
        raise ContractFailure("residual vectors are misaligned")
    residual = truth - pred
    residual_var = float(np.var(residual, ddof=0))
    pred_var = float(np.var(pred, ddof=0))
    poss_var = float(np.var(poss, ddof=0))
    nulls: dict[str, str] = {}

    def relationship(independent: np.ndarray, variance: float, label: str):
        correlation, reason = _pearson(residual, independent)
        if reason:
            nulls[f"residual_vs_{label}_pearson"] = reason
        if variance == 0.0:
            slope = None
            nulls[f"residual_vs_{label}_slope"] = f"{label} variance is zero"
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
        "residual_variance": residual_var,
        "prediction_variance": pred_var,
        "possessions_variance": poss_var,
        "residual_vs_prediction_pearson": pred_corr,
        "residual_vs_prediction_slope": pred_slope,
        "residual_vs_possessions_pearson": poss_corr,
        "residual_vs_possessions_slope": poss_slope,
        "null_reasons": nulls,
    }


def classify(stage_a: bool, stage_b: bool, mae_improvement: float, rmse_improvement: float) -> str:
    return phase3r3.classify_evaluation(stage_a, stage_b, mae_improvement, rmse_improvement)


def _subgroup_rows(records: Sequence[Mapping[str, Any]], prediction: np.ndarray, target: np.ndarray) -> list[dict[str, Any]]:
    output = []
    complete_mae = metric_set(
        [prediction[i] for i, row in enumerate(records) if row["history_status"] == "complete"],
        [target[i] for i, row in enumerate(records) if row["history_status"] == "complete"],
    )[0]["mae"]
    for group in ("complete", "one_missing", "both_missing"):
        indices = [i for i, row in enumerate(records) if row["history_status"] == group]
        metrics, _ = metric_set(prediction[indices], target[indices])
        difference = metrics["mae"] - complete_mae
        adequate = len(indices) >= 100 and group in {"complete", "one_missing"}
        output.append({
            "history_group": group,
            "row_count": len(indices),
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "bias": metrics["bias"],
            "mae_difference_from_complete": difference,
            "adequate_for_formal_comparison": adequate,
            "material_absolute_difference": abs(difference) >= 0.50,
            "adverse_lower_confidence_difference": group != "complete" and difference >= 0.50,
        })
    return output


def _team_rows(records: Sequence[Mapping[str, Any]], prediction: np.ndarray, target: np.ndarray, possessions: np.ndarray):
    teams = sorted({row["team_id"] for row in records}, key=int)
    output, loto = [], []
    full_mae = float(np.mean(np.abs(prediction - target)))
    for team in teams:
        selected = np.asarray([row["team_id"] == team for row in records], dtype=bool)
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
        loto.append({
            "removed_team_id": team,
            "remaining_rows": int(np.sum(remaining)),
            "leave_one_team_out_mae": leave_mae,
            "full_sample_mae": full_mae,
            "full_sample_minus_leave_one_team_out_mae": full_mae - leave_mae,
        })
    return output, loto


def _calibration_rows(records: Sequence[Mapping[str, Any]], prediction: np.ndarray, target: np.ndarray):
    order = sorted(
        range(len(records)),
        key=lambda i: (
            prediction[i], int(records[i]["team_id"]), int(records[i]["player_1_id"]), int(records[i]["player_2_id"])
        ),
    )
    output = []
    for bin_number in range(1, 11):
        indices = order[(bin_number - 1) * 270:bin_number * 270]
        mean_prediction = float(np.mean(prediction[indices]))
        mean_target = float(np.mean(target[indices]))
        output.append({
            "bin": bin_number,
            "tail": "lower" if bin_number == 1 else "upper" if bin_number == 10 else "middle",
            "row_count": len(indices),
            "mean_prediction": mean_prediction,
            "mean_target": mean_target,
            "calibration_difference": mean_target - mean_prediction,
        })
    return output


def _historical_stability(ridge_metrics: Mapping[str, Any]) -> dict[str, Any]:
    references = phase3r3.HISTORICAL_METRICS
    pooled = dict(references["pooled"])
    folds = {season: dict(references[season]) for season in phase3r3.HISTORICAL_VALIDATION_SEASONS}
    compared = ("r2", "bias", "spearman", "prediction_std", "target_std", "prediction_to_target_std_ratio")
    deltas = {
        metric: ridge_metrics[metric] - pooled[metric]
        for metric in ("mae", "rmse", *compared)
        if ridge_metrics[metric] is not None
    }
    ranges, outside = {}, {}
    for metric in compared:
        values = [folds[season][metric] for season in phase3r3.HISTORICAL_VALIDATION_SEASONS]
        value = ridge_metrics[metric]
        status = "not_comparable" if value is None else "below" if value < min(values) else "above" if value > max(values) else "within"
        ranges[metric] = {"fold_min": min(values), "fold_max": max(values), "holdout_value": value, "position": status}
        outside[metric] = status in {"below", "above"}
    warnings = {
        "mae_above_worst_by_more_than_0_50": ridge_metrics["mae"] > 8.096126328447196,
        "rmse_above_historical_worst": ridge_metrics["rmse"] > 10.330015941206614,
        "outside_six_fold_range": outside,
        "absolute_bias_above_historical_maximum": abs(ridge_metrics["bias"]) > max(abs(folds[s]["bias"]) for s in folds),
    }
    return {
        "version": VERSION,
        "holdout_values": dict(ridge_metrics),
        "historical_pooled_reference": pooled,
        "historical_fold_references": folds,
        "deltas_from_pooled": deltas | {
            "mae_minus_phase3d_macro_mae": ridge_metrics["mae"] - 7.113451159210443,
            "mae_minus_historical_worst_season_mae": ridge_metrics["mae"] - 7.596126328447196,
            "rmse_minus_historical_worst_season_rmse": ridge_metrics["rmse"] - 10.330015941206614,
        },
        "fold_range_comparisons": ranges,
        "warning_flags": warnings,
    }


def _validate_stage_b_in_memory(
    artifacts: Mapping[str, Any], policy: Mapping[str, Any]
) -> list[dict[str, Any]]:
    contract = policy["runtime_output_contract"]["artifacts"]
    required = set(PAYLOAD_ARTIFACTS[2:])
    missing = required - set(artifacts)
    if missing:
        raise ContractFailure(f"Stage B required artifact missing: {sorted(missing)}")
    for name in PAYLOAD_ARTIFACTS[2:]:
        item = artifacts[name]
        spec = contract[name]
        if "top_level_keys" in spec:
            validate_schema(item, spec["top_level_keys"], name)
        else:
            if len(item) != spec["rows"] or any(list(row) != spec["columns"] for row in item):
                raise ContractFailure(f"{name} schema or row-count mismatch")
    if len(artifacts["predictions.csv"]) != 2700:
        raise ContractFailure("predictions row count mismatch")
    if [row["row_position"] for row in artifacts["predictions.csv"]] != list(range(2700)):
        raise ContractFailure("prediction row ordering mismatch")
    if [row["history_group"] for row in artifacts["missing_history_metrics.csv"]] != ["complete", "one_missing", "both_missing"]:
        raise ContractFailure("missing-history ordering mismatch")
    if any(row["row_count"] != 270 for row in artifacts["calibration_bins.csv"]):
        raise ContractFailure("calibration bin size mismatch")
    return [
        {"stage": "B", "gate_id": gate["id"], "passed": True}
        for gate in phase3r3.STAGE_B_POST_COMPUTATION_CHECKS
    ]


def _write_bytes(path: Path, data: bytes) -> None:
    if path.exists():
        raise ContractFailure(f"refusing to overwrite output: {path}")
    path.write_bytes(data)


def _report_text(artifacts: Mapping[str, Any]) -> str:
    overall = artifacts["overall_metrics.json"]
    decision = artifacts["evaluation_decision.json"]
    history = artifacts["historical_stability.json"]
    residual = artifacts["residual_diagnostics.json"]
    missing = artifacts["missing_history_metrics.csv"]
    teams = artifacts["team_metrics.csv"]
    calibration = artifacts["calibration_bins.csv"]
    best = min(teams, key=lambda row: (row["mae"], int(row["team_id"])))
    worst = min(teams, key=lambda row: (-row["mae"], int(row["team_id"])))
    warnings = history["warning_flags"]
    outside = ", ".join(k for k, v in warnings["outside_six_fold_range"].items() if v) or "none"
    interpretation = {
        "VALID DEVELOPMENT-HOLDOUT PASS": "The frozen Ridge cleared both predeclared baseline-relative gates.",
        "VALID DEVELOPMENT-HOLDOUT MIXED RESULT": "The frozen Ridge produced a mixed result and this is not a pass.",
        "VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE": "The execution was valid, but the frozen model failed its scientific baseline-relative MAE gate.",
        "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE": "The execution is invalid and is not evidence for or against the model.",
    }[decision["classification"]]
    f = lambda value: "null" if value is None else f"{value:.6f}"
    lines = [
        "# Phase 3E-R4 Development-Holdout Evaluation Report",
        "",
        f"**{decision['classification']}**",
        "",
        f"Stage A: **{'passed' if decision['stage_a_pass'] else 'failed'}**. Stage B: **{'passed' if decision['stage_b_pass'] else 'failed'}**.",
        "",
        f"Ridge MAE was {f(overall['ridge_unweighted']['mae'])} versus baseline {f(overall['baseline_unweighted']['mae'])}, an improvement of {f(overall['improvements']['mae_baseline_minus_ridge'])}. Ridge RMSE was {f(overall['ridge_unweighted']['rmse'])} versus baseline {f(overall['baseline_unweighted']['rmse'])}, an improvement of {f(overall['improvements']['rmse_baseline_minus_ridge'])}.",
        "",
        interpretation,
        "",
        "## Overall diagnostics",
        "",
        f"R²: {f(overall['ridge_unweighted']['r2'])}; prediction-minus-target bias: {f(overall['ridge_unweighted']['bias'])}; Spearman: {f(overall['ridge_unweighted']['spearman'])}. Prediction SD: {f(overall['dispersion']['ridge_prediction_std'])}; target SD: {f(overall['dispersion']['target_std'])}; prediction/target SD ratio: {f(overall['dispersion']['ridge_prediction_to_target_std_ratio'])}.",
        "",
        f"Possession-weighted Ridge MAE/RMSE: {f(overall['possession_weighted']['ridge_mae'])}/{f(overall['possession_weighted']['ridge_rmse'])}; baseline: {f(overall['possession_weighted']['baseline_mae'])}/{f(overall['possession_weighted']['baseline_rmse'])}.",
        "",
        f"Historical warnings — MAE extreme deterioration: {str(warnings['mae_above_worst_by_more_than_0_50']).lower()}; RMSE above historical worst: {str(warnings['rmse_above_historical_worst']).lower()}; absolute bias above historical maximum: {str(warnings['absolute_bias_above_historical_maximum']).lower()}; fold-range warnings: {outside}. These warnings are non-decisional.",
        "",
        "## Subgroups and concentration",
        "",
    ]
    for row in missing:
        lines.append(f"- {row['history_group']}: n={row['row_count']}, MAE={f(row['mae'])}, RMSE={f(row['rmse'])}, bias={f(row['bias'])}, MAE difference from complete={f(row['mae_difference_from_complete'])}, adequate={str(row['adequate_for_formal_comparison']).lower()}, material={str(row['material_absolute_difference']).lower()}, adverse lower-confidence difference={str(row['adverse_lower_confidence_difference']).lower()}.")
    lines += [
        "",
        f"Best descriptive team MAE: {best['team_id']} at {f(best['mae'])}; worst: {worst['team_id']} at {f(worst['mae'])}. Team and leave-one-team-out diagnostics are descriptive and noncausal; no team was removed and no model was refit.",
        "",
        f"Exact-250 diagnostic: applicable={str(overall['exact_250_diagnostic']['applicable']).lower()}, rows={overall['exact_250_diagnostic']['row_count']}, MAE={f(overall['exact_250_diagnostic']['mae'])}, RMSE={f(overall['exact_250_diagnostic']['rmse'])}, bias={f(overall['exact_250_diagnostic']['bias'])}. It uses retained 2024–25 rows only and cannot address excluded-team endpoint truncation.",
        "",
        f"Calibration lower-tail difference (target minus prediction): {f(calibration[0]['calibration_difference'])}; upper-tail difference: {f(calibration[-1]['calibration_difference'])}. No calibrator or post-hoc adjustment was fitted.",
        "",
        f"Residual (target minus prediction) correlation/slope versus prediction: {f(residual['residual_vs_prediction_pearson'])}/{f(residual['residual_vs_prediction_slope'])}; versus possessions: {f(residual['residual_vs_possessions_pearson'])}/{f(residual['residual_vs_possessions_slope'])}.",
        "",
        "## Scope and limitations",
        "",
        "Charlotte (`1610612766`) and Philadelphia (`1610612755`) were excluded in full because their full-season endpoint responses were adjudicated non-exhaustive. This excludes approximately 9.82% of otherwise eligible rows and 6.33% of otherwise eligible possessions.",
        "",
        "The target is contextual shared-court net rating, not a causal player-pair effect. Historical validation showed modest signal. Missing-history results remain uncertain, especially the 38-row both-missing group. Prediction compression is assessed through the SD ratio and calibration bins. Rows overlap substantially in players and pairs, so observations are not independent player experiments.",
        "",
        "Exact-250 evidence is limited to retained rows and cannot rehabilitate excluded teams. No calibration, post-hoc tuning, alternative alpha, HGB comparison, row removal, team removal, or prediction transformation occurred.",
        "",
        "The 2024–25 season is now spent as development evidence. The protected 2025–26 season remains untouched.",
        "",
    ]
    return "\n".join(lines)


def run_official_evaluation(project_root: Path | str = ".") -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    verify_official_start(project_root)
    policy = load_and_validate_policy(project_root)
    before_hashes = verify_pinned_inputs(project_root, policy)
    before_cache = cache_fingerprints(project_root)
    output_dir = project_root / OUTPUT_DIR
    output_dir.mkdir(parents=False, exist_ok=False)
    configuration = execution_configuration(policy)
    validate_schema(configuration, policy["runtime_output_contract"]["artifacts"]["execution_configuration.json"]["top_level_keys"], "execution_configuration.json")
    _write_bytes(output_dir / "execution_configuration.json", serialize_json(configuration))

    stage_a_results: list[dict[str, Any]] = []
    event_number = 0

    def gate(gate_id: str, evidence: str) -> None:
        nonlocal event_number
        event_number += 1
        stage_a_results.append({"gate_id": gate_id, "passed": True, "evidence": evidence})

    try:
        with offline_scope():
            gate("pinned_input_hashes", f"{len(before_hashes)} pinned files and 129 cache files matched")
            preprocessing = _read_json(project_root / R2_DIR / "preprocessing_state.json")
            if canonical_content_hash(preprocessing) != preprocessing.get("deterministic_content_sha256"):
                raise ContractFailure("preprocessing-state content hash mismatch")
            train_columns, training_rows = _read_csv(project_root / TRAINING_PATH)
            index_columns, index_rows = _read_csv(project_root / R2_DIR / "holdout_row_index.csv")
            staging_columns, staging_rows = _read_csv(project_root / R2_DIR / "holdout_staging.csv")
            matrix_columns, matrix_rows = _read_csv(project_root / R2_DIR / "holdout_estimator_matrix.csv")
            if len(training_rows) != 27001 or not (len(index_rows) == len(staging_rows) == len(matrix_rows) == 2700):
                raise ContractFailure("frozen training or holdout row count mismatch")
            gate("training_holdout_row_counts", "27,001 training and 2,700 aligned holdout rows")
            features = list(phase3r3.FEATURES)
            if matrix_columns != features or len(features) != len(set(features)) or preprocessing["feature_order"] != features:
                raise ContractFailure("45-feature order mismatch")
            gate("feature_count_order", "45 unique features in frozen order for both matrices")
            training_x = reconstruct_training_matrix(training_rows, preprocessing)
            holdout_x = np.asarray([[row[name] for name in features] for row in matrix_rows], dtype=np.float64)
            if not np.isfinite(training_x).all() or not np.isfinite(holdout_x).all():
                raise ContractFailure("nonfinite estimator value")
            gate("finite_estimator_matrix", "all 1,215,045 estimator values finite")
            target = _finite_vector((row["target_net_rating"] for row in index_rows), "holdout target")
            if len(target) != 2700:
                raise ContractFailure("target length mismatch")
            gate("finite_target_vector", "2,700 target values finite; no target summary calculated")
            estimator = Ridge(alpha=3000.0)
            if estimator.__class__ is not Ridge or estimator.get_params()["alpha"] != 3000.0:
                raise ContractFailure("authorized estimator identity mismatch")
            gate("estimator_identity", "exact sklearn.linear_model.Ridge(alpha=3000.0)")
            seasons = {row["target_season"] for row in training_rows}
            if seasons != set(phase3r3.TRAINING_SEASONS) or any(float(row["pair_possessions"]) < 150 for row in training_rows):
                raise ContractFailure("training population mismatch")
            training_target = _finite_vector((row["target_net_rating"] for row in training_rows), "training target")
            gate("training_population_weights", "hash-pinned POSS >= 150 population; equal implicit row weights; exact-250 included")
            if not preprocessing["training_derived_only"] or preprocessing["holdout_predictors_or_targets_used_to_fit_preprocessing"]:
                raise ContractFailure("training-only preprocessing flag mismatch")
            gate("training_only_preprocessing", "frozen R2 medians, fills, and scaler applied without refit")
            if training_x.shape != (27001, 45) or holdout_x.shape != (2700, 45):
                raise ContractFailure("transformed matrix compatibility mismatch")
            gate("transformation_compatibility", "training and direct holdout matrices share frozen scaled feature space")
            keys = []
            for position, (index_row, staging_row) in enumerate(zip(index_rows, staging_rows)):
                key = numeric_observation_key(index_row)
                staging_key = numeric_observation_key(staging_row)
                if key != staging_key or any(index_row[name] != staging_row[name] for name in index_columns):
                    raise ContractFailure(f"holdout row alignment mismatch at {position}")
                keys.append(key)
            gate("row_key_alignment", "row positions 0..2699 align index, staging, matrix, target, and prediction input")
            if any(row["team_id"] in EXCLUDED_TEAMS for row in index_rows):
                raise ContractFailure("excluded team present")
            gate("excluded_teams_absent", "Charlotte and Philadelphia absent")
            if len(set(keys)) != 2700:
                raise ContractFailure("duplicate observation key")
            gate("canonical_unique_pairs", "2,700 unique numeric-canonical observation keys")
            manifest = _read_json(project_root / R2_DIR / "estimator_feature_manifest.json")
            proof = manifest["slot_swap_proof"]
            if proof["slot_swap_feature_values_checked"] != 121500 or proof["slot_swap_mismatches"] != 0 or not manifest["all_features_symmetric"]:
                raise ContractFailure("prediction symmetry proof mismatch")
            gate("prediction_symmetry", "R2 121,500-value slot-swap proof intact; symmetric columns only")
            estimator.fit(training_x, training_target)
            prediction = np.asarray(estimator.predict(holdout_x), dtype=np.float64)
            gate("single_authorized_prediction_vector", "one Ridge fit and one 2,700-value prediction call; vector remains memory-only")
            if prediction.shape != (2700,) or not np.isfinite(prediction).all():
                raise ContractFailure("prediction vector shape or finiteness mismatch")
            gate("finite_prediction_vector", "all 2,700 in-memory Ridge predictions finite and aligned")
            gate("no_calibrator_prediction_transform", "no calibrator or prediction transform instantiated or applied")
            gate("no_alternate_estimator_prediction", "no alternate estimator or prediction vector instantiated or generated")
            gate("offline_protected_scope", "socket-level network guard active; protected-season identity guard active; no 2025-26 access")
            after_hashes = verify_pinned_inputs(project_root, policy)
            after_cache = cache_fingerprints(project_root)
            if after_hashes != before_hashes or after_cache != before_cache:
                raise ContractFailure("input or cache fingerprints changed after prediction")
            gate("input_cache_immutability", "all pinned inputs and 129 cache fingerprints unchanged after prediction")
        expected_gate_ids = [item["id"] for item in phase3r3.STAGE_A_PRE_METRIC_GATES]
        if [item["gate_id"] for item in stage_a_results] != expected_gate_ids:
            raise ContractFailure("Stage A gate order mismatch")
        integrity = {
            "version": VERSION,
            "policy_identity": configuration["policy_identity"],
            "stage_a_gate_results": stage_a_results,
            "stage_a_pass": True,
            "training_rows": 27001,
            "holdout_rows": 2700,
            "feature_count": 45,
            "prediction_count": 2700,
            "finite_target_count": 2700,
            "finite_prediction_count": 2700,
            "estimator_identity": {"family": "sklearn.linear_model.Ridge", "constructor_parameters": {"alpha": 3000.0}},
            "input_cache_fingerprints_before": before_cache,
            "input_cache_fingerprints_after_prediction": after_cache,
            "sequence_evidence": {
                "last_stage_a_event_number": event_number,
                "finalized_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "first_metric_event_number": event_number + 1,
            },
        }
        validate_schema(integrity, policy["runtime_output_contract"]["artifacts"]["pre_metric_integrity.json"]["top_level_keys"], "pre_metric_integrity.json")
        _write_bytes(output_dir / "pre_metric_integrity.json", serialize_json(integrity))
    except Exception as exc:
        failed_ids = {item["gate_id"] for item in stage_a_results}
        next_gate = next((g["id"] for g in phase3r3.STAGE_A_PRE_METRIC_GATES if g["id"] not in failed_ids), "unknown")
        stage_a_results.append({"gate_id": next_gate, "passed": False, "evidence": str(exc)})
        failure = {
            "version": VERSION,
            "policy_identity": configuration["policy_identity"],
            "stage_a_gate_results": stage_a_results,
            "stage_a_pass": False,
            "training_rows": 0,
            "holdout_rows": 0,
            "feature_count": 0,
            "prediction_count": 0,
            "finite_target_count": 0,
            "finite_prediction_count": 0,
            "estimator_identity": {"family": "sklearn.linear_model.Ridge", "constructor_parameters": {"alpha": 3000.0}},
            "input_cache_fingerprints_before": before_cache,
            "input_cache_fingerprints_after_prediction": {},
            "sequence_evidence": {"last_stage_a_event_number": event_number + 1, "finalized_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "first_metric_event_number": None},
        }
        integrity_path = output_dir / "pre_metric_integrity.json"
        if not integrity_path.exists():
            _write_bytes(integrity_path, serialize_json(failure))
        raise ContractFailure(f"INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE: {exc}") from exc

    # Stage B begins only after the passing integrity record is written and closed.
    integrity_hash = sha256_file(output_dir / "pre_metric_integrity.json")
    baseline_value = float(np.mean(training_target))
    baseline = np.full(2700, baseline_value, dtype=np.float64)
    ridge_metrics, ridge_nulls = metric_set(prediction, target)
    baseline_metrics, baseline_nulls = metric_set(baseline, target)
    ridge_wmae, ridge_wrmse = weighted_errors(prediction, target, _finite_vector((row["pair_possessions"] for row in index_rows), "possessions"))
    possessions = _finite_vector((row["pair_possessions"] for row in index_rows), "possessions")
    baseline_wmae, baseline_wrmse = weighted_errors(baseline, target, possessions)
    exact_indices = [i for i, row in enumerate(index_rows) if row["endpoint_exact_250_flag"] == "1"]
    if exact_indices:
        exact_metrics, _ = metric_set(prediction[exact_indices], target[exact_indices])
        exact = {"applicable": True, "row_count": len(exact_indices), "mae": exact_metrics["mae"], "rmse": exact_metrics["rmse"], "bias": exact_metrics["bias"], "not_applicable_reason": None}
    else:
        exact = {"applicable": False, "row_count": 0, "mae": None, "rmse": None, "bias": None, "not_applicable_reason": "zero retained rows have endpoint_exact_250_flag"}
    improvements = {
        "mae_baseline_minus_ridge": baseline_metrics["mae"] - ridge_metrics["mae"],
        "rmse_baseline_minus_ridge": baseline_metrics["rmse"] - ridge_metrics["rmse"],
    }
    overall = {
        "version": VERSION,
        "row_count": 2700,
        "ridge_unweighted": ridge_metrics,
        "baseline_unweighted": baseline_metrics,
        "improvements": improvements,
        "possession_weighted": {"ridge_mae": ridge_wmae, "ridge_rmse": ridge_wrmse, "baseline_mae": baseline_wmae, "baseline_rmse": baseline_wrmse},
        "dispersion": {"ridge_prediction_std": ridge_metrics["prediction_std"], "baseline_prediction_std": baseline_metrics["prediction_std"], "target_std": ridge_metrics["target_std"], "ridge_prediction_to_target_std_ratio": ridge_metrics["prediction_to_target_std_ratio"], "baseline_prediction_to_target_std_ratio": baseline_metrics["prediction_to_target_std_ratio"]},
        "exact_250_diagnostic": exact,
        "null_reasons": {"ridge_unweighted": ridge_nulls, "baseline_unweighted": baseline_nulls},
        "pre_metric_integrity_sha256": integrity_hash,
    }
    prediction_rows = [{
        "row_position": i, "target_season": row["target_season"], "team_id": row["team_id"],
        "player_1_id": row["player_1_id"], "player_2_id": row["player_2_id"],
        "target_net_rating": target[i], "ridge_prediction": prediction[i], "baseline_prediction": baseline[i],
        "pair_possessions": possessions[i], "history_status": row["history_status"],
        "endpoint_exact_250_flag": bool(int(row["endpoint_exact_250_flag"])),
    } for i, row in enumerate(index_rows)]
    missing_rows = _subgroup_rows(index_rows, prediction, target)
    if {row["history_group"]: row["row_count"] for row in missing_rows} != EXPECTED_HISTORY_COUNTS:
        raise ContractFailure("Stage B missing-history count mismatch")
    team_rows, loto_rows = _team_rows(index_rows, prediction, target, possessions)
    calibration_rows = _calibration_rows(index_rows, prediction, target)
    residual = residual_relationships(prediction, target, possessions)
    historical = _historical_stability(ridge_metrics)
    provisional = {
        "predictions.csv": prediction_rows,
        "overall_metrics.json": overall,
        "missing_history_metrics.csv": missing_rows,
        "team_metrics.csv": team_rows,
        "leave_one_team_out_metrics.csv": loto_rows,
        "calibration_bins.csv": calibration_rows,
        "residual_diagnostics.json": residual,
        "historical_stability.json": historical,
    }
    classification = classify(True, True, improvements["mae_baseline_minus_ridge"], improvements["rmse_baseline_minus_ridge"])
    stage_b_outcomes = [
        {"stage": "B", "gate_id": gate["id"], "passed": True}
        for gate in phase3r3.STAGE_B_POST_COMPUTATION_CHECKS
    ]
    decision = {
        "version": VERSION, "stage_a_pass": True, "stage_b_pass": True,
        "mae_improvement": improvements["mae_baseline_minus_ridge"], "rmse_improvement": improvements["rmse_baseline_minus_ridge"],
        "gate_outcomes": [{"stage": "A", "gate_id": row["gate_id"], "passed": row["passed"]} for row in stage_a_results] + stage_b_outcomes,
        "classification": classification,
    }
    provisional["evaluation_decision.json"] = decision
    if _validate_stage_b_in_memory(provisional, policy) != stage_b_outcomes:
        raise ContractFailure("Stage B gate-outcome ordering mismatch")

    contract_artifacts = policy["runtime_output_contract"]["artifacts"]
    for name in PAYLOAD_ARTIFACTS[2:]:
        spec = contract_artifacts[name]
        data = serialize_json(provisional[name]) if "top_level_keys" in spec else serialize_csv(provisional[name], spec["columns"])
        _write_bytes(output_dir / name, data)
    payload_manifest = {
        "version": VERSION,
        "payload_artifacts": {
            name: {"relative_path": name, "serialized_byte_sha256": sha256_file(output_dir / name)}
            for name in sorted(PAYLOAD_ARTIFACTS)
        },
        "excluded_from_own_byte_manifest": ["artifact_hashes.json", "summary.json"],
    }
    payload_manifest["deterministic_content_sha256"] = canonical_content_hash(payload_manifest)
    _write_bytes(output_dir / "artifact_hashes.json", serialize_json(payload_manifest))
    summary = {
        "version": VERSION,
        "policy_identity": configuration["policy_identity"],
        "artifact_manifest_canonical_sha256": payload_manifest["deterministic_content_sha256"],
        "final_classification": classification,
        "required_row_counts": {"training": 27001, "holdout": 2700, "teams": 28, "missing_history_groups": 3, "leave_one_team_out": 28, "calibration_bins": 10},
        "generated_artifact_count": 13,
        "final_test_season_accessed": False,
        "network_accessed": False,
        "alternate_model_generated": False,
    }
    _write_bytes(output_dir / "summary.json", serialize_json(summary))
    all_artifacts = provisional | {"artifact_hashes.json": payload_manifest, "summary.json": summary}
    report = _report_text(all_artifacts)
    _write_bytes(project_root / REPORT_PATH, report.encode("utf-8"))

    if set(path.name for path in output_dir.iterdir()) != set(OFFICIAL_ARTIFACTS):
        raise ContractFailure("Stage B artifact inventory mismatch")
    if len(list(output_dir.iterdir())) != 13:
        raise ContractFailure("Stage B artifact count mismatch")
    for name, entry in payload_manifest["payload_artifacts"].items():
        if sha256_file(output_dir / name) != entry["serialized_byte_sha256"]:
            raise ContractFailure(f"Stage B payload hash mismatch: {name}")
    if summary["final_classification"] != decision["classification"] or classification not in report:
        raise ContractFailure("Stage B human/machine classification mismatch")
    if verify_pinned_inputs(project_root, policy) != before_hashes or cache_fingerprints(project_root) != before_cache:
        raise ContractFailure("Stage B input/cache immutability mismatch")
    return {"classification": classification, "output_dir": str(output_dir), "report": str(project_root / REPORT_PATH)}
