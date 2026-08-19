"""Extensible, leakage-aware registry contract for prior player feature sources."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from pair_fit_v2.phase1b_contract import normalize_season


FEATURE_SOURCE_STATUSES = frozenset({"observed", "proposed", "retired"})
FEATURE_FAMILIES = frozenset(
    {
        "capability",
        "role_style",
        "physical_context",
        "reliability",
        "team_context",
        "heliocentrism",
        "unresolved",
    }
)

DEFAULT_PLAYER_FEATURE_SOURCES: dict[str, dict[str, Any]] = {
    "nba_league_dash_player_stats_base_per100": {
        "source_id": "nba_league_dash_player_stats_base_per100",
        "source_version": "phase0f-observed-v1",
        "status": "observed",
        "entity_grain": "player_season",
        "source_kind": "nba_stats_endpoint",
        "source_locator": {
            "endpoint": "LeagueDashPlayerStats",
            "measure_type": "Base",
            "per_mode": "Per100Possessions",
        },
        "aggregation_contract": "one league-aggregate row per player-season as returned",
        "join_key_fields": ["feature_season", "player_id"],
        "availability_rule": "strictly_before_target_season",
        "feature_families": [
            "capability",
            "role_style",
            "reliability",
            "team_context",
        ],
        "field_contract": {
            "identity_fields": ["PLAYER_ID", "PLAYER_NAME"],
            "candidate_fields": [
                "AGE",
                "GP",
                "MIN",
                "FGM",
                "FGA",
                "FG_PCT",
                "FG3M",
                "FG3A",
                "FG3_PCT",
                "FTM",
                "FTA",
                "FT_PCT",
                "OREB",
                "DREB",
                "REB",
                "AST",
                "TOV",
                "STL",
                "BLK",
                "PTS",
            ],
        },
        "notes": "Observed source only; candidate fields are not an approved model feature set.",
    }
}


def validate_feature_source_spec(spec: Mapping[str, Any]) -> list[str]:
    """Return registry-contract errors for one source specification."""
    errors = []
    required = (
        "source_id",
        "source_version",
        "status",
        "entity_grain",
        "source_kind",
        "source_locator",
        "aggregation_contract",
        "join_key_fields",
        "availability_rule",
        "feature_families",
        "field_contract",
    )
    for field in required:
        if field not in spec:
            errors.append(f"missing_{field}")
    if spec.get("status") not in FEATURE_SOURCE_STATUSES:
        errors.append("invalid_status")
    if spec.get("entity_grain") != "player_season":
        errors.append("unsupported_entity_grain")
    for field in ("source_id", "source_version", "source_kind", "aggregation_contract"):
        if not str(spec.get(field, "")).strip():
            errors.append(f"empty_{field}")
    if not isinstance(spec.get("source_locator"), Mapping):
        errors.append("source_locator_must_be_mapping")
    join_keys = list(spec.get("join_key_fields", []))
    if "player_id" not in join_keys or "feature_season" not in join_keys:
        errors.append("join_keys_must_include_player_id_and_feature_season")
    if spec.get("availability_rule") != "strictly_before_target_season":
        errors.append("availability_rule_must_prevent_target_season_leakage")
    families = set(spec.get("feature_families", []))
    if not families or not families <= FEATURE_FAMILIES:
        errors.append("invalid_feature_families")
    if not isinstance(spec.get("field_contract"), Mapping):
        errors.append("field_contract_must_be_mapping")
    elif (
        spec.get("status") == "observed"
        and "heliocentrism" in families
        and not spec["field_contract"].get("metric_definitions")
    ):
        errors.append("observed_heliocentrism_requires_metric_definitions")
    return errors


def validate_feature_source_registry(
    registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate registry keys and every contained source contract."""
    source_errors = {}
    for registry_key, spec in registry.items():
        errors = validate_feature_source_spec(spec)
        if registry_key != spec.get("source_id"):
            errors.append("registry_key_must_match_source_id")
        if errors:
            source_errors[registry_key] = errors
    return {"valid": not source_errors, "source_errors": source_errors}


def register_feature_source(
    registry: Mapping[str, Mapping[str, Any]], spec: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    """Return a copied registry with one validated source added; never mutate input."""
    errors = validate_feature_source_spec(spec)
    if errors:
        raise ValueError(f"Invalid player feature source: {', '.join(errors)}")
    source_id = str(spec["source_id"])
    if source_id in registry:
        raise ValueError(f"Player feature source already registered: {source_id}")
    updated = deepcopy(dict(registry))
    updated[source_id] = deepcopy(dict(spec))
    return updated


def feature_season_precedes_target(feature_season: Any, target_season: Any) -> bool:
    """Enforce strict season ordering for prior-period player sources."""
    feature_start = int(normalize_season(feature_season).split("-", 1)[0])
    target_start = int(normalize_season(target_season).split("-", 1)[0])
    return feature_start < target_start
