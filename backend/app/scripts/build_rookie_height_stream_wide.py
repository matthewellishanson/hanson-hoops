# scripts/build_rookie_height_stream_wide.py

import pandas as pd
from pathlib import Path

INPUT = Path(r"C:\Users\mehan\Documents\matthewellishanson.github.io\hanson-hoops\rookies\data\rookie_height_stream.csv")
OUTPUT = Path(r"C:\Users\mehan\Documents\matthewellishanson.github.io\hanson-hoops\rookies\data\rookie_height_stream_wide.csv")

print("Loading long-format CSV...")
df = pd.read_csv(INPUT)

print("Pivoting to wide format...")
wide = (
    df.pivot_table(
        index=["season", "height", "position"],
        columns="stat",
        values="value",
        aggfunc="first"
    )
    .reset_index()
)

wide = wide.rename(columns={
    "height": "height_in",
    "position": "position_group",
    "avg_pick": "draft_number"
})

for col in ["minutes", "count", "draft_number"]:
    if col in wide.columns:
        wide[col] = pd.to_numeric(wide[col], errors="coerce")

wide = wide.sort_values(["season", "height_in", "position_group"])

print(f"Saving → {OUTPUT}")
wide.to_csv(OUTPUT, index=False)
print("Done.")
