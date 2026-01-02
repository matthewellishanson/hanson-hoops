import pandas as pd
from pathlib import Path

INPUT = Path("app/cache/rookie_snapshot.csv")
OUTPUT = Path("C:/Users/mehan/Documents/matthewellishanson.github.io/hanson-hoops/rookies/data/rookie_shooting_stream.csv")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

print("Loading rookie snapshot...")
df = pd.read_csv(INPUT)

# Ensure numeric
for col in ["fga","fgm","fg3a","fg3m","fta","ftm"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

rows = []

for (season, pos), g in df.groupby(["rookie_season", "position"]):
    for shot_type in ["fg", "3p", "ft"]:
        if shot_type == "fg":
            att = g["fga"]
            made = g["fgm"]
        elif shot_type == "3p":
            att = g["fg3a"]
            made = g["fg3m"]
        else:
            att = g["fta"]
            made = g["ftm"]

        # Drop players with zero attempts to avoid distortion
        valid = g[att > 0]

        if len(valid) == 0:
            continue

        rows.append({
            "season": season,
            "position_group": pos,
            "shot_type": shot_type,
            "metric": "attempts",
            "value": valid[att.name].mean()
        })
        rows.append({
            "season": season,
            "position_group": pos,
            "shot_type": shot_type,
            "metric": "makes",
            "value": valid[made.name].mean()
        })
        rows.append({
            "season": season,
            "position_group": pos,
            "shot_type": shot_type,
            "metric": "pct",
            "value": (valid[made.name].sum() / valid[att.name].sum()) if valid[att.name].sum() > 0 else None
        })

out = pd.DataFrame(rows)
out = out.sort_values(["season","position_group","shot_type","metric"])

print(f"Saving → {OUTPUT}")
out.to_csv(OUTPUT, index=False)
print("Done.")
