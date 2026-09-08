"""Bounded seven-season coordinator; acquisition remains in the configured engine."""

from __future__ import annotations

import json
import socket
import time
from copy import deepcopy
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from pair_fit_v2 import phase2c_raw_season as engine
from pair_fit_v2 import phase2d_raw_season as phase2d
from pair_fit_v2 import phase2b_raw_season as phase2b

SEASON_PAIRS = (
    ("2020-21", "2019-20"), ("2019-20", "2018-19"),
    ("2018-19", "2017-18"), ("2017-18", "2016-17"),
    ("2016-17", "2015-16"), ("2015-16", "2014-15"),
    ("2014-15", "2013-14"),
)
COMPLETE = "2014-15 through 2023-24 raw training window acquired with population caveats; curation planning ready"
INCOMPLETE = "Phase 2E historical raw acquisition incomplete; expansion blocked"
UNRESOLVED = "Phase 2E request sets complete; combined release audit unresolved"
PHASE2D_HASHES = {
    "analysis": "6b231f4d413d87d8e31bc92fa442ebf9e05587ea8dec9e876dba7cb21fed566f",
    "manifest": "0280fcccd8ddb57cfa1f0c2feeccefb815136a576dc672a28c2141bdb27f5015",
    "ledger": "19549243c95bfb00e7ac30a111cc8486909a078d7941ad4267609bbdc1a89266",
    "plan": "525f872009283d6a7b11ca31d392a8a84ec5f718cdbddb43b4182e91619b9906",
    "allowlist": "8ee84a9dc1d600e68326937595a08da584ca0b1941216a88e741ee612a4fef0a",
}


def _spec(target, prior):
    key = f"phase2e/{target}"
    return engine.HistoricalSeasonSpec(
        release_key=key, phase_label=f"Phase 2E {target}",
        target_season=target, prior_feature_season=prior,
        manifest_version=f"{key}.raw-season.v1", ledger_version=f"{key}.attempt-ledger.v1",
        analysis_version=f"{key}.release-audit.v1", asset_namespace=f"phase2e-{target}-asset",
        manifest_namespace=f"phase2e-{target}-manifest", plan_version=f"{key}.initial-plan.v1",
        allowlist_version=f"{key}.live-allowlist.v1", provenance_format=f"phase2e-{target}-live-v1",
        request_kind=f"phase2e_{target.replace('-', '_')}_live",
        prerequisite_key="phase2c_prerequisite",
        supported_classification=f"{target} raw release supported with population caveats",
        unresolved_classification=f"{target} request set complete; release audit unresolved",
        incomplete_classification=f"{target} raw acquisition incomplete; expansion blocked",
        canary_team_ids=engine.CANARY_TEAM_IDS, canary_asset_count=12,
        maximum_first_attempts=62, maximum_retry_attempts=6, maximum_total_attempts=68,
    )


SPECS = tuple(_spec(*pair) for pair in SEASON_PAIRS)
RECOVERY_ASSET = "phase2e-2020-21-asset:e26463f0f4802e8d69d3849c"
RECOVERY_ANCHOR = {
    "manifest": "5011d70b79eb5efa03470032c899e228b1bd5073d6890ae2326ef2b062f66211",
    "ledger": "6aa32983895bd5502155634bc445775c2a26ccb461137c886ae5adef2368100b",
}


def recovery_path(store):
    return store.cache_root / "phase2e/recovery-cleveland-16"


def _write_once(path, body):
    if path.exists():
        if path.read_bytes() != body:
            raise ValueError(f"Immutable recovery evidence collision: {path.name}")
    else:
        engine.atomic_write_bytes_new(path, body)


def audit_recovery(store):
    """Verify the frozen pre-recovery record without changing historical events."""
    directory = recovery_path(store)
    authorization = engine.read_json(directory / "authorization.json")
    if authorization != {
        "version": "phase2e.cleveland-16-recovery.v1", "asset_id": RECOVERY_ASSET,
        "attempt_number": 2, "original_outcome": "uncertain",
        "original_hashes": RECOVERY_ANCHOR, "budget_extension": 0,
        "authorization": "User explicitly authorized one recovery and original-plan continuation",
    }:
        raise ValueError("Recovery authorization mismatch")
    for name, filename in (("manifest", "manifest.json"), ("ledger", "attempt_ledger.json")):
        if engine._sha256_file(directory / "2020-21" / filename) != RECOVERY_ANCHOR[name]:
            raise ValueError("Recovery anchor changed")
    original = engine.read_json(directory / "2020-21/manifest.json")
    current = store.load()
    if current["assets"][:15] != original["assets"][:15]:
        raise ValueError("Original verified prefix changed")
    if current["assets"][15]["attempt_history"][:1] != original["assets"][15]["attempt_history"]:
        raise ValueError("Original uncertain attempt changed")
    return original


