from __future__ import annotations

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path

import pandas as pd

PACKAGE_CACHE_ROOT = Path(__file__).resolve().parents[1] / "cache" / "snapshots"
RUNTIME_CACHE_ROOT = Path(
    os.getenv("NBA_RUNTIME_CACHE_DIR", str(Path(tempfile.gettempdir()) / "hanson-hoops-cache"))
)


def _season_filename(season: str) -> str:
    return season.replace("/", "-").replace("\\", "-")


def _fit_paths(season: str, model_version: str) -> tuple[Path, Path]:
    filename = f"{_season_filename(season)}-player-pool.csv"
    return (
        RUNTIME_CACHE_ROOT / "fit" / model_version / filename,
        PACKAGE_CACHE_ROOT / "fit" / model_version / filename,
    )


def load_fit_pool(season: str, model_version: str) -> tuple[pd.DataFrame | None, str | None]:
    for path, source in zip(_fit_paths(season, model_version), ("runtime_cache", "packaged_snapshot")):
        if not path.is_file():
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if not frame.empty:
            return frame, source
    combined_path = PACKAGE_CACHE_ROOT / "fit" / model_version / "player-pools.csv.gz"
    if combined_path.is_file():
        try:
            combined = _combined_fit_pools(model_version)
            frame = combined[combined["season"].astype(str) == str(season)].copy()
        except Exception:
            frame = pd.DataFrame()
        if not frame.empty:
            return frame.drop(columns=["season"], errors="ignore"), "packaged_snapshot"
    return None, None


@lru_cache(maxsize=2)
def _combined_fit_pools(model_version: str) -> pd.DataFrame:
    path = PACKAGE_CACHE_ROOT / "fit" / model_version / "player-pools.csv.gz"
    return pd.read_csv(path, dtype={"season": "string"})


def save_runtime_fit_pool(season: str, model_version: str, frame: pd.DataFrame) -> None:
    try:
        path = _fit_paths(season, model_version)[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        frame.to_csv(temp_path, index=False)
        temp_path.replace(path)
    except OSError:
        # Cache persistence must never turn a successful upstream read into a 500.
        return


def load_player_snapshot(player_id: str) -> dict | None:
    path = PACKAGE_CACHE_ROOT / "players.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    record = payload.get("players", {}).get(str(player_id))
    return record if isinstance(record, dict) else None


def _player_season_paths(season: str) -> tuple[Path, Path, Path]:
    root = PACKAGE_CACHE_ROOT / "player-seasons"
    stem = _season_filename(season)
    return (
        root / f"{stem}-profiles.csv.gz",
        root / f"{stem}-shots.csv.gz",
        root / f"{stem}-metadata.json",
    )


@lru_cache(maxsize=1)
def _coverage_manifest() -> dict:
    try:
        payload = json.loads((PACKAGE_CACHE_ROOT / "coverage.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def comparison_coverage() -> dict:
    return _coverage_manifest()


@lru_cache(maxsize=8)
def _player_season_metadata(season: str) -> dict:
    metadata_path = _player_season_paths(season)[2]
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = _coverage_manifest()
        return {"generated_at": manifest.get("generated_at"), "season": season}
    return payload if isinstance(payload, dict) else {}


@lru_cache(maxsize=8)
def _player_profiles(season: str) -> pd.DataFrame | None:
    combined_path = PACKAGE_CACHE_ROOT / "player-seasons" / "profiles.csv.gz"
    if combined_path.is_file():
        try:
            combined = _combined_player_profiles()
            return combined[combined["season"].astype(str) == str(season)].copy()
        except Exception:
            pass
    profile_path = _player_season_paths(season)[0]
    if not profile_path.is_file():
        return None
    try:
        frame = pd.read_csv(profile_path, dtype={"player_id": "string", "jersey": "string"})
    except Exception:
        return None
    return frame if not frame.empty else None


@lru_cache(maxsize=1)
def _combined_player_profiles() -> pd.DataFrame:
    path = PACKAGE_CACHE_ROOT / "player-seasons" / "profiles.csv.gz"
    return pd.read_csv(
        path,
        dtype={"season": "string", "player_id": "string", "jersey": "string"},
    )


def load_player_season_profile(player_id: str, season: str) -> tuple[dict | None, dict]:
    frame = _player_profiles(season)
    metadata = _player_season_metadata(season)
    if frame is None or "player_id" not in frame.columns:
        return None, metadata
    match = frame[frame["player_id"].astype(str) == str(player_id)]
    if match.empty:
        return None, metadata
    record = {
        key: (None if pd.isna(value) else value)
        for key, value in match.iloc[0].to_dict().items()
    }
    return record, metadata


@lru_cache(maxsize=4)
def _player_shots(season: str) -> pd.DataFrame | None:
    shot_path = _player_season_paths(season)[1]
    if not shot_path.is_file():
        return None
    try:
        frame = pd.read_csv(shot_path, dtype={"PLAYER_ID": "string"})
    except Exception:
        return None
    # An empty but present season snapshot is authoritative: it means no shots
    # were recorded, not that the NBA endpoint should be queried at request time.
    return frame


def load_player_shot_snapshot(
    player_id: str, season: str
) -> tuple[pd.DataFrame | None, dict]:
    frame = _player_shots(season)
    metadata = _player_season_metadata(season)
    if frame is None or "PLAYER_ID" not in frame.columns:
        return None, metadata
    return frame[frame["PLAYER_ID"].astype(str) == str(player_id)].copy(), metadata


def load_season_shot_snapshot(season: str) -> tuple[pd.DataFrame | None, dict]:
    return _player_shots(season), _player_season_metadata(season)


@lru_cache(maxsize=1)
def _combined_team_profiles() -> pd.DataFrame:
    path = PACKAGE_CACHE_ROOT / "team-seasons" / "profiles.csv.gz"
    return pd.read_csv(path, dtype={"season": "string", "team_id": "string"})


def load_team_season_profile(team_id: str, season: str) -> tuple[dict | None, dict]:
    path = PACKAGE_CACHE_ROOT / "team-seasons" / "profiles.csv.gz"
    if not path.is_file():
        return None, {}
    try:
        frame = _combined_team_profiles()
    except Exception:
        return None, {}
    match = frame[
        (frame["season"].astype(str) == str(season))
        & (frame["team_id"].astype(str) == str(team_id))
    ]
    if match.empty:
        return None, _coverage_manifest()
    record = {key: (None if pd.isna(value) else value) for key, value in match.iloc[0].to_dict().items()}
    return record, _coverage_manifest()
