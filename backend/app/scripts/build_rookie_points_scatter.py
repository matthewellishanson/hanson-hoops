import pandas as pd
from pathlib import Path

OUT = Path("docs/data/rookie_points_scatter.csv")

df = pd.read_csv("app/cache/rookie_snapshot.csv")

# Ensure numeric
for c in ["minutes", "pts", "fga", "fta", "tov", "rookie_season"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

df = df[df.minutes >= 300].copy()

# Estimate possessions
df["poss"] = df.fga + 0.44 * df.fta + df.tov

# Avoid divide-by-zero
df = df[df.poss > 0]

# Compute pts per 100 possessions
df["pts_per_100"] = 100 * df.pts / df.poss

out = df[[
    "player",
    "rookie_season",
    "minutes",
    "pts",
    "poss",
    "pts_per_100",
    "position"
]]

print(out.describe())

out.to_csv(OUT, index=False)
print("Saved:", OUT)
