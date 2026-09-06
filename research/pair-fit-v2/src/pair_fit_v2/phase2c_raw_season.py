"""Bounded Phase 2C acquisition and audit for 2022-23 pair outcomes.

The module deliberately owns only Phase 2C state.  It reuses the reviewed
schema, hashing, pair parsing, and coverage helpers from earlier research
phases while enforcing a new season-scoped plan and retry policy.
"""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Mapping

import requests
from requests.adapters import HTTPAdapter

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS
from pair_fit_v2.lineup_audit import (
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
    PLAYER_EXTRA_PARAMETERS,
    SERIALIZATION_VERSION,
    _boundary,
    _extreme_rating_summary,
    _pair_identifier_detail,
    _pair_rows,
    _player_rows,
    _quantiles,
    utc_now,
)
from pair_fit_v2.phase2b_raw_season import (
    _coverage_detail,
    _numeric,
    _positive_target_failures,
    _threshold_coverage,
    create_store as create_phase2b_store,
    load_team_inventory,
    strict_pair_identifier_audit,
    strict_player_id,
)
from pair_fit_v2.player_audit import (
    attach_prior_context,
    join_pairs_to_prior_players,
    player_rows_by_id,
    summarize_exposure_weighted_coverage,
    summarize_pair_level_coverage,
    summarize_player_level_coverage,
)

TARGET_SEASON = "2022-23"
PRIOR_FEATURE_SEASON = "2021-22"
SEASON_TYPE = "Regular Season"
LEAGUE_ID = "00"
GROUP_QUANTITY = "2"
MEASURES = ("Base", "Advanced")
PLAYER_PER_MODES = ("Per100Possessions", "Totals")
PAIR_ENDPOINT = "TeamDashLineups"
PLAYER_ENDPOINT = "LeagueDashPlayerStats"
PAIR_URL = "https://stats.nba.com/stats/teamdashlineups"
PLAYER_URL = "https://stats.nba.com/stats/leaguedashplayerstats"
TIMEOUT_SECONDS = 30
MIN_DELAY_SECONDS = 1.0
MAX_FIRST_ATTEMPTS = 62
MAX_RETRIES = 6
MAX_ATTEMPTS = 68
RETRY_HTTP_STATUSES = frozenset({500, 502, 503, 504})
RETRY_CATEGORIES = frozenset({"timeout", "transient_connection_failure"})
CANARY_TEAM_IDS = (
    "1610612744", "1610612738", "1610612764", "1610612751", "1610612766"
)
MANIFEST_VERSION = "phase2c.raw-season.v1"
LEDGER_VERSION = "phase2c.attempt-ledger.v1"
ANALYSIS_VERSION = "phase2c.release-audit.v1"
PHASE2B_HASHES = {
    "manifest": "af8acbc10adf110f43c7c53a0ab2d6b402e3121fbe57e2d8b5dc3de7072e689e",
    "ledger": "d298f15316dec37cfb3efe6fb9f1451cb3052ed7a1f0b603ce0a4d6057f62dcb",
    "analysis": "00f4324311368184d1c184be89d23b866551678b3715c262e76b36f459e24b82",
}


def _sha256_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_season_scope(target: str, prior: str) -> None:
    if (target, prior) != (TARGET_SEASON, PRIOR_FEATURE_SEASON):
        raise ValueError("Phase 2C authorizes only target 2022-23 and prior 2021-22")
    if int(prior[:4]) + 1 != int(target[:4]):
        raise ValueError("Prior-player season must be the immediately preceding season")


def _phase2b_prerequisite(cache_root: Path) -> dict[str, Any]:
    store = create_phase2b_store(cache_root)
    analysis = __import__(
        "pair_fit_v2.phase2b_raw_season", fromlist=["analyze_release"]
    ).analyze_release(store)
    observed = {
        "manifest": _sha256_file(store.path),
        "ledger": _sha256_file(store.ledger_path),
        "analysis": analysis["deterministic_analysis_sha256"],
    }
    if observed != PHASE2B_HASHES:
        raise ValueError(f"Immutable Phase 2B prerequisite mismatch: {observed}")
    if (
        analysis["combined"]["matched_observation_keys"] != 5207
        or analysis["combined"]["target_ineligible_rows"] != 17
        or analysis["primary_classification"]
        != "2023-24 raw release supported with population caveats; next historical phase ready for separate authorization"
    ):
        raise ValueError("Immutable Phase 2B conclusion mismatch")
    return {"hashes": observed, "classification": analysis["primary_classification"]}


def _team_order(cache_root: Path) -> tuple[tuple[str, str], ...]:
    directory = load_team_inventory(cache_root)
    indexed = {team_id: name for team_id, name in directory}
    canary = tuple((team_id, indexed[team_id]) for team_id in CANARY_TEAM_IDS)
    remaining = tuple(item for item in directory if item[0] not in CANARY_TEAM_IDS)
    if len(canary) != 5 or len(remaining) != 25:
        raise ValueError("Phase 2C requires five canary and 25 remaining teams")
    return canary + remaining


def _identity(endpoint: str, parameters: Mapping[str, Any], team_ids: set[str]) -> dict[str, Any]:
    value = {
        "endpoint": endpoint,
        "target_season": TARGET_SEASON,
        "prior_feature_season": PRIOR_FEATURE_SEASON,
        "parameters": dict(parameters),
    }
    validate_identity(value, team_ids)
    return value


def player_identity(per_mode: str, team_ids: set[str]) -> dict[str, Any]:
    return _identity(PLAYER_ENDPOINT, {
        **PLAYER_EXTRA_PARAMETERS,
        "league_id": LEAGUE_ID,
        "season": PRIOR_FEATURE_SEASON,
        "season_type": "regular-season",
        "measure_type": "Base",
        "per_mode": per_mode,
    }, team_ids)


def pair_identity(team_id: str, measure: str, team_ids: set[str]) -> dict[str, Any]:
    return _identity(PAIR_ENDPOINT, {
        **TEAM_DASH_LINEUPS_EXTRA_PARAMETERS,
        "league_id": LEAGUE_ID,
        "season": TARGET_SEASON,
        "season_type": "regular-season",
        "team_id": str(team_id),
        "group_quantity": GROUP_QUANTITY,
        "measure_type": measure,
    }, team_ids)


def validate_identity(identity: Mapping[str, Any], team_ids: set[str]) -> None:
    validate_season_scope(str(identity.get("target_season")), str(identity.get("prior_feature_season")))
    params = identity.get("parameters")
    endpoint = identity.get("endpoint")
    if endpoint not in {PAIR_ENDPOINT, PLAYER_ENDPOINT} or not isinstance(params, Mapping):
        raise ValueError("Unauthorized Phase 2C endpoint")
    if params.get("league_id") != LEAGUE_ID or params.get("season_type") != "regular-season":
        raise ValueError("Unauthorized Phase 2C league or season type")
    if params.get("DateFrom") not in (None, "") or params.get("DateTo") not in (None, ""):
        raise ValueError("Date windows are prohibited")
    if str(params.get("LastNGames")) != "0":
        raise ValueError("LastNGames diagnostics are prohibited")
    if endpoint == PAIR_ENDPOINT:
        team_id = strict_player_id(params.get("team_id"), field="team_id")
        if (
            params.get("season") != TARGET_SEASON
            or params.get("measure_type") not in MEASURES
            or params.get("group_quantity") != GROUP_QUANTITY
            or team_id not in team_ids
        ):
            raise ValueError("Unauthorized Phase 2C pair identity")
    elif (
        params.get("season") != PRIOR_FEATURE_SEASON
        or params.get("measure_type") != "Base"
        or params.get("per_mode") not in PLAYER_PER_MODES
    ):
        raise ValueError("Unauthorized Phase 2C player identity")
    serialized = json.dumps(identity, sort_keys=True)
    for forbidden in ("2023-24", "2024-25", "2025-26"):
        if forbidden in serialized:
            raise ValueError("A non-Phase-2C season cannot satisfy the request identity")


def request_parameters(identity: Mapping[str, Any], team_ids: set[str]) -> dict[str, Any]:
    validate_identity(identity, team_ids)
    params = dict(identity["parameters"])
    params.pop("season_type")
    core = {
        "LeagueID": params.pop("league_id"),
        "Season": params.pop("season"),
        "SeasonType": SEASON_TYPE,
        "MeasureType": params.pop("measure_type"),
    }
    if identity["endpoint"] == PAIR_ENDPOINT:
        core.update({"TeamID": params.pop("team_id"), "GroupQuantity": params.pop("group_quantity")})
    else:
        core["PerMode"] = params.pop("per_mode")
    return {**params, **core}


