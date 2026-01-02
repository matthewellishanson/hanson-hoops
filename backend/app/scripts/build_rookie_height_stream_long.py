# scripts/build_rookie_height_stream_long.py

import pandas as pd
from pathlib import Path

OUT_PATH = Path(
    r"C:\Users\mehan\Documents\matthewellishanson.github.io\hanson-hoops\rookies\data\rookie_height_stream.csv"
)

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

print("Loading rookie snapshot...")
df = pd.read_csv("app/cache/rookie_snapshot.csv")

# Use raw height
df["height_bucket"] = df["height_in"]

rows = []

for (season, height, pos), g in df.groupby(["rookie_season", "height_bucket", "position"]):
    rows.append({
        "season": season,
        "height": height,
        "position": pos,
        "stat": "minutes",
        "value": g["minutes"].sum()
    })
    rows.append({
        "season": season,
        "height": height,
        "position": pos,
        "stat": "count",
        "value": g.shape[0]
    })
    rows.append({
        "season": season,
        "height": height,
        "position": pos,
        "stat": "avg_pick",
        "value": g["draft_number"].mean()
    })

out = pd.DataFrame(rows)
out.to_csv(OUT_PATH, index=False)

print(f"Saved → {OUT_PATH}")
