from nba_api.stats.endpoints import LeagueDashPlayerStats
import pandas as pd
from pathlib import Path

SNAPSHOT = Path("docs/data/rookie_snapshot.csv")

print("Loading existing snapshot...")
base = pd.read_csv(SNAPSHOT)

season = "2025-26"
season_year = 2026

print(f"Fetching {season} rookies...")

df = LeagueDashPlayerStats(
    season=season,
    season_type_all_star="Regular Season",
    per_mode_detailed="Totals",
    measure_type_detailed_defense="Base"
).get_data_frames()[0]

df.columns = df.columns.str.lower()

# Required columns
keep = {
    "player_id": "player_id",
    "player_name": "player",
    "min": "minutes",
    "pts": "pts",
    "fga": "fga",
    "fta": "fta",
    "tov": "tov"
}

df = df[list(keep.keys())].rename(columns=keep)

# Only players who are not already present
existing_ids = set(base["player_id"])
new = df[~df["player_id"].isin(existing_ids)].copy()

# Add rookie_season
new["rookie_season"] = season_year

print(f"New rookies found: {len(new)}")

# Append
updated = pd.concat([base, new], ignore_index=True)
updated.to_csv(SNAPSHOT, index=False)

print(f"Snapshot now has {len(updated)} rows")
print("Saved:", SNAPSHOT)
