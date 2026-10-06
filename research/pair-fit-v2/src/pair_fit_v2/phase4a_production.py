"""Pair Fit v2 production acquisition and deterministic packaging.

Phase 4A is deliberately limited to the frozen Ridge product contract.  It
does not compare models, calculate a new performance verdict, or integrate
with the application backend/frontend.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import requests
import numpy as np
from requests.adapters import HTTPAdapter
from sklearn.linear_model import Ridge
from urllib3.util.retry import Retry

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS
from pair_fit_v2 import phase3b_curation as phase3b
from pair_fit_v2 import phase3d_model_refinement as phase3d


VERSION = "phase4a.production-package.v1"
MODEL_VERSION = "pair-fit-v2.0.0"
REQUIRED_BRANCH = "research/pair-fit-v2"
REQUIRED_HEAD = "77fb75ae0fc82fdb01bf3bc1f492769843fe658e"
PROFILE_SEASON = "2025-26"
PACKAGE_FILENAMES = frozenset({
    "artifact_manifest.json", "metadata.json", "model.json", "player_profiles.csv",
})
ENDPOINT = "leaguedashplayerstats"
RESULT_SET = "LeagueDashPlayerStats"
URL = "https://stats.nba.com/stats/leaguedashplayerstats"
TIMEOUT_SECONDS = 30
MINIMUM_SPACING_SECONDS = 1.0

PLAYER_PARAMETERS = {
    "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
    "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "",
    "GameSegment": "", "Height": "", "LastNGames": "0", "LeagueID": "00",
    "Location": "", "MeasureType": "Base", "Month": "0", "OpponentTeamID": "0",
    "Outcome": "", "PORound": "", "PaceAdjust": "N", "Period": "0",
    "PlayerExperience": "", "PlayerPosition": "", "PlusMinus": "N", "Rank": "N",
    "Season": PROFILE_SEASON, "SeasonSegment": "", "SeasonType": "Regular Season",
    "ShotClockRange": "", "StarterBench": "", "TeamID": "", "TwoWay": "",
    "VsConference": "", "VsDivision": "", "Weight": "",
}
DIRECT_FIELDS = (
    "AGE", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "OREB", "DREB",
    "AST", "TOV", "STL", "BLK", "BLKA", "PF", "PFD", "PTS", "PLUS_MINUS",
)
DERIVED_FIELDS = (
    "effective_field_goal_pct", "true_shooting_pct", "three_point_attempt_rate",
    "free_throw_rate",
)
PER100_REQUIRED = ("PLAYER_ID", "PLAYER_NAME", "GP", "TEAM_COUNT", *DIRECT_FIELDS)
TOTALS_REQUIRED = ("PLAYER_ID", "MIN")
FEATURES = tuple(
    [f"pair_mean.{field}" for field in DIRECT_FIELDS + DERIVED_FIELDS]
    + [f"pair_absolute_difference.{field}" for field in DIRECT_FIELDS + DERIVED_FIELDS]
    + ["pair_traded_history_count"]
)
# Keep execution records below an explicit namespace. A managed-sandbox socket
# denial can be retained beside it without being mistaken for an external API
# attempt (the denial occurs before any connection leaves the host).
ACQUISITION_SUBDIRS = ("external/01-per100possessions", "external/02-totals")


class ProductionError(RuntimeError):
    """Raised when a Phase 4A production contract cannot be satisfied."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_json_bytes(value: bytes) -> Any:
    def reject(token: str) -> None:
        raise ValueError(f"nonfinite JSON token: {token}")
    return json.loads(value.decode("utf-8", errors="strict"), parse_constant=reject)


