"""Persisted Phase 1C raw-season manifest and cache reconciliation.

This module performs filesystem work only when its functions are called. It never
imports or invokes a network transport.
"""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from pair_fit_v2.lineup_audit import extract_result_set, result_set_rows
from pair_fit_v2.multi_team_audit import schema_fingerprint
from pair_fit_v2.phase1b_contract import (
    CONTRACT_VERSION,
    MANIFEST_KIND,
    REQUIRED_PAIR_MEASURES,
    REQUIRED_RESULT_SETS,
    build_season_manifest,
    raw_asset_identity,
    schema_drift_report,
    stable_contract_id,
)


TARGET_SEASON = "2024-25"
SEASON_TYPE = "Regular Season"
LEAGUE_ID = "00"
ENDPOINT = "TeamDashLineups"
GROUP_QUANTITY = "2"
OPERATIONAL_MANIFEST_VERSION = "phase1c.raw-season.v1"
STANDINGS_RECORDED_CANONICAL_HASH = "b44b1f751bba84da"
PILOT_TEAM_IDS = frozenset(
    {"1610612738", "1610612744", "1610612751", "1610612764"}
)

# Every TeamDashLineups request parameter not already represented by the core
# raw_asset_identity fields. These names match the upstream query parameters.
TEAM_DASH_LINEUPS_EXTRA_PARAMETERS: dict[str, Any] = {
    "DateFrom": "",
    "DateTo": "",
    "GameID": "",
    "GameSegment": "",
    "LastNGames": "0",
    "Location": "",
    "Month": "0",
    "OpponentTeamID": "0",
    "Outcome": "",
    "PORound": "",
    "PaceAdjust": "N",
    "PerMode": "Totals",
    "Period": "0",
    "PlusMinus": "N",
    "Rank": "N",
    "SeasonSegment": "",
    "ShotClockRange": "",
    "VsConference": "",
    "VsDivision": "",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(payload: Any) -> bytes:
    """Return the historical canonical representation used by recorded hashes."""
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def canonical_json_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def raw_body_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read valid JSON from {path}: {exc}") from exc


def atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON through a same-directory temporary file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_bytes_new(path: Path, body: bytes) -> None:
    """Atomically create an immutable cache file and refuse an existing target."""
    if path.exists():
        raise FileExistsError(f"Cache destination already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise FileExistsError(f"Cache destination already exists: {path}")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_payload_structure(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate required result sets, row widths, and return schema/data volume."""
    result_sets = payload.get("resultSets")
    if not isinstance(result_sets, list):
        raise ValueError("Payload is missing a resultSets list")
    names = [item.get("name") for item in result_sets if isinstance(item, Mapping)]
    if len(result_sets) != len(names):
        raise ValueError("Payload contains a malformed result set")
    duplicates = sorted(name for name in set(names) if names.count(name) > 1)
    if duplicates:
        raise ValueError(f"Duplicate result sets: {duplicates}")
    missing = sorted(set(REQUIRED_RESULT_SETS) - set(names))
    unexpected = sorted(set(names) - set(REQUIRED_RESULT_SETS))
    if missing or unexpected:
        raise ValueError(
            f"Result-set contract mismatch; missing={missing}, unexpected={unexpected}"
        )

    fingerprints = []
    row_counts: dict[str, int] = {}
    for name in REQUIRED_RESULT_SETS:
        result_set = extract_result_set(dict(payload), name)
        rows = result_set_rows(result_set)
        fingerprints.append(schema_fingerprint(result_set))
        row_counts[name] = len(rows)
    return {"fingerprints": fingerprints, "row_counts": row_counts}


def validate_standings_snapshot(cache_root: Path) -> list[dict[str, str]]:
    """Return the authoritative 30-team snapshot after hash/schema validation."""
    path = cache_root / "live_responses" / "league_standings_v3_2024-25_regular.json"
    if not path.is_file():
        raise FileNotFoundError(f"Required standings cache is missing: {path}")
    payload = read_json(path)
    digest = canonical_json_hash(payload)
    if not digest.startswith(STANDINGS_RECORDED_CANONICAL_HASH):
        raise ValueError(
            "Standings canonical hash mismatch: "
            f"recorded={STANDINGS_RECORDED_CANONICAL_HASH}, actual={digest[:16]}"
        )
    parameters = payload.get("parameters", {})
    expected_parameters = {
        "LeagueID": LEAGUE_ID,
        "SeasonYear": TARGET_SEASON,
        "SeasonType": SEASON_TYPE,
    }
    if parameters != expected_parameters:
        raise ValueError(
            f"Standings request context mismatch: expected={expected_parameters}, "
            f"actual={parameters}"
        )
    result_sets = payload.get("resultSets")
    if not isinstance(result_sets, list) or len(result_sets) != 1:
        raise ValueError("Standings cache must contain exactly one result set")
    result_set = result_sets[0]
    if result_set.get("name") != "Standings":
        raise ValueError("Standings cache result-set name mismatch")
    rows = result_set_rows(result_set)
    teams = []
    for row in rows:
        team_id = str(row.get("TeamID"))
        if not team_id.isdecimal() or int(team_id) <= 0:
            raise ValueError(f"Invalid standings TeamID: {team_id!r}")
        teams.append(
            {
                "team_id": str(int(team_id)),
                "team_name": f"{row.get('TeamCity', '')} {row.get('TeamName', '')}".strip(),
                "team_slug": str(row.get("TeamSlug", "")),
            }
        )
    if len(teams) != 30 or len({team["team_id"] for team in teams}) != 30:
        raise ValueError("Standings cache does not contain 30 distinct team IDs")
    return sorted(teams, key=lambda team: int(team["team_id"]))


def _legacy_cache_stem(team_id: str, measure_type: str) -> str:
    return f"team_dash_lineups_{team_id}_{TARGET_SEASON}_{measure_type.lower()}"


def _metadata_identity(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return raw_asset_identity(
        endpoint=metadata.get("endpoint"),
        season=metadata.get("season"),
        team_id=metadata.get("team_id"),
        measure_type=metadata.get("measure_type"),
        season_type=metadata.get("season_type"),
        league_id=LEAGUE_ID,
        group_quantity=metadata.get("group_quantity"),
        extra_parameters=TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
    )


def derive_approved_schema_contract(cache_root: Path) -> dict[str, dict[str, Any]]:
    """Validate all eight recorded pilot hashes and derive the approved schemas."""
    approved: dict[str, dict[str, Any]] = {}
    seen = 0
    for team_id in sorted(PILOT_TEAM_IDS, key=int):
        for measure in REQUIRED_PAIR_MEASURES:
            stem = _legacy_cache_stem(team_id, measure)
            payload_path = cache_root / "live_responses" / f"{stem}.json"
            metadata_path = cache_root / "live_responses" / f"{stem}_metadata.json"
            if not payload_path.is_file() or not metadata_path.is_file():
                raise FileNotFoundError(f"Required pilot cache or metadata is missing: {stem}")
            payload = read_json(payload_path)
            metadata = read_json(metadata_path)
            digest = canonical_json_hash(payload)
            recorded = str(metadata.get("content_hash", ""))
            if not recorded or not digest.startswith(recorded):
                raise ValueError(
                    f"Pilot canonical hash mismatch for {stem}: "
                    f"recorded={recorded}, actual={digest[:16]}"
                )
            expected_identity = raw_asset_identity(
                endpoint=ENDPOINT,
                season=TARGET_SEASON,
                team_id=team_id,
                measure_type=measure,
                season_type=SEASON_TYPE,
                league_id=LEAGUE_ID,
                group_quantity=GROUP_QUANTITY,
                extra_parameters=TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
            )
            if _metadata_identity(metadata) != expected_identity:
                raise ValueError(f"Pilot request identity mismatch for {stem}")
            validation = validate_payload_structure(payload)
            contract_for_measure = {
                item["name"]: item for item in validation["fingerprints"]
            }
            if measure not in approved:
                approved[measure] = contract_for_measure
            elif approved[measure] != contract_for_measure:
                raise ValueError(f"Pilot schema mismatch for {measure}: {stem}")
            seen += 1
    if seen != 8:
        raise AssertionError(f"Expected eight pilot assets, validated {seen}")
    return approved


def phase1c_manifest_path(cache_root: Path) -> Path:
    return (
        cache_root
        / "phase1c"
        / "manifests"
        / "2024-25_regular-season_teamdashlineups_group-2.json"
    )


def _asset_cache_relative_path(asset_id: str) -> str:
    safe_id = asset_id.replace(":", "_")
    return f"phase1c/raw/{safe_id}.json"


def build_operational_manifest(
    teams: list[Mapping[str, str]],
    approved_schema_contract: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Build the deterministic 60-asset operational manifest in planned state."""
    manifest = build_season_manifest(
        season=TARGET_SEASON,
        team_ids=[team["team_id"] for team in teams],
        measures=REQUIRED_PAIR_MEASURES,
        endpoint=ENDPOINT,
        season_type=SEASON_TYPE,
        league_id=LEAGUE_ID,
        group_quantity=GROUP_QUANTITY,
        extra_parameters=TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
    )
    manifest.update(
        {
            "operational_manifest_version": OPERATIONAL_MANIFEST_VERSION,
            "team_directory": {
                str(team["team_id"]): {
                    "team_name": str(team["team_name"]),
                    "team_slug": str(team.get("team_slug", "")),
                }
                for team in teams
            },
            "approved_schema_contract": deepcopy(approved_schema_contract),
            "approved_schema_contract_id": stable_contract_id(
                "schema-contract", approved_schema_contract
            ),
            "authorization": {
                "maximum_new_live_requests": 52,
                "authorized_team_count": 26,
                "authorized_measures": list(REQUIRED_PAIR_MEASURES),
            },
            "transition_sequence": 0,
        }
    )
    for asset in manifest["raw_assets"]:
        relative_path = _asset_cache_relative_path(asset["asset_id"])
        asset["cache"]["relative_path"] = relative_path
        asset["cache"]["metadata_relative_path"] = relative_path.replace(
            ".json", ".metadata.json"
        )
        asset["attempt_history"] = []
        asset["transition_history"] = []
        asset["legacy_reconciliation"] = None
    return manifest


def validate_manifest_envelope(
    manifest: Mapping[str, Any], expected_manifest: Mapping[str, Any]
) -> None:
    """Reject an incomplete, tampered, reordered, or incompatible manifest."""
    if manifest.get("manifest_kind") != MANIFEST_KIND:
        raise ValueError("Manifest kind mismatch")
    if manifest.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("Manifest contract version mismatch")
    if manifest.get("operational_manifest_version") != OPERATIONAL_MANIFEST_VERSION:
        raise ValueError("Operational manifest version mismatch")
    identity = manifest.get("logical_identity")
    if identity != expected_manifest.get("logical_identity"):
        raise ValueError("Manifest logical identity is incompatible")
    recomputed = stable_contract_id("season-manifest", identity)
    if manifest.get("manifest_id") != recomputed:
        raise ValueError(
            f"Manifest ID mismatch: stored={manifest.get('manifest_id')}, "
            f"recomputed={recomputed}"
        )
    if manifest.get("approved_schema_contract") != expected_manifest.get(
        "approved_schema_contract"
    ):
        raise ValueError("Approved schema contract mismatch")
    schema_contract = manifest.get("approved_schema_contract")
    schema_id = stable_contract_id("schema-contract", schema_contract)
    if manifest.get("approved_schema_contract_id") != schema_id:
        raise ValueError("Approved schema contract ID mismatch")
    assets = manifest.get("raw_assets")
    expected_assets = expected_manifest.get("raw_assets")
    if not isinstance(assets, list) or len(assets) != len(expected_assets):
        raise ValueError("Manifest asset count mismatch")
    seen_ids = set()
    for index, (asset, expected_asset) in enumerate(zip(assets, expected_assets)):
        if asset.get("identity") != expected_asset.get("identity"):
            raise ValueError(f"Asset identity mismatch at index {index}")
        recomputed_asset_id = stable_contract_id("raw-asset", asset["identity"])
        if asset.get("asset_id") != recomputed_asset_id:
            raise ValueError(f"Asset ID mismatch at index {index}")
        if asset["asset_id"] in seen_ids:
            raise ValueError(f"Duplicate asset ID at index {index}")
        seen_ids.add(asset["asset_id"])


class ManifestStore:
    """Atomic persisted-manifest store with compatibility checks on every load/save."""

    def __init__(
        self,
        cache_root: Path,
        expected_manifest: Mapping[str, Any],
        *,
        clock: Callable[[], str] = utc_now,
    ):
        self.cache_root = Path(cache_root)
        self.path = phase1c_manifest_path(self.cache_root)
        self.expected_manifest = deepcopy(expected_manifest)
        self.clock = clock

    def create_or_load(self) -> dict[str, Any]:
        if self.path.exists():
            return self.load()
        manifest = deepcopy(self.expected_manifest)
        manifest["created_at"] = self.clock()
        manifest["updated_at"] = manifest["created_at"]
        self.save(manifest)
        return manifest

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            raise FileNotFoundError(f"Persisted manifest is missing: {self.path}")
        manifest = read_json(self.path)
        validate_manifest_envelope(manifest, self.expected_manifest)
        return manifest

    def save(self, manifest: dict[str, Any]) -> None:
        validate_manifest_envelope(manifest, self.expected_manifest)
        if self.path.exists():
            existing = read_json(self.path)
            validate_manifest_envelope(existing, self.expected_manifest)
            if existing.get("manifest_id") != manifest.get("manifest_id"):
                raise ValueError("Refusing to overwrite an incompatible manifest")
        manifest["updated_at"] = self.clock()
        atomic_write_json(self.path, manifest)

    def transition(
        self,
        manifest: dict[str, Any],
        asset: dict[str, Any],
        status: str,
        *,
        category: str,
        detail: str | None = None,
    ) -> None:
        manifest["transition_sequence"] = int(manifest.get("transition_sequence", 0)) + 1
        asset["status"] = status
        asset.setdefault("transition_history", []).append(
            {
                "sequence": manifest["transition_sequence"],
                "at": self.clock(),
                "status": status,
                "category": category,
                "detail": detail,
            }
        )
        self.save(manifest)


def extend_live_request_authorization(
    store: ManifestStore,
    *,
    asset_id: str,
    authorization_note: str,
) -> dict[str, Any]:
    """Persist one additional live-attempt authorization for one planned asset.

    This intentionally narrow operation is auditable and idempotence-resistant:
    the named asset must be the manifest's sole planned asset, and an extension
    for that asset cannot be recorded twice.
    """
    manifest = store.load()
    planned = [asset for asset in manifest["raw_assets"] if asset["status"] == "planned"]
    if len(planned) != 1 or planned[0]["asset_id"] != asset_id:
        raise ValueError(
            "Additional authorization requires the named asset to be the sole "
            "planned manifest asset"
        )
    authorization = manifest.setdefault("authorization", {})
    extensions = authorization.setdefault("extensions", [])
    if any(extension.get("asset_id") == asset_id for extension in extensions):
        raise ValueError(f"Authorization extension already recorded for {asset_id}")
    extensions.append(
        {
            "asset_id": asset_id,
            "additional_live_attempts": 1,
            "authorized_at": store.clock(),
            "note": authorization_note,
        }
    )
    authorization["maximum_new_live_requests"] = (
        int(authorization["maximum_new_live_requests"]) + 1
    )
    store.save(manifest)
    return manifest


def _verify_overall_team(payload: Mapping[str, Any], expected_team_id: str) -> None:
    overall_rows = result_set_rows(extract_result_set(dict(payload), "Overall"))
    if len(overall_rows) != 1:
        raise ValueError(f"Overall must contain one row, found {len(overall_rows)}")
    returned_team_id = str(overall_rows[0].get("TEAM_ID"))
    if returned_team_id != expected_team_id:
        raise ValueError(
            f"Returned team mismatch: expected={expected_team_id}, actual={returned_team_id}"
        )


def verify_asset_cache(
    asset: Mapping[str, Any],
    cache_root: Path,
    approved_schema_contract: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Replay and verify one cache asset without changing it."""
    identity = asset.get("identity", {})
    expected_asset_id = stable_contract_id("raw-asset", identity)
    if asset.get("asset_id") != expected_asset_id:
        raise ValueError("Stored asset ID does not match embedded identity")
    parameters = identity.get("parameters", {})
    cache = asset.get("cache", {})
    relative_path = cache.get("relative_path")
    if not relative_path:
        raise ValueError("Asset has no cache path")
    payload_path = cache_root / str(relative_path)
    if not payload_path.is_file():
        raise FileNotFoundError(f"Asset cache is missing: {payload_path}")
    body = payload_path.read_bytes()
    actual_bytes = len(body)
    if actual_bytes != cache.get("cache_file_bytes"):
        raise ValueError("Cache-file byte size mismatch")
    payload = read_json(payload_path)
    digest = canonical_json_hash(payload)
    if digest != cache.get("canonical_json_hash"):
        raise ValueError("Canonical JSON hash mismatch")
    validation = validate_payload_structure(payload)
    _verify_overall_team(payload, str(parameters.get("team_id")))
    measure = str(parameters.get("measure_type"))
    expected_contract = approved_schema_contract.get(measure, {})
    actual_contract = {
        fingerprint["name"]: fingerprint
        for fingerprint in validation["fingerprints"]
    }
    schema_results = {}
    for result_set_name in REQUIRED_RESULT_SETS:
        if result_set_name not in expected_contract:
            raise ValueError(f"Approved schema missing {measure}/{result_set_name}")
        drift = schema_drift_report(
            expected_contract[result_set_name], actual_contract[result_set_name]
        )
        schema_results[result_set_name] = drift
        if not drift["accepted"]:
            raise ValueError(
                f"Schema mismatch for {measure}/{result_set_name}: "
                f"{drift['classification']}"
            )
    metadata_relative_path = cache.get("metadata_relative_path")
    if not metadata_relative_path:
        raise ValueError("Asset has no metadata path")
    metadata_path = cache_root / str(metadata_relative_path)
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Asset metadata is missing: {metadata_path}")
    metadata = read_json(metadata_path)
    source_event = asset.get("source_event", {})
    provenance_format = source_event.get("provenance_format")
    if provenance_format == "phase1c-live-v1":
        if metadata.get("asset_id") != asset.get("asset_id"):
            raise ValueError("Metadata asset ID mismatch")
        if metadata.get("identity") != identity:
            raise ValueError("Metadata request identity mismatch")
        if metadata.get("source_event") != source_event:
            raise ValueError("Metadata source-event mismatch")
        if source_event.get("http_status") != 200:
            raise ValueError("Verified live asset lacks HTTP 200 provenance")
        if source_event.get("response_body_bytes") != actual_bytes:
            raise ValueError("Response-body byte provenance mismatch")
        if source_event.get("raw_body_hash") != raw_body_hash(body):
            raise ValueError("Raw-body hash mismatch")
        metadata_cache = metadata.get("cache", {})
        for field in (
            "relative_path",
            "metadata_relative_path",
            "cache_file_bytes",
            "canonical_json_hash",
            "serialization_version",
        ):
            if metadata_cache.get(field) != cache.get(field):
                raise ValueError(f"Metadata cache provenance mismatch: {field}")
    elif provenance_format == "legacy-reconciled-v1":
        if _metadata_identity(metadata) != identity:
            raise ValueError("Legacy metadata request identity mismatch")
        recorded_hash = str(metadata.get("content_hash", ""))
        if not recorded_hash or not digest.startswith(recorded_hash):
            raise ValueError("Legacy recorded canonical hash mismatch")
        if cache.get("historical_recorded_hash") != recorded_hash:
            raise ValueError("Legacy manifest/metadata hash mismatch")
        if source_event.get("recorded_success") is not True:
            raise ValueError("Legacy source event was not recorded as successful")
    else:
        raise ValueError(f"Unsupported provenance format: {provenance_format!r}")
    return {
        "asset_id": asset["asset_id"],
        "canonical_json_hash": digest,
        "cache_file_bytes": actual_bytes,
        "row_counts": validation["row_counts"],
        "fingerprints": validation["fingerprints"],
        "schema_results": schema_results,
        "payload": payload,
    }


def reconcile_pilot_assets(
    manifest: dict[str, Any], store: ManifestStore
) -> dict[str, Any]:
    """Reconcile exactly eight legacy pilot payloads without inventing provenance."""
    approved = manifest["approved_schema_contract"]
    reconciled = 0
    for asset in manifest["raw_assets"]:
        parameters = asset["identity"]["parameters"]
        team_id = parameters["team_id"]
        measure = parameters["measure_type"]
        if team_id not in PILOT_TEAM_IDS:
            continue
        stem = _legacy_cache_stem(team_id, measure)
        payload_relative = f"live_responses/{stem}.json"
        metadata_relative = f"live_responses/{stem}_metadata.json"
        if asset.get("status") == "verified":
            verify_asset_cache(asset, store.cache_root, approved)
            reconciled += 1
            continue
        if asset.get("status") != "planned":
            raise ValueError(
                f"Pilot asset is not safely reconcilable from status {asset.get('status')}"
            )
        payload_path = store.cache_root / payload_relative
        metadata_path = store.cache_root / metadata_relative
        payload = read_json(payload_path)
        metadata = read_json(metadata_path)
        if _metadata_identity(metadata) != asset["identity"]:
            raise ValueError(f"Legacy metadata identity mismatch for {stem}")
        digest = canonical_json_hash(payload)
        recorded_hash = str(metadata.get("content_hash", ""))
        if not digest.startswith(recorded_hash):
            raise ValueError(f"Legacy canonical hash mismatch for {stem}")
        validation = validate_payload_structure(payload)
        _verify_overall_team(payload, team_id)
        actual_contract = {
            fingerprint["name"]: fingerprint
            for fingerprint in validation["fingerprints"]
        }
        for result_set_name in REQUIRED_RESULT_SETS:
            drift = schema_drift_report(
                approved[measure][result_set_name], actual_contract[result_set_name]
            )
            if not drift["accepted"]:
                raise ValueError(
                    f"Legacy schema mismatch for {stem}/{result_set_name}: "
                    f"{drift['classification']}"
                )

        asset["source_event"] = {
            "provenance_format": "legacy-reconciled-v1",
            "recorded_success": True,
            "acquired_at": None,
            "http_status": None,
            "response_body_bytes": None,
            "raw_body_hash": None,
            "unknown_fields": [
                "acquired_at",
                "http_status",
                "response_body_bytes",
                "raw_body_hash",
            ],
        }
        asset["cache"].update(
            {
                "relative_path": payload_relative,
                "metadata_relative_path": metadata_relative,
                "cache_file_bytes": payload_path.stat().st_size,
                "canonical_json_hash": digest,
                "canonical_json_hash_algorithm": "sha256-json-sort-keys.v1",
                "serialization_version": "historical-serialization-unknown",
                "historical_recorded_hash": recorded_hash,
            }
        )
        asset["schema_verification"] = {
            "status": "accepted",
            "fingerprints": validation["fingerprints"],
            "drift_classification": "identical",
            "row_counts": validation["row_counts"],
        }
        asset["legacy_reconciliation"] = {
            "metadata_format": "phase0-phase1a-sidecar-v1",
            "request_parameters_not_recorded_by_legacy_metadata": sorted(
                TEAM_DASH_LINEUPS_EXTRA_PARAMETERS
            ),
            "request_parameter_reconciliation_basis": (
                "versioned historical direct-fetch parameter contract"
            ),
            "metadata_payload_size_bytes": metadata.get("payload_size_bytes"),
            "metadata_payload_size_semantics": "historical_mixed_or_unknown",
            "metadata_fetch_time_seconds": metadata.get("fetch_time_seconds"),
            "reconciled_without_fabricated_provenance": True,
        }
        asset["last_error"] = None
        store.transition(
            manifest,
            asset,
            "verified",
            category="legacy_cache_reconciled",
            detail=f"recorded_hash={recorded_hash}",
        )
        verify_asset_cache(asset, store.cache_root, approved)
        reconciled += 1
    if reconciled != 8:
        raise ValueError(f"Expected exactly eight reconciled pilot assets, found {reconciled}")
    return {
        "verified_existing": reconciled,
        "planned_missing": sum(
            asset.get("status") == "planned" for asset in manifest["raw_assets"]
        ),
        "unique_asset_ids": len(
            {asset["asset_id"] for asset in manifest["raw_assets"]}
        ),
    }
