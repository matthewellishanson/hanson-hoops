from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import inspect
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .datasets import DatasetSpec, get_spec
from .storage import ResearchStore
from .transform import process_nba_payload

NBA_BASE_URL = "https://stats.nba.com/stats"
DEFAULT_HEADERS = {
    "User-Agent": os.getenv(
        "NBA_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.nba.com",
    "Referer": "https://www.nba.com/stats/",
    "Connection": "keep-alive",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}
PROXY_ENV_NAMES = ("NBA_RUNTIME_PROXY", "PROXY_URL", "NBA_STATS_PROXY")


class AcquisitionError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _endpoint_class(spec: DatasetSpec):
    module = importlib.import_module(f"nba_api.stats.endpoints.{spec.endpoint}")
    return getattr(module, spec.endpoint_class)


def verify_endpoint_parameters(spec: DatasetSpec, kwargs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    endpoint_class = _endpoint_class(spec)
    signature = inspect.signature(endpoint_class.__init__)
    unknown = sorted(set(kwargs) - set(signature.parameters))
    if unknown:
        raise AcquisitionError(
            f"Installed nba_api signature for {spec.endpoint_class} lacks: {', '.join(unknown)}"
        )
    endpoint = endpoint_class(**kwargs)
    package_version = importlib.metadata.version("nba_api")
    schema = {
        name: value for name, value in getattr(endpoint_class, "expected_data", {}).items()
    }
    return dict(endpoint.parameters), {
        "nba_api_version": package_version,
        "endpoint_class": spec.endpoint_class,
        "verified_signature_parameters": sorted(signature.parameters),
        "expected_result_schema": schema,
    }


def _session() -> requests.Session:
    retry = Retry(
        total=1,
        connect=1,
        read=0,
        status=1,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(("GET",)),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2))
    session.mount("http://", HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2))
    session.trust_env = os.getenv("NBA_TRUST_ENV_PROXY", "0") == "1"
    for name in PROXY_ENV_NAMES:
        value = os.getenv(name)
        if value:
            parsed = urlsplit(value)
            if not parsed.scheme or not parsed.hostname:
                raise AcquisitionError(f"{name} is set but is not a valid proxy URL")
            session.proxies.update({"http": value, "https": value})
            break
    return session