def prepare_recovery(stores):
    """Explicit one-asset authorization; normal engine performs attempt 2 and promotion."""
    validate_stores(stores)
    store = stores[0]
    directory = recovery_path(store)
    with network_blocked():
        for s in stores:
            engine._approved_identities(s)
            s.load()
        manifest = store.load()
        item = manifest["assets"][15]
        if (directory / "authorization.json").exists():
            original = audit_recovery(store)
            if item["status"] != "attempting" or len(item["attempt_history"]) != 1:
                return {"recovery": "already_prepared_or_consumed", "asset_id": RECOVERY_ASSET}
            if manifest != original:
                raise ValueError("Interrupted recovery preparation changed state")
        if {k: evidence_hashes(store)[k] for k in RECOVERY_ANCHOR} != RECOVERY_ANCHOR:
            raise ValueError("Interrupted state differs from authorized recovery anchor")
        if (item["asset_id"] != RECOVERY_ASSET or item["ordinal"] != 16
                or item["status"] != "attempting" or len(item["attempt_history"]) != 1
                or item["attempt_history"][0]["status"] != "started"
                or manifest["integrity_stop"] is not None
                or any(i["status"] != "verified" for i in manifest["assets"][:15])
                or any(i["status"] != "planned" or i["attempt_history"] for i in manifest["assets"][16:])
                or any(i["attempt_history"] for s in stores[1:] for i in s.load()["assets"])):
            raise ValueError("Recovery scope, prefix or integrity state mismatch")
        for i, expected in zip(manifest["assets"], store.expected["assets"]):
            for field in ("relative_path", "metadata_relative_path"):
                if i["cache"][field] != expected["cache"][field]:
                    raise ValueError("Recovery cache path mismatch")
            if i["status"] == "verified":
                engine.verify_asset(i, store, manifest)
        for field in ("relative_path", "metadata_relative_path"):
            if (store.cache_root / item["cache"][field]).exists():
                raise ValueError("Recovery destination collision")
        for number in (1, 2):
            if engine._failure_evidence_path(store, item, number).exists():
                raise ValueError("Recovery failure-evidence collision")
        # Reconcile in memory only; the proxy forbids missing/stale gates from being persisted.
        class ReadOnlyStore:
            def __getattr__(self, name):
                return getattr(store, name)
            def save(self, value):
                raise ValueError("Recovery prefix requires gate mutation")
        probe = deepcopy(manifest)
        probe["assets"][15]["status"] = "retryable"
        if not engine.reconcile_verified_prefix_gates(probe, ReadOnlyStore())["ok"]:
            raise ValueError("Recovery prefix gates failed")
        # Preserve every current state document byte-for-byte before operational advancement.
        for s in stores:
            for fn in (engine.manifest_path, engine.ledger_path, engine.plan_path, engine.allowlist_path):
                path = fn(s.cache_root, s.spec)
                _write_once(directory / s.spec.target_season / path.name, path.read_bytes())
        authorization = {
            "version": "phase2e.cleveland-16-recovery.v1", "asset_id": RECOVERY_ASSET,
            "attempt_number": 2, "original_outcome": "uncertain",
            "original_hashes": RECOVERY_ANCHOR, "budget_extension": 0,
            "authorization": "User explicitly authorized one recovery and original-plan continuation",
        }
        _write_once(directory / "authorization.json", (json.dumps(authorization, sort_keys=True, indent=2)+"\n").encode())
        item["last_error"] = {"category": "authorized_uncertain_recovery", "retry_after_seconds": 30.0,
                              "detail": "Original attempt outcome remains uncertain; user authorized attempt 2"}
        store.transition(manifest, item, "retryable", "explicit_recovery_authorization", RECOVERY_ASSET)
        audit_recovery(store)
        return {"recovery": "prepared", "asset_id": RECOVERY_ASSET, "next_attempt": 2}


