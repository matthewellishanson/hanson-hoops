"""Phase 2A bounded historical raw-acquisition canary.

All planning, validation, replay, and analysis functions are cache-only.  The
only network-capable entry point is :func:`run_acquisition`, which additionally
requires ``live_acquisition=True`` and a non-dry run.
"""

from __future__ import annotations

import json
import math
import time
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
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
from pair_fit_v2.multi_team_audit import (
    possession_distribution,
    schema_fingerprint,
    validate_combined_observation_keys,
)
from pair_fit_v2.phase1b_contract import (
    normalize_season,
    schema_drift_report,
    stable_contract_id,
)
from pair_fit_v2.phase1c_manifest import (
    TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
    atomic_write_bytes_new,
    atomic_write_json,
    canonical_json_hash,
    derive_approved_schema_contract,
    raw_body_hash,
    read_json,
    validate_payload_structure,
)
from pair_fit_v2.player_audit import (
    attach_prior_context,
    audit_stable_ids,
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
PAIR_ENDPOINT = "TeamDashLineups"
PLAYER_ENDPOINT = "LeagueDashPlayerStats"
MEASURES = ("Base", "Advanced")
PLAYER_PER_MODES = ("Per100Possessions", "Totals")
MAX_LIVE_ATTEMPTS = 12
TIMEOUT_SECONDS = 30
MANIFEST_VERSION = "phase2a.historical-canary.v1"
SERIALIZATION_VERSION = "raw-response-body.v1"
CANONICALIZATION = "sha256-json-sort-keys.v1"

TEAMS = (
    ("1610612744", "Golden State Warriors", "original Phase 0 canary continuity"),
    ("1610612738", "Boston Celtics", "comparatively stable veteran-team case"),
    ("1610612764", "Washington Wizards", "Phase 1A prior-history stress case"),
    ("1610612751", "Brooklyn Nets", "roster-turnover/trade-context case"),
    ("1610612766", "Charlotte Hornets", "prior endpoint-boundary risk context"),
)

PLAYER_EXTRA_PARAMETERS: dict[str, Any] = {
    "College": "", "Conference": "", "Country": "", "DateFrom": "",
    "DateTo": "", "Division": "", "DraftPick": "", "DraftYear": "",
    "GameScope": "", "GameSegment": "", "Height": "", "LastNGames": "0",
    "Location": "", "Month": "0", "OpponentTeamID": "0", "Outcome": "",
    "PORound": "", "PaceAdjust": "N", "Period": "0", "PlayerExperience": "",
    "PlayerPosition": "", "PlusMinus": "N", "Rank": "N", "SeasonSegment": "",
    "ShotClockRange": "", "StarterBench": "", "TeamID": "", "TwoWay": "",
    "VsConference": "", "VsDivision": "", "Weight": "",
}

PAIR_URL = "https://stats.nba.com/stats/teamdashlineups"
PLAYER_URL = "https://stats.nba.com/stats/leaguedashplayerstats"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _season_start(season: str) -> int:
    return int(normalize_season(season).split("-")[0])


def validate_season_shift(target_season: str, prior_feature_season: str) -> None:
    """Reject same-season, future-season, or non-adjacent feature sources."""
    target = _season_start(target_season)
    prior = _season_start(prior_feature_season)
    if prior >= target:
        raise ValueError("prior_feature_season must be earlier than target_season")
    if target - prior != 1:
        raise ValueError("Phase 2A requires target 2023-24 to map to prior 2022-23")
    if (normalize_season(target_season), normalize_season(prior_feature_season)) != (
        TARGET_SEASON, PRIOR_FEATURE_SEASON
    ):
        raise ValueError("Phase 2A authorizes only target 2023-24 and prior 2022-23")


def _identity(endpoint: str, parameters: Mapping[str, Any]) -> dict[str, Any]:
    identity = {
        "endpoint": endpoint,
        "target_season": TARGET_SEASON,
        "prior_feature_season": PRIOR_FEATURE_SEASON,
        "parameters": dict(parameters),
    }
    validate_identity(identity)
    return identity


def pair_identity(team_id: str, measure: str) -> dict[str, Any]:
    return _identity(PAIR_ENDPOINT, {
        **TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
        "league_id": LEAGUE_ID,
        "season": TARGET_SEASON,
        "season_type": "regular-season",
        "team_id": str(team_id),
        "group_quantity": GROUP_QUANTITY,
        "measure_type": measure,
    })


def player_identity(per_mode: str) -> dict[str, Any]:
    return _identity(PLAYER_ENDPOINT, {
        **PLAYER_EXTRA_PARAMETERS,
        "league_id": LEAGUE_ID,
        "season": PRIOR_FEATURE_SEASON,
        "season_type": "regular-season",
        "measure_type": "Base",
        "per_mode": per_mode,
    })


def validate_identity(identity: Mapping[str, Any]) -> None:
    validate_season_shift(str(identity.get("target_season")), str(identity.get("prior_feature_season")))
    endpoint = identity.get("endpoint")
    params = identity.get("parameters")
    if endpoint not in {PAIR_ENDPOINT, PLAYER_ENDPOINT} or not isinstance(params, Mapping):
        raise ValueError("Unsupported Phase 2A request identity")
    if params.get("league_id") != LEAGUE_ID or params.get("season_type") != "regular-season":
        raise ValueError("Unauthorized league or season type")
    season = params.get("season")
    if endpoint == PAIR_ENDPOINT:
        if season != TARGET_SEASON or params.get("measure_type") not in MEASURES:
            raise ValueError("Unauthorized pair season or measure")
        if params.get("group_quantity") != GROUP_QUANTITY:
            raise ValueError("Pair group quantity must be 2")
        if str(params.get("team_id")) not in {team[0] for team in TEAMS}:
            raise ValueError("Unauthorized canary team")
        for forbidden in ("DateFrom", "DateTo"):
            if params.get(forbidden) not in (None, ""):
                raise ValueError("Date-window requests are prohibited")
        if str(params.get("LastNGames")) != "0":
            raise ValueError("LastNGames diagnostics are prohibited")
    else:
        if season != PRIOR_FEATURE_SEASON or params.get("measure_type") != "Base":
            raise ValueError("Unauthorized prior-player season or measure")
        if params.get("per_mode") not in PLAYER_PER_MODES:
            raise ValueError("Unauthorized player PerMode")
    serialized = json.dumps(identity, sort_keys=True)
    if "2025-26" in serialized or "2024-25" in serialized:
        raise ValueError("A future/non-canary season cannot satisfy Phase 2A identity")


def diagnostic_asset_id(identity: Mapping[str, Any]) -> str:
    validate_identity(identity)
    return stable_contract_id("phase2a-raw-asset", identity)


def _safe_id(asset_id: str) -> str:
    return asset_id.replace(":", "_")


def build_manifest(pair_schemas: Mapping[str, Any], player_schema: Mapping[str, Any]) -> dict[str, Any]:
    validate_season_shift(TARGET_SEASON, PRIOR_FEATURE_SEASON)
    identities = []
    for team_id, _, _ in TEAMS:
        identities.extend(pair_identity(team_id, measure) for measure in MEASURES)
    identities.extend(player_identity(mode) for mode in PLAYER_PER_MODES)
    assets = []
    for ordinal, identity in enumerate(identities, 1):
        asset_id = diagnostic_asset_id(identity)
        stem = _safe_id(asset_id)
        assets.append({
            "ordinal": ordinal,
            "asset_id": asset_id,
            "identity": identity,
            "status": "planned",
            "attempt_count": 0,
            "attempt_history": [],
            "transition_history": [],
            "last_error": None,
            "cache": {
                "relative_path": f"phase2a/raw/{stem}.json",
                "metadata_relative_path": f"phase2a/raw/{stem}.metadata.json",
                "cache_file_bytes": None,
                "canonical_json_hash": None,
                "raw_body_hash": None,
                "serialization_version": SERIALIZATION_VERSION,
            },
            "schema_verification": None,
            "source_event": None,
        })
    identity = {
        "target_season": TARGET_SEASON,
        "prior_feature_season": PRIOR_FEATURE_SEASON,
        "season_type": "regular-season",
        "league_id": LEAGUE_ID,
        "assets": [asset["identity"] for asset in assets],
    }
    return {
        "manifest_version": MANIFEST_VERSION,
        "manifest_id": stable_contract_id("phase2a-canary-manifest", identity),
        "logical_identity": identity,
        "pair_schema_contract": deepcopy(pair_schemas),
        "pair_schema_contract_id": stable_contract_id("schema-contract", pair_schemas),
        "player_schema_contract": deepcopy(player_schema),
        "player_schema_contract_id": stable_contract_id("schema-contract", player_schema),
        "authorization": {"maximum_live_attempts": MAX_LIVE_ATTEMPTS, "retries": 0},
        "team_directory": {
            tid: {"team_name": name, "diversity_rationale": rationale}
            for tid, name, rationale in TEAMS
        },
        "transition_sequence": 0,
        "created_at": None,
        "updated_at": None,
        "raw_assets": assets,
    }


def derive_player_schema_contract(cache_root: Path) -> dict[str, Any]:
    path = cache_root / "live_responses" / "league_dash_player_stats_2023-24_base_per100possessions.json"
    payload = read_json(path)
    result_sets = payload.get("resultSets")
    if not isinstance(result_sets, list) or len(result_sets) != 1:
        raise ValueError("Approved player schema source must contain exactly one result set")
    result_set = result_sets[0]
    result_set_rows(result_set)
    if result_set.get("name") != "LeagueDashPlayerStats":
        raise ValueError("Approved player schema result-set name mismatch")
    return {"LeagueDashPlayerStats": schema_fingerprint(result_set)}


def expected_manifest(cache_root: Path) -> dict[str, Any]:
    return build_manifest(derive_approved_schema_contract(cache_root), derive_player_schema_contract(cache_root))


def manifest_path(cache_root: Path) -> Path:
    return cache_root / "phase2a" / "manifest.json"


def attempt_ledger_path(cache_root: Path) -> Path:
    return cache_root / "phase2a" / "attempt_ledger.json"


def validate_manifest(manifest: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    for key in ("manifest_version", "manifest_id", "logical_identity", "pair_schema_contract",
                "pair_schema_contract_id", "player_schema_contract", "player_schema_contract_id",
                "authorization", "team_directory"):
        if manifest.get(key) != expected.get(key):
            raise ValueError(f"Phase 2A manifest mismatch: {key}")
    assets = manifest.get("raw_assets")
    expected_assets = expected["raw_assets"]
    if not isinstance(assets, list) or len(assets) != 12:
        raise ValueError("Phase 2A manifest must contain exactly 12 assets")
    if [a.get("identity") for a in assets] != [a["identity"] for a in expected_assets]:
        raise ValueError("Phase 2A asset order or identity mismatch")
    ids, paths = set(), set()
    for asset in assets:
        validate_identity(asset["identity"])
        if asset.get("asset_id") != diagnostic_asset_id(asset["identity"]):
            raise ValueError("Phase 2A asset ID mismatch")
        path = asset.get("cache", {}).get("relative_path")
        if asset["asset_id"] in ids or path in paths:
            raise ValueError("Phase 2A asset/cache collision")
        if not str(path).startswith("phase2a/raw/"):
            raise ValueError("Phase 2A cache escaped its namespace")
        ids.add(asset["asset_id"]); paths.add(path)


class CanaryStore:
    def __init__(self, cache_root: Path, expected: Mapping[str, Any], *, clock: Callable[[], str] = utc_now):
        self.cache_root = Path(cache_root)
        self.expected = deepcopy(expected)
        self.path = manifest_path(self.cache_root)
        self.ledger_path = attempt_ledger_path(self.cache_root)
        self.clock = clock

    def create_or_load(self) -> dict[str, Any]:
        if self.path.exists():
            return self.load()
        manifest = deepcopy(self.expected)
        manifest["created_at"] = self.clock(); manifest["updated_at"] = manifest["created_at"]
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
        self._write_ledger(manifest)

    def _write_ledger(self, manifest: Mapping[str, Any]) -> None:
        ledger = {
            "ledger_version": "phase2a.attempt-ledger.v1",
            "manifest_id": manifest["manifest_id"],
            "authorization": manifest["authorization"],
            "attempts": [
                {"ordinal": a["ordinal"], "asset_id": a["asset_id"], "identity": a["identity"],
                 "status": a["status"], "attempt_history": a["attempt_history"], "last_error": a["last_error"]}
                for a in manifest["raw_assets"]
            ],
        }
        atomic_write_json(self.ledger_path, ledger)

    def transition(self, manifest: dict[str, Any], asset: dict[str, Any], status: str,
                   category: str, detail: str | None = None) -> None:
        manifest["transition_sequence"] += 1
        asset["status"] = status
        asset["transition_history"].append({"sequence": manifest["transition_sequence"], "at": self.clock(),
                                             "status": status, "category": category, "detail": detail})
        self.save(manifest)


def request_parameters(identity: Mapping[str, Any]) -> dict[str, Any]:
    validate_identity(identity)
    params = dict(identity["parameters"])
    season_type = params.pop("season_type")
    core = {"LeagueID": params.pop("league_id"), "Season": params.pop("season"),
            "SeasonType": SEASON_TYPE, "MeasureType": params.pop("measure_type")}
    if identity["endpoint"] == PAIR_ENDPOINT:
        core.update({"TeamID": params.pop("team_id"), "GroupQuantity": params.pop("group_quantity")})
    else:
        core["PerMode"] = params.pop("per_mode")
    if season_type != "regular-season":
        raise ValueError("Unauthorized season type")
    return {**params, **core}


@dataclass(frozen=True)
class TransportResult:
    status_code: int
    body: bytes
    elapsed_seconds: float


class TransportError(RuntimeError):
    def __init__(self, category: str, detail: str):
        super().__init__(detail); self.category = category; self.detail = detail


def direct_transport(identity: Mapping[str, Any], timeout_seconds: int = TIMEOUT_SECONDS) -> TransportResult:
    validate_identity(identity)
    url = PAIR_URL if identity["endpoint"] == PAIR_ENDPOINT else PLAYER_URL
    session = requests.Session(); session.trust_env = False; session.headers.update(RESEARCH_HEADERS)
    started = time.perf_counter()
    try:
        response = session.get(url, params=request_parameters(identity), timeout=timeout_seconds)
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


def _validate_returned_parameters(payload: Mapping[str, Any], identity: Mapping[str, Any]) -> None:
    returned = payload.get("parameters")
    if not isinstance(returned, Mapping):
        raise ValueError("Response lacks request-parameter identity")
    params = identity["parameters"]
    expected = {"Season": params["season"], "SeasonType": SEASON_TYPE,
                "MeasureType": params["measure_type"]}
    if identity["endpoint"] == PAIR_ENDPOINT:
        expected.update({"TeamID": int(params["team_id"]), "GroupQuantity": int(GROUP_QUANTITY)})
        # TeamDashLineups historically echoes LeagueID as null even when the
        # normalized request explicitly sends LeagueID=00.  Team identity is
        # independently required from both parameters.TeamID and Overall.
        if returned.get("LeagueID") not in (None, LEAGUE_ID, 0, "0"):
            raise ValueError(f"Response identity mismatch for LeagueID: {returned.get('LeagueID')!r}")
    else:
        expected["LeagueID"] = LEAGUE_ID
        expected["PerMode"] = params["per_mode"]
    for key, value in expected.items():
        actual = returned.get(key)
        if str(actual) != str(value):
            raise ValueError(f"Response identity mismatch for {key}: expected={value!r}, actual={actual!r}")


def _validate_player_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    sets = payload.get("resultSets")
    if not isinstance(sets, list) or len(sets) != 1 or sets[0].get("name") != "LeagueDashPlayerStats":
        raise ValueError("Player payload requires exactly one LeagueDashPlayerStats result set")
    rows = result_set_rows(sets[0])
    return {"fingerprints": [schema_fingerprint(sets[0])], "row_counts": {"LeagueDashPlayerStats": len(rows)}}


def validate_response(payload: Mapping[str, Any], identity: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    _validate_returned_parameters(payload, identity)
    if identity["endpoint"] == PAIR_ENDPOINT:
        validation = validate_payload_structure(payload)
        overall = result_set_rows(extract_result_set(dict(payload), "Overall"))
        if len(overall) != 1 or str(overall[0].get("TEAM_ID")) != identity["parameters"]["team_id"]:
            raise ValueError("Pair response team context mismatch")
        expected = manifest["pair_schema_contract"][identity["parameters"]["measure_type"]]
    else:
        validation = _validate_player_payload(payload)
        expected = manifest["player_schema_contract"]
    actual = {item["name"]: item for item in validation["fingerprints"]}
    drift = {}
    for name in set(expected) | set(actual):
        if name not in expected or name not in actual:
            drift[name] = {"classification": "result_set_name_changed", "accepted": False,
                           "expected": expected.get(name), "actual": actual.get(name)}
        else:
            drift[name] = schema_drift_report(expected[name], actual[name])
    rejected = {name: item["classification"] for name, item in drift.items() if not item["accepted"]}
    return {**validation, "drift_results": drift, "drift_classification": "identical" if not rejected else "non_identical",
            "accepted": not rejected, "rejected": rejected}


def verify_asset_cache(asset: Mapping[str, Any], cache_root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    validate_identity(asset["identity"])
    if asset["asset_id"] != diagnostic_asset_id(asset["identity"]):
        raise ValueError("Asset identity hash mismatch")
    cache = asset["cache"]
    path = cache_root / cache["relative_path"]
    metadata_path = cache_root / cache["metadata_relative_path"]
    body = path.read_bytes()
    if len(body) != cache.get("cache_file_bytes"):
        raise ValueError("Cache byte count mismatch")
    if raw_body_hash(body) != cache.get("raw_body_hash"):
        raise ValueError("Raw-body hash mismatch")
    payload = json.loads(body.decode("utf-8"))
    if canonical_json_hash(payload) != cache.get("canonical_json_hash"):
        raise ValueError("Canonical JSON hash mismatch")
    validation = validate_response(payload, asset["identity"], manifest)
    if not validation["accepted"]:
        raise ValueError(f"Schema mismatch: {validation['rejected']}")
    metadata = read_json(metadata_path)
    if metadata.get("asset_id") != asset["asset_id"] or metadata.get("identity") != asset["identity"]:
        raise ValueError("Metadata identity mismatch")
    if metadata.get("cache") != cache or metadata.get("source_event") != asset.get("source_event"):
        raise ValueError("Metadata provenance mismatch")
    return {"asset_id": asset["asset_id"], "payload": payload, **validation,
            "canonical_json_hash": cache["canonical_json_hash"], "raw_body_hash": cache["raw_body_hash"],
            "cache_file_bytes": len(body)}


def dry_run_plan(store: CanaryStore) -> dict[str, Any]:
    manifest = store.load()
    actions = []
    for asset in manifest["raw_assets"]:
        action = "acquire"
        digest = None
        if asset["status"] == "verified":
            digest = verify_asset_cache(asset, store.cache_root, manifest)["canonical_json_hash"]
            action = "reuse_verified_cache"
        elif asset["status"] in {"failed", "quarantined"}:
            action = "stop"
        actions.append({"ordinal": asset["ordinal"], "asset_id": asset["asset_id"], "action": action,
                        "identity": asset["identity"], "cache_path": asset["cache"]["relative_path"],
                        "request_parameters": request_parameters(asset["identity"]), "canonical_json_hash": digest})
        if action == "stop":
            break
    return {"dry_run": True, "network_calls": 0, "manifest_id": manifest["manifest_id"], "actions": actions}


def _result(manifest: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    counts = Counter(asset["status"] for asset in manifest["raw_assets"])
    attempts = sum(len(asset["attempt_history"]) for asset in manifest["raw_assets"])
    return {"attempted": attempts, "verified": counts["verified"], "failed": counts["failed"],
            "quarantined": counts["quarantined"], "planned": counts["planned"], **extra}


def run_acquisition(store: CanaryStore, *, dry_run: bool = True, live_acquisition: bool = False,
                    timeout_seconds: int = TIMEOUT_SECONDS, delay_seconds: float = 1.0,
                    transport: Callable[[Mapping[str, Any], int], TransportResult] | None = None,
                    sleep_fn: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    if dry_run:
        return dry_run_plan(store)
    if not live_acquisition:
        raise ValueError("Live acquisition requires explicit live_acquisition=True")
    if timeout_seconds != TIMEOUT_SECONDS or delay_seconds < 0:
        raise ValueError("Phase 2A requires timeout=30 and a nonnegative delay")
    transport = transport or direct_transport
    manifest = store.load()
    attempts_so_far = sum(len(a["attempt_history"]) for a in manifest["raw_assets"])
    if attempts_so_far > MAX_LIVE_ATTEMPTS:
        raise ValueError("Live-attempt budget already exceeded")
    for asset in manifest["raw_assets"]:
        if asset["status"] == "verified":
            try:
                verify_asset_cache(asset, store.cache_root, manifest)
            except Exception as exc:
                asset["last_error"] = {"category": "corrupt_verified_cache", "detail": str(exc)}
                store.transition(manifest, asset, "failed", "corrupt_verified_cache", str(exc))
                return _result(manifest, completed=False, stop_category="corrupt_verified_cache")
            continue
        if asset["status"] != "planned":
            return _result(manifest, completed=False, stop_category=f"existing_{asset['status']}")
        if asset["attempt_count"] or attempts_so_far >= MAX_LIVE_ATTEMPTS:
            return _result(manifest, completed=False, stop_category="retry_or_budget_prohibited")
        cache_path = store.cache_root / asset["cache"]["relative_path"]
        metadata_path = store.cache_root / asset["cache"]["metadata_relative_path"]
        if cache_path.exists() or metadata_path.exists():
            return _result(manifest, completed=False, stop_category="unverified_cache_collision")
        attempt = {"attempt_number": 1, "request_kind": "phase2a_live", "started_at": store.clock(),
                   "status": "started", "timeout_seconds": timeout_seconds}
        asset["attempt_history"].append(attempt); asset["attempt_count"] = 1
        store.save(manifest); attempts_so_far += 1
        try:
            response = transport(asset["identity"], timeout_seconds)
            attempt.update({"latency_seconds": response.elapsed_seconds, "http_status": response.status_code,
                            "response_body_bytes": len(response.body)})
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
                quarantine = store.cache_root / "phase2a" / "quarantine" / f"{_safe_id(asset['asset_id'])}.body"
                atomic_write_bytes_new(quarantine, response.body)
                attempt["preserved_response_path"] = str(quarantine.relative_to(store.cache_root)).replace("\\", "/")
                raise TransportError("schema_quarantine", json.dumps(validation["rejected"], sort_keys=True))
            # Promotion happens only after identity, structure, row-width, and schema validation.
            atomic_write_bytes_new(cache_path, response.body)
            cache = asset["cache"]
            cache.update({"cache_file_bytes": cache_path.stat().st_size,
                          "canonical_json_hash": canonical_json_hash(payload), "raw_body_hash": raw_body_hash(response.body),
                          "canonical_json_hash_algorithm": CANONICALIZATION, "serialization_version": SERIALIZATION_VERSION})
            asset["source_event"] = {"provenance_format": "phase2a-live-v1", "acquired_at": store.clock(),
                                     "http_status": response.status_code, "latency_seconds": response.elapsed_seconds,
                                     "response_body_bytes": len(response.body), "raw_body_hash": raw_body_hash(response.body)}
            atomic_write_json(metadata_path, {"asset_id": asset["asset_id"], "identity": asset["identity"],
                                              "source_event": asset["source_event"], "cache": cache,
                                              "schema_verification": asset["schema_verification"]})
            store.transition(manifest, asset, "acquired", "validated_response_cached")
            replay = verify_asset_cache(asset, store.cache_root, manifest)
            attempt.update({"status": "verified", "error_category": None, "error_detail": None,
                            "canonical_json_hash": replay["canonical_json_hash"], "cache_file_bytes": replay["cache_file_bytes"],
                            "row_counts": replay["row_counts"]})
            asset["last_error"] = None
            store.transition(manifest, asset, "verified", "cache_replay_verified", replay["canonical_json_hash"])
        except TransportError as exc:
            attempt.update({"status": "quarantined" if exc.category == "schema_quarantine" else "failed",
                            "error_category": exc.category, "error_detail": exc.detail})
            asset["last_error"] = {"category": exc.category, "detail": exc.detail}
            status = "quarantined" if exc.category == "schema_quarantine" else "failed"
            store.transition(manifest, asset, status, exc.category, exc.detail)
            return _result(manifest, completed=False, stop_category=exc.category, stop_detail=exc.detail)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            attempt.update({"status": "failed", "error_category": "unexpected_exception", "error_detail": detail})
            asset["last_error"] = {"category": "unexpected_exception", "detail": detail}
            store.transition(manifest, asset, "failed", "unexpected_exception", detail)
            return _result(manifest, completed=False, stop_category="unexpected_exception", stop_detail=detail)
        if asset["ordinal"] < len(manifest["raw_assets"]):
            sleep_fn(delay_seconds)
    return _result(manifest, completed=True, stop_category=None)


def reconcile_quarantine_evidence(store: CanaryStore) -> dict[str, Any]:
    """Record a persisted schema fingerprint for an existing quarantine body.

    This is cache-only, does not promote the body, and is idempotent.  It exists
    for acquisition processes interrupted after the quarantine body was written
    but before all validation detail reached the manifest.
    """
    manifest = store.load()
    reconciled = []
    for asset in manifest["raw_assets"]:
        if asset["status"] != "quarantined":
            continue
        attempts = asset.get("attempt_history", [])
        if len(attempts) != 1 or not attempts[0].get("preserved_response_path"):
            raise ValueError("Quarantined asset lacks exactly one preserved response")
        path = store.cache_root / attempts[0]["preserved_response_path"]
        body = path.read_bytes()
        payload = json.loads(body.decode("utf-8"))
        validation = validate_response(payload, asset["identity"], manifest)
        if validation["accepted"]:
            raise ValueError("A quarantined payload unexpectedly matches the approved schema")
        evidence = {
            "status": "rejected",
            **validation,
            "quarantine_relative_path": attempts[0]["preserved_response_path"],
            "response_body_bytes": len(body),
            "raw_body_hash": raw_body_hash(body),
            "canonical_json_hash": canonical_json_hash(payload),
        }
        existing = asset.get("schema_verification")
        if existing not in (None, evidence):
            for key in ("status", "fingerprints", "row_counts", "drift_results", "rejected"):
                if existing.get(key) != evidence.get(key):
                    raise ValueError("Existing quarantine schema evidence differs")
        asset["schema_verification"] = evidence
        reconciled.append(asset["asset_id"])
    store.save(manifest)
    return {"network_calls": 0, "reconciled_asset_ids": reconciled}


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool): return None
    try: result = float(value)
    except (TypeError, ValueError): return None
    return result if math.isfinite(result) else None


def _quantiles(values: list[float]) -> dict[str, Any]:
    values = sorted(values)
    if not values: return {"count": 0}
    def q(f: float) -> float:
        pos = f * (len(values)-1); low = int(pos); high = min(low+1, len(values)-1); w = pos-low
        return values[low]*(1-w)+values[high]*w
    return {"count": len(values), "minimum": values[0], "p25": q(.25), "median": q(.5),
            "p75": q(.75), "p90": q(.9), "maximum": values[-1], "total": sum(values)}


def _pair_rows(payload: Mapping[str, Any], season: str, team_id: str) -> list[dict[str, Any]]:
    return attach_pair_context(result_set_rows(extract_result_set(dict(payload), "Lineups")), season, team_id)


def _player_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return result_set_rows(extract_result_set(dict(payload), "LeagueDashPlayerStats"))


def _boundary(rows: list[dict[str, Any]], measure: str) -> dict[str, Any]:
    ids = set()
    for row in rows:
        key = row.get("pair_key")
        if key: ids.update(key)
    theoretical = len(ids)*(len(ids)-1)//2
    rank_fields = [key for key in (rows[0].keys() if rows else []) if key.endswith("_RANK")]
    rank_max = {field: max((v for row in rows if (v := _numeric(row.get(field))) is not None), default=None) for field in rank_fields}
    exposure_field = "MIN" if measure == "Base" else "POSS"
    values = [v for row in rows if (v := _numeric(row.get(exposure_field))) is not None]
    return {"returned_rows": len(rows), "distinct_players": len(ids), "theoretical_pairs": theoretical,
            "absent_theoretical_combinations": theoretical-len({r["pair_key"] for r in rows if r.get("pair_key")}),
            "minimum_returned_exposure": min(values) if values else None, "rank_maxima": rank_max,
            "exact_repeated_boundary": len(rows) == 250,
            "classification": "boundary_signal_present" if len(rows) == 250 else "no_boundary_signal_observed"}


def _pair_identifier_detail(rows: list[dict[str, Any]]) -> dict[str, int]:
    malformed = same_player = 0
    for row in rows:
        raw = row.get("GROUP_ID")
        tokens = [token for token in raw.strip("-").split("-") if token] if isinstance(raw, str) else []
        if len(tokens) != 2 or any(not token.isdecimal() or int(token) <= 0 for token in tokens):
            malformed += 1
        elif tokens[0] == tokens[1]:
            same_player += 1
    return {"malformed_identifiers": malformed, "same_player_identifiers": same_player}


def _extreme_rating_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bands = (("poss_1_9", 1, 10), ("poss_10_24", 10, 25), ("poss_25_49", 25, 50),
             ("poss_50_99", 50, 100), ("poss_100_plus", 100, math.inf))
    result = {}
    for label, lower, upper in bands:
        values = [_numeric(row.get("NET_RATING")) for row in rows
                  if (poss := _numeric(row.get("POSS"))) is not None and lower <= poss < upper]
        numeric = [value for value in values if value is not None]
        result[label] = {"rows": len(numeric), "minimum": min(numeric) if numeric else None,
                         "maximum": max(numeric) if numeric else None,
                         "absolute_net_rating_at_least_50": sum(abs(value) >= 50 for value in numeric),
                         "absolute_net_rating_at_least_100": sum(abs(value) >= 100 for value in numeric)}
    return result


def _trade_aggregation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    multi = [row for row in rows if (_numeric(row.get("TEAM_COUNT")) or 0) > 1]
    return {"rows_with_team_count_above_one": len(multi),
            "player_ids": [str(row.get("PLAYER_ID")) for row in multi],
            "team_abbreviations": sorted({str(row.get("TEAM_ABBREVIATION")) for row in multi}),
            "gp_above_82_rows": sum((_numeric(row.get("GP")) or 0) > 82 for row in rows),
            "interpretation": "one aggregate row per stable PLAYER_ID; TEAM_COUNT exposes multi-team history"}


def analyze_cache(store: CanaryStore) -> dict[str, Any]:
    manifest = store.load()
    pair_assets = manifest["raw_assets"][:10]
    if any(a["status"] != "verified" for a in pair_assets):
        raise ValueError("All ten pair assets must be verified before pair-canary analysis")
    verified = {a["ordinal"]: verify_asset_cache(a, store.cache_root, manifest) for a in pair_assets}
    teams_summary, all_base, all_advanced = {}, [], []
    for index, (team_id, team_name, _) in enumerate(TEAMS):
        base_asset = verified[index*2+1]; adv_asset = verified[index*2+2]
        base = _pair_rows(base_asset["payload"], TARGET_SEASON, team_id)
        adv = _pair_rows(adv_asset["payload"], TARGET_SEASON, team_id)
        base_summary, adv_summary = summarize_pair_rows(base), summarize_pair_rows(adv)
        reconciliation = join_pair_measures(base, adv)
        target = summarize_advanced_targets(adv)
        ineligible = identify_zero_or_missing_possession_rows(adv, base)
        by_key_base = {r["pair_key"]: r for r in base if r.get("pair_key")}
        matched = []
        for row in adv:
            if row.get("pair_key") in by_key_base:
                joined = dict(by_key_base[row["pair_key"]]); joined.update({f"ADV_{k}": v for k,v in row.items()})
                joined["POSS"] = row.get("POSS"); joined["pair_key"] = row["pair_key"]
                matched.append(joined)
        teams_summary[team_id] = {
            "team_name": team_name, "base_rows": len(base), "advanced_rows": len(adv),
            "base_identity": base_summary, "advanced_identity": adv_summary,
            "reconciliation": reconciliation, "target_audit": target,
            "target_ineligible_rows": ineligible, "possession_distribution": possession_distribution(adv),
            "base_identifier_detail": _pair_identifier_detail(base),
            "advanced_identifier_detail": _pair_identifier_detail(adv),
            "extreme_net_rating_by_exposure": _extreme_rating_summary(adv),
            "base_minute_distribution": _quantiles([v for r in base if (v := _numeric(r.get("MIN"))) is not None]),
            "base_population": _boundary(base, "Base"), "advanced_population": _boundary(adv, "Advanced"),
            "same_canonical_key_set": reconciliation["base_only_pairs"] == reconciliation["advanced_only_pairs"] == 0,
        }
        all_base.extend(base); all_advanced.extend(adv)
    combined = validate_combined_observation_keys(all_base)
    player_assets: dict[str, Any] = {}
    coverage: dict[str, Any] = {"status": "not_run_quarantined_prior_source"}
    min_audit: dict[str, Any] = {"classification": "unresolved", "reason": "Totals request skipped after Per100 schema quarantine"}
    for ordinal, mode in ((11, "Per100Possessions"), (12, "Totals")):
        asset = manifest["raw_assets"][ordinal - 1]
        entry: dict[str, Any] = {"status": asset["status"], "identity": asset["identity"],
                                "schema_verification": asset.get("schema_verification")}
        if asset["status"] == "verified":
            replay = verify_asset_cache(asset, store.cache_root, manifest)
            rows = _player_rows(replay["payload"])
            entry["stable_id_audit"] = audit_stable_ids(rows)
        elif asset["status"] == "quarantined":
            attempt = asset["attempt_history"][0]
            body = (store.cache_root / attempt["preserved_response_path"]).read_bytes()
            payload = json.loads(body.decode("utf-8")); rows = _player_rows(payload)
            entry.update({"result_sets": [rs.get("name") for rs in payload["resultSets"]],
                          "row_count": len(rows), "stable_id_audit_diagnostic_only": audit_stable_ids(rows),
                          "trade_aggregation_diagnostic_only": _trade_aggregation(rows),
                          "response_body_bytes": len(body), "raw_body_hash": raw_body_hash(body),
                          "canonical_json_hash": canonical_json_hash(payload)})
        player_assets[mode] = entry
    if all(manifest["raw_assets"][ordinal - 1]["status"] == "verified" for ordinal in (11, 12)):
        player_per100 = _player_rows(verify_asset_cache(manifest["raw_assets"][10], store.cache_root, manifest)["payload"])
        player_totals = _player_rows(verify_asset_cache(manifest["raw_assets"][11], store.cache_root, manifest)["payload"])
        prior_index = player_rows_by_id(attach_prior_context(player_per100, PRIOR_FEATURE_SEASON))
        coverage = {}
        adv_lookup = {(r["team_id"], r.get("pair_key")): r for r in all_advanced}
        combined_pairs = []
        for team_id, _, _ in TEAMS:
            pair_rows = []
            for row in (r for r in all_base if r["team_id"] == team_id):
                item = dict(row); item["POSS"] = adv_lookup.get((team_id, row.get("pair_key")), {}).get("POSS")
                pair_rows.append(item); combined_pairs.append(item)
            joined = join_pairs_to_prior_players(pair_rows, prior_index, TARGET_SEASON, PRIOR_FEATURE_SEASON)
            coverage[team_id] = {"players": summarize_player_level_coverage(pair_rows, prior_index),
                                 "pairs": summarize_pair_level_coverage(joined),
                                 "exposure": summarize_exposure_weighted_coverage(joined)}
        joined = join_pairs_to_prior_players(combined_pairs, prior_index, TARGET_SEASON, PRIOR_FEATURE_SEASON)
        coverage["combined"] = {"players": summarize_player_level_coverage(combined_pairs, prior_index),
                                "pairs": summarize_pair_level_coverage(joined),
                                "exposure": summarize_exposure_weighted_coverage(joined)}
        totals_by_id = {str(r.get("PLAYER_ID")): r for r in player_totals if r.get("PLAYER_ID") not in (None, "")}
        shared_minutes = []
        for row in player_per100:
            pid = str(row.get("PLAYER_ID")); per100_min = _numeric(row.get("MIN")); total_min = _numeric(totals_by_id.get(pid, {}).get("MIN"))
            if per100_min is not None and total_min is not None:
                shared_minutes.append((pid, per100_min, total_min))
        per100_minutes = [x[1] for x in shared_minutes]; total_minutes = [x[2] for x in shared_minutes]
        min_audit = {"comparable_players": len(shared_minutes), "per100_min": _quantiles(per100_minutes),
                     "totals_min": _quantiles(total_minutes),
                     "known_high_minute_records": sorted(shared_minutes, key=lambda x: x[2], reverse=True)[:10],
                     "units_distinct": bool(shared_minutes) and max(total_minutes) > 1000 and max(per100_minutes) < 100,
                     "classification": "season_total_minutes_supported" if shared_minutes and max(total_minutes) > 1000 and max(per100_minutes) < 100 else "unresolved"}
    assets = [{"ordinal": a["ordinal"], "asset_id": a["asset_id"], "identity": a["identity"], "status": a["status"],
               "latency_seconds": (a.get("source_event") or {}).get("latency_seconds"),
               "response_body_bytes": (a.get("source_event") or {}).get("response_body_bytes"),
               "cache_file_bytes": a["cache"].get("cache_file_bytes"), "raw_body_hash": a["cache"].get("raw_body_hash"),
               "canonical_json_hash": a["cache"].get("canonical_json_hash"),
               "schema": (a.get("schema_verification") or {}).get("fingerprints"),
               "row_counts": (a.get("schema_verification") or {}).get("row_counts")} for a in manifest["raw_assets"]]
    clean_pairs = all(t["reconciliation"]["base_only_pairs"] == t["reconciliation"]["advanced_only_pairs"] == 0 and
                      t["reconciliation"]["one_to_one"] for t in teams_summary.values())
    schema_ok = all((a.get("schema_verification") or {}).get("accepted") for a in pair_assets)
    summary = {"analysis_version": "phase2a.analysis.v1", "target_season": TARGET_SEASON,
               "prior_feature_season": PRIOR_FEATURE_SEASON, "assets": assets, "teams": teams_summary,
               "combined_identity": combined, "target_ineligible_count": sum(len(t["target_ineligible_rows"]) for t in teams_summary.values()),
               "player_assets": player_assets,
               "prior_coverage": coverage, "minutes_semantics": min_audit,
               "pair_schema_compatibility": "identical" if schema_ok else "non_identical",
               "prior_player_schema_compatibility": (
                   "additive_quarantined" if manifest["raw_assets"][10]["status"] == "quarantined"
                   else "identical" if manifest["raw_assets"][10]["status"] == "verified" else "not_observed"
               ),
               "base_advanced_reconciliation": "clean" if clean_pairs else "failed",
               "primary_classification": ("historical canary supported; complete 2023-24 raw acquisition ready"
                   if schema_ok and clean_pairs and min_audit["classification"] == "season_total_minutes_supported"
                   else "historical pair acquisition supported; prior-season join unresolved"
                   if schema_ok and clean_pairs else "historical canary failed; Phase 2B blocked")}
    deterministic = deepcopy(summary)
    for asset in deterministic["assets"]:
        asset.pop("latency_seconds", None)
    summary["deterministic_analysis_sha256"] = canonical_json_hash(deterministic)
    return summary
