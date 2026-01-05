import pandas as pd
from nba_api.stats.endpoints import LeagueDashPlayerStats

SCATTER = "docs/data/rookie_scatter_final.csv"
BR_2026 = "docs/data/2026_rookies_pp100.csv"
OUT = "docs/data/rookie_scatter_final_fixed.csv"

print("Loading scatter...")
scatter = pd.read_csv(SCATTER)

seasons = sorted(scatter["rookie_season"].unique())
api_seasons = [s for s in seasons if s <= 2025]

print("Fetching API seasons:", api_seasons)

all_stats = []

for season in api_seasons:
    season_str = f"{season-1}-{str(season)[-2:]}"
    print("Fetching", season_str)

    stats = LeagueDashPlayerStats(
        season=season_str,
        per_mode_detailed="Per100Possessions"
    ).get_data_frames()[0]

    stats = stats.rename(columns={
        "PLAYER_NAME": "player",
        "PLAYER_ID": "player_id",
        "PTS": "pts_per_100"
    })

    stats["rookie_season"] = season
    all_stats.append(stats[["player_id", "rookie_season", "pts_per_100"]])

api_df = pd.concat(all_stats, ignore_index=True)

print("Merging API data...")
scatter = scatter.merge(
    api_df,
    on=["player_id", "rookie_season"],
    how="left",
    suffixes=("", "_api")
)

if "pts_per_100_api" in scatter.columns:
    scatter["pts_per_100"] = scatter["pts_per_100_api"].combine_first(scatter.get("pts_per_100"))
    scatter = scatter.drop(columns=["pts_per_100_api"])
else:
    print("No pts_per_100_api column created — API data became pts_per_100 directly.")

print("Loading BR 2026...")
br = pd.read_csv(BR_2026)

br = br.rename(columns={
    "Player": "player",
    "PTS▼": "pts_per_100"
})

br["rookie_season"] = 2026

print("Merging BR 2026...")
scatter = scatter.merge(
    br[["player", "rookie_season", "pts_per_100"]],
    on=["player", "rookie_season"],
    how="left",
    suffixes=("", "_br")
)

if "pts_per_100_br" in scatter.columns:
    scatter["pts_per_100"] = scatter["pts_per_100_br"].combine_first(scatter.get("pts_per_100"))
    scatter = scatter.drop(columns=["pts_per_100_br"])

scatter.to_csv(OUT, index=False)

print("Saved →", OUT)
print("2026 missing pts_per_100:",
      scatter.query("rookie_season == 2026 and pts_per_100.isna()", engine="python").shape[0])
