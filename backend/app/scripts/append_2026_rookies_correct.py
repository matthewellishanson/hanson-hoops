import pandas as pd
from nba_api.stats.endpoints import LeagueDashPlayerStats

BASE = "docs/data/rookie_scatter_cleaned.csv"
STATHEAD = "docs/data/2026_rookies_usage.csv"
OUT = "docs/data/rookie_scatter_with_2026.csv"

# Load base
base = pd.read_csv(BASE)

# Load Stathead rookies
rookies = pd.read_csv(STATHEAD)
rookies = rookies.rename(columns={"Player": "player", "Draft Year": "draft_year"})
rookies["rookie_season"] = rookies["draft_year"] + 1

rookie_names = set(rookies["player"])

print("Fetching league stats...")
stats = LeagueDashPlayerStats(
    season="2025-26",
    season_type_all_star="Regular Season",
    per_mode_detailed="Per100Possessions"
).get_data_frames()[0]

stats = stats.rename(columns={
    "PLAYER_NAME": "player",
    "PLAYER_ID": "player_id",
    "MIN": "minutes",
    "PTS": "pts_per_100"
})

# Keep only rookies
stats = stats[stats["player"].isin(rookie_names)].copy()
stats["rookie_season"] = 2026

stats = stats[["player", "rookie_season", "minutes", "pts_per_100", "player_id"]]

# Append
merged = pd.concat([base, stats], ignore_index=True)

merged.to_csv(OUT, index=False)

print("Saved →", OUT)
print("2026 rookies:", merged.query("rookie_season == 2026").shape[0])
