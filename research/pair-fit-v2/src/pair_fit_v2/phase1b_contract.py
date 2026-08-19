"""Pure Phase 1B architecture contracts; no network, Parquet, or DuckDB I/O."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from typing import Any, Iterable, Mapping

from pair_fit_v2.schema import canonical_pair_key


CONTRACT_VERSION = "phase1b.contract.v1"
MANIFEST_KIND = "pair-fit-v2-season-ingestion"
REQUIRED_PAIR_MEASURES = ("Base", "Advanced")
REQUIRED_RESULT_SETS = ("Overall", "Lineups")
PRIOR_HISTORY_STATUSES = frozenset({"complete", "one_missing", "both_missing"})
RAW_ASSET_STATUSES = frozenset(
    {"planned", "acquired", "verified", "failed", "quarantined"}
)

_SEASON_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


def normalize_season(season: Any) -> str:
    """Validate and normalize an NBA season label such as ``2024-25``."""
    value = str(season).strip()
    match = _SEASON_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"Invalid NBA season label: {season!r}")
    start_year = int(match.group(1))
    if int(match.group(2)) != (start_year + 1) % 100:
        raise ValueError(f"NBA season label is not consecutive: {season!r}")
    return value


def normalize_nba_id(value: Any, field: str) -> str:
    """Return the canonical decimal-string representation of a positive NBA ID."""
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive decimal ID")
    text = str(value).strip()
    if not text.isdecimal() or int(text) <= 0:
        raise ValueError(f"{field} must be a positive decimal ID")
    return str(int(text))


def normalize_season_type(season_type: Any) -> str:
    """Return a stable lowercase slug for an NBA season type."""
    if season_type is None or isinstance(season_type, bool):
        raise ValueError("season_type must not be empty")
    value = "-".join(str(season_type).strip().lower().split())
    if not value:
        raise ValueError("season_type must not be empty")
    return value


def season_key(
    season: Any, season_type: Any = "Regular Season", league_id: Any = "00"
) -> tuple[str, str, str]:
    """Return the stable league/season/season-type key."""
    if league_id is None or isinstance(league_id, bool):
        raise ValueError("league_id must be a decimal string")
    league = str(league_id).strip()
    if not league.isdecimal():
        raise ValueError("league_id must be a decimal string")
    return (league, normalize_season(season), normalize_season_type(season_type))


def team_season_key(
    season: Any,
    team_id: Any,
    season_type: Any = "Regular Season",
    league_id: Any = "00",
) -> tuple[str, str, str, str]:
    """Return the stable league/season/season-type/team key."""
    return (*season_key(season, season_type, league_id), normalize_nba_id(team_id, "team_id"))


def stable_pair_key(player_a_id: Any, player_b_id: Any) -> tuple[str, str]:
    """Return the existing lexicographically ordered canonical player pair."""
    player_a = normalize_nba_id(player_a_id, "player_a_id")
    player_b = normalize_nba_id(player_b_id, "player_b_id")
    if player_a == player_b:
        raise ValueError("A pair observation requires two distinct player IDs")
    return canonical_pair_key(player_a, player_b)


def observation_key(
    season: Any,
    team_id: Any,
    player_a_id: Any,
    player_b_id: Any,
    season_type: Any = "Regular Season",
    league_id: Any = "00",
) -> tuple[str, str, str, str, str, str]:
    """Return the full stable pair observation identity."""
    return (
        *team_season_key(season, team_id, season_type, league_id),
        *stable_pair_key(player_a_id, player_b_id),
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_contract_id(kind: str, identity: Mapping[str, Any]) -> str:
    """Hash a versioned logical identity, not response or cache-file bytes."""
    digest = hashlib.sha256(
        _canonical_json(
            {"contract_version": CONTRACT_VERSION, "kind": kind, "identity": identity}
        ).encode("utf-8")
    ).hexdigest()
    return f"{kind}:{digest[:24]}"


def raw_asset_identity(
    *,
    endpoint: str,
    season: Any,
    team_id: Any,
    measure_type: str,
    season_type: Any = "Regular Season",
    league_id: Any = "00",
    group_quantity: Any = "2",
    extra_parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the complete normalized request identity for one raw lineup asset."""
    endpoint_value = "" if endpoint is None else str(endpoint).strip()
    measure_value = "" if measure_type is None else str(measure_type).strip()
    if not endpoint_value or not measure_value:
        raise ValueError("endpoint and measure_type must not be empty")
    league = season_key(season, season_type, league_id)[0]
    group_quantity_value = str(group_quantity).strip()
    if not group_quantity_value.isdecimal() or int(group_quantity_value) <= 0:
        raise ValueError("group_quantity must be a positive integer")
    parameters = {
        "league_id": league,
        "season": normalize_season(season),
        "season_type": normalize_season_type(season_type),
        "team_id": normalize_nba_id(team_id, "team_id"),
        "group_quantity": group_quantity_value,
        "measure_type": measure_value,
    }
    if extra_parameters:
        for name, value in extra_parameters.items():
            if name in parameters:
                raise ValueError(f"extra parameter duplicates canonical field: {name}")
            parameters[str(name)] = value
    return {"endpoint": endpoint_value, "parameters": parameters}


