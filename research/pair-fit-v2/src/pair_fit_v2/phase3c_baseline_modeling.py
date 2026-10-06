"""Leakage-safe rolling baseline models for Pair Fit v2 Phase 3C.

This is intentionally a small, offline experiment runner rather than a
general-purpose ML framework.  It accepts only the immutable Phase 3B primary
CSV, constructs the Phase 3B allowlisted symmetric features after fold-local
slot imputation, and writes audit-ready, deterministic artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from pair_fit_v2 import phase3b_curation as phase3b


VERSION = "phase3c.leakage-safe-rolling-baselines.v1"
PRIMARY_SHA256 = "da31ea8e01e9e0f213edee61fb4918e529883ceb77cf77f2c008da03fdf61db8"
MANIFEST_SHA256 = "ca137b375fa6613478ed826fa61eadd808d813e81e03311b2f70223e7ee25103"
SUMMARY_CONTENT_SHA256 = "70650038719f7a4f70505305cb00643f4b96e5753419a45691f594534b2e07b1"
ALLOWED_TARGET_SEASONS = tuple(f"{year}-{str(year + 1)[-2:]}" for year in range(2014, 2024))
OUTER_FOLDS = tuple(
    (validation, ALLOWED_TARGET_SEASONS[:ALLOWED_TARGET_SEASONS.index(validation)])
    for validation in ("2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24")
)
RIDGE_ALPHAS = (0.1, 1.0, 10.0, 100.0, 1000.0)
HGB_CONFIG = {"learning_rate": 0.05, "max_iter": 200, "max_leaf_nodes": 15,
              "min_samples_leaf": 50, "l2_regularization": 5.0,
              "early_stopping": False, "random_state": 314159}
VARIANTS = ("training_mean_baseline", "ridge_shot_enabled", "ridge_no_shot",
            "hist_gradient_boosting_shot_enabled", "hist_gradient_boosting_no_shot")
CALIBRATION_BINS = 10
PAYLOAD_ARTIFACTS = ("experiment_configuration.json", "fold_definitions.json", "feature_lists.json", "predictions.csv", "metrics.csv", "calibration.csv", "ridge_alpha_selection.csv", "imputation_diagnostics.csv")
EXPECTED_OUTPUT_ARTIFACTS = PAYLOAD_ARTIFACTS + ("artifact_hashes.json", "summary.json")
NONCIRCULAR_EXCLUDED_OUTPUTS = {
    "artifact_hashes.json": "self-referential byte hash is excluded; its canonical-content hash is stored inside the file",
    "summary.json": "serialized byte hash is excluded because summary.json records the artifact-manifest digest; its canonical-content hash is stored inside summary.json",
}


def canonical_json_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_content_hash(document, field="deterministic_content_sha256"):
    """Hash a documented semantic representation, excluding its self-hash."""
    value = dict(document)
    value.pop(field, None)
    return canonical_json_hash(value)


def validate_artifact_manifest_scope(manifest):
    """Fail closed when a planned output is silently absent from hash policy."""
    covered = set((manifest.get("artifacts") or {}).keys())
    excluded = set(NONCIRCULAR_EXCLUDED_OUTPUTS)
    if covered != set(PAYLOAD_ARTIFACTS):
        raise ValueError("artifact manifest payload coverage differs from Phase 3C contract")
    if covered | excluded != set(EXPECTED_OUTPUT_ARTIFACTS):
        raise ValueError("Phase 3C output is omitted from non-circular hash policy")
    return {"covered_byte_artifacts": len(covered), "explicitly_excluded_outputs": dict(NONCIRCULAR_EXCLUDED_OUTPUTS)}


def _finite(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _slot_column(field, slot):
    return f"player_{slot}_{field.lower()}"


def _shot_fields():
    primary = tuple(name for name in phase3b.PRIMARY_SHOT_SHARE_NAMES if name not in {
        "overall_three_point_location_share_overall", "classified_attempt_coverage"})
    l1 = ("shot_restricted_area_fga", "shot_non_restricted_paint_fga", "shot_mid_range_fga",
          "shot_left_corner_three_fga", "shot_right_corner_three_fga",
          "shot_above_the_break_three_fga", "shot_backcourt_fga",
          "shot_unclassified_fga", "shot_overall_fga")
    return primary, l1


SHOT_MEAN_FIELDS, L1_SLOT_FIELDS = _shot_fields()
CONTINUOUS_SLOT_FIELDS = tuple(field.lower() for field in phase3b.ESTIMATOR_CONTINUOUS_INPUTS)
IMPUTATION_SLOT_FIELDS = CONTINUOUS_SLOT_FIELDS + ("traded_player_indicator",) + tuple(
    f"shot_{field}" for field in SHOT_MEAN_FIELDS) + L1_SLOT_FIELDS
PROHIBITED_ESTIMATOR_SUBSTRINGS = ("pair_possessions", "pair_base_minutes", "target_", "player_1_", "player_2_", "weight", "gp", "total_min")


def feature_lists(manifest=None):
    """Return manifest-order shot and no-shot estimator feature allowlists."""
    manifest = manifest or phase3b.feature_manifest()
    enabled = tuple(manifest["future_estimator_features"])
    if len(enabled) != 52 or len(set(enabled)) != 52:
        raise ValueError("Phase 3B estimator contract must have exactly 52 distinct features")
    shot = tuple(name for name in enabled if name.startswith("pair_mean.shot_") or name == "pair_shot_distribution_l1_distance_overall_fga")
    no_shot = tuple(name for name in enabled if name not in shot)
    if len(shot) != 7 or len(no_shot) != 45:
        raise ValueError("unexpected Phase 3B shot/no-shot feature partition")
    for name in enabled:
        if any(token in name for token in PROHIBITED_ESTIMATOR_SUBSTRINGS):
            raise ValueError(f"prohibited estimator field: {name}")
    return enabled, no_shot, shot


def authorized_outer_folds():
    """Validate and expose the six required expanding-window folds."""
    if len(OUTER_FOLDS) != 6:
        raise ValueError("Phase 3C requires six outer folds")
    for validation, training in OUTER_FOLDS:
        if validation not in ALLOWED_TARGET_SEASONS or validation in training:
            raise ValueError(f"unauthorized outer fold: {validation}")
        expected = ALLOWED_TARGET_SEASONS[:ALLOWED_TARGET_SEASONS.index(validation)]
        if training != expected or len(training) < 4:
            raise ValueError(f"outer fold is not expanding history: {validation}")
    return OUTER_FOLDS


def inner_folds(outer_training_seasons):
    """Inner folds with at least three prior seasons, all inside outer train."""
    seasons = tuple(outer_training_seasons)
    return tuple((season, seasons[:index]) for index, season in enumerate(seasons) if index >= 3)


def load_primary_rows(csv_path, expected_sha256=PRIMARY_SHA256):
    path = Path(csv_path)
    if sha256_file(path) != expected_sha256:
        raise ValueError("Phase 3B primary CSV hash mismatch")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 27001:
        raise ValueError(f"unexpected Phase 3B primary population: {len(rows)}")
    validate_target_seasons(rows, require_full_window=True)
    for row in rows:
        if _finite(row.get("target_net_rating")) is None or _finite(row.get("pair_possessions")) is None:
            raise ValueError("nonfinite target or possession in primary input")
        if float(row["pair_possessions"]) < 150:
            raise ValueError("non-primary row supplied to Phase 3C")
    return rows


def validate_target_seasons(rows, require_full_window=False):
    """Fail closed if an input carries a protected target-outcome season."""
    unauthorized = sorted({row.get("target_season") for row in rows} - set(ALLOWED_TARGET_SEASONS))
    if unauthorized:
        raise ValueError(f"unauthorized target season(s): {unauthorized}")
    if require_full_window and {row["target_season"] for row in rows} != set(ALLOWED_TARGET_SEASONS):
        raise ValueError("primary input does not contain exactly the authorized seasons")


def _profile_key(row, slot):
    season = row.get(f"player_{slot}_history_profile_season")
    player = row.get(f"player_{slot}_id")
    return (player, season) if player and season else None


def fit_slot_imputer(training_rows):
    """Fold-only medians from unique observed player-season profiles.

    The first appearance of a profile supplies its immutable materialized slot
    values; later pair appearances cannot change a median.
    """
    profiles = {}
    for row in training_rows:
        for slot in ("1", "2"):
            key = _profile_key(row, slot)
            if key is None:
                continue
            values = {field: _finite(row.get(_slot_column(field, slot))) for field in IMPUTATION_SLOT_FIELDS}
            if key in profiles and profiles[key] != values:
                raise ValueError(f"inconsistent materialized profile: {key}")
            profiles[key] = values
    medians = {}
    for field in IMPUTATION_SLOT_FIELDS:
        values = sorted(value[field] for value in profiles.values() if value[field] is not None)
        if not values:
            raise ValueError(f"required imputation feature has no finite training value: {field}")
        medians[field] = float(np.median(np.asarray(values, dtype=float)))
    return medians, len(profiles)


def impute_slots(row, medians):
    """Apply the same learned value for a field to both player slots."""
    slots = []
    for slot in ("1", "2"):
        values = {}
        for field in IMPUTATION_SLOT_FIELDS:
            observed = _finite(row.get(_slot_column(field, slot)))
            values[field] = medians[field] if observed is None else observed
        slots.append(values)
    return slots[0], slots[1]


def transform_row(row, medians, enabled_features=None):
    """Construct all 52 order-invariant estimator values after imputation."""
    enabled_features, _, _ = feature_lists() if enabled_features is None else (tuple(enabled_features), (), ())
    left, right = impute_slots(row, medians)
    # Phase 3B feature names preserve source capitalization; map using its own
    # allowlist rather than hard-coding particular basketball variables.
    remapped = {}
    for name in enabled_features:
        if name.startswith("pair_mean.") and not name.startswith("pair_mean.shot_"):
            source = name.split(".", 1)[1].lower()
            remapped[name] = (left[source] + right[source]) / 2
        elif name.startswith("pair_absolute_difference."):
            source = name.split(".", 1)[1].lower()
            remapped[name] = abs(left[source] - right[source])
    remapped["pair_traded_history_count"] = left["traded_player_indicator"] + right["traded_player_indicator"]
    for field in SHOT_MEAN_FIELDS:
        remapped[f"pair_mean.shot_{field}"] = (left[f"shot_{field}"] + right[f"shot_{field}"]) / 2
    remapped["pair_shot_distribution_l1_distance_overall_fga"] = phase3b.shot_distribution_l1_distance_overall_fga(left, right)
    result = {name: remapped[name] for name in enabled_features}
    undefined = {name for name, value in result.items() if _finite(value) is None}
    # Slot imputation resolves absent player profiles.  The approved L1 formula
    # remains undefined for an *observed* zero overall-FGA denominator; its
    # later pair-feature median is learned from training rows below.
    if undefined - {"pair_shot_distribution_l1_distance_overall_fga"}:
        raise ValueError(f"nonfinite transformed estimator feature: {sorted(undefined)}")
    return result


def matrix_for_rows(rows, medians, feature_names):
    all_features, _, _ = feature_lists()
    transformed = [transform_row(row, medians, all_features) for row in rows]
    return np.asarray([[np.nan if item[name] is None else item[name] for name in feature_names] for item in transformed], dtype=float)


def _targets(rows):
    return np.asarray([float(row["target_net_rating"]) for row in rows], dtype=float)


def fit_preprocessor(training_rows, validation_rows, feature_names, scale):
    medians, profile_count = fit_slot_imputer(training_rows)
    train_x = matrix_for_rows(training_rows, medians, feature_names)
    validation_x = matrix_for_rows(validation_rows, medians, feature_names)
    feature_medians = {}
    for index, name in enumerate(feature_names):
        finite = train_x[np.isfinite(train_x[:, index]), index]
        if not len(finite):
            raise ValueError(f"required symmetric feature has no finite training value: {name}")
        feature_medians[name] = float(np.median(finite))
        train_x[~np.isfinite(train_x[:, index]), index] = feature_medians[name]
        validation_x[~np.isfinite(validation_x[:, index]), index] = feature_medians[name]
    if not np.isfinite(train_x).all() or not np.isfinite(validation_x).all():
        raise ValueError("pair-feature imputation left nonfinite matrix values")
    scaler = StandardScaler() if scale else None
    if scaler is not None:
        train_x = scaler.fit_transform(train_x)
        validation_x = scaler.transform(validation_x)
    return train_x, validation_x, medians, profile_count, scaler, feature_medians


def metric_values(actual, prediction):
    actual, prediction = np.asarray(actual, dtype=float), np.asarray(prediction, dtype=float)
    if len(actual) != len(prediction) or not len(actual) or not np.isfinite(prediction).all():
        raise ValueError("invalid metric inputs or nonfinite prediction")
    error = prediction - actual
    ss_total = float(np.sum((actual - actual.mean()) ** 2))
    r2 = None if ss_total == 0 else float(1 - np.sum(error ** 2) / ss_total)
    correlation = None if np.std(actual) == 0 or np.std(prediction) == 0 else spearmanr(actual, prediction).statistic
    return {"validation_rows": int(len(actual)), "mae": float(np.mean(np.abs(error))),
            "rmse": float(np.sqrt(np.mean(error ** 2))), "r2": r2,
            "mean_signed_error_bias": float(np.mean(error)),
            "spearman_rank_correlation": None if correlation is None or not math.isfinite(correlation) else float(correlation),
            "prediction_mean": float(prediction.mean()), "target_mean": float(actual.mean()),
            "prediction_std": float(prediction.std(ddof=0)), "target_std": float(actual.std(ddof=0))}


def calibration_rows(prediction_rows, bins=CALIBRATION_BINS):
    grouped = defaultdict(list)
    for row in prediction_rows:
        grouped[(row["model_variant"], row["outer_fold"])].append(row)
    output = []
    for (variant, season), rows in sorted(grouped.items()):
        count = min(bins, len(rows))
        ordered = sorted(rows, key=lambda row: (float(row["prediction"]), row["team_id"], row["player_1_id"], row["player_2_id"]))
        assigned = defaultdict(list)
        for index, row in enumerate(ordered):
            assigned[1 + index * count // len(ordered)].append(row)
        for bin_number in range(1, count + 1):
            members = assigned[bin_number]
            output.append({"model_variant": variant, "outer_fold": season, "requested_bins": bins,
                           "used_bins": count, "bin": bin_number, "rows": len(members),
                           "prediction_mean": float(np.mean([float(x["prediction"]) for x in members])),
                           "target_mean": float(np.mean([float(x["actual_target"]) for x in members]))})
    return output


def _metric_rows(prediction_rows):
    rows = []
    groups = defaultdict(list)
    for row in prediction_rows:
        groups[(row["model_variant"], row["outer_fold"], "per_fold", "all")].append(row)
        groups[(row["model_variant"], "all_outer", "aggregate", "all")].append(row)
        groups[(row["model_variant"], row["outer_fold"], "history_status", row["history_status"])].append(row)
        groups[(row["model_variant"], "all_outer", "history_status", row["history_status"])].append(row)
        groups[(row["model_variant"], row["outer_fold"], "pandemic_context", "pandemic" if row["pandemic_flag"] == "1" else "non_pandemic")].append(row)
        groups[(row["model_variant"], "all_outer", "pandemic_context", "pandemic" if row["pandemic_flag"] == "1" else "non_pandemic")].append(row)
        groups[(row["model_variant"], row["outer_fold"], "exact_250_flag", "exact_250" if row["exact_250_flag"] == "1" else "not_exact_250")].append(row)
        groups[(row["model_variant"], "all_outer", "exact_250_flag", "exact_250" if row["exact_250_flag"] == "1" else "not_exact_250")].append(row)
    for (variant, season, scope, subgroup), members in sorted(groups.items()):
        metrics = metric_values([float(x["actual_target"]) for x in members], [float(x["prediction"]) for x in members])
        rows.append({"model_variant": variant, "season": season, "scope": scope, "subgroup": subgroup, **metrics})
    # Equal-season macro metrics and a team-season macro where each group is
    # equally influential, not a claim that pair rows are independent.
    for variant in VARIANTS:
        fold_metrics = [row for row in rows if row["model_variant"] == variant and row["scope"] == "per_fold"]
        rows.append({"model_variant": variant, "season": "all_outer", "scope": "macro_season", "subgroup": "all", **_macro_metrics(fold_metrics)})
        team_groups = defaultdict(list)
        for item in prediction_rows:
            if item["model_variant"] == variant:
                team_groups[(item["outer_fold"], item["team_id"])].append(item)
        team_metrics = [metric_values([float(x["actual_target"]) for x in members], [float(x["prediction"]) for x in members]) for members in team_groups.values()]
        rows.append({"model_variant": variant, "season": "all_outer", "scope": "macro_team_season", "subgroup": "all", **_macro_metrics(team_metrics)})
    return rows


def _macro_metrics(rows):
    keys = ("mae", "rmse", "r2", "mean_signed_error_bias", "spearman_rank_correlation", "prediction_mean", "target_mean", "prediction_std", "target_std")
    result = {"validation_rows": int(sum(row["validation_rows"] for row in rows))}
    for key in keys:
        values = [row[key] for row in rows if row[key] is not None]
        result[key] = None if not values else float(np.mean(values))
    return result


def _prediction_record(row, prediction, variant, fold):
    return {"target_season": row["target_season"], "team_id": row["team_id"], "player_1_id": row["player_1_id"], "player_2_id": row["player_2_id"],
            "actual_target": float(row["target_net_rating"]), "prediction": float(prediction),
            "model_variant": variant, "outer_fold": fold, "history_status": row["history_status"],
            "pandemic_flag": row["pandemic_affected_season_flag"], "exact_250_flag": row["endpoint_exact_250_flag"]}


def select_ridge_alpha(training_rows, training_seasons, shot_features):
    results = []
    for alpha in RIDGE_ALPHAS:
        maes = []
        for validation, seasons in inner_folds(training_seasons):
            train = [row for row in training_rows if row["target_season"] in seasons]
            valid = [row for row in training_rows if row["target_season"] == validation]
            train_x, valid_x, *_ = fit_preprocessor(train, valid, shot_features, scale=True)
            model = Ridge(alpha=alpha).fit(train_x, _targets(train))
            maes.append(metric_values(_targets(valid), model.predict(valid_x))["mae"])
        results.append({"alpha": alpha, "inner_fold_count": len(maes), "mean_inner_mae": float(np.mean(maes)), "inner_maes": maes})
    # Stable smaller-alpha tie break, after exact floating-point equality only.
    selected = min(results, key=lambda value: (value["mean_inner_mae"], value["alpha"]))
    return selected, results


def _write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row}) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def run(primary_csv, manifest_path, summary_path, output_dir):
    """Run all five predeclared variants and write deterministic artifacts."""
    if sha256_file(manifest_path) != MANIFEST_SHA256:
        raise ValueError("Phase 3B feature manifest hash mismatch")
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    if summary.get("deterministic_content_sha256") != SUMMARY_CONTENT_SHA256:
        raise ValueError("Phase 3B curation summary content hash mismatch")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    phase3b.validate_feature_manifest(manifest)
    enabled, no_shot, shot = feature_lists(manifest)
    rows = load_primary_rows(primary_csv)
    folds = authorized_outer_folds()
    predictions, imputation_diagnostics, alpha_rows = [], [], []
    for validation_season, train_seasons in folds:
        train = [row for row in rows if row["target_season"] in train_seasons]
        valid = [row for row in rows if row["target_season"] == validation_season]
        if not train or not valid:
            raise ValueError(f"empty outer fold: {validation_season}")
        selected, tuning = select_ridge_alpha(train, train_seasons, enabled)
        alpha = selected["alpha"]
        for candidate in tuning:
            alpha_rows.append({"outer_fold": validation_season, "selected": int(candidate["alpha"] == alpha), **candidate})
        # Fit separately by declared variant; every fit uses the exact same
        # training records and fold-local median policy.
        mean_prediction = float(np.mean(_targets(train)))
        predictions.extend(_prediction_record(row, mean_prediction, "training_mean_baseline", validation_season) for row in valid)
        for label, features in (("shot_enabled", enabled), ("no_shot", no_shot)):
            train_x, valid_x, medians, profile_count, _, feature_medians = fit_preprocessor(train, valid, features, scale=True)
            imputation_diagnostics.extend({"outer_fold": validation_season, "variant_feature_set": label, "feature": field,
                                           "preprocessing_stage": "slot", "median": value, "unique_training_profiles": profile_count,
                                           "training_rows": len(train), "validation_rows": len(valid)} for field, value in sorted(medians.items()))
            imputation_diagnostics.extend({"outer_fold": validation_season, "variant_feature_set": label, "feature": field,
                                           "preprocessing_stage": "symmetric_feature", "median": value, "unique_training_profiles": profile_count,
                                           "training_rows": len(train), "validation_rows": len(valid)} for field, value in sorted(feature_medians.items()))
            ridge = Ridge(alpha=alpha).fit(train_x, _targets(train))
            ridge_prediction = ridge.predict(valid_x)
            if not np.isfinite(ridge_prediction).all():
                raise ValueError("nonfinite ridge prediction")
            predictions.extend(_prediction_record(row, value, f"ridge_{label}", validation_season) for row, value in zip(valid, ridge_prediction))
            train_x, valid_x, *_ = fit_preprocessor(train, valid, features, scale=False)
            hgb = HistGradientBoostingRegressor(**HGB_CONFIG).fit(train_x, _targets(train))
            hgb_prediction = hgb.predict(valid_x)
            if not np.isfinite(hgb_prediction).all():
                raise ValueError("nonfinite HGB prediction")
            predictions.extend(_prediction_record(row, value, f"hist_gradient_boosting_{label}", validation_season) for row, value in zip(valid, hgb_prediction))
    predictions.sort(key=lambda row: (row["model_variant"], row["outer_fold"], row["team_id"], row["player_1_id"], row["player_2_id"]))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config = {"version": VERSION, "network": "prohibited", "primary_population": {"threshold": "POSS >= 150", "rows": 27001, "equal_row_weights": True, "sha256": PRIMARY_SHA256},
              "authorized_target_seasons": list(ALLOWED_TARGET_SEASONS), "outer_folds": [{"validation_season": valid, "training_seasons": list(train)} for valid, train in folds],
              "ridge_alpha_grid": list(RIDGE_ALPHAS), "ridge_tie_break": "lowest alpha after exact mean-inner-MAE tie", "hgb_configuration": HGB_CONFIG,
              "feature_counts": {"shot_enabled": len(enabled), "no_shot": len(no_shot), "removed_shot_features": list(shot)},
              "variants": list(VARIANTS), "target": "NET_RATING", "target_transform": "none", "phase3b_manifest_sha256": MANIFEST_SHA256,
              "phase3b_summary_content_sha256": SUMMARY_CONTENT_SHA256}
    _write_json(output / "experiment_configuration.json", config)
    _write_json(output / "fold_definitions.json", config["outer_folds"])
    _write_json(output / "feature_lists.json", {"shot_enabled": list(enabled), "no_shot": list(no_shot), "shot_only": list(shot)})
    _write_csv(output / "predictions.csv", predictions)
    metrics = _metric_rows(predictions)
    _write_csv(output / "metrics.csv", metrics)
    _write_csv(output / "calibration.csv", calibration_rows(predictions))
    _write_csv(output / "ridge_alpha_selection.csv", alpha_rows)
    _write_csv(output / "imputation_diagnostics.csv", imputation_diagnostics)
    hashes = {name: sha256_file(output / name) for name in PAYLOAD_ARTIFACTS}
    hash_manifest = {"artifacts": hashes, "self_hash_policy": "this file omits its own byte hash; deterministic_content_sha256 hashes this object without that field"}
    hash_manifest["deterministic_content_sha256"] = canonical_json_hash(hash_manifest)
    validate_artifact_manifest_scope(hash_manifest)
    _write_json(output / "artifact_hashes.json", hash_manifest)
    summary_out = {"version": VERSION, "rows": len(rows), "outer_folds": len(folds), "model_variants": len(VARIANTS),
                   "prediction_rows": len(predictions), "artifact_hashes": hashes,
                   "artifact_hashes_content_sha256": hash_manifest["deterministic_content_sha256"],
                   "phase3b_reconciliation": {"primary_csv_sha256": PRIMARY_SHA256, "manifest_sha256": MANIFEST_SHA256,
                                                "summary_content_sha256": SUMMARY_CONTENT_SHA256},
                   "determinism": {"hgb_random_state": HGB_CONFIG["random_state"], "prediction_order": "variant, fold, team, canonical player IDs"}}
    summary_out["deterministic_content_sha256"] = canonical_json_hash(summary_out)
    _write_json(output / "summary.json", summary_out)
    return summary_out
