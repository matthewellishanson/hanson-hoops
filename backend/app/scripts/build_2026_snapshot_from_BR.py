import pandas as pd

SNAP = "docs/data/rookie_snapshot.csv"
BR   = "docs/data/rookies_2026_BR.csv"
OUT  = SNAP

print("Loading snapshot...")
snap = pd.read_csv(SNAP)

print("Removing existing 2026 rows...")
snap = snap[snap["rookie_season"] != 2026].copy()

print("Loading BR rookies...")
br = pd.read_csv(BR)

# Normalize column names
br = br.rename(columns={
    "Player": "player",
    "MP": "minutes",
    "G": "games",
    "Pos": "position",
    "Season": "season",
    "Draft Year": "draft_year"
})

# Force rookie season
br["rookie_season"] = 2026

# Normalize height if present (inches)
if "Ht" in br.columns:
    br["height_in"] = br["Ht"].str.replace("-", ".").astype(float)

# Select only snapshot columns
cols = [
    "player",
    "draft_year",
    "rookie_season",
    "age",
    "height_in",
    "weight_lbs",
    "position",
    "games",
    "minutes"
]

for c in cols:
    if c not in br.columns:
        br[c] = pd.NA

br = br[cols].copy()

final = pd.concat([snap, br], ignore_index=True)

final.to_csv(OUT, index=False)

print("Saved fixed snapshot.")
print("2026 rows:", final.query("rookie_season == 2026").shape[0])
