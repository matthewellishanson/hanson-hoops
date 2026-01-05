import pandas as pd

SCATTER = "docs/data/rookie_scatter_final.csv"
MINUTES = "docs/data/true_total_minutes.csv"
OUT = "docs/data/rookie_scatter_final.csv"  # overwrite in place

scatter = pd.read_csv(SCATTER)
minutes = pd.read_csv(MINUTES)

merged = scatter.merge(
    minutes,
    on=["player_id", "rookie_season"],
    how="left",
    suffixes=("", "_true")
)

merged["minutes"] = merged["minutes_true"].combine_first(merged["minutes"])
merged = merged.drop(columns=["minutes_true"])

merged.to_csv(OUT, index=False)

print(f"Updated minutes saved → {OUT}")
print("Missing minutes after merge:", merged["minutes"].isna().sum())
print(merged["minutes"].describe())
