"""Explicit, sequential Phase 1C acquisition runner.

Imports and ordinary function calls are offline by default. A caller must pass
``live_acquisition=True`` and ``dry_run=False`` before the direct transport can run.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS
from pair_fit_v2.phase1b_contract import REQUIRED_RESULT_SETS, schema_drift_report
from pair_fit_v2.phase1c_manifest import (
    ENDPOINT,
    LEAGUE_ID,
    SEASON_TYPE,
    ManifestStore,
    atomic_write_bytes_new,
    atomic_write_json,
    canonical_json_hash,
    raw_body_hash,
    validate_manifest_envelope,
    validate_payload_structure,
    verify_asset_cache,
)


TEAM_DASH_LINEUPS_URL = "https://stats.nba.com/stats/teamdashlineups"


@dataclass(frozen=True)
class TransportResult:
    status_code: int
    body: bytes
    elapsed_seconds: float


class AcquisitionTransportError(RuntimeError):
    def __init__(self, category: str, detail: str):
        super().__init__(detail)
        self.category = category
        self.detail = detail


def _request_parameters(identity: Mapping[str, Any]) -> dict[str, Any]:
    if identity.get("endpoint") != ENDPOINT:
        raise ValueError(f"Unsupported endpoint: {identity.get('endpoint')}")
    parameters = dict(identity.get("parameters", {}))
    season_type_slug = parameters.pop("season_type")
    if season_type_slug != "regular-season":
        raise ValueError(f"Unauthorized season type: {season_type_slug}")
    core = {
        "LeagueID": parameters.pop("league_id"),
        "Season": parameters.pop("season"),
        "SeasonType": SEASON_TYPE,
        "TeamID": parameters.pop("team_id"),
        "GroupQuantity": parameters.pop("group_quantity"),
        "MeasureType": parameters.pop("measure_type"),
    }
    if core["LeagueID"] != LEAGUE_ID:
        raise ValueError("Only NBA league ID 00 is authorized")
    return {**parameters, **core}


def direct_nba_transport(
    identity: Mapping[str, Any], timeout_seconds: int = 30
) -> TransportResult:
    """Perform exactly one direct request with fixed headers and no proxy/retry."""
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    started = time.perf_counter()
    try:
        response = session.get(
            TEAM_DASH_LINEUPS_URL,
            params=_request_parameters(identity),
            timeout=timeout_seconds,
        )
        return TransportResult(
            status_code=response.status_code,
            body=response.content,
            elapsed_seconds=time.perf_counter() - started,
        )
    except requests.Timeout as exc:
        raise AcquisitionTransportError("timeout", str(exc)) from exc
    except requests.exceptions.SSLError as exc:
        raise AcquisitionTransportError("tls_failure", str(exc)) from exc
    except requests.ConnectionError as exc:
        raise AcquisitionTransportError("connection_or_dns_failure", str(exc)) from exc
    except requests.RequestException as exc:
        raise AcquisitionTransportError("request_failure", str(exc)) from exc
    finally:
        session.close()


def _complete_attempt(
    attempt: dict[str, Any], *, status: str, category: str | None, detail: str | None
) -> None:
    attempt.update(
        {
            "status": status,
            "error_category": category,
            "error_detail": detail,
        }
    )


def _stop_result(
    manifest: Mapping[str, Any],
    *,
    actions: list[dict[str, Any]],
    attempted: int,
    successful: int,
    failed: int,
    quarantined: int,
    skipped: int,
    asset: Mapping[str, Any] | None,
    category: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "completed": False,
        "stopped_early": True,
        "actions": actions,
        "attempted": attempted,
        "successful": successful,
        "failed": failed,
        "quarantined": quarantined,
        "skipped": skipped,
        "verified": sum(
            item.get("status") == "verified" for item in manifest["raw_assets"]
        ),
        "stop_category": category,
        "stop_detail": detail,
        "resume_asset_id": asset.get("asset_id") if asset else None,
        "resume_instruction": (
            "Resolve the recorded failure, then rerun with --live-acquisition. "
            "Add --retry-failed only when explicitly authorizing retry of the failed asset."
        ),
    }


def run_manifest_acquisition(
    store: ManifestStore,
    *,
    dry_run: bool = True,
    live_acquisition: bool = False,
    retry_failed: bool = False,
    timeout_seconds: int = 30,
    delay_seconds: float = 1.0,
    transport: Callable[[Mapping[str, Any], int], TransportResult] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    authorized_asset_id: str | None = None,
    max_live_attempts_this_run: int | None = None,
) -> dict[str, Any]:
    """Consume the manifest in deterministic order and stop after the first error."""
    if timeout_seconds != 30:
        raise ValueError("Phase 1C live requests require the approved 30-second timeout")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must not be negative")
    if max_live_attempts_this_run is not None and max_live_attempts_this_run < 1:
        raise ValueError("max_live_attempts_this_run must be positive")
    if not dry_run and not live_acquisition:
        raise ValueError("Live acquisition requires the explicit live_acquisition flag")
    if live_acquisition and transport is None:
        transport = direct_nba_transport

    manifest = store.load()
    validate_manifest_envelope(manifest, store.expected_manifest)
    approved = manifest["approved_schema_contract"]
    actions: list[dict[str, Any]] = []
    attempted = successful = failed = quarantined = skipped = 0
    authorization_limit = int(manifest["authorization"]["maximum_new_live_requests"])
    historical_live_attempts = sum(
        1
        for asset in manifest["raw_assets"]
        for attempt in asset.get("attempt_history", [])
        if attempt.get("request_kind") == "phase1c_live"
    )

    for asset in manifest["raw_assets"]:
        status = asset.get("status")
        identity = asset["identity"]
        parameters = identity["parameters"]
        action_context = {
            "asset_id": asset["asset_id"],
            "team_id": parameters["team_id"],
            "measure_type": parameters["measure_type"],
        }

        if status == "verified":
            try:
                verification = verify_asset_cache(asset, store.cache_root, approved)
            except Exception as exc:
                detail = f"Previously verified cache failed replay: {exc}"
                if not dry_run:
                    asset["last_error"] = {
                        "category": "verified_cache_replay_failure",
                        "detail": detail,
                    }
                    store.transition(
                        manifest,
                        asset,
                        "failed",
                        category="verified_cache_replay_failure",
                        detail=detail,
                    )
                return _stop_result(
                    manifest,
                    actions=actions,
                    attempted=attempted,
                    successful=successful,
                    failed=failed + 1,
                    quarantined=quarantined,
                    skipped=skipped,
                    asset=asset,
                    category="verified_cache_replay_failure",
                    detail=detail,
                )
            actions.append(
                {
                    **action_context,
                    "action": "skip_verified",
                    "canonical_json_hash": verification["canonical_json_hash"],
                }
            )
            skipped += 1
            continue

        if status == "quarantined":
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed,
                quarantined=quarantined + 1,
                skipped=skipped,
                asset=asset,
                category="quarantined_asset",
                detail="A quarantined asset requires explicit schema review",
            )
        if status == "failed" and not retry_failed:
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed + 1,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="failed_asset_retry_not_authorized",
                detail="Retry requires retry_failed=True",
            )
        if status not in {"planned", "failed"}:
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed + 1,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="invalid_asset_status",
                detail=f"Cannot acquire asset from status {status!r}",
            )

        if authorized_asset_id is not None and asset["asset_id"] != authorized_asset_id:
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="asset_not_authorized_for_run",
                detail=(
                    f"This run authorizes only {authorized_asset_id}; encountered "
                    f"{asset['asset_id']}"
                ),
            )

        cache_path = store.cache_root / asset["cache"]["relative_path"]
        metadata_path = store.cache_root / asset["cache"]["metadata_relative_path"]
        if cache_path.exists() or metadata_path.exists():
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed + 1,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="duplicate_cache_destination",
                detail=f"Planned asset destination already exists: {cache_path}",
            )

        actions.append({**action_context, "action": "acquire"})
        if dry_run:
            continue
        if (
            max_live_attempts_this_run is not None
            and attempted >= max_live_attempts_this_run
        ):
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="per_run_attempt_limit_reached",
                detail=(
                    f"This run's {max_live_attempts_this_run}-attempt limit is exhausted"
                ),
            )
        if historical_live_attempts + attempted >= authorization_limit:
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="authorization_limit_reached",
                detail=f"The {authorization_limit}-request authorization is exhausted",
            )

        attempt = {
            "attempt_number": len(asset.get("attempt_history", [])) + 1,
            "request_kind": "phase1c_live",
            "started_at": store.clock(),
            "status": "started",
            "timeout_seconds": timeout_seconds,
        }
        asset.setdefault("attempt_history", []).append(attempt)
        asset["attempt_count"] = int(asset.get("attempt_count", 0)) + 1
        asset["last_error"] = None
        store.save(manifest)
        attempted += 1

        try:
            response = transport(identity, timeout_seconds)  # type: ignore[misc]
        except AcquisitionTransportError as exc:
            _complete_attempt(
                attempt, status="failed", category=exc.category, detail=exc.detail
            )
            asset["last_error"] = {"category": exc.category, "detail": exc.detail}
            store.transition(
                manifest,
                asset,
                "failed",
                category=exc.category,
                detail=exc.detail,
            )
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed + 1,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category=exc.category,
                detail=exc.detail,
            )
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            _complete_attempt(
                attempt, status="failed", category="unexpected_exception", detail=detail
            )
            asset["last_error"] = {
                "category": "unexpected_exception",
                "detail": detail,
            }
            store.transition(
                manifest,
                asset,
                "failed",
                category="unexpected_exception",
                detail=detail,
            )
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed + 1,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="unexpected_exception",
                detail=detail,
            )

        attempt["elapsed_seconds"] = response.elapsed_seconds
        attempt["response_body_bytes"] = len(response.body)
        if response.status_code != 200:
            detail = f"HTTP {response.status_code}"
            _complete_attempt(
                attempt, status="failed", category="non_200_http", detail=detail
            )
            asset["last_error"] = {"category": "non_200_http", "detail": detail}
            store.transition(
                manifest,
                asset,
                "failed",
                category="non_200_http",
                detail=detail,
            )
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed + 1,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="non_200_http",
                detail=detail,
            )

        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            detail = f"Invalid JSON response: {exc}"
            quarantine_body = (
                store.cache_root
                / "phase1c"
                / "quarantine"
                / f"{asset['asset_id'].replace(':', '_')}.attempt-{attempt['attempt_number']}.body"
            )
            try:
                atomic_write_bytes_new(quarantine_body, response.body)
                attempt["preserved_response_path"] = str(
                    quarantine_body.relative_to(store.cache_root)
                ).replace("\\", "/")
            except Exception as write_exc:
                detail += f"; failed to preserve body: {write_exc}"
            _complete_attempt(
                attempt, status="failed", category="invalid_json", detail=detail
            )
            asset["last_error"] = {"category": "invalid_json", "detail": detail}
            store.transition(
                manifest, asset, "failed", category="invalid_json", detail=detail
            )
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed + 1,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="invalid_json",
                detail=detail,
            )

        schema_error = None
        validation = None
        drift_results = {}
        rejected = {}
        try:
            validation = validate_payload_structure(payload)
        except ValueError as exc:
            schema_error = str(exc)
        if validation is not None:
            measure = parameters["measure_type"]
            actual_by_name = {
                fingerprint["name"]: fingerprint
                for fingerprint in validation["fingerprints"]
            }
            for result_set_name in REQUIRED_RESULT_SETS:
                drift = schema_drift_report(
                    approved[measure][result_set_name], actual_by_name[result_set_name]
                )
                drift_results[result_set_name] = drift
            rejected = {
                name: drift["classification"]
                for name, drift in drift_results.items()
                if not drift["accepted"]
            }

        try:
            atomic_write_bytes_new(cache_path, response.body)
            digest = canonical_json_hash(payload)
            asset["source_event"] = {
                "provenance_format": "phase1c-live-v1",
                "recorded_success": True,
                "acquired_at": store.clock(),
                "http_status": response.status_code,
                "response_body_bytes": len(response.body),
                "raw_body_hash": raw_body_hash(response.body),
            }
            asset["cache"].update(
                {
                    "cache_file_bytes": cache_path.stat().st_size,
                    "canonical_json_hash": digest,
                    "canonical_json_hash_algorithm": "sha256-json-sort-keys.v1",
                    "serialization_version": "raw-response-body.v1",
                }
            )
            asset["schema_verification"] = {
                "status": (
                    "accepted" if schema_error is None and not rejected else "rejected"
                ),
                "fingerprints": validation["fingerprints"] if validation else [],
                "drift_classification": (
                    "identical"
                    if schema_error is None and not rejected
                    else "non_identical"
                ),
                "row_counts": validation["row_counts"] if validation else {},
                "error": schema_error,
                "drift_results": drift_results,
            }
            metadata = {
                "operational_manifest_version": manifest[
                    "operational_manifest_version"
                ],
                "manifest_id": manifest["manifest_id"],
                "asset_id": asset["asset_id"],
                "identity": identity,
                "source_event": asset["source_event"],
                "cache": asset["cache"],
                "schema_verification": asset["schema_verification"],
                "elapsed_seconds": response.elapsed_seconds,
            }
            if metadata_path.exists():
                raise FileExistsError(
                    f"Metadata destination already exists: {metadata_path}"
                )
            atomic_write_json(metadata_path, metadata)
        except Exception as exc:
            detail = f"Cache write failure: {type(exc).__name__}: {exc}"
            _complete_attempt(
                attempt, status="failed", category="cache_write_failure", detail=detail
            )
            asset["last_error"] = {
                "category": "cache_write_failure",
                "detail": detail,
            }
            store.transition(
                manifest,
                asset,
                "failed",
                category="cache_write_failure",
                detail=detail,
            )
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed + 1,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="cache_write_failure",
                detail=detail,
            )

        store.transition(
            manifest,
            asset,
            "acquired",
            category="response_cached",
            detail=f"bytes={len(response.body)}",
        )
        if schema_error is not None:
            _complete_attempt(
                attempt,
                status="quarantined",
                category="schema_quarantine",
                detail=schema_error,
            )
            asset["last_error"] = {
                "category": "schema_quarantine",
                "detail": schema_error,
            }
            store.transition(
                manifest,
                asset,
                "quarantined",
                category="schema_quarantine",
                detail=schema_error,
            )
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed,
                quarantined=quarantined + 1,
                skipped=skipped,
                asset=asset,
                category="schema_quarantine",
                detail=schema_error,
            )

        if rejected:
            detail = f"Schema drift: {rejected}"
            _complete_attempt(
                attempt,
                status="quarantined",
                category="schema_quarantine",
                detail=detail,
            )
            asset["last_error"] = {
                "category": "schema_quarantine",
                "detail": detail,
            }
            store.transition(
                manifest,
                asset,
                "quarantined",
                category="schema_quarantine",
                detail=detail,
            )
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed,
                quarantined=quarantined + 1,
                skipped=skipped,
                asset=asset,
                category="schema_quarantine",
                detail=detail,
            )

        try:
            replay = verify_asset_cache(asset, store.cache_root, approved)
        except Exception as exc:
            detail = f"Cache replay failure: {type(exc).__name__}: {exc}"
            _complete_attempt(
                attempt,
                status="failed",
                category="cache_replay_failure",
                detail=detail,
            )
            asset["last_error"] = {
                "category": "cache_replay_failure",
                "detail": detail,
            }
            store.transition(
                manifest,
                asset,
                "failed",
                category="cache_replay_failure",
                detail=detail,
            )
            return _stop_result(
                manifest,
                actions=actions,
                attempted=attempted,
                successful=successful,
                failed=failed + 1,
                quarantined=quarantined,
                skipped=skipped,
                asset=asset,
                category="cache_replay_failure",
                detail=detail,
            )

        _complete_attempt(attempt, status="verified", category=None, detail=None)
        attempt.update(
            {
                "asset_id": asset["asset_id"],
                "canonical_json_hash": replay["canonical_json_hash"],
                "cache_file_bytes": replay["cache_file_bytes"],
                "row_counts": replay["row_counts"],
            }
        )
        asset["last_error"] = None
        store.transition(
            manifest,
            asset,
            "verified",
            category="cache_replay_verified",
            detail=f"hash={replay['canonical_json_hash']}",
        )
        successful += 1
        sleep_fn(delay_seconds)

    return {
        "completed": not dry_run,
        "stopped_early": False,
        "dry_run": dry_run,
        "actions": actions,
        "attempted": attempted,
        "successful": successful,
        "failed": failed,
        "quarantined": quarantined,
        "skipped": skipped,
        "verified": sum(
            item.get("status") == "verified" for item in manifest["raw_assets"]
        ),
        "planned": sum(
            item.get("status") == "planned" for item in manifest["raw_assets"]
        ),
    }