@contextmanager
def network_blocked():
    def reject(*args, **kwargs):
        raise RuntimeError("Network blocked for cache-only replay")
    with patch.object(socket.socket, "connect", reject), patch.object(engine.requests, "Session", reject):
        yield


def evidence_hashes(store):
    return {name: engine._sha256_file(fn(store.cache_root, store.spec))
            for name, fn in (("manifest", engine.manifest_path), ("ledger", engine.ledger_path),
                             ("plan", engine.plan_path), ("allowlist", engine.allowlist_path))}


def verify_prerequisites(cache_root):
    results = {}
    with network_blocked():
        for spec, expected, count in ((engine.PHASE2C_SPEC, engine.PHASE2C_HASHES, 4805),
                                      (phase2d.SPEC, PHASE2D_HASHES, 5745)):
            store = engine.create_store(cache_root, spec=spec)
            first = engine.analyze_release(store)
            second = engine.analyze_release(store)
            hashes = {**evidence_hashes(store), "analysis": first["deterministic_analysis_sha256"]}
            if (first != second or hashes != expected or first["request_set"]["verified"] != 62
                    or first["combined"]["matched_observation_keys"] != count
                    or first["canary"]["certification"]["status"] != "certified"):
                raise ValueError(f"Committed checkpoint does not reproduce: {spec.release_key}")
            results[spec.release_key] = hashes
    return results


def create_stores(cache_root, specs=SPECS):
    if tuple(specs) != SPECS:
        raise ValueError("Only the exact seven authorized Phase 2E specifications are permitted")
    with network_blocked():
        stores = tuple(engine.create_store(Path(cache_root), spec=spec) for spec in specs)
        reference = engine.read_json(engine.manifest_path(Path(cache_root), phase2d.SPEC))
        for store in stores:
            for field in ("approved_pair_schema_contract", "approved_player_schema_contract"):
                if store.expected[field] != reference[field]:
                    raise ValueError("Schema expectation differs from verified Phase 2D")
    validate_stores(stores)
    return stores


def validate_stores(stores):
    if tuple(s.spec for s in stores) != SPECS:
        raise ValueError("Unauthorized season specification or order")
    namespaces, assets, paths, identities = set(), set(), set(), set()
    for store in stores:
        spec = store.spec
        if spec.release_key in namespaces:
            raise ValueError("Duplicate namespace")
        namespaces.add(spec.release_key)
        expected = store.expected
        if len(expected["assets"]) != 62:
            raise ValueError("Each season requires exactly 62 identities")
        team_ids = set(expected["team_directory"])
        order = (*spec.canary_team_ids, *sorted(team_ids - set(spec.canary_team_ids), key=int))
        authorized = [engine.player_identity(mode, team_ids, spec) for mode in engine.PLAYER_PER_MODES]
        authorized.extend(engine.pair_identity(team, measure, team_ids, spec)
                          for team in order for measure in engine.MEASURES)
        if [a["identity"] for a in expected["assets"]] != authorized or len(team_ids) != 30:
            raise ValueError("Plan differs from authorized deterministic inventory/order")
        for name in ("manifest.json", "attempt_ledger.json", "initial_plan.json", "live_allowlist.json", "checkpoint.json"):
            path = f"{spec.release_key}/{name}"
            if path.casefold() in paths:
                raise ValueError("Duplicate state path")
            paths.add(path.casefold())
        for ordinal, item in enumerate(expected["assets"], 1):
            identity = item["identity"]
            engine.validate_identity(identity, set(expected["team_directory"]), spec)
            aid = engine.asset_id(identity, spec)
            request_id = engine.canonical_json_hash(identity)
            if item["ordinal"] != ordinal or item["asset_id"] != aid or aid in assets or request_id in identities:
                raise ValueError("Duplicate or disagreeing identity/asset/order")
            assets.add(aid)
            identities.add(request_id)
            stem = engine._safe_id(aid)
            for field, suffix in (("relative_path", ".json"), ("metadata_relative_path", ".metadata.json")):
                path = item["cache"][field]
                if path != f"{spec.release_key}/raw/{stem}{suffix}" or path.casefold() in paths:
                    raise ValueError("Duplicate or disagreeing asset path")
                paths.add(path.casefold())
    return True


