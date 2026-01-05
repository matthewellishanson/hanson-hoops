import pandas as pd

df = pd.read_csv("docs/data/rookie_scatter_with_2026.csv")

# Remove everything with rookie_season == 2026
df = df[df["rookie_season"] != 2026]

df.to_csv("docs/data/rookie_scatter_cleaned.csv", index=False)

print("Cleaned. Rows left:", df.shape[0])