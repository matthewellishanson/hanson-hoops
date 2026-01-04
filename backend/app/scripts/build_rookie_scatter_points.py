import pandas as pd
from pathlib import Path

OUT = Path("docs/data/rookie_scatter_points.csv")

df = pd.read_csv("docs/data/rookie_snapshot.csv")

# Ensure numeric
for c in ["minutes", "pts", "usg_pct"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# Filter
df = df[df.minutes >= 300].copy()
df = df.dropna(subset=["pts", "minutes", "usg_pct"])

# Compute pts per 36 minutes
df["pts_per_36"] = df.pts / df.minutes * 36

out = df[[
    "player", "player_id", "rookie_season",
    "pts_per_36", "usg_pct", "minutes", "position"
]].copy()

out = out.rename(columns={"rookie_season": "season"})

OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT, index=False)

print("Saved:", OUT)
print(out.describe())
