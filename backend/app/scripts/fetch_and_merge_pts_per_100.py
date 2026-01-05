import time
import pandas as pd
from nba_api.stats.endpoints import LeagueDashPlayerStats

INPUT = "docs/data/rookie_scatter_final.csv"
OUTPUT = "docs/data/rookie_scatter_final_fixed.csv"

print("Loading scatter data...")
scatter = pd.read_csv(INPUT)

# Determine all seasons we need
seasons = sorted(scatter["rookie_season"].dropna().astype(int).unique())

print(f"Found seasons: {seasons}")

all_stats = []

for year in seasons:
    season_str = f"{year}-{str(year+1)[-2:]}"
    print(f"Fetching {season_str}...")

    try:
        stats = LeagueDashPlayerStats(
            season=season_str,
            per_mode_detailed="Per100Possessions",
            season_type_all_star="Regular Season",
            timeout=60
        ).get_data_frames()[0]

        stats = stats[["PLAYER_ID", "PLAYER_NAME", "PTS"]].copy()
        stats["rookie_season"] = year
        stats = stats.rename(columns={"PTS": "pts_per_100"})

        all_stats.append(stats)

        time.sleep(1.2)

    except Exception as e:
        print(f"⚠️ Failed on {season_str}: {e}")

stats_df = pd.concat(all_stats, ignore_index=True)

print("Merging into scatter...")
scatter = scatter.drop(columns=["pts_per_100"], errors="ignore")

scatter = scatter.merge(
    stats_df,
    left_on=["player_id", "rookie_season"],
    right_on=["PLAYER_ID", "rookie_season"],
    how="left"
)

scatter = scatter.drop(columns=["PLAYER_ID", "PLAYER_NAME"])

scatter.to_csv(OUTPUT, index=False)

print(f"Saved cleaned file to {OUTPUT}")
print(scatter["pts_per_100"].describe())