def preview(stores):
    validate_stores(stores)
    assets = []
    for store in stores:
        for item in engine.dry_run_plan(store)["assets"]:
            assets.append({**item, "master_ordinal": len(assets) + 1,
                           "request_kind": store.spec.request_kind})
    return {"version": "phase2e.master-plan.v1", "network_calls": 0, "side_effects": [],
            "authorization": {"first_attempts": 434, "retries": 42, "total_attempts": 476},
            "assets": assets}


def initialize(stores):
    validate_stores(stores)
    for store in stores:
        if checkpoint_path(store).exists():
            certify(store)
    return {s.spec.target_season: engine.persist_initial_plan(s) for s in stores}


def checkpoint_path(store):
    return store.cache_root / store.spec.release_key / "checkpoint.json"


def certify(store, *, persist=False):
    with network_blocked():
        before = evidence_hashes(store)
        engine._approved_identities(store)
        first = engine.analyze_release(store)
        second = engine.analyze_release(store)
        manifest = store.load()
        payloads = engine._payloads(manifest, store)
        if engine._json_normalized(engine._player_source_gate(manifest, store)) != manifest["player_source_gate"]:
            raise ValueError("Player gate does not reproduce")
        for team_id, gate in manifest["team_gate_results"].items():
            audit = engine._json_normalized(engine._audit_team(team_id, payloads[team_id]["Base"], payloads[team_id]["Advanced"], store.spec))
            if gate != {"status": "passed", "team_id": team_id, "audit": audit,
                        "deterministic_sha256": engine.canonical_json_hash(audit)}:
                raise ValueError("Team gate does not reproduce")
        if (first != second or first["primary_classification"] != store.spec.supported_classification
                or len(manifest["team_gate_results"]) != 30 or evidence_hashes(store) != before):
            raise ValueError("Season analysis/gates do not reproduce")
        checkpoint = {"version": "phase2e.checkpoint.v1", "target_season": store.spec.target_season,
                      "hashes": before, "analysis_sha256": first["deterministic_analysis_sha256"],
                      "canary_sha256": first["canary"]["certification"]["recomputed_sha256"]}
        path = checkpoint_path(store)
        if path.exists():
            if engine.read_json(path) != checkpoint:
                raise ValueError("Immutable completed checkpoint mismatch")
        elif persist:
            engine.atomic_write_bytes_new(path, (json.dumps(checkpoint, sort_keys=True, indent=2) + "\n").encode())
        return first


def accounting(store):
    manifest = store.load() if store.path.exists() else store.expected
    items = manifest["assets"]
    events = [event for item in items for event in item["attempt_history"]]
    statuses = Counter(item["status"] for item in items)
    first = sum(bool(item["attempt_history"]) for item in items)
    retries = len(events) - first
    unfinished = next((item for item in items if item["status"] != "verified"), None)
    return {"target_season": store.spec.target_season, "requested": 62, "attempted": first,
            "retried": retries, "transport_attempts": len(events), "verified": statuses["verified"],
            "failed": statuses["failed"],
            "quarantined": sum((i.get("schema_verification") or {}).get("status") == "rejected" for i in items),
            "unattempted": 62 - first, "http_statuses": dict(Counter(str(e["http_status"]) for e in events if "http_status" in e)),
            "latencies": engine._quantiles([e["latency_seconds"] for e in events if "latency_seconds" in e]),
            "remaining": {"first_attempts": 62-first, "retries": 6-retries, "total_attempts": 68-len(events)},
            "canary": manifest.get("canary_result"), "integrity_stop": manifest.get("integrity_stop"),
            "next_asset": None if unfinished is None else {k: unfinished[k] for k in ("ordinal", "asset_id", "identity", "status", "attempt_history", "last_error", "schema_verification")}}


