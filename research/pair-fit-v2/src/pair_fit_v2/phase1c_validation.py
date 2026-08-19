"""Cache-only complete-season validation and reporting for Phase 1C."""

from __future__ import annotations

from collections import Counter
from math import isfinite
from pathlib import Path
from typing import Any, Mapping

from pair_fit_v2.lineup_audit import (
    attach_pair_context,
    extract_result_set,
    identify_zero_or_missing_possession_rows,
    join_pair_measures,
    result_set_rows,
    summarize_advanced_targets,
    summarize_pair_rows,
)
from pair_fit_v2.multi_team_audit import (
    combine_pair_tables,
    possession_distribution,
    validate_combined_observation_keys,
)
from pair_fit_v2.phase1b_contract import (
    possession_target_eligibility,
    validate_complete_season_manifest,
)
from pair_fit_v2.phase1c_manifest import (
    ENDPOINT,
    GROUP_QUANTITY,
    LEAGUE_ID,
    REQUIRED_PAIR_MEASURES,
    SEASON_TYPE,
    TARGET_SEASON,
    TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
    ManifestStore,
    verify_asset_cache,
)


def _serializable_key(key: Any) -> Any:
    if isinstance(key, tuple):
        return [_serializable_key(item) for item in key]
    return key


def _serialize_join(join: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(join)
    for name in ("base_only_keys", "advanced_only_keys"):
        result[name] = [_serializable_key(key) for key in result[name]]
    return result


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _low_exposure(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    ranked = [
        (number, row)
        for row in rows
        if (number := _numeric(row.get(field))) is not None
    ]
    ranked.sort(key=lambda item: item[0])
    return {
        "field": field,
        "numeric_count": len(ranked),
        "missing_or_nonnumeric_count": len(rows) - len(ranked),
        "minimum": ranked[0][0] if ranked else None,
        "lowest_five": [
            {
                "value": value,
                "canonical_pair_ids": list(row.get("pair_key") or ()),
                "group_name": row.get("GROUP_NAME"),
            }
            for value, row in ranked[:5]
        ],
    }


def _response_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    marker_tokens = ("page", "total", "limit", "continu", "truncat", "next")
    markers = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                lowered = str(key).lower()
                if any(token in lowered for token in marker_tokens):
                    markers.append({"path": child_path, "value": child})
                if key not in {"rowSet", "headers"}:
                    walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(payload, "")
    result_sets = payload.get("resultSets", [])
    return {
        "top_level_keys": sorted(str(key) for key in payload),
        "result_set_envelope_keys": [
            {
                "name": item.get("name"),
                "keys": sorted(str(key) for key in item),
            }
            for item in result_sets
            if isinstance(item, Mapping)
        ],
        "pagination_limit_or_truncation_markers": markers,
    }


def audit_exact_row_boundaries(
    rows_by_team_measure: Mapping[str, Mapping[str, list[dict[str, Any]]]],
    payloads_by_team_measure: Mapping[str, Mapping[str, Mapping[str, Any]]],
    team_directory: Mapping[str, Mapping[str, Any]],
    *,
    boundary: int = 250,
) -> dict[str, Any]:
    """Flag exact-boundary responses for review without declaring truncation."""
    row_counts = {
        (team_id, measure): len(rows)
        for team_id, measures in rows_by_team_measure.items()
        for measure, rows in measures.items()
    }
    findings = []
    for (team_id, measure), row_count in sorted(row_counts.items()):
        if row_count != boundary:
            continue
        rows = rows_by_team_measure[team_id][measure]
        player_ids = {
            player_id
            for row in rows
            for player_id in (row.get("pair_key") or ())
        }
        canonical_pairs = {
            tuple(row["pair_key"])
            for row in rows
            if row.get("pair_key") is not None
        }
        theoretical = len(player_ids) * (len(player_ids) - 1) // 2
        exposure_fields = ("MIN",) if measure == "Base" else ("POSS", "MIN")
        rank_fields = sorted(
            {
                key
                for row in rows
                for key in row
                if key.endswith("_RANK")
            }
        )
        maximum_ranks = {
            field: max(
                (number for row in rows if (number := _numeric(row.get(field))) is not None),
                default=None,
            )
            for field in rank_fields
        }
        nearby = []
        for (other_team, other_measure), other_count in sorted(
            row_counts.items(), key=lambda item: (-item[1], item[0])
        ):
            if other_measure != measure or other_count >= boundary:
                continue
            other_rows = rows_by_team_measure[other_team][other_measure]
            nearby.append(
                {
                    "team_id": other_team,
                    "team_name": team_directory[other_team]["team_name"],
                    "row_count": other_count,
                    "low_exposure": {
                        field: _low_exposure(other_rows, field)["minimum"]
                        for field in exposure_fields
                    },
                }
            )
            if len(nearby) == 3:
                break
        findings.append(
            {
                "team_id": team_id,
                "team_name": team_directory[team_id]["team_name"],
                "measure_type": measure,
                "row_count": row_count,
                "distinct_player_ids": len(player_ids),
                "theoretical_unordered_pairs": theoretical,
                "returned_canonical_pair_count": len(canonical_pairs),
                "absent_theoretical_pairs": max(theoretical - len(canonical_pairs), 0),
                "low_exposure": {
                    field: _low_exposure(rows, field) for field in exposure_fields
                },
                "rank_fields": {
                    "maximum_observed": maximum_ranks,
                    "fields_reaching_boundary": sorted(
                        field for field, value in maximum_ranks.items() if value == boundary
                    ),
                    "fields_exceeding_boundary": sorted(
                        field
                        for field, value in maximum_ranks.items()
                        if value is not None and value > boundary
                    ),
                },
                "response_envelope": _response_envelope(
                    payloads_by_team_measure[team_id][measure]
                ),
                "nearby_below_boundary": nearby,
                "review_signal": True,
                "automatically_classified_as_truncated": False,
            }
        )
    return {
        "boundary": boundary,
        "exact_boundary_asset_count": len(findings),
        "findings": findings,
        "interpretation": (
            "An exact boundary is a review signal only; cached responses alone do "
            "not establish whether the endpoint truncated or exhausted observed pairs."
        ),
    }


def validate_raw_season(store: ManifestStore) -> dict[str, Any]:
    """Replay all raw assets and return the complete 30-team evidence summary."""
    manifest = store.load()
    approved = manifest["approved_schema_contract"]
    teams = list(manifest["logical_identity"]["team_ids"])
    gate = validate_complete_season_manifest(
        manifest,
        expected_season=TARGET_SEASON,
        expected_team_ids=teams,
        required_measures=REQUIRED_PAIR_MEASURES,
        expected_endpoint=ENDPOINT,
        expected_season_type=SEASON_TYPE,
        expected_league_id=LEAGUE_ID,
        expected_group_quantity=GROUP_QUANTITY,
        expected_extra_parameters=TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
        approved_schema_contract=approved,
    )

    assets: list[dict[str, Any]] = []
    rows_by_team_measure: dict[str, dict[str, list[dict[str, Any]]]] = {
        team_id: {} for team_id in teams
    }
    payloads_by_team_measure: dict[str, dict[str, Mapping[str, Any]]] = {
        team_id: {} for team_id in teams
    }
    cache_errors = []
    for asset in manifest["raw_assets"]:
        parameters = asset["identity"]["parameters"]
        try:
            replay = verify_asset_cache(asset, store.cache_root, approved)
        except Exception as exc:
            cache_errors.append(
                {"asset_id": asset.get("asset_id"), "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        lineup_rows = result_set_rows(extract_result_set(replay["payload"], "Lineups"))
        contextual_rows = attach_pair_context(
            lineup_rows, TARGET_SEASON, parameters["team_id"]
        )
        rows_by_team_measure[parameters["team_id"]][
            parameters["measure_type"]
        ] = contextual_rows
        payloads_by_team_measure[parameters["team_id"]][
            parameters["measure_type"]
        ] = replay["payload"]
        assets.append(
            {
                "asset_id": asset["asset_id"],
                "team_id": parameters["team_id"],
                "measure_type": parameters["measure_type"],
                "canonical_json_hash": replay["canonical_json_hash"],
                "cache_file_bytes": replay["cache_file_bytes"],
                "row_counts": replay["row_counts"],
                "fingerprints": replay["fingerprints"],
            }
        )

    team_summaries = {}
    all_base_rows = {}
    all_advanced_rows = {}
    all_zero_or_missing = []
    all_eligibility_reasons: Counter[str] = Counter()
    eligible_count = 0
    ineligible_count = 0
    clean_joins = True
    total_union = 0
    for team_id in teams:
        base_rows = rows_by_team_measure.get(team_id, {}).get("Base", [])
        advanced_rows = rows_by_team_measure.get(team_id, {}).get("Advanced", [])
        all_base_rows[team_id] = base_rows
        all_advanced_rows[team_id] = advanced_rows
        base_identity = summarize_pair_rows(base_rows)
        advanced_identity = summarize_pair_rows(advanced_rows)
        join = join_pair_measures(base_rows, advanced_rows)
        union_count = (
            join["matched_pairs"]
            + join["base_only_pairs"]
            + join["advanced_only_pairs"]
        )
        total_union += union_count
        team_join_clean = (
            join["one_to_one"]
            and join["base_only_pairs"] == 0
            and join["advanced_only_pairs"] == 0
            and join["matched_pairs"] == join["base_unique_pairs"]
            and join["matched_pairs"] == join["advanced_unique_pairs"]
        )
        clean_joins = clean_joins and team_join_clean
        flagged = identify_zero_or_missing_possession_rows(advanced_rows, base_rows)
        all_zero_or_missing.extend(flagged)
        for row in advanced_rows:
            eligibility = possession_target_eligibility(
                poss=row.get("POSS"),
                off_rating=row.get("OFF_RATING"),
                def_rating=row.get("DEF_RATING"),
                net_rating=row.get("NET_RATING"),
            )
            if eligibility["eligible"]:
                eligible_count += 1
            else:
                ineligible_count += 1
                all_eligibility_reasons.update(eligibility["reasons"])
        team_summaries[team_id] = {
            "team_name": manifest["team_directory"][team_id]["team_name"],
            "base": base_identity,
            "advanced": advanced_identity,
            "join": _serialize_join(join),
            "full_outer_union_count": union_count,
            "clean_one_to_one_join": team_join_clean,
            "zero_or_missing_possession_rows": flagged,
        }

    combined_base = combine_pair_tables(all_base_rows)
    combined_advanced = combine_pair_tables(all_advanced_rows)
    combined_base_keys = validate_combined_observation_keys(combined_base)
    combined_advanced_keys = validate_combined_observation_keys(combined_advanced)
    target_summary = summarize_advanced_targets(combined_advanced)

    washington_case = [
        row
        for row in all_zero_or_missing
        if row.get("team_id") == "1610612764"
        and tuple(row.get("canonical_pair_ids") or ()) == ("1629667", "203114")
    ]
    structural_identity_clean = all(
        summary[measure]["same_player_or_malformed_rows"] == 0
        and summary[measure]["duplicate_canonical_pairs"] == 0
        for summary in team_summaries.values()
        for measure in ("base", "advanced")
    )
    clean_release = (
        gate["valid"]
        and not cache_errors
        and len(assets) == 60
        and clean_joins
        and structural_identity_clean
        and combined_base_keys["duplicate_observation_key_count"] == 0
        and combined_advanced_keys["duplicate_observation_key_count"] == 0
    )

    return {
        "manifest_id": manifest["manifest_id"],
        "manifest_gate": gate,
        "cache_errors": cache_errors,
        "asset_replay": assets,
        "asset_count": len(assets),
        "status_counts": dict(Counter(asset["status"] for asset in manifest["raw_assets"])),
        "team_summaries": team_summaries,
        "totals": {
            "base_raw_pair_rows": len(combined_base),
            "advanced_raw_pair_rows": len(combined_advanced),
            "full_outer_union_count": total_union,
            "matched_pairs": sum(
                summary["join"]["matched_pairs"]
                for summary in team_summaries.values()
            ),
            "base_only_pairs": sum(
                summary["join"]["base_only_pairs"]
                for summary in team_summaries.values()
            ),
            "advanced_only_pairs": sum(
                summary["join"]["advanced_only_pairs"]
                for summary in team_summaries.values()
            ),
        },
        "combined_base_identity": combined_base_keys,
        "combined_advanced_identity": combined_advanced_keys,
        "target_summary": target_summary,
        "exposure": {
            "base_min": possession_distribution(combined_base, field="MIN"),
            "advanced_poss": possession_distribution(combined_advanced, field="POSS"),
            "advanced_min": possession_distribution(combined_advanced, field="MIN"),
        },
        "target_eligibility": {
            "eligible": eligible_count,
            "ineligible": ineligible_count,
            "reason_counts": dict(sorted(all_eligibility_reasons.items())),
        },
        "zero_or_missing_possession_rows": all_zero_or_missing,
        "washington_middleton_mcdaniels_present_and_ineligible": (
            len(washington_case) == 1
            and washington_case[0]["eligible_for_possession_based_rate_target"] is False
        ),
        "row_preservation": {
            "no_rows_filtered": True,
            "no_values_imputed": True,
            "no_endpoint_values_altered": True,
        },
        "exact_250_row_audit": audit_exact_row_boundaries(
            rows_by_team_measure,
            payloads_by_team_measure,
            manifest["team_directory"],
        ),
        "clean_release": clean_release,
    }
