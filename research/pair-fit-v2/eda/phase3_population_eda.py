# %%
"""Beginner-friendly, read-only EDA for the Pair-Fit v2 training population."""

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


# %%
# Find the Pair-Fit project whether VS Code starts from the repository root,
# the pair-fit-v2 directory, or the eda directory.

working_directory = Path.cwd().resolve()

project_candidates = [
    working_directory / "research" / "pair-fit-v2",
    working_directory,
    working_directory.parent,
]

PROJECT_ROOT = next(
    (
        candidate
        for candidate in project_candidates
        if (candidate / "src" / "pair_fit_v2").exists()
        and (candidate / "cache").exists()
    ),
    None,
)

if PROJECT_ROOT is None:
    raise FileNotFoundError(
        "Could not locate research/pair-fit-v2 from the current directory."
    )

CACHE_ROOT = PROJECT_ROOT / "cache"
SRC_ROOT = PROJECT_ROOT / "src"

print("Project root:", PROJECT_ROOT)


# %%
# Load and validate the complete training population.
#
# This function verifies raw-file hashes and checks the pair data before
# returning anything. It does not change the cache.

from pair_fit_v2.phase3a_population_audit import _load_population, _history_status

rows, profiles, boundaries, evidence = _load_population(CACHE_ROOT)

pair_df = pd.DataFrame(rows)
boundary_df = pd.DataFrame(boundaries)

evidence_df = (
    pd.DataFrame.from_dict(evidence, orient="index")
    .rename_axis("target_season")
    .reset_index()
)

profile_records = []

for profile_season, players in profiles.items():
    for player_id, profile in players.items():
        profile_records.append(
            {
                "profile_season": profile_season,
                "player_id": player_id,
                **profile,
            }
        )

profile_df = pd.DataFrame(profile_records)

print(f"Pair observations: {len(pair_df):,}")
print(f"Player-season profiles: {len(profile_df):,}")
print(f"Boundary records: {len(boundary_df):,}")


# %%
# Separate the two player IDs stored in the canonical pair tuple.

if "pair" in pair_df.columns:
    pair_ids = pd.DataFrame(
        pair_df["pair"].tolist(),
        columns=["player_1_id", "player_2_id"],
        index=pair_df.index,
    )
    pair_df = pd.concat([pair_df, pair_ids], axis=1)


# %%
# Convert important analytical fields to numbers.
# errors="coerce" would turn invalid values into missing values, so we
# immediately inspect and validate the result below.

numeric_candidates = [
    "POSS",
    "NET_RATING",
    "OFF_RATING",
    "DEF_RATING",
    "base_min",
]

for column in numeric_candidates:
    if column in pair_df.columns:
        pair_df[column] = pd.to_numeric(pair_df[column], errors="coerce")


# %%
# Confirm that we reproduced the audited Phase 3A population.

assert len(pair_df) == 46_938
assert pair_df["POSS"].notna().all()
assert pair_df["NET_RATING"].notna().all()
assert pair_df["POSS"].gt(0).sum() == 46_786
assert pair_df["POSS"].eq(0).sum() == 152
assert len(profile_df) == 5_219

print("Phase 3A population checks passed.")


# %%
# Basic orientation: dimensions, columns, sample observations, and data types.

print("Shape:", pair_df.shape)
print("\nColumns:")
print(pair_df.columns.tolist())

pair_df.head()


# %%
pair_df.info()


# %%
# Missing values by field.

missing_summary = (
    pair_df.isna()
    .sum()
    .sort_values(ascending=False)
    .rename("missing_rows")
    .to_frame()
)

missing_summary["missing_share"] = (
    missing_summary["missing_rows"] / len(pair_df)
)

missing_summary.head(30)


# %%
# Keep zero-possession records in pair_df, but exclude them from target EDA.

positive_df = pair_df.loc[pair_df["POSS"] > 0].copy()
positive_df["abs_net_rating"] = positive_df["NET_RATING"].abs()

print(f"Positive-possession rows: {len(positive_df):,}")
print(f"Preserved zero-possession rows: {(pair_df['POSS'] == 0).sum():,}")


