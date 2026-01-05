import pandas as pd
from pathlib import Path

IN = Path("docs/data/rookie_scatter_with_usage_v2.csv")
OUT = Path("docs/data/rookie_scatter_with_usage_v3.csv")

df = pd.read_csv(IN)

# Detect any values that look like percentages (> 1.0)
mask = df["usg_pct"] > 1

print("Rows to normalize:", mask.sum())

df.loc[mask, "usg_pct"] = df.loc[mask, "usg_pct"] / 100

df.to_csv(OUT, index=False)

print(f"Saved normalized file → {OUT}")
print(df["usg_pct"].describe())
