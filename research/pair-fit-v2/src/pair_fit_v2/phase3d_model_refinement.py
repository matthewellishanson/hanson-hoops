"""Bounded, leakage-safe Pair Fit v2 Phase 3D model refinement.

The runner consumes only the immutable Phase 3B training-era CSVs.  It uses a
predeclared staged design, chronological outer and inner folds, fold-local
preprocessing, and deterministic text artifacts.  It never serializes a fitted
estimator and rejects protected-season path names before opening any input.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from pair_fit_v2 import phase3b_curation as phase3b
from pair_fit_v2 import phase3c_baseline_modeling as phase3c


VERSION = "phase3d.bounded-leakage-safe-refinement.v1"
PHASE3A_CONTENT_SHA256 = "dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f"
PHASE3A1_CONTENT_SHA256 = "54743fee0db29f1847ecb46b2dae8ec07871d3a323e88d6a64fdff735c5d1b47"
POSS_150_SHA256 = "da31ea8e01e9e0f213edee61fb4918e529883ceb77cf77f2c008da03fdf61db8"
POSS_100_SHA256 = "cf01683e4923e34763f9ad7e62b16a7f07c7e1afd993ea26c3501cf67fcb594a"
MANIFEST_SHA256 = "ca137b375fa6613478ed826fa61eadd808d813e81e03311b2f70223e7ee25103"
PHASE3B_SUMMARY_CONTENT_SHA256 = "70650038719f7a4f70505305cb00643f4b96e5753419a45691f594534b2e07b1"
PHASE3C_SUMMARY_CONTENT_SHA256 = "c9cddb3710389183134e039830a6486f9d5981a1c7e867dd1a6a70def3b50ac3"
PHASE3C_SUMMARY_BYTES_SHA256 = "e10e233a435a38d13d66c65bb77a9a325b0f03bee26d77edf87741f173990d55"

ALLOWED_TARGET_SEASONS = phase3c.ALLOWED_TARGET_SEASONS
OUTER_FOLDS = phase3c.OUTER_FOLDS
PROTECTED_SEASONS = ("2024-25", "2025-26")
THRESHOLDS = (150, 100)
WEIGHT_POLICIES = ("equal", "sqrt_possessions", "capped_linear_300")
EXACT_250_POLICIES = ("include", "downweight_0_5", "exclude")
FEATURE_VARIANTS = ("no_shot", "distribution", "distribution_plus_efficiency")
RIDGE_ALPHAS = (0.1, 1.0, 10.0, 100.0, 1000.0, 3000.0, 10000.0)
SMOOTHING_K = (25.0, 50.0, 100.0)
HGB_CONFIG = dict(phase3c.HGB_CONFIG)
ESTIMATORS = ("ridge", "hist_gradient_boosting")
CALIBRATION_BINS = 10
SIMPLICITY_TOLERANCE = 0.10
ADEQUATE_SUBGROUP_ROWS = 100
EXACT_250_TEAM_SEASONS = {
    ("2020-21", "1610612745"): "Houston Rockets",
    ("2023-24", "1610612761"): "Toronto Raptors",
    ("2023-24", "1610612763"): "Memphis Grizzlies",
    ("2023-24", "1610612765"): "Detroit Pistons",
}

ZONE_KEYS = (
    "restricted_area",
    "non_restricted_paint",
    "mid_range",
    "combined_corners",
    "above_the_break_three",
    "backcourt",
    "unclassified_residual",
)
ZONE_INPUTS = {
    "restricted_area": (("restricted_area",),),
    "non_restricted_paint": (("non_restricted_paint",),),
    "mid_range": (("mid_range",),),
    "combined_corners": (("left_corner_three", "right_corner_three"),),
    "above_the_break_three": (("above_the_break_three",),),
    "backcourt": (("backcourt",),),
    "unclassified_residual": (("unclassified",),),
}
EFFICIENCY_FEATURES = tuple(
    feature
    for zone in ZONE_KEYS
    for feature in (
        f"pair_mean.shot_efficiency_{zone}_smoothed_pct",
        f"pair_absolute_difference.shot_efficiency_{zone}_smoothed_pct",
    )
)

PAYLOAD_ARTIFACTS = (
    "experiment_configuration.json",
    "staged_candidate_registry.csv",
    "fold_definitions.json",
    "feature_manifest.json",
    "population_diagnostics.csv",
    "smoothing_prior_diagnostics.csv",
    "weight_diagnostics.csv",
    "tuning_diagnostics.csv",
    "imputation_diagnostics.csv",
    "candidate_metrics.csv",
    "finalist_predictions.csv",
    "subgroup_metrics.csv",
    "calibration_diagnostics.csv",
    "residual_diagnostics.csv",
    "selection_decision.json",
)
EXPECTED_OUTPUT_ARTIFACTS = PAYLOAD_ARTIFACTS + ("artifact_hashes.json", "summary.json")
NONCIRCULAR_EXCLUDED_OUTPUTS = {
    "artifact_hashes.json": "self byte hash excluded; canonical content hash is stored within the artifact",
    "summary.json": "serialized byte hash excluded because summary records the artifact-manifest content hash; canonical content hash is stored within the summary",
}


def canonical_json_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_content_hash(document, field="deterministic_content_sha256"):
    value = dict(document)
    value.pop(field, None)
    return canonical_json_hash(value)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reject_protected_input_paths(*paths):
    """Reject protected-season path names before any caller can open them."""
    for path in paths:
        normalized = str(path).replace("\\", "/").lower()
        if any(season in normalized for season in PROTECTED_SEASONS):
            raise ValueError(f"protected-season input rejected before processing: {path}")


def validate_target_seasons(rows, require_full_window=False):
    return phase3c.validate_target_seasons(rows, require_full_window=require_full_window)


def authorized_outer_folds():
    return phase3c.authorized_outer_folds()


def inner_folds(training_seasons):
    folds = phase3c.inner_folds(training_seasons)
    for validation, training in folds:
        if validation not in training_seasons or any(ALLOWED_TARGET_SEASONS.index(x) >= ALLOWED_TARGET_SEASONS.index(validation) for x in training):
            raise ValueError("nonchronological inner fold")
    return folds


def _phase3b_canonical_content_hash(document):
    """Phase 3B used the historical spaced canonical JSON representation."""
    value = dict(document)
    value.pop("deterministic_content_sha256", None)
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def verify_prerequisites(poss_150_csv, poss_100_csv, manifest_path, phase3b_summary_path, phase3c_summary_path):
    paths = (poss_150_csv, poss_100_csv, manifest_path, phase3b_summary_path, phase3c_summary_path)
    reject_protected_input_paths(*paths)
    byte_expectations = {
        Path(poss_150_csv): POSS_150_SHA256,
        Path(poss_100_csv): POSS_100_SHA256,
        Path(manifest_path): MANIFEST_SHA256,
        Path(phase3c_summary_path): PHASE3C_SUMMARY_BYTES_SHA256,
    }
    for path, expected in byte_expectations.items():
        if sha256_file(path) != expected:
            raise ValueError(f"prerequisite byte hash mismatch: {path.name}")
    phase3b_summary = json.loads(Path(phase3b_summary_path).read_text(encoding="utf-8"))
    phase3c_summary = json.loads(Path(phase3c_summary_path).read_text(encoding="utf-8"))
    if _phase3b_canonical_content_hash(phase3b_summary) != PHASE3B_SUMMARY_CONTENT_SHA256:
        raise ValueError("Phase 3B summary canonical-content hash mismatch")
    if canonical_content_hash(phase3c_summary) != PHASE3C_SUMMARY_CONTENT_SHA256:
        raise ValueError("Phase 3C summary canonical-content hash mismatch")
    prerequisites = phase3b_summary.get("prerequisites", {})
    if prerequisites.get("phase3a_population_audit_sha256") != PHASE3A_CONTENT_SHA256:
        raise ValueError("Phase 3A content hash mismatch")
    if prerequisites.get("phase3a1_shot_profile_replay_sha256") != PHASE3A1_CONTENT_SHA256:
        raise ValueError("Phase 3A.1 content hash mismatch")
    return {
        "phase3a_content_sha256": PHASE3A_CONTENT_SHA256,
        "phase3a1_content_sha256": PHASE3A1_CONTENT_SHA256,
        "phase3b_poss_ge_150_bytes_sha256": POSS_150_SHA256,
        "phase3b_poss_ge_100_bytes_sha256": POSS_100_SHA256,
        "phase3b_feature_manifest_bytes_sha256": MANIFEST_SHA256,
        "phase3b_summary_canonical_content_sha256": PHASE3B_SUMMARY_CONTENT_SHA256,
        "phase3c_summary_canonical_content_sha256": PHASE3C_SUMMARY_CONTENT_SHA256,
        "phase3c_summary_serialized_bytes_sha256": PHASE3C_SUMMARY_BYTES_SHA256,
    }


def _load_csv(path, threshold, expected_rows=None):
    reject_protected_input_paths(path)
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    validate_target_seasons(rows, require_full_window=True)
    if expected_rows is not None and len(rows) != expected_rows:
        raise ValueError(f"unexpected row count for POSS >= {threshold}: {len(rows)}")
    for row in rows:
        possession = phase3c._finite(row.get("pair_possessions"))
        if possession is None or possession < threshold:
            raise ValueError(f"row below declared POSS >= {threshold} population")
        if phase3c._finite(row.get("target_net_rating")) is None:
            raise ValueError("nonfinite target")
    return rows


def load_inputs(poss_150_csv, poss_100_csv, manifest_path, phase3b_summary_path, phase3c_summary_path):
    anchors = verify_prerequisites(poss_150_csv, poss_100_csv, manifest_path, phase3b_summary_path, phase3c_summary_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    phase3b.validate_feature_manifest(manifest)
    rows = {150: _load_csv(poss_150_csv, 150, expected_rows=27001), 100: _load_csv(poss_100_csv, 100)}
    key = lambda row: (row["target_season"], row["team_id"], row["player_1_id"], row["player_2_id"])
    keys_100 = {key(row) for row in rows[100]}
    if not {key(row) for row in rows[150]} <= keys_100:
        raise ValueError("POSS >= 150 is not a subset of POSS >= 100")
    for threshold, population in rows.items():
        flagged = {(row["target_season"], row["team_id"]) for row in population if row["endpoint_exact_250_flag"] == "1"}
        if flagged != set(EXACT_250_TEAM_SEASONS):
            raise ValueError(f"unexpected exact-250 team-season membership for POSS >= {threshold}")
    return rows, manifest, anchors


def feature_lists(manifest=None):
    distribution, no_shot, distribution_only = phase3c.feature_lists(manifest)
    efficiency = tuple(distribution) + EFFICIENCY_FEATURES
    return {
        "no_shot": tuple(no_shot),
        "distribution": tuple(distribution),
        "distribution_plus_efficiency": efficiency,
        "distribution_only": tuple(distribution_only),
        "efficiency_only": EFFICIENCY_FEATURES,
    }


def feature_manifest(manifest=None):
    features = feature_lists(manifest)
    zones = {}
    for zone in ZONE_KEYS:
        components = list(ZONE_INPUTS[zone][0])
        zones[zone] = {
            "fgm_inputs": [f"player_[1|2]_shot_{component}_fgm" for component in components],
            "fga_inputs": [f"player_[1|2]_shot_{component}_fga" for component in components],
            "pair_features": [
                f"pair_mean.shot_efficiency_{zone}_smoothed_pct",
                f"pair_absolute_difference.shot_efficiency_{zone}_smoothed_pct",
            ],
            "unclassified_allocation": "none",
        }
    return {
        "version": VERSION,
        "variants": {name: list(features[name]) for name in FEATURE_VARIANTS},
        "efficiency_formula": "(FGM + k * training_zone_mean) / (FGA + k)",
        "smoothing_grid": list(SMOOTHING_K),
        "training_zone_mean": "sum(FGM)/sum(FGA) across unique valid player-season profiles in the applicable training partition only",
        "undefined_policy": "missing FGM/FGA, zero or negative FGA, or invalid counts remain undefined until fold-local player-slot median imputation",
        "zones": zones,
        "transform_order": [
            "learn priors and slot medians on training player-season profiles",
            "impute player slots",
            "construct symmetric pair means and absolute differences",
            "learn remaining symmetric-feature medians on training pair rows",
            "scale Ridge from training matrix only",
        ],
    }


def _profile_key(row, slot):
    return phase3c._profile_key(row, slot)


def _zone_counts(row, slot, zone):
    components = ZONE_INPUTS[zone][0]
    fgm_values = [phase3c._finite(row.get(f"player_{slot}_shot_{component}_fgm")) for component in components]
    fga_values = [phase3c._finite(row.get(f"player_{slot}_shot_{component}_fga")) for component in components]
    if any(value is None for value in fgm_values):
        return None, None, "missing_fgm"
    if any(value is None for value in fga_values):
        return None, None, "missing_fga"
    fgm, fga = float(sum(fgm_values)), float(sum(fga_values))
    if fga == 0:
        return fgm, fga, "zero_attempts"
    if fga < 0:
        return fgm, fga, "nonpositive_fga"
    if fgm < 0 or fgm > fga:
        return fgm, fga, "invalid_counts"
    return fgm, fga, "defined"


def unique_training_profiles(rows):
    profiles = {}
    for row in rows:
        for slot in ("1", "2"):
            key = _profile_key(row, slot)
            if key is None:
                continue
            values = {zone: _zone_counts(row, slot, zone) for zone in ZONE_KEYS}
            if key in profiles and profiles[key] != values:
                raise ValueError(f"inconsistent shot profile counts: {key}")
            profiles[key] = values
    return profiles


def fit_shot_priors(training_rows):
    profiles = unique_training_profiles(training_rows)
    priors, diagnostics = {}, []
    for zone in ZONE_KEYS:
        valid = [counts for counts in (profile[zone] for profile in profiles.values()) if counts[2] == "defined"]
        total_fgm = float(sum(item[0] for item in valid))
        total_fga = float(sum(item[1] for item in valid))
        if total_fga <= 0:
            raise ValueError(f"no valid training attempts for shot-efficiency prior: {zone}")
        priors[zone] = total_fgm / total_fga
        reasons = Counter(profile[zone][2] for profile in profiles.values())
        diagnostics.append({
            "zone": zone,
            "unique_training_profiles": len(profiles),
            "valid_profiles": len(valid),
            "training_fgm": total_fgm,
            "training_fga": total_fga,
            "training_zone_mean": priors[zone],
            **{f"undefined_{reason}": reasons.get(reason, 0) for reason in ("missing_fgm", "missing_fga", "zero_attempts", "nonpositive_fga", "invalid_counts")},
        })
    return priors, diagnostics, profiles


def smoothed_efficiency(fgm, fga, prior, k):
    if fgm is None or fga is None or not math.isfinite(fgm) or not math.isfinite(fga):
        return None
    if fga <= 0 or fgm < 0 or fgm > fga:
        return None
    return float((fgm + k * prior) / (fga + k))


def fit_efficiency_slot_medians(training_rows, priors, k, profiles=None):
    profiles = profiles or unique_training_profiles(training_rows)
    medians = {}
    for zone in ZONE_KEYS:
        values = [smoothed_efficiency(counts[0], counts[1], priors[zone], k) for counts in (profile[zone] for profile in profiles.values())]
        finite = sorted(value for value in values if value is not None and math.isfinite(value))
        if not finite:
            raise ValueError(f"no finite slot efficiency for {zone}")
        medians[zone] = float(np.median(np.asarray(finite, dtype=float)))
    return medians


def shot_efficiency_slot(row, slot, priors, k, medians):
    values, reasons = {}, {}
    for zone in ZONE_KEYS:
        fgm, fga, reason = _zone_counts(row, slot, zone)
        value = smoothed_efficiency(fgm, fga, priors[zone], k)
        reasons[zone] = reason
        values[zone] = medians[zone] if value is None else value
    return values, reasons


def transform_row(row, base_medians, variant, priors=None, k=None, efficiency_medians=None, manifest=None):
    features = feature_lists(manifest)
    base = phase3c.transform_row(row, base_medians, features["distribution"])
    if variant == "no_shot":
        return {name: base[name] for name in features["no_shot"]}
    if variant == "distribution":
        return base
    if variant != "distribution_plus_efficiency" or priors is None or k is None or efficiency_medians is None:
        raise ValueError("efficiency transform requires fold-local priors, k, and slot medians")
    left, _ = shot_efficiency_slot(row, "1", priors, k, efficiency_medians)
    right, _ = shot_efficiency_slot(row, "2", priors, k, efficiency_medians)
    for zone in ZONE_KEYS:
        base[f"pair_mean.shot_efficiency_{zone}_smoothed_pct"] = (left[zone] + right[zone]) / 2
        base[f"pair_absolute_difference.shot_efficiency_{zone}_smoothed_pct"] = abs(left[zone] - right[zone])
    return {name: base[name] for name in features[variant]}


def shot_l1_undefined_reason(row):
    if row.get("player_1_history_missing") == "1" or row.get("player_2_history_missing") == "1":
        return "missing_player_history"
    overall = [phase3c._finite(row.get(f"player_{slot}_shot_overall_fga")) for slot in ("1", "2")]
    if any(value is None for value in overall):
        return "missing_overall_fga"
    if any(value <= 0 for value in overall):
        return "nonpositive_overall_fga"
    components = ("restricted_area", "non_restricted_paint", "mid_range", "left_corner_three", "right_corner_three", "above_the_break_three", "backcourt", "unclassified")
    if any(phase3c._finite(row.get(f"player_{slot}_shot_{component}_fga")) is None for slot in ("1", "2") for component in components):
        return "missing_zone_component"
    return "defined"


def missing_history_group(row):
    missing = int(row.get("missing_player_count") or 0)
    return {0: "complete_player_history", 1: "one_player_missing", 2: "both_players_missing"}.get(missing, "invalid")


def prepare_matrices(training_rows, validation_rows, variant, k=None, scale=False, manifest=None):
    names = feature_lists(manifest)[variant]
    base_medians, profile_count = phase3c.fit_slot_imputer(training_rows)
    priors = efficiency_medians = None
    prior_diagnostics = []
    if variant == "distribution_plus_efficiency":
        if k not in SMOOTHING_K:
            raise ValueError("smoothing k outside predeclared grid")
        priors, prior_diagnostics, profiles = fit_shot_priors(training_rows)
        efficiency_medians = fit_efficiency_slot_medians(training_rows, priors, k, profiles)
    train_features = [transform_row(row, base_medians, variant, priors, k, efficiency_medians, manifest) for row in training_rows]
    valid_features = [transform_row(row, base_medians, variant, priors, k, efficiency_medians, manifest) for row in validation_rows]
    train_x = np.asarray([[np.nan if item[name] is None else item[name] for name in names] for item in train_features], dtype=float)
    valid_x = np.asarray([[np.nan if item[name] is None else item[name] for name in names] for item in valid_features], dtype=float)
    second_stage_train = ~np.isfinite(train_x).all(axis=1)
    second_stage_valid = ~np.isfinite(valid_x).all(axis=1)
    symmetric_medians = {}
    for index, name in enumerate(names):
        finite = train_x[np.isfinite(train_x[:, index]), index]
        if not len(finite):
            raise ValueError(f"no finite training value for symmetric feature: {name}")
        median = float(np.median(finite))
        symmetric_medians[name] = median
        train_x[~np.isfinite(train_x[:, index]), index] = median
        valid_x[~np.isfinite(valid_x[:, index]), index] = median
    scaler = None
    if scale:
        scaler = StandardScaler()
        train_x = scaler.fit_transform(train_x)
        valid_x = scaler.transform(valid_x)
    return {
        "train_x": train_x,
        "validation_x": valid_x,
        "feature_names": names,
        "base_slot_medians": base_medians,
        "efficiency_slot_medians": efficiency_medians or {},
        "symmetric_feature_medians": symmetric_medians,
        "unique_training_profiles": profile_count,
        "shot_priors": priors or {},
        "prior_diagnostics": prior_diagnostics,
        "second_stage_train": second_stage_train,
        "second_stage_validation": second_stage_valid,
        "scaler": scaler,
    }


def raw_training_weights(rows, policy):
    possessions = np.asarray([float(row["pair_possessions"]) for row in rows], dtype=float)
    if policy == "equal":
        return np.ones(len(rows), dtype=float)
    if policy == "sqrt_possessions":
        return np.sqrt(possessions)
    if policy == "capped_linear_300":
        return np.minimum(possessions, 300.0)
    raise ValueError(f"unknown weight policy: {policy}")


def apply_exact_250_training_policy(rows, policy):
    if policy not in EXACT_250_POLICIES:
        raise ValueError(f"unknown exact-250 policy: {policy}")
    if policy == "exclude":
        return [row for row in rows if row["endpoint_exact_250_flag"] != "1"], None
    multipliers = np.asarray([0.5 if policy == "downweight_0_5" and row["endpoint_exact_250_flag"] == "1" else 1.0 for row in rows], dtype=float)
    return list(rows), multipliers


def normalized_training_weights(rows, weight_policy, exact_policy="include"):
    selected, multipliers = apply_exact_250_training_policy(rows, exact_policy)
    if not selected:
        raise ValueError("exact-250 policy removed the full training partition")
    weights = raw_training_weights(selected, weight_policy)
    if multipliers is not None:
        weights *= multipliers
    mean = float(np.mean(weights))
    if not math.isfinite(mean) or mean <= 0:
        raise ValueError("invalid training weights")
    weights /= mean
    return selected, weights


def weight_diagnostic_rows(rows, weights, candidate_id, partition, outer_fold):
    weights = np.asarray(weights, dtype=float)
    total = float(weights.sum())
    top_count = max(1, int(math.ceil(len(weights) * 0.10)))
    output = [{
        "candidate_id": candidate_id,
        "partition": partition,
        "outer_fold": outer_fold,
        "scope": "overall",
        "group": "all",
        "rows": len(rows),
        "weight_min": float(weights.min()),
        "weight_median": float(np.median(weights)),
        "weight_max": float(weights.max()),
        "weight_sum": total,
        "effective_sample_size": float(total ** 2 / np.sum(weights ** 2)),
        "top_decile_weight_share": float(np.sort(weights)[-top_count:].sum() / total),
        "weight_share": 1.0,
    }]
    for scope, key_fn in (
        ("season_concentration", lambda row: row["target_season"]),
        ("team_season_concentration", lambda row: f"{row['target_season']}|{row['team_id']}"),
    ):
        groups = defaultdict(list)
        for row, weight in zip(rows, weights):
            groups[key_fn(row)].append(float(weight))
        for group, values in sorted(groups.items()):
            output.append({
                "candidate_id": candidate_id,
                "partition": partition,
                "outer_fold": outer_fold,
                "scope": scope,
                "group": group,
                "rows": len(values),
                "weight_min": min(values),
                "weight_median": float(np.median(values)),
                "weight_max": max(values),
                "weight_sum": float(sum(values)),
                "effective_sample_size": float(sum(values) ** 2 / sum(value ** 2 for value in values)),
                "top_decile_weight_share": None,
                "weight_share": float(sum(values) / total),
            })
    return output


def metric_values(actual, prediction):
    return phase3c.metric_values(actual, prediction)


def _targets(rows):
    return np.asarray([float(row["target_net_rating"]) for row in rows], dtype=float)


def _fit_predict(estimator, train_x, train_y, valid_x, weights, alpha=None):
    if estimator not in ESTIMATORS:
        raise ValueError(f"estimator not allowlisted: {estimator}")
    if estimator == "ridge":
        if alpha not in RIDGE_ALPHAS:
            raise ValueError("Ridge alpha outside predeclared grid")
        model = Ridge(alpha=alpha).fit(train_x, train_y, sample_weight=weights)
    else:
        model = HistGradientBoostingRegressor(**HGB_CONFIG).fit(train_x, train_y, sample_weight=weights)
    prediction = model.predict(valid_x)
    if not np.isfinite(prediction).all():
        raise ValueError("nonfinite prediction")
    return prediction


def _inner_partition(rows, validation_season, training_seasons, weight_policy, exact_policy):
    train = [row for row in rows if row["target_season"] in training_seasons]
    valid = [row for row in rows if row["target_season"] == validation_season]
    train, weights = normalized_training_weights(train, weight_policy, exact_policy)
    if not train or not valid:
        raise ValueError("empty chronological inner partition")
    return train, valid, weights


def select_ridge_alpha(rows, training_seasons, variant, weight_policy, exact_policy="include", k=None, manifest=None):
    prepared = []
    for validation, train_seasons in inner_folds(training_seasons):
        train, valid, weights = _inner_partition(rows, validation, train_seasons, weight_policy, exact_policy)
        matrices = prepare_matrices(train, valid, variant, k=k, scale=True, manifest=manifest)
        prepared.append((validation, train, valid, weights, matrices))
    results = []
    for alpha in RIDGE_ALPHAS:
        fold_maes = []
        for validation, train, valid, weights, matrices in prepared:
            prediction = _fit_predict("ridge", matrices["train_x"], _targets(train), matrices["validation_x"], weights, alpha=alpha)
            fold_maes.append(metric_values(_targets(valid), prediction)["mae"])
        results.append({"alpha": alpha, "inner_fold_count": len(fold_maes), "mean_inner_mae": float(np.mean(fold_maes)), "inner_maes": fold_maes})
    selected = min(results, key=lambda item: (item["mean_inner_mae"], item["alpha"]))
    return selected, results


def select_smoothing_parameters(estimator, rows, training_seasons, weight_policy, exact_policy="include", manifest=None):
    if estimator not in ESTIMATORS:
        raise ValueError(f"estimator not allowlisted: {estimator}")
    results = []
    for k in SMOOTHING_K:
        prepared = []
        for validation, train_seasons in inner_folds(training_seasons):
            train, valid, weights = _inner_partition(rows, validation, train_seasons, weight_policy, exact_policy)
            matrices = prepare_matrices(train, valid, "distribution_plus_efficiency", k=k, scale=estimator == "ridge", manifest=manifest)
            prepared.append((train, valid, weights, matrices))
        alphas = RIDGE_ALPHAS if estimator == "ridge" else (None,)
        for alpha in alphas:
            maes = []
            for train, valid, weights, matrices in prepared:
                prediction = _fit_predict(estimator, matrices["train_x"], _targets(train), matrices["validation_x"], weights, alpha=alpha)
                maes.append(metric_values(_targets(valid), prediction)["mae"])
            results.append({"k": k, "alpha": alpha, "inner_fold_count": len(maes), "mean_inner_mae": float(np.mean(maes)), "inner_maes": maes})
    selected = min(results, key=lambda item: (item["mean_inner_mae"], -item["k"], math.inf if item["alpha"] is None else item["alpha"]))
    return selected, results


def select_by_primary_mae(candidates, simplicity_key, tolerance=SIMPLICITY_TOLERANCE):
    if not candidates:
        raise ValueError("no candidates supplied")
    best_mae = min(float(item["macro_season_mae"]) for item in candidates)
    eligible = []
    for item in candidates:
        difference = float(item["macro_season_mae"]) - best_mae
        if difference < tolerance and not math.isclose(difference, tolerance, rel_tol=0.0, abs_tol=1e-12):
            eligible.append(item)
    return min(eligible, key=lambda item: (simplicity_key(item), float(item["macro_season_mae"]), item["candidate_id"]))


def _candidate_id(stage, estimator, threshold, weight_policy, feature_variant, exact_policy):
    return f"{stage}__{estimator}__poss{threshold}__{weight_policy}__{feature_variant}__{exact_policy}"


def _diagnostic_record(row, prediction, candidate_id, fold, second_stage):
    l1_reason = shot_l1_undefined_reason(row)
    efficiency_reasons = {
        f"player_{slot}_{zone}": _zone_counts(row, slot, zone)[2]
        for slot in ("1", "2")
        for zone in ZONE_KEYS
        if _zone_counts(row, slot, zone)[2] != "defined"
    }
    return {
        "candidate_id": candidate_id,
        "outer_fold": fold,
        "target_season": row["target_season"],
        "team_id": row["team_id"],
        "player_1_id": row["player_1_id"],
        "player_2_id": row["player_2_id"],
        "actual_target": float(row["target_net_rating"]),
        "prediction": float(prediction),
        "pair_possessions": float(row["pair_possessions"]),
        "missing_history_group": missing_history_group(row),
        "second_stage_symmetric_imputation_required": int(bool(second_stage)),
        "shot_l1_undefined_reason": l1_reason,
        "shot_l1_undefined_missing_or_nonpositive_overall_fga": int(l1_reason in {"missing_overall_fga", "nonpositive_overall_fga"}),
        "shot_efficiency_any_undefined_before_slot_imputation": int(bool(efficiency_reasons)),
        "shot_efficiency_undefined_reasons": efficiency_reasons,
        "exact_250_membership": int(row["endpoint_exact_250_flag"] == "1"),
        "pandemic_affected": int(row["pandemic_affected_season_flag"] == "1"),
    }


def _summarize_candidate(candidate, predictions, train_counts, validation_counts):
    by_season = defaultdict(list)
    for row in predictions:
        by_season[row["outer_fold"]].append(row)
    season_metrics = []
    for season, members in sorted(by_season.items()):
        values = metric_values([row["actual_target"] for row in members], [row["prediction"] for row in members])
        season_metrics.append({"candidate_id": candidate["candidate_id"], "stage": candidate["stage"], "scope": "validation_season", "season": season,
                               "training_rows": train_counts[season], "training_seasons": len(dict(OUTER_FOLDS)[season]),
                               "training_team_seasons": candidate["training_team_seasons"][season], "validation_team_seasons": candidate["validation_team_seasons"][season], **values})
    pooled = metric_values([row["actual_target"] for row in predictions], [row["prediction"] for row in predictions])
    macro_mae = float(np.mean([row["mae"] for row in season_metrics]))
    macro_rmse = float(np.mean([row["rmse"] for row in season_metrics]))
    macro_r2 = float(np.mean([row["r2"] for row in season_metrics if row["r2"] is not None]))
    macro_bias = float(np.mean([row["mean_signed_error_bias"] for row in season_metrics]))
    macro_spearman = float(np.mean([row["spearman_rank_correlation"] for row in season_metrics if row["spearman_rank_correlation"] is not None]))
    macro_prediction_std = float(np.mean([row["prediction_std"] for row in season_metrics]))
    macro_target_std = float(np.mean([row["target_std"] for row in season_metrics]))
    worst = float(max(row["mae"] for row in season_metrics))
    summary = {
        **candidate,
        "macro_season_mae": macro_mae,
        "pooled_mae": pooled["mae"],
        "macro_season_rmse": macro_rmse,
        "macro_season_r2": macro_r2,
        "macro_season_bias": macro_bias,
        "macro_season_spearman": macro_spearman,
        "macro_prediction_std": macro_prediction_std,
        "macro_target_std": macro_target_std,
        "pooled_rmse": pooled["rmse"],
        "pooled_r2": pooled["r2"],
        "pooled_bias": pooled["mean_signed_error_bias"],
        "pooled_spearman": pooled["spearman_rank_correlation"],
        "prediction_std": pooled["prediction_std"],
        "target_std": pooled["target_std"],
        "worst_season_mae": worst,
        "validation_rows": len(predictions),
        "validation_seasons_won": 0,
    }
    aggregate = {"candidate_id": candidate["candidate_id"], "stage": candidate["stage"], "scope": "pooled", "season": "all_outer",
                 "training_rows": "", "training_seasons": "", "training_team_seasons": "", "validation_team_seasons": "", **pooled,
                 "macro_season_mae": macro_mae, "macro_season_rmse": macro_rmse, "worst_season_mae": worst}
    macro = {"candidate_id": candidate["candidate_id"], "stage": candidate["stage"], "scope": "macro_season", "season": "all_outer",
             "training_rows": "", "training_seasons": "", "training_team_seasons": "", "validation_team_seasons": "",
             "validation_rows": len(predictions), "mae": macro_mae, "rmse": macro_rmse, "r2": macro_r2,
             "mean_signed_error_bias": macro_bias, "spearman_rank_correlation": macro_spearman,
             "prediction_mean": float(np.mean([row["prediction_mean"] for row in season_metrics])),
             "target_mean": float(np.mean([row["target_mean"] for row in season_metrics])),
             "prediction_std": macro_prediction_std, "target_std": macro_target_std,
             "macro_season_mae": macro_mae, "macro_season_rmse": macro_rmse, "worst_season_mae": worst}
    return summary, season_metrics + [aggregate, macro]


def evaluate_candidate(stage, estimator, threshold, weight_policy, feature_variant, exact_policy, rows, manifest=None, reused_fold_parameters=None):
    if estimator not in ESTIMATORS or threshold not in THRESHOLDS or weight_policy not in WEIGHT_POLICIES or feature_variant not in FEATURE_VARIANTS or exact_policy not in EXACT_250_POLICIES:
        raise ValueError("candidate outside predeclared design")
    candidate_id = _candidate_id(stage, estimator, threshold, weight_policy, feature_variant, exact_policy)
    predictions, tuning, weights_out, priors_out, imputations = [], [], [], [], []
    fold_parameters, train_counts, validation_counts = {}, {}, {}
    training_team_seasons, validation_team_seasons = {}, {}
    for validation_season, training_seasons in authorized_outer_folds():
        raw_train = [row for row in rows if row["target_season"] in training_seasons]
        valid = [row for row in rows if row["target_season"] == validation_season]
        train, weights = normalized_training_weights(raw_train, weight_policy, exact_policy)
        train_counts[validation_season], validation_counts[validation_season] = len(train), len(valid)
        training_team_seasons[validation_season] = len({(row["target_season"], row["team_id"]) for row in train})
        validation_team_seasons[validation_season] = len({(row["target_season"], row["team_id"]) for row in valid})
        alpha = k = None
        if reused_fold_parameters is not None:
            parameters = reused_fold_parameters[validation_season]
            alpha, k = parameters.get("alpha"), parameters.get("k")
        elif feature_variant == "distribution_plus_efficiency":
            selected, tried = select_smoothing_parameters(estimator, raw_train, training_seasons, weight_policy, exact_policy, manifest)
            alpha, k = selected.get("alpha"), selected["k"]
            tuning.extend({"candidate_id": candidate_id, "outer_fold": validation_season, "tuning_type": "joint_smoothing_and_alpha" if estimator == "ridge" else "smoothing_k",
                           "selected": int(item == selected), **item} for item in tried)
        elif estimator == "ridge":
            tuning_variant = "distribution" if feature_variant == "no_shot" else feature_variant
            selected, tried = select_ridge_alpha(raw_train, training_seasons, tuning_variant, weight_policy, exact_policy, manifest=manifest)
            alpha = selected["alpha"]
            tuning.extend({"candidate_id": candidate_id, "outer_fold": validation_season, "tuning_type": "ridge_alpha_reused_from_distribution" if feature_variant == "no_shot" else "ridge_alpha",
                           "selected": int(item == selected), **item} for item in tried)
        fold_parameters[validation_season] = {"alpha": alpha, "k": k}
        matrices = prepare_matrices(train, valid, feature_variant, k=k, scale=estimator == "ridge", manifest=manifest)
        predicted = _fit_predict(estimator, matrices["train_x"], _targets(train), matrices["validation_x"], weights, alpha=alpha)
        predictions.extend(_diagnostic_record(row, value, candidate_id, validation_season, needed) for row, value, needed in zip(valid, predicted, matrices["second_stage_validation"]))
        weights_out.extend(weight_diagnostic_rows(train, weights, candidate_id, "outer_training", validation_season))
        for diagnostic in matrices["prior_diagnostics"]:
            priors_out.append({"candidate_id": candidate_id, "outer_fold": validation_season, "partition": "outer_training", "k": k, **diagnostic})
        for name, median in sorted(matrices["base_slot_medians"].items()):
            imputations.append({"candidate_id": candidate_id, "outer_fold": validation_season, "stage": "player_slot", "feature": name, "median": median,
                                "unique_training_profiles": matrices["unique_training_profiles"], "training_rows": len(train), "validation_rows": len(valid)})
        for name, median in sorted(matrices["efficiency_slot_medians"].items()):
            imputations.append({"candidate_id": candidate_id, "outer_fold": validation_season, "stage": "efficiency_player_slot", "feature": name, "median": median,
                                "unique_training_profiles": matrices["unique_training_profiles"], "training_rows": len(train), "validation_rows": len(valid)})
        for name, median in sorted(matrices["symmetric_feature_medians"].items()):
            imputations.append({"candidate_id": candidate_id, "outer_fold": validation_season, "stage": "symmetric_feature", "feature": name, "median": median,
                                "unique_training_profiles": matrices["unique_training_profiles"], "training_rows": len(train), "validation_rows": len(valid)})
    predictions.sort(key=lambda row: (row["candidate_id"], row["outer_fold"], int(row["team_id"]), int(row["player_1_id"]), int(row["player_2_id"])))
    candidate = {"candidate_id": candidate_id, "stage": stage, "estimator": estimator, "threshold": threshold, "weight_policy": weight_policy,
                 "feature_variant": feature_variant, "exact_250_policy": exact_policy, "fold_parameters": fold_parameters,
                 "training_team_seasons": training_team_seasons, "validation_team_seasons": validation_team_seasons}
    summary, metrics = _summarize_candidate(candidate, predictions, train_counts, validation_counts)
    summary.pop("training_team_seasons")
    summary.pop("validation_team_seasons")
    return {"summary": summary, "metrics": metrics, "predictions": predictions, "fold_parameters": fold_parameters,
            "tuning": tuning, "weights": weights_out, "priors": priors_out, "imputations": imputations}


def _assign_season_wins(results):
    grouped = defaultdict(list)
    for result in results:
        for metric in result["metrics"]:
            if metric["scope"] == "validation_season":
                grouped[metric["season"]].append((metric["mae"], result["summary"]["candidate_id"]))
    wins = Counter()
    for values in grouped.values():
        best = min(value[0] for value in values)
        for mae, candidate_id in values:
            if mae == best:
                wins[candidate_id] += 1
    for result in results:
        result["summary"]["validation_seasons_won"] = wins[result["summary"]["candidate_id"]]


def subgroup_metrics(predictions):
    groups = defaultdict(list)
    for row in predictions:
        dimensions = (
            ("missing_history", row["missing_history_group"]),
            ("exact_250", "exact_250" if row["exact_250_membership"] else "not_exact_250"),
            ("pandemic", "pandemic" if row["pandemic_affected"] else "non_pandemic"),
            ("second_stage_imputation", "required" if row["second_stage_symmetric_imputation_required"] else "not_required"),
            ("shot_l1_status", row["shot_l1_undefined_reason"]),
            ("threshold_population", "poss_ge_150_common" if row["pair_possessions"] >= 150 else "poss_100_to_149_incremental"),
        )
        for dimension, group in dimensions:
            groups[(row["candidate_id"], dimension, group)].append(row)
    output = []
    for (candidate_id, dimension, group), members in sorted(groups.items()):
        output.append({"candidate_id": candidate_id, "dimension": dimension, "group": group,
                       **metric_values([row["actual_target"] for row in members], [row["prediction"] for row in members])})
    return output


def calibration_diagnostics(predictions, bins=CALIBRATION_BINS):
    groups = defaultdict(list)
    for row in predictions:
        groups[(row["candidate_id"], row["outer_fold"])].append(row)
    output = []
    for (candidate_id, season), members in sorted(groups.items()):
        ordered = sorted(members, key=lambda row: (row["prediction"], int(row["team_id"]), int(row["player_1_id"]), int(row["player_2_id"])))
        used_bins = min(bins, len(ordered))
        assigned = defaultdict(list)
        for index, row in enumerate(ordered):
            assigned[1 + index * used_bins // len(ordered)].append(row)
        for bin_number in range(1, used_bins + 1):
            group = assigned[bin_number]
            predicted = float(np.mean([row["prediction"] for row in group]))
            observed = float(np.mean([row["actual_target"] for row in group]))
            output.append({"candidate_id": candidate_id, "outer_fold": season, "bin": bin_number, "used_bins": used_bins, "rows": len(group),
                           "prediction_mean": predicted, "target_mean": observed, "observed_minus_predicted": observed - predicted,
                           "tail": "lower" if bin_number == 1 else "upper" if bin_number == used_bins else "middle"})
    return output


def residual_diagnostics(predictions):
    groups = defaultdict(list)
    for row in predictions:
        groups[(row["candidate_id"], "all_outer")].append(row)
        groups[(row["candidate_id"], row["outer_fold"])].append(row)
    output = []
    for (candidate_id, season), members in sorted(groups.items()):
        residual = np.asarray([row["actual_target"] - row["prediction"] for row in members], dtype=float)
        prediction = np.asarray([row["prediction"] for row in members], dtype=float)
        possession = np.asarray([row["pair_possessions"] for row in members], dtype=float)
        pred_corr = None if np.std(prediction) == 0 else float(np.corrcoef(residual, prediction)[0, 1])
        poss_corr = None if np.std(possession) == 0 else float(np.corrcoef(residual, possession)[0, 1])
        pred_slope = None if np.var(prediction) == 0 else float(np.cov(prediction, residual, ddof=0)[0, 1] / np.var(prediction))
        poss_slope = None if np.var(possession) == 0 else float(np.cov(possession, residual, ddof=0)[0, 1] / np.var(possession))
        output.append({"candidate_id": candidate_id, "season": season, "rows": len(members), "residual_mean": float(residual.mean()),
                       "residual_vs_prediction_pearson": pred_corr, "residual_vs_prediction_slope": pred_slope,
                       "residual_vs_possessions_pearson": poss_corr, "residual_vs_possessions_slope": poss_slope})
    return output


def ridge_vs_hgb_decision(ridge_summary, hgb_summary, ridge_predictions, hgb_predictions, subgroup_rows):
    grouped_ridge, grouped_hgb = defaultdict(list), defaultdict(list)
    for row in ridge_predictions:
        grouped_ridge[row["outer_fold"]].append(row)
    for row in hgb_predictions:
        grouped_hgb[row["outer_fold"]].append(row)
    hgb_wins = sum(
        metric_values([row["actual_target"] for row in grouped_hgb[season]], [row["prediction"] for row in grouped_hgb[season]])["mae"]
        < metric_values([row["actual_target"] for row in grouped_ridge[season]], [row["prediction"] for row in grouped_ridge[season]])["mae"]
        for season in sorted(grouped_ridge)
    )
    subgroup = defaultdict(dict)
    for row in subgroup_rows:
        if row["dimension"] == "missing_history":
            subgroup[row["candidate_id"]][row["group"]] = row
    major_worsening = []
    for group, ridge_metric in subgroup[ridge_summary["candidate_id"]].items():
        hgb_metric = subgroup[hgb_summary["candidate_id"]].get(group)
        if hgb_metric and min(ridge_metric["validation_rows"], hgb_metric["validation_rows"]) >= ADEQUATE_SUBGROUP_ROWS and hgb_metric["mae"] - ridge_metric["mae"] > 0.25:
            major_worsening.append({"group": group, "hgb_minus_ridge_mae": hgb_metric["mae"] - ridge_metric["mae"]})
    def slice_mae(predictions, predicate):
        selected = [row for row in predictions if predicate(row)]
        return metric_values([row["actual_target"] for row in selected], [row["prediction"] for row in selected])["mae"]
    non_exact_advantage = slice_mae(ridge_predictions, lambda row: not row["exact_250_membership"]) - slice_mae(hgb_predictions, lambda row: not row["exact_250_membership"])
    non_pandemic_advantage = slice_mae(ridge_predictions, lambda row: not row["pandemic_affected"]) - slice_mae(hgb_predictions, lambda row: not row["pandemic_affected"])
    conditions = {
        "macro_mae_improvement_at_least_0_10": ridge_summary["macro_season_mae"] - hgb_summary["macro_season_mae"] >= 0.10,
        "hgb_wins_at_least_four_seasons": hgb_wins >= 4,
        "pooled_rmse_does_not_worsen": hgb_summary["pooled_rmse"] <= ridge_summary["pooled_rmse"],
        "no_adequate_missing_history_group_worsens_over_0_25": not major_worsening,
        "advantage_not_solely_exact_250_or_pandemic": non_exact_advantage > 0 and non_pandemic_advantage > 0,
    }
    choose_hgb = all(conditions.values())
    return {
        "selected_estimator": "hist_gradient_boosting" if choose_hgb else "ridge",
        "rule_result": "all HGB conditions passed" if choose_hgb else "retain Ridge because one or more HGB conditions failed",
        "conditions": conditions,
        "macro_mae_hgb_improvement": ridge_summary["macro_season_mae"] - hgb_summary["macro_season_mae"],
        "hgb_validation_seasons_won": hgb_wins,
        "major_missing_history_worsening": major_worsening,
        "non_exact_250_mae_improvement": non_exact_advantage,
        "non_pandemic_mae_improvement": non_pandemic_advantage,
    }


def calibration_recommendation(finalist_predictions, finalist_summaries, calibration_rows):
    details = {}
    recommend = False
    for summary in finalist_summaries:
        candidate_id = summary["candidate_id"]
        ratios, upper, lower = [], [], []
        for season in (fold[0] for fold in OUTER_FOLDS):
            rows = [row for row in finalist_predictions if row["candidate_id"] == candidate_id and row["outer_fold"] == season]
            metrics = metric_values([row["actual_target"] for row in rows], [row["prediction"] for row in rows])
            ratios.append(metrics["prediction_std"] / metrics["target_std"])
            bins = [row for row in calibration_rows if row["candidate_id"] == candidate_id and row["outer_fold"] == season]
            lower.append(next(row["observed_minus_predicted"] for row in bins if row["tail"] == "lower"))
            upper.append(next(row["observed_minus_predicted"] for row in bins if row["tail"] == "upper"))
        stable_compression = sum(ratio < 0.75 for ratio in ratios) >= 5
        stable_tail_direction = (all(value > 0 for value in upper) or all(value < 0 for value in upper)) and (all(value > 0 for value in lower) or all(value < 0 for value in lower))
        details[candidate_id] = {"season_prediction_to_target_std_ratios": ratios, "lower_tail_observed_minus_predicted": lower,
                                 "upper_tail_observed_minus_predicted": upper, "stable_dispersion_compression": stable_compression,
                                 "stable_tail_direction": stable_tail_direction}
        recommend = recommend or (stable_compression and stable_tail_direction)
    return {"fit_calibrator_in_phase3d": False, "recommend_later_calibration_study": recommend,
            "rule": "recommend later study only when at least five seasons have prediction/target SD below 0.75 and both tail directions are consistent across all six seasons",
            "details": details}


def confidence_labels(subgroups, selected_candidate_id):
    rows = {row["group"]: row for row in subgroups if row["candidate_id"] == selected_candidate_id and row["dimension"] == "missing_history"}
    complete = rows.get("complete_player_history")
    if not complete:
        return {"recommended": False, "labels": {}, "reason": "complete-history reference unavailable"}
    labels = {"complete_player_history": "standard"}
    evidence = {}
    for group in ("one_player_missing", "both_players_missing"):
        row = rows.get(group)
        if not row:
            continue
        delta = row["mae"] - complete["mae"]
        adequate = row["validation_rows"] >= ADEQUATE_SUBGROUP_ROWS
        evidence[group] = {"rows": row["validation_rows"], "mae": row["mae"], "mae_delta_vs_complete": delta, "adequate_sample": adequate}
        labels[group] = "lower" if adequate and delta >= 0.50 else "standard"
    recommended = any(label == "lower" for label in labels.values())
    return {"recommended": recommended, "labels": labels, "evidence": evidence,
            "rule": "lower confidence only for groups with at least 100 rows and MAE at least 0.50 above complete history"}


def population_diagnostics(rows_by_threshold):
    output = []
    for threshold, rows in sorted(rows_by_threshold.items(), reverse=True):
        for validation, training in authorized_outer_folds():
            train = [row for row in rows if row["target_season"] in training]
            valid = [row for row in rows if row["target_season"] == validation]
            output.append({"threshold": threshold, "outer_fold": validation, "training_rows": len(train), "validation_rows": len(valid),
                           "training_seasons": len(set(row["target_season"] for row in train)), "validation_seasons": len(set(row["target_season"] for row in valid)),
                           "training_team_seasons": len({(row["target_season"], row["team_id"]) for row in train}),
                           "validation_team_seasons": len({(row["target_season"], row["team_id"]) for row in valid})})
    return output


def staged_candidate_plan():
    plan = []
    for estimator in ESTIMATORS:
        for threshold in THRESHOLDS:
            for weight in WEIGHT_POLICIES:
                plan.append({"stage": "A", "estimator": estimator, "threshold": threshold, "weight_policy": weight,
                             "feature_variant": "distribution", "exact_250_policy": "include", "status": "predeclared"})
    for estimator in ESTIMATORS:
        for feature_variant in FEATURE_VARIANTS:
            plan.append({"stage": "B", "estimator": estimator, "threshold": "selected_in_A", "weight_policy": "selected_in_A",
                         "feature_variant": feature_variant, "exact_250_policy": "include", "status": "conditional_predeclared"})
    for estimator in ESTIMATORS:
        for exact_policy in EXACT_250_POLICIES:
            plan.append({"stage": "C", "estimator": estimator, "threshold": "selected_in_A", "weight_policy": "selected_in_A",
                         "feature_variant": "selected_in_B", "exact_250_policy": exact_policy, "status": "conditional_predeclared"})
    return plan


def _write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else json.dumps(row[field], sort_keys=True, separators=(",", ":")) if isinstance(row.get(field), (dict, list)) else row.get(field) for field in fields})


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def validate_artifact_manifest_scope(manifest):
    covered = set((manifest.get("artifacts") or {}).keys())
    excluded = set(NONCIRCULAR_EXCLUDED_OUTPUTS)
    if covered != set(PAYLOAD_ARTIFACTS) or covered | excluded != set(EXPECTED_OUTPUT_ARTIFACTS):
        raise ValueError("Phase 3D output omitted from non-circular hash policy")
    return {"covered_byte_artifacts": len(covered), "explicitly_excluded_outputs": dict(NONCIRCULAR_EXCLUDED_OUTPUTS)}


def _config(anchors, manifest):
    return {
        "version": VERSION,
        "network": "prohibited",
        "authorized_target_seasons": list(ALLOWED_TARGET_SEASONS),
        "protected_target_seasons": list(PROTECTED_SEASONS),
        "target": "full-season pair NET_RATING",
        "primary_metrics_unweighted": True,
        "thresholds": list(THRESHOLDS),
        "weight_policies": {
            "equal": "w=1",
            "sqrt_possessions": "w=sqrt(POSS)",
            "capped_linear_300": "w=min(POSS,300)",
            "normalization": "mean 1 within each training partition after the exact-250 multiplier/exclusion; validation possessions are unused",
        },
        "feature_variants": list(FEATURE_VARIANTS),
        "ridge_alpha_grid": list(RIDGE_ALPHAS),
        "ridge_alpha_tie_break": "smaller alpha on exact mean-inner-MAE tie, preserving Phase 3C",
        "smoothing_k_grid": list(SMOOTHING_K),
        "smoothing_k_tie_break": "larger k on exact mean-inner-MAE tie",
        "hgb_configuration": HGB_CONFIG,
        "estimator_allowlist": list(ESTIMATORS),
        "exact_250_policies": list(EXACT_250_POLICIES),
        "exact_250_team_seasons": {f"{season}|{team_id}": name for (season, team_id), name in sorted(EXACT_250_TEAM_SEASONS.items())},
        "selection": {
            "primary": "macro validation-season MAE",
            "simplicity_indifference_band": "strictly less than 0.10 net-rating points",
            "threshold_simplicity": list(THRESHOLDS),
            "weight_simplicity": list(WEIGHT_POLICIES),
            "feature_simplicity": list(FEATURE_VARIANTS),
            "exact_250_simplicity": list(EXACT_250_POLICIES),
            "adequate_subgroup_rows": ADEQUATE_SUBGROUP_ROWS,
        },
        "outer_folds": [{"validation_season": validation, "training_seasons": list(training)} for validation, training in OUTER_FOLDS],
        "preprocessing_order": feature_manifest(manifest)["transform_order"],
        "predeclared_staged_candidate_plan": staged_candidate_plan(),
        "prerequisite_hashes": anchors,
    }


def run(poss_150_csv, poss_100_csv, manifest_path, phase3b_summary_path, phase3c_summary_path, output_dir):
    """Execute the frozen A/B/C/D design and write deterministic artifacts."""
    rows_by_threshold, manifest, anchors = load_inputs(poss_150_csv, poss_100_csv, manifest_path, phase3b_summary_path, phase3c_summary_path)
    registry, all_metrics, all_tuning, all_weights, all_priors, all_imputations = [], [], [], [], [], []

    stage_a = []
    for estimator in ESTIMATORS:
        family = []
        for threshold in THRESHOLDS:
            for weight in WEIGHT_POLICIES:
                result = evaluate_candidate("A", estimator, threshold, weight, "distribution", "include", rows_by_threshold[threshold], manifest)
                family.append(result)
        _assign_season_wins(family)
        threshold_rank = {value: index for index, value in enumerate(THRESHOLDS)}
        weight_rank = {value: index for index, value in enumerate(WEIGHT_POLICIES)}
        selected = select_by_primary_mae([item["summary"] for item in family], lambda item: (threshold_rank[item["threshold"]], weight_rank[item["weight_policy"]]))
        for item in family:
            item["summary"]["advanced_from_stage"] = int(item["summary"]["candidate_id"] == selected["candidate_id"])
        stage_a.extend(family)

    stage_b = []
    for estimator in ESTIMATORS:
        selected_a = next(item for item in stage_a if item["summary"]["estimator"] == estimator and item["summary"]["advanced_from_stage"])
        threshold, weight = selected_a["summary"]["threshold"], selected_a["summary"]["weight_policy"]
        distribution = evaluate_candidate("B", estimator, threshold, weight, "distribution", "include", rows_by_threshold[threshold], manifest)
        no_shot = evaluate_candidate("B", estimator, threshold, weight, "no_shot", "include", rows_by_threshold[threshold], manifest,
                                     reused_fold_parameters=distribution["fold_parameters"] if estimator == "ridge" else None)
        efficiency = evaluate_candidate("B", estimator, threshold, weight, "distribution_plus_efficiency", "include", rows_by_threshold[threshold], manifest)
        family = [no_shot, distribution, efficiency]
        _assign_season_wins(family)
        feature_rank = {value: index for index, value in enumerate(FEATURE_VARIANTS)}
        selected = select_by_primary_mae([item["summary"] for item in family], lambda item: feature_rank[item["feature_variant"]])
        for item in family:
            item["summary"]["advanced_from_stage"] = int(item["summary"]["candidate_id"] == selected["candidate_id"])
        stage_b.extend(family)

    stage_c = []
    for estimator in ESTIMATORS:
        selected_b = next(item for item in stage_b if item["summary"]["estimator"] == estimator and item["summary"]["advanced_from_stage"])
        summary = selected_b["summary"]
        family = []
        for exact_policy in EXACT_250_POLICIES:
            reused = selected_b["fold_parameters"] if exact_policy == "include" else None
            family.append(evaluate_candidate("C", estimator, summary["threshold"], summary["weight_policy"], summary["feature_variant"], exact_policy,
                                             rows_by_threshold[summary["threshold"]], manifest, reused_fold_parameters=reused))
        _assign_season_wins(family)
        exact_rank = {value: index for index, value in enumerate(EXACT_250_POLICIES)}
        selected = select_by_primary_mae([item["summary"] for item in family], lambda item: exact_rank[item["exact_250_policy"]])
        for item in family:
            item["summary"]["advanced_from_stage"] = int(item["summary"]["candidate_id"] == selected["candidate_id"])
        stage_c.extend(family)

    all_results = stage_a + stage_b + stage_c
    for result in all_results:
        registry.append(result["summary"])
        all_metrics.extend(result["metrics"])
        all_tuning.extend(result["tuning"])
        all_weights.extend(result["weights"])
        all_priors.extend(result["priors"])
        all_imputations.extend(result["imputations"])

    finalists = [item for item in stage_c if item["summary"]["advanced_from_stage"]]
    finalist_predictions = sorted([row for item in finalists for row in item["predictions"]], key=lambda row: (row["candidate_id"], row["outer_fold"], int(row["team_id"]), int(row["player_1_id"]), int(row["player_2_id"])))
    all_candidate_predictions = [row for item in all_results for row in item["predictions"]]
    subgroups = subgroup_metrics(all_candidate_predictions)
    calibration = calibration_diagnostics(finalist_predictions)
    residuals = residual_diagnostics(finalist_predictions)
    ridge_final = next(item for item in finalists if item["summary"]["estimator"] == "ridge")
    hgb_final = next(item for item in finalists if item["summary"]["estimator"] == "hist_gradient_boosting")
    estimator_decision = ridge_vs_hgb_decision(ridge_final["summary"], hgb_final["summary"], ridge_final["predictions"], hgb_final["predictions"], subgroups)
    selected = ridge_final if estimator_decision["selected_estimator"] == "ridge" else hgb_final
    decision = {
        "version": VERSION,
        "stage_a_winners": {estimator: next(item["summary"] for item in stage_a if item["summary"]["estimator"] == estimator and item["summary"]["advanced_from_stage"]) for estimator in ESTIMATORS},
        "stage_b_winners": {estimator: next(item["summary"] for item in stage_b if item["summary"]["estimator"] == estimator and item["summary"]["advanced_from_stage"]) for estimator in ESTIMATORS},
        "stage_c_finalists": {estimator: next(item["summary"] for item in stage_c if item["summary"]["estimator"] == estimator and item["summary"]["advanced_from_stage"]) for estimator in ESTIMATORS},
        "estimator_decision": estimator_decision,
        "selected_candidate": selected["summary"],
        "confidence_labels": confidence_labels(subgroups, selected["summary"]["candidate_id"]),
        "calibration": calibration_recommendation(finalist_predictions, [item["summary"] for item in finalists], calibration),
        "classification": "Phase 3D design frozen; 2024-25 development holdout ready for separate authorization",
    }

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "experiment_configuration.json", _config(anchors, manifest))
    for row in registry:
        row["predeclared_plan_status"] = "executed"
    _write_csv(output / "staged_candidate_registry.csv", registry)
    _write_json(output / "fold_definitions.json", _config(anchors, manifest)["outer_folds"])
    feature_doc = feature_manifest(manifest)
    feature_doc["deterministic_content_sha256"] = canonical_json_hash(feature_doc)
    _write_json(output / "feature_manifest.json", feature_doc)
    _write_csv(output / "population_diagnostics.csv", population_diagnostics(rows_by_threshold))
    _write_csv(output / "smoothing_prior_diagnostics.csv", all_priors)
    _write_csv(output / "weight_diagnostics.csv", all_weights)
    _write_csv(output / "tuning_diagnostics.csv", all_tuning)
    _write_csv(output / "imputation_diagnostics.csv", all_imputations)
    _write_csv(output / "candidate_metrics.csv", all_metrics)
    _write_csv(output / "finalist_predictions.csv", finalist_predictions)
    _write_csv(output / "subgroup_metrics.csv", subgroups)
    _write_csv(output / "calibration_diagnostics.csv", calibration)
    _write_csv(output / "residual_diagnostics.csv", residuals)
    decision["deterministic_content_sha256"] = canonical_json_hash(decision)
    _write_json(output / "selection_decision.json", decision)

    hashes = {name: sha256_file(output / name) for name in PAYLOAD_ARTIFACTS}
    hash_manifest = {
        "version": VERSION,
        "artifacts": hashes,
        "hash_type": "SHA-256 of exact serialized bytes for every listed payload artifact",
        "excluded_outputs": NONCIRCULAR_EXCLUDED_OUTPUTS,
    }
    hash_manifest["deterministic_content_sha256"] = canonical_json_hash(hash_manifest)
    validate_artifact_manifest_scope(hash_manifest)
    _write_json(output / "artifact_hashes.json", hash_manifest)
    summary = {
        "version": VERSION,
        "classification": decision["classification"],
        "selected_candidate_id": selected["summary"]["candidate_id"],
        "selected_estimator": estimator_decision["selected_estimator"],
        "selected_metrics": {key: selected["summary"][key] for key in ("macro_season_mae", "pooled_mae", "macro_season_rmse", "pooled_rmse", "macro_season_r2", "pooled_r2", "macro_season_bias", "pooled_bias", "macro_season_spearman", "pooled_spearman", "macro_prediction_std", "prediction_std", "macro_target_std", "target_std", "worst_season_mae")},
        "candidate_count": len(registry),
        "finalist_prediction_rows": len(finalist_predictions),
        "artifact_hashes": hashes,
        "artifact_hashes_canonical_content_sha256": hash_manifest["deterministic_content_sha256"],
        "non_circular_hash_policy": NONCIRCULAR_EXCLUDED_OUTPUTS,
        "prerequisite_hashes": anchors,
        "determinism": {"hgb_random_state": HGB_CONFIG["random_state"], "row_order": "candidate, outer fold, numeric team and canonical player IDs"},
    }
    summary["deterministic_content_sha256"] = canonical_json_hash(summary)
    _write_json(output / "summary.json", summary)
    return summary
