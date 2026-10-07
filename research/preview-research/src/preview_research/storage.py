from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .config import project_root, season_slug, season_type_slug


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        Path(temporary).replace(path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_bytes(path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))


@dataclass(frozen=True)
class DatasetPaths:
    raw_dir: Path
    processed_csv: Path
    processed_metadata: Path


class ResearchStore:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).resolve() if root else project_root()
        self.raw_root = self.root / "data" / "raw"
        self.processed_root = self.root / "data" / "processed"
        self.exports_root = self.root / "exports"

    def paths(
        self,
        dataset: str,
        season: str,
        season_type: str,
        team_id: str | int | None = None,
        provider: str = "nba",
    ) -> DatasetPaths:
        identity = dataset if team_id is None else f"{dataset}__team_{team_id}"
        relative = Path(provider) / season_slug(season) / season_type_slug(season_type) / identity
        return DatasetPaths(
            raw_dir=self.raw_root / relative,
            processed_csv=self.processed_root / relative.with_suffix(".csv"),
            processed_metadata=self.processed_root / relative.with_suffix(".metadata.json"),
        )

    def write_raw_response(self, paths: DatasetPaths, body: bytes, metadata: dict[str, Any]) -> None:
        _atomic_bytes(paths.raw_dir / "response.json", body)
        _atomic_json(paths.raw_dir / "metadata.json", metadata)

    def write_raw_metadata(self, paths: DatasetPaths, metadata: dict[str, Any]) -> None:
        _atomic_json(paths.raw_dir / "metadata.json", metadata)

    def write_processed(self, paths: DatasetPaths, frame: pd.DataFrame, metadata: dict[str, Any]) -> None:
        paths.processed_csv.parent.mkdir(parents=True, exist_ok=True)
        csv_bytes = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        _atomic_bytes(paths.processed_csv, csv_bytes)
        _atomic_json(paths.processed_metadata, metadata)

    def read_processed(
        self,
        dataset: str,
        season: str,
        season_type: str,
        team_id: str | int | None = None,
        provider: str = "nba",
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        paths = self.paths(dataset, season, season_type, team_id=team_id, provider=provider)
        if not paths.processed_csv.is_file() or not paths.processed_metadata.is_file():
            raise FileNotFoundError(
                f"No cached processed dataset for {dataset}, {season}, {season_type}"
                + (f", team {team_id}" if team_id is not None else "")
            )
        frame = pd.read_csv(paths.processed_csv, dtype={"PLAYER_ID": "string", "TEAM_ID": "string", "VS_PLAYER_ID": "string"})
        metadata = json.loads(paths.processed_metadata.read_text(encoding="utf-8"))
        return frame, metadata

    def metadata_files(self) -> list[Path]:
        if not self.processed_root.exists():
            return []
        return sorted(self.processed_root.rglob("*.metadata.json"))

    def coverage(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for path in self.metadata_files():
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            rows.append({
                "dataset": item.get("dataset"),
                "season": item.get("season"),
                "season_type": item.get("season_type"),
                "team_id": item.get("team_id"),
                "provider": item.get("provider"),
                "rows": item.get("row_count"),
                "status": item.get("validation_status", item.get("status", "unknown")),
                "benchmark": item.get("benchmark_status", "not_checked"),
                "retrieved_at": item.get("retrieved_at"),
            })
        return pd.DataFrame(rows, columns=[
            "dataset", "season", "season_type", "team_id", "provider", "rows",
            "status", "benchmark", "retrieved_at",
        ])


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_json(path, payload)

