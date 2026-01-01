# scripts/build_rookie_height_stream_long.py

import pandas as pd
from pathlib import Path

OUT_PATH = Path(
    r"C:\Users\mehan\Documents\matthewellishanson.github.io\hanson-hoops\rookies\data\rookie_height_stream.csv"
)

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv("app/cache/rookie_snapshot.csv")

# bucket heights (optional)
df["height_bucket"] = df["height_in"]

long_rows = []

for (season, height, pos), g in df.groupby(["rookie_season", "height_bucket", "position"]):
    long_rows.append({
        "season": season,
        "height": height,
        "position": pos,
        "stat": "minutes",
        "value": g["minutes"].sum()
    })
    long_rows.append({
        "season": season,
        "height": height,
        "position": pos,
        "stat": "usage",
        "value": g["usg_pct"].mean()
    })
    long_rows.append({
        "season": season,
        "height": height,
        "position": pos,
        "stat": "count",
        "value": g.shape[0]
    })
    long_rows.append({
        "season": season,
        "height": height,
        "position": pos,
        "stat": "avg_pick",
        "value": g["draft_year"].mean()
    })

out = pd.DataFrame(long_rows)
out.to_csv(OUT_PATH, index=False)