def raw_asset_id(**kwargs: Any) -> str:
    """Return a deterministic ID for a complete raw request identity."""
    return stable_contract_id("raw-asset", raw_asset_identity(**kwargs))


def _normalize_team_set(team_ids: Iterable[Any]) -> tuple[str, ...]:
    normalized = [normalize_nba_id(value, "team_id") for value in team_ids]
    if not normalized:
        raise ValueError("team_ids must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError("team_ids must be unique")
    return tuple(sorted(normalized, key=int))


def _normalize_measure_set(measures: Iterable[Any]) -> tuple[str, ...]:
    normalized = [str(value).strip() for value in measures]
    if not normalized or any(not value for value in normalized):
        raise ValueError("measures must contain nonempty values")
    if len(set(normalized)) != len(normalized):
        raise ValueError("measures must be unique")
    preferred_order = {value: index for index, value in enumerate(REQUIRED_PAIR_MEASURES)}
    return tuple(
        sorted(
            normalized,
            key=lambda value: (preferred_order.get(value, len(preferred_order)), value),
        )
    )


def _normalize_extra_parameters(
    extra_parameters: Mapping[str, Any] | None,
) -> dict[str, Any]:
    canonical_names = {
        "league_id",
        "season",
        "season_type",
        "team_id",
        "group_quantity",
        "measure_type",
    }
    normalized: dict[str, Any] = {}
    for raw_name, value in (extra_parameters or {}).items():
        name = str(raw_name).strip()
        if not name:
            raise ValueError("extra parameter names must not be empty")
        if name in canonical_names:
            raise ValueError(f"extra parameter duplicates canonical field: {name}")
        if name in normalized:
            raise ValueError(f"duplicate normalized extra parameter: {name}")
        normalized[name] = value
    return {name: normalized[name] for name in sorted(normalized)}


def _normalized_manifest_identity(
    *,
    season: Any,
    team_ids: Iterable[Any],
    measures: Iterable[Any],
    endpoint: Any,
    season_type: Any,
    league_id: Any,
    group_quantity: Any,
    extra_parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    endpoint_value = "" if endpoint is None else str(endpoint).strip()
    if not endpoint_value:
        raise ValueError("endpoint must not be empty")
    league, normalized_season, season_type_slug = season_key(
        season, season_type, league_id
    )
    group_quantity_value = str(group_quantity).strip()
    if not group_quantity_value.isdecimal() or int(group_quantity_value) <= 0:
        raise ValueError("group_quantity must be a positive integer")
    return {
        "league_id": league,
        "season": normalized_season,
        "season_type": season_type_slug,
        "team_ids": list(_normalize_team_set(team_ids)),
        "measures": list(_normalize_measure_set(measures)),
        "endpoint": endpoint_value,
        "group_quantity": group_quantity_value,
        "extra_parameters": _normalize_extra_parameters(extra_parameters),
    }


def _field_mismatches(
    expected: Any, actual: Any, *, path: str
) -> list[dict[str, Any]]:
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        mismatches = []
        for name in sorted(set(expected) | set(actual)):
            field_path = f"{path}.{name}"
            if name not in actual:
                mismatches.append(
                    {
                        "field": field_path,
                        "expected": expected[name],
                        "actual": None,
                        "problem": "missing",
                    }
                )
            elif name not in expected:
                mismatches.append(
                    {
                        "field": field_path,
                        "expected": None,
                        "actual": actual[name],
                        "problem": "unexpected",
                    }
                )
            else:
                mismatches.extend(
                    _field_mismatches(expected[name], actual[name], path=field_path)
                )
        return mismatches
    if expected != actual:
        return [
            {
                "field": path,
                "expected": expected,
                "actual": actual,
                "problem": "value_mismatch",
            }
        ]
    return []


def _normalize_embedded_asset_identity(
    identity: Any,
) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(identity, Mapping):
        return None, ["identity_not_mapping"]
    errors = []
    if set(identity) != {"endpoint", "parameters"}:
        errors.append("identity_top_level_fields_incomplete_or_unexpected")
    parameters = identity.get("parameters")
    if not isinstance(parameters, Mapping):
        return None, [*errors, "parameters_not_mapping"]
    required = {
        "league_id",
        "season",
        "season_type",
        "team_id",
        "group_quantity",
        "measure_type",
    }
    missing = sorted(required - set(parameters))
    if missing:
        return None, [*errors, f"missing_parameters:{','.join(missing)}"]
    extras = {name: value for name, value in parameters.items() if name not in required}
    try:
        normalized = raw_asset_identity(
            endpoint=identity.get("endpoint"),
            season=parameters.get("season"),
            team_id=parameters.get("team_id"),
            measure_type=parameters.get("measure_type"),
            season_type=parameters.get("season_type"),
            league_id=parameters.get("league_id"),
            group_quantity=parameters.get("group_quantity"),
            extra_parameters=extras,
        )
    except (TypeError, ValueError) as exc:
        return None, [*errors, f"normalization_error:{exc}"]
    if dict(identity) != normalized:
        errors.append("identity_not_normalized")
    return normalized, errors


def _fingerprint_errors(fingerprint: Any) -> list[str]:
    if not isinstance(fingerprint, Mapping):
        return ["fingerprint_not_mapping"]
    errors = []
    name = fingerprint.get("name")
    columns = fingerprint.get("columns")
    count = fingerprint.get("column_count")
    if not isinstance(name, str) or not name.strip():
        errors.append("missing_or_invalid_result_set_name")
    if not isinstance(columns, list) or not columns:
        errors.append("missing_or_invalid_columns")
        columns = []
    elif any(not isinstance(column, str) or not column for column in columns):
        errors.append("invalid_column_name")
    if isinstance(count, bool) or not isinstance(count, int):
        errors.append("missing_or_invalid_column_count")
    elif count != len(columns):
        errors.append("column_count_mismatch")
    if all(isinstance(column, str) for column in columns) and len(set(columns)) != len(
        columns
    ):
        errors.append("duplicate_columns")
    if not errors and not schema_drift_report(fingerprint, fingerprint)["accepted"]:
        errors.append("fingerprint_not_internally_identical")
    return errors


def schema_drift_report(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> dict[str, Any]:
    """Classify result-set schema drift without silently accepting any change."""
    expected_columns = list(expected.get("columns", []))
    actual_columns = list(actual.get("columns", []))
    expected_name = expected.get("name")
    actual_name = actual.get("name")

    invalid_reasons = []
    if expected.get("column_count") != len(expected_columns):
        invalid_reasons.append("expected_column_count_mismatch")
    if actual.get("column_count") != len(actual_columns):
        invalid_reasons.append("actual_column_count_mismatch")
    if len(set(expected_columns)) != len(expected_columns):
        invalid_reasons.append("expected_duplicate_columns")
    if len(set(actual_columns)) != len(actual_columns):
        invalid_reasons.append("actual_duplicate_columns")

    missing = [column for column in expected_columns if column not in actual_columns]
    additional = [column for column in actual_columns if column not in expected_columns]
    reordered = (
        not missing
        and not additional
        and expected_columns != actual_columns
    )

    if invalid_reasons:
        classification = "invalid_fingerprint"
    elif expected_name != actual_name:
        classification = "result_set_name_changed"
    elif not missing and not additional and not reordered:
        classification = "identical"
    elif reordered:
        classification = "reordered"
    elif missing and additional:
        classification = "mixed"
    elif missing:
        classification = "subtractive"
    else:
        classification = "additive"

    accepted = classification == "identical"
    return {
        "classification": classification,
        "accepted": accepted,
        "action": "accept" if accepted else "quarantine_for_review",
        "expected_name": expected_name,
        "actual_name": actual_name,
        "missing_columns": missing,
        "additional_columns": additional,
        "same_columns_different_order": reordered,
        "invalid_reasons": invalid_reasons,
    }


def _asset_record(
    *,
    endpoint: str,
    season: str,
    team_id: str,
    measure_type: str,
    season_type: str,
    league_id: str,
    group_quantity: str,
    extra_parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity = raw_asset_identity(
        endpoint=endpoint,
        season=season,
        team_id=team_id,
        measure_type=measure_type,
        season_type=season_type,
        league_id=league_id,
        group_quantity=group_quantity,
        extra_parameters=extra_parameters,
    )
    return {
        "asset_id": stable_contract_id("raw-asset", identity),
        "identity": identity,
        "status": "planned",
        "attempt_count": 0,
        "last_error": None,
        "source_event": {
            "acquired_at": None,
            "http_status": None,
            "response_body_bytes": None,
            "raw_body_hash": None,
        },
        "cache": {
            "relative_path": None,
            "cache_file_bytes": None,
            "canonical_json_hash": None,
            "serialization_version": None,
        },
        "schema_verification": {
            "status": "pending",
            "fingerprints": [],
            "drift_classification": None,
        },
    }


def build_season_manifest(
    *,
    season: Any,
    team_ids: Iterable[Any],
    measures: Iterable[str] = REQUIRED_PAIR_MEASURES,
    endpoint: str = "TeamDashLineups",
    season_type: Any = "Regular Season",
    league_id: Any = "00",
    group_quantity: Any = "2",
    extra_parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, design-only season manifest with planned assets."""
    logical_identity = _normalized_manifest_identity(
        season=season,
        team_ids=team_ids,
        measures=measures,
        endpoint=endpoint,
        season_type=season_type,
        league_id=league_id,
        group_quantity=group_quantity,
        extra_parameters=extra_parameters,
    )
    assets = [
        _asset_record(
            endpoint=logical_identity["endpoint"],
            season=logical_identity["season"],
            team_id=team_id,
            measure_type=measure,
            season_type=logical_identity["season_type"],
            league_id=logical_identity["league_id"],
            group_quantity=logical_identity["group_quantity"],
            extra_parameters=logical_identity["extra_parameters"],
        )
        for team_id in logical_identity["team_ids"]
        for measure in logical_identity["measures"]
    ]
    return {
        "manifest_kind": MANIFEST_KIND,
        "contract_version": CONTRACT_VERSION,
        "manifest_id": stable_contract_id("season-manifest", logical_identity),
        "logical_identity": logical_identity,
        "expected_team_count": len(logical_identity["team_ids"]),
        "raw_assets": assets,
        "stages": {
            "raw_validation": "pending",
            "curated_parquet": "pending",
            "duckdb_registration": "pending",
        },
    }


def resume_actions(manifest: Mapping[str, Any]) -> list[dict[str, str]]:
    """Describe the next safe action for every raw asset without executing it."""
    actions = []
    contract_matches = manifest.get("contract_version") == CONTRACT_VERSION
    for asset in manifest.get("raw_assets", []):
        status = asset.get("status")
        cache = asset.get("cache", {})
        schema = asset.get("schema_verification", {})
        if not contract_matches:
            action = "migrate_or_rebuild_manifest"
        elif (
            status == "verified"
            and cache.get("canonical_json_hash")
            and cache.get("serialization_version")
            and schema.get("status") == "accepted"
        ):
            action = "skip_verified"
        elif status == "quarantined":
            action = "manual_schema_review"
        elif status in {"acquired", "verified"}:
            action = "verify_cached_asset"
        elif status in {"planned", "failed"}:
            action = "acquire_or_restore_cache"
        else:
            action = "invalid_status"
        actions.append({"asset_id": str(asset.get("asset_id")), "action": action})
    return actions


def validate_complete_season_manifest(
    manifest: Mapping[str, Any],
    *,
    expected_season: Any,
    expected_team_ids: Iterable[Any],
    required_measures: Iterable[str] = REQUIRED_PAIR_MEASURES,
    expected_endpoint: str = "TeamDashLineups",
    expected_season_type: Any = "Regular Season",
    expected_league_id: Any = "00",
    expected_group_quantity: Any = "2",
    expected_extra_parameters: Mapping[str, Any] | None = None,
    approved_schema_contract: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Validate the raw-manifest release gate for one complete 30-team season."""
    expected_identity = _normalized_manifest_identity(
        season=expected_season,
        team_ids=expected_team_ids,
        measures=required_measures,
        endpoint=expected_endpoint,
        season_type=expected_season_type,
        league_id=expected_league_id,
        group_quantity=expected_group_quantity,
        extra_parameters=expected_extra_parameters,
    )
    expected_teams = set(expected_identity["team_ids"])
    measures = tuple(expected_identity["measures"])
    assets = list(manifest.get("raw_assets", []))
    logical_identity = manifest.get("logical_identity")

    schema_contract_errors = []
    for measure in measures:
        measure_contract = approved_schema_contract.get(measure)
        if not isinstance(measure_contract, Mapping):
            schema_contract_errors.append(f"missing_measure_contract:{measure}")
            continue
        missing_names = sorted(set(REQUIRED_RESULT_SETS) - set(measure_contract))
        unexpected_names = sorted(set(measure_contract) - set(REQUIRED_RESULT_SETS))
        if missing_names:
            schema_contract_errors.append(
                f"missing_result_set_contract:{measure}:{','.join(missing_names)}"
            )
        if unexpected_names:
            schema_contract_errors.append(
                f"unexpected_result_set_contract:{measure}:{','.join(unexpected_names)}"
            )
        for result_set_name, fingerprint in measure_contract.items():
            errors = _fingerprint_errors(fingerprint)
            if errors:
                schema_contract_errors.append(
                    f"malformed_contract_fingerprint:{measure}:{result_set_name}:"
                    f"{','.join(errors)}"
                )
            elif fingerprint.get("name") != result_set_name:
                schema_contract_errors.append(
                    f"contract_result_set_name_mismatch:{measure}:{result_set_name}"
                )
    unexpected_measure_contracts = sorted(
        set(approved_schema_contract) - set(measures)
    )
    if unexpected_measure_contracts:
        schema_contract_errors.append(
            "unexpected_measure_contracts:" + ",".join(unexpected_measure_contracts)
        )

    manifest_identity_errors = []
    normalized_manifest_identity = None
    if not isinstance(logical_identity, Mapping):
        manifest_identity_errors.append("logical_identity_not_mapping")
    else:
        expected_fields = set(expected_identity)
        missing_fields = sorted(expected_fields - set(logical_identity))
        unexpected_fields = sorted(set(logical_identity) - expected_fields)
        if missing_fields:
            manifest_identity_errors.append(
                f"missing_logical_identity_fields:{','.join(missing_fields)}"
            )
        if unexpected_fields:
            manifest_identity_errors.append(
                f"unexpected_logical_identity_fields:{','.join(unexpected_fields)}"
            )
        try:
            normalized_manifest_identity = _normalized_manifest_identity(
                season=logical_identity.get("season"),
                team_ids=logical_identity.get("team_ids", []),
                measures=logical_identity.get("measures", []),
                endpoint=logical_identity.get("endpoint"),
                season_type=logical_identity.get("season_type"),
                league_id=logical_identity.get("league_id"),
                group_quantity=logical_identity.get("group_quantity"),
                extra_parameters=logical_identity.get("extra_parameters"),
            )
        except (TypeError, ValueError) as exc:
            manifest_identity_errors.append(f"logical_identity_normalization_error:{exc}")
        else:
            if dict(logical_identity) != normalized_manifest_identity:
                manifest_identity_errors.append("logical_identity_not_normalized")

    manifest_identity_mismatches = _field_mismatches(
        expected_identity,
        normalized_manifest_identity if normalized_manifest_identity is not None else {},
        path="logical_identity",
    )
    recomputed_manifest_id = (
        stable_contract_id("season-manifest", normalized_manifest_identity)
        if normalized_manifest_identity is not None
        else None
    )
    manifest_id_mismatch = None
    if manifest.get("manifest_id") != recomputed_manifest_id:
        manifest_id_mismatch = {
            "stored": manifest.get("manifest_id"),
            "recomputed": recomputed_manifest_id,
        }

    expected_asset_identities = [
        raw_asset_identity(
            endpoint=expected_identity["endpoint"],
            season=expected_identity["season"],
            team_id=team_id,
            measure_type=measure,
            season_type=expected_identity["season_type"],
            league_id=expected_identity["league_id"],
            group_quantity=expected_identity["group_quantity"],
            extra_parameters=expected_identity["extra_parameters"],
        )
        for team_id in expected_identity["team_ids"]
        for measure in expected_identity["measures"]
    ]

    asset_pairs = []
    asset_ids = []
    nonreproducible_asset_ids = []
    asset_id_mismatches = []
    malformed_asset_identities = []
    asset_identity_mismatches = []
    invalid_statuses = []
    unverified_assets = []
    missing_provenance = []
    unaccepted_schemas = []
    missing_schema_fingerprints = []
    missing_required_result_sets = []
    duplicate_result_set_fingerprints = []
    unexpected_result_set_fingerprints = []
    malformed_schema_fingerprints = []
    unaccepted_schema_fingerprints = []
    for index, asset in enumerate(assets):
        asset_id = asset.get("asset_id")
        asset_ids.append(asset_id)
        embedded_identity = asset.get("identity")
        try:
            identity_asset_id = stable_contract_id("raw-asset", embedded_identity)
        except (TypeError, ValueError):
            identity_asset_id = None
        if asset_id != identity_asset_id:
            nonreproducible_asset_ids.append(asset_id)
            asset_id_mismatches.append(
                {
                    "index": index,
                    "stored_asset_id": asset_id,
                    "recomputed_from_embedded_identity": identity_asset_id,
                }
            )

        normalized_asset_identity, identity_errors = _normalize_embedded_asset_identity(
            embedded_identity
        )
        if identity_errors:
            malformed_asset_identities.append(
                {"index": index, "asset_id": asset_id, "errors": identity_errors}
            )
        if index < len(expected_asset_identities):
            expected_asset_identity = expected_asset_identities[index]
            identity_mismatches = _field_mismatches(
                expected_asset_identity,
                normalized_asset_identity if normalized_asset_identity is not None else {},
                path="identity",
            )
            if identity_mismatches:
                asset_identity_mismatches.append(
                    {
                        "index": index,
                        "asset_id": asset_id,
                        "expected_asset_id": stable_contract_id(
                            "raw-asset", expected_asset_identity
                        ),
                        "mismatched_fields": identity_mismatches,
                    }
                )

        parameters = (
            embedded_identity.get("parameters", {})
            if isinstance(embedded_identity, Mapping)
            else {}
        )
        pair = (str(parameters.get("team_id")), str(parameters.get("measure_type")))
        asset_pairs.append(pair)
        if asset.get("status") not in RAW_ASSET_STATUSES:
            invalid_statuses.append(asset.get("asset_id"))
        if asset.get("status") != "verified":
            unverified_assets.append(asset.get("asset_id"))
        source_event = asset.get("source_event", {})
        cache = asset.get("cache", {})
        source_event_complete = (
            source_event.get("acquired_at")
            and source_event.get("http_status") == 200
            and isinstance(source_event.get("response_body_bytes"), int)
            and source_event.get("response_body_bytes") > 0
        )
        cache_provenance_complete = (
            cache.get("relative_path")
            and isinstance(cache.get("cache_file_bytes"), int)
            and cache.get("cache_file_bytes") > 0
            and cache.get("canonical_json_hash")
            and cache.get("serialization_version")
        )
        if not source_event_complete or not cache_provenance_complete:
            missing_provenance.append(asset.get("asset_id"))
        schema = asset.get("schema_verification", {})
        if (
            schema.get("status") != "accepted"
            or schema.get("drift_classification") != "identical"
        ):
            unaccepted_schemas.append(asset.get("asset_id"))
        fingerprints = schema.get("fingerprints")
        if not isinstance(fingerprints, list) or not fingerprints:
            missing_schema_fingerprints.append(asset.get("asset_id"))
            fingerprints = []
        fingerprint_names = [
            fingerprint.get("name")
            for fingerprint in fingerprints
            if isinstance(fingerprint, Mapping)
        ]
        name_counts = Counter(fingerprint_names)
        missing_names = [
            name for name in REQUIRED_RESULT_SETS if name_counts.get(name, 0) == 0
        ]
        duplicate_names = sorted(
            str(name) for name, count in name_counts.items() if count > 1
        )
        unexpected_names = sorted(
            str(name) for name in name_counts if name not in REQUIRED_RESULT_SETS
        )
        if missing_names:
            missing_required_result_sets.append(
                {"asset_id": asset_id, "result_sets": missing_names}
            )
        if duplicate_names:
            duplicate_result_set_fingerprints.append(
                {"asset_id": asset_id, "result_sets": duplicate_names}
            )
        if unexpected_names:
            unexpected_result_set_fingerprints.append(
                {"asset_id": asset_id, "result_sets": unexpected_names}
            )
        for fingerprint_index, fingerprint in enumerate(fingerprints):
            errors = _fingerprint_errors(fingerprint)
            if errors:
                malformed_schema_fingerprints.append(
                    {
                        "asset_id": asset_id,
                        "fingerprint_index": fingerprint_index,
                        "errors": errors,
                    }
                )
        if index < len(expected_asset_identities):
            expected_measure = expected_asset_identities[index]["parameters"][
                "measure_type"
            ]
            measure_contract = approved_schema_contract.get(expected_measure, {})
            fingerprints_by_name = {
                fingerprint.get("name"): fingerprint
                for fingerprint in fingerprints
                if isinstance(fingerprint, Mapping)
                and name_counts.get(fingerprint.get("name")) == 1
            }
            for result_set_name in REQUIRED_RESULT_SETS:
                expected_fingerprint = measure_contract.get(result_set_name)
                actual_fingerprint = fingerprints_by_name.get(result_set_name)
                if (
                    isinstance(expected_fingerprint, Mapping)
                    and isinstance(actual_fingerprint, Mapping)
                    and not _fingerprint_errors(actual_fingerprint)
                ):
                    drift = schema_drift_report(
                        expected_fingerprint, actual_fingerprint
                    )
                    if not drift["accepted"]:
                        unaccepted_schema_fingerprints.append(
                            {
                                "asset_id": asset_id,
                                "measure_type": expected_measure,
                                "result_set": result_set_name,
                                "classification": drift["classification"],
                            }
                        )

    expected_pairs = {(team_id, measure) for team_id in expected_teams for measure in measures}
    counts = Counter(asset_pairs)
    duplicate_pairs = sorted(pair for pair, count in counts.items() if count > 1)
    missing_pairs = sorted(expected_pairs - set(asset_pairs))
    unexpected_pairs = sorted(set(asset_pairs) - expected_pairs)

    checks = {
        "manifest_contract_matches": (
            manifest.get("manifest_kind") == MANIFEST_KIND
            and manifest.get("contract_version") == CONTRACT_VERSION
        ),
        "approved_schema_contract_valid": not schema_contract_errors,
        "manifest_identity_complete_and_normalized": not manifest_identity_errors,
        "manifest_identity_matches_expected_contract": not manifest_identity_mismatches,
        "manifest_id_matches_logical_identity": manifest_id_mismatch is None,
        "exactly_30_expected_teams": len(expected_teams) == 30,
        "declared_team_set_matches": (
            isinstance(normalized_manifest_identity, Mapping)
            and set(normalized_manifest_identity.get("team_ids", [])) == expected_teams
            and manifest.get("expected_team_count") == 30
        ),
        "declared_measures_match": (
            isinstance(normalized_manifest_identity, Mapping)
            and tuple(normalized_manifest_identity.get("measures", [])) == measures
        ),
        "manifest_team_set_matches": {
            team_id for team_id, _ in asset_pairs
        } == expected_teams,
        "exact_team_measure_matrix": not missing_pairs and not unexpected_pairs and not duplicate_pairs,
        "asset_ids_unique_and_reproducible": (
            len(set(asset_ids)) == len(asset_ids) and not nonreproducible_asset_ids
        ),
        "asset_identities_complete_and_normalized": not malformed_asset_identities,
        "asset_identities_match_manifest": (
            len(assets) == len(expected_asset_identities)
            and not asset_identity_mismatches
        ),
        "all_asset_statuses_valid": not invalid_statuses,
        "all_assets_verified": not unverified_assets,
        "all_assets_have_provenance": not missing_provenance,
        "all_schema_fingerprints_present": not missing_schema_fingerprints,
        "all_required_result_sets_present_once": (
            not missing_required_result_sets
            and not duplicate_result_set_fingerprints
            and not unexpected_result_set_fingerprints
        ),
        "all_schema_fingerprints_well_formed": not malformed_schema_fingerprints,
        "all_schemas_accepted": (
            not unaccepted_schemas
            and not schema_contract_errors
            and not missing_schema_fingerprints
            and not missing_required_result_sets
            and not duplicate_result_set_fingerprints
            and not unexpected_result_set_fingerprints
            and not malformed_schema_fingerprints
            and not unaccepted_schema_fingerprints
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "expected_asset_count": len(expected_pairs),
        "actual_asset_count": len(assets),
        "missing_team_measure_pairs": missing_pairs,
        "unexpected_team_measure_pairs": unexpected_pairs,
        "duplicate_team_measure_pairs": duplicate_pairs,
        "manifest_identity_errors": manifest_identity_errors,
        "manifest_identity_mismatches": manifest_identity_mismatches,
        "manifest_id_mismatch": manifest_id_mismatch,
        "asset_id_mismatches": asset_id_mismatches,
        "asset_identity_mismatches": asset_identity_mismatches,
        "malformed_asset_identities": malformed_asset_identities,
        "nonreproducible_asset_ids": nonreproducible_asset_ids,
        "invalid_status_asset_ids": invalid_statuses,
        "unverified_asset_ids": unverified_assets,
        "missing_provenance_asset_ids": missing_provenance,
        "unaccepted_schema_asset_ids": unaccepted_schemas,
        "schema_contract_errors": schema_contract_errors,
        "missing_schema_fingerprint_asset_ids": missing_schema_fingerprints,
        "missing_required_result_sets": missing_required_result_sets,
        "duplicate_result_set_fingerprints": duplicate_result_set_fingerprints,
        "unexpected_result_set_fingerprints": unexpected_result_set_fingerprints,
        "malformed_schema_fingerprints": malformed_schema_fingerprints,
        "unaccepted_schema_fingerprints": unaccepted_schema_fingerprints,
    }


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def possession_target_eligibility(
    *, poss: Any, off_rating: Any, def_rating: Any, net_rating: Any
) -> dict[str, Any]:
    """Derive explicit eligibility without mutating or imputing endpoint values."""
    reasons = []
    numeric_poss = _finite_number(poss)
    if numeric_poss is None:
        reasons.append("missing_or_nonnumeric_possessions")
    elif numeric_poss <= 0:
        reasons.append("nonpositive_possessions")
    for name, value in (
        ("off_rating", off_rating),
        ("def_rating", def_rating),
        ("net_rating", net_rating),
    ):
        if _finite_number(value) is None:
            reasons.append(f"missing_or_nonnumeric_{name}")
    return {"eligible": not reasons, "reasons": reasons}


def validate_curated_pair_records(
    records: Iterable[Mapping[str, Any]], *, expected_source_union_count: int
) -> dict[str, Any]:
    """Validate row preservation, keys, statuses, and derived target eligibility."""
    rows = list(records)
    keys = []
    invalid_keys = []
    invalid_statuses = []
    eligibility_mismatches = []
    source_presence_mismatches = []
    for index, row in enumerate(rows):
        try:
            key = observation_key(
                row.get("target_season"),
                row.get("team_id"),
                row.get("player_1_id"),
                row.get("player_2_id"),
                row.get("season_type"),
                row.get("league_id"),
            )
        except (TypeError, ValueError):
            invalid_keys.append(index)
            continue
        keys.append(key)
        stored_key = (
            str(row.get("league_id")),
            str(row.get("target_season")),
            str(row.get("season_type")),
            str(row.get("team_id")),
            str(row.get("player_1_id")),
            str(row.get("player_2_id")),
        )
        if stored_key != key:
            invalid_keys.append(index)
        if row.get("prior_history_status") not in PRIOR_HISTORY_STATUSES:
            invalid_statuses.append(index)
        base_present = row.get("base_row_present")
        advanced_present = row.get("advanced_row_present")
        if (
            not isinstance(base_present, bool)
            or not isinstance(advanced_present, bool)
            or not (base_present or advanced_present)
        ):
            source_presence_mismatches.append(index)
        derived = possession_target_eligibility(
            poss=row.get("advanced_poss"),
            off_rating=row.get("off_rating"),
            def_rating=row.get("def_rating"),
            net_rating=row.get("net_rating"),
        )
        if row.get("possession_rate_target_eligible") is not derived["eligible"]:
            eligibility_mismatches.append(index)
        if advanced_present is False and row.get("possession_rate_target_eligible") is not False:
            eligibility_mismatches.append(index)
        if list(row.get("target_eligibility_reasons", [])) != derived["reasons"]:
            eligibility_mismatches.append(index)

    duplicate_key_count = sum(
        count - 1 for count in Counter(keys).values() if count > 1
    )
    checks = {
        "all_source_union_rows_preserved": len(rows) == expected_source_union_count,
        "all_observation_keys_valid": not invalid_keys,
        "observation_keys_unique": duplicate_key_count == 0,
        "all_prior_history_statuses_valid": not invalid_statuses,
        "all_rows_have_source_presence": not source_presence_mismatches,
        "all_target_eligibility_values_reproducible": not eligibility_mismatches,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "row_count": len(rows),
        "duplicate_observation_key_count": duplicate_key_count,
        "invalid_key_row_indexes": invalid_keys,
        "invalid_prior_history_status_row_indexes": invalid_statuses,
        "source_presence_mismatch_row_indexes": source_presence_mismatches,
        "eligibility_mismatch_row_indexes": sorted(set(eligibility_mismatches)),
    }
