import pandas as pd
from pathlib import Path

IN = Path("docs/data/rookie_scatter_with_usage.csv")
OUT = Path("docs/data/rookie_scatter_with_usage.csv")  # overwrite in place

df = pd.read_csv(IN)

print("Before:", df.columns.tolist())

# Drop the empty/useless one
if "usg_pct_x" in df.columns:
    df = df.drop(columns=["usg_pct_x"])

# Rename the good one
if "usg_pct_y" in df.columns:
    df = df.rename(columns={"usg_pct_y": "usg_pct"})

print("After:", df.columns.tolist())
print(df[["usg_pct"]].describe())

df.to_csv(OUT, index=False)
print("Saved cleaned file →", OUT)
