import pandas as pd
from pathlib import Path

STREAM_PATH = Path("C:/Users/mehan/Documents/matthewellishanson.github.io/hanson-hoops/rookies/data/rookie_height_stream_wide.csv")
SNAPSHOT_PATH = Path("app/cache/rookie_snapshot.csv")
OUT_PATH = Path("C:/Users/mehan/Documents/matthewellishanson.github.io/hanson-hoops/rookies/data/rookie_height_stream_wide.csv")

print("Loading stream...")
stream = pd.read_csv(STREAM_PATH)

print("Loading rookie_snapshot...")
snap = pd.read_csv(SNAPSHOT_PATH)

# Normalize column names
snap = snap.rename(columns={
    "rookie_season": "season",
    "height_in": "height_in",
    "position": "position_group",
    "usg_pct": "usage"
})

# Drop missing usage
snap = snap.dropna(subset=["usage"])

# Aggregate usage by group
usage_by_group = (
    snap.groupby(["season", "height_in", "position_group"])["usage"]
    .mean()
    .reset_index()
)

print("Merging usage...")
merged = stream.merge(
    usage_by_group,
    on=["season", "height_in", "position_group"],
    how="left"
)

print("Saving...")
merged.to_csv(OUT_PATH, index=False)

print("Done.")
