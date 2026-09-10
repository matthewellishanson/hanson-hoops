"""Offline deterministic curation and feature contract for Pair Fit v2 Phase 3B.

This module deliberately stops at a row-preserving, historically available
source table.  It does not impute, scale, fit, select, or evaluate anything.
The CSV outputs contain player slots and audit metadata; their order-sensitive
slots are *not* estimator inputs.  The manifest defines the later symmetric
feature contract and the required fold-safe ordering.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from pair_fit_v2 import phase3a1_shot_zone_acquisition as phase3a1
from pair_fit_v2 import phase3a_population_audit as phase3a
from pair_fit_v2.phase1c_manifest import canonical_json_hash


VERSION = "phase3b.deterministic-curation-feature-spec.v1"
PRIMARY_THRESHOLD = 150
SENSITIVITY_THRESHOLD = 100
MAX_HISTORY_LOOKBACK = 3
RATING_TOLERANCE = 0.1000001
ZONE_KEYS = (
    "restricted_area",
    "non_restricted_paint",
    "mid_range",
    "left_corner_three",
    "right_corner_three",
    "above_the_break_three",
    "backcourt",
)
ZONE_LABELS = dict(zip(ZONE_KEYS, phase3a1.EXPECTED_ZONES))
PRIMARY_SHOT_SHARE_NAMES = (
    "restricted_area_attempt_share_overall",
    "non_restricted_paint_attempt_share_overall",
    "mid_range_attempt_share_overall",
    "combined_corner_three_attempt_share_overall",
    "above_the_break_three_attempt_share_overall",
    "overall_three_point_location_share_overall",
    "unclassified_attempt_share_overall",
    "classified_attempt_coverage",
)

# These are all player-period inputs, never target-period pair inputs.  Raw
# percentage columns and REB are intentionally omitted because they duplicate
# retained count fields or their component counts.
PLAYER_NUMERIC_INPUTS = (
    "AGE", "GP", "TOTAL_MIN", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA",
    "OREB", "DREB", "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS",
    "PLUS_MINUS", "TEAM_COUNT",
)
PLAYER_DERIVED_INPUTS = (
    "effective_field_goal_pct",
    "true_shooting_pct",
    "three_point_attempt_rate",
    "free_throw_rate",
    "traded_player_indicator",
)
CONTINUOUS_PAIR_INPUTS = PLAYER_NUMERIC_INPUTS[:-1] + PLAYER_DERIVED_INPUTS[:-1]
RELIABILITY_PLAYER_INPUTS = ("GP", "TOTAL_MIN")
ESTIMATOR_CONTINUOUS_INPUTS = tuple(
    field for field in CONTINUOUS_PAIR_INPUTS if field not in RELIABILITY_PLAYER_INPUTS
)
SHOT_L1_COMPONENTS = (
    "restricted_area", "non_restricted_paint", "mid_range",
    "combined_corner_three", "above_the_break_three", "backcourt", "unclassified",
)


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def safe_rate(numerator, denominator):
    """Leave zero/unknown denominators undefined; never turn them into 0%."""
    numerator, denominator = _number(numerator), _number(denominator)
    return None if numerator is None or denominator is None or denominator <= 0 else numerator / denominator


def derived_player_inputs(profile):
    """Count-based prior-player derivations with explicit safe denominators."""
    fgm, fga = _number(profile.get("FGM")), _number(profile.get("FGA"))
    fg3m, fg3a = _number(profile.get("FG3M")), _number(profile.get("FG3A"))
    pts, fta = _number(profile.get("PTS")), _number(profile.get("FTA"))
    return {
        "effective_field_goal_pct": safe_rate(None if fgm is None or fg3m is None else fgm + 0.5 * fg3m, fga),
        "true_shooting_pct": safe_rate(pts, None if fga is None or fta is None else 2 * (fga + 0.44 * fta)),
        "three_point_attempt_rate": safe_rate(fg3a, fga),
        "free_throw_rate": safe_rate(fta, fga),
        "traded_player_indicator": traded_history_indicator(profile.get("TEAM_COUNT")),
    }


def traded_history_indicator(team_count):
    """Return 0/1 only for a valid positive integral team count; otherwise null."""
    value = _number(team_count)
    if value is None or value <= 0 or not value.is_integer():
        return None
    return int(value > 1)


def pair_traded_history_count(left, right):
    """Known-only sum of two slot-level traded-history indicators."""
    if left not in (0, 1) or right not in (0, 1):
        return None
    return left + right


def shot_distribution_l1_distance_overall_fga(left, right):
    """L1 distance over seven mutually exclusive overall-FGA shot shares.

    ``left`` and ``right`` use the materialized slot suffixes, for example
    ``shot_restricted_area_fga`` and ``shot_overall_fga``.  Missing profiles
    and zero/nonpositive overall FGA remain null rather than becoming zeros.
    """
    def vector(profile):
        overall = _number(profile.get("shot_overall_fga"))
        if overall is None or overall <= 0:
            return None
        numerators = {
            "restricted_area": _number(profile.get("shot_restricted_area_fga")),
            "non_restricted_paint": _number(profile.get("shot_non_restricted_paint_fga")),
            "mid_range": _number(profile.get("shot_mid_range_fga")),
            "combined_corner_three": None,
            "above_the_break_three": _number(profile.get("shot_above_the_break_three_fga")),
            "backcourt": _number(profile.get("shot_backcourt_fga")),
            "unclassified": _number(profile.get("shot_unclassified_fga")),
        }
        left_corner = _number(profile.get("shot_left_corner_three_fga"))
        right_corner = _number(profile.get("shot_right_corner_three_fga"))
        if left_corner is None or right_corner is None:
            return None
        numerators["combined_corner_three"] = left_corner + right_corner
        if any(value is None or value < 0 for value in numerators.values()):
            return None
        return {key: value / overall for key, value in numerators.items()}
    left_vector, right_vector = vector(left), vector(right)
    if left_vector is None or right_vector is None:
        return None
    return sum(abs(left_vector[key] - right_vector[key]) for key in SHOT_L1_COMPONENTS)


def symmetric_pair_features(left, right, fields):
    """Order-invariant primitives for a later post-imputation pipeline.

    This intentionally does not fill a missing slot.  A caller must first fit
    and apply a training-fold-only slot imputer, then pass the completed slots
    here.  It exists to make the no-order-sensitive-estimator rule testable.
    """
    result = {}
    for field in fields:
        a, b = _number(left.get(field)), _number(right.get(field))
        result[f"pair_mean.{field}"] = None if a is None or b is None else (a + b) / 2
        result[f"pair_absolute_difference.{field}"] = None if a is None or b is None else abs(a - b)
    return result


def _phase_paths(cache_root: Path):
    return {
        **{season: cache_root / "phase2e" / season / "manifest.json" for season in phase3a.WINDOW[:7]},
        "2021-22": cache_root / "phase2d" / "manifest.json",
        "2022-23": cache_root / "phase2c" / "manifest.json",
        "2023-24": cache_root / "phase2b" / "release_manifest.json",
    }


def _cache_reference(asset):
    cache = asset.get("cache") or asset.get("source_reference")
    # Phase 2B's two reused player dependencies predate the nested ``cache``
    # shape.  Their flattened source_cache_path/raw_body_hash are immutable
    # evidence just like the later nested form.
    cache = cache or asset
    relative_path = cache.get("relative_path") or cache.get("source_cache_path")
    raw_hash = cache.get("raw_body_hash")
    if not relative_path or not raw_hash:
        raise ValueError("source asset missing immutable cache path/hash")
    return {
        "asset_id": asset.get("asset_id") or asset.get("source_asset_id") or f"source:{canonical_json_hash(asset.get('identity') or asset.get('source_identity'))}",
        "relative_path": relative_path,
        "raw_body_hash": raw_hash,
    }


def _source_provenance(cache_root: Path):
    """Index immutable raw evidence without altering the Phase 3A loader."""
    pair_sources, player_sources = {}, {}
    for target_season, path in _phase_paths(cache_root).items():
        manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        assets = manifest.get("assets") or manifest.get("pair_assets")
        for asset in assets:
            identity = asset.get("identity", {})
            if identity.get("endpoint") != "TeamDashLineups":
                continue
            params = identity["parameters"]
            pair_sources[(target_season, str(params["team_id"]), params["measure_type"])] = _cache_reference(asset)
        dependencies = manifest.get("player_dependencies") or [
            asset for asset in assets if asset.get("identity", {}).get("endpoint") == "LeagueDashPlayerStats"
        ]
        profile_season = f"{int(target_season[:4]) - 1}-{target_season[2:4]}"
        modes = {}
        for asset in dependencies:
            identity = asset.get("identity") or asset.get("source_identity")
            modes[identity["parameters"]["per_mode"]] = _cache_reference(asset)
        if set(modes) != {"Per100Possessions", "Totals"}:
            raise ValueError(f"player source provenance incomplete for {profile_season}")
        player_sources[profile_season] = modes
    return pair_sources, player_sources


def _totals_profiles(cache_root: Path, player_sources):
    totals = {}
    for season, sources in player_sources.items():
        source = sources["Totals"]
        body = (cache_root / source["relative_path"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != source["raw_body_hash"]:
            raise ValueError(f"player Totals raw hash mismatch: {season}")
        totals[season] = {phase3a._id(row["PLAYER_ID"]): row for row in phase3a._rows(json.loads(body), "LeagueDashPlayerStats")}
    return totals


def _shot_profiles(cache_root: Path, profiles, totals_profiles):
    """Parse verified residual-v1 aggregate zone vectors by player-season."""
    manifest = phase3a1.load(cache_root, "manifest")
    result = {}
    for asset in manifest["assets"]:
        season = asset["season"]
        if asset["status"] not in {"verified", "verified_reviewed_promotion"}:
            raise ValueError(f"shot profile is not verified: {season}")
        # 2023-24 was acquired as the Phase 3A.1 canary and is replayed above,
        # but cannot be a prior profile for this 2014-15--2023-24 target
        # window.  Do not join it merely because it exists locally.
        if season not in profiles:
            continue
        cache = asset["cache"]
        body = (cache_root / cache["body_path"]).read_bytes()
        raw_hash = cache.get("raw_body_hash") or cache.get("raw_body_sha256")
        if hashlib.sha256(body).hexdigest() != raw_hash:
            raise ValueError(f"shot raw hash mismatch: {season}")
        payload = json.loads(body)
        # Semantic replay has already checked residual direction, source nulls,
        # percentages, and the overlapping Corner 3 identity.  Parsing here is
        # label-based and retains the null evidence for the materialized table.
        nested = payload["resultSets"]
        categories = nested["headers"][0]["columnNames"]
        if tuple(categories[:7]) != phase3a1.EXPECTED_ZONES or categories[7] != "Corner 3":
            raise ValueError(f"shot category drift: {season}")
        by_player = {}
        totals = totals_profiles.get(season, {})
        for raw in nested["rowSet"]:
            player_id = phase3a._id(raw[0])
            if player_id in by_player or player_id not in totals:
                raise ValueError(f"shot/player profile ID reconciliation failed: {season}/{player_id}")
            zones, source_null = {}, {}
            for index, key in enumerate(ZONE_KEYS):
                made, attempts, pct = raw[6 + index * 3: 9 + index * 3]
                paired_null = made is None and attempts is None
                if (made is None) != (attempts is None):
                    raise ValueError(f"one-sided shot source null: {season}/{player_id}/{key}")
                if paired_null:
                    made, attempts = 0, 0
                if int(made) != made or int(attempts) != attempts or made < 0 or attempts < 0 or made > attempts:
                    raise ValueError(f"invalid shot counts: {season}/{player_id}/{key}")
                zones[key] = {"fgm": int(made), "fga": int(attempts)}
                source_null[key] = int(paired_null)
            left, right = zones["left_corner_three"], zones["right_corner_three"]
            corner_m, corner_a, _ = raw[6 + 7 * 3: 9 + 7 * 3]
            if corner_m is None and corner_a is None:
                corner_m, corner_a = 0, 0
            if (corner_m, corner_a) != (left["fgm"] + right["fgm"], left["fga"] + right["fga"]):
                raise ValueError(f"Corner 3 aggregate mismatch: {season}/{player_id}")
            overall_m, overall_a = _number(totals[player_id].get("FGM")), _number(totals[player_id].get("FGA"))
            classified_m = sum(zone["fgm"] for zone in zones.values())
            classified_a = sum(zone["fga"] for zone in zones.values())
            unclassified_m, unclassified_a = int(overall_m) - classified_m, int(overall_a) - classified_a
            if unclassified_m < 0 or unclassified_a < 0 or unclassified_m > unclassified_a:
                raise ValueError(f"invalid residual profile: {season}/{player_id}")
            by_player[player_id] = {
                "zones": zones,
                "source_null": source_null,
                "overall_fgm": int(overall_m), "overall_fga": int(overall_a),
                "unclassified_fgm": unclassified_m, "unclassified_fga": unclassified_a,
                "classified_fgm": classified_m, "classified_fga": classified_a,
                "source_path": cache["body_path"], "source_raw_body_hash": raw_hash,
            }
        if set(by_player) != set(totals):
            raise ValueError(f"shot profile player set mismatch: {season}")
        result[season] = by_player
    return result


def _select_history(target_season, player_id, profiles):
    target_year = int(target_season[:4])
    choices = []
    for profile_season, by_player in profiles.items():
        gap = target_year - int(profile_season[:4])
        if 1 <= gap <= MAX_HISTORY_LOOKBACK and player_id in by_player:
            choices.append((gap, profile_season, by_player[player_id]))
    if not choices:
        return None, None, None
    gap, season, profile = min(choices, key=lambda item: item[0])
    return season, gap, profile


def _slot_values(slot, target_season, player_id, profiles, shot_profiles, player_sources):
    profile_season, gap, profile = _select_history(target_season, player_id, profiles)
    out = {
        f"player_{slot}_history_missing": int(profile is None),
        f"player_{slot}_history_profile_season": profile_season,
        f"player_{slot}_history_gap": gap,
        f"player_{slot}_profile_source_per100_path": None,
        f"player_{slot}_profile_source_totals_path": None,
        f"player_{slot}_profile_source_per100_hash": None,
        f"player_{slot}_profile_source_totals_hash": None,
        f"player_{slot}_shot_source_path": None,
        f"player_{slot}_shot_source_hash": None,
    }
    for field in PLAYER_NUMERIC_INPUTS + PLAYER_DERIVED_INPUTS:
        out[f"player_{slot}_{field.lower()}"] = None
    for key in ZONE_KEYS:
        for suffix in ("fgm", "fga", "source_null", "attempted_zone"):
            out[f"player_{slot}_shot_{key}_{suffix}"] = None
        out[f"player_{slot}_shot_{key}_attempt_share_classified"] = None
    for suffix in ("fgm", "fga", "attempted_zone"):
        out[f"player_{slot}_shot_overall_{suffix}"] = None
        out[f"player_{slot}_shot_unclassified_{suffix}"] = None
    for field in ("classified_fgm", "classified_fga", "classified_attempt_coverage") + PRIMARY_SHOT_SHARE_NAMES[:-1]:
        out[f"player_{slot}_shot_{field}"] = None
    if profile is None:
        return out
    source = player_sources[profile_season]
    out.update({
        f"player_{slot}_profile_source_per100_path": source["Per100Possessions"]["relative_path"],
        f"player_{slot}_profile_source_totals_path": source["Totals"]["relative_path"],
        f"player_{slot}_profile_source_per100_hash": source["Per100Possessions"]["raw_body_hash"],
        f"player_{slot}_profile_source_totals_hash": source["Totals"]["raw_body_hash"],
    })
    for field in PLAYER_NUMERIC_INPUTS:
        out[f"player_{slot}_{field.lower()}"] = _number(profile.get(field))
    for field, value in derived_player_inputs(profile).items():
        out[f"player_{slot}_{field}"] = value
    shot = shot_profiles.get(profile_season, {}).get(player_id)
    if shot is None:
        raise ValueError(f"verified shot profile unavailable for selected history: {profile_season}/{player_id}")
    out[f"player_{slot}_shot_source_path"] = shot["source_path"]
    out[f"player_{slot}_shot_source_hash"] = shot["source_raw_body_hash"]
    for key, zone in shot["zones"].items():
        out[f"player_{slot}_shot_{key}_fgm"] = zone["fgm"]
        out[f"player_{slot}_shot_{key}_fga"] = zone["fga"]
        out[f"player_{slot}_shot_{key}_source_null"] = shot["source_null"][key]
        out[f"player_{slot}_shot_{key}_attempted_zone"] = int(zone["fga"] > 0)
        out[f"player_{slot}_shot_{key}_attempt_share_classified"] = safe_rate(zone["fga"], shot["classified_fga"])
    overall_a = shot["overall_fga"]
    for name, numerator in {
        "restricted_area_attempt_share_overall": shot["zones"]["restricted_area"]["fga"],
        "non_restricted_paint_attempt_share_overall": shot["zones"]["non_restricted_paint"]["fga"],
        "mid_range_attempt_share_overall": shot["zones"]["mid_range"]["fga"],
        "combined_corner_three_attempt_share_overall": shot["zones"]["left_corner_three"]["fga"] + shot["zones"]["right_corner_three"]["fga"],
        "above_the_break_three_attempt_share_overall": shot["zones"]["above_the_break_three"]["fga"],
        "overall_three_point_location_share_overall": shot["zones"]["left_corner_three"]["fga"] + shot["zones"]["right_corner_three"]["fga"] + shot["zones"]["above_the_break_three"]["fga"],
        "unclassified_attempt_share_overall": shot["unclassified_fga"],
    }.items():
        out[f"player_{slot}_shot_{name}"] = safe_rate(numerator, overall_a)
    for label, made, attempts in (("overall", shot["overall_fgm"], shot["overall_fga"]), ("unclassified", shot["unclassified_fgm"], shot["unclassified_fga"])):
        out[f"player_{slot}_shot_{label}_fgm"] = made
        out[f"player_{slot}_shot_{label}_fga"] = attempts
        out[f"player_{slot}_shot_{label}_attempted_zone"] = int(attempts > 0)
    out[f"player_{slot}_shot_classified_fgm"] = shot["classified_fgm"]
    out[f"player_{slot}_shot_classified_fga"] = shot["classified_fga"]
    out[f"player_{slot}_shot_classified_attempt_coverage"] = safe_rate(shot["classified_fga"], overall_a)
    return out


def _row_values(raw, profiles, shot_profiles, pair_sources, player_sources):
    season, team_id, (player_1, player_2) = raw["season"], raw["team_id"], raw["pair"]
    base_source = pair_sources[(season, team_id, "Base")]
    advanced_source = pair_sources[(season, team_id, "Advanced")]
    poss = _number(raw["POSS"])
    off, defense, net = _number(raw["OFF_RATING"]), _number(raw["DEF_RATING"]), _number(raw["NET_RATING"])
    if poss is None or off is None or defense is None or net is None:
        raise ValueError(f"invalid target/exposure values: {season}/{team_id}/{player_1}/{player_2}")
    if abs(net - (off - defense)) > RATING_TOLERANCE:
        raise ValueError(f"NET_RATING identity failed: {season}/{team_id}/{player_1}/{player_2}")
    row = {
        "target_season": season, "team_id": team_id, "player_1_id": player_1, "player_2_id": player_2,
        "raw_pair_base_asset_id": base_source["asset_id"], "raw_pair_advanced_asset_id": advanced_source["asset_id"],
        "raw_pair_base_path": base_source["relative_path"], "raw_pair_advanced_path": advanced_source["relative_path"],
        "raw_pair_base_hash": base_source["raw_body_hash"], "raw_pair_advanced_hash": advanced_source["raw_body_hash"],
        "target_net_rating": net, "target_off_rating_audit": off, "target_def_rating_audit": defense,
        "pair_possessions": poss, "pair_base_minutes": _number(raw.get("base_min")),
        "eligible_poss_ge_100": int(poss >= SENSITIVITY_THRESHOLD), "eligible_poss_ge_150": int(poss >= PRIMARY_THRESHOLD),
        "candidate_weight_equal_row": 1.0, "candidate_weight_sqrt_possessions": math.sqrt(poss),
        "candidate_weight_possessions_capped_300": min(poss, 300.0),
        "endpoint_exact_250_flag": int(raw["endpoint_boundary_250"]),
        "pandemic_affected_season_flag": int(season in {"2019-20", "2020-21"}),
    }
    row.update(_slot_values(1, season, player_1, profiles, shot_profiles, player_sources))
    row.update(_slot_values(2, season, player_2, profiles, shot_profiles, player_sources))
    missing = row["player_1_history_missing"] + row["player_2_history_missing"]
    status = ("complete" if missing == 0 else "one_missing" if missing == 1 else "both_missing")
    row.update({
        "missing_player_count": missing, "history_status": status,
        "strict_complete_history_eligible": int(status == "complete"),
    })
    return row


def _fieldnames(rows):
    return sorted({field for row in rows for field in row})


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _fieldnames(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})
    return {"relative_path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows), "columns": len(fieldnames)}


def feature_manifest():
    """The static allowlist and non-negotiable later-pipeline contract."""
    slot_numeric = [f"player_slot.{field.lower()}" for field in PLAYER_NUMERIC_INPUTS]
    slot_derived = [f"player_slot.{field}" for field in PLAYER_DERIVED_INPUTS]
    shot_counts = [f"player_slot.shot_{key}_{suffix}" for key in (*ZONE_KEYS, "overall", "unclassified") for suffix in ("fgm", "fga")]
    source_nulls = [f"player_slot.shot_{key}_source_null" for key in ZONE_KEYS]
    attempts = [f"player_slot.shot_{key}_attempted_zone" for key in (*ZONE_KEYS, "overall", "unclassified")]
    shot_estimator_shares = tuple(field for field in PRIMARY_SHOT_SHARE_NAMES if field not in {
        "overall_three_point_location_share_overall", "classified_attempt_coverage"
    })
    estimator = ([f"pair_mean.{field}" for field in ESTIMATOR_CONTINUOUS_INPUTS] +
                 [f"pair_absolute_difference.{field}" for field in ESTIMATOR_CONTINUOUS_INPUTS] +
                 ["pair_traded_history_count"] +
                 [f"pair_mean.shot_{field}" for field in shot_estimator_shares] +
                 ["pair_shot_distribution_l1_distance_overall_fga"])
    categories = {
        "identifiers": ["target_season", "team_id", "player_1_id", "player_2_id"],
        "target": ["target_net_rating"],
        "eligibility_exposure": ["pair_possessions", "pair_base_minutes", "eligible_poss_ge_100", "eligible_poss_ge_150"],
        "reliability_metadata": ["player_slot.gp", "player_slot.total_min"],
        "weight_candidates": ["candidate_weight_equal_row", "candidate_weight_sqrt_possessions", "candidate_weight_possessions_capped_300"],
        "player_attributes_and_production": [field for field in slot_numeric + slot_derived if field not in {"player_slot.gp", "player_slot.total_min"}],
        "shot_semantics": source_nulls,
        "missingness_metadata": ["player_1_history_missing", "player_2_history_missing", "missing_player_count", "history_status", "strict_complete_history_eligible"],
        "sensitivity_metadata": ["endpoint_exact_250_flag", "pandemic_affected_season_flag", "player_1_history_profile_season", "player_2_history_profile_season", "player_1_history_gap", "player_2_history_gap"],
        "audit_provenance": ["raw_pair_base_asset_id", "raw_pair_advanced_asset_id", "raw_pair_base_path", "raw_pair_advanced_path", "raw_pair_base_hash", "raw_pair_advanced_hash"],
        "estimator_predictors": estimator,
    }
    manifest = {
        "version": VERSION,
        "observation_grain": "team × target season × canonical unordered player pair",
        "target": {"allowlist": ["target_net_rating"], "raw_value_preserved": True,
                   "identity": "NET_RATING ~= OFF_RATING - DEF_RATING within 0.1"},
        "authoritative_categories": categories,
        "category_partition_note": "Each listed field/template has exactly one authoritative category. Descriptive tags, if added later, are non-authoritative.",
        "identifiers": categories["identifiers"],
        "exposure_fields": categories["eligibility_exposure"],
        "weight_candidates": categories["weight_candidates"],
        "reliability_metadata": categories["reliability_metadata"],
        "raw_player_inputs": {"numeric": slot_numeric, "derived": slot_derived,
                              "formulas": {"effective_field_goal_pct": "(FGM + 0.5*FG3M) / FGA",
                                           "true_shooting_pct": "PTS / (2*(FGA + 0.44*FTA))",
                                           "three_point_attempt_rate": "FG3A / FGA", "free_throw_rate": "FTA / FGA"},
                              "safe_denominator": "nonpositive or missing denominator -> null; no replacement during curation"},
        "shot_profile_raw_inputs": {"reconciliation_policy": phase3a1.RESIDUAL_RECONCILIATION_POLICY,
                                     "counts": shot_counts, "source_null_indicators": source_nulls,
                                     "attempt_indicators": attempts,
                                     "coverage": ["player_slot.shot_classified_fgm", "player_slot.shot_classified_fga", "player_slot.shot_classified_attempt_coverage"],
                                     "primary_overall_fga_shares": list(PRIMARY_SHOT_SHARE_NAMES),
                                     "classified_normalized_sensitivity": [f"shot_{key}_attempt_share_classified" for key in ZONE_KEYS],
                                     "corner_three_rule": "Left + Right only; source Corner 3 aggregate validates and is never summed as an input.",
                                     "zero_attempt_efficiency": "undefined/null; FGM/FGA counts and attempted_zone are retained for later fold-safe smoothing."},
        "future_estimator_features": estimator,
        "estimator_feature_specs": {
            "pair_traded_history_count": {"formula": "player_1_traded_player_indicator + player_2_traded_player_indicator", "input_columns": ["player_1_traded_player_indicator", "player_2_traded_player_indicator"], "valid_range": [0, 2], "null_behavior": "null unless both indicators are known 0 or 1"},
            "pair_shot_distribution_l1_distance_overall_fga": {"formula": "sum_z(abs(FGA_1,z/FGA_1,overall - FGA_2,z/FGA_2,overall)) over restricted area, non-restricted paint, mid-range, combined left+right corner three, above-the-break three, backcourt, and unclassified", "input_columns": ["player_[1|2]_shot_restricted_area_fga", "player_[1|2]_shot_non_restricted_paint_fga", "player_[1|2]_shot_mid_range_fga", "player_[1|2]_shot_left_corner_three_fga", "player_[1|2]_shot_right_corner_three_fga", "player_[1|2]_shot_above_the_break_three_fga", "player_[1|2]_shot_backcourt_fga", "player_[1|2]_shot_unclassified_fga", "player_[1|2]_shot_overall_fga"], "valid_range": [0, 2], "null_behavior": "null if either profile is missing, either overall FGA is missing/nonpositive, or any required component is missing; no missing component becomes zero", "excluded_inputs": ["aggregate overall three-point-location share", "classified-attempt coverage", "source Corner 3 aggregate", "classified-FGA-normalized sensitivity shares"]},
        },
        "missingness_indicators": categories["missingness_metadata"],
        "sensitivity_metadata": categories["sensitivity_metadata"],
        "prohibited_predictors": ["pair_possessions", "pair_base_minutes", "target_off_rating_audit", "target_def_rating_audit", "target_net_rating", "target-season pair pace/rating/minutes/statistics", "all identifiers", "raw pair asset provenance", "candidate weights", "rank columns", "fantasy fields", "high-score fields", "PLAYER_NAME", "prior shared-pair experience", "source Corner 3 aggregate"],
        "future_fold_contract": ["fit imputation only on training-fold player slots", "apply imputation separately and identically to both player slots", "construct symmetric transforms after imputation", "expose only symmetric transforms to the estimator", "fit any scaling only within training folds", "do not select features by full-window target association"],
    }
    validate_feature_manifest(manifest)
    return manifest


def _known_authoritative_columns():
    slot_numeric = {f"player_slot.{field.lower()}" for field in PLAYER_NUMERIC_INPUTS}
    slot_derived = {f"player_slot.{field}" for field in PLAYER_DERIVED_INPUTS}
    shot_nulls = {f"player_slot.shot_{key}_source_null" for key in ZONE_KEYS}
    shot_shares = tuple(field for field in PRIMARY_SHOT_SHARE_NAMES if field not in {
        "overall_three_point_location_share_overall", "classified_attempt_coverage"
    })
    predictors = ({f"pair_mean.{field}" for field in ESTIMATOR_CONTINUOUS_INPUTS} |
                  {f"pair_absolute_difference.{field}" for field in ESTIMATOR_CONTINUOUS_INPUTS} |
                  {"pair_traded_history_count", "pair_shot_distribution_l1_distance_overall_fga"} |
                  {f"pair_mean.shot_{field}" for field in shot_shares})
    return (slot_numeric | slot_derived | shot_nulls | predictors | {
        "target_season", "team_id", "player_1_id", "player_2_id", "target_net_rating", "pair_possessions", "pair_base_minutes", "eligible_poss_ge_100", "eligible_poss_ge_150", "candidate_weight_equal_row", "candidate_weight_sqrt_possessions", "candidate_weight_possessions_capped_300", "player_1_history_missing", "player_2_history_missing", "missing_player_count", "history_status", "strict_complete_history_eligible", "endpoint_exact_250_flag", "pandemic_affected_season_flag", "player_1_history_profile_season", "player_2_history_profile_season", "player_1_history_gap", "player_2_history_gap", "raw_pair_base_asset_id", "raw_pair_advanced_asset_id", "raw_pair_base_path", "raw_pair_advanced_path", "raw_pair_base_hash", "raw_pair_advanced_hash"
    })


def validate_feature_manifest(manifest):
    """Reject ambiguous category partitions and forbidden estimator overlap."""
    categories = manifest.get("authoritative_categories")
    required = {"identifiers", "target", "eligibility_exposure", "reliability_metadata", "weight_candidates", "estimator_predictors"}
    if not isinstance(categories, dict) or not required <= set(categories):
        raise ValueError("manifest missing required authoritative category")
    seen = {}
    known = _known_authoritative_columns()
    for category, fields in categories.items():
        if not isinstance(fields, list):
            raise ValueError(f"manifest category is not a list: {category}")
        for field in fields:
            if not isinstance(field, str) or not field:
                raise ValueError(f"manifest unknown referenced column in {category}")
            if field not in known:
                raise ValueError(f"manifest unknown referenced column in {category}: {field}")
            if field in seen:
                raise ValueError(f"manifest column assigned to multiple categories: {field}")
            seen[field] = category
    predictors = set(categories["estimator_predictors"])
    for category in ("identifiers", "target", "eligibility_exposure", "reliability_metadata", "weight_candidates"):
        if overlap := predictors & set(categories[category]):
            raise ValueError(f"manifest predictor overlap with {category}: {sorted(overlap)}")
    if overlap := predictors & set(manifest.get("prohibited_predictors", [])):
        raise ValueError(f"manifest predictor/prohibited overlap: {sorted(overlap)}")
    if set(manifest.get("future_estimator_features", [])) != predictors:
        raise ValueError("manifest estimator predictor allowlist differs from authoritative category")
    return {"valid": True, "authoritative_columns": len(seen), "categories": len(categories)}


def _coverage(rows):
    by_season = {}
    by_team = {}
    for label, predicate in (("100", lambda row: row["eligible_poss_ge_100"]), ("150", lambda row: row["eligible_poss_ge_150"])):
        by_season[label] = {}
        by_team[label] = {}
        for season in phase3a.WINDOW:
            selected = [row for row in rows if row["target_season"] == season and predicate(row)]
            statuses = Counter(row["history_status"] for row in selected)
            by_season[label][season] = {"retained_rows": len(selected), "history_status": dict(sorted(statuses.items()))}
        for season, team_id in sorted({(row["target_season"], row["team_id"]) for row in rows}, key=lambda x: (x[0], int(x[1]))):
            selected = [row for row in rows if row["target_season"] == season and row["team_id"] == team_id and predicate(row)]
            by_team[label][f"{season}|{team_id}"] = len(selected)
    return by_season, by_team


def build(cache_root: Path | str, output_dir: Path | str):
    """Replay prerequisites, curate >=100 rows, and materialize >=150 selection."""
    cache_root, output_dir = Path(cache_root), Path(output_dir)
    with phase3a.network_prohibited():
        phase3a_summary = phase3a.analyze(cache_root)
        shot_summary = phase3a1.analyze_residual_window(cache_root, policy=phase3a1.RESIDUAL_RECONCILIATION_POLICY)
        if phase3a_summary["deterministic_analysis_sha256"] != "dbe0b83dca9196e915b42223d47dd473988c42313a7cd8910448bb282f99054f":
            raise ValueError("Phase 3A prerequisite SHA-256 mismatch")
        if shot_summary["deterministic_analysis_sha256"] != "54743fee0db29f1847ecb46b2dae8ec07871d3a323e88d6a64fdff735c5d1b47":
            raise ValueError("Phase 3A.1 prerequisite SHA-256 mismatch")
        raw_rows, profiles, _, _ = phase3a._load_population(cache_root)
        if len(raw_rows) != 46938:
            raise ValueError("Phase 3B source population does not reconcile to Phase 3A")
        pair_sources, player_sources = _source_provenance(cache_root)
        totals = _totals_profiles(cache_root, player_sources)
        shots = _shot_profiles(cache_root, profiles, totals)
        rows = [_row_values(raw, profiles, shots, pair_sources, player_sources) for raw in raw_rows]
    rows.sort(key=lambda row: (row["target_season"], int(row["team_id"]), int(row["player_1_id"]), int(row["player_2_id"])))
    keys = [(row["target_season"], row["team_id"], row["player_1_id"], row["player_2_id"]) for row in rows]
    if len(keys) != len(set(keys)) or any(int(row["player_1_id"]) >= int(row["player_2_id"]) for row in rows):
        raise ValueError("noncanonical or duplicate Phase 3B observation key")
    sensitivity_rows = [row for row in rows if row["eligible_poss_ge_100"]]
    primary_rows = [row for row in rows if row["eligible_poss_ge_150"]]
    if not set((row["target_season"], row["team_id"], row["player_1_id"], row["player_2_id"]) for row in primary_rows) <= set(keys):
        raise ValueError("primary rows not a subset of raw population")
    by_season, by_team = _coverage(rows)
    manifest = feature_manifest()
    manifest["deterministic_content_sha256"] = canonical_json_hash(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "phase3b_feature_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    artifacts = {
        "poss_ge_100": _write_csv(output_dir / "phase3b_poss_ge_100.csv", sensitivity_rows),
        "poss_ge_150": _write_csv(output_dir / "phase3b_poss_ge_150.csv", primary_rows),
        "feature_manifest": {"relative_path": manifest_path.name, "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
    }
    history = {label: dict(Counter(row["history_status"] for row in selected)) for label, selected in (("100", sensitivity_rows), ("150", primary_rows))}
    summary = {
        "version": VERSION, "network": "prohibited", "source_population_rows": len(rows),
        "source_population_phase3a_rows": phase3a_summary["population"]["rows"],
        "prerequisites": {"phase3a_population_audit_sha256": phase3a_summary["deterministic_analysis_sha256"],
                            "phase3a1_shot_profile_replay_sha256": shot_summary["deterministic_analysis_sha256"],
                            "phase1_anchors": phase3a_summary["immutable_evidence"],
                            "phase2_window_anchor": phase3a.PHASE2E_HASH},
        "retention": {"poss_ge_100": {"retained_rows": len(sensitivity_rows), "excluded_raw_rows": len(rows) - len(sensitivity_rows)},
                      "poss_ge_150": {"retained_rows": len(primary_rows), "excluded_raw_rows": len(rows) - len(primary_rows)}},
        "history_coverage": history, "retention_by_season": by_season, "retention_by_team_season": by_team,
        "feature_counts": {"raw_player_numeric": len(PLAYER_NUMERIC_INPUTS), "raw_player_derived": len(PLAYER_DERIVED_INPUTS),
                           "future_estimator_features": len(manifest["future_estimator_features"]), "prohibited_predictors": len(manifest["prohibited_predictors"])},
        "artifacts": artifacts,
        "classification": "Phase 3B deterministic curation and feature specification complete; modeling not started.",
        "selection_bias_note": "Rows require observed substantial shared possessions. This can select pairs that coaches used, were healthy, and remained on one team; it is not a census of all possible pair fit.",
    }
    summary["deterministic_content_sha256"] = canonical_json_hash(summary)
    summary_path = output_dir / "phase3b_curation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline Phase 3B Pair Fit v2 curation; no model fitting.")
    parser.add_argument("--cache-root", default="cache")
    parser.add_argument("--output-dir", default="curated/phase3b")
    args = parser.parse_args(argv)
    print(json.dumps(build(args.cache_root, args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
