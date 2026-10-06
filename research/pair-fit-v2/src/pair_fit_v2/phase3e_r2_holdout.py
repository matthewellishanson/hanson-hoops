"""Deterministic, cache-only construction of the 2024-25 holdout dataset.

This module prepares data and training-derived preprocessing state only.  It
does not instantiate, fit, load, or run an estimator and does not calculate
prediction or model-performance statistics.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from pair_fit_v2 import phase3a_population_audit as phase3a
from pair_fit_v2 import phase3b_curation as phase3b
from pair_fit_v2 import phase3d_model_refinement as phase3d
from pair_fit_v2 import phase3e_r0_evidence_reconciliation as phase3e_r0
from pair_fit_v2.phase1c_manifest import verify_asset_cache


VERSION = "phase3e-r2.deterministic-holdout-construction.v1"
TARGET_SEASON = "2024-25"
PROTECTED_SEASON = "2025-26"
SEASON_TYPE = "regular-season"
ELIGIBILITY_THRESHOLD = 150.0
MAX_HISTORY_LOOKBACK = 3
REQUIRED_STARTING_HEAD = "cb749f7c7841c87eb8ddc473c745981b9f67898a"
EXCLUDED_TEAMS = {
    "1610612766": "Charlotte Hornets",
    "1610612755": "Philadelphia 76ers",
}

PHASE1C_MANIFEST = Path("phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json")
PHASE1C_MANIFEST_SHA256 = "5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c"
PHASE2B_MANIFEST = Path("phase2b/release_manifest.json")
PHASE2B_MANIFEST_SHA256 = "af8acbc10adf110f43c7c53a0ab2d6b402e3121fbe57e2d8b5dc3de7072e689e"
PHASE2C_MANIFEST = Path("phase2c/manifest.json")
PHASE2C_MANIFEST_SHA256 = "cce7150e0aa0a4c0278c34d8f20bed0b534bc02ef65c61031c65b03fd786ed0d"
PER100_2023 = Path("live_responses/league_dash_player_stats_2023-24_base_per100possessions.json")
PER100_2023_SHA256 = "da9ba4375be5522407e908e073a95d51b1a1ede41fe659ef75d07e178f8bbc0a"
TOTALS_2023 = Path("phase3a1/raw/league_dash_player_stats_2023-24_base_totals.attempt-1.json")
TOTALS_2023_SHA256 = phase3e_r0.PLAYER_TOTALS_RAW_SHA256
TRAINING_CSV_SHA256 = phase3d.POSS_150_SHA256
PHASE3D_SELECTION_SHA256 = "5ef9663dff906fc04b3a31aec56c0dce1ce9fe4e7cdcc87dbaab95762ff02ca0"
R1_RESULT_SHA256 = "907f8474a052ad6358737c8941d6e7a059889d154214e44a5c62aa7b975b4bc5"
R1_POLICY_SHA256 = "9273090b5cc55faddf54f0e531ad3845d5f67e311fa806bf2a6e7d8db74a6c41"
R1_REPORT_SHA256 = "f70011e3084eda35271a250106d232f2ce4422cee20f3b7f315f2d8167c73d9d"

OUTPUT_FILES = (
    "holdout_staging.csv",
    "holdout_row_index.csv",
    "holdout_estimator_matrix.csv",
    "estimator_feature_manifest.json",
    "population_diagnostics.json",
    "preprocessing_state.json",
    "input_fingerprints.json",
)
PROHIBITED_EXACT = {
    "MIN", "TOTAL_MIN", "GP", "POSS", "pair_possessions", "pair_base_minutes",
    "target_net_rating", "target_off_rating_audit", "target_def_rating_audit",
}
PROHIBITED_SUBSTRINGS = (
    "shot_", "player_1_", "player_2_", "weight", "usage", "reliability",
)


class FrozenContractViolation(ValueError):
    """Raised when cached evidence violates the frozen population/feature contract."""


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path | str) -> str:
    return _sha_bytes(_read_bytes(Path(path)))


def canonical_content_hash(document: dict, field: str = "deterministic_content_sha256") -> str:
    value = dict(document)
    value.pop(field, None)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return _sha_bytes(encoded)


def reject_protected_paths(*paths: Path | str) -> None:
    for path in paths:
        if PROTECTED_SEASON in str(path).replace("\\", "/").lower():
            raise ValueError(f"protected-season path rejected before access: {path}")


def _read_bytes(path: Path) -> bytes:
    reject_protected_paths(path)
    return path.read_bytes()


def _read_json(path: Path) -> dict:
    return json.loads(_read_bytes(path).decode("utf-8-sig"))


def _require_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"prerequisite hash mismatch: {path}; expected={expected}; actual={actual}")


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _result_rows(payload: dict, name: str) -> tuple[list[str], list[dict]]:
    matches = [item for item in payload.get("resultSets", []) if item.get("name") == name]
    if len(matches) != 1:
        raise FrozenContractViolation(f"expected exactly one {name} result set")
    headers = matches[0].get("headers")
    raw_rows = matches[0].get("rowSet")
    if not isinstance(headers, list) or len(headers) != len(set(headers)) or not isinstance(raw_rows, list):
        raise FrozenContractViolation(f"malformed {name} result set")
    if any(not isinstance(row, list) or len(row) != len(headers) for row in raw_rows):
        raise FrozenContractViolation(f"malformed {name} row width")
    return headers, [dict(zip(headers, row)) for row in raw_rows]


def _pair_index(payload: dict) -> tuple[dict[tuple[str, str], dict], dict]:
    _, rows = _result_rows(payload, "Lineups")
    valid: list[tuple[tuple[str, str], dict]] = []
    malformed = same_player = 0
    for row in rows:
        tokens = [token for token in str(row.get("GROUP_ID", "")).strip("-").split("-") if token]
        if len(tokens) != 2 or any(not token.isdecimal() or int(token) <= 0 for token in tokens):
            malformed += 1
            continue
        if int(tokens[0]) == int(tokens[1]):
            same_player += 1
            continue
        key = tuple(sorted((str(int(tokens[0])), str(int(tokens[1]))), key=int))
        valid.append((key, row))
    counts = Counter(key for key, _ in valid)
    duplicate = sum(count - 1 for count in counts.values() if count > 1)
    index = {key: row for key, row in valid}
    return index, {
        "returned_rows": len(rows),
        "canonical_unique_pair_keys": len(index),
        "malformed_pair_rows": malformed,
        "same_player_rows": same_player,
        "duplicate_pair_rows": duplicate,
    }


def _asset_raw_hash(asset: dict, cache_root: Path) -> str:
    path = cache_root / asset["cache"]["relative_path"]
    actual = sha256_file(path)
    expected = asset.get("source_event", {}).get("raw_body_hash")
    if expected and actual != expected:
        raise ValueError(f"raw body hash mismatch: {path}")
    return actual


def load_holdout_population(cache_root: Path) -> tuple[list[dict], dict, dict[str, str]]:
    """Verify all 30 team-seasons and return canonical raw rows plus diagnostics."""
    manifest_path = cache_root / PHASE1C_MANIFEST
    _require_hash(manifest_path, PHASE1C_MANIFEST_SHA256)
    manifest = _read_json(manifest_path)
    logical = manifest.get("logical_identity", {})
    if logical.get("season") != TARGET_SEASON or logical.get("season_type") != "regular-season":
        raise FrozenContractViolation("Phase 1C manifest target identity mismatch")
    team_directory = manifest.get("team_directory", {})
    if len(team_directory) != 30:
        raise FrozenContractViolation(f"expected 30 cached team-seasons, found {len(team_directory)}")

    verified: dict[str, dict[str, dict]] = defaultdict(dict)
    fingerprints = {str(PHASE1C_MANIFEST).replace("\\", "/"): sha256_file(manifest_path)}
    assets = manifest.get("raw_assets", [])
    for asset in assets:
        identity = asset.get("identity", {})
        params = identity.get("parameters", {})
        measure = params.get("measure_type")
        team_id = str(params.get("team_id"))
        if identity.get("endpoint") != "TeamDashLineups" or measure not in {"Base", "Advanced"}:
            raise FrozenContractViolation("unexpected asset in Phase 1C pair manifest")
        if params.get("season") != TARGET_SEASON or params.get("season_type") != SEASON_TYPE:
            raise FrozenContractViolation("target asset identity mismatch")
        for key in ("relative_path", "metadata_relative_path"):
            path = cache_root / asset["cache"][key]
            reject_protected_paths(path)
            fingerprints[str(path.relative_to(cache_root)).replace("\\", "/")] = sha256_file(path)
        validation = verify_asset_cache(asset, cache_root, manifest["approved_schema_contract"])
        raw_hash = _asset_raw_hash(asset, cache_root)
        verified[team_id][measure] = {
            "asset": asset,
            "payload": validation["payload"],
            "raw_hash": raw_hash,
        }
    if len(assets) != 60 or set(verified) != set(team_directory):
        raise FrozenContractViolation("30-team Base/Advanced asset inventory mismatch")

    raw_rows: list[dict] = []
    team_diagnostics = []
    blockers = []
    for team_id in sorted(team_directory, key=int):
        measures = verified[team_id]
        if set(measures) != {"Base", "Advanced"}:
            raise FrozenContractViolation(f"Base/Advanced asset missing for {team_id}")
        base, base_diag = _pair_index(measures["Base"]["payload"])
        advanced, advanced_diag = _pair_index(measures["Advanced"]["payload"])
        base_only = sorted(set(base) - set(advanced), key=lambda pair: tuple(map(int, pair)))
        advanced_only = sorted(set(advanced) - set(base), key=lambda pair: tuple(map(int, pair)))
        missing_target = nonfinite_target = missing_possession = nonpositive_possession = negative_possession = 0
        eligible = 0
        summed_possessions = eligible_summed_possessions = 0.0
        for key, row in advanced.items():
            target_raw = row.get("NET_RATING")
            possession_raw = row.get("POSS")
            target = _number(target_raw)
            possession = _number(possession_raw)
            missing_target += int(target_raw is None or target_raw == "")
            nonfinite_target += int(target_raw not in (None, "") and target is None)
            missing_possession += int(possession_raw is None or possession_raw == "" or possession is None)
            nonpositive_possession += int(possession is not None and possession <= 0)
            negative_possession += int(possession is not None and possession < 0)
            if possession is not None:
                summed_possessions += possession
            if possession is not None and possession >= ELIGIBILITY_THRESHOLD:
                eligible += 1
                eligible_summed_possessions += possession
            if key in base and target is not None and possession is not None:
                raw_rows.append({
                    "target_season": TARGET_SEASON,
                    "team_id": team_id,
                    "team_name": team_directory[team_id]["team_name"],
                    "player_1_id": key[0],
                    "player_2_id": key[1],
                    "target_net_rating": target,
                    "pair_possessions": possession,
                    "pair_base_minutes": _number(base[key].get("MIN")),
                    "endpoint_exact_250_flag": int(len(advanced) == 250),
                    "raw_pair_base_asset_id": measures["Base"]["asset"]["asset_id"],
                    "raw_pair_advanced_asset_id": measures["Advanced"]["asset"]["asset_id"],
                    "raw_pair_base_path": measures["Base"]["asset"]["cache"]["relative_path"],
                    "raw_pair_advanced_path": measures["Advanced"]["asset"]["cache"]["relative_path"],
                    "raw_pair_base_hash": measures["Base"]["raw_hash"],
                    "raw_pair_advanced_hash": measures["Advanced"]["raw_hash"],
                })
        structural = {
            "malformed_pair_rows": base_diag["malformed_pair_rows"] + advanced_diag["malformed_pair_rows"],
            "same_player_rows": base_diag["same_player_rows"] + advanced_diag["same_player_rows"],
            "duplicate_pair_rows": base_diag["duplicate_pair_rows"] + advanced_diag["duplicate_pair_rows"],
        }
        record = {
            "team_id": team_id,
            "team_name": team_directory[team_id]["team_name"],
            "population_disposition": "excluded_full_team_season_non_exhaustive" if team_id in EXCLUDED_TEAMS else "retained_if_eligible",
            "base_raw_rows": base_diag["returned_rows"],
            "advanced_raw_rows": advanced_diag["returned_rows"],
            "base_unique_pair_keys": len(base),
            "advanced_unique_pair_keys": len(advanced),
            "base_only_pair_keys": len(base_only),
            "advanced_only_pair_keys": len(advanced_only),
            "eligible_poss_ge_150_rows": eligible,
            "summed_possessions": summed_possessions,
            "eligible_summed_possessions": eligible_summed_possessions,
            **structural,
            "missing_target_rows": missing_target,
            "nonfinite_target_rows": nonfinite_target,
            "missing_possession_rows": missing_possession,
            "nonpositive_possession_rows": nonpositive_possession,
            "negative_possession_rows": negative_possession,
            "reconciliation_passed": not (base_only or advanced_only or any(structural.values())),
        }
        team_diagnostics.append(record)
        if base_only or advanced_only or any(structural.values()) or missing_target or nonfinite_target or missing_possession or negative_possession:
            blockers.append(team_id)
    if blockers:
        raise FrozenContractViolation(f"identity/schema/pair/finite-value contract failed for teams: {blockers}")
    keys = [(row["team_id"], row["player_1_id"], row["player_2_id"]) for row in raw_rows]
    if len(keys) != len(set(keys)):
        raise FrozenContractViolation("duplicate cross-team observation keys")
    diagnostics = {
        "original_cached_team_seasons": team_diagnostics,
        "original_cached_team_season_count": 30,
        "base_advanced_reconciliation_all_passed": all(row["reconciliation_passed"] for row in team_diagnostics),
    }
    return raw_rows, diagnostics, fingerprints


def _profile_sources_from_manifest(cache_root: Path, manifest_relative: Path, target_season: str) -> tuple[dict, dict, dict[str, str]]:
    manifest = _read_json(cache_root / manifest_relative)
    assets = manifest.get("player_dependencies") or [
        item for item in (manifest.get("assets") or manifest.get("pair_assets") or [])
        if item.get("identity", {}).get("endpoint") == "LeagueDashPlayerStats"
    ]
    sources = {}
    fingerprints = {str(manifest_relative).replace("\\", "/"): sha256_file(cache_root / manifest_relative)}
    payloads = {}
    for asset in assets:
        identity = asset.get("identity") or asset.get("source_identity")
        if identity.get("endpoint") != "LeagueDashPlayerStats":
            continue
        reference = phase3b._cache_reference(asset)
        path = cache_root / reference["relative_path"]
        _require_hash(path, reference["raw_body_hash"])
        mode = identity["parameters"]["per_mode"]
        sources[mode] = reference
        payloads[mode] = _read_json(path)
        fingerprints[reference["relative_path"].replace("\\", "/")] = reference["raw_body_hash"]
    if set(sources) != {"Per100Possessions", "Totals"}:
        raise FrozenContractViolation(f"player evidence incomplete for target manifest {target_season}")
    profile_season = f"{int(target_season[:4]) - 1}-{target_season[2:4]}"
    return {profile_season: sources}, {profile_season: payloads}, fingerprints


def _profiles_from_payloads(profile_season: str, payloads: dict[str, dict]) -> dict[str, dict]:
    _, per100_rows = _result_rows(payloads["Per100Possessions"], "LeagueDashPlayerStats")
    _, totals_rows = _result_rows(payloads["Totals"], "LeagueDashPlayerStats")
    totals = {}
    for row in totals_rows:
        player_id = phase3a._id(row["PLAYER_ID"])
        if player_id in totals:
            raise FrozenContractViolation(f"duplicate Totals player ID: {profile_season}/{player_id}")
        totals[player_id] = row
    profiles = {}
    for row in per100_rows:
        player_id = phase3a._id(row["PLAYER_ID"])
        if player_id in profiles or player_id not in totals:
            raise FrozenContractViolation(f"Per100/Totals player reconciliation failed: {profile_season}/{player_id}")
        profiles[player_id] = {**row, "TOTAL_MIN": totals[player_id].get("MIN")}
    if set(profiles) != set(totals):
        raise FrozenContractViolation(f"Per100/Totals player sets differ: {profile_season}")
    return profiles


def load_prior_profiles(cache_root: Path) -> tuple[dict, dict, dict[str, str]]:
    """Load only the three profile seasons authorized by the lookback rule."""
    _require_hash(cache_root / PHASE2B_MANIFEST, PHASE2B_MANIFEST_SHA256)
    _require_hash(cache_root / PHASE2C_MANIFEST, PHASE2C_MANIFEST_SHA256)
    sources: dict[str, dict] = {}
    payloads_by_season: dict[str, dict] = {}
    fingerprints: dict[str, str] = {}
    for manifest, target in ((PHASE2B_MANIFEST, "2023-24"), (PHASE2C_MANIFEST, "2022-23")):
        season_sources, season_payloads, season_fingerprints = _profile_sources_from_manifest(cache_root, manifest, target)
        sources.update(season_sources)
        payloads_by_season.update(season_payloads)
        fingerprints.update(season_fingerprints)

    phase3e_r0.verify_player_totals_dependency(cache_root)
    _require_hash(cache_root / PER100_2023, PER100_2023_SHA256)
    _require_hash(cache_root / TOTALS_2023, TOTALS_2023_SHA256)
    sources["2023-24"] = {
        "Per100Possessions": {"relative_path": str(PER100_2023).replace("\\", "/"), "raw_body_hash": PER100_2023_SHA256},
        "Totals": {"relative_path": str(TOTALS_2023).replace("\\", "/"), "raw_body_hash": TOTALS_2023_SHA256},
    }
    payloads_by_season["2023-24"] = {
        "Per100Possessions": _read_json(cache_root / PER100_2023),
        "Totals": _read_json(cache_root / TOTALS_2023),
    }
    fingerprints[str(PER100_2023).replace("\\", "/")] = PER100_2023_SHA256
    fingerprints[str(TOTALS_2023).replace("\\", "/")] = TOTALS_2023_SHA256
    profiles = {season: _profiles_from_payloads(season, payloads) for season, payloads in payloads_by_season.items()}
    if set(profiles) != {"2021-22", "2022-23", "2023-24"}:
        raise FrozenContractViolation("three-season profile window mismatch")
    return profiles, sources, fingerprints


def _slot_values(slot: int, player_id: str, profiles: dict, sources: dict) -> dict:
    profile_season, gap, profile = phase3b._select_history(TARGET_SEASON, player_id, profiles)
    result = {
        f"player_{slot}_history_missing": int(profile is None),
        f"player_{slot}_history_profile_season": profile_season,
        f"player_{slot}_history_gap": gap,
        f"player_{slot}_profile_source_per100_path": None,
        f"player_{slot}_profile_source_totals_path": None,
        f"player_{slot}_profile_source_per100_hash": None,
        f"player_{slot}_profile_source_totals_hash": None,
    }
    for field in phase3b.PLAYER_NUMERIC_INPUTS + phase3b.PLAYER_DERIVED_INPUTS:
        result[f"player_{slot}_{field.lower()}"] = None
    if profile is None:
        return result
    source = sources[profile_season]
    result.update({
        f"player_{slot}_profile_source_per100_path": source["Per100Possessions"]["relative_path"],
        f"player_{slot}_profile_source_totals_path": source["Totals"]["relative_path"],
        f"player_{slot}_profile_source_per100_hash": source["Per100Possessions"]["raw_body_hash"],
        f"player_{slot}_profile_source_totals_hash": source["Totals"]["raw_body_hash"],
    })
    for field in phase3b.PLAYER_NUMERIC_INPUTS:
        result[f"player_{slot}_{field.lower()}"] = _number(profile.get(field))
    for field, value in phase3b.derived_player_inputs(profile).items():
        result[f"player_{slot}_{field}"] = value
    return result


def curate_rows(raw_rows: list[dict], profiles: dict, sources: dict) -> tuple[list[dict], dict]:
    rows = []
    for raw in raw_rows:
        if raw["team_id"] in EXCLUDED_TEAMS or raw["pair_possessions"] < ELIGIBILITY_THRESHOLD:
            continue
        row = dict(raw)
        row.update(_slot_values(1, row["player_1_id"], profiles, sources))
        row.update(_slot_values(2, row["player_2_id"], profiles, sources))
        missing = row["player_1_history_missing"] + row["player_2_history_missing"]
        row["missing_player_count"] = missing
        row["history_status"] = {0: "complete", 1: "one_missing", 2: "both_missing"}[missing]
        row["strict_complete_history_eligible"] = int(missing == 0)
        rows.append(row)
    rows.sort(key=lambda row: (int(row["team_id"]), int(row["player_1_id"]), int(row["player_2_id"])))
    history = Counter(row["history_status"] for row in rows)
    selected_seasons = Counter(
        row[f"player_{slot}_history_profile_season"]
        for row in rows for slot in (1, 2)
        if row[f"player_{slot}_history_profile_season"]
    )
    gaps = Counter(
        str(row[f"player_{slot}_history_gap"])
        for row in rows for slot in (1, 2)
        if row[f"player_{slot}_history_gap"] is not None
    )
    return rows, {
        "history_status_rows": {key: history.get(key, 0) for key in ("complete", "one_missing", "both_missing")},
        "selected_profile_seasons_all_slots": dict(sorted(selected_seasons.items())),
        "history_lookback_age_all_slots": dict(sorted(gaps.items(), key=lambda item: int(item[0]))),
        "slot_selected_profile_seasons": {
            str(slot): dict(sorted(Counter(
                row[f"player_{slot}_history_profile_season"] for row in rows
                if row[f"player_{slot}_history_profile_season"]
            ).items())) for slot in (1, 2)
        },
        "slot_history_lookback_age": {
            str(slot): dict(sorted(Counter(
                str(row[f"player_{slot}_history_gap"]) for row in rows
                if row[f"player_{slot}_history_gap"] is not None
            ).items(), key=lambda item: int(item[0]))) for slot in (1, 2)
        },
    }


def _swap_player_slots(row: dict) -> dict:
    swapped = dict(row)
    for key in row:
        if key.startswith("player_1_"):
            swapped[key] = row.get("player_2_" + key[len("player_1_"):])
        elif key.startswith("player_2_"):
            swapped[key] = row.get("player_1_" + key[len("player_2_"):])
    return swapped


def prepare_estimator_features(training_csv: Path, rows: list[dict]) -> tuple[np.ndarray, dict, dict]:
    """Reproduce Phase 3D preprocessing without creating an estimator."""
    _require_hash(training_csv, TRAINING_CSV_SHA256)
    with training_csv.open(newline="", encoding="utf-8") as handle:
        training_rows = list(csv.DictReader(handle))
    if len(training_rows) != 27001 or {row["target_season"] for row in training_rows} != set(phase3d.ALLOWED_TARGET_SEASONS):
        raise FrozenContractViolation("training-era preprocessing population mismatch")
    manifest = phase3b.feature_manifest()
    names = phase3d.feature_lists(manifest)["no_shot"]
    if len(names) != 45 or len(set(names)) != 45:
        raise FrozenContractViolation("frozen no-shot feature count is not 45")
    violations = sorted(
        name for name in names
        if name in PROHIBITED_EXACT or any(token in name.lower() for token in PROHIBITED_SUBSTRINGS)
    )
    if violations:
        raise FrozenContractViolation(f"prohibited estimator columns: {violations}")
    prepared = phase3d.prepare_matrices(training_rows, rows, "no_shot", scale=True, manifest=manifest)
    matrix = prepared["validation_x"]
    if matrix.shape != (len(rows), 45) or not np.isfinite(matrix).all():
        raise FrozenContractViolation(f"estimator matrix shape/finite contract failed: {matrix.shape}")

    swap_mismatches = 0
    for row in rows:
        original = phase3d.transform_row(row, prepared["base_slot_medians"], "no_shot", manifest=manifest)
        swapped = phase3d.transform_row(_swap_player_slots(row), prepared["base_slot_medians"], "no_shot", manifest=manifest)
        if original != swapped:
            swap_mismatches += 1
    if swap_mismatches:
        raise FrozenContractViolation(f"player-slot swap changed features for {swap_mismatches} rows")
    scaler = prepared["scaler"]
    state = {
        "preprocessing_training_target_seasons": list(phase3d.ALLOWED_TARGET_SEASONS),
        "training_rows": len(training_rows),
        "unique_training_profiles": prepared["unique_training_profiles"],
        "feature_order": list(names),
        "player_slot_medians": prepared["base_slot_medians"],
        "symmetric_feature_medians": prepared["symmetric_feature_medians"],
        "scaler_mean": dict(zip(names, map(float, scaler.mean_))),
        "scaler_scale": dict(zip(names, map(float, scaler.scale_))),
        "training_derived_only": True,
        "holdout_predictors_or_targets_used_to_fit_preprocessing": False,
    }
    diagnostics = {
        "second_stage_symmetric_imputation_required_training_rows": int(prepared["second_stage_train"].sum()),
        "second_stage_symmetric_imputation_required_holdout_rows": int(prepared["second_stage_validation"].sum()),
        "second_stage_requirement_by_history": dict(sorted(Counter(
            row["history_status"] for row, required in zip(rows, prepared["second_stage_validation"]) if required
        ).items())),
        "slot_swap_rows_checked": len(rows),
        "slot_swap_feature_values_checked": len(rows) * len(names),
        "slot_swap_mismatches": swap_mismatches,
    }
    return matrix, state, diagnostics


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str] | tuple[str, ...] | None = None) -> dict:
    if fieldnames is None:
        fieldnames = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})
    return {"relative_path": path.name, "rows": len(rows), "columns": len(fieldnames), "serialized_byte_sha256": sha256_file(path)}


def _write_json(path: Path, value: dict) -> dict:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return {"relative_path": path.name, "serialized_byte_sha256": sha256_file(path)}


def _population_summary(raw_rows: list[dict], team_diagnostics: list[dict]) -> dict:
    excluded_raw = [row for row in raw_rows if row["team_id"] in EXCLUDED_TEAMS]
    retained_raw = [row for row in raw_rows if row["team_id"] not in EXCLUDED_TEAMS]
    excluded_eligible = [row for row in excluded_raw if row["pair_possessions"] >= ELIGIBILITY_THRESHOLD]
    retained_eligible = [row for row in retained_raw if row["pair_possessions"] >= ELIGIBILITY_THRESHOLD]
    all_poss = sum(row["pair_possessions"] for row in raw_rows)
    excluded_poss = sum(row["pair_possessions"] for row in excluded_raw)
    retained_poss = sum(row["pair_possessions"] for row in retained_raw)
    eligible_poss = sum(row["pair_possessions"] for row in retained_eligible)
    excluded_eligible_poss = sum(row["pair_possessions"] for row in excluded_eligible)
    by_team = {row["team_id"]: row for row in team_diagnostics}
    return {
        "all_30_teams_raw_pair_rows": len(raw_rows),
        "all_30_teams_summed_possessions": all_poss,
        "excluded_teams": {
            team_id: {
                "team_name": EXCLUDED_TEAMS[team_id],
                "raw_pair_rows": by_team[team_id]["advanced_raw_rows"],
                "eligible_poss_ge_150_rows": by_team[team_id]["eligible_poss_ge_150_rows"],
                "summed_possessions": by_team[team_id]["summed_possessions"],
                "eligible_summed_possessions": by_team[team_id]["eligible_summed_possessions"],
            } for team_id in sorted(EXCLUDED_TEAMS, key=int)
        },
        "remaining_28_team_raw_pair_rows": len(retained_raw),
        "remaining_28_team_eligible_poss_ge_150_rows": len(retained_eligible),
        "remaining_28_team_summed_possessions": retained_poss,
        "remaining_28_team_eligible_summed_possessions": eligible_poss,
        "retained_versus_excluded_shares": {
            "raw_pair_rows": {
                "retained_count": len(retained_raw), "excluded_count": len(excluded_raw),
                "retained_share": len(retained_raw) / len(raw_rows), "excluded_share": len(excluded_raw) / len(raw_rows),
            },
            "raw_summed_possessions": {
                "retained": retained_poss, "excluded": excluded_poss,
                "retained_share": retained_poss / all_poss, "excluded_share": excluded_poss / all_poss,
            },
            "eligible_pair_rows": {
                "retained_count": len(retained_eligible), "excluded_count": len(excluded_eligible),
                "retained_share": len(retained_eligible) / (len(retained_eligible) + len(excluded_eligible)),
                "excluded_share": len(excluded_eligible) / (len(retained_eligible) + len(excluded_eligible)),
            },
            "eligible_summed_possessions": {
                "retained": eligible_poss, "excluded": excluded_eligible_poss,
                "retained_share": eligible_poss / (eligible_poss + excluded_eligible_poss),
                "excluded_share": excluded_eligible_poss / (eligible_poss + excluded_eligible_poss),
            },
        },
    }


def verify_prerequisite_documents(project_root: Path) -> dict[str, str]:
    paths = {
        "phase3d_selection": (project_root / "modeling/phase3d/selection_decision.json", PHASE3D_SELECTION_SHA256),
        "phase3e_r1_result": (project_root / "modeling/phase3e-r1/philadelphia_evidence.json", R1_RESULT_SHA256),
        "phase3e_r1_policy": (project_root / "PHASE3E_R1_INCOMPLETE_TEAM_SEASON_POLICY.md", R1_POLICY_SHA256),
        "phase3e_r1_report": (project_root / "PHASE3E_R1_PHILADELPHIA_EVIDENCE_REPORT.md", R1_REPORT_SHA256),
    }
    result = {}
    for name, (path, expected) in paths.items():
        _require_hash(path, expected)
        result[name] = expected
    decision = _read_json(paths["phase3d_selection"][0])["selected_candidate"]
    if not (
        decision["estimator"] == "ridge" and decision["feature_variant"] == "no_shot"
        and decision["threshold"] == 150 and decision["weight_policy"] == "equal"
        and decision["exact_250_policy"] == "include"
        and {item["alpha"] for item in decision["fold_parameters"].values()} == {3000.0}
    ):
        raise FrozenContractViolation("Phase 3D frozen selection does not match Phase 3E-R2 contract")
    r1 = _read_json(paths["phase3e_r1_result"][0])
    if r1.get("primary_classification") != "Philadelphia full-season response proven non-exhaustive":
        raise FrozenContractViolation("Phase 3E-R1 exclusion evidence mismatch")
    return result


def build(project_root: Path | str = ".", output_dir: Path | str = "curated/phase3e-r2") -> dict:
    project_root, output_dir = Path(project_root), Path(output_dir)
    cache_root = project_root / "cache"
    training_csv = project_root / "curated/phase3b/phase3b_poss_ge_150.csv"
    reject_protected_paths(project_root, output_dir, cache_root, training_csv)
    with phase3a.network_prohibited():
        prerequisite_hashes = verify_prerequisite_documents(project_root)
        raw_rows, population_diagnostics, input_fingerprints = load_holdout_population(cache_root)
        profiles, profile_sources, profile_fingerprints = load_prior_profiles(cache_root)
        input_fingerprints.update(profile_fingerprints)
        rows, history_diagnostics = curate_rows(raw_rows, profiles, profile_sources)
        matrix, preprocessing_state, imputation_diagnostics = prepare_estimator_features(training_csv, rows)
    if len({row["team_id"] for row in rows}) != 28 or any(row["team_id"] in EXCLUDED_TEAMS for row in rows):
        raise FrozenContractViolation("holdout population is not exactly the 28 retained teams")

    team_diagnostics = population_diagnostics["original_cached_team_seasons"]
    population_diagnostics.update(_population_summary(raw_rows, team_diagnostics))
    population_diagnostics.update(history_diagnostics)
    population_diagnostics["row_issue_totals"] = {
        field: sum(item[field] for item in team_diagnostics) for field in (
            "duplicate_pair_rows", "malformed_pair_rows", "same_player_rows", "missing_target_rows",
            "nonfinite_target_rows", "missing_possession_rows", "nonpositive_possession_rows",
        )
    }
    population_diagnostics["second_stage_imputation"] = imputation_diagnostics

    feature_names = preprocessing_state["feature_order"]
    feature_manifest = {
        "version": VERSION,
        "estimator_family": "Ridge",
        "alpha": 3000.0,
        "eligibility_threshold_possessions": 150,
        "training_weight_policy": "equal",
        "exact_250_policy": "not an independent exclusion; Charlotte and Philadelphia excluded only under adjudicated non-exhaustive-team policy",
        "target": "observed full-season shared-court NET_RATING",
        "feature_variant": "no_shot",
        "estimator_feature_count": len(feature_names),
        "ordered_estimator_features": feature_names,
        "estimator_matrix_columns": feature_names,
        "prohibited_exact_columns_absent": sorted(PROHIBITED_EXACT),
        "prohibited_substrings_absent": list(PROHIBITED_SUBSTRINGS),
        "all_features_symmetric": True,
        "slot_swap_proof": imputation_diagnostics,
        "preprocessing": "player-slot medians, symmetric-feature medians, and Ridge scaling learned only from 2014-15 through 2023-24 Phase 3B training rows",
        "holdout_target_used_for_preprocessing": False,
    }
    feature_manifest["deterministic_content_sha256"] = canonical_content_hash(feature_manifest)
    preprocessing_state["deterministic_content_sha256"] = canonical_content_hash(preprocessing_state)
    population_diagnostics["deterministic_content_sha256"] = canonical_content_hash(population_diagnostics)

    current_fingerprints = {relative: sha256_file(cache_root / relative) for relative in sorted(input_fingerprints)}
    if current_fingerprints != dict(sorted(input_fingerprints.items())):
        raise FrozenContractViolation("raw-cache fingerprints changed during construction")
    fingerprint_document = {
        "referenced_cache_files": current_fingerprints,
        "referenced_cache_file_count": len(current_fingerprints),
        "unchanged_during_construction": True,
    }
    fingerprint_document["deterministic_content_sha256"] = canonical_content_hash(fingerprint_document)

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    artifacts["holdout_staging"] = _write_csv(output_dir / "holdout_staging.csv", rows)
    index_fields = [
        "target_season", "team_id", "team_name", "player_1_id", "player_2_id", "target_net_rating",
        "pair_possessions", "pair_base_minutes", "history_status", "missing_player_count",
        "player_1_history_profile_season", "player_1_history_gap", "player_2_history_profile_season",
        "player_2_history_gap", "endpoint_exact_250_flag",
    ]
    artifacts["holdout_row_index"] = _write_csv(output_dir / "holdout_row_index.csv", rows, index_fields)
    matrix_rows = [dict(zip(feature_names, map(float, vector))) for vector in matrix]
    artifacts["holdout_estimator_matrix"] = _write_csv(output_dir / "holdout_estimator_matrix.csv", matrix_rows, feature_names)
    artifacts["estimator_feature_manifest"] = _write_json(output_dir / "estimator_feature_manifest.json", feature_manifest)
    artifacts["population_diagnostics"] = _write_json(output_dir / "population_diagnostics.json", population_diagnostics)
    artifacts["preprocessing_state"] = _write_json(output_dir / "preprocessing_state.json", preprocessing_state)
    artifacts["input_fingerprints"] = _write_json(output_dir / "input_fingerprints.json", fingerprint_document)

    artifact_hashes = {
        "version": VERSION,
        "payload_artifacts": {name: record["serialized_byte_sha256"] for name, record in sorted(artifacts.items())},
        "excluded_from_own_byte_manifest": ["artifact_hashes.json", "summary.json"],
    }
    artifact_hashes["deterministic_content_sha256"] = canonical_content_hash(artifact_hashes)
    artifact_hash_record = _write_json(output_dir / "artifact_hashes.json", artifact_hashes)
    summary = {
        "version": VERSION,
        "classification": "2024-25 holdout dataset constructed; ready for read-only audit",
        "scope": "deterministic cache-only holdout construction and training-derived preprocessing; no estimator, predictions, or performance metrics",
        "required_starting_head": REQUIRED_STARTING_HEAD,
        "network": "prohibited",
        "final_test_season_accessed": False,
        "target_season": TARGET_SEASON,
        "target_usage": "retained unevaluated and checked only for presence/numeric finiteness",
        "feature_source_seasons": sorted(profiles),
        "training_preprocessing_target_seasons": list(phase3d.ALLOWED_TARGET_SEASONS),
        "original_team_seasons": 30,
        "retained_team_seasons": 28,
        "excluded_team_ids": sorted(EXCLUDED_TEAMS, key=int),
        "retained_rows": len(rows),
        "feature_count": len(feature_names),
        "prerequisite_hashes": prerequisite_hashes,
        "artifacts": artifacts | {"artifact_hashes": artifact_hash_record},
        "artifact_manifest_content_sha256": artifact_hashes["deterministic_content_sha256"],
    }
    summary["deterministic_content_sha256"] = canonical_content_hash(summary)
    _write_json(output_dir / "summary.json", summary)
    return summary
