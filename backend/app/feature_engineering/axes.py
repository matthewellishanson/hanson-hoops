from __future__ import annotations

import pandas as pd


def _wavg(df: pd.DataFrame, cols: list[str], weights: list[float]) -> pd.Series:
    # Shared weighted-average helper for axis construction.
    total_w = float(sum(weights)) or 1.0
    s = pd.Series(0.0, index=df.index, dtype="float64")
    for c, w in zip(cols, weights):
        s += pd.to_numeric(df.get(c, 0.0), errors="coerce").fillna(0.0) * float(w)
    return (s / total_w).clip(0.0, 100.0)


def compute_axes(features_df: pd.DataFrame) -> pd.DataFrame:
    # Translate low-level percentiles into interpretable "style axes".
    df = features_df.copy()

    # Inverted legs where lower raw value is better.
    inv_tov = (100.0 - pd.to_numeric(df.get("TOV_PCT_PCTILE", 0.0), errors="coerce").fillna(0.0)).clip(0.0, 100.0)
    inv_pf = (100.0 - pd.to_numeric(df.get("PF_PER100_PCTILE", 0.0), errors="coerce").fillna(0.0)).clip(0.0, 100.0)

    df["AXIS_CREATION_LOAD"] = _wavg(
        df,
        ["USG_PCT_PCTILE", "AST_PCT_PCTILE"],
        [0.55, 0.45],
    ) * 0.7 + inv_tov * 0.3

    df["AXIS_SCORING_PRESSURE"] = _wavg(
        df,
        ["PTS_PER100_PCTILE", "FGA_PER100_PCTILE", "FTAR_PCTILE"],
        [0.45, 0.35, 0.20],
    )

    df["AXIS_SPACING_GRAVITY"] = _wavg(
        df,
        ["FG3A_PER100_PCTILE", "FG3_PCT_PCTILE", "TS_PCT_PCTILE"],
        [0.40, 0.35, 0.25],
    )

    df["AXIS_BALL_SECURITY"] = inv_tov

    df["AXIS_DISRUPTION"] = _wavg(
        df,
        ["STL_PER100_PCTILE", "BLK_PER100_PCTILE"],
        [0.60, 0.40],
    )

    df["AXIS_RIM_PROTECTION"] = _wavg(df, ["BLK_PER100_PCTILE"], [1.0])
    df["AXIS_REBOUNDING"] = _wavg(df, ["ORB_PCT_PCTILE", "DRB_PCT_PCTILE"], [0.45, 0.55])
    df["AXIS_DISCIPLINE"] = inv_pf

    df["AXIS_FINISHING"] = _wavg(
        df,
        ["TS_PCT_PCTILE", "FTAR_PCTILE"],
        [0.6, 0.4],
    )

    # Keep every axis on a consistent 0-100 scale for UI and scoring.
    axis_cols = [c for c in df.columns if c.startswith("AXIS_")]
    for col in axis_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).clip(0.0, 100.0).round(1)
    return df
