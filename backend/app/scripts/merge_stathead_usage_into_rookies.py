import pandas as pd
import unicodedata

def normalize_name(name):
    if pd.isna(name):
        return None
    name = unicodedata.normalize("NFKD", name)
    name = name.replace("’", "'").replace("–", "-").replace(".", "").strip()
    return name.lower()

rookies = pd.read_csv("docs/data/rookie_scatter_with_2026.csv")
rookies["player_norm"] = rookies["player"].apply(normalize_name)

usage_2025 = pd.read_csv("docs/data/2025_rookies_usage.csv")
usage_2026 = pd.read_csv("docs/data/2026_rookies_usage.csv")
usage = pd.concat([usage_2025, usage_2026], ignore_index=True)

usage = usage.rename(columns={
    "Player": "player",
    "USG%": "usg_pct_stathead",
    "Draft Year": "draft_year"
})

usage["player_norm"] = usage["player"].apply(normalize_name)

# 👇 THIS IS THE FIX
usage["rookie_season"] = usage["draft_year"] + 1

merged = rookies.merge(
    usage[["player_norm", "rookie_season", "usg_pct_stathead"]],
    on=["player_norm", "rookie_season"],
    how="left"
)

merged["usg_pct"] = merged["usg_pct"].fillna(merged["usg_pct_stathead"])
merged = merged.drop(columns=["player_norm", "usg_pct_stathead"])

merged["usg_pct"] = pd.to_numeric(merged["usg_pct"], errors="coerce")

merged.to_csv("docs/data/rookie_scatter_with_usage_v2.csv", index=False)

print("Saved: docs/data/rookie_scatter_with_usage_v2.csv")

print("2025 missing usage:",
      merged.query("rookie_season == 2025 and usg_pct.isna()", engine="python").shape[0])

print("2026 missing usage:",
      merged.query("rookie_season == 2026 and usg_pct.isna()", engine="python").shape[0])
