from nba_api.stats.endpoints import LeagueDashPlayerStats
import pandas as pd
from pathlib import Path
import time

OUT = Path("docs/data/rookie_usage.csv")

SEASONS = [f"{y}-{str(y+1)[-2:]}" for y in range(2000, 2025)]

rows = []

for season in SEASONS:
    print(f"Fetching {season}...")

    df = LeagueDashPlayerStats(
        season=season,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
        measure_type_detailed_defense="Advanced"
    ).get_data_frames()[0]

    print("Columns:", df.columns.tolist())

    df = df.rename(columns=str.upper)

    if "USG_PCT" not in df.columns:
        print(f"⚠️  No USG_PCT for {season}, skipping")
        continue

    df["season"] = int(season[:4])

    df = df[["PLAYER_ID", "season", "USG_PCT"]].copy()
    df = df.rename(columns={"USG_PCT": "usg_pct", "PLAYER_ID": "player_id"})

    rows.append(df)

    time.sleep(0.6)

full = pd.concat(rows, ignore_index=True)

# Load rookies
rookies = pd.read_csv("docs/data/rookie_snapshot.csv")[["player_id", "rookie_season"]]

merged = full.merge(
    rookies,
    left_on=["player_id", "season"],
    right_on=["player_id", "rookie_season"],
    how="inner"
)

merged = merged[["player_id", "season", "usg_pct"]]

# Ensure numeric and convert to percentage points
merged['usg_pct'] = pd.to_numeric(merged['usg_pct']) * 100

OUT.parent.mkdir(parents=True, exist_ok=True)
merged.to_csv(OUT, index=False)

print(f"\n✅ Wrote {len(merged)} rows to {OUT}")