def _result_schema(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(sets, dict):
        sets = [sets]
    result = []
    for item in sets:
        headers = item.get("headers", []) if isinstance(item, dict) else []
        result.append({
            "name": item.get("name") if isinstance(item, dict) else None,
            "headers": headers,
            "row_count": len(item.get("rowSet", [])) if isinstance(item, dict) else 0,
        })
    return result


def acquire_dataset(
    dataset: str,
    season: str,
    season_type: str,
    *,
    team_id: str | int | None = None,
    store: ResearchStore | None = None,
    timeout: float = 30,
    force: bool = False,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    spec = get_spec(dataset)
    store = store or ResearchStore()
    paths = store.paths(dataset, season, season_type, team_id=team_id)
    if paths.processed_csv.is_file() and paths.processed_metadata.is_file() and not force:
        return store.read_processed(dataset, season, season_type, team_id=team_id)

    kwargs = spec.nba_kwargs(season, season_type, str(team_id) if team_id is not None else None)
    kwargs["timeout"] = max(1, min(float(timeout), 30))
    params, package_schema = verify_endpoint_parameters(spec, kwargs)
    metadata: dict[str, Any] = {
        "dataset": dataset,
        "season": season,
        "season_type": season_type,
        "team_id": str(team_id) if team_id is not None else None,
        "provider": "nba",
        "source": f"stats.nba.com/{spec.endpoint}",
        "endpoint": spec.endpoint,
        "request_parameters": params,
        "request_started_at": utc_now(),
        "status": "request_started",
        "row_grain": spec.grain,
        "units": "NBA endpoint units; percentage fields are fractions from 0 to 1",
        **package_schema,
    }
    store.write_raw_metadata(paths, metadata)
    client = session or _session()
    try:
        response = client.get(
            f"{NBA_BASE_URL}/{spec.endpoint}",
            params=params,
            timeout=(5, kwargs["timeout"]),
            allow_redirects=False,
        )
        if response.is_redirect or response.is_permanent_redirect:
            raise AcquisitionError("Redirect responses are prohibited")
        response.raise_for_status()
        body = response.content
        payload = response.json()
        if not isinstance(payload, dict):
            raise AcquisitionError("NBA response was not a JSON object")
        schema = _result_schema(payload)
        if not schema or all(item["row_count"] == 0 for item in schema):
            raise AcquisitionError("NBA response contained no rows")
        metadata.update({
            "status": "acquired",
            "retrieved_at": utc_now(),
            "http_status": response.status_code,
            "raw_sha256": hashlib.sha256(body).hexdigest(),
            "raw_byte_count": len(body),
            "response_schema": schema,
        })
        store.write_raw_response(paths, body, metadata)
        return process_nba_payload(payload, spec, season, season_type, team_id=team_id, store=store, raw_metadata=metadata)
    except Exception as exc:
        metadata.update({
            "status": "unavailable",
            "failed_at": utc_now(),
            "error_type": type(exc).__name__,
        })
        store.write_raw_metadata(paths, metadata)
        if isinstance(exc, AcquisitionError):
            raise
        raise AcquisitionError(
            f"Acquisition unavailable for {dataset} {season} {season_type}; "
            f"failure type: {type(exc).__name__}. No dataset was created."
        ) from None


def acquire_many(
    datasets: list[str],
    seasons: list[str],
    season_type: str,
    *,
    team_id: str | int | None = None,
    timeout: float = 30,
    force: bool = False,
    delay_seconds: float = 1.0,
    store: ResearchStore | None = None,
) -> list[dict[str, Any]]:
    store = store or ResearchStore()
    client = _session()
    outcomes: list[dict[str, Any]] = []
    first = True
    for season in seasons:
        for dataset in datasets:
            if not first:
                time.sleep(max(1.0, delay_seconds))
            first = False
            try:
                frame, metadata = acquire_dataset(
                    dataset, season, season_type, team_id=team_id, store=store,
                    timeout=timeout, force=force, session=client,
                )
                outcomes.append({"dataset": dataset, "season": season, "status": metadata["validation_status"], "rows": len(frame)})
            except AcquisitionError as exc:
                outcomes.append({"dataset": dataset, "season": season, "status": "unavailable", "error": str(exc)})
    return outcomes


def import_csv(
    csv_path: str | Path,
    dataset: str,
    season: str,
    season_type: str,
    *,
    provider: str,
    source: str,
    source_url: str | None,
    grain: str,
    keys: list[str],
    row_scope: str,
    store: ResearchStore | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    from .validation import validate_general

    store = store or ResearchStore()
    source_path = Path(csv_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    paths = store.paths(dataset, season, season_type, provider=provider)
    paths.raw_dir.mkdir(parents=True, exist_ok=True)
    raw_copy = paths.raw_dir / "source.csv"
    shutil.copyfile(source_path, raw_copy)
    frame = pd.read_csv(raw_copy)
    frame.columns = [str(column).strip() for column in frame.columns]
    for identity_column in ("PLAYER_ID", "TEAM_ID", "VS_PLAYER_ID"):
        if identity_column in frame.columns:
            frame[identity_column] = frame[identity_column].astype("string")
    frame["SEASON"] = season
    frame["SEASON_TYPE"] = season_type
    frame["ROW_GRAIN"] = grain
    frame["ROW_SCOPE"] = row_scope
    frame["SOURCE_PROVIDER"] = provider
    report = validate_general(frame, keys, required=keys)
    retrieved = utc_now()
    metadata = {
        "dataset": dataset,
        "season": season,
        "season_type": season_type,
        "team_id": None,
        "provider": provider,
        "source": source,
        "source_url": source_url,
        "retrieved_at": retrieved,
        "status": "imported",
        "row_grain": grain,
        "row_scope": row_scope,
        "keys": keys,
        "input_filename": source_path.name,
        "raw_sha256": hashlib.sha256(raw_copy.read_bytes()).hexdigest(),
        "schema_columns": list(frame.columns),
        "units": "As published by the named source; no cross-provider equivalence is implied",
        "benchmark_status": "not_checked",
        **report.as_dict(),
    }
    store.write_raw_metadata(paths, metadata)
    store.write_processed(paths, frame, metadata)
    return frame, metadata


def import_nba_response(
    response_path: str | Path,
    dataset: str,
    season: str,
    season_type: str,
    *,
    source: str,
    source_metadata_path: str | Path | None = None,
    team_id: str | int | None = None,
    store: ResearchStore | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Import a previously captured NBA JSON response without trusting its filename."""
    spec = get_spec(dataset)
    store = store or ResearchStore()
    path = Path(response_path).resolve()
    body = path.read_bytes()
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise AcquisitionError("Imported NBA response must be a JSON object")
    expected_kwargs = spec.nba_kwargs(season, season_type, str(team_id) if team_id is not None else None)
    expected_params, package_schema = verify_endpoint_parameters(spec, expected_kwargs)
    resource = str(payload.get("resource", "")).lower()
    if resource and resource != spec.endpoint:
        raise AcquisitionError(f"Response resource {resource!r} does not match {spec.endpoint!r}")
    actual_params = payload.get("parameters") or {}
    identity_checks = {
        "Season": season,
        "SeasonType": season_type,
        "MeasureType": spec.measure_type,
        "PerMode": spec.per_mode,
    }
    if spec.team_required:
        identity_checks["TeamID"] = int(team_id) if team_id is not None else None
    mismatches = {
        key: {"expected": expected, "actual": actual_params.get(key)}
        for key, expected in identity_checks.items()
        if str(actual_params.get(key)) != str(expected)
    }
    if mismatches:
        raise AcquisitionError(f"Imported NBA response identity mismatch: {mismatches}")
    supplemental: dict[str, Any] | None = None
    supplemental_hash: str | None = None
    if source_metadata_path:
        metadata_path = Path(source_metadata_path).resolve()
        supplemental = json.loads(metadata_path.read_text(encoding="utf-8"))
        supplemental_hash = hashlib.sha256(metadata_path.read_bytes()).hexdigest()
    retrieved = utc_now()
    metadata = {
        "dataset": dataset,
        "season": season,
        "season_type": season_type,
        "team_id": str(team_id) if team_id is not None else None,
        "provider": "nba",
        "source": source,
        "endpoint": spec.endpoint,
        "request_parameters": expected_params,
        "status": "imported_raw_response",
        "retrieved_at": retrieved,
        "original_filename": path.name,
        "raw_sha256": hashlib.sha256(body).hexdigest(),
        "raw_byte_count": len(body),
        "response_schema": _result_schema(payload),
        "source_metadata": supplemental,
        "source_metadata_sha256": supplemental_hash,
        "row_grain": spec.grain,
        "units": "NBA endpoint units; percentage fields are fractions from 0 to 1",
        **package_schema,
    }
    paths = store.paths(dataset, season, season_type, team_id=team_id)
    store.write_raw_response(paths, body, metadata)
    return process_nba_payload(
        payload, spec, season, season_type, team_id=team_id,
        store=store, raw_metadata=metadata,
    )