def asset_id(identity: Mapping[str, Any]) -> str:
    return stable_contract_id("phase2c-raw-asset", identity)


def _safe_id(value: str) -> str:
    return value.replace(":", "_")


def manifest_path(cache_root: Path) -> Path:
    return cache_root / "phase2c/manifest.json"


def ledger_path(cache_root: Path) -> Path:
    return cache_root / "phase2c/attempt_ledger.json"


def plan_path(cache_root: Path) -> Path:
    return cache_root / "phase2c/initial_plan.json"


def allowlist_path(cache_root: Path) -> Path:
    return cache_root / "phase2c/live_allowlist.json"


def build_expected_manifest(cache_root: Path) -> dict[str, Any]:
    prerequisite = _phase2b_prerequisite(cache_root)
    teams = _team_order(cache_root)
    team_ids = {team_id for team_id, _ in teams}
    phase2b = read_json(cache_root / "phase2b/release_manifest.json")
    phase2a = read_json(cache_root / "phase2a/manifest.json")
    player_schema = phase2a.get("active_player_schema_contract")
    if phase2a.get("active_player_schema_version") != "phase2a.player-base.v2" or not player_schema:
        raise ValueError("Reviewed 69-column player schema is not active")
    identities = [player_identity(mode, team_ids) for mode in PLAYER_PER_MODES]
    for team_id, _name in teams:
        identities.extend(pair_identity(team_id, measure, team_ids) for measure in MEASURES)
    assets = []
    for ordinal, identity in enumerate(identities, 1):
        aid = asset_id(identity)
        stem = _safe_id(aid)
        team_id = identity["parameters"].get("team_id")
        assets.append({
            "ordinal": ordinal,
            "asset_id": aid,
            "identity": identity,
            "team_name": dict(teams).get(team_id),
            "status": "planned",
            "attempt_count": 0,
            "attempt_history": [],
            "transition_history": [],
            "last_error": None,
            "cache": {
                "relative_path": f"phase2c/raw/{stem}.json",
                "metadata_relative_path": f"phase2c/raw/{stem}.metadata.json",
                "cache_file_bytes": None,
                "raw_body_hash": None,
                "canonical_json_hash": None,
                "canonical_json_hash_algorithm": CANONICALIZATION,
                "serialization_version": SERIALIZATION_VERSION,
            },
            "schema_verification": None,
            "source_event": None,
        })
    logical = {
        "target_season": TARGET_SEASON,
        "prior_feature_season": PRIOR_FEATURE_SEASON,
        "season_type": "regular-season",
        "league_id": LEAGUE_ID,
        "assets": identities,
    }
    return {
        "manifest_version": MANIFEST_VERSION,
        "manifest_id": stable_contract_id("phase2c-manifest", logical),
        "logical_identity": logical,
        "authorization": {
            "maximum_first_attempts": MAX_FIRST_ATTEMPTS,
            "maximum_retry_attempts": MAX_RETRIES,
            "maximum_total_attempts": MAX_ATTEMPTS,
            "maximum_attempts_per_asset": 2,
        },
        "team_directory": {team_id: {"team_name": name} for team_id, name in teams},
        "approved_pair_schema_contract": deepcopy(phase2b["approved_pair_schema_contract"]),
        "approved_pair_schema_contract_id": phase2b["approved_pair_schema_contract_id"],
        "approved_player_schema_contract": deepcopy(player_schema),
        "approved_player_schema_version": phase2a["active_player_schema_version"],
        "approved_player_schema_contract_id": stable_contract_id("schema-contract", player_schema),
        "phase2b_prerequisite": prerequisite,
        "transition_sequence": 0,
        "created_at": None,
        "updated_at": None,
        "player_source_gate": None,
        "team_gate_results": {},
        "canary_result": None,
        "integrity_stop": None,
        "assets": assets,
    }


