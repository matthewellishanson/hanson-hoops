import pandas as pd
from pathlib import Path

OUT = Path("docs/data/rookie_points_scatter.csv")

df = pd.read_csv("app/cache/rookie_snapshot.csv")

# Ensure numeric
for c in ["minutes", "pts", "pace"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# Filter: rookie seasons in last 25 years
max_season = df["rookie_season"].max()
df = df[df["rookie_season"] >= max_season - 24]

# Filter: minimum minutes
df = df[df["minutes"] >= 300]

# Compute possessions and points per 100
df["possessions"] = df["minutes"] * df["pace"] / 48
df["pts_per_100"] = df["pts"] / df["possessions"] * 100

out = df[[
    "player_id",
    "player",
    "rookie_season",
    "position",
    "minutes",
    "pts_per_100"
]].copy()

out = out.rename(columns={"rookie_season": "season"})

print("Sanity check:")
print(out.describe())

out.to_csv(OUT, index=False)
print("Saved:", OUT)
