import pandas as pd
from pathlib import Path

OUT = Path("docs/data/rookie_scatter_pp100.csv")

df = pd.read_csv("app/cache/rookie_snapshot.csv")

# numeric safety
for c in ["games","minutes","fga","fta","tov","pts","usg_pct"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# filter rookies, minutes, recent seasons
df = df[
    (df["minutes"] >= 300) &
    (df["rookie_season"] >= df["rookie_season"].max() - 25)
].copy()

# Estimate possessions (Basketball-Reference formula)
df["poss_est"] = (
    df.fga +
    0.44 * df.fta +
    df.tov
)

df = df[df.poss_est > 0]

df["pts_per_100"] = 100 * df.pts / df.poss_est

out = df[[
    "player",
    "rookie_season",
    "minutes",
    "usg_pct",
    "pts_per_100",
    "poss_est"
]]

print(out.describe())

out.to_csv(OUT, index=False)
print("Saved:", OUT)