# %%
# Assign observations to possession bands.
#
# A bin is simply a range used to group numerical observations.

possession_edges = [0, 25, 50, 75, 100, 150, 300, np.inf]
possession_labels = [
    "1–24",
    "25–49",
    "50–74",
    "75–99",
    "100–149",
    "150–299",
    "300+",
]

positive_df["possession_band"] = pd.cut(
    positive_df["POSS"],
    bins=possession_edges,
    labels=possession_labels,
    right=False,
)


# %%
# Summarize target behavior within each exposure band.

band_summary = (
    positive_df.groupby("possession_band", observed=True)
    .agg(
        rows=("POSS", "size"),
        summed_possessions=("POSS", "sum"),
        median_possessions=("POSS", "median"),
        median_net_rating=("NET_RATING", "median"),
        net_rating_variance=("NET_RATING", "var"),
        median_absolute_net=("abs_net_rating", "median"),
        extreme_net_share=(
            "NET_RATING",
            lambda values: values.abs().ge(50).mean(),
        ),
    )
)

band_summary["row_share"] = band_summary["rows"] / len(positive_df)
band_summary["possession_share"] = (
    band_summary["summed_possessions"] / positive_df["POSS"].sum()
)

band_summary
band_summary.rename_axis("possession_band").reset_index().to_csv(
    PROJECT_ROOT / "band_summary.csv",
    index=False,
)

# %%
# Compare season-level population and target distributions.

season_summary = (
    positive_df.groupby("season")
    .agg(
        rows=("POSS", "size"),
        median_possessions=("POSS", "median"),
        mean_net_rating=("NET_RATING", "mean"),
        median_net_rating=("NET_RATING", "median"),
        net_rating_variance=("NET_RATING", "var"),
        median_absolute_net=("abs_net_rating", "median"),
    )
)

zero_rows_by_season = (
    pair_df.assign(zero_possession=pair_df["POSS"].eq(0))
    .groupby("season")["zero_possession"]
    .sum()
)

season_summary["zero_possession_rows"] = zero_rows_by_season
season_summary
season_summary.rename_axis("season").reset_index().to_csv(
    PROJECT_ROOT / "season_summary.csv",
    index=False,
)

season_player_counts = {}

for season, season_rows in positive_df.groupby("season"):
    all_player_ids = (
        set(season_rows["player_1_id"])
        | set(season_rows["player_2_id"])
    )
    season_player_counts[season] = len(all_player_ids)

season_summary["unique_players"] = pd.Series(season_player_counts)

# %%
# Plot 1: possession distribution.
#
# log1p means log(1 + POSS). It compresses the long right tail so both
# low- and high-possession observations remain visible.

sns.set_theme(style="whitegrid")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

sns.histplot(
    data=positive_df,
    x="POSS",
    bins=60,
    ax=axes[0],
)
axes[0].set_title("Pair Possession Distribution")
axes[0].set_xlabel("Shared possessions")

axes[0].axvline(
    100,
    color="red",
    linestyle="--",
    label="100-possession candidate",
)
axes[0].legend()

sns.histplot(
    x=np.log1p(positive_df["POSS"]),
    bins=60,
    ax=axes[1],
)
axes[1].set_title("Pair Possessions on a Logarithmic Scale")
axes[1].set_xlabel("log(1 + shared possessions)")

axes[1].axvline(
    np.log1p(100),
    color="red",
    linestyle="--",
    label="100-possession candidate",
)
axes[1].legend()

plt.tight_layout()
plt.savefig(PROJECT_ROOT / "histogram_possession_distribution.png")



# %%
# Plot 2: net-rating distribution by possession band.
#
# showfliers=False hides individual outlier dots visually, but it does not
# remove those observations from the data or the summary calculations.

plt.figure(figsize=(12, 6))

sns.boxplot(
    data=positive_df,
    x="possession_band",
    y="NET_RATING",
    showfliers=False,
)

plt.axhline(0, color="black", linewidth=1)
plt.title("Net Rating by Shared-Possession Band")
plt.xlabel("Shared-possession band")
plt.ylabel("Team net rating while the pair shared the court")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "boxplot_net_rating_by_possession_band.png")