def validate_manifest(manifest: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    immutable = (
        "manifest_version", "manifest_id", "logical_identity", "authorization", "team_directory",
        "approved_pair_schema_contract", "approved_pair_schema_contract_id",
        "approved_player_schema_contract", "approved_player_schema_version",
        "approved_player_schema_contract_id", "phase2b_prerequisite",
    )
    for key in immutable:
        if manifest.get(key) != expected.get(key):
            raise ValueError(f"Phase 2C manifest mismatch: {key}")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or len(assets) != 62:
        raise ValueError("Phase 2C manifest must contain exactly 62 assets")
    if [item.get("identity") for item in assets] != [item["identity"] for item in expected["assets"]]:
        raise ValueError("Phase 2C request identity/order changed")
    team_ids = set(manifest["team_directory"])
    ids: set[str] = set()
    paths: set[str] = set()
    attempts = retries = firsts = 0
    for item in assets:
        validate_identity(item["identity"], team_ids)
        if item.get("asset_id") != asset_id(item["identity"]):
            raise ValueError("Phase 2C asset ID mismatch")
        path = str(item.get("cache", {}).get("relative_path"))
        if item["asset_id"] in ids or path in paths or not path.startswith("phase2c/raw/"):
            raise ValueError("Phase 2C asset/cache collision")
        ids.add(item["asset_id"]); paths.add(path)
        history = item.get("attempt_history")
        if not isinstance(history, list) or item.get("attempt_count") != len(history) or len(history) > 2:
            raise ValueError("Phase 2C attempt history violates per-asset limit")
        if [event.get("attempt_number") for event in history] != list(range(1, len(history) + 1)):
            raise ValueError("Phase 2C attempt numbering is not contiguous")
        attempts += len(history)
        firsts += bool(history)
        retries += max(0, len(history) - 1)
    if attempts > MAX_ATTEMPTS or firsts > MAX_FIRST_ATTEMPTS or retries > MAX_RETRIES:
        raise ValueError("Phase 2C cumulative attempt budget exceeded")


class Phase2CStore:
    def __init__(self, cache_root: Path, expected: Mapping[str, Any], *, clock: Callable[[], str]):
        self.cache_root = Path(cache_root)
        self.expected = deepcopy(expected)
        self.path = manifest_path(self.cache_root)
        self.ledger_path = ledger_path(self.cache_root)
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
        value = read_json(self.path)
        validate_manifest(value, self.expected)
        self._validate_ledger(value)
        return value

    def save(self, manifest: dict[str, Any]) -> None:
        validate_manifest(manifest, self.expected)
        manifest["updated_at"] = self.clock()
        atomic_write_json(self.path, manifest)
        atomic_write_json(self.ledger_path, {
            "ledger_version": LEDGER_VERSION,
            "manifest_id": manifest["manifest_id"],
            "authorization": manifest["authorization"],
            "player_source_gate": deepcopy(manifest.get("player_source_gate")),
            "canary_result": deepcopy(manifest.get("canary_result")),
            "integrity_stop": deepcopy(manifest.get("integrity_stop")),
            "attempts": [{
                "ordinal": item["ordinal"], "asset_id": item["asset_id"],
                "identity": item["identity"], "status": item["status"],
                "attempt_history": item["attempt_history"], "last_error": item["last_error"],
            } for item in manifest["assets"]],
        })

    def _validate_ledger(self, manifest: Mapping[str, Any]) -> None:
        ledger = read_json(self.ledger_path)
        expected = {
            "ledger_version": LEDGER_VERSION,
            "manifest_id": manifest["manifest_id"],
            "authorization": manifest["authorization"],
            "player_source_gate": manifest.get("player_source_gate"),
            "canary_result": manifest.get("canary_result"),
            "integrity_stop": manifest.get("integrity_stop"),
            "attempts": [{
                "ordinal": item["ordinal"], "asset_id": item["asset_id"],
                "identity": item["identity"], "status": item["status"],
                "attempt_history": item["attempt_history"], "last_error": item["last_error"],
            } for item in manifest["assets"]],
        }
        if ledger != expected:
            raise ValueError("Phase 2C attempt ledger does not match manifest state")

    def transition(self, manifest: dict[str, Any], item: dict[str, Any], status: str, category: str, detail: str | None = None) -> None:
        manifest["transition_sequence"] += 1
        item["status"] = status
        item["transition_history"].append({
            "sequence": manifest["transition_sequence"], "at": self.clock(),
            "status": status, "category": category, "detail": detail,
        })
        self.save(manifest)


def create_store(cache_root: Path, *, clock: Callable[[], str] | None = None) -> Phase2CStore:
    return Phase2CStore(cache_root, build_expected_manifest(cache_root), clock=clock or utc_now)


def _plan_document(store: Phase2CStore) -> dict[str, Any]:
    manifest = store.expected
    team_ids = set(manifest["team_directory"])
    return {
        "plan_version": "phase2c.initial-plan.v1", "manifest_id": manifest["manifest_id"],
        "network_calls": 0, "read_only_preview": True,
        "assets": [{
            "ordinal": item["ordinal"], "asset_id": item["asset_id"],
            "identity": item["identity"], "cache_path": item["cache"]["relative_path"],
            "request_parameters": request_parameters(item["identity"], team_ids),
        } for item in manifest["assets"]],
    }


def dry_run_plan(store: Phase2CStore) -> dict[str, Any]:
    result = _plan_document(store)
    result["side_effects"] = []
    return result


def persist_initial_plan(store: Phase2CStore) -> dict[str, Any]:
    manifest = store.create_or_load()
    plan = _plan_document(store)
    allowlist = {
        "allowlist_version": "phase2c.live-allowlist.v1",
        "manifest_id": manifest["manifest_id"],
        "assets": [{"ordinal": item["ordinal"], "asset_id": item["asset_id"], "identity": item["identity"]}
                   for item in manifest["assets"]],
    }
    for path, value in ((plan_path(store.cache_root), plan), (allowlist_path(store.cache_root), allowlist)):
        body = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        if path.exists():
            if path.read_bytes() != body:
                raise ValueError(f"Create-once evidence conflicts: {path.name}")
        else:
            atomic_write_bytes_new(path, body)
    return {"plan_sha256": _sha256_file(plan_path(store.cache_root)),
            "allowlist_sha256": _sha256_file(allowlist_path(store.cache_root)), "network_calls": 0}


def _approved_identities(store: Phase2CStore) -> dict[str, Mapping[str, Any]]:
    plan = read_json(plan_path(store.cache_root)); allowlist = read_json(allowlist_path(store.cache_root))
    if plan != _plan_document(store) or allowlist.get("manifest_id") != store.expected["manifest_id"]:
        raise ValueError("Phase 2C persisted plan/allowlist mismatch")
    expected = [{"ordinal": item["ordinal"], "asset_id": item["asset_id"], "identity": item["identity"]}
                for item in store.expected["assets"]]
    if allowlist.get("assets") != expected:
        raise ValueError("Phase 2C allowlist changed")
    return {item["asset_id"]: item for item in expected}


@dataclass(frozen=True)
class TransportResult:
    status_code: int
    body: bytes
    elapsed_seconds: float
    headers: Mapping[str, str] | None = None


class TransportError(RuntimeError):
    def __init__(self, category: str, detail: str):
        super().__init__(detail); self.category = category; self.detail = detail


def direct_transport(identity: Mapping[str, Any], timeout_seconds: int = TIMEOUT_SECONDS, *,
                     cache_root: Path, approved_identities: Mapping[str, Mapping[str, Any]]) -> TransportResult:
    team_ids = {team_id for team_id, _ in _team_order(cache_root)}
    validate_identity(identity, team_ids)
    aid = asset_id(identity)
    approved = approved_identities.get(aid)
    if not approved or approved.get("identity") != identity:
        raise ValueError("Transport identity is absent from the Phase 2C allowlist")
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    session.mount("https://", HTTPAdapter(max_retries=0))
    started = time.perf_counter()
    try:
        response = session.get(
            PAIR_URL if identity["endpoint"] == PAIR_ENDPOINT else PLAYER_URL,
            params=request_parameters(identity, team_ids), timeout=timeout_seconds,
            allow_redirects=False,
        )
        return TransportResult(response.status_code, response.content, time.perf_counter() - started,
                               dict(response.headers))
    except requests.Timeout as exc:
        raise TransportError("timeout", str(exc)) from exc
    except requests.exceptions.SSLError as exc:
        raise TransportError("tls_failure", str(exc)) from exc
    except requests.ConnectionError as exc:
        raise TransportError("transient_connection_failure", str(exc)) from exc
    except requests.RequestException as exc:
        raise TransportError("request_failure", str(exc)) from exc
    finally:
        session.close()


def _validate_returned_identity(payload: Mapping[str, Any], identity: Mapping[str, Any]) -> None:
    returned = payload.get("parameters")
    if not isinstance(returned, Mapping):
        raise ValueError("Response lacks request-parameter identity")
    params = identity["parameters"]
    expected: dict[str, Any] = {"Season": params["season"], "SeasonType": SEASON_TYPE,
                                "MeasureType": params["measure_type"]}
    if identity["endpoint"] == PAIR_ENDPOINT:
        expected.update({"TeamID": int(params["team_id"]), "GroupQuantity": int(GROUP_QUANTITY)})
        if returned.get("LeagueID") not in (None, LEAGUE_ID, 0, "0"):
            raise ValueError("Response league identity mismatch")
    else:
        expected.update({"LeagueID": LEAGUE_ID, "PerMode": params["per_mode"]})
    for key, value in expected.items():
        if str(returned.get(key)) != str(value):
            raise ValueError(f"Response identity mismatch for {key}: {returned.get(key)!r}")


def strict_player_source_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = []
    invalid = []
    for index, row in enumerate(rows):
        try:
            ids.append(strict_player_id(row.get("PLAYER_ID")))
        except ValueError as exc:
            invalid.append({"row_index": index, "value": row.get("PLAYER_ID"), "reason": str(exc)})
    counts = Counter(ids)
    return {"rows": len(rows), "valid_ids": len(ids), "unique_ids": len(counts),
            "invalid_ids": invalid, "duplicate_ids": {key: count for key, count in counts.items() if count > 1},
            "player_ids": sorted(counts, key=int)}


def validate_response(payload: Mapping[str, Any], identity: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    team_ids = set(manifest["team_directory"])
    validate_identity(identity, team_ids); _validate_returned_identity(payload, identity)
    if identity["endpoint"] == PAIR_ENDPOINT:
        validation = validate_payload_structure(payload)
        if set(validation["row_counts"]) != {"Overall", "Lineups"} or validation["row_counts"]["Overall"] != 1:
            raise ValueError("Pair response requires exactly one Overall and one nonempty Lineups result set")
        if validation["row_counts"]["Lineups"] <= 0:
            raise ValueError("Pair Lineups result set is empty")
        overall = result_set_rows(extract_result_set(dict(payload), "Overall"))
        if str(overall[0].get("TEAM_ID")) != identity["parameters"]["team_id"]:
            raise ValueError("Pair response team context mismatch")
        expected = manifest["approved_pair_schema_contract"][identity["parameters"]["measure_type"]]
    else:
        sets = payload.get("resultSets")
        if not isinstance(sets, list) or len(sets) != 1 or sets[0].get("name") != "LeagueDashPlayerStats":
            raise ValueError("Player response requires one LeagueDashPlayerStats result set")
        rows = result_set_rows(sets[0])
        validation = {"fingerprints": [schema_fingerprint(sets[0])],
                      "row_counts": {"LeagueDashPlayerStats": len(rows)}}
        audit = strict_player_source_audit(rows)
        if audit["invalid_ids"] or audit["duplicate_ids"]:
            raise ValueError("Player response contains invalid or duplicate canonical IDs")
        expected = manifest["approved_player_schema_contract"]
    actual = {item["name"]: item for item in validation["fingerprints"]}
    drift = {}
    for name in set(expected) | set(actual):
        drift[name] = ({"classification": "result_set_name_changed", "accepted": False}
                       if name not in expected or name not in actual
                       else schema_drift_report(expected[name], actual[name]))
    rejected = {name: value["classification"] for name, value in drift.items() if not value["accepted"]}
    if identity["endpoint"] == PAIR_ENDPOINT and not rejected:
        rows = _pair_rows(payload, TARGET_SEASON, identity["parameters"]["team_id"])
        audit = strict_pair_identifier_audit(rows)
        if audit["invalid_rows"] or audit["duplicate_canonical_pairs"]:
            raise ValueError("Pair response contains invalid or duplicate canonical IDs")
    return {**validation, "drift_results": drift,
            "drift_classification": "identical" if not rejected else "non_identical",
            "accepted": not rejected, "rejected": rejected,
            "strict_identifier_audit": audit}


def verify_asset(item: Mapping[str, Any], store: Phase2CStore, manifest: Mapping[str, Any]) -> dict[str, Any]:
    validate_identity(item["identity"], set(manifest["team_directory"]))
    if item["asset_id"] != asset_id(item["identity"]):
        raise ValueError("Asset identity hash mismatch")
    cache = item["cache"]; path = store.cache_root / cache["relative_path"]
    body = path.read_bytes()
    if len(body) != cache["cache_file_bytes"] or raw_body_hash(body) != cache["raw_body_hash"]:
        raise ValueError("Raw cache byte/hash mismatch")
    payload = json.loads(body.decode("utf-8"))
    if canonical_json_hash(payload) != cache["canonical_json_hash"]:
        raise ValueError("Canonical JSON hash mismatch")
    validation = validate_response(payload, item["identity"], manifest)
    if not validation["accepted"]:
        raise ValueError(f"Schema mismatch: {validation['rejected']}")
    metadata = read_json(store.cache_root / cache["metadata_relative_path"])
    if (metadata.get("asset_id") != item["asset_id"] or metadata.get("identity") != item["identity"]
            or metadata.get("cache") != cache or metadata.get("source_event") != item.get("source_event")):
        raise ValueError("Cache metadata/provenance mismatch")
    return {"payload": payload, "cache_file_bytes": len(body),
            "raw_body_hash": cache["raw_body_hash"], "canonical_json_hash": cache["canonical_json_hash"],
            **validation}


def _audit_team(team_id: str, base_payload: Mapping[str, Any], advanced_payload: Mapping[str, Any]) -> dict[str, Any]:
    base = _pair_rows(base_payload, TARGET_SEASON, team_id)
    advanced = _pair_rows(advanced_payload, TARGET_SEASON, team_id)
    base_summary = summarize_pair_rows(base); advanced_summary = summarize_pair_rows(advanced)
    base_strict = strict_pair_identifier_audit(base); advanced_strict = strict_pair_identifier_audit(advanced)
    reconciliation = join_pair_measures(base, advanced)
    standard_failures = _positive_target_failures(advanced)
    estimated_failures = []
    for row in advanced:
        poss = _numeric(row.get("POSS"))
        if poss is None or poss < 0:
            estimated_failures.append({"pair_key": row.get("pair_key"), "reason": "invalid_possessions"})
            continue
        if poss == 0:
            continue
        values = [_numeric(row.get(field)) for field in ("E_OFF_RATING", "E_DEF_RATING", "E_NET_RATING")]
        if any(value is None for value in values) or abs(values[2] - (values[0] - values[1])) > .1000000001:
            estimated_failures.append({"pair_key": row.get("pair_key"), "reason": "estimated_net_identity_failure"})
    clean = (
        base_summary["same_player_or_malformed_rows"] == 0
        and advanced_summary["same_player_or_malformed_rows"] == 0
        and base_strict["invalid_rows"] == advanced_strict["invalid_rows"] == 0
        and base_strict["duplicate_canonical_pairs"] == advanced_strict["duplicate_canonical_pairs"] == 0
        and reconciliation["one_to_one"] and reconciliation["base_only_pairs"] == 0
        and reconciliation["advanced_only_pairs"] == 0 and not standard_failures and not estimated_failures
    )
    return {"team_id": team_id, "base_identity": base_summary, "advanced_identity": advanced_summary,
            "strict_base_identity": base_strict, "strict_advanced_identity": advanced_strict,
            "reconciliation": reconciliation, "positive_possession_target_failures": standard_failures,
            "estimated_identity_failures": estimated_failures, "clean_release_gate": clean}


def _payloads(manifest: Mapping[str, Any], store: Phase2CStore) -> dict[str, dict[str, Mapping[str, Any]]]:
    result: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for item in manifest["assets"]:
        if item["status"] != "verified":
            continue
        replay = verify_asset(item, store, manifest)
        params = item["identity"]["parameters"]
        key = params.get("team_id", "players")
        measure = params.get("measure_type") if item["identity"]["endpoint"] == PAIR_ENDPOINT else params["per_mode"]
        result[key][measure] = replay["payload"]
    return result


def _canary_audit(manifest: Mapping[str, Any], store: Phase2CStore) -> dict[str, Any]:
    payloads = _payloads(manifest, store)
    player_sets = {}
    for mode in PLAYER_PER_MODES:
        rows = _player_rows(payloads["players"][mode]); audit = strict_player_source_audit(rows)
        if audit["invalid_ids"] or audit["duplicate_ids"]:
            raise ValueError("Canary prior-player ID audit failed")
        player_sets[mode] = set(audit["player_ids"])
    if player_sets[PLAYER_PER_MODES[0]] != player_sets[PLAYER_PER_MODES[1]]:
        raise ValueError("Canary prior-player ID sets differ")
    prior = player_rows_by_id(attach_prior_context(_player_rows(payloads["players"]["Per100Possessions"]), PRIOR_FEATURE_SEASON))
    rows = []
    teams = {}
    for team_id in CANARY_TEAM_IDS:
        audit = _audit_team(team_id, payloads[team_id]["Base"], payloads[team_id]["Advanced"])
        if not audit["clean_release_gate"]:
            raise ValueError(f"Canary team audit failed: {team_id}")
        base = _pair_rows(payloads[team_id]["Base"], TARGET_SEASON, team_id)
        advanced = _pair_rows(payloads[team_id]["Advanced"], TARGET_SEASON, team_id)
        poss = {(row["team_id"], row["pair_key"]): row["POSS"] for row in advanced}
        for row in base:
            row = dict(row); row["POSS"] = poss[(team_id, row["pair_key"])]; rows.append(row)
        teams[team_id] = {"matched": audit["reconciliation"]["matched_pairs"]}
    joined = join_pairs_to_prior_players(rows, prior, TARGET_SEASON, PRIOR_FEATURE_SEASON)
    result = {"status": "passed", "assets_verified": 12, "teams": teams,
              "player_rows": len(player_sets[PLAYER_PER_MODES[0]]),
              "coverage": _coverage_detail(joined)}
    result["deterministic_sha256"] = canonical_json_hash(result)
    return result


def _player_source_gate(manifest: Mapping[str, Any], store: Phase2CStore) -> dict[str, Any]:
    payloads = _payloads(manifest, store).get("players", {})
    if set(payloads) != set(PLAYER_PER_MODES):
        raise ValueError("Both prior-player modes must verify")
    audits = {}
    id_sets = {}
    minute_summaries = {}
    for mode in PLAYER_PER_MODES:
        rows = _player_rows(payloads[mode])
        audit = strict_player_source_audit(rows)
        if audit["invalid_ids"] or audit["duplicate_ids"]:
            raise ValueError(f"Invalid {mode} player IDs")
        minutes = [_numeric(row.get("MIN")) for row in rows]
        if any(value is None or value < 0 for value in minutes):
            raise ValueError(f"{mode} MIN must be numeric and nonnegative")
        audits[mode] = {key: value for key, value in audit.items() if key != "player_ids"}
        id_sets[mode] = set(audit["player_ids"])
        minute_summaries[mode] = _quantiles([float(value) for value in minutes])
    if id_sets[PLAYER_PER_MODES[0]] != id_sets[PLAYER_PER_MODES[1]]:
        raise ValueError("Prior-player Per100Possessions and Totals ID sets differ")
    result = {"status": "passed", "exact_id_set_match": True, "audits": audits,
              "minute_summaries": minute_summaries}
    result["deterministic_sha256"] = canonical_json_hash(result)
    return result


def _json_normalized(value: Any) -> Any:
    """Return the exact JSON-persisted representation used for gate comparison."""
    return json.loads(json.dumps(value, sort_keys=True))


def _persist_gate_stop(
    manifest: dict[str, Any],
    store: Phase2CStore,
    *,
    category: str,
    detail: str,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    stop = {"category": category, "detail": detail, **dict(context or {})}
    manifest["integrity_stop"] = stop
    store.save(manifest)
    return {"ok": False, "stop_category": category, "stop": stop}


def reconcile_verified_prefix_gates(
    manifest: dict[str, Any], store: Phase2CStore
) -> dict[str, Any]:
    """Recreate and verify every gate implied by the persisted verified prefix.

    This function has no transport surface.  It must run before the default
    transport is selected and after every newly verified asset.
    """
    if manifest.get("integrity_stop"):
        return {
            "ok": False,
            "stop_category": "persisted_integrity_stop",
            "stop": deepcopy(manifest["integrity_stop"]),
        }
    if any(item["status"] == "attempting" for item in manifest["assets"]):
        return {"ok": False, "stop_category": "uncertain_interrupted_attempt"}

    seen_nonverified = False
    for item in manifest["assets"]:
        if item["status"] != "verified":
            seen_nonverified = True
        elif seen_nonverified:
            return _persist_gate_stop(
                manifest,
                store,
                category="verified_prefix_order_failure",
                detail="A verified asset appears after a nonverified asset",
                context={"asset_id": item["asset_id"], "ordinal": item["ordinal"]},
            )

    changed = False
    if all(item["status"] == "verified" for item in manifest["assets"][:2]):
        try:
            derived_player_gate = _json_normalized(_player_source_gate(manifest, store))
        except Exception as exc:
            return _persist_gate_stop(
                manifest,
                store,
                category="player_source_integrity_failure",
                detail=str(exc),
            )
        persisted_player_gate = manifest.get("player_source_gate")
        if persisted_player_gate is None:
            manifest["player_source_gate"] = derived_player_gate
            changed = True
        elif persisted_player_gate != derived_player_gate:
            return _persist_gate_stop(
                manifest,
                store,
                category="player_source_gate_mismatch",
                detail="Persisted player-source gate differs from verified-cache derivation",
                context={"persisted": persisted_player_gate, "derived": derived_player_gate},
            )

    persisted_team_gates = manifest.get("team_gate_results")
    if persisted_team_gates is None:
        persisted_team_gates = {}
        manifest["team_gate_results"] = persisted_team_gates
        changed = True
    if not isinstance(persisted_team_gates, dict):
        return _persist_gate_stop(
            manifest,
            store,
            category="team_gate_state_invalid",
            detail="Persisted team-gate state must be an object",
        )
    by_team: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for item in manifest["assets"]:
        if item["identity"]["endpoint"] != PAIR_ENDPOINT:
            continue
        params = item["identity"]["parameters"]
        by_team[params["team_id"]][params["measure_type"]] = item
    for team_id, measures in by_team.items():
        base = measures["Base"]
        advanced = measures["Advanced"]
        if advanced["status"] == "verified" and base["status"] != "verified":
            return _persist_gate_stop(
                manifest,
                store,
                category="team_verified_order_failure",
                detail="Advanced is verified without its Base asset",
                context={"team_id": team_id},
            )
        if base["status"] != "verified" or advanced["status"] != "verified":
            continue
        try:
            pair_payloads = _payloads(manifest, store)[team_id]
            audit = _audit_team(team_id, pair_payloads["Base"], pair_payloads["Advanced"])
        except Exception as exc:
            return _persist_gate_stop(
                manifest,
                store,
                category="team_integrity_failure",
                detail=str(exc),
                context={"team_id": team_id},
            )
        if not audit["clean_release_gate"]:
            return _persist_gate_stop(
                manifest,
                store,
                category="team_integrity_failure",
                detail="Cache-derived team gate failed",
                context={"team_id": team_id, "audit": _json_normalized(audit)},
            )
        normalized_audit = _json_normalized(audit)
        derived_team_gate = {
            "status": "passed",
            "team_id": team_id,
            "audit": normalized_audit,
            "deterministic_sha256": canonical_json_hash(normalized_audit),
        }
        persisted_team_gate = persisted_team_gates.get(team_id)
        if persisted_team_gate is None:
            persisted_team_gates[team_id] = derived_team_gate
            changed = True
        elif persisted_team_gate != derived_team_gate:
            return _persist_gate_stop(
                manifest,
                store,
                category="team_gate_mismatch",
                detail="Persisted team gate differs from verified-cache derivation",
                context={"team_id": team_id, "persisted": persisted_team_gate,
                         "derived": derived_team_gate},
            )

    if all(item["status"] == "verified" for item in manifest["assets"][:12]):
        try:
            derived_canary = _json_normalized(_canary_audit(manifest, store))
        except Exception as exc:
            return _persist_gate_stop(
                manifest,
                store,
                category="canary_failure",
                detail=str(exc),
            )
        persisted_canary = manifest.get("canary_result")
        if persisted_canary is None:
            manifest["canary_result"] = derived_canary
            changed = True
        elif persisted_canary != derived_canary:
            return _persist_gate_stop(
                manifest,
                store,
                category="canary_gate_mismatch",
                detail="Persisted canary differs from verified-cache derivation",
                context={"persisted": persisted_canary, "derived": derived_canary},
            )
    if changed:
        store.save(manifest)
    return {
        "ok": True,
        "player_source_gate": manifest.get("player_source_gate"),
        "team_gates": len(manifest.get("team_gate_results", {})),
        "canary_result": manifest.get("canary_result"),
    }


def _failure_evidence_path(
    store: Phase2CStore,
    item: Mapping[str, Any],
    attempt_number: int,
) -> Path:
    return (
        store.cache_root
        / "phase2c/failure_evidence"
        / f"{_safe_id(item['asset_id'])}.attempt-{attempt_number}.body"
    )


def _failure_evidence_collision_path(
    store: Phase2CStore,
    item: Mapping[str, Any],
    attempt_number: int,
    body_sha256: str,
) -> Path:
    identity_token = canonical_json_hash(item["identity"])[:24]
    return (
        store.cache_root
        / "phase2c/failure_evidence"
        / f"collision-{identity_token}-a{attempt_number}-{body_sha256}.body"
    )


def _relative_evidence_path(store: Phase2CStore, path: Path) -> str:
    return str(path.relative_to(store.cache_root)).replace("\\", "/")


def _preserve_unaccepted_response(
    store: Phase2CStore,
    item: Mapping[str, Any],
    event: dict[str, Any],
    body: bytes,
    attempt_number: int,
) -> dict[str, Any]:
    """Create and link immutable evidence, or describe terminal corruption."""
    path = _failure_evidence_path(store, item, attempt_number)
    body_sha256 = raw_body_hash(body)
    collision = False
    conflicting_path: Path | None = None
    try:
        atomic_write_bytes_new(path, body)
    except FileExistsError:
        # The normal path passed preflight but appeared before the create-once
        # write. Retain it and use the content-addressed path during normal
        # operation; contradictory content there is a terminal integrity stop.
        collision = True
        conflicting_path = path
        path = _failure_evidence_collision_path(
            store, item, attempt_number, body_sha256
        )
        try:
            atomic_write_bytes_new(path, body)
        except FileExistsError:
            existing_body = path.read_bytes()
            if existing_body != body:
                intended_path = _relative_evidence_path(store, path)
                conflicting_file_sha256 = raw_body_hash(existing_body)
                event.update({
                    "evidence_persistence_status": "content_addressed_contradiction",
                    "returned_body_expected_sha256": body_sha256,
                    "returned_body_bytes": len(body),
                    "intended_preserved_response_path": intended_path,
                    "conflicting_file_actual_sha256": conflicting_file_sha256,
                })
                return {
                    "collision": True,
                    "terminal_inconsistency": True,
                    "preserved_path": None,
                    "conflicting_path": _relative_evidence_path(
                        store, conflicting_path
                    ),
                    "intended_path": intended_path,
                    "returned_body_sha256": body_sha256,
                    "returned_body_bytes": len(body),
                    "conflicting_file_sha256": conflicting_file_sha256,
                }
    event.update({
        "preserved_response_path": _relative_evidence_path(store, path),
        "preserved_response_bytes": len(body),
        "preserved_response_raw_sha256": body_sha256,
    })
    return {
        "collision": collision,
        "terminal_inconsistency": False,
        "preserved_path": _relative_evidence_path(store, path),
        "conflicting_path": (
            _relative_evidence_path(store, conflicting_path)
            if conflicting_path is not None
            else None
        ),
    }


def _retry_after_seconds(headers: Mapping[str, str] | None) -> float:
    if not headers:
        return 30.0
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if not raw:
        return 30.0
    try:
        return max(30.0, float(raw))
    except ValueError:
        try:
            delay = (parsedate_to_datetime(raw) - __import__("datetime").datetime.now(__import__("datetime").timezone.utc)).total_seconds()
            return max(30.0, delay)
        except Exception:
            return 30.0


def _counts(manifest: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    statuses = Counter(item["status"] for item in manifest["assets"])
    histories = [event for item in manifest["assets"] for event in item["attempt_history"]]
    firsts = sum(bool(item["attempt_history"]) for item in manifest["assets"])
    return {"planned_assets": 62, "verified": statuses["verified"], "failed": statuses["failed"],
            "retryable": statuses["retryable"], "quarantined": statuses["quarantined"],
            "unattempted": statuses["planned"], "attempts": len(histories), "first_attempts": firsts,
            "retry_attempts": len(histories) - firsts,
            "actual_http_responses": sum("http_status" in event for event in histories), **extra}


def _canary_certification(
    persisted: Mapping[str, Any] | None, recomputed: Mapping[str, Any]
) -> dict[str, Any]:
    mismatch_fields = []
    if persisted is None:
        mismatch_fields.append("missing_persisted_canary")
    else:
        for field in ("status", "assets_verified", "player_rows", "teams", "coverage",
                      "deterministic_sha256"):
            if persisted.get(field) != recomputed.get(field):
                mismatch_fields.append(field)
        if persisted != recomputed and not mismatch_fields:
            mismatch_fields.append("full_result")
    return {
        "status": "certified" if not mismatch_fields else "mismatch",
        "exact_agreement": not mismatch_fields,
        "mismatch_fields": mismatch_fields,
        "persisted_sha256": (persisted or {}).get("deterministic_sha256"),
        "recomputed_sha256": recomputed.get("deterministic_sha256"),
    }


def run_acquisition(store: Phase2CStore, *, live_acquisition: bool,
                    timeout_seconds: int = TIMEOUT_SECONDS, delay_seconds: float = MIN_DELAY_SECONDS,
                    transport: Callable[[Mapping[str, Any], int], TransportResult] | None = None,
                    sleep_fn: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    if not live_acquisition:
        raise ValueError("Live acquisition requires explicit authorization")
    if timeout_seconds != 30 or delay_seconds < 1:
        raise ValueError("Phase 2C requires timeout=30 and delay>=1 second")
    manifest = store.load()
    if manifest.get("integrity_stop"):
        return _counts(manifest, completed=False, stop_category="persisted_integrity_stop",
                       stop=deepcopy(manifest["integrity_stop"]))
    gate_reconciliation = reconcile_verified_prefix_gates(manifest, store)
    if not gate_reconciliation["ok"]:
        return _counts(
            manifest,
            completed=False,
            stop_category=gate_reconciliation["stop_category"],
            stop=gate_reconciliation.get("stop"),
        )
    approved = _approved_identities(store)
    attempts = sum(len(item["attempt_history"]) for item in manifest["assets"])
    retries = sum(max(0, len(item["attempt_history"]) - 1) for item in manifest["assets"])
    for item in manifest["assets"]:
        if item["status"] == "verified":
            try: verify_asset(item, store, manifest)
            except Exception as exc:
                manifest["integrity_stop"] = {"category": "corrupt_verified_cache", "asset_id": item["asset_id"], "detail": str(exc)}
                store.save(manifest); return _counts(manifest, completed=False, stop_category="corrupt_verified_cache")
            continue
        if item["status"] == "attempting":
            return _counts(manifest, completed=False, stop_category="uncertain_interrupted_attempt")
        if item["status"] not in {"planned", "retryable"}:
            return _counts(manifest, completed=False, stop_category=f"existing_{item['status']}")
        allowed = approved.get(item["asset_id"])
        if not allowed or allowed["ordinal"] != item["ordinal"] or allowed["identity"] != item["identity"]:
            return _counts(manifest, completed=False, stop_category="allowlist_identity_mismatch")
        next_number = len(item["attempt_history"]) + 1
        if next_number > 2 or attempts >= MAX_ATTEMPTS or (next_number == 2 and retries >= MAX_RETRIES):
            return _counts(manifest, completed=False, stop_category="attempt_budget_exhausted")
        if next_number == 1 and sum(bool(value["attempt_history"]) for value in manifest["assets"]) >= MAX_FIRST_ATTEMPTS:
            return _counts(manifest, completed=False, stop_category="first_attempt_budget_exhausted")
        cache_path = store.cache_root / item["cache"]["relative_path"]
        metadata_path = store.cache_root / item["cache"]["metadata_relative_path"]
        if cache_path.exists() or metadata_path.exists():
            return _counts(manifest, completed=False, stop_category="unverified_cache_collision")
        evidence_path = _failure_evidence_path(store, item, next_number)
        if evidence_path.exists():
            relative_path = _relative_evidence_path(store, evidence_path)
            detail = (
                "The next attempt's immutable failure-evidence destination "
                f"already exists: {relative_path}"
            )
            stopped = _persist_gate_stop(
                manifest,
                store,
                category="failure_evidence_preflight_collision",
                detail=detail,
                context={
                    "asset_id": item["asset_id"],
                    "attempt_number": next_number,
                    "conflicting_path": relative_path,
                },
            )
            return _counts(
                manifest,
                completed=False,
                stop_category=stopped["stop_category"],
                stop=stopped["stop"],
            )
        if next_number == 2:
            wait_seconds = float(item["last_error"].get("retry_after_seconds", 30.0))
            sleep_fn(wait_seconds)
            retries += 1
        elif attempts:
            sleep_fn(delay_seconds)
        event = {"attempt_number": next_number, "started_at": store.clock(), "status": "started",
                 "timeout_seconds": timeout_seconds, "request_kind": "phase2c_live"}
        item["attempt_history"].append(event); item["attempt_count"] = next_number
        store.transition(manifest, item, "attempting", "attempt_recorded_before_transport")
        attempts += 1
        response: TransportResult | None = None
        try:
            selected_transport = transport
            if selected_transport is None:
                selected_transport = lambda identity, timeout: direct_transport(
                    identity,
                    timeout,
                    cache_root=store.cache_root,
                    approved_identities=approved,
                )
            response = selected_transport(item["identity"], timeout_seconds)
            event.update({"latency_seconds": response.elapsed_seconds, "http_status": response.status_code,
                          "response_body_bytes": len(response.body)})
            if response.status_code != 200:
                if response.status_code in RETRY_HTTP_STATUSES:
                    raise TransportError("retryable_http", f"HTTP {response.status_code}")
                raise TransportError("nonretryable_http", f"HTTP {response.status_code}")
            try: payload = json.loads(response.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise TransportError("invalid_json", str(exc)) from exc
            try: validation = validate_response(payload, item["identity"], manifest)
            except ValueError as exc: raise TransportError("validation_failure", str(exc)) from exc
            item["schema_verification"] = {"status": "accepted" if validation["accepted"] else "rejected", **validation}
            if not validation["accepted"]:
                raise TransportError("schema_quarantine", json.dumps(validation["rejected"], sort_keys=True))
            atomic_write_bytes_new(cache_path, response.body)
            item["cache"].update({"cache_file_bytes": cache_path.stat().st_size,
                                  "raw_body_hash": raw_body_hash(response.body),
                                  "canonical_json_hash": canonical_json_hash(payload)})
            item["source_event"] = {"provenance_format": "phase2c-live-v1", "acquired_at": store.clock(),
                                    "http_status": 200, "latency_seconds": response.elapsed_seconds,
                                    "response_body_bytes": len(response.body),
                                    "raw_body_hash": item["cache"]["raw_body_hash"]}
            atomic_write_json(metadata_path, {"asset_id": item["asset_id"], "identity": item["identity"],
                                              "source_event": item["source_event"], "cache": item["cache"],
                                              "schema_verification": item["schema_verification"]})
            replay = verify_asset(item, store, manifest)
            event.update({"status": "verified", "error_category": None, "error_detail": None,
                          "canonical_json_hash": replay["canonical_json_hash"], "row_counts": replay["row_counts"]})
            item["last_error"] = None
            store.transition(manifest, item, "verified", "cache_replay_verified", replay["canonical_json_hash"])
            gate_reconciliation = reconcile_verified_prefix_gates(manifest, store)
            if not gate_reconciliation["ok"]:
                return _counts(
                    manifest,
                    completed=False,
                    stop_category=gate_reconciliation["stop_category"],
                    stop=gate_reconciliation.get("stop"),
                )
        except TransportError as exc:
            retryable = exc.category in RETRY_CATEGORIES or exc.category == "retryable_http"
            retry_after = _retry_after_seconds(response.headers if response is not None else None)
            if response is not None:
                try:
                    preservation = _preserve_unaccepted_response(
                        store, item, event, response.body, next_number
                    )
                except Exception as preserve_exc:
                    detail = f"{type(preserve_exc).__name__}: {preserve_exc}"
                    event.update({
                        "status": "failed",
                        "error_category": "failure_evidence_collision",
                        "error_detail": detail,
                    })
                    item["last_error"] = {
                        "category": "failure_evidence_collision",
                        "detail": detail,
                    }
                    store.transition(
                        manifest,
                        item,
                        "failed",
                        "failure_evidence_collision",
                        detail,
                    )
                    stopped = _persist_gate_stop(
                        manifest,
                        store,
                        category="failure_evidence_collision",
                        detail=detail,
                        context={
                            "asset_id": item["asset_id"],
                            "attempt_number": next_number,
                        },
                    )
                    return _counts(
                        manifest,
                        completed=False,
                        stop_category="failure_evidence_collision",
                        stop=stopped["stop"],
                    )
                if preservation["terminal_inconsistency"]:
                    detail = (
                        "Returned response bytes could not be persisted because "
                        "existing evidence contradicted its content-addressed filename"
                    )
                    event.update({
                        "status": "failed",
                        "error_category": "failure_evidence_content_address_mismatch",
                        "error_detail": detail,
                    })
                    item["last_error"] = {
                        "category": "failure_evidence_content_address_mismatch",
                        "detail": detail,
                    }
                    store.transition(
                        manifest,
                        item,
                        "failed",
                        "failure_evidence_content_address_mismatch",
                        detail,
                    )
                    stopped = _persist_gate_stop(
                        manifest,
                        store,
                        category="failure_evidence_content_address_mismatch",
                        detail=detail,
                        context={
                            "asset_id": item["asset_id"],
                            "attempt_number": next_number,
                            "conflicting_path": preservation["conflicting_path"],
                            "returned_body_expected_sha256": preservation["returned_body_sha256"],
                            "returned_body_bytes": preservation["returned_body_bytes"],
                            "intended_preserved_response_path": preservation["intended_path"],
                            "conflicting_file_actual_sha256": preservation["conflicting_file_sha256"],
                        },
                    )
                    return _counts(
                        manifest,
                        completed=False,
                        stop_category=stopped["stop_category"],
                        stop=stopped["stop"],
                    )
                if preservation["collision"]:
                    detail = (
                        "The normal failure-evidence path appeared after preflight; "
                        "the returned body was preserved at the hash-derived collision path"
                    )
                    event.update({
                        "status": "failed",
                        "error_category": "failure_evidence_postcheck_collision",
                        "error_detail": detail,
                    })
                    item["last_error"] = {
                        "category": "failure_evidence_postcheck_collision",
                        "detail": detail,
                    }
                    store.transition(
                        manifest,
                        item,
                        "failed",
                        "failure_evidence_postcheck_collision",
                        detail,
                    )
                    stopped = _persist_gate_stop(
                        manifest,
                        store,
                        category="failure_evidence_postcheck_collision",
                        detail=detail,
                        context={
                            "asset_id": item["asset_id"],
                            "attempt_number": next_number,
                            "conflicting_path": preservation["conflicting_path"],
                            "preserved_response_path": preservation["preserved_path"],
                        },
                    )
                    return _counts(
                        manifest,
                        completed=False,
                        stop_category=stopped["stop_category"],
                        stop=stopped["stop"],
                    )
            event.update({"status": "retryable" if retryable else "failed", "error_category": exc.category,
                          "error_detail": exc.detail})
            item["last_error"] = {"category": exc.category, "detail": exc.detail,
                                  "retry_after_seconds": retry_after if retryable else None}
            if retryable and next_number == 1 and retries < MAX_RETRIES:
                store.transition(manifest, item, "retryable", exc.category, exc.detail)
                return run_acquisition(
                    store,
                    live_acquisition=True,
                    timeout_seconds=timeout_seconds,
                    delay_seconds=delay_seconds,
                    transport=transport,
                    sleep_fn=sleep_fn,
                )
            store.transition(manifest, item, "failed", exc.category, exc.detail)
            return _counts(manifest, completed=False, stop_category=exc.category, stop_detail=exc.detail)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            event.update({"status": "failed", "error_category": "unexpected_exception", "error_detail": detail})
            item["last_error"] = {"category": "unexpected_exception", "detail": detail}
            store.transition(manifest, item, "failed", "unexpected_exception", detail)
            return _counts(manifest, completed=False, stop_category="unexpected_exception", stop_detail=detail)
    return _counts(manifest, completed=True, stop_category=None)


def analyze_release(store: Phase2CStore) -> dict[str, Any]:
    """Deterministically replay and audit a complete Phase 2C request set."""
    manifest = store.load()
    if manifest.get("integrity_stop") or any(item["status"] != "verified" for item in manifest["assets"]):
        raise ValueError("All 62 Phase 2C assets must verify before analysis")
    recomputed_canary = _json_normalized(_canary_audit(manifest, store))
    persisted_canary = manifest.get("canary_result")
    canary_certification = _canary_certification(persisted_canary, recomputed_canary)
    payloads = _payloads(manifest, store)
    player_audits = {}; player_rows = {}
    for mode in PLAYER_PER_MODES:
        rows = _player_rows(payloads["players"][mode]); player_rows[mode] = rows
        audit = strict_player_source_audit(rows); player_audits[mode] = {key: value for key, value in audit.items() if key != "player_ids"}
    per100_ids = {strict_player_id(row["PLAYER_ID"]) for row in player_rows["Per100Possessions"]}
    totals_ids = {strict_player_id(row["PLAYER_ID"]) for row in player_rows["Totals"]}
    if per100_ids != totals_ids:
        raise ValueError("Prior-player Per100 and Totals ID sets differ")
    prior = player_rows_by_id(attach_prior_context(player_rows["Per100Possessions"], PRIOR_FEATURE_SEASON))
    if any(len(value) != 1 for value in prior.values()):
        raise ValueError("Prior-player index is not unique")
    per_team = {}; all_base = []; all_advanced = []; asset_ledger = []
    for item in manifest["assets"]:
        replay = verify_asset(item, store, manifest)
        asset_ledger.append({"ordinal": item["ordinal"], "asset_id": item["asset_id"],
                             "endpoint": item["identity"]["endpoint"], "identity": item["identity"],
                             "raw_body_hash": replay["raw_body_hash"], "canonical_json_hash": replay["canonical_json_hash"],
                             "cache_file_bytes": replay["cache_file_bytes"], "row_counts": replay["row_counts"],
                             "schema_fingerprints": replay["fingerprints"],
                             "latency_seconds": (item.get("source_event") or {}).get("latency_seconds")})
    for team_id in sorted(manifest["team_directory"], key=int):
        base = _pair_rows(payloads[team_id]["Base"], TARGET_SEASON, team_id)
        advanced = _pair_rows(payloads[team_id]["Advanced"], TARGET_SEASON, team_id)
        audit = _audit_team(team_id, payloads[team_id]["Base"], payloads[team_id]["Advanced"])
        per_team[team_id] = {"team_name": manifest["team_directory"][team_id]["team_name"], **audit,
                             "target_audit": summarize_advanced_targets(advanced),
                             "target_ineligible_rows": identify_zero_or_missing_possession_rows(advanced, base),
                             "base_identifier_detail": _pair_identifier_detail(base),
                             "advanced_identifier_detail": _pair_identifier_detail(advanced),
                             "base_population": _boundary(base, "Base"), "advanced_population": _boundary(advanced, "Advanced"),
                             "base_minutes": _quantiles([x for row in base if (x := _numeric(row.get("MIN"))) is not None]),
                             "possessions": _quantiles([x for row in advanced if (x := _numeric(row.get("POSS"))) is not None]),
                             "extreme_net_rating_by_exposure": _extreme_rating_summary(advanced)}
        if not audit["clean_release_gate"]: raise ValueError(f"Team audit failed: {team_id}")
        all_base.extend(base); all_advanced.extend(advanced)
    advanced_lookup = {(row["team_id"], row["pair_key"]): row for row in all_advanced}
    join_input = []
    for row in all_base:
        value = dict(row); value["POSS"] = advanced_lookup[(row["team_id"], row["pair_key"])]["POSS"]
        join_input.append(value)
    joined = join_pairs_to_prior_players(join_input, prior, TARGET_SEASON, PRIOR_FEATURE_SEASON)
    coverage_by_team = {}
    for team_id in sorted(manifest["team_directory"], key=int):
        rows = [row for row in join_input if row["team_id"] == team_id]
        team_joined = join_pairs_to_prior_players(rows, prior, TARGET_SEASON, PRIOR_FEATURE_SEASON)
        coverage_by_team[team_id] = {"players": summarize_player_level_coverage(rows, prior),
                                     "pairs": summarize_pair_level_coverage(team_joined),
                                     "exposure": summarize_exposure_weighted_coverage(team_joined),
                                     "detail": _coverage_detail(team_joined), "thresholds": _threshold_coverage(team_joined)}
    combined_coverage = {"players": summarize_player_level_coverage(join_input, prior),
                         "pairs": summarize_pair_level_coverage(joined),
                         "exposure": summarize_exposure_weighted_coverage(joined),
                         "detail": _coverage_detail(joined), "thresholds": _threshold_coverage(joined)}
    missing = []
    for player_id in combined_coverage["players"]["missing_player_ids"]:
        affected = [row for row in join_input if player_id in row["pair_key"]]
        names = set()
        for row in affected:
            raw_ids = [token for token in str(row.get("GROUP_ID", "")).strip("-").split("-") if token]
            raw_names = [part.strip() for part in str(row.get("GROUP_NAME", "")).replace(" – ", " - ").split(" - ")]
            names.update(name for pid, name in zip(raw_ids, raw_names) if pid == player_id)
        missing.append({"player_id": player_id, "observed_names": sorted(names),
                        "teams": sorted({row["team_id"] for row in affected}, key=int),
                        "affected_pair_observations": len(affected),
                        "summed_base_minutes": sum(_numeric(row.get("MIN")) or 0 for row in affected),
                        "summed_pair_possessions": sum(_numeric(row.get("POSS")) or 0 for row in affected),
                        "reason": "no_2021-22_source_record"})
    totals_minutes = [_numeric(row.get("MIN")) for row in player_rows["Totals"]]
    per100_minutes = [_numeric(row.get("MIN")) for row in player_rows["Per100Possessions"]]
    totals_valid = [value for value in totals_minutes if value is not None]
    per100_valid = [value for value in per100_minutes if value is not None]
    totals_semantics = {"classification": "consistent_with_season_total_minutes"
                        if totals_valid and max(totals_valid) > 2000 and max(per100_valid or [0]) < 100 else "unresolved",
                        "totals_min": _quantiles(totals_valid), "per100_min": _quantiles(per100_valid),
                        "top_totals": sorted([{"player_id": str(row["PLAYER_ID"]), "player_name": row.get("PLAYER_NAME"),
                                               "MIN": _numeric(row.get("MIN"))} for row in player_rows["Totals"]],
                                             key=lambda row: row["MIN"] or -1, reverse=True)[:10]}
    boundary = [team_id for team_id, value in per_team.items()
                if value["base_population"]["classification"] == "boundary_signal_present"
                or value["advanced_population"]["classification"] == "boundary_signal_present"]
    base_keys = {(row["team_id"], row["pair_key"]) for row in all_base}
    advanced_keys = {(row["team_id"], row["pair_key"]) for row in all_advanced}
    player_teams: dict[str, set[str]] = defaultdict(set)
    pair_teams: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in all_base:
        pair_teams[row["pair_key"]].add(row["team_id"])
        for player_id in row["pair_key"]:
            player_teams[player_id].add(row["team_id"])
    total_possessions = sum(_numeric(row.get("POSS")) or 0 for row in all_advanced)
    exposure_thresholds = []
    for threshold in (1, 5, 10, 25, 50, 100, 200, 300):
        retained = [row for row in all_advanced if (_numeric(row.get("POSS")) or -1) >= threshold]
        retained_possessions = sum(_numeric(row.get("POSS")) or 0 for row in retained)
        exposure_thresholds.append({
            "possessions_at_least": threshold,
            "rows": len(retained),
            "row_share": len(retained) / len(all_advanced) if all_advanced else 0.0,
            "summed_pair_possessions": retained_possessions,
            "share_of_summed_pair_possessions": retained_possessions / total_possessions if total_possessions else 0.0,
            "absolute_net_rating_at_least_50": sum(abs(_numeric(row.get("NET_RATING")) or 0) >= 50 for row in retained),
            "absolute_net_rating_at_least_100": sum(abs(_numeric(row.get("NET_RATING")) or 0) >= 100 for row in retained),
        })
    canary_rows = [row for row in join_input if row["team_id"] in CANARY_TEAM_IDS]
    canary_joined = join_pairs_to_prior_players(canary_rows, prior, TARGET_SEASON, PRIOR_FEATURE_SEASON)
    summary = {
        "analysis_version": ANALYSIS_VERSION, "target_season": TARGET_SEASON,
        "prior_feature_season": PRIOR_FEATURE_SEASON, "phase2b_prerequisite": manifest["phase2b_prerequisite"],
        "request_set": {"assets": 62, "player_assets": 2, "pair_assets": 60,
                        "verified": len(asset_ledger), "attempts": sum(len(item["attempt_history"]) for item in manifest["assets"]),
                        "retries": sum(max(0, len(item["attempt_history"]) - 1) for item in manifest["assets"])},
        "asset_ledger": asset_ledger, "per_team": per_team,
        "combined": {"base_rows": len(all_base), "advanced_rows": len(all_advanced),
                     "matched_observation_keys": len(base_keys & advanced_keys),
                     "base_only_observation_keys": len(base_keys - advanced_keys),
                     "advanced_only_observation_keys": len(advanced_keys - base_keys),
                     "target_eligible_rows": sum((_numeric(row.get("POSS")) or 0) > 0 for row in all_advanced),
                     "target_ineligible_rows": sum((_numeric(row.get("POSS")) or 0) == 0 for row in all_advanced),
                     "malformed_pair_rows": sum(value["strict_base_identity"]["invalid_rows"] + value["strict_advanced_identity"]["invalid_rows"] for value in per_team.values()),
                     "duplicate_pair_keys": sum(value["strict_base_identity"]["duplicate_canonical_pairs"] + value["strict_advanced_identity"]["duplicate_canonical_pairs"] for value in per_team.values()),
                     "standard_rating_identity_failures": sum(len(value["positive_possession_target_failures"]) for value in per_team.values()),
                     "estimated_rating_identity_failures": sum(len(value["estimated_identity_failures"]) for value in per_team.values()),
                     "unique_players": len(player_teams),
                     "globally_unique_unordered_pairs": len(pair_teams),
                     "players_observed_for_multiple_teams": {player_id: sorted(teams, key=int) for player_id, teams in player_teams.items() if len(teams) > 1},
                     "pairs_observed_for_multiple_teams": [{"pair_ids": pair, "teams": sorted(teams, key=int)} for pair, teams in sorted(pair_teams.items()) if len(teams) > 1],
                     "base_minutes": _quantiles([x for row in all_base if (x := _numeric(row.get("MIN"))) is not None]),
                     "possessions": _quantiles([x for row in all_advanced if (x := _numeric(row.get("POSS"))) is not None]),
                     "exposure_thresholds": exposure_thresholds,
                     "boundary_signal_team_ids": boundary, "population_exhaustiveness": "not_proven_exhaustive"},
        "player_sources": {"audits": player_audits, "exact_id_set_match": per100_ids == totals_ids,
                           "totals_min_semantics": totals_semantics},
        "prior_history": {"per_team": coverage_by_team, "combined": combined_coverage,
                          "unmatched_player_ledger": missing, "policy": "descriptive_only_policy_deferred"},
        "canary": {
            "persisted": persisted_canary,
            "recomputed": recomputed_canary,
            "certification": canary_certification,
            "matched_rows": len(canary_rows),
            "coverage": _coverage_detail(canary_joined),
        },
        "release_gates": {"request_set_complete": len(asset_ledger) == 62,
                          "returned_row_integrity": base_keys == advanced_keys,
                          "player_sources_valid": per100_ids == totals_ids,
                          "canary_passed": canary_certification["exact_agreement"],
                          "population_exhaustiveness": "unproven_with_boundary_signals" if boundary else "unproven_no_boundary_signal_observed"},
    }
    summary["primary_classification"] = (
        "2022-23 raw release supported with population caveats; next historical phase ready for separate authorization"
        if all((summary["release_gates"]["request_set_complete"], summary["release_gates"]["returned_row_integrity"],
                summary["release_gates"]["player_sources_valid"], summary["release_gates"]["canary_passed"]))
        else "2022-23 raw request set complete; release audit unresolved"
    )
    deterministic = deepcopy(summary)
    for item in deterministic["asset_ledger"]: item.pop("latency_seconds", None)
    summary["deterministic_analysis_sha256"] = canonical_json_hash(deterministic)
    return summary
