import pandas as pd
from pathlib import Path

INPUT = Path("C:/Users/mehan/Documents/matthewellishanson.github.io/hanson-hoops/rookies/data/rookie_height_stream.csv")
OUTPUT = Path("C:/Users/mehan/Documents/matthewellishanson.github.io/hanson-hoops/rookies/data/rookie_height_stream_wide.csv")

print("Loading long-format CSV...")
df = pd.read_csv(INPUT)

print("Pivoting...")
wide = (
    df.pivot_table(
        index=["season", "height", "position"],
        columns="stat",
        values="value",
        aggfunc="first"
    )
    .reset_index()
)

# Rename to what D3 expects
wide = wide.rename(columns={
    "height": "height_in",
    "avg_pick": "draft_number",
    "position": "position_group"
})

# Ensure numeric
for col in ["minutes", "usage", "draft_number"]:
    if col in wide.columns:
        wide[col] = pd.to_numeric(wide[col], errors="coerce")

# Sort nicely
wide = wide.sort_values(["season", "height_in", "position_group"])

print(f"Saving → {OUTPUT}")
wide.to_csv(OUTPUT, index=False)

print("Done.")
