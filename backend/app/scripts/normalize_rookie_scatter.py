import pandas as pd

IN = "docs/data/rookie_scatter_with_usage_v2.csv"
OUT = "docs/data/rookie_scatter_final.csv"

df = pd.read_csv(IN)

# Normalize usage
df["usg_pct"] = pd.to_numeric(df["usg_pct"], errors="coerce")
mask = df["usg_pct"] < 1
df.loc[mask, "usg_pct"] = df.loc[mask, "usg_pct"] * 100

# Numeric hygiene
for c in ["minutes", "pts_per_100", "poss_est"]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

df.to_csv(OUT, index=False)

print("Saved →", OUT)
print("Rows:", len(df))
print("2026 rows:", df.query("rookie_season == 2026").shape[0])
print(df.query("rookie_season == 2026")[["player","minutes","usg_pct"]].head())