def _write_once(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise ProductionError(f"write-once record already exists: {path}") from exc


def acquisition_requests() -> list[dict[str, Any]]:
    return [
        {
            "request_id": f"phase4a-{ordinal}-{mode.lower()}",
            "endpoint": ENDPOINT,
            "parameters": {**PLAYER_PARAMETERS, "PerMode": mode},
        }
        for ordinal, mode in (("01", "Per100Possessions"), ("02", "Totals"))
    ]


def _request_paths(evidence_root: Path, ordinal: int) -> dict[str, Path]:
    base = evidence_root / ACQUISITION_SUBDIRS[ordinal]
    return {
        "start": base / "attempt-1-start.json",
        "response": base / "attempt-1-response.bin",
        "outcome": base / "attempt-1-outcome.json",
        "verified": base / "verified-response.json",
        "verification": base / "verification.json",
        "quarantine": base / "quarantine.json",
    }


def _result(payload: Mapping[str, Any]) -> tuple[list[str], list[list[Any]]]:
    result_sets = payload.get("resultSets")
    if not isinstance(result_sets, list) or len(result_sets) != 1:
        raise ProductionError("response must contain exactly one result set")
    result = result_sets[0]
    if not isinstance(result, Mapping) or result.get("name") != RESULT_SET:
        raise ProductionError("LeagueDashPlayerStats result-set identity mismatch")
    headers, rows = result.get("headers"), result.get("rowSet")
    if not isinstance(headers, list) or len(headers) != len(set(headers)) or not all(isinstance(x, str) for x in headers):
        raise ProductionError("invalid LeagueDashPlayerStats headers")
    if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != len(headers) for row in rows):
        raise ProductionError("invalid LeagueDashPlayerStats row set")
    return headers, rows


