"""Phase 2B complete 2023-24 raw-season acquisition and release audit.

Planning, import verification, and analysis are cache-only.  ``run_acquisition``
is the sole network-capable operation and requires an explicit live flag.
"""

from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS
from pair_fit_v2.lineup_audit import (
    attach_pair_context,
    extract_result_set,
    identify_zero_or_missing_possession_rows,
    join_pair_measures,
    result_set_rows,
    summarize_advanced_targets,
    summarize_pair_rows,
)
from pair_fit_v2.multi_team_audit import schema_fingerprint
from pair_fit_v2.phase1b_contract import schema_drift_report, stable_contract_id
from pair_fit_v2.phase1c_manifest import (
    TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
    atomic_write_bytes_new,
    atomic_write_json,
    canonical_json_hash,
    raw_body_hash,
    read_json,
    validate_payload_structure,
)
from pair_fit_v2.phase2a_historical_canary import (
    CANONICALIZATION,
    CanaryStore,
    SERIALIZATION_VERSION,
    _boundary,
    _extreme_rating_summary,
    _pair_identifier_detail,
    _pair_rows,
    _player_rows,
    _quantiles,
    analyze_cache as analyze_phase2a_cache,
    expected_manifest as expected_phase2a_manifest,
    verify_asset_cache as verify_phase2a_asset_cache,
)
from pair_fit_v2.player_audit import (
    attach_prior_context,
    join_pairs_to_prior_players,
    player_rows_by_id,
    summarize_exposure_weighted_coverage,
    summarize_pair_level_coverage,
    summarize_player_level_coverage,
)


TARGET_SEASON = "2023-24"
PRIOR_FEATURE_SEASON = "2022-23"
SEASON_TYPE = "Regular Season"
LEAGUE_ID = "00"
GROUP_QUANTITY = "2"
ENDPOINT = "TeamDashLineups"
MEASURES = ("Base", "Advanced")
TIMEOUT_SECONDS = 30
MAX_NEW_ATTEMPTS = 50
MANIFEST_VERSION = "phase2b.raw-season-release.v1"
ANALYSIS_VERSION = "phase2b.release-audit.v1"
PAIR_URL = "https://stats.nba.com/stats/teamdashlineups"
CANARY_TEAM_IDS = frozenset(
    {"1610612738", "1610612744", "1610612751", "1610612764", "1610612766"}
)
THRESHOLDS = (1, 5, 10, 25, 50, 100, 200, 300)

PHASE1_HASHES = {
    "phase1c_manifest": "5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c",
    "phase1d_ledger": "f6873ebe3a4feb8940ec092bb0501d9067eddeed2391663c10c864d3f1a3dee9",
    "phase1e_ledger": "5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde",
}
PHASE2A_HASHES = {
    "manifest": "55406bb879d2fb93edd490b11b39bbcdb3a4de85a17a9bd0672444d9680ec6e0",
    "ledger": "78b4242de669c3a22d88d4cac3b7d26c671c579e1aa1cb474da1f81939fcc1bd",
}


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def phase1c_manifest_path(cache_root: Path) -> Path:
    return cache_root / "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"


def phase2b_manifest_path(cache_root: Path) -> Path:
    return cache_root / "phase2b/release_manifest.json"


def phase2b_ledger_path(cache_root: Path) -> Path:
    return cache_root / "phase2b/attempt_ledger.json"


def validate_season_scope(target_season: str, prior_feature_season: str) -> None:
    if (target_season, prior_feature_season) != (TARGET_SEASON, PRIOR_FEATURE_SEASON):
        raise ValueError("Phase 2B authorizes only target 2023-24 and prior 2022-23")
    if int(prior_feature_season[:4]) >= int(target_season[:4]):
        raise ValueError("Prior-player season must precede the target season")


def load_team_inventory(cache_root: Path) -> tuple[tuple[str, str], ...]:
    """Load the frozen franchise-ID inventory from the verified Phase 1C manifest."""
    manifest = read_json(phase1c_manifest_path(cache_root))
    directory = manifest.get("team_directory")
    if not isinstance(directory, Mapping) or len(directory) != 30:
        raise ValueError("Phase 1C team inventory must contain 30 teams")
    asset_teams = {
        str(asset.get("identity", {}).get("parameters", {}).get("team_id"))
        for asset in manifest.get("raw_assets", [])
    }
    if asset_teams != set(directory):
        raise ValueError("Phase 1C manifest assets do not match its team inventory")
    return tuple(
        (team_id, str(directory[team_id]["team_name"]))
        for team_id in sorted(directory, key=int)
    )


def pair_identity(team_id: str, measure: str, authorized_team_ids: set[str]) -> dict[str, Any]:
    identity = {
        "endpoint": ENDPOINT,
        "target_season": TARGET_SEASON,
        "prior_feature_season": PRIOR_FEATURE_SEASON,
        "parameters": {
            **TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
            "league_id": LEAGUE_ID,
            "season": TARGET_SEASON,
            "season_type": "regular-season",
            "team_id": str(team_id),
            "group_quantity": GROUP_QUANTITY,
            "measure_type": measure,
        },
    }
    validate_pair_identity(identity, authorized_team_ids)
    return identity


def validate_pair_identity(identity: Mapping[str, Any], authorized_team_ids: set[str]) -> None:
    validate_season_scope(str(identity.get("target_season")), str(identity.get("prior_feature_season")))
    params = identity.get("parameters")
    if identity.get("endpoint") != ENDPOINT or not isinstance(params, Mapping):
        raise ValueError("Only TeamDashLineups pair identities are authorized")
    if (
        params.get("season") != TARGET_SEASON
        or params.get("season_type") != "regular-season"
        or params.get("league_id") != LEAGUE_ID
        or params.get("group_quantity") != GROUP_QUANTITY
        or params.get("measure_type") not in MEASURES
        or str(params.get("team_id")) not in authorized_team_ids
    ):
        raise ValueError("Unauthorized Phase 2B pair request identity")
    if params.get("DateFrom") not in (None, "") or params.get("DateTo") not in (None, ""):
        raise ValueError("Date-window requests are prohibited")
    if str(params.get("LastNGames")) != "0":
        raise ValueError("LastNGames diagnostics are prohibited")
    serialized = json.dumps(identity, sort_keys=True)
    if "2025-26" in serialized or "2024-25" in serialized:
        raise ValueError("Future/non-target season cannot satisfy a Phase 2B identity")


def request_parameters(identity: Mapping[str, Any], authorized_team_ids: set[str]) -> dict[str, Any]:
    validate_pair_identity(identity, authorized_team_ids)
    params = dict(identity["parameters"])
    params.pop("season_type")
    core = {
        "LeagueID": params.pop("league_id"),
        "Season": params.pop("season"),
        "SeasonType": SEASON_TYPE,
        "TeamID": params.pop("team_id"),
        "GroupQuantity": params.pop("group_quantity"),
        "MeasureType": params.pop("measure_type"),
    }
    return {**params, **core}