def acquire(stores, *, live_acquisition=False, transport=None, sleep_fn=time.sleep):
    if not live_acquisition:
        raise ValueError("Explicit live acquisition operation required")
    validate_stores(stores)
    completed = []
    if (recovery_path(stores[0]) / "authorization.json").exists():
        audit_recovery(stores[0])
    for index, store in enumerate(stores):
        try:
            if checkpoint_path(store).exists():
                certify(store)
            else:
                manifest = store.load()
                if any(i["attempt_history"] for later in stores[index+1:] for i in later.load()["assets"]):
                    raise ValueError("Later season touched after incomplete prefix")
                if not all(i["status"] == "verified" for i in manifest["assets"]):
                    if index:
                        sleep_fn(1.0)
                    result = engine.run_acquisition(store, live_acquisition=True, transport=transport, sleep_fn=sleep_fn)
                    if not result["completed"]:
                        return {"primary_classification": INCOMPLETE, "completed": completed,
                                "stopped_season": store.spec.target_season, "stop": result,
                                "accounting": accounting(store)}
                certify(store, persist=True)
            completed.append(store.spec.target_season)
        except Exception as exc:
            return {"primary_classification": INCOMPLETE, "completed": completed,
                    "stopped_season": store.spec.target_season,
                    "stop": {"category": "coordinator_integrity_stop", "detail": f"{type(exc).__name__}: {exc}"}}
    return {"primary_classification": UNRESOLVED, "completed": completed,
            "next_operation": "network-blocked combined analysis"}


def summarize(analyses, pairs_by_season):
    """Keep all team-season observations; count repeated identities descriptively."""
    players, pairs = defaultdict(set), defaultdict(set)
    seasons = {}
    for season in sorted(analyses):
        analysis = analyses[season]
        for pair in pairs_by_season[season]:
            pair = tuple(sorted(pair, key=int))
            pairs[pair].add(season)
            for player in pair:
                players[player].add(season)
        seasons[season] = {"observations": analysis["combined"]["matched_observation_keys"],
                           "combined": analysis["combined"], "prior_history": analysis["prior_history"]["combined"],
                           "schema_fingerprints": [a["schema_fingerprints"] for a in analysis["asset_ledger"]],
                           "pandemic_era": season in {"2019-20", "2020-21"}}
    return {"seasons": seasons, "total_pair_season_team_observations": sum(s["observations"] for s in seasons.values()),
            "unique_players": len(players), "unique_unordered_pairs": len(pairs),
            "players_in_multiple_seasons": {k: sorted(v) for k, v in sorted(players.items(), key=lambda x: int(x[0])) if len(v)>1},
            "pairs_in_multiple_seasons": [{"pair": k, "seasons": sorted(v)} for k, v in sorted(pairs.items()) if len(v)>1],
            "population_exhaustiveness": "remains unproven",
            "window": "Intended three-point-era research window; internal change requires time-aware modeling"}


def analyze(stores):
    validate_stores(stores)
    result = {"version": "phase2e.combined-audit.v1", "primary_classification": INCOMPLETE,
              "accounting": [accounting(s) for s in stores], "releases": {}}
    with network_blocked():
        for store in stores:
            if not checkpoint_path(store).exists():
                break
            result["releases"][store.spec.target_season] = certify(store)
        if len(result["releases"]) == 7:
            result["primary_classification"] = UNRESOLVED
            analyses = dict(result["releases"])
            old = [engine.create_store(stores[0].cache_root, spec=spec) for spec in (phase2d.SPEC, engine.PHASE2C_SPEC)]
            for store in old:
                analyses[store.spec.target_season] = engine.analyze_release(store)
            bstore = phase2b.create_store(stores[0].cache_root)
            analyses["2023-24"] = phase2b.analyze_release(bstore)
            pairs = {}
            for season, analysis in analyses.items():
                pairs[season] = []
                for asset in analysis["asset_ledger"]:
                    if season == "2023-24":
                        if asset["measure"] == "Base":
                            payload = engine.read_json(bstore.cache_root / asset["cache_path"])
                            pairs[season].extend(row["pair_key"] for row in engine._pair_rows(payload, season, asset["team_id"]))
                        continue
                    identity = asset["identity"]
                    if identity["endpoint"] != engine.PAIR_ENDPOINT or identity["parameters"]["measure_type"] != "Base":
                        continue
                    # Resolve only from the audited manifest, never infer another season's cache.
                    source = bstore if season == "2023-24" else next(s for s in (*stores, *old) if s.spec.target_season == season)
                    item = next(i for i in source.load()["assets"] if i["asset_id"] == asset["asset_id"])
                    payload = engine.read_json(source.cache_root / item["cache"]["relative_path"])
                    pairs[season].extend(row["pair_key"] for row in engine._pair_rows(payload, season, identity["parameters"]["team_id"]))
            result["historical_window"] = summarize(analyses, pairs)
            result["primary_classification"] = COMPLETE
    result["deterministic_analysis_sha256"] = engine.canonical_json_hash(result)
    return result
