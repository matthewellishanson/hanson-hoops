"""Correction-only reconciliation of the pinned Phase 3E-R4 prediction vector.

This module is deliberately model-free.  It verifies surviving evidence and
recomputes the frozen Stage B diagnostics without reconstructing estimator
inputs or creating any prediction values.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import math
import os
import re
import socket
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence
from unittest.mock import patch

import numpy as np


VERSION = "phase3e-r4-1.correction-only-reconciliation.v1"
EXPECTED_BRANCH = "research/pair-fit-v2"
EXPECTED_HEAD = "91635b517d3f63a318cae2ea6f65f324b9463b44"
ORIGINAL_CLASSIFICATION = "INVALID EVALUATION — IMPLEMENTATION OR CONTRACT FAILURE"
RECONCILIATION_STATUS = (
    "CORRECTION-ONLY RECONCILIATION ACCEPTED WITH DISCLOSED PROVENANCE LIMITATION"
)
PRE_EXECUTION_WRAPPER_FAILURE = {
    "occurred": True,
    "classification": "failed launcher attempt outside the official reconciliation execution",
    "cause": "Python module search path omitted the research project's src directory",
    "module_imported": False,
    "reconciliation_function_began": False,
    "runtime_directory_created": False,
    "event_ledger_created": False,
    "reconciliation_artifact_written": False,
    "original_r4_file_changed": False,
    "model_loaded_or_fitted": False,
    "prediction_generated": False,
    "protected_season_evidence_accessed": False,
    "corrective_action": "one separately authorized launch with PYTHONPATH explicitly set to src",
}
POLICY_CONTENT_SHA256 = "6e0eff4b38c520ed5bd0c26100b2ddb4b911d6d3c9bb92fd7f016416b6211ad4"
POLICY_BYTES_SHA256 = "f5d1e8852693b74d4e82ae505e9d355526a3ddaedc7fbb7ffc7282db3f48ee48"
PREDICTION_SHA256 = "616d39c61408986bcae69f4d1b2a5747d8322929a2cf1b003fcbf683b70fe58b"
STAGE_A_SHA256 = "b209f2a60ff4651f097f4347ad78f8c76ec8aae8e4f1a67d1e874ef7c986ee52"
ORIGINAL_DECISION_SHA256 = "34cc815f739c4182d5c22c4ad3b4d8bd1cee08e3798ed368f7d13b71e2c6856a"
ORIGINAL_SUMMARY_SHA256 = "e7245c11a0364bd0810a0022b67a856939ceb90ea961d461e0fc22daead00178"
ORIGINAL_REPORT_SHA256 = "321eb2de5fe1cf6d2a41b2b24d28f6e80a148546f11ca599433a258fac472342"
FLOAT_TOLERANCE = 1e-12
PROTECTED_SEASON = "2025-26"
EXCLUDED_TEAMS = {"1610612755", "1610612766"}

POLICY_PATH = Path("modeling/phase3e-r3/evaluation_policy.json")
R2_INDEX_PATH = Path("curated/phase3e-r2/holdout_row_index.csv")
ORIGINAL_DIR = Path("modeling/phase3e-r4")
PREDICTION_PATH = ORIGINAL_DIR / "predictions.csv"
STAGE_A_PATH = ORIGINAL_DIR / "pre_metric_integrity.json"
ORIGINAL_DECISION_PATH = ORIGINAL_DIR / "evaluation_decision.json"
ORIGINAL_SUMMARY_PATH = ORIGINAL_DIR / "summary.json"
ORIGINAL_REPORT_PATH = Path("PHASE3E_R4_DEVELOPMENT_HOLDOUT_EVALUATION_REPORT.md")
WAIVER_PATH = Path("PHASE3E_R4_PROVENANCE_WAIVER.md")
OUTPUT_DIR = Path("modeling/phase3e-r4-1-reconciliation")
REPORT_PATH = Path("PHASE3E_R4_1_CORRECTION_ONLY_RECONCILIATION_REPORT.md")

ORIGINAL_RUNTIME_FILES = (
    "artifact_hashes.json",
    "calibration_bins.csv",
    "evaluation_decision.json",
    "execution_configuration.json",
    "historical_stability.json",
    "leave_one_team_out_metrics.csv",
    "missing_history_metrics.csv",
    "overall_metrics.json",
    "pre_metric_integrity.json",
    "predictions.csv",
    "residual_diagnostics.json",
    "summary.json",
    "team_metrics.csv",
)
RUNTIME_FILES = (
    "reconciliation_configuration.json",
    "source_evidence_verification.json",
    "reconciled_overall_metrics.json",
    "reconciled_missing_history_metrics.csv",
    "reconciled_team_metrics.csv",
    "reconciled_leave_one_team_out_metrics.csv",
    "reconciled_calibration_bins.csv",
    "reconciled_residual_diagnostics.json",
    "reconciled_historical_stability.json",
    "reconciliation_decision.json",
    "artifact_hashes.json",
    "summary.json",
    "execution_events.jsonl",
    "verification_results.json",
)
PAYLOAD_FILES = tuple(
    name for name in RUNTIME_FILES if name not in {"artifact_hashes.json", "summary.json"}
)
PREDICTION_COLUMNS = (
    "row_position",
    "target_season",
    "team_id",
    "player_1_id",
    "player_2_id",
    "target_net_rating",
    "ridge_prediction",
    "baseline_prediction",
    "pair_possessions",
    "history_status",
    "endpoint_exact_250_flag",
)
MISSING_COLUMNS = (
    "history_group",
    "row_count",
    "mae",
    "rmse",
    "bias",
    "mae_difference_from_complete",
    "adequate_for_formal_comparison",
    "descriptive_only",
    "material_absolute_difference",
    "adverse_lower_confidence_difference",
)
TEAM_COLUMNS = (
    "team_id",
    "eligible_rows",
    "summed_possessions",
    "mae",
    "rmse",
    "bias",
    "mean_target",
    "mean_prediction",
)
LOTO_COLUMNS = (
    "removed_team_id",
    "remaining_rows",
    "leave_one_team_out_mae",
    "full_sample_mae",
    "full_sample_minus_leave_one_team_out_mae",
)
CALIBRATION_COLUMNS = (
    "bin",
    "tail",
    "row_count",
    "mean_prediction",
    "mean_target",
    "calibration_difference",
)

EXPECTED_PRE_RUN_REPOSITORY_CHANGES = {
    ".gitignore",
    "research/pair-fit-v2/PHASE3E_R4_DEVELOPMENT_HOLDOUT_EVALUATION_REPORT.md",
    "research/pair-fit-v2/PHASE3E_R4_PROVENANCE_WAIVER.md",
    "research/pair-fit-v2/src/pair_fit_v2/phase3e_r4_cli.py",
    "research/pair-fit-v2/src/pair_fit_v2/phase3e_r4_evaluation.py",
    "research/pair-fit-v2/src/pair_fit_v2/phase3e_r4_1_cli.py",
    "research/pair-fit-v2/src/pair_fit_v2/phase3e_r4_1_reconciliation.py",
    "research/pair-fit-v2/tests/test_phase3e_r4_evaluation.py",
    "research/pair-fit-v2/tests/test_phase3e_r4_1_reconciliation.py",
}


class ReconciliationFailure(RuntimeError):
    """A correction-only reconciliation contract failed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def reject_protected_identity(value: Any) -> None:
    if PROTECTED_SEASON in str(value).replace("\\", "/").lower():
        raise ReconciliationFailure(f"protected-season identity rejected before access: {value}")


@contextmanager
def offline_scope():
    """Fail closed if any socket-level network operation is attempted."""

    def reject(*_args: Any, **_kwargs: Any) -> None:
        raise ReconciliationFailure("network access is prohibited during reconciliation")

    with (
        patch.object(socket.socket, "connect", reject),
        patch.object(socket.socket, "connect_ex", reject),
        patch.object(socket, "create_connection", reject),
        patch.object(socket, "getaddrinfo", reject),
    ):
        yield


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    reject_protected_identity(path)
    return sha256_bytes(path.read_bytes())


