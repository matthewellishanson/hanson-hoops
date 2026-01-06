"""
Backfill height_in for 2026 rookies using a BR export with heights in feet-inches.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = BACKEND_DIR / "app" / "cache" / "rookie_snapshot.csv"
DOCS_SNAPSHOT_PATH = BACKEND_DIR / "docs" / "data" / "rookie_snapshot.csv"
HEIGHTS_PATH = BACKEND_DIR / "docs" / "data" / "rookies_2026_heights.csv"

REQUIRED_HEIGHT_COLS = ["Player", "Ht"]


def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    name = name.lower()
    name = re.sub(r"[^a-z ]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def height_to_inches(ht: str) -> float | None:
    if not isinstance(ht, str):
        return None
    if "-" not in ht:
        return None
    try:
        feet, inches = ht.split("-")
        return int(feet) * 12 + int(inches)
    except Exception:
        return None


def require_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def main(
    snapshot_path: Path = SNAPSHOT_PATH,
    heights_path: Path = HEIGHTS_PATH,
    docs_snapshot_path: Path = DOCS_SNAPSHOT_PATH,
) -> None:
    snap = pd.read_csv(snapshot_path)
    snap["player_norm"] = snap["player"].apply(normalize_name)

    heights = pd.read_csv(heights_path)
    require_columns(heights, REQUIRED_HEIGHT_COLS, "Heights CSV")

    heights["player_norm"] = heights["Player"].apply(normalize_name)
    heights["height_in"] = heights["Ht"].apply(height_to_inches)
    heights = heights.dropna(subset=["height_in"])

    h_map = dict(zip(heights["player_norm"], heights["height_in"]))

    mask_2026 = snap["rookie_season"] == 2026
    snap.loc[mask_2026, "height_in"] = snap.loc[mask_2026, "player_norm"].map(h_map)

    updated = snap.drop(columns=["player_norm"])
    updated.to_csv(snapshot_path, index=False)
    updated.to_csv(docs_snapshot_path, index=False)

    missing = snap.loc[mask_2026 & snap["height_in"].isna(), "player"].tolist()
    print(f"Updated heights for {mask_2026.sum() - len(missing)} players. Missing: {missing}")


if __name__ == "__main__":
    main()