def release_asset_id(identity: Mapping[str, Any]) -> str:
    return stable_contract_id("phase2b-pair-release", identity)


def _safe_id(value: str) -> str:
    return value.replace(":", "_")


def _phase2a_context(cache_root: Path) -> tuple[CanaryStore, dict[str, Any], dict[str, Any]]:
    store = CanaryStore(cache_root, expected_phase2a_manifest(cache_root))
    manifest = store.load()
    analysis = analyze_phase2a_cache(store)
    if (
        _sha256_file(store.path) != PHASE2A_HASHES["manifest"]
        or _sha256_file(store.ledger_path) != PHASE2A_HASHES["ledger"]
        or analysis["deterministic_analysis_sha256"]
        != "a2af422b8e912396aa7eb2ec39089ece52113711ebf7476f05a994fdc1a26340"
        or analysis["phase2b_decision"] != "go: complete 2023-24 raw acquisition authorized"
    ):
        raise ValueError("Post-Phase-2A.1 prerequisite mismatch")
    return store, manifest, analysis


def _source_snapshot(asset: Mapping[str, Any]) -> dict[str, Any]:
    cache = asset["cache"]
    return {
        "source_asset_id": asset["asset_id"],
        "source_identity": deepcopy(asset["identity"]),
        "source_cache_path": cache["relative_path"],
        "source_metadata_path": cache["metadata_relative_path"],
        "raw_body_hash": cache["raw_body_hash"],
        "canonical_json_hash": cache["canonical_json_hash"],
        "cache_file_bytes": cache["cache_file_bytes"],
        "source_event": deepcopy(asset.get("source_event")),
        "schema_verification": deepcopy(asset.get("schema_verification")),
        "reuse_provenance": "immutable_phase2a_verified_source",
    }


def build_expected_manifest(cache_root: Path) -> dict[str, Any]:
    validate_season_scope(TARGET_SEASON, PRIOR_FEATURE_SEASON)
    teams = load_team_inventory(cache_root)
    team_ids = {team_id for team_id, _ in teams}
    source_store, source_manifest, _ = _phase2a_context(cache_root)
    source_pairs = {
        (
            asset["identity"]["parameters"].get("team_id"),
            asset["identity"]["parameters"].get("measure_type"),
        ): asset
        for asset in source_manifest["raw_assets"][:10]
    }
    assets = []
    for ordinal, (team_id, team_name, measure) in enumerate(
        ((tid, name, measure) for tid, name in teams for measure in MEASURES), 1
    ):
        identity = pair_identity(team_id, measure, team_ids)
        rid = release_asset_id(identity)
        imported = team_id in CANARY_TEAM_IDS
        entry = {
            "ordinal": ordinal,
            "release_asset_id": rid,
            "identity": identity,
            "team_name": team_name,
            "mode": "imported_reuse" if imported else "new_acquisition",
            "status": "reused_verified" if imported else "planned",
            "attempt_count": 0,
            "attempt_history": [],
            "transition_history": [],
            "last_error": None,
            "schema_verification": None,
            "source_event": None,
        }
        if imported:
            source = source_pairs.get((team_id, measure))
            if source is None:
                raise ValueError(f"Missing Phase 2A canary source for {team_id} {measure}")
            entry["source_reference"] = _source_snapshot(source)
            entry["cache"] = None
        else:
            stem = _safe_id(rid)
            entry["source_reference"] = None
            entry["cache"] = {
                "relative_path": f"phase2b/raw/{stem}.json",
                "metadata_relative_path": f"phase2b/raw/{stem}.metadata.json",
                "cache_file_bytes": None,
                "raw_body_hash": None,
                "canonical_json_hash": None,
                "canonical_json_hash_algorithm": CANONICALIZATION,
                "serialization_version": SERIALIZATION_VERSION,
            }
        assets.append(entry)
    dependencies = []
    for label, source in zip(("Per100Possessions", "Totals"), source_manifest["raw_assets"][10:12]):
        dependencies.append(
            {
                "dependency": f"2022-23 player Base/{label}",
                "status": "reused_verified",
                **_source_snapshot(source),
            }
        )
    logical_identity = {
        "target_season": TARGET_SEASON,
        "prior_feature_season": PRIOR_FEATURE_SEASON,
        "season_type": "regular-season",
        "league_id": LEAGUE_ID,
        "group_quantity": GROUP_QUANTITY,
        "pair_assets": [entry["identity"] for entry in assets],
        "player_dependencies": [dependency["source_identity"] for dependency in dependencies],
    }
    return {
        "manifest_version": MANIFEST_VERSION,
        "manifest_id": stable_contract_id("phase2b-release-manifest", logical_identity),
        "logical_identity": logical_identity,
        "authorization": {"maximum_new_live_attempts": MAX_NEW_ATTEMPTS, "retries": 0},
        "team_directory": {tid: {"team_name": name} for tid, name in teams},
        "approved_pair_schema_contract": deepcopy(source_manifest["pair_schema_contract"]),
        "approved_pair_schema_contract_id": source_manifest["pair_schema_contract_id"],
        "imported_phase2a_manifest_hash": _sha256_file(source_store.path),
        "imported_phase2a_ledger_hash": _sha256_file(source_store.ledger_path),
        "player_dependencies": dependencies,
        "transition_sequence": 0,
        "created_at": None,
        "updated_at": None,
        "release_analysis_failure": None,
        "pair_assets": assets,
    }