# %%
# Plot 3: exposure versus target extremity.
#
# Darker hexagons represent areas containing more observations.

plt.figure(figsize=(11, 6))

plt.hexbin(
    positive_df["POSS"],
    positive_df["abs_net_rating"],
    gridsize=45,
    xscale="log",
    bins="log",
    mincnt=1,
    cmap="viridis",
)

plt.colorbar(label="Log observation count")
plt.title("Are Extreme Net Ratings Concentrated at Low Exposure?")
plt.xlabel("Shared possessions — logarithmic scale")
plt.ylabel("Absolute net rating")
plt.tight_layout()
plt.savefig(PROJECT_ROOT / "hexbin_exposure_vs_extremity.png")


# %%
# Inspect endpoint warnings and season-level evidence.

boundary_df.head(20)


# %%
evidence_df

# %%
evidence_df.to_csv(PROJECT_ROOT / "evidence_df.csv", index=False)

# %%

# Mark pairs as eligible based on possession thresholds.
pair_df["eligible_poss_75"] = pair_df["POSS"] >= 75
pair_df["eligible_poss_100"] = pair_df["POSS"] >= 100
pair_df["eligible_poss_150"] = pair_df["POSS"] >= 150

# %%
pair_df["history_1yr"] = [
    _history_status(row, profiles, lookback=1)[0]
    for row in rows
]

pair_df["history_3yr"] = [
    _history_status(row, profiles, lookback=3)[0]
    for row in rows
]

pair_df["history_5yr"] = [
    _history_status(row, profiles, lookback=5)[0]
    for row in rows
]
# %%
eligible_150_df = pair_df.loc[pair_df["POSS"] >= 150].copy()

print(f"Rows at POSS >= 150: {len(eligible_150_df):,}")
print(
    "Row retention:",
    f"{len(eligible_150_df) / pair_df['POSS'].gt(0).sum():.2%}",
)
print(
    "Possession retention:",
    f"{eligible_150_df['POSS'].sum() / positive_df['POSS'].sum():.2%}",
)

# %%
def summarize_history(data, status_column, policy_label):
    result = (
        data.groupby(status_column, dropna=False)
        .agg(
            rows=("POSS", "size"),
            summed_possessions=("POSS", "sum"),
            summed_minutes=("base_min", "sum"),
            median_possessions=("POSS", "median"),
            net_rating_variance=("NET_RATING", "var"),
        )
    )

    result["row_share"] = result["rows"] / len(data)
    result["possession_share"] = (
        result["summed_possessions"] / data["POSS"].sum()
    )
    result["minute_share"] = (
        result["summed_minutes"] / data["base_min"].sum()
    )

    result.insert(0, "policy", policy_label)

    return (
        result.rename_axis("history_status")
        .reset_index()
    )


history_150_summary = pd.concat(
    [
        summarize_history(
            eligible_150_df,
            "history_1yr",
            "Strict previous season",
        ),
        summarize_history(
            eligible_150_df,
            "history_3yr",
            "Most recent within 3 years",
        ),
        summarize_history(
            eligible_150_df,
            "history_5yr",
            "Most recent within 5 years",
        ),
    ],
    ignore_index=True,
)

history_150_summary

# %%
history_150_by_season = (
    pd.crosstab(
        eligible_150_df["season"],
        eligible_150_df["history_3yr"],
        normalize="index",
    )
    * 100
)

history_150_by_season
history_150_by_season.to_csv(PROJECT_ROOT / "history_coverage_poss_150_by_season.csv")

# %%
history_150_by_season.plot(
    kind="bar",
    stacked=True,
    figsize=(12, 6),
    colormap="viridis",
)

plt.title(
    "Three-Year Player-History Coverage at POSS ≥ 150"
)
plt.xlabel("Target season")
plt.ylabel("Share of eligible pair rows (%)")
plt.legend(title="History status")
plt.tight_layout()

plt.savefig(
    PROJECT_ROOT / "history_coverage_poss_150.png",
    dpi=150,
    bbox_inches="tight",
)
# %%
