import pandas as pd
import unicodedata

# ---------- helpers ----------
def normalize_name(name):
    if pd.isna(name):
        return None
    name = unicodedata.normalize("NFKD", name)
    name = name.replace("’", "'").replace("–", "-").strip()
    name = name.replace(".", "")
    return name.lower()

# ---------- load ----------
rookies = pd.read_csv("docs/data/rookie_scatter_with_usage.csv")
usage_2025 = pd.read_csv("docs/data/2025_rookies_usage.csv")
usage_2026 = pd.read_csv("docs/data/2026_rookies_usage.csv")

# ---------- prep rookies ----------
rookies["player_norm"] = rookies["player"].apply(normalize_name)

# ---------- prep usage ----------
usage = pd.concat([usage_2025, usage_2026], ignore_index=True)
usage = usage[["Player", "USG%", "Season"]].copy()
usage["player_norm"] = usage["Player"].apply(normalize_name)
usage["rookie_season"] = usage["Season"].str[:4].astype(int)

# rename for merge
usage = usage.rename(columns={"USG%": "usg_pct_stathead"})

# ---------- merge ----------
merged = rookies.merge(
    usage[["player_norm", "rookie_season", "usg_pct_stathead"]],
    on=["player_norm", "rookie_season"],
    how="left"
)

# fill only where missing
merged["usg_pct"] = merged["usg_pct"].fillna(merged["usg_pct_stathead"])

# cleanup
merged = merged.drop(columns=["player_norm", "usg_pct_stathead"])

# ---------- write ----------
merged.to_csv("docs/data/rookie_scatter_with_usage_v2.csv", index=False)

print("Saved: docs/data/rookie_scatter_with_usage_v2.csv")
print("2025 missing usage:", merged.query("rookie_season == 2025 and usg_pct.isna()", engine="python").shape[0])
print("2026 missing usage:", merged.query("rookie_season == 2026 and usg_pct.isna()", engine="python").shape[0])