def _positive_player_id(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("boolean player ID")
    number = int(value)
    if number <= 0 or float(value) != number:
        raise ValueError("invalid player ID")
    return str(number)


def verify_profile_response(body: bytes, request: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = strict_json_bytes(body)
        headers, raw_rows = _result(payload)
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionError(f"invalid response JSON: {exc}") from exc
    required = PER100_REQUIRED if request["parameters"]["PerMode"] == "Per100Possessions" else TOTALS_REQUIRED
    missing = sorted(set(required) - set(headers))
    rows = [dict(zip(headers, row)) for row in raw_rows]
    ids: list[str] = []
    malformed = 0
    for row in rows:
        try:
            ids.append(_positive_player_id(row.get("PLAYER_ID")))
        except (TypeError, ValueError, OverflowError):
            malformed += 1
    duplicates = sum(count - 1 for count in Counter(ids).values() if count > 1)
    invalid_min = 0
    if request["parameters"]["PerMode"] == "Totals":
        for row in rows:
            try:
                value = float(row.get("MIN"))
                invalid_min += int(not math.isfinite(value) or value < 0)
            except (TypeError, ValueError):
                invalid_min += 1
    verification = {
        "version": VERSION,
        "request_identity": {"endpoint": ENDPOINT, "parameters": request["parameters"]},
        "request_identity_sha256": sha256_bytes(canonical_json_bytes({"endpoint": ENDPOINT, "parameters": request["parameters"]})),
        "raw_sha256": sha256_bytes(body),
        "byte_count": len(body),
        "row_count": len(rows),
        "column_names": headers,
        "required_fields": {"names": list(required), "missing": missing, "all_present": not missing},
        "player_ids": {"unique_count": len(set(ids)), "duplicate_count": duplicates, "malformed_or_nonpositive_count": malformed},
        "totals_min": {"required": request["parameters"]["PerMode"] == "Totals", "invalid_count": invalid_min},
    }
    if not rows or missing or malformed or duplicates or invalid_min:
        raise ProductionError(f"profile response failed verification: {verification}")
    return verification


def _create_session() -> requests.Session:
    retry = Retry(total=0, connect=0, read=0, redirect=0, status=0)
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _completed(paths: Mapping[str, Path]) -> bool:
    required = ("start", "response", "outcome", "verified", "verification")
    return all(paths[name].is_file() for name in required) and not paths["quarantine"].exists()


def acquire_2025_26_profiles(
    project_root: Path,
    *,
    session_factory: Callable[[], requests.Session] = _create_session,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Acquire only missing 2025-26 Base Per100/Totals profile identities."""
    evidence_root = project_root / "cache/phase4a/2025-26-player-profiles"
    requests_value = acquisition_requests()
    states = [_completed(_request_paths(evidence_root, i)) for i in range(2)]
    for index, complete in enumerate(states):
        paths = _request_paths(evidence_root, index)
        if not complete and any(path.exists() for path in paths.values()):
            raise ProductionError(f"conflicting acquisition state: {paths['start'].parent}")
    attempted = 0
    last_finished: float | None = None
    session = session_factory()
    try:
        for index, (request, complete) in enumerate(zip(requests_value, states)):
            if complete:
                continue
            if last_finished is not None:
                elapsed = monotonic() - last_finished
                if elapsed < MINIMUM_SPACING_SECONDS:
                    sleeper(MINIMUM_SPACING_SECONDS - elapsed)
            paths = _request_paths(evidence_root, index)
            start = {
                "version": VERSION, "attempt": 1, "started_at_utc": utc_now(),
                "request": request, "transport": {
                    "sequential": True, "trust_env": False, "allow_redirects": False,
                    "timeout_seconds": TIMEOUT_SECONDS, "automatic_retries": 0,
                },
            }
            _write_once(paths["start"], pretty_json_bytes(start))
            attempted += 1
            try:
                response = session.get(URL, params=request["parameters"], timeout=TIMEOUT_SECONDS, allow_redirects=False)
                body = response.content
                _write_once(paths["response"], body)
                outcome = {
                    "version": VERSION, "attempt": 1, "finished_at_utc": utc_now(),
                    "http_status": response.status_code,
                    "redirected": bool(response.is_redirect or response.is_permanent_redirect or 300 <= response.status_code < 400),
                    "automatic_retries": 0, "response_bytes": len(body), "response_sha256": sha256_bytes(body),
                }
                _write_once(paths["outcome"], pretty_json_bytes(outcome))
                if response.status_code != 200 or outcome["redirected"]:
                    raise ProductionError(f"transport failed with HTTP {response.status_code}")
                verification = verify_profile_response(body, request)
                _write_once(paths["verified"], body)
                _write_once(paths["verification"], pretty_json_bytes(verification))
            except Exception as exc:
                quarantine = {"version": VERSION, "failed_at_utc": utc_now(), "request": request, "error": str(exc)}
                if not paths["quarantine"].exists():
                    _write_once(paths["quarantine"], pretty_json_bytes(quarantine))
                raise ProductionError(f"2025-26 profile acquisition failed and was quarantined: {exc}") from exc
            last_finished = monotonic()
    finally:
        session.close()
    ids = []
    verifications = []
    for index, request in enumerate(requests_value):
        paths = _request_paths(evidence_root, index)
        body = paths["verified"].read_bytes()
        verification = verify_profile_response(body, request)
        headers, raw_rows = _result(strict_json_bytes(body))
        ids.append({_positive_player_id(dict(zip(headers, row))["PLAYER_ID"]) for row in raw_rows})
        verifications.append(verification)
    if ids[0] != ids[1]:
        raise ProductionError(f"Per100/Totals player-ID sets differ: {len(ids[0] - ids[1])}/{len(ids[1] - ids[0])}")
    return {
        "version": VERSION,
        "request_count_this_run": attempted,
        "verified_request_count": 2,
        "player_count": len(ids[0]),
        "id_set_equality": True,
        "verifications": verifications,
    }


def _sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ProductionError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def _season_start(season: str) -> int:
    try:
        start_text, end_text = season.split("-")
        start = int(start_text)
        if int(end_text) != (start + 1) % 100:
            raise ValueError
        return start
    except (AttributeError, TypeError, ValueError):
        raise ProductionError(f"invalid season: {season!r}") from None


def _observation_key(row: Mapping[str, Any]) -> str:
    return "|".join((str(row["target_season"]), str(row["team_id"]), str(row["player_1_id"]), str(row["player_2_id"])))


def _finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ProductionError(f"non-numeric {label}") from None
    if not math.isfinite(result):
        raise ProductionError(f"nonfinite {label}")
    return result


def _validate_history(row: Mapping[str, Any]) -> None:
    target = _season_start(str(row["target_season"]))
    missing_count = 0
    for slot in (1, 2):
        missing = str(row[f"player_{slot}_history_missing"])
        profile = str(row.get(f"player_{slot}_history_profile_season", ""))
        gap = str(row.get(f"player_{slot}_history_gap", ""))
        if missing == "1":
            missing_count += 1
            if profile or gap:
                raise ProductionError("missing profile has season or gap")
        elif missing == "0":
            if not profile or not gap or target - _season_start(profile) != int(float(gap)) or int(float(gap)) not in (1, 2, 3):
                raise ProductionError("strict-prior history contract failed")
        else:
            raise ProductionError("invalid history missing flag")
    expected_status = {0: "complete", 1: "one_missing", 2: "both_missing"}[missing_count]
    if str(row["history_status"]) != expected_status or int(float(row["missing_player_count"])) != missing_count:
        raise ProductionError("history status mismatch")


def load_production_population(project_root: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    r0_dir = project_root / "curated/phase3f-r0"
    r3_dir = project_root / "curated/phase3f-r3"
    r0_paths = {
        "staging": r0_dir / "expanded_training_staging.csv",
        "index": r0_dir / "expanded_training_row_index.csv",
        "matrix": r0_dir / "expanded_training_estimator_matrix_unscaled.csv",
        "features": r0_dir / "expanded_feature_manifest.json",
    }
    r3_paths = {
        "staging": r3_dir / "final_test_staging.csv",
        "index": r3_dir / "final_test_row_index.csv",
        "target": r3_dir / "final_test_target_vector.csv",
        "features": r3_dir / "estimator_feature_manifest.json",
    }
    expected_hashes = {
        r0_paths["staging"]: "3fced86922b533b0da2b42748d6c0b8afddef57b1281fe14880b11a446df21b6",
        r0_paths["index"]: "3062b1524e7599dcab32ae1dc419040e7f16f6730308e3a88b18c71293d4c427",
        r0_paths["matrix"]: "a8a2b08daa3c56ccda78d34f77c2a29b7ef7c9e00835e7ab6ac77412ec6f8588",
        r0_paths["features"]: "93693a520151387f0c9fb514ada7324639387a7ae60bae5bba9d2a607a5beb14",
        r3_paths["staging"]: "c7994aceebedf4093e97d3b0b41d28ab69abaebb38f6486d07c82a5125635f06",
        r3_paths["index"]: "b0c2204be4dd67d504cde0e720f3453160416a3e9f838aad6e45273d197225f9",
        r3_paths["target"]: "a258c02992f2006ee083d39b79d328f775d8923157d80f7bed2c73955d276198",
        r3_paths["features"]: "b2ef6f25b18e1b5522c2624c1b0532648ac961c4558114fc8d94e437351564a6",
    }
    for path, expected in expected_hashes.items():
        if _sha256_file(path) != expected:
            raise ProductionError(f"authenticated input hash mismatch: {path}")
    _, r0 = _read_csv(r0_paths["staging"])
    _, r0_index = _read_csv(r0_paths["index"])
    _, r3 = _read_csv(r3_paths["staging"])
    _, r3_index = _read_csv(r3_paths["index"])
    if len(r0) != 29_701 or len(r3) != 2_811 or len(r0_index) != len(r0) or len(r3_index) != len(r3):
        raise ProductionError("production population is not 29,701 + 2,811 rows")
    rows = r0 + r3
    keys: list[str] = []
    seasons = Counter()
    for position, row in enumerate(rows):
        if int(row["player_1_id"]) >= int(row["player_2_id"]):
            raise ProductionError("canonical numeric player order failed")
        eligibility = row.get("eligible_poss_ge_150", "")
        if _finite(row["pair_possessions"], "pair possessions") < 150 or (eligibility and int(float(eligibility)) != 1):
            raise ProductionError("ineligible production row")
        _finite(row["target_net_rating"], "target")
        _validate_history(row)
        key = _observation_key(row)
        reference = r0_index[position] if position < len(r0) else r3_index[position - len(r0)]
        reference_key = reference.get("observation_key") or _observation_key(reference)
        if key != reference_key:
            raise ProductionError("staging/index identity mismatch")
        keys.append(key)
        seasons[row["target_season"]] += 1
        if position >= len(r0):
            if int(float(row.get("direct_full_season_source", "0"))) != 1 or int(float(row.get("recovered_or_window_source", "1"))) != 0:
                raise ProductionError("2025-26 row lacks direct full-season provenance")
        elif "recover" in (row.get("raw_pair_base_path", "") + row.get("raw_pair_advanced_path", "")).lower():
            raise ProductionError("recovered row entered production training")
    if len(rows) != 32_512 or len(keys) != len(set(keys)):
        raise ProductionError("production row count or canonical-key uniqueness failed")
    excluded = {
        ("2024-25", "1610612766"), ("2024-25", "1610612755"),
        ("2025-26", "1610612754"), ("2025-26", "1610612763"),
    }
    if any((row["target_season"], row["team_id"]) in excluded for row in rows):
        raise ProductionError("frozen excluded team-season entered production training")
    feature_docs = [strict_json_bytes(path.read_bytes()) for path in (r0_paths["features"], r3_paths["features"])]
    orders = [doc.get("ordered_estimator_features") for doc in feature_docs]
    if any(order != list(FEATURES) for order in orders):
        raise ProductionError("exact ordered 45-feature identity mismatch")
    identity_bytes = canonical_json_bytes([{"observation_key": key, "target_net_rating": _finite(row["target_net_rating"], "target")} for key, row in zip(keys, rows)])
    return rows, {
        "rows": len(rows), "unique_observation_keys": len(set(keys)),
        "season_counts": dict(sorted(seasons.items())),
        "training_identity_sha256": sha256_bytes(identity_bytes),
        "authenticated_input_sha256": {path.relative_to(project_root).as_posix(): expected for path, expected in expected_hashes.items()},
    }


def _profile_source_map(project_root: Path) -> dict[str, dict[str, dict[str, str]]]:
    cache_root = project_root / "cache"
    _, sources = phase3b._source_provenance(cache_root)
    sources = {season: {mode: dict(value) for mode, value in modes.items()} for season, modes in sources.items()}
    extras = {
        "2023-24": {
            "Per100Possessions": {"relative_path": "live_responses/league_dash_player_stats_2023-24_base_per100possessions.json", "raw_body_hash": "da9ba4375be5522407e908e073a95d51b1a1ede41fe659ef75d07e178f8bbc0a"},
            "Totals": {"relative_path": "phase3a1/raw/league_dash_player_stats_2023-24_base_totals.attempt-1.json", "raw_body_hash": "0a856d37c33218362a0b88fc645b7d609a64a7da0773a1be1368d22d07b54774"},
        },
        "2024-25": {
            "Per100Possessions": {"relative_path": "phase3f-r2a/non-protected-prior-profiles/01-per100possessions/verified-response.json", "raw_body_hash": "047d8c16703647425c2fa23678667595a6b7843b213e7e0c5794562bd96fc9ff"},
            "Totals": {"relative_path": "phase3f-r2a/non-protected-prior-profiles/02-totals/verified-response.json", "raw_body_hash": "3bd21076a2fde4b75ce70023f4c07cc633d811cfe08fce65a1c75bb653dfccd5"},
        },
        "2025-26": {
            "Per100Possessions": {"relative_path": "phase4a/2025-26-player-profiles/external/01-per100possessions/verified-response.json", "raw_body_hash": "8d8c88647a002bc3fddae8de757aea1916b24ffa6dcfbb9e8bde08bdcabd206a"},
            "Totals": {"relative_path": "phase4a/2025-26-player-profiles/external/02-totals/verified-response.json", "raw_body_hash": "eeeb6e6115058e7c86ca1a452e7b47072321e04b7e7e163e75a7828ec14bc03d"},
        },
    }
    sources.update(extras)
    expected_seasons = {f"{year}-{str(year + 1)[2:]}" for year in range(2013, 2026)}
    if set(sources) != expected_seasons:
        raise ProductionError(f"profile season inventory mismatch: {sorted(sources)}")
    return dict(sorted(sources.items()))


def _number_or_none(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _rate(numerator: float | None, denominator: float | None) -> float | None:
    return None if numerator is None or denominator is None or denominator <= 0 else numerator / denominator


def _derived(profile: Mapping[str, Any]) -> dict[str, float | None]:
    fgm, fga = _number_or_none(profile.get("FGM")), _number_or_none(profile.get("FGA"))
    fg3m, fg3a = _number_or_none(profile.get("FG3M")), _number_or_none(profile.get("FG3A"))
    pts, fta = _number_or_none(profile.get("PTS")), _number_or_none(profile.get("FTA"))
    team_count = _number_or_none(profile.get("TEAM_COUNT"))
    traded = None if team_count is None or team_count <= 0 or not team_count.is_integer() else float(team_count > 1)
    return {
        "effective_field_goal_pct": _rate(None if fgm is None or fg3m is None else fgm + 0.5 * fg3m, fga),
        "true_shooting_pct": _rate(pts, None if fga is None or fta is None else 2.0 * (fga + 0.44 * fta)),
        "three_point_attempt_rate": _rate(fg3a, fga), "free_throw_rate": _rate(fta, fga),
        "traded_player_indicator": traded,
    }


def build_profile_rows(project_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cache_root = project_root / "cache"
    sources = _profile_source_map(project_root)
    rows: list[dict[str, Any]] = []
    season_counts: dict[str, int] = {}
    source_hashes: dict[str, str] = {}
    for season, modes in sources.items():
        parsed: dict[str, dict[str, Mapping[str, Any]]] = {}
        for mode in ("Per100Possessions", "Totals"):
            source = modes[mode]
            path = cache_root / source["relative_path"]
            body = path.read_bytes()
            if sha256_bytes(body) != source["raw_body_hash"]:
                raise ProductionError(f"profile source hash mismatch: {season}/{mode}")
            headers, raw_rows = _result(strict_json_bytes(body))
            by_id: dict[str, Mapping[str, Any]] = {}
            for raw in raw_rows:
                item = dict(zip(headers, raw))
                player_id = _positive_player_id(item.get("PLAYER_ID"))
                if player_id in by_id:
                    raise ProductionError(f"duplicate profile ID: {season}/{mode}/{player_id}")
                by_id[player_id] = item
            parsed[mode] = by_id
            source_hashes[f"cache/{source['relative_path']}"] = source["raw_body_hash"]
        if set(parsed["Per100Possessions"]) != set(parsed["Totals"]):
            raise ProductionError(f"Per100/Totals profile ID sets differ: {season}")
        for player_id in sorted(parsed["Per100Possessions"], key=int):
            profile = parsed["Per100Possessions"][player_id]
            total = parsed["Totals"][player_id]
            row: dict[str, Any] = {
                "player_id": player_id, "player_name": str(profile.get("PLAYER_NAME") or ""),
                "source_season": season,
            }
            for field in DIRECT_FIELDS:
                row[field.lower()] = _number_or_none(profile.get(field))
            row.update(_derived(profile))
            row["gp"] = _number_or_none(profile.get("GP"))
            row["total_min"] = _number_or_none(total.get("MIN"))
            row["source_per100_path"] = f"cache/{modes['Per100Possessions']['relative_path']}"
            row["source_per100_sha256"] = modes["Per100Possessions"]["raw_body_hash"]
            row["source_totals_path"] = f"cache/{modes['Totals']['relative_path']}"
            row["source_totals_sha256"] = modes["Totals"]["raw_body_hash"]
            rows.append(row)
        season_counts[season] = len(parsed["Per100Possessions"])
    keys = [(row["source_season"], row["player_id"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ProductionError("profile bundle contains duplicate player-season")
    return rows, {"rows": len(rows), "season_counts": season_counts, "source_sha256": dict(sorted(source_hashes.items()))}


PROFILE_COLUMNS = (
    "player_id", "player_name", "source_season", *(field.lower() for field in DIRECT_FIELDS),
    *DERIVED_FIELDS, "traded_player_indicator", "gp", "total_min",
    "source_per100_path", "source_per100_sha256", "source_totals_path", "source_totals_sha256",
)


def _csv_bytes(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column) for column in columns})
    return stream.getvalue().encode("utf-8")


def _swap_slots(row: Mapping[str, Any]) -> dict[str, Any]:
    swapped = dict(row)
    for key, value in row.items():
        if key.startswith("player_1_"):
            swapped[key] = row.get("player_2_" + key[len("player_1_"):])
        elif key.startswith("player_2_"):
            swapped[key] = row.get("player_1_" + key[len("player_2_"):])
    return swapped


def _build_matrix(rows: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    manifest = phase3b.feature_manifest()
    slot_medians, unique_profiles = phase3d.phase3c.fit_slot_imputer(rows)
    transformed = [phase3d.transform_row(row, slot_medians, "no_shot", manifest=manifest) for row in rows]
    matrix = np.asarray([[np.nan if item[name] is None else item[name] for name in FEATURES] for item in transformed], dtype=np.float64)
    fills: dict[str, float] = {}
    for index, name in enumerate(FEATURES):
        finite = matrix[np.isfinite(matrix[:, index]), index]
        if not len(finite):
            raise ProductionError(f"feature has no finite production values: {name}")
        fills[name] = float(np.median(finite))
        matrix[~np.isfinite(matrix[:, index]), index] = fills[name]
    if matrix.shape != (32_512, 45) or not np.isfinite(matrix).all():
        raise ProductionError("production matrix shape/finiteness mismatch")
    swap_mismatches = 0
    for row, original in zip(rows, transformed):
        if original != phase3d.transform_row(_swap_slots(row), slot_medians, "no_shot", manifest=manifest):
            swap_mismatches += 1
    if swap_mismatches:
        raise ProductionError("slot swap changed symmetric production features")
    means = np.mean(matrix, axis=0)
    scales = np.std(matrix, axis=0, ddof=0)
    scales[scales == 0.0] = 1.0
    if not np.isfinite(means).all() or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ProductionError("invalid production scaler")
    scaled = (matrix - means) / scales
    return scaled, {
        "unique_training_player_season_profiles": unique_profiles,
        "player_slot_medians": {key: float(value) for key, value in sorted(slot_medians.items())},
        "symmetric_feature_fill_values": fills,
        "scaler_means": dict(zip(FEATURES, map(float, means))),
        "scaler_scales": dict(zip(FEATURES, map(float, scales))),
    }, {"slot_swap_rows_checked": len(rows), "slot_swap_mismatches": swap_mismatches}


def _preflight_destination(output: Path) -> None:
    """Permit publication only to an absent or completely empty destination."""
    if not output.exists():
        return
    if not output.is_dir():
        raise ProductionError(f"production destination is not a directory: {output}")
    entries = sorted(output.iterdir(), key=lambda path: path.name)
    if entries:
        inventory = ", ".join(
            f"{path.name}/" if path.is_dir() else path.name
            for path in entries
        )
        raise ProductionError(
            f"production destination must be absent or completely empty; "
            f"found {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}: {inventory}"
        )


def _publish(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_once(path, content)


def build_production_package(project_root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """Fit the one frozen production Ridge and serialize deterministic artifacts."""
    output = output_dir or project_root / "production" / MODEL_VERSION
    _preflight_destination(output)
    rows, population = load_production_population(project_root)
    profile_rows, profiles = build_profile_rows(project_root)
    scaled, preprocessing, symmetry = _build_matrix(rows)
    target = np.asarray([_finite(row["target_net_rating"], "target") for row in rows], dtype=np.float64)
    estimator = Ridge(alpha=3000.0)
    estimator.fit(scaled, target)
    sklearn_predictions = np.asarray(estimator.predict(scaled), dtype=np.float64)
    coefficients = np.asarray(estimator.coef_, dtype=np.float64)
    intercept = float(estimator.intercept_)
    if coefficients.shape != (45,) or not np.isfinite(coefficients).all() or not math.isfinite(intercept):
        raise ProductionError("nonfinite or malformed fitted Ridge state")
    packaged_predictions = scaled @ coefficients + intercept
    max_error = float(np.max(np.abs(sklearn_predictions - packaged_predictions)))
    parity_tolerance = 1e-10
    if max_error > parity_tolerance:
        raise ProductionError(f"packaged/sklearn parity exceeded {parity_tolerance}: {max_error}")
    code_paths = (
        project_root / "src/pair_fit_v2/phase4a_production.py",
        project_root / "src/pair_fit_v2/inference.py",
        project_root / "src/pair_fit_v2/phase4a_cli.py",
    )
    code_identity = {path.relative_to(project_root).as_posix(): _sha256_file(path) for path in code_paths}
    final_result_path = project_root / "curated/phase3f-r4/evaluation_decision.json"
    final_metrics_path = project_root / "curated/phase3f-r4/overall_metrics.json"
    if strict_json_bytes(final_result_path.read_bytes()).get("classification") != "FINAL SCIENTIFIC PASS":
        raise ProductionError("committed final scientific result did not authenticate")
    final_mae = float(strict_json_bytes(final_metrics_path.read_bytes())["ridge_unweighted"]["mae"])
    model = {
        "serialization_version": 1,
        "model_name": "Pair Fit v2", "model_version": MODEL_VERSION,
        "output_definition": "projected shared-court team NET_RATING",
        "training_seasons": {"earliest": "2014-15", "latest": "2025-26"},
        "training_population": {
            "rows": 32_512, "unique_canonical_observation_keys": 32_512,
            "identity_sha256": population["training_identity_sha256"], "weights": "equal",
            "exclusions": ["2024-25 Charlotte", "2024-25 Philadelphia", "2025-26 Indiana", "2025-26 Memphis"],
        },
        "estimator": {"type": "sklearn.linear_model.Ridge", "alpha": 3000.0, "fit_count": 1, "calibrator": None, "ensemble": None},
        "ordered_feature_names": list(FEATURES), "coefficients": list(map(float, coefficients)), "intercept": intercept,
        "preprocessing": preprocessing,
        "history": {"strict_prior": True, "maximum_lookback_seasons": 3, "missing_recorded_before_imputation": True},
        "support": {"target_season_earliest": "2014-15", "target_season_latest": "2026-27", "profile_season_earliest": "2013-14", "profile_season_latest": "2025-26", "cross_season_pairs": "unsupported", "cross_era_projections": "unsupported"},
        "display": {"rounding": "nearest whole NET_RATING point; half away from zero", "positive_sign": True},
        "confidence": {"standard": "both histories found", "lower": "either or both histories missing", "numerical_score": None, "meaning": "history completeness, not probability"},
        "final_test": {
            "mae": final_mae, "public_disclosure": "Typical final-test error: approximately 7.8 points per 100 possessions.",
            "result": "FINAL SCIENTIFIC PASS", "result_path": "curated/phase3f-r4/evaluation_decision.json",
            "result_sha256": _sha256_file(final_result_path), "metrics_path": "curated/phase3f-r4/overall_metrics.json",
            "metrics_sha256": _sha256_file(final_metrics_path),
        },
        "input_sha256": {**population["authenticated_input_sha256"], **profiles["source_sha256"]},
        "creation_code_sha256": code_identity,
    }
    profile_bytes = _csv_bytes(profile_rows, PROFILE_COLUMNS)
    model_bytes = pretty_json_bytes(model)
    metadata = {
        "version": VERSION, "model_version": MODEL_VERSION,
        "population": population, "profiles": {"rows": profiles["rows"], "season_counts": profiles["season_counts"]},
        "preprocessing": {"learned_from_rows": 32_512, "scaled_exactly_once": True, "feature_count": 45, **symmetry},
        "fit": {"estimator": "Ridge", "alpha": 3000.0, "weights": "equal", "fit_count": 1},
        "parity": {"rows": 32_512, "predeclared_absolute_tolerance": parity_tolerance, "maximum_absolute_error": max_error, "passed": True},
        "acquisition": {"season": "2025-26", "request_count": 2, "per100_totals_id_set_equal": True, "player_count": 582},
    }
    metadata_bytes = pretty_json_bytes(metadata)
    payloads = {
        "model.json": model_bytes,
        "player_profiles.csv": profile_bytes,
        "metadata.json": metadata_bytes,
    }
    manifest = {
        "serialization_version": 1, "model_version": MODEL_VERSION,
        "coverage": "all non-manifest regular files in this directory; nonrecursive",
        "files": {name: {"bytes": len(content), "sha256": sha256_bytes(content)} for name, content in sorted(payloads.items())},
    }
    payloads["artifact_manifest.json"] = pretty_json_bytes(manifest)
    if set(payloads) != PACKAGE_FILENAMES:
        raise ProductionError(f"production payload inventory mismatch: {sorted(payloads)}")
    for name, content in payloads.items():
        _publish(output / name, content)
    return {
        "output_dir": str(output), "files": {name: {"bytes": len(content), "sha256": sha256_bytes(content)} for name, content in sorted(payloads.items())},
        "metadata": metadata,
    }
