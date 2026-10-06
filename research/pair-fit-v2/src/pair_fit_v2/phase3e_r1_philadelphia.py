"""Phase 3E-R1 bounded Philadelphia window evidence acquisition.

This research-only module can acquire exactly four predeclared 2024-25
Philadelphia TeamDashLineups responses.  It does not construct holdout rows,
aggregate rate targets, fit a model, generate predictions, or access the final
test season.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS
from pair_fit_v2.phase1c_manifest import (
    atomic_write_bytes_new,
    canonical_json_hash,
    raw_body_hash,
    read_json,
    utc_now,
    verify_asset_cache,
)
from pair_fit_v2.phase1d_exhaustiveness import (
    PHILADELPHIA_ID,
    TEAM_DASH_LINEUPS,
    TEAM_DASH_LINEUPS_URL,
    _expected_query,
    validate_diagnostic_payload,
)
from pair_fit_v2 import phase1e_recovery as phase1e


VERSION = "phase3e-r1.philadelphia-window-evidence.v1"
STARTING_HEAD = "a21314d71b369890844f1fdd883ac0375561507d"
TARGET_SEASON = "2024-25"
PROTECTED_SEASON = "2025-26"
POLICY_FILENAME = "PHASE3E_R1_INCOMPLETE_TEAM_SEASON_POLICY.md"
POLICY_SHA256 = "9273090b5cc55faddf54f0e531ad3845d5f67e311fa806bf2a6e7d8db74a6c41"
PHASE1C_MANIFEST = Path(
    "phase1c/manifests/2024-25_regular-season_teamdashlineups_group-2.json"
)
PHASE1C_MANIFEST_SHA256 = (
    "5465a63ce7cb9ae2df5fcddbc5436e9a711e23419c286c2cb1cdffe6a382a30c"
)
PHASE1E_LEDGER = Path("phase1e/recovery_ledger.json")
PHASE1E_LEDGER_SHA256 = (
    "5e51423b52e90b1369e834a3ec52d29956b54cf3e685e507d685f2224caccfde"
)
R1_ROOT = Path("phase3e-r1")
ATTEMPT_NUMBER = 1
TIMEOUT_SECONDS = 30
MINIMUM_ATTEMPT_INTERVAL_SECONDS = 1.0
PRIMARY_CLASSIFICATIONS = (
    "Philadelphia full-season response proven non-exhaustive",
    "Philadelphia incompleteness not demonstrated by acquired windows",
    "Philadelphia recovery evidence incomplete or invalid",
)
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


def reject_protected_paths(*paths: Path | str) -> None:
    for path in paths:
        if PROTECTED_SEASON in str(path).replace("\\", "/").lower():
            raise ValueError(f"protected-season path rejected before access: {path}")


def _read_bytes(path: Path) -> bytes:
    reject_protected_paths(path)
    return path.read_bytes()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(_read_bytes(path).decode("utf-8-sig"))


def _serialized_sha256(path: Path) -> str:
    return hashlib.sha256(_read_bytes(path)).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _write_json_new(path: Path, value: Any) -> None:
    reject_protected_paths(path)
    atomic_write_bytes_new(path, _json_bytes(value))


def canonical_content_hash(document: Mapping[str, Any]) -> str:
    value = dict(document)
    value.pop("deterministic_content_sha256", None)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_policy(project_root: Path) -> dict[str, Any]:
    path = project_root / POLICY_FILENAME
    actual = _serialized_sha256(path)
    if actual != POLICY_SHA256:
        raise ValueError("Phase 3E-R1 predeclared policy hash mismatch")
    return {
        "relative_path": POLICY_FILENAME,
        "serialized_byte_sha256": actual,
        "byte_count": len(_read_bytes(path)),
        "fixed_before_philadelphia_response_access": True,
    }


def authorized_assets() -> list[dict[str, Any]]:
    phase1e_assets = [
        deepcopy(asset)
        for asset in phase1e.build_phase1e_ledger()["assets"]
        if str(asset["identity"]["parameters"]["team_id"]) == PHILADELPHIA_ID
    ]
    if len(phase1e_assets) != 4:
        raise ValueError("Expected exactly four established Philadelphia identities")
    result = []
    for sequence, source in enumerate(phase1e_assets, start=1):
        identity = source["identity"]
        parameters = identity["parameters"]
        if (
            identity["endpoint"] != TEAM_DASH_LINEUPS
            or parameters["season"] != TARGET_SEASON
            or parameters["season_type"] != "regular-season"
            or parameters["team_id"] != PHILADELPHIA_ID
            or parameters["measure_type"] not in phase1e.MEASURES
        ):
            raise ValueError("Established identity is outside Phase 3E-R1 authorization")
        stem = source["asset_id"].replace(":", "_")
        result.append(
            {
                "sequence": sequence,
                "source_phase1e_sequence": source["sequence"],
                "source_phase1e_asset_id": source["asset_id"],
                "window": source["window"],
                "measure": source["measure"],
                "identity": identity,
                "paths": {
                    "started": str(R1_ROOT / "attempts" / f"{stem}.attempt-1.started.json"),
                    "outcome": str(R1_ROOT / "attempts" / f"{stem}.attempt-1.outcome.json"),
                    "verified_body": str(R1_ROOT / "verified" / f"{stem}.attempt-1.json"),
                    "quarantine_body": str(R1_ROOT / "quarantine" / f"{stem}.attempt-1.bin"),
                },
                "legacy_paths": deepcopy(source["cache"]),
            }
        )
    return result


def authorization_document(policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "starting_head": STARTING_HEAD,
        "policy": dict(policy),
        "network_scope": "only the four listed Philadelphia TeamDashLineups identities",
        "transport": {
            "sequential": True,
            "timeout_seconds": TIMEOUT_SECONDS,
            "minimum_seconds_between_transport_attempts": MINIMUM_ATTEMPT_INTERVAL_SECONDS,
            "automatic_retries": 0,
            "trust_env": False,
            "allow_redirects": False,
        },
        "assets": authorized_assets(),
    }


def ensure_authorization(cache_root: Path, project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    reject_protected_paths(cache_root, project_root)
    policy = verify_policy(project_root)
    expected = authorization_document(policy)
    path = cache_root / R1_ROOT / "authorization.json"
    if path.exists():
        actual = _read_json(path)
        if actual != expected:
            raise ValueError("Immutable Phase 3E-R1 authorization mismatch")
    else:
        _write_json_new(path, expected)
    return expected, {
        "relative_path": str(path.relative_to(cache_root)).replace("\\", "/"),
        "serialized_byte_sha256": _serialized_sha256(path),
        "byte_count": len(_read_bytes(path)),
    }


def direct_transport(identity: Mapping[str, Any], timeout_seconds: int = TIMEOUT_SECONDS) -> TransportResult:
    if timeout_seconds != TIMEOUT_SECONDS:
        raise ValueError("Phase 3E-R1 requires a 30-second timeout")
    if identity != next(
        (asset["identity"] for asset in authorized_assets() if asset["identity"] == identity),
        None,
    ):
        raise ValueError("Transport identity is not authorized")
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
    started = time.perf_counter()
    try:
        response = session.get(
            TEAM_DASH_LINEUPS_URL,
            params=_expected_query(identity),
            timeout=timeout_seconds,
            allow_redirects=False,
        )
        return TransportResult(
            status_code=response.status_code,
            body=response.content,
            elapsed_seconds=time.perf_counter() - started,
        )
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


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            pass
    return None


def validate_payload(
    payload: Mapping[str, Any],
    identity: Mapping[str, Any],
    approved_schema: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    parameters = payload.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ValueError("Response lacks a parameters identity envelope")
    expected = _expected_query(identity)
    for field in ("DateFrom", "DateTo"):
        returned_date = _parse_date(parameters.get(field))
        requested_date = _parse_date(expected[field])
        if returned_date is None or returned_date != requested_date:
            raise ValueError(
                f"Ambiguous or ignored {field}: expected={expected[field]!r}, actual={parameters.get(field)!r}"
            )
    echo_aligned = deepcopy(identity)
    echo_aligned["parameters"]["DateFrom"] = parameters["DateFrom"]
    echo_aligned["parameters"]["DateTo"] = parameters["DateTo"]
    return validate_diagnostic_payload(payload, echo_aligned, approved_schema)


def load_context(cache_root: Path) -> dict[str, Any]:
    manifest_path = cache_root / PHASE1C_MANIFEST
    if _serialized_sha256(manifest_path) != PHASE1C_MANIFEST_SHA256:
        raise ValueError("Immutable Phase 1C manifest hash mismatch")
    manifest = _read_json(manifest_path)
    schemas = manifest["approved_schema_contract"]
    full: dict[str, dict[str, Any]] = {}
    for asset in manifest.get("raw_assets", []):
        parameters = asset.get("identity", {}).get("parameters", {})
        if str(parameters.get("team_id")) != PHILADELPHIA_ID:
            continue
        measure = parameters.get("measure_type")
        if measure not in phase1e.MEASURES:
            continue
        replay = verify_asset_cache(asset, cache_root, schemas)
        full[measure] = {"asset": asset, "replay": replay, "payload": replay["payload"]}
    if set(full) != set(phase1e.MEASURES):
        raise ValueError("Philadelphia full-season evidence is incomplete")

    ledger_path = cache_root / PHASE1E_LEDGER
    if _serialized_sha256(ledger_path) != PHASE1E_LEDGER_SHA256:
        raise ValueError("Immutable Phase 1E ledger hash mismatch")
    ledger = _read_json(ledger_path)
    phase1e._validate_ledger(ledger, phase1e.build_phase1e_ledger())
    legacy = {
        asset["asset_id"]: asset
        for asset in ledger["assets"]
        if str(asset["identity"]["parameters"]["team_id"]) == PHILADELPHIA_ID
    }
    if len(legacy) != 4:
        raise ValueError("Phase 1E Philadelphia identity inventory mismatch")
    return {"manifest": manifest, "schemas": schemas, "full": full, "legacy": legacy}


def _path_map(cache_root: Path, asset: Mapping[str, Any]) -> dict[str, Path]:
    paths = {key: cache_root / value for key, value in asset["paths"].items()}
    reject_protected_paths(*paths.values())
    return paths


def _legacy_existing(
    cache_root: Path,
    asset: Mapping[str, Any],
    legacy: Mapping[str, Any],
    approved_schemas: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> tuple[dict | None, dict | None]:
    source = legacy[asset["source_phase1e_asset_id"]]
    if source["identity"] != asset["identity"]:
        raise ValueError("Phase 1E/R1 identity mismatch")
    paths = {key: cache_root / value for key, value in source["cache"].items()}
    reject_protected_paths(*paths.values())
    exists = {key: path.exists() for key, path in paths.items()}
    pristine = source.get("status") == "planned" and source.get("attempt_count") == 0 and not any(exists.values())
    if pristine:
        return None, None
    if source.get("status") == "verified" and exists["relative_path"] and exists["metadata_relative_path"] and not exists["error_body_relative_path"]:
        payload, validation = phase1e._verify_cached_asset(
            cache_root, source, approved_schemas
        )
        return payload, {
            "source": "verified_phase1e_identity",
            "asset_id": source["asset_id"],
            "relative_path": source["cache"]["relative_path"],
            "raw_body_sha256": raw_body_hash(_read_bytes(paths["relative_path"])),
            "canonical_json_sha256": canonical_json_hash(payload),
            "byte_count": len(_read_bytes(paths["relative_path"])),
            "row_count": validation["row_counts"]["Lineups"],
        }
    raise ValueError(f"Existing attempted or quarantined Phase 1E identity blocks request: {source['asset_id']}")


def _verify_r1_asset(
    cache_root: Path,
    asset: Mapping[str, Any],
    approved_schema: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    paths = _path_map(cache_root, asset)
    exists = {key: path.exists() for key, path in paths.items()}
    if not any(exists.values()):
        return None, None
    if exists["quarantine_body"]:
        raise ValueError(f"Quarantined identity blocks request: {asset['source_phase1e_asset_id']}")
    if not (exists["started"] and exists["outcome"] and exists["verified_body"]):
        raise ValueError(f"Incomplete prior attempt blocks request: {asset['source_phase1e_asset_id']}")
    started = _read_json(paths["started"])
    outcome = _read_json(paths["outcome"])
    if started.get("identity") != asset["identity"] or outcome.get("identity") != asset["identity"]:
        raise ValueError("R1 cached attempt identity mismatch")
    if outcome.get("status") != "verified" or outcome.get("http_status") != 200:
        raise ValueError("R1 existing outcome is not reusable verified evidence")
    body = _read_bytes(paths["verified_body"])
    if outcome.get("byte_count") != len(body) or outcome.get("raw_body_sha256") != raw_body_hash(body):
        raise ValueError("R1 cached raw-body provenance mismatch")
    payload = json.loads(body)
    if outcome.get("canonical_json_sha256") != canonical_json_hash(payload):
        raise ValueError("R1 cached canonical JSON provenance mismatch")
    validation = validate_payload(payload, asset["identity"], approved_schema)
    if outcome.get("row_count") != validation["row_counts"]["Lineups"]:
        raise ValueError("R1 cached row-count provenance mismatch")
    return payload, outcome


def _failure(classification_detail: str, assets: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "version": VERSION,
        "completed": False,
        "primary_classification": PRIMARY_CLASSIFICATIONS[2],
        "classification_detail": classification_detail,
        "assets": assets,
        "population_decision_made": False,
        "charlotte_disposition": "provisionally excluded in full",
        "philadelphia_disposition": "no population decision",
    }
    result["deterministic_content_sha256"] = canonical_content_hash(result)
    return result


def _record_quarantine(
    paths: Mapping[str, Path],
    asset: Mapping[str, Any],
    response: TransportResult,
    category: str,
    detail: str,
    started_at: str,
) -> dict[str, Any]:
    _write_json_new(
        paths["outcome"],
        {
            "version": VERSION,
            "status": "quarantined",
            "category": category,
            "detail": detail,
            "identity": asset["identity"],
            "attempt_number": ATTEMPT_NUMBER,
            "started_at": started_at,
            "completed_at": utc_now(),
            "http_status": response.status_code,
            "elapsed_seconds": response.elapsed_seconds,
            "byte_count": len(response.body),
            "raw_body_sha256": raw_body_hash(response.body),
            "quarantine_relative_path": str(paths["quarantine_body"].relative_to(paths["quarantine_body"].parents[2])).replace("\\", "/"),
        },
    )
    return _read_json(paths["outcome"])


def acquire(
    cache_root: Path,
    project_root: Path,
    *,
    live: bool = False,
    transport: Callable[[Mapping[str, Any], int], TransportResult] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    authorization, authorization_record = ensure_authorization(cache_root, project_root)
    context = load_context(cache_root)
    if live and transport is None:
        transport = direct_transport
    payloads: dict[str, dict[str, Any]] = {"early": {}, "late": {}}
    asset_records: list[dict[str, Any]] = []
    made_transport_attempt = False

    for asset in authorization["assets"]:
        measure = asset["measure"]
        try:
            payload, record = _verify_r1_asset(cache_root, asset, context["schemas"][measure])
            if payload is None:
                payload, record = _legacy_existing(
                    cache_root, asset, context["legacy"], context["schemas"]
                )
        except Exception as exc:
            return _failure(f"existing_identity_error: {type(exc).__name__}: {exc}", asset_records)
        if payload is not None:
            payloads[asset["window"]][measure] = payload
            record_label = (
                "verified"
                if record.get("version") == VERSION and record.get("status") == "verified"
                else "reused"
            )
            asset_records.append(
                {"sequence": asset["sequence"], "outcome": record_label, **record}
            )
            continue
        if not live:
            return _failure(f"uncached authorized identity: {asset['source_phase1e_asset_id']}", asset_records)
        if made_transport_attempt:
            sleeper(MINIMUM_ATTEMPT_INTERVAL_SECONDS)
        paths = _path_map(cache_root, asset)
        started_at = utc_now()
        started = {
            "version": VERSION,
            "status": "started",
            "identity": asset["identity"],
            "attempt_number": ATTEMPT_NUMBER,
            "started_at": started_at,
            "timeout_seconds": TIMEOUT_SECONDS,
            "automatic_retries": 0,
            "trust_env": False,
            "allow_redirects": False,
        }
        _write_json_new(paths["started"], started)
        made_transport_attempt = True
        try:
            response = transport(asset["identity"], TIMEOUT_SECONDS)  # type: ignore[misc]
        except TransportError as exc:
            outcome = {
                "version": VERSION,
                "status": "transport_failure",
                "category": exc.category,
                "detail": exc.detail,
                "identity": asset["identity"],
                "attempt_number": ATTEMPT_NUMBER,
                "started_at": started_at,
                "completed_at": utc_now(),
                "http_status": None,
                "returned_body": False,
            }
            _write_json_new(paths["outcome"], outcome)
            asset_records.append({"sequence": asset["sequence"], "outcome": "transport_failure", **outcome})
            return _failure(f"{exc.category}: {exc.detail}", asset_records)
        if response.status_code != 200:
            atomic_write_bytes_new(paths["quarantine_body"], response.body)
            outcome = _record_quarantine(paths, asset, response, "http_error", f"HTTP {response.status_code}", started_at)
            asset_records.append({"sequence": asset["sequence"], "outcome": "quarantined", **outcome})
            return _failure(f"http_error: HTTP {response.status_code}", asset_records)
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            atomic_write_bytes_new(paths["quarantine_body"], response.body)
            detail = f"{type(exc).__name__}: {exc}"
            outcome = _record_quarantine(paths, asset, response, "invalid_json", detail, started_at)
            asset_records.append({"sequence": asset["sequence"], "outcome": "quarantined", **outcome})
            return _failure(f"invalid_json: {detail}", asset_records)
        try:
            validation = validate_payload(payload, asset["identity"], context["schemas"][measure])
        except Exception as exc:
            atomic_write_bytes_new(paths["quarantine_body"], response.body)
            detail = f"{type(exc).__name__}: {exc}"
            outcome = _record_quarantine(paths, asset, response, "validation_error", detail, started_at)
            asset_records.append({"sequence": asset["sequence"], "outcome": "quarantined", **outcome})
            return _failure(f"validation_error: {detail}", asset_records)
        atomic_write_bytes_new(paths["verified_body"], response.body)
        outcome = {
            "version": VERSION,
            "status": "verified",
            "identity": asset["identity"],
            "attempt_number": ATTEMPT_NUMBER,
            "started_at": started_at,
            "completed_at": utc_now(),
            "http_status": response.status_code,
            "elapsed_seconds": response.elapsed_seconds,
            "byte_count": len(response.body),
            "raw_body_sha256": raw_body_hash(response.body),
            "canonical_json_sha256": canonical_json_hash(payload),
            "row_count": validation["row_counts"]["Lineups"],
            "verified_relative_path": str(paths["verified_body"].relative_to(cache_root)).replace("\\", "/"),
        }
        _write_json_new(paths["outcome"], outcome)
        payloads[asset["window"]][measure] = payload
        asset_records.append({"sequence": asset["sequence"], "outcome": "verified", **outcome})

    if any(set(payloads[window]) != set(phase1e.MEASURES) for window in ("early", "late")):
        return _failure("all four authorized assets were not verified", asset_records)
    try:
        reconciliation = reconcile(context, payloads)
    except Exception as exc:
        return _failure(f"reconciliation_error: {type(exc).__name__}: {exc}", asset_records)
    classification = (
        PRIMARY_CLASSIFICATIONS[0]
        if reconciliation["recovered_only_key_count"] > 0
        else PRIMARY_CLASSIFICATIONS[1]
    )
    philadelphia_disposition = (
        "excluded in full"
        if classification == PRIMARY_CLASSIFICATIONS[0]
        else "not excluded by the predeclared proven-non-exhaustive rule; exhaustiveness remains unproven"
    )
    result = {
        "version": VERSION,
        "completed": True,
        "primary_classification": classification,
        "classification_detail": (
            "At least one valid canonical window-union pair is absent from the direct full-season response."
            if classification == PRIMARY_CLASSIFICATIONS[0]
            else "No valid canonical window-union pair absent from the full-season response was found; this does not prove exhaustiveness."
        ),
        "population_decision_made": True,
        "policy": authorization["policy"],
        "authorization_record": authorization_record,
        "assets": asset_records,
        "population_reconciliation": reconciliation,
        "charlotte_disposition": "provisionally excluded in full",
        "philadelphia_disposition": philadelphia_disposition,
        "target_constraints": {
            "recovered_only_full_season_net_rating_assigned": False,
            "weighted_window_ratings_used_as_targets": False,
            "holdout_dataset_constructed": False,
            "predictions_or_metrics_generated": False,
            "frozen_model_run": False,
        },
        "final_test_season_accessed": False,
    }
    result["deterministic_content_sha256"] = canonical_content_hash(result)
    return result


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _pair_diagnostics(payload: Mapping[str, Any]) -> dict[str, Any]:
    return phase1e._pair_index(payload)


def _structural_issues(indexed: Mapping[str, Any]) -> bool:
    return bool(indexed["malformed"] or indexed["same_player"] or indexed["duplicates"])


def _full_asset_record(item: Mapping[str, Any]) -> dict[str, Any]:
    asset = item["asset"]
    replay = item["replay"]
    return {
        "asset_id": asset["asset_id"],
        "relative_path": asset["cache"]["relative_path"],
        "byte_count": replay["cache_file_bytes"],
        "raw_body_sha256": asset["source_event"]["raw_body_hash"],
        "canonical_json_sha256": replay["canonical_json_hash"],
        "lineup_rows": replay["row_counts"]["Lineups"],
    }


def reconcile(context: Mapping[str, Any], payloads: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, Any]:
    full_indexes = {
        measure: _pair_diagnostics(context["full"][measure]["payload"])
        for measure in phase1e.MEASURES
    }
    if any(_structural_issues(value) for value in full_indexes.values()):
        raise ValueError("Philadelphia full-season response has malformed, same-player, or duplicate keys")
    full_base_keys = set(full_indexes["Base"]["index"])
    full_advanced_keys = set(full_indexes["Advanced"]["index"])
    if full_base_keys != full_advanced_keys or len(full_base_keys) != 250:
        raise ValueError("Philadelphia full-season Base/Advanced population is not a matched 250-key set")

    window_reconciliation: dict[str, Any] = {}
    window_indexes: dict[str, dict[str, Any]] = {}
    for window in ("early", "late"):
        base = _pair_diagnostics(payloads[window]["Base"])
        advanced = _pair_diagnostics(payloads[window]["Advanced"])
        keys_base, keys_advanced = set(base["index"]), set(advanced["index"])
        reconciliation = phase1e.reconcile_window_measures(
            payloads[window]["Base"], payloads[window]["Advanced"]
        )
        window_reconciliation[window] = reconciliation
        window_indexes[window] = {"Base": base, "Advanced": advanced}
        structural_invalid = (
            _structural_issues(base)
            or _structural_issues(advanced)
            or keys_base != keys_advanced
            or reconciliation["negative_possessions"] > 0
            or reconciliation["missing_or_nonnumeric_possessions"] > 0
        )
        if structural_invalid:
            raise ValueError(f"{window} Base/Advanced key or possession reconciliation failed")

    early_keys = set(window_indexes["early"]["Base"]["index"])
    late_keys = set(window_indexes["late"]["Base"]["index"])
    union = early_keys | late_keys
    recovered_only = sorted(union - full_base_keys, key=phase1e._key_sort)
    recovered_rows = []
    for key in recovered_only:
        per_window = []
        all_base_rows = []
        all_advanced_rows = []
        for window in ("early", "late"):
            base_row = window_indexes[window]["Base"]["index"].get(key)
            advanced_row = window_indexes[window]["Advanced"]["index"].get(key)
            if base_row is None:
                continue
            all_base_rows.append(base_row)
            all_advanced_rows.append(advanced_row)
            per_window.append(
                {
                    "window": window,
                    "base_gp": _numeric(base_row.get("GP")),
                    "base_minutes": _numeric(base_row.get("MIN")),
                    "base_sum_time_played": _numeric(base_row.get("SUM_TIME_PLAYED")),
                    "advanced_possessions": _numeric(advanced_row.get("POSS")),
                }
            )
        total_poss = phase1e._sum_field(all_advanced_rows, "POSS")
        recovered_rows.append(
            {
                "player_1_id": key[0],
                "player_2_id": key[1],
                "group_name": next((row.get("GROUP_NAME") for row in all_base_rows if row.get("GROUP_NAME")), None),
                "windows_present": [row["window"] for row in per_window],
                "per_window_additive_exposure": per_window,
                "summed_base_gp": phase1e._sum_field(all_base_rows, "GP"),
                "summed_base_minutes": phase1e._sum_field(all_base_rows, "MIN"),
                "summed_base_sum_time_played": phase1e._sum_field(all_base_rows, "SUM_TIME_PLAYED"),
                "summed_advanced_possessions": total_poss,
                "could_potentially_meet_poss_150": total_poss is not None and total_poss >= 150,
                "full_season_net_rating_assigned": False,
            }
        )

    return {
        "full_season_key_count": len(full_base_keys),
        "full_season_assets": {
            measure: _full_asset_record(context["full"][measure]) for measure in phase1e.MEASURES
        },
        "window_key_counts": {"early": len(early_keys), "late": len(late_keys)},
        "window_union_key_count": len(union),
        "full_season_keys_absent_from_union": [list(key) for key in sorted(full_base_keys - union, key=phase1e._key_sort)],
        "full_season_keys_absent_from_union_count": len(full_base_keys - union),
        "recovered_only_keys_absent_from_full_season": [list(key) for key in recovered_only],
        "recovered_only_key_count": len(recovered_only),
        "recovered_only_pairs": recovered_rows,
        "recovered_only_pairs_potentially_meeting_poss_150": sum(
            row["could_potentially_meet_poss_150"] for row in recovered_rows
        ),
        "window_overlap": {
            "both_windows": len(early_keys & late_keys),
            "early_only": len(early_keys - late_keys),
            "late_only": len(late_keys - early_keys),
        },
        "window_reconciliation": window_reconciliation,
        "full_season_reconciliation": {
            "base_only_keys": [],
            "advanced_only_keys": [],
            "base_malformed_identifiers": full_indexes["Base"]["malformed"],
            "advanced_malformed_identifiers": full_indexes["Advanced"]["malformed"],
            "base_duplicate_keys": full_indexes["Base"]["duplicates"],
            "advanced_duplicate_keys": full_indexes["Advanced"]["duplicates"],
        },
        "ratings_aggregated_or_assigned": False,
    }


def write_result(output_dir: Path, result: Mapping[str, Any]) -> Path:
    reject_protected_paths(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "philadelphia_evidence.json"
    data = _json_bytes(result)
    if path.exists():
        if _read_bytes(path) != data:
            raise FileExistsError(f"Refusing to overwrite differing replay result: {path}")
    else:
        atomic_write_bytes_new(path, data)
    return path
