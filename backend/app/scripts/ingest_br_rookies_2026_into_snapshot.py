"""
Ingest 2025-26 rookies from a Basketball Reference export into the
canonical snapshot at app/cache/rookie_snapshot.csv.

Rules:
- Filter BR rows where Draft Year == 2025 or Season == 2025-26
- Map BR stats to snapshot schema and compute pct fields if missing
- Merge only rookie_season == 2026 rows (idempotent)
- Do not overwrite the snapshot without first writing a backup
- Log unmatched names between BR and existing snapshot 2026 rows
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Set
import unicodedata

import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = BACKEND_DIR / "app" / "cache" / "rookie_snapshot.csv"
DOCS_SNAPSHOT_PATH = BACKEND_DIR / "docs" / "data" / "rookie_snapshot.csv"
BR_DEFAULT = BACKEND_DIR / "docs" / "data" / "rookies_2026_BR.csv"

REQUIRED_SNAPSHOT_COLUMNS = [
    "player_id",
    "player",
    "draft_year",
    "rookie_season",
    "age",
    "height_in",
    "weight_lbs",
    "position",
    "games",
    "minutes",
    "mpg",
    "fga",
    "fgm",
    "fg_pct",
    "fg3a",
    "fg3m",
    "fg3_pct",
    "fta",
    "ftm",
    "ft_pct",
]

BR_REQUIRED_COLUMNS = [
    "Player",
    "Pos",
    "G",
    "MP",
    "FG",
    "FGA",
    "3P",
    "3PA",
    "FT",
    "FTA",
    "Draft Year",
    "Season",
]


def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    name = name.lower()
    name = re.sub(r"[^a-z ]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def require_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {missing}")


def backup_snapshot(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = path.with_name(f"{path.stem}.bak.{ts}{path.suffix}")
    shutil.copy(path, backup)
    print(f"Backup written to {backup}")
    return backup


def load_br_data(br_path: Path) -> pd.DataFrame:
    print(f"Loading BR export from {br_path}")
    br = pd.read_csv(br_path)
    require_columns(br, BR_REQUIRED_COLUMNS, "BR export")

    # Filter for 2026 class
    season_str = br["Season"].astype(str).str.strip()
    draft_year_str = br["Draft Year"].astype(str).str.strip()
    mask = (draft_year_str == "2025") | season_str.str.contains(r"2025-?26")
    br = br[mask].copy()

    rename_map = {
        "Player": "player",
        "Pos": "position",
        "G": "games",
        "MP": "minutes",
        "FG": "fgm",
        "FGA": "fga",
        "3P": "fg3m",
        "3PA": "fg3a",
        "FT": "ftm",
        "FTA": "fta",
        "FG%": "fg_pct",
        "3P%": "fg3_pct",
        "FT%": "ft_pct",
        "Draft Year": "draft_year",
        "Age": "age",
    }
    br = br.rename(columns=rename_map)

    numeric_cols = ["games", "minutes", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "fg_pct", "fg3_pct", "ft_pct"]
    for col in numeric_cols:
        if col in br.columns:
            br[col] = pd.to_numeric(br[col], errors="coerce")

    br["draft_year"] = pd.to_numeric(br["draft_year"], errors="coerce")
    br["rookie_season"] = 2026
    br["player_norm"] = br["player"].apply(normalize_name)

    def compute_pct(num, den):
        return num / den.where(den != 0)

    if "fg_pct" not in br.columns or br["fg_pct"].isna().all():
        br["fg_pct"] = compute_pct(br["fgm"], br["fga"])
    if "fg3_pct" not in br.columns or br["fg3_pct"].isna().all():
        br["fg3_pct"] = compute_pct(br["fg3m"], br["fg3a"])
    if "ft_pct" not in br.columns or br["ft_pct"].isna().all():
        br["ft_pct"] = compute_pct(br["ftm"], br["fta"])

    br["mpg"] = br.apply(
        lambda r: (r["minutes"] / r["games"]) if pd.notna(r["minutes"]) and pd.notna(r["games"]) and r["games"] else pd.NA,
        axis=1,
    )

    for col in ["age", "height_in", "weight_lbs", "player_id"]:
        if col not in br.columns:
            br[col] = pd.NA

    br = br[
        ["player_id", "player", "player_norm", "draft_year", "rookie_season", "age", "height_in", "weight_lbs", "position", "games", "minutes", "mpg", "fga", "fgm", "fg_pct", "fg3a", "fg3m", "fg3_pct", "fta", "ftm", "ft_pct"]
    ].copy()

    print(f"BR rows after filter: {len(br)}")
    return br


def merge_br_into_snapshot(snapshot_path: Path, br: pd.DataFrame) -> pd.DataFrame:
    print(f"Loading snapshot from {snapshot_path}")
    snap = pd.read_csv(snapshot_path)
    require_columns(snap, REQUIRED_SNAPSHOT_COLUMNS, "Snapshot")

    snap["player_norm"] = snap["player"].apply(normalize_name)

    base = snap[snap["rookie_season"] == 2026].copy()
    base["player_norm"] = base["player_norm"].fillna("")
    others = snap[snap["rookie_season"] != 2026].copy()

    snap_norms: Set[str] = set(base["player_norm"])
    br_norms: Set[str] = set(br["player_norm"])

    unmatched_br = sorted(br_norms - snap_norms)
    unmatched_snap = sorted(snap_norms - br_norms)

    if unmatched_br:
        print(f"BR names not in snapshot (count {len(unmatched_br)}): {unmatched_br}")
    if unmatched_snap:
        print(f"Snapshot 2026 names not in BR (count {len(unmatched_snap)}): {unmatched_snap}")

    updates = 0
    for _, row in br.iterrows():
        norm = row["player_norm"]
        mask = base["player_norm"] == norm
        if mask.any():
            idx = base.index[mask][0]
            for col in REQUIRED_SNAPSHOT_COLUMNS:
                if col in row and pd.notna(row[col]):
                    base.at[idx, col] = row[col]
            updates += 1
        else:
            new_row = {col: pd.NA for col in snap.columns}
            for col in REQUIRED_SNAPSHOT_COLUMNS:
                if col in row:
                    new_row[col] = row[col]
            new_row["player"] = row["player"]
            new_row["rookie_season"] = 2026
            new_row["player_norm"] = norm
            base = pd.concat([base, pd.DataFrame([new_row])], ignore_index=True)

    base = base.drop_duplicates(subset=["rookie_season", "player_norm"], keep="last")
    base = base.drop(columns=["player_norm"])
    others = others.drop(columns=["player_norm"], errors="ignore")

    final = pd.concat([others, base], ignore_index=True)

    print(f"Updated {updates} existing rows; total 2026 rows now {base.shape[0]}")
    print(f"Final snapshot row count: {final.shape[0]}")
    return final


def main(br_path: Path = BR_DEFAULT, snapshot_path: Path = SNAPSHOT_PATH) -> None:
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot not found at {snapshot_path}")
    if not br_path.exists():
        raise FileNotFoundError(f"BR export not found at {br_path}")

    backup_snapshot(snapshot_path)
    br_df = load_br_data(br_path)
    final = merge_br_into_snapshot(snapshot_path, br_df)
    final.to_csv(snapshot_path, index=False)
    final.to_csv(DOCS_SNAPSHOT_PATH, index=False)
    print(f"Snapshot saved to {snapshot_path}")


if __name__ == "__main__":
    main()
