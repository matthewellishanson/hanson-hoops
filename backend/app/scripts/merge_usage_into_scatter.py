import pandas as pd

scatter = pd.read_csv("docs/data/rookie_scatter_pp100.csv")
usage = pd.read_csv("docs/data/rookie_usage.csv")
snap = pd.read_csv("docs/data/rookie_snapshot.csv")[["player_id","player","rookie_season"]]

# Attach player_id to scatter
scatter = scatter.merge(
    snap,
    on=["player","rookie_season"],
    how="left",
    validate="many_to_one"
)

# Attach usage
scatter = scatter.merge(
    usage,
    left_on=["player_id","rookie_season"],
    right_on=["player_id","season"],
    how="left",
    validate="many_to_one"
)

scatter = scatter.drop(columns=["season"])

scatter.to_csv("docs/data/rookie_scatter_with_usage.csv", index=False)

print("Saved docs/data/rookie_scatter_with_usage.csv")
print(scatter[["usg_pct_y"]].describe())
