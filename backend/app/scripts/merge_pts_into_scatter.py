import pandas as pd

SCATTER = "docs/data/rookie_scatter_final.csv"
API = "docs/data/pts_per_100_api_cache.csv"
BR_2026 = "docs/data/2026_rookies_pp100.csv"
OUT = "docs/data/rookie_scatter_final_fixed.csv"

scatter = pd.read_csv(SCATTER)
api = pd.read_csv(API)

scatter = scatter.merge(
    api,
    on=["player_id", "rookie_season"],
    how="left",
    suffixes=("", "_api")
)

if "pts_per_100_api" in scatter.columns:
    scatter["pts_per_100"] = scatter["pts_per_100_api"].combine_first(scatter.get("pts_per_100"))
    scatter = scatter.drop(columns=["pts_per_100_api"])

br = pd.read_csv(BR_2026).rename(columns={"Player": "player", "PTS▼": "pts_per_100"})
br["rookie_season"] = 2026

scatter = scatter.merge(
    br[["player", "rookie_season", "pts_per_100"]],
    on=["player", "rookie_season"],
    how="left",
    suffixes=("", "_br")
)

if "pts_per_100_br" in scatter.columns:
    scatter["pts_per_100"] = scatter["pts_per_100_br"].combine_first(scatter["pts_per_100"])
    scatter = scatter.drop(columns=["pts_per_100_br"])

scatter.to_csv(OUT, index=False)

print("Saved →", OUT)
print("Missing 2026:",
      scatter.query("rookie_season == 2026 and pts_per_100.isna()", engine="python").shape[0])