def validate_manifest(manifest: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    for key in (
        "manifest_version",
        "manifest_id",
        "logical_identity",
        "authorization",
        "team_directory",
        "approved_pair_schema_contract",
        "approved_pair_schema_contract_id",
        "imported_phase2a_manifest_hash",
        "imported_phase2a_ledger_hash",
        "player_dependencies",
    ):
        if manifest.get(key) != expected.get(key):
            raise ValueError(f"Phase 2B manifest mismatch: {key}")
    assets = manifest.get("pair_assets")
    if not isinstance(assets, list) or len(assets) != 60:
        raise ValueError("Phase 2B release must contain exactly 60 pair entries")
    if [asset.get("identity") for asset in assets] != [asset["identity"] for asset in expected["pair_assets"]]:
        raise ValueError("Phase 2B pair order or identity mismatch")
    team_ids = set(manifest["team_directory"])
    ids: set[str] = set()
    paths: set[str] = set()
    imports = new_assets = 0
    for asset in assets:
        validate_pair_identity(asset["identity"], team_ids)
        if asset.get("release_asset_id") != release_asset_id(asset["identity"]):
            raise ValueError("Phase 2B release asset ID mismatch")
        if asset["release_asset_id"] in ids:
            raise ValueError("Duplicate Phase 2B release asset ID")
        ids.add(asset["release_asset_id"])
        if asset["mode"] == "imported_reuse":
            imports += 1
            if asset.get("attempt_count") != 0 or asset.get("attempt_history"):
                raise ValueError("Imported sources cannot acquire invented Phase 2B attempts")
            if asset.get("source_reference") != expected["pair_assets"][asset["ordinal"] - 1]["source_reference"]:
                raise ValueError("Imported source provenance changed")
        elif asset["mode"] == "new_acquisition":
            new_assets += 1
            path = str(asset.get("cache", {}).get("relative_path"))
            if not path.startswith("phase2b/raw/") or path in paths:
                raise ValueError("Phase 2B raw-cache path collision or namespace escape")
            paths.add(path)
        else:
            raise ValueError("Unknown Phase 2B release-entry mode")
    if (imports, new_assets, len(team_ids)) != (10, 50, 30):
        raise ValueError("Phase 2B must contain 10 imports, 50 new assets, and 30 teams")


class ReleaseStore:
    def __init__(
        self,
        cache_root: Path,
        expected: Mapping[str, Any],
        *,
        clock: Callable[[], str],
    ):
        self.cache_root = Path(cache_root)
        self.expected = deepcopy(expected)
        self.path = phase2b_manifest_path(self.cache_root)
        self.ledger_path = phase2b_ledger_path(self.cache_root)
        self.clock = clock

    def create_or_load(self) -> dict[str, Any]:
        if self.path.exists():
            return self.load()
        manifest = deepcopy(self.expected)
        manifest["created_at"] = self.clock()
        manifest["updated_at"] = manifest["created_at"]
        self.save(manifest)
        return manifest

    def load(self) -> dict[str, Any]:
        manifest = read_json(self.path)
        validate_manifest(manifest, self.expected)
        return manifest

    def save(self, manifest: dict[str, Any]) -> None:
        validate_manifest(manifest, self.expected)
        manifest["updated_at"] = self.clock()
        atomic_write_json(self.path, manifest)
        ledger = {
            "ledger_version": "phase2b.attempt-ledger.v1",
            "manifest_id": manifest["manifest_id"],
            "authorization": manifest["authorization"],
            "attempts": [
                {
                    "ordinal": asset["ordinal"],
                    "release_asset_id": asset["release_asset_id"],
                    "mode": asset["mode"],
                    "identity": asset["identity"],
                    "status": asset["status"],
                    "attempt_history": asset["attempt_history"],
                    "last_error": asset["last_error"],
                }
                for asset in manifest["pair_assets"]
            ],
        }
        atomic_write_json(self.ledger_path, ledger)

    def transition(
        self, manifest: dict[str, Any], asset: dict[str, Any], status: str, category: str, detail: str | None = None
    ) -> None:
        manifest["transition_sequence"] += 1
        asset["status"] = status
        asset["transition_history"].append(
            {
                "sequence": manifest["transition_sequence"],
                "at": self.clock(),
                "status": status,
                "category": category,
                "detail": detail,
            }
        )
        self.save(manifest)


def create_store(cache_root: Path, *, clock: Callable[[], str] | None = None) -> ReleaseStore:
    from pair_fit_v2.phase2a_historical_canary import utc_now

    return ReleaseStore(cache_root, build_expected_manifest(cache_root), clock=clock or utc_now)


def _validate_returned_identity(payload: Mapping[str, Any], identity: Mapping[str, Any]) -> None:
    returned = payload.get("parameters")
    if not isinstance(returned, Mapping):
        raise ValueError("Response lacks request-parameter identity")
    params = identity["parameters"]
    expected = {
        "Season": TARGET_SEASON,
        "SeasonType": SEASON_TYPE,
        "MeasureType": params["measure_type"],
        "TeamID": int(params["team_id"]),
        "GroupQuantity": int(GROUP_QUANTITY),
    }
    for key, value in expected.items():
        if str(returned.get(key)) != str(value):
            raise ValueError(f"Response identity mismatch for {key}: {returned.get(key)!r}")
    if returned.get("LeagueID") not in (None, LEAGUE_ID, 0, "0"):
        raise ValueError("Response league identity mismatch")


def validate_response(payload: Mapping[str, Any], identity: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    validate_pair_identity(identity, set(manifest["team_directory"]))
    _validate_returned_identity(payload, identity)
    validation = validate_payload_structure(payload)
    if set(validation["row_counts"]) != {"Overall", "Lineups"}:
        raise ValueError("Pair payload requires exactly Overall and Lineups result sets")
    if validation["row_counts"]["Overall"] != 1 or validation["row_counts"]["Lineups"] <= 0:
        raise ValueError("Unexpected empty or non-singleton full-season result sets")
    overall = result_set_rows(extract_result_set(dict(payload), "Overall"))
    if str(overall[0].get("TEAM_ID")) != identity["parameters"]["team_id"]:
        raise ValueError("Pair response team context mismatch")
    expected = manifest["approved_pair_schema_contract"][identity["parameters"]["measure_type"]]
    actual = {item["name"]: item for item in validation["fingerprints"]}
    drift = {}
    for name in set(expected) | set(actual):
        if name not in expected or name not in actual:
            drift[name] = {"classification": "result_set_name_changed", "accepted": False}
        else:
            drift[name] = schema_drift_report(expected[name], actual[name])
    rejected = {name: value["classification"] for name, value in drift.items() if not value["accepted"]}
    return {
        **validation,
        "drift_results": drift,
        "drift_classification": "identical" if not rejected else "non_identical",
        "accepted": not rejected,
        "rejected": rejected,
    }


def verify_release_asset(asset: Mapping[str, Any], store: ReleaseStore, manifest: Mapping[str, Any]) -> dict[str, Any]:
    if asset["mode"] == "imported_reuse":
        source_store, source_manifest, _ = _phase2a_context(store.cache_root)
        matches = [
            item
            for item in source_manifest["raw_assets"][:10]
            if item["asset_id"] == asset["source_reference"]["source_asset_id"]
        ]
        if len(matches) != 1 or matches[0]["identity"] != asset["identity"]:
            raise ValueError("Imported source identity mismatch")
        replay = verify_phase2a_asset_cache(matches[0], store.cache_root, source_manifest)
        source = asset["source_reference"]
        if (
            replay["raw_body_hash"] != source["raw_body_hash"]
            or replay["canonical_json_hash"] != source["canonical_json_hash"]
            or replay["cache_file_bytes"] != source["cache_file_bytes"]
            or source_manifest["raw_assets"][matches[0]["ordinal"] - 1].get("source_event")
            != source["source_event"]
        ):
            raise ValueError("Imported source hash or provenance mismatch")
        validation = validate_response(replay["payload"], asset["identity"], manifest)
        if not validation["accepted"]:
            raise ValueError("Imported pair schema mismatch")
        return {**replay, **validation, "provenance": "imported_phase2a_reuse"}
    cache = asset["cache"]
    path = store.cache_root / cache["relative_path"]
    metadata_path = store.cache_root / cache["metadata_relative_path"]
    body = path.read_bytes()
    if len(body) != cache.get("cache_file_bytes") or raw_body_hash(body) != cache.get("raw_body_hash"):
        raise ValueError("Phase 2B raw cache byte/hash mismatch")
    payload = json.loads(body.decode("utf-8"))
    if canonical_json_hash(payload) != cache.get("canonical_json_hash"):
        raise ValueError("Phase 2B canonical JSON hash mismatch")
    validation = validate_response(payload, asset["identity"], manifest)
    if not validation["accepted"]:
        raise ValueError("Phase 2B cached schema mismatch")
    metadata = read_json(metadata_path)
    if (
        metadata.get("release_asset_id") != asset["release_asset_id"]
        or metadata.get("identity") != asset["identity"]
        or metadata.get("cache") != cache
        or metadata.get("source_event") != asset.get("source_event")
    ):
        raise ValueError("Phase 2B metadata provenance mismatch")
    return {
        "release_asset_id": asset["release_asset_id"],
        "payload": payload,
        **validation,
        "raw_body_hash": cache["raw_body_hash"],
        "canonical_json_hash": cache["canonical_json_hash"],
        "cache_file_bytes": len(body),
        "provenance": "phase2b_live_acquisition",
    }


def verify_all_imports_and_dependencies(store: ReleaseStore) -> dict[str, Any]:
    manifest = store.load()
    imported = [asset for asset in manifest["pair_assets"] if asset["mode"] == "imported_reuse"]
    imported_results = [verify_release_asset(asset, store, manifest) for asset in imported]
    source_store, source_manifest, source_analysis = _phase2a_context(store.cache_root)
    dependencies = []
    for dependency in manifest["player_dependencies"]:
        matches = [
            asset
            for asset in source_manifest["raw_assets"][10:]
            if asset["asset_id"] == dependency["source_asset_id"]
        ]
        if len(matches) != 1:
            raise ValueError("Player dependency source mismatch")
        replay = verify_phase2a_asset_cache(matches[0], store.cache_root, source_manifest)
        if (
            replay["raw_body_hash"] != dependency["raw_body_hash"]
            or replay["canonical_json_hash"] != dependency["canonical_json_hash"]
        ):
            raise ValueError("Player dependency hash mismatch")
        dependencies.append(replay)
    return {
        "network_calls": 0,
        "imported_pair_assets_verified": len(imported_results),
        "player_dependencies_verified": len(dependencies),
        "phase2a_manifest_hash": _sha256_file(source_store.path),
        "phase2a_ledger_hash": _sha256_file(source_store.ledger_path),
        "phase2a_analysis_hash": source_analysis["deterministic_analysis_sha256"],
    }


def dry_run_plan(store: ReleaseStore) -> dict[str, Any]:
    replay = verify_all_imports_and_dependencies(store)
    manifest = store.load()
    actions = []
    for asset in manifest["pair_assets"]:
        if asset["mode"] == "imported_reuse":
            action = "reuse_verified_phase2a_source"
        elif asset["status"] == "verified":
            verify_release_asset(asset, store, manifest)
            action = "reuse_verified_phase2b_cache"
        elif asset["status"] == "planned":
            action = "acquire"
        else:
            action = "stop"
        actions.append(
            {
                "ordinal": asset["ordinal"],
                "team_id": asset["identity"]["parameters"]["team_id"],
                "team_name": asset["team_name"],
                "measure": asset["identity"]["parameters"]["measure_type"],
                "release_asset_id": asset["release_asset_id"],
                "action": action,
                "identity": asset["identity"],
                "cache_path": (
                    asset["source_reference"]["source_cache_path"]
                    if asset["mode"] == "imported_reuse"
                    else asset["cache"]["relative_path"]
                ),
                "request_parameters": request_parameters(
                    asset["identity"], set(manifest["team_directory"])
                ),
            }
        )
    return {
        "dry_run": True,
        "network_calls": 0,
        "manifest_id": manifest["manifest_id"],
        "pair_entries": len(actions),
        "team_count": len(manifest["team_directory"]),
        "initial_imported_reuses": sum(action["action"] == "reuse_verified_phase2a_source" for action in actions),
        "planned_or_remaining_acquisitions": sum(action["action"] == "acquire" for action in actions),
        "continuation_reuses": sum(action["action"] == "reuse_verified_phase2b_cache" for action in actions),
        "player_dependencies": len(manifest["player_dependencies"]),
        "import_replay": replay,
        "actions": actions,
    }


def persist_dry_run(store: ReleaseStore) -> dict[str, Any]:
    """Persist the deterministic plan and exact new-live identity allowlist."""
    plan = dry_run_plan(store)
    allowlist = {
        "allowlist_version": "phase2b.live-allowlist.v1",
        "manifest_id": plan["manifest_id"],
        "maximum_new_live_attempts": MAX_NEW_ATTEMPTS,
        "authorized_assets": [
            {
                "ordinal": action["ordinal"],
                "release_asset_id": action["release_asset_id"],
                "identity": action["identity"],
            }
            for action in plan["actions"]
            if action["action"] == "acquire"
        ],
    }
    if len(allowlist["authorized_assets"]) > MAX_NEW_ATTEMPTS:
        raise ValueError("Dry-run allowlist exceeds the Phase 2B budget")
    plan_path = store.cache_root / "phase2b/dry_run.json"
    allowlist_path = store.cache_root / "phase2b/live_allowlist.json"
    atomic_write_json(plan_path, plan)
    atomic_write_json(allowlist_path, allowlist)
    return {
        **plan,
        "dry_run_path": str(plan_path.relative_to(store.cache_root)).replace("\\", "/"),
        "live_allowlist_path": str(allowlist_path.relative_to(store.cache_root)).replace("\\", "/"),
        "live_allowlist_count": len(allowlist["authorized_assets"]),
        "dry_run_sha256": _sha256_file(plan_path),
        "live_allowlist_sha256": _sha256_file(allowlist_path),
    }


@dataclass(frozen=True)
class TransportResult:
    status_code: int
    body: bytes
    elapsed_seconds: float


class TransportError(RuntimeError):
    def __init__(self, category: str, detail: str):
        super().__init__(detail)
        self.category = category
        self.detail = detail


def direct_transport(identity: Mapping[str, Any], timeout_seconds: int = TIMEOUT_SECONDS) -> TransportResult:
    team_ids = {
        team_id for team_id, _team_name in load_team_inventory(Path("research/pair-fit-v2/cache"))
    }
    validate_pair_identity(identity, team_ids)
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    started = time.perf_counter()
    try:
        response = session.get(
            PAIR_URL,
            params=request_parameters(identity, team_ids),
            timeout=timeout_seconds,
        )
        return TransportResult(response.status_code, response.content, time.perf_counter() - started)
    except requests.Timeout as exc:
        raise TransportError("timeout", str(exc)) from exc
    except requests.exceptions.SSLError as exc:
        raise TransportError("tls_failure", str(exc)) from exc
    except requests.ConnectionError as exc:
        raise TransportError("connection_or_dns_failure", str(exc)) from exc
    except requests.RequestException as exc:
        raise TransportError("request_failure", str(exc)) from exc
    finally:
        session.close()


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _positive_target_failures(rows: list[dict[str, Any]], tolerance: float = 0.1000000001) -> list[dict[str, Any]]:
    failures = []
    for row in rows:
        poss = _numeric(row.get("POSS"))
        if poss is None or poss <= 0:
            continue
        values = [_numeric(row.get(field)) for field in ("OFF_RATING", "DEF_RATING", "NET_RATING")]
        if any(value is None for value in values):
            failures.append({"pair_key": row.get("pair_key"), "reason": "missing_standard_rating"})
            continue
        offense, defense, net = values
        if abs(net - (offense - defense)) > tolerance:
            failures.append(
                {
                    "pair_key": row.get("pair_key"),
                    "reason": "standard_net_identity_failure",
                    "difference": net - (offense - defense),
                }
            )
    return failures


def audit_team_payloads(team_id: str, base_payload: Mapping[str, Any], advanced_payload: Mapping[str, Any]) -> dict[str, Any]:
    base = _pair_rows(base_payload, TARGET_SEASON, team_id)
    advanced = _pair_rows(advanced_payload, TARGET_SEASON, team_id)
    base_identity = summarize_pair_rows(base)
    advanced_identity = summarize_pair_rows(advanced)
    reconciliation = join_pair_measures(base, advanced)
    failures = _positive_target_failures(advanced)
    clean = (
        base_identity["same_player_or_malformed_rows"] == 0
        and advanced_identity["same_player_or_malformed_rows"] == 0
        and base_identity["duplicate_canonical_pairs"] == 0
        and advanced_identity["duplicate_canonical_pairs"] == 0
        and reconciliation["base_only_pairs"] == 0
        and reconciliation["advanced_only_pairs"] == 0
        and reconciliation["one_to_one"]
        and not failures
    )
    return {
        "team_id": team_id,
        "base_identity": base_identity,
        "advanced_identity": advanced_identity,
        "reconciliation": reconciliation,
        "positive_possession_target_failures": failures,
        "clean_release_gate": clean,
    }


def _team_payloads(team_id: str, store: ReleaseStore, manifest: Mapping[str, Any]) -> dict[str, Any]:
    payloads = {}
    for asset in manifest["pair_assets"]:
        params = asset["identity"]["parameters"]
        if params["team_id"] == team_id and asset["status"] in {"verified", "reused_verified"}:
            payloads[params["measure_type"]] = verify_release_asset(asset, store, manifest)["payload"]
    return payloads


def _run_result(manifest: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    counts = Counter(asset["status"] for asset in manifest["pair_assets"])
    new_attempts = sum(len(asset["attempt_history"]) for asset in manifest["pair_assets"])
    return {
        "authorized_new_attempts": MAX_NEW_ATTEMPTS,
        "new_attempts": new_attempts,
        "new_verified": sum(
            asset["mode"] == "new_acquisition" and asset["status"] == "verified"
            for asset in manifest["pair_assets"]
        ),
        "imported_reused": counts["reused_verified"],
        "failed": counts["failed"],
        "quarantined": counts["quarantined"],
        "unattempted": counts["planned"],
        "remaining_budget": MAX_NEW_ATTEMPTS - new_attempts,
        **extra,
    }


def run_acquisition(
    store: ReleaseStore,
    *,
    live_acquisition: bool,
    timeout_seconds: int = TIMEOUT_SECONDS,
    delay_seconds: float = 1.0,
    transport: Callable[[Mapping[str, Any], int], TransportResult] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if not live_acquisition:
        raise ValueError("Live acquisition requires explicit live_acquisition=True")
    if timeout_seconds != TIMEOUT_SECONDS or delay_seconds < 1.0:
        raise ValueError("Phase 2B requires timeout=30 and at least one-second delay")
    verify_all_imports_and_dependencies(store)
    transport = transport or direct_transport
    manifest = store.load()
    attempts_so_far = sum(len(asset["attempt_history"]) for asset in manifest["pair_assets"])
    if attempts_so_far > MAX_NEW_ATTEMPTS:
        raise ValueError("Phase 2B cumulative live-attempt budget exceeded")
    for asset in manifest["pair_assets"]:
        if asset["mode"] == "imported_reuse":
            verify_release_asset(asset, store, manifest)
            continue
        if asset["status"] == "verified":
            try:
                verify_release_asset(asset, store, manifest)
            except Exception as exc:
                asset["last_error"] = {"category": "corrupt_verified_cache", "detail": str(exc)}
                store.transition(manifest, asset, "failed", "corrupt_verified_cache", str(exc))
                return _run_result(manifest, completed=False, stop_category="corrupt_verified_cache")
            continue
        if asset["status"] != "planned":
            return _run_result(manifest, completed=False, stop_category=f"existing_{asset['status']}")
        if asset["attempt_count"] or attempts_so_far >= MAX_NEW_ATTEMPTS:
            return _run_result(manifest, completed=False, stop_category="retry_or_budget_prohibited")
        cache_path = store.cache_root / asset["cache"]["relative_path"]
        metadata_path = store.cache_root / asset["cache"]["metadata_relative_path"]
        if cache_path.exists() or metadata_path.exists():
            return _run_result(manifest, completed=False, stop_category="unverified_cache_collision")
        attempt = {
            "attempt_number": 1,
            "request_kind": "phase2b_live",
            "started_at": store.clock(),
            "status": "started",
            "timeout_seconds": timeout_seconds,
        }
        asset["attempt_count"] = 1
        asset["attempt_history"].append(attempt)
        store.save(manifest)
        attempts_so_far += 1
        try:
            response = transport(asset["identity"], timeout_seconds)
            attempt.update(
                {
                    "latency_seconds": response.elapsed_seconds,
                    "http_status": response.status_code,
                    "response_body_bytes": len(response.body),
                }
            )
            if response.status_code != 200:
                raise TransportError("non_200_http", f"HTTP {response.status_code}")
            try:
                payload = json.loads(response.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise TransportError("invalid_json", str(exc)) from exc
            try:
                validation = validate_response(payload, asset["identity"], manifest)
            except ValueError as exc:
                raise TransportError("validation_failure", str(exc)) from exc
            asset["schema_verification"] = {
                "status": "accepted" if validation["accepted"] else "rejected",
                **validation,
            }
            if not validation["accepted"]:
                quarantine = (
                    store.cache_root
                    / "phase2b/quarantine"
                    / f"{_safe_id(asset['release_asset_id'])}.body"
                )
                atomic_write_bytes_new(quarantine, response.body)
                attempt["preserved_response_path"] = str(
                    quarantine.relative_to(store.cache_root)
                ).replace("\\", "/")
                raise TransportError("schema_quarantine", json.dumps(validation["rejected"], sort_keys=True))
            atomic_write_bytes_new(cache_path, response.body)
            cache = asset["cache"]
            cache.update(
                {
                    "cache_file_bytes": cache_path.stat().st_size,
                    "raw_body_hash": raw_body_hash(response.body),
                    "canonical_json_hash": canonical_json_hash(payload),
                }
            )
            asset["source_event"] = {
                "provenance_format": "phase2b-live-v1",
                "acquired_at": store.clock(),
                "http_status": response.status_code,
                "latency_seconds": response.elapsed_seconds,
                "response_body_bytes": len(response.body),
                "raw_body_hash": cache["raw_body_hash"],
            }
            atomic_write_json(
                metadata_path,
                {
                    "release_asset_id": asset["release_asset_id"],
                    "identity": asset["identity"],
                    "source_event": asset["source_event"],
                    "cache": cache,
                    "schema_verification": asset["schema_verification"],
                },
            )
            store.transition(manifest, asset, "acquired", "validated_response_cached")
            replay = verify_release_asset(asset, store, manifest)
            attempt.update(
                {
                    "status": "verified",
                    "error_category": None,
                    "error_detail": None,
                    "canonical_json_hash": replay["canonical_json_hash"],
                    "cache_file_bytes": replay["cache_file_bytes"],
                    "row_counts": replay["row_counts"],
                }
            )
            asset["last_error"] = None
            store.transition(
                manifest, asset, "verified", "cache_replay_verified", replay["canonical_json_hash"]
            )
            if asset["identity"]["parameters"]["measure_type"] == "Advanced":
                team_id = asset["identity"]["parameters"]["team_id"]
                payloads = _team_payloads(team_id, store, manifest)
                if set(payloads) != set(MEASURES):
                    raise TransportError("team_reconciliation_failure", "Both measures unavailable")
                team_audit = audit_team_payloads(team_id, payloads["Base"], payloads["Advanced"])
                if not team_audit["clean_release_gate"]:
                    manifest["release_analysis_failure"] = {
                        "team_id": team_id,
                        "category": "team_reconciliation_or_target_failure",
                        "audit": team_audit,
                    }
                    store.save(manifest)
                    return _run_result(
                        manifest,
                        completed=False,
                        stop_category="team_reconciliation_or_target_failure",
                        team_audit=team_audit,
                    )
        except TransportError as exc:
            attempt.update(
                {
                    "status": "quarantined" if exc.category == "schema_quarantine" else "failed",
                    "error_category": exc.category,
                    "error_detail": exc.detail,
                }
            )
            asset["last_error"] = {"category": exc.category, "detail": exc.detail}
            status = "quarantined" if exc.category == "schema_quarantine" else "failed"
            store.transition(manifest, asset, status, exc.category, exc.detail)
            return _run_result(manifest, completed=False, stop_category=exc.category, stop_detail=exc.detail)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            attempt.update(
                {"status": "failed", "error_category": "unexpected_exception", "error_detail": detail}
            )
            asset["last_error"] = {"category": "unexpected_exception", "detail": detail}
            store.transition(manifest, asset, "failed", "unexpected_exception", detail)
            return _run_result(
                manifest, completed=False, stop_category="unexpected_exception", stop_detail=detail
            )
        if any(
            later["mode"] == "new_acquisition" and later["status"] == "planned"
            for later in manifest["pair_assets"][asset["ordinal"] :]
        ):
            sleep_fn(delay_seconds)
    return _run_result(manifest, completed=True, stop_category=None)


def _coverage_category(joined: Mapping[str, Any]) -> str:
    if joined["player_1_matched"] and joined["player_2_matched"]:
        return "complete"
    if joined["player_1_matched"] or joined["player_2_matched"]:
        return "one_missing"
    return "both_missing"


def _coverage_detail(joined: list[dict[str, Any]]) -> dict[str, Any]:
    categories = ("complete", "one_missing", "both_missing")
    counts = Counter(_coverage_category(row) for row in joined)
    minute_sums = Counter()
    poss_sums = Counter()
    valid_minutes = valid_possessions = 0
    crossed = Counter()
    for row in joined:
        category = _coverage_category(row)
        minute = _numeric(row.get("shared_min"))
        poss = _numeric(row.get("shared_poss"))
        if minute is not None and minute >= 0:
            minute_sums[category] += minute
            valid_minutes += 1
        if poss is not None and poss >= 0:
            poss_sums[category] += poss
            valid_possessions += 1
        eligible = poss is not None and poss > 0
        crossed[(category, "target_eligible" if eligible else "target_ineligible")] += 1
    total_minutes = sum(minute_sums.values())
    total_poss = sum(poss_sums.values())
    return {
        "total_pairs": len(joined),
        "categories": {
            category: {
                "count": counts[category],
                "percentage": counts[category] / len(joined) if joined else 0.0,
                "summed_base_minutes": minute_sums[category],
                "share_of_valid_summed_base_minutes": minute_sums[category] / total_minutes if total_minutes else 0.0,
                "summed_pair_possessions": poss_sums[category],
                "share_of_valid_summed_pair_possessions": poss_sums[category] / total_poss if total_poss else 0.0,
                "target_eligible": crossed[(category, "target_eligible")],
                "target_ineligible": crossed[(category, "target_ineligible")],
            }
            for category in categories
        },
        "valid_minute_rows": valid_minutes,
        "invalid_minute_rows": len(joined) - valid_minutes,
        "valid_possession_rows": valid_possessions,
        "invalid_possession_rows": len(joined) - valid_possessions,
        "exposure_note": "Summed pair exposures overlap and are not distinct NBA minutes or possessions.",
    }


def _threshold_coverage(joined: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for threshold in THRESHOLDS:
        eligible = [row for row in joined if (_numeric(row.get("shared_poss")) or -1) >= threshold]
        counts = Counter(_coverage_category(row) for row in eligible)
        rows.append(
            {
                "possessions_at_least": threshold,
                "rows": len(eligible),
                "complete": counts["complete"],
                "one_missing": counts["one_missing"],
                "both_missing": counts["both_missing"],
                "complete_percentage": counts["complete"] / len(eligible) if eligible else 0.0,
            }
        )
    return rows


def analyze_release(store: ReleaseStore) -> dict[str, Any]:
    """Replay and audit the completed release without any network surface."""
    prerequisite = verify_all_imports_and_dependencies(store)
    manifest = store.load()
    if any(asset["status"] not in {"verified", "reused_verified"} for asset in manifest["pair_assets"]):
        raise ValueError("All 60 pair release entries must verify before final analysis")
    source_store, source_manifest, source_analysis = _phase2a_context(store.cache_root)
    payloads_by_team: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    asset_ledger = []
    for asset in manifest["pair_assets"]:
        replay = verify_release_asset(asset, store, manifest)
        params = asset["identity"]["parameters"]
        payloads_by_team[params["team_id"]][params["measure_type"]] = replay["payload"]
        asset_ledger.append(
            {
                "ordinal": asset["ordinal"],
                "team_id": params["team_id"],
                "team_name": asset["team_name"],
                "measure": params["measure_type"],
                "mode": asset["mode"],
                "status": asset["status"],
                "release_asset_id": asset["release_asset_id"],
                "source_asset_id": (asset.get("source_reference") or {}).get("source_asset_id"),
                "cache_path": (
                    asset["source_reference"]["source_cache_path"]
                    if asset["mode"] == "imported_reuse"
                    else asset["cache"]["relative_path"]
                ),
                "latency_seconds": (asset.get("source_event") or {}).get("latency_seconds"),
                "response_body_bytes": (asset.get("source_event") or {}).get("response_body_bytes"),
                "cache_file_bytes": replay["cache_file_bytes"],
                "raw_body_hash": replay["raw_body_hash"],
                "canonical_json_hash": replay["canonical_json_hash"],
                "schema_fingerprints": replay["fingerprints"],
                "row_counts": replay["row_counts"],
                "provenance": replay["provenance"],
            }
        )
    per_team = {}
    all_base: list[dict[str, Any]] = []
    all_advanced: list[dict[str, Any]] = []
    for team_id in sorted(payloads_by_team, key=int):
        payloads = payloads_by_team[team_id]
        team_name = manifest["team_directory"][team_id]["team_name"]
        base = _pair_rows(payloads["Base"], TARGET_SEASON, team_id)
        advanced = _pair_rows(payloads["Advanced"], TARGET_SEASON, team_id)
        audit = audit_team_payloads(team_id, payloads["Base"], payloads["Advanced"])
        target = summarize_advanced_targets(advanced)
        ineligible = identify_zero_or_missing_possession_rows(advanced, base)
        per_team[team_id] = {
            "team_name": team_name,
            **audit,
            "target_audit": target,
            "target_ineligible_rows": ineligible,
            "base_identifier_detail": _pair_identifier_detail(base),
            "advanced_identifier_detail": _pair_identifier_detail(advanced),
            "base_population": _boundary(base, "Base"),
            "advanced_population": _boundary(advanced, "Advanced"),
            "same_canonical_key_set": audit["reconciliation"]["base_only_pairs"] == 0
            and audit["reconciliation"]["advanced_only_pairs"] == 0,
            "base_minutes": _quantiles(
                [value for row in base if (value := _numeric(row.get("MIN"))) is not None]
            ),
            "possessions": _quantiles(
                [value for row in advanced if (value := _numeric(row.get("POSS"))) is not None]
            ),
            "advanced_zero_min_positive_possessions": sum(
                _numeric(row.get("MIN")) == 0 and (_numeric(row.get("POSS")) or 0) > 0
                for row in advanced
            ),
            "extreme_net_rating_by_exposure": _extreme_rating_summary(advanced),
        }
        all_base.extend(base)
        all_advanced.extend(advanced)
    if not all(team["clean_release_gate"] for team in per_team.values()):
        raise ValueError("A team failed full release reconciliation")
    base_observations = {
        (row["team_id"], row["pair_key"]) for row in all_base if row.get("pair_key") is not None
    }
    advanced_observations = {
        (row["team_id"], row["pair_key"])
        for row in all_advanced
        if row.get("pair_key") is not None
    }
    player_teams: dict[str, set[str]] = defaultdict(set)
    pair_teams: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in all_base:
        if row.get("pair_key"):
            pair_teams[row["pair_key"]].add(row["team_id"])
            for player_id in row["pair_key"]:
                player_teams[player_id].add(row["team_id"])
    per100 = _player_rows(
        verify_phase2a_asset_cache(source_manifest["raw_assets"][10], store.cache_root, source_manifest)["payload"]
    )
    totals = _player_rows(
        verify_phase2a_asset_cache(source_manifest["raw_assets"][11], store.cache_root, source_manifest)["payload"]
    )
    prior_index = player_rows_by_id(attach_prior_context(per100, PRIOR_FEATURE_SEASON))
    advanced_lookup = {(row["team_id"], row.get("pair_key")): row for row in all_advanced}
    coverage_by_team = {}
    all_join_input = []
    for team_id in sorted(payloads_by_team, key=int):
        rows = []
        for row in (item for item in all_base if item["team_id"] == team_id):
            item = dict(row)
            item["POSS"] = advanced_lookup.get((team_id, row.get("pair_key")), {}).get("POSS")
            rows.append(item)
            all_join_input.append(item)
        joined = join_pairs_to_prior_players(rows, prior_index, TARGET_SEASON, PRIOR_FEATURE_SEASON)
        coverage_by_team[team_id] = {
            "players": summarize_player_level_coverage(rows, prior_index),
            "pairs": summarize_pair_level_coverage(joined),
            "exposure": summarize_exposure_weighted_coverage(joined),
            "detail": _coverage_detail(joined),
            "thresholds": _threshold_coverage(joined),
        }
    all_joined = join_pairs_to_prior_players(
        all_join_input, prior_index, TARGET_SEASON, PRIOR_FEATURE_SEASON
    )
    combined_coverage = {
        "players": summarize_player_level_coverage(all_join_input, prior_index),
        "pairs": summarize_pair_level_coverage(all_joined),
        "exposure": summarize_exposure_weighted_coverage(all_joined),
        "detail": _coverage_detail(all_joined),
        "thresholds": _threshold_coverage(all_joined),
    }
    missing_ids = set(combined_coverage["players"]["missing_player_ids"])
    missing_ledger = []
    for player_id in sorted(missing_ids, key=int):
        affected = [row for row in all_join_input if player_id in (row.get("pair_key") or ())]
        names = set()
        for row in affected:
            raw_ids = [token for token in str(row.get("GROUP_ID", "")).strip("-").split("-") if token]
            raw_names = [part.strip() for part in str(row.get("GROUP_NAME", "")).split(" - ")]
            names.update(name for pid, name in zip(raw_ids, raw_names) if pid == player_id)
        missing_ledger.append(
            {
                "player_id": player_id,
                "observed_names": sorted(names),
                "teams": sorted({row["team_id"] for row in affected}, key=int),
                "affected_pair_observations": len(affected),
                "summed_base_minutes": sum(_numeric(row.get("MIN")) or 0 for row in affected),
                "summed_pair_possessions": sum(_numeric(row.get("POSS")) or 0 for row in affected),
                "reason": "no_2022-23_source_record",
            }
        )
    canary_ids = sorted(CANARY_TEAM_IDS, key=int)
    canary_matches = sum(per_team[team_id]["reconciliation"]["matched_pairs"] for team_id in canary_ids)
    canary_inputs = [row for row in all_join_input if row["team_id"] in CANARY_TEAM_IDS]
    canary_joined = join_pairs_to_prior_players(
        canary_inputs, prior_index, TARGET_SEASON, PRIOR_FEATURE_SEASON
    )
    canary_coverage = {
        "players": summarize_player_level_coverage(canary_inputs, prior_index),
        "pairs": summarize_pair_level_coverage(canary_joined),
        "detail": _coverage_detail(canary_joined),
    }
    dependencies = []
    for dependency in manifest["player_dependencies"]:
        dependencies.append(
            {
                **deepcopy(dependency),
                "latency_seconds": None,
                "phase2b_network_request": False,
            }
        )
    total_ineligible = sum(len(team["target_ineligible_rows"]) for team in per_team.values())
    boundary_teams = [
        team_id
        for team_id, team in per_team.items()
        if team["base_population"]["classification"] == "boundary_signal_present"
        or team["advanced_population"]["classification"] == "boundary_signal_present"
    ]
    summary = {
        "analysis_version": ANALYSIS_VERSION,
        "target_season": TARGET_SEASON,
        "prior_feature_season": PRIOR_FEATURE_SEASON,
        "prerequisite_replay": prerequisite,
        "source_phase2a_analysis_hash": source_analysis["deterministic_analysis_sha256"],
        "request_set": {
            "pair_entries": len(asset_ledger),
            "teams": len(per_team),
            "imported_reuses": sum(asset["mode"] == "imported_reuse" for asset in manifest["pair_assets"]),
            "newly_acquired": sum(asset["mode"] == "new_acquisition" for asset in manifest["pair_assets"]),
            "new_live_attempts": sum(len(asset["attempt_history"]) for asset in manifest["pair_assets"]),
            "player_dependencies_reused": 2,
            "player_live_requests": 0,
        },
        "asset_ledger": asset_ledger,
        "dependency_ledger": dependencies,
        "per_team": per_team,
        "combined": {
            "base_rows": len(all_base),
            "advanced_rows": len(all_advanced),
            "matched_observation_keys": len(base_observations & advanced_observations),
            "base_only_observation_keys": len(base_observations - advanced_observations),
            "advanced_only_observation_keys": len(advanced_observations - base_observations),
            "unique_players": len(player_teams),
            "globally_unique_unordered_pairs": len(pair_teams),
            "players_observed_for_multiple_teams": {
                player: sorted(teams, key=int) for player, teams in player_teams.items() if len(teams) > 1
            },
            "pairs_observed_for_multiple_teams": [
                {"pair_ids": pair, "teams": sorted(teams, key=int)}
                for pair, teams in sorted(pair_teams.items())
                if len(teams) > 1
            ],
            "target_ineligible_rows": total_ineligible,
            "base_minutes": _quantiles(
                [value for row in all_base if (value := _numeric(row.get("MIN"))) is not None]
            ),
            "possessions": _quantiles(
                [value for row in all_advanced if (value := _numeric(row.get("POSS"))) is not None]
            ),
            "boundary_signal_team_ids": boundary_teams,
            "population_classification": (
                "boundary_signal_present" if boundary_teams else "no_boundary_signal_observed"
            ),
            "population_exhaustiveness": "not_proven_exhaustive",
        },
        "prior_history": {
            "per_team": coverage_by_team,
            "combined": combined_coverage,
            "unmatched_player_ledger": missing_ledger,
            "player_source_reconciliation": {
                "per100_rows": len(per100),
                "totals_rows": len(totals),
                "per100_unique_ids": len({str(row["PLAYER_ID"]) for row in per100}),
                "totals_unique_ids": len({str(row["PLAYER_ID"]) for row in totals}),
                "exact_id_set_match": {str(row["PLAYER_ID"]) for row in per100}
                == {str(row["PLAYER_ID"]) for row in totals},
            },
            "policy": "descriptive_only_final_missing_history_policy_deferred",
        },
        "canary_reproduction": {
            "matched_rows": canary_matches,
            "expected_matched_rows": 880,
            "coverage": canary_coverage,
            "phase2a_expected_coverage": source_analysis["prior_coverage"]["combined"],
            "exact": canary_matches == 880
            and canary_coverage["pairs"]["both_players_matched"] == 526
            and canary_coverage["pairs"]["neither_player_matched"] == 47
            and (
                canary_coverage["pairs"]["only_player_1_matched"]
                + canary_coverage["pairs"]["only_player_2_matched"]
            )
            == 307,
        },
        "release_gates": {
            "request_set_complete": len(asset_ledger) == 60,
            "source_integrity": True,
            "returned_row_integrity": len(base_observations ^ advanced_observations) == 0
            and all(team["clean_release_gate"] for team in per_team.values()),
            "population_exhaustiveness": "unproven_with_boundary_signals"
            if boundary_teams
            else "unproven_no_boundary_signal_observed",
            "prior_history_coverage": "measured_and_preserved_policy_unresolved",
            "next_historical_phase_readiness": "ready_for_separate_authorization",
        },
    }
    summary["primary_classification"] = (
        "2023-24 raw release supported with population caveats; next historical phase ready for separate authorization"
        if all(
            (
                summary["release_gates"]["request_set_complete"],
                summary["release_gates"]["source_integrity"],
                summary["release_gates"]["returned_row_integrity"],
                summary["canary_reproduction"]["exact"],
            )
        )
        else "2023-24 raw request set complete; release audit unresolved"
    )
    deterministic = deepcopy(summary)
    for asset in deterministic["asset_ledger"]:
        asset.pop("latency_seconds", None)
    summary["deterministic_analysis_sha256"] = canonical_json_hash(deterministic)
    return summary
