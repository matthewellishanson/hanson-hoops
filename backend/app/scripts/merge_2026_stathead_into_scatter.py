import pandas as pd
import unicodedata

BASE = "docs/data/rookie_scatter_with_usage_v2.csv"
STATHEAD = "docs/data/2026_rookies_pp100.csv"
OUT = "docs/data/rookie_scatter_with_usage_v3.csv"

def normalize(name):
    if pd.isna(name):
        return None
    name = unicodedata.normalize("NFKD", name)
    name = name.replace("’", "'").replace("–", "-").replace(".", "").strip()
    return name.lower()

# Load base scatter
base = pd.read_csv(BASE)
base["player_norm"] = base["player"].apply(normalize)

# Drop any existing 2026 rows (we'll replace them)
base = base[base["rookie_season"] != 2026].copy()

# Load Stathead
stat = pd.read_csv(STATHEAD)

stat = stat.rename(columns={
    "Player": "player",
    "PTS▼": "pts_per_100",
    "USG%": "usg_pct_stathead"
})

stat["player_norm"] = stat["player"].apply(normalize)
stat["rookie_season"] = 2026

# Keep only what we need
stat = stat[["player", "player_norm", "rookie_season", "pts_per_100", "usg_pct_stathead"]].copy()

# Merge
merged = base.merge(
    stat[["player_norm", "rookie_season", "pts_per_100", "usg_pct_stathead"]],
    on=["player_norm", "rookie_season"],
    how="outer",
    suffixes=("", "_new")
)

# Prefer stathead values for 2026
merged["pts_per_100"] = merged["pts_per_100_new"].combine_first(merged["pts_per_100"])
merged["usg_pct"] = merged["usg_pct_new"].combine_first(merged["usg_pct"])

merged = merged.drop(columns=[c for c in merged.columns if c.endswith("_new")])

merged = merged.drop(columns=["player_norm"], errors="ignore")

merged.to_csv(OUT, index=False)

print(f"Saved: {OUT}")
print("2026 rows:", merged.query("rookie_season == 2026").shape[0])
print("2026 missing pts_per_100:", merged.query("rookie_season == 2026 and pts_per_100.isna()", engine="python").shape[0])
print("2026 missing usg_pct:", merged.query("rookie_season == 2026 and usg_pct.isna()", engine="python").shape[0])