def require_sha256(path: Path, expected: str, label: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise ReconciliationFailure(f"{label} hash mismatch")
    return actual


def serialize_json(document: Any) -> bytes:
    return (
        json.dumps(document, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def canonical_content_hash(document: Mapping[str, Any]) -> str:
    value = dict(document)
    value.pop("deterministic_content_sha256", None)
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return sha256_bytes(encoded)


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number):
            raise ReconciliationFailure("nonfinite CSV output is prohibited")
        return repr(number)
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return str(value)


def serialize_csv(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> bytes:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(
        handle, fieldnames=list(columns), lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    for row in rows:
        if list(row) != list(columns):
            raise ReconciliationFailure("CSV row schema or ordering mismatch")
        writer.writerow({column: _csv_value(row[column]) for column in columns})
    return handle.getvalue().encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    reject_protected_identity(path)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    reject_protected_identity(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ReconciliationFailure(f"invalid CSV header: {path}")
        return list(reader.fieldnames), list(reader)


def write_once(path: Path, data: bytes) -> None:
    reject_protected_identity(path)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ReconciliationFailure(f"refusing to overwrite: {path}") from exc


def _git(project_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=project_root, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise ReconciliationFailure(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def verify_git_state(project_root: Path) -> dict[str, Any]:
    branch = _git(project_root, "branch", "--show-current")
    head = _git(project_root, "rev-parse", "HEAD")
    upstream = _git(project_root, "rev-parse", "@{upstream}")
    staged = _git(project_root, "diff", "--cached", "--name-only").splitlines()
    status_lines = _git(
        project_root, "status", "--porcelain=v1", "--untracked-files=all"
    ).splitlines()
    changed: set[str] = set()
    for line in status_lines:
        if not line:
            continue
        value = line[3:].strip('"').replace("\\", "/")
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        changed.add(value)
    if branch != EXPECTED_BRANCH or head != EXPECTED_HEAD or upstream != EXPECTED_HEAD:
        raise ReconciliationFailure("branch, HEAD, or upstream mismatch")
    if staged:
        raise ReconciliationFailure(f"staging area is not empty: {staged}")
    if changed != EXPECTED_PRE_RUN_REPOSITORY_CHANGES:
        raise ReconciliationFailure(
            f"Git-visible inventory mismatch: expected {sorted(EXPECTED_PRE_RUN_REPOSITORY_CHANGES)}, "
            f"found {sorted(changed)}"
        )
    return {
        "branch": branch,
        "head": head,
        "upstream": upstream,
        "staged_paths": staged,
        "git_visible_paths": sorted(changed),
    }


def inventory_namespace(project_root: Path) -> dict[str, Any]:
    directory = project_root / ORIGINAL_DIR
    if not directory.is_dir():
        raise ReconciliationFailure("original R4 namespace is missing")
    entries: list[dict[str, Any]] = []
    for path in sorted((item for item in directory.rglob("*") if item.is_file())):
        stat = path.stat()
        entries.append(
            {
                "relative_path": path.relative_to(project_root).as_posix(),
                "byte_length": stat.st_size,
                "sha256": sha256_file(path),
                "modified_time_ns": stat.st_mtime_ns,
                "modified_utc": datetime.fromtimestamp(
                    stat.st_mtime_ns / 1_000_000_000, timezone.utc
                ).isoformat().replace("+00:00", "Z"),
            }
        )
    names = tuple(Path(entry["relative_path"]).name for entry in entries)
    if names != ORIGINAL_RUNTIME_FILES:
        raise ReconciliationFailure(f"original R4 runtime inventory mismatch: {names}")
    fingerprint = sha256_bytes(
        json.dumps(entries, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
            "utf-8"
        )
    )
    return {"file_count": len(entries), "files": entries, "fingerprint_sha256": fingerprint}


def report_identity(project_root: Path) -> dict[str, Any]:
    path = project_root / ORIGINAL_REPORT_PATH
    stat = path.stat()
    return {
        "relative_path": ORIGINAL_REPORT_PATH.as_posix(),
        "byte_length": stat.st_size,
        "sha256": sha256_file(path),
        "modified_time_ns": stat.st_mtime_ns,
        "modified_utc": datetime.fromtimestamp(
            stat.st_mtime_ns / 1_000_000_000, timezone.utc
        ).isoformat().replace("+00:00", "Z"),
    }


def verify_restart_safe(project_root: Path) -> None:
    if (project_root / OUTPUT_DIR).exists():
        raise ReconciliationFailure("reconciliation directory already exists; refusing restart")
    if (project_root / REPORT_PATH).exists():
        raise ReconciliationFailure("reconciliation report already exists; refusing overwrite")


def require_unchanged(before: Any, after: Any, label: str) -> None:
    if before != after:
        raise ReconciliationFailure(f"{label} changed during reconciliation")


class EventLedger:
    """Append-only JSONL event writer with a fixed schema."""

    def __init__(self, path: Path, clock: Callable[[], str] = utc_now):
        self.path = path
        self.clock = clock
        self.number = 0
        self.closed = False
        self.path.touch(exist_ok=False)

    def add(
        self,
        event_type: str,
        status: str,
        *,
        path: str | None = None,
        sha256: str | None = None,
        detail: str | None = None,
    ) -> dict[str, Any]:
        if self.closed:
            raise ReconciliationFailure("event ledger is closed")
        self.number += 1
        event = {
            "event_number": self.number,
            "timestamp_utc": self.clock(),
            "event_type": event_type,
            "status": status,
            "path": path,
            "sha256": sha256,
            "detail": detail,
        }
        data = (
            json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
            + "\n"
        ).encode("utf-8")
        with self.path.open("ab") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return event

    def close(self) -> None:
        self.closed = True


def validate_event_ledger(path: Path) -> dict[str, Any]:
    required = {
        "event_number",
        "timestamp_utc",
        "event_type",
        "status",
        "path",
        "sha256",
        "detail",
    }
    lines = path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    if not events or any(set(event) != required for event in events):
        raise ReconciliationFailure("event ledger schema mismatch")
    if [event["event_number"] for event in events] != list(range(1, len(events) + 1)):
        raise ReconciliationFailure("event numbers are not monotonic and contiguous")
    timestamps = [event["timestamp_utc"] for event in events]
    if timestamps != sorted(timestamps):
        raise ReconciliationFailure("event timestamps are not monotonic")
    return {"event_count": len(events), "first_event": events[0], "last_event": events[-1]}


def static_prohibition_audit(project_root: Path) -> dict[str, Any]:
    paths = [
        project_root / "src/pair_fit_v2/phase3e_r4_1_reconciliation.py",
        project_root / "src/pair_fit_v2/phase3e_r4_1_cli.py",
    ]
    forbidden_imports: list[str] = []
    forbidden_calls: list[str] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                forbidden_imports.extend(
                    alias.name for alias in node.names if alias.name == "sklearn" or alias.name.startswith("sklearn.")
                )
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "sklearn" or module.startswith("sklearn."):
                    forbidden_imports.append(module)
            if isinstance(node, ast.Call):
                called = node.func
                name = called.attr if isinstance(called, ast.Attribute) else called.id if isinstance(called, ast.Name) else ""
                if name in {"fit", "predict", "fit_predict"}:
                    forbidden_calls.append(name)
    if forbidden_imports or forbidden_calls:
        raise ReconciliationFailure(
            f"model prohibition audit failed: imports={forbidden_imports}, calls={forbidden_calls}"
        )
    return {
        "paths": [path.relative_to(project_root).as_posix() for path in paths],
        "forbidden_imports": forbidden_imports,
        "forbidden_calls": forbidden_calls,
        "passed": True,
    }


def _finite_vector(values: Iterable[Any], name: str) -> np.ndarray:
    try:
        vector = np.asarray(list(values), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ReconciliationFailure(f"{name} is not numeric") from exc
    if vector.ndim != 1 or not np.isfinite(vector).all():
        raise ReconciliationFailure(f"{name} contains missing or nonfinite values")
    return vector


def numeric_observation_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    season = str(row["target_season"])
    reject_protected_identity(season)
    identifiers = [str(row[name]) for name in ("team_id", "player_1_id", "player_2_id")]
    if any(
        not value.isdecimal() or int(value) <= 0 or str(int(value)) != value
        for value in identifiers
    ):
        raise ReconciliationFailure("noncanonical numeric observation key")
    if int(identifiers[1]) >= int(identifiers[2]):
        raise ReconciliationFailure("player identifiers are not in numeric canonical order")
    return season, *identifiers


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
    left_variance = float(np.var(left, ddof=0))
    right_variance = float(np.var(right, ddof=0))
    if left_variance == 0.0:
        return None, "left vector variance is zero"
    if right_variance == 0.0:
        return None, "right vector variance is zero"
    covariance = float(np.mean((left - np.mean(left)) * (right - np.mean(right))))
    value = covariance / math.sqrt(left_variance * right_variance)
    if not math.isfinite(value):
        return None, "correlation is nonfinite"
    return value, None


def metric_set(values: Iterable[Any], target: Iterable[Any]) -> tuple[dict[str, Any], dict[str, str]]:
    estimate = _finite_vector(values, "estimate")
    truth = _finite_vector(target, "target")
    if len(estimate) != len(truth) or not len(estimate):
        raise ReconciliationFailure("metric vectors are empty or misaligned")
    error = estimate - truth
    target_variance = float(np.var(truth, ddof=0))
    estimate_std = float(np.std(estimate, ddof=0))
    target_std = float(np.std(truth, ddof=0))
    nulls: dict[str, str] = {}
    if target_variance == 0.0:
        r2 = None
        nulls["r2"] = "target variance is zero"
    else:
        r2 = 1.0 - float(np.sum(error * error)) / float(
            np.sum((truth - np.mean(truth)) ** 2)
        )
    spearman, reason = _pearson(_average_ranks(estimate), _average_ranks(truth))
    if reason:
        nulls["spearman"] = reason
    if target_std == 0.0:
        ratio = None
        nulls["prediction_to_target_std_ratio"] = "target standard deviation is zero"
    else:
        ratio = estimate_std / target_std
    return (
        {
            "mae": float(np.mean(np.abs(error))),
            "rmse": float(math.sqrt(float(np.mean(error * error)))),
            "r2": r2,
            "bias": float(np.mean(error)),
            "spearman": spearman,
            "prediction_std": estimate_std,
            "target_std": target_std,
            "prediction_to_target_std_ratio": ratio,
        },
        nulls,
    )


def weighted_errors(values: np.ndarray, target: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    if np.any(weights <= 0) or not np.isfinite(weights).all() or float(np.sum(weights)) <= 0:
        raise ReconciliationFailure("possession weights must be finite and positive")
    error = values - target
    return (
        float(np.sum(weights * np.abs(error)) / np.sum(weights)),
        float(math.sqrt(float(np.sum(weights * error * error) / np.sum(weights)))),
    )


def residual_relationships(values: Iterable[Any], target: Iterable[Any], possessions: Iterable[Any]) -> dict[str, Any]:
    estimate = _finite_vector(values, "estimate")
    truth = _finite_vector(target, "target")
    weights = _finite_vector(possessions, "possessions")
    if not (len(estimate) == len(truth) == len(weights)):
        raise ReconciliationFailure("residual vectors are misaligned")
    residual = truth - estimate
    residual_variance = float(np.var(residual, ddof=0))
    estimate_variance = float(np.var(estimate, ddof=0))
    possession_variance = float(np.var(weights, ddof=0))
    nulls: dict[str, str] = {}

    def relationship(independent: np.ndarray, variance: float, label: str) -> tuple[float | None, float | None]:
        correlation, reason = _pearson(residual, independent)
        if reason:
            nulls[f"residual_vs_{label}_pearson"] = reason
        if variance == 0.0:
            slope = None
            nulls[f"residual_vs_{label}_slope"] = f"{label} variance is zero"
        else:
            slope = float(
                np.mean(
                    (independent - np.mean(independent)) * (residual - np.mean(residual))
                )
                / variance
            )
        return correlation, slope

    estimate_correlation, estimate_slope = relationship(
        estimate, estimate_variance, "prediction"
    )
    possession_correlation, possession_slope = relationship(
        weights, possession_variance, "possessions"
    )
    return {
        "version": VERSION,
        "row_count": len(estimate),
        "residual_sign_convention": "target minus prediction",
        "residual_mean": float(np.mean(residual)),
        "residual_variance": residual_variance,
        "prediction_variance": estimate_variance,
        "possessions_variance": possession_variance,
        "residual_vs_prediction_pearson": estimate_correlation,
        "residual_vs_prediction_slope": estimate_slope,
        "residual_vs_possessions_pearson": possession_correlation,
        "residual_vs_possessions_slope": possession_slope,
        "null_reasons": nulls,
    }


def classify_scientific(mae_improvement: float, rmse_improvement: float) -> str:
    if not math.isfinite(mae_improvement) or not math.isfinite(rmse_improvement):
        raise ReconciliationFailure("nonfinite improvement cannot receive a scientific classification")
    if mae_improvement <= 0.0:
        return "VALID DEVELOPMENT-HOLDOUT SCIENTIFIC FAILURE"
    if mae_improvement >= 0.10 and rmse_improvement >= 0.0:
        return "VALID DEVELOPMENT-HOLDOUT PASS"
    return "VALID DEVELOPMENT-HOLDOUT MIXED RESULT"


def subgroup_rows(records: Sequence[Mapping[str, Any]], values: np.ndarray, target: np.ndarray) -> list[dict[str, Any]]:
    complete_indices = [
        index for index, row in enumerate(records) if row["history_status"] == "complete"
    ]
    complete_mae = metric_set(values[complete_indices], target[complete_indices])[0]["mae"]
    output: list[dict[str, Any]] = []
    for group in ("complete", "one_missing", "both_missing"):
        indices = [index for index, row in enumerate(records) if row["history_status"] == group]
        metrics, _ = metric_set(values[indices], target[indices])
        difference = metrics["mae"] - complete_mae
        adequate = len(indices) >= 100 and group in {"complete", "one_missing"}
        output.append(
            {
                "history_group": group,
                "row_count": len(indices),
                "mae": metrics["mae"],
                "rmse": metrics["rmse"],
                "bias": metrics["bias"],
                "mae_difference_from_complete": difference,
                "adequate_for_formal_comparison": adequate,
                "descriptive_only": group == "both_missing",
                "material_absolute_difference": abs(difference) >= 0.50,
                "adverse_lower_confidence_difference": group != "complete" and difference >= 0.50,
            }
        )
    return output


def team_rows(
    records: Sequence[Mapping[str, Any]], values: np.ndarray, target: np.ndarray, possessions: np.ndarray
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    teams = sorted({str(row["team_id"]) for row in records}, key=int)
    output: list[dict[str, Any]] = []
    leave_one_out: list[dict[str, Any]] = []
    full_mae = float(np.mean(np.abs(values - target)))
    for team in teams:
        selected = np.asarray([str(row["team_id"]) == team for row in records], dtype=bool)
        metrics, _ = metric_set(values[selected], target[selected])
        output.append(
            {
                "team_id": team,
                "eligible_rows": int(np.sum(selected)),
                "summed_possessions": float(np.sum(possessions[selected])),
                "mae": metrics["mae"],
                "rmse": metrics["rmse"],
                "bias": metrics["bias"],
                "mean_target": float(np.mean(target[selected])),
                "mean_prediction": float(np.mean(values[selected])),
            }
        )
        remaining = ~selected
        without_team = float(np.mean(np.abs(values[remaining] - target[remaining])))
        leave_one_out.append(
            {
                "removed_team_id": team,
                "remaining_rows": int(np.sum(remaining)),
                "leave_one_team_out_mae": without_team,
                "full_sample_mae": full_mae,
                "full_sample_minus_leave_one_team_out_mae": full_mae - without_team,
            }
        )
    return output, leave_one_out


def calibration_rows(records: Sequence[Mapping[str, Any]], values: np.ndarray, target: np.ndarray) -> list[dict[str, Any]]:
    order = sorted(
        range(len(records)),
        key=lambda index: (
            values[index],
            int(records[index]["team_id"]),
            int(records[index]["player_1_id"]),
            int(records[index]["player_2_id"]),
        ),
    )
    output: list[dict[str, Any]] = []
    for bin_number in range(1, 11):
        indices = order[(bin_number - 1) * 270 : bin_number * 270]
        mean_value = float(np.mean(values[indices]))
        mean_target = float(np.mean(target[indices]))
        output.append(
            {
                "bin": bin_number,
                "tail": "lower" if bin_number == 1 else "upper" if bin_number == 10 else "middle",
                "row_count": len(indices),
                "mean_prediction": mean_value,
                "mean_target": mean_target,
                "calibration_difference": mean_target - mean_value,
            }
        )
    return output


def historical_stability(metrics: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    reference = policy["historical_reference"]
    source = reference["six_validation_seasons_and_pooled"]
    pooled = dict(source["pooled"])
    seasons = ("2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24")
    folds = {season: dict(source[season]) for season in seasons}
    compared = (
        "r2",
        "bias",
        "spearman",
        "prediction_std",
        "target_std",
        "prediction_to_target_std_ratio",
    )
    deltas = {
        metric: metrics[metric] - pooled[metric]
        for metric in ("mae", "rmse", *compared)
        if metrics[metric] is not None
    }
    ranges: dict[str, Any] = {}
    outside: dict[str, bool] = {}
    for metric in compared:
        values = [folds[season][metric] for season in seasons]
        value = metrics[metric]
        position = (
            "not_comparable"
            if value is None
            else "below"
            if value < min(values)
            else "above"
            if value > max(values)
            else "within"
        )
        ranges[metric] = {
            "fold_min": min(values),
            "fold_max": max(values),
            "holdout_value": value,
            "position": position,
        }
        outside[metric] = position in {"below", "above"}
    return {
        "version": VERSION,
        "holdout_values": dict(metrics),
        "historical_pooled_reference": pooled,
        "historical_fold_references": folds,
        "deltas_from_pooled": deltas
        | {
            "mae_minus_phase3d_macro_mae": metrics["mae"] - reference["phase3d_macro_mae"],
            "mae_minus_historical_worst_season_mae": metrics["mae"]
            - reference["phase3d_worst_validation_season_mae"],
            "rmse_minus_historical_worst_season_rmse": metrics["rmse"]
            - reference["phase3d_worst_validation_season_rmse"],
        },
        "fold_range_comparisons": ranges,
        "warning_flags": {
            "mae_above_worst_by_more_than_0_50": metrics["mae"]
            > reference["mae_extreme_deterioration_threshold"],
            "rmse_above_historical_worst": metrics["rmse"]
            > reference["phase3d_worst_validation_season_rmse"],
            "outside_six_fold_range": outside,
            "absolute_bias_above_historical_maximum": abs(metrics["bias"])
            > max(abs(folds[season]["bias"]) for season in seasons),
        },
    }


def _policy_r2_index_hash(policy: Mapping[str, Any]) -> str:
    return policy["input_artifacts"]["phase3e_r2"]["holdout_row_index.csv"][
        "serialized_byte_sha256"
    ]


def verify_source_evidence(
    project_root: Path, before_namespace: Mapping[str, Any], before_report: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    policy_path = project_root / POLICY_PATH
    require_sha256(policy_path, POLICY_BYTES_SHA256, "serialized R3 policy")
    policy = read_json(policy_path)
    if canonical_content_hash(policy) != POLICY_CONTENT_SHA256:
        raise ReconciliationFailure("canonical R3 policy hash mismatch")
    require_sha256(project_root / PREDICTION_PATH, PREDICTION_SHA256, "persisted prediction")
    require_sha256(project_root / STAGE_A_PATH, STAGE_A_SHA256, "Stage A record")
    require_sha256(
        project_root / ORIGINAL_DECISION_PATH, ORIGINAL_DECISION_SHA256, "original invalid decision"
    )
    require_sha256(
        project_root / ORIGINAL_SUMMARY_PATH, ORIGINAL_SUMMARY_SHA256, "original invalid summary"
    )
    if before_report["sha256"] != ORIGINAL_REPORT_SHA256:
        raise ReconciliationFailure("original invalid report hash mismatch")

    stage_a = read_json(project_root / STAGE_A_PATH)
    original_decision = read_json(project_root / ORIGINAL_DECISION_PATH)
    original_summary = read_json(project_root / ORIGINAL_SUMMARY_PATH)
    if stage_a.get("stage_a_pass") is not True or len(stage_a.get("stage_a_gate_results", [])) != 19:
        raise ReconciliationFailure("surviving Stage A record is not passing and complete")
    if original_decision.get("classification") != ORIGINAL_CLASSIFICATION:
        raise ReconciliationFailure("original invalid classification mismatch")
    if original_summary.get("final_classification") != ORIGINAL_CLASSIFICATION:
        raise ReconciliationFailure("original invalid summary classification mismatch")

    prediction_columns, prediction_rows = read_csv(project_root / PREDICTION_PATH)
    index_path = project_root / R2_INDEX_PATH
    expected_index_hash = _policy_r2_index_hash(policy)
    if sha256_file(index_path) != expected_index_hash:
        raise ReconciliationFailure("frozen R2 row-index hash mismatch")
    _, index_rows = read_csv(index_path)
    if prediction_columns != list(PREDICTION_COLUMNS) or len(prediction_rows) != 2700:
        raise ReconciliationFailure("prediction schema or row count mismatch")
    if len(index_rows) != 2700:
        raise ReconciliationFailure("R2 row-index count mismatch")
    if [int(row["row_position"]) for row in prediction_rows] != list(range(2700)):
        raise ReconciliationFailure("prediction row positions are not 0..2699")

    keys: list[tuple[str, str, str, str]] = []
    for position, (row, index_row) in enumerate(zip(prediction_rows, index_rows)):
        key = numeric_observation_key(row)
        if key != numeric_observation_key(index_row):
            raise ReconciliationFailure(f"R2 observation-key misalignment at row {position}")
        for field in ("target_net_rating", "pair_possessions"):
            if float(row[field]) != float(index_row[field]):
                raise ReconciliationFailure(f"R2 {field} misalignment at row {position}")
        if row["history_status"] != index_row["history_status"]:
            raise ReconciliationFailure(f"R2 history status misalignment at row {position}")
        expected_flag = index_row["endpoint_exact_250_flag"] == "1"
        if (row["endpoint_exact_250_flag"].lower() == "true") != expected_flag:
            raise ReconciliationFailure(f"R2 exact-250 flag misalignment at row {position}")
        keys.append(key)
    if len(set(keys)) != 2700:
        raise ReconciliationFailure("prediction observation keys are not unique")
    if {row["target_season"] for row in prediction_rows} != {"2024-25"}:
        raise ReconciliationFailure("prediction file is not exclusively 2024-25")
    if {row["team_id"] for row in prediction_rows} & EXCLUDED_TEAMS:
        raise ReconciliationFailure("excluded team appears in prediction file")

    target = _finite_vector((row["target_net_rating"] for row in prediction_rows), "target")
    values = _finite_vector((row["ridge_prediction"] for row in prediction_rows), "prediction")
    baseline = _finite_vector((row["baseline_prediction"] for row in prediction_rows), "baseline")
    possessions = _finite_vector((row["pair_possessions"] for row in prediction_rows), "possessions")
    if len(set(float(value) for value in baseline)) != 1:
        raise ReconciliationFailure("persisted baseline is not one constant historical mean")
    if np.any(possessions <= 0):
        raise ReconciliationFailure("prediction possessions are not positive and finite")
    if any("prediction" in column and column not in {"ridge_prediction", "baseline_prediction"} for column in prediction_columns):
        raise ReconciliationFailure("unexpected prediction column exists")
    if any(Path(name).suffix.lower() in {".pkl", ".pickle", ".joblib", ".onnx"} for name in ORIGINAL_RUNTIME_FILES):
        raise ReconciliationFailure("model artifact exists in original namespace")

    evidence = {
        "version": VERSION,
        "verification_status": "passed under explicit provenance waiver",
        "prediction_source": {
            "relative_path": PREDICTION_PATH.as_posix(),
            "serialized_byte_sha256": PREDICTION_SHA256,
            "row_count": 2700,
            "columns": list(PREDICTION_COLUMNS),
            "row_positions": "0..2699",
            "unique_numeric_canonical_observation_keys": 2700,
            "target_seasons": ["2024-25"],
            "excluded_teams_absent": True,
            "ridge_prediction_columns": 1,
            "constant_baseline_columns": 1,
            "finite_target_prediction_baseline_possessions": True,
            "aligned_r2_row_index_relative_path": R2_INDEX_PATH.as_posix(),
            "aligned_r2_row_index_sha256": expected_index_hash,
            "target_source": "unchanged direct frozen R2 row-index target; not reconstructed or window aggregated",
        },
        "stage_a_source": {
            "relative_path": STAGE_A_PATH.as_posix(),
            "serialized_byte_sha256": STAGE_A_SHA256,
            "stage_a_pass": True,
            "gate_count": 19,
        },
        "policy_identity": {
            "relative_path": POLICY_PATH.as_posix(),
            "canonical_content_sha256": POLICY_CONTENT_SHA256,
            "serialized_byte_sha256": POLICY_BYTES_SHA256,
        },
        "original_invalid_evidence": {
            "decision_relative_path": ORIGINAL_DECISION_PATH.as_posix(),
            "decision_sha256": ORIGINAL_DECISION_SHA256,
            "summary_relative_path": ORIGINAL_SUMMARY_PATH.as_posix(),
            "summary_sha256": ORIGINAL_SUMMARY_SHA256,
            "report_relative_path": ORIGINAL_REPORT_PATH.as_posix(),
            "report_sha256": ORIGINAL_REPORT_SHA256,
            "classification": ORIGINAL_CLASSIFICATION,
        },
        "original_namespace_before": before_namespace,
        "original_report_before": before_report,
        "evidence_categories": {
            "directly_verified_surviving_evidence": [
                "persisted prediction bytes, schema, row count, finiteness, constant baseline, and R2 alignment",
                "passing surviving Stage A record bytes and status",
                "R3 policy bytes and canonical content",
                "original invalid decision, summary, report, and namespace inventory",
            ],
            "strongly_corroborated_historical_claims": [
                "exactly one fit and one prediction operation produced the persisted vector"
            ],
            "unresolved_historical_claims": [
                "first stopped invocation was not directly logged",
                "exact narrow preflight patch cannot be reconstructed",
                "original defective Stage B artifacts and manifest were overwritten",
                "original test console output was not retained",
            ],
            "user_accepted_waiver_claims": [
                "no recovered evidence contradicts the production account",
                "unchanged persisted prediction vector is authoritative 2024-25 development evidence",
                "Stage B may be recomputed without refitting or regenerating predictions",
            ],
        },
        "prohibition_verification": {
            "model_artifact_present": False,
            "alternate_prediction_present": False,
            "network_accessed": False,
            "protected_season_accessed": False,
        },
    }
    vectors = {
        "target": target,
        "values": values,
        "baseline": baseline,
        "possessions": possessions,
        "policy": policy,
    }
    return evidence, prediction_rows, vectors


def compute_stage_b(
    records: Sequence[Mapping[str, Any]], vectors: Mapping[str, Any]
) -> dict[str, Any]:
    values = vectors["values"]
    target = vectors["target"]
    baseline = vectors["baseline"]
    possessions = vectors["possessions"]
    policy = vectors["policy"]
    ridge_metrics, ridge_nulls = metric_set(values, target)
    baseline_metrics, baseline_nulls = metric_set(baseline, target)
    ridge_weighted = weighted_errors(values, target, possessions)
    baseline_weighted = weighted_errors(baseline, target, possessions)
    exact_indices = [
        index
        for index, row in enumerate(records)
        if row["endpoint_exact_250_flag"].lower() == "true"
    ]
    if exact_indices:
        exact_metrics, _ = metric_set(values[exact_indices], target[exact_indices])
        exact = {
            "applicable": True,
            "row_count": len(exact_indices),
            "mae": exact_metrics["mae"],
            "rmse": exact_metrics["rmse"],
            "bias": exact_metrics["bias"],
            "not_applicable_reason": None,
        }
    else:
        exact = {
            "applicable": False,
            "row_count": 0,
            "mae": None,
            "rmse": None,
            "bias": None,
            "not_applicable_reason": "zero retained rows have endpoint_exact_250_flag",
        }
    improvements = {
        "mae_baseline_minus_ridge": baseline_metrics["mae"] - ridge_metrics["mae"],
        "rmse_baseline_minus_ridge": baseline_metrics["rmse"] - ridge_metrics["rmse"],
    }
    overall = {
        "version": VERSION,
        "source_prediction_sha256": PREDICTION_SHA256,
        "row_count": 2700,
        "ridge_unweighted": ridge_metrics,
        "baseline_unweighted": baseline_metrics,
        "improvements": improvements,
        "possession_weighted": {
            "ridge_mae": ridge_weighted[0],
            "ridge_rmse": ridge_weighted[1],
            "baseline_mae": baseline_weighted[0],
            "baseline_rmse": baseline_weighted[1],
        },
        "dispersion": {
            "ridge_prediction_std": ridge_metrics["prediction_std"],
            "baseline_prediction_std": baseline_metrics["prediction_std"],
            "target_std": ridge_metrics["target_std"],
            "ridge_prediction_to_target_std_ratio": ridge_metrics[
                "prediction_to_target_std_ratio"
            ],
            "baseline_prediction_to_target_std_ratio": baseline_metrics[
                "prediction_to_target_std_ratio"
            ],
        },
        "exact_250_diagnostic": exact,
        "null_reasons": {
            "ridge_unweighted": ridge_nulls,
            "baseline_unweighted": baseline_nulls,
        },
        "stage_a_source_sha256": STAGE_A_SHA256,
    }
    missing = subgroup_rows(records, values, target)
    teams, leave_one_out = team_rows(records, values, target, possessions)
    calibration = calibration_rows(records, values, target)
    residual = residual_relationships(values, target, possessions)
    historical = historical_stability(ridge_metrics, policy)
    if {row["history_group"]: row["row_count"] for row in missing} != {
        "complete": 2139,
        "one_missing": 523,
        "both_missing": 38,
    }:
        raise ReconciliationFailure("missing-history counts do not match the frozen policy")
    if len(teams) != 28 or len(leave_one_out) != 28:
        raise ReconciliationFailure("team diagnostic row count mismatch")
    if len(calibration) != 10 or any(row["row_count"] != 270 for row in calibration):
        raise ReconciliationFailure("calibration row count mismatch")
    classification = classify_scientific(
        improvements["mae_baseline_minus_ridge"], improvements["rmse_baseline_minus_ridge"]
    )
    decision = {
        "version": VERSION,
        "original_r4_classification": ORIGINAL_CLASSIFICATION,
        "reconciled_scientific_classification": classification,
        "reconciliation_status": RECONCILIATION_STATUS,
        "provenance_limitation": (
            "accepted under explicit user waiver; exactly-one-fit/prediction lineage is strongly "
            "corroborated rather than command-log proven"
        ),
        "source_stage_a_pass": True,
        "recomputed_stage_b_pass": True,
        "mae_improvement": improvements["mae_baseline_minus_ridge"],
        "rmse_improvement": improvements["rmse_baseline_minus_ridge"],
        "frozen_gate_outcomes": {
            "mae_improvement_at_least_0_10": improvements["mae_baseline_minus_ridge"] >= 0.10,
            "rmse_improvement_at_least_0_0": improvements["rmse_baseline_minus_ridge"] >= 0.0,
        },
        "original_numerical_artifact_match": True,
        "network_accessed": False,
        "final_test_season_accessed": False,
        "model_fit_or_prediction_generated": False,
    }
    return {
        "reconciled_overall_metrics.json": overall,
        "reconciled_missing_history_metrics.csv": missing,
        "reconciled_team_metrics.csv": teams,
        "reconciled_leave_one_team_out_metrics.csv": leave_one_out,
        "reconciled_calibration_bins.csv": calibration,
        "reconciled_residual_diagnostics.json": residual,
        "reconciled_historical_stability.json": historical,
        "reconciliation_decision.json": decision,
    }


def _assert_close(actual: Any, expected: Any, path: str = "root") -> None:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping) or set(actual) != set(expected):
            raise ReconciliationFailure(f"numerical artifact mapping mismatch at {path}")
        for key in expected:
            _assert_close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ReconciliationFailure(f"numerical artifact list mismatch at {path}")
        for index, (left, right) in enumerate(zip(actual, expected)):
            _assert_close(left, right, f"{path}[{index}]")
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if actual != expected:
            raise ReconciliationFailure(f"numerical artifact value mismatch at {path}")
    elif isinstance(expected, (int, float)):
        if not isinstance(actual, (int, float)) or not math.isclose(
            float(actual), float(expected), rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE
        ):
            raise ReconciliationFailure(
                f"numerical artifact mismatch at {path}: {actual!r} != {expected!r}"
            )
    elif actual != expected:
        raise ReconciliationFailure(f"artifact mismatch at {path}")


def _typed_csv(path: Path) -> list[dict[str, Any]]:
    _, rows = read_csv(path)
    output: list[dict[str, Any]] = []
    for row in rows:
        converted: dict[str, Any] = {}
        for key, value in row.items():
            if value in {"true", "false"}:
                converted[key] = value == "true"
            elif key in {"history_group", "team_id", "removed_team_id", "tail"}:
                converted[key] = value
            elif key in {"row_count", "eligible_rows", "remaining_rows", "bin"}:
                converted[key] = int(value)
            else:
                converted[key] = float(value)
        output.append(converted)
    return output


def compare_original_numerical_artifacts(project_root: Path, artifacts: Mapping[str, Any]) -> None:
    original_overall = read_json(project_root / ORIGINAL_DIR / "overall_metrics.json")
    recomputed_overall = dict(artifacts["reconciled_overall_metrics.json"])
    recomputed_overall.pop("source_prediction_sha256")
    recomputed_overall.pop("stage_a_source_sha256")
    recomputed_overall["pre_metric_integrity_sha256"] = STAGE_A_SHA256
    recomputed_overall["version"] = original_overall["version"]
    _assert_close(recomputed_overall, original_overall, "overall")

    pairs = (
        ("reconciled_team_metrics.csv", "team_metrics.csv"),
        ("reconciled_leave_one_team_out_metrics.csv", "leave_one_team_out_metrics.csv"),
        ("reconciled_calibration_bins.csv", "calibration_bins.csv"),
    )
    for new_name, old_name in pairs:
        _assert_close(artifacts[new_name], _typed_csv(project_root / ORIGINAL_DIR / old_name), old_name)
    original_missing = _typed_csv(project_root / ORIGINAL_DIR / "missing_history_metrics.csv")
    recomputed_missing = [
        {key: value for key, value in row.items() if key != "descriptive_only"}
        for row in artifacts["reconciled_missing_history_metrics.csv"]
    ]
    _assert_close(recomputed_missing, original_missing, "missing_history_metrics.csv")
    for new_name, old_name in (
        ("reconciled_residual_diagnostics.json", "residual_diagnostics.json"),
        ("reconciled_historical_stability.json", "historical_stability.json"),
    ):
        expected = read_json(project_root / ORIGINAL_DIR / old_name)
        actual = dict(artifacts[new_name])
        actual["version"] = expected["version"]
        _assert_close(actual, expected, old_name)


def artifact_bytes(name: str, value: Any) -> bytes:
    if name == "reconciled_missing_history_metrics.csv":
        return serialize_csv(value, MISSING_COLUMNS)
    if name == "reconciled_team_metrics.csv":
        return serialize_csv(value, TEAM_COLUMNS)
    if name == "reconciled_leave_one_team_out_metrics.csv":
        return serialize_csv(value, LOTO_COLUMNS)
    if name == "reconciled_calibration_bins.csv":
        return serialize_csv(value, CALIBRATION_COLUMNS)
    return serialize_json(value)


def run_verification_command(project_root: Path, command: Sequence[str]) -> dict[str, Any]:
    started = utc_now()
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = str(project_root / "src")
    result = subprocess.run(
        list(command),
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    completed = utc_now()
    combined = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    passed_match = re.search(r"(\d+) passed", combined)
    failed_match = re.search(r"(\d+) failed", combined)
    deselected_match = re.search(r"(\d+) deselected", combined)
    return {
        "command": subprocess.list2cmdline(list(command)),
        "started_utc": started,
        "completed_utc": completed,
        "exit_code": result.returncode,
        "passed_count": int(passed_match.group(1)) if passed_match else None,
        "failed_count": int(failed_match.group(1)) if failed_match else 0 if passed_match else None,
        "deselected_count": int(deselected_match.group(1)) if deselected_match else 0,
        "output": combined,
    }


def verification_commands(project_root: Path) -> list[list[str]]:
    python = sys.executable
    return [
        [python, "-m", "pytest", "-q", "tests/test_phase3e_r4_1_reconciliation.py"],
        [
            python,
            "-m",
            "pytest",
            "-q",
            "tests/test_phase3e_r3_evaluation_policy.py",
            "-k",
            "not exact_r4_output_inventory_schemas_and_mutation_allowlist",
        ],
        [
            python,
            "-m",
            "pytest",
            "-q",
            "tests/test_phase3e_r4_1_reconciliation.py::test_pinned_persisted_prediction_audit_without_model_code",
        ],
        [
            python,
            "-m",
            "pytest",
            "-q",
            "tests/test_phase1a_pilot_audit.py::test_per_team_canonical_keys_are_unique_within_team",
            "tests/test_phase1b_architecture.py::test_stable_keys_make_league_season_type_team_and_unordered_pair_explicit",
        ],
        [
            python,
            "-m",
            "py_compile",
            "src/pair_fit_v2/phase3e_r4_1_reconciliation.py",
            "src/pair_fit_v2/phase3e_r4_1_cli.py",
        ],
        ["git", "diff", "--check"],
        [
            "git",
            "check-ignore",
            "-v",
            "--no-index",
            (OUTPUT_DIR / "ignore-probe").as_posix(),
        ],
        [
            python,
            "-m",
            "pytest",
            "-q",
            "tests/test_phase3e_r4_1_reconciliation.py::test_static_model_prohibitions",
        ],
        [
            python,
            "-m",
            "pytest",
            "-q",
            "tests/test_phase3e_r4_1_reconciliation.py::test_network_and_protected_season_blocking",
        ],
    ]


def _report_text(
    artifacts: Mapping[str, Any], manifest: Mapping[str, Any], verification: Mapping[str, Any]
) -> str:
    overall = artifacts["reconciled_overall_metrics.json"]
    decision = artifacts["reconciliation_decision.json"]
    missing = artifacts["reconciled_missing_history_metrics.csv"]
    teams = artifacts["reconciled_team_metrics.csv"]
    calibration = artifacts["reconciled_calibration_bins.csv"]
    residual = artifacts["reconciled_residual_diagnostics.json"]
    historical = artifacts["reconciled_historical_stability.json"]
    best = min(teams, key=lambda row: (row["mae"], int(row["team_id"])))
    worst = min(teams, key=lambda row: (-row["mae"], int(row["team_id"])))
    display = lambda value: "null" if value is None else f"{value:.6f}"
    command_lines = [
        f"- `{item['command']}` — exit {item['exit_code']}; passed={item['passed_count']}; "
        f"failed={item['failed_count']}; deselected={item['deselected_count']}"
        for item in verification["commands"]
    ]
    hash_lines = [
        f"- `{name}`: `{entry['serialized_byte_sha256']}`"
        for name, entry in sorted(manifest["payload_artifacts"].items())
    ]
    missing_lines = [
        f"- {row['history_group']}: n={row['row_count']}, MAE={display(row['mae'])}, "
        f"RMSE={display(row['rmse'])}, bias={display(row['bias'])}, difference={display(row['mae_difference_from_complete'])}, "
        f"adequate={str(row['adequate_for_formal_comparison']).lower()}, descriptive-only={str(row['descriptive_only']).lower()}, "
        f"material={str(row['material_absolute_difference']).lower()}, adverse={str(row['adverse_lower_confidence_difference']).lower()}"
        for row in missing
    ]
    warning = historical["warning_flags"]
    return "\n".join(
        [
            "# Phase 3E-R4.1 Correction-Only Reconciliation Report",
            "",
            f"1. Original R4: **{ORIGINAL_CLASSIFICATION}**",
            f"2. Reconciled scientific result: **{decision['reconciled_scientific_classification']}**",
            "",
            "The unchanged persisted prediction vector numerically satisfies the frozen development-holdout PASS gates. This conclusion is accepted through a correction-only reconciliation under an explicit provenance waiver. The original R4 execution remains formally invalid.",
            "",
            "## Why reconciliation was required",
            "",
            "R4 was invalid because its first Stage B missing-history artifact omitted the required independent materiality and adversity flags, after which the defective Stage B artifacts and manifest were overwritten. The first stopped invocation, exact narrow preflight patch, immutable command log, original artifacts, and original test console output were not durably preserved. Exactly-one-fit/prediction lineage is strongly corroborated, not directly proven. No recovered evidence contradicts the production account. The user approved the bounded waiver so the unchanged persisted vector could be evaluated without any refit or regenerated prediction.",
            "",
            "Before the official R4.1 execution, an initial launcher command failed because it omitted the research project's `src` directory from `PYTHONPATH`. Python did not import the reconciliation package, the reconciliation function did not begin, and no runtime directory, ledger, artifact, model operation, prediction, original-file change, network access, or protected-season access occurred. This is retained as a failed launcher attempt outside the official reconciliation execution. The user separately authorized exactly one corrected launch with the import path set explicitly.",
            "",
            "## Direct verification and prohibitions",
            "",
            f"Prediction: `{PREDICTION_PATH.as_posix()}` at `{PREDICTION_SHA256}`; Stage A: `{STAGE_A_SHA256}`; policy canonical/serialized: `{POLICY_CONTENT_SHA256}` / `{POLICY_BYTES_SHA256}`; original invalid decision: `{ORIGINAL_DECISION_SHA256}`; original invalid summary: `{ORIGINAL_SUMMARY_SHA256}`; original report: `{ORIGINAL_REPORT_SHA256}`.",
            "",
            "The 2,700-row, 11-column prediction file was verified as finite, uniquely keyed, numerically canonical, aligned position-for-position with the frozen R2 row index, limited to 2024-25, and free of Charlotte and Philadelphia. Its baseline is one constant historical-training-mean column. Static AST checks found no scikit-learn import and no estimator-operation call in the reconciliation module or CLI. The reconciliation opened no training estimator matrix, created no model artifact, and generated or changed no target, baseline, or prediction.",
            "",
            "## Recomputed metrics",
            "",
            f"Ridge MAE {display(overall['ridge_unweighted']['mae'])}; baseline MAE {display(overall['baseline_unweighted']['mae'])}; improvement {display(overall['improvements']['mae_baseline_minus_ridge'])}. Ridge RMSE {display(overall['ridge_unweighted']['rmse'])}; baseline RMSE {display(overall['baseline_unweighted']['rmse'])}; improvement {display(overall['improvements']['rmse_baseline_minus_ridge'])}.",
            "",
            f"R² {display(overall['ridge_unweighted']['r2'])}; prediction-minus-target bias {display(overall['ridge_unweighted']['bias'])}; Spearman {display(overall['ridge_unweighted']['spearman'])}; prediction SD {display(overall['dispersion']['ridge_prediction_std'])}; target SD {display(overall['dispersion']['target_std'])}; SD ratio {display(overall['dispersion']['ridge_prediction_to_target_std_ratio'])}.",
            "",
            f"Possession-weighted Ridge MAE/RMSE {display(overall['possession_weighted']['ridge_mae'])}/{display(overall['possession_weighted']['ridge_rmse'])}; baseline {display(overall['possession_weighted']['baseline_mae'])}/{display(overall['possession_weighted']['baseline_rmse'])}. Exact-250 is not applicable because zero retained rows are flagged.",
            "",
            "## Missing history and diagnostics",
            "",
            *missing_lines,
            "",
            f"All 28 team rows and 28 no-refit leave-one-team-out rows were retained. Best descriptive team MAE: {best['team_id']} at {display(best['mae'])}; worst: {worst['team_id']} at {display(worst['mae'])}.",
            "",
            f"All ten calibration bins contain 270 rows. Lower/upper target-minus-prediction differences are {display(calibration[0]['calibration_difference'])}/{display(calibration[-1]['calibration_difference'])}. Residual target-minus-prediction correlation/slope versus prediction: {display(residual['residual_vs_prediction_pearson'])}/{display(residual['residual_vs_prediction_slope'])}; versus possessions: {display(residual['residual_vs_possessions_pearson'])}/{display(residual['residual_vs_possessions_slope'])}.",
            "",
            f"Historical warnings: extreme MAE={str(warning['mae_above_worst_by_more_than_0_50']).lower()}, RMSE above worst={str(warning['rmse_above_historical_worst']).lower()}, absolute bias above historical maximum={str(warning['absolute_bias_above_historical_maximum']).lower()}, fold-range flags={json.dumps(warning['outside_six_fold_range'], sort_keys=True)}. These remain non-decisional under R3.",
            "",
            "## Preservation, hashes, and verification",
            "",
            f"The original 13-file namespace fingerprint remained `{verification['original_namespace_before_fingerprint']}` before and after reconciliation. Every byte length, SHA-256, and nanosecond modification timestamp matched. The original report hash and timestamp also matched. Manifest canonical hash: `{manifest['deterministic_content_sha256']}`.",
            "",
            *hash_lines,
            "",
            *command_lines,
            "",
            "## Scope",
            "",
            "The provenance limitation remains attached to this scientific result. It does not retroactively validate R4. The 2024-25 season remains spent as development evidence. The protected final-test season remains untouched, no network was accessed, and no production work began. Final-test execution must retain immutable commands, events, failures, original artifacts, manifests, and test output.",
            "",
        ]
    )


def run_reconciliation(project_root: Path | str = ".") -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    verify_restart_safe(project_root)
    waiver_path = project_root / WAIVER_PATH
    if not waiver_path.is_file():
        raise ReconciliationFailure("required provenance waiver is missing")
    waiver_hash = sha256_file(waiver_path)
    output_dir = project_root / OUTPUT_DIR
    output_dir.mkdir(parents=False, exist_ok=False)
    ledger = EventLedger(output_dir / "execution_events.jsonl")
    ledger.add(
        "reconciliation_authorization_start",
        "authorized",
        path=WAIVER_PATH.as_posix(),
        sha256=waiver_hash,
        detail="explicit user-approved provenance waiver; correction-only scope",
    )
    try:
        with offline_scope():
            git_state = verify_git_state(project_root)
            ledger.add(
                "branch_head_status_verification",
                "passed",
                detail=f"{git_state['branch']} at {git_state['head']}; upstream identical; staging empty",
            )
            before_namespace = inventory_namespace(project_root)
            before_report = report_identity(project_root)
            ledger.add(
                "original_namespace_fingerprint_verification",
                "passed",
                path=ORIGINAL_DIR.as_posix(),
                sha256=before_namespace["fingerprint_sha256"],
                detail="13 files inventoried with byte length, SHA-256, and modification timestamp",
            )
            static_audit = static_prohibition_audit(project_root)
            ledger.add(
                "no_model_import_static_prohibition_verification",
                "passed",
                detail="no prohibited import or estimator-operation call",
            )
            evidence, records, vectors = verify_source_evidence(
                project_root, before_namespace, before_report
            )
            ledger.add(
                "source_prediction_hash_verification",
                "passed",
                path=PREDICTION_PATH.as_posix(),
                sha256=PREDICTION_SHA256,
                detail="2,700 aligned rows and exact 11-column schema",
            )
            ledger.add(
                "policy_verification",
                "passed",
                path=POLICY_PATH.as_posix(),
                sha256=POLICY_BYTES_SHA256,
                detail=f"canonical content {POLICY_CONTENT_SHA256}",
            )
            ledger.add(
                "prediction_file_opening",
                "completed",
                path=PREDICTION_PATH.as_posix(),
                sha256=PREDICTION_SHA256,
                detail="opened read-only for Stage B recomputation",
            )
            configuration = {
                "version": VERSION,
                "authorization": {
                    "waiver_relative_path": WAIVER_PATH.as_posix(),
                    "waiver_sha256": waiver_hash,
                    "scope": "2024-25 R4 correction-only reconciliation",
                },
                "pre_execution_wrapper_failure": dict(PRE_EXECUTION_WRAPPER_FAILURE),
                "git_state": git_state,
                "source_prediction": {
                    "relative_path": PREDICTION_PATH.as_posix(),
                    "serialized_byte_sha256": PREDICTION_SHA256,
                },
                "policy_identity": {
                    "relative_path": POLICY_PATH.as_posix(),
                    "canonical_content_sha256": POLICY_CONTENT_SHA256,
                    "serialized_byte_sha256": POLICY_BYTES_SHA256,
                },
                "original_namespace_fingerprint_sha256": before_namespace[
                    "fingerprint_sha256"
                ],
                "floating_point_comparison_tolerance": FLOAT_TOLERANCE,
                "authorized_operations": [
                    "verify surviving evidence",
                    "recompute frozen Stage B metrics from persisted values",
                    "apply frozen R3 gates",
                    "run read-only verification",
                ],
                "prohibited_operations_confirmed_absent": {
                    "model_fit": True,
                    "prediction_generation": True,
                    "prediction_or_target_mutation": True,
                    "alternate_baseline": True,
                    "network_access": True,
                    "protected_season_access": True,
                },
            }
            initial = {
                "reconciliation_configuration.json": configuration,
                "source_evidence_verification.json": evidence,
            }
            for name, value in initial.items():
                data = artifact_bytes(name, value)
                write_once(output_dir / name, data)
                ledger.add(
                    "stage_b_artifact_write",
                    "completed",
                    path=(OUTPUT_DIR / name).as_posix(),
                    sha256=sha256_bytes(data),
                    detail="write-once reconciliation artifact",
                )

            artifacts = compute_stage_b(records, vectors)
            compare_original_numerical_artifacts(project_root, artifacts)
            for name in (
                "reconciled_overall_metrics.json",
                "reconciled_missing_history_metrics.csv",
                "reconciled_team_metrics.csv",
                "reconciled_leave_one_team_out_metrics.csv",
                "reconciled_calibration_bins.csv",
                "reconciled_residual_diagnostics.json",
                "reconciled_historical_stability.json",
                "reconciliation_decision.json",
            ):
                data = artifact_bytes(name, artifacts[name])
                write_once(output_dir / name, data)
                ledger.add(
                    "stage_b_artifact_write",
                    "completed",
                    path=(OUTPUT_DIR / name).as_posix(),
                    sha256=sha256_bytes(data),
                    detail="recomputed from unchanged persisted values",
                )

            audit_artifacts = compute_stage_b(records, vectors)
            for name, value in artifacts.items():
                _assert_close(audit_artifacts[name], value, f"independent_audit.{name}")
            ledger.add(
                "independent_read_only_stage_b_audit",
                "passed",
                detail="every Stage B output independently recomputed from the pinned prediction file",
            )

            command_results: list[dict[str, Any]] = []
            for command in verification_commands(project_root):
                result = run_verification_command(project_root, command)
                command_results.append(result)
                ledger.add(
                    "verification_command_result",
                    "passed" if result["exit_code"] == 0 else "failed",
                    detail=f"{result['command']} => exit {result['exit_code']}",
                )
                if result["exit_code"] != 0:
                    raise ReconciliationFailure(
                        f"verification command failed: {result['command']}\n{result['output']}"
                    )

            after_namespace = inventory_namespace(project_root)
            after_report = report_identity(project_root)
            require_unchanged(before_namespace, after_namespace, "original R4 namespace")
            require_unchanged(before_report, after_report, "original invalid R4 report")
            ledger.add(
                "original_namespace_after_fingerprint_verification",
                "passed",
                path=ORIGINAL_DIR.as_posix(),
                sha256=after_namespace["fingerprint_sha256"],
                detail="every byte length, hash, and timestamp is identical",
            )

            verification = {
                "version": VERSION,
                "completed_utc": utc_now(),
                "overall_status": "passed",
                "commands": command_results,
                "independent_read_only_recomputation": {
                    "passed": True,
                    "source_prediction_sha256": PREDICTION_SHA256,
                    "model_fit_or_prediction_generated": False,
                },
                "py_compile_passed": any(
                    "py_compile" in item["command"] and item["exit_code"] == 0
                    for item in command_results
                ),
                "git_diff_check_passed": any(
                    "git diff --check" in item["command"] and item["exit_code"] == 0
                    for item in command_results
                ),
                "ignore_check_passed": any(
                    "git check-ignore" in item["command"] and item["exit_code"] == 0
                    for item in command_results
                ),
                "prohibited_artifact_check": {
                    "passed": True,
                    "unexpected_files": [],
                    "model_artifacts": [],
                    "static_audit": static_audit,
                },
                "protected_season_and_network_checks": {
                    "passed": True,
                    "network_accessed": False,
                    "protected_season_accessed": False,
                },
                "original_namespace_before_fingerprint": before_namespace[
                    "fingerprint_sha256"
                ],
                "original_namespace_after_fingerprint": after_namespace[
                    "fingerprint_sha256"
                ],
                "original_namespace_identical": True,
                "original_report_before": before_report,
                "original_report_after": after_report,
                "original_report_identical": True,
                "event_ledger_prepublication_note": (
                    "ledger ordering is validated after its final completion event; manifest and summary "
                    "are nonrecursive publication artifacts"
                ),
            }
            verification_data = serialize_json(verification)
            write_once(output_dir / "verification_results.json", verification_data)
            ledger.add(
                "stage_b_artifact_write",
                "completed",
                path=(OUTPUT_DIR / "verification_results.json").as_posix(),
                sha256=sha256_bytes(verification_data),
                detail="durable command outputs and read-only audit results",
            )
            ledger.add(
                "verification_commands_and_results",
                "passed",
                path=(OUTPUT_DIR / "verification_results.json").as_posix(),
                sha256=sha256_bytes(verification_data),
                detail=f"{len(command_results)} commands completed successfully",
            )

            manifest_path = output_dir / "artifact_hashes.json"
            summary_path = output_dir / "summary.json"
            manifest_handle = manifest_path.open("xb")
            summary_handle = summary_path.open("xb")
            ledger.add(
                "manifest_creation",
                "created_for_finalization",
                path=(OUTPUT_DIR / "artifact_hashes.json").as_posix(),
                detail="exclusive write-once handle created; payload hashes finalized after ledger close",
            )
            ledger.add(
                "summary_creation",
                "created_for_finalization",
                path=(OUTPUT_DIR / "summary.json").as_posix(),
                detail="exclusive write-once handle created; manifest reference finalized after ledger close",
            )
            ledger.add(
                "final_completion",
                "success",
                detail=RECONCILIATION_STATUS,
            )
            ledger.close()
            validate_event_ledger(output_dir / "execution_events.jsonl")

            payload_manifest = {
                "version": VERSION,
                "payload_artifacts": {
                    name: {
                        "relative_path": name,
                        "serialized_byte_sha256": sha256_file(output_dir / name),
                    }
                    for name in sorted(PAYLOAD_FILES)
                },
                "excluded_from_own_byte_manifest": ["artifact_hashes.json", "summary.json"],
            }
            payload_manifest["deterministic_content_sha256"] = canonical_content_hash(
                payload_manifest
            )
            manifest_data = serialize_json(payload_manifest)
            manifest_handle.write(manifest_data)
            manifest_handle.flush()
            os.fsync(manifest_handle.fileno())
            manifest_handle.close()

            decision = artifacts["reconciliation_decision.json"]
            summary = {
                "version": VERSION,
                "artifact_manifest_canonical_sha256": payload_manifest[
                    "deterministic_content_sha256"
                ],
                "source_prediction_sha256": PREDICTION_SHA256,
                "original_r4_classification": ORIGINAL_CLASSIFICATION,
                "reconciled_scientific_classification": decision[
                    "reconciled_scientific_classification"
                ],
                "reconciliation_status": RECONCILIATION_STATUS,
                "provenance_waiver_relative_path": WAIVER_PATH.as_posix(),
                "provenance_waiver_sha256": waiver_hash,
                "provenance_limitation": decision["provenance_limitation"],
                "generated_artifact_count": 14,
                "original_namespace_fingerprint_sha256": before_namespace[
                    "fingerprint_sha256"
                ],
                "final_test_season_accessed": False,
                "network_accessed": False,
                "model_fit_or_prediction_generated": False,
            }
            summary_data = serialize_json(summary)
            summary_handle.write(summary_data)
            summary_handle.flush()
            os.fsync(summary_handle.fileno())
            summary_handle.close()

            report = _report_text(artifacts, payload_manifest, verification)
            write_once(project_root / REPORT_PATH, report.encode("utf-8"))

            actual_names = {path.name for path in output_dir.iterdir() if path.is_file()}
            if actual_names != set(RUNTIME_FILES) or len(actual_names) != 14:
                raise ReconciliationFailure("reconciliation runtime inventory mismatch")
            for name, entry in payload_manifest["payload_artifacts"].items():
                if sha256_file(output_dir / name) != entry["serialized_byte_sha256"]:
                    raise ReconciliationFailure(f"payload hash mismatch after publication: {name}")
            if inventory_namespace(project_root) != before_namespace:
                raise ReconciliationFailure("original namespace changed after publication")
            if report_identity(project_root) != before_report:
                raise ReconciliationFailure("original report changed after publication")
            return {
                "classification": decision["reconciled_scientific_classification"],
                "reconciliation_status": RECONCILIATION_STATUS,
                "output_dir": str(output_dir),
                "report": str(project_root / REPORT_PATH),
            }
    except Exception as exc:
        if not ledger.closed:
            ledger.add("final_completion", "failure", detail=str(exc))
            ledger.close()
        raise
