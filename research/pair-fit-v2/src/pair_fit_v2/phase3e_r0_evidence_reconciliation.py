"""Cache-only Phase 3E-R0 evidence reconciliation.

This checkpoint verifies evidence and reconstruction prerequisites only.  It
does not construct a model dataset, fit a model, generate predictions, or
calculate holdout/model performance metrics.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

from pair_fit_v2 import phase1d_exhaustiveness as phase1d
from pair_fit_v2 import phase1e_recovery as phase1e
from pair_fit_v2 import phase3a1_shot_zone_acquisition as phase3a1
from pair_fit_v2.phase1c_manifest import canonical_json_hash, read_json, verify_asset_cache


VERSION = "phase3e-r0.cache-only-evidence-reconciliation.v1"
PROTECTED_SEASON = "2025-26"
TARGET_SEASON = "2024-25"
PRIOR_SEASON = "2023-24"
CHARLOTTE_ID = "1610612766"

PLAYER_TOTALS_RAW_SHA256 = "0a856d37c33218362a0b88fc645b7d609a64a7da0773a1be1368d22d07b54774"
PLAYER_TOTALS_CANONICAL_SHA256 = "8d1efef313fbaf4a508a1e786e520feb1ad2161e0400e3f7003a1df062b6cd85"
PLAYER_TOTALS_BYTES = 173_713
PLAYER_ROWS = 572
PHASE1C_MANIFEST_SHA256 = "5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c"
PHASE1D_LEDGER_SHA256 = "f6873ebe3a4feb8940ec092bb0501d9067eddeed2391663c10c864d3f1a3dee9"
PHASE1E_LEDGER_SHA256 = "5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde"

PHASE1C_MANIFEST = Path("phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json")
PHASE1D_LEDGER = Path("phase1d/diagnostic_ledger.json")
PHASE1E_LEDGER = Path("phase1e/recovery_ledger.json")
PER100_BODY = Path("live_responses/league_dash_player_stats_2023-24_base_per100possessions.json")
PER100_METADATA = Path("live_responses/league_dash_player_stats_2023-24_base_per100possessions_metadata.json")

BASE_ADDITIVE_FIELDS = tuple(phase1e.BASE_ADDITIVE_FIELDS)
RATE_FIELDS = tuple(phase1e.RATE_FIELDS)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_content_hash(document: dict, field: str = "deterministic_content_sha256") -> str:
    value = dict(document)
    value.pop(field, None)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reject_protected_paths(*paths: Path | str) -> None:
    """Reject final-test season paths before any filesystem access."""
    for path in paths:
        if PROTECTED_SEASON in str(path).replace("\\", "/").lower():
            raise ValueError(f"protected-season path rejected before access: {path}")


def _read_bytes(path: Path) -> bytes:
    reject_protected_paths(path)
    return path.read_bytes()


def _read_json(path: Path) -> dict:
    return json.loads(_read_bytes(path).decode("utf-8-sig"))


def _require_hash(path: Path, expected: str) -> str:
    actual = sha256_bytes(_read_bytes(path))
    if actual != expected:
        raise ValueError(f"immutable evidence hash mismatch: {path}")
    return actual


def _result_set(payload: dict, name: str) -> tuple[list[str], list[list]]:
    result_sets = payload.get("resultSets")
    if not isinstance(result_sets, list):
        raise ValueError(f"{name} response lacks a resultSets list")
    matches = [item for item in result_sets if item.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {name} result set")
    headers, rows = matches[0].get("headers"), matches[0].get("rowSet")
    if not isinstance(headers, list) or not isinstance(rows, list) or len(headers) != len(set(headers)):
        raise ValueError(f"malformed {name} result set")
    if any(not isinstance(row, list) or len(row) != len(headers) for row in rows):
        raise ValueError(f"malformed {name} row width")
    return headers, rows


def _player_table(payload: dict) -> tuple[list[str], list[dict], set[str]]:
    headers, raw_rows = _result_set(payload, "LeagueDashPlayerStats")
    rows = [dict(zip(headers, raw)) for raw in raw_rows]
    ids = [phase3a1.strict_id(row["PLAYER_ID"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate player IDs")
    return headers, rows, set(ids)


def _numeric_summary(values: list[float]) -> dict:
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "minimum": ordered[0],
        "median": float(statistics.median(ordered)),
        "maximum": ordered[-1],
        "zero_count": sum(value == 0 for value in ordered),
    }


def _compact_error_summary(summary: dict) -> dict:
    """Retain deterministic diagnostics without embedding per-pair target rows."""
    return {
        key: value
        for key, value in summary.items()
        if key != "discrepancies_over_0_2"
    } | {"discrepancies_over_0_2_count": len(summary.get("discrepancies_over_0_2", []))}


def verify_player_totals_dependency(cache_root: Path) -> dict:
    """Verify the existing Phase 3A.1 Totals dependency in place."""
    dependency = phase3a1.dependency_paths(cache_root)
    referenced = [dependency[name] for name in ("plan", "allowlist", "authorization", "ledger", "raw", "metadata")]
    referenced.extend((cache_root / PER100_BODY, cache_root / PER100_METADATA))
    reject_protected_paths(*referenced)

    plan = _read_json(dependency["plan"])
    allowlist = _read_json(dependency["allowlist"])
    authorization = _read_json(dependency["authorization"])
    ledger = _read_json(dependency["ledger"])
    metadata = _read_json(dependency["metadata"])
    expected_identity = phase3a1.dependency_identity()
    if plan.get("newly_authorized_identities") != [expected_identity]:
        raise ValueError("dependency dry-run identity mismatch")
    if allowlist.get("identities") != [expected_identity]:
        raise ValueError("dependency allowlist identity mismatch")
    if authorization.get("reason") != "exact 2023-24 shot-zone Totals reconciliation only":
        raise ValueError("dependency authorization mismatch")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list) or attempts != [metadata]:
        raise ValueError("dependency ledger/metadata mismatch")
    if metadata.get("identity") != expected_identity or metadata.get("result") != "verified":
        raise ValueError("dependency immutable identity/status mismatch")
    if metadata.get("attempt") != 1 or metadata.get("http_status") != 200:
        raise ValueError("dependency attempt provenance mismatch")

    body = _read_bytes(dependency["raw"])
    payload = json.loads(body)
    if len(body) != PLAYER_TOTALS_BYTES or metadata.get("byte_count") != len(body):
        raise ValueError("player-Totals byte count mismatch")
    raw_hash = sha256_bytes(body)
    if raw_hash != PLAYER_TOTALS_RAW_SHA256 or metadata.get("raw_body_sha256") != raw_hash:
        raise ValueError("player-Totals raw SHA-256 mismatch")
    canonical_hash = canonical_json_hash(payload)
    if canonical_hash != PLAYER_TOTALS_CANONICAL_SHA256 or metadata.get("canonical_json_sha256") != canonical_hash:
        raise ValueError("player-Totals canonical JSON SHA-256 mismatch")
    headers, total_rows, total_ids = _player_table(payload)
    if len(headers) != 69 or len(total_rows) != PLAYER_ROWS or metadata.get("schema_headers") != headers:
        raise ValueError("player-Totals schema/row contract mismatch")

    per100_payload = _read_json(cache_root / PER100_BODY)
    per100_metadata = _read_json(cache_root / PER100_METADATA)
    per100_headers, per100_rows, per100_ids = _player_table(per100_payload)
    if per100_metadata.get("season") != PRIOR_SEASON or per100_metadata.get("measure_type") != "Base" or per100_metadata.get("per_mode") != "Per100Possessions":
        raise ValueError("prior Per100 identity mismatch")
    recorded_prefix = str(per100_metadata.get("content_hash", ""))
    if not recorded_prefix or not canonical_json_hash(per100_payload).startswith(recorded_prefix):
        raise ValueError("prior Per100 canonical hash prefix mismatch")
    if len(per100_rows) != PLAYER_ROWS or total_ids != per100_ids:
        raise ValueError("2023-24 Totals/Per100 player-ID reconciliation failure")

    total_minutes = []
    invalid_minutes = []
    for row in total_rows:
        try:
            value = float(row["MIN"])
        except (KeyError, TypeError, ValueError):
            invalid_minutes.append(row.get("PLAYER_ID"))
            continue
        if not math.isfinite(value) or value < 0:
            invalid_minutes.append(row.get("PLAYER_ID"))
        else:
            total_minutes.append(value)
    if invalid_minutes or len(total_minutes) != PLAYER_ROWS:
        raise ValueError("invalid season-total MIN evidence")

    required_reliability = {"GP", "MIN"}
    reliability_satisfied = (
        expected_identity["parameters"]["per_mode"] == "Totals"
        and required_reliability <= set(headers)
        and len(total_minutes) == PLAYER_ROWS
        and total_ids == per100_ids
    )
    def evidence_record(path: Path) -> dict:
        value = _read_bytes(path)
        return {
            "relative_path": str(path.relative_to(cache_root)).replace("\\", "/"),
            "byte_count": len(value),
            "serialized_byte_sha256": sha256_bytes(value),
        }
    return {
        "identity": expected_identity,
        "immutable_records": {
            "dry_run": evidence_record(dependency["plan"]),
            "allowlist": evidence_record(dependency["allowlist"]),
            "authorization": evidence_record(dependency["authorization"]),
            "ledger": evidence_record(dependency["ledger"]),
            "metadata": evidence_record(dependency["metadata"]),
            "raw_body": evidence_record(dependency["raw"]),
        },
        "attempt_count": len(attempts),
        "byte_count": len(body),
        "raw_body_sha256": raw_hash,
        "canonical_json_sha256": canonical_hash,
        "schema_column_count": len(headers),
        "schema_headers": headers,
        "unique_player_ids": len(total_ids),
        "duplicate_player_ids": 0,
        "malformed_player_ids": 0,
        "per100_reconciliation": {
            "path": str(PER100_BODY).replace("\\", "/"),
            "byte_count": len(_read_bytes(cache_root / PER100_BODY)),
            "serialized_byte_sha256": sha256_bytes(_read_bytes(cache_root / PER100_BODY)),
            "canonical_json_sha256": canonical_json_hash(per100_payload),
            "schema_column_count": len(per100_headers),
            "unique_player_ids": len(per100_ids),
            "totals_only_ids": [],
            "per100_only_ids": [],
        },
        "season_total_minutes": {
            "source_field": "MIN",
            "materialized_phase3b_field": "TOTAL_MIN",
            "summary": _numeric_summary(total_minutes),
            "invalid_or_missing": 0,
            "reliability_metadata_contract_satisfied": reliability_satisfied,
            "reason": "The verified Base/Totals identity supplies finite nonnegative season-total MIN for all 572 IDs; Phase 3B materializes it as TOTAL_MIN and classifies player_slot.total_min as reliability metadata, not an estimator predictor.",
        },
        "path_convention_action": "none; evidence remains in its original Phase 3A.1 namespace",
    }


def _full_season_assets(cache_root: Path, manifest: dict, team_id: str) -> dict[str, dict]:
    selected = {}
    for asset in manifest.get("raw_assets", []):
        parameters = asset.get("identity", {}).get("parameters", {})
        if str(parameters.get("team_id")) != team_id:
            continue
        measure = parameters.get("measure_type")
        if measure not in {"Base", "Advanced"}:
            continue
        reject_protected_paths(
            cache_root / asset["cache"]["relative_path"],
            cache_root / asset["cache"]["metadata_relative_path"],
        )
        selected[measure] = verify_asset_cache(asset, cache_root, manifest["approved_schema_contract"])
        selected[measure]["asset"] = asset
    if set(selected) != {"Base", "Advanced"}:
        raise ValueError(f"full-season Base/Advanced evidence incomplete for {team_id}")
    return selected


def _asset_summary(cache_root: Path, asset: dict, validation: dict) -> dict:
    metadata = _read_json(cache_root / asset["cache"]["metadata_relative_path"])
    parameters = asset["identity"]["parameters"]
    return {
        "asset_id": asset["asset_id"],
        "status": asset["status"],
        "team_id": str(parameters["team_id"]),
        "measure_type": parameters["measure_type"],
        "date_from": parameters.get("DateFrom", ""),
        "date_to": parameters.get("DateTo", ""),
        "last_n_games": str(parameters.get("LastNGames", "0")),
        "relative_path": asset["cache"]["relative_path"].replace("\\", "/"),
        "byte_count": metadata["response_body_bytes"],
        "raw_body_sha256": metadata["raw_body_hash"],
        "canonical_json_sha256": metadata["canonical_json_hash"],
        "lineup_rows": validation["row_counts"]["Lineups"],
        "lineup_columns": next(item["column_count"] for item in validation["fingerprints"] if item["name"] == "Lineups"),
    }


def analyze_charlotte_and_windows(cache_root: Path) -> dict:
    """Verify Charlotte full/window evidence and inventory cached partitions."""
    manifest_path = cache_root / PHASE1C_MANIFEST
    phase1d_path = cache_root / PHASE1D_LEDGER
    phase1e_path = cache_root / PHASE1E_LEDGER
    reject_protected_paths(manifest_path, phase1d_path, phase1e_path)
    manifest_hash = _require_hash(manifest_path, PHASE1C_MANIFEST_SHA256)
    phase1d_hash = _require_hash(phase1d_path, PHASE1D_LEDGER_SHA256)
    phase1e_hash = _require_hash(phase1e_path, PHASE1E_LEDGER_SHA256)
    manifest = read_json(manifest_path)
    full = _full_season_assets(cache_root, manifest, CHARLOTTE_ID)
    full_payloads = {measure: item["payload"] for measure, item in full.items()}

    ledger_e = read_json(phase1e_path)
    window_payloads: dict[str, dict[str, dict]] = {"early": {}, "late": {}}
    window_assets = []
    planned_assets = []
    for asset in ledger_e.get("assets", []):
        parameters = asset["identity"]["parameters"]
        if asset.get("status") != "verified":
            planned_assets.append({
                "asset_id": asset["asset_id"],
                "status": asset["status"],
                "team_id": str(parameters["team_id"]),
                "measure_type": parameters["measure_type"],
                "date_from": parameters["DateFrom"],
                "date_to": parameters["DateTo"],
            })
            continue
        reject_protected_paths(
            cache_root / asset["cache"]["relative_path"],
            cache_root / asset["cache"]["metadata_relative_path"],
        )
        payload, validation = phase1e._verify_cached_asset(cache_root, asset, manifest["approved_schema_contract"])
        label = "early" if parameters["DateFrom"] == "10/22/2024" else "late"
        window_payloads[label][asset["measure"]] = payload
        window_assets.append(_asset_summary(cache_root, asset, validation))
    if any(set(measures) != {"Base", "Advanced"} for measures in window_payloads.values()):
        raise ValueError("Charlotte early/late Base/Advanced evidence incomplete")

    reconciliations = {
        label: phase1e.reconcile_window_measures(values["Base"], values["Advanced"])
        for label, values in window_payloads.items()
    }
    indexes = phase1e._window_indexes(window_payloads)
    early = set(indexes["early"]["Base"])
    late = set(indexes["late"]["Base"])
    union = early | late
    full_base = phase1e._pair_index(full_payloads["Base"])["index"]
    full_advanced = phase1e._pair_index(full_payloads["Advanced"])["index"]
    full_keys = set(full_base) | set(full_advanced)
    recovered_only = sorted(union - full_keys, key=phase1e._key_sort)
    recovered_rows = []
    for key in recovered_only:
        base_rows = [indexes[label]["Base"][key] for label in ("early", "late") if key in indexes[label]["Base"]]
        advanced_rows = [indexes[label]["Advanced"][key] for label in ("early", "late") if key in indexes[label]["Advanced"]]
        recovered_rows.append({
            "player_1_id": key[0],
            "player_2_id": key[1],
            "group_name": next(row.get("GROUP_NAME") for row in base_rows + advanced_rows if row.get("GROUP_NAME")),
            "windows_present": [label for label in ("early", "late") if key in indexes[label]["Base"]],
            "base_minutes": phase1e._sum_field(base_rows, "MIN"),
            "advanced_possessions": phase1e._sum_field(advanced_rows, "POSS"),
            "direct_full_season_net_rating_available": key in full_advanced,
        })

    aggregation = phase1e.audit_additive_reconstruction(
        full_payloads["Base"], full_payloads["Advanced"], window_payloads
    )
    rate_summary = {
        field: _compact_error_summary(aggregation["rate_recomposition"][field])
        for field in RATE_FIELDS
    }
    derived_summary = {
        "classification": aggregation["base_points_plus_minus_derived_ratings"]["classification"],
        "summaries": {
            field: _compact_error_summary(
                aggregation["base_points_plus_minus_derived_ratings"]["summaries"][field]
            )
            for field in RATE_FIELDS
        },
    }

    ledger_d = read_json(phase1d_path)
    phase1d_assets = []
    for asset in ledger_d.get("assets", []):
        parameters = asset["identity"]["parameters"]
        if asset.get("status") not in {"verified", "verified_after_offline_revalidation"}:
            phase1d_assets.append({
                "asset_id": asset["asset_id"], "status": asset["status"],
                "team_id": str(parameters["team_id"]), "measure_type": parameters["measure_type"],
                "last_n_games": str(parameters["LastNGames"]),
            })
            continue
        reject_protected_paths(
            cache_root / asset["cache"]["relative_path"],
            cache_root / asset["cache"]["metadata_relative_path"],
        )
        _, validation = phase1d._verify_cached_diagnostic(
            cache_root, asset, manifest["approved_schema_contract"]["Base"]
        )
        phase1d_assets.append(_asset_summary(cache_root, asset, validation))

    full_counts = {}
    for asset in manifest["raw_assets"]:
        p = asset["identity"]["parameters"]
        if p["measure_type"] == "Advanced":
            full_counts[str(p["team_id"])] = asset["schema_verification"]["row_counts"]["Lineups"]
    exact_250 = sorted(team for team, count in full_counts.items() if count == 250)

    return {
        "immutable_ledgers": {
            "phase1c_manifest": {"relative_path": str(PHASE1C_MANIFEST).replace("\\", "/"), "serialized_byte_sha256": manifest_hash, "byte_count": len(_read_bytes(manifest_path))},
            "phase1d_ledger": {"relative_path": str(PHASE1D_LEDGER).replace("\\", "/"), "serialized_byte_sha256": phase1d_hash, "byte_count": len(_read_bytes(phase1d_path))},
            "phase1e_ledger": {"relative_path": str(PHASE1E_LEDGER).replace("\\", "/"), "serialized_byte_sha256": phase1e_hash, "byte_count": len(_read_bytes(phase1e_path))},
        },
        "full_season": {
            measure: {
                "asset_id": item["asset"]["asset_id"],
                "byte_count": item["cache_file_bytes"],
                "canonical_json_sha256": item["canonical_json_hash"],
                "raw_body_sha256": item["asset"]["source_event"]["raw_body_hash"],
                "lineup_rows": item["row_counts"]["Lineups"],
                "lineup_columns": next(x["column_count"] for x in item["fingerprints"] if x["name"] == "Lineups"),
            }
            for measure, item in sorted(full.items())
        },
        "window_assets": sorted(window_assets, key=lambda item: (item["date_from"], item["measure_type"])),
        "window_reconciliation": reconciliations,
        "population_reconciliation": {
            "early_keys": len(early),
            "late_keys": len(late),
            "both_windows": len(early & late),
            "early_only": len(early - late),
            "late_only": len(late - early),
            "window_union_keys": len(union),
            "full_season_keys": len(full_keys),
            "full_season_keys_in_union": len(full_keys & union),
            "full_season_only_keys": [list(key) for key in sorted(full_keys - union, key=phase1e._key_sort)],
            "recovered_only_keys": [list(key) for key in recovered_only],
        },
        "recovered_only_rows": recovered_rows,
        "reconstruction_analysis": {
            "located_in": [
                "PHASE1E_RECOVERY_FEASIBILITY_REPORT.md",
                "PHASE1F_TARGET_SEMANTICS_REPORT.md",
                "src/pair_fit_v2/phase1e_recovery.py:audit_additive_reconstruction",
            ],
            "additive_fields": list(BASE_ADDITIVE_FIELDS) + ["POSS"],
            "additive_discrepancy_count": aggregation["additive_discrepancy_count"],
            "additive_totals_reproduced": aggregation["additive_totals_reproduced"],
            "rate_recomposition_using_team_possessions": rate_summary,
            "base_points_plus_minus_using_team_possessions": derived_summary,
            "available_definition_fields": {
                "team_points_numerator": "Base.PTS",
                "opponent_points_numerator": "Base.PTS - Base.PLUS_MINUS",
                "team_possession_denominator": "Advanced.POSS",
                "direct_standard_rates": list(RATE_FIELDS),
                "other_exposure_not_proven_as_rate_denominator": ["Base.MIN", "Base.SUM_TIME_PLAYED"],
            },
            "missing_definition_fields": [
                "opponent possessions at pair/window grain",
                "unrounded internal rating numerators/denominators or full-precision rates",
            ],
            "why_unresolved": "OFF_RATING uses team possessions and recomposes, but DEF_RATING is defined over opponent possessions, which the cached schemas do not expose. NET_RATING is a difference of rates with those different denominators, so directly weighting window NET_RATING by team POSS is not definition-based. Published one-decimal window rates also omit internal precision.",
        },
        "all_cached_partition_inventory": {
            "phase1d_assets": phase1d_assets,
            "phase1e_verified_assets": sorted(window_assets, key=lambda item: (item["date_from"], item["measure_type"])),
            "phase1e_planned_not_cached": sorted(planned_assets, key=lambda item: (item["team_id"], item["date_from"], item["measure_type"])),
            "full_season_team_count": len(full_counts),
            "full_season_exact_250_team_ids": exact_250,
            "full_season_below_250_team_count": sum(count < 250 for count in full_counts.values()),
            "noncapped_validation_package_present": False,
            "reason": "Every verified window-partition asset is Charlotte evidence, while Charlotte's direct full-season response is exactly 250 rows. The only Phase 1D cached diagnostic is overlapping Base-only LastNGames=41 evidence. No below-250 full-season team has matching exhaustive Base/Advanced child windows in cache.",
        },
    }


def build_summary(cache_root: Path | str = "cache") -> dict:
    cache_root = Path(cache_root)
    reject_protected_paths(cache_root)
    player = verify_player_totals_dependency(cache_root)
    pair = analyze_charlotte_and_windows(cache_root)
    summary = {
        "version": VERSION,
        "scope": "cache-only evidence reconciliation; no dataset construction, prediction, model fitting, holdout metrics, or aggregation selection",
        "network": "prohibited",
        "target_season_evidence": TARGET_SEASON,
        "final_test_season_evidence_accessed": False,
        "player_totals_dependency": player,
        "charlotte_and_window_evidence": pair,
        "evidence_classification": {
            "verified_evidence": [
                "The original Phase 3A.1 2023-24 Base/Totals dependency is intact and satisfies Phase 3E reliability metadata without reacquisition.",
                "Charlotte's verified early/late Base/Advanced windows contain 257 canonical keys, all 250 full-season keys, and seven recovered-only keys.",
                "All supported additive Base fields and Advanced POSS reproduce the direct full-season values for the 250 overlapping keys.",
            ],
            "reconstruction_hypotheses_not_selected": [
                "Possession-weighted window OFF_RATING is empirically and definitionally supported for the cached Charlotte overlap.",
                "Any weighting of DEF_RATING or NET_RATING by team possessions or minutes remains a hypothesis, not an approved aggregation method.",
            ],
            "missing_evidence": [
                "An authoritative opponent-possession denominator at pair/window grain.",
                "A matched exhaustive window partition for a team whose direct full-season Base/Advanced responses are both below 250 rows.",
                "Direct full-season standard ratings for Charlotte's seven recovered-only keys.",
            ],
            "cache_only_reconstruction_validation_feasible": False,
            "minimum_additional_acquisition": {
                "empirical_noncapped_validation": "Four TeamDashLineups responses for one predeclared below-250 full-season team: Base and Advanced for each of the same two exhaustive, nonoverlapping date windows.",
                "definition_based_defensive_and_net_validation": "In addition, authoritative opponent-possession denominators for every pair in both windows at the identical grain. If one denominator-bearing response covers each window, this is two additional responses (six total). If no such source exists, exact definition-based validation is not acquirable through the current schema.",
                "important_limit": "The four TeamDashLineups responses alone can test empirical agreement but cannot prove the DEF_RATING/NET_RATING formula because their schema still omits opponent possessions.",
            },
        },
    }
    # Normalize tuples returned by older audit helpers so the in-memory value
    # and its deterministic JSON representation have identical semantics.
    summary = json.loads(json.dumps(summary, sort_keys=True, allow_nan=False))
    summary["deterministic_content_sha256"] = canonical_content_hash(summary)
    return summary


def write_summary(output_dir: Path | str, summary: dict) -> Path:
    output_dir = Path(output_dir)
    reject_protected_paths(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "evidence_reconciliation.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return path
